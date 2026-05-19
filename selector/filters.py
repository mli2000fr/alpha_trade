"""
Phase 3.3.a — Filtres univers et statistiques de rejet (pur, sans I/O).

Extrait de ``selector.alpha_scanner``. Contient :

- ``apply_filters_with_stats(merged_df, config)`` : applique tous les filtres
  (historique, prix, liquidité, volatilité, ATR, RSI, MA200, high 52w, weekly
  trend, market_cap + TTL, beta, spread + relâchement IEX, earnings blackout,
  liquidité scores, sanitizer, anomalies, missing days) et retourne le DataFrame
  filtré + un dict de stats granulaires (consommé par le ``run_summary``).
- ``log_filter_stats(stats)`` : logger INFO compact d'une exécution.
- ``enrich_and_filter_equities(merged_df, metadata_df)`` : exclusion ETF/fonds
  via ``stock_metadata`` (asset_class, status, tradable, history_status, regex
  nom).
- ``merge_optional_symbol_overlays(merged_df, quotes_df, earnings_df)`` :
  superpose snapshots quotes (spread/bid/ask) et calendrier earnings.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from database.assets import (
    HISTORY_STATUS_EXCLUDED_BY_POLICY,
    HISTORY_STATUS_NO_HISTORY,
    HISTORY_STATUS_PENDING,
    HISTORY_STATUS_PROVIDER_ERROR,
    HISTORY_STATUS_READY,
    HISTORY_STATUS_SUSPENDED_OR_STALE,
)

if TYPE_CHECKING:  # pragma: no cover
    from selector.alpha_scanner import AlphaScannerConfig

LOGGER = logging.getLogger(__name__)

METADATA_COLUMNS = [
    "symbol",
    "company_name",
    "asset_class",
    "status",
    "tradable",
    "bars_available",
    "history_status",
    "sector",
    "market_cap",
    # Phase 3.3.d — TTL filtre market_cap (selector consomme la fraîcheur).
    "market_cap_refreshed_at",
]
ELIGIBLE_HISTORY_STATUSES = {HISTORY_STATUS_PENDING, HISTORY_STATUS_READY}
ETF_NAME_PATTERNS = (
    "etf",
    "etn",
    "fund",
    "index fund",
    "ishares",
    "spdr",
    "vanguard",
    "invesco",
    "proshares",
    "direxion",
    "wisdomtree",
    "global x",
    "first trust",
    "xtrackers",
    "schwab",
    "bond",
    "treasury",
)


def apply_filters_with_stats(
    merged_df: pd.DataFrame,
    config: AlphaScannerConfig,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Applique les filtres univers et retourne ``(df_filtré, stats_par_filtre)``."""
    if merged_df.empty:
        empty_stats = {
            "input": 0,
            "output": 0,
            "rejected_etf": 0,
            "rejected_history": 0,
            "rejected_price": 0,
            "rejected_market_liquidity": 0,
            "rejected_volatility": 0,
            "rejected_atr": 0,
            "rejected_relative_strength": 0,
            "rejected_ma200": 0,
            "rejected_high_52w": 0,
            "rejected_weekly": 0,
            "rejected_market_cap": 0,
            "rejected_market_cap_stale": 0,
            "rejected_beta": 0,
            "rejected_spread": 0,
            "rescued_spread_iex": 0,
            "rejected_earnings_blackout": 0,
            "rejected_score_liquidity": 0,
            "rejected_anomalies": 0,
            "rejected_missing_days": 0,
        }
        return merged_df.copy(), empty_stats

    filtered = merged_df.copy()
    before_count = len(filtered)

    # Exclusion ETF / crypto : seules les actions us_equity actives et tradables sont retenues.
    # (Le JOIN stock_metadata dans _iter_eligible_symbol_chunks filtre déjà en amont ;
    #  ce filtre pandas est un filet de sécurité au cas où metadata_df serait partielle.)
    if "asset_class" in filtered.columns:
        before_etf = len(filtered)
        filtered = filtered[filtered["asset_class"].isna() | (filtered["asset_class"] == "us_equity")]
        after_etf = len(filtered)
        if before_etf - after_etf:
            LOGGER.info("Filtre ETF/crypto | rejetes=%s", before_etf - after_etf)
    if "tradable" in filtered.columns:
        filtered = filtered[filtered["tradable"].isna() | (filtered["tradable"] == True)]  # noqa: E712

    after_etf_filter = len(filtered)
    filtered = filtered[filtered["history_days"] >= config.min_history_days]
    after_history = len(filtered)
    filtered = filtered[filtered["latest_close"] > config.min_close]
    after_close = len(filtered)
    filtered = filtered[filtered["avg_dollar_volume_20d"] > config.liquidity_threshold]
    after_market_liquidity = len(filtered)

    if config.max_volatility_ratio is not None:
        if "volatility_ratio" not in filtered.columns:
            LOGGER.warning(
                "Filtre volatilite relative active mais colonne volatility_ratio absente; aucun titre retenu."
            )
            filtered = filtered.iloc[0:0].copy()
        else:
            filtered = filtered[
                filtered["volatility_ratio"].notna()
                & (filtered["volatility_ratio"] <= config.max_volatility_ratio)
            ]
    after_volatility = len(filtered)

    if config.min_atr_pct_20 is not None or config.max_atr_pct_20 is not None:
        if "atr_pct_20" not in filtered.columns:
            LOGGER.warning(
                "Filtre ATR %% active mais colonne atr_pct_20 absente; aucun titre retenu."
            )
            filtered = filtered.iloc[0:0].copy()
        else:
            atr_mask = filtered["atr_pct_20"].notna()
            if config.min_atr_pct_20 is not None:
                atr_mask &= filtered["atr_pct_20"] >= config.min_atr_pct_20
            if config.max_atr_pct_20 is not None:
                atr_mask &= filtered["atr_pct_20"] <= config.max_atr_pct_20
            filtered = filtered[atr_mask]
    after_atr = len(filtered)

    if config.min_relative_strength_index is not None:
        if "relative_strength_index" not in filtered.columns:
            LOGGER.warning(
                "Filtre force relative active mais colonne relative_strength_index absente; aucun titre retenu."
            )
            filtered = filtered.iloc[0:0].copy()
        else:
            filtered = filtered[
                filtered["relative_strength_index"].notna()
                & (filtered["relative_strength_index"] >= config.min_relative_strength_index)
            ]
    after_relative_strength = len(filtered)

    if config.require_above_ma200:
        required_ma200_cols = {"ma200", "latest_close"}
        if not required_ma200_cols.issubset(filtered.columns):
            LOGGER.warning(
                "Filtre close>MA200 active mais colonnes requises absentes; aucun titre retenu."
            )
            filtered = filtered.iloc[0:0].copy()
        else:
            filtered = filtered[filtered["ma200"].notna() & (filtered["latest_close"] > filtered["ma200"])]
    after_ma200 = len(filtered)

    if config.min_high_52w_proximity is not None:
        if "high_52w_proximity" not in filtered.columns:
            LOGGER.warning(
                "Filtre proximité high 52w active mais colonne high_52w_proximity absente; aucun titre retenu."
            )
            filtered = filtered.iloc[0:0].copy()
        else:
            filtered = filtered[
                filtered["high_52w_proximity"].notna()
                & (filtered["high_52w_proximity"] >= config.min_high_52w_proximity)
            ]
    after_high_52w = len(filtered)

    if config.min_weekly_trend_score is not None:
        if "weekly_trend_score" not in filtered.columns:
            LOGGER.warning(
                "Filtre weekly trend active mais colonne weekly_trend_score absente; aucun titre retenu."
            )
            filtered = filtered.iloc[0:0].copy()
        else:
            filtered = filtered[
                filtered["weekly_trend_score"].notna()
                & (filtered["weekly_trend_score"] >= config.min_weekly_trend_score)
            ]
    after_weekly = len(filtered)

    if config.min_market_cap is not None:
        if "market_cap" not in filtered.columns:
            LOGGER.warning(
                "Filtre market cap active mais colonne market_cap absente; aucun titre retenu."
            )
            filtered = filtered.iloc[0:0].copy()
        else:
            filtered = filtered[
                filtered["market_cap"].notna()
                & (pd.to_numeric(filtered["market_cap"], errors="coerce") >= config.min_market_cap)
            ]
    after_market_cap = len(filtered)

    # Phase 3.3.d — TTL sur la fraîcheur de market_cap_refreshed_at.
    rejected_market_cap_stale = 0
    if (
        config.market_cap_max_age_days is not None
        and config.min_market_cap is not None
        and "market_cap_refreshed_at" in filtered.columns
        and not filtered.empty
    ):
        refreshed_at = pd.to_datetime(
            filtered["market_cap_refreshed_at"], errors="coerce", utc=True
        )
        now_utc = pd.Timestamp.now(tz="UTC")
        age_days = (now_utc - refreshed_at).dt.total_seconds() / 86400.0
        stale_mask = refreshed_at.isna() | (
            age_days > float(config.market_cap_max_age_days)
        )
        rejected_market_cap_stale = int(stale_mask.sum())
        if rejected_market_cap_stale:
            LOGGER.info(
                "Filtre market_cap TTL | seuil_jours=%s rejets=%s",
                config.market_cap_max_age_days,
                rejected_market_cap_stale,
            )
        filtered = filtered[~stale_mask]
    after_market_cap_ttl = len(filtered)

    if config.min_beta_126 is not None:
        if "beta_126" not in filtered.columns:
            LOGGER.warning(
                "Filtre beta 126 active mais colonne beta_126 absente; aucun titre retenu."
            )
            filtered = filtered.iloc[0:0].copy()
        else:
            filtered = filtered[
                filtered["beta_126"].notna()
                & (pd.to_numeric(filtered["beta_126"], errors="coerce") >= config.min_beta_126)
            ]
    after_beta = len(filtered)

    # Phase 3.3.c — filtre spread avec relâchement IEX contrôlé.
    rejected_spread_iex_relaxed = 0
    if config.max_spread_bps is not None:
        if "spread_bps" not in filtered.columns:
            LOGGER.warning(
                "Filtre spread active mais colonne spread_bps absente; aucun titre retenu."
            )
            filtered = filtered.iloc[0:0].copy()
        else:
            spread_numeric = pd.to_numeric(filtered["spread_bps"], errors="coerce")
            strict_mask = spread_numeric.notna() & (spread_numeric <= config.max_spread_bps)
            stale_quote_mask = pd.Series(False, index=filtered.index)
            if "quote_timestamp" in filtered.columns and "quote_date" in filtered.columns:
                quote_timestamps = pd.to_datetime(filtered["quote_timestamp"], errors="coerce", utc=False)
                quote_dates = pd.to_datetime(filtered["quote_date"], errors="coerce", utc=False)
                stale_quote_mask = (
                    quote_timestamps.notna()
                    & quote_dates.notna()
                    & (quote_timestamps.dt.normalize() < quote_dates.dt.normalize())
                )
                stale_quote_count = int(stale_quote_mask.sum())
                if stale_quote_count:
                    LOGGER.info(
                        "Filtre spread | quotes stale ignorees=%s (quote_timestamp < quote_date)",
                        stale_quote_count,
                    )

            if (
                config.max_spread_bps_iex is not None
                and config.min_quote_size is not None
                and "bid_size" in filtered.columns
                and "ask_size" in filtered.columns
            ):
                bid_size = pd.to_numeric(filtered["bid_size"], errors="coerce")
                ask_size = pd.to_numeric(filtered["ask_size"], errors="coerce")
                iex_mask = (
                    spread_numeric.notna()
                    & (spread_numeric > config.max_spread_bps)
                    & (spread_numeric <= config.max_spread_bps_iex)
                    & bid_size.notna()
                    & ask_size.notna()
                    & (bid_size >= config.min_quote_size)
                    & (ask_size >= config.min_quote_size)
                )
                rejected_spread_iex_relaxed = int(iex_mask.sum())
                if rejected_spread_iex_relaxed:
                    LOGGER.info(
                        "Relâchement IEX spread | strict=%s bps relâché<=%s bps min_size=%s rescues=%s",
                        config.max_spread_bps,
                        config.max_spread_bps_iex,
                        config.min_quote_size,
                        rejected_spread_iex_relaxed,
                    )
                filtered = filtered[strict_mask | iex_mask | stale_quote_mask]
            else:
                filtered = filtered[strict_mask | stale_quote_mask]
    after_spread = len(filtered)

    if config.earnings_blackout_days is not None:
        if "earnings_blackout" not in filtered.columns:
            LOGGER.warning(
                "Filtre earnings blackout active mais colonne earnings_blackout absente; aucun titre retenu."
            )
            filtered = filtered.iloc[0:0].copy()
        else:
            filtered = filtered[
                pd.to_numeric(filtered["earnings_blackout"], errors="coerce").fillna(0).astype(int) == 0
            ]
    after_earnings_blackout = len(filtered)

    if "liquidity_val" in filtered.columns:
        filtered = filtered[(filtered["liquidity_val"].isna()) | (filtered["liquidity_val"] > config.liquidity_threshold)]
    after_score_liquidity = len(filtered)
    if "sanitizer_status" in filtered.columns:
        filtered = filtered[
            filtered["sanitizer_status"].isna()
            | (filtered["sanitizer_status"].astype(str).str.lower() == "success")
        ]
    after_sanitizer = len(filtered)
    if "anomaly_count" in filtered.columns:
        filtered = filtered[(filtered["anomaly_count"].isna()) | (filtered["anomaly_count"] <= config.max_anomaly_count)]
    after_anomaly = len(filtered)
    if "missing_days_count" in filtered.columns:
        filtered = filtered[(filtered["missing_days_count"].isna()) | (filtered["missing_days_count"] < config.max_missing_days_count)]

    stats = {
        "input": before_count,
        "output": len(filtered),
        "rejected_etf": before_count - after_etf_filter,
        "rejected_history": after_etf_filter - after_history,
        "rejected_price": after_history - after_close,
        "rejected_market_liquidity": after_close - after_market_liquidity,
        "rejected_volatility": after_market_liquidity - after_volatility,
        "rejected_atr": after_volatility - after_atr,
        "rejected_relative_strength": after_atr - after_relative_strength,
        "rejected_ma200": after_relative_strength - after_ma200,
        "rejected_high_52w": after_ma200 - after_high_52w,
        "rejected_weekly": after_high_52w - after_weekly,
        "rejected_market_cap": after_weekly - after_market_cap,
        # Phase 3.3.d — rejets liés à la fraîcheur de market_cap_refreshed_at.
        "rejected_market_cap_stale": rejected_market_cap_stale,
        "rejected_beta": after_market_cap_ttl - after_beta,
        "rejected_spread": after_beta - after_spread,
        # Phase 3.3.c — titres "sauvés" par le relâchement IEX (informatif).
        "rescued_spread_iex": rejected_spread_iex_relaxed,
        "rejected_earnings_blackout": after_spread - after_earnings_blackout,
        "rejected_score_liquidity": after_earnings_blackout - after_score_liquidity,
        "rejected_sanitizer": after_score_liquidity - after_sanitizer,
        "rejected_anomalies": after_sanitizer - after_anomaly,
        "rejected_missing_days": after_anomaly - len(filtered),
    }
    return filtered.reset_index(drop=True), stats


