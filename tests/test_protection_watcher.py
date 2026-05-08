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
    assert all(call[0] != "upsert_execution_order" for call in repo.method_calls)


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


def test_watcher_retries_adopted_entry_with_manual_default_stop() -> None:
    repo = MagicMock()
    repo.load_pending_protection_watch_items.return_value = []
    repo.load_unprotected_filled_parents.return_value = [
        {
            "parent_intent_id": "adopt-parent-1",
            "exec_run_id": "adopt-run-1",
            "risk_run_id": "adopt-run-1",
            "account_id": "acct-1",
            "broker_mode": "paper",
            "symbol": "TSLA",
            "side": "buy",
            "parent_intent_role": "adopted_entry",
            "target_qty": 3.0,
            "order_type": "market",
            "limit_price": None,
            "decision_price": 100.0,
            "business_key": "adopt-buy|acct-1|broker-order-1",
            "submission_key": "adopt-submission-1",
            "fill_qty": 3.0,
            "fill_price": 100.0,
        }
    ]
    repo.load_orphan_filled_buy_positions.return_value = []

    broker = MagicMock()
    # Issue 1 (2026-05) — TP + SL sont posés en OCO atomique : on mocke
    # ``submit_oco_protection`` et on vérifie que ``submit_intent`` n'est
    # pas appelé pour les enfants.
    broker.submit_oco_protection.return_value = (
        _order("tp-1", "broker-tp-1", status=OrderStatus.SUBMITTED, order_type="limit"),
        _order("sl-1", "broker-sl-1", status=OrderStatus.SUBMITTED, order_type="stop", stop_price=95.0),
    )

    watcher = ProtectionTransitionWatcher(
        repo,
        broker_factory=lambda broker_mode, account_id: broker,
        config_factory=lambda broker_mode, account_id: ExecutionConfig(
            broker_mode=broker_mode,
            account_id=account_id,
            profit_taker_pct=0.08,
            manual_buy_stop_loss_pct=0.05,
            trailing_stop_pct=0.05,
        ),
    )

    summaries = watcher.run(account_id="acct-1")

    assert len(summaries) == 1
    assert summaries[0]["armed_missing_protections"] == 1
    assert summaries[0]["armed_missing_protections_failed"] == 0

    broker.submit_oco_protection.assert_called_once()
    parent_arg, tp_arg, stop_arg = broker.submit_oco_protection.call_args.args
    assert tp_arg.intent_role == "take_profit"
    assert stop_arg.intent_role == "initial_stop"
    assert stop_arg.stop_price == 95.0
    assert stop_arg.order_type == "stop"
    broker.submit_intent.assert_not_called()


def test_watcher_completes_only_missing_leg_for_adopted_entry() -> None:
    repo = MagicMock()
    repo.load_pending_protection_watch_items.return_value = []
    repo.load_unprotected_filled_parents.return_value = [
        {
            "parent_intent_id": "adopt-parent-2",
            "exec_run_id": "adopt-run-2",
            "risk_run_id": "adopt-run-2",
            "account_id": "acct-1",
            "broker_mode": "paper",
            "symbol": "TSLA",
            "side": "buy",
            "parent_intent_role": "adopted_entry",
            "has_open_take_profit": 1,
            "has_open_protection": 0,
            "target_qty": 3.0,
            "order_type": "market",
            "limit_price": None,
            "decision_price": 100.0,
            "business_key": "adopt-buy|acct-1|broker-order-2",
            "submission_key": "adopt-submission-2",
            "fill_qty": 3.0,
            "fill_price": 100.0,
        }
    ]
    repo.load_orphan_filled_buy_positions.return_value = []

    broker = MagicMock()
    broker.submit_intent.return_value = _order(
        "sl-2",
        "broker-sl-2",
        status=OrderStatus.SUBMITTED,
        order_type="stop",
        stop_price=95.0,
    )

    watcher = ProtectionTransitionWatcher(
        repo,
        broker_factory=lambda broker_mode, account_id: broker,
        config_factory=lambda broker_mode, account_id: ExecutionConfig(
            broker_mode=broker_mode,
            account_id=account_id,
            profit_taker_pct=0.08,
            manual_buy_stop_loss_pct=0.05,
            trailing_stop_pct=0.05,
        ),
    )

    summaries = watcher.run(account_id="acct-1")

    assert len(summaries) == 1
    assert summaries[0]["armed_missing_protections"] == 1
    broker.submit_intent.assert_called_once()
    submitted_intent = broker.submit_intent.call_args.args[0]
    assert submitted_intent.intent_role == "initial_stop"
    assert submitted_intent.stop_price == 95.0


