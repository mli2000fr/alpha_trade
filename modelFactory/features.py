"""modelFactory/features.py — Feature engineering à partir de stock_bars_daily."""
from __future__ import annotations

import hashlib
import json
import logging

import numpy as np
import pandas as pd


LOGGER = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Liste ordonnée des features V1 (dérivées de OHLCV uniquement)
# -------------------------------------------------------------------------
FEATURE_COLUMNS: list[str] = [
    "daily_return",
    "log_return",
    "intraday_range",
    "overnight_gap",
    "close_to_vwap",
    "volume_ratio_20",
    "rolling_volatility_20",
    "rolling_volatility_60",
    "rolling_mean_return_5",
    "rolling_mean_return_20",
    "rsi_14",
    "atr_14_norm",
    "is_filled",
]

EXPERT_FEATURE_COLUMNS: list[str] = [
    "sma20_distance",
    "sma50_distance",
    "sma100_distance",
    "sma200_distance",
    "ema20_distance",
    "ema50_distance",
    "momentum_10",
    "momentum_20",
    "momentum_60",
    "vol_ratio_20_60",
    "range_position_20",
    "market_return_20",
    "market_volatility_20",
    "market_trend_strength_50",
    "relative_strength_20",
    "relative_strength_60",
    "regime_bull_market",
    "regime_risk_off",
]

# Features sentiment auxiliaires (depuis ticker_daily_sentiment_features)
SENTIMENT_FEATURE_COLUMNS: list[str] = [
    "sentiment_net_mean_1d",
    "sentiment_confidence_mean_1d",
    "news_count_log",
    "major_event_flag",
    "sentiment_intensity",  # direction × confiance × volume (2026-07-29)
]

# Features d'interaction régime × technique (Cause 3 — changement de régime)
# Calculées uniquement quand feature_set="expert" et benchmark_df dispo.
REGIME_INTERACTION_FEATURES: list[str] = [
    "momentum_20_x_bull",
    "momentum_20_x_risk_off",
    "momentum_60_x_bull",
    "momentum_60_x_risk_off",
    "relative_strength_20_x_bull",
    "relative_strength_20_x_risk_off",
    "relative_strength_60_x_bull",
    "relative_strength_60_x_risk_off",
    "rolling_volatility_20_x_bull",
    "rolling_volatility_20_x_risk_off",
    "vol_ratio_20_60_x_bull",
    "vol_ratio_20_60_x_risk_off",
    "rsi_14_x_bull",
    "rsi_14_x_risk_off",
    "sma20_distance_x_bull",
    "sma20_distance_x_risk_off",
    "sma50_distance_x_bull",
    "sma50_distance_x_risk_off",
]

# ── Sprint 2026-07-25 : Features multi-horizons, interactions techniques, z-score ──

MULTI_HORIZON_FEATURES: list[str] = [
    "momentum_3",
    "momentum_5",
    "momentum_120",
    "momentum_250",
    "rolling_volatility_5",
    "rolling_volatility_10",
    "rolling_volatility_120",
    "sma10_distance",
    "sma250_distance",
    "rsi_2",
    "rsi_3",
    "rsi_5",
    "rsi_21",
    "dist_to_sma_5d",
    "volume_zscore_5d",
    "volume_ratio_5",
    "zscore_close_vs_ma10",
]

INTERACTION_FEATURES: list[str] = [
    "momentum_20_div_vol_20",
    "momentum_60_div_vol_60",
    "momentum_5_minus_momentum_20",
    "momentum_20_minus_momentum_60",
    "volume_ratio_5_div_volume_ratio_20",
    "rsi_14_times_volume_ratio_20",
    "rsi_14_div_volatility_20",
    "sma20_minus_sma50",
    "sma50_minus_sma200",
    "ema20_minus_sma20",
    "intraday_range_div_atr_14",
    "range_position_20_times_vol_ratio_20_60",
    "daily_return_times_volume_ratio_20",
    "log_return_div_intraday_range",
    "relative_strength_20_times_market_trend",
    "relative_strength_60_div_market_volatility",
]

# ── Sprint 2026-07-26 : Features de dynamique temporelle (Niveau 3) ──
# Vitesse, accélération et convexité des indicateurs. Ces features sont
# non-linéaires/non-monotones → les arbres ne peuvent pas les inférer de
# features statiques. Capturent la « dérivée seconde » du signal.
TEMPORAL_DYNAMICS_FEATURES: list[str] = [
    "accel_3_5",         # momentum_5 / momentum_3 − 1  (accélération court-terme)
    "decay_5_10",        # momentum_10 / momentum_5 − 1 (essoufflement du momentum)
    "rsi_slope",         # rsi_3 − rsi_14              (vitesse de changement du RSI)
    "vol_expansion",     # vol_5 / vol_20 − 1          (explosion de volatilité)
    "meanrev_signal",    # dist_to_sma_5d − sma20_distance (tension de réversion)
    "gap_fade",          # overnight_gap × (1 − |rsi_3−50|/50) (gap conditionnel)
]

# ── Sprint 2026-07-25 : Z-score rolling (normalisation temporelle) ──
# Chaque feature transformée en z-score sur fenêtre glissante 5 ans (1260j, min_periods=252j).
# Rend les features comparables dans le temps, indépendamment du régime de marché.

ZSCORE_SOURCE_FEATURES: list[str] = [
    "momentum_5", "momentum_10", "momentum_20", "momentum_60", "momentum_120", "momentum_250",
    "rolling_volatility_5", "rolling_volatility_10", "rolling_volatility_20", "rolling_volatility_60", "rolling_volatility_120",
    "rsi_5", "rsi_14", "rsi_21",
    "sma10_distance", "sma20_distance", "sma50_distance", "sma100_distance", "sma200_distance", "sma250_distance",
    "volume_ratio_20",
    "intraday_range",
]

def _zscore_column_name(source_col: str) -> str:
    return f"{source_col}_zscore"

ZSCORE_FEATURE_COLUMNS: list[str] = [_zscore_column_name(c) for c in ZSCORE_SOURCE_FEATURES]

# ── P3-5 (2026-08-14) : profil volume / liquidité ──
# Famille opt-in (`--include-volume-features`) — jamais testée jusqu'ici.
# Profondeur de marché, impact de marché, confirmation prix/volume.
VOLUME_LIQUIDITY_FEATURE_COLUMNS: list[str] = [
    "dollar_volume_log_20",      # log(volume × close) moy 20j — profondeur de marché
    "dollar_volume_trend_20_60", # dv20 / dv60 − 1 — tendance de liquidité
    "amihud_illiq_20",           # |ret| / dollar_volume moy 20j — impact de marché (Amihud)
    "volume_std_ratio_20",       # std(volume) / mean(volume) 20j — stabilité du flux
    "up_volume_ratio_20",        # part du volume des jours haussiers 20j — pression acheteuse
    "volume_price_corr_20",      # corr(ret, volume) 20j — confirmation des mouvements
    "obv_slope_20",              # pente OBV normalisée 20j — accumulation/distribution
    "dollar_volume_zscore_20",   # z-score du dollar volume 20j — pic de liquidité
    "high_low_range_20",         # (high−low)/close moy 20j — liquidité intrinsèque
    "volume_skew_20",            # skewness du volume 20j — journées extrêmes
]

# ── Sprint 2026-07-26 : Indicateurs de régime macro (SPY + VIX) ──
MACRO_REGIME_FEATURE_COLUMNS: list[str] = [
    "SPY_SMA_200_slope",
    "VIX_zscore",
]

# ── Sprint 2026-07-26 : Interactions global_rank × features locales ──
RANK_INTERACTION_FEATURES: list[str] = [
    "rank_x_rsi_14",
    "rank_x_momentum_20",
    "rank_x_momentum_60",
    "rank_x_volatility_20",
    "rank_x_sma20_distance",
    "rank_acceleration",  # global_rank_3 - global_rank_10 (vitesse du rang)
]

# Features macro contextuelles (depuis stock_macro_indicators_daily)
MACRO_FEATURE_COLUMNS: list[str] = [
    "vix_close",
    "vix_momentum_5j",
    "vxn_close",
    "vxn_spread_vix",
    "vix3m_close",
    "vix_term_structure_ratio",
    "vix_backwardation",
    "move_close",
]

