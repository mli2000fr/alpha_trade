from types import SimpleNamespace

import pandas as pd

from screener import db_io


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


class _FakeInsert:
    def __init__(self) -> None:
        self.records = None
        self.inserted = SimpleNamespace(
            liquidity_val="liquidity_val",
            relative_strength_index="relative_strength_index",
            historical_range_score="historical_range_score",
            total_score="total_score",
            last_updated_score="last_updated_score",
            is_candidate="is_candidate",
            sector="sector",
            last_updated_scan="last_updated_scan",
        )

    def values(self, records):
        self.records = records
        return self

    def on_duplicate_key_update(self, **kwargs):
        return ("upsert", self.records, kwargs)


def test_upsert_scores_snapshot_deletes_all_when_snapshot_is_empty() -> None:
    engine = _FakeEngine()

    db_io.upsert_scores_snapshot(engine, pd.DataFrame(), chunksize=2)

    assert len(engine.connection.executed) == 1
    statement, params = engine.connection.executed[0]
    assert "DELETE FROM stock_scores" in str(statement)
    assert params is None


def test_upsert_scores_snapshot_bulk_upserts_then_purges_missing(monkeypatch) -> None:
    engine = _FakeEngine()
    purge_calls: list[list[str]] = []

    monkeypatch.setattr(db_io, "_get_scores_table", lambda current_engine: object())
    monkeypatch.setattr(db_io, "mysql_insert", lambda table: _FakeInsert())
    monkeypatch.setattr(db_io, "_purge_missing_scores", lambda current_engine, symbols: purge_calls.append(symbols))

    scores_df = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "liquidity_val": 1.0,
                "relative_strength_index": 2.0,
                "historical_range_score": 3.0,
                "total_score": 4.0,
                "last_updated_score": "2026-01-01 00:00:00",
                "is_candidate": 1,
                "sector": "Tech",
                "last_updated_scan": "2026-01-01 00:05:00",
            },
            {
                "symbol": "BBB",
                "liquidity_val": 1.1,
                "relative_strength_index": 2.1,
                "historical_range_score": 3.1,
                "total_score": 4.1,
                "last_updated_score": "2026-01-01 00:00:00",
                "is_candidate": 0,
                "sector": None,
                "last_updated_scan": "2026-01-01 00:05:00",
            },
            {
                "symbol": "CCC",
                "liquidity_val": 1.2,
                "relative_strength_index": 2.2,
                "historical_range_score": 3.2,
                "total_score": 4.2,
                "last_updated_score": "2026-01-01 00:00:00",
                "is_candidate": 0,
                "sector": "Finance",
                "last_updated_scan": "2026-01-01 00:05:00",
            },
        ]
    )

    db_io.upsert_scores_snapshot(engine, scores_df, chunksize=2)

    assert len(engine.connection.executed) == 2
    assert purge_calls == [["AAA", "BBB", "CCC"]]

    first_statement, _ = engine.connection.executed[0]
    assert first_statement[0] == "upsert"
    assert first_statement[1][0]["last_updated_score"].isoformat(sep=" ") == "2026-01-01 00:00:00"
    assert first_statement[1][0]["is_candidate"] == 1
    assert first_statement[1][0]["sector"] == "Tech"
    assert first_statement[2]["last_updated_score"] == "last_updated_score"
    assert first_statement[2]["is_candidate"] == "is_candidate"
    assert first_statement[2]["sector"] == "sector"
    assert first_statement[2]["last_updated_scan"] == "last_updated_scan"


def test_upsert_scores_snapshot_accepts_legacy_last_updated_and_top_swing(monkeypatch) -> None:
    engine = _FakeEngine()
    purge_calls: list[list[str]] = []

    monkeypatch.setattr(db_io, "_get_scores_table", lambda current_engine: object())
    monkeypatch.setattr(db_io, "mysql_insert", lambda table: _FakeInsert())
    monkeypatch.setattr(db_io, "_purge_missing_scores", lambda current_engine, symbols: purge_calls.append(symbols))

    scores_df = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "liquidity_val": 1.0,
                "relative_strength_index": 2.0,
                "historical_range_score": 3.0,
                "total_score": 4.0,
                "last_updated": "2026-01-01 00:00:00",
                "top_swing": 1,
            }
        ]
    )

    db_io.upsert_scores_snapshot(engine, scores_df, chunksize=1000)

    assert purge_calls == [["AAA"]]
    statement, _ = engine.connection.executed[0]
    record = statement[1][0]
    assert record["last_updated_score"].isoformat(sep=" ") == "2026-01-01 00:00:00"
    assert record["is_candidate"] == 1
    assert record["sector"] is None
    assert record["last_updated_scan"].isoformat(sep=" ") == "2026-01-01 00:00:00"

