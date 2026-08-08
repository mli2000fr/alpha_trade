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
from dataclasses import asdict
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
    cross_sectional_df: pd.DataFrame | None = None,
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

    # ── P0-1 fix (2026-08-04) : préparer chaque symbole INDÉPENDAMMENT ──
    # Avant : concaténation des barres brutes → prepare_symbol_frame sur le panel
    #   → compute_features() fait sort_values("date") sans groupby("symbol")
    #   → rolling() et shift(-h) traversent les symboles → features corrompues.
    # Après : chaque symbole est préparé isolément, PUIS les frames sont concaténées.
    prepared_frames: list[pd.DataFrame] = []
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
            # Préparer ce symbole seul (features + targets, PAS de neutralisation)
            # Note: universe_df n'est pas passé → pas de cross-sectional features
            # par symbole. Elles seront fusionnées après concaténation si activées.
            sym_prepared = prepare_symbol_frame(
                bars,
                cfg.data,
                sentiment_df=sentiment_df[sentiment_df["symbol"] == sym] if sentiment_df is not None and "symbol" in sentiment_df.columns else sentiment_df,
                benchmark_df=benchmark_df,
                universe_df=None,  # cross-sectional: fusionné après concaténation
                selector_df=selector_df[selector_df["symbol"] == sym] if selector_df is not None and "symbol" in selector_df.columns else selector_df,
                fundamental_df=fundamental_df[fundamental_df["symbol"] == sym] if fundamental_df is not None and "symbol" in fundamental_df.columns else fundamental_df,
            )
            sym_prepared["symbol"] = sym
            prepared_frames.append(sym_prepared)
        except Exception as exc:
            LOGGER.warning("train_sector: failed to prepare %s: %s", sym, exc)

    if not prepared_frames:
        raise ValueError(f"No bar data loaded for any symbol in sector")

    prepared = pd.concat(prepared_frames, ignore_index=True)
    prepared = prepared.sort_values(["date", "symbol"]).reset_index(drop=True)
    LOGGER.info(
        "train_sector: prepared %d symbols independently, %d total rows",
        len(prepared_frames), len(prepared),
    )

    # ── Action 1.1 (2026-08-04) : fusionner les features cross-sectionnelles ──
    # Avant : universe_df=None → les colonnes XS étaient remplies de valeurs
    # neutres (0.5 pour les rangs, 0.0 pour les sectorielles/neutralisées)
    # par merge_cross_sectional_features, rendant ~30 features inactives.
    # Maintenant : on construit le cache XS une fois dans run_per_sector_batch
    # et on le merge ici après concaténation.
    from modelFactory.cross_sectional import (
        CROSS_SECTIONAL_FEATURE_COLUMNS,
        GLOBAL_PRED_FEATURE_COLUMNS,
        merge_cross_sectional_features,
    )
    prepared = merge_cross_sectional_features(prepared, cross_sectional_df)
    # Diagnostic : compter les colonnes XS réellement alimentées (variance > 0)
    _rank_cols = set(CROSS_SECTIONAL_FEATURE_COLUMNS) | set(GLOBAL_PRED_FEATURE_COLUMNS)
    _xs_cols = [c for c in prepared.columns if c in _rank_cols or c.startswith("sector_") or c.startswith("global_rank")]
    _xs_alive = 0
    if _xs_cols:
        _xs_var = prepared[_xs_cols].var(numeric_only=True)
        _xs_alive = int((_xs_var > 1e-9).sum())
    LOGGER.info(
        "train_sector: XS merge done — %d XS columns requested, %d alive (variance > 0)",
        len(_xs_cols), _xs_alive,
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

    # ── T2 experiment (2026-08-05) : rang percentile intra-secteur ──
    # Au lieu de prédire la magnitude de la surperformance, le modèle apprend
    # à classer les titres dans leur secteur. La target devient un rang [0,1].
    if cfg.data.target_intra_sector_rank:
        _ranked = 0
        if cfg.data.forecast_horizons:
            for h in cfg.data.forecast_horizons:
                _col = f"target_h{h}"
                if _col in prepared.columns:
                    prepared[_col] = prepared.groupby("date")[_col].rank(pct=True)
                    _ranked += 1
            if "target" in prepared.columns:
                prepared["target"] = prepared[f"target_h{cfg.data.forecast_horizon}"]
        elif "target" in prepared.columns:
            prepared["target"] = prepared.groupby("date")["target"].rank(pct=True)
            _ranked = 1
        LOGGER.info(
            "train_sector: T2 intra-sector rank applied — %d targets converted to percentile rank [0,1]",
            _ranked,
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
        include_fundamentals=cfg.data.include_fundamentals_features,
        include_score_components=cfg.data.include_score_components,
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
    sector_dir: Path | None = None,
    symbols: list[str] | None = None,
    cfg: Any = None,
    has_symbol_feat: bool = False,
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
    # ── Déterminer sector_dir (paramètre ou dérivé du model_path) ──
    if sector_dir is None:
        _model_path = lgbm_result.get("artifact_paths", {}).get("model_path") or ""
        sector_dir = Path(_model_path).parent.parent if _model_path else Path(".")
    artifact_routes = {
        "lightgbm": {
            "inference_backend": "lightgbm_tabular",
            "config_path": str(sector_dir / "config.json"),
            "model_path": str(lgbm_result.get("artifact_paths", {}).get("model_path", "")),
        },
        "catboost": {
            "inference_backend": "catboost_tabular",
            "config_path": str(sector_dir / "config.json"),
            "model_path": str(cb_result.get("artifact_paths", {}).get("model_path", "")),
        },
    }
    # ── P0-2 fix (2026-08-04) : persister un config.json complet pour l'inférence ──
    _feature_cols = lgbm_result.get("feature_columns") or cb_result.get("feature_columns") or []
    # P0-3: persister la liste des symboles comme catégories pour reconstruction
    _symbol_categories = sorted(symbols) if (has_symbol_feat and symbols) else None
    _artifact_routes_for_config = {
        "selected_model": champion,
        "models": {
            "lightgbm": artifact_routes["lightgbm"],
            "catboost": artifact_routes["catboost"],
        },
    }
    _sector_config = {
        "run_id": run_id,
        "data": asdict(cfg.data),
        "model": asdict(cfg.model),
        "feature_columns": _feature_cols,
        "feature_contract": lgbm_result.get("feature_contract") or cb_result.get("feature_contract"),
        "feature_fingerprint": lgbm_result.get("feature_fingerprint") or cb_result.get("feature_fingerprint"),
        "inference_backend": f"{champion}_tabular",
        "selected_model": champion,
        "sector": sector_name,
        "symbols": symbols,
        "target_mode": cfg.data.target_mode,
        "artifact_routes": _artifact_routes_for_config,
        # P0-3: catégories pour reconstruction du dtype category à l'inférence
        "symbol_categories": _symbol_categories,
    }
    _config_path = Path(artifact_routes[champion]["config_path"])
    _config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(_config_path, "w", encoding="utf-8") as _fh:
        json.dump(_sector_config, _fh, indent=2, default=str)
    # ── Marquer completed AVANT replace_model_governance (survit si erreur ensuite) ──
    update_training_run(engine, run_id, status="completed", finished_at=datetime.now(timezone.utc))

    replace_model_governance(
        engine, run_id=run_id, symbol=sector_name,
        challengers=challengers,
        artifact_routes_models=artifact_routes,
        selected_model=champion,
        selection_mode="auto_selected_champion",
        selection_metric="selection_score",
        ranking=[],
    )

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
    cross_sectional_df: pd.DataFrame | None = None,
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
        cross_sectional_df=cross_sectional_df,
    )

    if train_df.empty:
        return {"sector": sector_name, "status": "skipped", "reason": "empty_train"}

    # ── T3 experiment (2026-08-05) : classification ternaire intra-secteur ──
    # Convertit la target continue en labels LONG(+1)/FLAT(0)/SHORT(-1)
    # avec des seuils en quantiles calculés sur le TRAIN uniquement.
    _is_ternary = (
        cfg.data.target_mode == "regression"
        and cfg.data.target_ternary_intra_sector
    )
    if _is_ternary:
        from dataclasses import replace
        _q = cfg.data.target_ternary_quantile
        _q_lo = _q
        _q_hi = 1.0 - _q
        for _df in (train_df, val_df, test_df):
            if "target" not in _df.columns:
                continue
            _target = _df["target"].copy()
            if _df is train_df:
                _train_lo = _target.quantile(_q_lo)
                _train_hi = _target.quantile(_q_hi)
                LOGGER.info(
                    "train_sector T3: train quantiles lo=%.4f (q=%.2f) hi=%.4f (q=%.2f)",
                    _train_lo, _q_lo, _train_hi, _q_hi,
                )
            _ternary = pd.Series(0, index=_df.index, dtype=int)
            _ternary = _ternary.mask(_target > _train_hi, 1)
            _ternary = _ternary.mask(_target < _train_lo, -1)
            _df["target"] = _ternary
            # Propager aux targets multi-horizon si présentes
            for _hcol in [c for c in _df.columns if c.startswith("target_h")]:
                _t = _df[_hcol].copy()
                _t_ternary = pd.Series(0, index=_df.index, dtype=int)
                _t_ternary = _t_ternary.mask(_t > _train_hi, 1)
                _t_ternary = _t_ternary.mask(_t < _train_lo, -1)
                _df[_hcol] = _t_ternary
        _ternary_dist = train_df["target"].value_counts().to_dict()
        LOGGER.info(
            "train_sector T3: ternary distribution train — %s", _ternary_dist,
        )
        # Remplacer cfg pour que les fonctions aval voient target_mode="ternary"
        cfg = replace(cfg, data=replace(cfg.data, target_mode="ternary"))

    # Build prepared_df for tabular baselines
    prepared_df = pd.concat([train_df, val_df, test_df], ignore_index=True)

    # Ensure symbol is a categorical feature for tree models (P0-3 fix)
    tab_feature_cols = list(feature_cols)
    _has_symbol_feat = "symbol" in tab_feature_cols

    # ── LightGBM ──
    is_reg = cfg.data.target_mode == "regression" and not _is_ternary
    _effective_mode = "ternary" if _is_ternary else cfg.data.target_mode
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
            objective="multiclass" if _effective_mode == "ternary" else "binary",
            num_class=3 if _effective_mode == "ternary" else 1,
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
    # P0-3 fix: passer cat_features=["symbol"] pour le support natif des catégorielles
    _cb_cat_features = ["symbol"] if _has_symbol_feat else None
    if is_reg:
        _cb_builder = lambda seed, cf=_cb_cat_features: __import__("catboost").CatBoostRegressor(
            depth=cfg.baseline.catboost_depth,
            iterations=cfg.baseline.catboost_iterations,
            learning_rate=cfg.baseline.catboost_learning_rate,
            random_seed=seed,
            loss_function="RMSE",
            verbose=False, allow_writing_files=False,
            l2_leaf_reg=cfg.baseline.catboost_l2_leaf_reg,
            **( {"cat_features": cf} if cf else {}),
        )
    else:
        _cb_builder = lambda seed, cf=_cb_cat_features: __import__("catboost").CatBoostClassifier(
            depth=cfg.baseline.catboost_depth,
            iterations=cfg.baseline.catboost_iterations,
            learning_rate=cfg.baseline.catboost_learning_rate,
            random_seed=seed,
            loss_function="MultiClass" if _effective_mode == "ternary" else "Logloss",
            verbose=False, allow_writing_files=False,
            auto_class_weights="Balanced",
            l2_leaf_reg=cfg.baseline.catboost_l2_leaf_reg,
            **( {"cat_features": cf} if cf else {}),
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

        # ── Encodage catégoriel de "symbol" (P0-3 fix) ──
        if _has_symbol_feat and "symbol" in _df.columns:
            _df["symbol"] = _df["symbol"].astype("category")

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
            feature_columns_override=tab_feature_cols,
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
            feature_columns_override=tab_feature_cols,
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
                feature_columns_override=tab_feature_cols,
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
                feature_columns_override=tab_feature_cols,
            )
            if cb_wf.get("status") == "completed" and cb_wf.get("mean"):
                _cb_h["wf"] = cb_wf["mean"]
                _cb_h["walk_forward"] = cb_wf

    # Merge horizon results: use forecast_horizon (max horizon) as primary (P2-2 fix)
    # ⚠️ Copier pour éviter une référence circulaire :
    #    lgbm_result["horizons"][primary_h] → lgbm_result (cycle)
    _primary_horizon = f"h{cfg.data.forecast_horizon}"
    if _primary_horizon not in horizon_metrics_lgbm:
        _primary_horizon = next(iter(horizon_metrics_lgbm), None)  # fallback
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
            sector_dir=sector_dir,
            symbols=symbols,
            cfg=cfg,
            has_symbol_feat=_has_symbol_feat,
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
    sentiment_df = _load_sentiment_for_symbols(symbols, engine, cfg) if cfg.data.include_sentiment_features else None
    benchmark_df = _load_benchmark(engine, cfg)
    universe_df = _load_universe(symbols, engine)
    selector_df = None
    if cfg.data.include_screener_scores or cfg.data.include_short_score_features:
        selector_df = _load_selector_for_symbols(symbols, engine, cfg)
    fundamental_df = _load_fundamentals_for_symbols(symbols, engine, cfg) if cfg.data.include_fundamentals_features else None

    # ── Action 1.1 (2026-08-04) : construire le cache cross-sectionnel UNE FOIS ──
    # Avant : chaque _prepare_sector_data recevait universe_df=None → les features
    # XS étaient remplies de valeurs neutres (0.5). Maintenant : on bâtit le cache
    # globalement (comme le fait l'orchestrateur pour le per-symbol) et on le passe
    # à chaque secteur.
    cross_sectional_cache: pd.DataFrame | None = None
    _needs_cross_sectional = (
        cfg.data.enable_cross_sectional_features
        or cfg.global_model.stacking_enabled
    )
    if _needs_cross_sectional and symbols:
        from modelFactory.cross_sectional import build_cross_sectional_features_from_db, _load_sector_mapping
        LOGGER.info(
            "run_per_sector_batch: building cross-sectional cache for %d symbols", len(symbols),
        )
        _sector_map: dict[str, str] | None = _load_sector_mapping(engine)
        cross_sectional_cache, _xs_diag = build_cross_sectional_features_from_db(
            engine,
            symbols,
            benchmark_df=benchmark_df,
            min_universe_size=cfg.data.cross_sectional_min_universe,
            start_date=cfg.data.training_start_date,
            end_date=cfg.data.training_end_date,
            sector_map=_sector_map,
        )
        LOGGER.info(
            "run_per_sector_batch: XS cache ready — rows=%d symbols=%d",
            len(cross_sectional_cache),
            cross_sectional_cache["symbol"].nunique() if not cross_sectional_cache.empty else 0,
        )

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
                cross_sectional_df=cross_sectional_cache,
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
    """Charge les features sentiment pour une liste de symboles.

    Utilise load_symbols_sentiment (pluriel) pour charger toutes les
    données en une seule requête SQL.
    """
    try:
        from modelFactory.data_loader import load_symbols_sentiment
        return load_symbols_sentiment(
            engine,
            symbols,
            end_date=cfg.data.training_end_date,
            start_date=cfg.data.training_start_date,
        )
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
    """Charge le contexte selector PIT-safe pour une liste de symboles.

    Utilise load_symbols_selector_context (pluriel) pour charger toutes les
    données en une seule requête SQL (plus efficace que N appels mono-symbole).
    """
    try:
        from modelFactory.data_loader import load_symbols_selector_context
        return load_symbols_selector_context(
            engine,
            symbols,
            end_date=cfg.data.training_end_date,
            start_date=cfg.data.training_start_date,
        )
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
