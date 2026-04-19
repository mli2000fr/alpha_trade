import sys
import os
# Ajout du dossier parent au sys.path pour import corporate_actions
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from datetime import date, datetime
from sqlalchemy import create_engine, text
from corporate_actions.db_io import CorporateActionRepository
from corporate_actions.models import CorporateActionEvent, CaType, CaStatus, CorporateActionApplication, CashLedgerEntry

SQLITE_SCHEMA = """
    CREATE TABLE corporate_actions_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idempotency_key VARCHAR(64) UNIQUE NOT NULL,
        provider VARCHAR(30) NOT NULL,
        provider_event_id VARCHAR(128),
        symbol VARCHAR(20) NOT NULL,
        ca_type VARCHAR(30) NOT NULL,
        amount_per_share DOUBLE,
        split_from INT,
        split_to INT,
        currency VARCHAR(5) DEFAULT 'USD',
        announcement_date DATE,
        ex_date DATE NOT NULL,
        record_date DATE,
        payable_date DATE,
        raw_payload TEXT,
        status VARCHAR(20) DEFAULT 'pending',
        error_message VARCHAR(500),
        ingested_at TIMESTAMP,
        applied_at TIMESTAMP
    );
    CREATE TABLE corporate_actions_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id BIGINT NOT NULL,
        symbol VARCHAR(20) NOT NULL,
        ca_type VARCHAR(30) NOT NULL,
        position_qty_before DOUBLE NOT NULL,
        position_qty_after DOUBLE NOT NULL,
        cost_basis_before DOUBLE,
        cost_basis_after DOUBLE,
        cash_impact DOUBLE DEFAULT 0,
        fractional_shares DOUBLE DEFAULT 0,
        account_id VARCHAR(32),
        applied_at TIMESTAMP
    );
    CREATE TABLE portfolio_cash_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id BIGINT,
        symbol VARCHAR(20) NOT NULL,
        entry_type VARCHAR(30) NOT NULL,
        amount DOUBLE NOT NULL,
        currency VARCHAR(5) DEFAULT 'USD',
        description VARCHAR(255),
        account_id VARCHAR(32),
        created_at TIMESTAMP
    );
    CREATE TABLE broker_positions_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exec_run_id VARCHAR(32),
        broker_mode VARCHAR(10),
        symbol VARCHAR(20),
        qty DOUBLE DEFAULT 0,
        avg_entry_price DOUBLE DEFAULT 0,
        market_value DOUBLE DEFAULT 0,
        unrealized_pnl DOUBLE DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE stock_metadata (
        symbol VARCHAR(20) PRIMARY KEY,
        status VARCHAR(20),
        tradable BOOLEAN,
        bars_available BOOLEAN
    );
"""

@pytest.fixture()
def engine():
    e = create_engine("sqlite:///:memory:")
    with e.begin() as conn:
        for stmt in SQLITE_SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    return e

@pytest.fixture()
def repo(engine):
    return CorporateActionRepository(engine=engine)

def make_event(symbol="AAPL", amount=1.0, ex_date=date(2026, 4, 10)):
    return CorporateActionEvent(
        provider="alpaca",
        provider_event_id="div-001",
        symbol=symbol,
        ca_type=CaType.CASH_DIVIDEND,
        amount_per_share=amount,
        ex_date=ex_date,
    )

def test_insert_event_and_duplicate(repo):
    event = make_event()
    row_id = repo.insert_event(event)
    assert row_id > 0
    # Doublon
    row_id2 = repo.insert_event(event)
    assert row_id2 == -1

def test_insert_event_sqlite(repo):
    event = make_event(symbol="MSFT")
    row_id = repo.insert_event_sqlite(event)
    assert row_id > 0
    # Doublon
    row_id2 = repo.insert_event_sqlite(event)
    assert row_id2 == -1

def test_load_pending_events(repo):
    event = make_event()
    repo.insert_event(event)
    events = repo.load_pending_events()
    assert len(events) == 1
    # as_of filtre
    events2 = repo.load_pending_events(as_of=date(2026, 4, 9))
    assert len(events2) == 0

def test_is_event_applied_and_mark_applied(repo):
    event = make_event()
    row_id = repo.insert_event(event)
    assert not repo.is_event_applied(event.idempotency_key)
    repo.mark_applied(row_id)
    assert repo.is_event_applied(event.idempotency_key)

def test_mark_failed_and_skipped(repo):
    event = make_event()
    row_id = repo.insert_event(event)
    repo.mark_failed(row_id, "erreur")
    repo.mark_skipped(row_id, "skip reason")
    # Pas d'exception

def test_insert_application_and_ledger(repo):
    event = make_event()
    row_id = repo.insert_event(event)
    app = CorporateActionApplication(
        event_id=row_id, symbol="AAPL", ca_type=CaType.CASH_DIVIDEND,
        position_qty_before=10, position_qty_after=10,
        cost_basis_before=100.0, cost_basis_after=100.0,
        cash_impact=10.0,
    )
    repo.insert_application(app)
    ledger = CashLedgerEntry(
        event_id=row_id, symbol="AAPL", entry_type="dividend_credit",
        amount=10.0, description="Test",
    )
    repo.insert_cash_ledger(ledger)
    total = repo.get_total_dividends(symbol="AAPL")
    assert total == 10.0

def test_load_latest_positions_and_symbols(repo, engine):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO broker_positions_snapshots
                (exec_run_id, broker_mode, symbol, qty, avg_entry_price, market_value, unrealized_pnl)
            VALUES ('run-001', 'paper', 'AAPL', 10, 100.0, 1000.0, 0.0),
                   ('run-001', 'paper', 'MSFT', 0, 150.0, 0.0, 0.0),
                   ('run-001', 'paper', 'NVDA', 5, 800.0, 4000.0, 0.0)
        """))
    pos = repo.load_latest_positions()
    assert any(r['symbol'].strip().upper() == 'AAPL' for r in pos)
    symbols = repo.load_latest_position_symbols()
    assert symbols == ['AAPL', 'NVDA']

def test_load_bars_available_symbols(repo, engine):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO stock_metadata (symbol, status, tradable, bars_available)
            VALUES ('AAPL', 'active', 1, 1),
                   ('MSFT', 'inactive', 1, 1),
                   ('NVDA', 'active', 0, 1),
                   ('AMD', 'active', 1, 0),
                   ('META', 'active', 1, 1)
        """))
    symbols = repo.load_bars_available_symbols()
    assert symbols == ['AAPL', 'META']

def test_load_existing_event_symbols(repo):
    repo.insert_event(make_event(symbol="AAPL"))
    repo.insert_event(make_event(symbol="MSFT", ex_date=date(2026, 4, 11)))
    all_syms = repo.load_existing_event_symbols()
    assert set(all_syms) == {'AAPL', 'MSFT'}
    subset = repo.load_existing_event_symbols([" msft ", "NVDA"])
    assert subset == ['MSFT']
    assert repo.load_existing_event_symbols([]) == []

def test_row_to_event_json_error():
    r = {'id': 1, 'provider': 'alpaca', 'provider_event_id': 'x', 'symbol': 'AAPL', 'ca_type': CaType.CASH_DIVIDEND, 'amount_per_share': 1.0, 'split_from': None, 'split_to': None, 'currency': 'USD', 'announcement_date': None, 'ex_date': date(2026,4,10), 'record_date': None, 'payable_date': None, 'raw_payload': '{malformed}', 'status': CaStatus.PENDING, 'ingested_at': datetime.now()}
    evt = CorporateActionRepository._row_to_event(r)
    assert evt.symbol == 'AAPL'
    assert evt.raw_payload is None

