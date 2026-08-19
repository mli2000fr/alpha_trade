"""modelFactory/oracle/fundamental_diagnostic.py — S6.6-A : matière première directionnelle.

Teste si les données FONDAMENTALES + SENTIMENT (par nature directionnelles)
contiennent un signal H20 que les features techniques n'ont pas :

- **eps_surprise** / **rev_surprise** (PIT strict : earnings_date ≤ D) ;
- **eps_growth_yoy**, **revenue_growth_yoy**, **forward_pe**, **peg_ratio**, **roe**, **net_margin** ;
- **sentiment_net_mean_5d/20d**, **major_event_flag**.

Deux diagnostics :
1. **direction** : Spearman intra-date avec future_return vs |future_return| ;
2. **détection de faux TOP catastrophiques** : parmi les candidats B25 TOP 10 %
   (global_rank_20 ≥ 0.90), AUC de la feature pour séparer « Oracle réel 0-20 % »
   (catastrophique) du reste.

Usage :
    python -m modelFactory.oracle.fundamental_diagnostic --batch-id model-factory-20260811223551-ef2cd0
"""
from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.config import resolve_oracle_batch_id
from modelFactory.oracle.dataset import (
    TARGET_COL,
    load_global_rank_feature,
    load_oracle_targets,
)

LOGGER = logging.getLogger(__name__)


def _cs_spearman(df: pd.DataFrame, feat: str, target: str, min_universe: int = 30) -> float | None:
    vals: list[float] = []
    for _, g in df.groupby("date"):
        if len(g) < min_universe:
            continue
        c = g[feat].corr(g[target], method="spearman")
        if np.isfinite(c):
            vals.append(c)
    return float(np.mean(vals)) if vals else None


def _auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    """AUC Mann-Whitney (sans scikit-learn)."""
    y = np.asarray(y_true, dtype=float)
    s = np.asarray(y_score, dtype=float)
    mask = np.isfinite(s) & np.isfinite(y)
    y, s = y[mask], s[mask]
    pos = y == 1.0
    neg = y == 0.0
    if pos.sum() == 0 or neg.sum() == 0:
        return None
    ranks = pd.Series(s).rank(method="average").to_numpy()
    r_pos = ranks[pos].sum()
    auc = (r_pos - pos.sum() * (pos.sum() + 1) / 2.0) / (pos.sum() * neg.sum())
    return float(auc)


def _load_earnings(engine, symbols: list[str]) -> pd.DataFrame:
    syms = ",".join(f":s{i}" for i in range(len(symbols)))
    q = text(f"""
        SELECT symbol, earnings_date, eps_actual, eps_estimate, revenue_actual, revenue_estimate
        FROM stock_earnings_calendar
        WHERE symbol IN ({syms}) AND eps_actual IS NOT NULL AND eps_estimate IS NOT NULL
    """)
    params = {f"s{i}": s for i, s in enumerate(symbols)}
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params=params, parse_dates=["earnings_date"])
    eps = pd.to_numeric(df["eps_actual"], errors="coerce")
    est = pd.to_numeric(df["eps_estimate"], errors="coerce")
    df["eps_surprise"] = (eps - est) / est.abs().clip(lower=1e-6)
    rev = pd.to_numeric(df["revenue_actual"], errors="coerce")
    rev_est = pd.to_numeric(df["revenue_estimate"], errors="coerce")
    df["rev_surprise"] = (rev - rev_est) / rev_est.abs().clip(lower=1e-6)
    df = df.dropna(subset=["eps_surprise"])
    df = df.sort_values(["symbol", "earnings_date"])
    return df[["symbol", "earnings_date", "eps_surprise", "rev_surprise"]]


