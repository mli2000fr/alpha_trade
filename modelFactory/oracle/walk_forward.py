"""modelFactory/oracle/walk_forward.py — Walk-forward causal strict (S4).

Pipeline strictement temporel (spec §11) :

- Chaque fold d'entraînement vérifie ``oracle_available_date < test_start``
  (T2 bloquant) : aucun fold ne « voit » une ligne Oracle dont l'horizon n'était
  pas encore réalisé au moment de la première prédiction de test.
- Retrain par fold (fenêtre expansive) + prédictions OOS par fold.
- Persistance des prédictions OOS en parquet sous ``artifacts/models/oracle/<run_id>/``.

Usage :
    python -m modelFactory.oracle.walk_forward --batch-id model-factory-20260811223551-ef2cd0 --ablation O1
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.config import resolve_oracle_batch_id
from modelFactory.oracle.dataset import (
    GUARD_COL,
    TARGET_COL,
    ablation_features,
    build_dataset,
)
from modelFactory.oracle.leakage import assert_training_cutoff_valid
from modelFactory.oracle.train import (
    decile_monotonicity,
    get_universe_symbols,
    precision_recall_at_top_pct,
    roc_auc,
    train_lightgbm,
)
from modelFactory.feature_logging import log_feature_duplicates, log_feature_values, log_feature_weights

LOGGER = logging.getLogger(__name__)

# Fenêtres de test (fenêtre expansive d'entraînement).
DEFAULT_TEST_WINDOWS: list[tuple[str, str]] = [
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2025-01-01", "2025-12-31"),
    ("2026-01-01", "2026-05-29"),
]

_ABLATIONS: dict[str, dict[str, Any]] = {
    "O0": {"include_global_rank": False, "include_oracle_extras": False, "lean": False},
    "O1": {"include_global_rank": True, "include_oracle_extras": True, "lean": False},
    "O2": {"include_global_rank": False, "include_oracle_extras": False, "lean": True},
}

_ARTIFACTS_ROOT = Path("artifacts/models/oracle")


def build_folds(dataset: pd.DataFrame, test_windows: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """Découpe le dataset en folds causaux (T2 bloquant).

    Pour chaque fenêtre ``[t_start, t_end]`` :
    - train = lignes dont ``oracle_available_date < t_start`` (labels déjà connues) ;
    - test  = lignes dont ``date ∈ [t_start, t_end]`` (prédictions après cutoff).
    """
    folds: list[dict[str, Any]] = []
    for t_start, t_end in test_windows:
        train = dataset[dataset[GUARD_COL] < pd.Timestamp(t_start)]
        test = dataset[
            (dataset["date"] >= pd.Timestamp(t_start)) & (dataset["date"] <= pd.Timestamp(t_end))
        ]
        if train.empty or test.empty:
            LOGGER.warning("fold %s→%s vide (train=%d test=%d) — skipped", t_start, t_end, len(train), len(test))
            continue
        # T2 — bloquant : le cutoff couvre bien toutes les labels d'entraînement.
        assert_training_cutoff_valid(
            training_cutoff=t_start,
            max_oracle_available_date=train[GUARD_COL].max(),
        )
        folds.append({"t_start": t_start, "t_end": t_end, "train": train, "test": test})
    return folds


def run_walk_forward(
    dataset: pd.DataFrame,
    feature_columns: list[str],
    *,
    test_windows: list[tuple[str, str]],
    ablation: str = "O1",
) -> dict[str, Any]:
    """Retrain par fold + prédictions OOS + métriques par fold et globales.

    Cible unique : ``oracle_extreme10`` (détection de gros mouvement H20,
    TOP 10 % ∪ BOTTOM 10 %). Colonne proba : ``proba_extreme``.
    """
    _target_col = TARGET_COL
    _proba_col = "proba_extreme"

    folds = build_folds(dataset, test_windows)
    if not folds:
        return {"status": "error", "reason": "no_folds"}

    cols = [c for c in ablation_features(feature_columns, **_ABLATIONS[ablation]) if c in dataset.columns]
    # ── Audit : toutes les features sont-elles alimentées ? (une ligne par feature) ──
    log_feature_values(dataset, cols, label="oracle_extreme_train_features")
    log_feature_duplicates(dataset, cols, label="oracle_extreme_train_features")

    oos_parts: list[pd.DataFrame] = []
    per_fold: list[dict[str, Any]] = []
    _test_feature_parts: list[pd.DataFrame] = []

    for fold in folds:
        X_tr = fold["train"][cols].astype(float)
        y_tr = fold["train"][_target_col].astype(int)
        X_te = fold["test"][cols].astype(float)
        y_te = fold["test"][_target_col].astype(int)
        if y_tr.nunique() < 2 or y_te.nunique() < 2:
            LOGGER.warning("fold %s: target constant — skipped", fold["t_start"])
            continue

        model = train_lightgbm(X_tr, y_tr, X_te, y_te)
        log_feature_weights(model, cols, label=f"oracle_extreme fold={fold['t_start']}")
        _test_feature_parts.append(X_te)
        proba = model.predict(X_te)

        oos_cols = ["date", "symbol", _target_col, "future_return"]
        oos = fold["test"][oos_cols].copy()
        oos[_proba_col] = proba
        oos["fold_start"] = fold["t_start"]
        oos_parts.append(oos)

        pr = precision_recall_at_top_pct(oos, _proba_col, target_col=_target_col)
        prevalence = float(oos[_target_col].astype(float).mean()) if not oos.empty else None
        per_fold.append({
            "fold_start": fold["t_start"],
            "n_train": int(len(fold["train"])),
            "n_test": int(len(fold["test"])),
            "prevalence": prevalence,
            "precision_at_10pct": pr["precision"],
            "recall_at_10pct": pr["recall"],
            "auc": roc_auc(y_te.to_numpy(), proba),
            "decile_monotonicity": decile_monotonicity(oos, _proba_col)[0],
        })

    if not oos_parts:
        return {"status": "error", "reason": "no_oos"}

    # ── Audit : valeurs des features au moment de la prédiction (une ligne par feature) ──
    if _test_feature_parts:
        log_feature_values(
            pd.concat(_test_feature_parts, ignore_index=True),
            cols,
            label="oracle_extreme_predict_features",
        )

    oos = pd.concat(oos_parts, ignore_index=True)
    pr_overall = precision_recall_at_top_pct(oos, _proba_col, target_col=_target_col)
    prevalence_overall = float(oos[_target_col].astype(float).mean()) if not oos.empty else None

    n_folds = len(per_fold)

    return {
        "status": "completed",
        "ablation": ablation,
        "n_folds": n_folds,
        "folds": per_fold,
        "overall": {
            "precision_at_10pct": pr_overall["precision"],
            "recall_at_10pct": pr_overall["recall"],
            "prevalence": prevalence_overall,
            "auc": roc_auc(oos[_target_col].to_numpy(), oos[_proba_col].to_numpy()),
            "decile_monotonicity": decile_monotonicity(oos, _proba_col)[0],
        },
        "oos": oos,
        "feature_columns": cols,
    }


def persist_oos(oos: pd.DataFrame, run_id: str) -> Path:
    """Persiste les prédictions OOS en parquet."""
    out_dir = _ARTIFACTS_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "oos_predictions.parquet"
    oos.to_parquet(path, index=False)
    LOGGER.info("persisted OOS predictions → %s", path)
    return path


def format_report(result: dict[str, Any]) -> str:
    """Rapport lisible."""
    if result.get("status") != "completed":
        return f"Walk-forward: {result}"
    lines = [f"=== WALK-FORWARD CAUSAL ({result['ablation']}) — {result['n_folds']} folds ==="]
    for f in result["folds"]:
        prev = f.get("prevalence")
        prev_s = f"{prev*100:.1f}%" if prev is not None else "-"
        lines.append(
            f"  {f['fold_start']}: train={f['n_train']} test={f['n_test']} "
            f"prev={prev_s} "
            f"precision@10%={f['precision_at_10pct']:.3f} "
            f"recall@10%={f['recall_at_10pct']:.3f} AUC={f['auc']:.3f} "
            f"mono={f['decile_monotonicity']:.3f}"
        )
    o = result["overall"]
    prev = o.get("prevalence")
    prev_s = f"{prev*100:.1f}%" if prev is not None else "-"
    lift = (o["precision_at_10pct"] / prev) if (prev and o["precision_at_10pct"] is not None) else None
    lift_s = f"{lift:.2f}x" if lift is not None else "-"
    lines.append(
        f"OVERALL: prev={prev_s} precision@10%={o['precision_at_10pct']:.3f} "
        f"recall@10%={o['recall_at_10pct']:.3f} "
        f"lift_oracle_vs_prev={lift_s} AUC={o['auc']:.3f} mono={o['decile_monotonicity']:.3f}"
    )
    lines.append(
        "Légende : 'prev' = prévalence de la cible dans le fold test (~20% pour "
        "oracle_extreme10) ; 'precision@10%' = précision@10% du modèle Oracle "
        "Extreme. Comparer toujours precision@10% à prev (lift = precision/prev)."
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward causal Oracle (S4).")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--ablation", choices=["O0", "O1", "O2"], default="O1")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-05-29")
    parser.add_argument("--symbols", type=int, default=None, help="Limite le nb de symboles (smoke test).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    batch_id = args.batch_id or resolve_oracle_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")

    engine = get_sqlalchemy_engine()
    symbols = get_universe_symbols(engine, batch_id, args.horizon)
    if args.symbols:
        symbols = symbols[:args.symbols]

    dataset, feature_columns = build_dataset(
        engine, batch_id, symbols,
        start_date=args.start_date, end_date=args.end_date, horizon=args.horizon,
    )
    if dataset.empty:
        raise SystemExit("Dataset vide.")

    result = run_walk_forward(
        dataset, feature_columns,
        test_windows=DEFAULT_TEST_WINDOWS,
        ablation=args.ablation,
    )
    if result.get("status") == "completed":
        run_id = f"oracle-wf-{datetime.now():%Y%m%d%H%M%S}"
        path = persist_oos(result["oos"], run_id)
        result["run_id"] = run_id
        result["oos_path"] = str(path)
    print(format_report(result))


if __name__ == "__main__":
    main()
