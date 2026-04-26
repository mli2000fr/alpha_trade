"""Tests for execution_engine.protection_watcher."""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from execution_engine.config import ExecutionConfig, ProtectionWatcherServiceConfig
from execution_engine.models import BrokerOrder, OrderStatus, ProtectionWatchItem
from execution_engine import protection_watcher as protection_watcher_module
from execution_engine.protection_watcher import ProtectionTransitionWatcher, ProtectionWatcherService, parse_args


def _item() -> ProtectionWatchItem:
    return ProtectionWatchItem(
        source_exec_run_id="exec-1",
        risk_run_id="risk-1",
        trade_date=date(2026, 4, 26),
        account_id="acct-1",
        broker_mode="paper",
        symbol="AAPL",
        parent_intent_id="parent-1",
        initial_stop_intent_id="stop-1",
        initial_stop_broker_order_id="broker-stop-1",
        fill_qty=100.0,
        fill_price=150.0,
        stop_price_initial=140.0,
        risk_per_share=10.0,
        initial_risk_dollars=1000.0,
        target_notional=15000.0,
    )


def _order(intent_id: str, broker_order_id: str, *, status: str, order_type: str, stop_price: float | None = None, trail_percent: float | None = None) -> BrokerOrder:
    now = datetime.now(timezone.utc)
    return BrokerOrder(
        broker_order_id=broker_order_id,
        client_order_id=f"client-{broker_order_id}",
        intent_id=intent_id,
        symbol="AAPL",
        side="sell" if order_type != "market" else "buy",
        qty=100.0,
        filled_qty=0.0,
        avg_fill_price=None,
        status=status,
        order_type=order_type,
        limit_price=None,
        stop_price=stop_price,
        trail_percent=trail_percent,
        created_at=now,
        updated_at=now,
    )


def test_watcher_promotes_initial_stop_to_trailing_when_trigger_hit() -> None:
    repo = MagicMock()
    repo.load_pending_protection_watch_items.return_value = [_item()]
    repo.load_open_child_orders.return_value = []

    broker = MagicMock()
    broker.poll_order_status.side_effect = [
        _order("stop-1", "broker-stop-1", status=OrderStatus.SUBMITTED, order_type="stop", stop_price=140.0),
        _order("stop-1", "broker-stop-1", status=OrderStatus.CANCELED, order_type="stop", stop_price=140.0),
    ]
    broker.get_latest_market_price.return_value = 161.0
    broker.cancel_broker_order.return_value = True
    broker.submit_intent.return_value = _order("trail-1", "broker-trail-1", status=OrderStatus.SUBMITTED, order_type="trailing_stop", trail_percent=6.67)

    watcher = ProtectionTransitionWatcher(
        repo,
        broker_factory=lambda broker_mode, account_id: broker,
        config_factory=lambda broker_mode, account_id: ExecutionConfig(
            broker_mode=broker_mode,
            account_id=account_id,
            trailing_activation_trigger="multiple_r",
            trailing_activation_r_multiple=1.0,
            trailing_stop_pct=0.05,
        ),
    )

    summaries = watcher.run(exec_run_id="exec-1")

    assert len(summaries) == 1
    assert summaries[0]["transitioned_items"] == 1
    assert summaries[0]["triggered_items"] == 1
    assert broker.cancel_broker_order.called
    assert broker.submit_intent.called
    event_types = [call.args[0]["event_type"] for call in repo.insert_execution_event.call_args_list]
    assert "PROTECTION_TRIGGER_HIT" in event_types
    assert "PROTECTION_TRANSITION_COMPLETED" in event_types
    persisted_request_ids = [call.args[0].intent_id for call in repo.upsert_execution_order_request_from_intent.call_args_list]
    assert persisted_request_ids[0] == "stop-1"
    assert any(call.args[0].intent_role == "trailing_stop" for call in repo.upsert_execution_order_request_from_intent.call_args_list)
    assert all(call.kwargs["account_id"] == "acct-1" for call in repo.upsert_execution_order_request_from_intent.call_args_list)
    assert repo.upsert_execution_broker_order.called


def test_watcher_keeps_item_pending_when_trigger_not_reached() -> None:
    repo = MagicMock()
    repo.load_pending_protection_watch_items.return_value = [_item()]

    broker = MagicMock()
    broker.poll_order_status.return_value = _order("stop-1", "broker-stop-1", status=OrderStatus.SUBMITTED, order_type="stop", stop_price=140.0)
    broker.get_latest_market_price.return_value = 155.0

    watcher = ProtectionTransitionWatcher(
        repo,
        broker_factory=lambda broker_mode, account_id: broker,
        config_factory=lambda broker_mode, account_id: ExecutionConfig(
            broker_mode=broker_mode,
            account_id=account_id,
            trailing_activation_trigger="multiple_r",
            trailing_activation_r_multiple=2.0,
            trailing_stop_pct=0.05,
        ),
    )

    summaries = watcher.run(exec_run_id="exec-1")

    assert len(summaries) == 1
    assert summaries[0]["pending_items"] == 1
    broker.cancel_broker_order.assert_not_called()
    broker.submit_intent.assert_not_called()


