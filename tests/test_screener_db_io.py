from types import SimpleNamespace

import pandas as pd
import pytest

from screener import db_io


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[object] = []
        self.rows_queue: list[list[object]] = []

    def execute(self, statement, params=None):
        self.executed.append((statement, params))
        rows = self.rows_queue.pop(0) if self.rows_queue else []
        return SimpleNamespace(fetchall=lambda: rows)


class _FakeConnectContext:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    def __enter__(self) -> _FakeConnection:
        return self._connection

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


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

    def connect(self) -> _FakeConnectContext:
        return _FakeConnectContext(self.connection)


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
            anomaly_count="anomaly_count",
            missing_days_count="missing_days_count",
            sanitizer_status="sanitizer_status",
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
    monkeypatch.setattr(
        db_io,
        "_load_metadata_sectors",
        lambda current_engine, symbols: pd.DataFrame(
            [
                {"symbol": "AAA", "sector": "Technology"},
                {"symbol": "BBB", "sector": "Industrials"},
            ]
        ),
    )
    monkeypatch.setattr(
        db_io,
        "_load_latest_audit_metrics",
        lambda current_engine, symbols: pd.DataFrame(
            [
                {"symbol": "AAA", "anomaly_count": 1, "missing_days_count": 2, "sanitizer_status": "success"},
                {"symbol": "BBB", "anomaly_count": None, "missing_days_count": None, "sanitizer_status": "failed"},
            ]
        ),
    )
    monkeypatch.setattr(db_io, "_purge_missing_scores", lambda current_engine, symbols: purge_calls.append(symbols))
    monkeypatch.setattr(db_io, "archive_scores_snapshot", lambda engine, snapshot_date=None: 0)

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
    assert first_statement[1][0]["sector"] == "Technology"
    assert first_statement[1][0]["anomaly_count"] == 1
    assert first_statement[1][0]["missing_days_count"] == 2
    assert first_statement[1][0]["sanitizer_status"] == "success"
    assert first_statement[1][1]["sector"] == "Industrials"
    assert first_statement[1][1]["sanitizer_status"] == "failed"
    assert first_statement[2]["last_updated_score"] == "last_updated_score"
    assert first_statement[2]["is_candidate"] == "is_candidate"
    assert first_statement[2]["sector"] == "sector"
    assert first_statement[2]["anomaly_count"] == "anomaly_count"
    assert first_statement[2]["missing_days_count"] == "missing_days_count"
    assert first_statement[2]["sanitizer_status"] == "sanitizer_status"
    assert first_statement[2]["last_updated_scan"] == "last_updated_scan"


def test_upsert_scores_snapshot_accepts_legacy_last_updated_and_top_swing(monkeypatch) -> None:
    engine = _FakeEngine()
    purge_calls: list[list[str]] = []

    monkeypatch.setattr(db_io, "_get_scores_table", lambda current_engine: object())
    monkeypatch.setattr(db_io, "mysql_insert", lambda table: _FakeInsert())
    monkeypatch.setattr(
        db_io,
        "_load_metadata_sectors",
        lambda current_engine, symbols: pd.DataFrame([{"symbol": "AAA", "sector": "Healthcare"}]),
    )
    monkeypatch.setattr(db_io, "_load_latest_audit_metrics", lambda current_engine, symbols: pd.DataFrame())
    monkeypatch.setattr(db_io, "_purge_missing_scores", lambda current_engine, symbols: purge_calls.append(symbols))
    monkeypatch.setattr(db_io, "archive_scores_snapshot", lambda engine, snapshot_date=None: 0)

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
    assert record["sector"] == "Healthcare"
    assert record["sanitizer_status"] == "pending"
    assert record["last_updated_scan"].isoformat(sep=" ") == "2026-01-01 00:00:00"


def test_iter_symbol_chunks_reads_from_stock_bars_daily() -> None:
    engine = _FakeEngine()
    engine.connection.rows_queue = [[("AAA",), ("BBB",)], [("CCC",)], []]

    chunks = list(db_io.iter_symbol_chunks(engine, chunk_size=2))

    assert chunks == [["AAA", "BBB"], ["CCC"]]
    statement, params = engine.connection.executed[0]
    assert "FROM stock_bars_daily" in str(statement)
    assert "INNER JOIN stock_metadata" in str(statement)
    assert "timeframe" not in params
    assert params["last_symbol"] is None
    _, next_params = engine.connection.executed[1]
    assert next_params["last_symbol"] == "BBB"


