"""modelFactory/directional_data_research/short_interest.py — Famille short.

Priorité 4 du plan (short interest). Sources (cache FINRA, 400 symboles) :
- ``artifacts/finra_short_volume/short_sale_volume_400.parquet`` : short volume
  QUOTIDIEN (date, symbol, short_volume, total_volume) — PIT via shift 1 jour ;
- ``artifacts/finra_short_volume/short_interest_400.parquet`` : short interest
  BIMENSUEL (settlement_date, publication_date, days_to_cover, change_percent,
  current_short_position, average_daily_volume) — PIT via publication_date
  (disponible à J uniquement si publication_date <= J, merge_asof backward).

Features à J :
- ``short_ratio_1d/5d/10d`` : ratio short_volume/total_volume (D-1, glissant) ;
- ``short_vw_ratio_5d/20d`` : ratio pondéré par le volume ;
- ``short_days_to_cover``, ``short_interest_change_pct``, ``short_interest_to_adv``
  (bimensuel, PIT).

Discipline : harnais de séparabilité AVANT tout modèle.

Usage :
    python -m modelFactory.directional_data_research.short_interest --batch-id ...
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.directional_data_research.harness import (
    analyze_features,
    assemble_pool,
    format_report,
)
from modelFactory.global_direction.config import resolve_global_direction_batch_id

LOGGER = logging.getLogger(__name__)

_SHORT_ROOT = Path("artifacts/finra_short_volume")

_SHORT_FEATURES = [
    "short_ratio_1d", "short_ratio_5d", "short_ratio_10d",
    "short_vw_ratio_5d", "short_vw_ratio_20d",
    "short_days_to_cover", "short_interest_change_pct", "short_interest_to_adv",
]


def load_daily_short_volume() -> pd.DataFrame:
    df = pd.read_parquet(_SHORT_ROOT / "short_sale_volume_400.parquet")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    for c in ["short_volume", "total_volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date", "symbol", "short_volume", "total_volume"])
    df["short_ratio"] = df["short_volume"] / df["total_volume"].replace(0, np.nan)
    return df[["symbol", "date", "short_ratio", "short_volume", "total_volume"]]


def load_short_interest() -> pd.DataFrame:
    df = pd.read_parquet(_SHORT_ROOT / "short_interest_400.parquet")
    df["publication_date"] = pd.to_datetime(df["publication_date"], errors="coerce").dt.normalize()
    df["settlement_date"] = pd.to_datetime(df["settlement_date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    for c in ["days_to_cover", "change_percent", "current_short_position", "average_daily_volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["short_interest_to_adv"] = df["current_short_position"] / df["average_daily_volume"].replace(0, np.nan)
    return df.rename(columns={
        "days_to_cover": "short_days_to_cover",
        "change_percent": "short_interest_change_pct",
    })[["symbol", "publication_date", "short_days_to_cover",
        "short_interest_change_pct", "short_interest_to_adv"]]


def build_daily_features(pool: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Features short volume quotidien (PIT : valeur de D-1)."""
    out = pool[["date", "symbol"]].copy()
    if daily.empty:
        for c in ["short_ratio_1d", "short_ratio_5d", "short_ratio_10d",
                  "short_vw_ratio_5d", "short_vw_ratio_20d"]:
            out[c] = np.nan
        return out
    merged = out.merge(daily, on=["date", "symbol"], how="left")
    merged = merged.sort_values(["symbol", "date"]).reset_index(drop=True)
    # PIT : le short volume de D-1 (shift intra-symbole sur les dates de trading)
    for c in ["short_ratio", "short_volume", "total_volume"]:
        merged[c] = merged.groupby("symbol")[c].shift(1)
    grp = merged.groupby("symbol")
    merged["short_ratio_1d"] = merged["short_ratio"]
    merged["short_ratio_5d"] = grp["short_ratio"].transform(lambda s: s.rolling(5, min_periods=1).mean())
    merged["short_ratio_10d"] = grp["short_ratio"].transform(lambda s: s.rolling(10, min_periods=1).mean())
    merged["short_vw_ratio_5d"] = (
        grp["short_volume"].transform(lambda s: s.rolling(5, min_periods=1).sum())
        / grp["total_volume"].transform(lambda s: s.rolling(5, min_periods=1).sum()).replace(0, np.nan)
    )
    merged["short_vw_ratio_20d"] = (
        grp["short_volume"].transform(lambda s: s.rolling(20, min_periods=1).sum())
        / grp["total_volume"].transform(lambda s: s.rolling(20, min_periods=1).sum()).replace(0, np.nan)
    )
    return merged[["date", "symbol", "short_ratio_1d", "short_ratio_5d", "short_ratio_10d",
                   "short_vw_ratio_5d", "short_vw_ratio_20d"]]


def build_short_interest_features(pool: pd.DataFrame, si: pd.DataFrame) -> pd.DataFrame:
    """Features short interest bimensuel (PIT via publication_date, merge_asof backward)."""
    out = pool[["date", "symbol"]].copy()
    if si.empty:
        for c in ["short_days_to_cover", "short_interest_change_pct", "short_interest_to_adv"]:
            out[c] = np.nan
        return out
    si = si.dropna(subset=["publication_date"]).sort_values("publication_date")
    parts: list[pd.DataFrame] = []
    for sym, g in out.groupby("symbol"):
        s = si[si["symbol"] == sym].drop(columns=["symbol"]).sort_values("publication_date")
        if s.empty:
            row = g[["date", "symbol"]].copy()
            for c in ["short_days_to_cover", "short_interest_change_pct", "short_interest_to_adv"]:
                row[c] = np.nan
            parts.append(row)
            continue
        m = pd.merge_asof(
            g.sort_values("date"), s,
            left_on="date", right_on="publication_date", direction="backward",
        )
        parts.append(m[["date", "symbol", "short_days_to_cover", "short_interest_change_pct",
                        "short_interest_to_adv"]])
    return pd.concat(parts, ignore_index=True) if parts else out


def main() -> None:
    parser = argparse.ArgumentParser(description="Séparabilité famille short (pool Oracle TOP20%).")
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
    pool = assemble_pool(engine, batch_id, start_date=args.start_date, end_date=args.end_date,
                         oracle_run=args.oracle_run)
    if pool.empty:
        raise SystemExit("Pool Oracle vide.")
    symbols = list(pool["symbol"].unique())
    if args.symbols:
        symbols = symbols[: args.symbols]
        pool = pool[pool["symbol"].isin(symbols)]
    LOGGER.info("pool Oracle top20%% : %d lignes, %d dates", len(pool), pool["date"].nunique())

    daily = load_daily_short_volume()
    si = load_short_interest()
    f_daily = build_daily_features(pool, daily)
    f_si = build_short_interest_features(pool, si)
    merged = pool.merge(f_daily, on=["date", "symbol"], how="left")
    merged = merged.merge(f_si, on=["date", "symbol"], how="left")
    LOGGER.info("features short fusionnées : %d lignes", len(merged))

    result = analyze_features(merged, _SHORT_FEATURES)
    out_path = Path("artifacts/directional_data_research_short.csv")
    result.to_csv(out_path, index=False)
    print(f"→ CSV : {out_path}")
    print(format_report(result, top_n=args.top_n))


if __name__ == "__main__":
    main()
