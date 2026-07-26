"""modelFactory/global_ranking.py — Global Ranking Model (Sprint 2026-07-25).

Régression cross-sectionnelle du rendement futur J+10 → rang percentil.
Remplace l'ancien classifieur ternaire global_model.py pour le stacking.

Contrat PIT :
- Entraîné en walk-forward (mêmes splits que le per-symbol).
- Target : future_return (continu, J+10), pas de classification.
- Sortie : global_rank[symbol, date] ∈ [0, 1] (percentile dans l'univers).
- Métrique : IC Rank (Spearman correlation), pas de F1.

Architecture :
- Toutes les features (OHLCV, expert, cross-sectional, macro, screener, sentiment).
- LightGBM ou CatBoost en mode régression.
- Walk-forward identique au per-symbol pour garantir le PIT.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.config import ReproducibilityConfig, TrainingConfig
from modelFactory.cross_sectional import (
    build_cross_sectional_features,
    merge_cross_sectional_features,
)
from modelFactory.data_loader import (
    load_benchmark_bars,
    load_symbols_selector_context,
    load_symbols_sentiment,
    load_universe_bars,
    load_universe_latest_bar_date,
    resolve_training_start_date,
)
from modelFactory.dataset import generate_walk_forward_splits
from modelFactory.features import (
    build_feature_contract,
    compute_features,
    get_feature_columns,
)
from modelFactory.features import fingerprint as compute_feature_fingerprint
from modelFactory.reproducibility import apply_reproducibility, derive_seed

LOGGER = logging.getLogger(__name__)

# Horizons pour le ranking multi-horizons (stacking Phase 2)
_GLOBAL_RANKING_HORIZONS: tuple[int, ...] = (3, 5, 10)


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _prepare_global_ranking_frame(
    bars_df: pd.DataFrame,
    cfg: TrainingConfig,
    *,
    benchmark_df: pd.DataFrame | None = None,
    sentiment_df: pd.DataFrame | None = None,
    selector_df: pd.DataFrame | None = None,
    cross_sectional_df: pd.DataFrame | None = None,
    symbol: str | None = None,
    horizon: int = 10,
) -> pd.DataFrame:
    """Prépare le DataFrame pour un symbole avec toutes les features + future_return."""
    df = compute_features(
        bars_df,
        sentiment_df=sentiment_df,
        include_sentiment=cfg.data.include_sentiment_features,
        benchmark_df=benchmark_df,
        feature_set=cfg.data.feature_set,
        selector_df=selector_df,
        include_screener_scores=cfg.data.include_screener_scores,
        include_short_score=cfg.data.include_short_score_features,
        include_macro_vix=cfg.data.include_macro_vix_features,
        include_macro_vxn=cfg.data.include_macro_vxn_features,
        include_macro_vix3m=cfg.data.include_macro_vix3m_features,
        include_macro_move=cfg.data.include_macro_move_features,
        include_fundamentals=cfg.data.include_fundamentals_features,
        include_factors=cfg.data.include_factors_features,
        include_macro_regime=cfg.data.include_macro_regime_features,
    )
    if cfg.data.enable_cross_sectional_features and cross_sectional_df is not None:
        df = merge_cross_sectional_features(df, cross_sectional_df)

    # Target : rendement excédentaire vs SPY (market-neutral), horizon variable
    close = df["close"].astype(float)
    stock_return = close.shift(-horizon) / close - 1.0

    if benchmark_df is not None and "close" in benchmark_df.columns:
        _spy_close = benchmark_df.set_index("date")["close"].astype(float)
        _spy_return = _spy_close.shift(-horizon) / _spy_close - 1.0
        _spy_map = _spy_return.reindex(pd.to_datetime(df["date"])).fillna(0.0)
        df["future_return"] = (stock_return - _spy_map.values).astype(float)
    else:
        df["future_return"] = stock_return

    # Stocker aussi le rendement brut pour référence
    df[f"future_return_raw"] = stock_return

    return df


def _get_ranking_feature_columns(cfg: TrainingConfig) -> list[str]:
    """Retourne les features pour le Global Ranking Model.

    Exclut les features macro-globales (identiques pour tous les symboles
    à une date donnée) car elles ne peuvent pas discriminer le classement
    cross-sectionnel. Ces features restent disponibles pour les modèles
    per-symbol (Phase 2) qui en ont besoin pour le contexte de régime.
    """
    all_cols = get_feature_columns(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
        include_screener_scores=cfg.data.include_screener_scores,
        include_short_score=cfg.data.include_short_score_features,
        include_macro_vix=cfg.data.include_macro_vix_features,
        include_macro_vxn=cfg.data.include_macro_vxn_features,
        include_macro_vix3m=cfg.data.include_macro_vix3m_features,
        include_macro_move=cfg.data.include_macro_move_features,
        include_global_stacking=False,
        include_fundamentals=cfg.data.include_fundamentals_features,
        include_factors=cfg.data.include_factors_features,
        include_macro_regime=cfg.data.include_macro_regime_features,
    )
    # Supprimer les features purement macro (identiques pour tous les symboles
    # à une date donnée → ne peuvent pas classer les titres entre eux).
    _macro_blacklist: set[str] = {
        # Macro regime (calculées depuis SPY/VIX, identiques ∀ symboles)
        "SPY_SMA_200_slope", "VIX_zscore",
        # VIX / VXN / VIX3M / MOVE (identiques ∀ symboles)
        "vix_close", "vix_momentum_5j",
        "vxn_close", "vxn_spread_vix",
        "vix3m_close", "vix_term_structure_ratio", "vix_backwardation",
        "move_close",
        # Régime de marché SPY (identiques ∀ symboles)
        "market_return_20", "market_volatility_20", "market_trend_strength_50",
        "regime_bull_market", "regime_risk_off",
    }
    return [c for c in all_cols if c not in _macro_blacklist]


def compute_ic_rank(predicted: np.ndarray, actual: np.ndarray) -> float | None:
    """Spearman rank correlation (Information Coefficient).

    Métrique standard en finance quantitative.
    - IC > 0.05 : bon modèle de ranking
    - IC > 0.10 : excellent

    Returns None si moins de 10 observations.
    """
    if len(predicted) < 10:
        return None
    try:
        from scipy.stats import spearmanr
        corr, _ = spearmanr(predicted, actual)
        return float(corr)
    except Exception:
        return None


def _compute_per_date_rank(pred_df: pd.DataFrame, *, suffix: str = "") -> pd.DataFrame:
    """Calcule le rang percentil (0..1) par date.

    Si suffix est fourni (ex: "_3", "_5", "_10"), les colonnes sont suffixées.
    """
    result = pred_df.copy()
    pred_col = "predicted_return"
    rank_col = "global_rank" if not suffix else f"global_rank{suffix}"
    if suffix:
        pred_col = f"predicted_return{suffix}"
    if pred_col not in result.columns:
        result[rank_col] = 0.5
        return result
    result[rank_col] = result.groupby("date")[pred_col].rank(pct=True)
    result[rank_col] = result[rank_col].fillna(0.5).astype(np.float64)
    return result


# ────────────────────────────────────────────────────────────────────
# Modèle principal
# ────────────────────────────────────────────────────────────────────

def _import_lightgbm() -> Any:
    import lightgbm as lgb  # type: ignore[import-not-found]
    return lgb


def _import_catboost() -> Any:
    from catboost import CatBoostRegressor  # type: ignore[import-not-found]
    return CatBoostRegressor


def _build_ranking_estimator(
    cfg: TrainingConfig,
    *,
    resolved_seed: int,
) -> tuple[str, Any]:
    """Construit l'estimateur de ranking (LightGBM ou CatBoost en régression)."""
    model_name = cfg.global_model.model_name
    if model_name == "catboost":
        try:
            CatBoostRegressor = _import_catboost()
        except ImportError:
            LOGGER.warning("CatBoost indisponible pour global ranking → fallback LightGBM")
            model_name = "lightgbm"
    if model_name == "lightgbm":
        lgb = _import_lightgbm()
        return "lightgbm", lgb.LGBMRanker(
            objective="lambdarank",
            metric="ndcg",
            eval_at=[10, 20, 50],
            max_depth=cfg.baseline.max_depth,
            num_leaves=cfg.baseline.lgbm_num_leaves,
            n_estimators=cfg.baseline.n_estimators,
            learning_rate=cfg.baseline.learning_rate,
            random_state=resolved_seed,
            verbosity=-1,
            reg_alpha=cfg.baseline.lgbm_reg_alpha,
            reg_lambda=cfg.baseline.lgbm_reg_lambda,
            min_child_samples=cfg.baseline.lgbm_min_child_samples,
            subsample=cfg.baseline.lgbm_subsample,
            colsample_bytree=cfg.baseline.lgbm_colsample_bytree,
        )
    else:
        CatBoostRegressor = _import_catboost()
        return "catboost", CatBoostRegressor(
            depth=cfg.baseline.catboost_depth,
            iterations=cfg.baseline.catboost_iterations,
            learning_rate=cfg.baseline.catboost_learning_rate,
            random_seed=resolved_seed,
            loss_function="RMSE",
            verbose=False,
            l2_leaf_reg=cfg.baseline.catboost_l2_leaf_reg,
            border_count=cfg.baseline.catboost_border_count,
            random_strength=cfg.baseline.catboost_random_strength,
            bagging_temperature=cfg.baseline.catboost_bagging_temperature,
            od_type=cfg.baseline.catboost_od_type,
            od_wait=cfg.baseline.catboost_od_wait,
        )


