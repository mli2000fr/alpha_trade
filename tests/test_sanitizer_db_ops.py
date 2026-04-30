from datetime import date, datetime
from decimal import Decimal
from typing import cast

import polars as pl
from sqlalchemy import Boolean, Column, Date, DateTime, Integer, MetaData, Numeric, String, Table, create_engine
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


def _build_cleaning_audit_latest_table(metadata: MetaData) -> Table:
    return Table(
        "cleaning_audit_latest",
        metadata,
        Column("symbol", String(10), primary_key=True),
        Column("last_sync_date", Date, nullable=True),
        Column("missing_days_count", Integer, nullable=True),
        Column("anomaly_count", Integer, nullable=True),
        Column("status", String(20), nullable=False),
        Column("error_message", String(255), nullable=True),
        Column("latest_run_at", DateTime, nullable=True),
    )


def _build_cleaning_audit_runs_table(metadata: MetaData) -> Table:
    return Table(
        "cleaning_audit_runs",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("symbol", String(10), nullable=False),
        Column("last_sync_date", Date, nullable=True),
        Column("missing_days_count", Integer, nullable=True),
        Column("anomaly_count", Integer, nullable=True),
        Column("status", String(20), nullable=False),
        Column("error_message", String(255), nullable=True),
        Column("created_at", DateTime, nullable=True),
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


def test_upsert_audit_logs_failed_payload_and_persists_latest_plus_run(caplog) -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    cleaning_audit_latest = _build_cleaning_audit_latest_table(metadata)
    cleaning_audit_runs = _build_cleaning_audit_runs_table(metadata)
    metadata.create_all(engine)

    with engine.begin() as conn:
        with caplog.at_level("ERROR", logger="database.sanitizer_db_ops"):
            sanitizer_db_ops.upsert_audit(
                conn,
                cleaning_audit_latest,
                cleaning_audit_runs,
                "AAPL",
                date(2024, 1, 5),
                None,
                None,
                "failed",
                "RuntimeError: boom",
            )

        latest_row = conn.execute(cleaning_audit_latest.select()).mappings().one()
        run_row = conn.execute(cleaning_audit_runs.select()).mappings().one()

    assert any("Audit en echec | symbol=AAPL" in message for message in caplog.messages)
    assert latest_row["symbol"] == "AAPL"
    assert latest_row["status"] == "failed"
    assert latest_row["error_message"] == "RuntimeError: boom"
    assert run_row["symbol"] == "AAPL"
    assert run_row["status"] == "failed"
    assert run_row["error_message"] == "RuntimeError: boom"


def test_sync_audit_to_stock_scores_updates_existing_symbol() -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    stock_scores = Table(
        "stock_scores",
        metadata,
        Column("symbol", String(10), primary_key=True),
        Column("missing_days_count", Integer, nullable=True, default=0),
        Column("anomaly_count", Integer, nullable=True, default=0),
        Column("sanitizer_status", String(16), nullable=False, default="pending"),
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
                sanitizer_status="pending",
                last_updated_audit=initial_ts,
            )
        )

        updated = sanitizer_db_ops.sync_audit_to_stock_scores(conn, stock_scores, "AAPL", 3, 7, "success")
        row = conn.execute(stock_scores.select().where(stock_scores.c.symbol == "AAPL")).mappings().one()

    assert updated == 1
    assert row["missing_days_count"] == 3
    assert row["anomaly_count"] == 7
    assert row["sanitizer_status"] == "success"
    assert row["last_updated_audit"] >= initial_ts


def test_sync_audit_to_stock_scores_ignores_missing_symbol() -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    stock_scores = Table(
        "stock_scores",
        metadata,
        Column("symbol", String(10), primary_key=True),
        Column("missing_days_count", Integer, nullable=True, default=0),
        Column("anomaly_count", Integer, nullable=True, default=0),
        Column("sanitizer_status", String(16), nullable=False, default="pending"),
        Column("last_updated_audit", DateTime, nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as conn:
        updated = sanitizer_db_ops.sync_audit_to_stock_scores(conn, stock_scores, "MISSING", 2, 5, "failed")
        rows = conn.execute(stock_scores.select()).all()

    assert updated == 0
    assert rows == []


def test_get_failed_audits_returns_recent_failed_rows() -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    cleaning_audit_latest = _build_cleaning_audit_latest_table(metadata)
    metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            cleaning_audit_latest.insert(),
            [
                {
                    "symbol": "AAA",
                    "last_sync_date": date(2024, 1, 1),
                    "missing_days_count": 0,
                    "anomaly_count": 0,
                    "status": "failed",
                    "error_message": "first",
                    "latest_run_at": datetime(2024, 1, 1, 10, 0, 0),
                },
                {
                    "symbol": "BBB",
                    "last_sync_date": date(2024, 1, 2),
                    "missing_days_count": 0,
                    "anomaly_count": 0,
                    "status": "success",
                    "error_message": None,
                    "latest_run_at": datetime(2024, 1, 2, 10, 0, 0),
                },
                {
                    "symbol": "CCC",
                    "last_sync_date": date(2024, 1, 3),
                    "missing_days_count": 0,
                    "anomaly_count": 0,
                    "status": "failed",
                    "error_message": "latest",
                    "latest_run_at": datetime(2024, 1, 3, 10, 0, 0),
                },
            ],
        )

        failed_audits = get_failed_audits(conn, cleaning_audit_latest, limit=10)

    assert [audit["symbol"] for audit in failed_audits] == ["CCC", "AAA"]


def test_get_last_sync_date_reads_from_cleaning_audit_latest() -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    cleaning_audit_latest = _build_cleaning_audit_latest_table(metadata)
    metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            cleaning_audit_latest.insert().values(
                symbol="AAPL",
                last_sync_date=date(2024, 1, 9),
                missing_days_count=1,
                anomaly_count=0,
                status="success",
            )
        )

        last_sync = sanitizer_db_ops.get_last_sync_date(conn, cleaning_audit_latest, "AAPL")

    assert last_sync == date(2024, 1, 9)


def test_get_symbols_excludes_blocked_history_statuses_when_available() -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    stock_metadata = Table(
        "stock_metadata",
        metadata,
        Column("symbol", String(20), primary_key=True),
        Column("status", String(20)),
        Column("tradable", Boolean),
        Column("bars_available", Boolean),
        Column("history_status", String(32)),
        Column("asset_class", String(20)),
    )
    metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            stock_metadata.insert(),
            [
                {"symbol": "AAPL", "status": "active", "tradable": True, "bars_available": True, "history_status": "ready", "asset_class": "us_equity"},
                {"symbol": "MSFT", "status": "active", "tradable": True, "bars_available": True, "history_status": "pending", "asset_class": "us_equity"},
                {"symbol": "NVDA", "status": "active", "tradable": True, "bars_available": True, "history_status": "provider_error", "asset_class": "us_equity"},
            ],
        )

        symbols = sanitizer_db_ops.get_symbols(conn, stock_metadata)

    assert symbols == ["AAPL", "MSFT"]


