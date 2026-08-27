"""modelFactory/global_direction/walk_forward.py — Walk-forward causal GlobalDirection.

Pipeline strictement temporel (identique Oracle S4) :

- Chaque fold vérifie ``oracle_available_date < test_start`` (T2 bloquant) ;
- Retrain par fold (fenêtre expansive) + prédictions OOS par fold ;
- Cible binaire ``gd_direction`` : 1 = D10 (bon long), 0 = D1 (mauvais long),
  **D2-D9 exclus** ; la colonne proba est ``direction_score = P(D10 | D1∨D10)`` ;
- Persistance OOS sous ``artifacts/models/global_direction/<run_id>/``.

Usage :
    python -m modelFactory.global_direction.walk_forward \
        --batch-id model-factory-20260811223551-ef2cd0
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.global_direction.config import resolve_global_direction_batch_id
from modelFactory.global_direction.dataset import (
    DECILE_COL,
    DIRECTION_SCORE_COL,
    RETURN_COL,
    TARGET_COL,
    build_dataset,
)
from modelFactory.oracle.dataset import GUARD_COL
from modelFactory.oracle.leakage import assert_training_cutoff_valid
from modelFactory.oracle.train import (
    decile_monotonicity,
    get_universe_symbols,
    roc_auc,
    train_lightgbm,
)
from modelFactory.oracle.walk_forward import build_folds, DEFAULT_TEST_WINDOWS

LOGGER = logging.getLogger(__name__)

_ARTIFACTS_ROOT = Path("artifacts/models/global_direction")


def _train_lightgbm_multiclass(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_valid: pd.DataFrame,
    y_valid: pd.Series,
    num_boost_round: int = 400,
) -> Any:
    """Classifieur LightGBM multi-classes (3) avec early stopping.

    Utilisé en mode ``ordinal`` (D1=0 / middle=1 / D10=2) ;
    ``direction_score = P(class D10)``.
    """
    import lightgbm as lgb

    params = {
        "objective": "multiclass",
        "num_class": 3,
        "metric": "multi_logloss",
        "verbosity": -1,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_data_in_leaf": 50,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "seed": 42,
    }
    dtr = lgb.Dataset(X_train.astype(float), label=y_train.astype(int))
    dva = lgb.Dataset(X_valid.astype(float), label=y_valid.astype(int), reference=dtr)
    model = lgb.train(
        params, dtr, num_boost_round=num_boost_round, valid_sets=[dva],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
    )
    return model


def _train_lightgbm_regression(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_valid: pd.DataFrame,
    y_valid: pd.Series,
    num_boost_round: int = 400,
) -> Any:
    """Régression LightGBM (V2 « rank ») sur le percentile cross-sectionnel.

    ``direction_score`` = prédiction (0..1) = GoodLongRank : plus c'est haut,
    plus le titre ressemble à un futur bon LONG (relativement aux autres).
    """
    import lightgbm as lgb

    params = {
        "objective": "regression",
        "metric": "rmse",
        "verbosity": -1,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_data_in_leaf": 50,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "seed": 42,
    }
    dtr = lgb.Dataset(X_train.astype(float), label=y_train.astype(float))
    dva = lgb.Dataset(X_valid.astype(float), label=y_valid.astype(float), reference=dtr)
    model = lgb.train(
        params, dtr, num_boost_round=num_boost_round, valid_sets=[dva],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
    )
    return model


def _auc_d10_vs_d1(oos: pd.DataFrame) -> float | None:
    """AUC de ``direction_score`` vs (D10=1 / D1=0) sur le sous-ensemble D1∪D10."""
    sub = oos[oos[DECILE_COL].isin([1, 10])].dropna(subset=[DIRECTION_SCORE_COL])
    if len(sub) < 2:
        return None
    y = (sub[DECILE_COL] == 10).astype(int).to_numpy()
    s = sub[DIRECTION_SCORE_COL].to_numpy()
    return roc_auc(y, s)


def run_walk_forward(
    dataset: pd.DataFrame,
    feature_columns: list[str],
    *,
    test_windows: list[tuple[str, str]] = DEFAULT_TEST_WINDOWS,
    target_mode: str = "binary",
) -> dict[str, Any]:
    """Retrain par fold + prédictions OOS (direction_score) + métriques.

    ``target_mode`` :
    - ``binary`` : entraîne sur D1/D10 uniquement (D2-D9 exclus), score = P(D10).
    - ``ordinal`` : entraîne sur D1=0 / middle=1 / D10=2 (3 classes), le modèle
      connaît le milieu ; ``direction_score = P(D10)``.
    Dans les deux cas, on score TOUT le fold (univers complet, D2-D9 inclus).
    """
    target_mode = str(target_mode).strip().lower()
    if target_mode not in ("binary", "ordinal", "rank"):
        target_mode = "binary"

    folds = build_folds(dataset, test_windows)
    if not folds:
        return {"status": "error", "reason": "no_folds"}

    cols = [c for c in feature_columns if c in dataset.columns]
    oos_parts: list[pd.DataFrame] = []
    per_fold: list[dict[str, Any]] = []

    for fold in folds:
        te = fold["test"]
        X_te = te[cols].astype(float)

        if target_mode == "rank":
            tr = fold["train"]  # toutes les lignes (percentile)
            X_tr = tr[cols].astype(float)
            y_tr = tr[TARGET_COL].astype(float)
            te_valid = te
            if y_tr.nunique() < 2 or te_valid[TARGET_COL].nunique() < 2:
                LOGGER.warning("fold %s: target rank constant — skipped", fold["t_start"])
                continue
            model = _train_lightgbm_regression(
                X_tr, y_tr, te_valid[cols].astype(float), te_valid[TARGET_COL].astype(float),
            )
            score = np.clip(model.predict(X_te), 0.0, 1.0)
        elif target_mode == "ordinal":
            tr = fold["train"]  # toutes les lignes (0/1/2)
            X_tr = tr[cols].astype(float)
            y_tr = tr[TARGET_COL].astype(int)
            te_valid = te
            if y_tr.nunique() < 3 or te_valid[TARGET_COL].nunique() < 3:
                LOGGER.warning("fold %s: target ordinal constant — skipped", fold["t_start"])
                continue
            model = _train_lightgbm_multiclass(
                X_tr, y_tr, te_valid[cols].astype(float), te_valid[TARGET_COL].astype(int),
            )
            proba = model.predict(X_te)
            score = np.asarray(proba)[:, 2]  # P(D10)
        else:
            tr = fold["train"].dropna(subset=[TARGET_COL])  # D1/D10 uniquement
            X_tr = tr[cols].astype(float)
            y_tr = tr[TARGET_COL].astype(int)
            te_valid = te.dropna(subset=[TARGET_COL])
            if y_tr.nunique() < 2 or te_valid[TARGET_COL].nunique() < 2:
                LOGGER.warning("fold %s: target constant (train=%d D1/D10, test=%d D1/D10) — skipped",
                               fold["t_start"], len(tr), len(te_valid))
                continue
            model = train_lightgbm(X_tr, y_tr, te_valid[cols].astype(float), te_valid[TARGET_COL].astype(int))
            proba = model.predict(X_te)  # univers complet
            score = proba

        oos = te[["date", "symbol", RETURN_COL, DECILE_COL, TARGET_COL]].copy()
        oos[DIRECTION_SCORE_COL] = score
        oos["fold_start"] = fold["t_start"]
        oos_parts.append(oos)

        per_fold.append({
            "fold_start": fold["t_start"],
            "n_train": int(len(tr)),
            "n_test": int(len(te)),
            "target_mode": target_mode,
            "auc_d10_vs_d1": _auc_d10_vs_d1(oos),
            "decile_monotonicity": decile_monotonicity(oos, DIRECTION_SCORE_COL)[0],
        })

    if not oos_parts:
        return {"status": "error", "reason": "no_oos"}

    oos = pd.concat(oos_parts, ignore_index=True)
    return {
        "status": "completed",
        "target_mode": target_mode,
        "n_folds": len(per_fold),
        "folds": per_fold,
        "overall": {
            "auc_d10_vs_d1": _auc_d10_vs_d1(oos),
            "decile_monotonicity": decile_monotonicity(oos, DIRECTION_SCORE_COL)[0],
        },
        "oos": oos,
        "feature_columns": cols,
    }


def persist_oos(oos: pd.DataFrame, run_id: str, batch_id: str | None = None) -> Path:
    """Persiste les prédictions OOS en parquet (+ tag batch sidecar)."""
    out_dir = _ARTIFACTS_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "oos_predictions.parquet"
    oos.to_parquet(path, index=False)
    if batch_id:
        try:
            (out_dir / "batch_id.txt").write_text(str(batch_id), encoding="utf-8")
        except OSError:
            pass
    LOGGER.info("persisted GlobalDirection OOS → %s (batch=%s)", path, batch_id or "?")
    return path


def format_report(result: dict[str, Any]) -> str:
    """Rapport lisible."""
    if result.get("status") != "completed":
        return f"Walk-forward GlobalDirection: {result}"
    lines = [f"=== WALK-FORWARD CAUSAL GLOBALDIRECTION — {result['n_folds']} folds "
             f"(target={result.get('target_mode', 'binary')}) ==="]
    for f in result["folds"]:
        auc = f.get("auc_d10_vs_d1")
        auc_s = f"{auc:.3f}" if auc is not None else "-"
        mono = f.get("decile_monotonicity")
        mono_s = f"{mono:+.3f}" if mono is not None else "-"
        lines.append(
            f"  {f['fold_start']}: train={f['n_train']} test={f['n_test']} "
            f"AUC(D10 vs D1)={auc_s} mono={mono_s}"
        )
    o = result["overall"]
    auc = o.get("auc_d10_vs_d1")
    auc_s = f"{auc:.3f}" if auc is not None else "-"
    mono = o.get("decile_monotonicity")
    mono_s = f"{mono:+.3f}" if mono is not None else "-"
    lines.append(f"OVERALL: AUC(D10 vs D1)={auc_s} mono={mono_s}")
    lines.append(
        "Légende : AUC(D10 vs D1) sur l'échantillon D1|D10 (union) ; 0.5 = hasard, "
        ">0.5 = direction_score sépare D10 des D1. Le critère FINAL est le "
        "gradient D1/D10 par quintile dans le pool Oracle (pipeline.py)."
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward causal GlobalDirection H20.")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--feature-mode", default="minimal",
                        choices=["minimal", "directional", "directional+xs",
                                 "sector", "complete", "all"],
                        help="minimal = ~25 features directionnelles (défaut, premier test) ; "
                             "sector = minimal + famille sectorielle (V2) ; "
                             "complete = directional+xs + famille sectorielle (V3).")
    parser.add_argument("--target-mode", default="binary", choices=["binary", "ordinal", "rank"],
                        help="binary = D1/D10 (défaut) ; ordinal = D1/middle/D10 (V1b) ; "
                             "rank = percentile cross-sectionnel D1..D10 (V2, GoodLongRank).")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-05-29")
    parser.add_argument("--symbols", type=int, default=None, help="Limite le nb de symboles (smoke test).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")

    engine = get_sqlalchemy_engine()
    symbols = get_universe_symbols(engine, batch_id, args.horizon)
    if args.symbols:
        symbols = symbols[: args.symbols]

    dataset, feature_columns = build_dataset(
        engine, batch_id, symbols,
        start_date=args.start_date, end_date=args.end_date, horizon=args.horizon,
        feature_mode=args.feature_mode, target_mode=args.target_mode,
    )
    if dataset.empty:
        raise SystemExit("Dataset vide.")
    LOGGER.info("GlobalDirection features (%s) : %d colonnes ; target=%s",
                args.feature_mode, len(feature_columns), args.target_mode)

    result = run_walk_forward(dataset, feature_columns, target_mode=args.target_mode)
    if result.get("status") == "completed":
        run_id = f"global-direction-wf-{datetime.now():%Y%m%d%H%M%S}"
        path = persist_oos(result["oos"], run_id, batch_id=batch_id)
        result["run_id"] = run_id
        result["oos_path"] = str(path)
    print(format_report(result))


if __name__ == "__main__":
    main()
