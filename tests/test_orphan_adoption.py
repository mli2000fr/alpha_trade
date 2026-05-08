"""Tests Sprint 2026-05 — adoption d'ordres / positions orphelins.

Couvre :

* ``adopt_orphan_sell`` (Q5 / Q6 du FAQ opérateur — vente manuelle hors
  Alpha Trade depuis le site/app Alpaca ou le bouton « Vendre tout »).
* ``adopt_orphan_buy`` à partir d'un ``raw_order`` broker (Q8 — achat manuel
  exécuté hors pipeline) et à partir d'une position broker pure (cas
  watcher quand l'ordre d'origine est trop ancien pour être relu).
* Idempotence des deux entrées (ne pas créer de doublons sur un re-run).
* Persistance d'un événement ``ORPHAN_ADOPTED`` rattaché à un
  ``execution_runs`` synthétique préfixé ``adopt-``.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from execution_engine.db_io import ExecutionRepository
from execution_engine.models import BrokerOrder, EventType, IntentRole, OrderIntent, OrderStatus
from execution_engine.orphan_adoption import (
    ADOPTION_RUN_PREFIX,
    adopt_orphan_buy,
    adopt_orphan_sell,
)


@pytest.fixture()
def engine():
    e = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with e.begin() as conn:
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
            CREATE TABLE execution_position_lots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_id VARCHAR(64) UNIQUE,
                account_id VARCHAR(64) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                opened_qty DOUBLE NOT NULL,
                remaining_qty DOUBLE NOT NULL,
                entry_price DOUBLE NOT NULL,
                opened_at TIMESTAMP,
                open_exec_run_id VARCHAR(32),
                open_request_id VARCHAR(32),
                open_fill_id VARCHAR(32),
                lot_status VARCHAR(20) NOT NULL,
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
            CREATE TABLE broker_positions_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exec_run_id VARCHAR(32),
                broker_mode VARCHAR(10),
                symbol VARCHAR(20),
                qty DOUBLE,
                avg_entry_price DOUBLE,
                market_value DOUBLE,
                unrealized_pnl DOUBLE,
                created_at TIMESTAMP,
                account_id VARCHAR(64)
            )
        """))
    try:
        yield e
    finally:
        e.dispose()


@pytest.fixture()
def repo(engine):
    return ExecutionRepository(engine=engine)


def _sell_payload(**overrides):
    payload = {
        "id": "broker-sell-1",
        "client_order_id": "ihm-sell-1",
        "symbol": "AAPL",
        "side": "sell",
        "qty": "10",
        "filled_qty": "10",
        "filled_avg_price": "152.50",
        "status": "filled",
        "type": "market",
        "submitted_at": datetime(2026, 5, 7, 14, 30, tzinfo=timezone.utc).isoformat(),
        "filled_at": datetime(2026, 5, 7, 14, 30, 1, tzinfo=timezone.utc).isoformat(),
    }
    payload.update(overrides)
    return payload


def _buy_payload(**overrides):
    payload = {
        "id": "broker-buy-1",
        "client_order_id": "manual-buy-1",
        "symbol": "MSFT",
        "side": "buy",
        "qty": "5",
        "filled_qty": "5",
        "filled_avg_price": "320.10",
        "status": "filled",
        "type": "market",
        "submitted_at": datetime(2026, 5, 7, 14, 0, tzinfo=timezone.utc).isoformat(),
        "filled_at": datetime(2026, 5, 7, 14, 0, 1, tzinfo=timezone.utc).isoformat(),
    }
    payload.update(overrides)
    return payload


def _fetch_one(engine, sql: str, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).mappings().first()


def _fetch_all(engine, sql: str, **params):
    with engine.connect() as conn:
        return list(conn.execute(text(sql), params).mappings())