def train_global_ranking_wf(
    symbols: list[str],
    cfg: TrainingConfig,
    *,
    artifacts_dir: Path,
    engine: Any,
) -> dict[str, Any]:
    """Entraîne le Global Ranking Model en walk-forward.

    Returns
    -------
    dict avec :
    - global_rank_df : pd.DataFrame [symbol, date, global_rank, predicted_return]
    - ic_rank_mean : float — IC Rank moyen WF
    - ic_rank_std : float — écart-type IC Rank WF
    - feature_columns : list[str]
    - status : str
    """
    if not cfg.global_model.enabled:
        return {"status": "skipped", "reason": "disabled"}

    horizon = cfg.data.forecast_horizon  # J+10 swing

    history_end_date = load_universe_latest_bar_date(
        engine, symbols, end_date=cfg.data.training_end_date,
    )
    history_start_date = resolve_training_start_date(
        history_end_date, cfg.data.training_start_date,
    )
    universe_df = load_universe_bars(
        engine, symbols, end_date=history_end_date, start_date=history_start_date,
    )
    if universe_df.empty:
        return {"status": "skipped", "reason": "empty_universe"}

    # ── Chargement données auxiliaires ──
    benchmark_df = None
    if cfg.data.feature_set == "expert":
        benchmark_df = load_benchmark_bars(
            engine, cfg.data.benchmark_symbol,
            end_date=history_end_date, start_date=history_start_date,
        )
    sentiment_df = None
    if cfg.data.include_sentiment_features:
        sentiment_df = load_symbols_sentiment(
            engine, symbols, end_date=history_end_date, start_date=history_start_date,
        )
    selector_context_df = None
    if cfg.data.include_screener_scores or cfg.data.include_short_score_features:
        selector_context_df = load_symbols_selector_context(
            engine, symbols, end_date=history_end_date, start_date=history_start_date,
        )
    cross_sectional_df = None
    if cfg.data.enable_cross_sectional_features:
        cross_sectional_df, _ = build_cross_sectional_features(
            universe_df, benchmark_df=benchmark_df,
            min_universe_size=cfg.data.cross_sectional_min_universe,
        )

    # ── Préparation du DataFrame poolé (features communes à tous les horizons) ──
    feature_columns = _get_ranking_feature_columns(cfg)
    _base_parts: list[pd.DataFrame] = []
    for symbol in symbols:
        bars_df = universe_df[universe_df["symbol"] == symbol].copy().sort_values("date").reset_index(drop=True)
        if len(bars_df) < cfg.data.min_history_days:
            continue
        sym_sentiment = None
        if sentiment_df is not None and not sentiment_df.empty:
            sym_sentiment = sentiment_df[sentiment_df["symbol"] == symbol].copy().reset_index(drop=True)
        sym_selector = None
        if selector_context_df is not None and not selector_context_df.empty:
            sym_selector = selector_context_df[selector_context_df["symbol"] == symbol].copy().reset_index(drop=True)
        sym_cross = None
        if cross_sectional_df is not None and not cross_sectional_df.empty:
            sym_cross = cross_sectional_df[cross_sectional_df["symbol"] == symbol].copy()

        prepared = _prepare_global_ranking_frame(
            bars_df, cfg,
            benchmark_df=benchmark_df, sentiment_df=sym_sentiment,
            selector_df=sym_selector, cross_sectional_df=sym_cross,
            symbol=symbol, horizon=max(_GLOBAL_RANKING_HORIZONS),
        )
        if prepared.empty:
            continue
        prepared["symbol"] = symbol
        _base_parts.append(prepared)

    if not _base_parts:
        return {"status": "skipped", "reason": "no_prepared_rows"}

    base_df = pd.concat(_base_parts, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
    # Conserver close + SPY close pour recalculer la target par horizon
    _close = base_df["close"].astype(float)
    _spy_series: pd.Series | None = None
    if benchmark_df is not None and "close" in benchmark_df.columns:
        _spy_close = benchmark_df.set_index("date")["close"].astype(float)
        _spy_series = _spy_close.reindex(pd.to_datetime(base_df["date"])).fillna(0.0)
    base_df = base_df.dropna(subset=feature_columns).reset_index(drop=True)

    # ── Walk-Forward splits (communs à tous les horizons) ──
    _daily_symbols = int(round(base_df.groupby("date").size().median()))
    _daily_symbols = max(_daily_symbols, 1)
    wf_splits = generate_walk_forward_splits(
        base_df,
        min_train_size=cfg.walk_forward.min_train_size * _daily_symbols,
        val_size=cfg.walk_forward.val_size * _daily_symbols,
        test_size=cfg.walk_forward.test_size * _daily_symbols,
        step_size=cfg.walk_forward.step_size * _daily_symbols,
        max_splits=cfg.walk_forward.max_splits,
        forecast_horizon=max(_GLOBAL_RANKING_HORIZONS),
        date_column="date",
    )
    if not wf_splits:
        return {"status": "skipped", "reason": "no_valid_wf_split"}

    LOGGER.info(
        "train_global_ranking_wf start symbols=%d splits=%d feature_cols=%d horizons=%s",
        len(symbols), len(wf_splits), len(feature_columns), list(_GLOBAL_RANKING_HORIZONS),
    )

    # ── Entraîner un modèle par horizon ──
    all_ic_means: dict[int, float] = {}
    all_rank_dfs: list[pd.DataFrame] = []
    _saved_models: dict[int, str] = {}

    for horizon in _GLOBAL_RANKING_HORIZONS:
        h_suffix = f"_{horizon}"
        LOGGER.info("global_ranking_wf horizon=%d start", horizon)

        # Calculer la target pour cet horizon
        base_df["future_return"] = (_close.shift(-horizon) / _close - 1.0)
        if _spy_series is not None:
            _spy_ret = _spy_series.shift(-horizon) / _spy_series - 1.0
            base_df["future_return"] = (base_df["future_return"] - _spy_ret).astype(float)
        base_df["future_return"] = base_df.groupby("date")["future_return"].rank(pct=True).astype(np.float64)

        resolved_seed = derive_seed(cfg.reproducibility.seed, f"global_ranking_wf_{horizon}", cfg.global_model.model_name)
        apply_reproducibility(
            ReproducibilityConfig(seed=resolved_seed, deterministic=cfg.reproducibility.deterministic),
            context=f"global_ranking_wf:{cfg.global_model.model_name}:h{horizon}",
        )

        h_parts: list[pd.DataFrame] = []
        h_ics: list[float] = []
        _last_model: Any = None
        _last_model_name: str = ""

        for split in wf_splits:
            split_seed = derive_seed(resolved_seed, split.split_index)
            apply_reproducibility(
                ReproducibilityConfig(seed=split_seed, deterministic=cfg.reproducibility.deterministic),
                context=f"global_ranking_wf:split_{split.split_index}:h{horizon}",
            )
            try:
                backend_model_name, model = _build_ranking_estimator(cfg, resolved_seed=split_seed)
            except ImportError:
                return {"status": "unavailable", "reason": f"{cfg.global_model.model_name}_not_installed"}

            train_df = split.train.dropna(subset=feature_columns + ["future_return"])
            val_df = split.val.dropna(subset=feature_columns + ["future_return"])
            if train_df.empty or val_df.empty:
                continue

            _sample_weights = None
            if "date" in train_df.columns:
                _train_dates = pd.to_datetime(train_df["date"])
                _days_diff = (_train_dates.max() - _train_dates).dt.days
                _sample_weights = np.exp(-_days_diff.values.astype(np.float64) / 365.0)

            _group = None
            if backend_model_name == "lightgbm":
                _group = train_df.groupby("date", sort=False).size().to_numpy(dtype=np.int32)

            X_train = train_df[feature_columns]
            y_train = train_df["future_return"].to_numpy(dtype=np.float64)
            if _group is not None and len(_group) > 0:
                model.fit(X_train, y_train, sample_weight=_sample_weights, group=_group)
            else:
                model.fit(X_train, y_train, sample_weight=_sample_weights)

            _last_model = model
            _last_model_name = backend_model_name

            X_val = val_df[feature_columns]
            y_val = val_df["future_return"].to_numpy(dtype=np.float64)
            pred_part = val_df[["symbol", "date"]].copy()
            pred_part[f"predicted_return{h_suffix}"] = model.predict(X_val).astype(np.float64)
            pred_part["actual_return"] = y_val

            ic = compute_ic_rank(pred_part[f"predicted_return{h_suffix}"].to_numpy(), y_val)
            if ic is not None:
                h_ics.append(ic)
            h_parts.append(pred_part)

            LOGGER.info(
                "global_ranking_wf horizon=%d split=%d/%d train_rows=%d val_rows=%d ic_rank=%.4f",
                horizon, split.split_index + 1, len(wf_splits),
                len(train_df), len(val_df), ic if ic is not None else float("nan"),
            )

        if h_parts:
            h_pred_df = pd.concat(h_parts, ignore_index=True)
            h_pred_df[f"global_rank{h_suffix}"] = h_pred_df[f"predicted_return{h_suffix}"].clip(0.0, 1.0).astype(np.float64)
            all_rank_dfs.append(h_pred_df[["symbol", "date", f"global_rank{h_suffix}"]])
            all_ic_means[horizon] = float(np.mean(h_ics)) if h_ics else float("nan")

            # Sauvegarder le modèle pour cet horizon
            if _last_model is not None:
                _model_dir = Path(cfg.artifacts_dir)
                _model_dir.mkdir(parents=True, exist_ok=True)
                try:
                    if _last_model_name == "lightgbm":
                        _mp = str(_model_dir / f"_global_ranking_model{h_suffix}.txt")
                        _last_model.booster_.save_model(_mp)
                        _saved_models[horizon] = _mp
                    elif _last_model_name == "catboost":
                        _mp = str(_model_dir / f"_global_ranking_model{h_suffix}.pkl")
                        _last_model.save_model(_mp)
                        _saved_models[horizon] = _mp
                except Exception as _exc:
                    LOGGER.warning("train_global_ranking_wf h=%d failed to save model: %s", horizon, _exc)

            LOGGER.info("global_ranking_wf horizon=%d done ic_mean=%.4f", horizon, all_ic_means[horizon])
        else:
            LOGGER.warning("global_ranking_wf horizon=%d no predictions", horizon)

    if not all_rank_dfs:
        return {"status": "skipped", "reason": "no_predictions"}

    # ── Fusionner tous les horizons ──
    global_rank_df = all_rank_dfs[0]
    for _df in all_rank_dfs[1:]:
        global_rank_df = global_rank_df.merge(_df, on=["symbol", "date"], how="outer")
    for h in _GLOBAL_RANKING_HORIZONS:
        _col = f"global_rank_{h}"
        if _col not in global_rank_df.columns:
            global_rank_df[_col] = 0.5
        global_rank_df[_col] = global_rank_df[_col].fillna(0.5).astype(np.float64)
    global_rank_df = global_rank_df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # IC moyen (moyenne des IC par horizon)
    _valid_ics = [v for v in all_ic_means.values() if not np.isnan(v)]
    ic_mean = float(np.mean(_valid_ics)) if _valid_ics else None
    ic_std = float(np.std(_valid_ics)) if len(_valid_ics) > 1 else None

    LOGGER.info(
        "train_global_ranking_wf done pred_rows=%d symbols=%d horizons=%s ic_by_h=%s ic_mean=%.4f",
        len(global_rank_df),
        global_rank_df["symbol"].nunique() if not global_rank_df.empty else 0,
        list(all_ic_means.keys()),
        {h: f"{v:.4f}" for h, v in all_ic_means.items()},
        ic_mean if ic_mean is not None else float("nan"),
    )

    # ── Sauvegarder les métadonnées features ──
    import json as _json_
    _model_dir = Path(cfg.artifacts_dir)
    _model_dir.mkdir(parents=True, exist_ok=True)
    _model_dir.joinpath("_global_ranking_features.json").write_text(
        _json_.dumps({
            "feature_columns": feature_columns,
            "model_name": cfg.global_model.model_name,
            "horizons": list(_GLOBAL_RANKING_HORIZONS),
            "saved_models": _saved_models,
        }),
        encoding="utf-8",
    )

    return {
        "status": "completed",
        "model_name": "global_ranking",
        "backend_model_name": cfg.global_model.model_name,
        "global_rank_df": global_rank_df if not global_rank_df.empty else None,
        "ic_rank_mean": ic_mean,
        "ic_rank_std": ic_std,
        "ic_by_horizon": all_ic_means,
        "feature_columns": feature_columns,
        "n_features": len(feature_columns),
        "horizons": list(_GLOBAL_RANKING_HORIZONS),
    }


# ────────────────────────────────────────────────────────────────────
# Inférence (appelé depuis predictor.py en étape 10)
# ────────────────────────────────────────────────────────────────────

def predict_global_rank(
    universe_df: pd.DataFrame,
    artifacts_dir: Path,
    *,
    benchmark_df: pd.DataFrame | None = None,
) -> pd.DataFrame | None:
    """Prédit les ``global_rank_{h}`` multi-horizons pour l'univers du jour.

    Charge les modèles sauvegardés par ``train_global_ranking_wf()`` et
    les applique sur l'univers courant.

    Returns:
        DataFrame [symbol, date, global_rank_3, global_rank_5, global_rank_10]
        ou None si indisponible.
    """
    _features_path = artifacts_dir / "_global_ranking_features.json"
    if not _features_path.exists():
        LOGGER.warning("predict_global_rank: features metadata not found at %s", _features_path)
        return None

    try:
        _meta = json.loads(_features_path.read_text(encoding="utf-8"))
        _feature_columns: list[str] = _meta["feature_columns"]
        _model_name: str = _meta.get("model_name", "lightgbm")
        _horizons: list[int] = _meta.get("horizons", [10])
    except Exception as exc:
        LOGGER.warning("predict_global_rank: failed to load features metadata: %s", exc)
        return None

    # ── Construire les features (communes à tous les horizons) ──
    from modelFactory.cross_sectional import build_cross_sectional_features, merge_cross_sectional_features
    cross_sectional_df, _cs_diag = build_cross_sectional_features(
        universe_df, benchmark_df=benchmark_df, min_universe_size=5,
    )

    frames: list[pd.DataFrame] = []
    symbols = sorted(universe_df["symbol"].unique())
    for sym in symbols:
        try:
            sym_bars = universe_df[universe_df["symbol"] == sym].copy()
            if sym_bars.empty or len(sym_bars) < 20:
                continue
            sym_bars = sym_bars.sort_values("date")
            sym_df = compute_features(sym_bars, benchmark_df=benchmark_df, feature_set="expert")
            if sym_df.empty:
                continue
            sym_cross = cross_sectional_df[cross_sectional_df["symbol"] == sym].copy() if not cross_sectional_df.empty else None
            sym_df = merge_cross_sectional_features(sym_df, sym_cross)
            last_row = sym_df.iloc[[-1]].copy()
            for col in _feature_columns:
                if col not in last_row.columns:
                    last_row[col] = 0.5 if col.endswith("_rank") or col.startswith("global_rank") else 0.0
            frames.append(last_row[["symbol", "date"] + _feature_columns])
        except Exception:
            continue

    if not frames:
        LOGGER.warning("predict_global_rank: no valid frames built")
        return None

    pred_df = pd.concat(frames, ignore_index=True)
    X = pred_df[_feature_columns]
    if X.shape[1] != len(_feature_columns):
        LOGGER.warning("predict_global_rank: feature mismatch expected=%d got=%d", len(_feature_columns), X.shape[1])
        return None

    # ── Prédire pour chaque horizon ──
    result = pred_df[["symbol", "date"]].copy()
    for horizon in _horizons:
        h_suffix = f"_{horizon}"
        _model_path = artifacts_dir / f"_global_ranking_model{h_suffix}.txt"
        if not _model_path.exists():
            _model_path = artifacts_dir / f"_global_ranking_model{h_suffix}.pkl"
        if not _model_path.exists():
            LOGGER.warning("predict_global_rank: model for horizon %d not found", horizon)
            result[f"global_rank{h_suffix}"] = 0.5
            continue
        try:
            lgb = _import_lightgbm()
            model = lgb.Booster(model_file=str(_model_path))
            result[f"global_rank{h_suffix}"] = model.predict(X.to_numpy(dtype=np.float64)).clip(0.0, 1.0).astype(np.float64)
        except Exception as exc:
            LOGGER.warning("predict_global_rank: prediction failed for h=%d: %s", horizon, exc)
            result[f"global_rank{h_suffix}"] = 0.5

    LOGGER.info("predict_global_rank: predicted %d symbols for horizons %s", len(result), _horizons)
    return result
