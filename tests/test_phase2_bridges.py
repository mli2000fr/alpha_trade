from __future__ import annotations

import warnings
from datetime import date
from pathlib import Path

import pandas as pd
import pytest


@pytest.mark.parametrize(
    ("score_column", "expected_sources"),
    [
        (
            None,
            {
                "AAA": "final_score_walk_forward",
                "BBB": "final_score_sentiment",
                "CCC": "final_score",
            },
        ),
        (
            "final_score_sentiment",
            {
                "AAA": "final_score_sentiment",
                "BBB": "final_score_sentiment",
                "CCC": "final_score",
            },
        ),
        (
            "final_score",
            {
                "AAA": "final_score",
                "BBB": "final_score",
                "CCC": "final_score",
            },
        ),
    ],
)
def test_signal_replay_and_risk_bridge_keep_same_score_cascade(score_column, expected_sources) -> None:
    from backtesting.risk_bridge import build_phase2_risk_result
    from backtesting.signal_replay import replay_signals
    from risk_management.config import RiskConfig

    trade_dates = pd.date_range("2025-01-01", periods=30, freq="D")
    snapshot_ts = trade_dates[-1]
    close_df = pd.DataFrame(
        {
            "AAA": [100.0 + idx for idx in range(len(trade_dates))],
            "BBB": [80.0 + idx for idx in range(len(trade_dates))],
            "CCC": [60.0 + idx for idx in range(len(trade_dates))],
        },
        index=trade_dates,
    )
    high_df = close_df + 1.0
    low_df = close_df - 1.0
    scores_df = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC"],
            "trade_date": [snapshot_ts, snapshot_ts, snapshot_ts],
            "final_score": [0.20, 0.70, 0.90],
            "final_score_sentiment": [0.60, 0.75, None],
            "final_score_walk_forward": [0.95, None, None],
            "sector": ["Tech", "Health", "Energy"],
        }
    )

    replay_df = replay_signals(
        scores_df,
        predictions_df=None,
        score_column=score_column,
        max_positions=10,
    )
    phase2_result = build_phase2_risk_result(
        scores_df=scores_df,
        predictions_df=pd.DataFrame(),
        close_df=close_df,
        high_df=high_df,
        low_df=low_df,
        risk_config=RiskConfig(
            account_equity=100_000.0,
            max_positions=10,
            max_position_weight=1.0,
            max_sector_weight=1.0,
            max_gross_exposure=1.0,
            min_position_notional=1.0,
        ),
        score_column=score_column,
    )

    replay_by_symbol = replay_df.set_index("symbol")
    entries_by_symbol = {entry.symbol: entry for entry in phase2_result.entries}

    assert set(entries_by_symbol) == {"AAA", "BBB", "CCC"}
    for symbol, expected_source in expected_sources.items():
        assert replay_by_symbol.loc[symbol, "score_source"] == expected_source
        assert entries_by_symbol[symbol].score_source == expected_source
        assert float(replay_by_symbol.loc[symbol, "score"]) == pytest.approx(entries_by_symbol[symbol].score_used)


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
            "candidate_rank": [6],
            "selector_signal_mode": ["sector_neutralized"],
            "selection_explanation": ["mode=sector_neutralized; rank=6"],
            "earnings_blackout": [1],
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
    assert int(signal["candidate_rank"]) == 6
    assert signal["selector_signal_mode"] == "sector_neutralized"
    assert signal["selection_explanation"] == "mode=sector_neutralized; rank=6"
    assert int(signal["selector_earnings_blackout"]) == 1
    assert int(signal.get("approved_shares", 0)) == int(entry.approved_shares)


