from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.dialects import mysql
from sqlalchemy import Date, Float, MetaData, String, Table, Column
from sqlalchemy.pool import StaticPool

from database import selector_reference


def _create_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_list_active_tradable_symbols_filters_blocked_history_statuses(monkeypatch) -> None:
    engine = _create_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_metadata (
                    symbol TEXT PRIMARY KEY,
                    status TEXT,
                    tradable BOOLEAN,
                    bars_available BOOLEAN,
                    history_status TEXT,
                    asset_class TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO stock_metadata (symbol, status, tradable, bars_available, history_status, asset_class)
                VALUES
                    ('AAPL', 'active', 1, 1, 'ready', 'us_equity'),
                    ('MSFT', 'active', 1, 1, 'pending', 'us_equity'),
                    ('ERR', 'active', 1, 1, 'provider_error', 'us_equity'),
                    ('STALE', 'active', 1, 1, 'suspended_or_stale', 'us_equity'),
                    ('AMD', 'active', 1, 0, 'no_history', 'us_equity'),
                    ('QQQ', 'active', 1, 1, 'ready', 'etf')
                """
            )
        )

    monkeypatch.setattr(selector_reference, "get_sqlalchemy_engine", lambda: engine)

    assert selector_reference.list_active_tradable_symbols() == ["AAPL", "MSFT"]


def test_list_active_tradable_symbols_falls_back_when_history_status_column_is_absent(monkeypatch) -> None:
    engine = _create_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_metadata (
                    symbol TEXT PRIMARY KEY,
                    status TEXT,
                    tradable BOOLEAN,
                    bars_available BOOLEAN,
                    asset_class TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO stock_metadata (symbol, status, tradable, bars_available, asset_class)
                VALUES
                    ('AAPL', 'active', 1, 1, 'us_equity'),
                    ('MSFT', 'inactive', 1, 1, 'us_equity'),
                    ('AMD', 'active', 1, 0, 'us_equity')
                """
            )
        )

    monkeypatch.setattr(selector_reference, "get_sqlalchemy_engine", lambda: engine)

    assert selector_reference.list_active_tradable_symbols() == ["AAPL"]


def test_upsert_quote_snapshots_ignores_missing_legacy_columns(monkeypatch) -> None:
    legacy_table = Table(
        "stock_quote_snapshots",
        MetaData(),
        Column("symbol", String(20), primary_key=True),
        Column("quote_date", Date, primary_key=True),
        Column("spread_bps", Float),
    )
    captured: dict[str, object] = {}

    class _FakeSession:
        def execute(self, stmt):
            captured["sql"] = str(
                stmt.compile(
                    dialect=mysql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            )

        def commit(self):
            captured["committed"] = True

        def rollback(self):
            captured["rolled_back"] = True

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(selector_reference, "get_stock_quote_snapshots_table", lambda: legacy_table)
    monkeypatch.setattr(selector_reference, "SessionLocal", lambda: _FakeSession())

    row_count = selector_reference.upsert_quote_snapshots(
        [
            {
                "symbol": "AAPL",
                "quote_date": date(2026, 4, 30),
                "quote_timestamp": datetime(2026, 4, 30, 20, 0, 0),
                "bid_price": 100.0,
                "ask_price": 100.5,
                "bid_size": 10.0,
                "ask_size": 12.0,
                "spread_bps": 49.9,
            }
        ]
    )

    sql = str(captured["sql"])
    assert row_count == 1
    assert captured["committed"] is True
    assert captured["closed"] is True
    assert "quote_timestamp" not in sql
    assert "bid_size" not in sql
    assert "ask_size" not in sql
    assert "bid_price" not in sql
    assert "ask_price" not in sql
    assert "spread_bps" in sql


def test_get_quote_snapshot_resume_state_detects_complete_and_missing_days(monkeypatch) -> None:
    engine = _create_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_quote_snapshots (
                    symbol TEXT,
                    quote_date DATE,
                    spread_bps FLOAT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO stock_quote_snapshots (symbol, quote_date, spread_bps)
                VALUES
                    ('AAPL', '2026-04-21', 12.0),
                    ('AAPL', '2026-04-23', 13.0)
                """
            )
        )

    monkeypatch.setattr(selector_reference, "get_sqlalchemy_engine", lambda: engine)

    state = selector_reference.get_quote_snapshot_resume_state(
        "AAPL",
        from_date=date(2026, 4, 21),
        to_date=date(2026, 4, 23),
        expected_dates=[date(2026, 4, 21), date(2026, 4, 22), date(2026, 4, 23)],
    )

    assert state["has_expected_days"] is True
    assert state["is_complete"] is False
    assert state["expected_days"] == 3
    assert state["stored_days"] == 2
    assert state["missing_days"] == 1
    assert state["first_missing_date"] == date(2026, 4, 22)
    assert state["missing_ranges"] == [(date(2026, 4, 22), date(2026, 4, 22))]


def test_get_quote_snapshot_resume_state_groups_missing_trading_days_across_weekend(monkeypatch) -> None:
    engine = _create_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_quote_snapshots (
                    symbol TEXT,
                    quote_date DATE,
                    spread_bps FLOAT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO stock_quote_snapshots (symbol, quote_date, spread_bps)
                VALUES
                    ('AAPL', '2026-04-21', 12.0),
                    ('AAPL', '2026-04-24', 13.0)
                """
            )
        )

    monkeypatch.setattr(selector_reference, "get_sqlalchemy_engine", lambda: engine)

    state = selector_reference.get_quote_snapshot_resume_state(
        "AAPL",
        from_date=date(2026, 4, 21),
        to_date=date(2026, 4, 27),
        expected_dates=[
            date(2026, 4, 21),
            date(2026, 4, 22),
            date(2026, 4, 23),
            date(2026, 4, 24),
            date(2026, 4, 27),
        ],
    )

    assert state["missing_days"] == 3
    assert state["missing_ranges"] == [(date(2026, 4, 22), date(2026, 4, 23)), (date(2026, 4, 27), date(2026, 4, 27))]


