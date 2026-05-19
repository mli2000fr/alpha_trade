from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import cast

import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from selector.alpha_scanner import (
    AlphaScanner,
    AlphaScannerConfig,
    SelectorAblationPlan,
    SelectorVariantSpec,
    _build_arg_parser,
    _build_config_from_args,
    _summarize_zero_candidate_filters,
    load_selector_ablation_plan_from_file,
)


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

    assert config.preset_profile == "strict_swing_cash"
    assert config.preset_profile_version == "v1"
    assert config.min_close == pytest.approx(10.0)
    assert config.liquidity_threshold == pytest.approx(30_000_000.0)
    assert config.max_volatility_ratio == pytest.approx(0.9)
    assert config.min_relative_strength_index == pytest.approx(100.0)
    assert config.min_high_52w_proximity == pytest.approx(0.75)
    assert config.min_weekly_trend_score == pytest.approx(1.0)
    assert config.min_atr_pct_20 == pytest.approx(0.015)
    assert config.max_atr_pct_20 == pytest.approx(0.06)
    assert config.min_market_cap == pytest.approx(2_000_000_000.0)
    assert config.min_beta_126 == pytest.approx(0.8)
    assert config.max_spread_bps == pytest.approx(40.0)
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


def test_cli_can_override_data_quality_modes_per_filter() -> None:
    args = _build_arg_parser().parse_args(
        [
            "--spread-data-quality-mode",
            "warn_skip_filter",
            "--earnings-data-quality-mode",
            "warn_skip_filter",
            "--market-cap-data-quality-mode",
            "warn_skip_filter",
        ]
    )

    config = _build_config_from_args(args)

    assert config.spread_data_quality_mode == "warn_skip_filter"
    assert config.earnings_data_quality_mode == "warn_skip_filter"
    assert config.market_cap_filter_data_quality_mode == "warn_skip_filter"


def test_selector_variant_spec_rejects_unknown_disabled_filter() -> None:
    with pytest.raises(ValueError, match="Filtre d'ablation inconnu"):
        SelectorVariantSpec(variant_id="bad", disabled_filters=("unknown_filter",))


def test_selector_ablation_plan_requires_variants_in_shadow_mode() -> None:
    with pytest.raises(ValueError, match="mode=shadow"):
        SelectorAblationPlan(mode="shadow")