def _load_fundamentals(engine, symbols: list[str]) -> pd.DataFrame:
    syms = ",".join(f":s{i}" for i in range(len(symbols)))
    q = text(f"""
        SELECT symbol, trade_date, eps_growth_yoy, revenue_growth_yoy, forward_pe, peg_ratio,
               pe_ratio, ev_to_ebitda, roe, roa, net_margin, operating_margin
        FROM stock_fundamentals_daily
        WHERE symbol IN ({syms})
    """)
    params = {f"s{i}": s for i, s in enumerate(symbols)}
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params=params, parse_dates=["trade_date"])
    return df


def _load_sentiment(engine, symbols: list[str]) -> pd.DataFrame:
    syms = ",".join(f":s{i}" for i in range(len(symbols)))
    q = text(f"""
        SELECT symbol, trade_date, sentiment_net_mean_5d, sentiment_net_mean_20d,
               news_count_5d, news_count_20d, major_event_flag
        FROM ticker_daily_sentiment_features
        WHERE symbol IN ({syms})
    """)
    params = {f"s{i}": s for i, s in enumerate(symbols)}
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params=params, parse_dates=["trade_date"])
    return df


def run_fundamental_diagnostic(batch_id: str, *, horizon: int = 20, start: str = "2022-01-01") -> dict[str, Any]:
    engine = get_sqlalchemy_engine()
    from modelFactory.oracle.train import get_universe_symbols
    symbols = get_universe_symbols(engine, batch_id, horizon)
    LOGGER.info("universe=%d symbols — chargement des sources...", len(symbols))

    ranks = load_global_rank_feature(engine, batch_id)
    targets = load_oracle_targets(engine, batch_id, horizon)
    earn = _load_earnings(engine, symbols)
    fund = _load_fundamentals(engine, symbols)
    sent = _load_sentiment(engine, symbols)
    LOGGER.info("earnings=%d fundamentals=%d sentiment=%d", len(earn), len(fund), len(sent))

    df = ranks.merge(targets, left_on=["date", "symbol"], right_on=["prediction_date", "symbol"], how="inner")
    df = df[df["date"] >= pd.Timestamp(start)].copy()
    df = df.merge(fund, left_on=["date", "symbol"], right_on=["trade_date", "symbol"], how="left")
    df = df.merge(sent, left_on=["date", "symbol"], right_on=["trade_date", "symbol"], how="left")
    df = df.drop(columns=[c for c in ("prediction_date", "trade_date_x", "trade_date_y") if c in df.columns])

    # As-of join earnings PIT : dernier earnings_date ≤ date (searchsorted par symbole)
    eps_arr = np.full(len(df), np.nan)
    rev_arr = np.full(len(df), np.nan)
    earn_by_sym = {s: g.sort_values("earnings_date") for s, g in earn.groupby("symbol")}
    for sym, g in df.groupby("symbol"):
        e = earn_by_sym.get(sym)
        if e is None or e.empty:
            continue
        edates = e["earnings_date"].to_numpy()
        idx = np.searchsorted(edates, g["date"].to_numpy(), side="right") - 1
        valid = idx >= 0
        eps_arr[g.index[valid]] = e["eps_surprise"].to_numpy()[idx[valid]]
        rev_arr[g.index[valid]] = e["rev_surprise"].to_numpy()[idx[valid]]
    df["eps_surprise"] = eps_arr
    df["rev_surprise"] = rev_arr

    df["abs_return"] = df["future_return"].abs()
    # Candidats B25 TOP 10 %
    df["b25_top"] = df["global_rank_20"] >= 0.90
    df["cat20"] = ((df["oracle_pct_rank"] < 0.20).astype(int))
    df["cat10"] = ((df["oracle_pct_rank"] < 0.10).astype(int))

    feat_cols = ["eps_surprise", "rev_surprise", "eps_growth_yoy", "revenue_growth_yoy",
                 "forward_pe", "peg_ratio", "pe_ratio", "ev_to_ebitda", "roe", "roa",
                 "net_margin", "operating_margin", "sentiment_net_mean_5d", "sentiment_net_mean_20d",
                 "news_count_5d", "news_count_20d", "major_event_flag"]

    top = df[df["b25_top"]]
    LOGGER.info("dates=%d rows=%d | B25 TOP candidats=%d (cat20=%.1f%% cat10=%.1f%%)",
                df["date"].nunique(), len(df), len(top),
                100 * top["cat20"].mean(), 100 * top["cat10"].mean())

    rows: list[dict[str, Any]] = []
    for feat in feat_cols:
        if feat not in df.columns or df[feat].notna().sum() < 100:
            continue
        r: dict[str, Any] = {"feature": feat}
        r["corr_ret"] = _cs_spearman(df, feat, "future_return")
        r["corr_abs"] = _cs_spearman(df, feat, "abs_return")
        # AUC détection de catastrophique parmi B25 TOP
        sub = top.dropna(subset=[feat])
        r["auc_cat20"] = _auc(sub["cat20"].to_numpy(), sub[feat].to_numpy()) if len(sub) > 200 else None
        r["auc_cat10"] = _auc(sub["cat10"].to_numpy(), sub[feat].to_numpy()) if len(sub) > 200 else None
        # direction de la séparation : mean feature pour cat20 vs non-cat20
        if r["auc_cat20"] is not None and len(sub) > 200:
            r["mean_cat20"] = float(sub.loc[sub["cat20"] == 1, feat].mean())
            r["mean_ok"] = float(sub.loc[sub["cat20"] == 0, feat].mean())
        else:
            r["mean_cat20"] = r["mean_ok"] = None
        rows.append(r)

    out = pd.DataFrame(rows)
    out["auc_dev20"] = (out["auc_cat20"] - 0.5).abs()
    out["auc_dev10"] = (out["auc_cat10"] - 0.5).abs()
    out = out.sort_values("auc_dev20", ascending=False)
    return {"status": "completed", "features": out.to_dict("records"),
            "b25_top_cat20_pct": float(100 * top["cat20"].mean()),
            "b25_top_cat10_pct": float(100 * top["cat10"].mean())}