def test_build_phase2_risk_result_uses_walk_forward_score_when_available() -> None:
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
            "final_score_walk_forward": [0.93],
            "sector": ["Tech"],
        }
    )
    close_df = pd.DataFrame({"AAPL": close_values}, index=trade_dates)
    high_df = pd.DataFrame({"AAPL": high_values}, index=trade_dates)
    low_df = pd.DataFrame({"AAPL": low_values}, index=trade_dates)

    result = build_phase2_risk_result(
        scores_df=scores_df,
        predictions_df=pd.DataFrame(),
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

    assert result.entries[0].score_used == pytest.approx(0.93)
    assert result.entries[0].score_source == "final_score_walk_forward"


def test_build_phase2_risk_result_preserves_empty_signal_schema_when_all_entries_rejected() -> None:
    from backtesting.risk_bridge import build_phase2_risk_result
    from risk_management.config import RiskConfig

    trade_dates = pd.to_datetime(["2025-01-01", "2025-01-02"])
    close_df = pd.DataFrame({"AAPL": [100.0, 101.0]}, index=trade_dates)
    high_df = pd.DataFrame({"AAPL": [101.0, 102.0]}, index=trade_dates)
    low_df = pd.DataFrame({"AAPL": [99.0, 100.0]}, index=trade_dates)
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

    result = build_phase2_risk_result(
        scores_df=scores_df,
        predictions_df=pd.DataFrame(),
        close_df=close_df,
        high_df=high_df,
        low_df=low_df,
        risk_config=RiskConfig(
            account_equity=2_000.0,
            max_positions=4,
            min_position_notional=500.0,
        ),
    )

    assert result.signals_df.empty
    assert result.diagnostics["entries_total"] == 1
    assert result.diagnostics["entries_accepted"] == 0
    assert result.diagnostics["signals_generated"] == 0
    assert list(result.signals_df.columns) == [
        "trade_date",
        "symbol",
        "selected",
        "rank",
        "candidate_rank",
        "score",
        "score_source",
        "conviction_score",
        "conviction_source",
        "predicted_proba",
        "selector_signal_mode",
        "selection_explanation",
        "selector_earnings_blackout",
        "target_weight",
        "target_notional",
        "approved_shares",
        "decision",
        "decision_reason",
        "decision_reason_code",
    ]


def test_short_flow_selector_and_phase2_risk_bridge_keep_same_side_decisions(monkeypatch) -> None:
    import service.market as market_service

    from backtesting.risk_bridge import build_phase2_risk_result
    from risk_management.config import RiskConfig
    from risk_management.enums import Decision
    from risk_management.models import PortfolioEntry
    from selector.short_score import (
        enrich_with_short_score,
        inject_predicted_side,
        resolve_regime_adaptive_short_params,
        tag_short_candidates,
    )
    from service.market.config import MarketRegimesConfig
    from service.market.models import MarketRegimeSnapshot

    trade_dates = pd.date_range("2025-01-01", periods=60, freq="D")
    snapshot_ts = trade_dates[-1]
    close_df = pd.DataFrame(
        {
            "AAPL": [160.0 - idx for idx in range(len(trade_dates))],
            "MSFT": [100.0 + idx for idx in range(len(trade_dates))],
        },
        index=trade_dates,
    )
    high_df = close_df + 1.0
    low_df = close_df - 1.0
    scores_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT"],
            "trade_date": [snapshot_ts, snapshot_ts],
            "final_score": [0.20, 0.80],
            "score": [0.20, 0.80],
            "score_source": ["test", "test"],
            "sector": ["Tech", "Tech"],
            "trend_score": [0.10, 0.85],
            "relative_strength_index": [25.0, 68.0],
        }
    )
    predictions_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT"],
            "trade_date": [snapshot_ts, snapshot_ts],
            "predicted_side": ["short", "long"],
            "predicted_proba": [0.35, 0.70],
            "predicted_class": [-1, 1],
            "run_id": ["ml-run", "ml-run"],
        }
    )

    selector_day = inject_predicted_side(scores_df.copy(), predictions_df, snapshot_ts)
    selector_day = enrich_with_short_score(selector_day, close_df=close_df, trade_day=snapshot_ts)
    eff_max_short, eff_min_short = resolve_regime_adaptive_short_params(
        RiskConfig(short_selling_enabled=True, short_max_positions=2, short_min_score=0.30),
        True,
    )
    selector_day = tag_short_candidates(
        selector_day,
        max_short_positions=eff_max_short,
        min_score_for_short=eff_min_short,
    )
    selector_sides = dict(zip(selector_day["symbol"], selector_day["side"]))

    def fake_build_snapshot(trade_date, *, config, equity=None, execution_context="backtest", **kwargs):
        return MarketRegimeSnapshot(
            trade_date=trade_date,
            mode="capital_preservation",
            allow_new_entries=True,
            allowed_long_entries=True,
            allowed_short_entries=True,
            reasons=("test",),
            data_quality={"macro": "ok"},
        )

    class _FakeBuilder:
        def __init__(self, config, rotation_state=None, factor_exposures=None, factor_covariance=None):
            self.progress_callback = None

        def build(self, candidates, prices, predictions=None, return_matrix=None):
            return [
                PortfolioEntry(
                    symbol=candidate.symbol,
                    sector=candidate.sector,
                    entry_price=prices[candidate.symbol].last_close,
                    score_used=candidate.score_used,
                    score_source=candidate.score_source,
                    atr_20=prices[candidate.symbol].atr_20,
                    proposed_shares=1.0,
                    approved_shares=1.0,
                    target_notional=prices[candidate.symbol].last_close,
                    target_weight=0.01,
                    decision=Decision.ACCEPTED,
                    decision_reason="OK",
                    conviction_score=candidate.score_used,
                    predicted_proba=(
                        predictions[candidate.symbol].predicted_proba
                        if predictions and candidate.symbol in predictions
                        else None
                    ),
                    side=candidate.side,
                )
                for candidate in candidates
            ]

    monkeypatch.setattr(market_service, "build_snapshot", fake_build_snapshot)
    monkeypatch.setattr("backtesting.risk_bridge.PortfolioBuilder", _FakeBuilder)

    result = build_phase2_risk_result(
        scores_df=scores_df,
        predictions_df=predictions_df,
        close_df=close_df,
        high_df=high_df,
        low_df=low_df,
        risk_config=RiskConfig(
            account_equity=100_000.0,
            max_positions=5,
            max_position_weight=1.0,
            max_sector_weight=1.0,
            max_gross_exposure=1.0,
            min_position_notional=1.0,
            short_selling_enabled=True,
            short_max_positions=2,
            short_min_score=0.30,
        ),
        market_regimes_config=MarketRegimesConfig(enabled=True),
    )

    bridge_sides = {entry.symbol: entry.side for entry in result.entries}
    signal_sides = result.signals_df.set_index("symbol")["side"].to_dict()

    assert selector_sides == {"AAPL": "sell", "MSFT": "buy"}
    assert bridge_sides == selector_sides
    assert signal_sides == selector_sides


