"""E3-A2 research-only: utilité économique conditionnelle aux événements Oracle.

Cette expérience complète E3-A sans modifier le serving. Pour chaque côté,
elle entraîne un régresseur du rendement net path-aware et un classifieur de
perte extrême. Le score économique combine les deux estimations, puis il est
normalisé quotidiennement avant de classer les candidats Oracle.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.oracle.train import get_universe_symbols
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.path_aware_directional import (
    LONG_EXIT_REASON_COL,
    LONG_NET_RETURN_COL,
    SHORT_EXIT_REASON_COL,
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
    _tail,
    build_shared_dataset,
    load_profile,
)

LOGGER = logging.getLogger(__name__)

LONG_EXPECTED_RETURN_COL = "predicted_long_net_return"
SHORT_EXPECTED_RETURN_COL = "predicted_short_net_return"
LONG_TAIL_RISK_COL = "predicted_long_extreme_loss_probability"
SHORT_TAIL_RISK_COL = "predicted_short_extreme_loss_probability"
LONG_UTILITY_RAW_COL = "long_economic_utility_raw"
SHORT_UTILITY_RAW_COL = "short_economic_utility_raw"
LONG_UTILITY_RANK_COL = "long_economic_utility_daily_rank"
SHORT_UTILITY_RANK_COL = "short_economic_utility_daily_rank"


@dataclass(frozen=True, slots=True)
class EconomicUtilityConfig:
    """Contrat économique E3-A2, séparé du lifecycle de production."""

    catastrophic_loss_threshold: float = -0.20
    risk_penalty_return: float = 0.20
    target_winsor_lower: float = 0.01
    target_winsor_upper: float = 0.99
    top_fraction: float = 0.10

    def __post_init__(self) -> None:
        if self.catastrophic_loss_threshold >= 0:
            raise ValueError("catastrophic_loss_threshold doit être négatif.")
        if self.risk_penalty_return < 0:
            raise ValueError("risk_penalty_return doit être >= 0.")
        if not 0 <= self.target_winsor_lower < self.target_winsor_upper <= 1:
            raise ValueError("Quantiles de winsorisation E3-A2 invalides.")
        if not 0 < self.top_fraction < 0.5:
            raise ValueError("top_fraction doit être dans ]0, 0.5[.")


def _catboost_common(config: SharedDirectionalConfig, iterations: int | None) -> dict[str, Any]:
    return {
        "iterations": int(iterations or config.iterations),
        "depth": config.depth,
        "learning_rate": config.learning_rate,
        "l2_leaf_reg": 5.0,
        "random_seed": config.random_seed,
        "random_strength": 1.0,
        "bootstrap_type": "Bayesian",
        "bagging_temperature": 1.0,
        "allow_writing_files": False,
        "verbose": False,
        "thread_count": -1,
    }


def target_winsor_bounds(
    train: pd.DataFrame,
    target_column: str,
    config: EconomicUtilityConfig,
) -> tuple[float, float]:
    """Calcule les bornes sur le train uniquement pour éviter toute fuite."""
    values = pd.to_numeric(train[target_column], errors="coerce").dropna()
    if values.empty:
        raise ValueError(f"Cible économique vide: {target_column}")
    lower = float(values.quantile(config.target_winsor_lower))
    upper = float(values.quantile(config.target_winsor_upper))
    if not np.isfinite(lower) or not np.isfinite(upper) or lower >= upper:
        raise ValueError(f"Bornes de winsorisation invalides: {target_column}")
    return lower, upper


def _fit_return_model(
    train: pd.DataFrame,
    valid: pd.DataFrame | None,
    feature_columns: list[str],
    categorical_columns: list[str],
    training: SharedDirectionalConfig,
    utility: EconomicUtilityConfig,
    target_column: str,
    *,
    iterations: int | None = None,
    bounds: tuple[float, float] | None = None,
) -> tuple[Any, tuple[float, float]]:
    from catboost import CatBoostRegressor

    lower, upper = bounds or target_winsor_bounds(train, target_column, utility)
    ordered_train = train.sort_values(["date", "symbol"])
    y_train = pd.to_numeric(ordered_train[target_column], errors="coerce").clip(lower, upper)
    model = CatBoostRegressor(loss_function="RMSE", eval_metric="RMSE", **_catboost_common(training, iterations))
    kwargs: dict[str, Any] = {"cat_features": categorical_columns}
    if valid is not None and not valid.empty:
        ordered_valid = valid.sort_values(["date", "symbol"])
        y_valid = pd.to_numeric(ordered_valid[target_column], errors="coerce").clip(lower, upper)
        kwargs.update({
            "eval_set": (_prepare_X(ordered_valid, feature_columns, categorical_columns), y_valid),
            "early_stopping_rounds": 60,
            "use_best_model": True,
        })
    model.fit(
        _prepare_X(ordered_train, feature_columns, categorical_columns),
        y_train,
        **kwargs,
    )
    return model, (lower, upper)


def _fit_tail_risk_model(
    train: pd.DataFrame,
    valid: pd.DataFrame | None,
    feature_columns: list[str],
    categorical_columns: list[str],
    training: SharedDirectionalConfig,
    utility: EconomicUtilityConfig,
    target_column: str,
    *,
    iterations: int | None = None,
) -> Any:
    from catboost import CatBoostClassifier

    ordered_train = train.sort_values(["date", "symbol"])
    y_train = pd.to_numeric(ordered_train[target_column], errors="coerce").le(
        utility.catastrophic_loss_threshold
    ).astype(int)
    if y_train.nunique() != 2:
        raise ValueError(f"Classe de perte extrême absente du train: {target_column}")
    model = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="AUC",
        auto_class_weights="Balanced",
        **_catboost_common(training, iterations),
    )
    kwargs: dict[str, Any] = {"cat_features": categorical_columns}
    if valid is not None and not valid.empty:
        ordered_valid = valid.sort_values(["date", "symbol"])
        y_valid = pd.to_numeric(ordered_valid[target_column], errors="coerce").le(
            utility.catastrophic_loss_threshold
        ).astype(int)
        if y_valid.nunique() == 2:
            kwargs.update({
                "eval_set": (_prepare_X(ordered_valid, feature_columns, categorical_columns), y_valid),
                "early_stopping_rounds": 60,
                "use_best_model": True,
            })
    model.fit(
        _prepare_X(ordered_train, feature_columns, categorical_columns),
        y_train,
        **kwargs,
    )
    return model


def add_economic_scores(frame: pd.DataFrame, config: EconomicUtilityConfig) -> pd.DataFrame:
    """Combine rendement et tail-risk, puis normalise le classement par date."""
    result = frame.copy()
    result[LONG_UTILITY_RAW_COL] = (
        result[LONG_EXPECTED_RETURN_COL]
        - config.risk_penalty_return * result[LONG_TAIL_RISK_COL]
    )
    result[SHORT_UTILITY_RAW_COL] = (
        result[SHORT_EXPECTED_RETURN_COL]
        - config.risk_penalty_return * result[SHORT_TAIL_RISK_COL]
    )
    result[LONG_UTILITY_RANK_COL] = result.groupby("date")[LONG_UTILITY_RAW_COL].rank(
        method="average", pct=True
    )
    result[SHORT_UTILITY_RANK_COL] = result.groupby("date")[SHORT_UTILITY_RAW_COL].rank(
        method="average", pct=True
    )
    return result


def _mean_daily_spearman(frame: pd.DataFrame, score_col: str, return_col: str) -> float | None:
    values: list[float] = []
    for _, group in frame.groupby("date", sort=False):
        valid = group[[score_col, return_col]].dropna()
        if len(valid) >= 3 and valid[score_col].nunique() > 1:
            values.append(float(valid[score_col].corr(valid[return_col], method="spearman")))
    return float(np.nanmean(values)) if values else None


def _cvar(values: pd.Series, fraction: float = 0.05) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna().sort_values()
    if numeric.empty:
        return None
    count = max(1, int(np.ceil(len(numeric) * fraction)))
    return float(numeric.iloc[:count].mean())


def _concentration(selected: pd.DataFrame, return_col: str) -> dict[str, Any]:
    if selected.empty:
        return {"top1_positive_contribution_share": None, "top5_positive_contribution_share": None}
    totals = selected.groupby("symbol")[return_col].sum().sort_values(ascending=False)
    positive_total = float(totals.clip(lower=0).sum())
    return {
        "top1_positive_contribution_share": (
            float(max(0.0, totals.iloc[0]) / positive_total) if positive_total > 0 else None
        ),
        "top5_positive_contribution_share": (
            float(totals.head(5).clip(lower=0).sum() / positive_total) if positive_total > 0 else None
        ),
        "top_profit_symbols": [str(value) for value in totals.head(5).index],
    }


def _economic_side_metrics(
    selected: pd.DataFrame,
    pool: pd.DataFrame,
    *,
    side: str,
    config: EconomicUtilityConfig,
) -> dict[str, Any]:
    return_col = LONG_NET_RETURN_COL if side == "long" else SHORT_NET_RETURN_COL
    score_col = LONG_UTILITY_RANK_COL if side == "long" else SHORT_UTILITY_RANK_COL
    if selected.empty:
        return {
            "rows": 0, "dates": 0, "symbols": 0, "success_rate": None,
            "mean_net_return": None, "median_net_return": None,
            "matched_date_return": None, "return_lift_vs_matched": None,
            "catastrophic_loss_rate": None, "matched_catastrophic_loss_rate": None,
            "cvar_05": None, "matched_date_cvar_05": None, "cvar_lift_vs_matched": None,
            "mean_daily_ic": None, "concentration": _concentration(selected, return_col),
        }
    date_base = pool.groupby("date")[return_col].mean()
    matched_return = float(date_base.reindex(selected["date"]).mean())
    pool_cat = pd.to_numeric(pool[return_col], errors="coerce").le(
        config.catastrophic_loss_threshold
    ).groupby(pool["date"]).mean()
    matched_cat = float(pool_cat.reindex(selected["date"]).mean())
    daily_pool_cvar = pool.groupby("date")[return_col].apply(_cvar)
    matched_cvar = float(daily_pool_cvar.reindex(selected["date"]).mean())
    values = pd.to_numeric(selected[return_col], errors="coerce")
    selected_cvar = _cvar(values)
    return {
        "rows": int(len(selected)),
        "dates": int(selected["date"].nunique()),
        "symbols": int(selected["symbol"].nunique()),
        "success_rate": float(values.gt(0).mean()),
        "mean_net_return": float(values.mean()),
        "median_net_return": float(values.median()),
        "matched_date_return": matched_return,
        "return_lift_vs_matched": float(values.mean() - matched_return),
        "catastrophic_loss_rate": float(values.le(config.catastrophic_loss_threshold).mean()),
        "matched_catastrophic_loss_rate": matched_cat,
        "cvar_05": selected_cvar,
        "matched_date_cvar_05": matched_cvar,
        "cvar_lift_vs_matched": (
            float(selected_cvar - matched_cvar) if selected_cvar is not None else None
        ),
        "mean_daily_ic": _mean_daily_spearman(pool, score_col, return_col),
        "concentration": _concentration(selected, return_col),
    }


def evaluate_economic_oos(
    frame: pd.DataFrame,
    config: EconomicUtilityConfig | None = None,
) -> dict[str, Any]:
    utility = config or EconomicUtilityConfig()
    required = [
        "date", "symbol", LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL,
        LONG_EXPECTED_RETURN_COL, SHORT_EXPECTED_RETURN_COL,
        LONG_TAIL_RISK_COL, SHORT_TAIL_RISK_COL,
    ]
    work = frame.dropna(subset=required).copy()
    if work.empty:
        return {"rows": 0}
    work = add_economic_scores(work, utility)
    long_selected = _tail(work, LONG_UTILITY_RANK_COL, utility.top_fraction, ascending=False)
    short_selected = _tail(work, SHORT_UTILITY_RANK_COL, utility.top_fraction, ascending=False)
    semesters: dict[str, Any] = {}
    for semester, group in work.groupby(work["date"].map(_semester_label), sort=True):
        semesters[str(semester)] = {
            "rows": int(len(group)),
            "long": _economic_side_metrics(
                _tail(group, LONG_UTILITY_RANK_COL, utility.top_fraction, ascending=False),
                group, side="long", config=utility,
            ),
            "short": _economic_side_metrics(
                _tail(group, SHORT_UTILITY_RANK_COL, utility.top_fraction, ascending=False),
                group, side="short", config=utility,
            ),
        }
    return {
        "rows": int(len(work)),
        "long": _economic_side_metrics(long_selected, work, side="long", config=utility),
        "short": _economic_side_metrics(short_selected, work, side="short", config=utility),
        "semesters": semesters,
    }


def _fold_stability(folds: list[dict[str, Any]], overall: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for side in ("long", "short"):
        ic = np.asarray([fold[side]["mean_daily_ic"] for fold in folds], dtype=float)
        lift = np.asarray([fold[side]["return_lift_vs_matched"] for fold in folds], dtype=float)
        net = np.asarray([fold[side]["mean_net_return"] for fold in folds], dtype=float)
        metrics = overall[side]
        concentration = metrics["concentration"]["top1_positive_contribution_share"]
        gates = {
            "mean_daily_ic_gte_0_03": bool(np.nanmean(ic) >= 0.03),
            "positive_ic_folds_gte_7": bool(np.sum(ic > 0) >= 7),
            "return_lift_gte_0_0025": bool(metrics["return_lift_vs_matched"] >= 0.0025),
            "positive_return_lift_folds_gte_7": bool(np.sum(lift > 0) >= 7),
            "positive_net_return_folds_gte_7": bool(np.sum(net > 0) >= 7),
            "catastrophic_rate_not_worse_than_matched": bool(
                metrics["catastrophic_loss_rate"] <= metrics["matched_catastrophic_loss_rate"]
            ),
            "cvar_not_worse_than_matched": bool(metrics["cvar_lift_vs_matched"] >= 0),
            "top1_positive_contribution_lte_0_35": bool(
                concentration is not None and concentration <= 0.35
            ),
        }
        output[side] = {
            "mean_fold_daily_ic": float(np.nanmean(ic)),
            "positive_ic_folds": int(np.sum(ic > 0)),
            "positive_return_lift_folds": int(np.sum(lift > 0)),
            "positive_net_return_folds": int(np.sum(net > 0)),
            "gates": gates,
            "all_gates_passed": bool(all(gates.values())),
        }
    return output


def _best_iterations(model: Any) -> int:
    value = int(model.get_best_iteration()) + 1
    return max(10, value)


def train_path_utility(
    dataset: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
    training: SharedDirectionalConfig,
    utility: EconomicUtilityConfig,
    artifact_dir: Path,
) -> dict[str, Any]:
    targets = [LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL]
    folds = build_folds_adaptive(
        dataset,
        min_train_dates=training.min_train_dates,
        val_dates=training.val_dates,
        test_dates=training.test_dates,
        step_dates=training.step_dates,
        max_splits=training.max_splits,
        forecast_horizon=training.horizon,
    )
    if not folds:
        raise ValueError("Aucun fold Walk-Forward E3-A2 valide.")
    oos_parts: list[pd.DataFrame] = []
    fold_metrics: list[dict[str, Any]] = []
    iterations: dict[str, list[int]] = {"long_return": [], "short_return": [], "long_risk": [], "short_risk": []}
    fold_bounds: list[dict[str, Any]] = []
    for index, fold in enumerate(folds):
        train = fold["train"].dropna(subset=targets).copy()
        valid = fold["val"].dropna(subset=targets).copy()
        test = fold["test"].dropna(subset=targets).copy()
        if train.empty or valid.empty or test.empty:
            continue
        risk_classes_valid = all(
            pd.to_numeric(part[target], errors="coerce").le(
                utility.catastrophic_loss_threshold
            ).nunique() == 2
            for part in (train, valid)
            for target in targets
        )
        if not risk_classes_valid:
            LOGGER.warning("path_utility fold=%d ignoré: classe tail-risk insuffisante", index)
            continue
        long_return, long_bounds = _fit_return_model(
            train, valid, feature_columns, categorical_columns, training, utility,
            LONG_NET_RETURN_COL,
        )
        short_return, short_bounds = _fit_return_model(
            train, valid, feature_columns, categorical_columns, training, utility,
            SHORT_NET_RETURN_COL,
        )
        long_risk = _fit_tail_risk_model(
            train, valid, feature_columns, categorical_columns, training, utility,
            LONG_NET_RETURN_COL,
        )
        short_risk = _fit_tail_risk_model(
            train, valid, feature_columns, categorical_columns, training, utility,
            SHORT_NET_RETURN_COL,
        )
        X_test = _prepare_X(test, feature_columns, categorical_columns)
        scored = test[[
            "date", "symbol", "future_return", "oracle_decile", ORACLE_GATE_SCORE_COL,
            LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL,
            LONG_EXIT_REASON_COL, SHORT_EXIT_REASON_COL, "path_entry_gap_abs",
        ]].copy()
        scored[LONG_EXPECTED_RETURN_COL] = long_return.predict(X_test)
        scored[SHORT_EXPECTED_RETURN_COL] = short_return.predict(X_test)
        scored[LONG_TAIL_RISK_COL] = long_risk.predict_proba(X_test)[:, 1]
        scored[SHORT_TAIL_RISK_COL] = short_risk.predict_proba(X_test)[:, 1]
        scored["fold_index"] = index
        scored = add_economic_scores(scored, utility)
        oos_parts.append(scored)
        metrics = evaluate_economic_oos(scored, utility)
        metrics.update({
            "fold_index": index,
            "test_start": str(pd.Timestamp(test["date"].min()).date()),
            "test_end": str(pd.Timestamp(test["date"].max()).date()),
            "train_rows": int(len(train)),
            "valid_rows": int(len(valid)),
            "winsor_bounds": {"long": list(long_bounds), "short": list(short_bounds)},
        })
        fold_metrics.append(metrics)
        fold_bounds.append(metrics["winsor_bounds"])
        for key, model in (
            ("long_return", long_return), ("short_return", short_return),
            ("long_risk", long_risk), ("short_risk", short_risk),
        ):
            iterations[key].append(_best_iterations(model))
        LOGGER.info(
            "path_utility fold=%d long=%+.4f lift=%+.4f short=%+.4f lift=%+.4f",
            index, metrics["long"]["mean_net_return"], metrics["long"]["return_lift_vs_matched"],
            metrics["short"]["mean_net_return"], metrics["short"]["return_lift_vs_matched"],
        )
    if not oos_parts:
        raise ValueError("Tous les folds E3-A2 ont été rejetés.")
    oos = pd.concat(oos_parts, ignore_index=True)
    overall = evaluate_economic_oos(oos, utility)
    labeled = dataset.dropna(subset=targets).copy()
    final_iterations = {key: max(10, int(np.median(values))) for key, values in iterations.items()}
    final_bounds = {
        "long": target_winsor_bounds(labeled, LONG_NET_RETURN_COL, utility),
        "short": target_winsor_bounds(labeled, SHORT_NET_RETURN_COL, utility),
    }
    final_long_return, _ = _fit_return_model(
        labeled, None, feature_columns, categorical_columns, training, utility,
        LONG_NET_RETURN_COL, iterations=final_iterations["long_return"], bounds=final_bounds["long"],
    )
    final_short_return, _ = _fit_return_model(
        labeled, None, feature_columns, categorical_columns, training, utility,
        SHORT_NET_RETURN_COL, iterations=final_iterations["short_return"], bounds=final_bounds["short"],
    )
    final_long_risk = _fit_tail_risk_model(
        labeled, None, feature_columns, categorical_columns, training, utility,
        LONG_NET_RETURN_COL, iterations=final_iterations["long_risk"],
    )
    final_short_risk = _fit_tail_risk_model(
        labeled, None, feature_columns, categorical_columns, training, utility,
        SHORT_NET_RETURN_COL, iterations=final_iterations["short_risk"],
    )
    artifact_dir.mkdir(parents=True, exist_ok=False)
    model_paths = {
        "long_return_model": artifact_dir / "long_return_model.cbm",
        "short_return_model": artifact_dir / "short_return_model.cbm",
        "long_tail_risk_model": artifact_dir / "long_tail_risk_model.cbm",
        "short_tail_risk_model": artifact_dir / "short_tail_risk_model.cbm",
    }
    for model, path in (
        (final_long_return, model_paths["long_return_model"]),
        (final_short_return, model_paths["short_return_model"]),
        (final_long_risk, model_paths["long_tail_risk_model"]),
        (final_short_risk, model_paths["short_tail_risk_model"]),
    ):
        model.save_model(str(path))
    oos_path = artifact_dir / "oof_predictions.parquet"
    oos.to_parquet(oos_path, index=False)
    metrics = {
        "status": "completed", "research_only": True, "serving_ready": False,
        "model_role": "oracle_conditional_path_economic_utility",
        "n_folds": len(fold_metrics), "final_iterations": final_iterations,
        "final_winsor_bounds": {key: list(value) for key, value in final_bounds.items()},
        "overall": overall, "folds": fold_metrics,
        "fold_stability": _fold_stability(fold_metrics, overall),
        "trained_rows": int(len(labeled)), "trained_symbols": int(labeled["symbol"].nunique()),
        "artifact_paths": {key: str(value) for key, value in model_paths.items()} | {"oof": str(oos_path)},
    }
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return metrics


def run_path_utility_campaign(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    profile_path: Path = DEFAULT_PROFILE,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    symbols_limit: int | None = None,
    training_config: SharedDirectionalConfig | None = None,
    barrier_config: BarrierRaceConfig | None = None,
    utility_config: EconomicUtilityConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    barrier = barrier_config or BarrierRaceConfig()
    utility = utility_config or EconomicUtilityConfig()
    training = training_config or SharedDirectionalConfig(
        horizon=barrier.max_sessions, objective="regressor", target_mode="signed_return",
        context_mode="none", amplitude_weighting=False,
    )
    profile = load_profile(profile_path)
    symbols = get_universe_symbols(engine, oracle_batch_id, 20)
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    gate_path = Path("artifacts/models") / oracle_batch_id / "_oracle_oof_gate.parquet"
    base_config = SharedDirectionalConfig(
        horizon=barrier.max_sessions, pool_pct=training.pool_pct,
        top_fraction=utility.top_fraction, context_mode=training.context_mode,
        objective="classifier", target_mode="decile_direction", amplitude_weighting=False,
    )
    oracle_pool, features, categoricals, population = build_shared_dataset(
        engine, oracle_batch_id, symbols, start_date=start_date, end_date=end_date,
        gate_path=gate_path, profile=profile, config=base_config,
    )
    requested_start = pd.Timestamp(start_date).normalize()
    requested_end = pd.Timestamp(end_date).normalize()
    oracle_pool = oracle_pool[pd.to_datetime(oracle_pool["date"]).between(requested_start, requested_end)].copy()
    if oracle_pool.empty:
        raise ValueError("Pool Oracle E3-A2 vide dans la période demandée.")
    population = {
        **population,
        "rows_oracle_pool": int(len(oracle_pool)), "symbols": int(oracle_pool["symbol"].nunique()),
        "dates": int(oracle_pool["date"].nunique()),
        "requested_period_start": str(requested_start.date()),
        "requested_period_end": str(requested_end.date()),
        "actual_period_start": str(pd.Timestamp(oracle_pool["date"].min()).date()),
        "actual_period_end": str(pd.Timestamp(oracle_pool["date"].max()).date()),
    }
    warmup_start = (requested_start - pd.offsets.BDay(barrier.atr_window + 5)).date()
    future_end = (requested_end + pd.offsets.BDay(barrier.max_sessions + 2)).date()
    bars = load_universe_bars(engine, symbols, start_date=warmup_start, end_date=future_end)
    dataset = attach_path_targets(oracle_pool, build_path_label_panel(bars, barrier))
    usable = dataset[[LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL]].notna().all(axis=1)
    if int(usable.sum()) < 100:
        raise ValueError(f"Cibles E3-A2 insuffisantes: {int(usable.sum())} lignes.")
    run_id = f"shared-path-utility-{datetime.now(UTC):%Y%m%d%H%M%S}-{oracle_batch_id[-6:]}"
    output = artifacts_root / run_id
    metrics = train_path_utility(dataset, features, categoricals, training, utility, output)
    contract = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "E3_A2_oracle_conditional_path_economic_utility_v1",
        "source_oracle_batch_id": oracle_batch_id,
        "status": "completed", "research_only": True, "serving_ready": False,
        "target_contract": {
            "entry": "next_open_J_plus_1", "long_and_short_replayed_independently": True,
            "regression_target": "side_net_return_after_costs",
            "regression_winsorization": "train_only_per_fold",
            "tail_risk_target": f"side_net_return_lte_{utility.catastrophic_loss_threshold}",
            "economic_utility": "predicted_net_return-risk_penalty_return*P(extreme_loss)",
            "daily_normalization": "within_date_percentile_rank",
            "production_parity": False,
            "barrier": asdict(barrier), "utility": asdict(utility),
        },
        "conditioning": {
            "source": "oracle_walk_forward_oof_test", "pool_pct": training.pool_pct,
            "oracle_score_is_feature": False, "gate_path": str(gate_path),
        },
        "population": {
            **population, "target_rows": int(usable.sum()), "target_coverage": float(usable.mean()),
            "long_catastrophic_rate": float(dataset.loc[usable, LONG_NET_RETURN_COL].le(utility.catastrophic_loss_threshold).mean()),
            "short_catastrophic_rate": float(dataset.loc[usable, SHORT_NET_RETURN_COL].le(utility.catastrophic_loss_threshold).mean()),
        },
        "feature_profile": profile, "feature_columns": features,
        "categorical_columns": categoricals, "context_mode": training.context_mode,
        "walk_forward": {
            "min_train_dates": training.min_train_dates, "val_dates": training.val_dates,
            "test_dates": training.test_dates, "step_dates": training.step_dates,
            "max_splits": training.max_splits, "purge_sessions": barrier.max_sessions,
        },
        "primary_policy": {
            "selection": f"daily top {utility.top_fraction:.0%} by economic utility per side",
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


def _format_summary(path: Path, contract: dict[str, Any]) -> str:
    metrics = contract["metrics"]
    lines = [
        f"E3-A2 path utility terminé: {path}",
        f"Population labellisée: {contract['population']['target_rows']} lignes, folds={metrics['n_folds']}",
    ]
    for side in ("long", "short"):
        result = metrics["overall"][side]
        stable = metrics["fold_stability"][side]
        lines.append(
            f"{side.upper()} net top10={result['mean_net_return']:+.2%} "
            f"lift={result['return_lift_vs_matched']:+.2%} "
            f"IC={result['mean_daily_ic']:+.4f} CVaR5={result['cvar_05']:+.2%} "
            f"gates={stable['all_gates_passed']}"
        )
    lines.append("Serving désactivé: résultat de recherche uniquement.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--feature-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--symbols-limit", type=int, default=None)
    parser.add_argument("--stop-atr-mult", type=float, default=2.5)
    parser.add_argument("--tp-atr-mult", type=float, default=3.0)
    parser.add_argument("--tp-max-pct", type=float, default=0.07)
    parser.add_argument("--max-sessions", type=int, default=20)
    parser.add_argument("--max-entry-gap-pct", type=float, default=0.03)
    parser.add_argument("--spread-bps", type=float, default=5.0)
    parser.add_argument("--commission-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--borrow-fee-annual", type=float, default=0.003)
    parser.add_argument("--catastrophic-loss-threshold", type=float, default=-0.20)
    parser.add_argument("--risk-penalty-return", type=float, default=0.20)
    parser.add_argument("--target-winsor-lower", type=float, default=0.01)
    parser.add_argument("--target-winsor-upper", type=float, default=0.99)
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
    barrier = BarrierRaceConfig(
        stop_atr_mult=args.stop_atr_mult, tp_atr_mult=args.tp_atr_mult,
        tp_max_pct=args.tp_max_pct, max_sessions=args.max_sessions,
        max_entry_gap_pct=args.max_entry_gap_pct, spread_bps=args.spread_bps,
        commission_bps=args.commission_bps, slippage_bps=args.slippage_bps,
        borrow_fee_annual=args.borrow_fee_annual,
    )
    utility = EconomicUtilityConfig(
        catastrophic_loss_threshold=args.catastrophic_loss_threshold,
        risk_penalty_return=args.risk_penalty_return,
        target_winsor_lower=args.target_winsor_lower,
        target_winsor_upper=args.target_winsor_upper,
    )
    training = SharedDirectionalConfig(
        horizon=args.max_sessions, min_train_dates=args.wf_min_train_size,
        val_dates=args.wf_val_size, test_dates=args.wf_test_size,
        step_dates=args.wf_step_size, max_splits=args.wf_max_splits,
        iterations=args.iterations, depth=args.depth, learning_rate=args.learning_rate,
        context_mode=args.context_mode, amplitude_weighting=False,
        objective="regressor", target_mode="signed_return",
    )
    path, contract = run_path_utility_campaign(
        get_sqlalchemy_engine(), args.oracle_batch_id,
        start_date=args.start_date, end_date=args.end_date,
        profile_path=args.feature_profile, artifacts_root=args.artifacts_root,
        symbols_limit=args.symbols_limit, training_config=training,
        barrier_config=barrier, utility_config=utility,
    )
    print(_format_summary(path, contract))


if __name__ == "__main__":
    main()
