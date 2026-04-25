import argparse
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

import dateutil.parser

from common.utils import configure_root_logging
from event_sentiment.config import EventSentimentConfig
from event_sentiment.db_io import EventSentimentRepository
from event_sentiment.pipeline import EventSentimentPipeline

RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"


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
    stats: dict[str, object],
    started_at: datetime,
    finished_at: datetime,
) -> dict[str, object]:
    ingestion = stats.get("ingestion") if isinstance(stats.get("ingestion"), dict) else {}
    return {
        "run_id": _build_run_id("event-sentiment"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "resolved_symbols": int(stats.get("resolved_symbols") or 0),
        "window_start_utc": stats.get("start_utc"),
        "window_end_utc": stats.get("end_utc"),
        "fetched_articles": int(ingestion.get("fetched") or 0),
        "deduped_articles": int(ingestion.get("deduped") or 0),
        "landed_articles": int(ingestion.get("landed") or 0),
        "ticker_maps": int(ingestion.get("ticker_maps") or 0),
        "sentiment_inferred": int(stats.get("sentiment_inferred") or 0),
        "macro_rows": int(stats.get("macro_rows") or 0),
        "ticker_day_rows": int(stats.get("ticker_day_rows") or 0),
        "sector_day_rows": int(stats.get("sector_day_rows") or 0),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline Event Sentiment basée sur FinBERT")
    parser.add_argument("--start-utc", type=str, default=None, help="Fenêtre UTC de début, ex: 2026-01-01T00:00:00Z")
    parser.add_argument("--end-utc", type=str, default=None, help="Fenêtre UTC de fin, ex: 2026-01-31T23:59:59Z")
    parser.add_argument("--symbols", type=str, default=None, help="Liste optionnelle de symboles, séparés par des virgules")
    return parser


def main() -> None:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/event_sentiment.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    args = build_arg_parser().parse_args()

    start_utc = dateutil.parser.isoparse(args.start_utc) if args.start_utc else None
    end_utc = dateutil.parser.isoparse(args.end_utc) if args.end_utc else None
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",")] if args.symbols else None

    repository = EventSentimentRepository()
    config = EventSentimentConfig()
    pipeline = EventSentimentPipeline(repository=repository, config=config)
    started_at = _utc_now_naive()
    stats = pipeline.run(start_utc=start_utc, end_utc=end_utc, symbols=symbols)
    finished_at = _utc_now_naive()
    _emit_run_summary(
        _build_cli_run_summary(
            stats=stats,
            started_at=started_at,
            finished_at=finished_at,
        )
    )
