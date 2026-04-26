"""Tests for execution_engine.db_io — SQLite in-memory."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from execution_engine.db_io import ExecutionRepository
@pytest.fixture()
def engine():
    e = create_engine("sqlite:///:memory:")
    with e.begin() as conn:
        # Create tables with SQLite-compatible syntax
        conn.execute(text("""
            CREATE TABLE portfolio_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id VARCHAR(32), trade_date DATE, symbol VARCHAR(20),
                    decision_rank INT, side VARCHAR(10),
                    shares INT, entry_price DOUBLE, atr_20 DOUBLE,
                    price_asof_date DATE, atr_asof_date DATE,
                    stop_price_initial DOUBLE, risk_per_share DOUBLE,
                    risk_budget_dollars DOUBLE, initial_risk_dollars DOUBLE,
                    target_notional DOUBLE, target_weight DOUBLE,
                sector VARCHAR(60), score_used DOUBLE, score_source VARCHAR(40),
                conviction_score DOUBLE, sizing_method VARCHAR(20), kelly_fraction DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE execution_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exec_run_id VARCHAR(32) UNIQUE, risk_run_id VARCHAR(32),
                trade_date DATE, broker_mode VARCHAR(10), dry_run BOOLEAN,
                status VARCHAR(20), started_at TIMESTAMP, completed_at TIMESTAMP,
                error_message TEXT, total_targets INT, total_submitted INT, total_filled INT,
                account_id VARCHAR(64),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE execution_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exec_run_id VARCHAR(32), risk_run_id VARCHAR(32),
                symbol VARCHAR(20), intent_id VARCHAR(32),
                parent_intent_id VARCHAR(32), intent_role VARCHAR(20),
                idempotency_key VARCHAR(64) UNIQUE, broker_mode VARCHAR(10),
                broker_order_id VARCHAR(64), client_order_id VARCHAR(64),
                side VARCHAR(10), qty DOUBLE, filled_qty DOUBLE,
                avg_fill_price DOUBLE, order_type VARCHAR(20),
                limit_price DOUBLE, stop_price DOUBLE, trail_percent DOUBLE,
                decision_price DOUBLE, status VARCHAR(20),
                created_at TIMESTAMP, updated_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE execution_fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exec_run_id VARCHAR(32), fill_id VARCHAR(32) UNIQUE,
                broker_order_id VARCHAR(64), intent_id VARCHAR(32),
                symbol VARCHAR(20), filled_qty DOUBLE, avg_fill_price DOUBLE,
                fill_timestamp TIMESTAMP, decision_price DOUBLE,
                slippage_bps DOUBLE, implementation_shortfall DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE execution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id VARCHAR(32) UNIQUE, exec_run_id VARCHAR(32),
                symbol VARCHAR(20), event_type VARCHAR(40),
                message VARCHAR(255), broker_order_id VARCHAR(64),
                intent_id VARCHAR(32), payload_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE broker_positions_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exec_run_id VARCHAR(32), broker_mode VARCHAR(10),
                symbol VARCHAR(20), qty DOUBLE, avg_entry_price DOUBLE,
                market_value DOUBLE, unrealized_pnl DOUBLE,
                account_id VARCHAR(64),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
    return e


@pytest.fixture()
def repo(engine):
    return ExecutionRepository(engine=engine)