def test_cli_can_load_selector_ablation_plan_from_json(tmp_path) -> None:
    config_path = tmp_path / "selector_ablation.json"
    config_path.write_text(
        json.dumps(
            {
                "mode": "shadow",
                "artifact_dir": str(tmp_path / "artifacts"),
                "variants": [
                    {
                        "variant_id": "no_spread",
                        "disabled_filters": ["spread"],
                    },
                    {
                        "variant_id": "looser_rsi",
                        "config_overrides": {"min_relative_strength_index": 95.0},
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    args = _build_arg_parser().parse_args(
        [
            "--ablation-mode",
            "shadow",
            "--ablation-config",
            str(config_path),
        ]
    )

    config = _build_config_from_args(args)

    assert config.ablation_plan is not None
    assert config.ablation_plan.mode == "shadow"
    assert [variant.variant_id for variant in config.ablation_plan.variants] == ["no_spread", "looser_rsi"]
    assert config.ablation_plan.variants[0].disabled_filters == ("spread",)
    assert config.ablation_plan.variants[1].config_overrides == {"min_relative_strength_index": 95.0}


def test_repo_ready_ablation_preset_is_loadable() -> None:
    preset_path = Path(__file__).resolve().parents[1] / "config" / "selector_ablation_strict_swing_shadow.yaml"

    plan = load_selector_ablation_plan_from_file(preset_path)

    assert plan.mode == "shadow"
    assert [variant.variant_id for variant in plan.variants] == [
        "no_spread",
        "no_earnings_blackout",
        "trend_floor_relaxed",
        "no_ma200",
        "midcap_flex",
    ]


def test_cli_without_preset_uses_strict_profile_implicitly() -> None:
    args = _build_arg_parser().parse_args([])

    config = _build_config_from_args(args)

    assert config.min_close == pytest.approx(10.0)
    assert config.liquidity_threshold == pytest.approx(30_000_000.0)
    assert config.max_volatility_ratio == pytest.approx(0.9)
    assert config.min_relative_strength_index == pytest.approx(100.0)
    assert config.min_atr_pct_20 == pytest.approx(0.015)
    assert config.min_market_cap == pytest.approx(2_000_000_000.0)
    assert config.min_beta_126 == pytest.approx(0.8)
    assert config.max_spread_bps == pytest.approx(40.0)
    assert config.earnings_blackout_days == 3
    assert config.require_above_ma200 is True


def test_cli_help_formats_percent_values_without_argparse_error() -> None:
    help_text = _build_arg_parser().format_help()

    assert "--sector-cap-ratio" in help_text
    assert "0.30 = 30%" in help_text


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


def test_apply_filters_rejects_failed_sanitizer_status() -> None:
    scanner = _make_scanner(AlphaScannerConfig())
    merged_df = pd.DataFrame(
        [
            {
                "symbol": "PASS", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 50.0, "avg_dollar_volume_20d": 30_000_000.0,
                "liquidity_val": 30_000_000.0, "sanitizer_status": "success",
                "anomaly_count": 0, "missing_days_count": 0,
            },
            {
                "symbol": "FAIL", "asset_class": "us_equity", "tradable": True,
                "history_days": 300, "latest_close": 50.0, "avg_dollar_volume_20d": 30_000_000.0,
                "liquidity_val": 30_000_000.0, "sanitizer_status": "failed",
                "anomaly_count": 0, "missing_days_count": 0,
            },
        ]
    )

    filtered = scanner.apply_filters(merged_df)

    assert list(filtered["symbol"]) == ["PASS"]


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
                "weekly_trend_score": 0.5,
                "atr_pct_20": 0.03,
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


# --- Phase 3.3.b/c/d -------------------------------------------------------

def test_strict_swing_cash_propagates_iex_and_ttl_extensions() -> None:
    """Phase 3.3.c/d — extensions IEX/TTL doivent transiter du profil → config."""
    config = AlphaScannerConfig.strict_swing_cash()
    assert config.max_spread_bps_iex == pytest.approx(65.0)
    assert config.min_quote_size == pytest.approx(100.0)
    assert config.market_cap_max_age_days == 45


def test_summarize_zero_candidate_filters_highlights_last_bottlenecks() -> None:
    summary = _summarize_zero_candidate_filters(
        {
            "input": 1661,
            "rejected_volatility": 674,
            "rejected_atr": 140,
            "rejected_relative_strength": 491,
            "rejected_ma200": 28,
            "rejected_weekly": 55,
            "rejected_market_cap": 3,
            "rejected_market_cap_stale": 0,
            "rejected_beta": 241,
            "rejected_spread": 29,
        }
    )

    assert "volatilite_relative=674" in summary
    assert "force_relative=491" in summary
    assert "beta_tres_selectif=241/270" in summary
    assert "tous_les_survivants_avant_spread=29" in summary


def test_alpha_scanner_config_rejects_iex_relaxation_below_strict() -> None:
    with pytest.raises(ValueError, match="max_spread_bps_iex"):
        AlphaScannerConfig(max_spread_bps=30.0, max_spread_bps_iex=10.0)


def test_alpha_scanner_config_rejects_negative_min_quote_size() -> None:
    with pytest.raises(ValueError, match="min_quote_size"):
        AlphaScannerConfig(min_quote_size=-1.0)


def test_alpha_scanner_config_rejects_negative_market_cap_ttl() -> None:
    with pytest.raises(ValueError, match="market_cap_max_age_days"):
        AlphaScannerConfig(market_cap_max_age_days=-5)


def test_alpha_scanner_config_rejects_unknown_data_quality_mode() -> None:
    with pytest.raises(ValueError, match="spread_data_quality_mode"):
        AlphaScannerConfig(spread_data_quality_mode="skip")


def test_apply_filters_iex_relaxation_rescues_thick_book() -> None:
    """Phase 3.3.c — un titre dépassant max_spread_bps mais sous max_spread_bps_iex
    et avec bid_size/ask_size >= min_quote_size doit être conservé."""
    scanner = _make_scanner(
        AlphaScannerConfig(
            max_spread_bps=25.0,
            max_spread_bps_iex=50.0,
            min_quote_size=100.0,
        )
    )
    base_row = {
        "history_days": 300,
        "latest_close": 50.0,
        "avg_dollar_volume_20d": 100_000_000.0,
        "asset_class": "us_equity",
        "tradable": True,
    }
    merged_df = pd.DataFrame(
        [
            {**base_row, "symbol": "STRICT", "spread_bps": 12.0, "bid_size": 200.0, "ask_size": 200.0},
            {**base_row, "symbol": "RESCUE", "spread_bps": 35.0, "bid_size": 150.0, "ask_size": 150.0},
            {**base_row, "symbol": "THIN", "spread_bps": 35.0, "bid_size": 50.0, "ask_size": 50.0},
            {**base_row, "symbol": "WIDE", "spread_bps": 80.0, "bid_size": 500.0, "ask_size": 500.0},
        ]
    )

    filtered, stats = scanner._apply_filters_with_stats(merged_df)

    assert sorted(filtered["symbol"].tolist()) == ["RESCUE", "STRICT"]
    assert stats["rescued_spread_iex"] == 1
    assert stats["rejected_spread"] == 2


def test_apply_filters_ignores_stale_quotes_for_spread_filter() -> None:
    """Des snapshots quotes manifestement stales ne doivent pas vider l'univers."""
    scanner = _make_scanner(
        AlphaScannerConfig(
            max_spread_bps=40.0,
            max_spread_bps_iex=65.0,
            min_quote_size=100.0,
        )
    )
    merged_df = pd.DataFrame(
        [
            {
                "symbol": "STALE_OK",
                "history_days": 300,
                "latest_close": 50.0,
                "avg_dollar_volume_20d": 100_000_000.0,
                "asset_class": "us_equity",
                "tradable": True,
                "spread_bps": 1500.0,
                "bid_size": 100.0,
                "ask_size": 100.0,
                "quote_date": pd.Timestamp("2026-04-30"),
                "quote_timestamp": pd.Timestamp("2026-04-29 20:00:00"),
            },
            {
                "symbol": "FRESH_BAD",
                "history_days": 300,
                "latest_close": 50.0,
                "avg_dollar_volume_20d": 100_000_000.0,
                "asset_class": "us_equity",
                "tradable": True,
                "spread_bps": 1500.0,
                "bid_size": 100.0,
                "ask_size": 100.0,
                "quote_date": pd.Timestamp("2026-04-30"),
                "quote_timestamp": pd.Timestamp("2026-04-30 20:00:00"),
            },
        ]
    )

    filtered, stats = scanner._apply_filters_with_stats(merged_df)

    assert filtered["symbol"].tolist() == ["STALE_OK"]
    assert stats["rejected_spread"] == 1


def test_fetch_quote_snapshots_normalizes_missing_optional_columns(monkeypatch) -> None:
    scanner = _make_scanner()
    monkeypatch.setattr(
        scanner,
        "_get_stock_quote_snapshots_columns",
        lambda: {"symbol", "quote_date", "spread_bps"},
    )
    monkeypatch.setattr(
        "selector.alpha_scanner.pd.read_sql_query",
        lambda *args, **kwargs: pd.DataFrame(
            [
                {"symbol": "AAPL", "quote_date": pd.Timestamp("2026-04-30"), "spread_bps": 12.0},
            ]
        ),
    )

    quotes_df = scanner.fetch_quote_snapshots(["AAPL"], reference_date=date(2026, 4, 30))

    assert quotes_df.columns.tolist() == ["symbol", "quote_date", "quote_timestamp", "spread_bps", "bid_size", "ask_size"]
    assert quotes_df.loc[0, "symbol"] == "AAPL"
    assert pd.isna(quotes_df.loc[0, "quote_timestamp"])
    assert pd.isna(quotes_df.loc[0, "bid_size"])
    assert pd.isna(quotes_df.loc[0, "ask_size"])


def test_merge_optional_symbol_overlays_tolerates_quotes_without_quote_timestamp() -> None:
    scanner = _make_scanner()
    merged_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "spread_bps": pd.NA},
        ]
    )
    quotes_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "quote_date": pd.Timestamp("2026-04-30"), "spread_bps": 12.0},
        ]
    )
    earnings_df = pd.DataFrame()

    enriched = scanner._merge_optional_symbol_overlays(merged_df, quotes_df, earnings_df)

    assert enriched["symbol"].tolist() == ["AAPL"]
    assert float(enriched.loc[0, "spread_bps"]) == pytest.approx(12.0)
    assert "quote_timestamp" not in enriched.columns or pd.isna(enriched.loc[0, "quote_timestamp"])