def test_build_return_matrix_uses_explicit_no_fill_on_price_gaps() -> None:
    from backtesting.risk_bridge import _build_return_matrix

    trade_dates = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"])
    close_df = pd.DataFrame(
        {
            "AAPL": [100.0, None, 110.0, 121.0],
            "MSFT": [50.0, 55.0, 60.0, 66.0],
        },
        index=trade_dates,
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", FutureWarning)
        returns = _build_return_matrix(
            close_df,
            date(2025, 1, 4),
            ["AAPL", "MSFT"],
            lookback_days=10,
        )

    assert returns is not None
    assert not any(issubclass(w.category, FutureWarning) for w in caught)
    aapl_returns = returns["AAPL"]
    msft_returns = returns["MSFT"]
    assert pd.isna(aapl_returns.at[pd.Timestamp("2025-01-02")])
    assert pd.isna(aapl_returns.at[pd.Timestamp("2025-01-03")])
    assert aapl_returns.at[pd.Timestamp("2025-01-04")] == pytest.approx(0.1)
    assert msft_returns.at[pd.Timestamp("2025-01-02")] == pytest.approx(0.1)


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
        candidate_rank=2,
        decision_rank=1,
        selector_signal_mode="strict",
        selection_explanation="mode=strict; rank=2",
        selector_earnings_blackout=0,
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
    assert result.targets[0].candidate_rank == 2
    assert result.targets[0].selector_signal_mode == "strict"
    assert result.targets[0].selection_explanation == "mode=strict; rank=2"
    assert result.targets[0].selector_earnings_blackout == 0
    assert result.entry_intents[0].symbol == "AAPL"
    assert result.fills[0].avg_fill_price == 123.45
    assert result.tca_summary["total_filled"] == 1


def test_simulate_phase3_execution_replay_generates_replay_signals() -> None:
    from backtesting.execution_replay import simulate_phase3_execution_replay
    from execution_engine.config import ExecutionConfig
    from execution_engine.models import EventType, IntentRole, OrderStatus
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
        candidate_rank=9,
        decision_rank=1,
        selector_signal_mode="sector_neutralized",
        selection_explanation="mode=sector_neutralized; rank=9",
        selector_earnings_blackout=1,
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
    assert int(signal["candidate_rank"]) == 9
    assert signal["selector_signal_mode"] == "sector_neutralized"
    assert signal["selection_explanation"] == "mode=sector_neutralized; rank=9"
    assert int(signal["selector_earnings_blackout"]) == 1
    assert float(signal["filled_qty"]) == 40.0
    assert float(signal["fill_price"]) == 105.0
    assert signal["entry_order_status"] == OrderStatus.FILLED
    assert int(signal["entry_attempt_count"]) == 4
    assert int(signal["entry_partial_fill_count"]) == 1
    assert int(signal["entry_retry_count"]) == 3
    assert int(signal["entry_resubmit_count"]) == 3
    assert int(signal["entry_cancel_count"]) == 1
    assert int(signal["entry_reject_count"]) == 1
    assert int(signal["entry_timeout_count"]) == 1
    assert pd.notna(signal["entry_retry_chain_id"])
    assert result.execution_result.diagnostics["fills"] == 2
    assert result.diagnostics["broker_like_orders"] == 7
    assert result.diagnostics["partial_fill_orders"] == 1
    assert result.diagnostics["retry_orders"] == 3
    assert result.diagnostics["canceled_orders"] == 1
    assert result.diagnostics["rejected_orders"] == 1
    assert result.diagnostics["timed_out_orders"] == 1
    assert result.diagnostics["held_orders"] == 1
    assert set(result.order_lifecycle_frame["intent_role"]) == {
        IntentRole.ENTRY,
        IntentRole.TAKE_PROFIT,
        IntentRole.TRAILING_STOP,
        IntentRole.INITIAL_STOP,
    }
    entry_rows = result.order_lifecycle_frame[result.order_lifecycle_frame["intent_role"] == IntentRole.ENTRY].sort_values("attempt_no")
    assert len(entry_rows) == 4
    assert list(entry_rows["order_status"]) == [OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.EXPIRED, OrderStatus.FILLED]
    assert list(entry_rows["synthetic_retry"].astype(bool)) == [False, True, True, True]
    assert list(entry_rows["remaining_qty"]) == [16.0, 16.0, 16.0, 0.0]
    assert list(entry_rows["attempt_outcome"]) == ["partial_fill_canceled", "rejected", "timed_out", "filled_after_resubmit"]
    assert list(entry_rows["resubmit_of_attempt_no"].fillna(0).astype(int)) == [0, 1, 2, 3]
    trailing_row = result.order_lifecycle_frame[result.order_lifecycle_frame["intent_role"] == IntentRole.TRAILING_STOP].iloc[0]
    assert trailing_row["order_status"] == OrderStatus.HELD
    assert trailing_row["broker_state"] == "held"
    assert EventType.ORDER_PARTIALLY_FILLED in set(result.event_frame["event_type"])
    assert EventType.ORDER_CANCELED in set(result.event_frame["event_type"])
    assert EventType.ORDER_REJECTED in set(result.event_frame["event_type"])
    assert EventType.ORDER_TIMEOUT in set(result.event_frame["event_type"])


def test_build_phase4_protection_replay_enriches_signals_with_child_protections() -> None:
    from backtesting.execution_lifecycle_replay import build_phase4_protection_replay
    from backtesting.execution_replay import simulate_phase3_execution_replay
    from execution_engine.config import ExecutionConfig
    from execution_engine.models import OrderStatus
    from risk_management.models import PortfolioEntry

    execution_config = ExecutionConfig(
        broker_mode="paper",
        dry_run=True,
        account_type="margin",
        swing_only=False,
        simulated_account_equity=100_000.0,
        profit_taker_pct=0.08,
        trailing_stop_pct=0.05,
    )
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
        stop_price_initial=100.0,
        risk_per_share=5.0,
        risk_budget_dollars=1_000.0,
        initial_risk_dollars=200.0,
        score_snapshot_date=date(2025, 1, 1),
        price_asof_date=date(2025, 1, 1),
        atr_asof_date=date(2025, 1, 1),
    )

    replay_result = simulate_phase3_execution_replay(
        [entry],
        execution_config=execution_config,
        open_df=open_df,
        risk_run_id_prefix="bt_phase4_20250101_20250103",
        exec_run_id="exec_replay_002",
    )
    protection_result = build_phase4_protection_replay(
        replay_result,
        execution_config=execution_config,
    )

    assert protection_result.diagnostics["protections_replayed"] == 1
    assert protection_result.diagnostics["bridge"] == "execution_engine.child_intents+protection_replay"
    assert not protection_result.protection_frame.empty
    enriched_signal = protection_result.signals_df.iloc[0]
    assert float(enriched_signal["replay_take_profit_price"]) > float(enriched_signal["fill_price"])
    assert float(enriched_signal["replay_initial_stop_price"]) < float(enriched_signal["fill_price"])
    assert float(enriched_signal["replay_trailing_stop_pct"]) == pytest.approx(0.0476, rel=1e-2)
    assert float(enriched_signal["replay_trailing_activation_price"]) > float(enriched_signal["fill_price"])
    assert enriched_signal["replay_trailing_stop_order_status"] == OrderStatus.HELD
    assert pd.notna(enriched_signal["replay_take_profit_intent_id"])
    assert pd.notna(enriched_signal["replay_oco_group_id"])


