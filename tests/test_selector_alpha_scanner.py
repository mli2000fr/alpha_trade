from __future__ import annotations

from typing import cast

import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from selector.alpha_scanner import AlphaScanner, AlphaScannerConfig, _build_arg_parser, _build_config_from_args


def _make_scanner(config: AlphaScannerConfig | None = None) -> AlphaScanner:
    return AlphaScanner(engine=cast(Engine, object()), config=config or AlphaScannerConfig())


def test_alpha_scanner_config_rejects_invalid_weight_sum() -> None:
    with pytest.raises(ValueError, match="somme des poids"):
        AlphaScannerConfig(weight_trend_vcp=0.6, weight_total_score=0.3, weight_rsi=0.3)


def test_alpha_scanner_config_rejects_invalid_max_volatility_ratio() -> None:
    with pytest.raises(ValueError, match="max_volatility_ratio"):
        AlphaScannerConfig(max_volatility_ratio=0.0)


def test_alpha_scanner_config_strict_swing_cash_uses_shared_profile() -> None:
    config = AlphaScannerConfig.strict_swing_cash(selection_size=42)

    assert config.min_close == pytest.approx(10.0)
    assert config.liquidity_threshold == pytest.approx(30_000_000.0)
    assert config.max_volatility_ratio == pytest.approx(0.9)
    assert config.min_relative_strength_index == pytest.approx(100.0)
    assert config.min_high_52w_proximity == pytest.approx(0.75)
    assert config.min_weekly_trend_score == pytest.approx(1.0)
    assert config.min_atr_pct_20 == pytest.approx(0.015)
    assert config.max_atr_pct_20 == pytest.approx(0.06)
    assert config.min_market_cap == pytest.approx(2_000_000_000.0)
    assert config.min_beta_126 == pytest.approx(1.0)
    assert config.max_spread_bps == pytest.approx(25.0)
    assert config.earnings_blackout_days == 3
    assert config.require_above_ma200 is True
    assert config.selection_size == 42


def test_cli_preset_strict_builds_shared_config() -> None:
    args = _build_arg_parser().parse_args(["--preset", "strict", "--selection-size", "12"])

    config = _build_config_from_args(args)

    assert config.selection_size == 12
    assert config.min_close == pytest.approx(10.0)
    assert config.liquidity_threshold == pytest.approx(30_000_000.0)
    assert config.max_volatility_ratio == pytest.approx(0.9)
    assert config.min_relative_strength_index == pytest.approx(100.0)
    assert config.require_above_ma200 is True


def test_cli_explicit_thresholds_override_strict_preset() -> None:
    args = _build_arg_parser().parse_args(
        [
            "--preset",
            "strict",
            "--min-close",
            "12",
            "--liquidity-threshold",
            "50000000",
            "--max-volatility-ratio",
            "0.8",
            "--min-relative-strength-index",
            "105",
            "--min-high-52w-proximity",
            "0.85",
            "--min-weekly-trend-score",
            "0.5",
            "--min-atr-pct-20",
            "0.02",
            "--max-atr-pct-20",
            "0.04",
            "--min-market-cap",
            "3000000000",
            "--min-beta-126",
            "1.2",
            "--max-spread-bps",
            "18",
            "--earnings-blackout-days",
            "5",
        ]
    )

    config = _build_config_from_args(args)

    assert config.min_close == pytest.approx(12.0)
    assert config.liquidity_threshold == pytest.approx(50_000_000.0)
    assert config.max_volatility_ratio == pytest.approx(0.8)
    assert config.min_relative_strength_index == pytest.approx(105.0)
    assert config.min_high_52w_proximity == pytest.approx(0.85)
    assert config.min_weekly_trend_score == pytest.approx(0.5)
    assert config.min_atr_pct_20 == pytest.approx(0.02)
    assert config.max_atr_pct_20 == pytest.approx(0.04)
    assert config.min_market_cap == pytest.approx(3_000_000_000.0)
    assert config.min_beta_126 == pytest.approx(1.2)
    assert config.max_spread_bps == pytest.approx(18.0)
    assert config.earnings_blackout_days == 5