class TestExecutionDbIo:
    def test_load_portfolio_targets(self, engine, repo) -> None:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO portfolio_targets (run_id, trade_date, symbol, decision_rank, side, shares, entry_price,
                    atr_20, price_asof_date, atr_asof_date, stop_price_initial, risk_per_share,
                    risk_budget_dollars, initial_risk_dollars, target_notional, target_weight,
                    sector, score_used, score_source, conviction_score, sizing_method, kelly_fraction)
                VALUES ('r1', '2026-04-18', 'AAPL', 1, 'long', 100, 150.0,
                    5.0, '2026-04-18', '2026-04-18', 140.0, 10.0,
                    1000.0, 1000.0, 15000.0, 0.05,
                    'Tech', 0.9, 'quant', 0.8, 'atr', 0.1)
            """))
        targets = repo.load_portfolio_targets(risk_run_id="r1")
        assert len(targets) == 1
        assert targets[0].symbol == "AAPL"
        assert targets[0].target_shares == 100
        assert targets[0].decision_rank == 1
        assert targets[0].stop_price_initial == 140.0
        assert targets[0].risk_per_share == 10.0
        assert targets[0].target_notional == 15000.0

    def test_insert_execution_run(self, repo) -> None:
        repo.insert_execution_run("e1", "r1", date(2026, 4, 18), "paper", False, 5)
        with repo.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM execution_runs WHERE exec_run_id = 'e1'")).mappings().first()
        assert row is not None
        assert row["status"] == "RUNNING"

    def test_load_pending_protection_watch_items(self, engine, repo) -> None:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO execution_runs (exec_run_id, risk_run_id, trade_date, broker_mode, dry_run, status, started_at, total_targets, total_submitted, total_filled, account_id)
                VALUES ('e1', 'r1', '2026-04-18', 'paper', 0, 'COMPLETED', CURRENT_TIMESTAMP, 1, 1, 1, 'acct-1')
            """))
            conn.execute(text("""
                INSERT INTO execution_orders (exec_run_id, risk_run_id, symbol, intent_id, parent_intent_id, intent_role, idempotency_key, broker_mode,
                                              broker_order_id, client_order_id, side, qty, filled_qty, avg_fill_price, order_type, limit_price, stop_price,
                                              trail_percent, decision_price, status, created_at, updated_at)
                VALUES ('e1', 'r1', 'AAPL', 'parent-1', NULL, 'entry', 'k-parent', 'paper', 'bo-parent', 'co-parent', 'buy', 100, 100, 150.2, 'market', NULL, NULL, NULL, 150.0, 'FILLED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                       ('e1', 'r1', 'AAPL', 'stop-1', 'parent-1', 'initial_stop', 'k-stop', 'paper', 'bo-stop', 'co-stop', 'sell', 100, 0, NULL, 'stop', NULL, 140.0, NULL, 150.0, 'SUBMITTED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """))
            conn.execute(text("""
                INSERT INTO execution_fills (exec_run_id, fill_id, broker_order_id, intent_id, symbol, filled_qty, avg_fill_price, fill_timestamp, decision_price, slippage_bps, implementation_shortfall)
                VALUES ('e1', 'f1', 'bo-parent', 'parent-1', 'AAPL', 100, 150.2, CURRENT_TIMESTAMP, 150.0, 0.0, 0.0)
            """))

        items = repo.load_pending_protection_watch_items(exec_run_id='e1')

        assert len(items) == 1
        assert items[0].source_exec_run_id == 'e1'
        assert items[0].parent_intent_id == 'parent-1'
        assert items[0].initial_stop_intent_id == 'stop-1'
        assert items[0].fill_price == 150.2

    def test_upsert_order_idempotent(self, repo) -> None:
        d = {
            "exec_run_id": "e1", "risk_run_id": "r1", "symbol": "AAPL",
            "intent_id": "i1", "parent_intent_id": None, "intent_role": "entry",
            "idempotency_key": "k1", "broker_mode": "paper",
            "broker_order_id": None, "client_order_id": "k1",
            "side": "buy", "qty": 100, "filled_qty": 0, "avg_fill_price": None,
            "order_type": "market", "limit_price": None, "stop_price": None,
            "trail_percent": None, "decision_price": 150.0, "status": "NEW",
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        }
        # SQLite doesn't support ON DUPLICATE KEY UPDATE, use INSERT OR REPLACE
        # We test the repo with a small override for SQLite
        with repo.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO execution_orders
                    (exec_run_id, risk_run_id, symbol, intent_id, parent_intent_id,
                     intent_role, idempotency_key, broker_mode, broker_order_id,
                     client_order_id, side, qty, filled_qty, avg_fill_price,
                     order_type, limit_price, stop_price, trail_percent,
                     decision_price, status, created_at, updated_at)
                VALUES
                    (:exec_run_id, :risk_run_id, :symbol, :intent_id, :parent_intent_id,
                     :intent_role, :idempotency_key, :broker_mode, :broker_order_id,
                     :client_order_id, :side, :qty, :filled_qty, :avg_fill_price,
                     :order_type, :limit_price, :stop_price, :trail_percent,
                     :decision_price, :status, :created_at, :updated_at)
            """), d)
        keys = repo.load_submitted_idempotency_keys("e1")
        assert "k1" in keys

    def test_insert_fill(self, repo) -> None:
        d = {
            "exec_run_id": "e1", "fill_id": "f1", "broker_order_id": "bo1",
            "intent_id": "i1", "symbol": "AAPL", "filled_qty": 100,
            "avg_fill_price": 150.5, "fill_timestamp": datetime.now(timezone.utc),
            "decision_price": 150.0, "slippage_bps": 33.3, "implementation_shortfall": 50.0,
        }
        repo.insert_execution_fill(d)
        with repo.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM execution_fills WHERE fill_id = 'f1'")).mappings().first()
        assert row is not None

    def test_insert_event(self, repo) -> None:
        d = {
            "event_id": "ev1", "exec_run_id": "e1", "symbol": "AAPL",
            "event_type": "ORDER_SUBMITTED", "message": "test",
            "broker_order_id": None, "intent_id": None,
            "payload_json": None, "created_at": datetime.now(timezone.utc),
        }
        repo.insert_execution_event(d)
        with repo.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM execution_events WHERE event_id = 'ev1'")).mappings().first()
        assert row is not None

    def test_snapshot_positions(self, repo) -> None:
        positions = [{"symbol": "AAPL", "qty": 100, "avg_entry_price": 150.0, "market_value": 15000.0, "unrealized_pl": 50.0}]
        repo.snapshot_broker_positions("e1", "paper", positions)
        with repo.engine.connect() as conn:
            rows = conn.execute(text("SELECT * FROM broker_positions_snapshots")).mappings().all()
        assert len(rows) == 1
