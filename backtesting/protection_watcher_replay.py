"""Replay Phase 5 du watcher de protection pour le backtesting."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from backtesting.execution_broker_like import (
    concat_broker_event_frames,
    ensure_broker_event_frame,
    ensure_order_lifecycle_frame,
    save_execution_broker_like_artifacts,
)
from backtesting.execution_lifecycle_replay import ProtectionReplayResult
from execution_engine.models import EventType, IntentRole, OrderStatus


@dataclass(slots=True)
class ProtectionWatcherReplayResult:
    signals_df: pd.DataFrame
    lifecycle_frame: pd.DataFrame
    event_frame: pd.DataFrame
    diagnostics: dict[str, object]
    order_lifecycle_frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    broker_event_frame: pd.DataFrame = field(default_factory=pd.DataFrame)


def _find_trigger_date(
    *,
    symbol: str,
    execution_date: pd.Timestamp,
    trigger_price: float,
    high_df: pd.DataFrame,
    low_df: pd.DataFrame,
    short: bool,
) -> pd.Timestamp | None:
    if symbol not in high_df.columns:
        return None
    trading_days = pd.DatetimeIndex(high_df.index)
    start_idx = trading_days.searchsorted(execution_date.to_datetime64(), side="left")
    for idx in range(start_idx, len(trading_days)):
        trade_day = pd.Timestamp(trading_days[idx])
        try:
            if short:
                day_low = float(low_df.at[trade_day, symbol])
                if pd.notna(day_low) and day_low <= trigger_price:
                    return trade_day
            else:
                day_high = float(high_df.at[trade_day, symbol])
                if pd.notna(day_high) and day_high >= trigger_price:
                    return trade_day
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _next_trading_day(day: pd.Timestamp, trading_days: pd.DatetimeIndex) -> pd.Timestamp | None:
    idx = trading_days.searchsorted(day.to_datetime64(), side="right")
    if idx >= len(trading_days):
        return None
    return pd.Timestamp(trading_days[idx])


def build_phase5_watcher_replay(
    protection_replay_result: ProtectionReplayResult,
    *,
    high_df: pd.DataFrame,
    low_df: pd.DataFrame,
) -> ProtectionWatcherReplayResult:
    trading_days = pd.DatetimeIndex(high_df.index)
    lifecycle_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    broker_event_rows: list[dict[str, object]] = []
    order_lifecycle_frame = ensure_order_lifecycle_frame(protection_replay_result.order_lifecycle_frame).copy()
    for timestamp_column in ("active_from", "terminal_event_date"):
        if timestamp_column in order_lifecycle_frame.columns:
            order_lifecycle_frame[timestamp_column] = order_lifecycle_frame[timestamp_column].astype(object)

    for row in protection_replay_result.signals_df.to_dict("records"):
        symbol = str(row.get("symbol") or "")
        if not symbol:
            continue
        execution_date_raw = row.get("execution_date")
        execution_date = pd.Timestamp(execution_date_raw) if execution_date_raw is not None and pd.notna(execution_date_raw) else None
        trigger_price_raw = row.get("replay_trailing_activation_price")
        trigger_mode_raw = row.get("replay_trailing_activation_mode")
        trailing_stop_pct_raw = row.get("replay_trailing_stop_pct")
        initial_stop_intent_id = str(row.get("replay_initial_stop_intent_id") or "").strip()
        trailing_stop_intent_id = str(row.get("replay_trailing_stop_intent_id") or "").strip()
        order_group_id = str(row.get("order_group_id") or "").strip() or None
        oco_group_id = str(row.get("replay_oco_group_id") or row.get("oco_group_id") or "").strip() or None

        watcher_state = "not_applicable"
        trigger_date = None
        effective_date = None
        side = str(row.get("side") or "buy").strip().lower()
        short = side == "sell"
        if execution_date is not None and trigger_price_raw is not None and pd.notna(trigger_price_raw):
            trigger_price = float(trigger_price_raw)
            trigger_date = _find_trigger_date(
                symbol=symbol,
                execution_date=execution_date,
                trigger_price=trigger_price,
                high_df=high_df,
                low_df=low_df,
                short=short,
            )
            if trigger_date is None:
                watcher_state = "pending"
            else:
                watcher_state = "triggered"
                effective_date = _next_trading_day(trigger_date, trading_days)
                event_rows.append(
                    {
                        "symbol": symbol,
                        "event_date": trigger_date,
                        "event_type": EventType.PROTECTION_TRIGGER_HIT,
                        "trigger_price": trigger_price,
                        "trigger_mode": str(trigger_mode_raw or "unknown"),
                        "message": f"Trigger trailing atteint pour {symbol}",
                    }
                )
                if effective_date is None:
                    watcher_state = "failed"
                    event_rows.append(
                        {
                            "symbol": symbol,
                            "event_date": trigger_date,
                            "event_type": EventType.PROTECTION_TRANSITION_FAILED,
                            "trigger_price": trigger_price,
                            "trigger_mode": str(trigger_mode_raw or "unknown"),
                            "message": f"Aucune séance suivante disponible pour promouvoir le trailing sur {symbol}",
                        }
                    )
                else:
                    watcher_state = "transitioned"
                    if initial_stop_intent_id and not order_lifecycle_frame.empty and "intent_id" in order_lifecycle_frame.columns:
                        initial_stop_mask = order_lifecycle_frame["intent_id"].astype(str) == initial_stop_intent_id
                        order_lifecycle_frame.loc[initial_stop_mask, [
                            "lifecycle_phase",
                            "broker_state",
                            "order_status",
                            "state_reason",
                            "terminal_event_date",
                        ]] = [
                            "phase5_watcher_replay",
                            "canceled",
                            OrderStatus.CANCELED,
                            "replaced_by_trailing_stop",
                            effective_date,
                        ]
                        if bool(initial_stop_mask.any()):
                            broker_event_rows.append(
                                {
                                    "trade_date": pd.Timestamp(row.get("trade_date")) if row.get("trade_date") is not None and pd.notna(row.get("trade_date")) else None,
                                    "execution_date": execution_date,
                                    "symbol": symbol,
                                    "event_date": effective_date,
                                    "event_type": EventType.ORDER_CANCELED,
                                    "intent_id": initial_stop_intent_id,
                                    "parent_intent_id": order_group_id,
                                    "order_group_id": order_group_id,
                                    "oco_group_id": oco_group_id,
                                    "intent_role": IntentRole.INITIAL_STOP,
                                    "order_status": OrderStatus.CANCELED,
                                    "message": f"Stop initial remplacé par trailing sur {symbol}",
                                }
                            )
                    if trailing_stop_intent_id and not order_lifecycle_frame.empty and "intent_id" in order_lifecycle_frame.columns:
                        trailing_stop_mask = order_lifecycle_frame["intent_id"].astype(str) == trailing_stop_intent_id
                        order_lifecycle_frame.loc[trailing_stop_mask, [
                            "lifecycle_phase",
                            "broker_state",
                            "order_status",
                            "state_reason",
                            "active_from",
                        ]] = [
                            "phase5_watcher_replay",
                            "working",
                            OrderStatus.SUBMITTED,
                            "activated_after_watcher_trigger",
                            effective_date,
                        ]
                    event_rows.append(
                        {
                            "symbol": symbol,
                            "event_date": effective_date,
                            "event_type": EventType.PROTECTION_TRANSITION_COMPLETED,
                            "trigger_price": trigger_price,
                            "trigger_mode": str(trigger_mode_raw or "unknown"),
                            "trailing_stop_pct": float(trailing_stop_pct_raw) if trailing_stop_pct_raw is not None and pd.notna(trailing_stop_pct_raw) else None,
                            "message": f"Stop initial promu en trailing pour {symbol}",
                        }
                    )

        lifecycle_rows.append(
            {
                "trade_date": pd.Timestamp(row.get("trade_date")) if row.get("trade_date") is not None and pd.notna(row.get("trade_date")) else None,
                "execution_date": execution_date,
                "symbol": symbol,
                "watcher_transition_state": watcher_state,
                "watcher_trigger_date": trigger_date,
                "watcher_transition_effective_date": effective_date,
                "watcher_replay_mode": "watcher_replay",
            }
        )

    lifecycle_frame = pd.DataFrame(lifecycle_rows)
    event_frame = pd.DataFrame(event_rows)
    if lifecycle_frame.empty:
        signals_df = protection_replay_result.signals_df.copy()
    else:
        signals_df = protection_replay_result.signals_df.merge(
            lifecycle_frame,
            on=["trade_date", "execution_date", "symbol"],
            how="left",
        )

    state_series = lifecycle_frame["watcher_transition_state"] if "watcher_transition_state" in lifecycle_frame.columns else pd.Series(dtype=str)
    broker_event_frame = concat_broker_event_frames(
        ensure_broker_event_frame(protection_replay_result.broker_event_frame),
        ensure_broker_event_frame(pd.DataFrame(event_rows)),
        ensure_broker_event_frame(pd.DataFrame(broker_event_rows)),
    )

    diagnostics = {
        "signals_input": len(protection_replay_result.signals_df),
        "signals_enriched": len(signals_df),
        "watcher_items": len(lifecycle_frame),
        "pending_items": int((state_series == "pending").sum()) if not lifecycle_frame.empty else 0,
        "transitioned_items": int((state_series == "transitioned").sum()) if not lifecycle_frame.empty else 0,
        "failed_items": int((state_series == "failed").sum()) if not lifecycle_frame.empty else 0,
        "events_generated": len(event_frame),
        "canceled_initial_stop_orders": int((order_lifecycle_frame["state_reason"] == "replaced_by_trailing_stop").sum()) if not order_lifecycle_frame.empty else 0,
        "activated_trailing_orders": int((order_lifecycle_frame["state_reason"] == "activated_after_watcher_trigger").sum()) if not order_lifecycle_frame.empty else 0,
        "bridge": "execution_engine.protection_watcher+watcher_replay",
    }
    return ProtectionWatcherReplayResult(
        signals_df=signals_df,
        lifecycle_frame=lifecycle_frame,
        event_frame=event_frame,
        diagnostics=diagnostics,
        order_lifecycle_frame=order_lifecycle_frame,
        broker_event_frame=broker_event_frame,
    )


def save_phase5_watcher_replay_artifacts(result: ProtectionWatcherReplayResult, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths: dict[str, str] = {}

    lifecycle_csv = output_dir / "phase5_watcher_replay_lifecycle.csv"
    result.lifecycle_frame.to_csv(lifecycle_csv, index=False)
    artifact_paths["phase5_watcher_replay_lifecycle_csv"] = str(lifecycle_csv)

    event_csv = output_dir / "phase5_watcher_replay_events.csv"
    result.event_frame.to_csv(event_csv, index=False)
    artifact_paths["phase5_watcher_replay_events_csv"] = str(event_csv)

    signals_csv = output_dir / "phase5_watcher_replay_signals.csv"
    result.signals_df.to_csv(signals_csv, index=False)
    artifact_paths["phase5_watcher_replay_signals_csv"] = str(signals_csv)

    summary_json = output_dir / "phase5_watcher_replay_summary.json"
    summary_json.write_text(
        json.dumps(result.diagnostics, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    artifact_paths["phase5_watcher_replay_summary_json"] = str(summary_json)
    artifact_paths.update(
        save_execution_broker_like_artifacts(
            signals_df=result.signals_df,
            order_lifecycle_frame=result.order_lifecycle_frame,
            broker_event_frame=result.broker_event_frame,
            output_dir=output_dir,
            phase_modes={
                "phase3_mode": "execution_replay",
                "phase4_mode": "protection_replay",
                "phase5_mode": "watcher_replay",
            },
            diagnostics={"phase5_watcher_replay": result.diagnostics},
        )
    )
    return artifact_paths

