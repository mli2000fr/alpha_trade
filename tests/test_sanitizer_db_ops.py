from datetime import date, datetime
from decimal import Decimal
from typing import cast

import polars as pl
from sqlalchemy import Column, DateTime, Integer, MetaData, Numeric, String, Table, create_engine
from sqlalchemy.engine import Connection

from database import sanitizer_db_ops
from database.sanitizer_db_ops import get_failed_audits, get_stock_bars


class _FakeUpsertConnection:
    def __init__(self) -> None:
        self.executed = None

    def execute(self, statement):
        self.executed = statement


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeAuditConnection:
    def __init__(self, row_id=None) -> None:
        self.row_id = row_id
        self.executed: list[object] = []

    def execute(self, statement):
        self.executed.append(statement)
        if len(self.executed) == 1:
            return _FakeScalarResult(self.row_id)
        return None


class _FakeInsert:
    def __init__(self) -> None:
        self.records = None
        self.inserted = {
            "open": "open_inserted",
            "high": "high_inserted",
            "low": "low_inserted",
            "close": "close_inserted",
            "volume": "volume_inserted",
            "adj_close": "adj_close_inserted",
            "vwap": "vwap_inserted",
            "daily_return": "daily_return_inserted",
            "is_filled": "is_filled_inserted",
        }

    def values(self, records):
        self.records = records
        return self

    def on_duplicate_key_update(self, **kwargs):
        return ("upsert", self.records, kwargs)


def _build_stock_bars_table(metadata: MetaData) -> Table:
    return Table(
        "stock_bars",
        metadata,
        Column("symbol", String(10), nullable=False),
        Column("timeframe", String(5), nullable=False),
        Column("timestamp", DateTime, nullable=False),
        Column("open_price", Numeric(20, 8), nullable=False),
        Column("high_price", Numeric(20, 8), nullable=False),
        Column("low_price", Numeric(20, 8), nullable=False),
        Column("close_price", Numeric(20, 8), nullable=False),
        Column("trade_count", Numeric(20, 8), nullable=True),
        Column("volume", Integer, nullable=False),
        Column("vwa_price", Numeric(20, 8), nullable=True),
    )


def test_get_stock_bars_filters_and_sorts_from_start_date() -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    stock_bars = _build_stock_bars_table(metadata)
    metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            stock_bars.insert(),
            [
                {
                    "symbol": "SPY",
                    "timeframe": "1D",
                    "timestamp": datetime(2024, 1, 4, 0, 0, 0),
                    "open_price": Decimal("103.0"),
                    "high_price": Decimal("104.0"),
                    "low_price": Decimal("102.0"),
                    "close_price": Decimal("103.5"),
                    "trade_count": Decimal("12"),
                    "volume": 1300,
                    "vwa_price": Decimal("103.25"),
                },
                {
                    "symbol": "SPY",
                    "timeframe": "1D",
                    "timestamp": datetime(2024, 1, 2, 0, 0, 0),
                    "open_price": Decimal("100.0"),
                    "high_price": Decimal("101.0"),
                    "low_price": Decimal("99.0"),
                    "close_price": Decimal("100.5"),
                    "trade_count": Decimal("10"),
                    "volume": 1100,
                    "vwa_price": Decimal("100.25"),
                },
                {
                    "symbol": "SPY",
                    "timeframe": "1D",
                    "timestamp": datetime(2024, 1, 3, 0, 0, 0),
                    "open_price": Decimal("101.0"),
                    "high_price": Decimal("102.0"),
                    "low_price": Decimal("100.0"),
                    "close_price": Decimal("101.5"),
                    "trade_count": None,
                    "volume": 1200,
                    "vwa_price": None,
                },
                {
                    "symbol": "SPY",
                    "timeframe": "1H",
                    "timestamp": datetime(2024, 1, 3, 10, 0, 0),
                    "open_price": Decimal("1.0"),
                    "high_price": Decimal("1.0"),
                    "low_price": Decimal("1.0"),
                    "close_price": Decimal("1.0"),
                    "trade_count": Decimal("1"),
                    "volume": 1,
                    "vwa_price": Decimal("1.0"),
                },
                {
                    "symbol": "QQQ",
                    "timeframe": "1D",
                    "timestamp": datetime(2024, 1, 3, 0, 0, 0),
                    "open_price": Decimal("1.0"),
                    "high_price": Decimal("1.0"),
                    "low_price": Decimal("1.0"),
                    "close_price": Decimal("1.0"),
                    "trade_count": Decimal("1"),
                    "volume": 1,
                    "vwa_price": Decimal("1.0"),
                },
            ],
        )

        bars = get_stock_bars(conn, stock_bars, "SPY", "1D", date(2024, 1, 3))

    assert [bar["t"] for bar in bars] == [datetime(2024, 1, 3, 0, 0, 0), datetime(2024, 1, 4, 0, 0, 0)]
    assert [bar["c"] for bar in bars] == [101.5, 103.5]
    assert bars[0]["n"] == 0
    assert bars[0]["vw"] is None
    assert all(isinstance(bar["v"], int) for bar in bars)