def format_report(report: dict[str, Any]) -> str:
    if report.get("status") != "completed":
        return f"fundamental_diagnostic: {report}"
    df = pd.DataFrame(report["features"])
    lines = ["=== S6.6-A — MATIÈRE PREMIÈRE DIRECTIONNELLE (fondamental + sentiment) ==="]
    lines.append(f"B25 TOP candidats : cat20 (Oracle<20%) = {report['b25_top_cat20_pct']:.1f}% | cat10 (<10%) = {report['b25_top_cat10_pct']:.1f}%")
    hdr = f"{'feature':<24} {'corr_ret':>9} {'corr_abs':>9} {'AUCcat20':>8} {'dev20':>6} {'AUCcat10':>8} {'dev10':>6}"
    lines.append(hdr)
    for _, r in df.head(17).iterrows():
        auc20 = r['auc_cat20'] if pd.notna(r['auc_cat20']) else float('nan')
        auc10 = r['auc_cat10'] if pd.notna(r['auc_cat10']) else float('nan')
        lines.append(
            f"{r['feature']:<24} {r['corr_ret']:>9.3f} {r['corr_abs']:>9.3f} "
            f"{auc20:>8.3f} {abs(auc20-0.5):>6.3f} {auc10:>8.3f} {abs(auc10-0.5):>6.3f}"
        )
    lines.append("\nLecture : corr_ret > 0.05 (direction) et dev20 > 0.05 (détection catastrophique) sont les signaux recherchés.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostic directionnel fondamental + sentiment (S6.6-A).")
    parser.add_argument("--batch-id", default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    batch_id = args.batch_id or resolve_oracle_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    report = run_fundamental_diagnostic(batch_id)
    import os
    out = "artifacts/models/oracle/fundamental_diagnostic_report.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"→ rapport sauvegardé : {out}")
    print(format_report(report))


if __name__ == "__main__":
    main()