def test_load_prices_for_chunk_reads_daily_table_with_adjusted_close(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        pd,
        "read_sql_query",
        lambda stmt, engine, params=None: captured.update({"stmt": stmt, "params": params}) or pd.DataFrame(),
    )

    config = SimpleNamespace(lookback_history_years=10)
    db_io.load_prices_for_chunk(object(), ["AAA"], config)

    assert "FROM stock_bars_daily" in str(captured["stmt"])
    assert "COALESCE(adj_close, `close`) AS close_price" in str(captured["stmt"])
    assert "timeframe" not in captured["params"]


def test_load_spy_return_6m_reads_daily_table(monkeypatch) -> None:
    captured: dict[str, object] = {}
    spy_df = pd.DataFrame(
        {
            "timestamp": ["2026-01-01", "2026-04-01"],
            "close_price": [100.0, 110.0],
        }
    )

    monkeypatch.setattr(
        pd,
        "read_sql_query",
        lambda stmt, engine, params=None: captured.update({"stmt": stmt, "params": params}) or spy_df,
    )

    config = SimpleNamespace(benchmark_symbol="SPY", lookback_relative_days=183)
    result = db_io.load_spy_return_6m(object(), config)

    assert result == pytest.approx(0.1)
    assert "FROM stock_bars_daily" in str(captured["stmt"])
    assert "COALESCE(adj_close, `close`) AS close_price" in str(captured["stmt"])
    assert captured["params"] == {"symbol": "SPY"}


def test_screener_config_from_dict_ignores_legacy_timeframe() -> None:
    from screener.models import ScreenerConfig

    config = ScreenerConfig.from_dict({"timeframe": "1D", "chunk_size": 123})

    assert config.chunk_size == 123


def test_enrich_scores_with_metadata_sector_keeps_existing_when_metadata_missing(monkeypatch) -> None:
    engine = object()
    monkeypatch.setattr(
        db_io,
        "_load_metadata_sectors",
        lambda current_engine, symbols: pd.DataFrame([{"symbol": "AAA", "sector": None}]),
    )

    scores_df = pd.DataFrame(
        [
            {"symbol": "AAA", "sector": "LegacySector"},
            {"symbol": "BBB", "sector": "ExistingSector"},
        ]
    )

    enriched = db_io._enrich_scores_with_metadata_sector(engine, scores_df)

    assert enriched.loc[0, "sector"] == "LegacySector"
    assert enriched.loc[1, "sector"] == "ExistingSector"



def test_enrich_scores_with_audit_merges_latest_quality_flags(monkeypatch) -> None:
    engine = object()
    monkeypatch.setattr(
        db_io,
        "_load_latest_audit_metrics",
        lambda current_engine, symbols: pd.DataFrame(
            [
                {"symbol": "AAA", "anomaly_count": 3, "missing_days_count": 1, "sanitizer_status": "success"},
            ]
        ),
    )

    scores_df = pd.DataFrame(
        [
            {"symbol": "AAA", "sector": "Tech"},
            {"symbol": "BBB", "sector": "Finance"},
        ]
    )

    enriched = db_io._enrich_scores_with_audit(engine, scores_df)

    assert enriched.loc[enriched["symbol"] == "AAA", "sanitizer_status"].iloc[0] == "success"
    assert enriched.loc[enriched["symbol"] == "AAA", "anomaly_count"].iloc[0] == 3
    assert pd.isna(enriched.loc[enriched["symbol"] == "BBB", "sanitizer_status"].iloc[0])


# ---------------------------------------------------------------------------
# archive_scores_snapshot
# ---------------------------------------------------------------------------

class _FakeResultProxy:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


