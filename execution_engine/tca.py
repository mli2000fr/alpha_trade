"""Transaction Cost Analysis — fonctions pures."""
from __future__ import annotations

from execution_engine.models import ExecutionFill, TcaSummary


def compute_slippage_bps(fill_price: float, decision_price: float) -> float:
    if decision_price == 0:
        return 0.0
    return (fill_price - decision_price) / decision_price * 10_000


def compute_implementation_shortfall(fill_price: float, decision_price: float, qty: float) -> float:
    return (fill_price - decision_price) * qty


def build_tca_summary(fills: list[ExecutionFill], max_slippage_bps: int) -> TcaSummary:
    if not fills:
        return TcaSummary(
            total_orders=0, total_filled=0, total_notional=0.0,
            avg_slippage_bps=0.0, max_slippage_bps=0.0,
            total_implementation_shortfall=0.0, slippage_alerts=0,
        )
    slippages = [f.slippage_bps for f in fills]
    return TcaSummary(
        total_orders=len(fills),
        total_filled=len(fills),
        total_notional=sum(f.avg_fill_price * f.filled_qty for f in fills),
        avg_slippage_bps=sum(slippages) / len(slippages),
        max_slippage_bps=max(abs(s) for s in slippages),
        total_implementation_shortfall=sum(f.implementation_shortfall for f in fills),
        slippage_alerts=sum(1 for s in slippages if abs(s) > max_slippage_bps),
    )

