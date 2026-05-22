from datetime import date
from typing import Any, cast

import pandas as pd
import pytest
from sqlalchemy.exc import OperationalError

from event_sentiment.db_io import EventSentimentRepository


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[object, Any]] = []

    def execute(self, statement, params=None):
        self.executed.append((statement, params))


class _FakeBeginContext:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    def __enter__(self) -> _FakeConnection:
        return self._connection

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeEngine:
    def __init__(self) -> None:
        self.connection = _FakeConnection()

    def begin(self) -> _FakeBeginContext:
        return _FakeBeginContext(self.connection)

    def connect(self) -> _FakeBeginContext:
        return _FakeBeginContext(self.connection)


class _FakeInserted:
    def __getitem__(self, item):
        return item


class _FakeInsert:
    def __init__(self) -> None:
        self.records = None
        self.inserted = _FakeInserted()

    def values(self, records):
        self.records = records
        return self

    def on_duplicate_key_update(self, **kwargs):
        return ("upsert", self.records, kwargs)


class _FakeColumn:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeTable:
    def __init__(self) -> None:
        self.c = {
            "sector": _FakeColumn("sector"),
            "trade_date": _FakeColumn("trade_date"),
            "latest_event_timestamp_ny": _FakeColumn("latest_event_timestamp_ny"),
            "updated_at": _FakeColumn("updated_at"),
        }


class _FakeScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _FakeMappingsResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self):
        return self

    def all(self) -> list[dict[str, object]]:
        return self._rows


class _FakeMySQLError(Exception):
    def __init__(self, errno: int, message: str) -> None:
        super().__init__(errno, message)
        self.args = (errno, message)


def _make_relevance_row(index: int) -> dict[str, object]:
    article_id = f"a{index:04d}"
    symbol = f"S{index:04d}"
    return {
        "article_id": article_id,
        "symbol": symbol,
        "is_primary_ticker": 1,
        "headline": f"headline-{index}",
        "summary": None,
        "content": None,
        "company_name": None,
        "ticker_count": 1,
    }


def _make_repository() -> EventSentimentRepository:
    return cast(EventSentimentRepository, object.__new__(EventSentimentRepository))


def test_upsert_normalizes_pandas_nat_to_none(monkeypatch) -> None:
    repository = _make_repository()
    repository.engine = _FakeEngine()
    repository.metadata = None
    repository._tables = {}

    monkeypatch.setattr(repository, "_table", lambda table_name: _FakeTable())
    monkeypatch.setattr("event_sentiment.db_io.mysql_insert", lambda table: _FakeInsert())

    records = [{
        "sector": "Consumer Cyclical",
        "trade_date": date(2026, 4, 16),
        "latest_event_timestamp_ny": pd.NaT,
    }]

    rowcount = EventSentimentRepository._upsert(
        repository,
        "sector_daily_sentiment_features",
        records,
        key_columns={"sector", "trade_date"},
    )

    assert rowcount == 1
    statement, _ = repository.engine.connection.executed[0]
    statement = cast(tuple[object, list[dict[str, object]], object], statement)
    inserted_record = statement[1][0]
    assert inserted_record["latest_event_timestamp_ny"] is None


def test_upsert_macro_event_audit_uses_macro_event_type_in_unique_key(monkeypatch) -> None:
    repository = _make_repository()
    captured: dict[str, object] = {}

    def _fake_upsert(table_name, records, key_columns):
        captured["table_name"] = table_name
        captured["records"] = records
        captured["key_columns"] = key_columns
        return len(records)

    monkeypatch.setattr(repository, "_upsert", _fake_upsert)

    rowcount = EventSentimentRepository.upsert_macro_event_audit(
        repository,
        [
            {
                "article_id": "alpaca:1",
                "trade_date": date(2026, 4, 16),
                "sector": "Technology",
                "macro_event_type": "monetary_policy",
                "impact_direction": "positive",
                "impact_score": 0.4,
                "macro_event_intensity": 0.4,
                "rule_version": "macro_rules_v1",
                "rule_hits": {"keyword_hits": ["fed"]},
                "explanation_text": "synthetic test event",
            }
        ],
    )

    assert rowcount == 1
    assert captured["table_name"] == "macro_event_audit"
    assert captured["key_columns"] == {"article_id", "sector", "macro_event_type"}