SELECTOR_CONTEXT_FEATURE_COLUMNS: list[str] = [
    "selector_trend_score",
    "selector_vcp_score",
    "selector_final_score",
    "selector_raw_final_score",
    "selector_selection_rank",
    "selector_atr_pct_20",
    "selector_weekly_trend_score",
    "selector_high_52w_proximity",
    "selector_volatility_ratio",
    "selector_earnings_blackout",
    "selector_mode_sector_neutralized",
    # Nouvelles features — backfill PIT enrichi (Sprint S7)
    "selector_market_cap",
    "selector_beta_126",
    "selector_spread_bps",
    "selector_days_to_earnings",
    "selector_normalized_total_score",
    "selector_normalized_rsi",
    "selector_total_score_neutralized",
    "selector_relative_strength_index_neutralized",
    "selector_trend_vcp_component",
    "selector_total_score_component",
    "selector_rsi_component",
    "selector_short_score",
]

# ── Composants de score issus de stock_scores_history ──
# P0-6 (2026-08-07) : signal orthogonal aux features techniques.
# Applicable per-sector + global, désactivé par défaut sur per-symbol.
SCORE_COMPONENT_FEATURE_COLUMNS: list[str] = [
    "sentiment_net_agg",
    "company_idio_score",
    "macro_regime_score",
    "quant_component",
    "company_idio_signal_norm",
    "macro_regime_signal_norm",
    "company_idio_component",
    "macro_regime_component",
    "sector_impact_agg",
]

_SELECTOR_CONTEXT_SOURCE_TO_FEATURE = {
    "trend_score": "selector_trend_score",
    "vcp_score": "selector_vcp_score",
    "final_score": "selector_final_score",
    "raw_final_score": "selector_raw_final_score",
    "selection_rank": "selector_selection_rank",
    "atr_pct_20": "selector_atr_pct_20",
    "weekly_trend_score": "selector_weekly_trend_score",
    "high_52w_proximity": "selector_high_52w_proximity",
    "volatility_ratio": "selector_volatility_ratio",
    "earnings_blackout": "selector_earnings_blackout",
    # Nouvelles colonnes — backfill PIT enrichi (Sprint S7)
    "market_cap": "selector_market_cap",
    "beta_126": "selector_beta_126",
    "spread_bps": "selector_spread_bps",
    "days_to_earnings": "selector_days_to_earnings",
    "normalized_total_score": "selector_normalized_total_score",
    "normalized_rsi": "selector_normalized_rsi",
    "total_score_neutralized": "selector_total_score_neutralized",
    "relative_strength_index_neutralized": "selector_relative_strength_index_neutralized",
    "trend_vcp_component": "selector_trend_vcp_component",
    "total_score_component": "selector_total_score_component",
    "rsi_component": "selector_rsi_component",
    "short_score": "selector_short_score",
    # ── Score components (P0-6, 2026-08-08) — identité DB→feature ──
    "sentiment_net_agg": "sentiment_net_agg",
    "company_idio_score": "company_idio_score",
    "macro_regime_score": "macro_regime_score",
    "quant_component": "quant_component",
    "company_idio_signal_norm": "company_idio_signal_norm",
    "macro_regime_signal_norm": "macro_regime_signal_norm",
    "company_idio_component": "company_idio_component",
    "macro_regime_component": "macro_regime_component",
    "sector_impact_agg": "sector_impact_agg",
}

_SELECTOR_CONTEXT_DEFAULTS = {
    "selector_trend_score": 0.0,
    "selector_vcp_score": 0.0,
    "selector_final_score": 0.0,
    "selector_raw_final_score": 0.0,
    "selector_selection_rank": 0.0,
    "selector_atr_pct_20": 0.0,
    "selector_weekly_trend_score": 0.0,
    "selector_high_52w_proximity": 0.0,
    "selector_volatility_ratio": 0.0,
    "selector_earnings_blackout": 0.0,
    "selector_mode_sector_neutralized": 0.0,
    # Nouvelles features — backfill PIT enrichi (Sprint S7)
    "selector_market_cap": 0.0,
    "selector_beta_126": 0.0,
    "selector_spread_bps": 0.0,
    "selector_days_to_earnings": 0.0,
    "selector_normalized_total_score": 0.0,
    "selector_normalized_rsi": 0.0,
    "selector_total_score_neutralized": 0.0,
    "selector_relative_strength_index_neutralized": 0.0,
    "selector_trend_vcp_component": 0.0,
    "selector_total_score_component": 0.0,
    "selector_rsi_component": 0.0,
    "selector_short_score": 0.0,
    # ── Score components (P0-6, 2026-08-08) ──
    "sentiment_net_agg": 0.0,
    "company_idio_score": 0.0,
    "macro_regime_score": 0.0,
    "quant_component": 0.0,
    "company_idio_signal_norm": 0.0,
    "macro_regime_signal_norm": 0.0,
    "company_idio_component": 0.0,
    "macro_regime_component": 0.0,
    "sector_impact_agg": 0.0,
}


def get_feature_columns(
    include_sentiment: bool = False,
    feature_set: str = "v1",
    include_cross_sectional: bool = False,
    include_screener_scores: bool = False,
    include_short_score: bool = False,
    include_macro_vix: bool = False,
    include_macro_vxn: bool = False,
    include_macro_vix3m: bool = False,
    include_macro_move: bool = False,
    include_global_stacking: bool = False,
    include_fundamentals: bool = False,
    include_factors: bool = False,
    include_macro_regime: bool = False,
    include_score_components: bool = False,
    include_volume_features: bool = False,
) -> list[str]:
    """Retourne la liste complète des colonnes features (OHLCV + optionnels).

    ``include_cross_sectional`` active à la fois les rangs percentiles
    cross-sectionnels ET les features sectorielles dynamiques (momentum,
    volatilité, alpha intra-secteur).

    ``include_global_stacking`` (Approche 2) ajoute ``global_rank``
    (rang percentil du Global Ranking Model) comme feature.

    ``include_fundamentals`` ajoute les features fondamentales
    (PE, ROE, marges, croissance, etc.) depuis stock_fundamentals_daily.

    ``include_factors`` ajoute les expositions factorielles CAPM
    (beta, alpha, R²) calculées par rolling regression 252j.

    ``include_score_components`` (P0-6) ajoute les composants de score
    issus de ``stock_scores_history`` (sentiment_net_agg, company_idio_score,
    macro_regime_score, etc.). Applicable per-sector + global, désactivé
    par défaut sur per-symbol.
    """
    cols = list(FEATURE_COLUMNS)
    if feature_set == "expert":
        cols.extend(EXPERT_FEATURE_COLUMNS)
    if include_cross_sectional:
        from modelFactory.cross_sectional import CROSS_SECTIONAL_FEATURE_COLUMNS, SECTOR_FEATURE_COLUMNS, SECTOR_NEUTRAL_FEATURE_COLUMNS, SECTOR_ZSCORE_FEATURE_COLUMNS

        cols.extend(CROSS_SECTIONAL_FEATURE_COLUMNS)
        cols.extend(SECTOR_FEATURE_COLUMNS)
        cols.extend(SECTOR_NEUTRAL_FEATURE_COLUMNS)
        cols.extend(SECTOR_ZSCORE_FEATURE_COLUMNS)
    # ── Global stacking : indépendant de include_cross_sectional ──
    # Le global_rank est une feature à part entière, pas une feature XS.
    # Il doit être disponible même sans --enable-cross-sectional.
    if include_global_stacking:
        from modelFactory.cross_sectional import GLOBAL_PRED_FEATURE_COLUMNS

        cols.extend(GLOBAL_PRED_FEATURE_COLUMNS)
        # Interactions global_rank × features locales
        cols.extend(RANK_INTERACTION_FEATURES)
    if include_sentiment:
        cols.extend(SENTIMENT_FEATURE_COLUMNS)
    if include_screener_scores:
        cols.extend(SELECTOR_CONTEXT_FEATURE_COLUMNS)
    if include_short_score and "selector_short_score" not in cols:
        cols.append("selector_short_score")
    # Macro features — ajoutées après les features OHLCV pour préserver l'ordre canonique
    if include_macro_vix:
        for col in ["vix_close", "vix_momentum_5j"]:
            if col not in cols:
                cols.append(col)
    if include_macro_vxn:
        for col in ["vxn_close", "vxn_spread_vix"]:
            if col not in cols:
                cols.append(col)
    if include_macro_vix3m:
        for col in ["vix3m_close", "vix_term_structure_ratio", "vix_backwardation"]:
            if col not in cols:
                cols.append(col)
    if include_macro_move:
        if "move_close" not in cols:
            cols.append("move_close")
    # Interaction régime × technique — ajoutées après les features expert
    if feature_set == "expert":
        cols.extend(REGIME_INTERACTION_FEATURES)
        cols.extend(MULTI_HORIZON_FEATURES)
        cols.extend(INTERACTION_FEATURES)
        cols.extend(TEMPORAL_DYNAMICS_FEATURES)
        cols.extend(ZSCORE_FEATURE_COLUMNS)
    if include_fundamentals:
        from modelFactory.fundamental_features import FUNDAMENTAL_FEATURE_COLUMNS
        cols.extend(FUNDAMENTAL_FEATURE_COLUMNS)
    if include_factors:
        from modelFactory.factor_features import FACTOR_FEATURE_COLUMNS
        cols.extend(FACTOR_FEATURE_COLUMNS)
    if include_macro_regime:
        cols.extend(MACRO_REGIME_FEATURE_COLUMNS)
    if include_score_components:
        cols.extend(SCORE_COMPONENT_FEATURE_COLUMNS)
    if include_volume_features:
        cols.extend(VOLUME_LIQUIDITY_FEATURE_COLUMNS)
    return cols


