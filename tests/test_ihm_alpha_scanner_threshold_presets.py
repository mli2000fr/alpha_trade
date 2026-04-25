from ihm.services.alpha_scanner_threshold_presets import (
    DEFAULT_ALPHA_SCANNER_DEPENDENCY_THRESHOLDS,
    DEFAULT_MARKET_REGIME,
    DEFAULT_PRESET_STYLE,
    get_alpha_scanner_threshold_preset,
)


def test_default_preset_matches_swing_cash_pro_normal() -> None:
    thresholds = get_alpha_scanner_threshold_preset(style=DEFAULT_PRESET_STYLE, market_regime=DEFAULT_MARKET_REGIME)

    assert thresholds == DEFAULT_ALPHA_SCANNER_DEPENDENCY_THRESHOLDS


def test_very_selective_regime_is_stricter_than_normal_for_swing_cash_pro() -> None:
    normal = get_alpha_scanner_threshold_preset(style="swing_cash_pro", market_regime="normal")
    very_selective = get_alpha_scanner_threshold_preset(style="swing_cash_pro", market_regime="very_selective")

    assert very_selective["sync_latest_quotes"]["coverage_warn_pct"] > normal["sync_latest_quotes"]["coverage_warn_pct"]
    assert very_selective["sync_latest_quotes"]["max_age_error_days"] < normal["sync_latest_quotes"]["max_age_error_days"]
    assert very_selective["sync_earnings_calendar"]["min_horizon_warn_days"] > normal["sync_earnings_calendar"]["min_horizon_warn_days"]


def test_tolerant_style_is_more_permissive_than_swing_cash_pro_in_normal_market() -> None:
    strict = get_alpha_scanner_threshold_preset(style="swing_cash_pro", market_regime="normal")
    tolerant = get_alpha_scanner_threshold_preset(style="tolerant", market_regime="normal")

    assert tolerant["sync_latest_quotes"]["coverage_warn_pct"] < strict["sync_latest_quotes"]["coverage_warn_pct"]
    assert tolerant["sync_latest_quotes"]["max_age_error_days"] > strict["sync_latest_quotes"]["max_age_error_days"]
    assert tolerant["sync_earnings_calendar"]["min_horizon_error_days"] < strict["sync_earnings_calendar"]["min_horizon_error_days"]
