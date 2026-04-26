"""Tests for execution_engine.db_io — SQLite in-memory."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from execution_engine.db_io import ExecutionRepository
from execution_engine.models import BrokerOrder, ExecutionFill, OrderIntent, OrderStatus
@pytest.fixture()
def engine():
    e = create_engine("sqlite:///:memory:")
    with e.begin() as conn:
        # Create tables with SQLite-compatible syntax
        conn.execute(text("""
            CREATE TABLE portfolio_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id VARCHAR(32), account_id VARCHAR(64) DEFAULT 'default', trade_date DATE, symbol VARCHAR(20),
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
                execution_profile VARCHAR(32), submission_window VARCHAR(16),
                status VARCHAR(20), started_at TIMESTAMP, completed_at TIMESTAMP,
                error_message TEXT, total_targets INT, total_submitted INT, total_filled INT,
                account_id VARCHAR(64),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE execution_targets_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exec_run_id VARCHAR(32), account_id VARCHAR(64), risk_run_id VARCHAR(32),
                trade_date DATE, symbol VARCHAR(20), decision_rank INT, side VARCHAR(10),
                target_shares INT, entry_price DOUBLE, target_weight DOUBLE, sector VARCHAR(60),
                conviction_score DOUBLE, sizing_method VARCHAR(20), kelly_fraction DOUBLE,
                atr_20 DOUBLE, price_asof_date DATE, atr_asof_date DATE,
                stop_price_initial DOUBLE, risk_per_share DOUBLE, risk_budget_dollars DOUBLE,
                initial_risk_dollars DOUBLE, target_notional DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE execution_locks (
                account_id VARCHAR(64) PRIMARY KEY,
                locked_by_run_id VARCHAR(32) NOT NULL,
                acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
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
            CREATE TABLE execution_order_requests (
                request_id VARCHAR(32) PRIMARY KEY,
                exec_run_id VARCHAR(32) NOT NULL,
                account_id VARCHAR(64) NOT NULL,
                risk_run_id VARCHAR(32) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                side VARCHAR(10) NOT NULL,
                target_qty DOUBLE NOT NULL,
                order_type VARCHAR(20) NOT NULL,
                business_key VARCHAR(64) NOT NULL,
                submission_key VARCHAR(64),
                attempt_no INT NOT NULL,
                parent_request_id VARCHAR(32),
                intent_role VARCHAR(20) NOT NULL,
                decision_price DOUBLE,
                limit_price DOUBLE,
                stop_price DOUBLE,
                trail_percent DOUBLE,
                status VARCHAR(20) NOT NULL,
                failure_reason VARCHAR(255),
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                UNIQUE(account_id, business_key, attempt_no),
                UNIQUE(submission_key)
            )
        """))
        conn.execute(text("""
            CREATE TABLE execution_broker_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id VARCHAR(32) NOT NULL,
                exec_run_id VARCHAR(32) NOT NULL,
                account_id VARCHAR(64) NOT NULL,
                broker_order_id VARCHAR(64) NOT NULL UNIQUE,
                client_order_id VARCHAR(64),
                symbol VARCHAR(20) NOT NULL,
                side VARCHAR(10) NOT NULL,
                qty DOUBLE NOT NULL,
                filled_qty DOUBLE NOT NULL,
                avg_fill_price DOUBLE,
                raw_status VARCHAR(32) NOT NULL,
                normalized_status VARCHAR(32) NOT NULL,
                order_type VARCHAR(20) NOT NULL,
                limit_price DOUBLE,
                stop_price DOUBLE,
                trail_percent DOUBLE,
                raw_payload_json TEXT,
                raw_response_json TEXT,
                submitted_at TIMESTAMP,
                last_seen_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE execution_broker_fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fill_id VARCHAR(32) NOT NULL UNIQUE,
                exec_run_id VARCHAR(32) NOT NULL,
                account_id VARCHAR(64) NOT NULL,
                broker_order_id VARCHAR(64) NOT NULL,
                request_id VARCHAR(32) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                filled_qty DOUBLE NOT NULL,
                avg_fill_price DOUBLE NOT NULL,
                fill_timestamp TIMESTAMP NOT NULL,
                decision_price DOUBLE,
                slippage_bps DOUBLE,
                implementation_shortfall DOUBLE,
                raw_fill_json TEXT,
                created_at TIMESTAMP
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
            CREATE TABLE broker_account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exec_run_id VARCHAR(32) NOT NULL,
                account_id VARCHAR(64) NOT NULL,
                broker_mode VARCHAR(10) NOT NULL,
                snapshot_kind VARCHAR(20) NOT NULL,
                equity DOUBLE NOT NULL,
                cash DOUBLE NOT NULL,
                settled_cash DOUBLE NOT NULL,
                buying_power DOUBLE NOT NULL,
                daytrade_count INT NOT NULL,
                raw_payload_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE execution_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id VARCHAR(64) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                net_qty DOUBLE NOT NULL,
                avg_entry_price DOUBLE,
                market_price DOUBLE,
                market_value DOUBLE,
                unrealized_pnl DOUBLE,
                broker_mode VARCHAR(10),
                source_exec_run_id VARCHAR(32),
                position_status VARCHAR(16) NOT NULL,
                last_broker_snapshot_at TIMESTAMP,
                updated_at TIMESTAMP,
                UNIQUE(account_id, symbol)
            )
        """))
        conn.execute(text("""
            CREATE TABLE execution_position_lots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_id VARCHAR(40) NOT NULL UNIQUE,
                account_id VARCHAR(64) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                opened_qty DOUBLE NOT NULL,
                remaining_qty DOUBLE NOT NULL,
                entry_price DOUBLE NOT NULL,
                opened_at TIMESTAMP NOT NULL,
                open_exec_run_id VARCHAR(32),
                open_request_id VARCHAR(32),
                open_fill_id VARCHAR(32),
                lot_status VARCHAR(16) NOT NULL,
                close_exec_run_id VARCHAR(32),
                close_request_id VARCHAR(32),
                close_fill_id VARCHAR(32),
                closed_at TIMESTAMP,
                exit_price DOUBLE,
                source_kind VARCHAR(32),
                updated_at TIMESTAMP
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
    @staticmethod
    def _intent(exec_run_id: str, request_id: str, submission_key: str) -> OrderIntent:
        return OrderIntent(
            intent_id=request_id,
            risk_run_id="r1",
            exec_run_id=exec_run_id,
            symbol="AAPL",
            side="buy",
            qty=100.0,
            order_type="market",
            limit_price=None,
            trail_percent=None,
            broker_mode="paper",
            parent_intent_id=None,
            intent_role="entry",
            idempotency_key="business-aapl-entry",
            decision_price=150.0,
            submission_key=submission_key,
        )

    def test_load_portfolio_targets(self, engine, repo) -> None:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO portfolio_targets (run_id, trade_date, symbol, decision_rank, side, shares, entry_price,
                    account_id, atr_20, price_asof_date, atr_asof_date, stop_price_initial, risk_per_share,
                    risk_budget_dollars, initial_risk_dollars, target_notional, target_weight,
                    sector, score_used, score_source, conviction_score, sizing_method, kelly_fraction)
                VALUES ('r1', '2026-04-18', 'AAPL', 1, 'long', 100, 150.0,
                    'default',
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
        repo.insert_execution_run("e1", "r1", date(2026, 4, 18), "paper", False, 5, execution_profile="overnight_cash_swing", submission_window="both")
        with repo.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM execution_runs WHERE exec_run_id = 'e1'")).mappings().first()
        assert row is not None
        assert row["status"] == "RUNNING"
        assert row["execution_profile"] == "overnight_cash_swing"
        assert row["submission_window"] == "both"

    def test_load_portfolio_targets_scopes_account_id(self, engine, repo) -> None:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO portfolio_targets (run_id, account_id, trade_date, symbol, decision_rank, side, shares, entry_price,
                    atr_20, price_asof_date, atr_asof_date, stop_price_initial, risk_per_share,
                    risk_budget_dollars, initial_risk_dollars, target_notional, target_weight,
                    sector, score_used, score_source, conviction_score, sizing_method, kelly_fraction)
                VALUES ('r-scope', 'default', '2026-04-18', 'AAPL', 1, 'long', 100, 150.0,
                    5.0, '2026-04-18', '2026-04-18', 140.0, 10.0,
                    1000.0, 1000.0, 15000.0, 0.05,
                    'Tech', 0.9, 'quant', 0.8, 'atr', 0.1),
                       ('r-scope', 'live1', '2026-04-18', 'MSFT', 1, 'long', 50, 300.0,
                    7.0, '2026-04-18', '2026-04-18', 280.0, 20.0,
                    1000.0, 1000.0, 15000.0, 0.05,
                    'Tech', 0.9, 'quant', 0.8, 'atr', 0.1)
            """))

        default_targets = repo.load_portfolio_targets(risk_run_id="r-scope", account_id="default")
        live_targets = repo.load_portfolio_targets(risk_run_id="r-scope", account_id="live1")

        assert [target.symbol for target in default_targets] == ["AAPL"]
        assert [target.symbol for target in live_targets] == ["MSFT"]

    def test_load_latest_portfolio_targets_scopes_account_id(self, engine, repo) -> None:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO portfolio_targets (run_id, account_id, trade_date, symbol, decision_rank, side, shares, entry_price,
                    atr_20, price_asof_date, atr_asof_date, stop_price_initial, risk_per_share,
                    risk_budget_dollars, initial_risk_dollars, target_notional, target_weight,
                    sector, score_used, score_source, conviction_score, sizing_method, kelly_fraction, created_at)
                VALUES ('r-default', 'default', '2026-04-18', 'AAPL', 1, 'long', 100, 150.0,
                    5.0, '2026-04-18', '2026-04-18', 140.0, 10.0,
                    1000.0, 1000.0, 15000.0, 0.05,
                    'Tech', 0.9, 'quant', 0.8, 'atr', 0.1, '2026-04-18 10:00:00'),
                       ('r-live', 'live1', '2026-04-18', 'MSFT', 1, 'long', 50, 300.0,
                    7.0, '2026-04-18', '2026-04-18', 280.0, 20.0,
                    1000.0, 1000.0, 15000.0, 0.05,
                    'Tech', 0.9, 'quant', 0.8, 'atr', 0.1, '2026-04-18 11:00:00')
            """))

        default_targets = repo.load_portfolio_targets(account_id="default")
        live_targets = repo.load_portfolio_targets(account_id="live1")

        assert [target.symbol for target in default_targets] == ["AAPL"]
        assert [target.symbol for target in live_targets] == ["MSFT"]

    def test_execution_lock_acquire_release_cycle(self, repo) -> None:
        assert repo.acquire_execution_lock(account_id="default", exec_run_id="exec-1") is True
        assert repo.acquire_execution_lock(account_id="default", exec_run_id="exec-2") is False

        repo.release_execution_lock(account_id="default", exec_run_id="exec-1")

        assert repo.acquire_execution_lock(account_id="default", exec_run_id="exec-3") is True

    def test_snapshot_execution_targets(self, engine, repo) -> None:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO portfolio_targets (run_id, account_id, trade_date, symbol, decision_rank, side, shares, entry_price,
                    atr_20, price_asof_date, atr_asof_date, stop_price_initial, risk_per_share,
                    risk_budget_dollars, initial_risk_dollars, target_notional, target_weight,
                    sector, score_used, score_source, conviction_score, sizing_method, kelly_fraction)
                VALUES ('r1', 'default', '2026-04-18', 'AAPL', 1, 'long', 100, 150.0,
                    5.0, '2026-04-18', '2026-04-18', 140.0, 10.0,
                    1000.0, 1000.0, 15000.0, 0.05,
                    'Tech', 0.9, 'quant', 0.8, 'atr', 0.1)
            """))
        targets = repo.load_portfolio_targets(risk_run_id="r1", account_id="default")

        inserted = repo.snapshot_execution_targets(exec_run_id="e-snap", account_id="default", targets=targets)

        assert inserted == 1
        with repo.engine.connect() as conn:
            row = conn.execute(text("SELECT exec_run_id, account_id, symbol FROM execution_targets_snapshot WHERE exec_run_id = 'e-snap'"))\
                .mappings().first()
        assert row is not None
        assert row["account_id"] == "default"
        assert row["symbol"] == "AAPL"

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

    def test_load_pending_protection_watch_items_reads_v2_schema(self, engine, repo) -> None:
        now = datetime.now(timezone.utc)
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO execution_runs (exec_run_id, risk_run_id, trade_date, broker_mode, dry_run, status, started_at, total_targets, total_submitted, total_filled, account_id)
                VALUES ('e2', 'r2', '2026-04-19', 'paper', 0, 'COMPLETED', CURRENT_TIMESTAMP, 1, 1, 1, 'acct-2')
            """))
            conn.execute(text("""
                INSERT INTO execution_targets_snapshot (
                    exec_run_id, account_id, risk_run_id, trade_date, symbol, decision_rank, side,
                    target_shares, entry_price, target_weight, stop_price_initial, risk_per_share,
                    risk_budget_dollars, initial_risk_dollars, target_notional, created_at
                ) VALUES (
                    'e2', 'acct-2', 'r2', '2026-04-19', 'AAPL', 1, 'long',
                    100, 151.0, 0.05, 141.0, 10.0, 1000.0, 1000.0, 15100.0, :created_at
                )
            """), {"created_at": now})
            conn.execute(text("""
                INSERT INTO execution_order_requests (
                    request_id, exec_run_id, account_id, risk_run_id, symbol, side, target_qty,
                    order_type, business_key, submission_key, attempt_no, parent_request_id,
                    intent_role, decision_price, status, created_at, updated_at
                ) VALUES
                    ('parent-2', 'e2', 'acct-2', 'r2', 'AAPL', 'buy', 100,
                     'market', 'bk-parent-2', 'sub-parent-2', 1, NULL,
                     'entry', 151.0, 'FILLED', :created_at, :created_at),
                    ('stop-2', 'e2', 'acct-2', 'r2', 'AAPL', 'sell', 100,
                     'stop', 'bk-stop-2', 'sub-stop-2', 1, 'parent-2',
                     'initial_stop', 151.0, 'SUBMITTED', :created_at, :created_at)
            """), {"created_at": now})
            conn.execute(text("""
                INSERT INTO execution_broker_orders (
                    request_id, exec_run_id, account_id, broker_order_id, client_order_id,
                    symbol, side, qty, filled_qty, avg_fill_price, raw_status, normalized_status,
                    order_type, stop_price, submitted_at, last_seen_at
                ) VALUES (
                    'stop-2', 'e2', 'acct-2', 'bo-stop-2', 'sub-stop-2',
                    'AAPL', 'sell', 100, 0, NULL, 'accepted', 'SUBMITTED',
                    'stop', 141.0, :created_at, :created_at
                )
            """), {"created_at": now})
            conn.execute(text("""
                INSERT INTO execution_broker_fills (
                    fill_id, exec_run_id, account_id, broker_order_id, request_id,
                    symbol, filled_qty, avg_fill_price, fill_timestamp, decision_price,
                    slippage_bps, implementation_shortfall, created_at
                ) VALUES (
                    'fill-2', 'e2', 'acct-2', 'bo-parent-2', 'parent-2',
                    'AAPL', 100, 151.2, :created_at, 151.0,
                    0.0, 0.0, :created_at
                )
            """), {"created_at": now})

        items = repo.load_pending_protection_watch_items(exec_run_id='e2', account_id='acct-2')

        assert len(items) == 1
        assert items[0].source_exec_run_id == 'e2'
        assert items[0].parent_intent_id == 'parent-2'
        assert items[0].initial_stop_intent_id == 'stop-2'
        assert items[0].initial_stop_broker_order_id == 'bo-stop-2'
        assert items[0].fill_price == 151.2
        assert items[0].stop_price_initial == 141.0

    def test_load_open_child_orders_merges_v2_and_legacy_children(self, engine, repo) -> None:
        now = datetime.now(timezone.utc)
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO execution_order_requests (
                    request_id, exec_run_id, account_id, risk_run_id, symbol, side, target_qty,
                    order_type, business_key, submission_key, attempt_no, parent_request_id,
                    intent_role, decision_price, trail_percent, status, created_at, updated_at
                ) VALUES (
                    'trail-v2', 'e3', 'acct-3', 'r3', 'AAPL', 'sell', 100,
                    'trailing_stop', 'bk-trail-v2', 'sub-trail-v2', 1, 'parent-3',
                    'trailing_stop', 152.0, 5.0, 'SUBMITTED', :created_at, :created_at
                )
            """), {"created_at": now})
            conn.execute(text("""
                INSERT INTO execution_broker_orders (
                    request_id, exec_run_id, account_id, broker_order_id, client_order_id,
                    symbol, side, qty, filled_qty, avg_fill_price, raw_status, normalized_status,
                    order_type, trail_percent, submitted_at, last_seen_at
                ) VALUES (
                    'trail-v2', 'e3', 'acct-3', 'bo-trail-v2', 'sub-trail-v2',
                    'AAPL', 'sell', 100, 0, NULL, 'accepted', 'SUBMITTED',
                    'trailing_stop', 5.0, :created_at, :created_at
                )
            """), {"created_at": now})
            conn.execute(text("""
                INSERT INTO execution_orders (
                    exec_run_id, risk_run_id, symbol, intent_id, parent_intent_id, intent_role,
                    idempotency_key, broker_mode, broker_order_id, client_order_id, side, qty,
                    filled_qty, avg_fill_price, order_type, limit_price, stop_price, trail_percent,
                    decision_price, status, created_at, updated_at
                ) VALUES (
                    'e3', 'r3', 'AAPL', 'tp-legacy', 'parent-3', 'take_profit',
                    'k-tp-legacy', 'paper', 'bo-tp-legacy', 'co-tp-legacy', 'sell', 100,
                    0, NULL, 'limit', 160.0, NULL, NULL,
                    152.0, 'SUBMITTED', :created_at, :created_at
                )
            """), {"created_at": now})

        children = repo.load_open_child_orders('parent-3')

        intent_ids = {child.intent_id for child in children}
        assert intent_ids == {'trail-v2', 'tp-legacy'}

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

    def test_upsert_execution_order_request_tracks_attempts_by_business_key(self, repo) -> None:
        intent_v1 = self._intent("exec-1", "req-1", "submit-1")
        intent_v2 = self._intent("exec-2", "req-2", "submit-2")

        attempt_1 = repo.upsert_execution_order_request_from_intent(intent_v1, account_id="acct-1", status=OrderStatus.SUBMITTED)
        attempt_2 = repo.upsert_execution_order_request_from_intent(intent_v2, account_id="acct-1", status=OrderStatus.SUBMITTED)

        assert attempt_1 == 1
        assert attempt_2 == 2
        with repo.engine.connect() as conn:
            rows = conn.execute(text("SELECT request_id, attempt_no, submission_key FROM execution_order_requests ORDER BY attempt_no")).mappings().all()
        assert [row["request_id"] for row in rows] == ["req-1", "req-2"]
        assert [row["attempt_no"] for row in rows] == [1, 2]
        assert [row["submission_key"] for row in rows] == ["submit-1", "submit-2"]

        resolved = repo.find_order_request_by_submission_key(account_id="acct-1", submission_key="submit-2")
        assert resolved is not None
        assert resolved.request_id == "req-2"

    def test_upsert_execution_broker_order_and_broker_fill(self, repo) -> None:
        intent = self._intent("exec-1", "req-1", "submit-1")
        repo.upsert_execution_order_request_from_intent(intent, account_id="acct-1", status=OrderStatus.SUBMITTED)
        now = datetime.now(timezone.utc)
        order = BrokerOrder(
            broker_order_id="bo-1",
            client_order_id="submit-1",
            intent_id="req-1",
            symbol="AAPL",
            side="buy",
            qty=100.0,
            filled_qty=100.0,
            avg_fill_price=150.25,
            status=OrderStatus.FILLED,
            order_type="market",
            limit_price=None,
            stop_price=None,
            trail_percent=None,
            created_at=now,
            updated_at=now,
        )
        fill = ExecutionFill(
            fill_id="fill-1",
            broker_order_id="bo-1",
            intent_id="req-1",
            symbol="AAPL",
            filled_qty=100.0,
            avg_fill_price=150.25,
            fill_timestamp=now,
            decision_price=150.0,
            slippage_bps=16.7,
            implementation_shortfall=25.0,
        )

        repo.upsert_execution_broker_order(intent, order, account_id="acct-1", raw_payload={"client_order_id": "submit-1"})
        repo.insert_execution_broker_fill(fill, account_id="acct-1", raw_fill={"fill_id": "fill-1"})

        with repo.engine.connect() as conn:
            broker_order_row = conn.execute(text("SELECT broker_order_id, normalized_status FROM execution_broker_orders WHERE broker_order_id = 'bo-1'"))\
                .mappings().first()
            broker_fill_row = conn.execute(text("SELECT fill_id, request_id, exec_run_id FROM execution_broker_fills WHERE fill_id = 'fill-1'"))\
                .mappings().first()
        assert broker_order_row is not None
        assert broker_order_row["normalized_status"] == OrderStatus.FILLED
        assert broker_fill_row is not None
        assert broker_fill_row["request_id"] == "req-1"
        assert broker_fill_row["exec_run_id"] == "exec-1"

    def test_snapshot_broker_account(self, repo) -> None:
        repo.snapshot_broker_account(
            "exec-1",
            account_id="acct-1",
            broker_mode="paper",
            snapshot={
                "equity": 100_000.0,
                "cash": 75_000.0,
                "settled_cash": 70_000.0,
                "buying_power": 150_000.0,
                "daytrade_count": 1,
            },
        )

        with repo.engine.connect() as conn:
            row = conn.execute(text("SELECT account_id, snapshot_kind, equity, settled_cash FROM broker_account_snapshots"))\
                .mappings().first()
        assert row is not None
        assert row["account_id"] == "acct-1"
        assert row["snapshot_kind"] == "preflight"
        assert row["equity"] == 100_000.0
        assert row["settled_cash"] == 70_000.0

    def test_replace_execution_positions_writes_open_positions(self, repo) -> None:
        count = repo.replace_execution_positions(
            exec_run_id="exec-10",
            account_id="acct-10",
            broker_mode="paper",
            positions=[
                {
                    "symbol": "AAPL",
                    "qty": 15,
                    "avg_entry_price": 150.0,
                    "current_price": 155.0,
                    "market_value": 2325.0,
                    "unrealized_pl": 75.0,
                }
            ],
        )

        assert count == 1
        positions = repo.load_execution_positions(account_id="acct-10")
        assert len(positions) == 1
        assert positions[0].symbol == "AAPL"
        assert positions[0].net_qty == 15
        assert positions[0].position_status == "OPEN"

    def test_replace_execution_positions_writes_explicit_flat_marker(self, repo) -> None:
        count = repo.replace_execution_positions(
            exec_run_id="exec-flat",
            account_id="acct-flat",
            broker_mode="paper",
            positions=[],
        )

        assert count == 1
        positions = repo.load_execution_positions(account_id="acct-flat")
        assert len(positions) == 1
        assert positions[0].symbol == "__FLAT__"
        assert positions[0].position_status == "FLAT"

    def test_rebuild_execution_position_lots_tracks_open_and_closed_lots_fifo(self, repo) -> None:
        intent_buy_1 = self._intent("exec-1", "req-buy-1", "submit-buy-1")
        intent_buy_2 = self._intent("exec-2", "req-buy-2", "submit-buy-2")
        intent_sell = OrderIntent(
            intent_id="req-sell-1",
            risk_run_id="r1",
            exec_run_id="exec-3",
            symbol="AAPL",
            side="sell",
            qty=12.0,
            order_type="market",
            limit_price=None,
            trail_percent=None,
            broker_mode="paper",
            parent_intent_id=None,
            intent_role="exit",
            idempotency_key="business-aapl-exit",
            decision_price=155.0,
            submission_key="submit-sell-1",
        )
        repo.upsert_execution_order_request_from_intent(intent_buy_1, account_id="acct-lots", status=OrderStatus.FILLED)
        repo.upsert_execution_order_request_from_intent(intent_buy_2, account_id="acct-lots", status=OrderStatus.FILLED)
        repo.upsert_execution_order_request_from_intent(intent_sell, account_id="acct-lots", status=OrderStatus.FILLED)

        base_ts = datetime(2026, 4, 26, 20, 0, tzinfo=timezone.utc)
        fills = [
            ExecutionFill("fill-buy-1", "bo-buy-1", "req-buy-1", "AAPL", 10.0, 150.0, base_ts, 150.0, 0.0, 0.0),
            ExecutionFill("fill-buy-2", "bo-buy-2", "req-buy-2", "AAPL", 5.0, 152.0, base_ts.replace(minute=1), 152.0, 0.0, 0.0),
            ExecutionFill("fill-sell-1", "bo-sell-1", "req-sell-1", "AAPL", 12.0, 155.0, base_ts.replace(minute=2), 155.0, 0.0, 0.0),
        ]
        for fill in fills:
            repo.insert_execution_broker_fill(fill, account_id="acct-lots")

        count = repo.rebuild_execution_position_lots(account_id="acct-lots")

        assert count == 2
        lots = repo.load_execution_position_lots(account_id="acct-lots")
        assert len(lots) == 2
        closed_lot = next(lot for lot in lots if lot.open_fill_id == "fill-buy-1")
        open_lot = next(lot for lot in lots if lot.open_fill_id == "fill-buy-2")
        assert closed_lot.remaining_qty == 0.0
        assert closed_lot.lot_status == "CLOSED"
        assert closed_lot.close_fill_id == "fill-sell-1"
        assert open_lot.remaining_qty == 3.0
        assert open_lot.lot_status == "OPEN"

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
