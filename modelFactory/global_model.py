"""modelFactory/global_model.py — Modèle global tabulaire multi-symboles."""
from __future__ import annotations

import json
import logging
import pickle
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.config import ReproducibilityConfig, TrainingConfig
from modelFactory.cross_sectional import build_cross_sectional_features, merge_cross_sectional_features
from modelFactory.dataset import chrono_split_by_dates
from modelFactory.data_loader import (
    load_benchmark_bars,
    load_symbols_sentiment,
    load_universe_bars,
    load_universe_latest_bar_date,
    resolve_training_start_date,
)
from modelFactory.features import build_feature_contract, build_target, compute_features, compute_future_return, get_feature_columns
from modelFactory.features import fingerprint as compute_feature_fingerprint
from modelFactory.reproducibility import apply_reproducibility, derive_seed
from modelFactory.tabular_baseline import apply_tabular_calibration, compute_tabular_metrics, fit_tabular_calibrator

LOGGER = logging.getLogger(__name__)


def _import_lightgbm() -> Any:
    import lightgbm as lgb  # type: ignore[import-not-found]

    return lgb


def _import_catboost() -> Any:
    from catboost import CatBoostClassifier  # type: ignore[import-not-found]

    return CatBoostClassifier


def _prepare_global_symbol_frame(
    bars_df: pd.DataFrame,
    *,
    cfg: TrainingConfig,
    benchmark_df: pd.DataFrame | None,
    sentiment_df: pd.DataFrame | None,
    cross_sectional_df: pd.DataFrame | None,
) -> pd.DataFrame:
    effective_data_cfg = replace(
        cfg.data,
        enable_cross_sectional_features=(cfg.data.enable_cross_sectional_features and cfg.global_model.use_cross_sectional_features),
    )
    df = compute_features(
        bars_df,
        sentiment_df=sentiment_df,
        include_sentiment=effective_data_cfg.include_sentiment_features,
        benchmark_df=benchmark_df,
        feature_set=effective_data_cfg.feature_set,
    )
    if effective_data_cfg.enable_cross_sectional_features:
        df = merge_cross_sectional_features(df, cross_sectional_df)
    df["future_return"] = compute_future_return(df, horizon=effective_data_cfg.forecast_horizon)
    df["target"] = build_target(
        df,
        horizon=effective_data_cfg.forecast_horizon,
        mode=effective_data_cfg.target_mode,
        positive_threshold=effective_data_cfg.target_up_threshold,
        negative_threshold=effective_data_cfg.target_down_threshold,
    )
    active_features = get_feature_columns(
        effective_data_cfg.include_sentiment_features,
        feature_set=effective_data_cfg.feature_set,
        include_cross_sectional=effective_data_cfg.enable_cross_sectional_features,
    )
    df = df.dropna(subset=active_features).reset_index(drop=True)
    df = df.loc[df["target"].notna() & df["future_return"].notna()].reset_index(drop=True)
    return df