def fingerprint(
    *,
    include_sentiment: bool = False,
    feature_set: str = "v1",
    include_cross_sectional: bool = False,
    include_screener_scores: bool = False,
    include_short_score: bool = False,
    include_macro_vix: bool = False,
    include_macro_vxn: bool = False,
    include_macro_vix3m: bool = False,
    include_macro_move: bool = False,
    include_global_stacking: bool = False,
    include_fundamentals: bool = False,
    include_factors: bool = False,
    include_macro_regime: bool = False,
    include_score_components: bool = False,
    include_volume_features: bool = False,
    feature_columns: list[str] | None = None,
) -> str:
    """SHA256[:16] du contrat de features actif (Phase 4.2.b).

    Persisté dans ``config.json`` du modèle ; recalculé à l'inférence
    pour détecter toute dérive silencieuse du contrat de features
    (la valeur **doit** rester stable tant que la liste de colonnes ne
    change pas — un test gold bloque les modifications accidentelles).
    """
    columns = list(feature_columns or get_feature_columns(
        include_sentiment=include_sentiment,
        feature_set=feature_set,
        include_cross_sectional=include_cross_sectional,
        include_screener_scores=include_screener_scores,
        include_short_score=include_short_score,
        include_macro_vix=include_macro_vix,
        include_macro_vxn=include_macro_vxn,
        include_macro_vix3m=include_macro_vix3m,
        include_macro_move=include_macro_move,
        include_global_stacking=include_global_stacking,
        include_fundamentals=include_fundamentals,
        include_factors=include_factors,
        include_macro_regime=include_macro_regime,
        include_score_components=include_score_components,
        include_volume_features=include_volume_features,
    ))
    payload = {
        "columns": columns,
        "feature_set": feature_set,
        "include_sentiment": bool(include_sentiment),
        "include_cross_sectional": bool(include_cross_sectional),
        "include_screener_scores": bool(include_screener_scores),
        "include_short_score": bool(include_short_score),
        "include_macro_vix": bool(include_macro_vix),
        "include_macro_vxn": bool(include_macro_vxn),
        "include_macro_vix3m": bool(include_macro_vix3m),
        "include_macro_move": bool(include_macro_move),
        "include_global_stacking": bool(include_global_stacking),
        "include_fundamentals": bool(include_fundamentals),
        "include_factors": bool(include_factors),
        "include_macro_regime": bool(include_macro_regime),
        "include_score_components": bool(include_score_components),
        "include_volume_features": bool(include_volume_features),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def normalize_feature_columns(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        return None
    normalized = [str(column) for column in value]
    return normalized or None


def build_feature_contract(
    *,
    include_sentiment: bool = False,
    feature_set: str = "v1",
    include_cross_sectional: bool = False,
    include_screener_scores: bool = False,
    include_short_score: bool = False,
    include_macro_vix: bool = False,
    include_macro_vxn: bool = False,
    include_macro_vix3m: bool = False,
    include_macro_move: bool = False,
    include_global_stacking: bool = False,
    include_fundamentals: bool = False,
    include_factors: bool = False,
    include_macro_regime: bool = False,
    include_score_components: bool = False,
    feature_columns: list[str] | None = None,
    scaler_feature_names: list[str] | None = None,
) -> dict[str, object]:
    """Construit le manifeste persistant du contrat de features."""
    resolved_columns = list(feature_columns or get_feature_columns(
        include_sentiment=include_sentiment,
        feature_set=feature_set,
        include_cross_sectional=include_cross_sectional,
        include_screener_scores=include_screener_scores,
        include_short_score=include_short_score,
        include_macro_vix=include_macro_vix,
        include_macro_vxn=include_macro_vxn,
        include_macro_vix3m=include_macro_vix3m,
        include_macro_move=include_macro_move,
        include_global_stacking=include_global_stacking,
        include_fundamentals=include_fundamentals,
        include_factors=include_factors,
        include_macro_regime=include_macro_regime,
        include_score_components=include_score_components,
    ))
    contract: dict[str, object] = {
        "schema_version": 1,
        "feature_columns": resolved_columns,
        "feature_count": len(resolved_columns),
        "feature_fingerprint": fingerprint(
            include_sentiment=include_sentiment,
            feature_set=feature_set,
            include_cross_sectional=include_cross_sectional,
            include_screener_scores=include_screener_scores,
            include_short_score=include_short_score,
            include_macro_vix=include_macro_vix,
            include_macro_vxn=include_macro_vxn,
            include_macro_vix3m=include_macro_vix3m,
            include_macro_move=include_macro_move,
            include_global_stacking=include_global_stacking,
            include_fundamentals=include_fundamentals,
            include_factors=include_factors,
            include_macro_regime=include_macro_regime,
            include_score_components=include_score_components,
            feature_columns=resolved_columns,
        ),
        "require_exact_order": True,
        "allow_extra_runtime_columns": True,
    }
    if scaler_feature_names is not None:
        contract["scaler_feature_names"] = list(scaler_feature_names)
    return contract


def validate_feature_contract(
    contract_payload: object,
    *,
    include_sentiment: bool = False,
    feature_set: str = "v1",
    include_cross_sectional: bool = False,
    include_screener_scores: bool = False,
    include_short_score: bool = False,
    include_macro_vix: bool = False,
    include_macro_vxn: bool = False,
    include_macro_vix3m: bool = False,
    include_macro_move: bool = False,
    include_global_stacking: bool = False,
    include_fundamentals: bool = False,
    include_factors: bool = False,
    include_macro_regime: bool = False,
    include_score_components: bool = False,
    persisted_feature_columns: object = None,
    persisted_feature_fingerprint: object = None,
    scaler_feature_names: object = None,
    route_feature_columns: object = None,
    route_feature_fingerprint: object = None,
    runtime_feature_columns: object = None,
    allow_legacy_missing_contract: bool = False,
) -> str | None:
    expected_columns = get_feature_columns(
        include_sentiment=include_sentiment,
        feature_set=feature_set,
        include_cross_sectional=include_cross_sectional,
        include_screener_scores=include_screener_scores,
        include_short_score=include_short_score,
        include_macro_vix=include_macro_vix,
        include_macro_vxn=include_macro_vxn,
        include_macro_vix3m=include_macro_vix3m,
        include_macro_move=include_macro_move,
        include_global_stacking=include_global_stacking,
        include_fundamentals=include_fundamentals,
        include_factors=include_factors,
        include_macro_regime=include_macro_regime,
        include_score_components=include_score_components,
    )
    contract = contract_payload if isinstance(contract_payload, dict) else None
    contract_columns = normalize_feature_columns(contract.get("feature_columns")) if contract is not None else None
    contract_fingerprint = str(contract.get("feature_fingerprint") or "").strip() if contract is not None else ""

    # P0-4 (2026-08-06) : "symbol" est ajouté post-hoc comme feature
    # catégorielle pour les modèles tabulaires per-sector. Il n'est pas
    # listé par get_feature_columns() mais fait partie du contrat légitime.
    if contract_columns is not None and "symbol" in contract_columns and "symbol" not in expected_columns:
        expected_columns = list(expected_columns) + ["symbol"]

    expected_fingerprint = fingerprint(
        include_sentiment=include_sentiment,
        feature_set=feature_set,
        include_cross_sectional=include_cross_sectional,
        include_screener_scores=include_screener_scores,
        include_short_score=include_short_score,
        include_macro_vix=include_macro_vix,
        include_macro_vxn=include_macro_vxn,
        include_macro_vix3m=include_macro_vix3m,
        include_macro_move=include_macro_move,
        include_global_stacking=include_global_stacking,
        include_fundamentals=include_fundamentals,
        include_factors=include_factors,
        include_macro_regime=include_macro_regime,
        include_score_components=include_score_components,
        feature_columns=expected_columns,
    )

    if contract is None:
        if not allow_legacy_missing_contract:
            return "feature_contract_missing"
        contract_columns = (
            normalize_feature_columns(persisted_feature_columns)
            or normalize_feature_columns(route_feature_columns)
            or normalize_feature_columns(scaler_feature_names)
            or list(expected_columns)
        )
        contract_fingerprint = fingerprint(
            include_sentiment=include_sentiment,
            feature_set=feature_set,
            include_cross_sectional=include_cross_sectional,
            include_screener_scores=include_screener_scores,
            include_short_score=include_short_score,
            include_macro_vix=include_macro_vix,
            include_macro_vxn=include_macro_vxn,
            include_macro_vix3m=include_macro_vix3m,
            include_macro_move=include_macro_move,
            include_global_stacking=include_global_stacking,
            include_fundamentals=include_fundamentals,
            include_factors=include_factors,
            include_macro_regime=include_macro_regime,
            include_score_components=include_score_components,
            feature_columns=contract_columns,
        )
    else:
        if contract_columns is None:
            return "feature_contract_columns_missing"
        if contract_columns != list(expected_columns):
            return (
                "feature_contract_columns_mismatch "
                f"persisted={contract_columns} expected={expected_columns}"
            )
        if not contract_fingerprint:
            return "feature_contract_fingerprint_missing"
        if contract_fingerprint != expected_fingerprint:
            return (
                "feature_contract_fingerprint_mismatch "
                f"persisted={contract_fingerprint} expected={expected_fingerprint}"
            )
        scaler_names_in_contract = normalize_feature_columns(contract.get("scaler_feature_names"))
        if scaler_names_in_contract is not None and scaler_names_in_contract != contract_columns:
            return (
                "feature_contract_scaler_names_mismatch "
                f"persisted={scaler_names_in_contract} expected={contract_columns}"
            )

    persisted_columns_normalized = normalize_feature_columns(persisted_feature_columns)
    if persisted_columns_normalized is not None and persisted_columns_normalized != contract_columns:
        return (
            "feature_columns_mismatch "
            f"persisted={persisted_columns_normalized} expected={contract_columns}"
        )

    persisted_fp_normalized = str(persisted_feature_fingerprint or "").strip()
    if persisted_fp_normalized and persisted_fp_normalized != contract_fingerprint:
        return (
            "feature_fingerprint_mismatch "
            f"persisted={persisted_fp_normalized} expected={contract_fingerprint}"
        )

    scaler_feature_names_normalized = normalize_feature_columns(scaler_feature_names)
    if scaler_feature_names_normalized is not None and scaler_feature_names_normalized != contract_columns:
        return (
            "scaler_feature_columns_mismatch "
            f"persisted={scaler_feature_names_normalized} expected={contract_columns}"
        )

    route_feature_columns_normalized = normalize_feature_columns(route_feature_columns)
    if route_feature_columns_normalized is not None and route_feature_columns_normalized != contract_columns:
        return (
            "route_feature_columns_mismatch "
            f"persisted={route_feature_columns_normalized} expected={contract_columns}"
        )

    route_fp_normalized = str(route_feature_fingerprint or "").strip()
    if route_fp_normalized and route_fp_normalized != contract_fingerprint:
        return (
            "route_feature_fingerprint_mismatch "
            f"persisted={route_fp_normalized} expected={contract_fingerprint}"
        )

    runtime_feature_columns_normalized = normalize_feature_columns(runtime_feature_columns)
    if runtime_feature_columns_normalized is not None:
        missing_columns = [column for column in contract_columns if column not in runtime_feature_columns_normalized]
        if missing_columns:
            return (
                "runtime_feature_columns_missing "
                f"missing={missing_columns} expected={contract_columns}"
            )

    return None


def _merge_macro_features(
    df: pd.DataFrame,
    *,
    include_vix: bool = False,
    include_vxn: bool = False,
    include_vix3m: bool = False,
    include_move: bool = False,
) -> pd.DataFrame:
    """Charge les indicateurs macro depuis ``stock_macro_indicators_daily`` et les fusionne sur ``date``.

    Les features dérivées :
    - ``vix_close``, ``vix_momentum_5j`` (VIX)
    - ``vxn_close``, ``vxn_spread_vix`` (VXN)
    - ``vix3m_close``, ``vix_term_structure_ratio``, ``vix_backwardation`` (VIX3M)
    - ``move_close`` (MOVE)

    La table macro est chargée une fois, forward-filled, puis mergée left sur ``date``.
    Les dates sans données macro reçoivent la dernière valeur connue (ffill).
    """
    if not {"date"}.issubset(df.columns):
        return df

    requested_columns: set[str] = set()
    if include_vix:
        requested_columns.update({"vix"})
    if include_vxn:
        requested_columns.update({"vxn"})
    if include_vix3m:
        requested_columns.update({"vix", "vix3m"})
    if include_move:
        requested_columns.update({"move"})
    if not requested_columns:
        return df

    try:
        from sqlalchemy import select as _sa_select
        from database.connection import get_sqlalchemy_engine
        from database.macro_indicators import get_macro_indicators_daily_table

        engine = get_sqlalchemy_engine()
        table = get_macro_indicators_daily_table()

        date_min = pd.to_datetime(df["date"].min()) - pd.Timedelta(days=30)
        date_max = pd.to_datetime(df["date"].max())

        db_columns = [table.c.trade_date] + [
            getattr(table.c, col) for col in sorted(requested_columns)
        ]
        query = (
            _sa_select(*db_columns)
            .where(table.c.trade_date >= date_min.date())
            .where(table.c.trade_date <= date_max.date())
            .order_by(table.c.trade_date.asc())
        )
        with engine.connect() as conn:
            macro_rows = pd.read_sql_query(query, conn)

        if macro_rows.empty:
            LOGGER.warning("_merge_macro_features: no macro data in range %s → %s, filling 0", date_min, date_max)
            _fill_macro_defaults(df, include_vix, include_vxn, include_vix3m, include_move)
            return df

        macro = macro_rows.rename(columns={"trade_date": "date"})
        macro["date"] = pd.to_datetime(macro["date"])

        # Construire une grille journalière complète et forward-fill
        full_dates = pd.date_range(macro["date"].min(), macro["date"].max(), freq="D")
        grid = pd.DataFrame({"date": full_dates})
        macro = grid.merge(macro, on="date", how="left")
        macro = macro.sort_values("date").ffill().reset_index(drop=True)

        # Features dérivées VIX
        if include_vix and "vix" in macro.columns:
            macro["vix_close"] = macro["vix"].astype(float)
            macro["vix_momentum_5j"] = macro["vix_close"].pct_change(5).fillna(0.0)

        # Features dérivées VXN
        if include_vxn and "vxn" in macro.columns:
            macro["vxn_close"] = macro["vxn"].astype(float)
            vix_series = macro["vix"].astype(float) if "vix" in macro.columns else macro["vxn_close"]
            macro["vxn_spread_vix"] = macro["vxn_close"] - vix_series

        # Features dérivées VIX3M
        if include_vix3m and "vix3m" in macro.columns and "vix" in macro.columns:
            macro["vix3m_close"] = macro["vix3m"].astype(float)
            macro["vix_term_structure_ratio"] = (
                macro["vix"].astype(float) / macro["vix3m"].astype(float).clip(lower=1e-8)
            ).fillna(1.0)
            macro["vix_backwardation"] = (
                macro["vix"].astype(float) > macro["vix3m"].astype(float)
            ).astype(float)

        # Features dérivées MOVE
        if include_move and "move" in macro.columns:
            macro["move_close"] = macro["move"].astype(float)

        # Merge sur date (left join → forward-fill les jours sans macro)
        keep_cols = ["date"] + [
            c for c in [
                "vix_close", "vix_momentum_5j",
                "vxn_close", "vxn_spread_vix",
                "vix3m_close", "vix_term_structure_ratio", "vix_backwardation",
                "move_close",
            ] if c in macro.columns
        ]
        macro = macro[keep_cols]
        df["date"] = pd.to_datetime(df["date"])
        df = df.merge(macro, on="date", how="left")
        df = df.sort_values("date").reset_index(drop=True)

        # Forward-fill les NaN macro (les weekends / jours fériés)
        macro_cols = [c for c in keep_cols if c != "date" and c in df.columns]
        df[macro_cols] = df[macro_cols].ffill().fillna(0.0)

    except Exception:
        LOGGER.warning("_merge_macro_features: failed to load macro data, filling 0", exc_info=True)
        _fill_macro_defaults(df, include_vix, include_vxn, include_vix3m, include_move)

    return df


def _fill_macro_defaults(
    df: pd.DataFrame,
    include_vix: bool,
    include_vxn: bool,
    include_vix3m: bool,
    include_move: bool,
) -> None:
    """Remplit les colonnes macro à 0.0 quand les données sont indisponibles."""
    macro_defaults: dict[str, float] = {}
    if include_vix:
        macro_defaults.update({"vix_close": 0.0, "vix_momentum_5j": 0.0})
    if include_vxn:
        macro_defaults.update({"vxn_close": 0.0, "vxn_spread_vix": 0.0})
    if include_vix3m:
        macro_defaults.update({"vix3m_close": 0.0, "vix_term_structure_ratio": 1.0, "vix_backwardation": 0.0})
    if include_move:
        macro_defaults.update({"move_close": 0.0})
    for col, default in macro_defaults.items():
        if col not in df.columns:
            df[col] = default
        else:
            df[col] = df[col].fillna(default).astype(float)


def compute_features(
    df: pd.DataFrame,
    sentiment_df: pd.DataFrame | None = None,
    include_sentiment: bool = False,
    benchmark_df: pd.DataFrame | None = None,
    feature_set: str = "v1",
    selector_df: pd.DataFrame | None = None,
    include_screener_scores: bool = False,
    include_short_score: bool = False,
    include_macro_vix: bool = False,
    include_macro_vxn: bool = False,
    include_macro_vix3m: bool = False,
    include_macro_move: bool = False,
    include_fundamentals: bool = False,
    fundamental_df: pd.DataFrame | None = None,
    include_factors: bool = False,
    include_macro_regime: bool = False,
    include_score_components: bool = False,
    include_volume_features: bool = False,
) -> pd.DataFrame:
    """Ajoute les features dérivées à un DataFrame de bars trié par date.

    Le DataFrame d'entrée doit avoir : open, high, low, close, volume, adj_close, vwap, daily_return, is_filled.
    Si include_sentiment=True et sentiment_df fourni, merge les colonnes sentiment sur (symbol, date).
    Si include_fundamentals=True, merge les features fondamentales depuis stock_fundamentals_daily.
    Retourne une copie avec les colonnes features ajoutées.
    Les premières lignes avec NaN rolling sont supprimées.
    """
    df = df.copy().sort_values("date").reset_index(drop=True)

    adj_prices = _build_adjusted_price_frame(df)
    close = adj_prices["close"]
    high = adj_prices["high"]
    low = adj_prices["low"]
    opn = adj_prices["open"]
    volume = df["volume"].astype(float)
    vwap = adj_prices["vwap"]

    # --- daily_return : recalculé depuis la série ajustée pour absorber splits/dividendes ---
    df["daily_return"] = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # --- log return ---
    df["log_return"] = np.log(close / close.shift(1))

    # --- intraday range ---
    df["intraday_range"] = (high - low) / close.clip(lower=1e-8)

    # --- overnight gap ---
    df["overnight_gap"] = (opn - close.shift(1)) / close.shift(1).clip(lower=1e-8)

    # --- close to vwap ---
    df["close_to_vwap"] = (close - vwap) / vwap.clip(lower=1e-8)
    df["close_to_vwap"] = df["close_to_vwap"].fillna(0.0)

    # --- volume ratio 20d ---
    vol_ma20 = volume.rolling(20).mean()
    df["volume_ratio_20"] = volume / vol_ma20.clip(lower=1.0)

    # --- rolling volatility ---
    df["rolling_volatility_20"] = df["daily_return"].rolling(20).std()
    df["rolling_volatility_60"] = df["daily_return"].rolling(60).std()

    # --- rolling mean return ---
    df["rolling_mean_return_5"] = df["daily_return"].rolling(5).mean()
    df["rolling_mean_return_20"] = df["daily_return"].rolling(20).mean()

    # --- RSI 14 ---
    df["rsi_14"] = _rsi(close, 14)

    # --- ATR 14 normalized ---
    df["atr_14_norm"] = _atr_norm(high, low, close, 14)

    # --- is_filled as float ---
    df["is_filled"] = df["is_filled"].astype(float)

    # ── P3-5 : profil volume / liquidité (opt-in) ──
    if include_volume_features:
        _dollar_vol = volume * close
        _dv20 = _dollar_vol.rolling(20).mean()
        _dv60 = _dollar_vol.rolling(60).mean()
        _v_mean20 = volume.rolling(20).mean()
        _v_std20 = volume.rolling(20).std()
        _up_mask = (df["daily_return"] > 0).astype(float)
        _obv = (np.sign(df["daily_return"]) * volume).cumsum()
        _obv_ma20 = _obv.rolling(20).mean()
        # Insertion groupée (évite la fragmentation du DataFrame)
        _vol_cols = {
            "dollar_volume_log_20": np.log(_dv20.clip(lower=1.0)),
            "dollar_volume_trend_20_60": _dv20 / _dv60.clip(lower=1.0) - 1.0,
            "amihud_illiq_20": (df["daily_return"].abs() / _dv20.clip(lower=1.0)).rolling(20).mean(),
            "volume_std_ratio_20": _v_std20 / _v_mean20.clip(lower=1.0),
            "up_volume_ratio_20": (volume * _up_mask).rolling(20).sum() / volume.rolling(20).sum().clip(lower=1.0),
            "volume_price_corr_20": df["daily_return"].rolling(20).corr(volume),
            "obv_slope_20": (_obv - _obv_ma20) / _obv_ma20.abs().clip(lower=1.0),
            "dollar_volume_zscore_20": (_dollar_vol - _dv20) / _dollar_vol.rolling(20).std().clip(lower=1e-8),
            "high_low_range_20": ((high - low) / close.clip(lower=1e-8)).rolling(20).mean(),
            "volume_skew_20": volume.rolling(20).skew(),
        }
        df = pd.concat([df, pd.DataFrame(_vol_cols, index=df.index)], axis=1)

    # --- Expert feature set: trend / relative strength / regime ---
    _has_benchmark = benchmark_df is not None and not benchmark_df.empty
    if feature_set == "expert":
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        sma100 = close.rolling(100).mean()
        sma200 = close.rolling(200).mean()
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()

        # Insertion groupée (évite la fragmentation du DataFrame)
        sma10 = close.rolling(10).mean()
        sma250 = close.rolling(250).mean()
        sma5 = close.rolling(5).mean()
        vol_ma5 = volume.rolling(5).mean()
        vol_std5 = volume.rolling(5).std()
        ma10 = close.rolling(10).mean()
        std10 = close.rolling(10).std()
        _expert_cols = {
            "sma20_distance": (close - sma20) / sma20.clip(lower=1e-8),
            "sma50_distance": (close - sma50) / sma50.clip(lower=1e-8),
            "sma100_distance": (close - sma100) / sma100.clip(lower=1e-8),
            "sma200_distance": (close - sma200) / sma200.clip(lower=1e-8),
            "ema20_distance": (close - ema20) / ema20.clip(lower=1e-8),
            "ema50_distance": (close - ema50) / ema50.clip(lower=1e-8),
            "momentum_10": close / close.shift(10) - 1.0,
            "momentum_20": close / close.shift(20) - 1.0,
            "momentum_60": close / close.shift(60) - 1.0,
            "vol_ratio_20_60": df["rolling_volatility_20"] / df["rolling_volatility_60"].clip(lower=1e-8),
            "range_position_20": _range_position(close, 20),
            "momentum_3": close / close.shift(3) - 1.0,
            "momentum_5": close / close.shift(5) - 1.0,
            "momentum_120": close / close.shift(120) - 1.0,
            "momentum_250": close / close.shift(250) - 1.0,
            "rolling_volatility_5": df["daily_return"].rolling(5).std(),
            "rolling_volatility_10": df["daily_return"].rolling(10).std(),
            "rolling_volatility_120": df["daily_return"].rolling(120).std(),
            "sma10_distance": (close - sma10) / sma10.clip(lower=1e-8),
            "sma250_distance": (close - sma250) / sma250.clip(lower=1e-8),
            "rsi_5": _rsi(close, 5),
            "rsi_21": _rsi(close, 21),
            "rsi_2": _rsi(close, 2),
            "rsi_3": _rsi(close, 3),
            "dist_to_sma_5d": (close - sma5) / sma5.clip(lower=1e-8),
            "volume_zscore_5d": (volume - vol_ma5) / vol_std5.clip(lower=1e-8),
            "volume_ratio_5": volume / volume.rolling(5).mean().clip(lower=1.0),
            "zscore_close_vs_ma10": (close - ma10) / std10.clip(lower=1e-8),
        }
        df = pd.concat([df, pd.DataFrame(_expert_cols, index=df.index)], axis=1)

        if _has_benchmark:
            bench_prices = _build_adjusted_price_frame(benchmark_df.copy().sort_values("date").reset_index(drop=True))
            bench = pd.DataFrame(
                {
                    "date": pd.to_datetime(benchmark_df["date"]),
                    "benchmark_close": bench_prices["close"],
                }
            )
            bench["benchmark_return_20"] = bench["benchmark_close"] / bench["benchmark_close"].shift(20) - 1.0
            bench["benchmark_return_60"] = bench["benchmark_close"] / bench["benchmark_close"].shift(60) - 1.0
            bench_daily_return = bench["benchmark_close"].pct_change(fill_method=None)
            bench["market_return_20"] = bench_daily_return.rolling(20).mean()
            bench["market_volatility_20"] = bench_daily_return.rolling(20).std()
            bench_sma50 = bench["benchmark_close"].rolling(50).mean()
            bench_sma200 = bench["benchmark_close"].rolling(200).mean()
            bench["market_trend_strength_50"] = (bench["benchmark_close"] - bench_sma50) / bench_sma50.clip(lower=1e-8)
            bench["regime_bull_market"] = (bench["benchmark_close"] > bench_sma200).astype(float)
            bench["regime_risk_off"] = (bench["market_volatility_20"] > bench_daily_return.rolling(60).std()).astype(float)
            df = df.merge(
                bench[
                    [
                        "date",
                        "benchmark_close",
                        "benchmark_return_20",
                        "benchmark_return_60",
                        "market_return_20",
                        "market_volatility_20",
                        "market_trend_strength_50",
                        "regime_bull_market",
                        "regime_risk_off",
                    ]
                ],
                on="date",
                how="left",
            )
            df["relative_strength_20"] = df["momentum_20"] - df["benchmark_return_20"]
            df["relative_strength_60"] = df["momentum_60"] - df["benchmark_return_60"]
        else:
            for col in [
                "market_return_20",
                "market_volatility_20",
                "market_trend_strength_50",
                "relative_strength_20",
                "relative_strength_60",
                "regime_bull_market",
                "regime_risk_off",
            ]:
                df[col] = 0.0

    # --- Sentiment features (optional) ---
    if include_sentiment:
        if sentiment_df is not None and not sentiment_df.empty:
            sent = sentiment_df.copy()
            # Normaliser la colonne date pour le merge
            if "trade_date" in sent.columns:
                sent = sent.rename(columns={"trade_date": "date"})
            sent["date"] = pd.to_datetime(sent["date"])
            sent["news_count_log"] = np.log1p(sent.get("news_count_1d", pd.Series(dtype=float)).fillna(0))
            merge_cols = ["date", "sentiment_net_mean_1d", "sentiment_confidence_mean_1d", "news_count_log", "major_event_flag"]
            if "symbol" in sent.columns and "symbol" in df.columns:
                merge_cols.insert(0, "symbol")
            sent = sent[[c for c in merge_cols if c in sent.columns]]
            df = df.merge(sent, on=[c for c in ["symbol", "date"] if c in sent.columns and c in df.columns], how="left")
        # Remplir les jours sans news par des valeurs neutres
        for col in SENTIMENT_FEATURE_COLUMNS:
            if col not in df.columns:
                df[col] = 0.0
            else:
                df[col] = df[col].fillna(0.0).astype(float)
        # ── Sentiment Intensity (2026-07-29) ──
        # Combine les 3 dimensions en 1 signal dense pour le per-symbol.
        # direction × confiance × volume → évite que des features sparse
        # (ex: major_event_flag=0 sur 95% des jours) soient ignorées.
        df["sentiment_intensity"] = (
            df["sentiment_net_mean_1d"]
            * df["sentiment_confidence_mean_1d"]
            * df["news_count_log"]
        ).astype(float)

    if include_screener_scores or include_short_score or include_score_components:
        if selector_df is not None and not selector_df.empty:
            selector = selector_df.copy()
            if "snapshot_date" in selector.columns and "date" not in selector.columns:
                selector = selector.rename(columns={"snapshot_date": "date"})
            if "date" in selector.columns:
                selector["date"] = pd.to_datetime(selector["date"])
            merge_keys = [column for column in ["symbol", "date"] if column in selector.columns and column in df.columns]
            if merge_keys:
                selector_columns = [
                    *merge_keys,
                    *[column for column in _SELECTOR_CONTEXT_SOURCE_TO_FEATURE if column in selector.columns],
                    *(["selector_signal_mode"] if "selector_signal_mode" in selector.columns else []),
                ]
                selector = selector.loc[:, selector_columns].copy()
                selector = selector.drop_duplicates(subset=merge_keys, keep="last")
                rename_map = {
                    source: target
                    for source, target in _SELECTOR_CONTEXT_SOURCE_TO_FEATURE.items()
                    if source in selector.columns
                }
                selector = selector.rename(columns=rename_map)
                if "selector_signal_mode" in selector.columns:
                    selector["selector_mode_sector_neutralized"] = (
                        selector["selector_signal_mode"].astype(str).str.strip().str.lower() == "sector_neutralized"
                    ).astype(float)
                df = df.merge(selector, on=merge_keys, how="left")
        for col, default in _SELECTOR_CONTEXT_DEFAULTS.items():
            if col not in df.columns:
                df[col] = default
            else:
                numeric_series = pd.Series(pd.to_numeric(df[col], errors="coerce"), index=df.index, dtype=float)
                df[col] = numeric_series.fillna(default).astype(float)

    # --- Macro features (optional, from stock_macro_indicators_daily) ---
    any_macro = include_macro_vix or include_macro_vxn or include_macro_vix3m or include_macro_move
    if any_macro:
        df = _merge_macro_features(
            df,
            include_vix=include_macro_vix,
            include_vxn=include_macro_vxn,
            include_vix3m=include_macro_vix3m,
            include_move=include_macro_move,
        )

    # --- Macro regime features (SPY_SMA_200_slope + VIX_zscore) ---
    if include_macro_regime:
        # 1. SPY SMA 200 slope = tendance long terme du marché
        if benchmark_df is not None and "close" in benchmark_df.columns:
            _spy_sma = benchmark_df["close"].rolling(200, min_periods=200).mean()
            _spy_slope = _spy_sma.diff(20) / _spy_sma.replace(0, np.nan)
            _spy_map = pd.Series(_spy_slope.values, index=benchmark_df["date"].values)
            df["SPY_SMA_200_slope"] = (
                pd.to_datetime(df["date"]).map(_spy_map).fillna(0.0).astype(float)
            )
        else:
            df["SPY_SMA_200_slope"] = 0.0

        # 2. VIX z-score (si VIX déjà chargé via macro features, sinon fallback 0)
        if "vix_close" in df.columns:
            _vix_roll = df["vix_close"].rolling(252, min_periods=60)
            _vix_mean = _vix_roll.mean()
            _vix_std = _vix_roll.std().replace(0, np.nan)
            df["VIX_zscore"] = ((df["vix_close"] - _vix_mean) / _vix_std).fillna(0.0).astype(float)
        else:
            df["VIX_zscore"] = 0.0

    # --- Régime × technique interaction features (Cause 3) ---
    # Permet aux arbres d'apprendre des splits conditionnels au régime.
    if feature_set == "expert" and _has_benchmark:
        _interact_pairs = [
            ("momentum_20", "regime_bull_market"),
            ("momentum_20", "regime_risk_off"),
            ("momentum_60", "regime_bull_market"),
            ("momentum_60", "regime_risk_off"),
            ("relative_strength_20", "regime_bull_market"),
            ("relative_strength_20", "regime_risk_off"),
            ("relative_strength_60", "regime_bull_market"),
            ("relative_strength_60", "regime_risk_off"),
            ("rolling_volatility_20", "regime_bull_market"),
            ("rolling_volatility_20", "regime_risk_off"),
            ("vol_ratio_20_60", "regime_bull_market"),
            ("vol_ratio_20_60", "regime_risk_off"),
            ("rsi_14", "regime_bull_market"),
            ("rsi_14", "regime_risk_off"),
            ("sma20_distance", "regime_bull_market"),
            ("sma20_distance", "regime_risk_off"),
            ("sma50_distance", "regime_bull_market"),
            ("sma50_distance", "regime_risk_off"),
        ]
        for tech_col, regime_col in _interact_pairs:
            _regime_suffix = regime_col.replace('regime_', '').replace('_market', '')
            target_col = f"{tech_col}_x_{_regime_suffix}"
            if tech_col in df.columns and regime_col in df.columns:
                df[target_col] = df[tech_col].astype(float) * df[regime_col].astype(float)
            else:
                df[target_col] = 0.0
    elif feature_set == "expert":
        # Pas de benchmark → remplir avec 0.0 pour que le contrat de features reste stable
        for col in REGIME_INTERACTION_FEATURES:
            df[col] = 0.0

    # ── Interaction features (Sprint 2026-07-25) ──
    if feature_set == "expert":
        _vol_20 = df["rolling_volatility_20"].clip(lower=1e-8)
        _vol_60 = df["rolling_volatility_60"].clip(lower=1e-8)
        _atr = df["atr_14_norm"].clip(lower=1e-8)
        _range = df["intraday_range"].clip(lower=1e-8)
        _vol_ratio_5 = volume.rolling(5).mean().clip(lower=1.0)
        _vol_ratio_5 = volume / _vol_ratio_5
        _vol_ratio_20_s = df["volume_ratio_20"].clip(lower=1e-3)
        _mkt_trend = df.get("market_trend_strength_50", pd.Series(0.0, index=df.index))
        _mkt_vol20 = df.get("market_volatility_20", pd.Series(1.0, index=df.index)).clip(lower=1e-8)

        # Insertion groupée (évite la fragmentation du DataFrame)
        _interaction_cols = {
            "momentum_20_div_vol_20": df["momentum_20"] / _vol_20,
            "momentum_60_div_vol_60": df["momentum_60"] / _vol_60,
            "momentum_5_minus_momentum_20": df["momentum_5"] - df["momentum_20"],
            "momentum_20_minus_momentum_60": df["momentum_20"] - df["momentum_60"],
            "volume_ratio_5_div_volume_ratio_20": _vol_ratio_5 / _vol_ratio_20_s,
            "rsi_14_times_volume_ratio_20": df["rsi_14"] * _vol_ratio_20_s,
            "rsi_14_div_volatility_20": df["rsi_14"] / _vol_20,
            "sma20_minus_sma50": df["sma20_distance"] - df["sma50_distance"],
            "sma50_minus_sma200": df["sma50_distance"] - df["sma200_distance"],
            "ema20_minus_sma20": df["ema20_distance"] - df["sma20_distance"],
            "intraday_range_div_atr_14": _range / _atr,
            "range_position_20_times_vol_ratio_20_60": df["range_position_20"] * df["vol_ratio_20_60"],
            "daily_return_times_volume_ratio_20": df["daily_return"] * _vol_ratio_20_s,
            "log_return_div_intraday_range": df["log_return"] / _range,
            "relative_strength_20_times_market_trend": df["relative_strength_20"] * _mkt_trend,
            "relative_strength_60_div_market_volatility": df["relative_strength_60"] / _mkt_vol20,
        }
        df = pd.concat([df, pd.DataFrame(_interaction_cols, index=df.index)], axis=1)

        for _col in INTERACTION_FEATURES:
            if _col in df.columns:
                df[_col] = df[_col].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # ── Temporal dynamics features (Niveau 3, Sprint 2026-07-26) ──
    if feature_set == "expert":
        # Accélération / décélération du momentum
        _m3 = df["momentum_3"].replace(0, np.nan)
        _m5 = df["momentum_5"].replace(0, np.nan)
        _m10 = df["momentum_10"]
        _v5 = df["rolling_volatility_5"].clip(lower=1e-8)
        _v20 = df["rolling_volatility_20"].clip(lower=1e-8)
        _rsi3_dev = 1.0 - (df["rsi_3"] - 50.0).abs() / 50.0
        # Insertion groupée (évite la fragmentation du DataFrame)
        _temporal_cols = {
            "accel_3_5": (_m5 / _m3 - 1.0).fillna(0.0),
            "decay_5_10": (_m10 / _m5 - 1.0).fillna(0.0),
            "rsi_slope": df["rsi_3"] - df["rsi_14"],
            "vol_expansion": (_v5 / _v20 - 1.0).fillna(0.0),
            "meanrev_signal": df["dist_to_sma_5d"] - df["sma20_distance"],
            "gap_fade": df["overnight_gap"] * _rsi3_dev.clip(0.0, 1.0),
        }
        df = pd.concat([df, pd.DataFrame(_temporal_cols, index=df.index)], axis=1)
        # Nettoyage inf/nan
        for _col in TEMPORAL_DYNAMICS_FEATURES:
            if _col in df.columns:
                df[_col] = df[_col].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # ── Z-score rolling (Sprint 2026-07-25) ──
    # Normalisation temporelle sur 5 ans glissants pour rendre les features
    # comparables indépendamment du régime de marché.
    if feature_set == "expert":
        _zscore_window = 1260  # 5 ans
        _zscore_min = 252      # 1 an minimum
        _new_zscore_cols: dict[str, "pd.Series"] = {}
        for _src in ZSCORE_SOURCE_FEATURES:
            _target = _zscore_column_name(_src)
            if _src in df.columns:
                _series = df[_src].astype(float)
                _roll_mean = _series.rolling(_zscore_window, min_periods=_zscore_min).mean()
                _roll_std = _series.rolling(_zscore_window, min_periods=_zscore_min).std()
                _new_zscore_cols[_target] = ((_series - _roll_mean) / _roll_std.clip(lower=1e-8)).fillna(0.0)
            else:
                _new_zscore_cols[_target] = pd.Series(0.0, index=df.index)
        if _new_zscore_cols:
            df = pd.concat([df, pd.DataFrame(_new_zscore_cols, index=df.index)], axis=1)

    # ── Fundamental features (optional, from stock_fundamentals_daily) ──
    if include_fundamentals:
        from modelFactory.fundamental_features import merge_fundamentals, FUNDAMENTAL_DEFAULTS
        df = merge_fundamentals(df, fundamental_df=fundamental_df)
        # Ensure all fundamental columns exist (merge may have skipped some)
        for col, default in FUNDAMENTAL_DEFAULTS.items():
            if col not in df.columns:
                df[col] = default

    # ── Factor exposures (CAPM beta/alpha/R², momentum vs market) ──
    if include_factors:
        from modelFactory.factor_features import compute_factor_features, fill_factor_defaults
        df = compute_factor_features(df, benchmark_df=benchmark_df)
        df = fill_factor_defaults(df)

    # Determine active feature columns
    active_features = get_feature_columns(
        include_sentiment,
        feature_set=feature_set,
        include_screener_scores=include_screener_scores,
        include_short_score=include_short_score,
        include_macro_vix=include_macro_vix,
        include_macro_vxn=include_macro_vxn,
        include_macro_vix3m=include_macro_vix3m,
        include_macro_move=include_macro_move,
        include_fundamentals=include_fundamentals,
        include_factors=include_factors,
        include_macro_regime=include_macro_regime,
    )

    feature_matrix = df.loc[:, active_features].astype(np.float64)
    non_finite_mask = ~np.isfinite(feature_matrix.to_numpy(dtype=np.float64, copy=False))
    if non_finite_mask.any():
        affected_column_indexes = np.where(non_finite_mask)[1].tolist()
        affected_columns = sorted({str(active_features[int(column_index)]) for column_index in affected_column_indexes})
        affected_rows = int(non_finite_mask.any(axis=1).sum())
        LOGGER.debug(
            "compute_features dropping non-finite rows=%d columns=%s",
            affected_rows,
            ",".join(affected_columns),
        )
        feature_matrix = feature_matrix.replace([np.inf, -np.inf], np.nan)
        df.loc[:, active_features] = feature_matrix

    # Drop warm-up NaN rows (rolling windows need ~60 rows)
    df = df.dropna(subset=active_features).reset_index(drop=True)
    return df


def compute_rank_interactions(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les features d'interaction global_rank × features locales.

    Doit être appelé APRÈS merge_cross_sectional_features (qui injecte global_rank).
    Utilise global_rank_10 comme référence primaire ; fallback sur global_rank.
    Les colonnes produites sont listées dans RANK_INTERACTION_FEATURES.
    """
    _rank_col = "global_rank_10" if "global_rank_10" in df.columns else "global_rank"
    if _rank_col not in df.columns:
        for col in RANK_INTERACTION_FEATURES:
            if col not in df.columns:
                df[col] = 0.0
        return df

    _rank = df[_rank_col].fillna(0.5).astype(float)

    _mapping = {
        "rank_x_rsi_14": "rsi_14",
        "rank_x_momentum_20": "momentum_20",
        "rank_x_momentum_60": "momentum_60",
        "rank_x_volatility_20": "rolling_volatility_20",
        "rank_x_sma20_distance": "sma20_distance",
    }

    for out_col, src_col in _mapping.items():
        if src_col in df.columns:
            df[out_col] = (_rank * df[src_col].fillna(0.0).astype(float)).astype(float)
        else:
            df[out_col] = 0.0

    # rank_acceleration = vitesse du rang (J+3 vs J+10)
    _r3 = df["global_rank_3"] if "global_rank_3" in df.columns else _rank
    _r10 = df["global_rank_10"] if "global_rank_10" in df.columns else _rank
    df["rank_acceleration"] = (_r3.fillna(0.5) - _r10.fillna(0.5)).astype(float)

    return df


def build_target(
    df: pd.DataFrame,
    horizon: int = 5,
    mode: str = "binary",
    positive_threshold: float = 0.0,
    negative_threshold: float = 0.0,
    *,
    skip_winsorize: bool = False,
    skip_vol_scaling: bool = False,
    excess_vs_spy: bool = False,
) -> pd.Series:
    """Construit la target pour l'horizon futur.

    Retourne une Series alignée sur l'index de df.
    Les dernières ``horizon`` lignes seront NaN.

    Modes
    -----
    - ``binary``      : 1 si future_return > positive_threshold, sinon 0.
    - ``swing_cash``  : 1 si future_return >= positive_threshold,
                        0 si future_return <= negative_threshold,
                        NaN entre les deux (zone no-trade ignorée).
    - ``ternary``     : +1 (long)  si future_return > positive_threshold,
                        -1 (short) si future_return < negative_threshold,
                         0 (flat)  entre les deux.
    - ``regression``  : rendement futur vol-scalé + winsorizé (continu).

      Pour ``ternary``, ``negative_threshold`` doit être < 0 (ex: -0.08 pour -8%).
    """
    close = _build_adjusted_price_frame(df)["close"]
    future_return = close.shift(-horizon) / close - 1.0

    if mode == "binary":
        return (future_return > positive_threshold).astype(float).where(future_return.notna())

    if mode == "swing_cash":
        target = pd.Series(np.nan, index=df.index, dtype=float)
        target = target.mask(future_return >= positive_threshold, 1.0)
        target = target.mask(future_return <= negative_threshold, 0.0)
        return target.where(future_return.notna())

    if mode == "ternary":
        # Sprint 1 ML — target directionnelle long (+1) / flat (0) / short (-1)
        target = pd.Series(0, index=df.index, dtype=int)
        target = target.mask(future_return > positive_threshold, 1)
        target = target.mask(future_return < negative_threshold, -1)
        return target.where(future_return.notna())

    if mode == "regression":
        # ── Regression target (Sprint 2026-08-02) ──
        # Vol-scaling ONLY. La winsorisation et la standardisation sont
        # appliquées APRÈS le split chronologique pour éviter le leakage
        # (→ run_tabular_baseline, run_tabular_walk_forward, SymbolDataModule).
        # skip_winsorize=True désactive la winsorisation pré-split (P1-1 fix).
        # skip_vol_scaling=True désactive le vol-scaling (T1 experiment).
        target = future_return.copy()
        # P0-7 (2026-08-07) : excès vs SPY pour centrer la distribution
        if excess_vs_spy and "benchmark_close" in df.columns:
            spy_close = df["benchmark_close"]
            spy_return = spy_close.shift(-horizon) / spy_close - 1.0
            target = target - spy_return
        if not skip_vol_scaling and horizon >= 5:
            rolling_vol = close.pct_change().rolling(20).std()
            target = target / rolling_vol
        if not skip_winsorize:
            lo, hi = target.quantile(0.01), target.quantile(0.99)
            target = target.clip(lo, hi)
        return target.where(future_return.notna()).astype(float)

    raise ValueError(f"Unsupported target mode: {mode}")


def compute_future_return(df: pd.DataFrame, horizon: int = 5) -> pd.Series:
    """Retourne le rendement futur aligné à la ligne courante."""
    close = _build_adjusted_price_frame(df)["close"]
    return close.shift(-horizon) / close - 1.0


def build_multi_horizon_targets(
    df: pd.DataFrame,
    horizons: tuple[int, ...],
    mode: str = "binary",
    positive_threshold: float = 0.0,
    negative_threshold: float = 0.0,
    *,
    skip_winsorize: bool = False,
    skip_vol_scaling: bool = False,
    excess_vs_spy: bool = False,
) -> pd.DataFrame:
    """Construit les targets pour plusieurs horizons en une seule passe.

    Retourne un DataFrame avec les colonnes ``target_h{horizon}`` et
    ``future_return_h{horizon}`` pour chaque horizon.

    Si ``skip_winsorize=True``, la winsorisation est désactivée (P1-1 fix).
    Elle sera appliquée après le split chronologique sur les stats du train.

    Si ``skip_vol_scaling=True``, le vol-scaling est désactivé (T1 experiment).
    La target est le forward return brut (non divisé par la volatilité).
    """
    close = _build_adjusted_price_frame(df)["close"]
    targets: dict[str, pd.Series] = {}
    for h in horizons:
        future_return = close.shift(-h) / close - 1.0
        targets[f"future_return_h{h}"] = future_return
        if mode == "regression":
            target = future_return.copy()
            # P0-7 (2026-08-07) : excès vs SPY
            if excess_vs_spy and "benchmark_close" in df.columns:
                spy_close = df["benchmark_close"]
                spy_return = spy_close.shift(-h) / spy_close - 1.0
                target = target - spy_return
            if not skip_vol_scaling and h >= 5:
                rolling_vol = close.pct_change().rolling(20).std()
                target = target / rolling_vol
            if not skip_winsorize:
                lo, hi = target.quantile(0.01), target.quantile(0.99)
                target = target.clip(lo, hi)
            targets[f"target_h{h}"] = target.where(future_return.notna()).astype(float)
        else:
            targets[f"target_h{h}"] = build_target(
                df, horizon=h, mode=mode,
                positive_threshold=positive_threshold,
                negative_threshold=negative_threshold,
                excess_vs_spy=excess_vs_spy,
            )
    return pd.DataFrame(targets, index=df.index)


def standardize_regression_target(
    prepared_df: pd.DataFrame,
    train_mask: "pd.Series | None" = None,
) -> pd.DataFrame:
    """Standardise la target regression (mean=0, std=1) sur les stats du train.

    Doit être appelée APRÈS le split chronologique pour éviter le data leakage.
    Si ``train_mask`` est None, standardise sur l'ensemble du DataFrame
    (utilisé uniquement pour l'inférence, où il n'y a pas de split).

    Returns
    -------
    pd.DataFrame
        Copie du DataFrame avec la colonne ``target`` standardisée.
    """
    if "target" not in prepared_df.columns:
        return prepared_df

    df = prepared_df.copy()
    target = df["target"]

    if train_mask is not None:
        train_target = target.loc[train_mask]
    else:
        train_target = target

    valid = train_target.notna()
    if valid.sum() < 2:
        return df

    t_mean = float(train_target.loc[valid].mean())
    t_std = float(train_target.loc[valid].std())
    if t_std > 1e-9:
        df["target"] = (target - t_mean) / t_std
    else:
        df["target"] = target - t_mean

    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_adjusted_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Reconstruit un OHLCV prix ajusté à partir de `adj_close` quand disponible.

    Pour des barres journalières actions, appliquer le ratio `adj_close / close`
    à OHLC/VWAP permet d'éviter que les splits/dividendes polluent les returns,
    la target et les indicateurs de volatilité.
    """
    close = pd.to_numeric(df["close"], errors="coerce").astype(float)
    adj_close_raw = pd.to_numeric(df["adj_close"], errors="coerce").astype(float) if "adj_close" in df.columns else close.copy()

    close_non_zero = pd.Series(close.replace(0.0, np.nan), index=df.index, dtype=float)
    ratio = pd.Series(adj_close_raw / close_non_zero, index=df.index, dtype=float)
    ratio = ratio.replace([np.inf, -np.inf], np.nan)
    ratio = ratio.where(ratio > 0.0, np.nan).fillna(1.0)

    def _scaled_col(name: str) -> pd.Series:
        base = df[name] if name in df.columns else close
        return pd.to_numeric(base, errors="coerce").astype(float) * ratio

    adjusted = pd.DataFrame({
        "open": _scaled_col("open"),
        "high": _scaled_col("high"),
        "low": _scaled_col("low"),
        "close": close * ratio,
        "vwap": _scaled_col("vwap"),
    })
    return adjusted


def _range_position(close: pd.Series, window: int) -> pd.Series:
    rolling_low = close.rolling(window).min()
    rolling_high = close.rolling(window).max()
    return (close - rolling_low) / (rolling_high - rolling_low).clip(lower=1e-8)

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.clip(lower=1e-10)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr_norm(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr / close.clip(lower=1e-8)

