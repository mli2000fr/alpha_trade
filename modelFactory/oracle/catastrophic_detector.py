"""modelFactory/oracle/catastrophic_detector.py — S6.6-B : Catastrophic TOP Detector (v2 WF).

B25 sélectionne le TOP 10 %. Ce détecteur apprend, PARMI ces candidats, lesquels
sont des « faux TOP dangereux » (Oracle réel bas), en s'appuyant sur la
valorisation/croissance (pe_ratio, ev_to_ebitda, revenue_growth_yoy, rev_surprise,
news_count_20d, eps_surprise) — SANS features de volatilité (magnitude).

- Cibles séparées : ``cat10`` (Oracle < 10 %) et ``cat20`` (< 20 %).
- Évaluation : **walk-forward** (5 folds, anti-leakage : train = oracle_available_date < t_start).
- Benchmark : filtre de valorisation simple (rejet par pe_ratio croissant).
- Critère GO/NO-GO : courbe « catastrophes évitées vs vrais TOP sacrifiés ».

Usage :
    python -m modelFactory.oracle.catastrophic_detector --batch-id model-factory-20260811223551-ef2cd0 --target-pct 0.10
"""
from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.config import resolve_oracle_batch_id
from modelFactory.oracle.dataset import (
    BOTTOM_TARGET_COL,
    GUARD_COL,
    TARGET_COL,
    load_global_rank_feature,
    load_oracle_targets,
)
from modelFactory.oracle.fundamental_diagnostic import _load_earnings, _load_fundamentals, _load_sentiment
from modelFactory.oracle.train import roc_auc, train_catboost, train_lightgbm

LOGGER = logging.getLogger(__name__)

_FEATURES = ["pe_ratio", "ev_to_ebitda", "revenue_growth_yoy", "rev_surprise",
             "news_count_20d", "news_count_5d", "eps_surprise"]

_FOLDS: list[tuple[str, str]] = [
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2025-01-01", "2025-12-31"),
    ("2026-01-01", "2026-05-29"),
]


def _auc(y_true, y_score):
    from modelFactory.oracle.train import roc_auc
    return roc_auc(y_true, y_score)


def _build_dataset(engine, batch_id: str, horizon: int = 20, start: str = "2022-01-01") -> pd.DataFrame:
    from modelFactory.oracle.train import get_universe_symbols
    symbols = get_universe_symbols(engine, batch_id, horizon)
    ranks = load_global_rank_feature(engine, batch_id)
    targets = load_oracle_targets(engine, batch_id, horizon)
    earn = _load_earnings(engine, symbols)
    fund = _load_fundamentals(engine, symbols)
    sent = _load_sentiment(engine, symbols)

    df = ranks.merge(targets, left_on=["date", "symbol"], right_on=["prediction_date", "symbol"], how="inner")
    df = df[df["date"] >= pd.Timestamp(start)].copy()
    df = df.merge(fund, left_on=["date", "symbol"], right_on=["trade_date", "symbol"], how="left")
    df = df.merge(sent, left_on=["date", "symbol"], right_on=["trade_date", "symbol"], how="left")
    df = df.drop(columns=[c for c in ("prediction_date", "trade_date_x", "trade_date_y") if c in df.columns])

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

    df["b25_top"] = df["global_rank_20"] >= 0.90
    return df