def test_watcher_refreshes_broker_state_when_initial_scan_is_empty(monkeypatch) -> None:
    repo = MagicMock()
    repo.load_pending_protection_watch_items.return_value = []
    repo.load_unprotected_filled_parents.return_value = [
        {
            "parent_intent_id": "parent-refresh-1",
            "exec_run_id": "exec-refresh-1",
            "risk_run_id": "risk-refresh-1",
            "account_id": "acct-1",
            "broker_mode": "paper",
            "symbol": "MSFT",
            "side": "buy",
            "parent_intent_role": "adopted_entry",
            "has_open_take_profit": 0,
            "has_open_protection": 0,
            "target_qty": 5.0,
            "order_type": "market",
            "limit_price": None,
            "decision_price": 300.0,
            "business_key": "bk-parent-refresh-1",
            "submission_key": "sub-parent-refresh-1",
            "fill_qty": 5.0,
            "fill_price": 301.0,
        }
    ]
    repo.load_orphan_filled_buy_positions.return_value = []
    repo.load_execution_run_context.return_value = {
        "exec_run_id": "exec-refresh-1",
        "account_id": "acct-1",
        "broker_mode": "paper",
    }

    broker = MagicMock()
    # Issue 1 (2026-05) : pose OCO atomique TP+SL.
    broker.submit_oco_protection.return_value = (
        _order("tp-refresh-1", "broker-tp-refresh-1", status=OrderStatus.SUBMITTED, order_type="limit"),
        _order("sl-refresh-1", "broker-sl-refresh-1", status=OrderStatus.SUBMITTED, order_type="stop", stop_price=285.95),
    )

    sync_calls: list[dict[str, object]] = []

    class _FakeSynchronizer:
        def __init__(self, repo_arg, broker_arg, *, broker_mode):
            assert repo_arg is repo
            assert broker_arg is broker
            assert broker_mode == "paper"

        def sync(self, *, exec_run_id, account_id, order_limit):
            sync_calls.append({
                "exec_run_id": exec_run_id,
                "account_id": account_id,
                "order_limit": order_limit,
            })
            return {
                "orders_synced": 1,
                "fills_synced": 1,
                "unmatched_orders": 0,
                "orphan_sells_adopted": 0,
                "orphan_buys_adopted": 0,
                "positions_projected": 1,
                "lots_projected": 1,
                "broker_positions": 1,
            }

    monkeypatch.setattr(protection_watcher_module, "BrokerStateSynchronizer", _FakeSynchronizer)

    watcher = ProtectionTransitionWatcher(
        repo,
        broker_factory=lambda broker_mode, account_id: broker,
        config_factory=lambda broker_mode, account_id: ExecutionConfig(
            broker_mode=broker_mode,
            account_id=account_id,
            profit_taker_pct=0.08,
            manual_buy_stop_loss_pct=0.05,
            trailing_stop_pct=0.05,
        ),
        default_broker_mode="paper",
    )

    summaries = watcher.run(exec_run_id="exec-refresh-1")

    assert sync_calls == [{"exec_run_id": "exec-refresh-1", "account_id": "acct-1", "order_limit": 200}]
    assert len(summaries) == 1
    assert summaries[0]["armed_missing_protections"] == 1
    broker.submit_oco_protection.assert_called_once()
    broker.submit_intent.assert_not_called()


def test_watcher_does_not_count_tp_only_as_protected_when_stop_rejected() -> None:
    repo = MagicMock()
    repo.load_pending_protection_watch_items.return_value = []
    repo.load_unprotected_filled_parents.return_value = [
        {
            "parent_intent_id": "adopt-parent-403",
            "exec_run_id": "adopt-run-403",
            "risk_run_id": "adopt-run-403",
            "account_id": "acct-1",
            "broker_mode": "paper",
            "symbol": "META",
            "side": "buy",
            "parent_intent_role": "adopted_entry",
            "has_open_take_profit": 0,
            "has_open_protection": 0,
            "target_qty": 2.0,
            "order_type": "market",
            "limit_price": None,
            "decision_price": 500.0,
            "business_key": "adopt-buy|acct-1|broker-order-403",
            "submission_key": "adopt-submission-403",
            "fill_qty": 2.0,
            "fill_price": 500.0,
        }
    ]
    repo.load_orphan_filled_buy_positions.return_value = []

    broker = MagicMock()
    # Issue 1 (2026-05) : OCO atomique tenté en premier — refusé par Alpaca
    # (403). Le watcher retombe alors sur les soumissions séparées
    # ``submit_intent`` (initial_stop puis fallback trailing_stop), elles
    # aussi rejetées dans ce scénario.
    broker.submit_oco_protection.side_effect = RuntimeError("[403] Forbidden")
    broker.submit_intent.side_effect = [RuntimeError("[403] Forbidden"), RuntimeError("[403] Forbidden")]
    # Position toujours présente côté Alpaca → pas de reconciliation closed.
    broker.get_position.return_value = {"qty": "2", "symbol": "META"}

    watcher = ProtectionTransitionWatcher(
        repo,
        broker_factory=lambda broker_mode, account_id: broker,
        config_factory=lambda broker_mode, account_id: ExecutionConfig(
            broker_mode=broker_mode,
            account_id=account_id,
            profit_taker_pct=0.08,
            manual_buy_stop_loss_pct=0.05,
            trailing_stop_pct=0.05,
        ),
    )

    summaries = watcher.run(account_id="acct-1")

    assert len(summaries) == 1
    assert summaries[0]["armed_missing_protections"] == 0
    assert summaries[0]["armed_missing_protections_failed"] == 1
    submitted_roles = [call.args[0].intent_role for call in broker.submit_intent.call_args_list]
    assert submitted_roles == ["initial_stop", "trailing_stop"]
    assert all(role != "take_profit" for role in submitted_roles)
    failure_statuses = [call.kwargs["status"] for call in repo.upsert_execution_order_request_from_intent.call_args_list]
    assert failure_statuses == [OrderStatus.REJECTED, OrderStatus.REJECTED]