def test_upsert_drops_unknown_columns_not_present_in_table(monkeypatch) -> None:
    repository = _make_repository()
    repository.engine = _FakeEngine()
    repository.metadata = None
    repository._tables = {}

    class _TickerTable:
        def __init__(self) -> None:
            self.c = {
                "symbol": _FakeColumn("symbol"),
                "trade_date": _FakeColumn("trade_date"),
                "news_count_1d": _FakeColumn("news_count_1d"),
                "updated_at": _FakeColumn("updated_at"),
            }

    monkeypatch.setattr(repository, "_table", lambda table_name: _TickerTable())
    monkeypatch.setattr("event_sentiment.db_io.mysql_insert", lambda table: _FakeInsert())

    rowcount = EventSentimentRepository._upsert(
        repository,
        "ticker_daily_sentiment_features",
        [{
            "symbol": "AAPL",
            "trade_date": date(2026, 4, 16),
            "news_count_1d": 3,
            "relevance_weight_sum_1d": 1.5,
        }],
        key_columns={"symbol", "trade_date"},
    )

    assert rowcount == 1
    statement, _ = repository.engine.connection.executed[0]
    statement = cast(tuple[object, list[dict[str, object]], object], statement)
    inserted_record = statement[1][0]
    assert inserted_record == {
        "symbol": "AAPL",
        "trade_date": date(2026, 4, 16),
        "news_count_1d": 3,
    }


def test_upsert_splits_large_payload_into_multiple_batches(monkeypatch) -> None:
    repository = _make_repository()
    repository.engine = _FakeEngine()
    repository.metadata = None
    repository._tables = {}

    class _TickerTable:
        def __init__(self) -> None:
            self.c = {
                "symbol": _FakeColumn("symbol"),
                "trade_date": _FakeColumn("trade_date"),
                "news_count_1d": _FakeColumn("news_count_1d"),
                "updated_at": _FakeColumn("updated_at"),
            }

    monkeypatch.setattr(repository, "_table", lambda table_name: _TickerTable())
    monkeypatch.setattr("event_sentiment.db_io.mysql_insert", lambda table: _FakeInsert())
    monkeypatch.setattr(repository, "_upsert_batch_size", lambda: 2)

    rowcount = EventSentimentRepository._upsert(
        repository,
        "ticker_daily_sentiment_features",
        [
            {"symbol": "AAPL", "trade_date": date(2026, 4, 16), "news_count_1d": 3},
            {"symbol": "MSFT", "trade_date": date(2026, 4, 16), "news_count_1d": 4},
            {"symbol": "NVDA", "trade_date": date(2026, 4, 16), "news_count_1d": 5},
        ],
        key_columns={"symbol", "trade_date"},
    )

    assert rowcount == 3
    assert len(repository.engine.connection.executed) == 2
    first_statement, _ = repository.engine.connection.executed[0]
    second_statement, _ = repository.engine.connection.executed[1]
    first_statement = cast(tuple[object, list[dict[str, object]], object], first_statement)
    second_statement = cast(tuple[object, list[dict[str, object]], object], second_statement)
    assert len(first_statement[1]) == 2
    assert len(second_statement[1]) == 1


def test_count_pending_contextual_pairs_uses_min_relevance_filter() -> None:
    repository = _make_repository()
    fake_engine = _FakeEngine()
    repository.engine = fake_engine
    repository.metadata = None
    repository._tables = {}

    def _fake_execute(statement, params=None):
        fake_engine.connection.executed.append((statement, params))
        return _FakeScalarResult(42)

    fake_engine.connection.execute = _fake_execute  # type: ignore[method-assign]

    count = EventSentimentRepository.count_pending_contextual_pairs(
        repository,
        min_relevance=0.35,
    )

    assert count == 42
    _statement, params = fake_engine.connection.executed[0]
    sql = str(_statement)
    assert params == {"min_relevance": 0.35}
    assert "ntm.relevance_score IS NOT NULL" in sql
    assert "ntm.relevance_score >= :min_relevance" in sql
    assert "COALESCE(ntm.relevance_score, 1.0) >= :min_relevance" not in sql