def _rejection_tradeoff(v: pd.DataFrame, score_col: str, cat_col: str) -> list[dict[str, Any]]:
    """Pour chaque fraction de rejet : catastrophes restantes vs vrais TOP restants."""
    v = v.dropna(subset=[score_col]).copy()
    v = v.sort_values(score_col, ascending=False)
    n = len(v)
    total_cat = int((v[cat_col] == 1).sum())
    total_top = int((v[TARGET_COL] == 1).sum())
    rows: list[dict[str, Any]] = []
    for frac in [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        k = int(n * frac)
        kept = v.iloc[k:]
        cat_kept = int((kept[cat_col] == 1).sum())
        top_kept = int((kept[TARGET_COL] == 1).sum())
        rows.append({
            "reject_frac": frac,
            "cat_kept_frac": cat_kept / total_cat if total_cat else None,
            "top_kept_frac": top_kept / total_top if total_top else None,
            "cat_pct": float((kept[cat_col] == 1).mean()) * 100,
            "true_top_pct": float((kept[TARGET_COL] == 1).mean()) * 100,
            "n_kept": len(kept),
        })
    return rows


def run_catastrophic_detector_wf(
    batch_id: str,
    *,
    target_pct: float = 0.10,
    horizon: int = 20,
    algos: tuple[str, ...] = ("catboost", "lightgbm"),
) -> dict[str, Any]:
    engine = get_sqlalchemy_engine()
    df = _build_dataset(engine, batch_id, horizon)
    df = df[df["b25_top"]].copy()
    LOGGER.info("B25 TOP dataset = %d rows | target cat<%d%%", len(df), int(target_pct * 100))

    feat_cols = [c for c in _FEATURES if c in df.columns]
    cat_col = "cat10" if target_pct == 0.10 else "cat20"
    df[cat_col] = (df["oracle_pct_rank"] < target_pct).astype(int)

    oos_parts: list[pd.DataFrame] = []
    for t_start, t_end in _FOLDS:
        train = df[df[GUARD_COL] <= pd.Timestamp(t_start)]
        test = df[(df["date"] >= pd.Timestamp(t_start)) & (df["date"] <= pd.Timestamp(t_end))]
        if train.empty or test.empty or train[cat_col].nunique() < 2:
            LOGGER.warning("fold %s skipped", t_start)
            continue
        X_tr = train[feat_cols].astype(float).fillna(0.0)
        y_tr = train[cat_col].astype(int)
        X_te = test[feat_cols].astype(float).fillna(0.0)
        part = test[["date", "symbol", "oracle_pct_rank", TARGET_COL, cat_col, "pe_ratio"]].copy()
        for algo in algos:
            cls = train_catboost if algo == "catboost" else train_lightgbm
            model = cls(X_tr, y_tr, X_te, test[cat_col].astype(int))
            p = model.predict_proba(X_te)[:, 1] if algo == "catboost" else model.predict(X_te)
            part[f"pcat_{algo}"] = p
        part["fold_start"] = t_start
        oos_parts.append(part)
        LOGGER.info("fold %s : test=%d cat+=%d", t_start, len(test), int(test[cat_col].sum()))

    oos = pd.concat(oos_parts, ignore_index=True)
    report: dict[str, Any] = {
        "status": "completed",
        "target_pct": target_pct,
        "cat_col": cat_col,
        "features": feat_cols,
        "baseline": {
            "n": int(len(oos)),
            "cat_pct": float((oos[cat_col] == 1).mean()) * 100,
            "true_top_pct": float((oos[TARGET_COL] == 1).mean()) * 100,
        },
        "algos": {},
    }

    for algo in algos:
        auc = roc_auc(oos[cat_col].to_numpy(), oos[f"pcat_{algo}"].to_numpy())
        report["algos"][algo] = {"auc": auc, "tradeoff": _rejection_tradeoff(oos, f"pcat_{algo}", cat_col)}
        LOGGER.info("[%s] AUC=%.3f", algo, auc)

    # Benchmark : filtre simple par pe_ratio (rejeter les plus chers)
    report["algos"]["pe_ratio_only"] = {
        "auc": roc_auc(oos[cat_col].to_numpy(), oos["pe_ratio"].to_numpy()),
        "tradeoff": _rejection_tradeoff(oos, "pe_ratio", cat_col),
    }
    return report


def format_report(report: dict[str, Any]) -> str:
    if report.get("status") != "completed":
        return f"catastrophic_detector: {report}"
    b = report["baseline"]
    lines = [f"=== S6.6-B — CATASTROPHIC TOP DETECTOR (WF, cible={report['cat_col']}) ==="]
    lines.append(f"Baseline OOS (B25 TOP) : {report['cat_col']}={b['cat_pct']:.1f}% vraiTOP={b['true_top_pct']:.1f}% (n={b['n']})")
    for algo, r in report["algos"].items():
        lines.append(f"\n[{algo}] AUC={r['auc']:.3f}  — « catastrophes restantes » vs « vrais TOP restants »")
        lines.append(f"{'rejet%':>6} {'cat_rest%':>9} {'TOP_rest%':>9} {'cat%':>6} {'vraiTOP%':>8}")
        for row in r["tradeoff"]:
            cat_rest = row["cat_kept_frac"] * 100 if row["cat_kept_frac"] is not None else float('nan')
            top_rest = row["top_kept_frac"] * 100 if row["top_kept_frac"] is not None else float('nan')
            lines.append(
                f"{row['reject_frac']*100:>6.0f} {cat_rest:>9.1f} {top_rest:>9.1f} "
                f"{row['cat_pct']:>6.1f} {row['true_top_pct']:>8.1f}"
            )
    lines.append("\nLecture : à rejet fixé, cat_rest% doit BAISSER beaucoup plus vite que TOP_rest%.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Catastrophic TOP Detector (S6.6-B, WF).")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--target-pct", type=float, default=0.10)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    batch_id = args.batch_id or resolve_oracle_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    report = run_catastrophic_detector_wf(batch_id, target_pct=args.target_pct)
    import os
    out = f"artifacts/models/oracle/catastrophic_detector_cat{int(args.target_pct*100)}_report.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"→ rapport sauvegardé : {out}")
    print(format_report(report))


if __name__ == "__main__":
    main()
