"""Tests Sprint 3 — backtest fractionnaire natif."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backtesting.execution_bridge import portfolio_entries_to_execution_targets
from backtesting.execution_replay import _build_synthetic_fill_attempts, _entry_to_target
from backtesting.fidelity import _execution_targets_to_compare_frame, _portfolio_entries_to_compare_frame
from backtesting.risk_bridge import portfolio_entries_to_signals
from backtesting.simulator import BacktestConfig, BacktestEngine
from execution_engine.models import ExecutionTarget
from risk_management.config import RiskConfig
from risk_management.enums import Decision
from risk_management.models import PortfolioEntry



def _entry(*, approved_shares: float = 0.5, target_notional: float = 75.0) -> PortfolioEntry:
    return PortfolioEntry(
        symbol="AAPL",
        sector="Tech",
        entry_price=150.0,
        score_used=0.95,
        score_source="test",
        atr_20=5.0,
        proposed_shares=approved_shares,
        approved_shares=approved_shares,
        target_notional=target_notional,
        target_weight=0.05,
        decision=Decision.ACCEPTED,
        decision_reason="OK",
        conviction_score=0.9,
        selection_rank=1,
        decision_rank=1,
    )



def test_execution_bridge_preserves_fractional_target_shares() -> None:
    targets = portfolio_entries_to_execution_targets(
        [_entry(approved_shares=0.5)],
        risk_run_id="risk-1",
        trade_date=date(2026, 6, 9),
    )

    assert len(targets) == 1
    assert targets[0].target_shares == pytest.approx(0.5)



def test_execution_replay_entry_target_preserves_fractional_shares() -> None:
    target = _entry_to_target(
        _entry(approved_shares=0.5),
        risk_run_id="risk-1",
        execution_date=pd.Timestamp("2026-06-10"),
        entry_price=150.0,
    )

    assert target.target_shares == pytest.approx(0.5)



def test_risk_bridge_preserves_fractional_shares_in_signals() -> None:
    signals = portfolio_entries_to_signals([_entry(approved_shares=0.5)], date(2026, 6, 9))

    assert float(signals.iloc[0]["approved_shares"]) == pytest.approx(0.5)



def test_fidelity_compare_frames_preserve_fractional_shares() -> None:
    entry_frame = _portfolio_entries_to_compare_frame([_entry(approved_shares=0.5)], run_id="risk-1")
    target_frame = _execution_targets_to_compare_frame(
        [
            ExecutionTarget(
                risk_run_id="risk-1",
                trade_date=date(2026, 6, 9),
                symbol="AAPL",
                target_shares=0.5,
                entry_price=150.0,
                target_weight=0.05,
                sector="Tech",
                conviction_score=0.9,
                sizing_method="atr",
                kelly_fraction=None,
            )
        ],
        run_id="risk-1",
    )

    assert float(entry_frame.iloc[0]["approved_shares"]) == pytest.approx(0.5)
    assert float(target_frame.iloc[0]["approved_shares"]) == pytest.approx(0.5)



def test_synthetic_fill_attempts_preserve_fractional_partial_quantities() -> None:
    attempts = _build_synthetic_fill_attempts(
        execution_day=pd.Timestamp("2026-06-10"),
        target_qty=2.5,
        symbol="AAPL",
    )

    assert attempts[0].filled_qty == pytest.approx(1.5)
    assert attempts[-1].cumulative_filled_qty == pytest.approx(2.5)



def test_backtest_engine_execution_replay_mode_supports_fractional_share_override() -> None:
    idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
    open_df = pd.DataFrame({"AAPL": [100.0, 100.0, 100.0]}, index=idx)
    close_df = pd.DataFrame({"AAPL": [100.0, 110.0, 105.0]}, index=idx)
    high_df = pd.DataFrame({"AAPL": [101.0, 120.0, 106.0]}, index=idx)
    low_df = pd.DataFrame({"AAPL": [99.0, 99.0, 100.0]}, index=idx)
    signals_df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "signal_date": pd.to_datetime(["2025-01-01"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "rank": [1.0],
            "approved_shares": [0.5],
            "filled_qty": [0.5],
            "target_weight": [0.10],
        }
    )

    result = BacktestEngine(
        BacktestConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 3),
            initial_equity=10_000,
            max_positions=1,
            fees_pct=0.0,
            risk_config=RiskConfig(allow_fractional_shares=True, max_positions=1),
            execution_replay_mode="execution_replay",
        )
    ).run(open=open_df, close=close_df, high=high_df, low=low_df, signals_df=signals_df)

    trades_df = result.trades.records_readable
    assert not trades_df.empty
    assert float(trades_df["Size"].iloc[0]) == pytest.approx(0.5)