def test_service_stops_cleanly_when_idle_mode_requested() -> None:
    watcher = MagicMock()
    watcher.run.return_value = []
    sleep_calls: list[float] = []

    service = ProtectionWatcherService(
        watcher,
        ProtectionWatcherServiceConfig(
            interval_seconds=0.1,
            idle_interval_seconds=0.2,
            heartbeat_interval_seconds=60.0,
            max_iterations=10,
            stop_when_idle=True,
        ),
        sleep_fn=sleep_calls.append,
        monotonic_fn=lambda: 0.0,
    )

    summary = service.run(exec_run_id="exec-1", account_id="acct-1", limit=25)

    assert summary["status"] == "COMPLETED"
    assert summary["iterations"] == 1
    assert summary["idle_cycles"] == 1
    assert summary["cycles_with_work"] == 0
    assert summary["watched_items"] == 0
    assert sleep_calls == []
    watcher.run.assert_called_once_with(exec_run_id="exec-1", account_id="acct-1", limit=25)


def test_service_stops_after_max_consecutive_failures() -> None:
    watcher = MagicMock()
    watcher.run.side_effect = [RuntimeError("boom"), RuntimeError("boom")]
    sleep_calls: list[float] = []

    service = ProtectionWatcherService(
        watcher,
        ProtectionWatcherServiceConfig(
            interval_seconds=0.1,
            idle_interval_seconds=0.2,
            heartbeat_interval_seconds=60.0,
            max_consecutive_failures=2,
        ),
        sleep_fn=sleep_calls.append,
        monotonic_fn=lambda: 0.0,
    )

    summary = service.run(account_id="acct-1", limit=10)

    assert summary["status"] == "FAILED"
    assert summary["iterations"] == 2
    assert summary["consecutive_failures"] == 2
    assert sleep_calls == [0.2]


def test_parse_args_accepts_service_mode_options() -> None:
    args = parse_args([
        "--mode", "service",
        "--service-interval-seconds", "15",
        "--idle-interval-seconds", "45",
        "--heartbeat-interval-seconds", "120",
        "--max-iterations", "3",
        "--stop-when-idle",
        "--max-consecutive-failures", "5",
    ])

    assert args.mode == "service"
    assert args.service_interval_seconds == 15.0
    assert args.idle_interval_seconds == 45.0
    assert args.heartbeat_interval_seconds == 120.0
    assert args.max_iterations == 3
    assert args.stop_when_idle is True
    assert args.max_consecutive_failures == 5


def test_service_persists_health_summary_updates(monkeypatch) -> None:
    watcher = MagicMock()
    watcher._repo = MagicMock()
    watcher._repo.engine = MagicMock()
    watcher.run.side_effect = [
        [{"watched_items": 2, "transitioned_items": 1, "pending_items": 1, "triggered_items": 1, "terminal_items": 0, "skipped_existing_trailing": 0, "cancel_failed_items": 0, "submit_failed_items": 0}],
        [],
    ]
    persisted: list[dict[str, object]] = []
    emitted: list[dict[str, object]] = []

    monkeypatch.setattr(
        protection_watcher_module,
        "persist_run_business_summary",
        lambda **kwargs: persisted.append(kwargs) or 1,
    )
    monkeypatch.setattr(
        protection_watcher_module,
        "emit_run_summary",
        lambda summary: emitted.append(dict(summary)),
    )

    service = ProtectionWatcherService(
        watcher,
        ProtectionWatcherServiceConfig(
            interval_seconds=0.1,
            idle_interval_seconds=0.2,
            heartbeat_interval_seconds=60.0,
            max_iterations=2,
        ),
        sleep_fn=lambda seconds: None,
        monotonic_fn=lambda: 0.0,
    )

    summary = service.run(exec_run_id="exec-1", account_id="acct-1", limit=15)

    assert summary["status"] == "COMPLETED"
    assert summary["iterations"] == 2
    assert summary["cycles_with_work"] == 1
    assert summary["idle_cycles"] == 1
    assert summary["transitioned_items"] == 1
    assert summary["heartbeat_count"] == 1
    assert summary["service_scope"] == "exec-1"
    assert summary["last_cycle_had_work"] is False
    assert persisted
    assert persisted[-1]["step_key"] == "execution_protection_watch_service"
    assert persisted[-1]["run_kind"] == "service"
    assert persisted[-1]["entity_run_id"] == "exec-1"
    assert persisted[-1]["account_id"] == "acct-1"
    assert emitted[-1]["run_id"] == summary["run_id"]


def test_service_health_summary_uses_account_scope_when_exec_run_not_provided(monkeypatch) -> None:
    watcher = MagicMock()
    watcher._repo = MagicMock()
    watcher._repo.engine = MagicMock()
    watcher.run.return_value = []
    persisted: list[dict[str, object]] = []

    monkeypatch.setattr(
        protection_watcher_module,
        "persist_run_business_summary",
        lambda **kwargs: persisted.append(kwargs) or 1,
    )
    monkeypatch.setattr(protection_watcher_module, "emit_run_summary", lambda summary: None)

    service = ProtectionWatcherService(
        watcher,
        ProtectionWatcherServiceConfig(
            interval_seconds=0.1,
            idle_interval_seconds=0.2,
            heartbeat_interval_seconds=60.0,
            max_iterations=1,
        ),
        sleep_fn=lambda seconds: None,
        monotonic_fn=lambda: 0.0,
    )

    summary = service.run(account_id="acct-1", limit=8)

    assert summary["service_scope"] == "acct-1"
    assert persisted[-1]["entity_run_id"] == "watcher-service:acct-1"