def test_build_phase4_protection_replay_keeps_trade_specific_stop_levels_for_same_symbol() -> None:
    from backtesting.execution_lifecycle_replay import build_phase4_protection_replay
    from backtesting.execution_replay import simulate_phase3_execution_replay
    from execution_engine.config import ExecutionConfig
    from risk_management.models import PortfolioEntry

    execution_config = ExecutionConfig(
        broker_mode="paper",
        dry_run=True,
        account_type="margin",
        swing_only=False,
        simulated_account_equity=100_000.0,
        profit_taker_pct=0.08,
        trailing_stop_pct=0.05,
    )
    open_df = pd.DataFrame(
        {"AAPL": [100.0, 110.0, 120.0, 121.0]},
        index=pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06"]),
    )
    entry_1 = PortfolioEntry(
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
        stop_price_initial=95.0,
        risk_per_share=5.0,
        risk_budget_dollars=1_000.0,
        initial_risk_dollars=200.0,
        score_snapshot_date=date(2025, 1, 1),
        price_asof_date=date(2025, 1, 1),
        atr_asof_date=date(2025, 1, 1),
    )
    entry_2 = PortfolioEntry(
        symbol="AAPL",
        sector="Tech",
        entry_price=130.0,
        score_used=0.81,
        score_source="final_score_sentiment",
        atr_20=3.0,
        proposed_shares=30,
        approved_shares=30,
        target_notional=3_900.0,
        target_weight=0.039,
        decision="ACCEPTED",
        decision_reason="OK",
        conviction_score=0.8,
        sizing_method="atr",
        decision_rank=1,
        stop_price_initial=105.0,
        risk_per_share=6.0,
        risk_budget_dollars=1_000.0,
        initial_risk_dollars=180.0,
        score_snapshot_date=date(2025, 1, 2),
        price_asof_date=date(2025, 1, 2),
        atr_asof_date=date(2025, 1, 2),
    )

    replay_result = simulate_phase3_execution_replay(
        [entry_1, entry_2],
        execution_config=execution_config,
        open_df=open_df,
        risk_run_id_prefix="bt_phase4_multientry",
        exec_run_id="exec_replay_002b",
    )
    protection_result = build_phase4_protection_replay(
        replay_result,
        execution_config=execution_config,
    )

    stop_values = (
        protection_result.signals_df.sort_values("execution_date")["replay_initial_stop_price"].dropna().tolist()
    )
    assert len(stop_values) == 2
    assert stop_values[0] != stop_values[1]