class TestAdoptOrphanSell:
    def test_writes_intent_broker_order_fill_and_event(self, engine, repo) -> None:
        result = adopt_orphan_sell(
            repo,
            broker_mode="paper",
            account_id="acct-1",
            raw_order=_sell_payload(),
        )

        assert result is not None
        assert result.trigger == "manual_sell"
        assert result.intent.intent_role == IntentRole.ADOPTED_EXIT
        assert result.intent.side == "sell"
        assert result.fill is not None
        assert result.fill.filled_qty == 10.0
        assert result.fill.avg_fill_price == 152.50

        request_row = _fetch_one(
            engine,
            "SELECT * FROM execution_order_requests WHERE account_id = :a",
            a="acct-1",
        )
        assert request_row is not None
        assert request_row["intent_role"] == IntentRole.ADOPTED_EXIT
        assert request_row["status"] == OrderStatus.FILLED
        assert request_row["business_key"].startswith("adopt-sell|acct-1|")

        broker_row = _fetch_one(
            engine,
            "SELECT * FROM execution_broker_orders WHERE broker_order_id = :b",
            b="broker-sell-1",
        )
        assert broker_row is not None
        assert broker_row["filled_qty"] == 10.0
        assert broker_row["normalized_status"] == OrderStatus.FILLED

        fill_rows = _fetch_all(
            engine,
            "SELECT * FROM execution_broker_fills WHERE broker_order_id = :b",
            b="broker-sell-1",
        )
        assert len(fill_rows) == 1
        assert fill_rows[0]["filled_qty"] == 10.0

        run_row = _fetch_one(
            engine,
            "SELECT * FROM execution_runs WHERE exec_run_id = :r",
            r=result.intent.exec_run_id,
        )
        assert run_row is not None
        assert run_row["exec_run_id"].startswith(f"{ADOPTION_RUN_PREFIX}-")
        assert run_row["account_id"] == "acct-1"

        event_row = _fetch_one(
            engine,
            "SELECT * FROM execution_events WHERE event_type = :t",
            t=EventType.ORPHAN_ADOPTED,
        )
        assert event_row is not None
        assert event_row["intent_id"] == result.intent.intent_id
        assert "AAPL" in event_row["message"]

    def test_skipped_when_payload_missing_broker_order_id(self, repo) -> None:
        assert adopt_orphan_sell(
            repo,
            broker_mode="paper",
            account_id="acct-1",
            raw_order=_sell_payload(id=""),
        ) is None

    def test_skipped_when_filled_qty_is_zero(self, repo) -> None:
        assert adopt_orphan_sell(
            repo,
            broker_mode="paper",
            account_id="acct-1",
            raw_order=_sell_payload(qty="0", filled_qty="0"),
        ) is None

    def test_idempotent_on_repeat_adoption(self, engine, repo) -> None:
        payload = _sell_payload()
        first = adopt_orphan_sell(repo, broker_mode="paper", account_id="acct-1", raw_order=payload)
        second = adopt_orphan_sell(repo, broker_mode="paper", account_id="acct-1", raw_order=payload)

        assert first is not None and second is not None
        # Même intent_id (dérivé du business_key déterministe) -> pas de doublon en DB.
        assert first.intent.intent_id == second.intent.intent_id

        request_rows = _fetch_all(
            engine,
            "SELECT * FROM execution_order_requests WHERE account_id = :a",
            a="acct-1",
        )
        assert len(request_rows) == 1

        broker_rows = _fetch_all(
            engine,
            "SELECT * FROM execution_broker_orders WHERE broker_order_id = :b",
            b="broker-sell-1",
        )
        assert len(broker_rows) == 1


