from __future__ import annotations

import json
from datetime import date
from typing import Any, cast

import pandas as pd

from backtesting.screener_diagnostics import (
    ScreenerDiagnosticsScenario,
    ScreenerDiagnosticsService,
    build_cross_regime_recommendations,
    build_screener_oat_scenarios,
    classify_market_regimes,
    export_screener_objective_recommendations,
    export_screener_recommendations,
    export_screener_regime_recommendations,
    recommend_screener_scenarios_by_objective,
    recommend_screener_scenarios,
    recommend_screener_scenarios_by_regime,
    summarize_screener_diagnostics_by_regime,
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


def test_screener_diagnostics_service_defaults_to_strict_swing_cash_baseline() -> None:
    service = ScreenerDiagnosticsService(engine=object())

    assert service.base_screener_config == ScreenerConfig.strict_swing_cash()


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
                "selection_rank": [1, 2, None],
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
    monkeypatch.setattr(service, "_build_market_regime_frame", lambda trading_dates: pd.DataFrame())
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


def test_recommend_screener_scenarios_ranks_best_compromise() -> None:
    summary = pd.DataFrame(
        [
            {
                "scenario_name": "baseline",
                "is_baseline": 1,
                "days_evaluated": 10,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.22,
                "selector_to_portfolio_survival_ratio_mean": 0.45,
                "portfolio_target_count_mean": 4.0,
                "portfolio_excess_return_20d_mean": 0.040,
                "selector_excess_return_20d_mean": 0.030,
                "portfolio_positive_share_20d_mean": 0.56,
                "portfolio_coverage_20d_mean": 4.0,
                "delta_portfolio_excess_return_20d_mean": 0.0,
            },
            {
                "scenario_name": "rs_102",
                "is_baseline": 0,
                "days_evaluated": 10,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.30,
                "selector_to_portfolio_survival_ratio_mean": 0.58,
                "portfolio_target_count_mean": 5.0,
                "portfolio_excess_return_20d_mean": 0.055,
                "selector_excess_return_20d_mean": 0.042,
                "portfolio_positive_share_20d_mean": 0.65,
                "portfolio_coverage_20d_mean": 5.0,
                "delta_portfolio_excess_return_20d_mean": 0.015,
            },
            {
                "scenario_name": "liq_20m",
                "is_baseline": 0,
                "days_evaluated": 10,
                "days_failed": 1,
                "portfolio_survival_ratio_mean": 0.16,
                "selector_to_portfolio_survival_ratio_mean": 0.39,
                "portfolio_target_count_mean": 2.0,
                "portfolio_excess_return_20d_mean": 0.070,
                "selector_excess_return_20d_mean": 0.050,
                "portfolio_positive_share_20d_mean": 0.60,
                "portfolio_coverage_20d_mean": 2.0,
                "delta_portfolio_excess_return_20d_mean": 0.030,
            },
        ]
    )
    daily = pd.DataFrame(
        [
            {"scenario_name": "baseline", "portfolio_survival_ratio": 0.20, "portfolio_excess_return_20d": 0.03},
            {"scenario_name": "baseline", "portfolio_survival_ratio": 0.24, "portfolio_excess_return_20d": 0.05},
            {"scenario_name": "rs_102", "portfolio_survival_ratio": 0.29, "portfolio_excess_return_20d": 0.05},
            {"scenario_name": "rs_102", "portfolio_survival_ratio": 0.31, "portfolio_excess_return_20d": 0.06},
            {"scenario_name": "liq_20m", "portfolio_survival_ratio": 0.10, "portfolio_excess_return_20d": -0.01},
            {"scenario_name": "liq_20m", "portfolio_survival_ratio": 0.22, "portfolio_excess_return_20d": 0.15},
        ]
    )

    recommendations, recommendation_summary = recommend_screener_scenarios(
        summary,
        daily_metrics=daily,
        baseline_name="baseline",
    )

    assert recommendations.iloc[0]["scenario_name"] == "rs_102"
    assert recommendations.iloc[0]["recommendation_label"] == "best_compromise"
    assert recommendation_summary["recommended_scenario"]["scenario_name"] == "rs_102"
    assert recommendation_summary["category_leaders"]["best_forward_quality"] == "liq_20m"
    assert recommendations["overall_score"].is_monotonic_decreasing


def test_recommend_screener_scenarios_handles_missing_columns() -> None:
    summary = pd.DataFrame(
        [
            {
                "scenario_name": "baseline",
                "is_baseline": 1,
                "days_evaluated": 5,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.25,
            }
        ]
    )

    recommendations, recommendation_summary = recommend_screener_scenarios(summary, baseline_name="baseline")

    assert len(recommendations) == 1
    assert recommendations.iloc[0]["rank"] == 1
    assert recommendations.iloc[0]["scenario_name"] == "baseline"
    assert pd.notna(recommendations.iloc[0]["overall_score"])
    assert "portfolio_forward_quality" in recommendation_summary["missing_metrics"]


def test_export_screener_recommendations_writes_files(tmp_path) -> None:
    recommendations = pd.DataFrame(
        [
            {
                "rank": 1,
                "scenario_name": "rs_102",
                "overall_score": 0.82,
                "robustness_score": 0.80,
                "survival_score": 0.79,
                "forward_quality_score": 0.86,
                "recommendation_label": "best_compromise",
            }
        ]
    )
    recommendation_summary = {
        "status": "ok",
        "recommended_scenario": {
            "scenario_name": "rs_102",
            "overall_score": 0.82,
        },
    }

    artifacts = export_screener_recommendations(recommendations, recommendation_summary, tmp_path)

    assert artifacts["scenario_recommendations"].exists()
    assert artifacts["recommendation_summary"].exists()
    payload = json.loads(artifacts["recommendation_summary"].read_text(encoding="utf-8"))
    assert payload["recommended_scenario"]["scenario_name"] == "rs_102"


def test_classify_market_regimes_identifies_bull_bear_range_and_vol() -> None:
    history = pd.DataFrame(
        {
            "symbol": ["SPY"] * 16,
            "bar_date": pd.date_range("2026-01-01", periods=16, freq="D"),
            "close_price": [100, 101, 102, 103, 104, 106, 106, 107, 106, 106, 100, 96, 92, 110, 80, 120],
        }
    )

    regimes = classify_market_regimes(
        history,
        benchmark_symbol="SPY",
        trend_lookback_days=3,
        long_ma_window=5,
        vol_window=3,
        vol_lookback_window=5,
        bull_bear_return_threshold=0.02,
        volatility_multiplier=1.1,
    )

    labels = dict(zip(regimes["trade_date"], regimes["market_regime"]))
    assert labels[pd.Timestamp("2026-01-06").date()] == "bull"
    assert labels[pd.Timestamp("2026-01-10").date()] == "range"
    assert labels[pd.Timestamp("2026-01-13").date()] == "bear"
    assert labels[pd.Timestamp("2026-01-16").date()] == "vol"


def test_recommend_screener_scenarios_by_regime_prefers_balanced_cross_regime_scenario() -> None:
    summary_by_regime = pd.DataFrame(
        [
            {
                "market_regime": "bull",
                "scenario_name": "baseline",
                "is_baseline": 1,
                "days_evaluated": 6,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.25,
                "selector_to_portfolio_survival_ratio_mean": 0.45,
                "portfolio_target_count_mean": 4.0,
                "portfolio_excess_return_20d_mean": 0.03,
                "selector_excess_return_20d_mean": 0.02,
                "portfolio_positive_share_20d_mean": 0.58,
                "portfolio_coverage_20d_mean": 4.0,
            },
            {
                "market_regime": "bull",
                "scenario_name": "balanced",
                "is_baseline": 0,
                "days_evaluated": 6,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.30,
                "selector_to_portfolio_survival_ratio_mean": 0.55,
                "portfolio_target_count_mean": 5.0,
                "portfolio_excess_return_20d_mean": 0.05,
                "selector_excess_return_20d_mean": 0.04,
                "portfolio_positive_share_20d_mean": 0.68,
                "portfolio_coverage_20d_mean": 5.0,
            },
            {
                "market_regime": "bull",
                "scenario_name": "opportunistic",
                "is_baseline": 0,
                "days_evaluated": 6,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.32,
                "selector_to_portfolio_survival_ratio_mean": 0.57,
                "portfolio_target_count_mean": 5.0,
                "portfolio_excess_return_20d_mean": 0.08,
                "selector_excess_return_20d_mean": 0.06,
                "portfolio_positive_share_20d_mean": 0.72,
                "portfolio_coverage_20d_mean": 5.0,
            },
            {
                "market_regime": "bear",
                "scenario_name": "baseline",
                "is_baseline": 1,
                "days_evaluated": 5,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.20,
                "selector_to_portfolio_survival_ratio_mean": 0.40,
                "portfolio_target_count_mean": 3.0,
                "portfolio_excess_return_20d_mean": 0.01,
                "selector_excess_return_20d_mean": 0.00,
                "portfolio_positive_share_20d_mean": 0.52,
                "portfolio_coverage_20d_mean": 3.0,
            },
            {
                "market_regime": "bear",
                "scenario_name": "balanced",
                "is_baseline": 0,
                "days_evaluated": 5,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.28,
                "selector_to_portfolio_survival_ratio_mean": 0.50,
                "portfolio_target_count_mean": 4.0,
                "portfolio_excess_return_20d_mean": 0.035,
                "selector_excess_return_20d_mean": 0.025,
                "portfolio_positive_share_20d_mean": 0.64,
                "portfolio_coverage_20d_mean": 4.0,
            },
            {
                "market_regime": "bear",
                "scenario_name": "opportunistic",
                "is_baseline": 0,
                "days_evaluated": 5,
                "days_failed": 1,
                "portfolio_survival_ratio_mean": 0.08,
                "selector_to_portfolio_survival_ratio_mean": 0.18,
                "portfolio_target_count_mean": 1.0,
                "portfolio_excess_return_20d_mean": -0.03,
                "selector_excess_return_20d_mean": -0.02,
                "portfolio_positive_share_20d_mean": 0.30,
                "portfolio_coverage_20d_mean": 1.0,
            },
        ]
    )

    regime_recommendations, regime_summary, cross_regime_recommendations, cross_regime_summary = recommend_screener_scenarios_by_regime(
        summary_by_regime,
        baseline_name="baseline",
    )

    assert not regime_recommendations.empty
    assert regime_summary["status"] == "ok"
    assert cross_regime_summary["recommended_scenario"]["scenario_name"] == "balanced"
    assert cross_regime_recommendations.iloc[0]["scenario_name"] == "balanced"
    assert cross_regime_recommendations.iloc[0]["recommendation_label"] == "best_cross_regime_compromise"


def test_build_cross_regime_recommendations_prefers_high_worst_case() -> None:
    regime_recommendations = pd.DataFrame(
        [
            {"market_regime": "bull", "scenario_name": "A", "overall_score": 0.90, "confidence_score": 0.90, "robustness_score": 0.85, "survival_score": 0.88, "forward_quality_score": 0.92},
            {"market_regime": "bear", "scenario_name": "A", "overall_score": 0.35, "confidence_score": 0.85, "robustness_score": 0.40, "survival_score": 0.38, "forward_quality_score": 0.30},
            {"market_regime": "bull", "scenario_name": "B", "overall_score": 0.72, "confidence_score": 0.88, "robustness_score": 0.70, "survival_score": 0.72, "forward_quality_score": 0.74},
            {"market_regime": "bear", "scenario_name": "B", "overall_score": 0.70, "confidence_score": 0.87, "robustness_score": 0.69, "survival_score": 0.71, "forward_quality_score": 0.69},
        ]
    )

    cross_regime_recommendations, cross_regime_summary = build_cross_regime_recommendations(regime_recommendations)

    assert cross_regime_recommendations.iloc[0]["scenario_name"] == "B"
    assert cross_regime_summary["recommended_scenario"]["scenario_name"] == "B"


def test_summarize_screener_diagnostics_by_regime_splits_rows() -> None:
    daily = pd.DataFrame(
        [
            {
                "trade_date": date(2026, 4, 1),
                "market_regime": "bull",
                "scenario_name": "baseline",
                "is_baseline": 1,
                "liquidity_threshold_usd": 10_000_000.0,
                "historical_range_lookback_days": 504,
                "min_relative_strength_index": 100.0,
                "min_historical_range_score": 70.0,
                "status": "ok",
                "portfolio_survival_ratio": 0.20,
            },
            {
                "trade_date": date(2026, 4, 2),
                "market_regime": "bear",
                "scenario_name": "baseline",
                "is_baseline": 1,
                "liquidity_threshold_usd": 10_000_000.0,
                "historical_range_lookback_days": 504,
                "min_relative_strength_index": 100.0,
                "min_historical_range_score": 70.0,
                "status": "ok",
                "portfolio_survival_ratio": 0.10,
            },
        ]
    )

    summary_by_regime = summarize_screener_diagnostics_by_regime(daily, baseline_name="baseline")

    assert set(summary_by_regime["market_regime"]) == {"bull", "bear"}
    assert len(summary_by_regime) == 2


def test_export_screener_regime_recommendations_writes_files(tmp_path) -> None:
    regime_recommendations = pd.DataFrame(
        [{"market_regime": "bull", "rank": 1, "scenario_name": "balanced", "overall_score": 0.81}]
    )
    regime_summary = {"status": "ok", "per_regime": {"bull": {"recommended_scenario": {"scenario_name": "balanced"}}}}
    cross_regime_recommendations = pd.DataFrame(
        [{"cross_regime_rank": 1, "scenario_name": "balanced", "cross_regime_overall_score": 0.79}]
    )
    cross_regime_summary = {"status": "ok", "recommended_scenario": {"scenario_name": "balanced"}}

    artifacts = export_screener_regime_recommendations(
        regime_recommendations,
        regime_summary,
        cross_regime_recommendations,
        cross_regime_summary,
        tmp_path,
    )

    assert artifacts["scenario_recommendations_by_regime"].exists()
    assert artifacts["cross_regime_recommendations"].exists()
    payload = json.loads(artifacts["cross_regime_recommendation_summary"].read_text(encoding="utf-8"))
    assert payload["recommended_scenario"]["scenario_name"] == "balanced"


def test_recommend_screener_scenarios_by_objective_adapts_to_operational_goal() -> None:
    summary = pd.DataFrame(
        [
            {
                "scenario_name": "robusto",
                "is_baseline": 1,
                "days_evaluated": 12,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.26,
                "selector_to_portfolio_survival_ratio_mean": 0.55,
                "portfolio_target_count_mean": 4.0,
                "portfolio_excess_return_20d_mean": 0.050,
                "selector_excess_return_20d_mean": 0.038,
                "portfolio_positive_share_20d_mean": 0.61,
                "portfolio_coverage_20d_mean": 4.0,
                "delta_portfolio_excess_return_20d_mean": 0.00,
            },
            {
                "scenario_name": "offensive",
                "is_baseline": 0,
                "days_evaluated": 12,
                "days_failed": 1,
                "portfolio_survival_ratio_mean": 0.15,
                "selector_to_portfolio_survival_ratio_mean": 0.34,
                "portfolio_target_count_mean": 2.0,
                "portfolio_excess_return_20d_mean": 0.135,
                "selector_excess_return_20d_mean": 0.110,
                "portfolio_positive_share_20d_mean": 0.66,
                "portfolio_coverage_20d_mean": 2.0,
                "delta_portfolio_excess_return_20d_mean": 0.085,
            },
            {
                "scenario_name": "bear_shield",
                "is_baseline": 0,
                "days_evaluated": 12,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.24,
                "selector_to_portfolio_survival_ratio_mean": 0.57,
                "portfolio_target_count_mean": 4.0,
                "portfolio_excess_return_20d_mean": 0.030,
                "selector_excess_return_20d_mean": 0.020,
                "portfolio_positive_share_20d_mean": 0.58,
                "portfolio_coverage_20d_mean": 4.0,
                "delta_portfolio_excess_return_20d_mean": -0.020,
            },
            {
                "scenario_name": "executable",
                "is_baseline": 0,
                "days_evaluated": 12,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.36,
                "selector_to_portfolio_survival_ratio_mean": 0.78,
                "portfolio_target_count_mean": 7.0,
                "portfolio_excess_return_20d_mean": 0.060,
                "selector_excess_return_20d_mean": 0.045,
                "portfolio_positive_share_20d_mean": 0.64,
                "portfolio_coverage_20d_mean": 7.0,
                "delta_portfolio_excess_return_20d_mean": 0.010,
            },
        ]
    )
    summary_by_regime = pd.DataFrame(
        [
            {
                "market_regime": "bull",
                "scenario_name": "robusto",
                "is_baseline": 1,
                "days_evaluated": 6,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.27,
                "selector_to_portfolio_survival_ratio_mean": 0.56,
                "portfolio_target_count_mean": 4.0,
                "portfolio_excess_return_20d_mean": 0.060,
                "selector_excess_return_20d_mean": 0.045,
                "portfolio_positive_share_20d_mean": 0.63,
                "portfolio_coverage_20d_mean": 4.0,
            },
            {
                "market_regime": "bull",
                "scenario_name": "offensive",
                "is_baseline": 0,
                "days_evaluated": 6,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.18,
                "selector_to_portfolio_survival_ratio_mean": 0.38,
                "portfolio_target_count_mean": 2.0,
                "portfolio_excess_return_20d_mean": 0.160,
                "selector_excess_return_20d_mean": 0.130,
                "portfolio_positive_share_20d_mean": 0.74,
                "portfolio_coverage_20d_mean": 2.0,
            },
            {
                "market_regime": "bull",
                "scenario_name": "bear_shield",
                "is_baseline": 0,
                "days_evaluated": 6,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.22,
                "selector_to_portfolio_survival_ratio_mean": 0.50,
                "portfolio_target_count_mean": 3.0,
                "portfolio_excess_return_20d_mean": 0.025,
                "selector_excess_return_20d_mean": 0.015,
                "portfolio_positive_share_20d_mean": 0.55,
                "portfolio_coverage_20d_mean": 3.0,
            },
            {
                "market_regime": "bull",
                "scenario_name": "executable",
                "is_baseline": 0,
                "days_evaluated": 6,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.32,
                "selector_to_portfolio_survival_ratio_mean": 0.72,
                "portfolio_target_count_mean": 6.0,
                "portfolio_excess_return_20d_mean": 0.065,
                "selector_excess_return_20d_mean": 0.048,
                "portfolio_positive_share_20d_mean": 0.64,
                "portfolio_coverage_20d_mean": 6.0,
            },
            {
                "market_regime": "bear",
                "scenario_name": "robusto",
                "is_baseline": 1,
                "days_evaluated": 6,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.29,
                "selector_to_portfolio_survival_ratio_mean": 0.60,
                "portfolio_target_count_mean": 5.0,
                "portfolio_excess_return_20d_mean": 0.045,
                "selector_excess_return_20d_mean": 0.036,
                "portfolio_positive_share_20d_mean": 0.64,
                "portfolio_coverage_20d_mean": 4.0,
            },
            {
                "market_regime": "bear",
                "scenario_name": "offensive",
                "is_baseline": 0,
                "days_evaluated": 6,
                "days_failed": 2,
                "portfolio_survival_ratio_mean": 0.08,
                "selector_to_portfolio_survival_ratio_mean": 0.14,
                "portfolio_target_count_mean": 1.0,
                "portfolio_excess_return_20d_mean": -0.060,
                "selector_excess_return_20d_mean": -0.040,
                "portfolio_positive_share_20d_mean": 0.25,
                "portfolio_coverage_20d_mean": 1.0,
            },
            {
                "market_regime": "bear",
                "scenario_name": "bear_shield",
                "is_baseline": 0,
                "days_evaluated": 6,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.31,
                "selector_to_portfolio_survival_ratio_mean": 0.63,
                "portfolio_target_count_mean": 5.0,
                "portfolio_excess_return_20d_mean": 0.050,
                "selector_excess_return_20d_mean": 0.040,
                "portfolio_positive_share_20d_mean": 0.67,
                "portfolio_coverage_20d_mean": 5.0,
            },
            {
                "market_regime": "bear",
                "scenario_name": "executable",
                "is_baseline": 0,
                "days_evaluated": 6,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.16,
                "selector_to_portfolio_survival_ratio_mean": 0.36,
                "portfolio_target_count_mean": 2.0,
                "portfolio_excess_return_20d_mean": -0.010,
                "selector_excess_return_20d_mean": -0.005,
                "portfolio_positive_share_20d_mean": 0.45,
                "portfolio_coverage_20d_mean": 2.0,
            },
        ]
    )

    recommendations, objective_summary = recommend_screener_scenarios_by_objective(
        summary,
        summary_metrics_by_regime=summary_by_regime,
        baseline_name="robusto",
    )

    assert not recommendations.empty
    assert objective_summary["status"] == "ok"
    assert objective_summary["cross_regime_analysis_available"] is True
    assert objective_summary["bear_market_data_available"] is True
    assert objective_summary["objectives"]["robust"]["recommended_scenario"]["scenario_name"] == "executable"
    assert objective_summary["objectives"]["robust"]["scope"] == "cross_regime"
    assert objective_summary["objectives"]["offensive"]["recommended_scenario"]["scenario_name"] == "offensive"
    assert objective_summary["objectives"]["bear_defensive"]["recommended_scenario"]["scenario_name"] == "bear_shield"
    assert objective_summary["objectives"]["executable_compromise"]["recommended_scenario"]["scenario_name"] == "executable"
    assert set(recommendations["objective"].unique()) == {"robust", "offensive", "bear_defensive", "executable_compromise"}


def test_recommend_screener_scenarios_by_objective_falls_back_without_bear_regime() -> None:
    summary = pd.DataFrame(
        [
            {
                "scenario_name": "baseline",
                "is_baseline": 1,
                "days_evaluated": 5,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.20,
                "selector_to_portfolio_survival_ratio_mean": 0.40,
                "portfolio_target_count_mean": 3.0,
                "portfolio_excess_return_20d_mean": 0.03,
                "portfolio_positive_share_20d_mean": 0.55,
                "portfolio_coverage_20d_mean": 3.0,
            },
            {
                "scenario_name": "safer",
                "is_baseline": 0,
                "days_evaluated": 5,
                "days_failed": 0,
                "portfolio_survival_ratio_mean": 0.28,
                "selector_to_portfolio_survival_ratio_mean": 0.60,
                "portfolio_target_count_mean": 4.0,
                "portfolio_excess_return_20d_mean": 0.025,
                "portfolio_positive_share_20d_mean": 0.58,
                "portfolio_coverage_20d_mean": 4.0,
            },
        ]
    )

    recommendations, objective_summary = recommend_screener_scenarios_by_objective(summary, baseline_name="baseline")

    assert not recommendations.empty
    assert objective_summary["bear_market_data_available"] is False
    assert objective_summary["objectives"]["bear_defensive"]["scope"] == "global_fallback"


def test_export_screener_objective_recommendations_writes_files(tmp_path) -> None:
    objective_recommendations = pd.DataFrame(
        [
            {
                "objective": "robust",
                "rank": 1,
                "scenario_name": "robusto",
                "objective_score": 0.81,
                "objective_recommendation_label": "best_robust_objective",
            }
        ]
    )
    objective_summary = {
        "status": "ok",
        "objectives": {
            "robust": {
                "recommended_scenario": {
                    "scenario_name": "robusto",
                    "objective_score": 0.81,
                }
            }
        },
    }

    artifacts = export_screener_objective_recommendations(objective_recommendations, objective_summary, tmp_path)

    assert artifacts["scenario_recommendations_by_objective"].exists()
    assert artifacts["recommendation_summary_by_objective"].exists()
    payload = json.loads(artifacts["recommendation_summary_by_objective"].read_text(encoding="utf-8"))
    assert payload["objectives"]["robust"]["recommended_scenario"]["scenario_name"] == "robusto"


def test_analyze_period_merges_market_regime_and_builds_summary_by_regime(monkeypatch) -> None:
    service = ScreenerDiagnosticsService(engine=object())
    scenario = ScreenerDiagnosticsScenario("baseline", ScreenerConfig(), is_baseline=True)
    as_of_date = date(2026, 4, 1)

    screener_df = pd.DataFrame({"symbol": ["AAA"], "total_score": [90.0], "relative_strength_index": [110.0], "historical_range_score": [80.0]})
    selector_df = pd.DataFrame({"symbol": ["AAA"]})
    history_df = pd.DataFrame(
        {"symbol": ["AAA"], "sector": ["Tech"], "is_candidate": [1], "final_score": [0.8], "final_score_sentiment": [0.82], "total_score": [90.0]}
    )

    monkeypatch.setattr(service, "list_trading_dates", lambda start_date, end_date: [as_of_date])
    monkeypatch.setattr(service, "_build_market_regime_frame", lambda trading_dates: pd.DataFrame([{"trade_date": as_of_date, "market_regime": "bull", "benchmark_symbol": "SPY", "benchmark_close": 500.0}]))
    monkeypatch.setattr(service, "_make_snapshot_service", lambda screener_config: object())
    monkeypatch.setattr(service, "_build_pit_frames", lambda snapshot_service, current_date: (screener_df, selector_df, history_df))
    monkeypatch.setattr(service, "_build_portfolio_entries", lambda selector_candidates, current_date: [])
    monkeypatch.setattr(service, "_compute_benchmark_forward_returns", lambda current_date: {"benchmark_forward_return_5d": 0.0, "benchmark_forward_return_10d": 0.0, "benchmark_forward_return_20d": 0.0})
    monkeypatch.setattr(service, "_compute_symbol_set_forward_metrics", lambda symbols, *, weights, as_of_date, benchmark_returns, prefix: {})

    result = service.analyze_period(start_date=as_of_date, end_date=as_of_date, scenarios=[scenario])

    assert result.daily_metrics.iloc[0]["market_regime"] == "bull"
    assert not result.summary_metrics_by_regime.empty
    assert result.summary_metrics_by_regime.iloc[0]["market_regime"] == "bull"


def test_load_price_history_filters_stock_bars_daily_on_eodhd_source(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    service = ScreenerDiagnosticsService.__new__(ScreenerDiagnosticsService)
    service.engine = _FakeEngine()
    service._stock_bars_layout = ("date", "COALESCE(adj_close, `close`)")

    # Phase G.2 : `screener_diagnostics` est devenu un package ; le binding
    # effectif de `get_required_bars_source_filter` réside dans `_impl`.
    monkeypatch.setattr(
        "backtesting.screener_diagnostics._impl.get_required_bars_source_filter",
        lambda engine, table_name="stock_bars_daily", table_alias=None: (
            "AND `data_source` = :required_data_source",
            {"required_data_source": "eodhd_eod"},
        ),
    )

    def _fake_read_sql_query(stmt, conn, params=None):
        captured["sql"] = str(stmt)
        captured["params"] = params
        return pd.DataFrame(columns=["symbol", "bar_date", "close_price", "high_price", "low_price", "volume"])

    monkeypatch.setattr(pd, "read_sql_query", _fake_read_sql_query)

    result = service._load_price_history(["AAPL"], start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))

    assert result.empty
    assert "required_data_source" in captured["sql"]
    params = cast(dict[str, Any], captured["params"])
    assert params["required_data_source"] == "eodhd_eod"


