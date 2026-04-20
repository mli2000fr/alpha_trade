"""Backfill point-in-time de stock_scores_history pour le backtesting."""
from __future__ import annotations

import logging
import os
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, cast

import pandas as pd
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from database.connection import get_sqlalchemy_engine
from event_sentiment.signal_aggregator import SentimentBoostConfig, SentimentSignalAggregator
from screener.db_io import iter_symbol_chunks, load_spy_return_6m
from screener.models import ScreenerConfig
from screener.stock_screener import _process_chunk as screener_process_chunk
from selector.alpha_scanner import AlphaScanner, AlphaScannerConfig

LOGGER = logging.getLogger(__name__)

HISTORY_COLUMNS = [
    "snapshot_date",
    "symbol",
    "sector",
    "liquidity_val",
    "relative_strength_index",
    "historical_range_score",
    "total_score",
    "trend_score",
    "vcp_score",
    "final_score",
    "is_candidate",
    "sentiment_net_agg",
    "sector_impact_agg",
    "final_score_sentiment",
    "signal_active",
    "anomaly_count",
    "missing_days_count",
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
    ) -> None:
        self.engine = engine or get_sqlalchemy_engine()
        self.screener_config = screener_config or ScreenerConfig()
        self.scanner_config = scanner_config or AlphaScannerConfig()
        self.sentiment_config = sentiment_config or SentimentBoostConfig()
        self.screener_max_workers = screener_max_workers
        self.scanner = AlphaScanner(engine=self.engine, config=self.scanner_config)
        self.aggregator = SentimentSignalAggregator(engine=self.engine, config=self.sentiment_config)

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
        with self.engine.connect() as conn:
            last_bar_date = conn.execute(text("SELECT MAX(`date`) FROM stock_bars_daily")).scalar_one_or_none()
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
                    """
                ),
                {"start_date": start_date},
            ).scalar_one_or_none()

            first_existing_snapshot = self._coerce_date(first_existing_snapshot)
            if first_existing_snapshot is None:
                return last_bar_date

            previous_bar_date = conn.execute(
                text(
                    """
                    SELECT MAX(`date`)
                    FROM stock_bars_daily
                    WHERE `date` < :first_existing_snapshot
                    """
                ),
                {"first_existing_snapshot": first_existing_snapshot},
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
        with self.engine.connect() as conn:
            trading_days = conn.execute(
                text(
                    """
                    SELECT DISTINCT `date`
                    FROM stock_bars_daily
                    WHERE `date` BETWEEN :start_date AND :end_date
                    ORDER BY `date`
                    """
                ),
                {"start_date": start_date, "end_date": end_date},
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
                        """
                    ),
                    {"start_date": start_date, "end_date": end_date},
                ).scalars().all()
                if (normalized := self._coerce_date(raw_day)) is not None
            }

        return [normalized for raw_day in trading_days if (normalized := self._coerce_date(raw_day)) not in existing_days]

    # ------------------------------------------------------------------
    # Construction d'un snapshot journalier
    # ------------------------------------------------------------------

    def build_snapshot_for_date(self, as_of_date: date) -> pd.DataFrame:
        """Construit un snapshot complet `stock_scores_history` pour une séance."""
        screener_df = self._compute_screener_snapshot(as_of_date)
        if screener_df.empty:
            LOGGER.warning("Aucun score screener pour %s.", as_of_date)
            return self._empty_history_frame()

        selector_df = self._compute_selector_snapshot(screener_df, as_of_date)
        if selector_df.empty:
            LOGGER.warning("Aucun score selector exploitable pour %s.", as_of_date)
            return self._empty_history_frame()

        sentiment_input = selector_df[[
            "symbol", "final_score", "trend_score", "vcp_score", "total_score", "sector",
            "liquidity_val", "relative_strength_index", "historical_range_score",
            "anomaly_count", "missing_days_count", "is_candidate",
        ]].copy()
        enriched = self.aggregator.merge(sentiment_input, trade_date=as_of_date)
        history_df = self._to_history_snapshot(enriched, as_of_date)
        LOGGER.info(
            "Snapshot PIT construit | date=%s lignes=%s candidats=%s",
            as_of_date,
            len(history_df),
            int(history_df["is_candidate"].sum()) if not history_df.empty else 0,
        )
        return history_df

    def _compute_screener_snapshot(self, as_of_date: date) -> pd.DataFrame:
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

        with ProcessPoolExecutor(max_workers=workers) as executor:
            for symbol_chunk in iter_symbol_chunks(self.engine, self.screener_config.chunk_size):
                while len(pending) >= max_in_flight:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    self._append_completed_results(done, all_results)
                pending.add(executor.submit(screener_process_chunk, symbol_chunk, config_dict, spy_return_6m, as_of_iso))

            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                self._append_completed_results(done, all_results)

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

        all_frames: list[pd.DataFrame] = []
        symbols = screener_df["symbol"].dropna().astype(str).tolist()
        chunk_size = max(1, self.scanner_config.chunk_size)

        for start in range(0, len(symbols), chunk_size):
            chunk_symbols = symbols[start:start + chunk_size]
            market_data = self._load_market_data(chunk_symbols, as_of_date)
            computed = self.scanner.compute_factors(market_data)
            aux_scores = screener_df[screener_df["symbol"].isin(chunk_symbols)].copy()
            metadata_df = self.scanner.fetch_instrument_metadata(chunk_symbols)
            merged = self.scanner.merge_scores(computed, aux_scores)
            merged = self.scanner._enrich_and_filter_equities(merged, metadata_df)
            filtered = self.scanner.apply_filters(merged)
            if not filtered.empty:
                all_frames.append(filtered)

        if not all_frames:
            return pd.DataFrame()

        merged_candidates = cast(pd.DataFrame, pd.concat(all_frames, ignore_index=True))
        merged_candidates = cast(pd.DataFrame, self.scanner._apply_factor_neutralization(merged_candidates))
        selected = self.scanner.rank_and_select(merged_candidates)
        selected_symbols = set(selected["symbol"].astype(str).tolist()) if not selected.empty else set()
        merged_candidates["is_candidate"] = merged_candidates["symbol"].astype(str).isin(selected_symbols).astype(int)
        return merged_candidates

    def _load_market_data(self, symbols: list[str], as_of_date: date) -> pd.DataFrame:
        """Charge l'historique de marché borné à `as_of_date` pour un lot de symboles."""
        if not symbols:
            return pd.DataFrame(columns=["symbol", "date", "close", "volume", "high", "low"])

        stmt = text(
            f"""
            SELECT symbol, `date`, `close`, volume, high, low
            FROM {self.scanner_config.price_table}
            WHERE symbol IN :symbols
              AND `date` <= :as_of_date
            ORDER BY symbol, `date`
            """
        ).bindparams(bindparam("symbols", expanding=True))
        with self.engine.connect() as conn:
            df = pd.read_sql_query(stmt, conn, params={"symbols": symbols, "as_of_date": as_of_date})
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], utc=False)
        return df

    def _to_history_snapshot(self, enriched_df: pd.DataFrame, snapshot_date: date) -> pd.DataFrame:
        """Normalise un DataFrame enrichi vers le schéma `stock_scores_history`."""
        if enriched_df.empty:
            return self._empty_history_frame()

        history_df = enriched_df.copy()
        history_df["snapshot_date"] = snapshot_date
        defaults: dict[str, Any] = {
            "sector": None,
            "liquidity_val": None,
            "relative_strength_index": None,
            "historical_range_score": None,
            "total_score": None,
            "trend_score": None,
            "vcp_score": None,
            "final_score": None,
            "is_candidate": 0,
            "sentiment_net_agg": 0.0,
            "sector_impact_agg": 0.0,
            "final_score_sentiment": None,
            "signal_active": 0,
            "anomaly_count": 0,
            "missing_days_count": 0,
        }
        for col, default in defaults.items():
            if col not in history_df.columns:
                history_df[col] = default

        history_df["signal_active"] = history_df["signal_active"].fillna(False).astype(int)
        history_df["is_candidate"] = history_df["is_candidate"].fillna(0).astype(int)
        history_df["anomaly_count"] = history_df["anomaly_count"].fillna(0).astype(int)
        history_df["missing_days_count"] = history_df["missing_days_count"].fillna(0).astype(int)
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

        insert_stmt = text(
            """
            INSERT INTO stock_scores_history (
                snapshot_date, symbol, sector,
                liquidity_val, relative_strength_index, historical_range_score, total_score,
                trend_score, vcp_score, final_score, is_candidate,
                sentiment_net_agg, sector_impact_agg, final_score_sentiment, signal_active,
                anomaly_count, missing_days_count
            ) VALUES (
                :snapshot_date, :symbol, :sector,
                :liquidity_val, :relative_strength_index, :historical_range_score, :total_score,
                :trend_score, :vcp_score, :final_score, :is_candidate,
                :sentiment_net_agg, :sector_impact_agg, :final_score_sentiment, :signal_active,
                :anomaly_count, :missing_days_count
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
                    text("DELETE FROM stock_scores_history WHERE snapshot_date = :snapshot_date"),
                    {"snapshot_date": snapshot_date},
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
            with self.engine.connect() as conn:
                total_trading_days = conn.execute(
                    text(
                        """
                        SELECT COUNT(DISTINCT `date`)
                        FROM stock_bars_daily
                        WHERE `date` BETWEEN :start_date AND :end_date
                        """
                    ),
                    {"start_date": start_date, "end_date": resolved_end},
                ).scalar_one()
            skipped_existing = int(total_trading_days) - len(trading_days)

        for idx, trading_day in enumerate(trading_days, start=1):
            LOGGER.info("Backfill progression | %s/%s | date=%s", idx, len(trading_days), trading_day)
            snapshot = self.build_snapshot_for_date(trading_day)
            rows_inserted += self.persist_snapshot(snapshot, overwrite_existing=overwrite_existing)
            processed += 1

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




