"""Reconciliation positions broker vs cibles portfolio_targets."""
from __future__ import annotations

from execution_engine.models import ExecutionTarget, ReconcileDiff


def reconcile_targets_vs_broker(
    targets: list[ExecutionTarget],
    broker_positions: list[dict],
    tolerance: int = 0,
) -> list[ReconcileDiff]:
    target_map: dict[str, int] = {t.symbol: t.target_shares for t in targets}
    broker_map: dict[str, float] = {
        str(p.get("symbol", "")).upper(): float(p.get("qty", 0))
        for p in broker_positions
    }
    all_symbols = sorted(set(target_map) | set(broker_map))
    diffs: list[ReconcileDiff] = []
    for sym in all_symbols:
        tgt = target_map.get(sym, 0)
        brk = broker_map.get(sym, 0.0)
        delta = brk - tgt
        if abs(delta) <= tolerance:
            action = "none"
        elif sym not in target_map:
            action = "investigate"
        elif delta > 0:
            action = "sell_excess"
        else:
            action = "buy_more"
        diffs.append(ReconcileDiff(symbol=sym, target_qty=tgt, broker_qty=brk, delta=delta, action=action))
    return diffs
