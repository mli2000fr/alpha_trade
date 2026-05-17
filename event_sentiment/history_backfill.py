from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence, cast
from uuid import uuid4

from common.utils import configure_root_logging
from event_sentiment.aggregation import build_sector_daily_features, build_ticker_daily_features
from event_sentiment.config import EventSentimentConfig
from event_sentiment.db_io import EventSentimentRepository
from event_sentiment.importe_news import resolve_symbols_from_inputs

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True, slots=True)
class EventSentimentHistoryBackfillResult:
    start_date: date
    end_date: date
    trade_dates_requested: int
    trade_dates_processed: int
    batches_processed: int
    ticker_rows_upserted: int
    sector_rows_upserted: int


class EventSentimentHistoryBackfillService:
    def __init__(
        self,
        repository: EventSentimentRepository | None = None,
        config: EventSentimentConfig | None = None,
    ) -> None:
        self.repository = repository or EventSentimentRepository()
        self.config = config or EventSentimentConfig()

    def resolve_bounds(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        years: int | None = None,
        ingestion_source: str | None = None,
    ) -> tuple[date, date]:
        scored_dates = self.repository.list_scored_trade_dates(ingestion_source=ingestion_source)
        if not scored_dates:
            raise RuntimeError("Aucune date scorée disponible dans news_raw/news_sentiment pour reconstruire l'historique.")

        resolved_end = end_date or max(scored_dates)
        if start_date is not None:
            resolved_start = start_date
        else:
            lookback_years = years or self.config.bootstrap_default_years
            resolved_start = resolved_end - timedelta(days=lookback_years * 365)

        available_dates = [trade_date for trade_date in scored_dates if resolved_start <= trade_date <= resolved_end]
        if not available_dates:
            raise RuntimeError(
                f"Aucune date scorée disponible dans la fenêtre demandée [{resolved_start} → {resolved_end}]."
            )
        return min(available_dates), max(available_dates)

    def list_trade_dates(
        self,
        start_date: date,
        end_date: date,
        *,
        ingestion_source: str | None = None,
    ) -> list[date]:
        return self.repository.list_scored_trade_dates(
            start_date=start_date,
            end_date=end_date,
            ingestion_source=ingestion_source,
        )

    @staticmethod
    def _chunk_dates(trade_dates: Sequence[date], batch_days: int) -> list[list[date]]:
        return [list(trade_dates[index:index + batch_days]) for index in range(0, len(trade_dates), batch_days)]

    def backfill(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        years: int | None = None,
        batch_days: int | None = None,
        *,
        ingestion_source: str | None = None,
        ticker_symbols: list[str] | None = None,
    ) -> EventSentimentHistoryBackfillResult:
        normalized_ticker_symbols = sorted({str(symbol).strip().upper() for symbol in (ticker_symbols or []) if str(symbol).strip()})
        resolved_start, resolved_end = self.resolve_bounds(
            start_date=start_date,
            end_date=end_date,
            years=years,
            ingestion_source=ingestion_source,
        )
        trade_dates = self.list_trade_dates(
            resolved_start,
            resolved_end,
            ingestion_source=ingestion_source,
        )
        if not trade_dates:
            return EventSentimentHistoryBackfillResult(
                start_date=resolved_start,
                end_date=resolved_end,
                trade_dates_requested=0,
                trade_dates_processed=0,
                batches_processed=0,
                ticker_rows_upserted=0,
                sector_rows_upserted=0,
            )

        effective_batch_days = batch_days or self.config.bootstrap_batch_days
        date_batches = self._chunk_dates(trade_dates, effective_batch_days)
        ticker_rows_upserted = 0
        sector_rows_upserted = 0

        for batch_index, target_dates in enumerate(date_batches, start=1):
            target_date_set = set(target_dates)
            batch_start = min(target_dates) - timedelta(days=self.config.feature_history_buffer_days)
            batch_end = max(target_dates)
            LOGGER.info(
                "Event sentiment history backfill | batch=%s/%s target_dates=%s range=[%s -> %s]",
                batch_index,
                len(date_batches),
                len(target_dates),
                batch_start,
                batch_end,
            )
            ticker_df, sector_df, macro_df = self.repository.load_feature_frames(
                start_date=batch_start,
                end_date=batch_end,
                ingestion_source=ingestion_source,
                ticker_symbols=normalized_ticker_symbols or None,
            )
            ticker_features = build_ticker_daily_features(
                ticker_df,
                feature_version=self.config.feature_version,
                rolling_windows=self.config.feature_rolling_windows,
            )
            sector_features = build_sector_daily_features(
                sector_df,
                macro_df,
                feature_version=self.config.feature_version,
                rolling_windows=self.config.feature_rolling_windows,
            )
            if normalized_ticker_symbols and not ticker_features.empty:
                ticker_features = ticker_features[
                    ticker_features["symbol"].astype(str).str.upper().isin(normalized_ticker_symbols)
                ].copy()
            ticker_features = ticker_features[ticker_features["trade_date"].isin(target_date_set)].copy()
            sector_features = sector_features[sector_features["trade_date"].isin(target_date_set)].copy()
            ticker_rows_upserted += self.repository.upsert_ticker_daily_features(
                cast(list[dict[str, Any]], ticker_features.to_dict(orient="records"))
            )
            sector_rows_upserted += self.repository.upsert_sector_daily_features(
                cast(list[dict[str, Any]], sector_features.to_dict(orient="records"))
            )

        return EventSentimentHistoryBackfillResult(
            start_date=resolved_start,
            end_date=resolved_end,
            trade_dates_requested=len(trade_dates),
            trade_dates_processed=len(trade_dates),
            batches_processed=len(date_batches),
            ticker_rows_upserted=ticker_rows_upserted,
            sector_rows_upserted=sector_rows_upserted,
        )


