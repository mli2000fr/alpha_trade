"""Watcher post-run dédié à la promotion stop initial -> trailing dynamique."""
from __future__ import annotations

import argparse
import logging
import time
from collections import defaultdict
from dataclasses import replace
from datetime import datetime
from typing import Any, Callable

from common.utils import configure_root_logging
from database.run_business_summaries import emit_run_summary, persist_run_business_summary
from execution_engine.audit import build_run_id, make_event
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.broker_state_sync import BrokerStateSynchronizer
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
    build_manual_buy_initial_stop_intent,
    build_take_profit_intent,
    build_trailing_stop_intent,
    intent_to_alpaca_payload,
    resolve_trailing_activation_price,
)
from execution_engine.orphan_adoption import adopt_orphan_buy
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
        "adopted_orphan_buys": int(metrics.get("adopted_orphan_buys", 0) or 0),
        "adopted_orphan_buys_failed": int(metrics.get("adopted_orphan_buys_failed", 0) or 0),
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
        "armed_missing_protections": int(metrics.get("armed_missing_protections", 0) or 0),
        "armed_missing_protections_failed": int(metrics.get("armed_missing_protections_failed", 0) or 0),
        "adopted_orphan_buys": int(metrics.get("adopted_orphan_buys", 0) or 0),
        "adopted_orphan_buys_failed": int(metrics.get("adopted_orphan_buys_failed", 0) or 0),
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
        *,
        default_broker_mode: str = "paper",
    ) -> None:
        self._repo = repo
        self._broker_factory = broker_factory
        self._config_factory = config_factory
        self._default_broker_mode = default_broker_mode
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
        # Issue 2 (2026-05) — Refresh systématique de l'état broker en début
        # de cycle, plus uniquement quand toutes les listes sont vides. Cela
        # garantit la détection des achats / ventes manuels effectués hors
        # Alpha Trade depuis le dernier cycle, quel que soit le mode de
        # lancement (Run watcher once / service local IHM).
        refresh_metrics = self._refresh_broker_state_if_needed(
            exec_run_id=exec_run_id,
            account_id=account_id,
            limit=limit,
        )
        if refresh_metrics:
            LOGGER.info(
                "Protection watcher refresh broker terminé en début de cycle: %s",
                refresh_metrics,
            )
        items, unprotected_rows, orphan_positions = self._load_watch_inputs(
            exec_run_id=exec_run_id,
            account_id=account_id,
            limit=limit,
        )
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
                "adopted_orphan_buys": 0,
                "adopted_orphan_buys_failed": 0,
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
        for row in unprotected_rows:
            source_exec_run_id = str(row.get("exec_run_id") or "")
            run_metrics = metrics_by_run[source_exec_run_id]
            run_metrics.setdefault("source_exec_run_id", source_exec_run_id)
            run_metrics.setdefault("trade_date", None)
            run_metrics["broker_mode"] = str(row.get("broker_mode") or run_metrics.get("broker_mode") or "paper")
            run_metrics["account_id"] = str(row.get("account_id") or run_metrics.get("account_id") or "default")
            use_manual_buy_stop = str(row.get("parent_intent_role") or "") == IntentRole.ADOPTED_ENTRY
            try:
                self._arm_missing_protections(
                    row,
                    run_metrics,
                    use_manual_buy_stop=use_manual_buy_stop,
                )
            except Exception:
                LOGGER.warning(
                    "Échec armement protections manquantes pour %s",
                    row.get("symbol"), exc_info=True,
                )
                run_metrics["armed_missing_protections_failed"] = (
                    int(run_metrics.get("armed_missing_protections_failed", 0) or 0) + 1
                )

        # ------------------------------------------------------------------
        # Sprint 2026-05 — Adoption d'achats manuels orphelins (Q8 FAQ).
        # Pour chaque position broker non rattachée à un OrderIntent ENTRY,
        # on crée un parent ``adopted_entry`` puis on arme TP + STOP en
        # utilisant le pourcentage `manual_buy_stop_loss_pct` dédié.
        # ------------------------------------------------------------------
        for position_row in orphan_positions:
            position_account_id = str(position_row.get("account_id") or account_id or "default")
            broker_mode = str(position_row.get("broker_mode") or "paper")
            try:
                adoption = adopt_orphan_buy(
                    self._repo,
                    broker_mode=broker_mode,
                    account_id=position_account_id,
                    broker_position=position_row,
                )
            except Exception:
                LOGGER.warning(
                    "Échec adoption achat manuel orphelin pour %s",
                    position_row.get("symbol"), exc_info=True,
                )
                continue
            if adoption is None:
                continue
            run_metrics = metrics_by_run[adoption.intent.exec_run_id]
            run_metrics.setdefault("source_exec_run_id", adoption.intent.exec_run_id)
            run_metrics.setdefault("trade_date", None)
            run_metrics["broker_mode"] = broker_mode
            run_metrics["account_id"] = position_account_id
            run_metrics["adopted_orphan_buys"] = int(run_metrics.get("adopted_orphan_buys", 0) or 0) + 1

            # Construit la "row" attendue par _arm_missing_protections à partir
            # du parent adopté + de la position broker.
            synthetic_row: dict[str, Any] = {
                "parent_intent_id": adoption.intent.intent_id,
                "exec_run_id": adoption.intent.exec_run_id,
                "risk_run_id": adoption.intent.risk_run_id,
                "account_id": position_account_id,
                "broker_mode": broker_mode,
                "symbol": adoption.intent.symbol,
                "side": "buy",
                "target_qty": adoption.intent.qty,
                "order_type": adoption.intent.order_type,
                "limit_price": None,
                "decision_price": adoption.intent.decision_price,
                "business_key": adoption.intent.idempotency_key,
                "submission_key": adoption.intent.submission_key,
                "fill_qty": float(position_row.get("qty") or 0.0),
                "fill_price": float(position_row.get("avg_entry_price") or 0.0),
            }
            try:
                self._arm_missing_protections(
                    synthetic_row,
                    run_metrics,
                    use_manual_buy_stop=True,
                )
            except Exception:
                LOGGER.warning(
                    "Échec armement TP/SL pour orphelin adopté %s",
                    adoption.intent.symbol, exc_info=True,
                )
                run_metrics["adopted_orphan_buys_failed"] = (
                    int(run_metrics.get("adopted_orphan_buys_failed", 0) or 0) + 1
                )

        summaries: list[dict[str, Any]] = []
        finished_at = datetime.now()
        if not metrics_by_run:
            LOGGER.info(
                "Protection watcher: aucun candidat après scan (pending=%s, unprotected=%s, orphan_positions=%s, account=%s, exec_run_id=%s)",
                len(items),
                len(unprotected_rows),
                len(orphan_positions),
                account_id or "*",
                exec_run_id or "*",
            )
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

    def _load_watch_inputs(
        self,
        *,
        exec_run_id: str | None,
        account_id: str | None,
        limit: int,
    ) -> tuple[list[ProtectionWatchItem], list[dict[str, Any]], list[dict[str, Any]]]:
        items = self._repo.load_pending_protection_watch_items(
            exec_run_id=exec_run_id,
            account_id=account_id,
            limit=limit,
        )
        try:
            unprotected_rows = self._repo.load_unprotected_filled_parents(
                exec_run_id=exec_run_id,
                account_id=account_id,
                limit=max(limit, 200),
            )
        except Exception:
            LOGGER.warning("load_unprotected_filled_parents failed", exc_info=True)
            unprotected_rows = []
        try:
            orphan_positions = self._repo.load_orphan_filled_buy_positions(
                account_id=account_id,
                limit=max(limit, 200),
            )
        except Exception:
            LOGGER.warning("load_orphan_filled_buy_positions failed", exc_info=True)
            orphan_positions = []
        return items, unprotected_rows, orphan_positions

    def _resolve_refresh_context(
        self,
        *,
        exec_run_id: str | None,
        account_id: str | None,
    ) -> tuple[str, str] | None:
        if exec_run_id:
            try:
                run_context = self._repo.load_execution_run_context(exec_run_id=exec_run_id)
            except Exception:
                LOGGER.debug("load_execution_run_context failed for %s", exec_run_id, exc_info=True)
                run_context = None
            if isinstance(run_context, dict):
                resolved_account_id = str(run_context.get("account_id") or account_id or "").strip()
                resolved_broker_mode = str(run_context.get("broker_mode") or self._default_broker_mode).strip() or self._default_broker_mode
                if resolved_account_id:
                    return resolved_broker_mode, resolved_account_id
        if account_id:
            return self._default_broker_mode, account_id
        return None

    def _refresh_broker_state_if_needed(
        self,
        *,
        exec_run_id: str | None,
        account_id: str | None,
        limit: int,
    ) -> dict[str, Any] | None:
        refresh_context = self._resolve_refresh_context(exec_run_id=exec_run_id, account_id=account_id)
        if refresh_context is None:
            return None
        broker_mode, resolved_account_id = refresh_context
        sync_exec_run_id = exec_run_id or f"watcher-sync-{build_run_id()}"
        try:
            sync_metrics = BrokerStateSynchronizer(
                self._repo,
                self._broker_for(broker_mode, resolved_account_id),
                broker_mode=broker_mode,
            ).sync(
                exec_run_id=sync_exec_run_id,
                account_id=resolved_account_id,
                order_limit=max(limit, 200),
            )
        except Exception:
            LOGGER.warning(
                "Protection watcher: refresh broker préalable échoué (account=%s, broker_mode=%s, exec_run_id=%s)",
                resolved_account_id,
                broker_mode,
                sync_exec_run_id,
                exc_info=True,
            )
            return None
        return {
            "account_id": resolved_account_id,
            "broker_mode": broker_mode,
            "sync_exec_run_id": sync_exec_run_id,
            **sync_metrics,
        }

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

    def _persist_order_request_failure(self, intent: OrderIntent, exc: Exception, *, account_id: str | None = None) -> None:
        resolved_account_id = account_id or "default"
        try:
            self._repo.upsert_execution_order_request_from_intent(
                intent,
                account_id=resolved_account_id,
                status=OrderStatus.REJECTED,
                failure_reason=str(exc)[:500],
            )
        except Exception:
            LOGGER.debug("Persistance rejet request watcher impossible pour %s", intent.intent_id, exc_info=True)

    @staticmethod
    def _is_protection_rejection_likely_due_to_open_exit(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(token in message for token in ("403", "forbidden", "insufficient", "available", "oversell", "wash"))

    def _reconcile_position_closed(
        self,
        parent_intent: OrderIntent,
        broker: BrokerAdapter,
        *,
        broker_mode: str,
        account_id: str,
        exec_run_id: str,
        symbol: str,
    ) -> bool:
        """Issue 3 (2026-05) — Vérifie qu'une position vendue hors application
        a bien disparu côté Alpaca, annule les enfants orphelins, et rafraîchit
        l'état broker pour que la requête ``load_unprotected_filled_parents``
        cesse de remonter le parent (la qty broker tombe à 0).
        Retourne ``True`` si la position a effectivement été reconciliée
        comme fermée (pas de retry à programmer)."""
        position = broker.get_position(symbol)
        # Stricte : ne reconcilie en "fermé" que si Alpaca a explicitement
        # retourné None (404) ou un dict avec qty <= 0. Un objet inattendu
        # est traité comme "présent" (safe default) afin de ne pas annuler
        # des protections valides sur un retour mal formé.
        if position is None:
            position_qty = 0.0
        elif isinstance(position, dict):
            try:
                position_qty = float(position.get("qty", 0) or 0)
            except (TypeError, ValueError):
                position_qty = 0.0
            if position_qty > 0:
                return False
        else:
            return False

        # Position absente / soldée chez Alpaca : annulons les enfants encore
        # ouverts puis resynchronisons les snapshots pour que le watcher arrête
        # de cibler ce parent au prochain cycle.
        try:
            open_children = self._repo.load_open_child_orders(parent_intent.intent_id)
        except Exception:
            LOGGER.debug(
                "load_open_child_orders échoué pour %s lors de la reconciliation",
                parent_intent.intent_id, exc_info=True,
            )
            open_children = []
        canceled = 0
        for child_order in open_children:
            if not child_order.broker_order_id:
                continue
            try:
                role = (
                    IntentRole.TAKE_PROFIT
                    if child_order.order_type == "limit"
                    else IntentRole.INITIAL_STOP
                )
                child_intent = self._build_existing_child_intent(parent_intent, child_order, role)
                if broker.cancel_broker_order(child_order.broker_order_id):
                    try:
                        latest_order = broker.poll_order_status(
                            child_order.broker_order_id, child_order.intent_id,
                        )
                    except Exception:
                        latest_order = replace(
                            child_order, status=OrderStatus.CANCELED, updated_at=datetime.now(),
                        )
                    if latest_order.status != OrderStatus.CANCELED:
                        latest_order = replace(
                            latest_order, status=OrderStatus.CANCELED, updated_at=datetime.now(),
                        )
                    self._persist_order_state(child_intent, latest_order, account_id=account_id)
                    canceled += 1
            except Exception:
                LOGGER.debug(
                    "Annulation enfant orphelin échouée pour %s/%s",
                    symbol, child_order.broker_order_id, exc_info=True,
                )

        # Resynchronise l'état broker : snapshot positions + lots → la qty
        # broker repassera à 0 et la requête `load_unprotected_filled_parents`
        # exclura le parent au prochain cycle.
        sync_run_id = f"watcher-reconcile-{build_run_id()}"
        try:
            BrokerStateSynchronizer(
                self._repo, broker, broker_mode=broker_mode,
            ).sync(
                exec_run_id=sync_run_id,
                account_id=account_id,
                order_limit=200,
            )
        except Exception:
            LOGGER.debug(
                "Resynchro broker post-reconciliation échouée pour %s",
                account_id, exc_info=True,
            )

        self._persist_event(make_event(
            exec_run_id,
            EventType.PROTECTION_TRANSITION_FAILED,
            f"Watcher : position {symbol} clôturée hors application — armement TP/SL annulé.",
            symbol=symbol,
            intent_id=parent_intent.intent_id,
            payload={
                "trigger": "watcher_position_closed_reconciliation",
                "canceled_children": canceled,
                "broker_position_qty": position_qty,
                "sync_exec_run_id": sync_run_id,
            },
        ))
        LOGGER.info(
            "Watcher : reconciliation %s — position absente côté Alpaca, %s enfant(s) annulé(s).",
            symbol, canceled,
        )
        return True

    @staticmethod
    def _build_existing_child_intent(parent: OrderIntent, child_order: BrokerOrder, role: str) -> OrderIntent:
        return OrderIntent(
            intent_id=child_order.intent_id,
            risk_run_id=parent.risk_run_id,
            exec_run_id=parent.exec_run_id,
            symbol=child_order.symbol or parent.symbol,
            side=child_order.side or "sell",
            qty=child_order.qty,
            order_type=child_order.order_type,
            limit_price=child_order.limit_price,
            trail_percent=child_order.trail_percent,
            broker_mode=parent.broker_mode,
            parent_intent_id=parent.intent_id,
            intent_role=role,
            idempotency_key=f"watch-existing-child-{child_order.intent_id}",
            decision_price=parent.decision_price,
            stop_price=child_order.stop_price,
            submission_key=child_order.client_order_id or None,
        )

    def _cancel_existing_take_profit_children(
        self,
        parent_intent: OrderIntent,
        broker: BrokerAdapter,
        *,
        account_id: str | None,
    ) -> int:
        try:
            open_children = self._repo.load_open_child_orders(parent_intent.intent_id)
        except Exception:
            LOGGER.debug("Lecture TP existants impossible pour %s", parent_intent.intent_id, exc_info=True)
            return 0

        canceled_count = 0
        for child_order in open_children:
            if child_order.order_type != "limit":
                continue
            if not child_order.broker_order_id:
                continue
            child_intent = self._build_existing_child_intent(parent_intent, child_order, IntentRole.TAKE_PROFIT)
            try:
                if not broker.cancel_broker_order(child_order.broker_order_id):
                    continue
                try:
                    latest_order = broker.poll_order_status(child_order.broker_order_id, child_order.intent_id)
                except Exception:
                    latest_order = replace(child_order, status=OrderStatus.CANCELED, updated_at=datetime.now())
                if latest_order.status != OrderStatus.CANCELED:
                    latest_order = replace(latest_order, status=OrderStatus.CANCELED, updated_at=datetime.now())
                self._persist_order_state(child_intent, latest_order, account_id=account_id)
                canceled_count += 1
            except Exception:
                LOGGER.warning(
                    "Watcher : annulation TP existant échouée pour %s (%s)",
                    parent_intent.symbol,
                    child_order.broker_order_id,
                    exc_info=True,
                )
        return canceled_count

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
        *,
        use_manual_buy_stop: bool = False,
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
        if use_manual_buy_stop:
            # Achat manuel orphelin : pas d'ATR / risk_per_share côté DB,
            # on applique le pourcentage configurable dédié.
            stop_intent = build_manual_buy_initial_stop_intent(
                parent_intent, fill_qty, fill_price, config,
            )
        else:
            stop_intent = build_initial_stop_intent(parent_intent, fill_qty, fill_price, config, target=None)
        protection_intent = stop_intent or build_trailing_stop_intent(
            parent_intent, fill_qty, fill_price, config, target=None
        )

        has_open_take_profit = bool(row.get("has_open_take_profit"))
        has_open_protection = bool(row.get("has_open_protection"))
        if has_open_take_profit and has_open_protection:
            return

        submitted_any = False
        protection_available = has_open_protection
        take_profit_available = has_open_take_profit
        submit_failures = 0
        last_submit_error: Exception | None = None
        reconciled_closed = False

        def _maybe_reconcile_position_closed(exc: Exception) -> bool:
            nonlocal reconciled_closed
            if reconciled_closed:
                return True
            if not self._is_protection_rejection_likely_due_to_open_exit(exc):
                return False
            try:
                if self._reconcile_position_closed(
                    parent_intent,
                    broker,
                    broker_mode=broker_mode,
                    account_id=account_id,
                    exec_run_id=str(row["exec_run_id"]),
                    symbol=symbol,
                ):
                    reconciled_closed = True
                    return True
            except Exception:
                LOGGER.debug(
                    "Reconciliation position fermée échouée pour %s", symbol, exc_info=True,
                )
            return False

        def _submit_child(child: OrderIntent) -> bool:
            nonlocal submitted_any, protection_available, take_profit_available
            nonlocal submit_failures, last_submit_error
            try:
                child_order = broker.submit_intent(child)
                self._persist_order_state(child, child_order, account_id=account_id)
                submitted_any = True
                last_submit_error = None
                if child.intent_role in {IntentRole.INITIAL_STOP, IntentRole.TRAILING_STOP}:
                    protection_available = True
                if child.intent_role == IntentRole.TAKE_PROFIT:
                    take_profit_available = True
                return True
            except Exception as exc:
                submit_failures += 1
                last_submit_error = exc
                self._persist_order_request_failure(child, exc, account_id=account_id)
                LOGGER.warning(
                    "Watcher : échec submit %s pour %s : %s",
                    child.intent_role, symbol, exc,
                )
                return False

        # Issue 1 (2026-05) — Si TP et SL sont tous deux à armer ET que le
        # stop est broker-side (type "stop", pas trailing_stop), on les pose
        # en une seule commande Alpaca OCO. Une soumission séquentielle
        # déclenchait sinon un 403 ``insufficient qty`` sur le second ordre
        # (chaque leg essayait de réserver la même qty de la position).
        if (
            not has_open_take_profit
            and not has_open_protection
            and stop_intent is not None
            and stop_intent.order_type == "stop"
            and stop_intent.stop_price is not None
            and tp_intent.limit_price is not None
        ):
            try:
                tp_order, stop_order = broker.submit_oco_protection(
                    parent_intent, tp_intent, stop_intent,
                )
                self._persist_order_state(tp_intent, tp_order, account_id=account_id)
                self._persist_order_state(stop_intent, stop_order, account_id=account_id)
                submitted_any = True
                take_profit_available = True
                protection_available = True
            except Exception as exc:
                submit_failures += 1
                last_submit_error = exc
                LOGGER.warning(
                    "Watcher : échec submit OCO TP+SL pour %s : %s — fallback sur soumissions séparées.",
                    symbol, exc,
                )
                # Issue 3 — si la position n'existe plus côté Alpaca (vente
                # manuelle), on reconcilie et on sort proprement. Sinon on
                # tombe dans la branche séquentielle ci-dessous (qui persistera
                # éventuellement le rejet sur chaque intent individuel).
                if _maybe_reconcile_position_closed(exc):
                    return

        if not has_open_protection and not protection_available:
            protection_error: Exception | None = last_submit_error
            if not _submit_child(protection_intent):
                protection_error = last_submit_error
                # Issue 3 — vente manuelle hors app : reconcilie et sort.
                if protection_error is not None and _maybe_reconcile_position_closed(protection_error):
                    return
                if protection_intent.intent_role == IntentRole.INITIAL_STOP:
                    fallback = build_trailing_stop_intent(
                        parent_intent, fill_qty, fill_price, config, target=None
                    )
                    try:
                        fallback_order = broker.submit_intent(fallback)
                        self._persist_order_state(fallback, fallback_order, account_id=account_id)
                        submitted_any = True
                        protection_available = True
                    except Exception as fb_exc:
                        submit_failures += 1
                        protection_error = fb_exc
                        self._persist_order_request_failure(fallback, fb_exc, account_id=account_id)
                        LOGGER.warning("Watcher : fallback trailing échoué pour %s : %s", symbol, fb_exc)
                        if _maybe_reconcile_position_closed(fb_exc):
                            return

            if not protection_available and has_open_take_profit and protection_error is not None:
                canceled_tps = 0
                if self._is_protection_rejection_likely_due_to_open_exit(protection_error):
                    canceled_tps = self._cancel_existing_take_profit_children(
                        parent_intent,
                        broker,
                        account_id=account_id,
                    )
                if canceled_tps > 0:
                    LOGGER.warning(
                        "Watcher : %s TP existant(s) annulé(s) pour prioriser le SL sur %s ; nouvelle tentative protection.",
                        canceled_tps,
                        symbol,
                    )
                    if not _submit_child(protection_intent) and protection_intent.intent_role == IntentRole.INITIAL_STOP:
                        fallback = build_trailing_stop_intent(parent_intent, fill_qty, fill_price, config, target=None)
                        try:
                            fallback_order = broker.submit_intent(fallback)
                            self._persist_order_state(fallback, fallback_order, account_id=account_id)
                            submitted_any = True
                            protection_available = True
                        except Exception as fb_exc:
                            submit_failures += 1
                            self._persist_order_request_failure(fallback, fb_exc, account_id=account_id)
                            LOGGER.warning("Watcher : fallback trailing après annulation TP échoué pour %s : %s", symbol, fb_exc)

        if reconciled_closed:
            return

        if not protection_available:
            metrics["armed_missing_protections_failed"] = (
                int(metrics.get("armed_missing_protections_failed", 0) or 0) + 1
            )
            self._persist_event(make_event(
                str(row["exec_run_id"]),
                EventType.PROTECTION_TRANSITION_FAILED,
                f"Watcher : protection manquante non armée pour {symbol}",
                symbol=symbol,
                intent_id=parent_intent.intent_id,
                payload={
                    "fill_qty": fill_qty,
                    "fill_price": fill_price,
                    "submit_failures": submit_failures,
                    "has_open_take_profit": has_open_take_profit,
                    "trigger": "watcher_orphan_buy_safety_net" if use_manual_buy_stop else "watcher_safety_net",
                },
            ))
            return

        if not has_open_take_profit and not take_profit_available:
            if not _submit_child(tp_intent):
                # Issue 3 — la position peut avoir été soldée pendant l'arming
                if last_submit_error is not None:
                    _maybe_reconcile_position_closed(last_submit_error)

        if submitted_any:
            metrics["armed_missing_protections"] = (
                int(metrics.get("armed_missing_protections", 0) or 0) + 1
            )
            self._persist_event(make_event(
                str(row["exec_run_id"]),
                EventType.CHILDREN_SUBMITTED,
                f"Watcher : protection armée (filet S26) pour {symbol}",
                symbol=symbol,
                intent_id=parent_intent.intent_id,
                payload={
                    "fill_qty": fill_qty,
                    "fill_price": fill_price,
                    "trigger": "watcher_orphan_buy_safety_net" if use_manual_buy_stop else "watcher_safety_net",
                    "take_profit_limit_price": tp_intent.limit_price,
                    "initial_stop_price": stop_intent.stop_price if stop_intent is not None else None,
                    "manual_buy_stop_loss_pct": config.manual_buy_stop_loss_pct if use_manual_buy_stop else None,
                    "submit_failures": submit_failures,
                    "protection_available": protection_available,
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
        # ttl = 2× le plus grand intervalle de boucle pour absorber les pauses.
        # Le lock est renouvelé à chaque cycle ; ne pas dépendre du heartbeat
        # long (300s par défaut) évite de laisser un verrou orphelin 10–20 min.
        leader_lock_account = f"watcher:{account_id or 'default'}"
        leader_ttl_seconds = max(int(max(
            self._cfg.interval_seconds,
            self._cfg.idle_interval_seconds,
        ) * 2), 60)
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
            "armed_missing_protections": 0,
            "armed_missing_protections_failed": 0,
            "adopted_orphan_buys": 0,
            "adopted_orphan_buys_failed": 0,
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
                        service_run_id=service_run_id,
                        leader_lock_account=leader_lock_account,
                        leader_ttl_seconds=leader_ttl_seconds,
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
                has_work = any(value > 0 for value in cycle_metrics.values())
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
                    service_run_id=service_run_id,
                    leader_lock_account=leader_lock_account,
                    leader_ttl_seconds=leader_ttl_seconds,
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
            "armed_missing_protections": 0,
            "armed_missing_protections_failed": 0,
            "adopted_orphan_buys": 0,
            "adopted_orphan_buys_failed": 0,
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
        service_run_id: str,
        leader_lock_account: str,
        leader_ttl_seconds: int,
        last_heartbeat: float,
    ) -> tuple[bool, float]:
        now = self._monotonic()
        try:
            refreshed = self._watcher._repo.refresh_execution_lock(
                account_id=leader_lock_account,
                exec_run_id=service_run_id,
                ttl_seconds=leader_ttl_seconds,
            )
            if not refreshed:
                LOGGER.warning(
                    "Cycle watcher protections: leader lock non renouvelé pour %s (run=%s).",
                    leader_lock_account,
                    service_run_id,
                )
        except Exception:
            LOGGER.debug("refresh_execution_lock watcher: erreur ignorée", exc_info=True)
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
    parser.add_argument(
        "--manual-buy-stop-loss-pct",
        type=float,
        default=0.05,
        help=(
            "Stop-loss appliqué EXCLUSIVEMENT aux achats manuels orphelins "
            "adoptés par le watcher (positions ouvertes hors Alpha Trade). "
            "Pour les achats normaux, le stop reste calculé via ATR / "
            "risk_per_share du selector."
        ),
    )
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
            manual_buy_stop_loss_pct=args.manual_buy_stop_loss_pct,
            trailing_activation_trigger=args.trailing_activation_trigger,
            trailing_activation_r_multiple=args.trailing_activation_r_multiple,
            trailing_activation_profit_pct=args.trailing_activation_profit_pct,
        )

    def broker_factory(broker_mode: str, account_id: str | None) -> BrokerAdapter:
        config = config_factory(broker_mode, account_id)
        client = AlpacaTradingClient(broker_mode=broker_mode, account_id=account_id)
        return BrokerAdapter(client, config)

    repo = ExecutionRepository()
    watcher = ProtectionTransitionWatcher(
        repo,
        broker_factory=broker_factory,
        config_factory=config_factory,
        default_broker_mode=args.broker_mode,
    )
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

