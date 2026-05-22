"""Transaction Cost Analysis — fonctions pures."""
from __future__ import annotations

import pandas as pd

from execution_engine.models import ExecutionFill, TcaSummary


def _series_or_default(df: pd.DataFrame, column: str, default: float | str = 0.0) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series([default] * len(df), index=df.index)


def compute_slippage_bps(fill_price: float, decision_price: float) -> float:
    if decision_price == 0:
        return 0.0
    return (fill_price - decision_price) / decision_price * 10_000


def compute_implementation_shortfall(fill_price: float, decision_price: float, qty: float) -> float:
    return (fill_price - decision_price) * qty


def bucket_slippage_bps(slippage_bps: float | int | None) -> str:
    value = abs(float(slippage_bps or 0.0))
    if value <= 10.0:
        return "0-10 bps"
    if value <= 25.0:
        return "10-25 bps"
    if value <= 50.0:
        return "25-50 bps"
    return "> 50 bps"


def build_tca_aggregate_frame(
    fills_df: pd.DataFrame,
    *,
    group_by: tuple[str, ...],
) -> pd.DataFrame:
    base_columns = [
        *group_by,
        "fill_count",
        "distinct_symbols",
        "distinct_runs",
        "total_qty",
        "total_notional",
        "avg_slippage_bps",
        "max_abs_slippage_bps",
        "total_implementation_shortfall",
    ]
    if fills_df.empty:
        return pd.DataFrame(columns=base_columns)

    prepared = fills_df.copy()
    prepared["filled_qty"] = pd.to_numeric(_series_or_default(prepared, "filled_qty"), errors="coerce").fillna(0.0)
    prepared["avg_fill_price"] = pd.to_numeric(_series_or_default(prepared, "avg_fill_price"), errors="coerce").fillna(0.0)
    prepared["slippage_bps"] = pd.to_numeric(_series_or_default(prepared, "slippage_bps"), errors="coerce").fillna(0.0)
    prepared["implementation_shortfall"] = pd.to_numeric(
        _series_or_default(prepared, "implementation_shortfall"), errors="coerce"
    ).fillna(0.0)
    prepared["total_notional"] = prepared["filled_qty"] * prepared["avg_fill_price"]
    prepared["abs_slippage_bps"] = prepared["slippage_bps"].abs()
    prepared["month"] = pd.to_datetime(_series_or_default(prepared, "fill_timestamp", ""), errors="coerce", utc=True).dt.strftime("%Y-%m")
    prepared["slippage_bucket"] = prepared["slippage_bps"].map(bucket_slippage_bps)

    for column in group_by:
        if column not in prepared.columns:
            prepared[column] = "—"
    grouped = (
        prepared.groupby(list(group_by), dropna=False)
        .agg(
            fill_count=("symbol", "size"),
            distinct_symbols=("symbol", "nunique"),
            distinct_runs=("exec_run_id", "nunique"),
            total_qty=("filled_qty", "sum"),
            total_notional=("total_notional", "sum"),
            avg_slippage_bps=("slippage_bps", "mean"),
            max_abs_slippage_bps=("abs_slippage_bps", "max"),
            total_implementation_shortfall=("implementation_shortfall", "sum"),
        )
        .reset_index()
    )
    sort_columns = [column for column in ("month", *group_by) if column in grouped.columns]
    ascending = [False if column == "month" else True for column in sort_columns]
    if sort_columns:
        grouped = grouped.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)
    return grouped[base_columns]


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

