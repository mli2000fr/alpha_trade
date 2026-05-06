"""Replay Phase 4 des protections d'exécution pour le backtesting."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backtesting.execution_replay import ExecutionReplayResult
from execution_engine.config import ExecutionConfig
from execution_engine.models import IntentRole, OrderIntent
from execution_engine.order_intents import resolve_trailing_activation_price


@dataclass(slots=True)
class ProtectionReplayResult:
    signals_df: pd.DataFrame
    protection_frame: pd.DataFrame
    diagnostics: dict[str, object]


def _child_intents_by_parent(child_intents: list[OrderIntent]) -> dict[str, list[OrderIntent]]:
    mapping: dict[str, list[OrderIntent]] = {}
    for intent in child_intents:
        parent_id = intent.parent_intent_id
        if not parent_id:
            continue
        mapping.setdefault(parent_id, []).append(intent)
    return mapping


def build_phase4_protection_replay(
    execution_replay_result: ExecutionReplayResult,
    *,
    execution_config: ExecutionConfig,
) -> ProtectionReplayResult:
    execution_result = execution_replay_result.execution_result
    child_by_parent = _child_intents_by_parent(execution_result.child_intents)
    fills_by_intent = {fill.intent_id: fill for fill in execution_result.fills}
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
        fill = fills_by_intent.get(entry_intent.intent_id)
        if fill is None:
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
            fill.avg_fill_price,
            execution_config,
            target=target,
        )

        protection_rows.append(
            {
                "trade_date": pd.Timestamp(signal_row.get("trade_date")),
                "execution_date": pd.Timestamp(signal_row.get("execution_date")),
                "symbol": symbol,
                "replay_take_profit_price": (
                    float(take_profit_intent.limit_price)
                    if take_profit_intent is not None and take_profit_intent.limit_price is not None
                    else None
                ),
                "replay_initial_stop_price": (
                    float(initial_stop_intent.stop_price)
                    if initial_stop_intent is not None and initial_stop_intent.stop_price is not None
                    else None
                ),
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

    diagnostics = {
        "signals_input": len(execution_replay_result.signals_df),
        "signals_enriched": len(signals_df),
        "protections_replayed": len(protection_frame),
        "take_profit_protections": int(protection_frame["replay_take_profit_price"].notna().sum()) if not protection_frame.empty else 0,
        "initial_stop_protections": int(protection_frame["replay_initial_stop_price"].notna().sum()) if not protection_frame.empty else 0,
        "trailing_stop_protections": int(protection_frame["replay_trailing_stop_pct"].notna().sum()) if not protection_frame.empty else 0,
        "bridge": "execution_engine.child_intents+protection_replay",
    }
    return ProtectionReplayResult(
        signals_df=signals_df,
        protection_frame=protection_frame,
        diagnostics=diagnostics,
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
    return artifact_paths

