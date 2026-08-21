"""modelFactory/oracle/feature_diagnostic.py — Diagnostic directionnel des features (S6.3).

Pour chaque feature, mesure la corrélation cross-sectionnelle (Spearman intra-date,
moyennée sur les dates) avec 4 cibles :

- ``future_return``      → direction (signée)
- ``abs_return``         → magnitude (amplitude)
- ``oracle_top10``       → appartient au vrai top 10 %
- ``oracle_bottom10``    → appartient au vrai bottom 10 %

Métriques clés :
- ``sep = corr(top10) − corr(bottom10)`` : une feature DIRECTIONNELLE a sep élevé
  (prédit top ET anti-prédit bottom) ; une feature MAGNITUDE a corr(top10)>0 ET
  corr(bottom10)>0 (prédit les deux extrêmes).
- stabilité : corr par fold WF (2022→2026).

Usage :
    python -m modelFactory.oracle.feature_diagnostic --batch-id model-factory-20260811223551-ef2cd0
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
    ORACLE_EXTRA_FEATURES,
    TARGET_COL,
    build_dataset,
)

LOGGER = logging.getLogger(__name__)

_TARGET_LABEL_COLS = {
    TARGET_COL, "oracle_pct_rank", "oracle_decile",
    "future_return", "oracle_available_date", "prediction_date", "date", "symbol",
}

_FOLDS: list[tuple[str, str]] = [
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2025-01-01", "2025-12-31"),
    ("2026-01-01", "2026-05-29"),
]


def _cs_spearman(df: pd.DataFrame, feat: str, target: str, min_universe: int = 30) -> float | None:
    """Corrélation Spearman intra-date moyenne (cross-sectionnelle)."""
    vals: list[float] = []
    for _, g in df.groupby("date"):
        if len(g) < min_universe:
            continue
        c = g[feat].corr(g[target], method="spearman")
        if np.isfinite(c):
            vals.append(c)
    return float(np.mean(vals)) if vals else None


def _feature_columns(dataset: pd.DataFrame, feature_columns: list[str]) -> list[str]:
    cols = [c for c in feature_columns if c in dataset.columns]
    for c in ("global_rank_20", *ORACLE_EXTRA_FEATURES):
        if c in dataset.columns and c not in cols:
            cols.append(c)
    return cols


def run_feature_diagnostic(batch_id: str, *, horizon: int = 20, start: str = "2022-01-01") -> dict[str, Any]:
    engine = get_sqlalchemy_engine()
    from modelFactory.oracle.train import get_universe_symbols

    symbols = get_universe_symbols(engine, batch_id, horizon)
    LOGGER.info("universe=%d symbols — build dataset...", len(symbols))
    dataset, feature_columns = build_dataset(
        engine, batch_id, symbols,
        start_date="2020-01-01", end_date="2026-05-29", horizon=horizon,
    )
    if dataset.empty:
        return {"status": "error", "reason": "empty_dataset"}

    df = dataset[dataset["date"] >= pd.Timestamp(start)].copy()
    df["abs_return"] = df["future_return"].abs()
    # top/bottom dérivés localement depuis pct_rank (la table n'expose plus que
    # oracle_extreme10 = TOP ∪ BOTTOM, target du modèle Oracle Extreme)
    df["_top10"] = (df["oracle_pct_rank"] >= 0.90).astype(int)
    df["_bottom10"] = (df["oracle_pct_rank"] <= 0.10).astype(int)
    feats = _feature_columns(df, feature_columns)
    LOGGER.info("dates=%d features=%d", df["date"].nunique(), len(feats))

    targets = {
        "future_return": "future_return",
        "abs_return": "abs_return",
        "oracle_top10": "_top10",
        "oracle_bottom10": "_bottom10",
    }

    rows: list[dict[str, Any]] = []
    for i, feat in enumerate(feats):
        row: dict[str, Any] = {"feature": feat}
        for tname, tcol in targets.items():
            row[f"corr_{tname}"] = _cs_spearman(df, feat, tcol)
        rows.append(row)
        if (i + 1) % 20 == 0:
            LOGGER.info("  %d/%d features", i + 1, len(feats))

    out = pd.DataFrame(rows)
    out["sep_top_bottom"] = out["corr_oracle_top10"] - out["corr_oracle_bottom10"]
    out["dir_ratio"] = out["corr_future_return"].abs() / (out["corr_abs_return"].abs() + 1e-6)

    # ── Stabilité par fold pour le top 25 directionnel ──
    top_dir = out.sort_values("sep_top_bottom", ascending=False).head(25)["feature"].tolist()
    stability: dict[str, dict[str, float | None]] = {}
    for feat in top_dir:
        per_fold: dict[str, float | None] = {}
        for t_start, t_end in _FOLDS:
            sub = df[(df["date"] >= pd.Timestamp(t_start)) & (df["date"] <= pd.Timestamp(t_end))]
            per_fold[t_start[:4]] = _cs_spearman(sub, feat, "future_return")
        stability[feat] = per_fold

    return {
        "status": "completed",
        "n_features": int(len(out)),
        "features": out.sort_values("sep_top_bottom", ascending=False).to_dict("records"),
        "top_directional": top_dir,
        "stability_top_directional": stability,
    }


def format_report(report: dict[str, Any]) -> str:
    if report.get("status") != "completed":
        return f"feature_diagnostic: {report}"
    df = pd.DataFrame(report["features"])
    lines = ["=== DIAGNOSTIC DES FEATURES — direction vs magnitude (Spearman intra-date) ==="]
    lines.append("Top 15 DIRECTIONNELLES (sep = corr(top10) − corr(bottom10)) :")
    hdr = f"{'feature':<32} {'corr_ret':>9} {'corr_abs':>9} {'corr_top':>9} {'corr_bot':>9} {'sep':>8}"
    lines.append(hdr)
    top = df.head(15)
    for _, r in top.iterrows():
        lines.append(
            f"{r['feature']:<32} {r['corr_future_return']:>9.3f} {r['corr_abs_return']:>9.3f} "
            f"{r['corr_oracle_top10']:>9.3f} {r['corr_oracle_bottom10']:>9.3f} {r['sep_top_bottom']:>8.3f}"
        )
    lines.append("\nTop 10 MAGNITUDE (corr_abs élevée, faible séparation top/bottom) :")
    mag = df.sort_values("corr_abs_return", ascending=False).head(10)
    for _, r in mag.iterrows():
        lines.append(
            f"{r['feature']:<32} corr_ret={r['corr_future_return']:>7.3f} corr_abs={r['corr_abs_return']:>7.3f} "
            f"top={r['corr_oracle_top10']:>7.3f} bot={r['corr_oracle_bottom10']:>7.3f}"
        )
    lines.append("\nStabilité corr(future_return) par fold des top directionnels :")
    stab = report["stability_top_directional"]
    years = ["2022", "2023", "2024", "2025", "2026"]
    lines.append(f"{'feature':<32} " + " ".join(f"{y:>7}" for y in years))
    for feat in report["top_directional"][:12]:
        vals = stab.get(feat, {})
        line = f"{feat:<32} " + " ".join(f"{vals.get(y, float('nan')):>7.2f}" if vals.get(y) is not None else f"{'—':>7}" for y in years)
        lines.append(line)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostic directionnel des features Oracle.")
    parser.add_argument("--batch-id", default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    batch_id = args.batch_id or resolve_oracle_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    report = run_feature_diagnostic(batch_id)
    print(format_report(report))
    import os
    out_dir = "artifacts/models/oracle"
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/feature_diagnostic_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n→ rapport sauvegardé : {out_dir}/feature_diagnostic_report.json")


if __name__ == "__main__":
    main()