def _build_run_id(prefix: str) -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _emit_run_summary(summary: dict[str, object]) -> None:
    print(f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}", flush=True)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconstruit les features historiques event_sentiment sur une longue période.")
    parser.add_argument("--start-date", type=str, default=None, help="Date de début ISO (YYYY-MM-DD).")
    parser.add_argument("--end-date", type=str, default=None, help="Date de fin ISO (YYYY-MM-DD).")
    parser.add_argument("--years", type=int, default=None, help="Lookback par défaut si start-date absent. Défaut config bootstrap_default_years.")
    parser.add_argument("--batch-days", type=int, default=None, help="Nombre de trade_dates par batch de reconstruction.")
    parser.add_argument(
        "--ingestion-source",
        type=str,
        choices=["alpaca", "finnhub", "eodhd"],
        default=None,
        help="Filtre optionnel sur `news_raw.ingestion_source` pour rester aligné avec le provider du run.",
    )
    parser.add_argument("--ticker-symbols", type=str, default=None, help="Liste CSV de symboles à conserver pour les features ticker.")
    parser.add_argument(
        "--ticker-symbol-source",
        type=str,
        choices=("stock_scores", "stock_scores_history", "stock_scores_all", "candidates", "stock_bars_daily"),
        default=None,
        help="Source optionnelle des symboles ticker quand --ticker-symbols est absent.",
    )
    parser.add_argument(
        "--ticker-max-symbols",
        type=int,
        default=None,
        help="Garde-fou sécurité : refuse le run si l'univers ticker résolu dépasse cette limite.",
    )
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    configure_root_logging(
        level=getattr(logging, args.log_level),
        log_path="./log/event_sentiment_history_backfill.log",
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    start_date = date.fromisoformat(args.start_date) if args.start_date else None
    end_date = date.fromisoformat(args.end_date) if args.end_date else None
    service = EventSentimentHistoryBackfillService()
    ticker_symbols: list[str] | None = None
    effective_ticker_symbol_source: str | None = None
    if args.ticker_symbols or args.ticker_symbol_source:
        ticker_symbols, effective_ticker_symbol_source = resolve_symbols_from_inputs(
            symbols_csv=args.ticker_symbols,
            symbol_source=str(args.ticker_symbol_source or "stock_scores_all"),
            repository=service.repository,
            logger=LOGGER,
        )
        resolved_ticker_symbols = ticker_symbols or []
        if (
            args.ticker_max_symbols is not None
            and args.ticker_max_symbols > 0
            and len(resolved_ticker_symbols) > int(args.ticker_max_symbols)
        ):
            raise SystemExit(
                "Le nombre de symboles ticker résolus ({0}) dépasse --ticker-max-symbols={1}. "
                "Réduisez l'univers (--ticker-symbol-source / --ticker-symbols) ou augmentez explicitement la limite.".format(
                    len(resolved_ticker_symbols),
                    int(args.ticker_max_symbols),
                )
            )
    started_at = _utc_now_naive()
    result = service.backfill(
        start_date=start_date,
        end_date=end_date,
        years=args.years,
        batch_days=args.batch_days,
        ingestion_source=str(args.ingestion_source or "").strip().lower() or None,
        ticker_symbols=ticker_symbols,
    )
    finished_at = _utc_now_naive()
    _emit_run_summary(
        {
            "run_id": _build_run_id("event-sentiment-history-backfill"),
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
            "ingestion_source": str(args.ingestion_source or "").strip().lower() or None,
            "ticker_symbol_source": effective_ticker_symbol_source,
            "ticker_symbol_count": len(ticker_symbols or []),
            **asdict(result),
        }
    )
    LOGGER.info("Backfill historique event_sentiment terminé | result=%s", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

