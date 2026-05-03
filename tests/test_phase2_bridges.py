from __future__ import annotations

from datetime import date

import pandas as pd


def test_build_phase2_risk_result_generates_entries_and_signals() -> None:
    from backtesting.risk_bridge import build_phase2_risk_result
    from risk_management.config import RiskConfig

    trade_dates = pd.date_range("2025-01-01", periods=25, freq="D")
    close_values = [100.0 + idx for idx in range(len(trade_dates))]
    high_values = [value + 1.0 for value in close_values]
    low_values = [value - 1.0 for value in close_values]

    scores_df = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "trade_date": [trade_dates[-1]],
            "final_score": [0.80],
            "final_score_sentiment": [0.82],
            "score": [0.82],
            "score_source": ["final_score_sentiment"],
            "sector": ["Tech"],
        }
    )
    predictions_df = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "trade_date": [trade_dates[-1]],
            "predicted_proba": [0.67],
            "predicted_class": [1],
            "run_id": ["ml_run_001"],
        }
    )
    close_df = pd.DataFrame({"AAPL": close_values}, index=trade_dates)
    high_df = pd.DataFrame({"AAPL": high_values}, index=trade_dates)
    low_df = pd.DataFrame({"AAPL": low_values}, index=trade_dates)
    snapshot_day = pd.Timestamp(trade_dates[-1]).date()

    result = build_phase2_risk_result(
        scores_df=scores_df,
        predictions_df=predictions_df,
        close_df=close_df,
        high_df=high_df,
        low_df=low_df,
        risk_config=RiskConfig(
            account_equity=100_000.0,
            max_positions=5,
            max_position_weight=0.20,
            max_sector_weight=1.0,
            max_gross_exposure=1.0,
            min_position_notional=500.0,
        ),
    )

    assert result.diagnostics["bridge"] == "risk_management.portfolio_builder"
    assert result.diagnostics["snapshot_dates"] == 1
    assert result.diagnostics["entries_total"] == 1
    assert result.diagnostics["entries_accepted"] == 1
    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.symbol == "AAPL"
    assert entry.approved_shares > 0
    assert entry.atr_20 is not None
    assert entry.score_snapshot_date == snapshot_day
    assert not result.signals_df.empty
    signal = result.signals_df.iloc[0]
    assert signal["symbol"] == "AAPL"
    assert bool(signal["selected"]) is True
    assert int(signal.get("approved_shares", 0)) == int(entry.approved_shares)


def test_simulate_phase2_execution_generates_targets_intents_and_fills() -> None:
    from backtesting.execution_bridge import simulate_phase2_execution
    from execution_engine.config import ExecutionConfig
    from risk_management.models import PortfolioEntry

    entry = PortfolioEntry(
        symbol="AAPL",
        sector="Tech",
        entry_price=123.45,
        score_used=0.82,
        score_source="final_score_sentiment",
        atr_20=2.5,
        proposed_shares=40,
        approved_shares=40,
        target_notional=4_938.0,
        target_weight=0.04938,
        decision="ACCEPTED",
        decision_reason="OK",
        conviction_score=0.83,
        sizing_method="atr",
        kelly_fraction=0.10,
        decision_rank=1,
        stop_price_initial=118.45,
        risk_per_share=5.0,
        risk_budget_dollars=1_000.0,
        initial_risk_dollars=200.0,
        score_snapshot_date=date(2025, 1, 31),
        price_asof_date=date(2025, 1, 31),
        atr_asof_date=date(2025, 1, 31),
    )

    result = simulate_phase2_execution(
        [entry],
        execution_config=ExecutionConfig(
            broker_mode="paper",
            dry_run=True,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            simulated_account_equity=100_000.0,
            profit_taker_pct=0.08,
            trailing_stop_pct=0.05,
        ),
        trade_date=date(2025, 1, 31),
        risk_run_id="bt_phase2_20250101_20250131",
        exec_run_id="exec_test_001",
    )

    assert result.diagnostics["bridge"] == "execution_engine.order_intents+tca"
    assert result.diagnostics["risk_run_id"] == "bt_phase2_20250101_20250131"
    assert result.diagnostics["exec_run_id"] == "exec_test_001"
    assert len(result.targets) == 1
    assert len(result.entry_intents) == 1
    assert len(result.child_intents) >= 2
    assert len(result.fills) == 1
    assert result.targets[0].symbol == "AAPL"
    assert result.entry_intents[0].symbol == "AAPL"
    assert result.fills[0].avg_fill_price == 123.45
    assert result.tca_summary["total_filled"] == 1


def test_simulate_phase3_execution_replay_generates_replay_signals() -> None:
    from backtesting.execution_replay import simulate_phase3_execution_replay
    from execution_engine.config import ExecutionConfig
    from risk_management.models import PortfolioEntry

    open_df = pd.DataFrame(
        {"AAPL": [100.0, 105.0, 106.0]},
        index=pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
    )
    entry = PortfolioEntry(
        symbol="AAPL",
        sector="Tech",
        entry_price=123.45,
        score_used=0.82,
        score_source="final_score_sentiment",
        atr_20=2.5,
        proposed_shares=40,
        approved_shares=40,
        target_notional=4_938.0,
        target_weight=0.04938,
        decision="ACCEPTED",
        decision_reason="OK",
        conviction_score=0.83,
        sizing_method="atr",
        decision_rank=1,
        stop_price_initial=118.45,
        risk_per_share=5.0,
        risk_budget_dollars=1_000.0,
        initial_risk_dollars=200.0,
        score_snapshot_date=date(2025, 1, 1),
        price_asof_date=date(2025, 1, 1),
        atr_asof_date=date(2025, 1, 1),
    )

    result = simulate_phase3_execution_replay(
        [entry],
        execution_config=ExecutionConfig(
            broker_mode="paper",
            dry_run=True,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            simulated_account_equity=100_000.0,
            profit_taker_pct=0.08,
            trailing_stop_pct=0.05,
        ),
        open_df=open_df,
        risk_run_id_prefix="bt_phase3_20250101_20250103",
        exec_run_id="exec_replay_001",
    )

    assert result.execution_result.diagnostics["exec_run_id"] == "exec_replay_001"
    assert result.execution_result.diagnostics["targets"] == 1
    assert result.diagnostics["scheduled_entries"] == 1
    assert result.diagnostics["signals_generated"] == 1
    assert not result.signals_df.empty
    signal = result.signals_df.iloc[0]
    assert signal["trade_date"] == pd.Timestamp("2025-01-01")
    assert signal["execution_date"] == pd.Timestamp("2025-01-02")
    assert signal["symbol"] == "AAPL"
    assert float(signal["filled_qty"]) == 40.0
    assert float(signal["fill_price"]) == 105.0




