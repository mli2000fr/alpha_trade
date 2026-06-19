"""
Phase 3.3.a — Composition des scores, neutralisation sectorielle et sélection.

Extrait de ``selector.alpha_scanner``. Contient :

- ``merge_scores(computed_df, scores_df, config)`` : fusion facteurs recalculés
  + scores screener (RSI, total_score) + winsorisation/normalisation +
  composition multi-facteurs avec poids configurables (weight_trend_vcp /
  weight_total_score / weight_rsi).
- ``apply_factor_neutralization(df, config)`` : z-score intra-secteur appliqué
  sur l'univers complet (cross-sectional) puis recomposition du final_score.
- ``apply_sector_neutrality(ranked_df, config)`` : sélection round-robin avec
  plafond sectoriel (sector_cap_ratio).
- ``rank_and_select(merged_df, config)`` : tri global, neutralisation
  sectorielle, top N final.

Toutes les fonctions sont pures (pas d'I/O DB).
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from selector.factors import FACTOR_COLUMNS, winsorize_and_normalize

if TYPE_CHECKING:  # pragma: no cover
    from selector.alpha_scanner import AlphaScannerConfig

LOGGER = logging.getLogger(__name__)

SCORE_COLUMNS = [
    "symbol",
    "liquidity_val",
    "relative_strength_index",
    "total_score",
    "sector",
    "market_cap",
    "beta_126",
    "spread_bps",
    "earnings_date",
    "days_to_earnings",
    "earnings_blackout",
    "sanitizer_status",
    "anomaly_count",
    "missing_days_count",
]
PERSISTED_SELECTOR_REQUIRED_COLUMNS = [
    "symbol",
    "trend_score",
    "vcp_score",
    "final_score",
    "market_cap",
    "beta_126",
    "spread_bps",
    "earnings_date",
    "days_to_earnings",
    "earnings_blackout",
]
PERSISTED_SELECTOR_OPTIONAL_COLUMNS = [
    "candidate_rank",
    "raw_final_score",
    "normalized_total_score",
    "normalized_rsi",
    "total_score_neutralized",
    "relative_strength_index_neutralized",
    "trend_vcp_component",
    "total_score_component",
    "rsi_component",
    "atr_pct_20",
    "weekly_trend_score",
    "high_52w_proximity",
    "volatility_ratio",
    "selector_signal_mode",
    "selection_explanation",
]
PERSISTED_SELECTOR_SCORE_COLUMNS = [
    *PERSISTED_SELECTOR_REQUIRED_COLUMNS,
    *PERSISTED_SELECTOR_OPTIONAL_COLUMNS,
]
OUTPUT_COLUMNS = [
    "rank",
    "symbol",
    "candidate_rank",
    "sector",
    "latest_close",
    "avg_dollar_volume_20d",
    "liquidity_val",
    "relative_strength_index",
    "total_score",
    "trend_score",
    "vcp_score",
    "raw_final_score",
    "final_score",
    "trend_vcp_component",
    "total_score_component",
    "rsi_component",
    "normalized_total_score",
    "normalized_rsi",
    "total_score_neutralized",
    "relative_strength_index_neutralized",
    "selector_signal_mode",
    "selection_explanation",
    "volatility_ratio",
    "atr_20",
    "atr_pct_20",
    "market_cap",
    "beta_126",
    "spread_bps",
    "earnings_date",
    "days_to_earnings",
    "earnings_blackout",
    "ma50",
    "ma150",
    "ma200",
    "high_52w",
    "low_52w",
    "high_52w_proximity",
    "weekly_close",
    "weekly_ma10",
    "weekly_ma30",
    "weekly_trend_score",
    "history_days",
    "anomaly_count",
    "missing_days_count",
]

SELECTION_EXPLANATION_MAX_LENGTH = 255


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_selection_explanation(row: pd.Series) -> str:
    parts = [f"mode={str(row.get('selector_signal_mode') or 'factor_only').strip() or 'factor_only'}"]
    for label, column in (
        ("trend_vcp", "trend_vcp_component"),
        ("total", "total_score_component"),
        ("rsi", "rsi_component"),
    ):
        value = _safe_float(row.get(column))
        if value is not None:
            parts.append(f"{label}={value:.4f}")
    final_score = _safe_float(row.get("final_score"))
    if final_score is not None:
        parts.append(f"final={final_score:.4f}")
    explanation = "; ".join(parts)
    return explanation[:SELECTION_EXPLANATION_MAX_LENGTH]


def _apply_selection_explainability(
    df: pd.DataFrame,
    *,
    trend_vcp_component: pd.Series,
    total_score_component: pd.Series,
    rsi_component: pd.Series,
    aux_mode_label: str,
) -> pd.DataFrame:
    result = df.copy()
    result["trend_vcp_component"] = pd.Series(
        pd.to_numeric(trend_vcp_component, errors="coerce"),
        index=result.index,
    ).fillna(0.0)
    result["total_score_component"] = pd.Series(
        pd.to_numeric(total_score_component, errors="coerce"),
        index=result.index,
    ).fillna(0.0)
    result["rsi_component"] = pd.Series(
        pd.to_numeric(rsi_component, errors="coerce"),
        index=result.index,
    ).fillna(0.0)
    result["selector_signal_mode"] = "factor_only"
    aux_mask = result[["total_score_component", "rsi_component"]].abs().sum(axis=1) > 1e-12
    result.loc[aux_mask, "selector_signal_mode"] = aux_mode_label
    result["raw_final_score"] = (
        result["trend_vcp_component"]
        + result["total_score_component"]
        + result["rsi_component"]
    )
    result["final_score"] = result["raw_final_score"]
    result["selection_explanation"] = result.apply(_build_selection_explanation, axis=1)
    return result


def merge_scores(
    computed_df: pd.DataFrame,
    scores_df: pd.DataFrame,
    config: AlphaScannerConfig,
) -> pd.DataFrame:
    """
    Fusionne facteurs recalculés et scores auxiliaires.

    Normalisation : winsorisation [winsor_lower_pct, winsor_upper_pct] + min-max → [0, 1].
    Composition   : poids configurables via AlphaScannerConfig.

    NOTE : la neutralisation sectorielle (cross-sectional z-score) est appliquée
    APRÈS, dans ``apply_factor_neutralization``, une fois le secteur connu pour
    l'ensemble de l'univers (après ``enrich_and_filter_equities`` + concat des
    chunks).
    """
    if computed_df.empty:
        return pd.DataFrame(
            columns=FACTOR_COLUMNS + SCORE_COLUMNS + PERSISTED_SELECTOR_OPTIONAL_COLUMNS
        )

    scores = scores_df.copy() if not scores_df.empty else pd.DataFrame(columns=SCORE_COLUMNS)
    merged = computed_df.merge(scores, on="symbol", how="left", suffixes=("", "_aux"))

    merged["normalized_total_score"] = winsorize_and_normalize(
        merged.get("total_score"),
        lower_pct=config.winsor_lower_pct,
        upper_pct=config.winsor_upper_pct,
    )
    merged["normalized_rsi"] = winsorize_and_normalize(
        merged.get("relative_strength_index"),
        lower_pct=config.winsor_lower_pct,
        upper_pct=config.winsor_upper_pct,
    )
    merged["sector"] = (
        merged.get("sector").where(merged.get("sector").notna(), "Unknown")
        if "sector" in merged.columns
        else "Unknown"
    )

    factor_component = 0.5 * (
        merged["trend_score"].fillna(0.0) + merged["vcp_score"].fillna(0.0)
    )
    aux_mask = merged[["total_score", "relative_strength_index"]].notna().any(axis=1)
    trend_component = factor_component.copy()
    total_component = pd.Series(0.0, index=merged.index, dtype=float)
    rsi_component = pd.Series(0.0, index=merged.index, dtype=float)
    trend_component.loc[aux_mask] = config.weight_trend_vcp * factor_component[aux_mask]
    total_component.loc[aux_mask] = (
        config.weight_total_score * merged.loc[aux_mask, "normalized_total_score"].fillna(0.0)
    )
    rsi_component.loc[aux_mask] = config.weight_rsi * merged.loc[aux_mask, "normalized_rsi"].fillna(0.0)
    merged["candidate_rank"] = np.nan
    merged["total_score_neutralized"] = np.nan
    merged["relative_strength_index_neutralized"] = np.nan
    return _apply_selection_explainability(
        merged,
        trend_vcp_component=trend_component,
        total_score_component=total_component,
        rsi_component=rsi_component,
        aux_mode_label="multi_factor",
    )


def apply_factor_neutralization(
    df: pd.DataFrame,
    config: AlphaScannerConfig,
) -> pd.DataFrame:
    """
    Neutralisation cross-sectorielle (P0) — appliquée sur l'univers COMPLET
    après concaténation de tous les chunks, une fois le secteur connu.

    Pour chaque facteur (relative_strength_index, total_score) :
      1. Calcule le z-score intra-secteur (mean=0, std=1 par secteur)
      2. Winsorise + normalise en [0, 1]
      3. Remplace la composante correspondante dans final_score
    """
    if not config.neutralize_by_sector or df.empty:
        return df

    if "sector" not in df.columns or df["sector"].isna().all():
        LOGGER.warning(
            "Neutralisation sectorielle desactivee : colonne sector absente ou entierement nulle."
        )
        return df

    result = df.copy()
    result["sector"] = result["sector"].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")

    def _intra_sector_zscore(series: pd.Series) -> pd.Series:
        """Z-score robuste par secteur (ddof=0, fallback 0.0 si std≈0)."""
        mu = series.mean()
        sigma = series.std(ddof=0)
        if sigma < 1e-9:
            return pd.Series(0.0, index=series.index)
        return (series - mu) / sigma

    factors_to_neutralize = [
        col for col in ["relative_strength_index", "total_score"]
        if col in result.columns and result[col].notna().any()
    ]

    for col in factors_to_neutralize:
        z_col = f"{col}_sector_z"
        result[z_col] = result.groupby("sector")[col].transform(_intra_sector_zscore)
        result[f"{col}_neutralized"] = winsorize_and_normalize(
            result[z_col],
            lower_pct=config.winsor_lower_pct,
            upper_pct=config.winsor_upper_pct,
        )

    LOGGER.info(
        "Neutralisation sectorielle appliquee | univers=%s secteurs=%s facteurs=%s",
        len(result),
        result["sector"].nunique(),
        factors_to_neutralize,
    )

    factor_component = 0.5 * (
        result["trend_score"].fillna(0.0) + result["vcp_score"].fillna(0.0)
    )

    rsi_neutralized = result.get("relative_strength_index_neutralized")
    total_neutralized = result.get("total_score_neutralized")

    aux_mask = pd.Series(False, index=result.index)
    if rsi_neutralized is not None:
        aux_mask |= rsi_neutralized.notna()
    if total_neutralized is not None:
        aux_mask |= total_neutralized.notna()

    result["total_score_neutralized"] = (
        pd.to_numeric(total_neutralized, errors="coerce") if total_neutralized is not None else np.nan
    )
    result["relative_strength_index_neutralized"] = (
        pd.to_numeric(rsi_neutralized, errors="coerce") if rsi_neutralized is not None else np.nan
    )
    trend_component = factor_component.copy()
    total_component = pd.Series(0.0, index=result.index, dtype=float)
    rsi_component = pd.Series(0.0, index=result.index, dtype=float)
    if aux_mask.any():
        trend_component.loc[aux_mask] = config.weight_trend_vcp * factor_component[aux_mask]
        if total_neutralized is not None:
            total_component.loc[aux_mask] = (
                config.weight_total_score * total_neutralized[aux_mask].fillna(0.0)
            )
        if rsi_neutralized is not None:
            rsi_component.loc[aux_mask] = config.weight_rsi * rsi_neutralized[aux_mask].fillna(0.0)
    return _apply_selection_explainability(
        result,
        trend_vcp_component=trend_component,
        total_score_component=total_component,
        rsi_component=rsi_component,
        aux_mode_label="sector_neutralized",
    )


def apply_sector_neutrality(
    ranked_df: pd.DataFrame,
    config: AlphaScannerConfig,
) -> pd.DataFrame:
    """Sélection round-robin avec plafond sectoriel."""
    if ranked_df.empty:
        return ranked_df.copy()

    target_size = min(config.selection_size, len(ranked_df))
    sector_cap = max(1, int(np.floor(config.selection_size * config.sector_cap_ratio)))
    LOGGER.info(
        "Neutralisation sectorielle | candidats=%s cible=%s plafond_par_secteur=%s",
        len(ranked_df),
        target_size,
        sector_cap,
    )
    prepared = ranked_df.copy()
    prepared["sector"] = prepared["sector"].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
    prepared = prepared.sort_values(
        ["final_score", "trend_score", "vcp_score", "avg_dollar_volume_20d"],
        ascending=False,
    ).reset_index(drop=True)

    groups = {
        sector: group.reset_index(drop=True)
        for sector, group in prepared.groupby("sector", sort=False)
    }
    pointers = dict.fromkeys(groups, 0)
    counts: Counter[str] = Counter()
    selected_rows: list[pd.Series] = []

    while len(selected_rows) < target_size:
        available: list[tuple[float, str]] = []
        for sector, group in groups.items():
            sector_name = str(sector)
            pointer = pointers[sector]
            if (sector_name != "Unknown" and counts[sector_name] >= sector_cap) or pointer >= len(group):
                continue
            available.append((float(group.iloc[pointer]["final_score"]), sector_name))

        if not available:
            break

        for _, sector in sorted(available, key=lambda item: item[0], reverse=True):
            if len(selected_rows) >= target_size:
                break
            pointer = pointers[sector]
            group = groups[sector]
            if (sector != "Unknown" and counts[sector] >= sector_cap) or pointer >= len(group):
                continue
            selected_rows.append(group.iloc[pointer])
            pointers[sector] += 1
            counts[sector] += 1

    if not selected_rows:
        return prepared.iloc[0:0].copy()

    selected = pd.DataFrame(selected_rows).reset_index(drop=True)
    LOGGER.info(
        "Neutralisation terminee | retenus=%s secteurs=%s repartition=%s",
        len(selected),
        selected["sector"].nunique(),
        selected["sector"].value_counts().to_dict(),
    )
    return selected


def rank_and_select(
    merged_df: pd.DataFrame,
    config: AlphaScannerConfig,
) -> pd.DataFrame:
    """Trie, neutralise par secteur et retourne le top final."""
    if merged_df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    LOGGER.info("Classement final | candidats_eligibles=%s", len(merged_df))

    ranked = merged_df.sort_values(
        ["final_score", "trend_score", "vcp_score", "avg_dollar_volume_20d"],
        ascending=False,
    ).reset_index(drop=True)
    selected = apply_sector_neutrality(ranked, config)
    if selected.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    selected = selected.sort_values(
        ["final_score", "trend_score", "vcp_score", "avg_dollar_volume_20d"],
        ascending=False,
    ).reset_index(drop=True)
    selected.insert(0, "rank", np.arange(1, len(selected) + 1))
    selected["candidate_rank"] = selected["rank"]
    LOGGER.info("Classement termine | selection_finale=%s top3=%s", len(selected), selected["symbol"].head(3).tolist())
    for column in OUTPUT_COLUMNS:
        if column not in selected.columns:
            selected[column] = np.nan
    return selected.loc[:, OUTPUT_COLUMNS].copy()


def rank_and_select_short(
    merged_df: pd.DataFrame,
    config: AlphaScannerConfig,
    *,
    long_selected_symbols: set[str] | None = None,
) -> pd.DataFrame:
    """Selection short parallele basee sur le short_score dedie.

    Plan v2 Sprint 5 — les candidats short sont selectionnes independamment
    des longs, via le score calcule par ``selector/short_score.py``.

    La colonne ``short_score`` doit deja etre presente dans ``merged_df``.
    Les symboles deja selectionnes en long sont exclus.
    """
    if merged_df.empty or config.short_selection_size <= 0:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    if "short_score" not in merged_df.columns:
        LOGGER.warning("rank_and_select_short: short_score column missing, skipping short selection")
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    short_candidates = merged_df.copy()
    # Exclure les symboles deja selectionnes en long (evite les doublons)
    if long_selected_symbols:
        short_candidates = short_candidates[~short_candidates["symbol"].isin(long_selected_symbols)]

    if short_candidates.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    short_candidates = short_candidates.sort_values(
        ["short_score", "avg_dollar_volume_20d"],
        ascending=[False, False],
    ).reset_index(drop=True)

    target_size = min(config.short_selection_size, len(short_candidates))
    selected = short_candidates.head(target_size).copy()
    selected.insert(0, "rank", np.arange(1, len(selected) + 1))
    selected["candidate_rank"] = selected["rank"]
    selected["selector_signal_mode"] = "short"

    LOGGER.info(
        "Classement short termine | selection_finale=%s/%s top3=%s",
        len(selected),
        config.short_selection_size,
        selected["symbol"].head(3).tolist(),
    )
    for column in OUTPUT_COLUMNS:
        if column not in selected.columns:
            selected[column] = np.nan
    return selected.loc[:, OUTPUT_COLUMNS].copy()

