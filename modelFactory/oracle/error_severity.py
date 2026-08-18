"""modelFactory/oracle/error_severity.py — Expérience « Oracle Rank Loss / Error Severity » (S6.4).

Teste si le problème vient de l'OBJECTIF d'apprentissage ou des FEATURES, en
gardant les mêmes features mais en changeant la façon de définir la cible :

- **BIN**  : classifieur binaire ``oracle_top10`` (baseline, objective actuel).
- **SEV**  : classifieur binaire pondéré par la sévérité ``(0.90 − r)²`` pour les
             non-top (pénalise les inclusions catastrophiques, r = oracle_pct_rank).
- **REG**  : régression sur ``oracle_pct_rank`` (distance continue au TOP).

Métrique reine = distribution des rangs Oracle réels des TOP prédits :
- ``capture`` (vrai top10), ``rank_mean/median``, ``P(rank<10%)`` (catastrophique),
  ``P(rank<20%)``, ``P(rank<50%)``, ``P(rank∈60-80%)``, ``P(rank∈80-90%)``,
  ``severity = mean(max(0, 0.90−r)²)``.

Usage :
    python -m modelFactory.oracle.error_severity --batch-id model-factory-20260811223551-ef2cd0
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
    TARGET_COL,
    ablation_features,
    build_dataset,
    split_dataset,
)
from modelFactory.oracle.train import (
    train_catboost,
    train_catboost_regressor,
    train_lightgbm,
    train_lightgbm_regressor,
)

LOGGER = logging.getLogger(__name__)

_SEV_LAMBDA = 50.0  # échelle de la sévérité (0.90-r)² pour les non-top


def _rank_quality(valid: pd.DataFrame, score_col: str) -> dict[str, Any]:
    """Qualité des TOP prédits : distribution des rangs Oracle réels."""
    v = valid.copy()
    v["_rank"] = v.groupby("date")[score_col].rank(pct=True)  # 1.0 = meilleur
    v["_pred_top"] = v["_rank"] >= 0.90
    pred_top = v[v["_pred_top"]]
    if pred_top.empty:
        return {"capture": None}
    r = pred_top["oracle_pct_rank"].astype(float)
    return {
        "capture": float((pred_top[TARGET_COL] == 1).mean()),
        "rank_mean": float(r.mean()),
        "rank_median": float(r.median()),
        "p_rank_lt_10": float((r < 0.10).mean()),
        "p_rank_lt_20": float((r < 0.20).mean()),
        "p_rank_lt_50": float((r < 0.50).mean()),
        "p_rank_60_80": float(((r >= 0.60) & (r < 0.80)).mean()),
        "p_rank_80_90": float(((r >= 0.80) & (r < 0.90)).mean()),
        "severity": float(np.mean(np.maximum(0.0, 0.90 - r) ** 2)),
    }


def _mag_corr(valid: pd.DataFrame, score_col: str) -> float | None:
    """Corrélation intra-date du score avec |future_return| (magnitude)."""
    vals: list[float] = []
    v = valid.copy()
    v["_abs"] = v["future_return"].abs()
    for _, g in v.groupby("date"):
        if len(g) < 30:
            continue
        c = g[score_col].corr(g["_abs"], method="spearman")
        if np.isfinite(c):
            vals.append(c)
    return float(np.mean(vals)) if vals else None


def run_error_severity_experiment(
    batch_id: str,
    *,
    train_cutoff: str = "2024-06-30",
    valid_start: str = "2025-01-01",
    horizon: int = 20,
    algos: tuple[str, ...] = ("catboost", "lightgbm"),
) -> dict[str, Any]:
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

    cols = [c for c in ablation_features(feature_columns, include_global_rank=True, include_oracle_extras=True) if c in dataset.columns]
    train, valid = split_dataset(dataset, train_cutoff=train_cutoff, valid_start=valid_start)
    LOGGER.info("train=%d valid=%d features=%d", len(train), len(valid), len(cols))

    X_tr = train[cols].astype(float)
    X_va = valid[cols].astype(float)
    y_tr_top = train[TARGET_COL].astype(int)
    y_tr_rank = train["oracle_pct_rank"].astype(float)
    y_va_top = valid[TARGET_COL].astype(int)
    y_va_rank = valid["oracle_pct_rank"].astype(float)

    # Poids de sévérité (indépendant de l'algo) : non-top pondérés par (0.90-r)^2
    r_tr = train["oracle_pct_rank"].astype(float).to_numpy()
    sev = np.where(y_tr_top.to_numpy() == 1, 1.0, 1.0 + _SEV_LAMBDA * np.maximum(0.0, 0.90 - r_tr) ** 2)

    valid_view = valid[["date", "symbol", TARGET_COL, BOTTOM_TARGET_COL,
                        "oracle_pct_rank", "future_return"]].copy()
    report: dict[str, Any] = {"status": "completed", "variants": {}}

    for algo in algos:
        cls = train_catboost if algo == "catboost" else train_lightgbm
        reg = train_catboost_regressor if algo == "catboost" else train_lightgbm_regressor

        def proba(m, X):
            return m.predict_proba(X)[:, 1] if algo == "catboost" else m.predict(X)

        # BIN — classifieur binaire (baseline)
        LOGGER.info("[%s] BIN...", algo)
        v = valid_view.copy()
        v["score"] = proba(cls(X_tr, y_tr_top, X_va, y_va_top), X_va)
        m = _rank_quality(v, "score")
        m["mag_corr"] = _mag_corr(v, "score")
        report["variants"][f"{algo}_BIN"] = m

        # SEV — binaire pondéré par la sévérité
        LOGGER.info("[%s] SEV...", algo)
        v = valid_view.copy()
        v["score"] = proba(cls(X_tr, y_tr_top, X_va, y_va_top, sample_weight=sev), X_va)
        m = _rank_quality(v, "score")
        m["mag_corr"] = _mag_corr(v, "score")
        report["variants"][f"{algo}_SEV"] = m

        # REG — régression sur le rang Oracle continu
        LOGGER.info("[%s] REG...", algo)
        v = valid_view.copy()
        v["score"] = reg(X_tr, y_tr_rank, X_va, y_va_rank).predict(X_va)
        m = _rank_quality(v, "score")
        m["mag_corr"] = _mag_corr(v, "score")
        report["variants"][f"{algo}_REG"] = m

    return report


def format_report(report: dict[str, Any]) -> str:
    if report.get("status") != "completed":
        return f"error_severity: {report}"
    lines = ["=== ERROR SEVERITY — rangs Oracle réels des TOP prédits (valid 2025-2026) ==="]
    hdr = (f"{'variant':<6} {'capture':>7} {'rankMean':>8} {'rankMed':>7} "
           f"{'<10%':>6} {'<20%':>6} {'<50%':>6} {'60-80%':>6} {'80-90%':>6} {'severity':>8} {'|corr|':>6}")
    lines.append(hdr)
    for name, m in report["variants"].items():
        lines.append(
            f"{name:<6} {m['capture']*100:>7.1f} {m['rank_mean']*100:>8.1f} {m['rank_median']*100:>7.1f} "
            f"{m['p_rank_lt_10']*100:>6.1f} {m['p_rank_lt_20']*100:>6.1f} {m['p_rank_lt_50']*100:>6.1f} "
            f"{m['p_rank_60_80']*100:>6.1f} {m['p_rank_80_90']*100:>6.1f} {m['severity']*1000:>8.2f} "
            f"{abs(m['mag_corr']):>6.2f}"
        )
    lines.append("\nLecture : <10% (catastrophique) et severity doivent BAISSER ; capture et 80-90% doivent tenir.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Oracle Rank Loss / Error Severity (S6.4).")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--algos", default="catboost,lightgbm")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    batch_id = args.batch_id or resolve_oracle_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    algos = tuple(a.strip() for a in args.algos.split(",") if a.strip())
    report = run_error_severity_experiment(batch_id, algos=algos)
    print(format_report(report))
    import os
    out = "artifacts/models/oracle/error_severity_report.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n→ rapport sauvegardé : {out}")


if __name__ == "__main__":
    main()
