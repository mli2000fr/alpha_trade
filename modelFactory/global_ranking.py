"""modelFactory/global_ranking.py — Global Ranking Model (Sprint 2026-07-25).

Classement cross-sectionnel multi-horizons avec LightGBM LambdaRank.
Remplace l'ancien classifieur ternaire global_model.py pour le stacking.

Contrat PIT :
- Entraîné en walk-forward (mêmes splits que le per-symbol).
- Target : rendement excédentaire vs SPY → vingtile de performance (label 0..19).
- LambdaRank (LightGBM) : group=date, objective=lambdarank, label_gain=0..9.
- CatBoost (fallback) : régression RMSE sur le rang continu [0, 1].
- Sortie : global_rank_{3,5,10}[symbol, date] ∈ [0, 1] (percentile dans l'univers).
- Métrique : IC Rank (Spearman correlation), pas de F1.

Architecture :
- Toutes les features (OHLCV, expert, cross-sectional, macro, screener, sentiment),
  sauf les features macro-globales (SPY/VIX/MOVE/régime) blacklistées du ranking.
- LightGBM LambdaRank (principal) ou CatBoost RMSE (fallback).
- Walk-forward identique au per-symbol pour garantir le PIT.
- Multi-horizons J+3, J+5, J+10 → 3 modèles indépendants.
"""
from __future__ import annotations

