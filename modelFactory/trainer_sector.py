"""modelFactory/trainer_sector.py — Per-Sector training (1 modèle par secteur GICS).

Sprint 2026-08-03 : alternative au per-symbol. Concatène tous les symboles
d'un même secteur, ajoute ``symbol`` comme feature, entraîne un seul jeu
de modèles (LSTM + LightGBM + CatBoost) par secteur.
"""
from __future__ import annotations

import json
import logging
import pickle
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.config import TrainingConfig
from modelFactory.dataset import (
    SymbolDataModule,
    chrono_split_by_dates,
    generate_walk_forward_splits,
    prepare_symbol_frame,
)
from modelFactory.features import build_target, compute_future_return, get_feature_columns
from modelFactory.tabular_baseline import (
    run_tabular_baseline,
    run_tabular_walk_forward,
)
from modelFactory.lightgbm_baseline import run_lightgbm_baseline
from modelFactory.catboost_baseline import run_catboost_baseline
from modelFactory.trainer import (
    _build_ternary_policy,
    _run_walk_forward_validation,
    train_symbol as _train_symbol_legacy,
)
from modelFactory.cross_sectional import load_sector_groups

LOGGER = logging.getLogger(__name__)


# ── Per-Sector Training ──────────────────────────────────────────────────────


def _prepare_sector_data(
    symbols: list[str],
    cfg: TrainingConfig,
    engine: Any,
    *,
    sentiment_df: pd.DataFrame | None = None,
    benchmark_df: pd.DataFrame | None = None,
    universe_df: pd.DataFrame | None = None,
    selector_df: pd.DataFrame | None = None,
    fundamental_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    """Charge et prépare les données pour un secteur entier.

    Concatène les barres de tous les symboles du secteur, avec une
    colonne ``symbol`` pour identification.

    Returns
    -------
    (train_df, val_df, test_df, feature_cols)
        Les trois splits chronologiques sur les données concaténées.
    """
    from modelFactory.data_loader import load_symbol_bars

    frames: list[pd.DataFrame] = []
    for sym in symbols:
        try:
            bars = load_symbol_bars(
                engine, sym,
                start_date=cfg.data.training_start_date,
                end_date=cfg.data.training_end_date,
            )
            if bars is None or bars.empty:
                LOGGER.warning("train_sector: no bars for %s, skipping", sym)
                continue
            bars["symbol"] = sym
            frames.append(bars)
        except Exception as exc:
            LOGGER.warning("train_sector: failed to load %s: %s", sym, exc)

    if not frames:
        raise ValueError(f"No bar data loaded for any symbol in sector")

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["date", "symbol"]).reset_index(drop=True)
    LOGGER.info(
        "train_sector: loaded %d symbols, %d total rows",
        len(frames), len(combined),
    )

    # Prepare features (same pipeline as per-symbol)
    prepared = prepare_symbol_frame(
        combined,
        cfg.data,
        sentiment_df=sentiment_df,
        benchmark_df=benchmark_df,
        universe_df=universe_df,
        selector_df=selector_df,
        fundamental_df=fundamental_df,
    )

    # ── Sector-neutral target ──
    # Predict outperformance within the sector, not absolute direction.
    # The target becomes: "will this stock beat the sector median?"
    # Must neutralize ALL horizon targets before splits are created.
    if "date" in prepared.columns:
        if cfg.data.forecast_horizons:
            for h in cfg.data.forecast_horizons:
                _col = f"target_h{h}"
                if _col in prepared.columns:
                    _daily_med = prepared.groupby("date")[_col].transform("median")
                    prepared[_col] = prepared[_col] - _daily_med
            # Sync primary "target" column with the max horizon (already neutralized)
            prepared["target"] = prepared[f"target_h{cfg.data.forecast_horizon}"]
            LOGGER.info(
                "train_sector: sector-neutralized %d horizon targets",
                len(cfg.data.forecast_horizons),
            )
        elif "target" in prepared.columns:
            daily_median = prepared.groupby("date")["target"].transform("median")
            prepared["target"] = prepared["target"] - daily_median
            LOGGER.info(
                "train_sector: target sector-neutralized "
                "(target = target - daily_median within sector)"
            )

    # Chronological split by DATES (PIT-safe: same date → same split)
    split = chrono_split_by_dates(
        prepared,
        train_ratio=cfg.data.train_ratio,
        val_ratio=cfg.data.val_ratio,
        forecast_horizon=cfg.data.forecast_horizon,
    )

    feature_cols = get_feature_columns(
        cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
        include_screener_scores=cfg.data.include_screener_scores,
        include_short_score=cfg.data.include_short_score_features,
        include_macro_vix=cfg.data.include_macro_vix_features,
        include_macro_vxn=cfg.data.include_macro_vxn_features,
        include_macro_vix3m=cfg.data.include_macro_vix3m_features,
        include_macro_move=cfg.data.include_macro_move_features,
        include_global_stacking=cfg.global_model.stacking_enabled,
        include_factors=cfg.data.include_factors_features,
        include_macro_regime=cfg.data.include_macro_regime_features,
    )

    # Add "symbol" as a categorical feature for tabular models
    if "symbol" in prepared.columns and "symbol" not in feature_cols:
        feature_cols = list(feature_cols) + ["symbol"]

    return split.train, split.val, split.test, feature_cols