def test_apply_filters_market_cap_ttl_rejects_stale_rows() -> None:
    """Phase 3.3.d — stale market_cap_refreshed_at doit être rejeté quand TTL actif."""
    scanner = _make_scanner(
        AlphaScannerConfig(
            min_market_cap=1_000_000_000.0,
            market_cap_max_age_days=30,
        )
    )
    now = pd.Timestamp.now(tz="UTC")
    fresh = (now - pd.Timedelta(days=10)).to_pydatetime()
    stale = (now - pd.Timedelta(days=120)).to_pydatetime()
    merged_df = pd.DataFrame(
        [
            {
                "symbol": "FRESH",
                "history_days": 300,
                "latest_close": 50.0,
                "avg_dollar_volume_20d": 100_000_000.0,
                "asset_class": "us_equity",
                "tradable": True,
                "market_cap": 5_000_000_000.0,
                "market_cap_refreshed_at": fresh,
            },
            {
                "symbol": "STALE",
                "history_days": 300,
                "latest_close": 50.0,
                "avg_dollar_volume_20d": 100_000_000.0,
                "asset_class": "us_equity",
                "tradable": True,
                "market_cap": 5_000_000_000.0,
                "market_cap_refreshed_at": stale,
            },
        ]
    )

    filtered, stats = scanner._apply_filters_with_stats(merged_df)

    assert filtered["symbol"].tolist() == ["FRESH"]
    assert stats["rejected_market_cap_stale"] == 1
    assert stats["rejected_market_cap"] == 0


