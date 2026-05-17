"""Tests pour ``event_sentiment.relevance_backfill`` (script CLI batch).

Repository et FinBERT sont mockés ; on ne touche pas la DB.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from event_sentiment.config import EventSentimentConfig
from event_sentiment.relevance_backfill import RelevanceBackfillService


class _FakeRepo:
    def __init__(self, batches: list[list[dict[str, Any]]]) -> None:
        self._batches = batches
        self.upsert_calls: list[list[dict[str, Any]]] = []
        self.deleted = 0
        self.relevance_iter_kwargs: dict[str, Any] | None = None
        self.delete_kwargs: dict[str, Any] | None = None
        self.contextual_pending: list[dict[str, Any]] = []
        self.contextual_upsert_calls: list[list[dict[str, Any]]] = []
        self.contextual_load_kwargs: dict[str, Any] | None = None

    def iter_ticker_map_for_relevance_backfill(self, **_kwargs):
        self.relevance_iter_kwargs = dict(_kwargs)
        for batch in self._batches:
            yield batch

    def upsert_news_ticker_map(self, records: list[dict[str, Any]]) -> int:
        self.upsert_calls.append(records)
        return len(records)

    def delete_ticker_map_below_score(self, **kwargs) -> int:
        self.delete_kwargs = dict(kwargs)
        self.deleted = 1
        return 1

    def load_pending_contextual_pairs(self, **_kwargs) -> list[dict[str, Any]]:
        self.contextual_load_kwargs = dict(_kwargs)
        return self.contextual_pending

    def upsert_news_ticker_sentiment(self, records: list[dict[str, Any]]) -> int:
        self.contextual_upsert_calls.append(records)
        return len(records)


def _make_row(article_id: str, symbol: str) -> dict[str, Any]:
    return {
        "article_id": article_id,
        "symbol": symbol,
        "is_primary_ticker": 1,
        "headline": f"{symbol} earnings beat",
        "summary": "Strong revenue growth",
        "content": None,
        "company_name": "Example Corp.",
        "ticker_count": 1,
    }


def test_backfill_relevance_dry_run_does_not_write() -> None:
    repo = _FakeRepo(batches=[[_make_row("a1", "AAPL"), _make_row("a2", "MSFT")]])
    service = RelevanceBackfillService(repository=repo, config=EventSentimentConfig())

    stats = service.backfill_relevance(batch_size=10, dry_run=True)
    assert stats["relevance_scanned"] == 2
    assert stats["relevance_rescored"] == 2
    assert repo.upsert_calls == []  # dry-run : pas d'upsert


def test_backfill_relevance_writes_when_not_dry_run() -> None:
    repo = _FakeRepo(batches=[[_make_row("a1", "AAPL")]])
    service = RelevanceBackfillService(repository=repo, config=EventSentimentConfig())

    stats = service.backfill_relevance(batch_size=10, dry_run=False)
    assert stats["relevance_rescored"] == 1
    assert len(repo.upsert_calls) == 1
    payload = repo.upsert_calls[0][0]
    assert payload["article_id"] == "a1"
    assert payload["symbol"] == "AAPL"
    assert "relevance_score" in payload
    assert isinstance(payload["relevance_components"], dict)
    assert 0.0 <= float(payload["relevance_score"]) <= 1.0


def test_backfill_relevance_forwards_ingestion_source_to_repository() -> None:
    repo = _FakeRepo(batches=[[_make_row("a1", "AAPL")]])
    service = RelevanceBackfillService(repository=repo, config=EventSentimentConfig())

    service.backfill_relevance(
        batch_size=10,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        symbols=["AAPL"],
        ingestion_source="eodhd",
        dry_run=True,
    )

    assert repo.relevance_iter_kwargs == {
        "batch_size": 10,
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 1, 31),
        "symbols": ["AAPL"],
        "ingestion_source": "eodhd",
        "rescore_all": False,
    }


def test_purge_below_dry_run_returns_zero() -> None:
    repo = _FakeRepo(batches=[])
    service = RelevanceBackfillService(repository=repo, config=EventSentimentConfig())
    stats = service.purge_below(threshold=0.2, dry_run=True)
    assert stats["relevance_purged"] == 0
    assert repo.deleted == 0


def test_purge_below_calls_repo_delete() -> None:
    repo = _FakeRepo(batches=[])
    service = RelevanceBackfillService(repository=repo, config=EventSentimentConfig())
    stats = service.purge_below(threshold=0.2, ingestion_source="alpaca", dry_run=False)
    assert stats["relevance_purged"] == 1
    assert repo.deleted == 1
    assert repo.delete_kwargs == {
        "threshold": 0.2,
        "start_date": None,
        "end_date": None,
        "symbols": None,
        "ingestion_source": "alpaca",
    }


def test_backfill_contextual_dry_run_skips_finbert() -> None:
    repo = _FakeRepo(batches=[])
    repo.contextual_pending = [
        {
            "article_id": "a1",
            "symbol": "AAPL",
            "headline": "Apple beats",
            "summary": None,
            "content": None,
            "source": "Reuters",
            "published_at_utc": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "event_timestamp_utc": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "event_timestamp_ny": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "effective_trade_date": date(2026, 1, 2),
            "market_session_tag": "regular",
            "is_major_event": 0,
            "company_name": "Apple Inc.",
        }
    ]
    service = RelevanceBackfillService(repository=repo, config=EventSentimentConfig())
    stats = service.backfill_contextual(batch_size=5, dry_run=True)
    assert stats["contextual_pairs_loaded"] == 1
    assert stats["contextual_scored"] == 0
    assert repo.contextual_upsert_calls == []


def test_backfill_contextual_forwards_scope_filters_to_repository() -> None:
    repo = _FakeRepo(batches=[])
    service = RelevanceBackfillService(repository=repo, config=EventSentimentConfig())

    service.backfill_contextual(
        batch_size=5,
        min_relevance=0.3,
        max_pairs=25,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        symbols=["AAPL", "MSFT"],
        ingestion_source="eodhd",
        dry_run=True,
    )

    assert repo.contextual_load_kwargs == {
        "limit": 25,
        "min_relevance": 0.3,
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 1, 31),
        "symbols": ["AAPL", "MSFT"],
        "ingestion_source": "eodhd",
    }