def test_watcher_cancels_existing_take_profit_that_blocks_missing_stop() -> None:
    repo = MagicMock()
    repo.load_pending_protection_watch_items.return_value = []
    repo.load_unprotected_filled_parents.return_value = [
        {
            "parent_intent_id": "adopt-parent-tp-blocks-sl",
            "exec_run_id": "adopt-run-tp-blocks-sl",
            "risk_run_id": "adopt-run-tp-blocks-sl",
            "account_id": "acct-1",
            "broker_mode": "paper",
            "symbol": "AAPL",
            "side": "buy",
            "parent_intent_role": "adopted_entry",
            "has_open_take_profit": 1,
            "has_open_protection": 0,
            "target_qty": 4.0,
            "order_type": "market",
            "limit_price": None,
            "decision_price": 200.0,
            "business_key": "adopt-buy|acct-1|broker-order-tp-blocks-sl",
            "submission_key": "adopt-submission-tp-blocks-sl",
            "fill_qty": 4.0,
            "fill_price": 200.0,
        }
    ]
    repo.load_orphan_filled_buy_positions.return_value = []
    repo.load_open_child_orders.return_value = [
        _order("tp-existing", "broker-tp-existing", status=OrderStatus.SUBMITTED, order_type="limit"),
    ]

    broker = MagicMock()
    broker.submit_intent.side_effect = [
        RuntimeError("[403] Forbidden"),
        RuntimeError("[403] Forbidden"),
        _order("sl-retry", "broker-sl-retry", status=OrderStatus.SUBMITTED, order_type="stop", stop_price=190.0),
    ]
    broker.cancel_broker_order.return_value = True
    # Position toujours présente côté Alpaca → la reconciliation post-403
    # ne doit PAS marquer la position comme fermée et doit laisser le
    # watcher annuler le TP existant pour réarmer le SL.
    broker.get_position.return_value = {"qty": "4", "symbol": "AAPL"}
    broker.poll_order_status.return_value = _order(
        "tp-existing",
        "broker-tp-existing",
        status=OrderStatus.CANCELED,
        order_type="limit",
    )

    watcher = ProtectionTransitionWatcher(
        repo,
        broker_factory=lambda broker_mode, account_id: broker,
        config_factory=lambda broker_mode, account_id: ExecutionConfig(
            broker_mode=broker_mode,
            account_id=account_id,
            profit_taker_pct=0.08,
            manual_buy_stop_loss_pct=0.05,
            trailing_stop_pct=0.05,
        ),
    )

    summaries = watcher.run(account_id="acct-1")

    assert summaries[0]["armed_missing_protections"] == 1
    assert summaries[0]["armed_missing_protections_failed"] == 0
    broker.cancel_broker_order.assert_called_once_with("broker-tp-existing")
    submitted_roles = [call.args[0].intent_role for call in broker.submit_intent.call_args_list]
    assert submitted_roles == ["initial_stop", "trailing_stop", "initial_stop"]


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


