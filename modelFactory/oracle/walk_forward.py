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
    """Retrain par fold + prédictions OOS + métriques par fold et globales."""
    folds = build_folds(dataset, test_windows)
    if not folds:
        return {"status": "error", "reason": "no_folds"}

    cols = [c for c in ablation_features(feature_columns, **_ABLATIONS[ablation]) if c in dataset.columns]
    oos_parts: list[pd.DataFrame] = []
    per_fold: list[dict[str, Any]] = []

    for fold in folds:
        X_tr = fold["train"][cols].astype(float)
        y_tr = fold["train"][TARGET_COL].astype(int)
        X_te = fold["test"][cols].astype(float)
        y_te = fold["test"][TARGET_COL].astype(int)
        if y_tr.nunique() < 2 or y_te.nunique() < 2:
            LOGGER.warning("fold %s: target constant — skipped", fold["t_start"])
            continue

        model = train_lightgbm(X_tr, y_tr, X_te, y_te)
        proba = model.predict(X_te)

        oos = fold["test"][["date", "symbol", TARGET_COL, "future_return", "global_rank_20"]].copy()
        oos["proba_top"] = proba
        oos["fold_start"] = fold["t_start"]
        oos_parts.append(oos)

        pr = precision_recall_at_top_pct(oos, "proba_top")
        baseline_pr = precision_recall_at_top_pct(oos, "global_rank_20")
        per_fold.append({
            "fold_start": fold["t_start"],
            "n_train": int(len(fold["train"])),
            "n_test": int(len(fold["test"])),
            "precision_at_10pct": pr["precision"],
            "recall_at_10pct": pr["recall"],
            "baseline_precision_at_10pct": baseline_pr["precision"],
            "auc": roc_auc(y_te.to_numpy(), proba),
            "decile_monotonicity": decile_monotonicity(oos, "proba_top")[0],
        })

    if not oos_parts:
        return {"status": "error", "reason": "no_oos"}

    oos = pd.concat(oos_parts, ignore_index=True)
    pr_overall = precision_recall_at_top_pct(oos, "proba_top")
    baseline_overall = precision_recall_at_top_pct(oos, "global_rank_20")

    # Stabilité : fraction des folds où le modèle bat la baseline global_rank_20.
    n_folds = len(per_fold)
    n_beat_baseline = sum(
        1 for f in per_fold
        if f["precision_at_10pct"] is not None
        and f["baseline_precision_at_10pct"] is not None
        and f["precision_at_10pct"] > f["baseline_precision_at_10pct"]
    )

    return {
        "status": "completed",
        "ablation": ablation,
        "n_folds": n_folds,
        "folds": per_fold,
        "overall": {
            "precision_at_10pct": pr_overall["precision"],
            "recall_at_10pct": pr_overall["recall"],
            "baseline_precision_at_10pct": baseline_overall["precision"],
            "auc": roc_auc(oos[TARGET_COL].to_numpy(), oos["proba_top"].to_numpy()),
            "decile_monotonicity": decile_monotonicity(oos, "proba_top")[0],
        },
        "fold_stability_pct": 100.0 * n_beat_baseline / n_folds if n_folds else None,
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
        lines.append(
            f"  {f['fold_start']}: train={f['n_train']} test={f['n_test']} "
            f"precision@10%={f['precision_at_10pct']:.3f} "
            f"(baseline {f['baseline_precision_at_10pct']:.3f}) AUC={f['auc']:.3f} mono={f['decile_monotonicity']:.3f}"
        )
    o = result["overall"]
    lines.append(
        f"OVERALL: precision@10%={o['precision_at_10pct']:.3f} "
        f"(baseline {o['baseline_precision_at_10pct']:.3f}) AUC={o['auc']:.3f} "
        f"mono={o['decile_monotonicity']:.3f}"
    )
    lines.append(f"fold_stability (bat baseline) = {result['fold_stability_pct']:.1f}%")
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

    result = run_walk_forward(dataset, feature_columns, test_windows=DEFAULT_TEST_WINDOWS, ablation=args.ablation)
    if result.get("status") == "completed":
        run_id = f"oracle-wf-{datetime.now():%Y%m%d%H%M%S}"
        path = persist_oos(result["oos"], run_id)
        result["run_id"] = run_id
        result["oos_path"] = str(path)
    print(format_report(result))


if __name__ == "__main__":
    main()