def test_build_phase5_watcher_replay_generates_lifecycle_and_events() -> None:
    from backtesting.execution_lifecycle_replay import build_phase4_protection_replay
    from backtesting.execution_replay import simulate_phase3_execution_replay
    from backtesting.protection_watcher_replay import build_phase5_watcher_replay
    from execution_engine.config import ExecutionConfig
    from execution_engine.models import EventType, IntentRole, OrderStatus
    from risk_management.models import PortfolioEntry

    execution_config = ExecutionConfig(
        broker_mode="paper",
        dry_run=True,
        account_type="margin",
        swing_only=False,
        simulated_account_equity=100_000.0,
        profit_taker_pct=0.08,
        trailing_stop_pct=0.05,
    )
    trading_index = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06"])
    open_df = pd.DataFrame({"AAPL": [100.0, 105.0, 106.0, 107.0]}, index=trading_index)
    high_df = pd.DataFrame({"AAPL": [100.0, 105.0, 111.0, 112.0]}, index=trading_index)
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
        stop_price_initial=100.0,
        risk_per_share=5.0,
        risk_budget_dollars=1_000.0,
        initial_risk_dollars=200.0,
        score_snapshot_date=date(2025, 1, 1),
        price_asof_date=date(2025, 1, 1),
        atr_asof_date=date(2025, 1, 1),
    )

    replay_result = simulate_phase3_execution_replay(
        [entry],
        execution_config=execution_config,
        open_df=open_df,
        risk_run_id_prefix="bt_phase5_20250101_20250106",
        exec_run_id="exec_replay_003",
    )
    protection_result = build_phase4_protection_replay(
        replay_result,
        execution_config=execution_config,
    )
    watcher_result = build_phase5_watcher_replay(
        protection_result,
        high_df=high_df,
    )

    assert watcher_result.diagnostics["bridge"] == "execution_engine.protection_watcher+watcher_replay"
    assert watcher_result.diagnostics["transitioned_items"] == 1
    assert len(watcher_result.event_frame) == 2
    assert set(watcher_result.event_frame["event_type"]) == {
        EventType.PROTECTION_TRIGGER_HIT,
        EventType.PROTECTION_TRANSITION_COMPLETED,
    }
    lifecycle = watcher_result.lifecycle_frame.iloc[0]
    assert lifecycle["watcher_transition_state"] == "transitioned"
    assert lifecycle["watcher_trigger_date"] == pd.Timestamp("2025-01-03")
    assert lifecycle["watcher_transition_effective_date"] == pd.Timestamp("2025-01-06")
    trailing_row = watcher_result.order_lifecycle_frame[
        watcher_result.order_lifecycle_frame["intent_role"] == IntentRole.TRAILING_STOP
    ].iloc[0]
    assert trailing_row["order_status"] == OrderStatus.SUBMITTED
    assert trailing_row["broker_state"] == "working"
    initial_stop_row = watcher_result.order_lifecycle_frame[
        watcher_result.order_lifecycle_frame["intent_role"] == IntentRole.INITIAL_STOP
    ].iloc[0]
    assert initial_stop_row["order_status"] == OrderStatus.CANCELED
    assert watcher_result.diagnostics["canceled_initial_stop_orders"] == 1


