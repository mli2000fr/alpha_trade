"""
AlphaScanner — orchestration multi-facteurs (façade).

Phase 3.3.a : la logique pure a été extraite dans des modules dédiés :

- ``selector.factors`` : ``compute_factor_frame``, ``winsorize_and_normalize``,
  ``FACTOR_COLUMNS``.
- ``selector.filters`` : ``apply_filters_with_stats``, ``log_filter_stats``,
  ``enrich_and_filter_equities``, ``merge_optional_symbol_overlays``,
  constantes ``METADATA_COLUMNS``/``ETF_NAME_PATTERNS``/``ELIGIBLE_HISTORY_STATUSES``.
- ``selector.ranking`` : ``merge_scores``, ``apply_factor_neutralization``,
  ``apply_sector_neutrality``, ``rank_and_select``, constantes
  ``SCORE_COLUMNS``/``OUTPUT_COLUMNS``/``PERSISTED_SELECTOR_SCORE_COLUMNS``.

Ce module conserve :

- ``AlphaScannerConfig`` (toutes les options/seuils + validations).
- La classe ``AlphaScanner`` (I/O DB + orchestration multithread).
- Tous les noms (publics ET privés tels que ``apply_filters``,
  ``apply_sector_neutrality``, ``merge_scores``, ``compute_factors``,
  ``_apply_filters_with_stats``, ``_winsorize_and_normalize``, etc.) sont
  préservés à des fins de rétrocompatibilité (tests, scripts externes,
  ``backtesting/*``).
- La CLI ``main()`` et l'helper ``_build_cli_run_summary``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import threading
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterator, Optional, Sequence, cast
from uuid import uuid4

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from common.utils import configure_root_logging
from core.run_summary import attach_schema_version, merge_iex_bias_counters
from database.connection import get_sqlalchemy_engine

# Phase 3.2.c — la source de vérité est ``core.filter_profiles`` ;
# l'import historique ``selector.strict_filter_profiles`` est conservé
# comme alias rétrocompatible pour les appelants legacy.
from core.filter_profiles import STRICT_SWING_CASH_FILTERS, StrictFilterProfile

# Phase 3.3.a — modules extraits ; ré-exportés pour rétrocompatibilité.
from selector.factors import (
    FACTOR_COLUMNS,
    compute_factor_frame,
    winsorize_and_normalize,
)
from selector.filters import (
    ELIGIBLE_HISTORY_STATUSES,
    ETF_NAME_PATTERNS,
    METADATA_COLUMNS,
    apply_filters_with_stats,
    enrich_and_filter_equities,
    log_filter_stats,
    merge_optional_symbol_overlays,
)
from selector.ranking import (
    OUTPUT_COLUMNS,
    PERSISTED_SELECTOR_SCORE_COLUMNS,
    SCORE_COLUMNS,
    apply_factor_neutralization,
    apply_sector_neutrality,
    merge_scores,
    rank_and_select,
)

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"

PRICE_COLUMNS = ["symbol", "date", "close", "volume", "high", "low"]


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _emit_run_summary(summary: dict[str, object]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def _build_cli_run_summary(
    *,
    config: "AlphaScannerConfig",
    result: pd.DataFrame,
    started_at: datetime,
    finished_at: datetime,
    rejected_by_filter: dict[str, int] | None = None,
) -> dict[str, object]:
    selected_symbols = result["symbol"].astype(str).tolist()[:5] if "symbol" in result.columns and not result.empty else []
    sector_breakdown = (
        result["sector"].fillna("Unknown").astype(str).str.strip().replace("", "Unknown").value_counts().to_dict()
        if "sector" in result.columns and not result.empty
        else {}
    )
    max_final_score = None
    avg_final_score = None
    if "final_score" in result.columns and not result.empty:
        numeric_final_score = pd.to_numeric(result["final_score"], errors="coerce").dropna()
        if not numeric_final_score.empty:
            max_final_score = round(float(numeric_final_score.max()), 4)
            avg_final_score = round(float(numeric_final_score.mean()), 4)

    return {
        "run_id": _build_run_id("alpha-scanner"),
        "preset_profile": STRICT_SWING_CASH_FILTERS.name,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "chunk_size": config.chunk_size,
        "requested_selection_size": config.selection_size,
        "selected_candidates": int(len(result)),
        "selection_fill_ratio": round((len(result) / config.selection_size), 4) if config.selection_size > 0 else 0.0,
        "workers": config.max_workers or min(8, os.cpu_count() or 1),
        "sector_cap_ratio": round(float(config.sector_cap_ratio), 4),
        "selected_sectors": int(result["sector"].nunique()) if "sector" in result.columns and not result.empty else 0,
        "sector_breakdown": sector_breakdown,
        "top_symbols": selected_symbols,
        "max_final_score": max_final_score,
        "avg_final_score": avg_final_score,
        "max_anomaly_count": config.max_anomaly_count,
        "max_spread_bps": config.max_spread_bps,
        "max_spread_bps_iex": config.max_spread_bps_iex,
        "min_quote_size": config.min_quote_size,
        "market_cap_max_age_days": config.market_cap_max_age_days,
        "earnings_blackout_days": config.earnings_blackout_days,
        # Phase 3.3.b — agrégat des rejets par filtre (cross-chunks).
        "rejected_by_filter": dict(sorted((rejected_by_filter or {}).items())),
    }


def _summarize_zero_candidate_filters(rejected_by_filter: dict[str, int] | None) -> str:
    stats = {str(key): int(value) for key, value in (rejected_by_filter or {}).items()}
    if not stats:
        return "rejets_par_filtre indisponibles"

    label_map = {
        "rejected_volatility": "volatilite_relative",
        "rejected_relative_strength": "force_relative",
        "rejected_beta": "beta",
        "rejected_atr": "atr_pct",
        "rejected_weekly": "weekly",
        "rejected_spread": "spread",
        "rejected_ma200": "ma200",
        "rejected_market_cap": "market_cap",
        "rejected_high_52w": "high_52w",
        "rejected_earnings_blackout": "earnings_blackout",
    }
    ranked_rejections = sorted(
        (
            (label_map.get(key, key), value)
            for key, value in stats.items()
            if key.startswith("rejected_") and value > 0
        ),
        key=lambda item: (-item[1], item[0]),
    )
    top_rejections = ", ".join(f"{label}={value}" for label, value in ranked_rejections[:4])
    if not top_rejections:
        top_rejections = "aucun rejet significatif capture"

    survivors = int(stats.get("input", 0))
    stage_order = (
        "rejected_etf",
        "rejected_history",
        "rejected_price",
        "rejected_market_liquidity",
        "rejected_volatility",
        "rejected_atr",
        "rejected_relative_strength",
        "rejected_ma200",
        "rejected_high_52w",
        "rejected_weekly",
        "rejected_market_cap",
        "rejected_market_cap_stale",
        "rejected_beta",
        "rejected_spread",
        "rejected_earnings_blackout",
        "rejected_score_liquidity",
        "rejected_sanitizer",
        "rejected_anomalies",
        "rejected_missing_days",
    )
    remaining_after_stage: dict[str, int] = {}
    for key in stage_order:
        survivors = max(survivors - int(stats.get(key, 0)), 0)
        remaining_after_stage[key] = survivors

    extra_hints: list[str] = []
    before_beta = remaining_after_stage.get("rejected_market_cap_stale", 0)
    before_spread = remaining_after_stage.get("rejected_beta", 0)
    after_spread = remaining_after_stage.get("rejected_spread", 0)
    if before_spread > 0 and after_spread == 0 and int(stats.get("rejected_spread", 0)) == before_spread:
        extra_hints.append(f"tous_les_survivants_avant_spread={before_spread} ont ete rejetes_au_spread")
    if before_beta > 0 and int(stats.get("rejected_beta", 0)) >= max(10, before_beta // 2):
        extra_hints.append(
            f"beta_tres_selectif={stats.get('rejected_beta', 0)}/{before_beta} rejetes_apres_market_cap"
        )

    detail = f"top_rejets=[{top_rejections}]"
    if extra_hints:
        detail += " | " + " | ".join(extra_hints)
    return detail


@dataclass(frozen=True, slots=True)
class AlphaScannerConfig:
    price_table: str = "stock_bars_daily"
    score_table: str = "stock_scores"
    chunk_size: int = 500
    selection_size: int = 100
    min_history_days: int = 252
    liquidity_threshold: float = 20_000_000.0
    min_close: float = 5.0
    max_volatility_ratio: float | None = None
    min_relative_strength_index: float | None = None
    min_high_52w_proximity: float | None = None
    min_weekly_trend_score: float | None = None
    min_atr_pct_20: float | None = None
    max_atr_pct_20: float | None = None
    min_market_cap: float | None = None
    min_beta_126: float | None = None
    max_spread_bps: float | None = None
    # Phase 3.3.c — extensions IEX : relâchement contrôlé du filtre spread.
    max_spread_bps_iex: float | None = None
    min_quote_size: float | None = None
    # Phase 3.3.d — TTL appliqué au filtre ``min_market_cap``.
    market_cap_max_age_days: int | None = None
    earnings_blackout_days: int | None = None
    require_above_ma200: bool = False
    max_anomaly_count: int = 20
    max_missing_days_count: int = 10
    sector_cap_ratio: float = 0.30
    volatility_short_window: int = 10
    volatility_long_window: int = 60
    vcp_ratio_threshold: float = 0.60
    ma_short_window: int = 50
    ma_mid_window: int = 150
    ma_long_window: int = 200
    trailing_range_window: int = 252
    liquidity_lookback_days: int = 20
    update_batch_size: int = 500
    max_workers: int | None = None

    # Composition multi-facteurs : poids configurables.
    weight_trend_vcp: float = 0.50
    weight_total_score: float = 0.30
    weight_rsi: float = 0.20

    # Winsorisation (anti-outliers).
    winsor_lower_pct: float = 0.01
    winsor_upper_pct: float = 0.99

    # Neutralisation cross-sectorielle (P0).
    neutralize_by_sector: bool = True

    @classmethod
    def from_filter_profile(
        cls,
        profile: StrictFilterProfile,
        **overrides: object,
    ) -> "AlphaScannerConfig":
        merged_kwargs: dict[str, object] = dict(profile.to_scanner_config_kwargs())
        # Phase 3.3.c/d — merger les extensions IEX/TTL.
        for key, value in profile.iex_extensions().items():
            if value is not None:
                merged_kwargs[key] = value
        for key, value in overrides.items():
            merged_kwargs[key] = value
        return cls(**merged_kwargs)

    @classmethod
    def strict_swing_cash(cls, **overrides: object) -> "AlphaScannerConfig":
        return cls.from_filter_profile(STRICT_SWING_CASH_FILTERS, **overrides)

    def __post_init__(self) -> None:
        if self.chunk_size < 1:
            raise ValueError("chunk_size doit être supérieur ou égal à 1.")
        if self.selection_size < 1:
            raise ValueError("selection_size doit être supérieur ou égal à 1.")
        if self.min_history_days < self.trailing_range_window:
            raise ValueError("min_history_days doit être supérieur ou égal à trailing_range_window.")
        if self.liquidity_threshold <= 0:
            raise ValueError("liquidity_threshold doit être strictement positif.")
        if self.min_close <= 0:
            raise ValueError("min_close doit être strictement positif.")
        if self.max_volatility_ratio is not None and self.max_volatility_ratio <= 0:
            raise ValueError("max_volatility_ratio doit être strictement positif lorsqu'il est renseigné.")
        if self.min_relative_strength_index is not None and self.min_relative_strength_index <= 0:
            raise ValueError("min_relative_strength_index doit être strictement positif lorsqu'il est renseigné.")
        if self.min_high_52w_proximity is not None and not 0 < self.min_high_52w_proximity <= 1:
            raise ValueError("min_high_52w_proximity doit être compris dans ]0, 1] lorsqu'il est renseigné.")
        if self.min_weekly_trend_score is not None and not 0 <= self.min_weekly_trend_score <= 1:
            raise ValueError("min_weekly_trend_score doit être compris dans [0, 1] lorsqu'il est renseigné.")
        if self.min_atr_pct_20 is not None and self.min_atr_pct_20 <= 0:
            raise ValueError("min_atr_pct_20 doit être strictement positif lorsqu'il est renseigné.")
        if self.max_atr_pct_20 is not None and self.max_atr_pct_20 <= 0:
            raise ValueError("max_atr_pct_20 doit être strictement positif lorsqu'il est renseigné.")
        if self.min_market_cap is not None and self.min_market_cap <= 0:
            raise ValueError("min_market_cap doit être strictement positif lorsqu'il est renseigné.")
        if self.min_beta_126 is not None and self.min_beta_126 <= 0:
            raise ValueError("min_beta_126 doit être strictement positif lorsqu'il est renseigné.")
        if self.max_spread_bps is not None and self.max_spread_bps <= 0:
            raise ValueError("max_spread_bps doit être strictement positif lorsqu'il est renseigné.")
        if self.max_spread_bps_iex is not None and self.max_spread_bps_iex <= 0:
            raise ValueError("max_spread_bps_iex doit être strictement positif lorsqu'il est renseigné.")
        if (
            self.max_spread_bps is not None
            and self.max_spread_bps_iex is not None
            and self.max_spread_bps_iex < self.max_spread_bps
        ):
            raise ValueError(
                "max_spread_bps_iex doit être >= max_spread_bps (relâchement IEX, pas durcissement)."
            )
        if self.min_quote_size is not None and self.min_quote_size < 0:
            raise ValueError("min_quote_size doit être positif ou nul lorsqu'il est renseigné.")
        if self.market_cap_max_age_days is not None and self.market_cap_max_age_days < 0:
            raise ValueError("market_cap_max_age_days doit être positif ou nul lorsqu'il est renseigné.")
        if self.earnings_blackout_days is not None and self.earnings_blackout_days < 0:
            raise ValueError("earnings_blackout_days doit être positif ou nul lorsqu'il est renseigné.")
        if (
            self.min_atr_pct_20 is not None
            and self.max_atr_pct_20 is not None
            and self.min_atr_pct_20 > self.max_atr_pct_20
        ):
            raise ValueError("min_atr_pct_20 ne peut pas être supérieur à max_atr_pct_20.")
        if not 0 < self.sector_cap_ratio <= 1:
            raise ValueError("sector_cap_ratio doit être compris entre 0 exclus et 1 inclus.")
        if self.volatility_short_window < 2 or self.volatility_long_window <= self.volatility_short_window:
            raise ValueError("Les fenêtres de volatilité sont invalides.")
        if self.vcp_ratio_threshold <= 0:
            raise ValueError("vcp_ratio_threshold doit être strictement positif.")
        if self.update_batch_size < 1:
            raise ValueError("update_batch_size doit être supérieur ou égal à 1.")
        if self.max_workers is not None and self.max_workers < 1:
            raise ValueError("max_workers doit être supérieur ou égal à 1.")
        total_weight = self.weight_trend_vcp + self.weight_total_score + self.weight_rsi
        if not np.isclose(total_weight, 1.0, atol=1e-6):
            raise ValueError(
                f"La somme des poids facteurs doit être égale à 1.0 "
                f"(weight_trend_vcp + weight_total_score + weight_rsi = {total_weight:.6f})."
            )
        if not 0.0 <= self.winsor_lower_pct < self.winsor_upper_pct <= 1.0:
            raise ValueError("winsor_lower_pct et winsor_upper_pct doivent respecter 0 ≤ lower < upper ≤ 1.")


class AlphaScanner:
    """Scanner multi-facteurs basé sur prix journaliers + table auxiliaire de scores.

    Phase 3.3.a — la logique pure (compute_factors / merge_scores / filtres /
    ranking) vit désormais dans ``selector.factors``, ``selector.filters`` et
    ``selector.ranking``. Cette classe garde la responsabilité I/O (DB,
    threading) et délègue tout le calcul.
    """

    def __init__(
        self,
        engine: Engine | None = None,
        config: AlphaScannerConfig | None = None,
    ) -> None:
        self.engine = engine or get_sqlalchemy_engine()
        self.config = config or AlphaScannerConfig.strict_swing_cash()
        self._stock_metadata_columns_cache: set[str] | None = None
        self._stock_quote_snapshots_columns_cache: set[str] | None = None
        # Phase 3.3.b — agrégation des stats `apply_filters_with_stats`.
        self._aggregated_filter_stats: Counter[str] = Counter()
        self._filter_stats_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Introspection schéma
    # ------------------------------------------------------------------
    def get_aggregated_filter_stats(self) -> dict[str, int]:
        """Phase 3.3.b — snapshot agrégé (cross-chunks) des stats de filtrage."""
        with self._filter_stats_lock:
            return dict(self._aggregated_filter_stats)

    def _get_stock_metadata_columns(self) -> set[str]:
        if self._stock_metadata_columns_cache is not None:
            return self._stock_metadata_columns_cache
        try:
            self._stock_metadata_columns_cache = {
                str(column.get("name"))
                for column in inspect(self.engine).get_columns("stock_metadata")
            }
        except Exception:
            LOGGER.warning("Inspection stock_metadata indisponible; fallback sans history_status explicite.")
            self._stock_metadata_columns_cache = set()
        return self._stock_metadata_columns_cache

    def _get_stock_quote_snapshots_columns(self) -> set[str]:
        # Phase 3.3.c — introspection défensive.
        if self._stock_quote_snapshots_columns_cache is not None:
            return self._stock_quote_snapshots_columns_cache
        try:
            self._stock_quote_snapshots_columns_cache = {
                str(column.get("name"))
                for column in inspect(self.engine).get_columns("stock_quote_snapshots")
            }
        except Exception:
            self._stock_quote_snapshots_columns_cache = set()
        return self._stock_quote_snapshots_columns_cache

    # ------------------------------------------------------------------
    # Lecture DB (I/O)
    # ------------------------------------------------------------------
    def fetch_market_data(self, symbols: Sequence[str]) -> pd.DataFrame:
        """Charge un chunk d'historique marché depuis la table daily."""
        if not symbols:
            return pd.DataFrame(columns=PRICE_COLUMNS)

        LOGGER.debug("Chargement market data | symboles=%s", len(symbols))

        stmt = text(
            f"""
            SELECT symbol, date, close, volume, high, low
            FROM {self.config.price_table}
            WHERE symbol IN :symbols
            ORDER BY symbol, date
            """
        ).bindparams(bindparam("symbols", expanding=True))

        try:
            market_data = pd.read_sql_query(
                stmt,
                self.engine,
                params=cast(dict[str, Any], {"symbols": list(symbols)}),
            )
        except SQLAlchemyError as exc:
            LOGGER.exception("Echec lecture %s pour %s symboles.", self.config.price_table, len(symbols))
            raise RuntimeError("Impossible de charger les données marché.") from exc

        if market_data.empty:
            return pd.DataFrame(columns=PRICE_COLUMNS)

        market_data["date"] = pd.to_datetime(market_data["date"], utc=False)
        return market_data

    def fetch_scores(self, symbols: Sequence[str]) -> pd.DataFrame:
        """Charge les scores auxiliaires; absence de table/ligne tolérée."""
        if not symbols:
            return pd.DataFrame(columns=SCORE_COLUMNS)

        LOGGER.debug("Chargement scores auxiliaires | symboles=%s", len(symbols))

        stmt = text(
            f"""
            SELECT symbol,
                   liquidity_val,
                   relative_strength_index,
                   total_score,
                   sector,
                   market_cap,
                   beta_126,
                   spread_bps,
                   earnings_date,
                   days_to_earnings,
                   earnings_blackout,
                   sanitizer_status,
                   anomaly_count,
                   missing_days_count
            FROM {self.config.score_table}
            WHERE symbol IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))

        try:
            scores = pd.read_sql_query(
                stmt,
                self.engine,
                params=cast(dict[str, Any], {"symbols": list(symbols)}),
            )
        except SQLAlchemyError:
            LOGGER.warning(
                "Lecture auxiliaire %s indisponible; poursuite avec facteurs recalcules seulement.",
                self.config.score_table,
            )
            return pd.DataFrame(columns=SCORE_COLUMNS)

        return scores if not scores.empty else pd.DataFrame(columns=SCORE_COLUMNS)

    def fetch_instrument_metadata(self, symbols: Sequence[str]) -> pd.DataFrame:
        """Charge les métadonnées instrument pour enrichir les secteurs et exclure les ETFs/fonds."""
        if not symbols:
            return pd.DataFrame(columns=METADATA_COLUMNS)

        available_columns = self._get_stock_metadata_columns()
        select_columns = [
            "symbol",
            "company_name",
            "asset_class",
            "status",
            "tradable",
            "bars_available",
        ]
        if "history_status" in available_columns:
            select_columns.append("history_status")
        if "sector" in available_columns:
            select_columns.append("sector")
        if "market_cap" in available_columns:
            select_columns.append("market_cap")
        # Phase 3.3.d — TTL filtre market_cap basé sur la fraîcheur SQL.
        if "market_cap_refreshed_at" in available_columns:
            select_columns.append("market_cap_refreshed_at")

        stmt = text(
            f"""
            SELECT {', '.join(select_columns)}
            FROM stock_metadata
            WHERE symbol IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))

        try:
            metadata_df = pd.read_sql_query(
                stmt,
                self.engine,
                params=cast(dict[str, Any], {"symbols": list(symbols)}),
            )
        except SQLAlchemyError:
            LOGGER.warning("Lecture stock_metadata indisponible; impossibilite de filtrer explicitement les ETFs.")
            return pd.DataFrame(columns=METADATA_COLUMNS)

        if metadata_df.empty:
            return pd.DataFrame(columns=METADATA_COLUMNS)

        for column in METADATA_COLUMNS:
            if column not in metadata_df.columns:
                metadata_df[column] = pd.NA
        return metadata_df.loc[:, METADATA_COLUMNS]

    def _load_benchmark_returns(self, start_date: date, end_date: date) -> pd.DataFrame:
        stmt = text(
            f"""
            SELECT date, close
            FROM {self.config.price_table}
            WHERE symbol = 'SPY'
              AND date BETWEEN :start_date AND :end_date
            ORDER BY date
            """
        )
        try:
            benchmark_df = pd.read_sql_query(
                stmt,
                self.engine,
                params={"start_date": start_date, "end_date": end_date},
            )
        except SQLAlchemyError:
            LOGGER.warning("Lecture benchmark SPY indisponible pour le calcul du beta.")
            return pd.DataFrame(columns=["date", "spy_return"])

        if benchmark_df.empty:
            return pd.DataFrame(columns=["date", "spy_return"])

        benchmark_df["date"] = pd.to_datetime(benchmark_df["date"], utc=False)
        benchmark_df["close"] = pd.to_numeric(benchmark_df["close"], errors="coerce")
        benchmark_df["spy_return"] = benchmark_df["close"].pct_change()
        return benchmark_df[["date", "spy_return"]].dropna().reset_index(drop=True)

    def fetch_quote_snapshots(self, symbols: Sequence[str], *, reference_date: date | None = None) -> pd.DataFrame:
        # Phase 3.3.c — bid_size/ask_size requis pour le relâchement IEX.
        available_columns = self._get_stock_quote_snapshots_columns()
        select_extra: list[str] = []
        if "quote_timestamp" in available_columns:
            select_extra.append("q.quote_timestamp")
        if "bid_size" in available_columns:
            select_extra.append("q.bid_size")
        if "ask_size" in available_columns:
            select_extra.append("q.ask_size")
        empty_columns = ["symbol", "quote_date", "quote_timestamp", "spread_bps", "bid_size", "ask_size"]
        if not symbols:
            return pd.DataFrame(columns=empty_columns)

        effective_reference_date = reference_date or date.today()

        select_clause = "q.symbol, q.quote_date, q.spread_bps"
        if select_extra:
            select_clause = select_clause + ", " + ", ".join(select_extra)

        stmt = text(
            f"""
            SELECT {select_clause}
            FROM stock_quote_snapshots q
            INNER JOIN (
                SELECT symbol, MAX(quote_date) AS max_quote_date
                FROM stock_quote_snapshots
                WHERE symbol IN :symbols
                  AND quote_date <= :reference_date
                GROUP BY symbol
            ) latest ON latest.symbol = q.symbol AND latest.max_quote_date = q.quote_date
            WHERE q.symbol IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))

        try:
            quotes_df = pd.read_sql_query(
                stmt,
                self.engine,
                params={"symbols": list(symbols), "reference_date": effective_reference_date},
            )
        except SQLAlchemyError:
            LOGGER.warning("Lecture stock_quote_snapshots indisponible; filtre de spread desactive.")
            return pd.DataFrame(columns=empty_columns)
        for column in ("quote_timestamp", "bid_size", "ask_size"):
            if column not in quotes_df.columns:
                quotes_df[column] = pd.NA
        return quotes_df if not quotes_df.empty else pd.DataFrame(columns=empty_columns)

    def fetch_next_earnings(self, symbols: Sequence[str], *, reference_date: date | None = None) -> pd.DataFrame:
        if not symbols:
            return pd.DataFrame(columns=["symbol", "earnings_date", "days_to_earnings", "earnings_blackout"])

        effective_reference_date = reference_date or date.today()

        stmt = text(
            """
            SELECT e.symbol,
                   e.earnings_date
            FROM stock_earnings_calendar e
            INNER JOIN (
                SELECT symbol, MIN(earnings_date) AS next_earnings_date
                FROM stock_earnings_calendar
                WHERE symbol IN :symbols
                  AND earnings_date >= :reference_date
                GROUP BY symbol
            ) next_e ON next_e.symbol = e.symbol AND next_e.next_earnings_date = e.earnings_date
            WHERE e.symbol IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))

        try:
            earnings_df = pd.read_sql_query(
                stmt,
                self.engine,
                params={"symbols": list(symbols), "reference_date": effective_reference_date},
            )
        except SQLAlchemyError:
            LOGGER.warning("Lecture stock_earnings_calendar indisponible; filtre earnings blackout desactive.")
            return pd.DataFrame(columns=["symbol", "earnings_date", "days_to_earnings", "earnings_blackout"])

        if earnings_df.empty:
            return pd.DataFrame(columns=["symbol", "earnings_date", "days_to_earnings", "earnings_blackout"])

        earnings_timestamps = pd.to_datetime(earnings_df["earnings_date"], utc=False)
        earnings_df["earnings_date"] = earnings_timestamps.dt.date
        days_to_earnings = (earnings_timestamps - pd.Timestamp(effective_reference_date)).dt.days
        earnings_df["days_to_earnings"] = pd.Series(days_to_earnings, index=earnings_df.index)
        blackout_days = self.config.earnings_blackout_days if self.config.earnings_blackout_days is not None else 0
        earnings_df["earnings_blackout"] = (
            pd.Series(pd.to_numeric(earnings_df["days_to_earnings"], errors="coerce"), index=earnings_df.index)
            .fillna(9999)
            .astype(int)
            <= blackout_days
        ).astype(int)
        return earnings_df

    # ------------------------------------------------------------------
    # Calcul (délégation pure aux modules factors / filters / ranking)
    # ------------------------------------------------------------------
    def compute_factors(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """Délègue à ``selector.factors.compute_factor_frame`` après avoir
        chargé les retours du benchmark SPY (I/O DB)."""
        if market_data.empty:
            return pd.DataFrame(columns=FACTOR_COLUMNS)
        dates = pd.to_datetime(market_data["date"], utc=False)
        benchmark_returns = self._load_benchmark_returns(
            start_date=dates.min().date(),
            end_date=dates.max().date(),
        )
        return compute_factor_frame(market_data, benchmark_returns, self.config)

    def merge_scores(self, computed_df: pd.DataFrame, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Délègue à ``selector.ranking.merge_scores``."""
        return merge_scores(computed_df, scores_df, self.config)

    def _apply_factor_neutralization(self, df: pd.DataFrame) -> pd.DataFrame:
        """Délègue à ``selector.ranking.apply_factor_neutralization``."""
        return apply_factor_neutralization(df, self.config)

    def _apply_filters_with_stats(self, merged_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
        """Délègue à ``selector.filters.apply_filters_with_stats``."""
        return apply_filters_with_stats(merged_df, self.config)

    def apply_filters(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        filtered, stats = self._apply_filters_with_stats(merged_df)
        self._log_filter_stats(stats)
        return filtered

    def _log_filter_stats(self, stats: dict[str, int]) -> None:
        log_filter_stats(stats)

    def apply_sector_neutrality(self, ranked_df: pd.DataFrame) -> pd.DataFrame:
        """Délègue à ``selector.ranking.apply_sector_neutrality``."""
        return apply_sector_neutrality(ranked_df, self.config)

    def rank_and_select(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """Délègue à ``selector.ranking.rank_and_select``."""
        return rank_and_select(merged_df, self.config)

    def _enrich_and_filter_equities(self, merged_df: pd.DataFrame, metadata_df: pd.DataFrame) -> pd.DataFrame:
        """Délègue à ``selector.filters.enrich_and_filter_equities``."""
        return enrich_and_filter_equities(merged_df, metadata_df)

    def _merge_optional_symbol_overlays(
        self,
        merged_df: pd.DataFrame,
        quotes_df: pd.DataFrame,
        earnings_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Délègue à ``selector.filters.merge_optional_symbol_overlays``."""
        return merge_optional_symbol_overlays(merged_df, quotes_df, earnings_df)

    # ------------------------------------------------------------------
    # Persistance DB
    # ------------------------------------------------------------------
    def update_database(self, selected_df: pd.DataFrame, scored_df: Optional[pd.DataFrame] = None) -> int:
        """Met à jour stock_scores avec les scores selector et les candidats retenus."""
        selected_symbols = selected_df["symbol"].astype(str).dropna().tolist() if not selected_df.empty else []
        scores_snapshot = self._prepare_scores_snapshot(scored_df)
        reset_stmt = text(f"UPDATE {self.config.score_table} SET is_candidate = 0")
        score_stmt = text(
            f"""
            UPDATE {self.config.score_table}
            SET trend_score = :trend_score,
                vcp_score = :vcp_score,
                final_score = :final_score,
                market_cap = :market_cap,
                beta_126 = :beta_126,
                spread_bps = :spread_bps,
                earnings_date = :earnings_date,
                days_to_earnings = :days_to_earnings,
                earnings_blackout = :earnings_blackout,
                last_updated_scan = :updated_at
            WHERE symbol = :symbol
            """
        )
        mark_stmt = text(
            f"""
            UPDATE {self.config.score_table}
            SET is_candidate = 1
            WHERE symbol IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))
        updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        LOGGER.info(
            "Mise a jour DB | table=%s snapshot_scores=%s candidats=%s batch_size=%s",
            self.config.score_table,
            len(scores_snapshot),
            len(selected_symbols),
            self.config.update_batch_size,
        )

        try:
            with self.engine.begin() as conn:
                for start in range(0, len(scores_snapshot), self.config.update_batch_size):
                    score_batch = [
                        {**row, "updated_at": updated_at}
                        for row in scores_snapshot[start:start + self.config.update_batch_size]
                    ]
                    if not score_batch:
                        continue
                    conn.execute(score_stmt, score_batch)
                    LOGGER.info(
                        "Mise a jour DB | scores selector batch=%s-%s taille=%s",
                        start + 1,
                        start + len(score_batch),
                        len(score_batch),
                    )
                conn.execute(reset_stmt)
                LOGGER.info("Mise a jour DB | reset is_candidate=0 effectue")
                for start in range(0, len(selected_symbols), self.config.update_batch_size):
                    batch = selected_symbols[start:start + self.config.update_batch_size]
                    if not batch:
                        continue
                    conn.execute(mark_stmt, {"updated_at": updated_at, "symbols": batch})
                    LOGGER.info(
                        "Mise a jour DB | batch=%s-%s taille=%s",
                        start + 1,
                        start + len(batch),
                        len(batch),
                    )
        except SQLAlchemyError as exc:
            LOGGER.exception("Echec de mise a jour transactionnelle de %s.", self.config.score_table)
            raise RuntimeError("Impossible de mettre à jour les candidats en base.") from exc

        LOGGER.info("Mise a jour DB terminee | candidats_mis_a_jour=%s", len(selected_symbols))
        return len(selected_symbols)

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def run(self) -> pd.DataFrame:
        """Exécute le scan complet et retourne le Top N final."""
        started_at = datetime.now(timezone.utc)
        LOGGER.info(
            "Demarrage AlphaScanner | table_prix=%s table_scores=%s chunk_size=%s selection=%s workers=%s",
            self.config.price_table,
            self.config.score_table,
            self.config.chunk_size,
            self.config.selection_size,
            self._resolve_worker_count(),
        )

        self._reset_selector_outputs()

        all_frames: list[pd.DataFrame] = []
        workers = self._resolve_worker_count()
        max_in_flight = max(2, workers * 2)
        pending: set[Future[pd.DataFrame]] = set()
        submitted_chunks = 0
        completed_chunks = 0

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for symbols in self._iter_eligible_symbol_chunks():
                while len(pending) >= max_in_flight:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    completed_chunks += self._collect_completed(done, all_frames)
                    LOGGER.info(
                        "Progression scan | chunks_termines=%s chunks_soumis=%s en_vol=%s candidats_cumules=%s",
                        completed_chunks,
                        submitted_chunks,
                        len(pending),
                        sum(len(frame) for frame in all_frames),
                    )
                pending.add(executor.submit(self._process_chunk, symbols))
                submitted_chunks += 1
                LOGGER.info(
                    "Chunk soumis | index=%s taille=%s en_vol=%s",
                    submitted_chunks,
                    len(symbols),
                    len(pending),
                )

            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                completed_chunks += self._collect_completed(done, all_frames)
                LOGGER.info(
                    "Progression scan | chunks_termines=%s chunks_soumis=%s en_vol=%s candidats_cumules=%s",
                    completed_chunks,
                    submitted_chunks,
                    len(pending),
                    sum(len(frame) for frame in all_frames),
                )

        merged_candidates = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
        LOGGER.info("Agregation terminee | lignes_candidates=%s", len(merged_candidates))

        # Neutralisation cross-sectorielle sur l'univers COMPLET (cf. ranking.apply_factor_neutralization).
        merged_candidates = self._apply_factor_neutralization(merged_candidates)

        selected = self.rank_and_select(merged_candidates)

        self.update_database(selected, merged_candidates)

        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()

        if selected.empty:
            zero_candidate_diagnostic = _summarize_zero_candidate_filters(self.get_aggregated_filter_stats())
            LOGGER.critical(
                "AlphaScanner a produit 0 candidats | duree=%.2fs | "
                "Verifier : stock_bars_daily peuplee ? liquidity_threshold trop eleve ? "
                "Marche en tendance baissiere (trend_score=0 pour tous) ? | %s",
                elapsed,
                zero_candidate_diagnostic,
            )
        else:
            LOGGER.info("AlphaScanner termine en %.2fs | candidats=%s", elapsed, len(selected))

        return selected

    def _process_chunk(self, symbols: Sequence[str], as_of_date: date | None = None) -> pd.DataFrame:
        try:
            LOGGER.debug("Debut chunk | symboles=%s", len(symbols))
            market_data = self.fetch_market_data(symbols)
            computed = self.compute_factors(market_data)
            scores = self.fetch_scores(symbols)
            metadata_df = self.fetch_instrument_metadata(symbols)
            quotes_df = self.fetch_quote_snapshots(symbols, reference_date=as_of_date)
            earnings_df = self.fetch_next_earnings(symbols, reference_date=as_of_date)
            merged = self.merge_scores(computed, scores)
            merged = self._enrich_and_filter_equities(merged, metadata_df)
            merged = self._merge_optional_symbol_overlays(merged, quotes_df, earnings_df)
            # Phase 3.3.b — collecte stats par filtre en un seul passage.
            filtered, chunk_stats = self._apply_filters_with_stats(merged)
            self._log_filter_stats(chunk_stats)
            with self._filter_stats_lock:
                for key, value in chunk_stats.items():
                    self._aggregated_filter_stats[key] += int(value)
            LOGGER.debug(
                "Fin chunk | symboles=%s lignes_market=%s facteurs=%s scores=%s metadata=%s quotes=%s earnings=%s fusion=%s filtre=%s",
                len(symbols),
                len(market_data),
                len(computed),
                len(scores),
                len(metadata_df),
                len(quotes_df),
                len(earnings_df),
                len(merged),
                len(filtered),
            )
            return filtered
        except Exception:
            LOGGER.exception("Chunk en echec | symboles=%s", len(symbols))
            return pd.DataFrame()

    def _collect_completed(self, done: set[Future[pd.DataFrame]], all_frames: list[pd.DataFrame]) -> int:
        completed = 0
        for future in done:
            frame = future.result()
            completed += 1
            if not frame.empty:
                all_frames.append(frame)
        return completed

    def _resolve_worker_count(self) -> int:
        if self.config.max_workers is not None:
            return self.config.max_workers
        return min(8, os.cpu_count() or 1)

    def _reset_selector_outputs(self) -> None:
        # Phase 3.3.b — réinitialiser l'agrégat de stats à chaque run.
        with self._filter_stats_lock:
            self._aggregated_filter_stats.clear()
        reset_stmt = text(
            f"""
            UPDATE {self.config.score_table}
            SET trend_score = NULL,
                vcp_score = NULL,
                final_score = NULL,
                market_cap = NULL,
                beta_126 = NULL,
                spread_bps = NULL,
                earnings_date = NULL,
                days_to_earnings = NULL,
                earnings_blackout = 0,
                is_candidate = 0
            """
        )

        LOGGER.info(
            "Reset selector avant run | table=%s colonnes=[trend_score, vcp_score, final_score, market_cap, beta_126, spread_bps, earnings_date, days_to_earnings, earnings_blackout, is_candidate]",
            self.config.score_table,
        )
        try:
            with self.engine.begin() as conn:
                conn.execute(reset_stmt)
        except SQLAlchemyError as exc:
            LOGGER.exception("Echec du reset selector sur %s.", self.config.score_table)
            raise RuntimeError("Impossible de réinitialiser les colonnes selector avant exécution.") from exc

    def _prepare_scores_snapshot(self, scored_df: Optional[pd.DataFrame]) -> list[dict[str, object]]:
        if scored_df is None or scored_df.empty:
            return []

        available_columns = [column for column in PERSISTED_SELECTOR_SCORE_COLUMNS if column in scored_df.columns]
        if available_columns != PERSISTED_SELECTOR_SCORE_COLUMNS:
            missing = [column for column in PERSISTED_SELECTOR_SCORE_COLUMNS if column not in available_columns]
            raise ValueError(f"Colonnes selector manquantes pour persistance: {missing}")

        snapshot = scored_df.loc[:, PERSISTED_SELECTOR_SCORE_COLUMNS].copy()
        snapshot = snapshot.dropna(subset=["symbol"]).drop_duplicates(subset=["symbol"], keep="last")
        for column in ["trend_score", "vcp_score", "final_score"]:
            snapshot[column] = pd.to_numeric(snapshot[column], errors="coerce")
        for column in ["market_cap", "beta_126", "spread_bps"]:
            snapshot[column] = pd.to_numeric(snapshot[column], errors="coerce")
        snapshot["days_to_earnings"] = pd.to_numeric(snapshot["days_to_earnings"], errors="coerce")
        snapshot["earnings_blackout"] = (
            pd.to_numeric(snapshot["earnings_blackout"], errors="coerce")
            .fillna(0)
            .astype(int)
        )
        snapshot["earnings_date"] = pd.to_datetime(snapshot["earnings_date"], errors="coerce", utc=False).dt.date

        snapshot = snapshot.astype(object)
        snapshot = snapshot.where(pd.notna(snapshot), None)
        return snapshot.to_dict(orient="records")

    def _iter_eligible_symbol_chunks(self) -> Iterator[list[str]]:
        """Filtre SQL brut: liquidité 20j, close > 5, historique >= 252 jours,
        actions US uniquement (asset_class='us_equity', tradable=1, exclut ETF/crypto)."""
        offset = 0
        history_status_filter = ""
        if "history_status" in self._get_stock_metadata_columns():
            eligible_statuses = ", ".join(f"'{status}'" for status in sorted(ELIGIBLE_HISTORY_STATUSES))
            history_status_filter = f"""
                  AND (
                        sm.history_status IS NULL
                     OR TRIM(sm.history_status) = ''
                     OR LOWER(TRIM(sm.history_status)) IN ({eligible_statuses})
                  )
            """
        stmt = text(
            f"""
            WITH ranked AS (
                SELECT symbol,
                       date,
                       close,
                       volume,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                FROM {self.config.price_table}
            ), eligible AS (
                SELECT r.symbol
                FROM ranked r
                INNER JOIN stock_metadata sm ON sm.symbol = r.symbol
                WHERE sm.asset_class = 'us_equity'
                  AND sm.tradable    = 1
                  AND sm.status      = 'active'
                  AND sm.bars_available = 1
                  {history_status_filter}
                GROUP BY r.symbol
                HAVING COUNT(*) >= :min_history_days
                   AND MAX(CASE WHEN rn = 1 THEN close END) > :min_close
                   AND AVG(CASE WHEN rn <= :liquidity_lookback_days THEN close * volume END) > :liquidity_threshold
            )
            SELECT symbol
            FROM eligible
            ORDER BY symbol
            LIMIT :limit OFFSET :offset
            """
        )

        while True:
            try:
                with self.engine.connect() as conn:
                    rows = conn.execute(
                        stmt,
                        {
                            "min_history_days": self.config.min_history_days,
                            "min_close": self.config.min_close,
                            "liquidity_lookback_days": self.config.liquidity_lookback_days,
                            "liquidity_threshold": self.config.liquidity_threshold,
                            "limit": self.config.chunk_size,
                            "offset": offset,
                        },
                    ).fetchall()
            except SQLAlchemyError as exc:
                LOGGER.exception("Echec de la preselection SQL sur %s.", self.config.price_table)
                raise RuntimeError("Impossible de présélectionner les symboles.") from exc

            symbols = [str(row[0]) for row in rows]
            if not symbols:
                break

            LOGGER.info(
                "Preselection SQL | offset=%s chunk_size=%s retournes=%s",
                offset,
                self.config.chunk_size,
                len(symbols),
            )
            yield symbols
            offset += self.config.chunk_size

    # ------------------------------------------------------------------
    # Helpers de rétrocompatibilité (statiques) — Phase 3.3.a
    # ------------------------------------------------------------------
    @staticmethod
    def _winsorize_and_normalize(
        series: Optional[pd.Series],
        lower_pct: float = 0.01,
        upper_pct: float = 0.99,
    ) -> pd.Series:
        """Délègue à ``selector.factors.winsorize_and_normalize`` (préservé
        pour compat. tests/scripts qui l'appellent en static method)."""
        return winsorize_and_normalize(series, lower_pct=lower_pct, upper_pct=upper_pct)

    @staticmethod
    def _normalize_zero_one(series: Optional[pd.Series]) -> pd.Series:
        """Déprécié — utiliser ``selector.factors.winsorize_and_normalize``."""
        return winsorize_and_normalize(series)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AlphaScanner multi-facteurs")
    parser.add_argument("--preset", choices=["strict"], default="strict", help=argparse.SUPPRESS)
    parser.add_argument("--chunk-size", type=int, default=500, help="Taille des chunks de symboles")
    parser.add_argument("--selection-size", type=int, default=50, help="Nombre final de titres à retenir")
    parser.add_argument("--max-workers", type=int, default=None, help="Nombre maximum de threads")
    parser.add_argument("--liquidity-threshold", type=float, default=None, help="Seuil minimal de liquidité en dollar volume moyen 20j")
    parser.add_argument("--min-close", type=float, default=None, help="Prix minimal de clôture")
    parser.add_argument("--max-volatility-ratio", type=float, default=None, help="Seuil maximal optionnel du ratio de volatilité récente vol10/vol60")
    parser.add_argument("--min-relative-strength-index", type=float, default=None, help="Force relative minimale vs SPY (100 = performance égale au benchmark)")
    parser.add_argument("--min-high-52w-proximity", type=float, default=None, help="Proximité minimale du high 52 semaines en ratio close/high_52w")
    parser.add_argument("--min-weekly-trend-score", type=float, default=None, help="Score trend weekly minimal sur [0,1]")
    parser.add_argument("--min-atr-pct-20", type=float, default=None, help="ATR20 minimale en pourcentage du prix, ex. 0.02 = 2%%")
    parser.add_argument("--max-atr-pct-20", type=float, default=None, help="ATR20 maximale en pourcentage du prix, ex. 0.05 = 5%%")
    parser.add_argument("--min-market-cap", type=float, default=None, help="Capitalisation minimale, ex. 2000000000 = 2 Md$")
    parser.add_argument("--min-beta-126", type=float, default=None, help="Beta minimale calculée sur 126 séances vs SPY")
    parser.add_argument("--max-spread-bps", type=float, default=None, help="Spread bid/ask maximal en basis points")
    parser.add_argument("--earnings-blackout-days", type=int, default=None, help="Exclut les titres dont les résultats tombent dans les N prochains jours")
    parser.add_argument("--require-above-ma200", action="store_true", default=False, help="Exige latest_close > MA200")
    parser.add_argument("--max-anomaly-count", type=int, default=20, help="Nombre maximum d'anomalies accepté par titre")
    parser.add_argument("--sector-cap-ratio", type=float, default=0.30, help="Plafond par secteur, ex. 0.30 = 30%")
    parser.add_argument("--log-level", type=str, default="INFO", help="Niveau de log (DEBUG, INFO, WARNING, ERROR)")
    return parser


def _build_config_from_args(args: argparse.Namespace) -> AlphaScannerConfig:
    threshold_overrides: dict[str, object] = {}
    if args.liquidity_threshold is not None:
        threshold_overrides["liquidity_threshold"] = args.liquidity_threshold
    if args.min_close is not None:
        threshold_overrides["min_close"] = args.min_close
    if args.max_volatility_ratio is not None:
        threshold_overrides["max_volatility_ratio"] = args.max_volatility_ratio
    if args.min_relative_strength_index is not None:
        threshold_overrides["min_relative_strength_index"] = args.min_relative_strength_index
    if args.min_high_52w_proximity is not None:
        threshold_overrides["min_high_52w_proximity"] = args.min_high_52w_proximity
    if args.min_weekly_trend_score is not None:
        threshold_overrides["min_weekly_trend_score"] = args.min_weekly_trend_score
    if args.min_atr_pct_20 is not None:
        threshold_overrides["min_atr_pct_20"] = args.min_atr_pct_20
    if args.max_atr_pct_20 is not None:
        threshold_overrides["max_atr_pct_20"] = args.max_atr_pct_20
    if args.min_market_cap is not None:
        threshold_overrides["min_market_cap"] = args.min_market_cap
    if args.min_beta_126 is not None:
        threshold_overrides["min_beta_126"] = args.min_beta_126
    if args.max_spread_bps is not None:
        threshold_overrides["max_spread_bps"] = args.max_spread_bps
    if args.earnings_blackout_days is not None:
        threshold_overrides["earnings_blackout_days"] = args.earnings_blackout_days
    if args.require_above_ma200:
        threshold_overrides["require_above_ma200"] = True

    common_kwargs = {
        "chunk_size": args.chunk_size,
        "selection_size": args.selection_size,
        "max_workers": args.max_workers,
        "max_anomaly_count": args.max_anomaly_count,
        "sector_cap_ratio": args.sector_cap_ratio,
        **threshold_overrides,
    }

    if args.preset == "strict":
        return AlphaScannerConfig.strict_swing_cash(**common_kwargs)
    return AlphaScannerConfig.strict_swing_cash(**common_kwargs)


def main() -> None:
    args = _build_arg_parser().parse_args()
    configure_root_logging(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        log_path="./log/alpha_scanner.log",
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    config = _build_config_from_args(args)

    started_at = _utc_now_naive()
    scanner = AlphaScanner(config=config)
    result = scanner.run()
    finished_at = _utc_now_naive()

    rejected_by_filter: dict[str, int] = {}
    # Phase 3.3.b — récupération défensive (fakes de tests peuvent ne pas
    # exposer cette méthode).
    getter = getattr(scanner, "get_aggregated_filter_stats", None)
    if callable(getter):
        try:
            rejected_by_filter = {str(k): int(v) for k, v in dict(getter()).items()}
        except Exception:
            rejected_by_filter = {}

    _emit_run_summary(
        _build_cli_run_summary(
            config=config,
            result=result,
            started_at=started_at,
            finished_at=finished_at,
            rejected_by_filter=rejected_by_filter,
        )
    )

    if result.empty:
        print("Aucun candidat retenu.")
        return

    display_columns = [
        column
        for column in ["rank", "symbol", "sector", "final_score", "trend_score", "vcp_score"]
        if column in result.columns
    ]
    print(result.loc[:, display_columns].to_string(index=False))


# Phase 3.3.a — `attach_schema_version` / `merge_iex_bias_counters` sont importés
# pour préserver la surface symbolique du module (utilisés par certains scripts
# externes via ``from selector.alpha_scanner import …``).
__all__ = [
    "AlphaScanner",
    "AlphaScannerConfig",
    # Constantes (préservées pour rétrocompat)
    "FACTOR_COLUMNS",
    "SCORE_COLUMNS",
    "OUTPUT_COLUMNS",
    "PERSISTED_SELECTOR_SCORE_COLUMNS",
    "METADATA_COLUMNS",
    "ETF_NAME_PATTERNS",
    "ELIGIBLE_HISTORY_STATUSES",
    "PRICE_COLUMNS",
    "RUN_SUMMARY_PREFIX",
    # Fonctions pures ré-exportées
    "compute_factor_frame",
    "winsorize_and_normalize",
    "apply_filters_with_stats",
    "log_filter_stats",
    "enrich_and_filter_equities",
    "merge_optional_symbol_overlays",
    "merge_scores",
    "apply_factor_neutralization",
    "apply_sector_neutrality",
    "rank_and_select",
    # Helpers CLI
    "main",
    "_summarize_zero_candidate_filters",
    "attach_schema_version",
    "merge_iex_bias_counters",
]


if __name__ == "__main__":
    main()