def test_cli_without_preset_uses_strict_profile_implicitly() -> None:
    args = _build_arg_parser().parse_args([])

    config = _build_config_from_args(args)

    assert config.min_close == pytest.approx(10.0)
    assert config.liquidity_threshold == pytest.approx(30_000_000.0)
    assert config.max_volatility_ratio == pytest.approx(0.9)
    assert config.min_relative_strength_index == pytest.approx(100.0)
    assert config.min_atr_pct_20 == pytest.approx(0.015)
    assert config.min_market_cap == pytest.approx(2_000_000_000.0)
    assert config.min_beta_126 == pytest.approx(1.0)
    assert config.max_spread_bps == pytest.approx(25.0)
    assert config.earnings_blackout_days == 3
    assert config.require_above_ma200 is True


def test_merge_scores_combines_factor_and_aux_scores() -> None:
    scanner = _make_scanner()
    computed_df = pd.DataFrame(
        [{
            "symbol": "AAPL",
            "date": pd.Timestamp("2026-04-18"),
            "latest_close": 150.0,
            "avg_dollar_volume_20d": 30_000_000.0,
            "history_days": 300,
            "ma50": 140.0,
            "ma150": 130.0,
            "ma200": 120.0,
            "high_52w": 160.0,
            "low_52w": 80.0,
            "volatility_ratio": 0.5,
            "trend_score": 0.8,
            "vcp_score": 0.6,
        }]
    )
    scores_df = pd.DataFrame(
        [{
            "symbol": "AAPL",
            "liquidity_val": 30_000_000.0,
            "relative_strength_index": 60.0,
            "total_score": 80.0,
            "sector": "Tech",
            "anomaly_count": 0,
            "missing_days_count": 0,
        }]
    )

    result = scanner.merge_scores(computed_df, scores_df)

    row = result.to_dict(orient="records")[0]
    assert row["normalized_total_score"] == pytest.approx(0.5)
    assert row["normalized_rsi"] == pytest.approx(0.5)
    assert row["raw_final_score"] == pytest.approx(0.60)
    assert row["final_score"] == pytest.approx(0.60)


def test_apply_filters_removes_non_eligible_rows() -> None:
    scanner = _make_scanner(
        AlphaScannerConfig(
            liquidity_threshold=20_000_000.0,
            min_history_days=252,
            min_close=5.0,
            max_volatility_ratio=0.9,
        )
    )
    merged_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 150.0, "avg_dollar_volume_20d": 25_000_000.0,
                "volatility_ratio": 0.5, "liquidity_val": 25_000_000.0, "anomaly_count": 0, "missing_days_count": 0,
            },
            {
                "symbol": "ETF1", "asset_class": "etf", "tradable": True,
                "history_days": 300, "latest_close": 150.0, "avg_dollar_volume_20d": 25_000_000.0,
                "volatility_ratio": 0.4, "liquidity_val": 25_000_000.0, "anomaly_count": 0, "missing_days_count": 0,
            },
            {
                "symbol": "ILLQ", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 4.0, "avg_dollar_volume_20d": 1_000_000.0,
                "volatility_ratio": 1.2, "liquidity_val": 1_000_000.0, "anomaly_count": 99, "missing_days_count": 20,
            },
        ]
    )

    filtered = scanner.apply_filters(merged_df)

    rows = filtered.to_dict(orient="records")
    assert [row["symbol"] for row in rows] == ["AAPL"]


def test_apply_filters_rejects_high_or_missing_volatility_ratio_when_enabled() -> None:
    scanner = _make_scanner(AlphaScannerConfig(max_volatility_ratio=0.9))
    merged_df = pd.DataFrame(
        [
            {
                "symbol": "PASS", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 50.0, "avg_dollar_volume_20d": 30_000_000.0,
                "volatility_ratio": 0.7,
            },
            {
                "symbol": "SPIKE", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 50.0, "avg_dollar_volume_20d": 30_000_000.0,
                "volatility_ratio": 1.1,
            },
            {
                "symbol": "UNKNOWN", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 50.0, "avg_dollar_volume_20d": 30_000_000.0,
                "volatility_ratio": pd.NA,
            },
        ]
    )

    filtered = scanner.apply_filters(merged_df)

    assert list(filtered["symbol"]) == ["PASS"]


