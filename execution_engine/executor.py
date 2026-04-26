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


@dataclass(slots=True)
class _AccountConstraintState:
    account_type: str
    effective_pdt_rule: str
    pdt_limited: bool
    swing_only: bool
    equity: float
    buying_power_available: float
    settled_cash_available: float
    daytrade_count: int
    remaining_day_trade_slots: int

    @property
    def pdt_active(self) -> bool:
        return self.pdt_limited


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
    ) -> dict[str, Any]:
        exec_run_id = build_run_id()
        metrics: dict[str, Any] = {
            "exec_run_id": exec_run_id,
            "risk_run_id": risk_run_id,
            "trade_date": trade_date.isoformat() if hasattr(trade_date, "isoformat") else trade_date,
            "status": "RUNNING",
            "targets": 0, "submitted": 0, "filled": 0, "failed": 0, "skipped": 0,
            "rebalance_submitted": 0, "rebalance_failed": 0,
            "constraint_blocked": 0, "children_deferred": 0,
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
                metrics["status"] = "ABORTED"
                return metrics

            actual_risk_run_id = targets[0].risk_run_id
            actual_trade_date = trade_date or targets[0].trade_date
            metrics["targets"] = len(targets)
            metrics["total_target_notional"] = round(sum(float(t.target_notional or (t.target_shares * t.entry_price)) for t in targets), 2)
            metrics["total_initial_risk_dollars"] = round(sum(float(t.initial_risk_dollars or 0.0) for t in targets), 2)
            metrics["total_risk_budget_dollars"] = round(sum(float(t.risk_budget_dollars or 0.0) for t in targets), 2)
            metrics["max_target_weight"] = round(max((float(t.target_weight) for t in targets), default=0.0), 4)
            metrics["targets_with_risk_controls"] = sum(1 for t in targets if t.stop_price_initial is not None or (t.risk_per_share or 0.0) > 0)
            metrics["stale_price_targets"] = sum(
                1 for t in targets
                if t.price_asof_date is not None and actual_trade_date is not None and t.price_asof_date < actual_trade_date
            )
            target_by_symbol = {t.symbol: t for t in targets}

            self._repo.insert_execution_run(
                exec_run_id=exec_run_id,
                risk_run_id=actual_risk_run_id,
                trade_date=actual_trade_date,
                broker_mode=self._cfg.broker_mode,
                dry_run=self._cfg.dry_run,
                total_targets=len(targets),
                account_id=self._cfg.account_id,
            )

            # Circuit breaker check (injection)
            if self._circuit_breaker is not None:
                try:
                    if self._circuit_breaker.is_active():
                        events.append(make_event(exec_run_id, EventType.CIRCUIT_BREAKER_ACTIVE, "CB active — aborting"))
                        self._persist_events(events)
                        self._repo.update_execution_run_status(exec_run_id, "ABORTED")
                        metrics["status"] = "ABORTED"
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
                        metrics["status"] = "ABORTED"
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

            # Phase 4 — Submit entries
            submitted_orders: dict[str, tuple[OrderIntent, BrokerOrder]] = {}
            batch_count = 0
            for intent in new_intents:
                if not self._reserve_account_capacity_for_intent(intent, account_state, exec_run_id, events, metrics):
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
                    self._repo.snapshot_broker_positions(exec_run_id, self._cfg.broker_mode, positions, account_id=self._cfg.account_id)
                    diffs = reconcile_targets_vs_broker(targets, positions, self._cfg.reconcile_tolerance_shares)
                    action_diffs = [d for d in diffs if d.action != "none"]
                    if action_diffs:
                        events.append(make_event(exec_run_id, EventType.RECONCILE_DIFF,
                                                 f"Reconciliation diffs found: {len(action_diffs)}"))
                        # Vente / achat automatique si auto_rebalance_on_reconcile
                        if self._cfg.auto_rebalance_on_reconcile:
                            rebalance_events = self._submit_rebalance_orders(
                                action_diffs, exec_run_id, targets, metrics, account_state,
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
            metrics["status"] = "COMPLETED"

        except Exception as exc:
            LOGGER.exception("Execution run failed: %s", exc)
            events.append(make_event(exec_run_id, EventType.RUN_FAILED, str(exc)[:255]))
            try:
                self._repo.update_execution_run_status(exec_run_id, "FAILED", error_message=str(exc)[:255])
            except Exception:
                pass
            metrics["status"] = "FAILED"

        self._persist_events(events)
        return metrics

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_account_constraint_state(self) -> _AccountConstraintState:
        if self._cfg.dry_run:
            equity = float(self._cfg.simulated_account_equity)
            settled_cash = equity
            buying_power = equity * self._cfg.simulated_margin_buying_power_multiplier if self._cfg.account_type == "margin" else settled_cash
            daytrade_count = 0
        else:
            snapshot = self._broker.get_account_snapshot()
            equity = self._safe_float(snapshot.get("equity") or snapshot.get("portfolio_value"), default=0.0)
            settled_cash = self._safe_float(
                snapshot.get("non_marginable_buying_power") if self._cfg.account_type == "cash" else snapshot.get("cash"),
                default=0.0,
            )
            if settled_cash <= 0:
                settled_cash = self._safe_float(snapshot.get("cash"), default=0.0)
            buying_power = self._safe_float(
                snapshot.get("buying_power") if self._cfg.account_type == "margin" else snapshot.get("non_marginable_buying_power"),
                default=settled_cash if self._cfg.account_type == "cash" else equity,
            )
            if self._cfg.account_type == "cash":
                buying_power = settled_cash
            daytrade_count = int(self._safe_float(snapshot.get("daytrade_count"), default=0.0))

        pdt_limited = self._cfg.applies_pdt_limit(equity)
        remaining_slots = max(self._cfg.max_day_trades - daytrade_count, 0) if pdt_limited else 0
        return _AccountConstraintState(
            account_type=self._cfg.account_type,
            effective_pdt_rule=self._cfg.effective_pdt_rule,
            pdt_limited=pdt_limited,
            swing_only=self._cfg.swing_only,
            equity=equity,
            buying_power_available=max(buying_power, 0.0),
            settled_cash_available=max(settled_cash, 0.0),
            daytrade_count=max(daytrade_count, 0),
            remaining_day_trade_slots=remaining_slots,
        )

    @staticmethod
    def _safe_float(value: object, *, default: float = 0.0) -> float:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    def _estimate_intent_notional(self, intent: OrderIntent) -> float:
        price = intent.limit_price if intent.limit_price is not None else intent.decision_price
        return max(float(intent.qty) * max(float(price), 0.0), 0.0)

    def _reserve_account_capacity_for_intent(
        self,
        intent: OrderIntent,
        account_state: _AccountConstraintState,
        exec_run_id: str,
        events: list[ExecutionEvent],
        metrics: dict[str, int],
    ) -> bool:
        if intent.side != "buy":
            return True

        estimated_notional = self._estimate_intent_notional(intent)
        available_budget = (
            account_state.settled_cash_available
            if account_state.account_type == "cash"
            else account_state.buying_power_available
        )
        if estimated_notional <= available_budget + 1e-9:
            if account_state.account_type == "cash":
                account_state.settled_cash_available = max(account_state.settled_cash_available - estimated_notional, 0.0)
            account_state.buying_power_available = max(account_state.buying_power_available - estimated_notional, 0.0)
            return True

        metrics["skipped"] += 1
        metrics["constraint_blocked"] += 1
        events.append(make_event(
            exec_run_id,
            EventType.INTENT_SKIPPED_ACCOUNT_CONSTRAINT,
            (
                f"Blocked by account constraints: {intent.symbol} requires ~{estimated_notional:.2f}, "
                f"available={available_budget:.2f} ({account_state.account_type})"
            ),
            symbol=intent.symbol,
            intent_id=intent.intent_id,
            payload={
                "account_type": account_state.account_type,
                "estimated_notional": estimated_notional,
                "available_budget": available_budget,
                "effective_pdt_rule": account_state.effective_pdt_rule,
                "swing_only": account_state.swing_only,
            },
        ))
        return False

    def _should_defer_children(
        self,
        account_state: _AccountConstraintState,
    ) -> tuple[bool, str | None]:
        if account_state.swing_only:
            return True, "swing_only"
        if account_state.pdt_active:
            if account_state.remaining_day_trade_slots <= 0:
                return True, "pdt_limit"
            account_state.remaining_day_trade_slots -= 1
        return False, None

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
        events: list[ExecutionEvent] = []
        fill_qty = filled_order.filled_qty
        fill_price = filled_order.avg_fill_price or parent.decision_price
        if fill_qty <= 0:
            return events

        defer_children, reason = self._should_defer_children(account_state)
        if defer_children:
            metrics["children_deferred"] += 1
            events.append(make_event(
                exec_run_id,
                EventType.CHILDREN_DEFERRED_ACCOUNT_CONSTRAINT,
                f"Children deferred for {parent.symbol} due to {reason}",
                symbol=parent.symbol,
                intent_id=parent.intent_id,
                payload={
                    "reason": reason,
                    "account_type": account_state.account_type,
                    "effective_pdt_rule": account_state.effective_pdt_rule,
                    "swing_only": account_state.swing_only,
                    "remaining_day_trade_slots": account_state.remaining_day_trade_slots,
                },
            ))
            return events

        tp_intent = build_take_profit_intent(parent, fill_qty, fill_price, self._cfg, target=target)
        ts_intent = build_trailing_stop_intent(parent, fill_qty, fill_price, self._cfg, target=target)

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
            payload={
                "take_profit_limit_price": tp_intent.limit_price,
                "trailing_stop_percent": ts_intent.trail_percent,
                "risk_per_share": getattr(target, "risk_per_share", None),
                "stop_price_initial": getattr(target, "stop_price_initial", None),
                "initial_risk_dollars": getattr(target, "initial_risk_dollars", None),
            },
        ))
        return events

    def _submit_rebalance_orders(
        self,
        action_diffs: list,
        exec_run_id: str,
        targets: list,
        metrics: dict[str, int],
        account_state: _AccountConstraintState,
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

                if not self._reserve_account_capacity_for_intent(intent, account_state, exec_run_id, events, metrics):
                    LOGGER.info("Rebalance buy blocked by account constraints: %s", diff.symbol)
                    continue

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
