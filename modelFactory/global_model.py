"""modelFactory/global_model.py — Modèle global tabulaire multi-symboles.

Approche 2 — Stacking (Sprint 2026-07) :
- ``train_global_model()`` : entraînement single-split (legacy, conservé
  pour backward compat).
- ``train_global_model_wf()`` : walk-forward 11 splits → produit
  ``global_pred_long(symbol, date)`` PIT-safe + métriques WF par symbole.

Architecture des features (Sprint 2026-07-21) :
Le Global Model n'utilise **que** les features cross-symboles (rangs
percentiles, agrégats sectoriels, macro). Les features locales au titre
(OHLCV, expert, sentiment, screener) sont **exclues** — elles sont
redondantes avec le per-symbol et n'apportent aucun signal transverse.
"""
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
from modelFactory.cross_sectional import (
    build_cross_sectional_features,
    CROSS_SECTIONAL_FEATURE_COLUMNS,
    GLOBAL_EXCLUSIVE_FEATURE_COLUMNS,
    GLOBAL_PRED_FEATURE_COLUMNS,  # noqa: F401  # re-export
    merge_cross_sectional_features,
    SECTOR_FEATURE_COLUMNS,
)
from modelFactory.dataset import chrono_split_by_dates, generate_walk_forward_splits
from modelFactory.data_loader import (
    load_benchmark_bars,
    load_symbols_selector_context,
    load_symbols_sentiment,
    load_universe_bars,
    load_universe_latest_bar_date,
    resolve_training_start_date,
)
from modelFactory.features import (
    build_feature_contract,
    build_target,
    compute_features,
    compute_future_return,
    get_feature_columns,
)
from modelFactory.features import fingerprint as compute_feature_fingerprint
from modelFactory.reproducibility import apply_reproducibility, derive_seed
from modelFactory.tabular_baseline import apply_tabular_calibration, compute_tabular_metrics, fit_tabular_calibrator
from modelFactory.calibration import VectorScaler

LOGGER = logging.getLogger(__name__)


