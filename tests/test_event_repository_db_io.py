from datetime import date

import pandas as pd

from event_sentiment.db_io import EventSentimentRepository


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[object] = []

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


def test_upsert_normalizes_pandas_nat_to_none(monkeypatch) -> None:
    repository = EventSentimentRepository.__new__(EventSentimentRepository)
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
    inserted_record = statement[1][0]
    assert inserted_record["latest_event_timestamp_ny"] is None


def test_upsert_macro_event_audit_uses_macro_event_type_in_unique_key(monkeypatch) -> None:
    repository = EventSentimentRepository.__new__(EventSentimentRepository)
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
    repository = EventSentimentRepository.__new__(EventSentimentRepository)
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
    inserted_record = statement[1][0]
    assert inserted_record == {
        "symbol": "AAPL",
        "trade_date": date(2026, 4, 16),
        "news_count_1d": 3,
    }


def test_count_pending_contextual_pairs_uses_min_relevance_filter() -> None:
    repository = EventSentimentRepository.__new__(EventSentimentRepository)
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
    assert params == {"min_relevance": 0.35}