def test_service_treats_armed_missing_protections_as_work_for_local_ihm() -> None:
    watcher = MagicMock()
    watcher.run.return_value = [
        {
            "watched_items": 0,
            "transitioned_items": 0,
            "pending_items": 0,
            "triggered_items": 0,
            "terminal_items": 0,
            "skipped_existing_trailing": 0,
            "cancel_failed_items": 0,
            "submit_failed_items": 0,
            "armed_missing_protections": 2,
            "armed_missing_protections_failed": 1,
            "adopted_orphan_buys": 0,
            "adopted_orphan_buys_failed": 0,
        }
    ]
    watcher._repo = MagicMock()

    service = ProtectionWatcherService(
        watcher,
        ProtectionWatcherServiceConfig(
            interval_seconds=0.1,
            idle_interval_seconds=0.2,
            heartbeat_interval_seconds=60.0,
            max_iterations=1,
            stop_when_idle=True,
        ),
        sleep_fn=lambda seconds: None,
        monotonic_fn=lambda: 0.0,
    )

    summary = service.run(account_id="acct-1", limit=10)

    assert summary["status"] == "COMPLETED"
    assert summary["cycles_with_work"] == 1
    assert summary["idle_cycles"] == 0
    assert summary["last_cycle_had_work"] is True
    assert summary["armed_missing_protections"] == 2
    assert summary["armed_missing_protections_failed"] == 1


def test_parse_args_accepts_service_mode_options() -> None:
    args = parse_args([
        "--mode", "service",
        "--profit-taker-pct", "0.09",
        "--service-interval-seconds", "15",
        "--idle-interval-seconds", "45",
        "--heartbeat-interval-seconds", "120",
        "--max-iterations", "3",
        "--stop-when-idle",
        "--max-consecutive-failures", "5",
    ])

    assert args.mode == "service"
    assert args.profit_taker_pct == 0.09
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


# --------------------------------------------------------------------------
# Issue 3 (2026-05) — quand le watcher reçoit un 403 mais que la position
# n'existe plus côté Alpaca (vente manuelle hors application), il doit
# annuler les enfants orphelins, resynchroniser l'état broker et NE PAS
# incrémenter ``armed_missing_protections_failed`` (cas attendu, pas erreur).
# --------------------------------------------------------------------------
def test_watcher_reconciles_when_position_closed_outside_app(monkeypatch) -> None:
    repo = MagicMock()
    repo.load_pending_protection_watch_items.return_value = []
    repo.load_unprotected_filled_parents.return_value = [
        {
            "parent_intent_id": "parent-sold-outside",
            "exec_run_id": "exec-sold-1",
            "risk_run_id": "risk-sold-1",
            "account_id": "acct-1",
            "broker_mode": "paper",
            "symbol": "NVDA",
            "side": "buy",
            "parent_intent_role": "adopted_entry",
            "has_open_take_profit": 0,
            "has_open_protection": 0,
            "target_qty": 2.0,
            "order_type": "market",
            "limit_price": None,
            "decision_price": 800.0,
            "business_key": "bk-sold-1",
            "submission_key": "sub-sold-1",
            "fill_qty": 2.0,
            "fill_price": 800.0,
        }
    ]
    repo.load_orphan_filled_buy_positions.return_value = []
    repo.load_open_child_orders.return_value = []

    broker = MagicMock()
    # OCO refusé avec 403 : Alpaca refuse car la position n'existe plus.
    broker.submit_oco_protection.side_effect = RuntimeError("[403] insufficient qty available")
    # Vérification : Alpaca renvoie 404 sur get_position → position absente.
    broker.get_position.return_value = None

    sync_calls: list[dict[str, object]] = []

    class _FakeSynchronizer:
        def __init__(self, repo_arg, broker_arg, *, broker_mode):
            assert broker_mode == "paper"

        def sync(self, *, exec_run_id, account_id, order_limit):
            sync_calls.append({"account_id": account_id, "order_limit": order_limit})
            return {
                "orders_synced": 0, "fills_synced": 0, "unmatched_orders": 0,
                "orphan_sells_adopted": 0, "orphan_buys_adopted": 0,
                "positions_projected": 0, "lots_projected": 0, "broker_positions": 0,
            }

    monkeypatch.setattr(protection_watcher_module, "BrokerStateSynchronizer", _FakeSynchronizer)

    watcher = ProtectionTransitionWatcher(
        repo,
        broker_factory=lambda broker_mode, account_id: broker,
        config_factory=lambda broker_mode, account_id: ExecutionConfig(
            broker_mode=broker_mode,
            account_id=account_id,
            profit_taker_pct=0.08,
            manual_buy_stop_loss_pct=0.05,
            trailing_stop_pct=0.05,
        ),
    )

    summaries = watcher.run(account_id="acct-1")

    # Reconciliation silencieuse : pas de rejet comptabilisé.
    assert len(summaries) == 0 or summaries[0].get("armed_missing_protections_failed", 0) == 0
    broker.get_position.assert_called_with("NVDA")
    # Au moins un sync de reconciliation a été déclenché.
    assert any(call["account_id"] == "acct-1" for call in sync_calls)
    # Aucune retry ``submit_intent`` : on a abandonné proprement.
    broker.submit_intent.assert_not_called()
