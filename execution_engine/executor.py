"""Production Executor — orchestrateur principal du module execution_engine.

Architecture Synthetic Bracket :
    Le broker Alpaca ne supporte PAS trailing_stop comme leg d'un bracket natif.
    Le pattern est donc un "synthetic bracket" :
      1. Soumettre l'ordre d'entree (market ou limit)
      2. Poller / attendre le fill
      3. Apres fill : soumettre separement un trailing_stop + un limit take-profit
      4. Gerer le OCO logique cote applicatif (si l'un est rempli, cancel l'autre)
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional

from core.run_summary import attach_live_progress
from execution_engine.account_state import (
    _AccountConstraintState,
    build_account_constraint_state as _build_account_constraint_state_impl,
    estimate_intent_notional as _estimate_intent_notional_impl,
    reserve_account_capacity_for_intent as _reserve_account_capacity_for_intent_impl,
    safe_float as _safe_float_impl,
    should_defer_children as _should_defer_children_impl,
)
from execution_engine.audit import (
    build_run_id,
    event_to_db_dict,
    make_event,
)
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.broker_state_sync import BrokerStateSynchronizer
from execution_engine.children_submission import (
    submit_children as _submit_children_impl,
    submit_rebalance_orders as _submit_rebalance_orders_impl,
)
from execution_engine.config import ExecutionConfig
from execution_engine.db_io import ExecutionRepository
from execution_engine.models import (
    BrokerOrder,
    EventType,
    ExecutionEvent,
    ExecutionFill,
    IntentRole,
    OrderIntent,
    OrderStatus,
    ReconcileDiff,
    ReconciliationStatus,
)
from execution_engine.oco_manager import OcoManager
from execution_engine.order_intents import (
    build_entry_intents,
    build_initial_stop_intent,
    build_take_profit_intent,
    build_trailing_stop_intent,
    build_rebalance_sell_intent,
    build_rebalance_buy_intent,
    intent_to_alpaca_payload,
    resolve_initial_stop_price,
    resolve_trailing_activation_price,
)
from execution_engine.protection_transition import (
    maybe_activate_dynamic_trailing as _maybe_activate_dynamic_trailing_impl,
)
from execution_engine.reconciliation import reconcile_execution_state
from execution_engine.state_machine import is_terminal
from execution_engine.tca import build_tca_summary, compute_implementation_shortfall, compute_slippage_bps
from service.alpaca.trading_client import BrokerApiError

LOGGER = logging.getLogger(__name__)


LOGGER = logging.getLogger(__name__)


# Sprint S7 - extracted to ``execution_engine.account_state``.
# Re-exported here for backwards compatibility (tests/test_execution_engine_executor.py).


class ProductionExecutor:
    """Orchestrateur de l execution."""

    def __init__(
        self,
        config: ExecutionConfig,
        repo: ExecutionRepository,
        broker: BrokerAdapter,
        oco: OcoManager,
        circuit_breaker: Optional[Any] = None,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self._cfg = config
        self._repo = repo
        self._broker = broker
        self._oco = oco
        self._circuit_breaker = circuit_breaker
        self._progress_callback = progress_callback

    def _emit_progress(
        self,
        metrics: dict[str, Any],
        *,
        current: int,
        total: int,
        label: str,
        phase: str,
        item: str | None = None,
        unit: str = "symboles",
    ) -> None:
        if not callable(self._progress_callback):
            return
        payload = dict(metrics)
        payload["last_phase"] = phase
        self._progress_callback(
            attach_live_progress(
                payload,
                current=current,
                total=total,
                label=label,
                phase=phase,
                unit=unit,
                item=item,
            )
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def execute_run(
        self,
        risk_run_id: str | None = None,
        trade_date: date | None = None,
    ) -> dict[str, Any]:
        exec_run_id = build_run_id()
        resolved_account_id = self._cfg.resolved_account_id
        metrics: dict[str, Any] = {
            "exec_run_id": exec_run_id,
            "risk_run_id": risk_run_id,
            "trade_date": trade_date.isoformat() if hasattr(trade_date, "isoformat") else trade_date,
            "status": "RUNNING",
            "targets": 0, "submitted": 0, "filled": 0, "failed": 0, "skipped": 0,
            "rebalance_submitted": 0, "rebalance_failed": 0,
            "constraint_blocked": 0, "children_deferred": 0,
            "child_take_profit_orders_submitted": 0,
            "child_initial_stop_orders_submitted": 0,
            "child_trailing_stop_orders_submitted": 0,
            "child_order_submit_failures": 0,
            "targets_eligible_for_dynamic_trailing": 0,
            "dynamic_trailing_trigger_checks": 0,
            "dynamic_trailing_activations": 0,
            "dynamic_trailing_timeouts": 0,
            "dynamic_trailing_cancel_failures": 0,
        }
        events: list[ExecutionEvent] = []
        fills: list[ExecutionFill] = []
        consecutive_failures = 0
        lock_acquired = False

        try:
            # Phase 1 — Init
            events.append(make_event(exec_run_id, EventType.RUN_STARTED, f"Exec run {exec_run_id} started"))
            lock_acquired = self._repo.acquire_execution_lock(account_id=resolved_account_id, exec_run_id=exec_run_id)
            if not lock_acquired:
                events.append(make_event(
                    exec_run_id,
                    EventType.RUN_LOCKED,
                    f"Execution already active for account_id={resolved_account_id}",
                    payload={"account_id": resolved_account_id},
                ))
                metrics["status"] = "ABORTED"
                return metrics

            # Phase 2 — Pre-flight
            targets = self._repo.load_portfolio_targets(
                risk_run_id=risk_run_id,
                trade_date=trade_date,
                account_id=resolved_account_id,
            )
            if not targets:
                events.append(make_event(exec_run_id, EventType.PRECHECK_FAILED, "No portfolio targets found"))
                metrics["status"] = "ABORTED"
                self._emit_progress(
                    metrics,
                    current=0,
                    total=1,
                    label="⚙️ Progression execution — pré-check",
                    phase="precheck",
                    unit="étapes",
                )
                return metrics

            actual_risk_run_id = targets[0].risk_run_id
            actual_trade_date = trade_date or targets[0].trade_date
            metrics["targets"] = len(targets)
            metrics["total_target_notional"] = round(sum(float(t.target_notional or (t.target_shares * t.entry_price)) for t in targets), 2)
            metrics["total_initial_risk_dollars"] = round(sum(float(t.initial_risk_dollars or 0.0) for t in targets), 2)
            metrics["total_risk_budget_dollars"] = round(sum(float(t.risk_budget_dollars or 0.0) for t in targets), 2)
            metrics["max_target_weight"] = round(max((float(t.target_weight) for t in targets), default=0.0), 4)
            metrics["targets_with_risk_controls"] = sum(1 for t in targets if t.stop_price_initial is not None or (t.risk_per_share or 0.0) > 0)
            metrics["targets_with_broker_initial_stop"] = sum(
                1 for t in targets
                if resolve_initial_stop_price(float(t.entry_price), t) is not None
            )
            metrics["targets_eligible_for_dynamic_trailing"] = int(metrics["targets_with_broker_initial_stop"]) if self._cfg.enable_dynamic_trailing_transition else 0
            metrics["targets_with_trailing_fallback"] = max(
                len(targets) - int(metrics["targets_with_broker_initial_stop"]),
                0,
            )
            metrics["stale_price_targets"] = sum(
                1 for t in targets
                if t.price_asof_date is not None and actual_trade_date is not None and t.price_asof_date < actual_trade_date
            )
            target_by_symbol = {t.symbol: t for t in targets}
            self._emit_progress(
                metrics,
                current=len(targets),
                total=max(len(targets), 1),
                label="⚙️ Progression execution — pré-check & chargement des cibles",
                phase="precheck",
            )

            self._repo.insert_execution_run(
                exec_run_id=exec_run_id,
                risk_run_id=actual_risk_run_id,
                trade_date=actual_trade_date,
                broker_mode=self._cfg.broker_mode,
                dry_run=self._cfg.dry_run,
                total_targets=len(targets),
                account_id=resolved_account_id,
                execution_profile=self._cfg.execution_profile,
                submission_window=self._cfg.submission_window,
            )
            try:
                self._repo.snapshot_execution_targets(
                    exec_run_id=exec_run_id,
                    account_id=resolved_account_id,
                    targets=targets,
                )
            except Exception as exc:
                LOGGER.debug("Target snapshot skipped: %s", exc)

            # Circuit breaker check (injection)
            if self._circuit_breaker is not None:
                try:
                    if self._circuit_breaker.is_active():
                        events.append(make_event(exec_run_id, EventType.CIRCUIT_BREAKER_ACTIVE, "CB active — aborting"))
                        self._repo.update_execution_run_status(exec_run_id, "ABORTED")
                        metrics["status"] = "ABORTED"
                        self._emit_progress(
                            metrics,
                            current=1,
                            total=1,
                            label="⚙️ Progression execution — arrêt circuit breaker",
                            phase="precheck",
                            unit="étapes",
                        )
                        return metrics
                except Exception as exc:
                    LOGGER.warning("Circuit breaker check failed: %s", exc)

            # Market hours check
            if not self._cfg.allow_outside_rth and not self._cfg.dry_run:
                try:
                    if not self._broker.is_market_open():
                        events.append(make_event(exec_run_id, EventType.PRECHECK_FAILED, "Market closed"))
                        self._repo.update_execution_run_status(exec_run_id, "ABORTED")
                        metrics["status"] = "ABORTED"
                        self._emit_progress(
                            metrics,
                            current=1,
                            total=1,
                            label="⚙️ Progression execution — marché fermé",
                            phase="precheck",
                            unit="étapes",
                        )
                        return metrics
                except Exception:
                    LOGGER.warning("Cannot check market clock — proceeding")

            events.append(make_event(exec_run_id, EventType.PRECHECK_OK, f"{len(targets)} targets loaded"))
            if metrics["stale_price_targets"] > 0:
                events.append(make_event(
                    exec_run_id,
                    EventType.PRECHECK_OK,
                    f"WARNING: {metrics['stale_price_targets']} targets utilisent un price_asof_date antérieur au trade_date",
                    payload={"stale_price_targets": metrics["stale_price_targets"]},
                ))

            account_state = self._build_account_constraint_state()
            events.append(make_event(
                exec_run_id,
                EventType.ACCOUNT_CONSTRAINT_APPLIED,
                (
                    f"Account constraints: type={account_state.account_type} "
                    f"pdt={account_state.effective_pdt_rule} swing_only={account_state.swing_only}"
                ),
                payload={
                    "account_type": account_state.account_type,
                    "effective_pdt_rule": account_state.effective_pdt_rule,
                    "swing_only": account_state.swing_only,
                    "equity": account_state.equity,
                    "buying_power_available": account_state.buying_power_available,
                    "settled_cash_available": account_state.settled_cash_available,
                    "daytrade_count": account_state.daytrade_count,
                    "remaining_day_trade_slots": account_state.remaining_day_trade_slots,
                },
            ))
            self._snapshot_account_constraints(exec_run_id, account_state)

            # Phase 2b — Corporate actions : alerter sur splits/dividendes pending
            try:
                from corporate_actions.db_io import CorporateActionRepository
                ca_repo = CorporateActionRepository(engine=self._repo.engine)
                pending_events = ca_repo.load_pending_events(as_of=actual_trade_date)
                if pending_events:
                    target_symbols = {t.symbol.upper() for t in targets}
                    pending_for_targets = [e for e in pending_events if e.symbol.upper() in target_symbols]
                    if pending_for_targets:
                        symbols_str = ", ".join(sorted({e.symbol for e in pending_for_targets}))
                        LOGGER.warning(
                            "Corporate actions pending NON appliquees pour %d symboles cibles : %s. "
                            "Les quantites/prix peuvent etre obsoletes. Executer 'python -m corporate_actions apply' avant.",
                            len(pending_for_targets), symbols_str,
                        )
                        events.append(make_event(
                            exec_run_id, EventType.PRECHECK_OK,
                            f"WARNING: {len(pending_for_targets)} corporate actions pending pour {symbols_str}",
                        ))
            except Exception as exc:
                LOGGER.debug("Corporate actions check skipped: %s", exc)

            # Phase 3 — Build intents, filter duplicates
            entry_intents = build_entry_intents(targets, self._cfg, exec_run_id)
            existing_keys: set[str] = set()
            if not self._cfg.dry_run:
                try:
                    existing_keys = self._repo.load_submitted_idempotency_keys(exec_run_id)
                except Exception:
                    pass

            new_intents: list[OrderIntent] = []
            for intent in entry_intents:
                if intent.idempotency_key in existing_keys:
                    events.append(make_event(
                        exec_run_id, EventType.INTENT_SKIPPED_DUPLICATE,
                        f"Duplicate: {intent.symbol}", symbol=intent.symbol, intent_id=intent.intent_id,
                    ))
                    metrics["skipped"] += 1
                else:
                    events.append(make_event(
                        exec_run_id, EventType.INTENT_BUILT,
                        f"Intent: {intent.symbol} {intent.side} {intent.qty}",
                        symbol=intent.symbol, intent_id=intent.intent_id,
                    ))
                    new_intents.append(intent)
            self._emit_progress(
                metrics,
                current=len(new_intents),
                total=max(len(entry_intents), 1),
                label="⚙️ Progression execution — construction des intents",
                phase="build_intents",
            )

            # Phase 4 — Submit entries
            submitted_orders: dict[str, tuple[OrderIntent, BrokerOrder]] = {}
            batch_count = 0
            submit_total = max(len(new_intents), 1)
            submit_processed = 0
            for intent in new_intents:
                submit_processed += 1
                if not self._reserve_account_capacity_for_intent(intent, account_state, exec_run_id, events, metrics):
                    self._emit_progress(
                        metrics,
                        current=submit_processed,
                        total=submit_total,
                        label="⚙️ Progression execution — soumission des ordres d'entrée",
                        phase="submit_entries",
                        item=intent.symbol,
                    )
                    continue

                # Kill switch
                if self._cfg.enable_kill_switch and consecutive_failures >= self._cfg.max_consecutive_failures:
                    events.append(make_event(exec_run_id, EventType.KILL_SWITCH_ACTIVATED,
                                             f"Kill switch after {consecutive_failures} failures"))
                    break

                # Throttle
                if batch_count > 0 and batch_count % self._cfg.execution_batch_size == 0:
                    events.append(make_event(exec_run_id, EventType.THROTTLE_WAIT, "Batch throttle"))
                if self._cfg.inter_order_delay_ms > 0 and batch_count > 0:
                    time.sleep(self._cfg.inter_order_delay_ms / 1000.0)

                # Persist intent
                self._persist_order_request_state(intent, status=OrderStatus.NEW)

                if self._cfg.dry_run:
                    self._persist_order_request_state(intent, status=OrderStatus.SIMULATED)
                    events.append(make_event(
                        exec_run_id, EventType.DRY_RUN_SIMULATED,
                        f"DRY RUN: {intent.symbol} {intent.side} {intent.qty}",
                        symbol=intent.symbol, intent_id=intent.intent_id,
                    ))
                    metrics["submitted"] += 1
                    batch_count += 1
                    self._emit_progress(
                        metrics,
                        current=submit_processed,
                        total=submit_total,
                        label="⚙️ Progression execution — soumission des ordres d'entrée",
                        phase="submit_entries",
                        item=intent.symbol,
                    )
                    continue

                # Submit to broker avec retry UNIQUEMENT sur erreurs reseau / 5xx / 429
                # Les erreurs 4xx (403 = client_order_id duplique, symbole interdit, etc.)
                # sont des erreurs permanentes : on ne retante PAS.
                order: BrokerOrder | None = None
                for attempt in range(self._cfg.max_order_retries + 1):
                    try:
                        order = self._broker.submit_intent(intent)
                        consecutive_failures = 0
                        break
                    except BrokerApiError as exc:
                        # Erreur 4xx : permanente, log detaille + pas de retry
                        body_info = f" — {exc.body[:200]}" if exc.body else ""
                        LOGGER.error(
                            "Ordre refuse par le broker [%s] %s : %s%s",
                            exc.status_code, intent.symbol, exc, body_info,
                        )
                        consecutive_failures += 1
                        metrics["failed"] += 1
                        events.append(make_event(
                            exec_run_id, EventType.ORDER_REJECTED,
                            f"[{exc.status_code}] {intent.symbol}: {str(exc)[:200]}",
                            symbol=intent.symbol, intent_id=intent.intent_id,
                        ))
                        self._persist_order_request_state(
                            intent,
                            status=OrderStatus.REJECTED,
                            failure_reason=f"[{exc.status_code}] {str(exc)[:200]}",
                        )
                        break  # pas de retry sur 4xx
                    except Exception as exc:
                        # Erreur reseau / timeout : on retente avec backoff
                        LOGGER.warning("Submit failed for %s attempt %d: %s", intent.symbol, attempt, exc)
                        if attempt < self._cfg.max_order_retries:
                            time.sleep(self._cfg.retry_base_delay_seconds * (2 ** attempt))
                        else:
                            consecutive_failures += 1
                            metrics["failed"] += 1
                            events.append(make_event(
                                exec_run_id, EventType.ORDER_REJECTED,
                                f"Submit failed after retries: {intent.symbol}",
                                symbol=intent.symbol, intent_id=intent.intent_id,
                            ))
                            self._persist_order_request_state(
                                intent,
                                status=OrderStatus.FAILED,
                                failure_reason=str(exc)[:200],
                            )

                if order is not None:
                    events.append(make_event(
                        exec_run_id, EventType.ORDER_SUBMITTED,
                        f"Submitted: {intent.symbol} → {order.broker_order_id}",
                        symbol=intent.symbol, broker_order_id=order.broker_order_id,
                        intent_id=intent.intent_id,
                    ))
                    submitted_orders[intent.intent_id] = (intent, order)
                    metrics["submitted"] += 1
                    self._persist_order_request_state(intent, status=order.status)
                    self._persist_broker_order_state(intent, order)

                batch_count += 1
                self._emit_progress(
                    metrics,
                    current=submit_processed,
                    total=submit_total,
                    label="⚙️ Progression execution — soumission des ordres d'entrée",
                    phase="submit_entries",
                    item=intent.symbol,
                )

            # Phase 5 — Poll fills
            # Si le marche est ferme, les ordres resteront en "accepted" (SUBMITTED)
            # et ne seront remplis qu'a l'ouverture : on saute le polling pour eviter
            # d'attendre 120s × N ordres inutilement.
            market_open_for_poll = True
            if not self._cfg.dry_run:
                try:
                    market_open_for_poll = self._broker.is_market_open()
                except Exception:
                    market_open_for_poll = False

            if not self._cfg.dry_run and market_open_for_poll:
                poll_total = max(len(submitted_orders), 1)
                poll_processed = 0
                for intent_id, (intent, order) in list(submitted_orders.items()):
                    poll_processed += 1
                    filled_order = self._poll_until_terminal(order.broker_order_id, intent.intent_id, exec_run_id)
                    if filled_order and filled_order.status == OrderStatus.FILLED:
                        metrics["filled"] += 1
                        fill = self._build_fill(filled_order, intent)
                        fills.append(fill)
                        try:
                            self._repo.insert_execution_broker_fill(fill, account_id=resolved_account_id)
                        except Exception:
                            LOGGER.debug("Could not persist Sprint 2 fill", exc_info=True)

                        # Slippage alert
                        if abs(fill.slippage_bps) > self._cfg.max_slippage_bps:
                            events.append(make_event(
                                exec_run_id, EventType.SLIPPAGE_ALERT,
                                f"Slippage {fill.slippage_bps:.1f} bps on {intent.symbol}",
                                symbol=intent.symbol,
                            ))

                        # Phase 6 — Submit children (synthetic bracket)
                        child_events = self._submit_children(
                            intent,
                            filled_order,
                            exec_run_id,
                            account_state=account_state,
                            metrics=metrics,
                            target=target_by_symbol.get(intent.symbol),
                        )
                        events.extend(child_events)

                        submitted_orders[intent_id] = (intent, filled_order)
                    elif filled_order:
                        events.append(make_event(
                            exec_run_id, EventType.ORDER_CANCELED if filled_order.status == OrderStatus.CANCELED else EventType.ORDER_REJECTED,
                            f"{filled_order.status}: {intent.symbol}",
                            symbol=intent.symbol, broker_order_id=filled_order.broker_order_id,
                        ))
                    self._emit_progress(
                        metrics,
                        current=poll_processed,
                        total=poll_total,
                        label="⚙️ Progression execution — suivi des fills",
                        phase="poll_fills",
                        item=intent.symbol,
                    )
            elif not self._cfg.dry_run and not market_open_for_poll and submitted_orders:
                LOGGER.info(
                    "Marche ferme — %d ordres soumis, pas de polling. "
                    "Les ordres seront remplis a l'ouverture (time_in_force=day).",
                    len(submitted_orders),
                )
                events.append(make_event(
                    exec_run_id, EventType.PRECHECK_OK,
                    f"Market closed — {len(submitted_orders)} orders queued, no polling. "
                    "They will fill at next market open.",
                ))
                self._emit_progress(
                    metrics,
                    current=len(submitted_orders),
                    total=max(len(submitted_orders), 1),
                    label="⚙️ Progression execution — ordres en attente d'ouverture marché",
                    phase="poll_fills",
                )

            if not self._cfg.dry_run:
                try:
                    sync_metrics = BrokerStateSynchronizer(
                        self._repo,
                        self._broker,
                        broker_mode=self._cfg.broker_mode,
                    ).sync(
                        exec_run_id=exec_run_id,
                        account_id=resolved_account_id,
                        order_limit=max(200, len(submitted_orders) * 10) if submitted_orders else 200,
                    )
                    sync_metrics = {key: int(value or 0) for key, value in sync_metrics.items()}
                    metrics["broker_orders_synced"] = sync_metrics["orders_synced"]
                    metrics["broker_fills_synced"] = sync_metrics["fills_synced"]
                    metrics["broker_positions_observed"] = sync_metrics["broker_positions"]
                    metrics["execution_positions_projected"] = sync_metrics["positions_projected"]
                    metrics["execution_position_lots_projected"] = sync_metrics["lots_projected"]
                    metrics["broker_sync_unmatched_orders"] = sync_metrics["unmatched_orders"]
                    events.append(make_event(
                        exec_run_id,
                        EventType.BROKER_SYNC_COMPLETED,
                        (
                            "Broker sync completed: "
                            f"orders={sync_metrics['orders_synced']} fills={sync_metrics['fills_synced']} "
                            f"positions={sync_metrics['positions_projected']} lots={sync_metrics['lots_projected']}"
                        ),
                        payload=sync_metrics,
                    ))
                    self._emit_progress(
                        metrics,
                        current=1,
                        total=1,
                        label="⚙️ Progression execution — synchronisation broker",
                        phase="broker_sync",
                        unit="étapes",
                    )
                except Exception as exc:
                    LOGGER.warning("Broker state sync failed: %s", exc, exc_info=True)
                    events.append(make_event(
                        exec_run_id,
                        EventType.BROKER_SYNC_FAILED,
                        f"Broker sync failed: {str(exc)[:160]}",
                    ))
                    self._emit_progress(
                        metrics,
                        current=1,
                        total=1,
                        label="⚙️ Progression execution — synchronisation broker",
                        phase="broker_sync",
                        unit="étapes",
                    )

            # Phase 8 — Reconciliation
            if self._cfg.reconcile_after_submit and not self._cfg.dry_run:
                try:
                    positions = self._broker.get_all_positions()
                    self._repo.snapshot_broker_positions(exec_run_id, self._cfg.broker_mode, positions, account_id=resolved_account_id)
                    reconciliation_results = reconcile_execution_state(
                        exec_run_id=exec_run_id,
                        account_id=resolved_account_id,
                        targets=targets,
                        broker_positions=positions,
                        internal_positions=self._repo.load_execution_positions(account_id=resolved_account_id),
                        open_order_state=self._repo.load_open_reconciliation_order_state(account_id=resolved_account_id),
                        protection_state=self._repo.load_reconciliation_protection_state(account_id=resolved_account_id),
                        tolerance=self._cfg.reconcile_tolerance_shares,
                        buying_power_available=account_state.buying_power_available,
                    )
                    self._repo.replace_execution_reconciliation_results(
                        exec_run_id=exec_run_id,
                        account_id=resolved_account_id,
                        results=reconciliation_results,
                    )
                    action_results = [result for result in reconciliation_results if result.action != "none"]
                    safe_auto_results = [result for result in action_results if result.reconciliation_status == ReconciliationStatus.SAFE_AUTO]
                    manual_review_results = [result for result in reconciliation_results if result.reconciliation_status == ReconciliationStatus.MANUAL_REVIEW]
                    blocked_results = [result for result in reconciliation_results if result.reconciliation_status == ReconciliationStatus.BLOCKED]
                    metrics["reconciliation_results"] = len(reconciliation_results)
                    metrics["reconciliation_safe_auto"] = len([result for result in reconciliation_results if result.reconciliation_status == ReconciliationStatus.SAFE_AUTO])
                    metrics["reconciliation_manual_review"] = len(manual_review_results)
                    metrics["reconciliation_blocked"] = len(blocked_results)
                    if action_results or manual_review_results or blocked_results:
                        events.append(make_event(exec_run_id, EventType.RECONCILE_DIFF,
                                                 (
                                                     "Reconciliation analyzed: "
                                                     f"actionable={len(action_results)} "
                                                     f"safe_auto={len(safe_auto_results)} "
                                                     f"manual_review={len(manual_review_results)} "
                                                     f"blocked={len(blocked_results)}"
                                                 ),
                                                 payload={
                                                     "actionable": len(action_results),
                                                     "safe_auto": len(safe_auto_results),
                                                     "manual_review": len(manual_review_results),
                                                     "blocked": len(blocked_results),
                                                 }))
                        if self._cfg.auto_rebalance_on_reconcile and safe_auto_results:
                            safe_auto_diffs = [
                                ReconcileDiff(
                                    symbol=result.symbol,
                                    target_qty=int(result.target_qty),
                                    broker_qty=result.broker_position_qty,
                                    delta=result.position_delta,
                                    action=result.action,
                                )
                                for result in safe_auto_results
                            ]
                            rebalance_events = self._submit_rebalance_orders(
                                safe_auto_diffs, exec_run_id, targets, metrics, account_state,
                            )
                            events.extend(rebalance_events)
                    else:
                        events.append(make_event(exec_run_id, EventType.RECONCILE_OK, "Reconciliation OK"))
                    self._emit_progress(
                        metrics,
                        current=1,
                        total=1,
                        label="⚙️ Progression execution — réconciliation",
                        phase="reconcile",
                        unit="étapes",
                    )
                except Exception as exc:
                    LOGGER.warning("Reconciliation failed: %s", exc)
                    self._emit_progress(
                        metrics,
                        current=1,
                        total=1,
                        label="⚙️ Progression execution — réconciliation",
                        phase="reconcile",
                        unit="étapes",
                    )

            # Phase 9 — TCA
            if self._cfg.enable_tca and fills:
                tca = build_tca_summary(fills, self._cfg.max_slippage_bps)
                events.append(make_event(
                    exec_run_id, EventType.TCA_SUMMARY,
                    f"TCA: avg_slip={tca.avg_slippage_bps:.1f}bps alerts={tca.slippage_alerts}",
                    payload={
                        "total_filled": tca.total_filled,
                        "avg_slippage_bps": tca.avg_slippage_bps,
                        "max_slippage_bps": tca.max_slippage_bps,
                        "total_implementation_shortfall": tca.total_implementation_shortfall,
                    },
                ))

            # Phase 10 — Finalize
            events.append(make_event(exec_run_id, EventType.RUN_COMPLETED,
                                     f"Run completed: {metrics}"))
            self._repo.update_execution_run_status(
                exec_run_id, "COMPLETED",
                total_submitted=metrics["submitted"], total_filled=metrics["filled"],
            )
            metrics["status"] = "COMPLETED"
            self._emit_progress(
                metrics,
                current=1,
                total=1,
                label="⚙️ Progression execution — finalisation",
                phase="finalize",
                unit="étapes",
            )

        except Exception as exc:
            LOGGER.exception("Execution run failed: %s", exc)
            events.append(make_event(exec_run_id, EventType.RUN_FAILED, str(exc)[:255]))
            try:
                self._repo.update_execution_run_status(exec_run_id, "FAILED", error_message=str(exc)[:255])
            except Exception:
                pass
            metrics["status"] = "FAILED"
            self._emit_progress(
                metrics,
                current=1,
                total=1,
                label="⚙️ Progression execution — échec du run",
                phase="failed",
                unit="étapes",
            )
        finally:
            self._persist_events(events)
            if lock_acquired:
                try:
                    self._repo.release_execution_lock(account_id=resolved_account_id, exec_run_id=exec_run_id)
                except Exception:
                    LOGGER.warning("Unable to release execution lock for account_id=%s", resolved_account_id, exc_info=True)
        return metrics

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Sprint S7 - account capacity helpers (delegated to ``account_state``).
    # ------------------------------------------------------------------

    def _build_account_constraint_state(self) -> _AccountConstraintState:
        return _build_account_constraint_state_impl(self._cfg, self._broker)

    @staticmethod
    def _safe_float(value: object, *, default: float = 0.0) -> float:
        return _safe_float_impl(value, default=default)

    def _estimate_intent_notional(self, intent: OrderIntent) -> float:
        return _estimate_intent_notional_impl(intent)

    def _reserve_account_capacity_for_intent(
        self,
        intent: OrderIntent,
        account_state: _AccountConstraintState,
        exec_run_id: str,
        events: list[ExecutionEvent],
        metrics: dict[str, int],
    ) -> bool:
        return _reserve_account_capacity_for_intent_impl(
            intent, account_state, exec_run_id, events, metrics
        )

    def _should_defer_children(
        self,
        account_state: _AccountConstraintState,
    ) -> tuple[bool, str | None]:
        return _should_defer_children_impl(account_state)

    def _poll_until_terminal(self, broker_order_id: str, intent_id: str, exec_run_id: str) -> BrokerOrder | None:
        deadline = time.monotonic() + self._cfg.fill_timeout_seconds
        while time.monotonic() < deadline:
            try:
                order = self._broker.poll_order_status(broker_order_id, intent_id)
                if is_terminal(order.status):
                    return order
                time.sleep(self._cfg.poll_interval_seconds)
            except Exception as exc:
                LOGGER.warning("Poll error for %s: %s", broker_order_id, exc)
                time.sleep(self._cfg.poll_interval_seconds)
        LOGGER.warning("Fill timeout for order %s", broker_order_id)
        return None

    def _build_fill(self, order: BrokerOrder, intent: OrderIntent) -> ExecutionFill:
        fill_price = order.avg_fill_price or intent.decision_price
        slip = compute_slippage_bps(fill_price, intent.decision_price)
        ishort = compute_implementation_shortfall(fill_price, intent.decision_price, order.filled_qty)
        return ExecutionFill(
            fill_id=uuid.uuid4().hex[:16],
            broker_order_id=order.broker_order_id,
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            filled_qty=order.filled_qty,
            avg_fill_price=fill_price,
            fill_timestamp=datetime.now(timezone.utc),
            decision_price=intent.decision_price,
            slippage_bps=slip,
            implementation_shortfall=ishort,
        )

    def _snapshot_account_constraints(self, exec_run_id: str, account_state: _AccountConstraintState) -> None:
        try:
            self._repo.snapshot_broker_account(
                exec_run_id,
                account_id=self._cfg.resolved_account_id,
                broker_mode=self._cfg.broker_mode,
                snapshot={
                    "equity": account_state.equity,
                    "cash": account_state.settled_cash_available,
                    "settled_cash": account_state.settled_cash_available,
                    "buying_power": account_state.buying_power_available,
                    "daytrade_count": account_state.daytrade_count,
                    "account_type": account_state.account_type,
                    "effective_pdt_rule": account_state.effective_pdt_rule,
                },
                snapshot_kind="preflight",
            )
        except Exception:
            LOGGER.debug("Could not persist broker account snapshot", exc_info=True)

    def _persist_order_request_state(
        self,
        intent: OrderIntent,
        *,
        status: str,
        failure_reason: str | None = None,
    ) -> None:
        try:
            self._repo.upsert_execution_order_request_from_intent(
                intent,
                account_id=self._cfg.resolved_account_id,
                status=status,
                failure_reason=failure_reason,
            )
        except Exception:
            LOGGER.debug("Could not persist Sprint 2 request for %s", intent.intent_id, exc_info=True)

    def _persist_broker_order_state(self, intent: OrderIntent, order: BrokerOrder) -> None:
        try:
            self._repo.upsert_execution_broker_order(
                intent,
                order,
                account_id=self._cfg.resolved_account_id,
                raw_payload=intent_to_alpaca_payload(intent),
            )
        except Exception:
            LOGGER.debug("Could not persist Sprint 2 broker order for %s", intent.intent_id, exc_info=True)

    def _persist_child_order_state(
        self,
        intent: OrderIntent,
        order: BrokerOrder,
    ) -> None:
        self._persist_order_request_state(intent, status=order.status)
        self._persist_broker_order_state(intent, order)

    def _cancel_child_for_transition(
        self,
        intent: OrderIntent,
        order: BrokerOrder,
        exec_run_id: str,
    ) -> tuple[bool, BrokerOrder]:
        try:
            cancel_requested = self._broker.cancel_broker_order(order.broker_order_id)
        except Exception:
            return False, order
        if not cancel_requested:
            return False, order

        latest_order = order
        deadline = time.monotonic() + self._cfg.cancel_timeout_seconds
        while time.monotonic() < deadline:
            try:
                latest_order = self._broker.poll_order_status(order.broker_order_id, intent.intent_id)
            except Exception:
                time.sleep(self._cfg.poll_interval_seconds)
                continue
            if latest_order.status == OrderStatus.CANCELED:
                self._persist_child_order_state(intent, latest_order)
                return True, latest_order
            if latest_order.status in {OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.FAILED, OrderStatus.EXPIRED}:
                self._persist_child_order_state(intent, latest_order)
                return False, latest_order
            time.sleep(self._cfg.poll_interval_seconds)
        return False, latest_order

    def _maybe_activate_dynamic_trailing(
        self,
        parent: OrderIntent,
        fill_qty: float,
        fill_price: float,
        exec_run_id: str,
        *,
        target: Any | None,
        initial_stop_intent: OrderIntent | None,
        initial_stop_order: BrokerOrder | None,
        metrics: dict[str, int],
    ) -> list[ExecutionEvent]:
        return _maybe_activate_dynamic_trailing_impl(
            self,
            parent,
            fill_qty,
            fill_price,
            exec_run_id,
            target=target,
            initial_stop_intent=initial_stop_intent,
            initial_stop_order=initial_stop_order,
            metrics=metrics,
        )

    def _submit_children(
        self,
        parent: OrderIntent,
        filled_order: BrokerOrder,
        exec_run_id: str,
        *,
        account_state: _AccountConstraintState,
        metrics: dict[str, int],
        target: Any | None = None,
    ) -> list[ExecutionEvent]:
        return _submit_children_impl(
            self,
            parent,
            filled_order,
            exec_run_id,
            account_state=account_state,
            metrics=metrics,
            target=target,
        )

    def _submit_rebalance_orders(
        self,
        action_diffs: list,
        exec_run_id: str,
        targets: list,
        metrics: dict[str, int],
        account_state: _AccountConstraintState,
    ) -> list[ExecutionEvent]:
        return _submit_rebalance_orders_impl(
            self,
            action_diffs,
            exec_run_id,
            targets,
            metrics,
            account_state,
        )

    def _persist_events(self, events: list[ExecutionEvent]) -> None:
        for ev in events:
            try:
                self._repo.insert_execution_event(event_to_db_dict(ev))
            except Exception:
                LOGGER.debug("Could not persist event %s", ev.event_type)
