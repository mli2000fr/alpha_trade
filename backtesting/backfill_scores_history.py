"""Backfill point-in-time de stock_scores_history pour le backtesting."""
from __future__ import annotations

import logging
import os
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from typing import Any, cast

import pandas as pd
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from backtesting.data_loader import get_required_bars_source_filter
from common.capital_presets import DEFAULT_CAPITAL_PRESET_KEY
from database.connection import get_sqlalchemy_engine
from event_sentiment.signal_aggregator import SentimentBoostConfig, SentimentSignalAggregator
from screener.db_io import iter_symbol_chunks, load_spy_return_6m
from screener.models import ScreenerConfig
from screener.stock_screener import _process_chunk as screener_process_chunk
from selector.alpha_scanner import AlphaScanner, AlphaScannerConfig
from selector.short_score import compute_short_score

LOGGER = logging.getLogger(__name__)

SELECTOR_FILTER_STAT_KEYS = (
    "input",
    "output",
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
    "rescued_spread_iex",
    "rejected_earnings_blackout",
    "rejected_score_liquidity",
    "rejected_sanitizer",
    "rejected_anomalies",
    "rejected_missing_days",
)

PIT_MIN_QUOTE_COVERAGE_PCT = 60.0
PIT_MAX_QUOTE_AGE_DAYS = 3

HISTORY_COLUMNS = [
    "snapshot_date",
    "capital_preset_key",
    "config_fingerprint",
    "symbol",
    "sector",
    "liquidity_val",
    "relative_strength_index",
    "historical_range_score",
    "total_score",
    "trend_score",
    "vcp_score",
    "final_score",
    "market_cap",
    "beta_126",
    "spread_bps",
    "earnings_date",
    "days_to_earnings",
    "earnings_blackout",
    "selection_rank",
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
    "selector_signal_mode",  # Plan v2 Sprint 5 — long/short
    "selection_explanation",
    "sentiment_net_agg",
    "sector_impact_agg",
    "company_idio_score",
    "macro_regime_score",
    "company_idio_signal_norm",
    "macro_regime_signal_norm",
    "company_idio_component",
    "macro_regime_component",
    "quant_component",
    "final_score_sentiment",
    "final_score_walk_forward",
    "walk_forward_sentiment_weight",
    "walk_forward_macro_weight",
    "walk_forward_quant_weight",
    "calibration_run_id",
    "calibration_source",
    "signal_active",
    "anomaly_count",
    "missing_days_count",
    "short_score",
    "sma_50",
    "sma_200",
]


@dataclass(frozen=True, slots=True)
class BackfillScoresHistoryResult:
    start_date: date
    end_date: date
    trading_days_requested: int
    trading_days_processed: int
    rows_inserted: int
    trading_days_skipped_existing: int


