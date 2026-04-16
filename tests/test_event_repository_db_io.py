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