def test_upsert_stock_bars_daily_uses_current_timestamp_for_last_updated(monkeypatch) -> None:
    metadata = MetaData()
    stock_bars_daily = Table(
        "stock_bars_daily",
        metadata,
        Column("symbol", String(10), primary_key=True),
        Column("date", DateTime, primary_key=True),
        Column("open", Numeric(20, 8), nullable=False),
        Column("high", Numeric(20, 8), nullable=False),
        Column("low", Numeric(20, 8), nullable=False),
        Column("close", Numeric(20, 8), nullable=False),
        Column("volume", Integer, nullable=False),
        Column("adj_close", Numeric(20, 8), nullable=False),
        Column("vwap", Numeric(20, 8), nullable=True),
        Column("daily_return", Numeric(20, 8), nullable=True),
        Column("is_filled", Integer, nullable=False),
        Column("last_updated", DateTime, nullable=True),
    )
    fake_insert = _FakeInsert()
    fake_conn = _FakeUpsertConnection()
    monkeypatch.setattr(sanitizer_db_ops, "mysql_insert", lambda table: fake_insert)

    df = pl.DataFrame(
        {
            "date": [datetime(2024, 1, 2, 0, 0, 0)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000],
            "adj_close": [100.5],
            "vwap": [100.25],
            "daily_return": [0.01],
            "is_filled": [False],
        }
    )

    inserted = sanitizer_db_ops.upsert_stock_bars_daily(
        cast(Connection, fake_conn),
        stock_bars_daily,
        "SPY",
        df,
    )

    assert inserted == 1
    assert fake_conn.executed[0] == "upsert"
    update_dict = fake_conn.executed[2]
    assert "symbol" not in update_dict
    assert "date" not in update_dict
    assert update_dict["open"] == "open_inserted"
    assert "last_updated" in update_dict
    assert "current_timestamp" in str(update_dict["last_updated"]).lower()


def test_upsert_stock_bars_daily_converts_nan_to_none(monkeypatch) -> None:
    metadata = MetaData()
    stock_bars_daily = Table(
        "stock_bars_daily",
        metadata,
        Column("symbol", String(10), primary_key=True),
        Column("date", DateTime, primary_key=True),
        Column("open", Numeric(20, 8), nullable=False),
        Column("high", Numeric(20, 8), nullable=False),
        Column("low", Numeric(20, 8), nullable=False),
        Column("close", Numeric(20, 8), nullable=False),
        Column("volume", Integer, nullable=False),
        Column("adj_close", Numeric(20, 8), nullable=False),
        Column("vwap", Numeric(20, 8), nullable=True),
        Column("daily_return", Numeric(20, 8), nullable=True),
        Column("is_filled", Integer, nullable=False),
        Column("last_updated", DateTime, nullable=True),
    )
    fake_insert = _FakeInsert()
    fake_conn = _FakeUpsertConnection()
    monkeypatch.setattr(sanitizer_db_ops, "mysql_insert", lambda table: fake_insert)

    df = pl.DataFrame(
        {
            "date": [datetime(2024, 1, 2, 0, 0, 0)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000],
            "adj_close": [100.5],
            "vwap": [float("nan")],
            "daily_return": [float("nan")],
            "is_filled": [False],
        }
    )

    sanitizer_db_ops.upsert_stock_bars_daily(
        cast(Connection, fake_conn),
        stock_bars_daily,
        "SPY",
        df,
    )

    records = fake_conn.executed[1]
    assert records[0]["vwap"] is None
    assert records[0]["daily_return"] is None


def test_upsert_stock_bars_daily_converts_inf_to_none_and_logs_warning(monkeypatch, caplog) -> None:
    metadata = MetaData()
    stock_bars_daily = Table(
        "stock_bars_daily",
        metadata,
        Column("symbol", String(10), primary_key=True),
        Column("date", DateTime, primary_key=True),
        Column("open", Numeric(20, 8), nullable=False),
        Column("high", Numeric(20, 8), nullable=False),
        Column("low", Numeric(20, 8), nullable=False),
        Column("close", Numeric(20, 8), nullable=False),
        Column("volume", Integer, nullable=False),
        Column("adj_close", Numeric(20, 8), nullable=False),
        Column("vwap", Numeric(20, 8), nullable=True),
        Column("daily_return", Numeric(20, 8), nullable=True),
        Column("is_filled", Integer, nullable=False),
        Column("last_updated", DateTime, nullable=True),
    )
    fake_insert = _FakeInsert()
    fake_conn = _FakeUpsertConnection()
    monkeypatch.setattr(sanitizer_db_ops, "mysql_insert", lambda table: fake_insert)

    df = pl.DataFrame(
        {
            "date": [datetime(2024, 1, 2, 0, 0, 0)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000],
            "adj_close": [100.5],
            "vwap": [float("inf")],
            "daily_return": [float("-inf")],
            "is_filled": [False],
        }
    )

    with caplog.at_level("WARNING", logger="database.sanitizer_db_ops"):
        sanitizer_db_ops.upsert_stock_bars_daily(
            cast(Connection, fake_conn),
            stock_bars_daily,
            "SPY",
            df,
        )

    records = fake_conn.executed[1]
    assert records[0]["vwap"] is None
    assert records[0]["daily_return"] is None
    assert any(
        "Valeurs non finies neutralis" in message and "stock_bars_daily" in message
        for message in caplog.messages
    )


