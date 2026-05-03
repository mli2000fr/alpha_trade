"""Replay Phase 5 du watcher de protection pour le backtesting."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backtesting.execution_lifecycle_replay import ProtectionReplayResult
from execution_engine.models import EventType


@dataclass(slots=True)
class ProtectionWatcherReplayResult:
    signals_df: pd.DataFrame
    lifecycle_frame: pd.DataFrame
    event_frame: pd.DataFrame
    diagnostics: dict[str, object]


def _find_trigger_date(
    *,
    symbol: str,
    execution_date: pd.Timestamp,
    trigger_price: float,
    high_df: pd.DataFrame,
) -> pd.Timestamp | None:
    if symbol not in high_df.columns:
        return None
    trading_days = pd.DatetimeIndex(high_df.index)
    start_idx = trading_days.searchsorted(execution_date.to_datetime64(), side="left")
    for idx in range(start_idx, len(trading_days)):
        trade_day = pd.Timestamp(trading_days[idx])
        try:
            day_high = float(high_df.at[trade_day, symbol])
        except (KeyError, TypeError, ValueError):
            continue
        if pd.notna(day_high) and day_high >= trigger_price:
            return trade_day
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
) -> ProtectionWatcherReplayResult:
    trading_days = pd.DatetimeIndex(high_df.index)
    lifecycle_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []

    for row in protection_replay_result.signals_df.to_dict("records"):
        symbol = str(row.get("symbol") or "")
        if not symbol:
            continue
        execution_date_raw = row.get("execution_date")
        execution_date = pd.Timestamp(execution_date_raw) if execution_date_raw is not None and pd.notna(execution_date_raw) else None
        trigger_price_raw = row.get("replay_trailing_activation_price")
        trigger_mode_raw = row.get("replay_trailing_activation_mode")
        trailing_stop_pct_raw = row.get("replay_trailing_stop_pct")

        watcher_state = "not_applicable"
        trigger_date = None
        effective_date = None
        if execution_date is not None and trigger_price_raw is not None and pd.notna(trigger_price_raw):
            trigger_price = float(trigger_price_raw)
            trigger_date = _find_trigger_date(
                symbol=symbol,
                execution_date=execution_date,
                trigger_price=trigger_price,
                high_df=high_df,
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

    diagnostics = {
        "signals_input": len(protection_replay_result.signals_df),
        "signals_enriched": len(signals_df),
        "watcher_items": len(lifecycle_frame),
        "pending_items": int((state_series == "pending").sum()) if not lifecycle_frame.empty else 0,
        "transitioned_items": int((state_series == "transitioned").sum()) if not lifecycle_frame.empty else 0,
        "failed_items": int((state_series == "failed").sum()) if not lifecycle_frame.empty else 0,
        "events_generated": len(event_frame),
        "bridge": "execution_engine.protection_watcher+watcher_replay",
    }
    return ProtectionWatcherReplayResult(
        signals_df=signals_df,
        lifecycle_frame=lifecycle_frame,
        event_frame=event_frame,
        diagnostics=diagnostics,
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
    return artifact_paths

