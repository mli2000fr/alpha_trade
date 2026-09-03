"""modelFactory/oracle/dataset.py — Construction du dataset Oracle Extreme (S3).

Construit, pour chaque ``(date, symbol)`` de l'univers Global Model :
- **features PIT** : réutilise ``compute_features()`` (feature_set ``expert``,
  même moteur que B25) + rangs percentiles cross-sectionnels ;
- **global_rank_20** : relu depuis ``global_rank_history`` (jamais recalculé — §28) ;
- **target** ``oracle_extreme10`` (+ ``oracle_pct_rank``, ``oracle_decile``,
  ``future_return``) : jointe depuis ``global_oracle_labels`` ;
- **colonne de garde** ``oracle_available_date`` (anti-leakage §9).

Le modèle Oracle Extreme apprend « ce titre va faire un gros mouvement » :
``oracle_extreme10 = oracle_top10 OR oracle_bottom10`` (TOP/BOTTOM 10 %
cross-sectionnel du jour). Il ne prédit PAS la direction (cf. E0/D0/D1/D1d).

Ablations (spec §7) :
- ``O0`` = features B25 (expert + xs_ranks), **sans** ``global_rank_20`` ;
- ``O1`` = O0 + ``global_rank_20`` + features Oracle spécialisées (§7C) ;
- ``O2`` = familles réduites : momentum / volume / volatility / market regime.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from modelFactory.data_loader import load_benchmark_bars, load_universe_bars
from modelFactory.features import compute_features, get_feature_columns
from modelFactory.global_ranking import _XS_RANK_SOURCE_FEATURES, _xs_rank_column_name

# ── Colonnes de target / garde ──
# oracle_extreme10 = 1 si le titre est dans le TOP 10 % OU le BOTTOM 10 %
# cross-sectionnel du jour (gros mouvement H20). Anciennement oracle_top10.
TARGET_COL = "oracle_extreme10"
GUARD_COL = "oracle_available_date"
GLOBAL_RANK_COL = "global_rank_20"

# Features Oracle spécialisées (§7C) — calculées en plus du set B25.
ORACLE_EXTRA_FEATURES: list[str] = ["drawdown_20", "high_low_position_20"]

# Redondances exactes du contrat EXPERT à ne jamais présenter au modèle Oracle.
# On conserve les noms historiques les plus directs (``ema*_distance`` et
# ``momentum_*``). Les colonnes restent calculées par le moteur partagé pour ne
# pas modifier les autres familles de modèles, mais elles sont retirées du
# contrat Oracle avant l'entraînement et le serving.
ORACLE_REDUNDANT_FEATURES: frozenset[str] = frozenset({
    "distance_ema20",       # == ema20_distance
    "distance_ema50",       # == ema50_distance
    "return_5d",            # == momentum_5
    "return_10d",           # == momentum_10
    "return_20d",           # == momentum_20
    "log_return_xs_rank",   # == daily_return_xs_rank (même ordre cross-sectionnel)
})

# Familles pour l'ablation O2 (le « set allégé »).
_MOMENTUM_PREFIXES = ("momentum_", "relative_strength_", "accel_", "decay_")
_VOLUME_PREFIXES = ("volume_", "dollar_volume_", "amihud_", "obv_", "up_volume_",
                    "volume_price_corr_", "volume_skew_", "volume_zscore_", "close_to_vwap")
_VOLATILITY_PREFIXES = ("rolling_volatility_", "atr_", "vol_ratio_", "vol_expansion", "intraday_range")
_REGIME_PREFIXES = ("regime_", "market_", "SPY_", "VIX_")


def expert_feature_columns() -> list[str]:
    """Liste canonique des features expert (même moteur que B25)."""
    return list(get_feature_columns(feature_set="expert"))


def deduplicate_oracle_feature_columns(features: list[str]) -> list[str]:
    """Retire les alias sémantiques connus du contrat Oracle en préservant l'ordre."""
    return [column for column in features if column not in ORACLE_REDUNDANT_FEATURES]


