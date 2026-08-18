"""modelFactory/oracle/directional_features.py — Bloc de features DIRECTIONNELLES (S6.5).

Suite au diagnostic : les 160 features expert encodent l'amplitude (corr_abs≈0.28)
mais quasi aucune direction (corr_ret≈0.03). Ce module construit un petit bloc de
features SIGNÉES candidates et mesure leur directionnalité cross-sectionnelle :

- retours signés (1/3/5/10/20/60/120j) ;
- position de tendance (close/SMA − 1, croisements, pente signée) ;
- force relative vs SPY (retour signé excédentaire) ;
- volume directionnel (volume des jours de hausse vs baisse) ;
- breakout/breakdown (distance signée aux plus hauts/bas 20/60j).

Diagnostic : Spearman intra-date avec future_return, |future_return|,
oracle_top10, oracle_bottom10 — même méthodologie que feature_diagnostic.

Usage :
    python -m modelFactory.oracle.directional_features --batch-id model-factory-20260811223551-ef2cd0
"""
from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_benchmark_bars, load_universe_bars
from modelFactory.oracle.config import resolve_oracle_batch_id
from modelFactory.oracle.dataset import BOTTOM_TARGET_COL, TARGET_COL, load_oracle_targets

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


def build_directional_features(engine, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    warmup_start = (pd.Timestamp(start_date) - pd.Timedelta(days=1100)).date().isoformat()
    bars = load_universe_bars(engine, symbols, start_date=warmup_start, end_date=end_date)
    spy = load_benchmark_bars(engine, "SPY", start_date=warmup_start, end_date=end_date)
    if bars.empty:
        return pd.DataFrame()

    bars = bars.sort_values(["symbol", "date"])
    spy_s = spy.sort_values("date").set_index("date")["adj_close"].astype(float)
    spy_ret = pd.DataFrame({
        "spy_ret_20": spy_s.pct_change(20),
        "spy_ret_60": spy_s.pct_change(60),
        "spy_ret_120": spy_s.pct_change(120),
    }).reset_index()

    parts: list[pd.DataFrame] = []
    for sym, g in bars.groupby("symbol"):
        g = g.sort_values("date").reset_index(drop=True)
        c = g["adj_close"].astype(float)
        v = g["volume"].astype(float)
        ret1 = c.pct_change(1)

        sma20 = c.rolling(20).mean()
        sma50 = c.rolling(50).mean()
        sma200 = c.rolling(200).mean()

        up = ret1 > 0
        up_vol_20 = v.where(up, 0.0).rolling(20).sum()
        down_vol_20 = v.where(~up, 0.0).rolling(20).sum()

        out = pd.DataFrame({
            "date": g["date"].values,
            "symbol": sym,
            "ret_1d": ret1,
            "ret_3d": c.pct_change(3),
            "ret_5d": c.pct_change(5),
            "ret_10d": c.pct_change(10),
            "ret_20d": c.pct_change(20),
            "ret_60d": c.pct_change(60),
            "ret_120d": c.pct_change(120),
            "close_to_sma20": c / sma20 - 1.0,
            "close_to_sma50": c / sma50 - 1.0,
            "close_to_sma200": c / sma200 - 1.0,
            "sma20_above_sma50": (sma20 > sma50).astype(float),
            "sma50_above_sma200": (sma50 > sma200).astype(float),
            "sma20_slope": sma20.pct_change(5),
            "sma50_slope": sma50.pct_change(5),
            "up_vol_ratio_20": up_vol_20 / (up_vol_20 + down_vol_20 + 1e-9),
            "dist_high_20": c / c.rolling(20).max() - 1.0,
            "dist_low_20": c / c.rolling(20).min() - 1.0,
            "dist_high_60": c / c.rolling(60).max() - 1.0,
            "dist_low_60": c / c.rolling(60).min() - 1.0,
        })
        parts.append(out)

    df = pd.concat(parts, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.merge(spy_ret, on="date", how="left")
    df["rs_20"] = df["ret_20d"] - df["spy_ret_20"]
    df["rs_60"] = df["ret_60d"] - df["spy_ret_60"]
    df["rs_120"] = df["ret_120d"] - df["spy_ret_120"]
    df = df.drop(columns=["spy_ret_20", "spy_ret_60", "spy_ret_120"])
    return df


def run_directional_diagnostic(batch_id: str, *, horizon: int = 20, start: str = "2022-01-01") -> dict[str, Any]:
    engine = get_sqlalchemy_engine()
    from modelFactory.oracle.train import get_universe_symbols

    symbols = get_universe_symbols(engine, batch_id, horizon)
    LOGGER.info("universe=%d symbols — build directional features...", len(symbols))
    feats = build_directional_features(engine, symbols, start_date="2020-01-01", end_date="2026-05-29")
    targets = load_oracle_targets(engine, batch_id, horizon)

    df = feats.merge(
        targets[["prediction_date", "symbol", "future_return", TARGET_COL, BOTTOM_TARGET_COL, "oracle_pct_rank"]],
        left_on=["date", "symbol"], right_on=["prediction_date", "symbol"], how="inner",
    )
    df = df[df["date"] >= pd.Timestamp(start)].copy()
    df["abs_return"] = df["future_return"].abs()
    LOGGER.info("dates=%d rows=%d features=%d", df["date"].nunique(), len(df), len(feats.columns) - 2)

    feat_cols = [c for c in feats.columns if c not in ("date", "symbol")]
    rows: list[dict[str, Any]] = []
    for feat in feat_cols:
        rows.append({
            "feature": feat,
            "corr_ret": _cs_spearman(df, feat, "future_return"),
            "corr_abs": _cs_spearman(df, feat, "abs_return"),
            "corr_top": _cs_spearman(df, feat, TARGET_COL),
            "corr_bottom": _cs_spearman(df, feat, BOTTOM_TARGET_COL),
        })
    out = pd.DataFrame(rows)
    out["sep"] = out["corr_top"] - out["corr_bottom"]
    out["dir_ratio"] = out["corr_ret"].abs() / (out["corr_abs"].abs() + 1e-6)
    return {
        "status": "completed",
        "features": out.sort_values("sep", ascending=False).to_dict("records"),
    }


def format_report(report: dict[str, Any]) -> str:
    if report.get("status") != "completed":
        return f"directional_features: {report}"
    df = pd.DataFrame(report["features"])
    lines = ["=== FEATURES DIRECTIONNELLES — direction vs magnitude (Spearman intra-date) ==="]
    hdr = f"{'feature':<22} {'corr_ret':>9} {'corr_abs':>9} {'corr_top':>9} {'corr_bot':>9} {'sep':>8} {'dir_ratio':>9}"
    lines.append(hdr)
    for _, r in df.iterrows():
        lines.append(
            f"{r['feature']:<22} {r['corr_ret']:>9.3f} {r['corr_abs']:>9.3f} "
            f"{r['corr_top']:>9.3f} {r['corr_bottom']:>9.3f} {r['sep']:>8.3f} {r['dir_ratio']:>9.2f}"
        )
    lines.append("\nObjectif : corr_ret élevé (>0.05), corr_abs faible, sep > 0 (direction).")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Features directionnelles Oracle (S6.5).")
    parser.add_argument("--batch-id", default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    batch_id = args.batch_id or resolve_oracle_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    report = run_directional_diagnostic(batch_id)
    import os
    out = "artifacts/models/oracle/directional_features_report.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"→ rapport sauvegardé : {out}")
    print(format_report(report))


if __name__ == "__main__":
    main()
