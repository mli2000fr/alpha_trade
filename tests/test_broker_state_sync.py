from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from execution_engine.broker_state_sync import BrokerStateSynchronizer
from execution_engine.db_io import ExecutionRepository
from execution_engine.models import OrderIntent, OrderStatus
from sqlalchemy import create_engine, text


def _setup_engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
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
            CREATE TABLE broker_positions_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exec_run_id VARCHAR(32), broker_mode VARCHAR(10),
                symbol VARCHAR(20), qty DOUBLE, avg_entry_price DOUBLE,
                market_value DOUBLE, unrealized_pnl DOUBLE,
                account_id VARCHAR(64),
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
    return engine


def _intent(exec_run_id: str, request_id: str, submission_key: str) -> OrderIntent:
    return OrderIntent(
        intent_id=request_id,
        risk_run_id="risk-1",
        exec_run_id=exec_run_id,
        symbol="AAPL",
        side="buy",
        qty=10.0,
        order_type="market",
        limit_price=None,
        trail_percent=None,
        broker_mode="paper",
        parent_intent_id=None,
        intent_role="entry",
        idempotency_key=f"business-{request_id}",
        decision_price=150.0,
        submission_key=submission_key,
    )


def test_broker_state_sync_inserts_missing_fill_and_projects_positions() -> None:
    repo = ExecutionRepository(engine=_setup_engine())
    repo.upsert_execution_order_request_from_intent(_intent("exec-1", "req-1", "sub-1"), account_id="acct-1", status=OrderStatus.SUBMITTED)

    broker = MagicMock()
    now = datetime.now(timezone.utc)
    broker.list_recent_orders.return_value = [
        {
            "id": "bo-1",
            "client_order_id": "sub-1",
            "symbol": "AAPL",
            "side": "buy",
            "qty": "10",
            "filled_qty": "10",
            "filled_avg_price": "151.0",
            "status": "filled",
            "type": "market",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
    ]
    broker.broker_order_from_api.side_effect = lambda payload, intent_id="": ExecutionRepository._row_to_broker_order(
        {
            "broker_order_id": payload["id"],
            "client_order_id": payload["client_order_id"],
            "intent_id": intent_id,
            "symbol": payload["symbol"],
            "side": payload["side"],
            "qty": payload["qty"],
            "filled_qty": payload["filled_qty"],
            "avg_fill_price": payload["filled_avg_price"],
            "status": "FILLED",
            "order_type": payload["type"],
            "limit_price": None,
            "stop_price": None,
            "trail_percent": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    broker.get_all_positions.return_value = [
        {
            "symbol": "AAPL",
            "qty": 10,
            "avg_entry_price": 151.0,
            "current_price": 152.0,
            "market_value": 1520.0,
            "unrealized_pl": 10.0,
        }
    ]

    sync = BrokerStateSynchronizer(repo, broker, broker_mode="paper")
    metrics = sync.sync(exec_run_id="exec-sync", account_id="acct-1", order_limit=10)

    assert metrics["orders_synced"] == 1
    assert metrics["fills_synced"] == 1
    assert metrics["positions_projected"] == 1
    assert metrics["lots_projected"] == 1
    assert repo.load_execution_positions(account_id="acct-1")[0].symbol == "AAPL"
    lots = repo.load_execution_position_lots(account_id="acct-1")
    assert len(lots) == 1
    assert lots[0].remaining_qty == 10.0


def test_broker_state_sync_writes_flat_marker_when_broker_has_no_position() -> None:
    repo = ExecutionRepository(engine=_setup_engine())
    broker = MagicMock()
    broker.list_recent_orders.return_value = []
    broker.get_all_positions.return_value = []

    sync = BrokerStateSynchronizer(repo, broker, broker_mode="paper")
    metrics = sync.sync(exec_run_id="exec-flat", account_id="acct-flat")

    assert metrics["orders_synced"] == 0
    assert metrics["positions_projected"] == 1
    positions = repo.load_execution_positions(account_id="acct-flat")
    assert len(positions) == 1
    assert positions[0].symbol == "__FLAT__"
    assert positions[0].position_status == "FLAT"