def test_apply_filters_supports_explicit_swing_criteria() -> None:
    scanner = _make_scanner(
        AlphaScannerConfig(
            max_volatility_ratio=0.9,
            min_relative_strength_index=100.0,
            min_high_52w_proximity=0.75,
            min_weekly_trend_score=1.0,
            min_atr_pct_20=0.015,
            max_atr_pct_20=0.05,
            min_market_cap=2_000_000_000.0,
            min_beta_126=1.0,
            max_spread_bps=25.0,
            earnings_blackout_days=3,
            require_above_ma200=True,
        )
    )
    merged_df = pd.DataFrame(
        [
            {
                "symbol": "PASS", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 105.0, "avg_dollar_volume_20d": 40_000_000.0,
                "volatility_ratio": 0.6, "liquidity_val": 40_000_000.0,
                "relative_strength_index": 110.0, "ma200": 95.0, "high_52w_proximity": 0.84,
                "weekly_trend_score": 1.0, "atr_pct_20": 0.03,
                "market_cap": 5_000_000_000.0, "beta_126": 1.25, "spread_bps": 12.0,
                "earnings_blackout": 0,
            },
            {
                "symbol": "LOWRS", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 105.0, "avg_dollar_volume_20d": 40_000_000.0,
                "volatility_ratio": 0.6, "liquidity_val": 40_000_000.0,
                "relative_strength_index": 95.0, "ma200": 95.0, "high_52w_proximity": 0.84,
                "weekly_trend_score": 1.0, "atr_pct_20": 0.03,
                "market_cap": 5_000_000_000.0, "beta_126": 1.25, "spread_bps": 12.0,
                "earnings_blackout": 0,
            },
            {
                "symbol": "FLAT", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 105.0, "avg_dollar_volume_20d": 40_000_000.0,
                "volatility_ratio": 0.6, "liquidity_val": 40_000_000.0,
                "relative_strength_index": 110.0, "ma200": 95.0, "high_52w_proximity": 0.84,
                "weekly_trend_score": 1.0, "atr_pct_20": 0.005,
                "market_cap": 5_000_000_000.0, "beta_126": 1.25, "spread_bps": 12.0,
                "earnings_blackout": 0,
            },
            {
                "symbol": "BELOW200", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 90.0, "avg_dollar_volume_20d": 40_000_000.0,
                "volatility_ratio": 0.6, "liquidity_val": 40_000_000.0,
                "relative_strength_index": 110.0, "ma200": 95.0, "high_52w_proximity": 0.84,
                "weekly_trend_score": 1.0, "atr_pct_20": 0.03,
                "market_cap": 5_000_000_000.0, "beta_126": 1.25, "spread_bps": 12.0,
                "earnings_blackout": 0,
            },
            {
                "symbol": "FARHIGH", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 70.0, "avg_dollar_volume_20d": 40_000_000.0,
                "volatility_ratio": 0.6, "liquidity_val": 40_000_000.0,
                "relative_strength_index": 110.0, "ma200": 60.0, "high_52w_proximity": 0.60,
                "weekly_trend_score": 1.0, "atr_pct_20": 0.03,
                "market_cap": 5_000_000_000.0, "beta_126": 1.25, "spread_bps": 12.0,
                "earnings_blackout": 0,
            },
            {
                "symbol": "NOWEEK", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 105.0, "avg_dollar_volume_20d": 40_000_000.0,
                "volatility_ratio": 0.6, "liquidity_val": 40_000_000.0,
                "relative_strength_index": 110.0, "ma200": 95.0, "high_52w_proximity": 0.84,
                "weekly_trend_score": 0.5, "atr_pct_20": 0.03,
                "market_cap": 5_000_000_000.0, "beta_126": 1.25, "spread_bps": 12.0,
                "earnings_blackout": 0,
            },
            {
                "symbol": "SMALLCAP", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 105.0, "avg_dollar_volume_20d": 40_000_000.0,
                "volatility_ratio": 0.6, "liquidity_val": 40_000_000.0,
                "relative_strength_index": 110.0, "ma200": 95.0, "high_52w_proximity": 0.84,
                "weekly_trend_score": 1.0, "atr_pct_20": 0.03,
                "market_cap": 1_500_000_000.0, "beta_126": 1.25, "spread_bps": 12.0,
                "earnings_blackout": 0,
            },
            {
                "symbol": "LOWBETA", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 105.0, "avg_dollar_volume_20d": 40_000_000.0,
                "volatility_ratio": 0.6, "liquidity_val": 40_000_000.0,
                "relative_strength_index": 110.0, "ma200": 95.0, "high_52w_proximity": 0.84,
                "weekly_trend_score": 1.0, "atr_pct_20": 0.03,
                "market_cap": 5_000_000_000.0, "beta_126": 0.85, "spread_bps": 12.0,
                "earnings_blackout": 0,
            },
            {
                "symbol": "WIDESPREAD", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 105.0, "avg_dollar_volume_20d": 40_000_000.0,
                "volatility_ratio": 0.6, "liquidity_val": 40_000_000.0,
                "relative_strength_index": 110.0, "ma200": 95.0, "high_52w_proximity": 0.84,
                "weekly_trend_score": 1.0, "atr_pct_20": 0.03,
                "market_cap": 5_000_000_000.0, "beta_126": 1.25, "spread_bps": 40.0,
                "earnings_blackout": 0,
            },
            {
                "symbol": "EARNINGS", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 105.0, "avg_dollar_volume_20d": 40_000_000.0,
                "volatility_ratio": 0.6, "liquidity_val": 40_000_000.0,
                "relative_strength_index": 110.0, "ma200": 95.0, "high_52w_proximity": 0.84,
                "weekly_trend_score": 1.0, "atr_pct_20": 0.03,
                "market_cap": 5_000_000_000.0, "beta_126": 1.25, "spread_bps": 12.0,
                "earnings_blackout": 1,
            },
        ]
    )

    filtered = scanner.apply_filters(merged_df)

    assert list(filtered["symbol"]) == ["PASS"]


