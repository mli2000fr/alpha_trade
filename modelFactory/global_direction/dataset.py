"""modelFactory/global_direction/dataset.py — Dataset GlobalDirection H20.

Assemble, pour chaque ``(date, symbol)`` de l'univers Global Model :
- **features PIT** : réutilise ``build_feature_matrix()`` de l'Oracle (feature_set
  ``expert`` + rangs cross-sectionnels). **``proba_extreme`` n'est JAMAIS une
  feature** (premier test) ; ``global_rank_20`` non plus.
- **target** ``gd_direction`` : dérivée de ``global_oracle_labels`` —
  ``oracle_decile == 10`` → y=1 (D10, bon long), ``oracle_decile == 1`` → y=0
  (D1, mauvais long) ; **D2-D9 exclus de l'entraînement**.
- **colonne de garde** ``oracle_available_date`` (anti-leakage T1/T2, identique
  Oracle).

Sortie : ``direction_score = P(D10 plutôt que D1)``.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from modelFactory.oracle.dataset import (
    GUARD_COL,
    build_feature_matrix,
    expert_feature_columns,
    load_oracle_targets,
)
from modelFactory.oracle.leakage import (
    assert_no_forbidden_features,
    assert_no_future_features,
)

# Cible GlobalDirection : 1 = D10 (bon long), 0 = D1 (mauvais long).
TARGET_COL = "gd_direction"
DECILE_COL = "oracle_decile"
RETURN_COL = "future_return"
DIRECTION_SCORE_COL = "direction_score"

# ── Familles de features directionnelles (curated, première itération) ─────
# Objectif D10-vs-D1 : on privilégie le SENS (momentum / trend / force
# relative). On exclut volontairement les features de volatilité/liquidité
# pures au premier essai (elles feraient apprendre « gros mouvement » au lieu
# du « bon côté du gros mouvement »).
# NB : la famille sectorielle (`sector_relative`) n'est PAS encore calculée par
# le moteur de features (mapping secteur + retours sectoriels à implémenter).

GD_FEATURE_FAMILIES: dict[str, list[str]] = {
    # 1. Momentum / trend absolu
    "directional_abs": [
        "momentum_5", "momentum_10", "momentum_20", "momentum_60", "momentum_120",
        "relative_strength_5", "relative_strength_20", "relative_strength_60",
        "rolling_mean_return_5", "rolling_mean_return_20",
        "sma20_distance", "sma50_distance", "sma200_distance",
        "ema20_distance", "ema50_distance", "ema20_slope_10", "ema50_slope_20",
        "range_position_20", "range_position_50", "distance_high_20",
        "close_location_value", "rsi_14", "adx_14", "cmf_20",
        "volume_zscore_20", "momentum_20_div_vol_20", "momentum_60_div_vol_60",
        "momentum_5_minus_momentum_20", "momentum_20_minus_momentum_60",
        "rsi_slope", "vol_expansion",
    ],
    # 2. Force relative cross-sectionnelle (rangs percentile du jour)
    "relative_xs": [
        "momentum_5_xs_rank", "momentum_10_xs_rank", "momentum_20_xs_rank",
        "momentum_60_xs_rank", "momentum_120_xs_rank",
        "rolling_mean_return_5_xs_rank", "rolling_mean_return_20_xs_rank",
        "sma20_distance_xs_rank", "sma50_distance_xs_rank", "sma200_distance_xs_rank",
        "ema20_distance_xs_rank", "ema50_distance_xs_rank",
        "range_position_20_xs_rank", "rsi_14_xs_rank",
    ],
    # 3. Force relative au secteur — NON DISPONIBLE dans le moteur (à implémenter)
    "sector_relative": [
        "momentum_20_sector_neutral", "relative_strength_20_sector_neutral",
        "stock_vs_sector_ret_20", "stock_vs_sector_ret_60",
        "sector_relative_strength_20", "sector_ret_20", "sector_ret_60",
    ],
}

# Liste MINIMALE (~25) pour le tout premier GlobalDirection H20 : sens directionnel
# + quelques rangs cross-sectionnels, sans volatilité/liquidité pures.
GD_MINIMAL_FIRST: list[str] = [
    "momentum_5", "momentum_10", "momentum_20", "momentum_60", "momentum_120",
    "relative_strength_5", "relative_strength_20", "relative_strength_60",
    "rolling_mean_return_5", "rolling_mean_return_20",
    "sma20_distance", "sma50_distance", "sma200_distance",
    "ema20_distance", "ema50_distance", "ema20_slope_10", "ema50_slope_20",
    "range_position_20", "range_position_50", "close_location_value",
    "momentum_5_minus_momentum_20", "momentum_20_minus_momentum_60",
    "momentum_20_xs_rank", "momentum_60_xs_rank", "rolling_mean_return_20_xs_rank",
]

_FEATURE_MODES = {"minimal", "directional", "directional+xs", "sector", "complete", "all"}


def select_direction_features(available: list[str], mode: str = "minimal") -> list[str]:
    """Sélectionne les features directionnelles disponibles selon le mode.

    - ``minimal``        : liste minimale (~25, premier test).
    - ``directional``    : famille momentum/trend absolu uniquement.
    - ``directional+xs`` : momentum/trend absolu + force relative xs.
    - ``sector``         : minimal + famille sectorielle (V2, voir ``build_sector_features``).
    - ``complete``       : directional+xs + famille sectorielle (V3).
    - ``all``            : toutes les features expert + xs (fallback, non recommandé).

    NB : les colonnes sectorielles sont ajoutées SÉPARÉMENT (elles ne sont pas
    dans ``available`` — elles proviennent du moteur cross-sectionnel).
    """
    mode = str(mode).strip().lower()
    if mode not in _FEATURE_MODES:
        mode = "minimal"
    avail = set(available)
    if mode == "all":
        return [c for c in available if c in avail]
    if mode == "minimal":
        wanted = list(GD_MINIMAL_FIRST)
    else:
        wanted = list(GD_FEATURE_FAMILIES["directional_abs"])
        if mode in ("directional+xs", "complete"):
            wanted += GD_FEATURE_FAMILIES["relative_xs"]
        if mode == "complete":
            wanted += GD_FEATURE_FAMILIES["sector_relative"]
    seen: set[str] = set()
    out: list[str] = []
    for c in wanted:
        if c in avail and c not in seen:
            out.append(c)
            seen.add(c)
    return out


def build_sector_features(
    engine: Any,
    symbols: list[str],
    *,
    start_date: str,
    end_date: str,
    base_cols: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """Features sectorielles / sector-neutral (famille ``DIRECTIONAL_FEATURES``).

    Réutilise ``build_cross_sectional_features_from_db`` (même moteur que le
    Global Ranking avec ``--include-directional-features``). Ne retourne que les
    colonnes SECTORIELLES non déjà présentes dans ``base_cols`` — les
    ``*_xs_rank`` de la liste direction sont déjà calculées par le moteur de
    base (``build_feature_matrix``).

    Returns:
        ``(frame, new_cols)`` — frame = [symbol, date, *sector_cols] ;
        ``new_cols`` = colonnes sectorielles ajoutables (vide si aucune).
    """
    from modelFactory.cross_sectional import (
        DIRECTIONAL_FEATURES,
        _load_sector_mapping,
        build_cross_sectional_features_from_db,
    )
    from modelFactory.data_loader import load_benchmark_bars

    try:
        sector_map = _load_sector_mapping(engine)
    except Exception:
        sector_map = {}
    if not sector_map:
        return pd.DataFrame(), []

    warmup_start = (pd.Timestamp(start_date) - pd.Timedelta(days=400)).date().isoformat()
    try:
        benchmark = load_benchmark_bars(engine, "SPY", start_date=warmup_start, end_date=end_date)
    except Exception:
        benchmark = None
    try:
        frame, _diag = build_cross_sectional_features_from_db(
            engine, symbols,
            benchmark_df=benchmark,
            sector_map=sector_map,
            start_date=warmup_start, end_date=end_date,
            feature_subset=list(DIRECTIONAL_FEATURES),
        )
    except Exception:
        return pd.DataFrame(), []
    if frame is None or frame.empty:
        return pd.DataFrame(), []

    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    base = set(base_cols)
    new_cols = [c for c in frame.columns if c not in ("symbol", "date") and c not in base]
    if not new_cols:
        return pd.DataFrame(), []
    return frame[["symbol", "date"] + new_cols].dropna(subset=["date", "symbol"]), new_cols


def gd_labels_from_oracle(
    targets: pd.DataFrame,
    target_mode: str = "binary",
) -> pd.DataFrame:
    """Dérive la cible GlobalDirection depuis ``global_oracle_labels``.

    ``target_mode`` :
    - ``binary`` (défaut) : ``oracle_decile==10``→1 (D10), ``==1``→0 (D1),
      D2-D9→NaN. **Exclus de l'entraînement** mais conservés au scoring (le
      walk-forward n'entraîne que sur les lignes à cible non-NaN). Répond à la
      question pure « parmi les vrais extrêmes, quel est le bon côté ? ».
    - ``ordinal`` (V1b) : D10→2, D2-D9→1, D1→0 — TOUTES les lignes entraînées.
      Le modèle connaît le milieu (D2-D9) qu'il rencontrera à l'inférence.
      ``direction_score = P(D10)`` ; on vérifie la monotonie D1↓ / D10↑.
    - ``rank`` (V2) : cible = **percentile cross-sectionnel du ``future_return``**
      (``oracle_pct_rank`` : D1≈0.05 … D10≈0.95), régression ordinale sur les 10
      niveaux ordonnés. C'est un **GoodLongRank** : classer du pire au meilleur
      futur rendement (LONG), pas seulement séparer D1 de D10.
    """
    target_mode = str(target_mode).strip().lower()
    if target_mode not in ("binary", "ordinal", "rank"):
        target_mode = "binary"
    df = targets.copy()
    if target_mode == "rank":
        df[TARGET_COL] = pd.to_numeric(df.get("oracle_pct_rank"), errors="coerce")
        return df
    if target_mode == "ordinal":
        df[TARGET_COL] = np.where(
            df[DECILE_COL] == 10, 2,
            np.where(df[DECILE_COL] == 1, 0, 1),
        )
        return df
    df[TARGET_COL] = np.nan
    df.loc[df[DECILE_COL] == 10, TARGET_COL] = 1
    df.loc[df[DECILE_COL] == 1, TARGET_COL] = 0
    return df


def build_dataset(
    engine: Any,
    batch_id: str,
    symbols: list[str],
    *,
    start_date: str,
    end_date: str,
    horizon: int = 20,
    feature_mode: str = "minimal",
    target_mode: str = "binary",
) -> tuple[pd.DataFrame, list[str]]:
    """Assemble features PIT + labels GlobalDirection.

    ``feature_mode`` : ``minimal`` (défaut, ~25 features directionnelles) |
    ``directional`` | ``directional+xs`` | ``sector`` | ``complete`` | ``all``.
    ``target_mode`` : ``binary`` (D1/D10, défaut) | ``ordinal`` (D1/middle/D10).

    Returns:
        ``(dataset, feature_columns)`` — SANS ``proba_extreme`` ni
        ``global_rank_20``. Les colonnes de garde / cible restent dans le
        DataFrame.
    """
    feats = build_feature_matrix(engine, symbols, start_date=start_date, end_date=end_date)
    if feats.empty:
        return pd.DataFrame(), []

    base_cols = [c for c in expert_feature_columns() if c in feats.columns]
    xs_cols = [c for c in feats.columns if c.endswith("_xs_rank")]
    if feature_mode == "all":
        feature_columns = base_cols + xs_cols
    else:
        feature_columns = select_direction_features(base_cols + xs_cols, feature_mode)

    # Famille sectorielle (V2/V3) : calculée par le moteur cross-sectionnel,
    # fusionnée aux features de base (uniquement les colonnes nouvelles).
    if feature_mode in ("sector", "complete"):
        sector_frame, sector_cols = build_sector_features(
            engine, symbols,
            start_date=start_date, end_date=end_date,
            base_cols=feature_columns,
        )
        if sector_cols:
            feats = feats.merge(sector_frame, on=["symbol", "date"], how="left")
            feature_columns = feature_columns + sector_cols

    if not feature_columns:
        raise ValueError("GlobalDirection: aucune feature directionnelle disponible.")

    # ── Garde-fous : proba_extreme / global_rank / features futures interdits ──
    if "proba_extreme" in feature_columns:
        raise ValueError("GlobalDirection: proba_extreme ne doit PAS être une feature (premier test)")
    if "global_rank_20" in feature_columns or "global_rank" in feature_columns:
        raise ValueError("GlobalDirection: global_rank ne doit PAS être une feature")
    assert_no_forbidden_features(feature_columns)
    assert_no_future_features(feature_columns)

    targets = load_oracle_targets(engine, batch_id, horizon)
    labels = gd_labels_from_oracle(targets, target_mode=target_mode)

    df = feats.merge(
        labels,
        left_on=["date", "symbol"],
        right_on=["prediction_date", "symbol"],
        how="inner",
    )
    df = df.drop(columns=["prediction_date"])
    # Garde anti-leakage (T1/T2) : ne garder que les labels strictement disponibles.
    df = df[df[GUARD_COL] > df["date"]]
    return df, feature_columns