def _split_global_by_dates(
    df: pd.DataFrame,
    *,
    train_ratio: float,
    val_ratio: float,
    forecast_horizon: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    split = chrono_split_by_dates(
        df,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        forecast_horizon=forecast_horizon,
    )
    return split.train, split.val, split.test


def _build_global_estimator(cfg: TrainingConfig, *, resolved_seed: int) -> tuple[str, Any]:
    model_name = cfg.global_model.model_name
    if model_name == "lightgbm":
        lgb = _import_lightgbm()
        return model_name, lgb.LGBMClassifier(
            objective="binary",
            max_depth=cfg.baseline.max_depth,
            n_estimators=cfg.baseline.n_estimators,
            learning_rate=cfg.baseline.learning_rate,
            random_state=resolved_seed,
        )
    CatBoostClassifier = _import_catboost()
    return model_name, CatBoostClassifier(
        depth=cfg.baseline.catboost_depth,
        iterations=cfg.baseline.catboost_iterations,
        learning_rate=cfg.baseline.catboost_learning_rate,
        random_seed=resolved_seed,
        loss_function="Logloss",
        verbose=False,
    )


def _compute_by_symbol_metrics(
    df: pd.DataFrame,
    probabilities: np.ndarray,
    *,
    decision_threshold: float,
) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    probs = np.asarray(probabilities, dtype=np.float64)
    for symbol, part in df.groupby("symbol", sort=False):
        idx = part.index.to_numpy()
        metrics = compute_tabular_metrics(
            part["target"].astype(int).to_numpy(),
            probs[idx],
            part["future_return"].to_numpy(),
            decision_threshold,
        )
        rows[str(symbol)] = {
            "status": "completed",
            "model_name": "global_model",
            "backend_model_name": None,
            "test": metrics,
            "selection_score": float(metrics.get("threshold_business_score") or metrics.get("auc") or 0.0),
        }
    return rows


def train_global_model(
    symbols: list[str],
    cfg: TrainingConfig,
    *,
    artifacts_dir: Path,
    engine: Any,
) -> dict[str, Any]:
    """Entraîne un premier modèle global tabulaire multi-symboles."""
    if not cfg.global_model.enabled:
        return {}
    if len(symbols) < 2:
        return {"status": "skipped", "model_name": "global_model", "reason": "insufficient_symbols"}

    effective_data_cfg = replace(
        cfg.data,
        enable_cross_sectional_features=(cfg.data.enable_cross_sectional_features and cfg.global_model.use_cross_sectional_features),
    )
    history_end_date = load_universe_latest_bar_date(engine, symbols)
    history_start_date = resolve_training_start_date(history_end_date, effective_data_cfg.training_start_date)
    universe_df = load_universe_bars(engine, symbols, end_date=history_end_date, start_date=history_start_date)
    if universe_df.empty:
        return {"status": "skipped", "model_name": "global_model", "reason": "empty_universe"}

    benchmark_df = None
    if effective_data_cfg.feature_set == "expert" or effective_data_cfg.enable_cross_sectional_features:
        benchmark_df = load_benchmark_bars(
            engine,
            effective_data_cfg.benchmark_symbol,
            end_date=history_end_date,
            start_date=history_start_date,
        )

    sentiment_df = None
    if effective_data_cfg.include_sentiment_features:
        sentiment_df = load_symbols_sentiment(
            engine,
            symbols,
            end_date=history_end_date,
            start_date=history_start_date,
        )

    cross_sectional_df = None
    cross_sectional_diagnostics: dict[str, Any] = {}
    if effective_data_cfg.enable_cross_sectional_features:
        cross_sectional_df, cross_sectional_diagnostics = build_cross_sectional_features(
            universe_df,
            benchmark_df=benchmark_df,
            min_universe_size=effective_data_cfg.cross_sectional_min_universe,
        )

    prepared_parts: list[pd.DataFrame] = []
    for symbol in symbols:
        bars_df = universe_df[universe_df["symbol"] == symbol].copy().sort_values("date").reset_index(drop=True)
        if len(bars_df) < effective_data_cfg.min_history_days:
            continue
        symbol_sentiment = None
        if sentiment_df is not None and not sentiment_df.empty:
            symbol_sentiment = sentiment_df[sentiment_df["symbol"] == symbol].copy().reset_index(drop=True)
        prepared = _prepare_global_symbol_frame(
            bars_df,
            cfg=replace(cfg, data=effective_data_cfg),
            benchmark_df=benchmark_df,
            sentiment_df=symbol_sentiment,
            cross_sectional_df=cross_sectional_df,
        )
        if prepared.empty:
            continue
        prepared_parts.append(prepared)

    if not prepared_parts:
        return {"status": "skipped", "model_name": "global_model", "reason": "no_prepared_rows"}

    global_df = pd.concat(prepared_parts, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
    train_df, val_df, test_df = _split_global_by_dates(
        global_df,
        train_ratio=effective_data_cfg.train_ratio,
        val_ratio=effective_data_cfg.val_ratio,
        forecast_horizon=effective_data_cfg.forecast_horizon,
    )
    if train_df.empty or val_df.empty or test_df.empty:
        return {"status": "skipped", "model_name": "global_model", "reason": "insufficient_rows_after_date_split"}

    feature_columns = get_feature_columns(
        effective_data_cfg.include_sentiment_features,
        feature_set=effective_data_cfg.feature_set,
        include_cross_sectional=effective_data_cfg.enable_cross_sectional_features,
    )
    feature_contract = build_feature_contract(
        include_sentiment=effective_data_cfg.include_sentiment_features,
        feature_set=effective_data_cfg.feature_set,
        include_cross_sectional=effective_data_cfg.enable_cross_sectional_features,
        feature_columns=feature_columns,
        scaler_feature_names=feature_columns,
    )
    resolved_seed = derive_seed(
        cfg.reproducibility.seed,
        "global_model",
        cfg.global_model.model_name,
        cfg.global_model.artifact_symbol,
    )
    reproducibility_state = apply_reproducibility(
        ReproducibilityConfig(seed=resolved_seed, deterministic=cfg.reproducibility.deterministic),
        context=f"global_model:{cfg.global_model.model_name}",
    )

    try:
        backend_model_name, model = _build_global_estimator(cfg, resolved_seed=resolved_seed)
    except ImportError:
        return {
            "status": "unavailable",
            "model_name": "global_model",
            "backend_model_name": cfg.global_model.model_name,
            "reason": f"{cfg.global_model.model_name}_not_installed",
        }

    model.fit(train_df[feature_columns], train_df["target"].astype(int))
    val_raw = model.predict_proba(val_df[feature_columns])[:, 1]
    calibrator = fit_tabular_calibrator(val_raw, val_df["target"].astype(int).to_numpy(), cfg)
    val_proba = apply_tabular_calibration(val_raw, calibrator)
    selected_threshold = float(effective_data_cfg.decision_threshold)
    threshold_summary: dict[str, Any]
    if cfg.threshold_optimization.enabled:
        from modelFactory.evaluation import optimize_decision_threshold

        threshold_summary = optimize_decision_threshold(
            val_proba,
            val_df["target"].astype(int).to_numpy(),
            val_df["future_return"].to_numpy(),
            candidate_thresholds=cfg.threshold_optimization.candidate_decision_thresholds,
            default_threshold=effective_data_cfg.decision_threshold,
            min_action_rate=cfg.threshold_optimization.min_action_rate,
            max_action_rate=cfg.threshold_optimization.max_action_rate,
            min_precision_long=cfg.threshold_optimization.min_precision_long,
            n_buckets=5,
        )
        selected_threshold = float(threshold_summary["selected_threshold"])
    else:
        threshold_summary = {
            "enabled": False,
            "selection_status": "disabled",
            "selected_threshold": selected_threshold,
            "candidates": [],
        }

    test_raw = model.predict_proba(test_df[feature_columns])[:, 1]
    test_proba = apply_tabular_calibration(test_raw, calibrator)
    val_metrics = compute_tabular_metrics(
        val_df["target"].astype(int).to_numpy(),
        val_proba,
        val_df["future_return"].to_numpy(),
        selected_threshold,
    )
    test_metrics = compute_tabular_metrics(
        test_df["target"].astype(int).to_numpy(),
        test_proba,
        test_df["future_return"].to_numpy(),
        selected_threshold,
    )

    by_symbol = _compute_by_symbol_metrics(test_df, test_proba, decision_threshold=selected_threshold)
    artifact_dir = (artifacts_dir / cfg.global_model.artifact_symbol).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "global_model.pkl"
    with open(model_path, "wb") as fh:
        pickle.dump(model, fh)

    calibrator_path: str | None = None
    if calibrator is not None and calibrator.fitted:
        cal_path = artifact_dir / "calibrator.pkl"
        with open(cal_path, "wb") as fh:
            pickle.dump(calibrator.state_dict(), fh)
        calibrator_path = str(cal_path)

    config_path = artifact_dir / "config.json"
    config_payload = {
        "data": asdict(replace(effective_data_cfg, decision_threshold=selected_threshold)),
        "global_model": asdict(cfg.global_model),
        "reproducibility": {
            **asdict(cfg.reproducibility),
            "resolved_seed": int(resolved_seed),
            "deterministic_applied": bool(reproducibility_state.get("deterministic_applied", False)),
        },
        "feature_columns": feature_columns,
        "feature_contract": feature_contract,
        "cross_sectional_feature_columns": [col for col in feature_columns if col in (cross_sectional_df.columns if cross_sectional_df is not None and not cross_sectional_df.empty else [])],
        "cross_sectional_diagnostics": cross_sectional_diagnostics,
        "artifact_symbol": cfg.global_model.artifact_symbol,
        "model_name": "global_model",
        "backend_model_name": backend_model_name,
        "model_path": str(model_path),
        "calibrator_path": calibrator_path,
        "selected_decision_threshold": selected_threshold,
        "trained_through_date": history_end_date.isoformat() if history_end_date is not None else None,
        "architecture_selected": "global_model",
        "selection_mode": "global_compare_only",
        "inference_backend": "global_tabular",
        "feature_fingerprint": compute_feature_fingerprint(
            include_sentiment=effective_data_cfg.include_sentiment_features,
            feature_set=effective_data_cfg.feature_set,
            include_cross_sectional=effective_data_cfg.enable_cross_sectional_features,
            feature_columns=feature_columns,
        ),
    }
    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(config_payload, fh, indent=2, default=str)

    metrics_path = artifact_dir / "metrics.json"
    result = {
        "status": "completed",
        "model_name": "global_model",
        "backend_model_name": backend_model_name,
        "artifact_symbol": cfg.global_model.artifact_symbol,
        "artifact_paths": {
            "model_path": str(model_path),
            "config_path": str(config_path),
            "calibrator_path": calibrator_path,
        },
        "feature_columns": feature_columns,
        "feature_contract": feature_contract,
        "feature_fingerprint": feature_contract.get("feature_fingerprint"),
        "seed": int(resolved_seed),
        "cross_sectional_diagnostics": cross_sectional_diagnostics,
        "threshold_optimization": threshold_summary,
        "val": val_metrics,
        "test": test_metrics,
        "by_symbol": by_symbol,
        "selection_score": float(test_metrics.get("threshold_business_score") or test_metrics.get("auc") or 0.0),
    }
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, default=str)
    return result