def test_get_aggregated_filter_stats_accumulates_across_chunks() -> None:
    """Phase 3.3.b — l'agrégat doit cumuler tous les chunks d'un run."""
    scanner = _make_scanner(AlphaScannerConfig(min_close=10.0))
    chunk_a = pd.DataFrame(
        [
            {
                "symbol": "OK",
                "history_days": 300,
                "latest_close": 50.0,
                "avg_dollar_volume_20d": 100_000_000.0,
                "asset_class": "us_equity",
                "tradable": True,
            },
            {
                "symbol": "CHEAP",
                "history_days": 300,
                "latest_close": 2.0,
                "avg_dollar_volume_20d": 100_000_000.0,
                "asset_class": "us_equity",
                "tradable": True,
            },
        ]
    )
    _, stats_a = scanner._apply_filters_with_stats(chunk_a)
    with scanner._filter_stats_lock:
        for key, value in stats_a.items():
            scanner._aggregated_filter_stats[key] += int(value)

    chunk_b = pd.DataFrame(
        [
            {
                "symbol": "ALSOCHEAP",
                "history_days": 300,
                "latest_close": 1.0,
                "avg_dollar_volume_20d": 100_000_000.0,
                "asset_class": "us_equity",
                "tradable": True,
            },
        ]
    )
    _, stats_b = scanner._apply_filters_with_stats(chunk_b)
    with scanner._filter_stats_lock:
        for key, value in stats_b.items():
            scanner._aggregated_filter_stats[key] += int(value)

    aggregated = scanner.get_aggregated_filter_stats()
    assert aggregated["rejected_price"] == 2
    assert aggregated["input"] == 3

