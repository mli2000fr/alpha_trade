"""Replay Phase 4 des protections d'exécution pour le backtesting."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from backtesting.execution_broker_like import (
    ensure_broker_event_frame,
    ensure_order_lifecycle_frame,
    save_execution_broker_like_artifacts,
)
from backtesting.execution_replay import ExecutionReplayResult
from execution_engine.config import ExecutionConfig
from execution_engine.models import IntentRole, OrderIntent, OrderStatus
from execution_engine.order_intents import resolve_trailing_activation_price


@dataclass(slots=True)
class ProtectionReplayResult:
    signals_df: pd.DataFrame
    protection_frame: pd.DataFrame
    diagnostics: dict[str, object]
    order_lifecycle_frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    broker_event_frame: pd.DataFrame = field(default_factory=pd.DataFrame)


def _child_intents_by_parent(child_intents: list[OrderIntent]) -> dict[str, list[OrderIntent]]:
    mapping: dict[str, list[OrderIntent]] = {}
    for intent in child_intents:
        parent_id = intent.parent_intent_id
        if not parent_id:
            continue
        mapping.setdefault(parent_id, []).append(intent)
    return mapping


def _aggregate_entry_fills_by_intent(execution_replay_result: ExecutionReplayResult) -> dict[str, dict[str, object]]:
    aggregated: dict[str, dict[str, object]] = {}
    for fill in execution_replay_result.execution_result.fills:
        bucket = aggregated.setdefault(
            fill.intent_id,
            {
                "filled_qty": 0.0,
                "weighted_notional": 0.0,
                "last_fill_timestamp": fill.fill_timestamp,
            },
        )
        fill_qty = float(fill.filled_qty)
        bucket["filled_qty"] = float(bucket["filled_qty"]) + fill_qty
        bucket["weighted_notional"] = float(bucket["weighted_notional"]) + (fill_qty * float(fill.avg_fill_price))
        if fill.fill_timestamp >= bucket["last_fill_timestamp"]:
            bucket["last_fill_timestamp"] = fill.fill_timestamp
    for bucket in aggregated.values():
        total_qty = float(bucket["filled_qty"])
        bucket["avg_fill_price"] = float(bucket["weighted_notional"]) / total_qty if total_qty > 0 else None
    return aggregated


def build_phase4_protection_replay(
    execution_replay_result: ExecutionReplayResult,
    *,
    execution_config: ExecutionConfig,
) -> ProtectionReplayResult:
    execution_result = execution_replay_result.execution_result
    child_by_parent = _child_intents_by_parent(execution_result.child_intents)
    fills_by_intent = _aggregate_entry_fills_by_intent(execution_replay_result)
    targets_by_symbol = {target.symbol: target for target in execution_result.targets}

    protection_rows: list[dict[str, object]] = []
    for signal_row in execution_replay_result.signals_df.to_dict("records"):
        symbol = str(signal_row.get("symbol") or "")
        if not symbol:
            continue
        target = targets_by_symbol.get(symbol)
        if target is None:
            continue

        entry_intent = next(
            (
                intent
                for intent in execution_result.entry_intents
                if intent.symbol == symbol
                and str(intent.risk_run_id) == str(target.risk_run_id)
            ),
            None,
        )
        if entry_intent is None:
            continue
        fill_summary = fills_by_intent.get(entry_intent.intent_id)
        if fill_summary is None:
            continue
        fill_avg_price = fill_summary.get("avg_fill_price")
        if fill_avg_price is None or not pd.notna(fill_avg_price):
            continue

        take_profit_intent = next(
            (intent for intent in child_by_parent.get(entry_intent.intent_id, []) if intent.intent_role == IntentRole.TAKE_PROFIT),
            None,
        )
        initial_stop_intent = next(
            (intent for intent in child_by_parent.get(entry_intent.intent_id, []) if intent.intent_role == IntentRole.INITIAL_STOP),
            None,
        )
        trailing_stop_intent = next(
            (intent for intent in child_by_parent.get(entry_intent.intent_id, []) if intent.intent_role == IntentRole.TRAILING_STOP),
            None,
        )
        trailing_activation_price, trailing_activation_mode = resolve_trailing_activation_price(
            float(fill_avg_price),
            execution_config,
            target=target,
        )

        protection_rows.append(
            {
                "trade_date": pd.Timestamp(signal_row.get("trade_date")),
                "execution_date": pd.Timestamp(signal_row.get("execution_date")),
                "symbol": symbol,
                "replay_oco_group_id": f"oco_{entry_intent.intent_id}",
                "replay_take_profit_intent_id": take_profit_intent.intent_id if take_profit_intent is not None else None,
                "replay_take_profit_order_status": OrderStatus.SUBMITTED if take_profit_intent is not None else None,
                "replay_take_profit_price": (
                    float(take_profit_intent.limit_price)
                    if take_profit_intent is not None and take_profit_intent.limit_price is not None
                    else None
                ),
                "replay_initial_stop_intent_id": initial_stop_intent.intent_id if initial_stop_intent is not None else None,
                "replay_initial_stop_order_status": OrderStatus.SUBMITTED if initial_stop_intent is not None else None,
                "replay_initial_stop_price": (
                    float(initial_stop_intent.stop_price)
                    if initial_stop_intent is not None and initial_stop_intent.stop_price is not None
                    else None
                ),
                "replay_trailing_stop_intent_id": trailing_stop_intent.intent_id if trailing_stop_intent is not None else None,
                "replay_trailing_stop_order_status": OrderStatus.HELD if trailing_stop_intent is not None else None,
                "replay_trailing_stop_pct": (
                    float(trailing_stop_intent.trail_percent) / 100.0
                    if trailing_stop_intent is not None and trailing_stop_intent.trail_percent is not None
                    else None
                ),
                "replay_trailing_activation_price": trailing_activation_price,
                "replay_trailing_activation_mode": trailing_activation_mode,
                "protection_replay_mode": "protection_replay",
            }
        )

    protection_frame = pd.DataFrame(protection_rows)
    if protection_frame.empty:
        signals_df = execution_replay_result.signals_df.copy()
    else:
        signals_df = execution_replay_result.signals_df.merge(
            protection_frame,
            on=["trade_date", "execution_date", "symbol"],
            how="left",
        )

    order_lifecycle_frame = ensure_order_lifecycle_frame(execution_replay_result.order_lifecycle_frame)
    broker_event_frame = ensure_broker_event_frame(execution_replay_result.event_frame)
    diagnostics = {
        "signals_input": len(execution_replay_result.signals_df),
        "signals_enriched": len(signals_df),
        "protections_replayed": len(protection_frame),
        "take_profit_protections": int(protection_frame["replay_take_profit_price"].notna().sum()) if not protection_frame.empty else 0,
        "initial_stop_protections": int(protection_frame["replay_initial_stop_price"].notna().sum()) if not protection_frame.empty else 0,
        "trailing_stop_protections": int(protection_frame["replay_trailing_stop_pct"].notna().sum()) if not protection_frame.empty else 0,
        "working_take_profit_orders": int((order_lifecycle_frame["intent_role"] == IntentRole.TAKE_PROFIT).sum()) if not order_lifecycle_frame.empty else 0,
        "working_initial_stop_orders": int((order_lifecycle_frame["intent_role"] == IntentRole.INITIAL_STOP).sum()) if not order_lifecycle_frame.empty else 0,
        "held_trailing_stop_orders": int(
            ((order_lifecycle_frame["intent_role"] == IntentRole.TRAILING_STOP) & (order_lifecycle_frame["order_status"] == OrderStatus.HELD)).sum()
        ) if not order_lifecycle_frame.empty else 0,
        "bridge": "execution_engine.child_intents+protection_replay",
    }
    return ProtectionReplayResult(
        signals_df=signals_df,
        protection_frame=protection_frame,
        diagnostics=diagnostics,
        order_lifecycle_frame=order_lifecycle_frame,
        broker_event_frame=broker_event_frame,
    )


def save_phase4_protection_replay_artifacts(result: ProtectionReplayResult, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths: dict[str, str] = {}

    if not result.protection_frame.empty:
        protection_csv = output_dir / "phase4_protection_replay.csv"
        result.protection_frame.to_csv(protection_csv, index=False)
        artifact_paths["phase4_protection_replay_csv"] = str(protection_csv)

    enriched_signals_csv = output_dir / "phase4_protection_replay_signals.csv"
    result.signals_df.to_csv(enriched_signals_csv, index=False)
    artifact_paths["phase4_protection_replay_signals_csv"] = str(enriched_signals_csv)

    summary_json = output_dir / "phase4_protection_replay_summary.json"
    summary_json.write_text(
        json.dumps(result.diagnostics, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    artifact_paths["phase4_protection_replay_summary_json"] = str(summary_json)
    artifact_paths.update(
        save_execution_broker_like_artifacts(
            signals_df=result.signals_df,
            order_lifecycle_frame=result.order_lifecycle_frame,
            broker_event_frame=result.broker_event_frame,
            output_dir=output_dir,
            phase_modes={
                "phase3_mode": "execution_replay",
                "phase4_mode": "protection_replay",
            },
            diagnostics={"phase4_protection_replay": result.diagnostics},
        )
    )
    return artifact_paths