class BackfillScoresHistoryService:
    """Reconstruit des snapshots PIT pour `stock_scores_history`."""

    def __init__(
        self,
        engine: Engine | None = None,
        screener_config: ScreenerConfig | None = None,
        scanner_config: AlphaScannerConfig | None = None,
        sentiment_config: SentimentBoostConfig | None = None,
        screener_max_workers: int | None = None,
        capital_preset_key: str = DEFAULT_CAPITAL_PRESET_KEY,
        config_fingerprint: str | None = None,
    ) -> None:
        self.engine = engine or get_sqlalchemy_engine()
        self.screener_config = screener_config or ScreenerConfig.strict_swing_cash()
        self.scanner_config = scanner_config or AlphaScannerConfig.strict_swing_cash()
        self.sentiment_config = sentiment_config or SentimentBoostConfig()
        self.screener_max_workers = screener_max_workers
        self.capital_preset_key = str(capital_preset_key or DEFAULT_CAPITAL_PRESET_KEY).strip() or DEFAULT_CAPITAL_PRESET_KEY
        self.config_fingerprint = str(config_fingerprint).strip() if config_fingerprint else None
        self.scanner = AlphaScanner(engine=self.engine, config=self.scanner_config)
        self.aggregator = SentimentSignalAggregator(engine=self.engine, config=self.sentiment_config)
        self._symbol_chunks_cache: tuple[tuple[str, ...], ...] | None = None

    @staticmethod
    def _coerce_date(value: Any) -> date | None:
        """Normalise une valeur SQL (date/datetime/string) vers `date`."""
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        return date.fromisoformat(str(value))

    # ------------------------------------------------------------------
    # Résolution des bornes
    # ------------------------------------------------------------------

    def resolve_end_date(self, start_date: date, explicit_end_date: date | None = None) -> date:
        """Résout la borne supérieure utile du backfill.

        Si `explicit_end_date` est fourni, il est borné au dernier bar disponible.
        Sinon, on s'arrête à la dernière séance < premier snapshot déjà présent
        dans `stock_scores_history`, ou à la dernière séance disponible s'il n'y a
        pas encore d'historique.
        """
        source_filter_sql, source_filter_params = get_required_bars_source_filter(
            self.engine,
            table_name="stock_bars_daily",
        )
        with self.engine.connect() as conn:
            last_bar_date = conn.execute(
                text(f"SELECT MAX(`date`) FROM stock_bars_daily WHERE 1=1 {source_filter_sql}"),
                source_filter_params,
            ).scalar_one_or_none()
            last_bar_date = self._coerce_date(last_bar_date)
            if last_bar_date is None:
                raise RuntimeError("Aucune donnée dans stock_bars_daily — impossible de backfiller.")

            if explicit_end_date is not None:
                return min(explicit_end_date, last_bar_date)

            first_existing_snapshot = conn.execute(
                text(
                    """
                    SELECT MIN(snapshot_date)
                    FROM stock_scores_history
                    WHERE snapshot_date >= :start_date
                      AND capital_preset_key = :capital_preset_key
                    """
                ),
                {"start_date": start_date, "capital_preset_key": self.capital_preset_key},
            ).scalar_one_or_none()

            first_existing_snapshot = self._coerce_date(first_existing_snapshot)
            if first_existing_snapshot is None:
                return last_bar_date

            previous_bar_date = conn.execute(
                text(
                    f"""
                    SELECT MAX(`date`)
                    FROM stock_bars_daily
                    WHERE `date` < :first_existing_snapshot
                      {source_filter_sql}
                    """
                ),
                {"first_existing_snapshot": first_existing_snapshot, **source_filter_params},
            ).scalar_one_or_none()

        previous_bar_date = self._coerce_date(previous_bar_date)
        if previous_bar_date is None:
            raise RuntimeError(
                "Impossible de trouver une séance avant le premier snapshot existant "
                f"({first_existing_snapshot})."
            )
        return previous_bar_date

    def list_trading_dates(self, start_date: date, end_date: date, overwrite_existing: bool = False) -> list[date]:
        """Liste les séances à traiter entre deux bornes."""
        source_filter_sql, source_filter_params = get_required_bars_source_filter(
            self.engine,
            table_name="stock_bars_daily",
        )
        with self.engine.connect() as conn:
            trading_days = conn.execute(
                text(
                    f"""
                    SELECT DISTINCT `date`
                    FROM stock_bars_daily
                    WHERE `date` BETWEEN :start_date AND :end_date
                      {source_filter_sql}
                    ORDER BY `date`
                    """
                ),
                {"start_date": start_date, "end_date": end_date, **source_filter_params},
            ).scalars().all()

            if overwrite_existing:
                return [self._coerce_date(day) for day in trading_days if self._coerce_date(day) is not None]

            existing_days = {
                normalized
                for raw_day in conn.execute(
                    text(
                        """
                        SELECT DISTINCT snapshot_date
                        FROM stock_scores_history
                        WHERE snapshot_date BETWEEN :start_date AND :end_date
                          AND capital_preset_key = :capital_preset_key
                        """
                    ),
                    {
                        "start_date": start_date,
                        "end_date": end_date,
                        "capital_preset_key": self.capital_preset_key,
                    },
                ).scalars().all()
                if (normalized := self._coerce_date(raw_day)) is not None
            }

        return [normalized for raw_day in trading_days if (normalized := self._coerce_date(raw_day)) not in existing_days]

    # ------------------------------------------------------------------
    # Construction d'un snapshot journalier
    # ------------------------------------------------------------------

    def build_snapshot_for_date(
        self,
        as_of_date: date,
        *,
        screener_executor: ProcessPoolExecutor | None = None,
    ) -> pd.DataFrame:
        """Construit un snapshot complet `stock_scores_history` pour une séance."""
        screener_df = self._compute_screener_snapshot(as_of_date, screener_executor=screener_executor)
        if screener_df.empty:
            LOGGER.warning("Aucun score screener pour %s.", as_of_date)
            return self._empty_history_frame()

        selector_df = self._compute_selector_snapshot(screener_df, as_of_date)
        if selector_df.empty:
            LOGGER.warning("Aucun score selector exploitable pour %s.", as_of_date)
            return self._empty_history_frame()

        # Construire sentiment_input en préservant toutes les colonnes
        # du pipeline selector pertinentes pour l'historique PIT.
        _selector_columns_to_preserve = [
            "symbol", "final_score", "trend_score", "vcp_score", "total_score", "sector",
            "liquidity_val", "relative_strength_index", "historical_range_score",
            "anomaly_count", "missing_days_count", "selector_signal_mode",
            # Colonnes enrichies par le pipeline selector (metadata / quotes / earnings / ranking)
            "market_cap", "beta_126", "spread_bps",
            "earnings_date", "days_to_earnings", "earnings_blackout",
            "selection_rank", "raw_final_score",
            "normalized_total_score", "normalized_rsi",
            "total_score_neutralized", "relative_strength_index_neutralized",
            "trend_vcp_component", "total_score_component", "rsi_component",
            "atr_pct_20", "weekly_trend_score", "high_52w_proximity", "volatility_ratio",
            "selection_explanation",
        ]
        _available_selector_cols = [c for c in _selector_columns_to_preserve if c in selector_df.columns]
        sentiment_input = selector_df[_available_selector_cols].copy()
        # ── P3 — SMA50/200 + short_score (score baissier complet) ──
        sentiment_input = self._enrich_with_sma(sentiment_input, as_of_date)
        sentiment_input["short_score"] = compute_short_score(sentiment_input)
        enriched = self.aggregator.merge(sentiment_input, trade_date=as_of_date)
        history_df = self._to_history_snapshot(enriched, as_of_date)
        LOGGER.info(
            "Snapshot PIT construit | date=%s lignes=%s candidats=%s",
            as_of_date,
            len(history_df),
            int(history_df["selection_rank"].notna().sum()) if not history_df.empty else 0,
        )
        return history_df

    def _get_symbol_chunks(self) -> tuple[tuple[str, ...], ...]:
        if self._symbol_chunks_cache is None:
            self._symbol_chunks_cache = tuple(
                tuple(chunk) for chunk in iter_symbol_chunks(self.engine, self.screener_config.chunk_size)
            )
        return self._symbol_chunks_cache

    @staticmethod
    def _index_prefetched_symbol_frame(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty or "symbol" not in frame.columns:
            return frame.copy()
        indexed = frame.copy()
        indexed["symbol"] = indexed["symbol"].astype(str)
        indexed = indexed.drop_duplicates(subset=["symbol"], keep="last")
        return indexed.set_index("symbol", drop=False)

    @staticmethod
    def _slice_prefetched_symbol_frame(frame: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
        if frame.empty or not symbols:
            return frame.iloc[0:0].copy()
        available_symbols = [symbol for symbol in symbols if symbol in frame.index]
        if not available_symbols:
            return frame.iloc[0:0].copy()
        sliced = frame.loc[available_symbols]
        if isinstance(sliced, pd.Series):
            sliced = sliced.to_frame().T
        return cast(pd.DataFrame, sliced.reset_index(drop=True).copy())

    def _create_screener_executor(self) -> ProcessPoolExecutor:
        workers = self._resolve_screener_workers()
        LOGGER.info("Backfill screener pool créé | workers=%s", workers)
        return ProcessPoolExecutor(max_workers=workers)

    def _shutdown_screener_executor(self, executor: ProcessPoolExecutor | None) -> None:
        if executor is None:
            return
        LOGGER.info("Backfill screener pool fermé")
        executor.shutdown(wait=True)

    def _compute_screener_snapshot(
        self,
        as_of_date: date,
        *,
        screener_executor: ProcessPoolExecutor | None = None,
    ) -> pd.DataFrame:
        """Rejoue le screener en mémoire sans toucher à stock_scores."""
        start_ts = datetime.now(timezone.utc)
        spy_return_6m = load_spy_return_6m(self.engine, self.screener_config, as_of_date=as_of_date)
        config_dict = self.screener_config.to_dict()
        as_of_iso = as_of_date.isoformat()
        workers = self._resolve_screener_workers()
        max_in_flight = max(2, workers * 2)
        all_results: list[pd.DataFrame] = []
        pending = set()

        LOGGER.info(
            "Backfill screener | date=%s workers=%s chunk_size=%s",
            as_of_date,
            workers,
            self.screener_config.chunk_size,
        )

        symbol_chunks = self._get_symbol_chunks()

        executor = screener_executor
        owns_executor = executor is None
        if executor is None:
            executor = self._create_screener_executor()
        try:
            for symbol_chunk in symbol_chunks:
                while len(pending) >= max_in_flight:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    self._append_completed_results(done, all_results)
                pending.add(executor.submit(screener_process_chunk, symbol_chunk, config_dict, spy_return_6m, as_of_iso))

            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                self._append_completed_results(done, all_results)
        finally:
            if owns_executor:
                self._shutdown_screener_executor(executor)

        if not all_results:
            return pd.DataFrame()

        final_scores = cast(pd.DataFrame, pd.concat(all_results, ignore_index=True))
        final_scores = (
            final_scores.sort_values(by="total_score", ascending=False)
            .drop_duplicates(subset=["symbol"])
            .reset_index(drop=True)
        )
        final_scores["anomaly_count"] = 0
        final_scores["missing_days_count"] = 0
        LOGGER.info(
            "Backfill screener terminé | date=%s scores=%s durée=%.2fs",
            as_of_date,
            len(final_scores),
            (datetime.now(timezone.utc) - start_ts).total_seconds(),
        )
        return final_scores

    def _compute_selector_snapshot(self, screener_df: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
        """Rejoue AlphaScanner en mémoire à partir du snapshot screener."""
        if screener_df.empty:
            return pd.DataFrame()

        scanner, quotes_available, earnings_available = self._resolve_pit_scanner(as_of_date)
        all_frames: list[pd.DataFrame] = []
        aggregated_filter_stats = {key: 0 for key in SELECTOR_FILTER_STAT_KEYS}
        symbols = screener_df["symbol"].dropna().astype(str).tolist()
        chunk_size = max(1, self.scanner_config.chunk_size)
        prefetched_metadata = self._index_prefetched_symbol_frame(scanner.fetch_instrument_metadata(symbols))
        raw_prefetched_quotes = (
            scanner.fetch_quote_snapshots(symbols, reference_date=as_of_date)
            if quotes_available else self._empty_quote_snapshot_frame()
        )
        prefetched_quotes, quote_diagnostics = self._prepare_pit_quote_snapshots(
            symbols,
            raw_prefetched_quotes,
            as_of_date,
        )
        quote_coverage_pct = float(quote_diagnostics.get("coverage_pct", 0.0))
        quote_covered_symbols = int(quote_diagnostics.get("covered_symbols", 0))
        quote_requested_symbols = int(quote_diagnostics.get("requested_symbols", 0))
        quote_stale_symbols = int(quote_diagnostics.get("stale_symbols", 0))
        quote_missing_spread_symbols = int(quote_diagnostics.get("missing_spread_symbols", 0))
        quote_latest_date = quote_diagnostics.get("latest_quote_date")
        quote_max_age_days = quote_diagnostics.get("max_quote_age_days")
        spread_filter_active = self._is_spread_filter_active(scanner)
        if spread_filter_active and not bool(quote_diagnostics["spread_filter_coverage_ok"]):
            LOGGER.warning(
                "Backfill PIT | date=%s couverture quotes PIT insuffisante pour filtre spread "
                "(%s/%s symboles=%.2f%% < %.2f%%, stale=%s, sans_spread=%s, latest_quote_date=%s, age_max_j=%s); "
                "filtre spread desactive pour la seance.",
                as_of_date,
                quote_covered_symbols,
                quote_requested_symbols,
                quote_coverage_pct,
                PIT_MIN_QUOTE_COVERAGE_PCT,
                quote_stale_symbols,
                quote_missing_spread_symbols,
                quote_latest_date,
                quote_max_age_days,
            )
            scanner = self._build_scanner_with_overrides(
                base_config=getattr(scanner, "config", self.scanner_config),
                max_spread_bps=None,
            )
            spread_filter_active = False
        prefetched_quotes = self._index_prefetched_symbol_frame(prefetched_quotes)
        prefetched_earnings = self._index_prefetched_symbol_frame(
            scanner.fetch_next_earnings(symbols, reference_date=as_of_date)
            if earnings_available else pd.DataFrame(columns=["symbol", "earnings_date", "days_to_earnings", "earnings_blackout"])
        )

        for start in range(0, len(symbols), chunk_size):
            chunk_symbols = symbols[start:start + chunk_size]
            market_data = self._load_market_data(chunk_symbols, as_of_date)
            computed = scanner.compute_factors(market_data)
            aux_scores = screener_df[screener_df["symbol"].isin(chunk_symbols)].copy()
            metadata_df = self._slice_prefetched_symbol_frame(prefetched_metadata, chunk_symbols)
            quotes_df = self._slice_prefetched_symbol_frame(prefetched_quotes, chunk_symbols)
            earnings_df = self._slice_prefetched_symbol_frame(prefetched_earnings, chunk_symbols)
            merged = scanner.merge_scores(computed, aux_scores)
            merged = scanner._enrich_and_filter_equities(merged, metadata_df)
            merged = scanner._merge_optional_symbol_overlays(merged, quotes_df, earnings_df)
            filtered, filter_stats = scanner._apply_filters_with_stats(merged)
            for key, value in filter_stats.items():
                aggregated_filter_stats[key] = aggregated_filter_stats.get(key, 0) + int(value)
            if not filtered.empty:
                all_frames.append(filtered)

        LOGGER.info(
            "Backfill PIT summary | date=%s quotes_available=%s earnings_available=%s avant_filtres=%s apres_filtres=%s rejet_etf=%s rejet_historique=%s rejet_prix=%s rejet_liquidite_marche=%s rejet_volatilite_relative=%s rejet_atr_pct=%s rejet_force_relative=%s rejet_ma200=%s rejet_high_52w=%s rejet_weekly=%s rejet_market_cap=%s rejet_market_cap_stale=%s rejet_beta=%s rejet_spread=%s rescues_spread_iex=%s rejet_earnings_blackout=%s rejet_liquidite_scores=%s rejet_sanitizer=%s rejet_anomalies=%s rejet_missing_days=%s quote_coverage_pct=%.2f quote_symbols=%s/%s stale_quote_symbols=%s missing_spread_symbols=%s spread_filter_active=%s latest_quote_date=%s max_quote_age_days=%s",
            as_of_date,
            quotes_available,
            earnings_available,
            aggregated_filter_stats["input"],
            aggregated_filter_stats["output"],
            aggregated_filter_stats["rejected_etf"],
            aggregated_filter_stats["rejected_history"],
            aggregated_filter_stats["rejected_price"],
            aggregated_filter_stats["rejected_market_liquidity"],
            aggregated_filter_stats["rejected_volatility"],
            aggregated_filter_stats["rejected_atr"],
            aggregated_filter_stats["rejected_relative_strength"],
            aggregated_filter_stats["rejected_ma200"],
            aggregated_filter_stats["rejected_high_52w"],
            aggregated_filter_stats["rejected_weekly"],
            aggregated_filter_stats["rejected_market_cap"],
            aggregated_filter_stats["rejected_market_cap_stale"],
            aggregated_filter_stats["rejected_beta"],
            aggregated_filter_stats["rejected_spread"],
            aggregated_filter_stats["rescued_spread_iex"],
            aggregated_filter_stats["rejected_earnings_blackout"],
            aggregated_filter_stats["rejected_score_liquidity"],
            aggregated_filter_stats["rejected_sanitizer"],
            aggregated_filter_stats["rejected_anomalies"],
            aggregated_filter_stats["rejected_missing_days"],
            quote_coverage_pct,
            quote_covered_symbols,
            quote_requested_symbols,
            quote_stale_symbols,
            quote_missing_spread_symbols,
            spread_filter_active,
            quote_latest_date,
            quote_max_age_days,
        )

        if not all_frames:
            return pd.DataFrame()

        merged_candidates = cast(pd.DataFrame, pd.concat(all_frames, ignore_index=True))
        merged_candidates = cast(pd.DataFrame, scanner._apply_factor_neutralization(merged_candidates))
        # Plan v2 Sprint 5 — enrichir short_score avant selection
        self._enrich_short_score_pit(merged_candidates, as_of_date)
        selected = scanner.rank_and_select(merged_candidates)
        short_selected = scanner.rank_and_select_short(merged_candidates, selected)
        if not short_selected.empty:
            selected = pd.concat([selected, short_selected], ignore_index=True)
            selected = selected.drop_duplicates(subset=["symbol"], keep="first")
        # Propager selector_signal_mode et selection_rank aux symboles sélectionnés.
        if "selector_signal_mode" in selected.columns:
            mode_map = selected.set_index("symbol")["selector_signal_mode"]
            merged_candidates["selector_signal_mode"] = merged_candidates["symbol"].map(mode_map)
        if "selection_rank" in selected.columns and not selected.empty:
            rank_map = selected.set_index("symbol")["selection_rank"]
            merged_candidates["selection_rank"] = merged_candidates["symbol"].map(rank_map)
        return merged_candidates

    def _enrich_short_score_pit(self, merged_df: pd.DataFrame, as_of_date: date) -> None:
        """Enrichit avec short_score dans le contexte PIT (backfill).

        Avant la correction (2026-06-25), close_df=None → les facteurs SMA50/SMA200
        (45% du poids du short_score) étaient ignorés en backtest.
        On appelle désormais ``_enrich_with_sma()`` qui interroge ``stock_bars_daily``
        en SQL pour obtenir des SMA PIT-correctes, puis ``compute_short_score()``
        détecte les colonnes ``sma_50``/``sma_200``/``last_close`` et les utilise.
        """
        try:
            from selector.short_score import compute_short_score
            # ── P0 FIX : enrichir avec SMA PIT avant le short_score ──
            enriched_sma = self._enrich_with_sma(merged_df, as_of_date)
            # _enrich_with_sma retourne une copie → on injecte les colonnes SMA dans l'original
            for col in ("sma_50", "sma_200", "last_close"):
                if col in enriched_sma.columns:
                    merged_df[col] = enriched_sma[col].values
            # compute_short_score détecte sma_50/sma_200/last_close → facteurs 3 & 4 OK
            merged_df["short_score"] = compute_short_score(merged_df)
        except Exception:
            LOGGER.debug("_enrich_short_score_pit: skipped", exc_info=True)

    @staticmethod
    def _empty_quote_snapshot_frame() -> pd.DataFrame:
        return pd.DataFrame(columns=["symbol", "quote_date", "quote_timestamp", "spread_bps", "bid_size", "ask_size"])

    def _build_scanner_with_overrides(
        self,
        *,
        base_config: AlphaScannerConfig | None = None,
        **overrides: object,
    ) -> AlphaScanner:
        effective_config = replace(base_config or self.scanner_config, **overrides)
        return AlphaScanner(engine=self.engine, config=effective_config)

    def _is_spread_filter_active(self, scanner: AlphaScanner | object) -> bool:
        config = getattr(scanner, "config", self.scanner_config)
        return getattr(config, "max_spread_bps", None) is not None

    def _prepare_pit_quote_snapshots(
        self,
        symbols: list[str],
        quotes_df: pd.DataFrame,
        as_of_date: date,
    ) -> tuple[pd.DataFrame, dict[str, object]]:
        requested_symbols = len({str(symbol) for symbol in symbols if str(symbol).strip()})
        diagnostics: dict[str, object] = {
            "requested_symbols": requested_symbols,
            "prefetched_rows": 0,
            "prefetched_symbols": 0,
            "covered_symbols": 0,
            "coverage_pct": 0.0,
            "stale_rows": 0,
            "stale_symbols": 0,
            "missing_spread_rows": 0,
            "missing_spread_symbols": 0,
            "latest_quote_date": None,
            "max_quote_age_days": None,
            "spread_filter_coverage_ok": requested_symbols == 0,
        }
        if requested_symbols == 0:
            return self._empty_quote_snapshot_frame(), diagnostics
        if quotes_df.empty or "symbol" not in quotes_df.columns:
            LOGGER.info(
                "Backfill PIT quotes | date=%s requested_symbols=%s prefetched_symbols=0 coverage=0.00%% stale_symbols=0 sans_spread=0 latest_quote_date=None age_max_j=None",
                as_of_date,
                requested_symbols,
            )
            return self._empty_quote_snapshot_frame(), diagnostics

        normalized = quotes_df.copy()
        normalized["symbol"] = normalized["symbol"].astype(str)
        for column in ("quote_date", "quote_timestamp", "spread_bps", "bid_size", "ask_size"):
            if column not in normalized.columns:
                normalized[column] = pd.NA
        quote_dates = cast(pd.Series, pd.to_datetime(normalized["quote_date"], errors="coerce", utc=False))
        normalized["quote_date"] = quote_dates
        spread_numeric = cast(pd.Series, pd.to_numeric(normalized["spread_bps"], errors="coerce"))
        age_days = pd.Series(pd.NA, index=normalized.index, dtype="Float64")
        valid_quote_dates = cast(pd.Series, quote_dates.notna())
        if bool(valid_quote_dates.any()):
            as_of_ts = pd.Timestamp(as_of_date)
            valid_quote_series = cast(pd.Series, quote_dates.loc[valid_quote_dates])
            computed_age_days = cast(
                pd.Series,
                (as_of_ts.normalize() - valid_quote_series.dt.normalize()).dt.days.astype("Float64"),
            )
            age_days.loc[valid_quote_dates] = computed_age_days

        stale_mask = normalized["quote_date"].isna() | age_days.isna() | (age_days > PIT_MAX_QUOTE_AGE_DAYS) | (age_days < 0)
        missing_spread_mask = ~stale_mask & spread_numeric.isna()
        usable_mask = ~stale_mask & spread_numeric.notna()
        usable_quotes = cast(pd.DataFrame, normalized.loc[usable_mask].copy())
        covered_symbols = int(usable_quotes["symbol"].nunique()) if not usable_quotes.empty else 0
        stale_symbols = int(cast(pd.Series, normalized.loc[stale_mask, "symbol"]).nunique()) if bool(stale_mask.any()) else 0
        missing_spread_symbols = (
            int(cast(pd.Series, normalized.loc[missing_spread_mask, "symbol"]).nunique()) if bool(missing_spread_mask.any()) else 0
        )
        latest_quote_date: str | None = None
        max_quote_age_days: int | None = None
        if bool(usable_mask.any()):
            latest_quote_ts = cast(pd.Series, normalized.loc[usable_mask, "quote_date"]).max()
            if pd.notna(latest_quote_ts):
                latest_quote_date = cast(pd.Timestamp, latest_quote_ts).date().isoformat()
            max_quote_age_raw = age_days.loc[usable_mask].max()
            if pd.notna(max_quote_age_raw):
                max_quote_age_days = int(max_quote_age_raw)
        coverage_pct = round((covered_symbols / requested_symbols) * 100.0, 2)
        spread_filter_coverage_ok = coverage_pct >= PIT_MIN_QUOTE_COVERAGE_PCT

        diagnostics.update(
            {
                "prefetched_rows": int(len(normalized)),
                "prefetched_symbols": int(normalized["symbol"].nunique()),
                "covered_symbols": covered_symbols,
                "stale_rows": int(stale_mask.sum()),
                "stale_symbols": stale_symbols,
                "missing_spread_rows": int(missing_spread_mask.sum()),
                "missing_spread_symbols": missing_spread_symbols,
                "latest_quote_date": latest_quote_date,
                "max_quote_age_days": max_quote_age_days,
                "coverage_pct": coverage_pct,
                "spread_filter_coverage_ok": spread_filter_coverage_ok,
            }
        )

        LOGGER.info(
            "Backfill PIT quotes | date=%s requested_symbols=%s prefetched_symbols=%s usable_symbols=%s coverage=%.2f%% stale_symbols=%s sans_spread=%s latest_quote_date=%s age_max_j=%s",
            as_of_date,
            requested_symbols,
            diagnostics["prefetched_symbols"],
            covered_symbols,
            coverage_pct,
            stale_symbols,
            missing_spread_symbols,
            latest_quote_date,
            max_quote_age_days,
        )
        return usable_quotes.loc[:, ["symbol", "quote_date", "quote_timestamp", "spread_bps", "bid_size", "ask_size"]], diagnostics

    def _has_quote_snapshot_coverage(self, as_of_date: date) -> bool:
        """Indique si un historique de quotes exploitable existe au plus tard à `as_of_date`."""
        stmt = text(
            """
            SELECT 1
            FROM stock_quote_snapshots
            WHERE quote_date BETWEEN :min_quote_date AND :as_of_date
              AND spread_bps IS NOT NULL
            LIMIT 1
            """
        )
        try:
            with self.engine.connect() as conn:
                return conn.execute(
                    stmt,
                    {"as_of_date": as_of_date, "min_quote_date": as_of_date - timedelta(days=PIT_MAX_QUOTE_AGE_DAYS)},
                ).first() is not None
        except Exception:
            return False

    def _has_earnings_calendar_coverage(self, as_of_date: date) -> bool:
        """Indique si un calendrier earnings exploitable existe à partir de `as_of_date`."""
        stmt = text(
            """
            SELECT 1
            FROM stock_earnings_calendar
            WHERE earnings_date >= :as_of_date
            LIMIT 1
            """
        )
        try:
            with self.engine.connect() as conn:
                return conn.execute(stmt, {"as_of_date": as_of_date}).first() is not None
        except Exception:
            return False

    def _resolve_pit_scanner(self, as_of_date: date) -> tuple[AlphaScanner, bool, bool]:
        """Construit un scanner PIT strict, avec fallback automatique sur les overlays non couverts."""
        quotes_available = self._has_quote_snapshot_coverage(as_of_date)
        earnings_available = self._has_earnings_calendar_coverage(as_of_date)

        overrides: dict[str, object] = {}
        disabled_filters: list[str] = []

        if self.scanner_config.max_spread_bps is not None and not quotes_available:
            overrides["max_spread_bps"] = None
            disabled_filters.append(f"spread_bps<={self.scanner_config.max_spread_bps}")
        if self.scanner_config.earnings_blackout_days is not None and not earnings_available:
            overrides["earnings_blackout_days"] = None
            disabled_filters.append(f"earnings_blackout_days={self.scanner_config.earnings_blackout_days}")

        if not overrides:
            return self.scanner, quotes_available, earnings_available

        LOGGER.warning(
            "Backfill PIT | date=%s couverture overlays absente; filtres stricts desactives=%s",
            as_of_date,
            ", ".join(disabled_filters),
        )
        return self._build_scanner_with_overrides(base_config=self.scanner_config, **overrides), quotes_available, earnings_available

    def _load_market_data(self, symbols: list[str], as_of_date: date) -> pd.DataFrame:
        """Charge l'historique de marché borné à `as_of_date` pour un lot de symboles."""
        if not symbols:
            return pd.DataFrame(columns=["symbol", "date", "close", "volume", "high", "low"])

        source_filter_sql, source_filter_params = get_required_bars_source_filter(
            self.engine,
            table_name=self.scanner_config.price_table,
        )

        stmt = text(
            f"""
            SELECT symbol, `date`, `close`, volume, high, low
            FROM {self.scanner_config.price_table}
            WHERE symbol IN :symbols
              AND `date` <= :as_of_date
              {source_filter_sql}
            ORDER BY symbol, `date`
            """
        ).bindparams(bindparam("symbols", expanding=True))
        with self.engine.connect() as conn:
            df = pd.read_sql_query(
                stmt,
                conn,
                params={"symbols": symbols, "as_of_date": as_of_date, **source_filter_params},
            )
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], utc=False)
        return df

    def _enrich_with_sma(
        self,
        selector_df: pd.DataFrame,
        as_of_date: date,
    ) -> pd.DataFrame:
        """Ajoute les colonnes ``sma_50`` et ``sma_200`` PIT depuis stock_bars_daily."""
        df = selector_df.copy()
        if df.empty or "symbol" not in df.columns:
            df["sma_50"] = None
            df["sma_200"] = None
            return df

        symbols = df["symbol"].unique().tolist()
        if not symbols:
            df["sma_50"] = None
            df["sma_200"] = None
            return df

        placeholders = ", ".join([f":s{i}" for i in range(len(symbols))])
        params: dict[str, Any] = {f"s{i}": s for i, s in enumerate(symbols)}
        params["trade_date"] = as_of_date
        params["limit_50"] = 50 + 1
        params["limit_200"] = 200 + 1

        # Une seule requête pour les deux SMA
        query = text(f"""
            WITH ranked AS (
                SELECT
                    symbol,
                    COALESCE(adj_close, close) AS close_price,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                FROM stock_bars_daily
                WHERE symbol IN ({placeholders})
                  AND date <= :trade_date
            )
            SELECT
                symbol,
                AVG(CASE WHEN rn <= 50 THEN close_price END) AS sma_50,
                AVG(CASE WHEN rn <= 200 THEN close_price END) AS sma_200,
                MAX(CASE WHEN rn = 1 THEN close_price END) AS last_close
            FROM ranked
            WHERE rn <= 200
            GROUP BY symbol
        """)

        with self.engine.connect() as conn:
            sma_rows = conn.execute(query, params).mappings().all()

        sma_map: dict[str, dict[str, float | None]] = {}
        for row in sma_rows:
            sym = str(row["symbol"])
            sma_map[sym] = {
                "sma_50": float(row["sma_50"]) if row["sma_50"] is not None else None,
                "sma_200": float(row["sma_200"]) if row["sma_200"] is not None else None,
                "last_close": float(row["last_close"]) if row["last_close"] is not None else None,
            }

        df["sma_50"] = [sma_map.get(str(s), {}).get("sma_50") for s in df["symbol"]]
        df["sma_200"] = [sma_map.get(str(s), {}).get("sma_200") for s in df["symbol"]]
        # Ajouter aussi last_close pour la comparaison SMA
        df["last_close"] = [sma_map.get(str(s), {}).get("last_close") for s in df["symbol"]]
        return df

    def _to_history_snapshot(self, enriched_df: pd.DataFrame, snapshot_date: date) -> pd.DataFrame:
        """Normalise un DataFrame enrichi vers le schéma `stock_scores_history`."""
        if enriched_df.empty:
            return self._empty_history_frame()

        history_df = enriched_df.copy()
        history_df["snapshot_date"] = snapshot_date
        history_df["capital_preset_key"] = self.capital_preset_key
        history_df["config_fingerprint"] = self.config_fingerprint
        defaults: dict[str, Any] = {
            "sector": None,
            "liquidity_val": None,
            "relative_strength_index": None,
            "historical_range_score": None,
            "total_score": None,
            "trend_score": None,
            "vcp_score": None,
            "final_score": None,
            "market_cap": None,
            "beta_126": None,
            "spread_bps": None,
            "earnings_date": None,
            "days_to_earnings": None,
            "earnings_blackout": 0,
            "selection_rank": None,
            "raw_final_score": None,
            "normalized_total_score": None,
            "normalized_rsi": None,
            "total_score_neutralized": None,
            "relative_strength_index_neutralized": None,
            "trend_vcp_component": 0.0,
            "total_score_component": 0.0,
            "rsi_component": 0.0,
            "atr_pct_20": None,
            "weekly_trend_score": None,
            "high_52w_proximity": None,
            "volatility_ratio": None,
            "selector_signal_mode": None,  # Plan v2 Sprint 5 — long/short
            "selection_explanation": None,
            "sentiment_net_agg": 0.0,
            "sector_impact_agg": 0.0,
            "company_idio_score": 0.0,
            "macro_regime_score": 0.0,
            "company_idio_signal_norm": 0.5,
            "macro_regime_signal_norm": 0.5,
            "company_idio_component": 0.0,
            "macro_regime_component": 0.0,
            "quant_component": 0.0,
            "final_score_sentiment": None,
            "final_score_walk_forward": None,
            "walk_forward_sentiment_weight": None,
            "walk_forward_macro_weight": None,
            "walk_forward_quant_weight": None,
            "calibration_run_id": None,
            "calibration_source": None,
            "signal_active": 0,
            "anomaly_count": 0,
            "missing_days_count": 0,
            "short_score": None,
            "sma_50": None,
            "sma_200": None,
        }
        for col, default in defaults.items():
            if col not in history_df.columns:
                history_df[col] = default

        history_df["signal_active"] = history_df["signal_active"].fillna(False).astype(int)
        history_df["earnings_blackout"] = history_df["earnings_blackout"].fillna(0).astype(int)
        history_df["anomaly_count"] = history_df["anomaly_count"].fillna(0).astype(int)
        history_df["missing_days_count"] = history_df["missing_days_count"].fillna(0).astype(int)
        # SMA50/200 et short_score sont optionnels (garder None si absents)
        for col in ("sma_50", "sma_200", "short_score"):
            if col not in history_df.columns:
                history_df[col] = None
        earnings_dates = pd.to_datetime(history_df["earnings_date"], errors="coerce", utc=False)
        history_df["earnings_date"] = pd.Series(
            [value.date() if not pd.isna(value) else None for value in earnings_dates],
            index=history_df.index,
            dtype="object",
        )
        history_df["symbol"] = history_df["symbol"].astype(str)
        history_df = history_df.loc[:, HISTORY_COLUMNS].copy()
        history_df = history_df.drop_duplicates(subset=["snapshot_date", "symbol"], keep="last")
        return history_df

    def _empty_history_frame(self) -> pd.DataFrame:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------

    def persist_snapshot(self, snapshot_df: pd.DataFrame, overwrite_existing: bool = False) -> int:
        """Insère un snapshot journalier dans `stock_scores_history`."""
        if snapshot_df.empty:
            return 0

        snapshot_dates = snapshot_df["snapshot_date"].dropna().unique().tolist()
        if len(snapshot_dates) != 1:
            raise ValueError("persist_snapshot attend exactement une seule snapshot_date par lot.")
        snapshot_date = snapshot_dates[0]
        preset_keys = snapshot_df["capital_preset_key"].dropna().astype(str).unique().tolist()
        if len(preset_keys) != 1:
            raise ValueError("persist_snapshot attend exactement une seule capital_preset_key par lot.")
        capital_preset_key = preset_keys[0]

        insert_stmt = text(
            """
            INSERT INTO stock_scores_history (
                snapshot_date, capital_preset_key, config_fingerprint, symbol, sector,
                liquidity_val, relative_strength_index, historical_range_score, total_score,
                trend_score, vcp_score, final_score,
                market_cap, beta_126, spread_bps, earnings_date, days_to_earnings, earnings_blackout,
                selection_rank, raw_final_score,
                normalized_total_score, normalized_rsi,
                total_score_neutralized, relative_strength_index_neutralized,
                trend_vcp_component, total_score_component, rsi_component,
                atr_pct_20, weekly_trend_score, high_52w_proximity, volatility_ratio,
                is_candidate, selector_signal_mode, selection_explanation,
                sentiment_net_agg, sector_impact_agg,
                company_idio_score, macro_regime_score,
                company_idio_signal_norm, macro_regime_signal_norm,
                company_idio_component, macro_regime_component, quant_component,
                final_score_sentiment, final_score_walk_forward,
                walk_forward_sentiment_weight, walk_forward_macro_weight, walk_forward_quant_weight,
                calibration_run_id, calibration_source,
                signal_active,
                anomaly_count, missing_days_count, short_score, sma_50, sma_200
            ) VALUES (
                :snapshot_date, :capital_preset_key, :config_fingerprint, :symbol, :sector,
                :liquidity_val, :relative_strength_index, :historical_range_score, :total_score,
                :trend_score, :vcp_score, :final_score,
                :market_cap, :beta_126, :spread_bps, :earnings_date, :days_to_earnings, :earnings_blackout,
                :selection_rank, :raw_final_score,
                :normalized_total_score, :normalized_rsi,
                :total_score_neutralized, :relative_strength_index_neutralized,
                :trend_vcp_component, :total_score_component, :rsi_component,
                :atr_pct_20, :weekly_trend_score, :high_52w_proximity, :volatility_ratio,
                :is_candidate, :selector_signal_mode, :selection_explanation,
                :sentiment_net_agg, :sector_impact_agg,
                :company_idio_score, :macro_regime_score,
                :company_idio_signal_norm, :macro_regime_signal_norm,
                :company_idio_component, :macro_regime_component, :quant_component,
                :final_score_sentiment, :final_score_walk_forward,
                :walk_forward_sentiment_weight, :walk_forward_macro_weight, :walk_forward_quant_weight,
                :calibration_run_id, :calibration_source,
                :signal_active,
                :anomaly_count, :missing_days_count, :short_score, :sma_50, :sma_200
            )
            """
        )

        records = cast(pd.DataFrame, snapshot_df.astype(object)).to_dict(orient="records")
        clean_records = [
            {key: (None if pd.isna(value) else value) for key, value in record.items()}
            for record in records
        ]

        with self.engine.begin() as conn:
            if overwrite_existing:
                conn.execute(
                    text(
                        "DELETE FROM stock_scores_history WHERE snapshot_date = :snapshot_date AND capital_preset_key = :capital_preset_key"
                    ),
                    {"snapshot_date": snapshot_date, "capital_preset_key": capital_preset_key},
                )
            conn.execute(insert_stmt, clean_records)
        return len(snapshot_df)

    # ------------------------------------------------------------------
    # Orchestration globale
    # ------------------------------------------------------------------

    def backfill(
        self,
        start_date: date,
        end_date: date | None = None,
        overwrite_existing: bool = False,
        limit_days: int | None = None,
    ) -> BackfillScoresHistoryResult:
        """Exécute le backfill entre deux bornes."""
        resolved_end = self.resolve_end_date(start_date, explicit_end_date=end_date)
        trading_days = self.list_trading_dates(start_date, resolved_end, overwrite_existing=overwrite_existing)
        if limit_days is not None:
            trading_days = trading_days[:limit_days]

        skipped_existing = 0
        rows_inserted = 0
        processed = 0

        LOGGER.info(
            "Backfill stock_scores_history | start=%s end=%s séances=%s overwrite=%s",
            start_date,
            resolved_end,
            len(trading_days),
            overwrite_existing,
        )

        if not overwrite_existing:
            source_filter_sql, source_filter_params = get_required_bars_source_filter(
                self.engine,
                table_name="stock_bars_daily",
            )
            with self.engine.connect() as conn:
                total_trading_days = conn.execute(
                    text(
                        f"""
                        SELECT COUNT(DISTINCT `date`)
                        FROM stock_bars_daily
                        WHERE `date` BETWEEN :start_date AND :end_date
                          {source_filter_sql}
                        """
                    ),
                    {"start_date": start_date, "end_date": resolved_end, **source_filter_params},
                ).scalar_one()
            skipped_existing = int(total_trading_days) - len(trading_days)

        screener_executor = self._create_screener_executor() if trading_days else None
        try:
            for idx, trading_day in enumerate(trading_days, start=1):
                LOGGER.info("Backfill progression | %s/%s | date=%s", idx, len(trading_days), trading_day)
                try:
                    snapshot = self.build_snapshot_for_date(trading_day, screener_executor=screener_executor)
                except Exception:
                    LOGGER.exception("Backfill interrompu pendant la construction du snapshot | date=%s", trading_day)
                    raise
                inserted_for_day = self.persist_snapshot(snapshot, overwrite_existing=overwrite_existing)
                rows_inserted += inserted_for_day
                processed += 1
                LOGGER.info(
                    "Backfill snapshot persisté | date=%s lignes=%s lignes_cumulées=%s séances_traitées=%s/%s",
                    trading_day,
                    inserted_for_day,
                    rows_inserted,
                    processed,
                    len(trading_days),
                )
        finally:
            self._shutdown_screener_executor(screener_executor)

        return BackfillScoresHistoryResult(
            start_date=start_date,
            end_date=resolved_end,
            trading_days_requested=len(trading_days),
            trading_days_processed=processed,
            rows_inserted=rows_inserted,
            trading_days_skipped_existing=skipped_existing,
        )

    # ------------------------------------------------------------------

    def _resolve_screener_workers(self) -> int:
        if self.screener_max_workers is not None:
            return max(1, self.screener_max_workers)
        return max(1, os.cpu_count() or 1)

    @staticmethod
    def _append_completed_results(done, all_results: list[pd.DataFrame]) -> None:
        for future in done:
            chunk_result = future.result()
            if not chunk_result.empty:
                all_results.append(chunk_result)




