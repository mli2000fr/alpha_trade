"""Watcher post-run dédié à la promotion stop initial -> trailing dynamique."""
from __future__ import annotations

import argparse
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable

from common.utils import configure_root_logging
from database.run_business_summaries import emit_run_summary, persist_run_business_summary
from execution_engine.audit import build_run_id, make_event
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.config import ExecutionConfig, ProtectionWatcherServiceConfig
from execution_engine.db_io import ExecutionRepository
from execution_engine.models import (
    BrokerOrder,
    EventType,
    IntentRole,
    OrderIntent,
    OrderStatus,
    ProtectionWatchItem,
)
from execution_engine.order_intents import (
    build_initial_stop_intent,
    build_take_profit_intent,
    build_trailing_stop_intent,
    intent_to_alpaca_payload,
    resolve_trailing_activation_price,
)
from service.alpaca.trading_client import AlpacaTradingClient

LOGGER = logging.getLogger(__name__)


def _build_summary(
    metrics: dict[str, Any],
    *,
    watch_run_id: str,
    started_at: datetime,
    finished_at: datetime,
) -> dict[str, Any]:
    return {
        "run_id": watch_run_id,
        "source_exec_run_id": metrics.get("source_exec_run_id"),
        "trade_date": metrics.get("trade_date"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "status": metrics.get("status", "COMPLETED"),
        "watched_items": int(metrics.get("watched_items", 0) or 0),
        "triggered_items": int(metrics.get("triggered_items", 0) or 0),
        "transitioned_items": int(metrics.get("transitioned_items", 0) or 0),
        "pending_items": int(metrics.get("pending_items", 0) or 0),
        "terminal_items": int(metrics.get("terminal_items", 0) or 0),
        "skipped_existing_trailing": int(metrics.get("skipped_existing_trailing", 0) or 0),
        "cancel_failed_items": int(metrics.get("cancel_failed_items", 0) or 0),
        "trigger_check_count": int(metrics.get("trigger_check_count", 0) or 0),
        "submit_failed_items": int(metrics.get("submit_failed_items", 0) or 0),
        "armed_missing_protections": int(metrics.get("armed_missing_protections", 0) or 0),
        "armed_missing_protections_failed": int(metrics.get("armed_missing_protections_failed", 0) or 0),
        "broker_mode": metrics.get("broker_mode"),
        "account_id": metrics.get("account_id"),
    }


def _build_service_summary(
    metrics: dict[str, Any],
    *,
    service_run_id: str,
    started_at: datetime,
    finished_at: datetime | None,
    exec_run_id: str | None,
    account_id: str | None,
    limit: int,
) -> dict[str, Any]:
    effective_finished_at = finished_at or datetime.now()
    return {
        "run_id": service_run_id,
        "mode": "service",
        "exec_run_id": exec_run_id,
        "account_id": account_id,
        "limit": limit,
        "service_scope": metrics.get("service_scope"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds") if finished_at is not None else None,
        "duration_seconds": round((effective_finished_at - started_at).total_seconds(), 2),
        "status": metrics.get("status", "COMPLETED"),
        "iterations": int(metrics.get("iterations", 0) or 0),
        "cycles_with_work": int(metrics.get("cycles_with_work", 0) or 0),
        "idle_cycles": int(metrics.get("idle_cycles", 0) or 0),
        "heartbeat_count": int(metrics.get("heartbeat_count", 0) or 0),
        "consecutive_failures": int(metrics.get("consecutive_failures", 0) or 0),
        "max_consecutive_failures": int(metrics.get("max_consecutive_failures", 0) or 0),
        "interval_seconds": float(metrics.get("interval_seconds", 0.0) or 0.0),
        "idle_interval_seconds": float(metrics.get("idle_interval_seconds", 0.0) or 0.0),
        "heartbeat_interval_seconds": float(metrics.get("heartbeat_interval_seconds", 0.0) or 0.0),
        "stop_when_idle": bool(metrics.get("stop_when_idle", False)),
        "max_iterations": metrics.get("max_iterations"),
        "watched_items": int(metrics.get("watched_items", 0) or 0),
        "triggered_items": int(metrics.get("triggered_items", 0) or 0),
        "transitioned_items": int(metrics.get("transitioned_items", 0) or 0),
        "pending_items": int(metrics.get("pending_items", 0) or 0),
        "terminal_items": int(metrics.get("terminal_items", 0) or 0),
        "skipped_existing_trailing": int(metrics.get("skipped_existing_trailing", 0) or 0),
        "cancel_failed_items": int(metrics.get("cancel_failed_items", 0) or 0),
        "submit_failed_items": int(metrics.get("submit_failed_items", 0) or 0),
        "last_heartbeat_at": metrics.get("last_heartbeat_at"),
        "last_cycle_at": metrics.get("last_cycle_at"),
        "last_cycle_had_work": bool(metrics.get("last_cycle_had_work", False)),
        "last_cycle_watched_items": int(metrics.get("last_cycle_watched_items", 0) or 0),
        "last_cycle_transitioned_items": int(metrics.get("last_cycle_transitioned_items", 0) or 0),
    }


class ProtectionTransitionWatcher:
    """Surveille après coup les stops initiaux actifs pour les promouvoir en trailing."""

    def __init__(
        self,
        repo: ExecutionRepository,
        broker_factory: Callable[[str, str | None], BrokerAdapter],
        config_factory: Callable[[str, str | None], ExecutionConfig],
    ) -> None:
        self._repo = repo
        self._broker_factory = broker_factory
        self._config_factory = config_factory
        self._broker_cache: dict[tuple[str, str | None], BrokerAdapter] = {}
        self._config_cache: dict[tuple[str, str | None], ExecutionConfig] = {}

    def run(
        self,
        *,
        exec_run_id: str | None = None,
        account_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        started_at = datetime.now()
        items = self._repo.load_pending_protection_watch_items(exec_run_id=exec_run_id, account_id=account_id, limit=limit)
        metrics_by_run: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "status": "COMPLETED",
                "watched_items": 0,
                "triggered_items": 0,
                "transitioned_items": 0,
                "pending_items": 0,
                "terminal_items": 0,
                "skipped_existing_trailing": 0,
                "cancel_failed_items": 0,
                "trigger_check_count": 0,
                "submit_failed_items": 0,
                "armed_missing_protections": 0,
                "armed_missing_protections_failed": 0,
            }
        )

        for item in items:
            run_metrics = metrics_by_run[item.source_exec_run_id]
            run_metrics["source_exec_run_id"] = item.source_exec_run_id
            run_metrics["trade_date"] = item.trade_date.isoformat()
            run_metrics["broker_mode"] = item.broker_mode
            run_metrics["account_id"] = item.account_id
            run_metrics["watched_items"] += 1
            self._process_item(item, run_metrics)

        # ------------------------------------------------------------------
        # Sprint S26 (gap P3) — Filet de sécurité TP/SL.
        # Détecte les ENTRÉES FILLED chez le broker qui n'ont AUCUN
        # take-profit ni stop ouvert (cas overnight où Execution n'a pas pu
        # appeler `_submit_children`). On arme les enfants manquants ici.
        # ------------------------------------------------------------------
        try:
            unprotected_rows = self._repo.load_unprotected_filled_parents(
                exec_run_id=exec_run_id,
                account_id=account_id,
                limit=max(limit, 200),
            )
        except Exception:
            LOGGER.warning("load_unprotected_filled_parents failed", exc_info=True)
            unprotected_rows = []

        for row in unprotected_rows:
            source_exec_run_id = str(row.get("exec_run_id") or "")
            run_metrics = metrics_by_run[source_exec_run_id]
            run_metrics.setdefault("source_exec_run_id", source_exec_run_id)
            run_metrics.setdefault("trade_date", None)
            run_metrics["broker_mode"] = str(row.get("broker_mode") or run_metrics.get("broker_mode") or "paper")
            run_metrics["account_id"] = str(row.get("account_id") or run_metrics.get("account_id") or "default")
            try:
                self._arm_missing_protections(row, run_metrics)
            except Exception:
                LOGGER.warning(
                    "Échec armement protections manquantes pour %s",
                    row.get("symbol"), exc_info=True,
                )
                run_metrics["armed_missing_protections_failed"] = (
                    int(run_metrics.get("armed_missing_protections_failed", 0) or 0) + 1
                )

        summaries: list[dict[str, Any]] = []
        finished_at = datetime.now()
        for source_exec_run_id, run_metrics in metrics_by_run.items():
            watch_run_id = f"watch-{build_run_id()}"
            summary = _build_summary(run_metrics, watch_run_id=watch_run_id, started_at=started_at, finished_at=finished_at)
            summaries.append(summary)
            try:
                persist_run_business_summary(
                    summary=summary,
                    step_key="execution_protection_watch",
                    run_kind="step",
                    status=str(summary.get("status", "") or "") or None,
                    summary_run_id=watch_run_id,
                    source_run_id=watch_run_id,
                    entity_run_id=source_exec_run_id,
                    parent_summary_run_id=source_exec_run_id,
                    account_id=run_metrics.get("account_id"),
                    trade_date=summary.get("trade_date"),
                    started_at=summary.get("started_at"),
                    finished_at=summary.get("finished_at"),
                    engine=self._repo.engine,
                )
            except Exception:
                LOGGER.debug("Persistance run_business_summaries indisponible pour le watcher protections.", exc_info=True)
            emit_run_summary(summary)
        return summaries

    def _config_for(self, broker_mode: str, account_id: str | None) -> ExecutionConfig:
        key = (broker_mode, account_id)
        if key not in self._config_cache:
            self._config_cache[key] = self._config_factory(broker_mode, account_id)
        return self._config_cache[key]

    def _broker_for(self, broker_mode: str, account_id: str | None) -> BrokerAdapter:
        key = (broker_mode, account_id)
        if key not in self._broker_cache:
            self._broker_cache[key] = self._broker_factory(broker_mode, account_id)
        return self._broker_cache[key]

    def _persist_event(self, event) -> None:
        try:
            from execution_engine.audit import event_to_db_dict

            self._repo.insert_execution_event(event_to_db_dict(event))
        except Exception:
            LOGGER.debug("Persistance event watcher impossible: %s", event.event_type, exc_info=True)

    def _persist_order_state(self, intent: OrderIntent, order: BrokerOrder, *, account_id: str | None = None) -> None:
        resolved_account_id = account_id or "default"
        try:
            self._repo.upsert_execution_order_request_from_intent(
                intent,
                account_id=resolved_account_id,
                status=order.status,
            )
        except Exception:
            LOGGER.debug("Persistance request watcher impossible pour %s", intent.intent_id, exc_info=True)
        try:
            self._repo.upsert_execution_broker_order(
                intent,
                order,
                account_id=resolved_account_id,
                raw_payload=intent_to_alpaca_payload(intent),
            )
        except Exception:
            LOGGER.debug("Persistance broker order watcher impossible pour %s", intent.intent_id, exc_info=True)

    @staticmethod
    def _build_parent_intent(item: ProtectionWatchItem, stop_order: BrokerOrder) -> OrderIntent:
        return OrderIntent(
            intent_id=item.parent_intent_id,
            risk_run_id=item.risk_run_id,
            exec_run_id=item.source_exec_run_id,
            symbol=item.symbol,
            side="buy",
            qty=item.fill_qty,
            order_type="market",
            limit_price=None,
            trail_percent=None,
            broker_mode=item.broker_mode,
            parent_intent_id=None,
            intent_role=IntentRole.ENTRY,
            idempotency_key=f"watch-parent-{item.parent_intent_id}",
            decision_price=item.fill_price,
            stop_price=stop_order.stop_price,
        )

    @staticmethod
    def _build_existing_stop_intent(item: ProtectionWatchItem, stop_order: BrokerOrder) -> OrderIntent:
        return OrderIntent(
            intent_id=item.initial_stop_intent_id,
            risk_run_id=item.risk_run_id,
            exec_run_id=item.source_exec_run_id,
            symbol=item.symbol,
            side="sell",
            qty=item.fill_qty,
            order_type="stop",
            limit_price=None,
            trail_percent=None,
            broker_mode=item.broker_mode,
            parent_intent_id=item.parent_intent_id,
            intent_role=IntentRole.INITIAL_STOP,
            idempotency_key=f"watch-existing-stop-{item.initial_stop_intent_id}",
            decision_price=item.fill_price,
            stop_price=stop_order.stop_price if stop_order.stop_price is not None else item.stop_price_initial,
            submission_key=stop_order.client_order_id or None,
        )

    def _cancel_initial_stop(
        self,
        broker: BrokerAdapter,
        config: ExecutionConfig,
        item: ProtectionWatchItem,
        stop_order: BrokerOrder,
    ) -> tuple[bool, BrokerOrder]:
        if not broker.cancel_broker_order(stop_order.broker_order_id):
            return False, stop_order
        latest_order = stop_order
        deadline = time.monotonic() + config.cancel_timeout_seconds
        while time.monotonic() < deadline:
            latest_order = broker.poll_order_status(stop_order.broker_order_id, item.initial_stop_intent_id)
            if latest_order.status == OrderStatus.CANCELED:
                return True, latest_order
            if latest_order.status in {OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.FAILED, OrderStatus.EXPIRED}:
                return False, latest_order
            time.sleep(config.poll_interval_seconds)
        return False, latest_order

    # Sprint S26 (gap P3) — Filet de sécurité TP/SL : arme TP+STOP pour un parent FILLED nu.
    def _arm_missing_protections(
        self,
        row: dict[str, Any],
        metrics: dict[str, Any],
    ) -> None:
        symbol = str(row["symbol"]).strip().upper()
        fill_qty = float(row.get("fill_qty") or 0.0)
        fill_price = float(row.get("fill_price") or 0.0)
        if fill_qty <= 0 or fill_price <= 0:
            metrics["armed_missing_protections_failed"] = (
                int(metrics.get("armed_missing_protections_failed", 0) or 0) + 1
            )
            return

        broker_mode = str(row.get("broker_mode") or "paper")
        account_id = str(row.get("account_id") or "default")
        config = self._config_for(broker_mode, account_id)
        broker = self._broker_for(broker_mode, account_id)

        decision_price = float(row.get("decision_price") or fill_price)
        target_qty = float(row.get("target_qty") or fill_qty)
        order_type = str(row.get("order_type") or "market")
        limit_price = row.get("limit_price")
        parent_intent = OrderIntent(
            intent_id=str(row["parent_intent_id"]),
            risk_run_id=str(row.get("risk_run_id") or ""),
            exec_run_id=str(row["exec_run_id"]),
            symbol=symbol,
            side=str(row.get("side") or "buy"),
            qty=target_qty,
            order_type=order_type,
            limit_price=float(limit_price) if limit_price is not None else None,
            trail_percent=None,
            broker_mode=broker_mode,
            parent_intent_id=None,
            intent_role=IntentRole.ENTRY,
            idempotency_key=str(row.get("business_key") or row.get("submission_key") or row["parent_intent_id"]),
            decision_price=decision_price,
            stop_price=None,
            submission_key=str(row["submission_key"]) if row.get("submission_key") else None,
        )

        tp_intent = build_take_profit_intent(parent_intent, fill_qty, fill_price, config, target=None)
        stop_intent = build_initial_stop_intent(parent_intent, fill_qty, fill_price, config, target=None)
        protection_intent = stop_intent or build_trailing_stop_intent(
            parent_intent, fill_qty, fill_price, config, target=None
        )

        armed_any = False
        for child in [tp_intent, protection_intent]:
            try:
                child_order = broker.submit_intent(child)
                self._persist_order_state(child, child_order, account_id=account_id)
                armed_any = True
            except Exception as exc:
                LOGGER.warning(
                    "Watcher : échec submit %s pour %s : %s",
                    child.intent_role, symbol, exc,
                )
                if child.intent_role == IntentRole.INITIAL_STOP:
                    fallback = build_trailing_stop_intent(
                        parent_intent, fill_qty, fill_price, config, target=None
                    )
                    try:
                        fallback_order = broker.submit_intent(fallback)
                        self._persist_order_state(fallback, fallback_order, account_id=account_id)
                        armed_any = True
                    except Exception as fb_exc:
                        LOGGER.warning(
                            "Watcher : fallback trailing échoué pour %s : %s", symbol, fb_exc,
                        )

        if armed_any:
            metrics["armed_missing_protections"] = (
                int(metrics.get("armed_missing_protections", 0) or 0) + 1
            )
            self._persist_event(make_event(
                str(row["exec_run_id"]),
                EventType.CHILDREN_SUBMITTED,
                f"Watcher : TP/SL armés (filet S26) pour {symbol}",
                symbol=symbol,
                intent_id=parent_intent.intent_id,
                payload={
                    "fill_qty": fill_qty,
                    "fill_price": fill_price,
                    "trigger": "watcher_safety_net",
                    "take_profit_limit_price": tp_intent.limit_price,
                    "initial_stop_price": stop_intent.stop_price if stop_intent is not None else None,
                },
            ))
        else:
            metrics["armed_missing_protections_failed"] = (
                int(metrics.get("armed_missing_protections_failed", 0) or 0) + 1
            )

    def _process_item(self, item: ProtectionWatchItem, metrics: dict[str, Any]) -> None:
        if not item.initial_stop_broker_order_id:
            metrics["submit_failed_items"] += 1
            return

        config = self._config_for(item.broker_mode, item.account_id)
        broker = self._broker_for(item.broker_mode, item.account_id)
        stop_order = broker.poll_order_status(item.initial_stop_broker_order_id, item.initial_stop_intent_id)
        parent_intent = self._build_parent_intent(item, stop_order)
        stop_intent = self._build_existing_stop_intent(item, stop_order)
        self._persist_order_state(stop_intent, stop_order, account_id=item.account_id)

        if stop_order.status in OrderStatus.TERMINAL:
            metrics["terminal_items"] += 1
            return

        trigger_price, trigger_mode = resolve_trailing_activation_price(item.fill_price, config, item)
        if trigger_price is None:
            metrics["pending_items"] += 1
            return

        market_price = broker.get_latest_market_price(item.symbol)
        metrics["trigger_check_count"] += 1
        if market_price is None or market_price < trigger_price:
            metrics["pending_items"] += 1
            return

        metrics["triggered_items"] += 1
        trigger_event = make_event(
            item.source_exec_run_id,
            EventType.PROTECTION_TRIGGER_HIT,
            f"Trigger trailing atteint pour {item.symbol} à {market_price:.2f}",
            symbol=item.symbol,
            broker_order_id=stop_order.broker_order_id,
            intent_id=item.initial_stop_intent_id,
            payload={
                "market_price": round(float(market_price), 4),
                "trigger_price": trigger_price,
                "trigger_mode": trigger_mode,
            },
        )
        self._persist_event(trigger_event)

        open_children = self._repo.load_open_child_orders(item.parent_intent_id)
        if any(child.intent_id != item.initial_stop_intent_id and child.order_type == "trailing_stop" for child in open_children):
            metrics["skipped_existing_trailing"] += 1
            return

        canceled, canceled_order = self._cancel_initial_stop(broker, config, item, stop_order)
        self._persist_order_state(stop_intent, canceled_order, account_id=item.account_id)
        if not canceled:
            metrics["cancel_failed_items"] += 1
            self._persist_event(make_event(
                item.source_exec_run_id,
                EventType.PROTECTION_TRANSITION_FAILED,
                f"Impossible d'annuler le stop initial pour {item.symbol}",
                symbol=item.symbol,
                broker_order_id=canceled_order.broker_order_id,
                intent_id=item.initial_stop_intent_id,
                payload={
                    "trigger_price": trigger_price,
                    "trigger_mode": trigger_mode,
                    "stop_status": canceled_order.status,
                },
            ))
            return

        trailing_intent = build_trailing_stop_intent(parent_intent, item.fill_qty, item.fill_price, config, target=item)
        try:
            trailing_order = broker.submit_intent(trailing_intent)
            self._persist_order_state(trailing_intent, trailing_order, account_id=item.account_id)
        except Exception as exc:
            metrics["submit_failed_items"] += 1
            self._persist_event(make_event(
                item.source_exec_run_id,
                EventType.PROTECTION_TRANSITION_FAILED,
                f"Echec soumission trailing dynamique pour {item.symbol}: {str(exc)[:120]}",
                symbol=item.symbol,
                intent_id=item.initial_stop_intent_id,
                payload={
                    "trigger_price": trigger_price,
                    "trigger_mode": trigger_mode,
                },
            ))
            return

        metrics["transitioned_items"] += 1
        self._persist_event(make_event(
            item.source_exec_run_id,
            EventType.PROTECTION_TRANSITION_COMPLETED,
            f"Stop initial promu en trailing pour {item.symbol}",
            symbol=item.symbol,
            broker_order_id=trailing_order.broker_order_id,
            intent_id=trailing_intent.intent_id,
            payload={
                "trigger_price": trigger_price,
                "trigger_mode": trigger_mode,
                "trailing_stop_percent": trailing_intent.trail_percent,
                "initial_stop_order_id": stop_order.broker_order_id,
                "trailing_stop_order_id": trailing_order.broker_order_id,
            },
        ))


class ProtectionWatcherService:
    """Boucle persistante qui ordonnance le watcher de transition de protection."""

    def __init__(
        self,
        watcher: ProtectionTransitionWatcher,
        service_config: ProtectionWatcherServiceConfig,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._watcher = watcher
        self._cfg = service_config
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn

    def run(
        self,
        *,
        exec_run_id: str | None = None,
        account_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        started_at = datetime.now()
        service_run_id = f"watch-service-{build_run_id()}"

        # Phase 6.3 — leader election best-effort via execution_locks.
        # Préfixe `watcher:` pour distinguer du lock executor (Phase 1.2).
        # ttl = 4× heartbeat_interval pour absorber GC pauses sans relâcher le lock.
        leader_lock_account = f"watcher:{account_id or 'default'}"
        leader_ttl_seconds = max(int(self._cfg.heartbeat_interval_seconds * 4), 60)
        leader_acquired = False
        try:
            leader_acquired = self._watcher._repo.acquire_execution_lock(
                account_id=leader_lock_account,
                exec_run_id=service_run_id,
                ttl_seconds=leader_ttl_seconds,
            )
        except Exception:
            LOGGER.debug("Leader election watcher: échec acquisition lock (table absente ?), continue.", exc_info=True)
            leader_acquired = True  # best-effort : pas de lock → on n'empêche pas le run.
        if not leader_acquired:
            LOGGER.warning(
                "Watcher protections : un autre leader est déjà actif pour account_id=%s (lock=%s).",
                account_id, leader_lock_account,
            )
            return {
                "status": "LEADER_LOCK_HELD",
                "service_scope": exec_run_id or account_id or "all",
                "leader_lock_account": leader_lock_account,
            }

        last_heartbeat = self._monotonic()
        metrics: dict[str, Any] = {
            "status": "RUNNING",
            "service_scope": exec_run_id or account_id or "all",
            "iterations": 0,
            "cycles_with_work": 0,
            "idle_cycles": 0,
            "heartbeat_count": 0,
            "consecutive_failures": 0,
            "max_consecutive_failures": self._cfg.max_consecutive_failures,
            "interval_seconds": self._cfg.interval_seconds,
            "idle_interval_seconds": self._cfg.idle_interval_seconds,
            "heartbeat_interval_seconds": self._cfg.heartbeat_interval_seconds,
            "stop_when_idle": self._cfg.stop_when_idle,
            "max_iterations": self._cfg.max_iterations,
            "watched_items": 0,
            "triggered_items": 0,
            "transitioned_items": 0,
            "pending_items": 0,
            "terminal_items": 0,
            "skipped_existing_trailing": 0,
            "cancel_failed_items": 0,
            "submit_failed_items": 0,
            "last_heartbeat_at": started_at.isoformat(timespec="seconds"),
            "last_cycle_at": None,
            "last_cycle_had_work": False,
            "last_cycle_watched_items": 0,
            "last_cycle_transitioned_items": 0,
        }
        self._persist_service_summary(
            service_run_id=service_run_id,
            metrics=metrics,
            started_at=started_at,
            finished_at=None,
            exec_run_id=exec_run_id,
            account_id=account_id,
            limit=limit,
        )

        try:
            while True:
                metrics["iterations"] += 1
                iteration = int(metrics["iterations"])
                try:
                    summaries = self._watcher.run(exec_run_id=exec_run_id, account_id=account_id, limit=limit)
                    metrics["consecutive_failures"] = 0
                except KeyboardInterrupt:
                    metrics["status"] = "STOPPED"
                    LOGGER.info("Arrêt demandé du service watcher protections (Ctrl+C).")
                    break
                except Exception:
                    metrics["consecutive_failures"] += 1
                    LOGGER.exception(
                        "Iteration %s du service watcher protections en échec (%s/%s).",
                        iteration,
                        metrics["consecutive_failures"],
                        self._cfg.max_consecutive_failures,
                    )
                    if metrics["consecutive_failures"] >= self._cfg.max_consecutive_failures:
                        metrics["status"] = "FAILED"
                        break
                    heartbeat_logged, last_heartbeat = self._maybe_log_heartbeat(
                        metrics,
                        account_id=account_id,
                        exec_run_id=exec_run_id,
                        last_heartbeat=last_heartbeat,
                    )
                    if heartbeat_logged:
                        self._persist_service_summary(
                            service_run_id=service_run_id,
                            metrics=metrics,
                            started_at=started_at,
                            finished_at=None,
                            exec_run_id=exec_run_id,
                            account_id=account_id,
                            limit=limit,
                        )
                    self._sleep(self._cfg.idle_interval_seconds)
                    continue

                cycle_metrics = self._aggregate_cycle_summaries(summaries)
                has_work = cycle_metrics["watched_items"] > 0
                cycle_finished_at = datetime.now()
                if has_work:
                    metrics["cycles_with_work"] += 1
                else:
                    metrics["idle_cycles"] += 1

                for key, value in cycle_metrics.items():
                    metrics[key] += value
                metrics["last_cycle_at"] = cycle_finished_at.isoformat(timespec="seconds")
                metrics["last_cycle_had_work"] = has_work
                metrics["last_cycle_watched_items"] = cycle_metrics["watched_items"]
                metrics["last_cycle_transitioned_items"] = cycle_metrics["transitioned_items"]

                LOGGER.info(
                    "Watcher protections iteration=%s watched=%s transitioned=%s pending=%s status=%s",
                    iteration,
                    cycle_metrics["watched_items"],
                    cycle_metrics["transitioned_items"],
                    cycle_metrics["pending_items"],
                    "work" if has_work else "idle",
                )

                _, last_heartbeat = self._maybe_log_heartbeat(
                    metrics,
                    account_id=account_id,
                    exec_run_id=exec_run_id,
                    last_heartbeat=last_heartbeat,
                )
                self._persist_service_summary(
                    service_run_id=service_run_id,
                    metrics=metrics,
                    started_at=started_at,
                    finished_at=None,
                    exec_run_id=exec_run_id,
                    account_id=account_id,
                    limit=limit,
                )

                if self._cfg.stop_when_idle and not has_work:
                    metrics["status"] = "COMPLETED"
                    break
                if self._cfg.max_iterations is not None and iteration >= self._cfg.max_iterations:
                    metrics["status"] = "COMPLETED"
                    break

                self._sleep(self._cfg.interval_seconds if has_work else self._cfg.idle_interval_seconds)
        except KeyboardInterrupt:
            metrics["status"] = "STOPPED"
            LOGGER.info("Service watcher protections interrompu proprement.")

        if metrics["status"] == "RUNNING":
            metrics["status"] = "COMPLETED"

        finished_at = datetime.now()
        summary = _build_service_summary(
            metrics,
            service_run_id=service_run_id,
            started_at=started_at,
            finished_at=finished_at,
            exec_run_id=exec_run_id,
            account_id=account_id,
            limit=limit,
        )
        self._persist_service_summary(
            service_run_id=service_run_id,
            metrics=metrics,
            started_at=started_at,
            finished_at=finished_at,
            exec_run_id=exec_run_id,
            account_id=account_id,
            limit=limit,
        )
        emit_run_summary(summary)
        # Phase 6.3 — release leader lock (best-effort).
        try:
            self._watcher._repo.release_execution_lock(
                account_id=leader_lock_account,
                exec_run_id=service_run_id,
            )
        except Exception:
            LOGGER.debug("release_execution_lock watcher: erreur ignorée", exc_info=True)
        summary["leader_lock_account"] = leader_lock_account
        return summary

    @staticmethod
    def _aggregate_cycle_summaries(summaries: list[dict[str, Any]]) -> dict[str, int]:
        aggregate = {
            "watched_items": 0,
            "triggered_items": 0,
            "transitioned_items": 0,
            "pending_items": 0,
            "terminal_items": 0,
            "skipped_existing_trailing": 0,
            "cancel_failed_items": 0,
            "submit_failed_items": 0,
        }
        for summary in summaries:
            for key in aggregate:
                aggregate[key] += int(summary.get(key, 0) or 0)
        return aggregate

    def _maybe_log_heartbeat(
        self,
        metrics: dict[str, Any],
        *,
        account_id: str | None,
        exec_run_id: str | None,
        last_heartbeat: float,
    ) -> tuple[bool, float]:
        now = self._monotonic()
        if metrics["iterations"] == 1 or (now - last_heartbeat) >= self._cfg.heartbeat_interval_seconds:
            metrics["heartbeat_count"] = int(metrics.get("heartbeat_count", 0) or 0) + 1
            metrics["last_heartbeat_at"] = datetime.now().isoformat(timespec="seconds")
            LOGGER.info(
                "Heartbeat watcher protections iterations=%s work_cycles=%s idle_cycles=%s transitioned=%s failures=%s account=%s exec_run_id=%s",
                metrics["iterations"],
                metrics["cycles_with_work"],
                metrics["idle_cycles"],
                metrics["transitioned_items"],
                metrics["consecutive_failures"],
                account_id or "*",
                exec_run_id or "*",
            )
            # Phase 1 refactor : persistance SQL du heartbeat
            # (audit_watcher.md, audit_global.md §6.8).
            try:
                import os
                import socket
                self._watcher._repo.upsert_watcher_heartbeat(
                    watcher_name="execution_protection_watcher",
                    account_id=account_id,
                    hostname=socket.gethostname(),
                    pid=os.getpid(),
                    status="RUNNING" if metrics["consecutive_failures"] == 0 else "ERROR",
                    last_error=None,
                )
            except Exception:
                LOGGER.debug("watcher_heartbeats persist failed", exc_info=True)
            return True, now
        return False, last_heartbeat

    def _persist_service_summary(
        self,
        *,
        service_run_id: str,
        metrics: dict[str, Any],
        started_at: datetime,
        finished_at: datetime | None,
        exec_run_id: str | None,
        account_id: str | None,
        limit: int,
    ) -> None:
        summary = _build_service_summary(
            metrics,
            service_run_id=service_run_id,
            started_at=started_at,
            finished_at=finished_at,
            exec_run_id=exec_run_id,
            account_id=account_id,
            limit=limit,
        )
        try:
            persist_run_business_summary(
                summary=summary,
                step_key="execution_protection_watch_service",
                run_kind="service",
                status=str(summary.get("status", "") or "") or None,
                summary_run_id=service_run_id,
                source_run_id=service_run_id,
                entity_run_id=exec_run_id or f"watcher-service:{account_id or 'all'}",
                parent_summary_run_id=exec_run_id,
                account_id=account_id,
                trade_date=None,
                started_at=summary.get("started_at"),
                finished_at=summary.get("finished_at") if finished_at is not None else None,
                engine=self._watcher._repo.engine,
            )
        except Exception:
            LOGGER.debug("Persistance run_business_summaries indisponible pour le service watcher protections.", exc_info=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Alpha Trade — Protection Transition Watcher")
    parser.add_argument("--mode", type=str, default="once", choices=["once", "service"])
    parser.add_argument("--exec-run-id", type=str, default=None)
    parser.add_argument("--account", type=str, default=None)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--broker-mode", type=str, default="paper", choices=["paper", "live"])
    parser.add_argument("--profit-taker-pct", type=float, default=0.08)
    parser.add_argument("--trailing-stop-pct", type=float, default=0.05)
    parser.add_argument("--trailing-activation-trigger", type=str, default="multiple_r", choices=["multiple_r", "profit_pct"])
    parser.add_argument("--trailing-activation-r-multiple", type=float, default=1.0)
    parser.add_argument("--trailing-activation-profit-pct", type=float, default=0.03)
    parser.add_argument("--service-interval-seconds", type=float, default=30.0)
    parser.add_argument("--idle-interval-seconds", type=float, default=120.0)
    parser.add_argument("--heartbeat-interval-seconds", type=float, default=300.0)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--stop-when-idle", action="store_true")
    parser.add_argument("--max-consecutive-failures", type=int, default=3)
    parser.add_argument("--log-level", type=str, default="INFO")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    configure_root_logging(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        log_path="./log/execution_protection_watcher.log",
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    def config_factory(broker_mode: str, account_id: str | None) -> ExecutionConfig:
        return ExecutionConfig(
            broker_mode=broker_mode,
            account_id=account_id,
            profit_taker_pct=args.profit_taker_pct,
            trailing_stop_pct=args.trailing_stop_pct,
            trailing_activation_trigger=args.trailing_activation_trigger,
            trailing_activation_r_multiple=args.trailing_activation_r_multiple,
            trailing_activation_profit_pct=args.trailing_activation_profit_pct,
        )

    def broker_factory(broker_mode: str, account_id: str | None) -> BrokerAdapter:
        config = config_factory(broker_mode, account_id)
        client = AlpacaTradingClient(broker_mode=broker_mode, account_id=account_id)
        return BrokerAdapter(client, config)

    repo = ExecutionRepository()
    watcher = ProtectionTransitionWatcher(repo, broker_factory=broker_factory, config_factory=config_factory)
    if args.mode == "service":
        service = ProtectionWatcherService(
            watcher,
            ProtectionWatcherServiceConfig(
                interval_seconds=args.service_interval_seconds,
                idle_interval_seconds=args.idle_interval_seconds,
                heartbeat_interval_seconds=args.heartbeat_interval_seconds,
                max_iterations=args.max_iterations,
                stop_when_idle=args.stop_when_idle,
                max_consecutive_failures=args.max_consecutive_failures,
            ),
        )
        summary = service.run(exec_run_id=args.exec_run_id, account_id=args.account, limit=args.limit)
        logging.getLogger(__name__).info("Protection watcher service summary: %s", summary)
        return

    summaries = watcher.run(exec_run_id=args.exec_run_id, account_id=args.account, limit=args.limit)
    logging.getLogger(__name__).info("Protection watcher summaries: %s", summaries)


if __name__ == "__main__":
    main()

