"""Replay d'exécution Phase 3 strictement opt-in pour le backtesting."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timezone
from pathlib import Path

import pandas as pd

from backtesting.execution_broker_like import (
    concat_broker_event_frames,
    ensure_broker_event_frame,
    ensure_order_lifecycle_frame,
    save_execution_broker_like_artifacts,
)
from backtesting.execution_bridge import ExecutionBridgeResult, save_phase2_execution_artifacts
from common.quantity_utils import QUANTITY_EPSILON, normalize_share_quantity
from execution_engine.config import ExecutionConfig
from execution_engine.models import EventType, ExecutionFill, ExecutionTarget, IntentRole, OrderIntent, OrderStatus
from execution_engine.order_intents import (
    build_entry_intents,
    build_initial_stop_intent,
    build_take_profit_intent,
    build_trailing_stop_intent,
)
from execution_engine.tca import (
    build_tca_summary,
    compute_implementation_shortfall,
    compute_slippage_bps,
)
from risk_management.models import PortfolioEntry


@dataclass(slots=True)
class ExecutionReplayResult:
    execution_result: ExecutionBridgeResult
    signals_df: pd.DataFrame
    diagnostics: dict[str, object]
    order_lifecycle_frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    event_frame: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass(frozen=True, slots=True)
class _SyntheticFillAttempt:
    attempt_no: int
    broker_order_id: str
    requested_qty: float
    filled_qty: float
    cumulative_filled_qty: float
    remaining_qty: float
    submitted_at: datetime
    terminal_event_at: datetime
    order_status: str
    broker_state: str
    state_reason: str
    attempt_outcome: str = "filled"
    synthetic_partial_fill: bool = False
    synthetic_retry: bool = False
    synthetic_cancel: bool = False
    synthetic_reject: bool = False
    synthetic_timeout: bool = False
    partial_fill_event_at: datetime | None = None
    resubmit_of_attempt_no: int | None = None
    resubmit_chain_id: str | None = None
    retry_reason: str | None = None


def _resolve_execution_day(snapshot_date: datetime | pd.Timestamp | object, trading_days: pd.DatetimeIndex) -> pd.Timestamp | None:
    snapshot_ts = pd.Timestamp(snapshot_date)
    if pd.isna(snapshot_ts):
        return None
    execution_idx = trading_days.searchsorted(snapshot_ts.to_datetime64(), side="right")
    if execution_idx >= len(trading_days):
        return None
    return pd.Timestamp(trading_days[execution_idx])


def _entry_to_target(
    entry: PortfolioEntry,
    *,
    risk_run_id: str,
    execution_date: pd.Timestamp,
    entry_price: float,
) -> ExecutionTarget:
    return ExecutionTarget(
        risk_run_id=risk_run_id,
        trade_date=execution_date.date(),
        symbol=entry.symbol,
        candidate_rank=entry.candidate_rank,
        target_shares=normalize_share_quantity(entry.approved_shares),
        entry_price=float(entry_price),
        target_weight=float(entry.target_weight),
        sector=entry.sector,
        conviction_score=float(entry.conviction_score),
        sizing_method=entry.sizing_method,
        kelly_fraction=entry.kelly_fraction,
        decision_rank=entry.decision_rank,
        selector_signal_mode=entry.selector_signal_mode,
        selection_explanation=entry.selection_explanation,
        selector_earnings_blackout=entry.selector_earnings_blackout,
        side="buy",
        atr_20=entry.atr_20,
        price_asof_date=entry.price_asof_date,
        atr_asof_date=entry.atr_asof_date,
        stop_price_initial=entry.stop_price_initial,
        risk_per_share=entry.risk_per_share,
        risk_budget_dollars=entry.risk_budget_dollars,
        initial_risk_dollars=entry.initial_risk_dollars,
        target_notional=entry.target_notional,
    )


def _build_synthetic_fill_attempts(
    *,
    execution_day: pd.Timestamp,
    target_qty: float,
    symbol: str = "",
) -> list[_SyntheticFillAttempt]:
    base_dt = execution_day.date()
    submitted_at = datetime.combine(base_dt, time(14, 30), tzinfo=timezone.utc)
    first_fill_at = datetime.combine(base_dt, time(14, 35), tzinfo=timezone.utc)
    first_cancel_at = datetime.combine(base_dt, time(14, 36), tzinfo=timezone.utc)
    retry_submitted_at = datetime.combine(base_dt, time(14, 40), tzinfo=timezone.utc)
    retry_reject_at = datetime.combine(base_dt, time(14, 41), tzinfo=timezone.utc)
    timeout_submitted_at = datetime.combine(base_dt, time(14, 43), tzinfo=timezone.utc)
    timeout_at = datetime.combine(base_dt, time(14, 44), tzinfo=timezone.utc)
    final_retry_submitted_at = datetime.combine(base_dt, time(14, 45), tzinfo=timezone.utc)
    retry_fill_at = datetime.combine(base_dt, time(14, 46), tzinfo=timezone.utc)
    normalized_target_qty = max(float(target_qty), 0.0)
    # resubmit_chain_id déterministe : basé sur symbol + date + qty pour garantir la reproductibilité
    _chain_seed = f"{symbol}_{base_dt}_{normalized_target_qty:.4f}"
    resubmit_chain_id = f"retry_chain_{hashlib.md5(_chain_seed.encode(), usedforsecurity=False).hexdigest()[:10]}"
    if normalized_target_qty <= 1.0:
        return [
            _SyntheticFillAttempt(
                attempt_no=1,
                broker_order_id=f"sim_{uuid.uuid4().hex[:12]}",
                requested_qty=normalized_target_qty,
                filled_qty=normalized_target_qty,
                cumulative_filled_qty=normalized_target_qty,
                remaining_qty=0.0,
                submitted_at=submitted_at,
                terminal_event_at=first_fill_at,
                order_status=OrderStatus.FILLED,
                broker_state="filled",
                state_reason="entry_filled_next_session_open",
                attempt_outcome="filled",
            )
        ]

    first_fill_qty = normalize_share_quantity(normalized_target_qty * 0.6)
    if normalized_target_qty >= 1.0 and first_fill_qty < 1.0:
        first_fill_qty = 1.0
    if first_fill_qty >= normalized_target_qty:
        first_fill_qty = normalize_share_quantity(normalized_target_qty / 2.0)
    remaining_qty = normalize_share_quantity(max(normalized_target_qty - first_fill_qty, 0.0))
    if remaining_qty <= QUANTITY_EPSILON:
        return [
            _SyntheticFillAttempt(
                attempt_no=1,
                broker_order_id=f"sim_{uuid.uuid4().hex[:12]}",
                requested_qty=normalized_target_qty,
                filled_qty=normalized_target_qty,
                cumulative_filled_qty=normalized_target_qty,
                remaining_qty=0.0,
                submitted_at=submitted_at,
                terminal_event_at=first_fill_at,
                order_status=OrderStatus.FILLED,
                broker_state="filled",
                state_reason="entry_filled_next_session_open",
                attempt_outcome="filled",
            )
        ]

    if normalized_target_qty < 20.0:
        return [
            _SyntheticFillAttempt(
                attempt_no=1,
                broker_order_id=f"sim_{uuid.uuid4().hex[:12]}",
                requested_qty=normalized_target_qty,
                filled_qty=first_fill_qty,
                cumulative_filled_qty=first_fill_qty,
                remaining_qty=remaining_qty,
                submitted_at=submitted_at,
                terminal_event_at=first_cancel_at,
                order_status=OrderStatus.CANCELED,
                broker_state="canceled",
                state_reason="partial_fill_canceled_for_resubmit",
                attempt_outcome="partial_fill_canceled",
                synthetic_partial_fill=True,
                synthetic_cancel=True,
                partial_fill_event_at=first_fill_at,
                resubmit_chain_id=resubmit_chain_id,
                retry_reason="resubmit_after_partial_cancel",
            ),
            _SyntheticFillAttempt(
                attempt_no=2,
                broker_order_id=f"sim_{uuid.uuid4().hex[:12]}",
                requested_qty=remaining_qty,
                filled_qty=remaining_qty,
                cumulative_filled_qty=normalized_target_qty,
                remaining_qty=0.0,
                submitted_at=retry_submitted_at,
                terminal_event_at=retry_fill_at,
                order_status=OrderStatus.FILLED,
                broker_state="filled",
                state_reason="retry_filled_after_partial_cancel",
                attempt_outcome="filled_after_resubmit",
                synthetic_retry=True,
                resubmit_of_attempt_no=1,
                resubmit_chain_id=resubmit_chain_id,
                retry_reason="resubmit_after_partial_cancel",
            ),
        ]

    return [
        _SyntheticFillAttempt(
            attempt_no=1,
            broker_order_id=f"sim_{uuid.uuid4().hex[:12]}",
            requested_qty=normalized_target_qty,
            filled_qty=first_fill_qty,
            cumulative_filled_qty=first_fill_qty,
            remaining_qty=remaining_qty,
            submitted_at=submitted_at,
            terminal_event_at=first_cancel_at,
            order_status=OrderStatus.CANCELED,
            broker_state="canceled",
            state_reason="partial_fill_canceled_for_resubmit",
            attempt_outcome="partial_fill_canceled",
            synthetic_partial_fill=True,
            synthetic_cancel=True,
            partial_fill_event_at=first_fill_at,
            resubmit_chain_id=resubmit_chain_id,
            retry_reason="resubmit_after_partial_cancel",
        ),
        _SyntheticFillAttempt(
            attempt_no=2,
            broker_order_id=f"sim_{uuid.uuid4().hex[:12]}",
            requested_qty=remaining_qty,
            filled_qty=0.0,
            cumulative_filled_qty=first_fill_qty,
            remaining_qty=remaining_qty,
            submitted_at=retry_submitted_at,
            terminal_event_at=retry_reject_at,
            order_status=OrderStatus.REJECTED,
            broker_state="rejected",
            state_reason="resubmit_rejected_before_fill",
            attempt_outcome="rejected",
            synthetic_retry=True,
            synthetic_reject=True,
            resubmit_of_attempt_no=1,
            resubmit_chain_id=resubmit_chain_id,
            retry_reason="resubmit_after_partial_cancel",
        ),
        _SyntheticFillAttempt(
            attempt_no=3,
            broker_order_id=f"sim_{uuid.uuid4().hex[:12]}",
            requested_qty=remaining_qty,
            filled_qty=0.0,
            cumulative_filled_qty=first_fill_qty,
            remaining_qty=remaining_qty,
            submitted_at=timeout_submitted_at,
            terminal_event_at=timeout_at,
            order_status=OrderStatus.EXPIRED,
            broker_state="timed_out",
            state_reason="resubmit_timed_out_before_fill",
            attempt_outcome="timed_out",
            synthetic_retry=True,
            synthetic_timeout=True,
            resubmit_of_attempt_no=2,
            resubmit_chain_id=resubmit_chain_id,
            retry_reason="resubmit_after_reject",
        ),
        _SyntheticFillAttempt(
            attempt_no=4,
            broker_order_id=f"sim_{uuid.uuid4().hex[:12]}",
            requested_qty=remaining_qty,
            filled_qty=remaining_qty,
            cumulative_filled_qty=normalized_target_qty,
            remaining_qty=0.0,
            submitted_at=final_retry_submitted_at,
            terminal_event_at=retry_fill_at,
            order_status=OrderStatus.FILLED,
            broker_state="filled",
            state_reason="retry_filled_after_timeout",
            attempt_outcome="filled_after_resubmit",
            synthetic_retry=True,
            resubmit_of_attempt_no=3,
            resubmit_chain_id=resubmit_chain_id,
            retry_reason="resubmit_after_timeout",
        ),
    ]


def _execution_fills_from_attempts(
    *,
    intent: OrderIntent,
    symbol: str,
    fill_price: float,
    attempt_plan: list[_SyntheticFillAttempt],
) -> list[ExecutionFill]:
    fills: list[ExecutionFill] = []
    for attempt in attempt_plan:
        fill_timestamp = attempt.partial_fill_event_at or (
            attempt.terminal_event_at if attempt.order_status == OrderStatus.FILLED and attempt.filled_qty > 0 else None
        )
        if fill_timestamp is None or attempt.filled_qty <= 0:
            continue
        fills.append(
            ExecutionFill(
                fill_id=f"fill_{uuid.uuid4().hex[:12]}",
                broker_order_id=attempt.broker_order_id,
                intent_id=intent.intent_id,
                symbol=symbol,
                filled_qty=float(attempt.filled_qty),
                avg_fill_price=fill_price,
                fill_timestamp=fill_timestamp,
                decision_price=float(intent.decision_price),
                slippage_bps=compute_slippage_bps(fill_price, float(intent.decision_price)),
                implementation_shortfall=compute_implementation_shortfall(
                    fill_price,
                    float(intent.decision_price),
                    float(attempt.filled_qty),
                ),
            )
        )
    return fills


def _weighted_average_fill_price(fills: list[ExecutionFill]) -> float:
    total_qty = float(sum(float(fill.filled_qty) for fill in fills))
    if total_qty <= 0.0:
        return 0.0
    weighted_total = sum(float(fill.avg_fill_price) * float(fill.filled_qty) for fill in fills)
    return float(weighted_total / total_qty)


def _event_type_for_attempt_terminal_state(attempt: _SyntheticFillAttempt) -> str:
    if attempt.synthetic_cancel:
        return EventType.ORDER_CANCELED
    if attempt.synthetic_reject:
        return EventType.ORDER_REJECTED
    if attempt.synthetic_timeout:
        return EventType.ORDER_TIMEOUT
    return EventType.ORDER_FILLED


def simulate_phase3_execution_replay(
    entries: list[PortfolioEntry],
    *,
    execution_config: ExecutionConfig,
    open_df: pd.DataFrame,
    risk_run_id_prefix: str,
    exec_run_id: str | None = None,
) -> ExecutionReplayResult:
    trading_days = pd.DatetimeIndex(open_df.index)
    effective_exec_run_id = exec_run_id or f"bt_exec_replay_{uuid.uuid4().hex[:12]}"

    targets: list[ExecutionTarget] = []
    entry_intents: list[OrderIntent] = []
    child_intents: list[OrderIntent] = []
    fills: list[ExecutionFill] = []
    replay_rows: list[dict[str, object]] = []
    order_lifecycle_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []

    skipped_missing_snapshot = 0
    skipped_no_next_session = 0
    skipped_missing_open = 0

    eligible_entries = sorted(
        [entry for entry in entries if entry.approved_shares > 0],
        key=lambda item: (
            item.score_snapshot_date or item.price_asof_date or item.prediction_asof_date or item.atr_asof_date,
            item.decision_rank or item.candidate_rank or 0,
            item.symbol,
        ),
    )

    for entry in eligible_entries:
        snapshot_date = (
            entry.score_snapshot_date
            or entry.price_asof_date
            or entry.prediction_asof_date
            or entry.atr_asof_date
        )
        if snapshot_date is None:
            skipped_missing_snapshot += 1
            continue

        execution_day = _resolve_execution_day(snapshot_date, trading_days)
        if execution_day is None:
            skipped_no_next_session += 1
            continue
        if entry.symbol not in open_df.columns or execution_day not in open_df.index:
            skipped_missing_open += 1
            continue

        try:
            fill_price = float(open_df.at[execution_day, entry.symbol])
        except (KeyError, TypeError, ValueError):
            skipped_missing_open += 1
            continue
        if not pd.notna(fill_price) or fill_price <= 0:
            skipped_missing_open += 1
            continue

        risk_run_id = f"{risk_run_id_prefix}_{pd.Timestamp(snapshot_date).strftime('%Y%m%d')}"
        target = _entry_to_target(
            entry,
            risk_run_id=risk_run_id,
            execution_date=execution_day,
            entry_price=fill_price,
        )
        intent = build_entry_intents([target], execution_config, effective_exec_run_id)[0]
        attempt_plan = _build_synthetic_fill_attempts(
            execution_day=execution_day,
            target_qty=float(target.target_shares),
            symbol=target.symbol,
        )
        intent_fills = _execution_fills_from_attempts(
            intent=intent,
            symbol=target.symbol,
            fill_price=fill_price,
            attempt_plan=attempt_plan,
        )
        fill_qty = float(sum(float(fill.filled_qty) for fill in intent_fills))
        average_fill_price = _weighted_average_fill_price(intent_fills) if intent_fills else float(fill_price)
        final_fill_timestamp = max((fill.fill_timestamp for fill in intent_fills), default=attempt_plan[-1].terminal_event_at)
        final_broker_order_id = attempt_plan[-1].broker_order_id
        partial_fill_count = sum(1 for attempt in attempt_plan if attempt.synthetic_partial_fill)
        retry_count = sum(1 for attempt in attempt_plan if attempt.synthetic_retry)
        cancel_count = sum(1 for attempt in attempt_plan if attempt.synthetic_cancel)
        reject_count = sum(1 for attempt in attempt_plan if attempt.synthetic_reject)
        timeout_count = sum(1 for attempt in attempt_plan if attempt.synthetic_timeout)
        resubmit_count = sum(1 for attempt in attempt_plan if attempt.resubmit_of_attempt_no is not None)
        retry_chain_id = next((attempt.resubmit_chain_id for attempt in attempt_plan if attempt.resubmit_chain_id), None)

        targets.append(target)
        entry_intents.append(intent)
        fills.extend(intent_fills)
        take_profit_intent = build_take_profit_intent(intent, fill_qty, average_fill_price, execution_config, target=target)
        trailing_stop_intent = build_trailing_stop_intent(intent, fill_qty, average_fill_price, execution_config, target=target)
        child_intents.append(take_profit_intent)
        child_intents.append(trailing_stop_intent)
        initial_stop = build_initial_stop_intent(intent, fill_qty, average_fill_price, execution_config, target=target)
        if initial_stop is not None:
            child_intents.append(initial_stop)
        oco_group_id = f"oco_{intent.intent_id}"

        for attempt in attempt_plan:
            order_lifecycle_rows.append(
                {
                    "trade_date": pd.Timestamp(snapshot_date),
                    "execution_date": execution_day,
                    "symbol": entry.symbol,
                    "risk_run_id": risk_run_id,
                    "exec_run_id": effective_exec_run_id,
                    "order_group_id": intent.intent_id,
                    "oco_group_id": oco_group_id,
                    "intent_id": intent.intent_id,
                    "parent_intent_id": None,
                    "broker_order_id": attempt.broker_order_id,
                    "intent_role": IntentRole.ENTRY,
                    "side": intent.side,
                    "order_type": intent.order_type,
                    "attempt_no": attempt.attempt_no,
                    "order_qty": float(attempt.requested_qty),
                    "filled_qty": float(attempt.filled_qty),
                    "cumulative_filled_qty": float(attempt.cumulative_filled_qty),
                    "remaining_qty": float(attempt.remaining_qty),
                    "limit_price": intent.limit_price,
                    "stop_price": intent.stop_price,
                    "trail_percent": intent.trail_percent,
                    "lifecycle_phase": "phase3_execution_replay",
                    "broker_state": attempt.broker_state,
                    "order_status": attempt.order_status,
                    "synthetic_cancel": bool(attempt.synthetic_cancel),
                    "synthetic_reject": bool(attempt.synthetic_reject),
                    "synthetic_timeout": bool(attempt.synthetic_timeout),
                    "attempt_outcome": attempt.attempt_outcome,
                    "resubmit_of_attempt_no": attempt.resubmit_of_attempt_no,
                    "resubmit_chain_id": attempt.resubmit_chain_id,
                    "synthetic_partial_fill": bool(attempt.synthetic_partial_fill),
                    "synthetic_retry": bool(attempt.synthetic_retry),
                    "retry_reason": attempt.retry_reason,
                    "state_reason": attempt.state_reason,
                    "active_from": attempt.submitted_at,
                    "terminal_event_date": attempt.terminal_event_at,
                }
            )
        for child_intent, broker_state, order_status, state_reason in (
            (take_profit_intent, "working", OrderStatus.SUBMITTED, "submitted_after_entry_fill"),
            (trailing_stop_intent, "held", OrderStatus.HELD, "awaiting_watcher_activation"),
            (initial_stop, "working", OrderStatus.SUBMITTED, "submitted_after_entry_fill"),
        ):
            if child_intent is None:
                continue
            order_lifecycle_rows.append(
                {
                    "trade_date": pd.Timestamp(snapshot_date),
                    "execution_date": execution_day,
                    "symbol": entry.symbol,
                    "risk_run_id": risk_run_id,
                    "exec_run_id": effective_exec_run_id,
                    "order_group_id": intent.intent_id,
                    "oco_group_id": oco_group_id,
                    "intent_id": child_intent.intent_id,
                    "parent_intent_id": child_intent.parent_intent_id,
                    "broker_order_id": f"sim_{child_intent.intent_id[:12]}",
                    "intent_role": child_intent.intent_role,
                    "side": child_intent.side,
                    "order_type": child_intent.order_type,
                    "attempt_no": 1,
                    "order_qty": float(child_intent.qty),
                    "filled_qty": 0.0,
                    "cumulative_filled_qty": 0.0,
                    "remaining_qty": float(child_intent.qty),
                    "limit_price": child_intent.limit_price,
                    "stop_price": child_intent.stop_price,
                    "trail_percent": child_intent.trail_percent,
                    "lifecycle_phase": "phase3_execution_replay",
                    "broker_state": broker_state,
                    "order_status": order_status,
                    "synthetic_cancel": False,
                    "synthetic_reject": False,
                    "synthetic_timeout": False,
                    "attempt_outcome": "open",
                    "resubmit_of_attempt_no": None,
                    "resubmit_chain_id": None,
                    "synthetic_partial_fill": False,
                    "synthetic_retry": False,
                    "retry_reason": None,
                    "state_reason": state_reason,
                    "active_from": final_fill_timestamp,
                    "terminal_event_date": None,
                }
            )

        for attempt in attempt_plan:
            event_rows.append(
                {
                    "trade_date": pd.Timestamp(snapshot_date),
                    "execution_date": execution_day,
                    "symbol": entry.symbol,
                    "event_date": attempt.submitted_at,
                    "event_type": EventType.ORDER_SUBMITTED,
                    "attempt_no": attempt.attempt_no,
                    "intent_id": intent.intent_id,
                    "parent_intent_id": None,
                    "order_group_id": intent.intent_id,
                    "oco_group_id": oco_group_id,
                    "intent_role": IntentRole.ENTRY,
                    "order_status": OrderStatus.SUBMITTED,
                    "event_qty": float(attempt.requested_qty),
                    "cumulative_filled_qty": float(max(attempt.cumulative_filled_qty - attempt.filled_qty, 0.0)),
                    "remaining_qty": float(attempt.requested_qty),
                    "synthetic_retry": bool(attempt.synthetic_retry),
                    "synthetic_cancel": False,
                    "synthetic_reject": False,
                    "synthetic_timeout": False,
                    "event_outcome": "submitted",
                    "resubmit_of_attempt_no": attempt.resubmit_of_attempt_no,
                    "resubmit_chain_id": attempt.resubmit_chain_id,
                    "retry_reason": attempt.retry_reason,
                    "message": (
                        f"Entrée retry #{attempt.attempt_no} soumise pour {entry.symbol}"
                        if attempt.synthetic_retry
                        else f"Entrée soumise pour {entry.symbol}"
                    ),
                }
            )
            if attempt.synthetic_partial_fill and attempt.partial_fill_event_at is not None:
                event_rows.append(
                    {
                        "trade_date": pd.Timestamp(snapshot_date),
                        "execution_date": execution_day,
                        "symbol": entry.symbol,
                        "event_date": attempt.partial_fill_event_at,
                        "event_type": EventType.ORDER_PARTIALLY_FILLED,
                        "attempt_no": attempt.attempt_no,
                        "intent_id": intent.intent_id,
                        "parent_intent_id": None,
                        "order_group_id": intent.intent_id,
                        "oco_group_id": oco_group_id,
                        "intent_role": IntentRole.ENTRY,
                        "order_status": OrderStatus.PARTIALLY_FILLED,
                        "event_qty": float(attempt.filled_qty),
                        "cumulative_filled_qty": float(attempt.cumulative_filled_qty),
                        "remaining_qty": float(attempt.remaining_qty),
                        "synthetic_retry": bool(attempt.synthetic_retry),
                        "synthetic_cancel": False,
                        "synthetic_reject": False,
                        "synthetic_timeout": False,
                        "event_outcome": "partial_fill",
                        "resubmit_of_attempt_no": attempt.resubmit_of_attempt_no,
                        "resubmit_chain_id": attempt.resubmit_chain_id,
                        "retry_reason": attempt.retry_reason,
                        "message": f"Entrée partiellement exécutée pour {entry.symbol} ({attempt.filled_qty:.0f}/{target.target_shares:.0f})",
                    }
                )
            event_rows.append(
                {
                    "trade_date": pd.Timestamp(snapshot_date),
                    "execution_date": execution_day,
                    "symbol": entry.symbol,
                    "event_date": attempt.terminal_event_at,
                    "event_type": _event_type_for_attempt_terminal_state(attempt),
                    "attempt_no": attempt.attempt_no,
                    "intent_id": intent.intent_id,
                    "parent_intent_id": None,
                    "order_group_id": intent.intent_id,
                    "oco_group_id": oco_group_id,
                    "intent_role": IntentRole.ENTRY,
                    "order_status": attempt.order_status,
                    "event_qty": float(attempt.remaining_qty if attempt.order_status != OrderStatus.FILLED else attempt.filled_qty),
                    "cumulative_filled_qty": float(attempt.cumulative_filled_qty),
                    "remaining_qty": float(attempt.remaining_qty),
                    "synthetic_retry": bool(attempt.synthetic_retry),
                    "synthetic_cancel": bool(attempt.synthetic_cancel),
                    "synthetic_reject": bool(attempt.synthetic_reject),
                    "synthetic_timeout": bool(attempt.synthetic_timeout),
                    "event_outcome": attempt.attempt_outcome,
                    "resubmit_of_attempt_no": attempt.resubmit_of_attempt_no,
                    "resubmit_chain_id": attempt.resubmit_chain_id,
                    "retry_reason": attempt.retry_reason,
                    "message": (
                        f"Reliquat annulé avant resubmit pour {entry.symbol}"
                        if attempt.synthetic_cancel
                        else (
                            f"Retry rejeté pour {entry.symbol}"
                            if attempt.synthetic_reject
                            else (
                                f"Retry expiré avant fill pour {entry.symbol}"
                                if attempt.synthetic_timeout
                                else (
                                    f"Entrée complétée après retry pour {entry.symbol}"
                                    if attempt.synthetic_retry
                                    else f"Entrée exécutée au prochain open pour {entry.symbol}"
                                )
                            )
                        )
                    ),
                }
            )
        event_rows.append(
            {
                "trade_date": pd.Timestamp(snapshot_date),
                "execution_date": execution_day,
                "symbol": entry.symbol,
                "event_date": final_fill_timestamp,
                "event_type": EventType.CHILDREN_SUBMITTED,
                "attempt_no": len(attempt_plan),
                "intent_id": intent.intent_id,
                "parent_intent_id": None,
                "order_group_id": intent.intent_id,
                "oco_group_id": oco_group_id,
                "intent_role": IntentRole.ENTRY,
                "order_status": None,
                "event_qty": float(fill_qty),
                "cumulative_filled_qty": float(fill_qty),
                "remaining_qty": 0.0,
                "synthetic_retry": bool(retry_count > 0),
                "synthetic_cancel": False,
                "synthetic_reject": False,
                "synthetic_timeout": False,
                "event_outcome": "children_submitted",
                "resubmit_of_attempt_no": None,
                "resubmit_chain_id": retry_chain_id,
                "retry_reason": attempt_plan[-1].retry_reason if retry_count > 0 else None,
                "message": f"Protections OCO préparées pour {entry.symbol}",
            }
        )
        for child_intent, child_status in (
            (take_profit_intent, OrderStatus.SUBMITTED),
            (trailing_stop_intent, OrderStatus.HELD),
            (initial_stop, OrderStatus.SUBMITTED),
        ):
            if child_intent is None:
                continue
            event_rows.append(
                {
                    "trade_date": pd.Timestamp(snapshot_date),
                    "execution_date": execution_day,
                    "symbol": entry.symbol,
                    "event_date": final_fill_timestamp,
                    "event_type": EventType.ORDER_SUBMITTED,
                    "attempt_no": 1,
                    "intent_id": child_intent.intent_id,
                    "parent_intent_id": child_intent.parent_intent_id,
                    "order_group_id": intent.intent_id,
                    "oco_group_id": oco_group_id,
                    "intent_role": child_intent.intent_role,
                    "order_status": child_status,
                    "event_qty": float(child_intent.qty),
                    "cumulative_filled_qty": 0.0,
                    "remaining_qty": float(child_intent.qty),
                    "synthetic_retry": False,
                    "synthetic_cancel": False,
                    "synthetic_reject": False,
                    "synthetic_timeout": False,
                    "event_outcome": "submitted",
                    "resubmit_of_attempt_no": None,
                    "resubmit_chain_id": None,
                    "retry_reason": None,
                    "message": f"Ordre enfant {child_intent.intent_role} soumis pour {entry.symbol}",
                }
            )

        replay_rows.append(
            {
                "trade_date": pd.Timestamp(snapshot_date),
                "execution_date": execution_day,
                "symbol": entry.symbol,
                "selected": True,
                "rank": float(entry.decision_rank or entry.candidate_rank or len(replay_rows) + 1),
                "candidate_rank": entry.candidate_rank,
                "score": float(entry.score_used),
                "score_source": entry.score_source,
                "selector_signal_mode": entry.selector_signal_mode,
                "selection_explanation": entry.selection_explanation,
                "selector_earnings_blackout": entry.selector_earnings_blackout,
                "target_weight": float(entry.target_weight),
                "target_notional": float(entry.target_notional),
                "approved_shares": normalize_share_quantity(entry.approved_shares),
                "filled_qty": fill_qty,
                "fill_price": average_fill_price,
                "entry_fill_timestamp": final_fill_timestamp,
                "decision": entry.decision,
                "decision_reason": entry.decision_reason,
                "risk_run_id": risk_run_id,
                "exec_run_id": effective_exec_run_id,
                "entry_intent_id": intent.intent_id,
                "entry_broker_order_id": final_broker_order_id,
                "order_group_id": intent.intent_id,
                "oco_group_id": oco_group_id,
                "entry_order_status": OrderStatus.FILLED,
                "entry_attempt_count": len(attempt_plan),
                "entry_partial_fill_count": partial_fill_count,
                "entry_retry_count": retry_count,
                "entry_resubmit_count": resubmit_count,
                "entry_cancel_count": cancel_count,
                "entry_reject_count": reject_count,
                "entry_timeout_count": timeout_count,
                "entry_retry_chain_id": retry_chain_id,
                "execution_replay_mode": "execution_replay",
            }
        )

    tca_payload = asdict(build_tca_summary(fills, execution_config.max_slippage_bps))
    execution_diagnostics = {
        "risk_run_id": risk_run_id_prefix,
        "exec_run_id": effective_exec_run_id,
        "targets": len(targets),
        "entry_intents": len(entry_intents),
        "child_intents": len(child_intents),
        "fills": len(fills),
        "bridge": "execution_engine.order_intents+tca",
    }
    execution_result = ExecutionBridgeResult(
        targets=targets,
        entry_intents=entry_intents,
        child_intents=child_intents,
        fills=fills,
        tca_summary=tca_payload,
        diagnostics=execution_diagnostics,
    )

    signals_df = pd.DataFrame(replay_rows)
    if signals_df.empty:
        signals_df = pd.DataFrame(
            columns=[
                "trade_date",
                "execution_date",
                "symbol",
                "selected",
                "rank",
                "candidate_rank",
                "score",
                "score_source",
                "selector_signal_mode",
                "selection_explanation",
                "selector_earnings_blackout",
                "target_weight",
                "target_notional",
                "approved_shares",
                "filled_qty",
                "fill_price",
                "entry_fill_timestamp",
                "decision",
                "decision_reason",
                "risk_run_id",
                "exec_run_id",
                "entry_intent_id",
                "entry_broker_order_id",
                "order_group_id",
                "oco_group_id",
                "entry_order_status",
                "entry_attempt_count",
                "entry_partial_fill_count",
                "entry_retry_count",
                "entry_resubmit_count",
                "entry_cancel_count",
                "entry_reject_count",
                "entry_timeout_count",
                "entry_retry_chain_id",
                "execution_replay_mode",
            ]
        )

    order_lifecycle_frame = ensure_order_lifecycle_frame(pd.DataFrame(order_lifecycle_rows))
    event_frame = ensure_broker_event_frame(pd.DataFrame(event_rows))
    replay_diagnostics = {
        "requested_entries": len(entries),
        "eligible_entries": len(eligible_entries),
        "scheduled_entries": len(targets),
        "signals_generated": len(signals_df),
        "skipped_missing_snapshot": skipped_missing_snapshot,
        "skipped_no_next_session": skipped_no_next_session,
        "skipped_missing_open": skipped_missing_open,
        "broker_like_orders": int(len(order_lifecycle_frame)),
        "broker_like_events": int(len(event_frame)),
        "filled_orders": int((order_lifecycle_frame["order_status"] == OrderStatus.FILLED).sum()) if not order_lifecycle_frame.empty else 0,
        "partial_fill_orders": int(order_lifecycle_frame.get("synthetic_partial_fill", pd.Series(dtype=bool)).map(bool).sum()) if not order_lifecycle_frame.empty else 0,
        "held_orders": int((order_lifecycle_frame["order_status"] == OrderStatus.HELD).sum()) if not order_lifecycle_frame.empty else 0,
        "retry_orders": int(order_lifecycle_frame.get("synthetic_retry", pd.Series(dtype=bool)).map(bool).sum()) if not order_lifecycle_frame.empty else 0,
        "canceled_orders": int(order_lifecycle_frame.get("synthetic_cancel", pd.Series(dtype=bool)).map(bool).sum()) if not order_lifecycle_frame.empty else 0,
        "rejected_orders": int(order_lifecycle_frame.get("synthetic_reject", pd.Series(dtype=bool)).map(bool).sum()) if not order_lifecycle_frame.empty else 0,
        "timed_out_orders": int(order_lifecycle_frame.get("synthetic_timeout", pd.Series(dtype=bool)).map(bool).sum()) if not order_lifecycle_frame.empty else 0,
        "exec_run_id": effective_exec_run_id,
        "bridge": "execution_engine.order_intents+tca+execution_replay",
    }
    return ExecutionReplayResult(
        execution_result=execution_result,
        signals_df=signals_df,
        diagnostics=replay_diagnostics,
        order_lifecycle_frame=order_lifecycle_frame,
        event_frame=event_frame,
    )


def save_phase3_execution_replay_artifacts(result: ExecutionReplayResult, output_dir: Path) -> dict[str, str]:
    artifact_paths = save_phase2_execution_artifacts(result.execution_result, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    signals_path = output_dir / "phase3_execution_replay_signals.csv"
    result.signals_df.to_csv(signals_path, index=False)
    artifact_paths["phase3_execution_replay_signals_csv"] = str(signals_path)

    summary_path = output_dir / "phase3_execution_replay_summary.json"
    summary_path.write_text(
        json.dumps(result.diagnostics, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    artifact_paths["phase3_execution_replay_summary_json"] = str(summary_path)
    artifact_paths.update(
        save_execution_broker_like_artifacts(
            signals_df=result.signals_df,
            order_lifecycle_frame=result.order_lifecycle_frame,
            broker_event_frame=concat_broker_event_frames(result.event_frame),
            output_dir=output_dir,
            phase_modes={"phase3_mode": "execution_replay"},
            diagnostics={"phase3_execution_replay": result.diagnostics},
        )
    )
    return artifact_paths