def test_load_pending_contextual_pairs_uses_same_strict_min_relevance_filter() -> None:
    repository = _make_repository()
    fake_engine = _FakeEngine()
    repository.engine = fake_engine
    repository.metadata = None
    repository._tables = {}

    def _fake_execute(statement, params=None):
        fake_engine.connection.executed.append((statement, params))
        return _FakeMappingsResult([])

    fake_engine.connection.execute = _fake_execute  # type: ignore[method-assign]

    rows = EventSentimentRepository.load_pending_contextual_pairs(
        repository,
        limit=500,
        min_relevance=0.3,
        start_date=date(2026, 5, 10),
        end_date=date(2026, 5, 17),
        symbols=["AAPL", "MSFT"],
        ingestion_source="eodhd",
    )

    assert rows == []
    _statement, params = fake_engine.connection.executed[0]
    sql = str(_statement)
    assert params == {
        "limit_rows": 500,
        "min_relevance": 0.3,
        "start_date": date(2026, 5, 10),
        "end_date": date(2026, 5, 17),
        "ingestion_source": "eodhd",
        "symbols": ["AAPL", "MSFT"],
    }
    assert "ntm.relevance_score IS NOT NULL" in sql
    assert "ntm.relevance_score >= :min_relevance" in sql


def test_iter_ticker_map_for_relevance_backfill_uses_stable_keyset_pagination() -> None:
    repository = _make_repository()
    fake_engine = _FakeEngine()
    repository.engine = fake_engine
    repository.metadata = None
    repository._tables = {}

    rows = [_make_relevance_row(index) for index in range(1, 1201)]

    def _fake_execute(statement, params=None):
        fake_engine.connection.executed.append((statement, params))
        params = params or {}
        last_article_id = params.get("last_article_id")
        last_symbol = params.get("last_symbol")
        limit_rows = int(params.get("limit_rows") or 0)
        filtered_rows = rows
        if last_article_id is not None and last_symbol is not None:
            filtered_rows = [
                row
                for row in rows
                if (str(row["article_id"]) > str(last_article_id))
                or (
                    str(row["article_id"]) == str(last_article_id)
                    and str(row["symbol"]) > str(last_symbol)
                )
            ]
        return _FakeMappingsResult(filtered_rows[:limit_rows])

    fake_engine.connection.execute = _fake_execute  # type: ignore[method-assign]

    batches = list(
        EventSentimentRepository.iter_ticker_map_for_relevance_backfill(
            repository,
            batch_size=500,
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 31),
            ingestion_source="eodhd",
        )
    )

    assert [len(batch) for batch in batches] == [500, 500, 200]
    assert sum(len(batch) for batch in batches) == 1200
    first_params = cast(dict[str, object], fake_engine.connection.executed[0][1])
    second_params = cast(dict[str, object], fake_engine.connection.executed[1][1])
    third_params = cast(dict[str, object], fake_engine.connection.executed[2][1])
    assert first_params == {
        "start_date": date(2020, 1, 1),
        "end_date": date(2020, 1, 31),
        "ingestion_source": "eodhd",
        "limit_rows": 500,
    }
    assert second_params["last_article_id"] == "a0500"
    assert second_params["last_symbol"] == "S0500"
    assert third_params["last_article_id"] == "a1000"
    assert third_params["last_symbol"] == "S1000"
    assert all("offset_rows" not in params for _stmt, params in fake_engine.connection.executed)