def lean_feature_columns(features: list[str]) -> list[str]:
    """O2 — familles momentum / volume / volatility / market regime."""
    prefixes = _MOMENTUM_PREFIXES + _VOLUME_PREFIXES + _VOLATILITY_PREFIXES + _REGIME_PREFIXES
    return [c for c in features if c.startswith(prefixes)]


def build_feature_matrix(
    engine: Any,
    symbols: list[str],
    *,
    start_date: str,
    end_date: str,
    feature_set: str = "expert",
) -> pd.DataFrame:
    """Calcule les features PIT par symbole + rangs cross-sectionnels + extras Oracle.

    Les barres sont chargées avec ~3 ans de warm-up avant ``start_date`` pour
    alimenter les fenêtres roulantes (momentum_250, z-scores 1 an min).
    """
    warmup_start = (pd.Timestamp(start_date) - pd.Timedelta(days=1100)).date().isoformat()
    bars = load_universe_bars(engine, symbols, start_date=warmup_start, end_date=end_date)
    if bars.empty:
        return pd.DataFrame()
    benchmark = load_benchmark_bars(engine, "SPY", start_date=warmup_start, end_date=end_date)

    parts: list[pd.DataFrame] = []
    for _, group in bars.groupby("symbol"):
        feats = compute_features(group, benchmark_df=benchmark, feature_set=feature_set)
        if feats.empty:
            continue
        # Features Oracle spécialisées (§7C) — calculées sur adj_close.
        if "adj_close" in feats.columns:
            close = feats["adj_close"].astype(float)
            feats["drawdown_20"] = close / close.rolling(20).max() - 1.0
            roll_min = close.rolling(20).min()
            roll_max = close.rolling(20).max()
            feats["high_low_position_20"] = (close - roll_min) / (roll_max - roll_min).clip(lower=1e-8)
        else:
            feats["drawdown_20"] = 0.0
            feats["high_low_position_20"] = 0.5
        parts.append(feats)

    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)

    # ── Rangs percentiles cross-sectionnels (même normalisation que B25) ──
    xs_available = [c for c in _XS_RANK_SOURCE_FEATURES if c in df.columns]
    if xs_available:
        ranked = df.groupby("date")[xs_available].rank(pct=True)
        ranked.columns = [_xs_rank_column_name(c) for c in xs_available]
        df = pd.concat([df, ranked], axis=1)
    return df


def load_global_rank_feature(engine: Any, batch_id: str) -> pd.DataFrame:
    """Relit ``global_rank_20`` depuis ``global_rank_history`` (jamais recalculé)."""
    query = text(
        "SELECT `date`, symbol, global_rank_20 FROM global_rank_history "
        "WHERE batch_id = :bid AND global_rank_20 IS NOT NULL"
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"bid": batch_id}, parse_dates=["date"])
    return df


def load_oracle_targets(engine: Any, batch_id: str, horizon: int = 20) -> pd.DataFrame:
    """Relit les targets Oracle depuis ``global_oracle_labels``."""
    query = text(
        "SELECT prediction_date, symbol, oracle_extreme10, oracle_pct_rank, oracle_decile, "
        "future_return, oracle_available_date FROM global_oracle_labels "
        "WHERE batch_id = :bid AND horizon = :h"
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"bid": batch_id, "h": horizon})
    df["prediction_date"] = pd.to_datetime(df["prediction_date"]).dt.normalize()
    df["oracle_available_date"] = pd.to_datetime(df["oracle_available_date"]).dt.normalize()
    return df


