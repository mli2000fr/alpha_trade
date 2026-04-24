from __future__ import annotations

from datetime import date

import pandas as pd

from backtesting.screener_diagnostics import (
    ScreenerDiagnosticsScenario,
    ScreenerDiagnosticsService,
    build_screener_oat_scenarios,
    summarize_screener_diagnostics,
)
from risk_management.models import PortfolioEntry
from screener.models import ScreenerConfig


def test_build_screener_oat_scenarios_includes_baseline_and_unique_variants() -> None:
    base = ScreenerConfig()

    scenarios = build_screener_oat_scenarios(
        base,
        rs_values=[100.0, 102.0, 102.0],
        range_lookback_values=[504, 252],
        historical_range_score_values=[70.0, 65.0],
        liquidity_threshold_values=[10_000_000.0, 5_000_000.0],
    )

    assert [scenario.name for scenario in scenarios] == [
        "baseline",
        "rs_102",
        "range_252d",
        "hist_score_65",
        "liq_5m",
    ]
    assert scenarios[0].is_baseline is True
    assert scenarios[1].screener_config.min_relative_strength_index == 102.0
    assert scenarios[2].screener_config.historical_range_lookback_days == 252
    assert scenarios[3].screener_config.min_historical_range_score == 65.0
    assert scenarios[4].screener_config.liquidity_threshold_usd == 5_000_000.0


def test_summarize_screener_diagnostics_adds_baseline_deltas() -> None:
    daily = pd.DataFrame(
        [
            {
                "trade_date": date(2026, 4, 1),
                "scenario_name": "baseline",
                "is_baseline": 1,
                "liquidity_threshold_usd": 10_000_000.0,
                "historical_range_lookback_days": 504,
                "min_relative_strength_index": 100.0,
                "min_historical_range_score": 70.0,
                "status": "ok",
                "portfolio_survival_ratio": 0.20,
                "portfolio_forward_return_20d": 0.05,
                "selector_candidate_count": 12,
            },
            {
                "trade_date": date(2026, 4, 2),
                "scenario_name": "baseline",
                "is_baseline": 1,
                "liquidity_threshold_usd": 10_000_000.0,
                "historical_range_lookback_days": 504,
                "min_relative_strength_index": 100.0,
                "min_historical_range_score": 70.0,
                "status": "ok",
                "portfolio_survival_ratio": 0.30,
                "portfolio_forward_return_20d": 0.01,
                "selector_candidate_count": 8,
            },
            {
                "trade_date": date(2026, 4, 1),
                "scenario_name": "rs_102",
                "is_baseline": 0,
                "liquidity_threshold_usd": 10_000_000.0,
                "historical_range_lookback_days": 504,
                "min_relative_strength_index": 102.0,
                "min_historical_range_score": 70.0,
                "status": "ok",
                "portfolio_survival_ratio": 0.35,
                "portfolio_forward_return_20d": 0.07,
                "selector_candidate_count": 10,
            },
            {
                "trade_date": date(2026, 4, 2),
                "scenario_name": "rs_102",
                "is_baseline": 0,
                "liquidity_threshold_usd": 10_000_000.0,
                "historical_range_lookback_days": 504,
                "min_relative_strength_index": 102.0,
                "min_historical_range_score": 70.0,
                "status": "error",
                "portfolio_survival_ratio": 0.25,
                "portfolio_forward_return_20d": 0.03,
                "selector_candidate_count": 6,
            },
        ]
    )

    summary = summarize_screener_diagnostics(daily, baseline_name="baseline")

    baseline_row = summary.loc[summary["scenario_name"] == "baseline"].iloc[0]
    variant_row = summary.loc[summary["scenario_name"] == "rs_102"].iloc[0]

    assert baseline_row["days_evaluated"] == 2
    assert baseline_row["days_failed"] == 0
    assert baseline_row["delta_portfolio_survival_ratio_mean"] == 0.0
    assert variant_row["days_failed"] == 1
    assert variant_row["portfolio_survival_ratio_mean"] == 0.30
    assert variant_row["delta_portfolio_survival_ratio_mean"] == 0.05
    assert variant_row["delta_portfolio_forward_return_20d_mean"] == 0.02


