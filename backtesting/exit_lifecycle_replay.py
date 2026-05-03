"""Replay Phase 7 du lifecycle terminal des exits pour le backtesting."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backtesting.microstructure import resolve_intrabar_exit
from backtesting.protection_watcher_replay import ProtectionWatcherReplayResult
from execution_engine.models import EventType, IntentRole


@dataclass(slots=True)
class ExitLifecycleReplayResult:
    signals_df: pd.DataFrame
    exit_frame: pd.DataFrame
    event_frame: pd.DataFrame
    diagnostics: dict[str, object]


def _map_exit_reason_to_intent_role(exit_reason: str) -> str:
    normalized = str(exit_reason or "").strip().lower()
    if normalized == "take_profit":
        return IntentRole.TAKE_PROFIT
    if normalized == "initial_stop":
        return IntentRole.INITIAL_STOP
    if normalized == "trailing_stop":
        return IntentRole.TRAILING_STOP
    return normalized or "unknown"


def build_phase7_exit_lifecycle_replay(
    watcher_replay_result: ProtectionWatcherReplayResult,
    *,
    high_df: pd.DataFrame,
    low_df: pd.DataFrame,
    intrabar_priority: str = "conservative",
) -> ExitLifecycleReplayResult:
    exit_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []

    trading_days = pd.DatetimeIndex(high_df.index)
    low_days = pd.DatetimeIndex(low_df.index)
    if not trading_days.equals(low_days):
        raise ValueError("high_df et low_df doivent partager le même calendrier d'index.")

    for row in watcher_replay_result.signals_df.to_dict("records"):
        symbol = str(row.get("symbol") or "")
        if not symbol or symbol not in high_df.columns or symbol not in low_df.columns:
            continue

        execution_date_raw = row.get("execution_date")
        fill_price_raw = row.get("fill_price")
        if execution_date_raw is None or pd.isna(execution_date_raw) or fill_price_raw is None or pd.isna(fill_price_raw):
            continue
        execution_date = pd.Timestamp(execution_date_raw)
        fill_price = float(fill_price_raw)
        take_profit_price = row.get("replay_take_profit_price")
        initial_stop_price = row.get("replay_initial_stop_price")
        trailing_stop_pct = row.get("replay_trailing_stop_pct")
        watcher_effective_date = row.get("watcher_transition_effective_date")
        effective_ts = pd.Timestamp(watcher_effective_date) if watcher_effective_date is not None and pd.notna(watcher_effective_date) else None

        if take_profit_price is None or pd.isna(take_profit_price):
            continue
        take_profit_price = float(take_profit_price)
        initial_stop_price = None if initial_stop_price is None or pd.isna(initial_stop_price) else float(initial_stop_price)
        trailing_stop_pct = None if trailing_stop_pct is None or pd.isna(trailing_stop_pct) else float(trailing_stop_pct)

        entry_idx = trading_days.searchsorted(execution_date.to_datetime64(), side="left")
        if entry_idx >= len(trading_days):
            continue

        peak_high = fill_price
        exit_row: dict[str, object] | None = None
        for idx in range(entry_idx, len(trading_days)):
            trade_day = pd.Timestamp(trading_days[idx])
            try:
                day_high = float(high_df.at[trade_day, symbol])
                day_low = float(low_df.at[trade_day, symbol])
            except (KeyError, TypeError, ValueError):
                continue
            if not pd.notna(day_high) or not pd.notna(day_low):
                continue

            previous_peak_high = peak_high
            peak_high = max(peak_high, day_high)
            trailing_active = (
                trailing_stop_pct is not None
                and effective_ts is not None
                and trade_day.normalize() >= effective_ts.normalize()
            )
            trailing_stop_price = previous_peak_high * (1.0 - trailing_stop_pct) if trailing_active and trailing_stop_pct is not None else float("-inf")
            active_initial_stop = None if trailing_active else initial_stop_price
            resolution = resolve_intrabar_exit(
                day_high=day_high,
                day_low=day_low,
                take_profit_price=take_profit_price,
                trailing_stop_price=trailing_stop_price,
                initial_stop_price=active_initial_stop,
                priority=intrabar_priority,
                rng=None,
            )
            if not resolution.triggered:
                continue

            exit_reason = resolution.exit_reason
            filled_intent_role = _map_exit_reason_to_intent_role(exit_reason)
            sibling_canceled = filled_intent_role in {
                IntentRole.TAKE_PROFIT,
                IntentRole.INITIAL_STOP,
                IntentRole.TRAILING_STOP,
            }
            exit_row = {
                "trade_date": pd.Timestamp(row.get("trade_date")) if row.get("trade_date") is not None and pd.notna(row.get("trade_date")) else None,
                "execution_date": execution_date,
                "symbol": symbol,
                "replay_exit_date": trade_day,
                "replay_exit_price": float(resolution.exit_price),
                "replay_exit_reason": exit_reason,
                "replay_exit_intent_role": filled_intent_role,
                "replay_oco_sibling_canceled": bool(sibling_canceled),
                "exit_lifecycle_replay_mode": "exit_lifecycle_replay",
            }
            event_rows.append(
                {
                    "symbol": symbol,
                    "event_date": trade_day,
                    "event_type": f"EXIT_FILLED_{filled_intent_role.upper()}",
                    "exit_reason": exit_reason,
                    "exit_price": float(resolution.exit_price),
                }
            )
            if sibling_canceled:
                event_rows.append(
                    {
                        "symbol": symbol,
                        "event_date": trade_day,
                        "event_type": EventType.OCO_CANCEL_TRIGGERED,
                        "exit_reason": exit_reason,
                        "message": f"OCO cancel sibling après exit {filled_intent_role} pour {symbol}",
                    }
                )
            break

        if exit_row is not None:
            exit_rows.append(exit_row)

    exit_frame = pd.DataFrame(exit_rows)
    event_frame = pd.DataFrame(event_rows)
    if exit_frame.empty:
        signals_df = watcher_replay_result.signals_df.copy()
    else:
        signals_df = watcher_replay_result.signals_df.merge(
            exit_frame,
            on=["trade_date", "execution_date", "symbol"],
            how="left",
        )

    diagnostics = {
        "signals_input": len(watcher_replay_result.signals_df),
        "signals_enriched": len(signals_df),
        "exit_rows": len(exit_frame),
        "events_generated": len(event_frame),
        "filled_take_profit": int((exit_frame["replay_exit_reason"] == "take_profit").sum()) if not exit_frame.empty else 0,
        "filled_initial_stop": int((exit_frame["replay_exit_reason"] == "initial_stop").sum()) if not exit_frame.empty else 0,
        "filled_trailing_stop": int((exit_frame["replay_exit_reason"] == "trailing_stop").sum()) if not exit_frame.empty else 0,
        "oco_cancels": int((event_frame["event_type"] == EventType.OCO_CANCEL_TRIGGERED).sum()) if not event_frame.empty and "event_type" in event_frame.columns else 0,
        "bridge": "execution_engine.oco_manager+exit_lifecycle_replay",
    }
    return ExitLifecycleReplayResult(
        signals_df=signals_df,
        exit_frame=exit_frame,
        event_frame=event_frame,
        diagnostics=diagnostics,
    )


def save_phase7_exit_lifecycle_replay_artifacts(result: ExitLifecycleReplayResult, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths: dict[str, str] = {}

    exit_csv = output_dir / "phase7_exit_lifecycle_replay.csv"
    result.exit_frame.to_csv(exit_csv, index=False)
    artifact_paths["phase7_exit_lifecycle_replay_csv"] = str(exit_csv)

    events_csv = output_dir / "phase7_exit_lifecycle_replay_events.csv"
    result.event_frame.to_csv(events_csv, index=False)
    artifact_paths["phase7_exit_lifecycle_replay_events_csv"] = str(events_csv)

    signals_csv = output_dir / "phase7_exit_lifecycle_replay_signals.csv"
    result.signals_df.to_csv(signals_csv, index=False)
    artifact_paths["phase7_exit_lifecycle_replay_signals_csv"] = str(signals_csv)

    summary_json = output_dir / "phase7_exit_lifecycle_replay_summary.json"
    summary_json.write_text(
        json.dumps(result.diagnostics, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    artifact_paths["phase7_exit_lifecycle_replay_summary_json"] = str(summary_json)
    return artifact_paths