def _persist_sector_metrics(
    engine: Any,
    sector_name: str,
    run_id: str,
    *,
    lgbm_result: dict[str, Any],
    cb_result: dict[str, Any],
    batch_id: str | None = None,
) -> None:
    """Persiste les métriques d'un secteur dans les tables model_training_*."""
    from modelFactory.db_registry import (
        ensure_registry_entry,
        insert_metrics,
        insert_training_run,
        replace_model_governance,
        update_training_run,
    )

    registry_id = ensure_registry_entry(engine, sector_name)
    insert_training_run(
        engine, run_id, registry_id, sector_name, status="running",
        **( {"batch_id": batch_id} if batch_id is not None else {}),
    )

    for model_name, model_result in [("lightgbm", lgbm_result), ("catboost", cb_result)]:
        if model_result.get("status") != "completed":
            continue
        # ── Multi-horizon : persister chaque horizon séparément ──
        _horizons_dict = model_result.get("horizons", {})
        if _horizons_dict:
            for _h_tag, _h_result in _horizons_dict.items():
                if isinstance(_h_result, dict) and _h_result.get("status") == "completed":
                    _h = int(_h_tag.lstrip("h")) if _h_tag.startswith("h") else None
                    for split_name in ("val", "test", "wf"):
                        metrics = _h_result.get(split_name)
                        if isinstance(metrics, dict) and metrics:
                            insert_metrics(engine, run_id, sector_name, split_name, metrics, model_name=model_name, horizon=_h)
        else:
            # Legacy single-horizon
            for split_name in ("val", "test", "wf"):
                metrics = model_result.get(split_name)
                if isinstance(metrics, dict) and metrics:
                    insert_metrics(engine, run_id, sector_name, split_name, metrics, model_name=model_name)

    wf_full_lgbm = lgbm_result.get("walk_forward") if isinstance(lgbm_result, dict) else None
    wf_full_cb = cb_result.get("walk_forward") if isinstance(cb_result, dict) else None
    if isinstance(wf_full_lgbm, dict):
        from modelFactory.db_registry import upsert_metrics_full
        upsert_metrics_full(engine, run_id=run_id, symbol=sector_name, metrics={"walk_forward": wf_full_lgbm})
    if isinstance(wf_full_cb, dict):
        from modelFactory.db_registry import upsert_metrics_full
        upsert_metrics_full(engine, run_id=run_id, symbol=sector_name, metrics={"walk_forward": wf_full_cb})

    lgbm_score = float(lgbm_result.get("selection_score") or 0)
    cb_score = float(cb_result.get("selection_score") or 0)
    champion = "lightgbm" if lgbm_score >= cb_score else "catboost"
    challengers = {
        "lightgbm": lgbm_result,
        "catboost": cb_result,
        "lstm_attention": {"status": "skipped"},
    }
    artifact_routes = {
        "lightgbm": {"inference_backend": "lightgbm_tabular", "config_path": "", "model_path": ""},
        "catboost": {"inference_backend": "catboost_tabular", "config_path": "", "model_path": ""},
    }
    replace_model_governance(
        engine, run_id=run_id, symbol=sector_name,
        challengers=challengers,
        artifact_routes_models=artifact_routes,
        selected_model=champion,
        selection_mode="auto_selected_champion",
        selection_metric="selection_score",
        ranking=[],
    )

    update_training_run(engine, run_id, status="completed", finished_at=datetime.now(timezone.utc))
    LOGGER.info("_persist_sector_metrics: sector=%s champion=%s lgbm=%.4f cb=%.4f",
                 sector_name, champion, lgbm_score, cb_score)