import gc
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.config import ReproducibilityConfig, TrainingConfig
from modelFactory.cross_sectional import (
    SECTOR_NEUTRAL_FEATURE_COLUMNS,
    SECTOR_NEUTRAL_SOURCE_FEATURES,
    SECTOR_ZSCORE_FEATURE_COLUMNS,
    SECTOR_ZSCORE_SOURCE_FEATURES,
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
from modelFactory.dataset import generate_walk_forward_splits_by_dates
from modelFactory.features import (
    build_feature_contract,
    compute_features,
    get_feature_columns,
)
from modelFactory.features import fingerprint as compute_feature_fingerprint
from modelFactory.reproducibility import apply_reproducibility, derive_seed

LOGGER = logging.getLogger(__name__)

# Horizons pour le ranking multi-horizons (stacking Phase 2)
# H10 : momentum moyen-terme, avec fondamentaux, avec vol scaling.
# H15 : momentum long-terme, avec fondamentaux, avec vol scaling.
# H20 : momentum très long-terme, avec fondamentaux, avec vol scaling.
# Note 2026-08-01 : H=3 et H=5 réactivés pour test short-term.
# Note 2026-07-29 : vol scaling actif pour tous les horizons ≥ 5j.
_GLOBAL_RANKING_HORIZONS: tuple[int, ...] = (3, 5, 10, 15, 20)
# Smoothing : uniquement sur les horizons fiables (H3/H5 trop bruités)
_SMOOTHING_HORIZONS: tuple[int, ...] = (10, 15, 20)

# ── Sector group mapping (Sprint 2026-08-01) ──
# GICS sectors → Cyclical / Defensive
_CYCLICAL_KEYWORDS: tuple[str, ...] = (
    "energy", "materials", "industri", "consumer discretionary",
    "consumer cycl", "financial", "real estate", "technology", "communication",
)
_DEFENSIVE_KEYWORDS: tuple[str, ...] = (
    "consumer stapl", "consumer defen", "health", "utilit",
)

def _classify_sector_group(sector: str) -> str:
    """Classifie un nom de secteur GICS en 'cyclical' ou 'defensive'."""
    _s = sector.lower().strip()
    for _kw in _DEFENSIVE_KEYWORDS:
        if _kw in _s:
            return "defensive"
    for _kw in _CYCLICAL_KEYWORDS:
        if _kw in _s:
            return "cyclical"
    return "other"

# Features "brutes" à normaliser en rang cross-sectionnel par date.
# Ces features varient par symbole mais leurs seuils absolus changent avec
# le régime de marché (volatilité, secteur, capitalisation). Le rank pct
# intra-date les rend comparables dans le temps et entre symboles.
_XS_RANK_SOURCE_FEATURES: list[str] = [
    # Momentum multi-horizons
    "momentum_3", "momentum_5", "momentum_10", "momentum_20", "momentum_60",
    "momentum_120", "momentum_250",
    # Volatilité
    "rolling_volatility_5", "rolling_volatility_10", "rolling_volatility_20",
    "rolling_volatility_60",
    # RSI
    "rsi_2", "rsi_3", "rsi_5", "rsi_14", "rsi_21",
    # Distance aux moyennes mobiles
    "sma10_distance", "sma20_distance", "sma50_distance",
    "sma100_distance", "sma200_distance", "sma250_distance",
    "ema20_distance", "ema50_distance",
    "dist_to_sma_5d",
    # Mean-reversion court terme (Mid Caps, Sprint 2026-08-01)
    "zscore_close_vs_ma10",
    # Rendements et volume
    "daily_return", "log_return", "volume_ratio_5", "volume_ratio_20",
    "volume_zscore_5d",
    "rolling_mean_return_5", "rolling_mean_return_20",
    # Range / gap / vwap
    "intraday_range", "overnight_gap", "close_to_vwap",
    "atr_14_norm", "range_position_20", "vol_ratio_20_60",
    # Force relative
    "relative_strength_20", "relative_strength_60",
    # ── Dynamique temporelle (Niveau 3) ──
    "accel_3_5", "decay_5_10", "rsi_slope",
    "vol_expansion", "meanrev_signal", "gap_fade",
]

def _xs_rank_column_name(source_col: str) -> str:
    return f"{source_col}_xs_rank"


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _compute_sector_neutral_inplace(
    df: pd.DataFrame,
    feature_columns: list[str],
    engine: Any,
) -> int:
    """Calcule les features sector-neutral dans ``df`` (modifié sur place).

    Pour chaque feature source de ``SECTOR_NEUTRAL_SOURCE_FEATURES``
    présente à la fois dans ``df`` et ``feature_columns``, soustrait la
    médiane du secteur à chaque date.

    Returns:
        Nombre de features sector-neutral calculées.
    """
    try:
        from modelFactory.cross_sectional import SECTOR_NEUTRAL_SOURCE_FEATURES, _load_sector_mapping
        _sector_map = _load_sector_mapping(engine)
    except Exception:
        LOGGER.warning("_compute_sector_neutral_inplace: failed to load sector map")
        return 0

    if not _sector_map:
        LOGGER.warning("_compute_sector_neutral_inplace: empty sector_map")
        return 0

    _sn_sources = [c for c in SECTOR_NEUTRAL_SOURCE_FEATURES if c in df.columns]
    if not _sn_sources:
        return 0

    df["_sector"] = df["symbol"].astype(str).str.upper().map(_sector_map)
    _valid = df["_sector"].notna()
    _sn_count = 0

    for _src in _sn_sources:
        _target = f"{_src}_sector_neutral"
        if _target not in feature_columns:
            continue
        try:
            _sector_med = (
                df.loc[_valid]
                .groupby(["date", "_sector"])[_src]
                .transform("median")
            )
            _neutral = df[_src].copy()
            _neutral.loc[_valid] = df.loc[_valid, _src] - _sector_med
            _neutral.loc[~_valid] = 0.0
            df[_target] = _neutral.fillna(0.0).astype(float)
            _sn_count += 1
        except Exception:
            df[_target] = 0.0

    # ── Z-score sectoriel pour fondamentales (Sprint 2026-08-02) ──
    from modelFactory.cross_sectional import SECTOR_ZSCORE_SOURCE_FEATURES, SECTOR_ZSCORE_FEATURE_COLUMNS, _sector_zscore_column_name
    _zs_sources = [c for c in SECTOR_ZSCORE_SOURCE_FEATURES if c in df.columns]
    _zs_targets = [_sector_zscore_column_name(c) for c in _zs_sources if _sector_zscore_column_name(c) in feature_columns]
    _zs_count = 0
    for _src in _zs_sources:
        _target = _sector_zscore_column_name(_src)
        if _target not in feature_columns:
            continue
        try:
            _grp = df.loc[_valid].groupby(["date", "_sector"])[_src]
            _sector_med = _grp.transform("median")
            # MAD = median absolute deviation (robuste aux outliers)
            _dev = (df.loc[_valid, _src] - _sector_med).abs()
            _sector_mad = (
                _dev.groupby([df.loc[_valid, "date"], df.loc[_valid, "_sector"]])
                .transform("median")
                .clip(lower=1e-8)
            )
            _zscore = df[_src].copy()
            _zscore.loc[_valid] = (df.loc[_valid, _src] - _sector_med) / _sector_mad
            _zscore.loc[~_valid] = 0.0
            df[_target] = _zscore.fillna(0.0).clip(-5.0, 5.0).astype(float)
            _zs_count += 1
        except Exception:
            df[_target] = 0.0
    if _zs_count > 0:
        LOGGER.info(
            "_compute_sector_neutral_inplace: %d z-score fundamentals computed",
            _zs_count,
        )

    df.drop(columns=["_sector"], inplace=True)

    if _sn_count > 0:
        LOGGER.info(
            "_compute_sector_neutral_inplace: %d features computed "
            "(%d symbols mapped to %d sectors)",
            _sn_count, len(_sector_map), len(set(_sector_map.values())),
        )
    return _sn_count


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
    """Prépare le DataFrame pour un symbole avec toutes les features (sans target).

    La target est calculée en une seule fois après concaténation de tous les
    symboles, via un groupby(\"symbol\")[\"close\"].shift(-horizon) pour garantir
    que le shift est bien intra-symbole.
    """
    df = compute_features(
        bars_df,
        sentiment_df=sentiment_df,
        include_sentiment=False,  # sentiment → per-symbol uniquement
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
        include_score_components=cfg.data.include_score_components,
    )
    if cfg.data.enable_cross_sectional_features and cross_sectional_df is not None:
        df = merge_cross_sectional_features(df, cross_sectional_df)

    return df


def _get_ranking_feature_columns(cfg: TrainingConfig) -> list[str]:
    """Retourne les features pour le Global Ranking Model.

    Exclut les features macro-globales (identiques pour tous les symboles
    à une date donnée) car elles ne peuvent pas discriminer le classement
    cross-sectionnel. Ces features restent disponibles pour les modèles
    per-symbol (Phase 2) qui en ont besoin pour le contexte de régime.
    """
    all_cols = get_feature_columns(
        include_sentiment=False,  # sentiment → per-symbol uniquement (sparse, noyé dans 177 features)
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
        include_score_components=cfg.data.include_score_components,
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
        # Régime de marché SPY — dé-blacklistés (Sprint 2026-08-01 P0)
        # Diagnostic : momentum_60 a un IC de -0.05 en bear, ~0 en bull.
        # Les arbres peuvent apprendre des splits conditionnels :
        #   « si regime_risk_off → sous-arbre défensif (vol, value) »
        #   « si regime_bull_market → sous-arbre momentum »
        # Même valeur ∀ symboles mais interaction non-linéaire via les arbres.
        "market_return_20", "market_volatility_20",
        # Liquidité — trop dominante, écrase les signaux d'alpha
        "dollar_volume_20_rank",
        # Volatilité 120j — béquille qui domine, empêche l'apprentissage du momentum
        "rolling_volatility_120", "rolling_volatility_120_zscore", "rolling_volatility_120_xs_rank",
        # Secteur agrégé — redondant avec les features cross-sectionnelles + sector_neutral
        "sector_ret_20", "sector_ret_60", "sector_vol_20",
        "sector_relative_strength_20", "sector_dollar_volume_20", "sector_symbol_count",
        "stock_vs_sector_ret_20", "stock_vs_sector_ret_60",
        # Métadonnées
        "is_filled",
        # ── Chirurgie 2026-07-28 ──
        # *_sector_neutral de volatilité → dominent H5 (imp 58.7 & 48.5),
        # écrasent le signal momentum et font chuter l'IC de 0.0081 à 0.0039.
        "rolling_volatility_20_sector_neutral",
        "rolling_volatility_60_sector_neutral",
        # CAPM → importance 0.0 sur tous les horizons (batch 2026-07-28).
        "beta_252", "alpha_252", "r_squared_252",
        # ── Chirurgie 2026-07-29 ──
        # Estimations analystes indisponibles via SEC EDGAR → importance 0.0,
        # polluent le set de features sans apporter de signal.
        "fund_forward_pe", "fund_peg_ratio",
        "fund_eps_estimate_current", "fund_eps_estimate_next",
        "fund_estimate_revision",
        # ── Chirurgie 2026-08-01 v2 : fondamentales brutes redondantes ──
        # Les versions sector-neutral (_sector_neutral) sont conservées car
        # elles normalisent par secteur (ex: PE=15 n'a pas le même sens
        # dans la Tech que dans l'Énergie). Les versions brutes font doublon.
        "fund_pe_ratio", "fund_pb_ratio", "fund_ev_to_ebitda",
        "fund_roa", "fund_roe",
        # ── Chirurgie 2026-08-01 : poids morts Mid Caps ──
        # Batch 2026-07-31 sur 939 puis 480 Mid Caps (500M–20B$) :
        # importance < 3.0 sur H=5,10,15,20 → bruit pur, aucun signal discriminant.
        "log_return", "log_return_xs_rank",
        "daily_return", "daily_return_xs_rank",
        "daily_return_times_volume_ratio_20",
        "close_to_vwap_xs_rank",
        "volume_zscore_5d", "volume_zscore_5d_xs_rank",
        "accel_3_5", "accel_3_5_xs_rank",
    }
    # Note 2026-07-28 : les *_sector_neutral de momentum, RSI, SMA distance
    # et volume_ratio sont CONSERVÉS (imp 2.8–28.6 en H3, 4.4–28.6 en H5).
    # Seules les versions volatilité + CAPM sont re-blacklistées.
    # Le calcul sector-neutral dans train_global_ranking_wf() reste actif
    # pour que les features conservées aient des valeurs réelles ≠ 0.0.
    cols = [c for c in all_cols if c not in _macro_blacklist]
    # Ajouter les rangs cross-sectionnels des features brutes
    for _src in _XS_RANK_SOURCE_FEATURES:
        _xsc = _xs_rank_column_name(_src)
        if _src in cols and _xsc not in cols:
            cols.append(_xsc)
    return cols


def compute_ic_rank(predicted: np.ndarray, actual: np.ndarray) -> float | None:
    """Spearman rank correlation (Information Coefficient).

    Métrique standard en finance quantitative.
    - IC > 0.05 : bon modèle de ranking
    - IC > 0.10 : excellent

    Returns None si moins de 10 observations.
    """
    if len(predicted) < 10:
        return None
    # Éviter le ConstantInputWarning de scipy : si l'une des séries est constante,
    # la corrélation de Spearman n'est pas définie.
    if np.std(predicted) < 1e-12 or np.std(actual) < 1e-12:
        return None
    try:
        from scipy.stats import spearmanr
        corr, _ = spearmanr(predicted, actual)
        return float(corr)
    except Exception:
        return None


def compute_cross_sectional_ic(
    pred_df: pd.DataFrame,
    *,
    score_col: str = "proba_long",
    return_col: str = "future_return",
    date_col: str = "date",
    vol_col: str | None = "rolling_volatility_20",
    min_symbols_per_date: int = 10,
) -> dict[str, Any]:
    """Calcule l'IC cross-sectionnel (Spearman rank) par date.

    Cette fonction permet de mesurer l'IC du per-symbol avec la **même**
    méthode que le Global Ranking, pour une comparaison directe.

    Pour chaque date, les symboles sont classés par ``score_col`` et
    corrélés avec ``return_col``.  Si ``vol_col`` est fourni, le
    rendement est divisé par la volatilité (vol scaling), comme pour
    les horizons ≥ 5j du Global Ranking.

    Args:
        pred_df: DataFrame avec au minimum [symbol, date, score, return].
        score_col: Colonne de score à évaluer (défaut: proba_long).
        return_col: Colonne de rendement forward réel.
        vol_col: Colonne de volatilité pour vol scaling (None = pas de scaling).
        min_symbols_per_date: Nombre minimum de symboles pour calculer l'IC.

    Returns:
        dict avec ``ic_mean``, ``ic_std``, ``n_dates``, ``ic_by_date``.
    """
    if pred_df.empty or score_col not in pred_df.columns or return_col not in pred_df.columns:
        LOGGER.warning("compute_cross_sectional_ic: missing required columns")
        return {"ic_mean": None, "ic_std": None, "n_dates": 0, "ic_by_date": {}}

    _df = pred_df.dropna(subset=[score_col, return_col]).copy()
    if vol_col and vol_col in _df.columns:
        _vol = _df[vol_col].clip(lower=0.001)
        _df["_target"] = _df[return_col] / _vol
    else:
        _df["_target"] = _df[return_col]

    _ics: dict[str, float] = {}
    for _date, _group in _df.groupby(date_col):
        if len(_group) < min_symbols_per_date:
            continue
        _ic = compute_ic_rank(_group[score_col].to_numpy(), _group["_target"].to_numpy())
        if _ic is not None:
            _ics[str(_date)] = _ic

    if not _ics:
        return {"ic_mean": None, "ic_std": None, "n_dates": 0, "ic_by_date": {}}

    _values = list(_ics.values())
    return {
        "ic_mean": float(np.mean(_values)),
        "ic_std": float(np.std(_values)) if len(_values) > 1 else 0.0,
        "n_dates": len(_values),
        "ic_by_date": _ics,
    }


def _compute_mean_importance(
    split_importances: list[dict[str, float]],
    feature_names: list[str],
) -> dict[str, float]:
    """Moyenne les feature importance sur les splits WF, triée décroissant."""
    if not split_importances:
        return {}
    _mean: dict[str, float] = {}
    for _fn in feature_names:
        _vals = [_imp.get(_fn, 0.0) for _imp in split_importances if _fn in _imp]
        if _vals:
            _mean[_fn] = float(np.mean(_vals))
    return dict(sorted(_mean.items(), key=lambda kv: kv[1], reverse=True))


def _compute_decile_spread(
    pred_df: pd.DataFrame,
    *,
    score_col: str = "predicted_score",
    return_col: str = "actual_return",
    n_deciles: int = 10,
) -> dict[str, float]:
    """Calcule le rendement moyen par décile et le spread Top−Bottom.

    Pour chaque date, les symboles sont classés en ``n_deciles`` selon
    ``score_col``. Le rendement moyen du décile est la moyenne de
    ``return_col`` (le vrai rendement futur percentile-ranké).

    Returns
    -------
    dict avec :
    - ``decile_spread`` : rendement moyen (Top − Bottom)
    - ``top_decile_return`` : rendement moyen du meilleur décile
    - ``bottom_decile_return`` : rendement moyen du pire décile
    - ``decile_returns`` : dict décile → rendement moyen (pour monotonicité)
    """
    if pred_df.empty or score_col not in pred_df.columns or return_col not in pred_df.columns:
        return {"decile_spread": 0.0, "top_decile_return": 0.0, "bottom_decile_return": 0.0, "decile_returns": {}}
    try:
        _df = pred_df.dropna(subset=[score_col, return_col])
        if _df.empty:
            return {"decile_spread": 0.0, "top_decile_return": 0.0, "bottom_decile_return": 0.0, "decile_returns": {}}
        # Classer en déciles par date
        _df["_decile"] = (
            _df.groupby("date")[score_col]
            .transform(lambda x: pd.qcut(x, n_deciles, labels=False, duplicates="drop"))
        )
        _decile_returns = _df.groupby("_decile")[return_col].mean().to_dict()
        _top = _decile_returns.get(n_deciles - 1, 0.0)
        _bottom = _decile_returns.get(0, 0.0)
        return {
            "decile_spread": float(_top - _bottom),
            "top_decile_return": float(_top),
            "bottom_decile_return": float(_bottom),
            "decile_returns": {int(k): float(v) for k, v in _decile_returns.items()},
        }
    except Exception:
        return {"decile_spread": 0.0, "top_decile_return": 0.0, "bottom_decile_return": 0.0, "decile_returns": {}}


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
    return _build_ranking_estimators(cfg, resolved_seed=resolved_seed, model_names=None)[0]


def _build_ranking_estimators(
    cfg: TrainingConfig,
    *,
    resolved_seed: int,
    model_names: list[str] | None = None,
) -> list[tuple[str, Any]]:
    """Construit un ou plusieurs estimateurs de ranking.

    Args:
        cfg: Configuration d'entraînement.
        resolved_seed: Graine résolue pour la reproductibilité.
        model_names: Liste de noms de modèles à construire.
            None → [cfg.global_model.model_name] (mode single).
            ["lightgbm", "catboost"] → les deux (mode champion).

    Returns:
        Liste de (model_name, estimator). Ordre déterministe.
    """
    if model_names is None:
        model_names = [cfg.global_model.model_name]

    estimators: list[tuple[str, Any]] = []
    for model_name in model_names:
        _name = model_name
        _rebuilt = False
        if _name == "catboost":
            try:
                CatBoostRegressor = _import_catboost()
            except ImportError:
                LOGGER.warning("CatBoost indisponible pour global ranking → fallback LightGBM")
                _name = "lightgbm"
                _rebuilt = True

        if _name == "lightgbm":
            lgb_mod = _import_lightgbm()
            estimators.append(("lightgbm", lgb_mod.LGBMRanker(
                objective="lambdarank",
                label_gain=list(range(10)),
                max_depth=cfg.global_model.ranking_max_depth,
                num_leaves=cfg.global_model.ranking_num_leaves,
                n_estimators=cfg.baseline.n_estimators,
                learning_rate=cfg.baseline.learning_rate,
                random_state=resolved_seed,
                verbosity=-1,
                reg_alpha=cfg.baseline.lgbm_reg_alpha,
                reg_lambda=cfg.baseline.lgbm_reg_lambda,
                min_child_samples=cfg.baseline.lgbm_min_child_samples,
                subsample=cfg.baseline.lgbm_subsample,
                colsample_bytree=cfg.baseline.lgbm_colsample_bytree,
            )))
            if _rebuilt:
                # CatBoost fallback → ne pas ajouter une deuxième fois lightgbm
                continue
        else:
            CatBoostRegressor = _import_catboost()
            _cb_depth = cfg.global_model.ranking_max_depth
            _cb_iterations = cfg.global_model.ranking_catboost_iterations
            _cb_lr = cfg.global_model.ranking_catboost_learning_rate
            estimators.append(("catboost", CatBoostRegressor(
                depth=_cb_depth,
                iterations=_cb_iterations,
                learning_rate=_cb_lr,
                random_seed=resolved_seed,
                loss_function="RMSE",
                verbose=False,
                l2_leaf_reg=cfg.baseline.catboost_l2_leaf_reg,
                border_count=cfg.baseline.catboost_border_count,
                random_strength=cfg.baseline.catboost_random_strength,
                bagging_temperature=cfg.baseline.catboost_bagging_temperature,
                od_type=cfg.baseline.catboost_od_type,
                od_wait=cfg.baseline.catboost_od_wait,
            )))
    return estimators


def _compute_ranking_targets(
    df: pd.DataFrame,
    *,
    horizons: tuple[int, ...],
    smoothing_horizons: tuple[int, ...],
    factor_cols: list[str],
    sector_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Compute ranking targets on an isolated DataFrame (PIT-étanche).

    Le ``shift(-horizon)`` est appliqué sur le DataFrame fourni **sans**
    accès aux données des folds voisins.  Les NaN naturels en queue de
    fold (shift au-delà des données disponibles) sont éliminés par le
    ``dropna`` appelant.

    La target pipeline complète est appliquée :
    1. future_return → vol scaling (H5+) → winsorize 1%/99% → rank
    2. Smoothing 50% h + 50% avg(smoothing_horizons) [si ≥2 horizons]
    3. Sector-neutral (médiane secteur par date)
    4. Factor-neutral (OLS résiduel sur size+value+momentum)

    Returns:
        ``df`` avec les colonnes ``future_return_{h}`` et ``label_{h}``
        pour chaque horizon, plus modifications in-place.
    """
    df = df.copy()

    # ── Étape 1 : future_return + vol scaling + winsorize + rank + label ──
    for horizon in horizons:
        h_suffix = f"_{horizon}"
        _fwd_close = df.groupby("symbol")["close"].shift(-horizon)
        df[f"future_return{h_suffix}"] = (_fwd_close / df["close"] - 1.0)
        if horizon >= 5:
            _vol20 = df["rolling_volatility_20"].clip(lower=0.001)
            df[f"future_return{h_suffix}"] = (
                df[f"future_return{h_suffix}"] / _vol20
            ).astype(float)
        # Winsorize intra-date 1%/99%
        df[f"future_return{h_suffix}"] = (
            df.groupby("date")[f"future_return{h_suffix}"]
            .transform(lambda x: x.clip(lower=x.quantile(0.01), upper=x.quantile(0.99)))
        )
        # Percentile rank intra-date → [0, 1]
        df[f"future_return{h_suffix}"] = (
            df.groupby("date")[f"future_return{h_suffix}"]
            .rank(pct=True)
            .astype(np.float64)
        )
        # Labels entiers 0..9 (déciles)
        df[f"label{h_suffix}"] = (
            np.floor(df[f"future_return{h_suffix}"] * 10)
            .clip(0, 9)
            .astype("Int32")
        )

    # ── Étape 2 : Smoothing multi-horizons ──
    if len(smoothing_horizons) >= 2:
        _all_ret_cols = [f"future_return_{h}" for h in smoothing_horizons]
        # mean() skipne les NaN → un horizon manquant ne casse pas le blend
        _avg = df[_all_ret_cols].mean(axis=1, skipna=True)
        for horizon in smoothing_horizons:
            h_suffix = f"_{horizon}"
            _col = f"future_return{h_suffix}"
            # Blend 50% horizon + 50% moyenne des autres horizons
            _blend = 0.5 * df[_col].fillna(_avg) + 0.5 * _avg
            df[_col] = _blend.astype(float)
            df[_col] = (
                df.groupby("date")[_col].rank(pct=True).astype(np.float64)
            )
            df[f"label{h_suffix}"] = (
                np.floor(df[_col] * 10).clip(0, 9).astype("Int32")
            )

    # ── Étape 3 : Sector-neutral ──
    if sector_map:
        df["_sector"] = df["symbol"].astype(str).str.upper().map(sector_map)
        _valid_sec = df["_sector"].notna()
        for horizon in horizons:
            h_suffix = f"_{horizon}"
            _col = f"future_return{h_suffix}"
            if _col not in df.columns:
                continue
            try:
                _sector_med = (
                    df.loc[_valid_sec]
                    .groupby(["date", "_sector"])[_col]
                    .transform("median")
                )
                _neutral = df[_col].copy()
                _neutral.loc[_valid_sec] = df.loc[_valid_sec, _col] - _sector_med
                _neutral.loc[~_valid_sec] = df.loc[~_valid_sec, _col]
                df[_col] = _neutral.astype(float)
                df[_col] = (
                    df.groupby("date")[_col].rank(pct=True).astype(np.float64)
                )
                df[f"label{h_suffix}"] = (
                    np.floor(df[_col] * 10).clip(0, 9).astype("Int32")
                )
            except Exception:
                pass
        df.drop(columns=["_sector"], inplace=True)

    # ── Étape 4 : Factor-neutral (OLS résiduel intra-date) ──
    if len(factor_cols) >= 2:
        for horizon in horizons:
            h_suffix = f"_{horizon}"
            _col = f"future_return{h_suffix}"
            if _col not in df.columns:
                continue
            _valid = df.dropna(subset=[_col] + factor_cols)
            if _valid.empty:
                continue
            _residuals = pd.Series(0.0, index=df.index, dtype=float)
            try:
                for _date, _group in _valid.groupby("date"):
                    if len(_group) < 20:
                        _residuals.loc[_group.index] = _group[_col]
                        continue
                    X = _group[factor_cols].to_numpy(dtype=np.float64)
                    X = np.column_stack([np.ones(len(X)), X])
                    y = _group[_col].to_numpy(dtype=np.float64)
                    try:
                        beta = np.linalg.lstsq(X, y, rcond=None)[0]
                        _residuals.loc[_group.index] = y - X @ beta
                    except np.linalg.LinAlgError:
                        _residuals.loc[_group.index] = y
            except Exception:
                _residuals = df[_col]
            df[_col] = _residuals.astype(float)
            df[_col] = (
                df.groupby("date")[_col].rank(pct=True).astype(np.float64)
            )
            df[f"label{h_suffix}"] = (
                np.floor(df[_col] * 10).clip(0, 9).astype("Int32")
            )

    return df


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

    # ── Limiter le nombre de symboles (mémoire + pertinence ranking) ──
    _max_sym = cfg.data.global_ranking_max_symbols
    _stratified = getattr(cfg.data, "global_ranking_selection_stratified", False)
    if _max_sym > 0 and len(symbols) > _max_sym:
        _vol_rank = (
            universe_df.groupby("symbol")["volume"].mean()
            .sort_values(ascending=False)
        )
        if _stratified and len(_vol_rank) >= 10:
            # Stratifié par déciles de volume
            _per_decile = max(1, _max_sym // 10)
            _vol_df = _vol_rank.reset_index()
            _vol_df.columns = ["symbol", "avg_vol"]
            _vol_df["decile"] = pd.qcut(_vol_df["avg_vol"], q=10, labels=False)
            _selected: list[str] = []
            for _d in range(10):
                _decile_syms = _vol_df[_vol_df["decile"] == _d]["symbol"].tolist()
                _selected.extend(_decile_syms[:_per_decile])
            symbols = _selected[:_max_sym]
            LOGGER.info(
                "global_ranking_wf capped symbols %d → %d (stratified deciles)",
                len(_vol_rank), len(symbols),
            )
        else:
            symbols = _vol_rank.head(_max_sym).index.tolist()
            LOGGER.info(
                "global_ranking_wf capped symbols %d → %d (top by avg volume)",
                len(_vol_rank), len(symbols),
            )

    # ── Sector group filter (Sprint 2026-08-01) ──
    _sector_group = getattr(cfg.global_model, 'ranking_sector_group', 'all') or 'all'
    if _sector_group != 'all':
        from modelFactory.cross_sectional import _load_sector_mapping as _load_smap
        _smap = _load_smap(engine)
        _before = len(symbols)
        _filtered = []
        for _s in symbols:
            _sec = _smap.get(_s.upper(), "") if _smap else ""
            if _classify_sector_group(_sec) == _sector_group:
                _filtered.append(_s)
        symbols = _filtered
        LOGGER.info(
            "global_ranking_wf sector_group=%s filtered %d → %d symbols",
            _sector_group, _before, len(symbols),
        )
        if not symbols:
            return {"status": "skipped", "reason": f"no_symbols_in_sector_group={_sector_group}"}

    # ── Chargement données auxiliaires ──
    benchmark_df = None
    if cfg.data.feature_set == "expert":
        benchmark_df = load_benchmark_bars(
            engine, cfg.data.benchmark_symbol,
            end_date=history_end_date, start_date=history_start_date,
        )
    sentiment_df = None
    # sentiment → per-symbol uniquement ; le global ranking ignore ces features
    # (sparse, noyées dans 177 features).  On saute le chargement pour gagner du temps.
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
    _req_horizons = getattr(cfg.data, "forecast_horizons", ()) or ()
    _requested_h = cfg.data.forecast_horizon
    if _req_horizons:
        _display_horizons = [h for h in _GLOBAL_RANKING_HORIZONS if h in _req_horizons]
    else:
        _display_horizons = [h for h in _GLOBAL_RANKING_HORIZONS if _requested_h <= 0 or h == _requested_h]
    LOGGER.info(
        "train_global_ranking_wf symbols=%d feature_cols=%d horizons=%s (requested=%d, multi=%s)",
        len(symbols), len(feature_columns), _display_horizons, _requested_h,
        bool(_req_horizons),
    )
    # Vérifier que l'univers est bien Mid Cap (pas de mega caps parasites)
    if cfg.data.enable_liquidity_filter:
        _max_mcap = cfg.data.liquidity_max_market_cap
        if _max_mcap > 0:
            LOGGER.info(
                "train_global_ranking_wf liquidity_filter active: max_market_cap=%.0f — "
                "ranking cross-sectionnel intra-Mid-Cap (pas de mega caps > %.0f$)",
                _max_mcap, _max_mcap,
            )
        else:
            LOGGER.info(
                "train_global_ranking_wf liquidity_filter active: min_market_cap=%.0f — "
                "pas de limite haute, univers mixte possible",
                cfg.data.liquidity_min_market_cap,
            )
    _base_parts: list[pd.DataFrame] = []
    for symbol in symbols:
        bars_df = universe_df[universe_df["symbol"] == symbol].sort_values("date").reset_index(drop=True)
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
            symbol=symbol,
        )
        if prepared.empty:
            continue
        prepared["symbol"] = symbol
        # ── Downcast immédiat float64→float32 (évite pic mémoire au concat) ──
        _f64 = [c for c in prepared.columns if prepared[c].dtype == np.float64]
        if _f64:
            prepared[_f64] = prepared[_f64].astype(np.float32)
        _base_parts.append(prepared)
        # Libérer les DataFrames intermédiaires
        del bars_df, sym_sentiment, sym_selector, sym_cross, prepared

    # Libérer les données sources massives avant le concat
    del universe_df
    if cross_sectional_df is not None:
        del cross_sectional_df
    if selector_context_df is not None:
        del selector_context_df
    gc.collect()

    if not _base_parts:
        return {"status": "skipped", "reason": "no_prepared_rows"}

    base_df = pd.concat(_base_parts, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
    # Libérer les parts individuelles (le concat a tout recopié)
    del _base_parts
    gc.collect()

    # ── Downcast float64 → float32 (mémoire ÷ 2, précision suffisante pour le ranking) ──
    # Déjà fait par symbole ci-dessus ; ce second passage attrape les colonnes
    # ajoutées par le concat (ex: symbol casté en object, etc.)
    _float_cols = [c for c in base_df.columns if base_df[c].dtype == np.float64]
    if _float_cols:
        base_df[_float_cols] = base_df[_float_cols].astype(np.float32)
        LOGGER.info("train_global_ranking_wf downcast %d columns float64→float32", len(_float_cols))

    # ── Normalisation cross-sectionnelle des features brutes ──
    # Chaque feature est transformée en rang percentil intra-date [0, 1].
    # Cela rend les features comparables entre régimes de marché (ex: RSI=70
    # n'a pas le même sens en marché haussier qu'en crise).
    _xs_available = [s for s in _XS_RANK_SOURCE_FEATURES if s in base_df.columns]
    if _xs_available:
        _xs_ranked = base_df.groupby("date")[_xs_available].rank(pct=True).astype(np.float64)
        _xs_ranked.columns = [_xs_rank_column_name(c) for c in _xs_available]
        # Joindre les colonnes _xs_rank au DataFrame principal
        for _col in _xs_ranked.columns:
            base_df[_col] = _xs_ranked[_col]
        LOGGER.info(
            "train_global_ranking_wf cross-sectional ranks computed for %d features",
            len(_xs_available),
        )

    # ── Sector-neutral features (2026-07-27) ──
    # Calcule les versions sector-neutralisées des features techniques
    # (momentum, RSI, volatilité, etc.) en soustrayant la médiane du secteur
    # à chaque date.  Isole l'alpha spécifique au titre vs son secteur.
    _sn_cols_in = [c for c in SECTOR_NEUTRAL_FEATURE_COLUMNS if c in feature_columns]
    if _sn_cols_in and cfg.data.enable_cross_sectional_features:
        _compute_sector_neutral_inplace(base_df, feature_columns, engine)

    base_df = base_df.dropna(subset=feature_columns).reset_index(drop=True)

    # ── Résoudre les colonnes facteurs et le secteur mapping une fois ──
    _factor_cols: list[str] = []
    for _fc in ["fund_market_cap_log", "fund_pe_ratio_sector_neutral", "momentum_60"]:
        if _fc in base_df.columns:
            _factor_cols.append(_fc)
    _sector_map: dict[str, str] = {}
    try:
        from modelFactory.cross_sectional import _load_sector_mapping
        _sector_map = _load_sector_mapping(engine)
        if _sector_map:
            LOGGER.info(
                "train_global_ranking_wf sector_map: %d symbols → %d sectors",
                len(_sector_map), len(set(_sector_map.values())),
            )
    except Exception as _exc:
        LOGGER.warning("train_global_ranking_wf sector_map failed: %s", _exc)

    # ── Walk-Forward splits par DATES (P1-2 fix, 2026-08-04) ──
    # Avant : generate_walk_forward_splits (par lignes) × median_symbols_per_date
    #   → si le nombre de symboles varie, une date peut être coupée entre train/val.
    # Après : generate_walk_forward_splits_by_dates (par dates uniques)
    #   → une date entière ne peut appartenir qu'à UN seul fold.
    wf_splits = generate_walk_forward_splits_by_dates(
        base_df,
        min_train_dates=cfg.walk_forward.min_train_size,
        val_dates=cfg.walk_forward.val_size,
        test_dates=cfg.walk_forward.test_size,
        step_dates=cfg.walk_forward.step_size,
        max_splits=cfg.walk_forward.max_splits,
        forecast_horizon=1,  # 1 date de purge (marge résiduelle)
        date_column="date",
    )
    if not wf_splits:
        return {"status": "skipped", "reason": "no_valid_wf_split"}

    # ── Calculer les targets sur chaque fold (PIT-étanche) ──
    # Les targets sont calculées à la volée dans la boucle split/horizon
    # car WalkForwardSplit est frozen (pas d'assignation possible).
    # Voir _compute_ranking_targets() appelé dans la double boucle.

    # P0-9 (2026-08-07) : respecter --forecast-horizon / --forecast-horizons.
    # --forecast-horizons 3,5,10,15,20 → ces 5 horizons exactement.
    # --forecast-horizon 20           → seulement H20.
    # --forecast-horizon 0 (ou omis)  → tous les horizons par défaut.
    _req_horizons = getattr(cfg.data, "forecast_horizons", ()) or ()
    if _req_horizons:
        _active_horizons = tuple(h for h in _GLOBAL_RANKING_HORIZONS if h in _req_horizons)
    else:
        _requested_horizon = cfg.data.forecast_horizon
        if _requested_horizon > 0:
            _active_horizons = tuple(h for h in _GLOBAL_RANKING_HORIZONS if h == _requested_horizon)
            if not _active_horizons:
                LOGGER.warning(
                    "global_ranking_wf forecast_horizon=%d not in %s, falling back to all horizons",
                    _requested_horizon, list(_GLOBAL_RANKING_HORIZONS),
                )
                _active_horizons = _GLOBAL_RANKING_HORIZONS
        else:
            _active_horizons = _GLOBAL_RANKING_HORIZONS

    LOGGER.info(
        "train_global_ranking_wf start symbols=%d splits=%d feature_cols=%d horizons=%s",
        len(symbols), len(wf_splits), len(feature_columns), list(_active_horizons),
    )

    # ── Entraîner un modèle par horizon ──
    all_ic_means: dict[int, float] = {}
    all_ic_stds: dict[int, float] = {}
    all_fold_ics: list[float] = []
    all_rank_dfs: list[pd.DataFrame] = []
    _saved_models: dict[int, str] = {}
    _horizon_features: dict[int, list[str]] = {}  # features actives par horizon
    _decile_spreads: dict[int, float] = {}  # decile spread par horizon
    _horizon_details: dict[str, Any] = {}  # détails par horizon pour IHM/rapport

    for horizon in _active_horizons:
        h_suffix = f"_{horizon}"
        _target_col = f"future_return{h_suffix}"
        _label_col = f"label{h_suffix}"
        LOGGER.info("global_ranking_wf horizon=%d start", horizon)

        resolved_seed = derive_seed(cfg.reproducibility.seed, f"global_ranking_wf_{horizon}", cfg.global_model.model_name)
        apply_reproducibility(
            ReproducibilityConfig(seed=resolved_seed, deterministic=cfg.reproducibility.deterministic),
            context=f"global_ranking_wf:{cfg.global_model.model_name}:h{horizon}",
        )

        h_parts: list[pd.DataFrame] = []
        h_ics: list[float] = []
        _last_model: Any = None
        _last_model_name: str = ""
        _split_importances: list[dict[str, float]] = []
        _active_features: list[str] = feature_columns
        _h_split_details: list[dict[str, Any]] = []  # détails par split pour IHM/rapport

        # ── H3 : exclure les features fondamentales (inefficaces à court terme) ──
        if horizon == 3:
            _active_features = [c for c in _active_features if not c.startswith("fund_")]
            LOGGER.info("global_ranking_wf horizon=3: fundamental features excluded (%d → %d features)",
                        len(feature_columns), len(_active_features))

        # ── Déterminer les candidats à entraîner pour cet horizon ──
        _champion_mode = cfg.global_model.champion_enabled
        _candidate_names: list[str]
        if _champion_mode:
            _candidate_names = ["lightgbm", "catboost"]
            LOGGER.info("global_ranking_wf horizon=%d champion_mode=ON candidates=%s", horizon, _candidate_names)
        else:
            _candidate_names = [cfg.global_model.model_name]

        LOGGER.info(
            "global_ranking_wf horizon=%d ⏳ starting — %d splits × %d candidates, %d features",
            horizon, len(wf_splits), len(_candidate_names), len(_active_features),
        )

        # ── Suivi des IC par candidat (pour sélection champion) ──
        _candidate_ics: dict[str, list[float]] = {_cn: [] for _cn in _candidate_names}
        _candidate_parts: dict[str, list[pd.DataFrame]] = {_cn: [] for _cn in _candidate_names}
        _candidate_last_model: dict[str, Any] = {}
        _candidate_last_name: dict[str, str] = {}
        _candidate_importances: dict[str, list[dict[str, float]]] = {_cn: [] for _cn in _candidate_names}

        for split in wf_splits:
            split_seed = derive_seed(resolved_seed, split.split_index)
            apply_reproducibility(
                ReproducibilityConfig(seed=split_seed, deterministic=cfg.reproducibility.deterministic),
                context=f"global_ranking_wf:split_{split.split_index}:h{horizon}",
            )

            # ── P1 : calculer les targets sur les folds isolés (étanche) ──
            _target_horizons = _SMOOTHING_HORIZONS if horizon in _SMOOTHING_HORIZONS else (horizon,)
            _train_with_targets = _compute_ranking_targets(
                split.train,
                horizons=_target_horizons,
                smoothing_horizons=_SMOOTHING_HORIZONS if horizon in _SMOOTHING_HORIZONS else (),
                factor_cols=_factor_cols,
                sector_map=_sector_map,
            )
            _val_with_targets = _compute_ranking_targets(
                split.val,
                horizons=_target_horizons,
                smoothing_horizons=_SMOOTHING_HORIZONS if horizon in _SMOOTHING_HORIZONS else (),
                factor_cols=_factor_cols,
                sector_map=_sector_map,
            )
            _train_orig = _train_with_targets.dropna(subset=_active_features + [_target_col, _label_col])
            _val_orig = _val_with_targets.dropna(subset=_active_features + [_target_col, _label_col])
            if _train_orig.empty or _val_orig.empty:
                continue

            # ── P1-6 (2026-08-04) : filtre liquidité + disponibilité par fold ──
            _total_syms = len(symbols)
            if cfg.data.enable_liquidity_filter and "date" in _train_orig.columns and "symbol" in _train_orig.columns and "volume" in _train_orig.columns:
                _sym_sessions = _train_orig.groupby("symbol")["date"].nunique()
                _min_sessions = max(cfg.walk_forward.min_train_size // 2, 60)
                _eligible_sessions = set(_sym_sessions[_sym_sessions >= _min_sessions].index)
                _sym_vol = _train_orig.groupby("symbol")["volume"].mean()
                _min_vol = cfg.data.liquidity_min_avg_volume_20d if hasattr(cfg.data, "liquidity_min_avg_volume_20d") else 50000
                _eligible_vol = set(_sym_vol[_sym_vol >= _min_vol].index)
                _eligible = _eligible_sessions & _eligible_vol
                _excluded = (set(_train_orig["symbol"].unique()) | set(_val_orig["symbol"].unique())) - _eligible
                if _excluded:
                    LOGGER.info(
                        "global_ranking_wf fold=%d: %d symbols excluded (low vol or sessions in train period)",
                        split.split_index + 1, len(_excluded),
                    )
                    _train_orig = _train_orig[_train_orig["symbol"].isin(_eligible)]
                    _val_orig = _val_orig[_val_orig["symbol"].isin(_eligible)]
            _train_syms = _train_orig["symbol"].nunique() if "symbol" in _train_orig.columns else 0
            _val_syms = _val_orig["symbol"].nunique() if "symbol" in _val_orig.columns else 0
            LOGGER.info(
                "global_ranking_wf fold=%d symbols train=%d/%d val=%d/%d (%.0f%% of universe)",
                split.split_index + 1, _train_syms, _total_syms, _val_syms, _total_syms,
                100 * _train_syms / _total_syms if _total_syms > 0 else 0,
            )
            if _train_syms < 0.5 * _total_syms and _total_syms > 20:
                LOGGER.warning(
                    "global_ranking_wf P1-6: fold %d only has %d/%d symbols after per-fold "
                    "filtering (sessions+volume in train period). Initial selection still "
                    "uses global liquidity filter — remaining symbols may have limited history.",
                    split.split_index + 1, _train_syms, _total_syms,
                )

            # ── Périodes des splits (diagnostic régime de marché) ──
            _train_dates = pd.to_datetime(_train_orig["date"]) if "date" in _train_orig.columns else None
            _val_dates = pd.to_datetime(_val_orig["date"]) if "date" in _val_orig.columns else None
            if _train_dates is not None and _val_dates is not None:
                LOGGER.info(
                    "global_ranking_wf horizon=%d split=%d/%d train_period=%s→%s val_period=%s→%s",
                    horizon, split.split_index + 1, len(wf_splits),
                    _train_dates.min().strftime("%Y-%m-%d"), _train_dates.max().strftime("%Y-%m-%d"),
                    _val_dates.min().strftime("%Y-%m-%d"), _val_dates.max().strftime("%Y-%m-%d"),
                )

            # ── Sample weights temporels (partagés entre tous les candidats) ──
            _sample_weights = None
            if _train_dates is not None:
                _days_diff = (_train_dates.max() - _train_dates).dt.days
                _sample_weights = np.exp(-_days_diff.values.astype(np.float64) / 360.0)

            # ── Entraîner chaque candidat sur ce split ──
            try:
                _candidates = _build_ranking_estimators(cfg, resolved_seed=split_seed, model_names=_candidate_names)
            except ImportError:
                return {"status": "unavailable", "reason": f"{_candidate_names[0]}_not_installed"}

            _split_ic: dict[str, float | None] = {}
            for backend_model_name, model in _candidates:
                # ── Chaque candidat travaille sur sa propre copie des données ──
                #    (LightGBM peut modifier train_df via early stopping split)
                train_df = _train_orig.copy()
                val_df = _val_orig.copy()
                _sw = _sample_weights.copy() if _sample_weights is not None else None

                _group = None
                _eval_set = None
                _eval_group = None
                if backend_model_name == "lightgbm":
                    _group = train_df.groupby("date", sort=False).size().to_numpy(dtype=np.int32)
                    _es_rounds = cfg.baseline.lgbm_early_stopping_rounds
                    if _es_rounds > 0 and len(train_df) > 100:
                        _es_cut = max(int(len(train_df) * 0.8), 1)
                        _train_sorted = train_df.sort_values("date")
                        _es_train = _train_sorted.iloc[:_es_cut]
                        _es_eval = _train_sorted.iloc[_es_cut:]
                        _eval_set = [(
                            _es_eval[_active_features],
                            _es_eval[_label_col].to_numpy(dtype=np.int32),
                        )]
                        _eval_group = [_es_eval.groupby("date", sort=False).size().to_numpy(dtype=np.int32)]
                        train_df = _es_train
                        _group = train_df.groupby("date", sort=False).size().to_numpy(dtype=np.int32)
                        if _sw is not None:
                            _sw = _sw[_es_train.index.get_indexer(train_df.index)]

                X_train = train_df[_active_features]
                if backend_model_name == "lightgbm":
                    y_train = train_df[_label_col].to_numpy(dtype=np.int32)
                else:
                    y_train = train_df[_target_col].to_numpy(dtype=np.float64)

                _fit_kwargs: dict[str, Any] = {}
                if _group is not None and len(_group) > 0:
                    _fit_kwargs["group"] = _group
                if _eval_set is not None:
                    _fit_kwargs["eval_set"] = _eval_set
                    _fit_kwargs["eval_group"] = _eval_group
                    _fit_kwargs["eval_at"] = [10, 20]
                    _es = getattr(cfg.baseline, "lgbm_early_stopping_rounds", None)
                    if _es and _es > 0:
                        _fit_kwargs["eval_metric"] = "ndcg"
                        # LightGBM 4.x : early stopping via callback, pas via fit()
                        _lgb_es = _import_lightgbm()
                        _fit_kwargs["callbacks"] = [_lgb_es.early_stopping(stopping_rounds=_es)]
                        LOGGER.info(
                            "global_ranking_wf horizon=%d split=%d/%d early_stopping=%d rounds eval_rows=%d",
                            horizon, split.split_index + 1, len(wf_splits),
                            _es, len(_es_eval) if _es_eval is not None else 0,
                        )
                if _sw is not None:
                    _fit_kwargs["sample_weight"] = _sw
                LOGGER.info(
                    "global_ranking_wf horizon=%d split=%d/%d → fitting %s (%d rows)...",
                    horizon, split.split_index + 1, len(wf_splits),
                    backend_model_name, len(train_df),
                )
                model.fit(X_train, y_train, **_fit_kwargs)

                _candidate_last_model[backend_model_name] = model
                _candidate_last_name[backend_model_name] = backend_model_name

                # ── Feature importance (LightGBM uniquement) ──
                if backend_model_name == "lightgbm" and hasattr(model, "booster_"):
                    try:
                        _imp = dict(zip(_active_features, model.booster_.feature_importance(importance_type="gain")))
                        _candidate_importances[backend_model_name].append(_imp)
                    except Exception:
                        pass

                X_val = val_df[_active_features]
                y_val = val_df[_target_col].to_numpy(dtype=np.float64)
                pred_part = val_df[["symbol", "date"]].copy()
                pred_part["predicted_score"] = model.predict(X_val).astype(np.float64)
                pred_part["actual_return"] = y_val

                _ic_result = compute_cross_sectional_ic(
                    pred_part,
                    score_col="predicted_score",
                    return_col="actual_return",
                    date_col="date",
                    vol_col=None,
                    min_symbols_per_date=10,
                )
                ic = _ic_result.get("ic_mean")
                if ic is not None:
                    _candidate_ics[backend_model_name].append(ic)
                _candidate_parts[backend_model_name].append(pred_part)
                _split_ic[backend_model_name] = ic

                LOGGER.info(
                    "global_ranking_wf horizon=%d split=%d/%d model=%s train_rows=%d val_rows=%d ic_rank=%.4f",
                    horizon, split.split_index + 1, len(wf_splits),
                    backend_model_name, len(train_df), len(val_df),
                    ic if ic is not None else float("nan"),
                )

            # ── Collecter les détails du split (modèle champion uniquement) ──
            _champion_for_split = max(_split_ic, key=lambda k: _split_ic.get(k) or float("-inf")) if _split_ic else _candidate_names[0]
            _champion_ic = _split_ic.get(_champion_for_split)
            if _champion_ic is not None:
                h_ics.append(_champion_ic)
            # ── Log champion du split (mode champion uniquement) ──
            if _champion_mode and len(_split_ic) > 1:
                _split_summary = ", ".join(
                    f"{cn}=IC {(_split_ic.get(cn) or float('nan')):.4f}"
                    for cn in _candidate_names
                )
                LOGGER.info(
                    "global_ranking_wf horizon=%d split=%d/%d 🏆 split_champion=%s (%s)",
                    horizon, split.split_index + 1, len(wf_splits),
                    _champion_for_split, _split_summary,
                )
            _h_split_details.append({
                "split_index": split.split_index + 1,
                "n_splits": len(wf_splits),
                "train_period_start": _train_dates.min().strftime("%Y-%m-%d") if _train_dates is not None else None,
                "train_period_end": _train_dates.max().strftime("%Y-%m-%d") if _train_dates is not None else None,
                "val_period_start": _val_dates.min().strftime("%Y-%m-%d") if _val_dates is not None else None,
                "val_period_end": _val_dates.max().strftime("%Y-%m-%d") if _val_dates is not None else None,
                "train_rows": len(_train_orig),
                "val_rows": len(_val_orig),
                "ic_rank": float(_champion_ic) if _champion_ic is not None else None,
                **({f"ic_rank_{cn}": float(_split_ic[cn]) if _split_ic.get(cn) is not None else None for cn in _candidate_names} if _champion_mode else {}),
            })

        # ── Sélection du champion pour cet horizon ──
        # Score composite : 55% IC Mean + 30% IC IR + 15% Positive Split Ratio.
        # L'IC mesure la qualité de l'alpha. L'IR mesure la stabilité.
        # Le % positif mesure la robustesse cross-régime (GPT: ne pas juste
        # s'en servir comme gate, l'intégrer dans le score).
        # Normalisation par le max des 2 candidats sur chaque métrique.
        #
        # Gates d'éligibilité (ordre de grandeur adapté au ranking cross-sectionnel) :
        #   1. IC Mean > 0 (un IC négatif classe à l'envers)
        #   2. IC IR ≥ 0.30 (filtre les modèles sans aucune stabilité)
        #   3. Au plus 2 splits négatifs : ≥ (N-2)/N splits avec IC > 0
        if _champion_mode and len(_candidate_names) > 1:
            _champion_details: dict[str, dict[str, float | None]] = {}
            _champion_eligible: dict[str, bool] = {}
            for _cn in _candidate_names:
                _ics = _candidate_ics.get(_cn, [])
                if not _ics:
                    _champion_details[_cn] = {"ic_mean": None, "ic_std": None, "ic_ir": None, "positive_pct": None}
                    _champion_eligible[_cn] = False
                    continue
                _mean = float(np.mean(_ics))
                _std = float(np.std(_ics)) if len(_ics) > 1 else 0.0
                _ir = _mean / _std if _std > 0 else _mean
                _positive = sum(1 for ic in _ics if ic > 0)
                _positive_pct = _positive / len(_ics) if _ics else 0.0
                _champion_details[_cn] = {
                    "ic_mean": _mean, "ic_std": _std if len(_ics) > 1 else None,
                    "ic_ir": _ir, "positive_pct": _positive_pct,
                }
                # Gates
                _eligible = True
                _gate_reason = ""
                if _mean <= 0:
                    _eligible = False
                    _gate_reason = f"IC_mean<=0 ({_mean:.4f})"
                elif _ir is not None and _ir < 0.30:
                    _eligible = False
                    _gate_reason = f"IC_IR={_ir:.2f}<0.30 (instable)"
                elif len(_ics) >= 3:
                    _min_positive = (len(_ics) - 2) / len(_ics)
                    if _positive_pct < _min_positive:
                        _eligible = False
                        _gate_reason = f"positive_splits={_positive_pct:.0%}<{_min_positive:.0%} ({_positive}/{len(_ics)})"
                _champion_eligible[_cn] = _eligible
                if not _eligible:
                    LOGGER.warning(
                        "global_ranking_wf horizon=%d candidate=%s INELIGIBLE: %s",
                        horizon, _cn, _gate_reason,
                    )

            # ── Calculer le score composite (seulement pour les éligibles) ──
            _eligible_candidates = [_cn for _cn in _candidate_names if _champion_eligible[_cn]]
            if not _eligible_candidates:
                _all_ic_positive = all(
                    (_champion_details[_cn].get("ic_mean") or 0.0) > 0
                    for _cn in _candidate_names
                )
                if not _all_ic_positive:
                    LOGGER.error(
                        "global_ranking_wf horizon=%d ⚠️ ALL candidates have IC≤0 — "
                        "picking least bad model. This horizon is likely unusable.",
                        horizon,
                    )
                else:
                    LOGGER.warning(
                        "global_ranking_wf horizon=%d NO eligible candidates "
                        "(IR<0.30 or too many negative splits) — fallback to best composite score",
                        horizon,
                    )
                _eligible_candidates = list(_candidate_names)  # fallback: tous

            # Normalisation : diviser par le max parmi les éligibles
            _max_ic = max(
                (_champion_details[_cn]["ic_mean"] or 0.0) for _cn in _eligible_candidates
            )
            _max_ir = max(
                (_champion_details[_cn]["ic_ir"] or 0.0) for _cn in _eligible_candidates
            )
            _champion_scores: dict[str, float] = {}
            for _cn in _eligible_candidates:
                _d = _champion_details[_cn]
                _ic_norm = (_d["ic_mean"] or 0.0) / _max_ic if _max_ic > 0 else 0.0
                _ir_norm = (_d["ic_ir"] or 0.0) / _max_ir if _max_ir > 0 else 0.0
                _pos_norm = (_d["positive_pct"] or 0.0)  # déjà dans [0,1], pas besoin de normaliser
                # Score composite : 55% IC + 30% IR + 15% Positive Split Ratio
                _champion_scores[_cn] = 0.55 * _ic_norm + 0.30 * _ir_norm + 0.15 * _pos_norm
            # Inéligibles : score = -inf
            for _cn in _candidate_names:
                if _cn not in _champion_scores:
                    _champion_scores[_cn] = float("-inf")

            _selected_champion = max(_champion_scores, key=lambda k: _champion_scores[k])
            LOGGER.info(
                "global_ranking_wf horizon=%d champion_selection (metric=composite 55%%IC+30%%IR+15%%pos) → champion=%s",
                horizon, _selected_champion,
            )
            # Log détaillé pour chaque candidat
            for _cn in _candidate_names:
                _d = _champion_details[_cn]
                _score = _champion_scores.get(_cn, float("-inf"))
                _elig = "✅" if _champion_eligible.get(_cn, False) else "❌"
                LOGGER.info(
                    "global_ranking_wf horizon=%d candidate=%s %s IC=%.4f IR=%.2f pos=%.0f%% score=%.3f",
                    horizon, _cn, _elig,
                    _d["ic_mean"] if _d["ic_mean"] is not None else float("nan"),
                    _d["ic_ir"] if _d["ic_ir"] is not None else float("nan"),
                    (_d["positive_pct"] or 0.0) * 100,
                    _score if _score != float("-inf") else float("nan"),
                )
            # Utiliser les prédictions du champion pour le ranking
            h_parts = _candidate_parts.get(_selected_champion, [])
            _last_model = _candidate_last_model.get(_selected_champion)
            _last_model_name = _selected_champion
            _split_importances = _candidate_importances.get(_selected_champion, [])
            # Recalculer h_ics avec les ICs du CHAMPION (pas le meilleur par split)
            _champion_split_ics = _candidate_ics.get(_selected_champion, [])
            if _champion_split_ics:
                h_ics = list(_champion_split_ics)
            # Mettre à jour ic_rank dans _h_split_details avec l'IC du champion
            _champ_ic_key = f"ic_rank_{_selected_champion}"
            for _sp in _h_split_details:
                _champ_ic = _sp.get(_champ_ic_key)
                if _champ_ic is not None:
                    _sp["ic_rank"] = float(_champ_ic)
            # Stocker les métriques des deux candidats pour le rapport
            _champion_sel = _champion_details[_selected_champion]
            _horizon_champion_info: dict[str, Any] = {
                "champion": _selected_champion,
                "champion_ic_mean": _champion_sel["ic_mean"],
                "champion_ic_ir": _champion_sel["ic_ir"],
                "champion_positive_pct": _champion_sel["positive_pct"],
                "champion_score": _champion_scores[_selected_champion],
                "selection_metric": "composite_55ic_30ir_15pos",
                "candidates": _champion_details,
                "eligibility": {_cn: _champion_eligible.get(_cn, False) for _cn in _candidate_names},
            }
        else:
            # Mode single-model : utiliser le seul candidat
            _single_name = _candidate_names[0]
            h_parts = _candidate_parts.get(_single_name, [])
            _last_model = _candidate_last_model.get(_single_name)
            _last_model_name = _single_name
            _split_importances = _candidate_importances.get(_single_name, [])
            _horizon_champion_info = {}

        # ── Feature importance agrégée pour cet horizon ──
        if _split_importances and _active_features:
            _mean_imp = _compute_mean_importance(_split_importances, _active_features)
            _top10 = list(_mean_imp.items())[:10]
            _bottom10 = list(_mean_imp.items())[-10:]
            LOGGER.info(
                "global_ranking_wf horizon=%d feature_importance top10=%s",
                horizon,
                {k: f"{v:.1f}" for k, v in _top10},
            )
            LOGGER.info(
                "global_ranking_wf horizon=%d feature_importance bottom10=%s",
                horizon,
                {k: f"{v:.1f}" for k, v in _bottom10},
            )
            # ── Log complet (toutes les features par importance décroissante) ──
            LOGGER.info(
                "global_ranking_wf horizon=%d feature_importance all=%d features: %s",
                horizon,
                len(_mean_imp),
                ", ".join(f"{k}={v:.1f}" for k, v in _mean_imp.items()),
            )

        if h_parts:
            h_pred_df = pd.concat(h_parts, ignore_index=True)
            # LambdaRank produit des scores continus → rank pct par date pour normaliser [0,1]
            h_pred_df[f"global_rank{h_suffix}"] = (
                h_pred_df.groupby("date")["predicted_score"]
                .rank(pct=True)
                .clip(0.0, 1.0)
                .astype(np.float64)
            )
            all_rank_dfs.append(h_pred_df[["symbol", "date", f"global_rank{h_suffix}"]])
            all_ic_means[horizon] = float(np.mean(h_ics)) if h_ics else float("nan")
            all_ic_stds[horizon] = float(np.std(h_ics)) if (h_ics and len(h_ics) > 1) else float("nan")
            all_fold_ics.extend(h_ics)

            # ── Decile Spread (monétisation du signal) ──
            _decile = _compute_decile_spread(h_pred_df)
            _decile_spreads[horizon] = _decile["decile_spread"]
            LOGGER.info(
                "global_ranking_wf horizon=%d decile_spread=%.4f top=%.4f bottom=%.4f",
                horizon, _decile["decile_spread"], _decile["top_decile_return"], _decile["bottom_decile_return"],
            )

            # ── Enregistrer les features actives pour cet horizon ──
            _horizon_features[horizon] = list(_active_features)

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

            _ic_mean = all_ic_means.get(horizon, float("nan"))
            _ic_std = all_ic_stds.get(horizon, float("nan"))
            _ic_ir = _ic_mean / _ic_std if (_ic_std and not np.isnan(_ic_std) and _ic_std > 0) else float("nan")
            LOGGER.info(
                "global_ranking_wf horizon=%d done ic_mean=%.4f ic_std=%.4f ic_ir=%.2f",
                horizon, _ic_mean, _ic_std, _ic_ir,
            )
            # ── Stocker les détails pour IHM/rapport ──
            _h_key = str(horizon)
            _horizon_details[_h_key] = {
                "ic_mean": float(all_ic_means[horizon]) if horizon in all_ic_means else None,
                "ic_std": float(all_ic_stds[horizon]) if horizon in all_ic_stds else None,
                "ic_ir": float(_ic_ir) if not np.isnan(_ic_ir) else None,
                "decile_spread": float(_decile_spreads.get(horizon)) if horizon in _decile_spreads else None,
                "decile_top": float(_decile.get("top_decile_return")) if _decile and _decile.get("top_decile_return") is not None else None,
                "decile_bottom": float(_decile.get("bottom_decile_return")) if _decile and _decile.get("bottom_decile_return") is not None else None,
                "n_features": len(_active_features),
                "splits": _h_split_details,
                "feature_importance_top10": [{"feature": k, "importance": round(v, 1)} for k, v in _top10] if (_split_importances and _active_features) else [],
                "feature_importance_bottom10": [{"feature": k, "importance": round(v, 1)} for k, v in _bottom10] if (_split_importances and _active_features) else [],
                "feature_importance_all": {k: round(v, 1) for k, v in _mean_imp.items()} if (_split_importances and _active_features) else {},
                **_horizon_champion_info,
            }
        else:
            LOGGER.warning("global_ranking_wf horizon=%d no predictions", horizon)
        # ── Libérer la mémoire avant l'horizon suivant ──
        del h_parts, h_ics, _last_model, _split_importances, _active_features
        del _candidate_parts, _candidate_ics, _candidate_last_model, _candidate_last_name, _candidate_importances
        gc.collect()

    if not all_rank_dfs:
        return {"status": "skipped", "reason": "no_predictions"}

    # ── Fusionner tous les horizons ──
    global_rank_df = all_rank_dfs[0].copy()
    for _df in all_rank_dfs[1:]:
        global_rank_df = global_rank_df.merge(_df, on=["symbol", "date"], how="outer")
    for h in _GLOBAL_RANKING_HORIZONS:
        _col = f"global_rank_{h}"
        if _col not in global_rank_df.columns:
            global_rank_df[_col] = 0.5
        else:
            global_rank_df[_col] = global_rank_df[_col].fillna(0.5).astype(np.float64)
    global_rank_df = global_rank_df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # IC moyen par horizon et dispersion sur les observations OOS fold×horizon.
    # La dispersion entre les seuls horizons ne mesure pas la stabilité temporelle.
    _valid_ics = [v for v in all_ic_means.values() if not np.isnan(v)]
    ic_mean = float(np.mean(_valid_ics)) if _valid_ics else None
    ic_std = float(np.std(all_fold_ics)) if len(all_fold_ics) > 1 else None

    LOGGER.info(
        "train_global_ranking_wf done pred_rows=%d symbols=%d horizons=%s ic_by_h=%s ic_mean=%.4f",
        len(global_rank_df),
        global_rank_df["symbol"].nunique() if not global_rank_df.empty else 0,
        list(all_ic_means.keys()),
        {h: f"{v:.4f}" for h, v in all_ic_means.items()},
        ic_mean if ic_mean is not None else float("nan"),
    )

    # ── Sauvegarder global_rank_df en parquet pour backtest ──
    if not global_rank_df.empty:
        try:
            _cache_path = Path(cfg.artifacts_dir) / "global_rank_cache.parquet"
            global_rank_df.to_parquet(_cache_path, index=False)
            LOGGER.info(
                "train_global_ranking_wf cached %d rows to %s",
                len(global_rank_df), _cache_path,
            )
        except Exception as _exc:
            LOGGER.warning("train_global_ranking_wf failed to cache ranks: %s", _exc)

    # ── Sauvegarder les métadonnées features ──
    _model_dir = Path(cfg.artifacts_dir)
    _model_dir.mkdir(parents=True, exist_ok=True)
    # ── Déterminer le nom effectif du modèle (champion ou configuré) ──
    _effective_model_name = cfg.global_model.model_name
    _champion_by_horizon: dict[str, str] = {}
    if cfg.global_model.champion_enabled:
        for _h_key, _h_info in _horizon_details.items():
            _champ = _h_info.get("champion")
            if _champ:
                _champion_by_horizon[_h_key] = _champ
        # Le nom effectif est le champion majoritaire sur les horizons
        if _champion_by_horizon:
            from collections import Counter
            _champion_counts = Counter(_champion_by_horizon.values())
            _effective_model_name = _champion_counts.most_common(1)[0][0]

    _model_dir.joinpath("_global_ranking_features.json").write_text(
        json.dumps({
            "feature_columns": feature_columns,
            "model_name": _effective_model_name,
            "champion_enabled": cfg.global_model.champion_enabled,
            "champion_by_horizon": _champion_by_horizon if _champion_by_horizon else None,
            "horizons": list(_active_horizons),
            "saved_models": _saved_models,
            "feature_set": cfg.data.feature_set,
            "include_sentiment": cfg.data.include_sentiment_features,
            "include_screener_scores": cfg.data.include_screener_scores,
            "include_short_score": cfg.data.include_short_score_features,
            "include_macro_vix": cfg.data.include_macro_vix_features,
            "include_macro_vxn": cfg.data.include_macro_vxn_features,
            "include_macro_vix3m": cfg.data.include_macro_vix3m_features,
            "include_macro_move": cfg.data.include_macro_move_features,
            "include_fundamentals": cfg.data.include_fundamentals_features,
            "include_factors": cfg.data.include_factors_features,
            "include_macro_regime": cfg.data.include_macro_regime_features,
            "enable_cross_sectional": cfg.data.enable_cross_sectional_features,
            "horizon_features": {str(h): feats for h, feats in _horizon_features.items()},
            "horizon_details": _horizon_details,
            "ic_by_horizon": {str(h): float(v) for h, v in all_ic_means.items()} if all_ic_means else {},
            "decile_spreads": {str(h): float(v) for h, v in _decile_spreads.items()} if _decile_spreads else {},
            "symbols_count": len(symbols),
            "pred_rows": len(global_rank_df) if not global_rank_df.empty else 0,
            "splits_count": len(wf_splits),
        }),
        encoding="utf-8",
    )

    return {
        "status": "completed",
        "model_name": "global_ranking",
        "backend_model_name": _effective_model_name,
        "champion_enabled": cfg.global_model.champion_enabled,
        "champion_by_horizon": _champion_by_horizon if _champion_by_horizon else None,
        "global_rank_df": global_rank_df if not global_rank_df.empty else None,
        "ic_rank_mean": ic_mean,
        "ic_rank_std": ic_std,
        "ic_by_horizon": all_ic_means,
        "decile_spreads": _decile_spreads,
        "horizon_details": _horizon_details,  # P0-8 : pour persistance immédiate dans metadata_json
        "symbols_count": len(symbols),
        "pred_rows": len(global_rank_df) if not global_rank_df.empty else 0,
        "splits_count": len(wf_splits),
        "feature_columns": feature_columns,
        "n_features": len(feature_columns),
        "horizons": list(_active_horizons),
    }


# ────────────────────────────────────────────────────────────────────
# Inférence (appelé depuis predictor.py en étape 10)
# ────────────────────────────────────────────────────────────────────

def predict_global_rank(
    universe_df: pd.DataFrame,
    artifacts_dir: Path,
    *,
    benchmark_df: pd.DataFrame | None = None,
    engine: Any | None = None,
) -> pd.DataFrame | None:
    """Prédit les ``global_rank_{h}`` multi-horizons pour l'univers du jour.

    Charge les modèles sauvegardés par ``train_global_ranking_wf()`` et
    les applique sur l'univers courant.

    Args:
        universe_df: Barres OHLCV de tout l'univers.
        artifacts_dir: Répertoire contenant ``_global_ranking_features.json``.
        benchmark_df: Barres du benchmark (SPY).
        engine: SQLAlchemy engine (requis pour les features sector-neutral).

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
        _feature_set: str = _meta.get("feature_set", "expert")
        _include_cross_sectional: bool = _meta.get("enable_cross_sectional", True)
        # Features spécifiques par horizon (post feature selection)
        _horizon_features_meta: dict[str, list[str]] = _meta.get("horizon_features", {})
    except Exception as exc:
        LOGGER.warning("predict_global_rank: failed to load features metadata: %s", exc)
        return None

    # ── Construire les features (communes à tous les horizons) ──
    from modelFactory.cross_sectional import build_cross_sectional_features, merge_cross_sectional_features
    cross_sectional_df: pd.DataFrame | None = None
    if _include_cross_sectional:
        cross_sectional_df, _cs_diag = build_cross_sectional_features(
            universe_df, benchmark_df=benchmark_df, min_universe_size=5,
        )

    # Extraire les flags include_* du metadata pour reproduire le feature set d'entraînement
    _include_kwargs: dict[str, Any] = {
        "feature_set": _feature_set,
        "include_sentiment": _meta.get("include_sentiment", False),
        "include_screener_scores": _meta.get("include_screener_scores", False),
        "include_short_score": _meta.get("include_short_score", False),
        "include_macro_vix": _meta.get("include_macro_vix", False),
        "include_macro_vxn": _meta.get("include_macro_vxn", False),
        "include_macro_vix3m": _meta.get("include_macro_vix3m", False),
        "include_macro_move": _meta.get("include_macro_move", False),
        "include_fundamentals": _meta.get("include_fundamentals", False),
        "include_factors": _meta.get("include_factors", False),
        "include_macro_regime": _meta.get("include_macro_regime", False),
    }

    frames: list[pd.DataFrame] = []
    symbols = sorted(universe_df["symbol"].unique())
    for sym in symbols:
        try:
            sym_bars = universe_df[universe_df["symbol"] == sym].copy()
            if sym_bars.empty or len(sym_bars) < 20:
                continue
            sym_bars = sym_bars.sort_values("date")
            sym_df = compute_features(sym_bars, benchmark_df=benchmark_df, **_include_kwargs)
            if sym_df.empty:
                continue
            if cross_sectional_df is not None and not cross_sectional_df.empty:
                sym_cross = cross_sectional_df[cross_sectional_df["symbol"] == sym].copy()
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

    # ── Normalisation cross-sectionnelle des features (identique à l'entraînement) ──
    _xs_available = [s for s in _XS_RANK_SOURCE_FEATURES if s in pred_df.columns]
    if _xs_available:
        _xs_ranked = pred_df.groupby("date")[_xs_available].rank(pct=True).astype(np.float64)
        _xs_ranked.columns = [_xs_rank_column_name(c) for c in _xs_available]
        for _col in _xs_ranked.columns:
            pred_df[_col] = _xs_ranked[_col]
        # Remplir les colonnes _xs_rank manquantes dans feature_columns
        for _src in _xs_available:
            _xsc = _xs_rank_column_name(_src)
            if _xsc not in pred_df.columns:
                pred_df[_xsc] = 0.5

    # Remplir les colonnes _xs_rank absentes (ex: feature non calculable)
    for col in _feature_columns:
        if col not in pred_df.columns:
            pred_df[col] = 0.5 if col.endswith("_rank") or col.startswith("global_rank") else 0.0

    # ── Sector-neutral features (parité entraînement/prédiction) ──
    _sn_cols_in = [c for c in SECTOR_NEUTRAL_FEATURE_COLUMNS if c in _feature_columns]
    if _sn_cols_in and engine is not None:
        _compute_sector_neutral_inplace(pred_df, _feature_columns, engine)

    X = pred_df[_feature_columns]
    if X.shape[1] != len(_feature_columns):
        LOGGER.warning("predict_global_rank: feature mismatch expected=%d got=%d", len(_feature_columns), X.shape[1])
        return None

    # ── Prédire pour chaque horizon ──
    result = pred_df[["symbol", "date"]].copy()
    for horizon in _horizons:
        h_suffix = f"_{horizon}"
        # Utiliser les features spécifiques à cet horizon (post feature selection)
        _hf = _horizon_features_meta.get(str(horizon), _feature_columns)
        _hf = [c for c in _hf if c in pred_df.columns]  # garder seulement celles disponibles
        if not _hf:
            LOGGER.warning("predict_global_rank: no features for horizon %d", horizon)
            result[f"global_rank{h_suffix}"] = 0.5
            continue
        X_h = pred_df[_hf].to_numpy(dtype=np.float64)

        # ── Charger le modèle pour cet horizon ──
        # Le type est déterminé par l'extension du fichier :
        #   .txt = LightGBM, .pkl = CatBoost
        # En mode champion, chaque horizon a UN seul fichier (le champion).
        # En mode simple, idem (le backend configuré).
        _model_path_txt = artifacts_dir / f"_global_ranking_model{h_suffix}.txt"
        _model_path_pkl = artifacts_dir / f"_global_ranking_model{h_suffix}.pkl"
        if _model_path_txt.exists():
            _model_path = _model_path_txt
            _load_as_catboost = False
        elif _model_path_pkl.exists():
            _model_path = _model_path_pkl
            _load_as_catboost = True
        else:
            LOGGER.warning("predict_global_rank: model for horizon %d not found", horizon)
            result[f"global_rank{h_suffix}"] = 0.5
            continue
        try:
            if _load_as_catboost:
                CatBoostRegressor = _import_catboost()
                model = CatBoostRegressor()
                model.load_model(str(_model_path))
            else:
                lgb = _import_lightgbm()
                model = lgb.Booster(model_file=str(_model_path))
            raw_scores = model.predict(X_h).astype(np.float64)
            # Scores continus → rank pct par date pour normaliser [0,1]
            temp = pd.DataFrame({"date": result["date"].values, "score": raw_scores})
            result[f"global_rank{h_suffix}"] = (
                temp.groupby("date")["score"].rank(pct=True).clip(0.0, 1.0).values.astype(np.float64)
            )
        except Exception as exc:
            LOGGER.warning("predict_global_rank: prediction failed for h=%d: %s", horizon, exc)
            result[f"global_rank{h_suffix}"] = 0.5

    LOGGER.info("predict_global_rank: predicted %d symbols for horizons %s", len(result), _horizons)
    return result
