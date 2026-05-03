"""Replay d'exécution Phase 3 strictement opt-in pour le backtesting."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, time, timezone
from pathlib import Path

import pandas as pd

from backtesting.execution_bridge import ExecutionBridgeResult, save_phase2_execution_artifacts
from execution_engine.config import ExecutionConfig
from execution_engine.models import ExecutionFill, ExecutionTarget, OrderIntent
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
        target_shares=int(entry.approved_shares),
        entry_price=float(entry_price),
        target_weight=float(entry.target_weight),
        sector=entry.sector,
        conviction_score=float(entry.conviction_score),
        sizing_method=entry.sizing_method,
        kelly_fraction=entry.kelly_fraction,
        decision_rank=entry.decision_rank,
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
        fill_qty = float(target.target_shares)
        fill_timestamp = datetime.combine(execution_day.date(), time(14, 30), tzinfo=timezone.utc)
        fill = ExecutionFill(
            fill_id=f"fill_{uuid.uuid4().hex[:12]}",
            broker_order_id=f"sim_{uuid.uuid4().hex[:12]}",
            intent_id=intent.intent_id,
            symbol=target.symbol,
            filled_qty=fill_qty,
            avg_fill_price=fill_price,
            fill_timestamp=fill_timestamp,
            decision_price=float(intent.decision_price),
            slippage_bps=compute_slippage_bps(fill_price, float(intent.decision_price)),
            implementation_shortfall=compute_implementation_shortfall(fill_price, float(intent.decision_price), fill_qty),
        )

        targets.append(target)
        entry_intents.append(intent)
        fills.append(fill)
        child_intents.append(build_take_profit_intent(intent, fill_qty, fill_price, execution_config, target=target))
        child_intents.append(build_trailing_stop_intent(intent, fill_qty, fill_price, execution_config, target=target))
        initial_stop = build_initial_stop_intent(intent, fill_qty, fill_price, execution_config, target=target)
        if initial_stop is not None:
            child_intents.append(initial_stop)

        replay_rows.append(
            {
                "trade_date": pd.Timestamp(snapshot_date),
                "execution_date": execution_day,
                "symbol": entry.symbol,
                "selected": True,
                "rank": float(entry.decision_rank or entry.candidate_rank or len(replay_rows) + 1),
                "score": float(entry.score_used),
                "score_source": entry.score_source,
                "target_weight": float(entry.target_weight),
                "target_notional": float(entry.target_notional),
                "approved_shares": int(entry.approved_shares),
                "filled_qty": fill_qty,
                "fill_price": fill_price,
                "decision": entry.decision,
                "decision_reason": entry.decision_reason,
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
                "score",
                "score_source",
                "target_weight",
                "target_notional",
                "approved_shares",
                "filled_qty",
                "fill_price",
                "decision",
                "decision_reason",
                "execution_replay_mode",
            ]
        )

    replay_diagnostics = {
        "requested_entries": len(entries),
        "eligible_entries": len(eligible_entries),
        "scheduled_entries": len(targets),
        "signals_generated": len(signals_df),
        "skipped_missing_snapshot": skipped_missing_snapshot,
        "skipped_no_next_session": skipped_no_next_session,
        "skipped_missing_open": skipped_missing_open,
        "exec_run_id": effective_exec_run_id,
        "bridge": "execution_engine.order_intents+tca+execution_replay",
    }
    return ExecutionReplayResult(
        execution_result=execution_result,
        signals_df=signals_df,
        diagnostics=replay_diagnostics,
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
    return artifact_paths