def test_apply_sector_neutrality_respects_sector_cap() -> None:
    scanner = _make_scanner(AlphaScannerConfig(selection_size=4, sector_cap_ratio=0.25))
    ranked_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "sector": "Tech", "final_score": 0.95, "trend_score": 0.9, "vcp_score": 0.8, "avg_dollar_volume_20d": 30_000_000.0},
            {"symbol": "MSFT", "sector": "Tech", "final_score": 0.94, "trend_score": 0.9, "vcp_score": 0.8, "avg_dollar_volume_20d": 29_000_000.0},
            {"symbol": "JPM", "sector": "Finance", "final_score": 0.93, "trend_score": 0.8, "vcp_score": 0.7, "avg_dollar_volume_20d": 28_000_000.0},
            {"symbol": "XOM", "sector": "Energy", "final_score": 0.92, "trend_score": 0.8, "vcp_score": 0.7, "avg_dollar_volume_20d": 27_000_000.0},
            {"symbol": "PFE", "sector": "Health", "final_score": 0.91, "trend_score": 0.8, "vcp_score": 0.7, "avg_dollar_volume_20d": 26_000_000.0},
        ]
    )

    selected = scanner.apply_sector_neutrality(ranked_df)

    rows = selected.to_dict(orient="records")
    sectors = [row["sector"] for row in rows]
    assert len(rows) == 4
    assert sectors.count("Tech") == 1
    assert set(sectors) == {"Tech", "Finance", "Energy", "Health"}

