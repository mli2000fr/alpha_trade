"""E4-B research-only: contrôle binaire UP_FIRST contre DOWN_FIRST.

Le fit ignore les rares classes NO_TOUCH et AMBIGUOUS et n'applique aucune
pondération automatique. Les tests OOS conservent toutefois tous les événements
Oracle afin que la couverture et l'économie ne soient pas artificiellement
embellies.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.first_touch_directional import (
    AMBIGUOUS,
    CLASS_NAMES,
    DOWN_FIRST,
    NO_TOUCH,
    P_AMBIGUOUS_COL,
    P_DOWN_COL,
    P_NO_TOUCH_COL,
    P_UP_COL,
    PREDICTED_CLASS_COL,
    PRIMARY_MARGIN,
    TARGET_COL,
    TARGET_NAME_COL,
    TOUCH_SESSIONS_COL,
    UP_FIRST,
    FirstTouchConfig,
    _gates,
    _stability,
    attach_first_touch_targets,
    build_first_touch_panel,
    evaluate_first_touch_oos,
)
from modelFactory.oracle.train import get_universe_symbols
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.path_aware_directional import (
    LONG_NET_RETURN_COL,
    SHORT_NET_RETURN_COL,
    BarrierRaceConfig,
    attach_path_targets,
    build_path_label_panel,
)
from modelFactory.shared_directional import (
    DEFAULT_ARTIFACTS_ROOT,
    DEFAULT_PROFILE,
    ORACLE_GATE_SCORE_COL,
    SharedDirectionalConfig,
    _prepare_X,
    _semester_label,
    build_shared_dataset,
    load_profile,
)

LOGGER = logging.getLogger(__name__)

BINARY_TARGET_COL = "first_touch_binary_target"


def add_binary_target(frame: pd.DataFrame) -> pd.DataFrame:
    """DOWN_FIRST=0, UP_FIRST=1, autres classes non entraînables."""
    result = frame.copy()
    result[BINARY_TARGET_COL] = np.where(
        result[TARGET_COL].eq(UP_FIRST), 1.0,
        np.where(result[TARGET_COL].eq(DOWN_FIRST), 0.0, np.nan),
    )
    return result


def _fit_binary(
    train: pd.DataFrame,
    valid: pd.DataFrame | None,
    features: list[str],
    categoricals: list[str],
    config: SharedDirectionalConfig,
    *,
    iterations: int | None = None,
) -> Any:
    from catboost import CatBoostClassifier

    # Contrôle E4-B préfixé : aucune pondération de classe.
    model = CatBoostClassifier(
        iterations=int(iterations or config.iterations), depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=5.0,
        random_seed=config.random_seed, random_strength=1.0,
        bootstrap_type="Bayesian", bagging_temperature=1.0,
        loss_function="Logloss", eval_metric="AUC",
        allow_writing_files=False, verbose=False, thread_count=-1,
    )
    train = train.sort_values(["date", "symbol"])
    kwargs: dict[str, Any] = {"cat_features": categoricals}
    if valid is not None and not valid.empty:
        kwargs.update({
            "eval_set": (
                _prepare_X(valid, features, categoricals),
                valid[BINARY_TARGET_COL].astype(int),
            ),
            "early_stopping_rounds": 60, "use_best_model": True,
        })
    model.fit(
        _prepare_X(train, features, categoricals),
        train[BINARY_TARGET_COL].astype(int),
        **kwargs,
    )
    return model


def score_binary_model(
    model: Any,
    frame: pd.DataFrame,
    features: list[str],
    categoricals: list[str],
) -> pd.DataFrame:
    """Expose le score binaire dans le schéma comparable à E4 multiclasses."""
    probability_up = model.predict_proba(_prepare_X(frame, features, categoricals))[:, 1]
    result = frame.copy()
    result[P_UP_COL] = probability_up
    result[P_DOWN_COL] = 1.0 - probability_up
    result[P_NO_TOUCH_COL] = 0.0
    result[P_AMBIGUOUS_COL] = 0.0
    result[PREDICTED_CLASS_COL] = np.where(
        probability_up >= 0.5, UP_FIRST, DOWN_FIRST
    ).astype(int)
    return result


def train_first_touch_binary(
    dataset: pd.DataFrame,
    features: list[str],
    categoricals: list[str],
    training: SharedDirectionalConfig,
    target_config: FirstTouchConfig,
    artifact_dir: Path,
) -> dict[str, Any]:
    dataset = add_binary_target(dataset)
    folds = build_folds_adaptive(
        dataset, min_train_dates=training.min_train_dates, val_dates=training.val_dates,
        test_dates=training.test_dates, step_dates=training.step_dates,
        max_splits=training.max_splits, forecast_horizon=target_config.max_sessions,
    )
    if not folds:
        raise ValueError("Aucun fold Walk-Forward E4-B valide.")
    oof_parts: list[pd.DataFrame] = []
    iterations: list[int] = []
    fold_diagnostics: list[dict[str, Any]] = []
    for fold_index, fold in enumerate(folds):
        train = fold["train"].dropna(subset=[BINARY_TARGET_COL]).copy()
        valid = fold["val"].dropna(subset=[BINARY_TARGET_COL]).copy()
        # Le test conserve NO_TOUCH et AMBIGUOUS.
        test = fold["test"].dropna(
            subset=[TARGET_COL, LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL]
        ).copy()
        if (
            train.empty or valid.empty or test.empty
            or train[BINARY_TARGET_COL].nunique() != 2
            or valid[BINARY_TARGET_COL].nunique() != 2
        ):
            LOGGER.warning("E4-B fold=%d ignoré: classes/partitions insuffisantes", fold_index)
            continue
        model = _fit_binary(train, valid, features, categoricals, training)
        scored = score_binary_model(model, test, features, categoricals)
        keep = [
            "date", "symbol", TARGET_COL, TARGET_NAME_COL, TOUCH_SESSIONS_COL,
            LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL, ORACLE_GATE_SCORE_COL,
            P_NO_TOUCH_COL, P_DOWN_COL, P_UP_COL, P_AMBIGUOUS_COL,
            PREDICTED_CLASS_COL,
        ]
        scored = scored[keep].copy()
        scored["fold_index"] = fold_index
        oof_parts.append(scored)
        best = int(model.get_best_iteration())
        iterations.append(max(10, best + 1 if best >= 0 else training.iterations))
        evaluation = evaluate_first_touch_oos(scored, target_config)
        primary = evaluation["policies"][f"{target_config.primary_margin:.2f}"]
        fold_diagnostics.append({
            "fold_index": fold_index,
            "test_start": str(pd.Timestamp(test["date"].min()).date()),
            "test_end": str(pd.Timestamp(test["date"].max()).date()),
            "train_rows_binary": int(len(train)),
            "valid_rows_binary": int(len(valid)),
            "test_rows_all_classes": int(len(test)),
            "iterations": iterations[-1],
        })
        LOGGER.info(
            "E4-B fold=%d auc=%s coverage=%.1f%% precision=%s net=%s",
            fold_index, evaluation["directional_auc_up_vs_down"],
            100 * primary.get("coverage", 0.0),
            primary.get("decision_precision"), primary.get("mean_net_return"),
        )
    if not oof_parts:
        raise ValueError("Tous les folds E4-B ont été rejetés.")
    oof = pd.concat(oof_parts, ignore_index=True)
    overall = evaluate_first_touch_oos(oof, target_config)
    stability = _stability(oof, target_config)
    gates = _gates(overall, stability, target_config)
    labeled = dataset.dropna(subset=[BINARY_TARGET_COL]).copy()
    final_iterations = max(10, int(np.median(iterations)))
    final_model = _fit_binary(
        labeled, None, features, categoricals, training, iterations=final_iterations
    )
    artifact_dir.mkdir(parents=True, exist_ok=False)
    model_path = artifact_dir / "first_touch_binary_model.cbm"
    oof_path = artifact_dir / "oof_predictions.parquet"
    final_model.save_model(str(model_path))
    oof.to_parquet(oof_path, index=False)
    metrics = {
        "status": "completed", "research_only": True, "serving_ready": False,
        "model_role": "oracle_conditional_first_touch_binary",
        "n_folds": int(oof["fold_index"].nunique()),
        "final_iterations": final_iterations,
        "trained_rows_binary": int(len(labeled)),
        "trained_symbols": int(labeled["symbol"].nunique()),
        "overall": overall, "fold_stability": stability,
        "fold_diagnostics": fold_diagnostics, "gates": gates,
        "semesters": {
            str(label): evaluate_first_touch_oos(group, target_config)["policies"][
                f"{target_config.primary_margin:.2f}"
            ]
            for label, group in oof.groupby(oof["date"].map(_semester_label), sort=True)
        },
        "artifact_paths": {"model": str(model_path), "oof": str(oof_path)},
    }
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return metrics


def run_first_touch_binary_campaign(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    profile_path: Path = DEFAULT_PROFILE,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    symbols_limit: int | None = None,
    training_config: SharedDirectionalConfig | None = None,
    target_config: FirstTouchConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    target = target_config or FirstTouchConfig()
    training = training_config or SharedDirectionalConfig(
        context_mode="none", amplitude_weighting=False
    )
    profile = load_profile(profile_path)
    symbols = get_universe_symbols(engine, oracle_batch_id, target.max_sessions)
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    gate_path = Path("artifacts/models") / oracle_batch_id / "_oracle_oof_gate.parquet"
    dataset_config = replace(
        training, horizon=target.max_sessions, objective="classifier",
        target_mode="decile_direction", amplitude_weighting=False,
    )
    pool, features, categoricals, population = build_shared_dataset(
        engine, oracle_batch_id, symbols, start_date=start_date, end_date=end_date,
        gate_path=gate_path, profile=profile, config=dataset_config,
    )
    requested_start, requested_end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    pool = pool[pd.to_datetime(pool["date"]).between(requested_start, requested_end)].copy()
    if pool.empty:
        raise ValueError("Pool Oracle E4-B vide dans la période demandée.")
    warmup_start = (requested_start - pd.offsets.BDay(target.atr_window + 5)).date()
    future_end = (requested_end + pd.offsets.BDay(target.max_sessions + 2)).date()
    bars = load_universe_bars(engine, symbols, start_date=warmup_start, end_date=future_end)
    dataset = attach_first_touch_targets(pool, build_first_touch_panel(bars, target))
    race = BarrierRaceConfig(
        max_sessions=target.max_sessions, max_entry_gap_pct=target.max_entry_gap_pct
    )
    dataset = attach_path_targets(dataset, build_path_label_panel(bars, race))
    usable_all = dataset[[TARGET_COL, LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL]].notna().all(axis=1)
    binary_mask = usable_all & dataset[TARGET_COL].isin([DOWN_FIRST, UP_FIRST])
    if int(binary_mask.sum()) < 100:
        raise ValueError(f"Cibles binaires E4-B insuffisantes: {int(binary_mask.sum())} lignes.")
    run_id = (
        f"shared-first-touch-binary-{datetime.now(UTC):%Y%m%d%H%M%S}-"
        f"{oracle_batch_id[-6:]}"
    )
    output = artifacts_root / run_id
    metrics = train_first_touch_binary(
        dataset, features, categoricals, training, target, output
    )
    contract = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "E4_B_oracle_conditional_first_touch_binary_v1",
        "source_oracle_batch_id": oracle_batch_id,
        "status": "completed", "research_only": True, "serving_ready": False,
        "target_contract": {
            "fit_classes": {0: "DOWN_FIRST", 1: "UP_FIRST"},
            "excluded_from_fit": [CLASS_NAMES[NO_TOUCH], CLASS_NAMES[AMBIGUOUS]],
            "excluded_classes_retained_in_oos_evaluation": True,
            "class_weighting": "none", "entry": "next_open_J_plus_1",
            "atr_information_cutoff": "signal_close_J",
            "configuration": asdict(target),
        },
        "conditioning": {
            "source": "oracle_walk_forward_oof_test", "pool_pct": training.pool_pct,
            "oracle_score_is_feature": False, "gate_path": str(gate_path),
        },
        "population": {
            **population, "requested_start": str(requested_start.date()),
            "requested_end": str(requested_end.date()),
            "actual_start": str(pd.Timestamp(pool["date"].min()).date()),
            "actual_end": str(pd.Timestamp(pool["date"].max()).date()),
            "all_class_rows": int(usable_all.sum()),
            "binary_fit_rows": int(binary_mask.sum()),
            "excluded_rare_rows": int((usable_all & ~binary_mask).sum()),
            "up_first_rate_within_binary": float(
                dataset.loc[binary_mask, TARGET_COL].eq(UP_FIRST).mean()
            ),
        },
        "feature_profile": profile, "feature_columns": features,
        "categorical_columns": categoricals,
        "walk_forward": {
            "min_train_dates": training.min_train_dates, "val_dates": training.val_dates,
            "test_dates": training.test_dates, "step_dates": training.step_dates,
            "max_splits": training.max_splits, "purge_sessions": target.max_sessions,
        },
        "policy": {
            "primary_margin": target.primary_margin,
            "selection": "abs(P(UP_FIRST)-P(DOWN_FIRST)) >= margin",
            "threshold_optimization": False,
        },
        "metrics": metrics,
    }
    (output / "contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (output / "feature_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return output, contract


def _summary(path: Path, contract: dict[str, Any]) -> str:
    metrics = contract["metrics"]
    overall = metrics["overall"]
    primary = overall["policies"][f"{contract['policy']['primary_margin']:.2f}"]
    return "\n".join([
        f"E4-B binaire terminé: {path}",
        f"Fit={contract['population']['binary_fit_rows']} folds={metrics['n_folds']} ",
        f"AUC={overall['directional_auc_up_vs_down']} coverage={primary.get('coverage', 0):.1%}",
        f"precision={primary.get('decision_precision', float('nan')):.1%} ",
        f"net={primary.get('mean_net_return', float('nan')):+.2%} "
        f"lift_random={primary.get('lift_vs_random_50_50', float('nan')):+.2%}",
        f"Gates={metrics['gates']['all_gates_passed']}",
        "Serving désactivé: contrôle OOF uniquement.",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--feature-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--symbols-limit", type=int, default=None)
    parser.add_argument("--barrier-atr-mult", type=float, default=3.0)
    parser.add_argument("--barrier-max-pct", type=float, default=0.07)
    parser.add_argument("--max-sessions", type=int, default=20)
    parser.add_argument("--max-entry-gap-pct", type=float, default=0.03)
    parser.add_argument("--primary-margin", type=float, default=PRIMARY_MARGIN)
    parser.add_argument("--wf-min-train-size", type=int, default=504)
    parser.add_argument("--wf-val-size", type=int, default=126)
    parser.add_argument("--wf-test-size", type=int, default=126)
    parser.add_argument("--wf-step-size", type=int, default=126)
    parser.add_argument("--wf-max-splits", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=600)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--context-mode", choices=["symbol_sector", "sector", "none"], default="none")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    target = FirstTouchConfig(
        barrier_atr_mult=args.barrier_atr_mult, barrier_max_pct=args.barrier_max_pct,
        max_sessions=args.max_sessions, max_entry_gap_pct=args.max_entry_gap_pct,
        primary_margin=args.primary_margin,
    )
    training = SharedDirectionalConfig(
        horizon=args.max_sessions, min_train_dates=args.wf_min_train_size,
        val_dates=args.wf_val_size, test_dates=args.wf_test_size,
        step_dates=args.wf_step_size, max_splits=args.wf_max_splits,
        iterations=args.iterations, depth=args.depth, learning_rate=args.learning_rate,
        context_mode=args.context_mode, amplitude_weighting=False,
    )
    path, contract = run_first_touch_binary_campaign(
        get_sqlalchemy_engine(), args.oracle_batch_id,
        start_date=args.start_date, end_date=args.end_date,
        profile_path=args.feature_profile, artifacts_root=args.artifacts_root,
        symbols_limit=args.symbols_limit, training_config=training, target_config=target,
    )
    print(_summary(path, contract))


if __name__ == "__main__":
    main()