def build_dataset(
    engine: Any,
    batch_id: str,
    symbols: list[str],
    *,
    start_date: str,
    end_date: str,
    horizon: int = 20,
    require_global_rank: bool = True,
    need_targets: bool = True,
    feature_whitelist: list[str] | tuple[str, ...] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Assemble features + global_rank_20 + target Oracle.

    Args:
        require_global_rank: si False (standalone ``--oracle-model-only``, sans
            ``global_rank_history``), on ne fusionne pas ``global_rank_20`` —
            l'univers vient alors des targets ``global_oracle_labels``.
        need_targets: si False (PRÉDICTION standard ``predict_oracle_extreme_history``),
            les labels Oracle sont OPTIONNELS : LEFT JOIN sur ``global_oracle_labels``.
            On prédit sur toute date ayant des features, même sans label encore
            réalisé (même logique que le Global Rank). ``future_return`` et
            ``oracle_extreme10`` sont alors NULL. L'anti-leakage (``oracle_available_date``)
            ne s'applique qu'aux lignes labellisées.

    Returns:
        ``(dataset, feature_columns)`` — ``feature_columns`` = liste O0 (sans
        ``global_rank_20`` ni extras Oracle). Les colonnes ``global_rank_20`` et
        ``ORACLE_EXTRA_FEATURES`` sont présentes dans le DataFrame mais pas dans
        cette liste (elles constituent les ablations O1).
    """
    feats = build_feature_matrix(engine, symbols, start_date=start_date, end_date=end_date)
    if feats.empty:
        return pd.DataFrame(), []

    base_cols = [c for c in expert_feature_columns() if c in feats.columns]
    xs_cols = [c for c in feats.columns if c.endswith("_xs_rank")]
    feature_columns = deduplicate_oracle_feature_columns(base_cols + xs_cols)  # O0
    if feature_whitelist is not None:
        requested = [str(column).strip() for column in feature_whitelist if str(column).strip()]
        available = set(feature_columns)
        feature_columns = [column for column in requested if column in available]
        missing = [column for column in requested if column not in available]
        if missing:
            raise ValueError(
                "Profil Oracle incompatible avec le dataset: features absentes="
                + ",".join(missing)
            )
        if not feature_columns:
            raise ValueError("Profil Oracle vide après résolution du dataset.")

    targets = load_oracle_targets(engine, batch_id, horizon)

    if require_global_rank:
        ranks = load_global_rank_feature(engine, batch_id)
        df = feats.merge(ranks, on=["date", "symbol"], how="inner")
    else:
        # Standalone O0 : pas de global_rank_history → l'univers = features.
        df = feats.copy()
    if need_targets:
        df = df.merge(
            targets,
            left_on=["date", "symbol"],
            right_on=["prediction_date", "symbol"],
            how="inner",
        )
        df = df.drop(columns=["prediction_date"])
        # Garde anti-leakage et contrat d'entraînement : une ligne dont le
        # rang cross-sectionnel n'a pas pu être calculé ne doit jamais arriver
        # au classifieur binaire ni être convertie implicitement en entier.
        df = df[
            df[TARGET_COL].notna()
            & df[GUARD_COL].notna()
            & (df[GUARD_COL] > df["date"])
        ]
    else:
        # Prédiction standard : labels optionnels (NULL si pas encore réalisés).
        df = df.merge(
            targets,
            left_on=["date", "symbol"],
            right_on=["prediction_date", "symbol"],
            how="left",
        )
        df = df.drop(columns=["prediction_date"])
        # Anti-leakage uniquement si un label est présent ; une ligne sans label
        # (prédiction forward) est conservée telle quelle.
        df = df[(df[GUARD_COL].isna()) | (df[GUARD_COL] > df["date"])]
    return df, feature_columns


def split_dataset(
    df: pd.DataFrame,
    *,
    train_cutoff: str,
    valid_start: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split temporel sans leakage : train = labels disponibles avant cutoff,
    valid = prédictions faites après ``valid_start``."""
    train = df[df[GUARD_COL] <= pd.Timestamp(train_cutoff)]
    valid = df[df["date"] >= pd.Timestamp(valid_start)]
    return train, valid


def ablation_features(
    feature_columns: list[str],
    *,
    include_global_rank: bool,
    include_oracle_extras: bool,
    lean: bool = False,
) -> list[str]:
    """Construit la liste de features d'une ablation (O0/O1/O2)."""
    if lean:
        return lean_feature_columns(feature_columns)
    cols = list(feature_columns)
    if include_global_rank:
        cols.append(GLOBAL_RANK_COL)
    if include_oracle_extras:
        cols.extend(ORACLE_EXTRA_FEATURES)
    return cols
