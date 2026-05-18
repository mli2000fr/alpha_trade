from __future__ import annotations

import logging
from datetime import date
from typing import Any, cast

import pandas as pd

from event_sentiment.config import EventSentimentConfig
from event_sentiment.history_backfill import EventSentimentHistoryBackfillService


class _FakeRepository:
    def __init__(self) -> None:
        self.scored_dates = [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)]
        self.feature_frame_calls: list[dict[str, object]] = []
        self.ticker_upserts: list[list[dict[str, object]]] = []
        self.sector_upserts: list[list[dict[str, object]]] = []

    def list_scored_trade_dates(self, start_date=None, end_date=None, ingestion_source=None):
        dates = list(self.scored_dates)
        if start_date is not None:
            dates = [value for value in dates if value >= start_date]
        if end_date is not None:
            dates = [value for value in dates if value <= end_date]
        return dates

    def load_feature_frames(self, start_date=None, end_date=None, trade_dates=None, ingestion_source=None, ticker_symbols=None):
        self.feature_frame_calls.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "trade_dates": trade_dates,
                "ingestion_source": ingestion_source,
                "ticker_symbols": ticker_symbols,
            }
        )
        ticker_df = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "effective_trade_date": date(2026, 1, 2),
                    "event_timestamp_ny": "2026-01-02 10:00:00",
                    "market_session_tag": "regular",
                    "source": "Reuters",
                    "is_major_event": 0,
                    "symbol": "AAPL",
                    "sector": "Technology",
                    "positive_score": 0.8,
                    "neutral_score": 0.1,
                    "negative_score": 0.1,
                    "sentiment_confidence": 0.8,
                    "sentiment_net_score": 0.7,
                },
                {
                    "article_id": "a1",
                    "effective_trade_date": date(2026, 1, 2),
                    "event_timestamp_ny": "2026-01-02 10:30:00",
                    "market_session_tag": "regular",
                    "source": "Reuters",
                    "is_major_event": 0,
                    "symbol": "MSFT",
                    "sector": "Technology",
                    "positive_score": 0.7,
                    "neutral_score": 0.2,
                    "negative_score": 0.1,
                    "sentiment_confidence": 0.7,
                    "sentiment_net_score": 0.6,
                },
                {
                    "article_id": "a2",
                    "effective_trade_date": date(2026, 1, 5),
                    "event_timestamp_ny": "2026-01-05 10:00:00",
                    "market_session_tag": "regular",
                    "source": "Reuters",
                    "is_major_event": 1,
                    "symbol": "AAPL",
                    "sector": "Technology",
                    "positive_score": 0.9,
                    "neutral_score": 0.05,
                    "negative_score": 0.05,
                    "sentiment_confidence": 0.9,
                    "sentiment_net_score": 0.8,
                },
            ]
        )
        sector_df = ticker_df[[
            "article_id",
            "effective_trade_date",
            "event_timestamp_ny",
            "market_session_tag",
            "source",
            "is_major_event",
            "sector",
            "sentiment_confidence",
            "sentiment_net_score",
        ]].assign(sentiment_label="positive")
        macro_df = pd.DataFrame(
            [
                {
                    "article_id": "a2",
                    "trade_date": date(2026, 1, 5),
                    "sector": "Technology",
                    "macro_event_type": "monetary_policy",
                    "impact_direction": "positive",
                    "impact_score": 0.4,
                    "macro_event_intensity": 0.4,
                }
            ]
        )
        return ticker_df, sector_df, macro_df

    def upsert_ticker_daily_features(self, records):
        self.ticker_upserts.append(list(records))
        return len(records)

    def upsert_sector_daily_features(self, records):
        self.sector_upserts.append(list(records))
        return len(records)


def _build_service(repository: _FakeRepository, config: EventSentimentConfig) -> EventSentimentHistoryBackfillService:
    return EventSentimentHistoryBackfillService(repository=cast(Any, repository), config=config)


def test_history_backfill_resolve_bounds_uses_available_scored_dates() -> None:
    repository = _FakeRepository()
    service = _build_service(repository, EventSentimentConfig(bootstrap_default_years=10))

    start_date, end_date = service.resolve_bounds(end_date=date(2026, 1, 6), years=1)

    assert start_date == date(2026, 1, 2)
    assert end_date == date(2026, 1, 6)


def test_history_backfill_rebuilds_by_batches_and_filters_target_dates() -> None:
    repository = _FakeRepository()
    config = EventSentimentConfig(feature_history_buffer_days=20, bootstrap_batch_days=2)
    service = _build_service(repository, config)

    result = service.backfill(start_date=date(2026, 1, 2), end_date=date(2026, 1, 6), batch_days=2)

    assert result.trade_dates_processed == 3
    assert result.batches_processed == 2
    assert repository.feature_frame_calls[0]["start_date"] == date(2025, 12, 13)
    assert repository.feature_frame_calls[0]["end_date"] == date(2026, 1, 5)
    first_batch_dates = {row["trade_date"] for row in repository.ticker_upserts[0]}
    second_batch_dates = {row["trade_date"] for row in repository.ticker_upserts[1]}
    assert first_batch_dates == {date(2026, 1, 2), date(2026, 1, 5)}


def test_history_backfill_can_filter_ticker_scope_and_provider() -> None:
    repository = _FakeRepository()
    config = EventSentimentConfig(feature_history_buffer_days=20, bootstrap_batch_days=2)
    service = _build_service(repository, config)

    result = service.backfill(
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 6),
        batch_days=2,
        ingestion_source="eodhd",
        ticker_symbols=["AAPL"],
    )

    assert result.trade_dates_processed == 3
    assert repository.feature_frame_calls[0]["ingestion_source"] == "eodhd"
    assert repository.feature_frame_calls[0]["ticker_symbols"] == ["AAPL"]
    assert all(row["symbol"] == "AAPL" for batch in repository.ticker_upserts for row in batch)


def test_history_backfill_emits_phase_logs(caplog) -> None:
    repository = _FakeRepository()
    config = EventSentimentConfig(feature_history_buffer_days=20, bootstrap_batch_days=2)
    service = _build_service(repository, config)

    with caplog.at_level(logging.INFO):
        service.backfill(start_date=date(2026, 1, 2), end_date=date(2026, 1, 6), batch_days=2)

    messages = [record.getMessage() for record in caplog.records]
    assert any("Event sentiment history backfill started" in message for message in messages)
    assert any("history_backfill.resolve_bounds.scored_dates started" in message for message in messages)
    assert any("history_backfill.list_trade_dates completed" in message for message in messages)
    assert any("history_backfill.load_feature_frames result" in message for message in messages)
    assert any("history_backfill.aggregate_features completed" in message for message in messages)
    assert any("history_backfill.upsert_features completed" in message for message in messages)
    assert any("history_backfill.batch_completed" in message for message in messages)


