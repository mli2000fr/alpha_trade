"""modelFactory/oracle/hard_negatives.py — Expérience Hard Negatives (S6.2).

Teste si la sur-pondération des « faux TOP directionnels » (vrai BOTTOM mais score
TOP élevé) permet de décorréler P(top) et P(bottom), i.e. de séparer direction et
magnitude — l'hypothèse H0 étant « les features encodent l'amplitude, pas le signe ».

Protocole (sans leakage — hard negatives identifiés UNIQUEMENT sur train) :
- split train (labels disponibles ≤ cutoff) / valid (dates ≥ valid_start) ;
- BOTTOM model (référence) + TOP model H0, en CatBoost ET LightGBM (algo vs features) ;
- hard negatives conditionnels = {vrai bottom10} ∩ {P(top) in-sample top 10% intra-date} ;
- re-train TOP avec sample_weight ∈ {2, 4, 8} sur ces hard negatives ;
- diagnostics : corr(Ptop,Pbottom), capture TOP, contamination (prédit top → vrai bottom),
  profil FP (fraction dans vrai bottom 0-10%), FN near-miss (80-90%).

Usage :
    python -m modelFactory.oracle.hard_negatives --batch-id model-factory-20260811223551-ef2cd0
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
    _proba_catboost,
    precision_recall_at_top_pct,
    train_catboost,
    train_lightgbm,
)

LOGGER = logging.getLogger(__name__)

_HN_TOP_PCT = 0.10      # « score TOP élevé » = top 10 % intra-date du P(top) in-sample
_WEIGHT_LEVELS = (2, 4, 8)
_ALGO_ABLATION = "O1"   # global_rank_20 + extras Oracle


def _intra_date_rank(df: pd.DataFrame, score_col: str) -> pd.Series:
    return df.groupby("date")[score_col].rank(pct=True)


def _intra_date_corr(df: pd.DataFrame, a: str, b: str) -> float | None:
    """Corrélation moyenne intra-date des rangs de deux colonnes de score."""
    vals: list[float] = []
    for _, g in df.groupby("date"):
        if len(g) < 20:
            continue
        ra = g[a].rank(pct=True)
        rb = g[b].rank(pct=True)
        c = ra.corr(rb)
        if np.isfinite(c):
            vals.append(c)
    return float(np.mean(vals)) if vals else None


def _train_model(algo: str, X_tr, y_tr, X_va, y_va, sample_weight=None):
    if algo == "catboost":
        model = train_catboost(X_tr, y_tr, X_va, y_va, sample_weight=sample_weight)
        return model, _proba_catboost(model, X_va)
    model = train_lightgbm(X_tr, y_tr, X_va, y_va, sample_weight=sample_weight)
    return model, model.predict(X_va)


def _diagnose(valid: pd.DataFrame, ptop_col: str, pbot_col: str) -> dict[str, Any]:
    """Diagnostics ML sur la valid : capture, contamination, profil FP/FN, corr."""
    v = valid.copy()
    v["_ptop_rank"] = v.groupby("date")[ptop_col].rank(pct=True)
    v["_pred_top"] = v["_ptop_rank"] >= 0.90

    cap = precision_recall_at_top_pct(v, ptop_col, target_col=TARGET_COL)

    pred_top = v[v["_pred_top"]]
    contam = float((pred_top[BOTTOM_TARGET_COL] == 1).mean()) if len(pred_top) else None

    # Faux positifs (prédit top, pas vrai top) : où tombent-ils dans le rang réel ?
    fp = v[v["_pred_top"] & (v[TARGET_COL] == 0)]
    if len(fp):
        fp_bottom = float((fp["oracle_pct_rank"] < 0.10).mean())
        fp_near = float(((fp["oracle_pct_rank"] >= 0.80) & (fp["oracle_pct_rank"] < 0.90)).mean())
    else:
        fp_bottom = fp_near = None

    # Faux négatifs (vrai top, pas prédit top) : quasi-ratés en 80-90% ?
    fn = v[(v[TARGET_COL] == 1) & (~v["_pred_top"])]
    if len(fn):
        fn_near = float(((fn["_ptop_rank"] >= 0.80) & (fn["_ptop_rank"] < 0.90)).mean())
    else:
        fn_near = None

    corr = _intra_date_corr(v, ptop_col, pbot_col)

    return {
        "corr_ptop_pbottom": corr,
        "precision_at_10pct": cap["precision"],
        "contamination_pct": 100.0 * contam if contam is not None else None,
        "fp_bottom_pct": 100.0 * fp_bottom if fp_bottom is not None else None,
        "fp_near_pct": 100.0 * fp_near if fp_near is not None else None,
        "fn_near_pct": 100.0 * fn_near if fn_near is not None else None,
    }


def run_hard_negative_experiment(
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
    y_tr_bot = train[BOTTOM_TARGET_COL].astype(int)
    y_va_top = valid[TARGET_COL].astype(int)
    y_va_bot = valid[BOTTOM_TARGET_COL].astype(int)

    report: dict[str, Any] = {"status": "completed", "algos": {}, "hn": {}}
    valid_view = valid[["date", "symbol", TARGET_COL, BOTTOM_TARGET_COL,
                        "oracle_pct_rank", "future_return"]].copy()

    # ── Phase A : modèles de référence (H0) par algo ──
    for algo in algos:
        LOGGER.info("[%s] BOTTOM model...", algo)
        _, p_bot = _train_model(algo, X_tr, y_tr_bot, X_va, y_va_bot)
        LOGGER.info("[%s] TOP model H0...", algo)
        top_model, p_top = _train_model(algo, X_tr, y_tr_top, X_va, y_va_top)

        v = valid_view.copy()
        v["ptop"] = p_top
        v["pbot"] = p_bot
        report["algos"][f"{algo}_H0"] = _diagnose(v, "ptop", "pbot")

        # Hard negatives conditionnels sur TRAIN (pas de leakage).
        if algo == "catboost":
            p_top_train = _proba_catboost(top_model, X_tr)
        else:
            p_top_train = top_model.predict(X_tr)
        tr = pd.DataFrame({"date": train["date"].values, "symbol": train["symbol"].values, "ptop": p_top_train})
        tr["ptop_rank"] = tr.groupby("date")["ptop"].rank(pct=True)
        hn_mask = (y_tr_bot.to_numpy() == 1) & (tr["ptop_rank"].to_numpy() >= 1.0 - _HN_TOP_PCT)
        n_hn = int(hn_mask.sum())
        LOGGER.info("[%s] hard negatives conditionnels (train) = %d / %d", algo, n_hn, len(X_tr))

        # ── Phase C : re-train TOP avec hard negatives pondérés ──
        for w in _WEIGHT_LEVELS:
            sw = np.ones(len(X_tr), dtype=float)
            sw[hn_mask] = float(w)
            _, p_top_hn = _train_model(algo, X_tr, y_tr_top, X_va, y_va_top, sample_weight=sw)
            vv = valid_view.copy()
            vv["ptop"] = p_top_hn
            vv["pbot"] = p_bot
            report["hn"][f"{algo}_HN{w}x"] = _diagnose(vv, "ptop", "pbot")
            LOGGER.info("[%s] HN%dx : corr=%.3f contamination=%.1f%%",
                        algo, w,
                        report["hn"][f"{algo}_HN{w}x"]["corr_ptop_pbottom"] or float('nan'),
                        report["hn"][f"{algo}_HN{w}x"]["contamination_pct"] or 0.0)

    return report


def format_report(report: dict[str, Any]) -> str:
    if report.get("status") != "completed":
        return f"Hard-negatives: {report}"
    lines = ["=== HARD NEGATIVES — séparation directionnelle (valid 2025-2026) ==="]
    header = f"{'variante':<18} {'corr(Ptop,Pbot)':>15} {'captureTOP%':>11} {'contam%':>8} {'FPbottom%':>9} {'FPnear%':>7} {'FNnear%':>7}"
    lines.append(header)
    for key in ("catboost_H0", "lightgbm_H0", "catboost_HN2x", "catboost_HN4x", "catboost_HN8x",
                "lightgbm_HN2x", "lightgbm_HN4x", "lightgbm_HN8x"):
        r = report["algos"].get(key) or report["hn"].get(key)
        if not r:
            continue
        lines.append(
            f"{key:<18} {r['corr_ptop_pbottom']:>15.3f} {r['precision_at_10pct']*100:>11.1f} "
            f"{r['contamination_pct']:>8.1f} {r['fp_bottom_pct']:>9.1f} {r['fp_near_pct']:>7.1f} {r['fn_near_pct']:>7.1f}"
        )
    lines.append("\nLecture : corr(Ptop,Pbot) doit BAISSER ; contam% et FPbottom% doivent baisser.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hard negatives Oracle (S6.2).")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--train-cutoff", default="2024-06-30")
    parser.add_argument("--valid-start", default="2025-01-01")
    parser.add_argument("--algos", default="catboost,lightgbm")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    batch_id = args.batch_id or resolve_oracle_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")

    algos = tuple(a.strip() for a in args.algos.split(",") if a.strip())
    report = run_hard_negative_experiment(
        batch_id,
        train_cutoff=args.train_cutoff,
        valid_start=args.valid_start,
        algos=algos,
    )
    print(format_report(report))
    out = "artifacts/models/oracle/hard_negatives_report.json"
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n→ rapport sauvegardé : {out}")


if __name__ == "__main__":
    main()