def test_upsert_retries_deadlock_and_succeeds(monkeypatch) -> None:
    repository = _make_repository()
    repository.engine = _FakeEngine()
    repository.metadata = None
    repository._tables = {}

    class _TickerTable:
        def __init__(self) -> None:
            self.c = {
                "symbol": _FakeColumn("symbol"),
                "trade_date": _FakeColumn("trade_date"),
                "news_count_1d": _FakeColumn("news_count_1d"),
                "updated_at": _FakeColumn("updated_at"),
            }

    attempts = {"count": 0}

    def _fake_execute(statement, params=None):
        attempts["count"] += 1
        repository.engine.connection.executed.append((statement, params))
        if attempts["count"] == 1:
            raise OperationalError("statement", params, _FakeMySQLError(1213, "Deadlock found"))
        return None

    monkeypatch.setattr(repository, "_table", lambda table_name: _TickerTable())
    monkeypatch.setattr("event_sentiment.db_io.mysql_insert", lambda table: _FakeInsert())
    monkeypatch.setattr(repository, "_upsert_retry_attempts", lambda: 3)
    monkeypatch.setattr(repository, "_upsert_retry_backoff_seconds", lambda: 0.0)
    monkeypatch.setattr(repository.engine.connection, "execute", _fake_execute)

    rowcount = EventSentimentRepository._upsert(
        repository,
        "ticker_daily_sentiment_features",
        [{"symbol": "AAPL", "trade_date": date(2026, 4, 16), "news_count_1d": 3}],
        key_columns={"symbol", "trade_date"},
    )

    assert rowcount == 1
    assert attempts["count"] == 2


def test_upsert_raises_after_exhausting_deadlock_retries(monkeypatch) -> None:
    repository = _make_repository()
    repository.engine = _FakeEngine()
    repository.metadata = None
    repository._tables = {}

    class _TickerTable:
        def __init__(self) -> None:
            self.c = {
                "symbol": _FakeColumn("symbol"),
                "trade_date": _FakeColumn("trade_date"),
                "news_count_1d": _FakeColumn("news_count_1d"),
                "updated_at": _FakeColumn("updated_at"),
            }

    attempts = {"count": 0}

    def _fake_execute(statement, params=None):
        attempts["count"] += 1
        repository.engine.connection.executed.append((statement, params))
        raise OperationalError("statement", params, _FakeMySQLError(1213, "Deadlock found"))

    monkeypatch.setattr(repository, "_table", lambda table_name: _TickerTable())
    monkeypatch.setattr("event_sentiment.db_io.mysql_insert", lambda table: _FakeInsert())
    monkeypatch.setattr(repository, "_upsert_retry_attempts", lambda: 2)
    monkeypatch.setattr(repository, "_upsert_retry_backoff_seconds", lambda: 0.0)
    monkeypatch.setattr(repository.engine.connection, "execute", _fake_execute)

    with pytest.raises(OperationalError):
        EventSentimentRepository._upsert(
            repository,
            "ticker_daily_sentiment_features",
            [{"symbol": "AAPL", "trade_date": date(2026, 4, 16), "news_count_1d": 3}],
            key_columns={"symbol", "trade_date"},
        )

    assert attempts["count"] == 2


def test_load_feature_frames_with_date_range_and_ticker_symbols_binds_expanding_param(monkeypatch) -> None:
    repository = _make_repository()
    repository.engine = object()
    repository.metadata = None
    repository._tables = {}

    calls: list[tuple[object, object, object]] = []

    def _fake_read_sql_query(statement, engine, params=None):
        calls.append((statement, engine, params))
        return pd.DataFrame()

    monkeypatch.setattr("event_sentiment.db_io.pd.read_sql_query", _fake_read_sql_query)

    ticker_df, sector_df, macro_df = EventSentimentRepository.load_feature_frames(
        repository,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 31),
        ingestion_source="eodhd",
        ticker_symbols=["aapl", "MSFT"],
    )

    assert ticker_df.empty
    assert sector_df.empty
    assert macro_df.empty
    assert len(calls) == 3
    ticker_statement, ticker_engine, ticker_params = calls[0]
    assert ticker_engine is repository.engine
    assert ticker_params == {
        "start_date": date(2020, 1, 1),
        "end_date": date(2020, 1, 31),
        "ingestion_source": "eodhd",
        "ticker_symbols": ["AAPL", "MSFT"],
    }
    assert "ntm.symbol IN" in str(ticker_statement)
    assert "ticker_symbols" in str(ticker_statement)