def test_archive_scores_snapshot_executes_insert_select() -> None:
    """archive_scores_snapshot doit exécuter un INSERT … SELECT depuis stock_scores."""
    from datetime import date as _date

    engine = _FakeEngine()
    engine.connection.rows_queue = []  # pas de lecture attendue

    # Patch execute pour retourner un rowcount
    original_execute = engine.connection.execute

    def patched_execute(statement, params=None):
        original_execute(statement, params)
        return _FakeResultProxy(rowcount=5)

    engine.connection.execute = patched_execute

    count = db_io.archive_scores_snapshot(engine, snapshot_date=_date(2025, 6, 15))

    assert count == 5
    # Vérifie qu'on a bien exécuté une requête avec la bonne date
    assert len(engine.connection.executed) == 1
    _, params = engine.connection.executed[0]
    assert params == {"snapshot_date": _date(2025, 6, 15)}


def test_archive_scores_snapshot_defaults_to_today() -> None:
    """Sans snapshot_date, archive_scores_snapshot utilise date.today()."""
    from datetime import date as _date

    engine = _FakeEngine()
    engine.connection.execute = lambda stmt, params=None: (
        engine.connection.executed.append((stmt, params))
        or _FakeResultProxy(rowcount=0)
    )

    db_io.archive_scores_snapshot(engine)

    _, params = engine.connection.executed[0]
    assert params["snapshot_date"] == _date.today()


def test_upsert_scores_snapshot_calls_archive(monkeypatch) -> None:
    """upsert_scores_snapshot doit appeler archive_scores_snapshot à la fin."""
    archive_calls: list = []

    monkeypatch.setattr(db_io, "archive_scores_snapshot", lambda engine, snapshot_date=None: archive_calls.append(snapshot_date) or 0)
    monkeypatch.setattr(db_io, "_purge_missing_scores", lambda engine, symbols: None)
    monkeypatch.setattr(db_io, "_enrich_scores_with_metadata_sector", lambda engine, df: df)
    monkeypatch.setattr(db_io, "_enrich_scores_with_audit", lambda engine, df: df)

    fake_insert = _FakeInsert()
    monkeypatch.setattr("screener.db_io.mysql_insert", lambda table: fake_insert)
    monkeypatch.setattr(db_io, "_get_scores_table", lambda engine: "stock_scores")

    scores_df = pd.DataFrame([{
        "symbol": "AAPL",
        "liquidity_val": 1.0,
        "relative_strength_index": 0.5,
        "historical_range_score": 0.3,
        "total_score": 0.8,
        "last_updated_score": "2025-01-01",
        "is_candidate": 1,
        "sector": "Tech",
        "last_updated_scan": "2025-01-01",
    }])

    engine = _FakeEngine()
    db_io.upsert_scores_snapshot(engine, scores_df, chunksize=1000)

    assert len(archive_calls) == 1, "archive_scores_snapshot doit être appelé une fois"


def test_upsert_scores_snapshot_archive_failure_does_not_break(monkeypatch) -> None:
    """Si l'archivage échoue (table absente), le pipeline principal ne casse pas."""

    def failing_archive(engine, snapshot_date=None):
        raise Exception("Table stock_scores_history does not exist")

    monkeypatch.setattr(db_io, "archive_scores_snapshot", failing_archive)
    monkeypatch.setattr(db_io, "_purge_missing_scores", lambda engine, symbols: None)
    monkeypatch.setattr(db_io, "_enrich_scores_with_metadata_sector", lambda engine, df: df)
    monkeypatch.setattr(db_io, "_enrich_scores_with_audit", lambda engine, df: df)

    fake_insert = _FakeInsert()
    monkeypatch.setattr("screener.db_io.mysql_insert", lambda table: fake_insert)
    monkeypatch.setattr(db_io, "_get_scores_table", lambda engine: "stock_scores")

    scores_df = pd.DataFrame([{
        "symbol": "AAPL",
        "liquidity_val": 1.0,
        "relative_strength_index": 0.5,
        "historical_range_score": 0.3,
        "total_score": 0.8,
        "last_updated_score": "2025-01-01",
        "is_candidate": 1,
        "sector": "Tech",
        "last_updated_scan": "2025-01-01",
    }])

    engine = _FakeEngine()
    # Ne doit PAS lever d'exception
    db_io.upsert_scores_snapshot(engine, scores_df, chunksize=1000)