def test_upsert_audit_logs_failed_payload(caplog) -> None:
    metadata = MetaData()
    cleaning_audit_log = Table(
        "cleaning_audit_log",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("symbol", String(10), nullable=False),
        Column("last_sync_date", DateTime, nullable=True),
        Column("missing_days_count", Integer, nullable=False),
        Column("anomaly_count", Integer, nullable=False),
        Column("status", String(20), nullable=False),
        Column("updated_at", DateTime, nullable=True),
    )
    conn = _FakeAuditConnection(row_id=None)

    with caplog.at_level("ERROR", logger="database.sanitizer_db_ops"):
        sanitizer_db_ops.upsert_audit(
            cast(Connection, conn),
            cleaning_audit_log,
            "AAPL",
            None,
            0,
            0,
            "failed",
        )

    assert any("Audit en échec | symbol=AAPL" in message for message in caplog.messages)


def test_sync_audit_to_stock_scores_updates_existing_symbol() -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    stock_scores = Table(
        "stock_scores",
        metadata,
        Column("symbol", String(10), primary_key=True),
        Column("missing_days_count", Integer, nullable=False, default=0),
        Column("anomaly_count", Integer, nullable=False, default=0),
        Column("last_updated_audit", DateTime, nullable=False),
    )
    metadata.create_all(engine)

    initial_ts = datetime(2024, 1, 1, 9, 0, 0)
    with engine.begin() as conn:
        conn.execute(
            stock_scores.insert().values(
                symbol="AAPL",
                missing_days_count=1,
                anomaly_count=1,
                last_updated_audit=initial_ts,
            )
        )

        updated = sanitizer_db_ops.sync_audit_to_stock_scores(conn, stock_scores, "AAPL", 3, 7)
        row = conn.execute(stock_scores.select().where(stock_scores.c.symbol == "AAPL")).mappings().one()

    assert updated == 1
    assert row["missing_days_count"] == 3
    assert row["anomaly_count"] == 7
    assert row["last_updated_audit"] >= initial_ts


def test_sync_audit_to_stock_scores_ignores_missing_symbol() -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    stock_scores = Table(
        "stock_scores",
        metadata,
        Column("symbol", String(10), primary_key=True),
        Column("missing_days_count", Integer, nullable=False, default=0),
        Column("anomaly_count", Integer, nullable=False, default=0),
        Column("last_updated_audit", DateTime, nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as conn:
        updated = sanitizer_db_ops.sync_audit_to_stock_scores(conn, stock_scores, "MISSING", 2, 5)
        rows = conn.execute(stock_scores.select()).all()

    assert updated == 0
    assert rows == []


def test_get_failed_audits_returns_recent_failed_rows() -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    cleaning_audit_log = Table(
        "cleaning_audit_log",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("symbol", String(10), nullable=False),
        Column("last_sync_date", DateTime, nullable=True),
        Column("missing_days_count", Integer, nullable=False),
        Column("anomaly_count", Integer, nullable=False),
        Column("status", String(20), nullable=False),
        Column("updated_at", DateTime, nullable=True),
    )
    metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            cleaning_audit_log.insert(),
            [
                {
                    "id": 1,
                    "symbol": "AAA",
                    "last_sync_date": datetime(2024, 1, 1, 0, 0, 0),
                    "missing_days_count": 0,
                    "anomaly_count": 0,
                    "status": "failed",
                    "updated_at": datetime(2024, 1, 1, 10, 0, 0),
                },
                {
                    "id": 2,
                    "symbol": "BBB",
                    "last_sync_date": datetime(2024, 1, 2, 0, 0, 0),
                    "missing_days_count": 0,
                    "anomaly_count": 0,
                    "status": "success",
                    "updated_at": datetime(2024, 1, 2, 10, 0, 0),
                },
                {
                    "id": 3,
                    "symbol": "CCC",
                    "last_sync_date": datetime(2024, 1, 3, 0, 0, 0),
                    "missing_days_count": 0,
                    "anomaly_count": 0,
                    "status": "failed",
                    "updated_at": datetime(2024, 1, 3, 10, 0, 0),
                },
            ],
        )

        failed_audits = get_failed_audits(conn, cleaning_audit_log, limit=10)

    assert [audit["symbol"] for audit in failed_audits] == ["CCC", "AAA"]