def _train_sector_models(
    sector_name: str,
    symbols: list[str],
    engine: Any,
    cfg: TrainingConfig,
    *,
    sentiment_df: pd.DataFrame | None = None,
    benchmark_df: pd.DataFrame | None = None,
    universe_df: pd.DataFrame | None = None,
    selector_df: pd.DataFrame | None = None,
    fundamental_df: pd.DataFrame | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    """Entraîne les 3 challengers (LSTM, LightGBM, CatBoost) pour un secteur.

    Returns
    -------
    dict with keys: sector, symbols_count, lstm, lightgbm, catboost, champion
    """
    LOGGER.info("train_sector start sector=%s symbols=%d", sector_name, len(symbols))

    train_df, val_df, test_df, feature_cols = _prepare_sector_data(
        symbols, cfg, engine,
        sentiment_df=sentiment_df,
        benchmark_df=benchmark_df,
        universe_df=universe_df,
        selector_df=selector_df,
        fundamental_df=fundamental_df,
    )

    if train_df.empty:
        return {"sector": sector_name, "status": "skipped", "reason": "empty_train"}

    # Build prepared_df for tabular baselines
    prepared_df = pd.concat([train_df, val_df, test_df], ignore_index=True)

    # Ensure symbol is a categorical feature for tree models
    tab_feature_cols = list(feature_cols)

    # ── LightGBM ──
    is_reg = cfg.data.target_mode == "regression"
    if is_reg:
        _lgbm_builder = lambda seed: __import__("lightgbm").LGBMRegressor(
            objective="regression",
            max_depth=cfg.baseline.max_depth,
            num_leaves=cfg.baseline.lgbm_num_leaves,
            n_estimators=cfg.baseline.n_estimators,
            learning_rate=cfg.baseline.learning_rate,
            random_state=seed, verbosity=-1,
            reg_alpha=cfg.baseline.lgbm_reg_alpha,
            reg_lambda=cfg.baseline.lgbm_reg_lambda,
            min_child_samples=cfg.baseline.lgbm_min_child_samples,
            subsample=cfg.baseline.lgbm_subsample,
            colsample_bytree=cfg.baseline.lgbm_colsample_bytree,
        )
    else:
        _lgbm_builder = lambda seed: __import__("lightgbm").LGBMClassifier(
            objective="multiclass" if cfg.data.target_mode == "ternary" else "binary",
            num_class=3 if cfg.data.target_mode == "ternary" else 1,
            max_depth=cfg.baseline.max_depth,
            num_leaves=cfg.baseline.lgbm_num_leaves,
            n_estimators=cfg.baseline.n_estimators,
            learning_rate=cfg.baseline.learning_rate,
            random_state=seed, verbosity=-1,
            class_weight="balanced",
            reg_alpha=cfg.baseline.lgbm_reg_alpha,
            reg_lambda=cfg.baseline.lgbm_reg_lambda,
            min_child_samples=cfg.baseline.lgbm_min_child_samples,
            subsample=cfg.baseline.lgbm_subsample,
            colsample_bytree=cfg.baseline.lgbm_colsample_bytree,
        )

    # ── CatBoost ──
    if is_reg:
        _cb_builder = lambda seed: __import__("catboost").CatBoostRegressor(
            depth=cfg.baseline.catboost_depth,
            iterations=cfg.baseline.catboost_iterations,
            learning_rate=cfg.baseline.catboost_learning_rate,
            random_seed=seed,
            loss_function="RMSE",
            verbose=False, allow_writing_files=False,
            l2_leaf_reg=cfg.baseline.catboost_l2_leaf_reg,
        )
    else:
        _cb_builder = lambda seed: __import__("catboost").CatBoostClassifier(
            depth=cfg.baseline.catboost_depth,
            iterations=cfg.baseline.catboost_iterations,
            learning_rate=cfg.baseline.catboost_learning_rate,
            random_seed=seed,
            loss_function="MultiClass" if cfg.data.target_mode == "ternary" else "Logloss",
            verbose=False, allow_writing_files=False,
            auto_class_weights="Balanced",
            l2_leaf_reg=cfg.baseline.catboost_l2_leaf_reg,
        )

    # ── Artifact directory ──
    sector_slug = sector_name.lower().replace(" ", "_").replace("/", "_")
    sector_dir = Path(cfg.artifacts_dir) / f"_sector_{sector_slug}"
    sector_dir.mkdir(parents=True, exist_ok=True)

    # ── Train tabular baselines (loop over horizons) ──
    horizons = cfg.data.forecast_horizons if cfg.data.forecast_horizons else (cfg.data.forecast_horizon,)
    ternary_policy = _build_ternary_policy(cfg)

    lgbm_result: dict[str, Any] = {"status": "completed", "model_name": "lightgbm"}
    cb_result: dict[str, Any] = {"status": "completed", "model_name": "catboost"}
    horizon_metrics_lgbm: dict[str, dict] = {}
    horizon_metrics_cb: dict[str, dict] = {}

    for h in horizons:
        _target_col = f"target_h{h}" if cfg.data.forecast_horizons else "target"
        _future_col = f"future_return_h{h}" if cfg.data.forecast_horizons else "future_return"
        _horizon_tag = f"h{h}"

        LOGGER.info(
            "train_sector horizon=%s sector=%s symbols=%d",
            _horizon_tag, sector_name, len(symbols),
        )

        # Swap target/future_return columns for this horizon
        _df = prepared_df.copy()
        if cfg.data.forecast_horizons:
            if _target_col not in _df.columns or _future_col not in _df.columns:
                LOGGER.warning("train_sector: skipping horizon %s (columns missing)", _horizon_tag)
                continue
            _df["target"] = _df[_target_col]
            _df["future_return"] = _df[_future_col]

        _sector_dir_h = sector_dir / _horizon_tag
        _sector_dir_h.mkdir(parents=True, exist_ok=True)

        LOGGER.info(
            "train_sector horizon=%s: training baselines (lgbm+catboost) sector=%s",
            _horizon_tag, sector_name,
        )
        _lgbm_h = run_tabular_baseline(
            _df, cfg,
            model_name="lightgbm",
            model_builder=_lgbm_builder,
            artifact_dir=_sector_dir_h / "lightgbm",
            model_extension=".txt" if not is_reg else ".pkl",
            ternary_policy=ternary_policy,
            by_dates=True,
            symbol_tag=f"{sector_name}_{_horizon_tag}",
            forecast_horizon_override=h,
        )
        _cb_h = run_tabular_baseline(
            _df, cfg,
            model_name="catboost",
            model_builder=_cb_builder,
            artifact_dir=_sector_dir_h / "catboost",
            model_extension=".cbm" if not is_reg else ".pkl",
            ternary_policy=ternary_policy,
            by_dates=True,
            symbol_tag=f"{sector_name}_{_horizon_tag}",
            forecast_horizon_override=h,
        )

        horizon_metrics_lgbm[_horizon_tag] = _lgbm_h
        horizon_metrics_cb[_horizon_tag] = _cb_h

        # ── Walk-forward tabular ──
        if cfg.walk_forward.enabled:
            lgbm_wf = run_tabular_walk_forward(
                _df, cfg,
                model_name="lightgbm",
                model_builder=_lgbm_builder,
                ternary_policy=ternary_policy,
                by_dates=True,
                symbol_tag=f"{sector_name}_{_horizon_tag}",
                forecast_horizon_override=h,
            )
            if lgbm_wf.get("status") == "completed" and lgbm_wf.get("mean"):
                _lgbm_h["wf"] = lgbm_wf["mean"]
                _lgbm_h["walk_forward"] = lgbm_wf

            cb_wf = run_tabular_walk_forward(
                _df, cfg,
                model_name="catboost",
                model_builder=_cb_builder,
                ternary_policy=ternary_policy,
                by_dates=True,
                symbol_tag=f"{sector_name}_{_horizon_tag}",
                forecast_horizon_override=h,
            )
            if cb_wf.get("status") == "completed" and cb_wf.get("mean"):
                _cb_h["wf"] = cb_wf["mean"]
                _cb_h["walk_forward"] = cb_wf

    # Merge horizon results: use h15 as primary (backward compat), store all in "horizons"
    # ⚠️ Copier pour éviter une référence circulaire :
    #    lgbm_result["horizons"][primary_h] → lgbm_result (cycle)
    _primary_horizon = "h15" if "h15" in horizon_metrics_lgbm else next(iter(horizon_metrics_lgbm), None)
    if _primary_horizon:
        lgbm_result = dict(horizon_metrics_lgbm[_primary_horizon])  # shallow copy
        cb_result = dict(horizon_metrics_cb[_primary_horizon])  # shallow copy
    lgbm_result["horizons"] = horizon_metrics_lgbm
    cb_result["horizons"] = horizon_metrics_cb

    # ── LSTM (si activé) ──
    lstm_result: dict[str, Any] = {"status": "skipped", "reason": "lstm_not_implemented_for_sectors"}
    # TODO: LSTM with symbol embedding — V2
    # For now, we use the tabular models only for per-sector training.

    # ── Champion selection ──
    challengers = {
        "lightgbm": lgbm_result,
        "catboost": cb_result,
    }
    # Simple champion: pick the one with better WF f1_macro
    lgbm_score = float(lgbm_result.get("selection_score") or 0)
    cb_score = float(cb_result.get("selection_score") or 0)
    champion = "lightgbm" if lgbm_score >= cb_score else "catboost"

    result = {
        "sector": sector_name,
        "status": "completed",
        "symbols_count": len(symbols),
        "feature_cols": tab_feature_cols,
        "lightgbm": lgbm_result,
        "catboost": cb_result,
        "lstm_attention": lstm_result,
        "champion": champion,
        "champion_score": max(lgbm_score, cb_score),
        "artifact_dir": str(sector_dir),
    }

    # ── Save metadata ──
    config_path = sector_dir / "config.json"
    sector_config = {
        "sector": sector_name,
        "symbols": symbols,
        "feature_cols": tab_feature_cols,
        "training_mode": "per_sector",
        "target_mode": cfg.data.target_mode,
        "champion": champion,
    }
    with open(config_path, "w") as f:
        json.dump(sector_config, f, indent=2, default=str)

    # ── Persist to DB ──
    try:
        sector_run_id = f"{batch_id}_{sector_slug}" if batch_id else f"sector_{sector_slug}_{uuid.uuid4().hex[:8]}"
        _persist_sector_metrics(
            engine, sector_name, run_id=sector_run_id,
            lgbm_result=lgbm_result, cb_result=cb_result,
            batch_id=batch_id,
        )
    except Exception as exc:
        LOGGER.warning("train_sector: failed to persist metrics for %s: %s", sector_name, exc)

    LOGGER.info(
        "train_sector completed sector=%s symbols=%d champion=%s score=%.4f",
        sector_name, len(symbols), champion, max(lgbm_score, cb_score),
    )
    return result


def run_per_sector_batch(
    symbols: list[str],
    engine: Any,
    cfg: TrainingConfig,
    *,
    batch_id: str | None = None,
) -> list[dict[str, Any]]:
    """Exécute l'entraînement per-sector pour tous les secteurs.

    Returns
    -------
    list of result dicts, one per sector.
    """
    sector_groups = load_sector_groups(engine)
    if not sector_groups:
        raise RuntimeError("No sector groups found — check stock_metadata.provider_sector")

    # Filter to requested symbols only
    requested = set(s.upper() for s in symbols)
    filtered_groups: dict[str, list[str]] = {}
    for gics, syms in sector_groups.items():
        filtered = [s for s in syms if s in requested]
        if filtered:
            filtered_groups[gics] = filtered

    LOGGER.info(
        "run_per_sector_batch: %d symbols → %d sectors (filtered from %d total sectors)",
        len(requested), len(filtered_groups), len(sector_groups),
    )

    if not filtered_groups:
        raise RuntimeError("No symbols match any sector — check symbol list vs stock_metadata")

    # Load shared data (same for all sectors)
    sentiment_df = _load_sentiment_for_symbols(symbols, engine, cfg)
    benchmark_df = _load_benchmark(engine, cfg)
    universe_df = _load_universe(symbols, engine)
    selector_df = _load_selector_for_symbols(symbols, engine, cfg)
    fundamental_df = _load_fundamentals_for_symbols(symbols, engine, cfg)

    # Train sectors sequentially
    results: list[dict[str, Any]] = []
    _total_sectors = len(filtered_groups)
    _sector_names = sorted(filtered_groups.keys())
    LOGGER.info(
        "🏁 run_per_sector_batch START: %d sectors to process: %s",
        _total_sectors, ", ".join(_sector_names),
    )
    for _idx, (sector_name, sector_symbols) in enumerate(sorted(filtered_groups.items()), start=1):
        LOGGER.info(
            "🔄 run_per_sector_batch [%d/%d] START sector=%s symbols=%d",
            _idx, _total_sectors, sector_name, len(sector_symbols),
        )
        try:
            result = _train_sector_models(
                sector_name,
                sector_symbols,
                engine,
                cfg,
                sentiment_df=sentiment_df,
                benchmark_df=benchmark_df,
                universe_df=universe_df,
                selector_df=selector_df,
                fundamental_df=fundamental_df,
                batch_id=batch_id,
            )
            results.append(result)
            LOGGER.info(
                "✅ run_per_sector_batch [%d/%d] DONE sector=%s status=%s",
                _idx, _total_sectors, sector_name, result.get("status", "?"),
            )
        except Exception as exc:
            LOGGER.error(
                "❌ run_per_sector_batch [%d/%d] FAILED sector=%s: %s",
                _idx, _total_sectors, sector_name, exc,
            )
            results.append({"sector": sector_name, "status": "failed", "reason": str(exc)})

    # ── Final summary ──
    _completed = sum(1 for r in results if r.get("status") == "completed")
    _failed = sum(1 for r in results if r.get("status") == "failed")
    _skipped = sum(1 for r in results if r.get("status") == "skipped")
    LOGGER.info(
        "🏁🏁🏁 run_per_sector_batch FINISHED: %d total | %d completed | %d failed | %d skipped 🏁🏁🏁",
        len(results), _completed, _failed, _skipped,
    )
    return results


def _load_benchmark(engine: Any, cfg: TrainingConfig) -> pd.DataFrame | None:
    try:
        from modelFactory.data_loader import load_benchmark_bars
        return load_benchmark_bars(
            engine,
            cfg.data.benchmark_symbol,
            end_date=cfg.data.training_end_date,
            start_date=cfg.data.training_start_date,
        )
    except Exception:
        return None


def _load_sentiment_for_symbols(symbols: list[str], engine: Any, cfg: TrainingConfig) -> pd.DataFrame | None:
    try:
        from modelFactory.data_loader import load_symbol_sentiment
        frames = []
        for sym in symbols:
            df = load_symbol_sentiment(sym, engine, cfg.data)
            if df is not None and not df.empty:
                df["symbol"] = sym
                frames.append(df)
        return pd.concat(frames, ignore_index=True) if frames else None
    except Exception:
        return None


def _load_universe(symbols: list[str], engine: Any) -> pd.DataFrame | None:
    try:
        from modelFactory.data_loader import load_tradable_universe_for_period
        # Load universe data for the symbols
        return load_tradable_universe_for_period(engine, None, None)
    except Exception:
        return None


def _load_selector_for_symbols(symbols: list[str], engine: Any, cfg: TrainingConfig) -> pd.DataFrame | None:
    try:
        from modelFactory.data_loader import load_symbol_selector_context
        frames = []
        for sym in symbols:
            df = load_symbol_selector_context(sym, engine, cfg)
            if df is not None and not df.empty:
                df["symbol"] = sym
                frames.append(df)
        return pd.concat(frames, ignore_index=True) if frames else None
    except Exception:
        return None


def _load_fundamentals_for_symbols(symbols: list[str], engine: Any, cfg: TrainingConfig) -> pd.DataFrame | None:
    try:
        from modelFactory.data_loader import load_fundamentals_for_symbols as _load_fund
        return _load_fund(
            symbols,
            start_date=cfg.data.training_start_date or pd.Timestamp.now().date(),
            end_date=cfg.data.training_end_date or pd.Timestamp.now().date(),
            engine=engine,
        )
    except Exception:
        return None
