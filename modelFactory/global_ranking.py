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
from dataclasses import asdict, replace
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
    )
    if cfg.data.enable_cross_sectional_features and cross_sectional_df is not None:
        df = merge_cross_sectional_features(df, cross_sectional_df)

    # Target : rendement futur J+10 (continu, pas de classification)
    horizon = cfg.data.forecast_horizon
    close = df["close"].astype(float)
    df["future_return"] = close.shift(-horizon) / close - 1.0

    return df


def _get_ranking_feature_columns(cfg: TrainingConfig) -> list[str]:
    """Retourne TOUTES les features pour le Global Ranking Model.

    Contrairement à l'ancien Global Model (cross-sectionnel uniquement),
    le Ranking Model utilise toutes les features disponibles : OHLCV, expert,
    cross-sectional, macro, screener, sentiment, interactions, multi-horizons.
    """
    return get_feature_columns(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
        include_screener_scores=cfg.data.include_screener_scores,
        include_short_score=cfg.data.include_short_score_features,
        include_macro_vix=cfg.data.include_macro_vix_features,
        include_macro_vxn=cfg.data.include_macro_vxn_features,
        include_macro_vix3m=cfg.data.include_macro_vix3m_features,
        include_macro_move=cfg.data.include_macro_move_features,
        include_global_stacking=False,  # pas de stacking récursif
        include_fundamentals=cfg.data.include_fundamentals_features,
        include_factors=cfg.data.include_factors_features,
    )


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