def test_load_feature_frames_with_trade_dates_and_ticker_symbols_binds_expanding_param(monkeypatch) -> None:
    repository = _make_repository()
    repository.engine = object()
    repository.metadata = None
    repository._tables = {}

    calls: list[tuple[object, object, object]] = []

    def _fake_read_sql_query(statement, engine, params=None):
        calls.append((statement, engine, params))
        return pd.DataFrame()

    monkeypatch.setattr("event_sentiment.db_io.pd.read_sql_query", _fake_read_sql_query)

    ticker_df, sector_df, macro_df = EventSentimentRepository.load_feature_frames(
        repository,
        trade_dates=[date(2020, 1, 2), date(2020, 1, 3)],
        ingestion_source="eodhd",
        ticker_symbols=["nvda"],
    )

    assert ticker_df.empty
    assert sector_df.empty
    assert macro_df.empty
    assert len(calls) == 3
    ticker_statement, ticker_engine, ticker_params = calls[0]
    assert ticker_engine is repository.engine
    assert ticker_params == {
        "trade_dates": [date(2020, 1, 2), date(2020, 1, 3)],
        "ingestion_source": "eodhd",
        "ticker_symbols": ["NVDA"],
    }
    assert "ntm.symbol IN" in str(ticker_statement)
    assert "ticker_symbols" in str(ticker_statement)


def test_touch_checkpoint_stage_upserts_normalized_symbols(monkeypatch) -> None:
    repository = _make_repository()

    captured: dict[str, object] = {}

    def _fake_upsert(table_name, records, key_columns):
        captured["table_name"] = table_name
        captured["records"] = records
        captured["key_columns"] = key_columns
        return len(records)

    monkeypatch.setattr(repository, "_upsert", _fake_upsert)

    rowcount = EventSentimentRepository.touch_checkpoint_stage(
        repository,
        "eodhd_news",
        ["aapl", "MSFT", "aapl"],
        stage="relevance_backfilled",
    )

    assert rowcount == 2
    assert captured["table_name"] == "news_ingestion_checkpoint"
    assert captured["key_columns"] == {"source_name", "symbol"}
    records = cast(list[dict[str, object]], captured["records"])
    assert [record["symbol"] for record in records] == ["AAPL", "MSFT"]
    assert all("relevance_backfill_at" in record for record in records)


def test_get_signal_aggregator_guard_status_detects_stale_stages(monkeypatch) -> None:
    repository = _make_repository()
    monkeypatch.setattr(
        repository,
        "get_checkpoints",
        lambda source_name, symbols: {
            "AAPL": {
                "news_ingested_at": date(2026, 5, 1),
                "relevance_backfill_at": None,
                "contextual_scoring_at": None,
                "features_aggregated_at": None,
            },
            "MSFT": {
                "news_ingested_at": date(2026, 5, 1),
                "relevance_backfill_at": date(2026, 5, 2),
                "contextual_scoring_at": date(2026, 5, 1),
                "features_aggregated_at": None,
            },
            "NVDA": {
                "news_ingested_at": date(2026, 5, 1),
                "relevance_backfill_at": date(2026, 5, 2),
                "contextual_scoring_at": date(2026, 5, 3),
                "features_aggregated_at": date(2026, 5, 2),
            },
        },
    )

    status = EventSentimentRepository.get_signal_aggregator_guard_status(
        repository,
        source_name="eodhd_news",
        symbols=["AAPL", "MSFT", "NVDA"],
    )

    assert status["ready"] is False
    assert status["symbols_with_news"] == 3
    assert status["stale_relevance_symbols"] == ["AAPL"]
    assert status["stale_contextual_symbols"] == ["MSFT"]
    assert status["stale_feature_symbols"] == ["NVDA"]