def test_build_phase7_exit_lifecycle_replay_generates_terminal_exit_and_oco_cancel() -> None:
    from backtesting.exit_lifecycle_replay import build_phase7_exit_lifecycle_replay
    from backtesting.protection_watcher_replay import ProtectionWatcherReplayResult
    from execution_engine.models import EventType, OrderStatus

    trading_index = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    signals_df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "execution_date": pd.to_datetime(["2025-01-02"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "fill_price": [100.0],
            "replay_take_profit_price": [150.0],
            "replay_initial_stop_price": [90.0],
            "replay_trailing_stop_pct": [0.05],
            "order_group_id": ["entry_001"],
            "replay_oco_group_id": ["oco_entry_001"],
            "replay_take_profit_intent_id": ["tp_001"],
            "replay_initial_stop_intent_id": ["stop_001"],
            "replay_trailing_stop_intent_id": ["trail_001"],
            "watcher_transition_effective_date": pd.to_datetime(["2025-01-03"]),
        }
    )
    watcher_result = ProtectionWatcherReplayResult(
        signals_df=signals_df,
        lifecycle_frame=pd.DataFrame(),
        event_frame=pd.DataFrame(),
        diagnostics={"bridge": "execution_engine.protection_watcher+watcher_replay"},
        order_lifecycle_frame=pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-01", "2025-01-01"]),
                "execution_date": pd.to_datetime(["2025-01-02", "2025-01-02", "2025-01-02", "2025-01-02"]),
                "symbol": ["AAPL", "AAPL", "AAPL", "AAPL"],
                "order_group_id": ["entry_001", "entry_001", "entry_001", "entry_001"],
                "oco_group_id": ["oco_entry_001", "oco_entry_001", "oco_entry_001", "oco_entry_001"],
                "intent_id": ["entry_001", "tp_001", "stop_001", "trail_001"],
                "parent_intent_id": [None, "entry_001", "entry_001", "entry_001"],
                "intent_role": ["entry", "take_profit", "initial_stop", "trailing_stop"],
                "order_status": ["FILLED", "SUBMITTED", "CANCELED", "SUBMITTED"],
                "broker_state": ["filled", "working", "canceled", "working"],
            }
        ),
        broker_event_frame=pd.DataFrame(),
    )
    high_df = pd.DataFrame({"AAPL": [106.0, 107.0, 101.0]}, index=trading_index)
    low_df = pd.DataFrame({"AAPL": [99.0, 100.0, 99.0]}, index=trading_index)

    result = build_phase7_exit_lifecycle_replay(
        watcher_result,
        high_df=high_df,
        low_df=low_df,
    )

    assert result.diagnostics["bridge"] == "execution_engine.oco_manager+exit_lifecycle_replay"
    assert result.diagnostics["exit_rows"] == 1
    assert result.diagnostics["filled_trailing_stop"] == 1
    assert result.diagnostics["oco_cancels"] == 1
    assert len(result.event_frame) == 2
    exit_row = result.exit_frame.iloc[0]
    assert exit_row["replay_exit_date"] == pd.Timestamp("2025-01-03")
    assert exit_row["replay_exit_reason"] == "trailing_stop"
    assert exit_row["replay_exit_intent_role"] == "trailing_stop"
    assert exit_row["replay_exit_intent_id"] == "trail_001"
    assert exit_row["replay_exit_order_status"] == OrderStatus.FILLED
    assert bool(exit_row["replay_oco_sibling_canceled"]) is True
    assert EventType.OCO_CANCEL_TRIGGERED in set(result.event_frame["event_type"])
    enriched_signal = result.signals_df.iloc[0]
    assert enriched_signal["replay_exit_reason"] == "trailing_stop"
    assert bool(enriched_signal["replay_oco_sibling_canceled"]) is True
    trailing_row = result.order_lifecycle_frame[result.order_lifecycle_frame["intent_id"] == "trail_001"].iloc[0]
    assert trailing_row["order_status"] == OrderStatus.FILLED
    take_profit_row = result.order_lifecycle_frame[result.order_lifecycle_frame["intent_id"] == "tp_001"].iloc[0]
    assert take_profit_row["order_status"] == OrderStatus.CANCELED
    assert result.diagnostics["canceled_orders"] >= 1