def _get_global_feature_columns(cfg: TrainingConfig) -> list[str]:
    """Feature columns spécifiques au Global Model (cross-symbol uniquement).

    Le Global Model ne doit PAS utiliser de features locales au titre
    (OHLCV, expert, sentiment, screener) — elles sont déjà exploitées
    par les modèles per-symbol. Le Global apprend des patterns émergents
    que le per-symbol ne peut pas voir seul :

    - Rangs percentiles : position relative dans l'univers
    - Secteur : momentum/volatilité agrégés par GICS
    - Cross-symbol exclusives : breadth, dispersion, concentration, rang, ratio vol, momentum spread
    - Macro : VIX, VXN, VIX3M, MOVE (contexte de marché global)
    - Régime : bull_market, risk_off (les arbres peuvent splitter conditionnellement)
    """
    cols: list[str] = []
    _use_cross_sectional = (
        cfg.data.enable_cross_sectional_features
        and cfg.global_model.use_cross_sectional_features
    )
    if _use_cross_sectional:
        cols.extend(CROSS_SECTIONAL_FEATURE_COLUMNS)        # 8 rangs
        cols.extend(SECTOR_FEATURE_COLUMNS)                  # 8 secteur
        cols.extend(GLOBAL_EXCLUSIVE_FEATURE_COLUMNS)        # 6 cross-symbol exclusives
    # Macro features — activées individuellement
    if cfg.data.include_macro_vix_features:
        cols.extend(["vix_close", "vix_momentum_5j"])
    if cfg.data.include_macro_vxn_features:
        cols.extend(["vxn_close", "vxn_spread_vix"])
    if cfg.data.include_macro_vix3m_features:
        cols.extend(["vix3m_close", "vix_term_structure_ratio", "vix_backwardation"])
    if cfg.data.include_macro_move_features:
        cols.append("move_close")
    # Régime de marché — features market-wide (même valeur pour tous les symboles à date donnée).
    # Les arbres (LightGBM/CatBoost) apprennent naturellement des splits conditionnels :
    #   « si regime_bull_market == 1 → sous-arbre haussier »
    #   « si regime_risk_off == 1   → sous-arbre défensif »
    # Présentes uniquement quand le benchmark est disponible (feature_set="expert").
    cols.extend(["regime_bull_market", "regime_risk_off"])
    return cols


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
    selector_df: pd.DataFrame | None,
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
        selector_df=selector_df,
        include_screener_scores=effective_data_cfg.include_screener_scores,
        include_short_score=effective_data_cfg.include_short_score_features,
        include_macro_vix=effective_data_cfg.include_macro_vix_features,
        include_macro_vxn=effective_data_cfg.include_macro_vxn_features,
        include_macro_vix3m=effective_data_cfg.include_macro_vix3m_features,
        include_macro_move=effective_data_cfg.include_macro_move_features,
    )
    if effective_data_cfg.enable_cross_sectional_features:
        df = merge_cross_sectional_features(df, cross_sectional_df)
    # Sécurité : garantir la présence des colonnes régime même sans benchmark
    for _regime_col in ("regime_bull_market", "regime_risk_off"):
        if _regime_col not in df.columns:
            df[_regime_col] = 0.0
    df["future_return"] = compute_future_return(df, horizon=effective_data_cfg.forecast_horizon)
    df["target"] = build_target(
        df,
        horizon=effective_data_cfg.forecast_horizon,
        mode=effective_data_cfg.target_mode,
        positive_threshold=effective_data_cfg.target_up_threshold,
        negative_threshold=effective_data_cfg.target_down_threshold,
    )
    active_features = _get_global_feature_columns(cfg)
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
        is_ternary = cfg.data.target_mode == "ternary"
        return model_name, lgb.LGBMClassifier(
            objective="multiclass" if is_ternary else "binary",
            num_class=3 if is_ternary else 1,
            max_depth=cfg.baseline.max_depth,
            n_estimators=cfg.baseline.n_estimators,
            learning_rate=cfg.baseline.learning_rate,
            random_state=resolved_seed,
            verbosity=-1,
            class_weight="balanced",
        )
    CatBoostClassifier = _import_catboost()
    is_ternary = cfg.data.target_mode == "ternary"
    train_dir = Path(cfg.catboost_artifacts_dir) / cfg.global_model.artifact_symbol / f"seed_{resolved_seed}"
    train_dir.mkdir(parents=True, exist_ok=True)
    return model_name, CatBoostClassifier(
        depth=cfg.baseline.catboost_depth,
        iterations=cfg.baseline.catboost_iterations,
        learning_rate=cfg.baseline.catboost_learning_rate,
        random_seed=resolved_seed,
        loss_function="MultiClass" if is_ternary else "Logloss",
        verbose=False,
        train_dir=str(train_dir),
        allow_writing_files=True,
        auto_class_weights="Balanced",
    )


def _compute_by_symbol_metrics(
    df: pd.DataFrame,
    probabilities: np.ndarray,
    *,
    decision_threshold: float,
    partition_name: str = "test",
) -> dict[str, dict[str, Any]]:
    """Calcule les métriques par symbole sur une partition (train/val/test).

    Parameters
    ----------
    partition_name : str
        Nom de la clé sous laquelle stocker les métriques dans le résultat
        (ex: ``"val"``, ``"test"``, ``"walk_forward"``).
    """
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
            partition_name: metrics,
            "selection_score": float(metrics.get("threshold_business_score") or metrics.get("auc") or 0.0),
        }
    return rows


