import pytest
from datetime import date
from dataclasses import replace

from common.capital_presets import load_capital_presets, build_selector_config_kwargs_from_preset
from core.filter_profiles import STRICT_SWING_CASH_FILTERS, normalize_earnings_blackout_days
from selector.config import AlphaScannerConfig
from selector.cli import _build_arg_parser, _build_config_from_args
from selector.db_io import _build_earnings_quality_check, fetch_next_earnings


@pytest.mark.parametrize("raw,expected", [(-1, None), (None, None), (0, 0), (2, 2)])
def test_blackout_contract(raw, expected):
    assert normalize_earnings_blackout_days(raw) == expected
    assert AlphaScannerConfig(earnings_blackout_days=raw).earnings_blackout_days == expected
    assert replace(STRICT_SWING_CASH_FILTERS, earnings_blackout_days=raw).earnings_blackout_days == expected


def test_other_negative_values_are_rejected():
    with pytest.raises(ValueError, match="earnings_blackout_days"):
        AlphaScannerConfig(earnings_blackout_days=-2)


def test_cli_disables_filter_and_quality_check_without_database():
    args = _build_arg_parser().parse_args(["--earnings-blackout-days", "-1"])
    config = _build_config_from_args(args)
    assert config.earnings_blackout_days is None
    assert _build_earnings_quality_check(object(), config, date(2026, 10, 29))["status"] == "disabled"
    assert fetch_next_earnings(object(), config, ["BAND"]).empty


def test_all_operational_presets_disable_blackout_and_keep_ui_sentinel():
    for preset in load_capital_presets():
        assert preset.values["selector_earnings_blackout_days"] == -1
        assert build_selector_config_kwargs_from_preset(preset)["earnings_blackout_days"] is None
        assert preset.to_session_state_values()["pipeline_selector_earnings_blackout_days"] == -1


def test_batch_defaults_propagate_disabled_control():
    from ihm.services.pipeline_runner import pipeline_page_default_options, build_pipeline_command
    options = pipeline_page_default_options(trade_date="2026-10-29")
    assert options.selector_earnings_blackout_days == -1
    command = build_pipeline_command("alpha_scanner", options)
    assert command[command.index("--earnings-blackout-days") + 1] == "-1"


def test_disabled_filter_clears_inherited_veto_without_mutating_input():
    import pandas as pd
    from selector.filters import apply_filters_with_stats
    frame = pd.DataFrame([dict(symbol="BAND", history_days=600, latest_close=20,
        avg_dollar_volume_20d=40_000_000, earnings_blackout=1, liquidity_val=40_000_000)])
    filtered, stats = apply_filters_with_stats(frame, AlphaScannerConfig(earnings_blackout_days=-1))
    assert len(filtered) == 1
    assert filtered.iloc[0].earnings_blackout == 0
    assert frame.iloc[0].earnings_blackout == 1
    assert stats["rejected_earnings_blackout"] == 0