def _compute_per_date_rank(pred_df: pd.DataFrame) -> pd.DataFrame:
    """Calcule le rang percentil (0..1) par date.

    global_rank = 0.0 → pire titre de l'univers ce jour-là
    global_rank = 1.0 → meilleur titre de l'univers ce jour-là
    """
    result = pred_df.copy()
    result["global_rank"] = result.groupby("date")["predicted_return"].rank(pct=True)
    result["global_rank"] = result["global_rank"].fillna(0.5).astype(np.float64)
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
        return "lightgbm", lgb.LGBMRegressor(
            objective="regression",
            max_depth=cfg.baseline.max_depth,
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

    effective_data_cfg = replace(
        cfg.data,
        enable_cross_sectional_features=(
            cfg.data.enable_cross_sectional_features
        ),
    )
    history_end_date = load_universe_latest_bar_date(
        engine, symbols, end_date=effective_data_cfg.training_end_date,
    )
    history_start_date = resolve_training_start_date(
        history_end_date, effective_data_cfg.training_start_date,
    )
    universe_df = load_universe_bars(
        engine, symbols, end_date=history_end_date, start_date=history_start_date,
    )
    if universe_df.empty:
        return {"status": "skipped", "reason": "empty_universe"}

    # ── Chargement données auxiliaires ──
    benchmark_df = None
    if effective_data_cfg.feature_set == "expert":
        benchmark_df = load_benchmark_bars(
            engine, effective_data_cfg.benchmark_symbol,
            end_date=history_end_date, start_date=history_start_date,
        )
    sentiment_df = None
    if effective_data_cfg.include_sentiment_features:
        sentiment_df = load_symbols_sentiment(
            engine, symbols, end_date=history_end_date, start_date=history_start_date,
        )
    selector_context_df = None
    if effective_data_cfg.include_screener_scores or effective_data_cfg.include_short_score_features:
        selector_context_df = load_symbols_selector_context(
            engine, symbols, end_date=history_end_date, start_date=history_start_date,
        )
    cross_sectional_df = None
    if effective_data_cfg.enable_cross_sectional_features:
        cross_sectional_df, _ = build_cross_sectional_features(
            universe_df, benchmark_df=benchmark_df,
            min_universe_size=effective_data_cfg.cross_sectional_min_universe,
        )

    # ── Préparation du DataFrame poolé ──
    feature_columns = _get_ranking_feature_columns(cfg)
    prepared_parts: list[pd.DataFrame] = []
    for symbol in symbols:
        bars_df = universe_df[universe_df["symbol"] == symbol].copy().sort_values("date").reset_index(drop=True)
        if len(bars_df) < effective_data_cfg.min_history_days:
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
            symbol=symbol,
        )
        if prepared.empty:
            continue
        prepared["symbol"] = symbol
        prepared_parts.append(prepared)

    if not prepared_parts:
        return {"status": "skipped", "reason": "no_prepared_rows"}

    global_df = pd.concat(prepared_parts, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
    global_df = global_df.dropna(subset=feature_columns + ["future_return"]).reset_index(drop=True)

    # ── Walk-Forward splits (adaptés pour données poolées multi-symboles) ──
    # Les paramètres walk_forward (val_size, min_train_size, step_size) sont
    # exprimés en JOURS pour le per-symbol. Pour le modèle global poolé, on
    # doit les multiplier par le nombre de symboles par jour pour obtenir des
    # splits de durée équivalente.
    _daily_symbols = int(round(global_df.groupby("date").size().median()))
    _daily_symbols = max(_daily_symbols, 1)
    LOGGER.info(
        "train_global_ranking_wf scaling WF params by daily_symbols=%d "
        "(raw: train=%d val=%d step=%d max_splits=%d)",
        _daily_symbols,
        cfg.walk_forward.min_train_size,
        cfg.walk_forward.val_size,
        cfg.walk_forward.step_size,
        cfg.walk_forward.max_splits,
    )
    wf_splits = generate_walk_forward_splits(
        global_df,
        min_train_size=cfg.walk_forward.min_train_size * _daily_symbols,
        val_size=cfg.walk_forward.val_size * _daily_symbols,
        test_size=cfg.walk_forward.test_size * _daily_symbols,
        step_size=cfg.walk_forward.step_size * _daily_symbols,
        max_splits=cfg.walk_forward.max_splits,
        forecast_horizon=horizon,
        date_column="date",
    )
    if not wf_splits:
        return {"status": "skipped", "reason": "no_valid_wf_split"}

    LOGGER.info(
        "train_global_ranking_wf start symbols=%d splits=%d feature_cols=%d horizon=%d",
        len(symbols), len(wf_splits), len(feature_columns), horizon,
    )

    resolved_seed = derive_seed(cfg.reproducibility.seed, "global_ranking_wf", cfg.global_model.model_name)
    apply_reproducibility(
        ReproducibilityConfig(seed=resolved_seed, deterministic=cfg.reproducibility.deterministic),
        context=f"global_ranking_wf:{cfg.global_model.model_name}",
    )

    global_rank_parts: list[pd.DataFrame] = []
    ic_ranks: list[float] = []
    _last_model: Any = None
    _last_model_name: str = ""

    for split in wf_splits:
        split_seed = derive_seed(resolved_seed, split.split_index)
        apply_reproducibility(
            ReproducibilityConfig(seed=split_seed, deterministic=cfg.reproducibility.deterministic),
            context=f"global_ranking_wf:split_{split.split_index}",
        )

        try:
            backend_model_name, model = _build_ranking_estimator(cfg, resolved_seed=split_seed)
        except ImportError:
            return {"status": "unavailable", "reason": f"{cfg.global_model.model_name}_not_installed"}

        train_df = split.train.dropna(subset=feature_columns + ["future_return"])
        val_df = split.val.dropna(subset=feature_columns + ["future_return"])

        if train_df.empty or val_df.empty:
            continue

        # ── Sample weighting par récence ──
        _sample_weights = None
        if "date" in train_df.columns:
            _train_dates = pd.to_datetime(train_df["date"])
            _days_diff = (_train_dates.max() - _train_dates).dt.days
            _sample_weights = np.exp(-_days_diff.values.astype(np.float64) / 365.0)

        # Fit régression
        X_train = train_df[feature_columns].to_numpy(dtype=np.float64)
        y_train = train_df["future_return"].to_numpy(dtype=np.float64)
        model.fit(X_train, y_train, sample_weight=_sample_weights)

        # ── Sauvegarder le modèle (dernier split = plus récent) ──
        _last_model = model
        _last_model_name = backend_model_name

        # Predict sur val
        X_val = val_df[feature_columns].to_numpy(dtype=np.float64)
        y_val = val_df["future_return"].to_numpy(dtype=np.float64)

        pred_part = val_df[["symbol", "date"]].copy()
        pred_part["predicted_return"] = model.predict(X_val).astype(np.float64)
        pred_part["actual_return"] = y_val

        # IC Rank
        ic = compute_ic_rank(pred_part["predicted_return"].to_numpy(), y_val)
        if ic is not None:
            ic_ranks.append(ic)

        global_rank_parts.append(pred_part)

        LOGGER.info(
            "global_ranking_wf split=%d/%d train_rows=%d val_rows=%d ic_rank=%.4f",
            split.split_index + 1, len(wf_splits),
            len(train_df), len(val_df), ic if ic is not None else float("nan"),
        )

    if not global_rank_parts:
        return {"status": "skipped", "reason": "no_predictions"}

    # ── Assemblage final ──
    global_pred_df = pd.concat(global_rank_parts, ignore_index=True)
    global_rank_df = _compute_per_date_rank(global_pred_df)
    global_rank_df = global_rank_df.sort_values(["symbol", "date"]).reset_index(drop=True)

    ic_mean = float(np.mean(ic_ranks)) if ic_ranks else None
    ic_std = float(np.std(ic_ranks)) if ic_ranks else None

    LOGGER.info(
        "train_global_ranking_wf done pred_rows=%d symbols=%d ic_mean=%.4f ic_std=%.4f",
        len(global_rank_df),
        global_rank_df["symbol"].nunique() if not global_rank_df.empty else 0,
        ic_mean if ic_mean is not None else float("nan"),
        ic_std if ic_std is not None else float("nan"),
    )

    import json as _json_

    # ── Persister le dernier modèle entraîné (pour inférence) ──
    _model_path: str | None = None
    if _last_model is not None:
        _model_dir = Path(cfg.artifacts_dir)
        _model_dir.mkdir(parents=True, exist_ok=True)
        try:
            if _last_model_name == "lightgbm":
                _model_path = str(_model_dir / "_global_ranking_model.txt")
                _last_model.booster_.save_model(_model_path)
            elif _last_model_name == "catboost":
                _model_path = str(_model_dir / "_global_ranking_model.pkl")
                _last_model.save_model(_model_path)
            _model_dir.joinpath("_global_ranking_features.json").write_text(
                _json_.dumps({"feature_columns": feature_columns, "model_name": _last_model_name}),
                encoding="utf-8",
            )
            LOGGER.info("train_global_ranking_wf model saved to %s", _model_path)
        except Exception as _exc:
            LOGGER.warning("train_global_ranking_wf failed to save model: %s", _exc)

    return {
        "status": "completed",
        "model_name": "global_ranking",
        "backend_model_name": cfg.global_model.model_name,
        "global_rank_df": global_rank_df if not global_rank_df.empty else None,
        "ic_rank_mean": ic_mean,
        "ic_rank_std": ic_std,
        "feature_columns": feature_columns,
        "n_features": len(feature_columns),
        "horizon": horizon,
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
    """Prédit le ``global_rank`` pour l'univers du jour.

    Charge le modèle sauvegardé par ``train_global_ranking_wf()`` et
    l'applique sur l'univers courant. Retourne un DataFrame avec les
    colonnes [symbol, date, global_rank], ou None si le modèle est
    indisponible.

    Args:
        universe_df: DataFrame universe avec barres OHLCV (doit avoir
            les colonnes 'symbol', 'date', 'open', 'high', 'low',
            'close', 'volume').
        artifacts_dir: Répertoire contenant ``_global_ranking_model.*``
            et ``_global_ranking_features.json``.
        benchmark_df: Barres du benchmark (SPY) pour les features expert.

    Returns:
        DataFrame [symbol, date, global_rank] ou None.
    """
    _features_path = artifacts_dir / "_global_ranking_features.json"
    if not _features_path.exists():
        LOGGER.warning("predict_global_rank: features metadata not found at %s", _features_path)
        return None

    try:
        _meta = json.loads(_features_path.read_text(encoding="utf-8"))
        _feature_columns: list[str] = _meta["feature_columns"]
        _model_name: str = _meta.get("model_name", "lightgbm")
    except Exception as exc:
        LOGGER.warning("predict_global_rank: failed to load features metadata: %s", exc)
        return None

    # ── Charger le modèle ──
    if _model_name == "lightgbm":
        _model_path = artifacts_dir / "_global_ranking_model.txt"
        if not _model_path.exists():
            LOGGER.warning("predict_global_rank: model not found at %s", _model_path)
            return None
        try:
            lgb = _import_lightgbm()
            model = lgb.Booster(model_file=str(_model_path))
        except Exception as exc:
            LOGGER.warning("predict_global_rank: failed to load LightGBM model: %s", exc)
            return None
    elif _model_name == "catboost":
        _model_path = artifacts_dir / "_global_ranking_model.pkl"
        if not _model_path.exists():
            LOGGER.warning("predict_global_rank: model not found at %s", _model_path)
            return None
        try:
            CatBoost = _import_catboost()
            model = CatBoost.CatBoostRegressor()
            model.load_model(str(_model_path))
        except Exception as exc:
            LOGGER.warning("predict_global_rank: failed to load CatBoost model: %s", exc)
            return None
    else:
        LOGGER.warning("predict_global_rank: unknown model_name=%s", _model_name)
        return None

    # ── Préparer les features ──
    from modelFactory.cross_sectional import CROSS_SECTIONAL_FEATURE_COLUMNS
    # Filtrer pour ne garder que les colonnes cross-sectional + common
    # qui sont disponibles (le modèle global n'utilise que celles-ci)

    # Construire les features pour chaque symbole
    frames: list[pd.DataFrame] = []
    symbols = sorted(universe_df["symbol"].unique())
    for sym in symbols:
        try:
            sym_bars = universe_df[universe_df["symbol"] == sym].copy()
            if sym_bars.empty or len(sym_bars) < 20:
                continue
            sym_bars = sym_bars.sort_values("date")
            # Features OHLCV de base
            from modelFactory.features import compute_features
            sym_df = compute_features(
                sym_bars,
                benchmark_df=benchmark_df,
                feature_set="expert",
            )
            # Merge cross-sectional
            from modelFactory.cross_sectional import merge_cross_sectional_features
            cs_df = universe_df[["symbol", "date"]].copy()
            # On ne peut pas construire de cross-sectional features ici
            # sans l'univers complet — on les skip pour l'inférence
            # et on garde les features locales + macro

            # Ne garder que les colonnes présentes
            available = [c for c in _feature_columns if c in sym_df.columns]
            if not available:
                continue
            last_row = sym_df.iloc[[-1]].copy()
            frames.append(last_row[["symbol", "date"] + available])
        except Exception:
            continue

    if not frames:
        LOGGER.warning("predict_global_rank: no valid frames built")
        return None

    pred_df = pd.concat(frames, ignore_index=True)

    # ── Prédire ──
    X = pred_df[[c for c in _feature_columns if c in pred_df.columns]].to_numpy(dtype=np.float64)
    if X.shape[1] == 0:
        LOGGER.warning("predict_global_rank: no matching feature columns")
        return None

    try:
        pred_df["predicted_return"] = model.predict(X).astype(np.float64)
    except Exception as exc:
        LOGGER.warning("predict_global_rank: prediction failed: %s", exc)
        return None

    # ── Calculer le rang percentile par date ──
    result = _compute_per_date_rank(pred_df)
    LOGGER.info(
        "predict_global_rank: predicted %d symbols, global_rank range [%.3f, %.3f]",
        len(result),
        result["global_rank"].min() if not result.empty else 0,
        result["global_rank"].max() if not result.empty else 0,
    )
    return result[["symbol", "date", "global_rank"]]