class TestAdoptOrphanBuy:
    def test_from_raw_order_creates_adopted_entry(self, engine, repo) -> None:
        result = adopt_orphan_buy(
            repo,
            broker_mode="paper",
            account_id="acct-2",
            raw_order=_buy_payload(),
        )

        assert result is not None
        assert result.trigger == "manual_buy"
        assert result.intent.intent_role == IntentRole.ADOPTED_ENTRY
        assert result.intent.side == "buy"
        assert result.fill is not None
        assert result.fill.avg_fill_price == 320.10

        request_row = _fetch_one(
            engine,
            "SELECT * FROM execution_order_requests WHERE account_id = :a",
            a="acct-2",
        )
        assert request_row is not None
        assert request_row["intent_role"] == IntentRole.ADOPTED_ENTRY
        assert request_row["business_key"].startswith("adopt-buy|acct-2|broker-buy-1")

    def test_from_broker_position_creates_synthetic_broker_order_id(self, engine, repo) -> None:
        result = adopt_orphan_buy(
            repo,
            broker_mode="paper",
            account_id="acct-3",
            broker_position={
                "symbol": "TSLA",
                "qty": 7.0,
                "avg_entry_price": 240.0,
            },
        )

        assert result is not None
        assert result.trigger == "watcher_orphan_buy"
        assert result.broker_order.broker_order_id.startswith("adopt-pos-")
        assert result.intent.symbol == "TSLA"
        assert result.intent.qty == 7.0
        assert result.fill is not None

        broker_row = _fetch_one(
            engine,
            "SELECT * FROM execution_broker_orders WHERE broker_order_id = :b",
            b=result.broker_order.broker_order_id,
        )
        assert broker_row is not None
        assert broker_row["normalized_status"] == OrderStatus.FILLED
        assert broker_row["filled_qty"] == 7.0

    def test_returns_none_when_no_input_provided(self, repo) -> None:
        assert adopt_orphan_buy(
            repo,
            broker_mode="paper",
            account_id="acct-x",
        ) is None

    def test_skipped_when_position_payload_incomplete(self, repo) -> None:
        assert adopt_orphan_buy(
            repo,
            broker_mode="paper",
            account_id="acct-x",
            broker_position={"symbol": "NVDA", "qty": 0, "avg_entry_price": 100.0},
        ) is None
        assert adopt_orphan_buy(
            repo,
            broker_mode="paper",
            account_id="acct-x",
            broker_position={"symbol": "NVDA", "qty": 4.0, "avg_entry_price": 0.0},
        ) is None

    def test_idempotent_on_repeat_adoption_from_position(self, engine, repo) -> None:
        position = {"symbol": "TSLA", "qty": 7.0, "avg_entry_price": 240.0}
        first = adopt_orphan_buy(repo, broker_mode="paper", account_id="acct-3", broker_position=position)
        second = adopt_orphan_buy(repo, broker_mode="paper", account_id="acct-3", broker_position=position)

        assert first is not None and second is not None
        assert first.broker_order.broker_order_id == second.broker_order.broker_order_id
        request_rows = _fetch_all(
            engine,
            "SELECT * FROM execution_order_requests WHERE account_id = :a",
            a="acct-3",
        )
        assert len(request_rows) == 1

    def test_adopted_entry_is_returned_by_unprotected_filled_parents(self, repo) -> None:
        result = adopt_orphan_buy(
            repo,
            broker_mode="paper",
            account_id="acct-4",
            broker_position={
                "symbol": "TSLA",
                "qty": 7.0,
                "avg_entry_price": 240.0,
            },
        )

        assert result is not None

        rows = repo.load_unprotected_filled_parents(account_id="acct-4")

        assert len(rows) == 1
        assert rows[0]["symbol"] == "TSLA"
        assert rows[0]["parent_intent_id"] == result.intent.intent_id
        assert rows[0]["parent_intent_role"] == IntentRole.ADOPTED_ENTRY

    def test_adopted_entry_is_returned_even_when_synthetic_execution_run_is_missing(self, engine, repo) -> None:
        result = adopt_orphan_buy(
            repo,
            broker_mode="paper",
            account_id="acct-4b",
            broker_position={
                "symbol": "MSFT",
                "qty": 2.0,
                "avg_entry_price": 300.0,
            },
        )

        assert result is not None
        repo.rebuild_execution_position_lots(account_id="acct-4b")
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM execution_runs WHERE exec_run_id = :run_id"),
                {"run_id": result.intent.exec_run_id},
            )

        rows = repo.load_unprotected_filled_parents(account_id="acct-4b")

        assert len(rows) == 1
        assert rows[0]["symbol"] == "MSFT"
        assert rows[0]["parent_intent_id"] == result.intent.intent_id
        assert rows[0]["broker_mode"] == "paper"
        assert rows[0]["fill_qty"] == pytest.approx(2.0)

    def test_unprotected_parents_are_limited_to_latest_positive_broker_snapshot(self, engine, repo) -> None:
        stale = adopt_orphan_buy(
            repo,
            broker_mode="paper",
            account_id="acct-4c",
            broker_position={"symbol": "MSFT", "qty": 2.0, "avg_entry_price": 300.0},
        )
        current = adopt_orphan_buy(
            repo,
            broker_mode="paper",
            account_id="acct-4c",
            broker_position={"symbol": "AAPL", "qty": 1.0, "avg_entry_price": 280.0},
        )

        assert stale is not None and current is not None
        repo.rebuild_execution_position_lots(account_id="acct-4c")
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO broker_positions_snapshots (
                    exec_run_id, broker_mode, symbol, qty, avg_entry_price,
                    market_value, unrealized_pnl, created_at, account_id
                ) VALUES (
                    'snap-1', 'paper', 'AAPL', 1.0, 281.0,
                    281.0, 1.0, :created_at, 'acct-4c'
                )
            """), {"created_at": datetime(2026, 5, 8, 16, 0, tzinfo=timezone.utc)})

        rows = repo.load_unprotected_filled_parents(account_id="acct-4c")

        assert len(rows) == 1
        assert rows[0]["symbol"] == "AAPL"
        assert rows[0]["parent_intent_id"] == current.intent.intent_id
        assert rows[0]["fill_qty"] == pytest.approx(1.0)
        assert rows[0]["fill_price"] == pytest.approx(281.0)

    def test_adopted_entry_with_open_take_profit_is_still_returned_to_complete_stop(self, repo) -> None:
        result = adopt_orphan_buy(
            repo,
            broker_mode="paper",
            account_id="acct-5",
            broker_position={
                "symbol": "TSLA",
                "qty": 7.0,
                "avg_entry_price": 240.0,
            },
        )

        assert result is not None

        tp_intent = OrderIntent(
            intent_id="tp-req-1",
            risk_run_id=result.intent.exec_run_id,
            exec_run_id=result.intent.exec_run_id,
            symbol="TSLA",
            side="sell",
            qty=7.0,
            order_type="limit",
            limit_price=259.2,
            trail_percent=None,
            broker_mode="paper",
            parent_intent_id=result.intent.intent_id,
            intent_role=IntentRole.TAKE_PROFIT,
            idempotency_key="tp-bk-1",
            decision_price=240.0,
            stop_price=None,
            submission_key="tp-sub-1",
        )
        tp_order = BrokerOrder(
            broker_order_id="broker-tp-1",
            client_order_id="tp-sub-1",
            intent_id="tp-req-1",
            symbol="TSLA",
            side="sell",
            qty=7.0,
            filled_qty=0.0,
            avg_fill_price=None,
            status=OrderStatus.SUBMITTED,
            order_type="limit",
            limit_price=259.2,
            stop_price=None,
            trail_percent=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        repo.upsert_execution_order_request_from_intent(tp_intent, account_id="acct-5", status=OrderStatus.SUBMITTED)
        repo.upsert_execution_broker_order(tp_intent, tp_order, account_id="acct-5")

        rows = repo.load_unprotected_filled_parents(account_id="acct-5")

        assert len(rows) == 1
        assert rows[0]["parent_intent_id"] == result.intent.intent_id
        assert rows[0]["has_open_take_profit"] == 1
        assert rows[0]["has_open_protection"] == 0

    def test_closed_entry_is_not_returned_by_unprotected_filled_parents(self, repo) -> None:
        result = adopt_orphan_buy(
            repo,
            broker_mode="paper",
            account_id="acct-6",
            raw_order=_buy_payload(
                id="broker-buy-tsla-1",
                client_order_id="manual-buy-tsla-1",
                symbol="TSLA",
                qty="7",
                filled_qty="7",
                filled_avg_price="240.0",
            ),
        )

        assert result is not None

        adopt_orphan_sell(
            repo,
            broker_mode="paper",
            account_id="acct-6",
            raw_order=_sell_payload(
                id="broker-sell-tsla-1",
                client_order_id="manual-sell-tsla-1",
                symbol="TSLA",
                qty="7",
                filled_qty="7",
                filled_avg_price="245.0",
            ),
        )
        repo.rebuild_execution_position_lots(account_id="acct-6")

        rows = repo.load_unprotected_filled_parents(account_id="acct-6")

        assert rows == []

    def test_partially_closed_entry_uses_remaining_open_qty(self, repo) -> None:
        result = adopt_orphan_buy(
            repo,
            broker_mode="paper",
            account_id="acct-7",
            raw_order=_buy_payload(
                id="broker-buy-tsla-2",
                client_order_id="manual-buy-tsla-2",
                symbol="TSLA",
                qty="7",
                filled_qty="7",
                filled_avg_price="240.0",
            ),
        )

        assert result is not None

        adopt_orphan_sell(
            repo,
            broker_mode="paper",
            account_id="acct-7",
            raw_order=_sell_payload(
                id="broker-sell-tsla-2",
                client_order_id="manual-sell-tsla-2",
                symbol="TSLA",
                qty="2",
                filled_qty="2",
                filled_avg_price="245.0",
            ),
        )
        repo.rebuild_execution_position_lots(account_id="acct-7")

        rows = repo.load_unprotected_filled_parents(account_id="acct-7")

        assert len(rows) == 1
        assert rows[0]["parent_intent_id"] == result.intent.intent_id
        assert rows[0]["fill_qty"] == pytest.approx(5.0)
        assert rows[0]["fill_price"] == pytest.approx(240.0)