def test_analyze_period_computes_survival_and_forward_metrics(monkeypatch) -> None:
    service = ScreenerDiagnosticsService(engine=object())
    scenario = ScreenerDiagnosticsScenario("baseline", ScreenerConfig(), is_baseline=True)
    as_of_date = date(2026, 4, 1)

    screener_df = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC", "DDD"],
            "total_score": [95.0, 90.0, 85.0, 80.0],
            "relative_strength_index": [110.0, 108.0, 105.0, 103.0],
            "historical_range_score": [88.0, 84.0, 80.0, 76.0],
        }
    )
    selector_df = pd.DataFrame({"symbol": ["AAA", "BBB", "CCC"]})
    history_df = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC"],
            "sector": ["Tech", "Energy", "Health"],
            "is_candidate": [1, 1, 0],
            "final_score": [0.80, 0.70, 0.55],
            "final_score_sentiment": [0.82, 0.72, 0.55],
            "total_score": [95.0, 90.0, 80.0],
        }
    )
    entries = [
        PortfolioEntry(
            symbol="AAA",
            sector="Tech",
            entry_price=100.0,
            score_used=0.82,
            score_source="final_score_sentiment",
            atr_20=3.0,
            proposed_shares=10,
            approved_shares=10,
            target_notional=1_000.0,
            target_weight=0.60,
            decision="ACCEPTED",
            decision_reason="OK",
        ),
        PortfolioEntry(
            symbol="BBB",
            sector="Energy",
            entry_price=50.0,
            score_used=0.72,
            score_source="final_score_sentiment",
            atr_20=2.0,
            proposed_shares=8,
            approved_shares=0,
            target_notional=0.0,
            target_weight=0.0,
            decision="REJECTED",
            decision_reason="contrainte de risque",
        ),
    ]

    monkeypatch.setattr(service, "list_trading_dates", lambda start_date, end_date: [as_of_date])
    monkeypatch.setattr(service, "_make_snapshot_service", lambda screener_config: object())
    monkeypatch.setattr(service, "_build_pit_frames", lambda snapshot_service, current_date: (screener_df, selector_df, history_df))
    monkeypatch.setattr(service, "_build_portfolio_entries", lambda selector_candidates, current_date: entries)
    monkeypatch.setattr(
        service,
        "_compute_benchmark_forward_returns",
        lambda current_date: {
            "benchmark_forward_return_5d": 0.01,
            "benchmark_forward_return_10d": 0.02,
            "benchmark_forward_return_20d": 0.03,
        },
    )

    def _fake_forward_metrics(symbols, *, weights, as_of_date, benchmark_returns, prefix):
        if prefix == "selector":
            return {
                "selector_forward_return_5d": 0.04,
                "selector_excess_return_5d": 0.03,
                "selector_positive_share_5d": 1.0,
                "selector_coverage_5d": 2.0,
                "selector_forward_return_10d": 0.06,
                "selector_excess_return_10d": 0.04,
                "selector_positive_share_10d": 1.0,
                "selector_coverage_10d": 2.0,
                "selector_forward_return_20d": 0.08,
                "selector_excess_return_20d": 0.05,
                "selector_positive_share_20d": 1.0,
                "selector_coverage_20d": 2.0,
            }
        return {
            "portfolio_forward_return_5d": 0.05,
            "portfolio_excess_return_5d": 0.04,
            "portfolio_positive_share_5d": 1.0,
            "portfolio_coverage_5d": 1.0,
            "portfolio_forward_return_10d": 0.07,
            "portfolio_excess_return_10d": 0.05,
            "portfolio_positive_share_10d": 1.0,
            "portfolio_coverage_10d": 1.0,
            "portfolio_forward_return_20d": 0.09,
            "portfolio_excess_return_20d": 0.06,
            "portfolio_positive_share_20d": 1.0,
            "portfolio_coverage_20d": 1.0,
        }

    monkeypatch.setattr(service, "_compute_symbol_set_forward_metrics", _fake_forward_metrics)

    result = service.analyze_period(
        start_date=as_of_date,
        end_date=as_of_date,
        scenarios=[scenario],
    )

    daily_row = result.daily_metrics.iloc[0]
    summary_row = result.summary_metrics.iloc[0]

    assert daily_row["screener_count"] == 4
    assert daily_row["selector_filtered_count"] == 3
    assert daily_row["selector_candidate_count"] == 2
    assert daily_row["portfolio_target_count"] == 1
    assert daily_row["selector_survival_ratio"] == 0.5
    assert daily_row["portfolio_survival_ratio"] == 0.25
    assert daily_row["selector_to_portfolio_survival_ratio"] == 0.5
    assert daily_row["portfolio_forward_return_20d"] == 0.09
    assert summary_row["portfolio_target_count_mean"] == 1.0
    assert summary_row["portfolio_survival_ratio_mean"] == 0.25
    assert summary_row["delta_portfolio_survival_ratio_mean"] == 0.0

