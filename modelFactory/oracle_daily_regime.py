"""E5 research-only: direction commune quotidienne du pool Oracle TOP20.

Une ligne représente une date et non un symbole. La cible continue mesure la
part de premières touches haussières dans le pool Oracle OOF. Deux estimateurs
préfixés (Ridge et CatBoost compact) sont évalués sans sélection postérieure.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.first_touch_directional import (
    DOWN_FIRST,
    UP_FIRST,
    FirstTouchConfig,
    attach_first_touch_targets,
    build_first_touch_panel,
)
from modelFactory.first_touch_directional import (
    TARGET_COL as FIRST_TOUCH_TARGET_COL,
)
from modelFactory.oracle.dataset import GUARD_COL
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
    _semester_label,
    build_shared_dataset,
    load_profile,
)

LOGGER = logging.getLogger(__name__)

DAILY_TARGET_COL = "daily_direction_balance"
UP_RATE_COL = "daily_up_first_rate"
PREDICTION_COL = "predicted_direction_balance"
DECISION_COL = "daily_regime_decision"
CHOSEN_RETURN_COL = "daily_chosen_basket_return"
LONG_BASKET_RETURN_COL = "daily_long_basket_return"
SHORT_BASKET_RETURN_COL = "daily_short_basket_return"
PRIMARY_THRESHOLD = 0.20
DIAGNOSTIC_THRESHOLDS = (0.0, 0.10, PRIMARY_THRESHOLD, 0.30)

COMMON_COLUMNS = [
    "market_return_20",
    "market_trend_strength_50",
    "regime_bull_market",
    "regime_risk_off",
]
MEDIAN_COLUMNS = [
    "daily_return",
    "momentum_5",
    "momentum_20",
    "momentum_60",
    "relative_strength_20",
    "sma20_distance",
    "rsi_14",
    "range_position_20",
]
BREADTH_COLUMNS = [
    "daily_return",
    "momentum_5",
    "momentum_20",
    "momentum_60",
    "relative_strength_20",
    "sma20_distance",
]
DISPERSION_COLUMNS = ["daily_return", "momentum_20", "relative_strength_20"]


@dataclass(frozen=True, slots=True)
class DailyRegimeConfig:
    min_daily_candidates: int = 20
    primary_threshold: float = PRIMARY_THRESHOLD
    ridge_alpha: float = 10.0
    catastrophic_basket_return: float = -0.10
    min_ic: float = 0.10
    min_precision: float = 0.58
    min_coverage: float = 0.30
    min_precision_lift: float = 0.05
    min_return_lift: float = 0.0025

    def __post_init__(self) -> None:
        if self.min_daily_candidates < 2:
            raise ValueError("min_daily_candidates doit être >= 2.")
        if not 0 <= self.primary_threshold < 1:
            raise ValueError("primary_threshold doit être dans [0,1[.")
        if self.ridge_alpha <= 0:
            raise ValueError("ridge_alpha doit être positif.")
        if self.catastrophic_basket_return >= 0:
            raise ValueError("catastrophic_basket_return doit être négatif.")


def _numeric(group: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(group[column], errors="coerce").replace([np.inf, -np.inf], np.nan)


def build_daily_regime_panel(
    events: pd.DataFrame,
    *,
    min_daily_candidates: int = 20,
) -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    """Agrège uniquement des valeurs connues à la date du signal."""
    required = {
        "date", "symbol", GUARD_COL, FIRST_TOUCH_TARGET_COL,
        LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL, ORACLE_GATE_SCORE_COL,
    }
    missing = sorted(required.difference(events.columns))
    if missing:
        raise ValueError(f"Événements E5 incomplets: {missing}")
    available_common = [column for column in COMMON_COLUMNS if column in events.columns]
    available_median = [column for column in MEDIAN_COLUMNS if column in events.columns]
    available_breadth = [column for column in BREADTH_COLUMNS if column in events.columns]
    available_dispersion = [column for column in DISPERSION_COLUMNS if column in events.columns]
    rows: list[dict[str, Any]] = []
    rejected_small = 0
    for date, group in events.groupby("date", sort=True):
        valid_target = group[FIRST_TOUCH_TARGET_COL].isin([DOWN_FIRST, UP_FIRST])
        directional = group.loc[valid_target]
        if len(directional) < min_daily_candidates:
            rejected_small += 1
            continue
        up_rate = float(directional[FIRST_TOUCH_TARGET_COL].eq(UP_FIRST).mean())
        row: dict[str, Any] = {
            "date": pd.Timestamp(date).normalize(),
            GUARD_COL: pd.to_datetime(group[GUARD_COL], errors="coerce").max(),
            "daily_candidate_count": int(len(group)),
            "daily_directional_count": int(len(directional)),
            "daily_directional_share": float(len(directional) / len(group)),
            UP_RATE_COL: up_rate,
            DAILY_TARGET_COL: 2.0 * up_rate - 1.0,
            LONG_BASKET_RETURN_COL: float(_numeric(group, LONG_NET_RETURN_COL).mean()),
            SHORT_BASKET_RETURN_COL: float(_numeric(group, SHORT_NET_RETURN_COL).mean()),
        }
        for column in available_common:
            row[f"common_{column}"] = float(_numeric(group, column).median())
        for column in available_median:
            row[f"median_{column}"] = float(_numeric(group, column).median())
        for column in available_breadth:
            values = _numeric(group, column).dropna()
            row[f"breadth_positive_{column}"] = float(values.gt(0).mean()) if len(values) else np.nan
        for column in available_dispersion:
            row[f"dispersion_{column}"] = float(_numeric(group, column).std(ddof=0))
        oracle = _numeric(group, ORACLE_GATE_SCORE_COL)
        row["oracle_score_mean"] = float(oracle.mean())
        row["oracle_score_dispersion"] = float(oracle.std(ddof=0))
        rows.append(row)
    panel = pd.DataFrame(rows)
    if panel.empty:
        raise ValueError("Panel quotidien E5 vide.")
    panel = panel.sort_values("date").reset_index(drop=True)
    if panel["date"].duplicated().any():
        raise ValueError("Le panel E5 doit contenir une seule ligne par date.")
    excluded = {
        "date", GUARD_COL, "daily_candidate_count", "daily_directional_count",
        "daily_directional_share", UP_RATE_COL, DAILY_TARGET_COL,
        LONG_BASKET_RETURN_COL, SHORT_BASKET_RETURN_COL,
    }
    features = [column for column in panel.columns if column not in excluded]
    diagnostics = {
        "dates": int(len(panel)),
        "first_date": str(panel["date"].min().date()),
        "last_date": str(panel["date"].max().date()),
        "feature_count": len(features),
        "features": features,
        "rejected_dates_below_min_candidates": rejected_small,
        "candidate_count": panel["daily_candidate_count"].describe().to_dict(),
        "directional_share_mean": float(panel["daily_directional_share"].mean()),
        "up_rate_mean": float(panel[UP_RATE_COL].mean()),
        "majority_share_mean": float(np.maximum(panel[UP_RATE_COL], 1-panel[UP_RATE_COL]).mean()),
        "majority_share_median": float(np.maximum(panel[UP_RATE_COL], 1-panel[UP_RATE_COL]).median()),
        "days_majority_gte_60pct": float(
            np.maximum(panel[UP_RATE_COL], 1-panel[UP_RATE_COL]).ge(0.60).mean()
        ),
    }
    return panel, features, diagnostics


def _prepare_numeric(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    result = frame[features].copy()
    for column in features:
        result[column] = pd.to_numeric(result[column], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )
    return result


def _fit_ridge(train: pd.DataFrame, features: list[str], alpha: float) -> Any:
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("ridge", Ridge(alpha=alpha)),
    ])
    model.fit(_prepare_numeric(train, features), train[DAILY_TARGET_COL].astype(float))
    return model


def _fit_catboost(
    train: pd.DataFrame,
    valid: pd.DataFrame | None,
    features: list[str],
    training: SharedDirectionalConfig,
    *,
    iterations: int | None = None,
) -> Any:
    from catboost import CatBoostRegressor

    model = CatBoostRegressor(
        iterations=int(iterations or training.iterations), depth=training.depth,
        learning_rate=training.learning_rate, l2_leaf_reg=10.0,
        loss_function="RMSE", eval_metric="RMSE", random_seed=training.random_seed,
        random_strength=1.0, bootstrap_type="Bayesian", bagging_temperature=1.0,
        allow_writing_files=False, verbose=False, thread_count=-1,
    )
    kwargs: dict[str, Any] = {}
    if valid is not None and not valid.empty:
        kwargs.update({
            "eval_set": (
                _prepare_numeric(valid, features), valid[DAILY_TARGET_COL].astype(float)
            ),
            "early_stopping_rounds": 60, "use_best_model": True,
        })
    model.fit(
        _prepare_numeric(train, features), train[DAILY_TARGET_COL].astype(float), **kwargs
    )
    return model


def apply_daily_policy(frame: pd.DataFrame, threshold: float) -> pd.DataFrame:
    if not 0 <= threshold < 1:
        raise ValueError("Le seuil E5 doit être dans [0,1[.")
    result = frame.copy()
    score = pd.to_numeric(result[PREDICTION_COL], errors="coerce")
    if threshold == 0:
        long_mask, short_mask = score.gt(0), score.lt(0)
    else:
        long_mask, short_mask = score.ge(threshold), score.le(-threshold)
    result[DECISION_COL] = "ABSTAIN"
    result.loc[long_mask, DECISION_COL] = "LONG_DAY"
    result.loc[short_mask, DECISION_COL] = "SHORT_DAY"
    result[CHOSEN_RETURN_COL] = np.nan
    result.loc[long_mask, CHOSEN_RETURN_COL] = result.loc[long_mask, LONG_BASKET_RETURN_COL]
    result.loc[short_mask, CHOSEN_RETURN_COL] = result.loc[short_mask, SHORT_BASKET_RETURN_COL]
    return result


def _cvar(values: pd.Series, fraction: float = 0.05) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna().sort_values()
    if numeric.empty:
        return None
    return float(numeric.iloc[:max(1, math.ceil(len(numeric) * fraction))].mean())


def _policy_metrics(frame: pd.DataFrame, threshold: float, catastrophic: float) -> dict[str, Any]:
    policy = apply_daily_policy(frame, threshold)
    selected = policy[policy[DECISION_COL].ne("ABSTAIN")].copy()
    if selected.empty:
        return {"rows": 0, "coverage": 0.0}
    decision_long = selected[DECISION_COL].eq("LONG_DAY")
    truth = pd.to_numeric(selected[DAILY_TARGET_COL], errors="coerce")
    correct = (decision_long & truth.gt(0)) | (~decision_long & truth.lt(0))
    long_return = pd.to_numeric(selected[LONG_BASKET_RETURN_COL], errors="coerce")
    short_return = pd.to_numeric(selected[SHORT_BASKET_RETURN_COL], errors="coerce")
    chosen = pd.to_numeric(selected[CHOSEN_RETURN_COL], errors="coerce")
    random_expected = (long_return + short_return) / 2.0
    majority_baseline = max(float(truth.gt(0).mean()), float(truth.lt(0).mean()))
    long_count = int(decision_long.sum())
    short_count = int((~decision_long).sum())
    return {
        "rows": int(len(selected)), "coverage": float(len(selected) / len(frame)),
        "long_days": long_count, "short_days": short_count,
        "long_share": float(long_count / len(selected)),
        "short_share": float(short_count / len(selected)),
        "direction_accuracy": float(correct.mean()),
        "majority_direction_baseline": majority_baseline,
        "accuracy_lift_vs_majority": float(correct.mean() - majority_baseline),
        "mean_realized_majority_share": float(
            np.maximum(selected[UP_RATE_COL], 1-selected[UP_RATE_COL]).mean()
        ),
        "mean_chosen_basket_return": float(chosen.mean()),
        "median_chosen_basket_return": float(chosen.median()),
        "positive_basket_day_rate": float(chosen.gt(0).mean()),
        "always_long_return": float(long_return.mean()),
        "always_short_return": float(short_return.mean()),
        "random_50_50_expected_return": float(random_expected.mean()),
        "best_static_side_return": max(float(long_return.mean()), float(short_return.mean())),
        "lift_vs_random_50_50": float(chosen.mean() - random_expected.mean()),
        "lift_vs_best_static_side": float(
            chosen.mean() - max(long_return.mean(), short_return.mean())
        ),
        "catastrophic_basket_day_rate": float(chosen.le(catastrophic).mean()),
        "cvar_05": _cvar(chosen), "worst_basket_return": float(chosen.min()),
    }


def evaluate_daily_predictions(
    frame: pd.DataFrame,
    config: DailyRegimeConfig | None = None,
) -> dict[str, Any]:
    cfg = config or DailyRegimeConfig()
    required = [
        "date", DAILY_TARGET_COL, UP_RATE_COL, PREDICTION_COL,
        LONG_BASKET_RETURN_COL, SHORT_BASKET_RETURN_COL,
    ]
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"Prédictions E5 incomplètes: {missing}")
    work = frame.dropna(subset=required).copy()
    prediction = pd.to_numeric(work[PREDICTION_COL], errors="coerce")
    target = pd.to_numeric(work[DAILY_TARGET_COL], errors="coerce")
    pearson = float(prediction.corr(target))
    spearman = float(prediction.rank().corr(target.rank()))
    return {
        "rows": int(len(work)),
        "pearson_ic": pearson, "spearman_ic": spearman,
        "rmse": float(np.sqrt(np.mean(np.square(prediction-target)))),
        "mae": float(np.mean(np.abs(prediction-target))),
        "prediction_mean": float(prediction.mean()),
        "prediction_std": float(prediction.std(ddof=0)),
        "policies": {
            f"{threshold:.2f}": _policy_metrics(
                work, threshold, cfg.catastrophic_basket_return
            )
            for threshold in DIAGNOSTIC_THRESHOLDS
        },
    }


def _trend_baselines(frame: pd.DataFrame, config: DailyRegimeConfig) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for name, column in (
        ("spy_trend_50", "common_market_trend_strength_50"),
        ("spy_return_20", "common_market_return_20"),
    ):
        if column not in frame.columns:
            continue
        baseline = frame.copy()
        baseline[PREDICTION_COL] = np.sign(pd.to_numeric(baseline[column], errors="coerce"))
        outputs[name] = _policy_metrics(baseline, 0.0, config.catastrophic_basket_return)
    return outputs


def _stability(oof: pd.DataFrame, model_name: str, config: DailyRegimeConfig) -> dict[str, Any]:
    folds: list[dict[str, Any]] = []
    for fold_index, group in oof.groupby("fold_index", sort=True):
        scored = group.copy()
        scored[PREDICTION_COL] = scored[f"{model_name}_prediction"]
        evaluation = evaluate_daily_predictions(scored, config)
        folds.append({
            "fold_index": int(fold_index),
            "pearson_ic": evaluation["pearson_ic"],
            "spearman_ic": evaluation["spearman_ic"],
            **evaluation["policies"][f"{config.primary_threshold:.2f}"],
        })
    return {
        "folds": folds,
        "mean_spearman_ic": float(np.nanmean([fold["spearman_ic"] for fold in folds])),
        "positive_ic_folds": int(sum(fold["spearman_ic"] > 0 for fold in folds)),
        "positive_lift_folds": int(sum(fold.get("lift_vs_random_50_50", -1) > 0 for fold in folds)),
        "positive_return_folds": int(sum(
            fold.get("mean_chosen_basket_return", -1) > 0 for fold in folds
        )),
        "beats_static_folds": int(sum(fold.get("lift_vs_best_static_side", -1) > 0 for fold in folds)),
    }


def _gates(overall: dict[str, Any], stability: dict[str, Any], config: DailyRegimeConfig) -> dict[str, Any]:
    primary = overall["policies"][f"{config.primary_threshold:.2f}"]
    values = {
        "spearman_ic_gte_0_10": bool(overall["spearman_ic"] >= config.min_ic),
        "mean_fold_spearman_ic_gte_0_10": bool(stability["mean_spearman_ic"] >= config.min_ic),
        "positive_ic_folds_gte_7": bool(stability["positive_ic_folds"] >= 7),
        "coverage_gte_0_30": bool(primary.get("coverage", 0) >= config.min_coverage),
        "direction_accuracy_gte_0_58": bool(
            primary.get("direction_accuracy", 0) >= config.min_precision
        ),
        "accuracy_lift_vs_majority_gte_0_05": bool(
            primary.get("accuracy_lift_vs_majority", -1) >= config.min_precision_lift
        ),
        "both_side_shares_gte_0_15": bool(
            min(primary.get("long_share", 0), primary.get("short_share", 0)) >= 0.15
        ),
        "mean_basket_return_positive": bool(
            primary.get("mean_chosen_basket_return", -1) > 0
        ),
        "lift_vs_random_gte_0_0025": bool(
            primary.get("lift_vs_random_50_50", -1) >= config.min_return_lift
        ),
        "positive_lift_folds_gte_7": bool(stability["positive_lift_folds"] >= 7),
        "positive_return_folds_gte_7": bool(stability["positive_return_folds"] >= 7),
        "beats_static_folds_gte_7": bool(stability["beats_static_folds"] >= 7),
    }
    return {"values": values, "all_gates_passed": bool(all(values.values()))}


def train_daily_regime(
    panel: pd.DataFrame,
    features: list[str],
    training: SharedDirectionalConfig,
    config: DailyRegimeConfig,
    artifact_dir: Path,
) -> dict[str, Any]:
    folds = build_folds_adaptive(
        panel, min_train_dates=training.min_train_dates, val_dates=training.val_dates,
        test_dates=training.test_dates, step_dates=training.step_dates,
        max_splits=training.max_splits, forecast_horizon=20,
    )
    if not folds:
        raise ValueError("Aucun fold Walk-Forward E5 valide.")
    oof_parts: list[pd.DataFrame] = []
    iterations: list[int] = []
    fold_diagnostics: list[dict[str, Any]] = []
    for fold_index, fold in enumerate(folds):
        train, valid, test = fold["train"].copy(), fold["val"].copy(), fold["test"].copy()
        ridge = _fit_ridge(train, features, config.ridge_alpha)
        catboost = _fit_catboost(train, valid, features, training)
        scored = test[[
            "date", GUARD_COL, DAILY_TARGET_COL, UP_RATE_COL,
            "daily_candidate_count", "daily_directional_count", "daily_directional_share",
            LONG_BASKET_RETURN_COL, SHORT_BASKET_RETURN_COL, *features,
        ]].copy()
        scored["ridge_prediction"] = ridge.predict(_prepare_numeric(test, features))
        scored["catboost_prediction"] = catboost.predict(_prepare_numeric(test, features))
        scored["fold_index"] = fold_index
        oof_parts.append(scored)
        best = int(catboost.get_best_iteration())
        iterations.append(max(10, best + 1 if best >= 0 else training.iterations))
        fold_diagnostics.append({
            "fold_index": fold_index,
            "test_start": str(pd.Timestamp(test["date"].min()).date()),
            "test_end": str(pd.Timestamp(test["date"].max()).date()),
            "train_dates": int(len(train)), "valid_dates": int(len(valid)),
            "test_dates": int(len(test)), "catboost_iterations": iterations[-1],
        })
        LOGGER.info("E5 fold=%d test=%s→%s", fold_index, fold_diagnostics[-1]["test_start"], fold_diagnostics[-1]["test_end"])
    oof = pd.concat(oof_parts, ignore_index=True)
    evaluations: dict[str, Any] = {}
    stabilities: dict[str, Any] = {}
    gates: dict[str, Any] = {}
    semesters: dict[str, Any] = {}
    for model_name in ("ridge", "catboost"):
        scored = oof.copy()
        scored[PREDICTION_COL] = scored[f"{model_name}_prediction"]
        evaluations[model_name] = evaluate_daily_predictions(scored, config)
        stabilities[model_name] = _stability(oof, model_name, config)
        gates[model_name] = _gates(evaluations[model_name], stabilities[model_name], config)
        semesters[model_name] = {
            str(label): evaluate_daily_predictions(group.assign(
                **{PREDICTION_COL: group[f"{model_name}_prediction"]}
            ), config)["policies"][f"{config.primary_threshold:.2f}"]
            for label, group in oof.groupby(oof["date"].map(_semester_label), sort=True)
        }
    final_ridge = _fit_ridge(panel, features, config.ridge_alpha)
    final_iterations = max(10, int(np.median(iterations)))
    final_catboost = _fit_catboost(
        panel, None, features, training, iterations=final_iterations
    )
    artifact_dir.mkdir(parents=True, exist_ok=False)
    import joblib
    ridge_path = artifact_dir / "ridge_model.joblib"
    catboost_path = artifact_dir / "catboost_model.cbm"
    oof_path = artifact_dir / "oof_predictions.parquet"
    panel_path = artifact_dir / "daily_panel.parquet"
    joblib.dump(final_ridge, ridge_path)
    final_catboost.save_model(str(catboost_path))
    oof.to_parquet(oof_path, index=False)
    panel.to_parquet(panel_path, index=False)
    benchmark = _trend_baselines(oof, config)
    metrics = {
        "status": "completed", "research_only": True, "serving_ready": False,
        "model_role": "oracle_daily_regime_direction",
        "n_folds": int(oof["fold_index"].nunique()),
        "final_catboost_iterations": final_iterations,
        "trained_dates": int(len(panel)), "feature_count": len(features),
        "evaluations": evaluations, "fold_stability": stabilities,
        "gates": gates, "semesters": semesters,
        "trend_baselines": benchmark, "fold_diagnostics": fold_diagnostics,
        "artifact_paths": {
            "ridge": str(ridge_path), "catboost": str(catboost_path),
            "oof": str(oof_path), "daily_panel": str(panel_path),
        },
    }
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return metrics


def run_daily_regime_campaign(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    profile_path: Path = DEFAULT_PROFILE,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    symbols_limit: int | None = None,
    training_config: SharedDirectionalConfig | None = None,
    regime_config: DailyRegimeConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    regime = regime_config or DailyRegimeConfig()
    training = training_config or SharedDirectionalConfig(
        context_mode="none", amplitude_weighting=False,
        iterations=400, depth=4, learning_rate=0.03,
    )
    touch = FirstTouchConfig()
    profile = load_profile(profile_path)
    symbols = get_universe_symbols(engine, oracle_batch_id, touch.max_sessions)
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    gate_path = Path("artifacts/models") / oracle_batch_id / "_oracle_oof_gate.parquet"
    dataset_config = replace(
        training, horizon=touch.max_sessions, objective="classifier",
        target_mode="decile_direction", amplitude_weighting=False,
    )
    pool, source_features, _, population = build_shared_dataset(
        engine, oracle_batch_id, symbols, start_date=start_date, end_date=end_date,
        gate_path=gate_path, profile=profile, config=dataset_config,
    )
    requested_start, requested_end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    pool = pool[pd.to_datetime(pool["date"]).between(requested_start, requested_end)].copy()
    warmup_start = (requested_start - pd.offsets.BDay(touch.atr_window + 5)).date()
    future_end = (requested_end + pd.offsets.BDay(touch.max_sessions + 2)).date()
    bars = load_universe_bars(engine, symbols, start_date=warmup_start, end_date=future_end)
    events = attach_first_touch_targets(pool, build_first_touch_panel(bars, touch))
    events = attach_path_targets(
        events, build_path_label_panel(bars, BarrierRaceConfig(max_sessions=20))
    )
    events = events.dropna(subset=[FIRST_TOUCH_TARGET_COL, LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL])
    panel, features, diagnostics = build_daily_regime_panel(
        events, min_daily_candidates=regime.min_daily_candidates
    )
    if len(features) > 26:
        raise ValueError(f"E5 doit rester compact; {len(features)} features détectées.")
    run_id = f"shared-daily-regime-{datetime.now(UTC):%Y%m%d%H%M%S}-{oracle_batch_id[-6:]}"
    output = artifacts_root / run_id
    metrics = train_daily_regime(panel, features, training, regime, output)
    contract = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "E5_oracle_daily_regime_direction_v1",
        "source_oracle_batch_id": oracle_batch_id,
        "status": "completed", "research_only": True, "serving_ready": False,
        "target_contract": {
            "unit": "one_row_per_signal_date",
            "target": "2 * UP_FIRST_rate - 1",
            "directional_denominator": "UP_FIRST + DOWN_FIRST",
            "rare_classes_excluded_from_target_denominator": ["NO_TOUCH", "AMBIGUOUS"],
            "minimum_candidates": regime.min_daily_candidates,
            "first_touch_contract": asdict(touch),
        },
        "policy": {
            "primary_threshold": regime.primary_threshold,
            "long": "prediction >= +threshold", "short": "prediction <= -threshold",
            "otherwise": "ABSTAIN", "threshold_optimization": False,
        },
        "conditioning": {
            "source": "oracle_walk_forward_oof_test", "pool_pct": training.pool_pct,
            "individual_oracle_score_is_feature": False,
            "daily_oracle_distribution_aggregates": True, "gate_path": str(gate_path),
        },
        "population": {
            **population, "requested_start": str(requested_start.date()),
            "requested_end": str(requested_end.date()),
            "actual_start": str(panel["date"].min().date()),
            "actual_end": str(panel["date"].max().date()),
            "event_rows": int(len(events)), "daily_diagnostics": diagnostics,
        },
        "source_feature_profile": profile,
        "source_symbol_features": source_features,
        "daily_feature_columns": features,
        "models": {
            "ridge": {"alpha": regime.ridge_alpha, "hyperparameter_tuning": False},
            "catboost": {
                "iterations": training.iterations, "depth": training.depth,
                "learning_rate": training.learning_rate, "hyperparameter_tuning": False,
            },
        },
        "walk_forward": {
            "min_train_dates": training.min_train_dates, "val_dates": training.val_dates,
            "test_dates": training.test_dates, "step_dates": training.step_dates,
            "max_splits": training.max_splits, "purge_sessions": 20,
        },
        "gates": asdict(regime), "metrics": metrics,
    }
    (output / "contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (output / "daily_feature_contract.json").write_text(
        json.dumps({"schema_version": 1, "features": features}, indent=2), encoding="utf-8"
    )
    return output, contract


def _summary(path: Path, contract: dict[str, Any]) -> str:
    lines = [f"E5 daily-regime terminé: {path}"]
    for model in ("ridge", "catboost"):
        evaluation = contract["metrics"]["evaluations"][model]
        primary = evaluation["policies"][f"{contract['policy']['primary_threshold']:.2f}"]
        lines.append(
            f"{model}: IC={evaluation['spearman_ic']:+.4f} "
            f"coverage={primary.get('coverage', 0):.1%} "
            f"accuracy={primary.get('direction_accuracy', float('nan')):.1%} "
            f"net={primary.get('mean_chosen_basket_return', float('nan')):+.2%} "
            f"gates={contract['metrics']['gates'][model]['all_gates_passed']}"
        )
    lines.append("Serving désactivé: expérience quotidienne OOF uniquement.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--feature-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--symbols-limit", type=int, default=None)
    parser.add_argument("--min-daily-candidates", type=int, default=20)
    parser.add_argument("--primary-threshold", type=float, default=PRIMARY_THRESHOLD)
    parser.add_argument("--ridge-alpha", type=float, default=10.0)
    parser.add_argument("--wf-min-train-size", type=int, default=504)
    parser.add_argument("--wf-val-size", type=int, default=126)
    parser.add_argument("--wf-test-size", type=int, default=126)
    parser.add_argument("--wf-step-size", type=int, default=126)
    parser.add_argument("--wf-max-splits", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=400)
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    regime = DailyRegimeConfig(
        min_daily_candidates=args.min_daily_candidates,
        primary_threshold=args.primary_threshold, ridge_alpha=args.ridge_alpha,
    )
    training = SharedDirectionalConfig(
        horizon=20, min_train_dates=args.wf_min_train_size,
        val_dates=args.wf_val_size, test_dates=args.wf_test_size,
        step_dates=args.wf_step_size, max_splits=args.wf_max_splits,
        iterations=args.iterations, depth=args.depth, learning_rate=args.learning_rate,
        context_mode="none", amplitude_weighting=False,
    )
    path, contract = run_daily_regime_campaign(
        get_sqlalchemy_engine(), args.oracle_batch_id,
        start_date=args.start_date, end_date=args.end_date,
        profile_path=args.feature_profile, artifacts_root=args.artifacts_root,
        symbols_limit=args.symbols_limit, training_config=training, regime_config=regime,
    )
    print(_summary(path, contract))


if __name__ == "__main__":
    main()