def log_filter_stats(stats: dict[str, int]) -> None:
    LOGGER.info(
        "Filtres appliques | entree=%s sortie=%s rejet_etf=%s rejet_historique=%s rejet_prix=%s rejet_liquidite_marche=%s rejet_volatilite_relative=%s rejet_atr_pct=%s rejet_force_relative=%s rejet_ma200=%s rejet_high_52w=%s rejet_weekly=%s rejet_market_cap=%s rejet_market_cap_stale=%s rejet_beta=%s rejet_spread=%s rescues_spread_iex=%s rejet_earnings_blackout=%s rejet_liquidite_scores=%s rejet_anomalies=%s rejet_missing_days=%s",
        stats.get("input", 0),
        stats.get("output", 0),
        stats.get("rejected_etf", 0),
        stats.get("rejected_history", 0),
        stats.get("rejected_price", 0),
        stats.get("rejected_market_liquidity", 0),
        stats.get("rejected_volatility", 0),
        stats.get("rejected_atr", 0),
        stats.get("rejected_relative_strength", 0),
        stats.get("rejected_ma200", 0),
        stats.get("rejected_high_52w", 0),
        stats.get("rejected_weekly", 0),
        stats.get("rejected_market_cap", 0),
        stats.get("rejected_market_cap_stale", 0),
        stats.get("rejected_beta", 0),
        stats.get("rejected_spread", 0),
        stats.get("rescued_spread_iex", 0),
        stats.get("rejected_earnings_blackout", 0),
        stats.get("rejected_score_liquidity", 0),
        stats.get("rejected_anomalies", 0),
        stats.get("rejected_missing_days", 0),
    )


