"""Helpers Sprint 4 pour exposer un lifecycle broker-like additif côté backtest."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


ORDER_LIFECYCLE_COLUMNS = [
    "trade_date",
    "execution_date",
    "symbol",
    "risk_run_id",
    "exec_run_id",
    "order_group_id",
    "oco_group_id",
    "intent_id",
    "parent_intent_id",
    "broker_order_id",
    "intent_role",
    "side",
    "order_type",
    "attempt_no",
    "order_qty",
    "filled_qty",
    "cumulative_filled_qty",
    "remaining_qty",
    "limit_price",
    "stop_price",
    "trail_percent",
    "lifecycle_phase",
    "broker_state",
    "order_status",
    "synthetic_partial_fill",
    "synthetic_retry",
    "synthetic_cancel",
    "synthetic_reject",
    "synthetic_timeout",
    "attempt_outcome",
    "resubmit_of_attempt_no",
    "resubmit_chain_id",
    "retry_reason",
    "state_reason",
    "active_from",
    "terminal_event_date",
]

BROKER_EVENT_COLUMNS = [
    "trade_date",
    "execution_date",
    "symbol",
    "event_date",
    "event_type",
    "attempt_no",
    "intent_id",
    "parent_intent_id",
    "order_group_id",
    "oco_group_id",
    "intent_role",
    "order_status",
    "event_qty",
    "cumulative_filled_qty",
    "remaining_qty",
    "synthetic_retry",
    "synthetic_cancel",
    "synthetic_reject",
    "synthetic_timeout",
    "event_outcome",
    "resubmit_of_attempt_no",
    "resubmit_chain_id",
    "retry_reason",
    "message",
]


def ensure_order_lifecycle_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=ORDER_LIFECYCLE_COLUMNS)
    normalized = frame.copy()
    for column in ORDER_LIFECYCLE_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = None
    return normalized.loc[:, ORDER_LIFECYCLE_COLUMNS]


def ensure_broker_event_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=BROKER_EVENT_COLUMNS)
    normalized = frame.copy()
    for column in BROKER_EVENT_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = None
    return normalized.loc[:, BROKER_EVENT_COLUMNS]


def concat_order_lifecycle_frames(*frames: pd.DataFrame | None) -> pd.DataFrame:
    normalized = [ensure_order_lifecycle_frame(frame) for frame in frames if frame is not None]
    if not normalized:
        return ensure_order_lifecycle_frame(None)
    non_empty = [frame.astype(object) for frame in normalized if not frame.empty]
    if not non_empty:
        return ensure_order_lifecycle_frame(None)
    return pd.concat(non_empty, ignore_index=True)


def concat_broker_event_frames(*frames: pd.DataFrame | None) -> pd.DataFrame:
    normalized = [ensure_broker_event_frame(frame) for frame in frames if frame is not None]
    if not normalized:
        return ensure_broker_event_frame(None)
    non_empty = [frame.astype(object) for frame in normalized if not frame.empty]
    if not non_empty:
        return ensure_broker_event_frame(None)
    return pd.concat(non_empty, ignore_index=True)


def _string_count_map(series: pd.Series | None) -> dict[str, int]:
    if series is None or series.empty:
        return {}
    normalized = series.dropna().astype(str).str.strip()
    normalized = normalized[normalized != ""]
    if normalized.empty:
        return {}
    return {str(key): int(value) for key, value in normalized.value_counts().sort_index().items()}


def _session_key_from_row(row: Mapping[str, Any]) -> str | None:
    for key in ("trade_date", "execution_date", "event_date"):
        raw_value = row.get(key)
        if raw_value is None or pd.isna(raw_value):
            continue
        try:
            return pd.Timestamp(raw_value).normalize().date().isoformat()
        except Exception:
            continue
    return None


def _count_true(series: pd.Series | None) -> int:
    if series is None or series.empty:
        return 0
    normalized = series.map(lambda value: False if pd.isna(value) else bool(value))
    return int(normalized.sum())


def _count_event_type(frame: pd.DataFrame, event_type: str) -> int:
    return int((frame.get("event_type", pd.Series(dtype=str)) == event_type).sum()) if not frame.empty else 0


def build_execution_broker_like_summary(
    *,
    signals_df: pd.DataFrame | None,
    order_lifecycle_frame: pd.DataFrame | None,
    broker_event_frame: pd.DataFrame | None,
    phase_modes: Mapping[str, Any] | None = None,
    diagnostics: Mapping[str, Mapping[str, Any] | Mapping[str, object] | Any] | None = None,
) -> dict[str, Any]:
    signals = signals_df.copy() if isinstance(signals_df, pd.DataFrame) else pd.DataFrame()
    orders = ensure_order_lifecycle_frame(order_lifecycle_frame)
    events = ensure_broker_event_frame(broker_event_frame)

    if not signals.empty and "trade_date" in signals.columns:
        signal_sessions = pd.to_datetime(signals["trade_date"], errors="coerce").dropna().dt.normalize()
        session_count = int(signal_sessions.nunique())
    else:
        session_count = 0

    symbols: list[str] = []
    if not signals.empty and "symbol" in signals.columns:
        symbols = sorted({str(symbol) for symbol in signals["symbol"].dropna().astype(str).tolist() if str(symbol).strip()})

    order_status_counts = _string_count_map(orders["order_status"] if "order_status" in orders.columns else None)
    broker_state_counts = _string_count_map(orders["broker_state"] if "broker_state" in orders.columns else None)
    intent_role_counts = _string_count_map(orders["intent_role"] if "intent_role" in orders.columns else None)
    event_type_counts = _string_count_map(events["event_type"] if "event_type" in events.columns else None)
    partial_fill_orders = _count_true(orders["synthetic_partial_fill"] if "synthetic_partial_fill" in orders.columns else None)
    retry_orders = _count_true(orders["synthetic_retry"] if "synthetic_retry" in orders.columns else None)
    canceled_orders = _count_true(orders["synthetic_cancel"] if "synthetic_cancel" in orders.columns else None)
    rejected_orders = _count_true(orders["synthetic_reject"] if "synthetic_reject" in orders.columns else None)
    timed_out_orders = _count_true(orders["synthetic_timeout"] if "synthetic_timeout" in orders.columns else None)
    partial_fill_events = _count_event_type(events, "ORDER_PARTIALLY_FILLED")
    retry_events = _count_true(events["synthetic_retry"] if "synthetic_retry" in events.columns else None)
    cancel_events = _count_event_type(events, "ORDER_CANCELED")
    reject_events = _count_event_type(events, "ORDER_REJECTED")
    timeout_events = _count_event_type(events, "ORDER_TIMEOUT")

    session_keys: set[str] = set()
    for frame in (signals, orders, events):
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        for row in frame.to_dict("records"):
            if not isinstance(row, dict):
                continue
            session_key = _session_key_from_row(row)
            if session_key:
                session_keys.add(session_key)

    sessions: list[dict[str, Any]] = []
    for session_key in sorted(session_keys):
        order_mask = pd.Series(False, index=orders.index)
        event_mask = pd.Series(False, index=events.index)
        signal_mask = pd.Series(False, index=signals.index)
        if not orders.empty:
            trade_dates = pd.to_datetime(orders["trade_date"], errors="coerce") if "trade_date" in orders.columns else pd.Series(pd.NaT, index=orders.index)
            execution_dates = pd.to_datetime(orders["execution_date"], errors="coerce") if "execution_date" in orders.columns else pd.Series(pd.NaT, index=orders.index)
            session_ts = pd.Timestamp(session_key)
            order_mask = trade_dates.dt.normalize().eq(session_ts) | execution_dates.dt.normalize().eq(session_ts)
        if not events.empty:
            trade_dates = pd.to_datetime(events["trade_date"], errors="coerce") if "trade_date" in events.columns else pd.Series(pd.NaT, index=events.index)
            execution_dates = pd.to_datetime(events["execution_date"], errors="coerce") if "execution_date" in events.columns else pd.Series(pd.NaT, index=events.index)
            event_dates = pd.to_datetime(events["event_date"], errors="coerce") if "event_date" in events.columns else pd.Series(pd.NaT, index=events.index)
            session_ts = pd.Timestamp(session_key)
            event_mask = (
                trade_dates.dt.normalize().eq(session_ts)
                | execution_dates.dt.normalize().eq(session_ts)
                | event_dates.dt.normalize().eq(session_ts)
            )
        if not signals.empty and "trade_date" in signals.columns:
            signal_mask = pd.to_datetime(signals["trade_date"], errors="coerce").dt.normalize().eq(pd.Timestamp(session_key))

        session_orders = orders.loc[order_mask] if not orders.empty else ensure_order_lifecycle_frame(None)
        session_events = events.loc[event_mask] if not events.empty else ensure_broker_event_frame(None)
        session_signals = signals.loc[signal_mask] if not signals.empty else pd.DataFrame()
        session_symbols = sorted(
            {
                *(str(symbol) for symbol in session_orders.get("symbol", pd.Series(dtype=str)).dropna().astype(str).tolist()),
                *(str(symbol) for symbol in session_events.get("symbol", pd.Series(dtype=str)).dropna().astype(str).tolist()),
                *(str(symbol) for symbol in session_signals.get("symbol", pd.Series(dtype=str)).dropna().astype(str).tolist()),
            }
        )
        sessions.append(
            {
                "trade_date": session_key,
                "symbols": session_symbols,
                "selected_signals": int(len(session_signals)),
                "orders_total": int(len(session_orders)),
                "filled_orders": int((session_orders.get("order_status", pd.Series(dtype=str)) == "FILLED").sum()),
                "partial_fill_orders": _count_true(session_orders.get("synthetic_partial_fill")),
                "retry_orders": _count_true(session_orders.get("synthetic_retry")),
                "rejected_orders": _count_true(session_orders.get("synthetic_reject")),
                "timed_out_orders": _count_true(session_orders.get("synthetic_timeout")),
                "working_orders": int((session_orders.get("broker_state", pd.Series(dtype=str)) == "working").sum()),
                "held_orders": int((session_orders.get("broker_state", pd.Series(dtype=str)) == "held").sum()),
                "canceled_orders": int((session_orders.get("order_status", pd.Series(dtype=str)) == "CANCELED").sum()),
                "stale_orders": int((session_orders.get("broker_state", pd.Series(dtype=str)) == "stale").sum()),
                "exit_filled_orders": int(
                    (
                        session_orders.get("order_status", pd.Series(dtype=str)).eq("FILLED")
                        & session_orders.get("intent_role", pd.Series(dtype=str)).isin(["take_profit", "initial_stop", "trailing_stop", "exit"])
                    ).sum()
                ),
                "partial_fill_events": _count_event_type(session_events, "ORDER_PARTIALLY_FILLED"),
                "retry_events": _count_true(session_events.get("synthetic_retry")),
                "cancel_events": _count_event_type(session_events, "ORDER_CANCELED"),
                "reject_events": _count_event_type(session_events, "ORDER_REJECTED"),
                "timeout_events": _count_event_type(session_events, "ORDER_TIMEOUT"),
                "trigger_hits": int((session_events.get("event_type", pd.Series(dtype=str)) == "PROTECTION_TRIGGER_HIT").sum()),
                "transition_completed": int((session_events.get("event_type", pd.Series(dtype=str)) == "PROTECTION_TRANSITION_COMPLETED").sum()),
                "oco_cancels": int((session_events.get("event_type", pd.Series(dtype=str)) == "OCO_CANCEL_TRIGGERED").sum()),
            }
        )

    return {
        "taxonomy_version": 2,
        "signal_count": int(len(signals)),
        "symbol_count": int(len(symbols)),
        "symbols": symbols,
        "session_count": session_count if session_count > 0 else int(len(sessions)),
        "order_count": int(len(orders)),
        "broker_event_count": int(len(events)),
        "order_status_counts": order_status_counts,
        "broker_state_counts": broker_state_counts,
        "intent_role_counts": intent_role_counts,
        "event_type_counts": event_type_counts,
        "phase_modes": {str(key): value for key, value in (phase_modes or {}).items()},
        "diagnostics": {
            str(key): dict(value) if isinstance(value, Mapping) else value
            for key, value in (diagnostics or {}).items()
        },
        "broker_semantics": {
            "supported_states": ["filled", "partial_fill", "working", "held", "canceled", "rejected", "timed_out", "stale", "retry_submitted"],
            "not_simulated_states": [],
            "partial_fill_orders": partial_fill_orders,
            "retry_orders": retry_orders,
            "canceled_orders": canceled_orders,
            "rejected_orders": rejected_orders,
            "timed_out_orders": timed_out_orders,
            "partial_fill_events": partial_fill_events,
            "retry_events": retry_events,
            "cancel_events": cancel_events,
            "reject_events": reject_events,
            "timeout_events": timeout_events,
            "stale_orders": int((orders.get("broker_state", pd.Series(dtype=str)) == "stale").sum()),
            "terminal_statuses": ["FILLED", "CANCELED", "REJECTED", "EXPIRED"],
        },
        "sessions": sessions,
    }


def save_execution_broker_like_artifacts(
    *,
    signals_df: pd.DataFrame | None,
    order_lifecycle_frame: pd.DataFrame | None,
    broker_event_frame: pd.DataFrame | None,
    output_dir: Path,
    phase_modes: Mapping[str, Any] | None = None,
    diagnostics: Mapping[str, Mapping[str, Any] | Mapping[str, object] | Any] | None = None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    orders = ensure_order_lifecycle_frame(order_lifecycle_frame)
    events = ensure_broker_event_frame(broker_event_frame)
    summary = build_execution_broker_like_summary(
        signals_df=signals_df,
        order_lifecycle_frame=orders,
        broker_event_frame=events,
        phase_modes=phase_modes,
        diagnostics=diagnostics,
    )

    orders_path = output_dir / "execution_broker_like_order_lifecycle.csv"
    orders.to_csv(orders_path, index=False)
    events_path = output_dir / "execution_broker_like_events.csv"
    events.to_csv(events_path, index=False)
    summary_path = output_dir / "execution_broker_like_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {
        "execution_broker_like_order_lifecycle_csv": str(orders_path),
        "execution_broker_like_events_csv": str(events_path),
        "execution_broker_like_summary_json": str(summary_path),
    }


__all__ = [
    "BROKER_EVENT_COLUMNS",
    "ORDER_LIFECYCLE_COLUMNS",
    "build_execution_broker_like_summary",
    "concat_broker_event_frames",
    "concat_order_lifecycle_frames",
    "ensure_broker_event_frame",
    "ensure_order_lifecycle_frame",
    "save_execution_broker_like_artifacts",
]