def _aggregate_wf_per_symbol_metrics(
    fold_metrics_by_symbol: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Agrège les métriques walk-forward par symbole (mean/std sur les splits).

    Pour chaque symbole, collecte les métriques ``val`` de chaque split WF
    et produit une entrée ``walk_forward`` avec ``{mean: {...}, std: {...}}``.
    """
    metric_keys = [
        "auc", "f1_macro", "f1_short", "f1_flat", "f1_long",
        "threshold_business_score", "action_rate", "precision",
        "recall", "directional_accuracy", "brier_score",
        # Distribution true/pred (ternaire)
        "true_short_pct", "true_flat_pct", "true_long_pct",
        "pred_short_pct", "pred_flat_pct", "pred_long_pct",
    ]
    aggregated: dict[str, dict[str, Any]] = {}
    for symbol, fold_list in fold_metrics_by_symbol.items():
        if not fold_list:
            continue
        mean_metrics: dict[str, float | None] = {}
        std_metrics: dict[str, float | None] = {}
        for key in metric_keys:
            vals = []
            for fold in fold_list:
                val_metrics = fold.get("val") if isinstance(fold.get("val"), dict) else {}
                v = val_metrics.get(key)
                if v is not None:
                    try:
                        vals.append(float(v))
                    except (TypeError, ValueError):
                        pass
            mean_metrics[key] = float(np.mean(vals)) if vals else None
            std_metrics[key] = float(np.std(vals)) if vals else None
        selection_score = float(
            mean_metrics.get("f1_macro")
            or mean_metrics.get("threshold_business_score")
            or mean_metrics.get("auc")
            or 0.0
        )
        aggregated[symbol] = {
            "status": "completed",
            "model_name": "global_model",
            "walk_forward": {
                "n_splits": len(fold_list),
                "mean": mean_metrics,
                "std": std_metrics,
            },
            "selection_score": selection_score,
        }
    return aggregated


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
    history_end_date = load_universe_latest_bar_date(
        engine,
        symbols,
        end_date=effective_data_cfg.training_end_date,
    )
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

    selector_context_df = None
    if effective_data_cfg.include_screener_scores or effective_data_cfg.include_short_score_features:
        selector_context_df = load_symbols_selector_context(
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
        symbol_selector_df = None
        if selector_context_df is not None and not selector_context_df.empty:
            symbol_selector_df = selector_context_df[
                selector_context_df["symbol"] == symbol
            ].copy().reset_index(drop=True)
        prepared = _prepare_global_symbol_frame(
            bars_df,
            cfg=replace(cfg, data=effective_data_cfg),
            benchmark_df=benchmark_df,
            sentiment_df=symbol_sentiment,
            cross_sectional_df=cross_sectional_df,
            selector_df=symbol_selector_df,
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

    feature_columns = _get_global_feature_columns(cfg)
    feature_contract = build_feature_contract(
        include_sentiment=False,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
        include_screener_scores=False,
        include_short_score=False,
        include_macro_vix=cfg.data.include_macro_vix_features,
        include_macro_vxn=cfg.data.include_macro_vxn_features,
        include_macro_vix3m=cfg.data.include_macro_vix3m_features,
        include_macro_move=cfg.data.include_macro_move_features,
        include_global_stacking=False,
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

    train_targets = train_df["target"].astype(int)
    is_ternary = effective_data_cfg.target_mode == "ternary"
    # LightGBM/CatBoost exigent des labels consecutifs a partir de 0.
    if is_ternary:
        train_targets = train_targets + 1  # shift: -1->0, 0->1, +1->2
    unique_classes = train_targets.unique()
    if len(unique_classes) < 2:
        return {"status": "skipped", "model_name": "global_model", "reason": f"single_class_target_{unique_classes[0]}"}
    model.fit(train_df[feature_columns], train_targets)
    is_ternary = effective_data_cfg.target_mode == "ternary"
    raw_val_all = model.predict_proba(val_df[feature_columns])
    num_val_cols = raw_val_all.shape[1]
    if is_ternary and num_val_cols >= 3:
        long_col = 2  # full ternary: [short, flat, long]
    else:
        long_col = num_val_cols - 1  # fallback: last column
    val_raw = raw_val_all[:, long_col]
    cal_labels = (val_df["target"].astype(int) == 1).astype(int).to_numpy() if is_ternary else val_df["target"].astype(int).to_numpy()

    # ── Sprint Maître 2 : calibration ternaire VectorScaler ──────────
    if is_ternary and num_val_cols >= 3:
        val_labels_ternary = (val_df["target"].astype(int) + 1).to_numpy()  # shift -1,0,1 -> 0,1,2
        calibrator = fit_tabular_calibrator(
            raw_val_all[:, :3], val_labels_ternary, cfg, target_mode="ternary",
        )
        calibrated_all = apply_tabular_calibration(
            raw_val_all[:, :3], calibrator, target_mode="ternary",
        )
        val_proba = calibrated_all[:, 2]  # p_long calibrée
    else:
        calibrator = fit_tabular_calibrator(val_raw, cal_labels, cfg)
        val_proba = apply_tabular_calibration(val_raw, calibrator)
    selected_threshold = float(effective_data_cfg.decision_threshold)
    threshold_summary: dict[str, Any]
    if cfg.threshold_optimization.enabled:
        from modelFactory.evaluation import optimize_decision_threshold

        threshold_summary = optimize_decision_threshold(
            val_proba,
            cal_labels,  # binarisee : 1=long, 0=sinon
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

    raw_test_all = model.predict_proba(test_df[feature_columns])
    num_test_cols = raw_test_all.shape[1]
    test_long_col = 2 if (is_ternary and num_test_cols >= 3) else (num_test_cols - 1)
    test_raw = raw_test_all[:, test_long_col]

    # ── Sprint Maître 2 : calibration test ternaire ──────────────────
    if is_ternary and num_test_cols >= 3:
        calibrated_test_all = apply_tabular_calibration(
            raw_test_all[:, :3], calibrator, target_mode="ternary",
        )
        test_proba = calibrated_test_all[:, 2]
    else:
        test_proba = apply_tabular_calibration(test_raw, calibrator)
    test_labels = (test_df["target"].astype(int) == 1).astype(int).to_numpy() if is_ternary else test_df["target"].astype(int).to_numpy()
    val_metrics = compute_tabular_metrics(
        cal_labels,
        val_proba,
        val_df["future_return"].to_numpy(),
        selected_threshold,
        raw_proba_all=raw_val_all if is_ternary else None,
        target_raw=val_df["target"].astype(int).to_numpy() if is_ternary else None,
        is_ternary=is_ternary,
    )
    test_metrics = compute_tabular_metrics(
        test_labels,
        test_proba,
        test_df["future_return"].to_numpy(),
        selected_threshold,
        raw_proba_all=raw_test_all if is_ternary else None,
        target_raw=test_df["target"].astype(int).to_numpy() if is_ternary else None,
        is_ternary=is_ternary,
    )

    by_symbol = _compute_by_symbol_metrics(test_df, test_proba, decision_threshold=selected_threshold, partition_name="test")
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
        "batch_id": cfg.batch_id,
        "artifacts_dir": str(artifacts_dir),
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
            include_screener_scores=effective_data_cfg.include_screener_scores,
            include_short_score=effective_data_cfg.include_short_score_features,
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


def train_global_model_wf(
    symbols: list[str],
    cfg: TrainingConfig,
    *,
    artifacts_dir: Path,
    engine: Any,
) -> dict[str, Any]:
    """Entraîne le Global Model en walk-forward (Phase 1 — Approche 2).

    Produit deux artefacts :
    1. ``global_pred_df`` : DataFrame ``[symbol, date, global_pred_short, global_pred_flat, global_pred_long]``
       PIT-safe, à merger dans le cache cross-sectional pour le stacking (3 probas ternaires).
    2. ``by_symbol`` : métriques WF par symbole avec ``walk_forward.mean.f1_macro``,
       utilisable par ``select_champion()`` (Phase 3).

    Returns
    -------
    dict avec les clés :
    - ``global_pred_df`` : pd.DataFrame | None
    - ``by_symbol`` : dict[str, dict] — métriques WF par symbole
    - ``status``, ``model_name``, ``feature_columns``, etc.
    """
    if not cfg.global_model.enabled:
        return {"status": "skipped", "model_name": "global_model", "reason": "disabled"}
    if len(symbols) < 2:
        return {"status": "skipped", "model_name": "global_model", "reason": "insufficient_symbols"}

    effective_data_cfg = replace(
        cfg.data,
        enable_cross_sectional_features=(
            cfg.data.enable_cross_sectional_features and cfg.global_model.use_cross_sectional_features
        ),
    )
    history_end_date = load_universe_latest_bar_date(
        engine, symbols, end_date=effective_data_cfg.training_end_date,
    )
    history_start_date = resolve_training_start_date(history_end_date, effective_data_cfg.training_start_date)
    universe_df = load_universe_bars(engine, symbols, end_date=history_end_date, start_date=history_start_date)
    if universe_df.empty:
        return {"status": "skipped", "model_name": "global_model", "reason": "empty_universe"}

    # ── Chargement des données auxiliaires (benchmark, sentiment, selector, cross-sectional) ──
    benchmark_df = None
    if effective_data_cfg.feature_set == "expert" or effective_data_cfg.enable_cross_sectional_features:
        benchmark_df = load_benchmark_bars(
            engine, effective_data_cfg.benchmark_symbol,
            end_date=history_end_date, start_date=history_start_date,
        )
    sentiment_df = None
    if effective_data_cfg.include_sentiment_features:
        sentiment_df = load_symbols_sentiment(engine, symbols, end_date=history_end_date, start_date=history_start_date)
    selector_context_df = None
    if effective_data_cfg.include_screener_scores or effective_data_cfg.include_short_score_features:
        selector_context_df = load_symbols_selector_context(engine, symbols, end_date=history_end_date, start_date=history_start_date)

    cross_sectional_df = None
    cross_sectional_diagnostics: dict[str, Any] = {}
    if effective_data_cfg.enable_cross_sectional_features:
        cross_sectional_df, cross_sectional_diagnostics = build_cross_sectional_features(
            universe_df, benchmark_df=benchmark_df,
            min_universe_size=effective_data_cfg.cross_sectional_min_universe,
        )

    # ── Préparation du DataFrame poolé (même logique que train_global_model) ──
    prepared_parts: list[pd.DataFrame] = []
    for symbol in symbols:
        bars_df = universe_df[universe_df["symbol"] == symbol].copy().sort_values("date").reset_index(drop=True)
        if len(bars_df) < effective_data_cfg.min_history_days:
            continue
        symbol_sentiment = None
        if sentiment_df is not None and not sentiment_df.empty:
            symbol_sentiment = sentiment_df[sentiment_df["symbol"] == symbol].copy().reset_index(drop=True)
        symbol_selector_df = None
        if selector_context_df is not None and not selector_context_df.empty:
            symbol_selector_df = selector_context_df[selector_context_df["symbol"] == symbol].copy().reset_index(drop=True)
        prepared = _prepare_global_symbol_frame(
            bars_df, cfg=replace(cfg, data=effective_data_cfg),
            benchmark_df=benchmark_df, sentiment_df=symbol_sentiment,
            cross_sectional_df=cross_sectional_df, selector_df=symbol_selector_df,
        )
        if prepared.empty:
            continue
        prepared_parts.append(prepared)

    if not prepared_parts:
        return {"status": "skipped", "model_name": "global_model", "reason": "no_prepared_rows"}

    global_df = pd.concat(prepared_parts, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)

    # ── Feature columns (cross-symbol uniquement, sans global_pred_long) ──
    feature_columns = _get_global_feature_columns(cfg)

    # ── Walk-Forward splits ──
    wf_splits = generate_walk_forward_splits(
        global_df,
        min_train_size=cfg.walk_forward.min_train_size,
        val_size=cfg.walk_forward.val_size,
        test_size=cfg.walk_forward.test_size,
        step_size=cfg.walk_forward.step_size,
        max_splits=cfg.walk_forward.max_splits,
        forecast_horizon=effective_data_cfg.forecast_horizon,
        date_column="date",
    )
    if not wf_splits:
        return {"status": "skipped", "model_name": "global_model", "reason": "no_valid_wf_split"}

    LOGGER.info(
        "train_global_model_wf start symbols=%d splits=%d feature_cols=%d",
        len(symbols), len(wf_splits), len(feature_columns),
    )

    resolved_seed = derive_seed(cfg.reproducibility.seed, "global_model_wf", cfg.global_model.model_name)
    apply_reproducibility(
        ReproducibilityConfig(seed=resolved_seed, deterministic=cfg.reproducibility.deterministic),
        context=f"global_model_wf:{cfg.global_model.model_name}",
    )

    is_ternary = effective_data_cfg.target_mode == "ternary"

    # ── Accumulateurs ──
    global_pred_parts: list[pd.DataFrame] = []
    fold_metrics_by_symbol: dict[str, list[dict[str, Any]]] = {}

    for split in wf_splits:
        split_seed = derive_seed(resolved_seed, split.split_index)
        apply_reproducibility(
            ReproducibilityConfig(seed=split_seed, deterministic=cfg.reproducibility.deterministic),
            context=f"global_model_wf:split_{split.split_index}",
        )

        try:
            backend_model_name, model = _build_global_estimator(cfg, resolved_seed=split_seed)
        except ImportError:
            return {
                "status": "unavailable", "model_name": "global_model",
                "backend_model_name": cfg.global_model.model_name,
                "reason": f"{cfg.global_model.model_name}_not_installed",
            }

        train_df = split.train
        val_df_split = split.val
        if train_df.empty or val_df_split.empty:
            LOGGER.warning("train_global_model_wf split=%d empty train or val", split.split_index)
            continue

        train_targets = train_df["target"].astype(int)
        if is_ternary:
            train_targets = train_targets + 1  # shift: -1→0, 0→1, +1→2
        unique_train = train_targets.unique()
        if len(unique_train) < 2:
            LOGGER.warning("train_global_model_wf split=%d single_class", split.split_index)
            continue

        # ── Sample weighting par récence (demi-vie = 1 an) ──
        # Les relations cross-sectionnelles se dégradent plus vite que
        # les patterns locaux → les observations récentes doivent peser plus.
        _sample_weights: "np.ndarray | None" = None
        if "date" in train_df.columns:
            _train_dates = pd.to_datetime(train_df["date"])
            _max_date = _train_dates.max()
            _days_diff = (_max_date - _train_dates).dt.days
            _sample_weights = np.exp(-_days_diff.values.astype(np.float64) / 365.0)
            LOGGER.info(
                "train_global_model_wf split=%d sample_weight rows=%d "
                "weight_min=%.3f weight_max=%.3f weight_mean=%.3f",
                split.split_index + 1,
                len(_sample_weights),
                float(_sample_weights.min()),
                float(_sample_weights.max()),
                float(_sample_weights.mean()),
            )

        # ── Fit ──
        model.fit(train_df[feature_columns], train_targets, sample_weight=_sample_weights)

        # ── Predict on val (per-symbol, PIT-safe) ──
        raw_val_all = model.predict_proba(val_df_split[feature_columns])
        num_val_cols = raw_val_all.shape[1]

        # ── Sprint Maître 2 : calibration ternaire VectorScaler par split ──
        # Fit sur train, appliqué sur val pour des métriques calibrées.
        # Le global_pred_df reste en probas brutes (non calibrées) car elles
        # servent de features de stacking — l'information brute est préférable.
        if is_ternary and num_val_cols >= 3:
            raw_train_all = model.predict_proba(train_df[feature_columns])
            eps = 1e-8
            _train_clipped = np.clip(raw_train_all[:, :3], eps, 1 - eps)
            _train_clipped = _train_clipped / _train_clipped.sum(axis=1, keepdims=True)
            _train_logits = np.log(_train_clipped)
            _split_calibrator = VectorScaler(max_iter=cfg.calibration.max_iter).fit(
                _train_logits, train_targets,
            )
            calibrated_val_all = apply_tabular_calibration(
                raw_val_all[:, :3], _split_calibrator, target_mode="ternary",
            )
            val_proba_long_for_metrics = calibrated_val_all[:, 2]
            val_proba_all_for_metrics = calibrated_val_all
        else:
            val_proba_long_for_metrics = raw_val_all[:, -1]
            val_proba_all_for_metrics = raw_val_all

        # ── Stocker global_pred pour le stacking (3 probas ternaires BRUTES) ──
        pred_part = val_df_split[["symbol", "date"]].copy()
        if is_ternary and num_val_cols >= 3:
            # short=col0, flat=col1, long=col2 — BRUT, non calibré pour stacking
            pred_part["global_pred_short"] = raw_val_all[:, 0].astype(np.float64)
            pred_part["global_pred_flat"] = raw_val_all[:, 1].astype(np.float64)
            pred_part["global_pred_long"] = raw_val_all[:, 2].astype(np.float64)
            val_proba_long = raw_val_all[:, 2]
        else:
            # fallback binaire : short=1-p, flat=0, long=p
            pred_part["global_pred_short"] = (1.0 - raw_val_all[:, -1]).astype(np.float64)
            pred_part["global_pred_flat"] = np.float64(0.0)
            pred_part["global_pred_long"] = raw_val_all[:, -1].astype(np.float64)
            val_proba_long = raw_val_all[:, -1]
        global_pred_parts.append(pred_part)

        # ── Métriques par symbole sur ce split (basées sur probas CALIBRÉES) ──
        split_by_symbol = _compute_by_symbol_metrics(
            val_df_split, val_proba_long_for_metrics,
            decision_threshold=float(effective_data_cfg.decision_threshold),
            partition_name="val",
        )
        for sym, metrics_entry in split_by_symbol.items():
            fold_metrics_by_symbol.setdefault(sym, []).append(metrics_entry)

        LOGGER.info(
            "train_global_model_wf split=%d/%d train_rows=%d val_rows=%d symbols_in_val=%d",
            split.split_index + 1, len(wf_splits),
            len(train_df), len(val_df_split), len(split_by_symbol),
        )

    # ── Agrégation WF par symbole ──
    by_symbol = _aggregate_wf_per_symbol_metrics(fold_metrics_by_symbol)

    # ── Assemblage du global_pred_df ──
    global_pred_df: pd.DataFrame | None = None
    if global_pred_parts:
        global_pred_df = pd.concat(global_pred_parts, ignore_index=True)
        global_pred_df = global_pred_df.sort_values(["symbol", "date"]).reset_index(drop=True)
        LOGGER.info(
            "train_global_model_wf done pred_rows=%d symbols=%d dates=%d",
            len(global_pred_df),
            global_pred_df["symbol"].nunique() if not global_pred_df.empty else 0,
            global_pred_df["date"].nunique() if not global_pred_df.empty else 0,
        )
    else:
        LOGGER.warning("train_global_model_wf done but no predictions generated")

    # ── Build feature contract ──
    feature_contract = build_feature_contract(
        include_sentiment=False,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
        include_screener_scores=False,
        include_short_score=False,
        include_macro_vix=cfg.data.include_macro_vix_features,
        include_macro_vxn=cfg.data.include_macro_vxn_features,
        include_macro_vix3m=cfg.data.include_macro_vix3m_features,
        include_macro_move=cfg.data.include_macro_move_features,
        include_global_stacking=False,
        feature_columns=feature_columns,
        scaler_feature_names=feature_columns,
    )

    wf_symbols_with_metrics = len(by_symbol)
    LOGGER.info(
        "train_global_model_wf completed splits=%d symbols_with_wf=%d",
        len(wf_splits), wf_symbols_with_metrics,
    )

    return {
        "status": "completed",
        "model_name": "global_model",
        "backend_model_name": cfg.global_model.model_name,
        "feature_columns": feature_columns,
        "feature_contract": feature_contract,
        "feature_fingerprint": feature_contract.get("feature_fingerprint"),
        "cross_sectional_diagnostics": cross_sectional_diagnostics,
        "global_pred_df": global_pred_df,
        "by_symbol": by_symbol,
        "selection_score": float(
            np.mean([
                entry.get("selection_score", 0.0)
                for entry in by_symbol.values()
            ]) if by_symbol else 0.0
        ),
        "walk_forward": {
            "n_splits": len(wf_splits),
            "symbols_with_metrics": wf_symbols_with_metrics,
        },
    }