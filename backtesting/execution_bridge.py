"""Bridge opt-in entre le backtesting et les primitives d'exécution."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from execution_engine.config import ExecutionConfig
from execution_engine.models import ExecutionFill, ExecutionTarget, OrderIntent
from execution_engine.order_intents import build_entry_intents, build_initial_stop_intent, build_take_profit_intent, build_trailing_stop_intent
from execution_engine.tca import build_tca_summary, compute_implementation_shortfall, compute_slippage_bps
from risk_management.models import PortfolioEntry


@dataclass(slots=True)
class ExecutionBridgeResult:
	targets: list[ExecutionTarget]
	entry_intents: list[OrderIntent]
	child_intents: list[OrderIntent]
	fills: list[ExecutionFill]
	tca_summary: dict[str, object]
	diagnostics: dict[str, object]


def portfolio_entries_to_execution_targets(
	entries: list[PortfolioEntry],
	*,
	risk_run_id: str,
	trade_date,
) -> list[ExecutionTarget]:
	targets: list[ExecutionTarget] = []
	for entry in entries:
		if entry.approved_shares <= 0:
			continue
		targets.append(
			ExecutionTarget(
				risk_run_id=risk_run_id,
				trade_date=trade_date,
				symbol=entry.symbol,
				candidate_rank=entry.candidate_rank,
				target_shares=int(entry.approved_shares),
				entry_price=float(entry.entry_price),
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
		)
	return targets


def simulate_phase2_execution(
	entries: list[PortfolioEntry],
	*,
	execution_config: ExecutionConfig,
	trade_date,
	risk_run_id: str,
	exec_run_id: str | None = None,
) -> ExecutionBridgeResult:
	effective_exec_run_id = exec_run_id or f"bt_exec_{uuid.uuid4().hex[:12]}"
	targets = portfolio_entries_to_execution_targets(entries, risk_run_id=risk_run_id, trade_date=trade_date)
	entry_intents = build_entry_intents(targets, execution_config, effective_exec_run_id)
	child_intents: list[OrderIntent] = []
	fills: list[ExecutionFill] = []

	for intent, target in zip(entry_intents, targets):
		fill_timestamp = datetime.now(timezone.utc)
		fill_price = float(target.entry_price)
		fill_qty = float(target.target_shares)
		fills.append(
			ExecutionFill(
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
		)
		child_intents.append(build_take_profit_intent(intent, fill_qty, fill_price, execution_config, target=target))
		child_intents.append(build_trailing_stop_intent(intent, fill_qty, fill_price, execution_config, target=target))
		initial_stop = build_initial_stop_intent(intent, fill_qty, fill_price, execution_config, target=target)
		if initial_stop is not None:
			child_intents.append(initial_stop)

	tca_payload = asdict(build_tca_summary(fills, execution_config.max_slippage_bps))
	diagnostics = {
		"risk_run_id": risk_run_id,
		"exec_run_id": effective_exec_run_id,
		"targets": len(targets),
		"entry_intents": len(entry_intents),
		"child_intents": len(child_intents),
		"fills": len(fills),
		"bridge": "execution_engine.order_intents+tca",
	}
	return ExecutionBridgeResult(
		targets=targets,
		entry_intents=entry_intents,
		child_intents=child_intents,
		fills=fills,
		tca_summary=tca_payload,
		diagnostics=diagnostics,
	)


def _dataclasses_to_frame(items: list[object]) -> pd.DataFrame:
	if not items:
		return pd.DataFrame()
	return pd.DataFrame([asdict(item) for item in items])


def save_phase2_execution_artifacts(result: ExecutionBridgeResult, output_dir: Path) -> dict[str, str]:
	output_dir.mkdir(parents=True, exist_ok=True)
	artifact_paths: dict[str, str] = {}

	mapping = {
		"phase2_execution_targets_csv": (result.targets, "phase2_execution_targets.csv"),
		"phase2_execution_entry_intents_csv": (result.entry_intents, "phase2_execution_entry_intents.csv"),
		"phase2_execution_child_intents_csv": (result.child_intents, "phase2_execution_child_intents.csv"),
		"phase2_execution_fills_csv": (result.fills, "phase2_execution_fills.csv"),
	}
	for key, (items, filename) in mapping.items():
		frame = _dataclasses_to_frame(items)
		if frame.empty:
			continue
		path = output_dir / filename
		frame.to_csv(path, index=False)
		artifact_paths[key] = str(path)

	tca_path = output_dir / "phase2_execution_tca_summary.json"
	tca_path.write_text(json.dumps(result.tca_summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
	artifact_paths["phase2_execution_tca_summary_json"] = str(tca_path)

	diag_path = output_dir / "phase2_execution_summary.json"
	diag_path.write_text(json.dumps(result.diagnostics, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
	artifact_paths["phase2_execution_summary_json"] = str(diag_path)
	return artifact_paths