def test_build_phase7_exit_lifecycle_replay_marks_open_children_as_stale_when_no_exit_occurs() -> None:
    from backtesting.exit_lifecycle_replay import build_phase7_exit_lifecycle_replay
    from backtesting.protection_watcher_replay import ProtectionWatcherReplayResult
    from execution_engine.models import OrderStatus

    trading_index = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    signals_df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "execution_date": pd.to_datetime(["2025-01-02"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "fill_price": [100.0],
            "replay_take_profit_price": [150.0],
            "replay_initial_stop_price": [90.0],
            "replay_trailing_stop_pct": [0.05],
            "replay_take_profit_intent_id": ["tp_002"],
            "replay_initial_stop_intent_id": ["stop_002"],
            "replay_trailing_stop_intent_id": ["trail_002"],
        }
    )
    watcher_result = ProtectionWatcherReplayResult(
        signals_df=signals_df,
        lifecycle_frame=pd.DataFrame(),
        event_frame=pd.DataFrame(),
        diagnostics={"bridge": "execution_engine.protection_watcher+watcher_replay"},
        order_lifecycle_frame=pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-01"]),
                "execution_date": pd.to_datetime(["2025-01-02", "2025-01-02", "2025-01-02"]),
                "symbol": ["AAPL", "AAPL", "AAPL"],
                "order_group_id": ["entry_002", "entry_002", "entry_002"],
                "oco_group_id": ["oco_entry_002", "oco_entry_002", "oco_entry_002"],
                "intent_id": ["tp_002", "stop_002", "trail_002"],
                "parent_intent_id": ["entry_002", "entry_002", "entry_002"],
                "intent_role": ["take_profit", "initial_stop", "trailing_stop"],
                "order_status": ["SUBMITTED", "SUBMITTED", "HELD"],
                "broker_state": ["working", "working", "held"],
            }
        ),
        broker_event_frame=pd.DataFrame(),
    )
    high_df = pd.DataFrame({"AAPL": [101.0, 102.0, 103.0]}, index=trading_index)
    low_df = pd.DataFrame({"AAPL": [99.0, 98.0, 97.0]}, index=trading_index)

    result = build_phase7_exit_lifecycle_replay(
        watcher_result,
        high_df=high_df,
        low_df=low_df,
    )

    assert result.exit_frame.empty
    assert result.diagnostics["stale_orders"] == 3
    assert set(result.order_lifecycle_frame["order_status"]) == {OrderStatus.EXPIRED}
    assert set(result.order_lifecycle_frame["broker_state"]) == {"stale"}