def enrich_and_filter_equities(
    merged_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> pd.DataFrame:
    """Exclut ETF/crypto/fonds via stock_metadata + enrichit secteur/market_cap."""
    if merged_df.empty:
        return merged_df.copy()
    if metadata_df.empty:
        LOGGER.info(
            "Filtre instruments | entree=%s sortie_actions=%s exclus_total=%s detail=%s",
            len(merged_df),
            len(merged_df),
            0,
            {"metadata_unavailable": 0},
        )
        return merged_df.copy()

    metadata = metadata_df.copy()
    metadata = metadata.drop_duplicates(subset=["symbol"], keep="last")
    for column in METADATA_COLUMNS:
        if column not in metadata.columns:
            metadata[column] = pd.NA
    metadata["company_name"] = metadata["company_name"].fillna("").astype(str)
    metadata["asset_class"] = metadata["asset_class"].fillna("").astype(str).str.lower()
    metadata["status"] = metadata["status"].fillna("").astype(str).str.lower()
    metadata["tradable"] = metadata["tradable"].fillna(False).astype(bool)
    metadata["bars_available"] = metadata["bars_available"].fillna(False).astype(bool)
    metadata["history_status"] = metadata["history_status"].fillna("").astype(str).str.lower().str.strip()

    requested_symbols = merged_df["symbol"].astype(str)
    requested_symbol_set = set(requested_symbols)
    metadata = metadata[metadata["symbol"].astype(str).isin(requested_symbol_set)].copy()

    company_name_normalized = metadata["company_name"].str.lower()
    etf_mask = company_name_normalized.apply(
        lambda value: any(pattern in value for pattern in ETF_NAME_PATTERNS)
    )
    reason_masks = {
        "metadata_missing": pd.Index(sorted(requested_symbol_set.difference(set(metadata["symbol"].astype(str))))),
        "non_us_equity": metadata.loc[metadata["asset_class"] != "us_equity", "symbol"],
        "inactive": metadata.loc[metadata["status"] != "active", "symbol"],
        "non_tradable": metadata.loc[~metadata["tradable"], "symbol"],
        "bars_unavailable": metadata.loc[~metadata["bars_available"], "symbol"],
        "history_no_history": metadata.loc[metadata["history_status"] == HISTORY_STATUS_NO_HISTORY, "symbol"],
        "history_provider_error": metadata.loc[metadata["history_status"] == HISTORY_STATUS_PROVIDER_ERROR, "symbol"],
        "history_suspended_or_stale": metadata.loc[metadata["history_status"] == HISTORY_STATUS_SUSPENDED_OR_STALE, "symbol"],
        "history_excluded_by_policy": metadata.loc[metadata["history_status"] == HISTORY_STATUS_EXCLUDED_BY_POLICY, "symbol"],
        "etf_name": metadata.loc[etf_mask, "symbol"],
    }
    exclusion_details = {
        reason: sorted({str(symbol) for symbol in symbols if str(symbol) in requested_symbol_set})
        for reason, symbols in reason_masks.items()
    }
    exclusion_counts = {
        reason: len(symbols)
        for reason, symbols in exclusion_details.items()
        if len(symbols) > 0
    }

    disqualified_symbols = {
        symbol
        for symbols in exclusion_details.values()
        for symbol in symbols
    }
    eligible_symbols = sorted(requested_symbol_set.difference(disqualified_symbols))

    eligible_metadata_columns = ["symbol", "sector", "history_status"]
    if "market_cap" in metadata.columns:
        eligible_metadata_columns.append("market_cap")
    eligible_metadata = metadata.loc[
        metadata["symbol"].astype(str).isin(eligible_symbols),
        eligible_metadata_columns,
    ].copy()
    enriched = merged_df.merge(eligible_metadata, on="symbol", how="inner", suffixes=("", "_meta"))
    if "sector_meta" in enriched.columns:
        enriched["sector"] = enriched["sector_meta"].where(
            enriched["sector_meta"].notna() & (enriched["sector_meta"].astype(str).str.strip() != ""),
            enriched.get("sector"),
        )
        enriched = enriched.drop(columns=["sector_meta"])
    if "market_cap_meta" in enriched.columns:
        enriched["market_cap"] = pd.to_numeric(enriched["market_cap_meta"], errors="coerce").combine_first(
            pd.to_numeric(enriched.get("market_cap"), errors="coerce")
        )
        enriched = enriched.drop(columns=["market_cap_meta"])

    LOGGER.info(
        "Filtre instruments | entree=%s sortie_actions=%s exclus_total=%s detail=%s",
        len(merged_df),
        len(enriched),
        len(merged_df) - len(enriched),
        exclusion_counts,
    )
    if exclusion_counts:
        LOGGER.debug(
            "Filtre instruments details symboles | %s",
            {reason: symbols[:5] for reason, symbols in exclusion_details.items() if symbols},
        )
    return enriched.reset_index(drop=True)


def merge_optional_symbol_overlays(
    merged_df: pd.DataFrame,
    quotes_df: pd.DataFrame,
    earnings_df: pd.DataFrame,
) -> pd.DataFrame:
    """Superpose snapshots quotes (spread/bid/ask) et calendrier earnings."""
    if merged_df.empty:
        return merged_df.copy()

    enriched = merged_df.copy()

    if not quotes_df.empty:
        if "symbol" not in quotes_df.columns:
            LOGGER.warning("Overlay quotes ignore : colonne symbol absente dans quotes_df.")
        else:
            # Phase 3.3.c — propager bid_size/ask_size pour le filtre spread IEX.
            normalized_quotes = quotes_df.copy()
            quote_columns = ["symbol", "spread_bps", "quote_date", "quote_timestamp", "bid_size", "ask_size"]
            for column in quote_columns:
                if column not in normalized_quotes.columns:
                    normalized_quotes[column] = pd.NA
            latest_quotes = normalized_quotes.loc[:, quote_columns].drop_duplicates(subset=["symbol"], keep="last")
            enriched = enriched.merge(latest_quotes, on="symbol", how="left", suffixes=("", "_quote"))
            for metadata_col in ("quote_date", "quote_timestamp"):
                quote_col = f"{metadata_col}_quote"
                if quote_col in enriched.columns:
                    enriched[metadata_col] = enriched[quote_col].combine_first(enriched.get(metadata_col))
                    enriched = enriched.drop(columns=[quote_col])
            if "spread_bps_quote" in enriched.columns:
                enriched["spread_bps"] = pd.to_numeric(enriched["spread_bps_quote"], errors="coerce").combine_first(
                    pd.to_numeric(enriched.get("spread_bps"), errors="coerce")
                )
                enriched = enriched.drop(columns=["spread_bps_quote"])
            for size_col in ("bid_size", "ask_size"):
                quote_col = f"{size_col}_quote"
                if quote_col in enriched.columns:
                    enriched[size_col] = pd.to_numeric(enriched[quote_col], errors="coerce").combine_first(
                        pd.to_numeric(enriched.get(size_col), errors="coerce")
                        if size_col in enriched.columns
                        else pd.Series(index=enriched.index, dtype=float)
                    )
                    enriched = enriched.drop(columns=[quote_col])

    if not earnings_df.empty:
        latest_earnings = earnings_df[
            ["symbol", "earnings_date", "days_to_earnings", "earnings_blackout"]
        ].drop_duplicates(subset=["symbol"], keep="last")
        enriched = enriched.merge(latest_earnings, on="symbol", how="left", suffixes=("", "_earnings"))
        if "earnings_date_earnings" in enriched.columns:
            enriched["earnings_date"] = enriched["earnings_date_earnings"].combine_first(enriched.get("earnings_date"))
            enriched = enriched.drop(columns=["earnings_date_earnings"])
        if "days_to_earnings_earnings" in enriched.columns:
            existing_days_to_earnings = (
                pd.to_numeric(enriched["days_to_earnings"], errors="coerce")
                if "days_to_earnings" in enriched.columns
                else pd.Series(index=enriched.index, dtype=float)
            )
            overlay_days_to_earnings = pd.to_numeric(
                enriched["days_to_earnings_earnings"], errors="coerce"
            )
            enriched["days_to_earnings"] = overlay_days_to_earnings.where(
                overlay_days_to_earnings.notna(),
                existing_days_to_earnings,
            )
            enriched = enriched.drop(columns=["days_to_earnings_earnings"])
        if "earnings_blackout_earnings" in enriched.columns:
            existing_earnings_blackout = (
                pd.to_numeric(enriched["earnings_blackout"], errors="coerce")
                if "earnings_blackout" in enriched.columns
                else pd.Series(index=enriched.index, dtype=float)
            )
            overlay_earnings_blackout = pd.to_numeric(
                enriched["earnings_blackout_earnings"], errors="coerce"
            )
            enriched["earnings_blackout"] = overlay_earnings_blackout.where(
                overlay_earnings_blackout.notna(),
                existing_earnings_blackout,
            )
            enriched = enriched.drop(columns=["earnings_blackout_earnings"])

    return enriched


# `np` réservé en cas d'évolution future ; importé pour cohérence des helpers.
_ = np


