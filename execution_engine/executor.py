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
from datetime import date, datetime, timezone
from typing import Any, Optional

from execution_engine.audit import (
    build_run_id,
    event_to_db_dict,
    fill_to_db_dict,
    make_event,
    order_intent_to_db_dict,
)
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.config import ExecutionConfig
from execution_engine.db_io import ExecutionRepository
from execution_engine.models import (
    BrokerOrder,
    EventType,
    ExecutionEvent,
    ExecutionFill,
    OrderIntent,
    OrderStatus,
)
from execution_engine.oco_manager import OcoManager
from execution_engine.order_intents import (
    build_entry_intents,
    build_take_profit_intent,
    build_trailing_stop_intent,
    build_rebalance_sell_intent,
    build_rebalance_buy_intent,
)
from execution_engine.reconciliation import reconcile_targets_vs_broker
from execution_engine.state_machine import is_terminal
from execution_engine.tca import build_tca_summary, compute_implementation_shortfall, compute_slippage_bps
from service.alpaca.trading_client import BrokerApiError

LOGGER = logging.getLogger(__name__)


class ProductionExecutor:
    """Orchestrateur de l execution."""

    def __init__(
        self,
        config: ExecutionConfig,
        repo: ExecutionRepository,
        broker: BrokerAdapter,
        oco: OcoManager,
        circuit_breaker: Optional[Any] = None,
    ) -> None:
        self._cfg = config
        self._repo = repo
        self._broker = broker
        self._oco = oco
        self._circuit_breaker = circuit_breaker

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def execute_run(
        self,
        risk_run_id: str | None = None,
        trade_date: date | None = None,
    ) -> dict[str, int]:
        exec_run_id = build_run_id()
        metrics: dict[str, int] = {
            "targets": 0, "submitted": 0, "filled": 0, "failed": 0, "skipped": 0,
            "rebalance_submitted": 0, "rebalance_failed": 0,
        }
        events: list[ExecutionEvent] = []
        fills: list[ExecutionFill] = []
        consecutive_failures = 0

        try:
            # Phase 1 — Init
            events.append(make_event(exec_run_id, EventType.RUN_STARTED, f"Exec run {exec_run_id} started"))

            # Phase 2 — Pre-flight
            targets = self._repo.load_portfolio_targets(risk_run_id=risk_run_id, trade_date=trade_date)
            if not targets:
                events.append(make_event(exec_run_id, EventType.PRECHECK_FAILED, "No portfolio targets found"))
                self._persist_events(events)
                return metrics

            actual_risk_run_id = targets[0].risk_run_id
            actual_trade_date = trade_date or targets[0].trade_date
            metrics["targets"] = len(targets)

            self._repo.insert_execution_run(
                exec_run_id=exec_run_id,
                risk_run_id=actual_risk_run_id,
                trade_date=actual_trade_date,
                broker_mode=self._cfg.broker_mode,
                dry_run=self._cfg.dry_run,
                total_targets=len(targets),
            )

            # Circuit breaker check (injection)
            if self._circuit_breaker is not None:
                try:
                    if self._circuit_breaker.is_active():
                        events.append(make_event(exec_run_id, EventType.CIRCUIT_BREAKER_ACTIVE, "CB active — aborting"))
                        self._persist_events(events)
                        self._repo.update_execution_run_status(exec_run_id, "ABORTED")
                        return metrics
                except Exception as exc:
                    LOGGER.warning("Circuit breaker check failed: %s", exc)

            # Market hours check
            if not self._cfg.allow_outside_rth and not self._cfg.dry_run:
                try:
                    if not self._broker.is_market_open():
                        events.append(make_event(exec_run_id, EventType.PRECHECK_FAILED, "Market closed"))
                        self._persist_events(events)
                        self._repo.update_execution_run_status(exec_run_id, "ABORTED")
                        return metrics
                except Exception:
                    LOGGER.warning("Cannot check market clock — proceeding")

            events.append(make_event(exec_run_id, EventType.PRECHECK_OK, f"{len(targets)} targets loaded"))

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

            # Phase 4 — Submit entries
            submitted_orders: dict[str, tuple[OrderIntent, BrokerOrder]] = {}
            batch_count = 0
            for intent in new_intents:
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
                db_dict = order_intent_to_db_dict(intent, exec_run_id)
                try:
                    self._repo.upsert_execution_order(db_dict)
                except Exception:
                    LOGGER.debug("Could not persist intent (table may not exist in test)")

                if self._cfg.dry_run:
                    events.append(make_event(
                        exec_run_id, EventType.DRY_RUN_SIMULATED,
                        f"DRY RUN: {intent.symbol} {intent.side} {intent.qty}",
                        symbol=intent.symbol, intent_id=intent.intent_id,
                    ))
                    metrics["submitted"] += 1
                    batch_count += 1
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

                if order is not None:
                    events.append(make_event(
                        exec_run_id, EventType.ORDER_SUBMITTED,
                        f"Submitted: {intent.symbol} → {order.broker_order_id}",
                        symbol=intent.symbol, broker_order_id=order.broker_order_id,
                        intent_id=intent.intent_id,
                    ))
                    submitted_orders[intent.intent_id] = (intent, order)
                    metrics["submitted"] += 1
                    # Update DB with broker_order_id
                    try:
                        db_dict["broker_order_id"] = order.broker_order_id
                        db_dict["status"] = order.status
                        self._repo.upsert_execution_order(db_dict)
                    except Exception:
                        pass

                batch_count += 1

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
                for intent_id, (intent, order) in list(submitted_orders.items()):
                    filled_order = self._poll_until_terminal(order.broker_order_id, intent.intent_id, exec_run_id)
                    if filled_order and filled_order.status == OrderStatus.FILLED:
                        metrics["filled"] += 1
                        fill = self._build_fill(filled_order, intent)
                        fills.append(fill)
                        try:
                            self._repo.insert_execution_fill(fill_to_db_dict(fill, exec_run_id))
                        except Exception:
                            pass

                        # Slippage alert
                        if abs(fill.slippage_bps) > self._cfg.max_slippage_bps:
                            events.append(make_event(
                                exec_run_id, EventType.SLIPPAGE_ALERT,
                                f"Slippage {fill.slippage_bps:.1f} bps on {intent.symbol}",
                                symbol=intent.symbol,
                            ))

                        # Phase 6 — Submit children (synthetic bracket)
                        child_events = self._submit_children(intent, filled_order, exec_run_id)
                        events.extend(child_events)

                        submitted_orders[intent_id] = (intent, filled_order)
                    elif filled_order:
                        events.append(make_event(
                            exec_run_id, EventType.ORDER_CANCELED if filled_order.status == OrderStatus.CANCELED else EventType.ORDER_REJECTED,
                            f"{filled_order.status}: {intent.symbol}",
                            symbol=intent.symbol, broker_order_id=filled_order.broker_order_id,
                        ))
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

            # Phase 8 — Reconciliation
            if self._cfg.reconcile_after_submit and not self._cfg.dry_run:
                try:
                    positions = self._broker.get_all_positions()
                    self._repo.snapshot_broker_positions(exec_run_id, self._cfg.broker_mode, positions)
                    diffs = reconcile_targets_vs_broker(targets, positions, self._cfg.reconcile_tolerance_shares)
                    action_diffs = [d for d in diffs if d.action != "none"]
                    if action_diffs:
                        events.append(make_event(exec_run_id, EventType.RECONCILE_DIFF,
                                                 f"Reconciliation diffs found: {len(action_diffs)}"))
                        # Vente / achat automatique si auto_rebalance_on_reconcile
                        if self._cfg.auto_rebalance_on_reconcile:
                            rebalance_events = self._submit_rebalance_orders(
                                action_diffs, exec_run_id, targets, metrics,
                            )
                            events.extend(rebalance_events)
                    else:
                        events.append(make_event(exec_run_id, EventType.RECONCILE_OK, "Reconciliation OK"))
                except Exception as exc:
                    LOGGER.warning("Reconciliation failed: %s", exc)

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

        except Exception as exc:
            LOGGER.exception("Execution run failed: %s", exc)
            events.append(make_event(exec_run_id, EventType.RUN_FAILED, str(exc)[:255]))
            try:
                self._repo.update_execution_run_status(exec_run_id, "FAILED", error_message=str(exc)[:255])
            except Exception:
                pass

        self._persist_events(events)
        return metrics

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

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

    def _submit_children(self, parent: OrderIntent, filled_order: BrokerOrder, exec_run_id: str) -> list[ExecutionEvent]:
        events: list[ExecutionEvent] = []
        fill_qty = filled_order.filled_qty
        fill_price = filled_order.avg_fill_price or parent.decision_price
        if fill_qty <= 0:
            return events

        tp_intent = build_take_profit_intent(parent, fill_qty, fill_price, self._cfg)
        ts_intent = build_trailing_stop_intent(parent, fill_qty, self._cfg)

        for child in [tp_intent, ts_intent]:
            try:
                child_order = self._broker.submit_intent(child)
                db_dict = order_intent_to_db_dict(child, exec_run_id, status=child_order.status)
                db_dict["broker_order_id"] = child_order.broker_order_id
                try:
                    self._repo.upsert_execution_order(db_dict)
                except Exception:
                    pass
            except Exception as exc:
                LOGGER.warning("Child submit failed for %s %s: %s", child.symbol, child.intent_role, exc)

        events.append(make_event(
            exec_run_id, EventType.CHILDREN_SUBMITTED,
            f"Bracket children for {parent.symbol}: TP + TS",
            symbol=parent.symbol, intent_id=parent.intent_id,
        ))
        return events

    def _submit_rebalance_orders(
        self,
        action_diffs: list,
        exec_run_id: str,
        targets: list,
        metrics: dict[str, int],
    ) -> list[ExecutionEvent]:
        """
        Soumet des ordres de vente (sell_excess) ou d'achat (buy_more)
        pour corriger les ecarts detectes en reconciliation.
        Les ordres 'investigate' (symboles hors cible) sont logues mais ignores
        pour eviter de solder des positions que l'operateur n'a pas declarees.
        """
        events: list[ExecutionEvent] = []
        risk_run_id = targets[0].risk_run_id if targets else "unknown"

        for diff in action_diffs:
            if diff.action == "investigate":
                LOGGER.warning(
                    "Rebalance SKIP %s (investigate) : %.0f shares broker hors cible — action manuelle requise",
                    diff.symbol, diff.broker_qty,
                )
                events.append(make_event(
                    exec_run_id, EventType.RECONCILE_DIFF,
                    f"INVESTIGATE {diff.symbol}: {diff.broker_qty:.0f} broker, hors cible",
                    symbol=diff.symbol,
                ))
                continue

            qty = abs(diff.delta)
            if qty < 1:
                continue

            if diff.action == "sell_excess":
                intent = build_rebalance_sell_intent(
                    exec_run_id=exec_run_id,
                    risk_run_id=risk_run_id,
                    symbol=diff.symbol,
                    qty=qty,
                    broker_mode=self._cfg.broker_mode,
                )
                action_label = f"SELL EXCESS {diff.symbol}: -{qty:.0f} shares (broker={diff.broker_qty:.0f} > cible={diff.target_qty})"
            else:  # buy_more
                intent = build_rebalance_buy_intent(
                    exec_run_id=exec_run_id,
                    risk_run_id=risk_run_id,
                    symbol=diff.symbol,
                    qty=qty,
                    broker_mode=self._cfg.broker_mode,
                )
                action_label = f"BUY MORE {diff.symbol}: +{qty:.0f} shares (broker={diff.broker_qty:.0f} < cible={diff.target_qty})"

            LOGGER.info("Rebalance: %s", action_label)

            # Persist intent
            db_dict = order_intent_to_db_dict(intent, exec_run_id)
            try:
                self._repo.upsert_execution_order(db_dict)
            except Exception:
                pass

            # Submit
            try:
                order = self._broker.submit_intent(intent)
                db_dict["broker_order_id"] = order.broker_order_id
                db_dict["status"] = order.status
                try:
                    self._repo.upsert_execution_order(db_dict)
                except Exception:
                    pass
                metrics["rebalance_submitted"] = metrics.get("rebalance_submitted", 0) + 1
                events.append(make_event(
                    exec_run_id, EventType.ORDER_SUBMITTED,
                    f"Rebalance submitted: {action_label}",
                    symbol=diff.symbol, broker_order_id=order.broker_order_id,
                    intent_id=intent.intent_id,
                ))
                LOGGER.info("Rebalance order submitted: %s → %s", diff.symbol, order.broker_order_id)
            except BrokerApiError as exc:
                LOGGER.error("Rebalance ordre refuse [%s] %s: %s", exc.status_code, diff.symbol, exc)
                metrics["rebalance_failed"] = metrics.get("rebalance_failed", 0) + 1
                events.append(make_event(
                    exec_run_id, EventType.ORDER_REJECTED,
                    f"Rebalance rejected [{exc.status_code}] {diff.symbol}: {str(exc)[:200]}",
                    symbol=diff.symbol, intent_id=intent.intent_id,
                ))
            except Exception as exc:
                LOGGER.error("Rebalance submit failed %s: %s", diff.symbol, exc)
                metrics["rebalance_failed"] = metrics.get("rebalance_failed", 0) + 1
                events.append(make_event(
                    exec_run_id, EventType.ORDER_REJECTED,
                    f"Rebalance failed {diff.symbol}: {str(exc)[:200]}",
                    symbol=diff.symbol, intent_id=intent.intent_id,
                ))

            if self._cfg.inter_order_delay_ms > 0:
                time.sleep(self._cfg.inter_order_delay_ms / 1000.0)

        return events

    def _persist_events(self, events: list[ExecutionEvent]) -> None:
        for ev in events:
            try:
                self._repo.insert_execution_event(event_to_db_dict(ev))
            except Exception:
                LOGGER.debug("Could not persist event %s", ev.event_type)