def test_build_phase7_exit_lifecycle_replay_respects_swing_only_no_same_day_exit() -> None:
    from backtesting.exit_lifecycle_replay import build_phase7_exit_lifecycle_replay
    from backtesting.protection_watcher_replay import ProtectionWatcherReplayResult

    trading_index = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    signals_df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "execution_date": pd.to_datetime(["2025-01-02"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "fill_price": [100.0],
            "replay_take_profit_price": [130.0],
            "replay_initial_stop_price": [99.0],
            "replay_trailing_stop_pct": [0.05],
            "replay_take_profit_intent_id": ["tp_003"],
            "replay_initial_stop_intent_id": ["stop_003"],
            "replay_trailing_stop_intent_id": ["trail_003"],
        }
    )
    watcher_result = ProtectionWatcherReplayResult(
        signals_df=signals_df,
        lifecycle_frame=pd.DataFrame(),
        event_frame=pd.DataFrame(),
        diagnostics={"bridge": "execution_engine.protection_watcher+watcher_replay"},
        order_lifecycle_frame=pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-01"]),
                "execution_date": pd.to_datetime(["2025-01-02", "2025-01-02", "2025-01-02"]),
                "symbol": ["AAPL", "AAPL", "AAPL"],
                "order_group_id": ["entry_003", "entry_003", "entry_003"],
                "oco_group_id": ["oco_entry_003", "oco_entry_003", "oco_entry_003"],
                "intent_id": ["tp_003", "stop_003", "trail_003"],
                "parent_intent_id": ["entry_003", "entry_003", "entry_003"],
                "intent_role": ["take_profit", "initial_stop", "trailing_stop"],
                "order_status": ["SUBMITTED", "SUBMITTED", "HELD"],
                "broker_state": ["working", "working", "held"],
            }
        ),
        broker_event_frame=pd.DataFrame(),
    )
    high_df = pd.DataFrame({"AAPL": [101.0, 102.0, 103.0]}, index=trading_index)
    low_df = pd.DataFrame({"AAPL": [98.0, 100.0, 101.0]}, index=trading_index)

    result = build_phase7_exit_lifecycle_replay(
        watcher_result,
        high_df=high_df,
        low_df=low_df,
        swing_only=True,
    )

    assert result.exit_frame.empty
    assert result.diagnostics["swing_only_applied"] is True


def test_save_phase7_exit_lifecycle_replay_artifacts_writes_expected_files(tmp_path) -> None:
    from backtesting.exit_lifecycle_replay import ExitLifecycleReplayResult, save_phase7_exit_lifecycle_replay_artifacts

    result = ExitLifecycleReplayResult(
        signals_df=pd.DataFrame({"symbol": ["AAPL"], "replay_exit_reason": ["take_profit"]}),
        exit_frame=pd.DataFrame({"symbol": ["AAPL"], "replay_exit_reason": ["take_profit"]}),
        event_frame=pd.DataFrame({"symbol": ["AAPL"], "event_type": ["EXIT_FILLED_TAKE_PROFIT"]}),
        diagnostics={"exit_rows": 1, "events_generated": 1, "bridge": "execution_engine.oco_manager+exit_lifecycle_replay"},
        order_lifecycle_frame=pd.DataFrame({"symbol": ["AAPL"], "order_status": ["FILLED"]}),
        broker_event_frame=pd.DataFrame({"symbol": ["AAPL"], "event_type": ["ORDER_FILLED"]}),
    )

    artifact_paths = save_phase7_exit_lifecycle_replay_artifacts(result, tmp_path)

    assert set(artifact_paths) == {
        "phase7_exit_lifecycle_replay_csv",
        "phase7_exit_lifecycle_replay_events_csv",
        "phase7_exit_lifecycle_replay_signals_csv",
        "phase7_exit_lifecycle_replay_summary_json",
        "execution_broker_like_order_lifecycle_csv",
        "execution_broker_like_events_csv",
        "execution_broker_like_summary_json",
    }
    for path in artifact_paths.values():
        assert pd.notna(path)
        assert Path(path).exists()




