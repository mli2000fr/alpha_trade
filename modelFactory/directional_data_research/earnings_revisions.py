"""modelFactory/directional_data_research/earnings_revisions.py — Famille estimate/earnings.

Première famille de données signées testée (priorité 1 du plan). Source :
``stock_fundamentals_daily`` (Yahoo fundamentals). Features à J :

- ``est_revision`` = eps_estimate_next / eps_estimate_current − 1 (révision signée) ;
- ``est_revision_20d`` = variation de ``est_revision`` sur 20 jours ouvrés
  (momentum de révision — signal « événementiel » signé, PIT) ;
- ``eps_estimate_current`` / ``eps_estimate_next`` (niveaux) ;
- ``eps_growth_yoy`` / ``revenue_growth_yoy`` (croissance signée) ;
- ``eps_to_price`` (earnings yield = eps / close).

Discipline : harnais de séparabilité AVANT tout modèle (IC décile, AUC
D1-D5 vs D6-D10, AUC D1-D3 vs D8-D10, stabilité du signe par fold, direction vs
amplitude). On ne passe au modèle multivarié QUE si plusieurs features montrent
un signal directionnel OOS stable.

Usage :
    python -m modelFactory.directional_data_research.earnings_revisions --batch-id ...
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from modelFactory.directional_data_research.harness import (
    analyze_features,
    assemble_pool,
    format_report,
)
from modelFactory.global_direction.config import resolve_global_direction_batch_id
from modelFactory.oracle.train import get_universe_symbols

LOGGER = logging.getLogger(__name__)

_EARNINGS_COLS = [
    "symbol", "trade_date",
    "eps_estimate_current", "eps_estimate_next",
    "eps_growth_yoy", "revenue_growth_yoy", "eps",
]


def load_earnings_features(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Charge les fondamentaux earnings/estimates depuis ``stock_fundamentals_daily``."""
    if not symbols:
        return pd.DataFrame()
    cols = ", ".join(_EARNINGS_COLS)
    query = text(
        f"SELECT {cols} FROM stock_fundamentals_daily "
        "WHERE symbol IN :syms AND trade_date >= :start AND trade_date <= :end"
    ).bindparams(bindparam("syms", expanding=True))
    with engine.connect() as conn:
        try:
            df = pd.read_sql(query, conn, params={"syms": symbols, "start": start_date, "end": end_date})
        except Exception:
            return pd.DataFrame()
    if df.empty:
        return df
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df = df.dropna(subset=["trade_date", "symbol"])
    for c in ["eps_estimate_current", "eps_estimate_next", "eps_growth_yoy",
              "revenue_growth_yoy", "eps"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def derive_earnings_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Dérive les features signées (révision + momentum) depuis les fondamentaux."""
    out = raw.copy()
    out = out.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    # révision = next / current - 1 (signée)
    cur = out["eps_estimate_current"].astype(float)
    nxt = out["eps_estimate_next"].astype(float)
    out["est_revision"] = np.where(cur.abs() > 1e-8, (nxt / cur.replace(0, np.nan)) - 1.0, np.nan)
    out.loc[out["eps_estimate_current"].isna() | out["eps_estimate_next"].isna(), "est_revision"] = np.nan
    # momentum de révision sur 20 jours (PIT, intra-symbole)
    out["est_revision_20d"] = out.groupby("symbol")["est_revision"].diff(20)
    # earnings yield
    out["eps_to_price"] = out["eps"].astype(float)
    return out


def merge_into_pool(pool: pd.DataFrame, feats: pd.DataFrame, price_map: pd.DataFrame) -> pd.DataFrame:
    """Fusionne les features earnings dans le pool (ffill intra-symbole)."""
    if feats.empty:
        return pool
    f = feats.rename(columns={"trade_date": "date"})
    # eps_to_price nécessite le close
    if not price_map.empty and "eps_to_price" in f.columns:
        f = f.merge(price_map, on=["date", "symbol"], how="left")
        f["eps_to_price"] = np.where(f["close"].fillna(0).abs() > 1e-8,
                                     f["eps"] / f["close"].replace(0, np.nan), np.nan)
        f = f.drop(columns=["eps", "close"])
    merged = pool.merge(
        f[["date", "symbol", "est_revision", "est_revision_20d",
           "eps_estimate_current", "eps_estimate_next",
           "eps_growth_yoy", "revenue_growth_yoy", "eps_to_price"]],
        on=["date", "symbol"], how="left",
    )
    # ffill intra-symbole (données dispo à J, PIT)
    merged = merged.sort_values(["symbol", "date"])
    for c in ["est_revision", "est_revision_20d", "eps_estimate_current",
              "eps_estimate_next", "eps_growth_yoy", "revenue_growth_yoy", "eps_to_price"]:
        merged[c] = merged.groupby("symbol")[c].ffill()
    return merged


def load_close_prices(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Close par (date, symbol) depuis stock_bars_daily (pour eps_to_price)."""
    query = text(
        "SELECT `date`, symbol, COALESCE(adj_close, close) AS close "
        "FROM stock_bars_daily WHERE symbol IN :syms AND `date` >= :start AND `date` <= :end"
    ).bindparams(bindparam("syms", expanding=True))
    with engine.connect() as conn:
        try:
            df = pd.read_sql(query, conn, params={"syms": symbols, "start": start_date, "end": end_date})
        except Exception:
            return pd.DataFrame()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.dropna(subset=["date", "symbol", "close"]).drop_duplicates(["date", "symbol"], keep="last")


_EARNINGS_FEATURES = [
    "est_revision", "est_revision_20d", "eps_estimate_current", "eps_estimate_next",
    "eps_growth_yoy", "revenue_growth_yoy", "eps_to_price",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Séparabilité famille estimate/earnings revisions (pool Oracle TOP20%).")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-05-29")
    parser.add_argument("--symbols", type=int, default=None)
    parser.add_argument("--oracle-run", default=None)
    parser.add_argument("--top-n", type=int, default=12)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")

    engine = get_sqlalchemy_engine()
    symbols = get_universe_symbols(engine, batch_id, 20)
    if args.symbols:
        symbols = symbols[: args.symbols]

    pool = assemble_pool(engine, batch_id, start_date=args.start_date, end_date=args.end_date,
                         oracle_run=args.oracle_run)
    if pool.empty:
        raise SystemExit("Pool Oracle vide.")
    LOGGER.info("pool Oracle top20%% : %d lignes, %d dates", len(pool), pool["date"].nunique())

    raw = load_earnings_features(engine, symbols, args.start_date, args.end_date)
    feats = derive_earnings_features(raw)
    price_map = load_close_prices(engine, symbols, args.start_date, args.end_date)
    merged = merge_into_pool(pool, feats, price_map)
    LOGGER.info("features earnings fusionnées : %d lignes", len(merged))

    avail = [c for c in _EARNINGS_FEATURES if c in merged.columns]
    result = analyze_features(merged, avail)
    out_path = Path("artifacts/directional_data_research_earnings.csv")
    result.to_csv(out_path, index=False)
    print(f"→ CSV : {out_path}")
    print(format_report(result, top_n=args.top_n))


if __name__ == "__main__":
    main()
