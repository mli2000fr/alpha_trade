"""Sprint S12.3 — Tests de la réconciliation broker statements."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from service.alpaca.reconciliation import (
    DIFF_TYPE_MISSING_BROKER,
    DIFF_TYPE_MISSING_INTERNAL,
    DIFF_TYPE_PRICE_MISMATCH,
    DIFF_TYPE_QTY_MISMATCH,
    build_reconciliation_summary,
    parse_statement_csv,
    persist_statements,
    reconcile,
)


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.execute(text("""
            CREATE TABLE broker_statements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                activity_id TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                symbol TEXT,
                side TEXT,
                qty NUMERIC,
                price NUMERIC,
                transaction_time TIMESTAMP,
                raw_json TEXT NOT NULL,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_id, activity_id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE execution_runs (
                exec_run_id TEXT PRIMARY KEY,
                trade_date DATE NOT NULL,
                account_id TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE execution_fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exec_run_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT,
                filled_qty NUMERIC,
                filled_avg_price NUMERIC,
                fill_time TIMESTAMP
            )
        """))
        conn.execute(text(
            "INSERT INTO execution_runs(exec_run_id, trade_date, account_id) "
            "VALUES ('exec-1', :d, 'default')"
        ), {"d": date(2026, 5, 5)})
    return eng


def _add_internal_fill(engine, *, symbol, qty, price):
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO execution_fills(exec_run_id, symbol, side, filled_qty, "
            "filled_avg_price, fill_time) VALUES('exec-1', :s, 'buy', :q, :p, :t)"
        ), {"s": symbol, "q": qty, "p": price, "t": datetime(2026, 5, 5, 10, tzinfo=timezone.utc)})


def test_persist_statements_is_idempotent(engine):
    activities = [{
        "id": "act-1", "activity_type": "FILL", "symbol": "AAPL", "side": "buy",
        "qty": "10", "price": "100.0", "transaction_time": "2026-05-05T10:00:00Z",
    }]
    n1 = persist_statements(engine, "default", activities)
    n2 = persist_statements(engine, "default", activities)  # même activity_id
    assert n1 == 1
    assert n2 == 0  # UNIQUE → ignoré silencieusement


def test_reconcile_perfect_match(engine):
    persist_statements(engine, "default", [{
        "id": "a1", "activity_type": "FILL", "symbol": "AAPL", "side": "buy",
        "qty": "10", "price": "100.0", "transaction_time": "2026-05-05T10:00:00Z",
    }])
    _add_internal_fill(engine, symbol="AAPL", qty=10, price=100.0)
    diffs = reconcile(engine, account_id="default", trade_date=date(2026, 5, 5))
    assert diffs == []


def test_reconcile_missing_internal(engine):
    persist_statements(engine, "default", [{
        "id": "a1", "activity_type": "FILL", "symbol": "AAPL", "side": "buy",
        "qty": "10", "price": "100.0", "transaction_time": "2026-05-05T10:00:00Z",
    }])
    diffs = reconcile(engine, account_id="default", trade_date=date(2026, 5, 5))
    assert len(diffs) == 1 and diffs[0].diff_type == DIFF_TYPE_MISSING_INTERNAL


def test_reconcile_missing_broker(engine):
    _add_internal_fill(engine, symbol="MSFT", qty=5, price=300.0)
    diffs = reconcile(engine, account_id="default", trade_date=date(2026, 5, 5))
    assert len(diffs) == 1 and diffs[0].diff_type == DIFF_TYPE_MISSING_BROKER


def test_reconcile_price_mismatch(engine):
    persist_statements(engine, "default", [{
        "id": "a1", "activity_type": "FILL", "symbol": "TSLA", "side": "buy",
        "qty": "1", "price": "200.0", "transaction_time": "2026-05-05T10:00:00Z",
    }])
    _add_internal_fill(engine, symbol="TSLA", qty=1, price=205.0)  # +2.5 %
    diffs = reconcile(engine, account_id="default", trade_date=date(2026, 5, 5))
    types = sorted(d.diff_type for d in diffs)
    assert DIFF_TYPE_PRICE_MISMATCH in types


def test_parse_statement_csv_accepts_human_friendly_headers() -> None:
    csv_payload = """Activity ID,Activity Type,Symbol,Side,Quantity,Price,Transaction Time
act-1,FILL,AAPL,buy,10,100.0,2026-05-05T10:00:00Z
"""
    rows = parse_statement_csv(csv_payload)
    assert rows == [
        {
            "id": "act-1",
            "activity_type": "FILL",
            "symbol": "AAPL",
            "side": "buy",
            "qty": "10",
            "price": "100.0",
            "transaction_time": "2026-05-05T10:00:00Z",
        }
    ]


def test_build_reconciliation_summary_aggregates_diff_types(engine) -> None:
    persist_statements(engine, "default", [{
        "id": "a1", "activity_type": "FILL", "symbol": "TSLA", "side": "buy",
        "qty": "1", "price": "200.0", "transaction_time": "2026-05-05T10:00:00Z",
    }])
    _add_internal_fill(engine, symbol="MSFT", qty=5, price=300.0)
    diffs = reconcile(engine, account_id="default", trade_date=date(2026, 5, 5))

    summary = build_reconciliation_summary(
        account_id="default",
        trade_date=date(2026, 5, 5),
        diffs=diffs,
        source_kind="csv",
        activity_count=1,
        inserted=1,
        fetched_from_api=False,
        statement_path="F:/tmp/alpaca_j1.csv",
    )

    assert summary["status"] == "WARNING"
    assert summary["diff_count"] == 2
    assert summary["diff_types"][DIFF_TYPE_MISSING_INTERNAL] == 1
    assert summary["diff_types"][DIFF_TYPE_MISSING_BROKER] == 1
    assert sorted(summary["distinct_symbols"]) == ["MSFT", "TSLA"]


