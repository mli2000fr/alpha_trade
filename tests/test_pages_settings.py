from ihm.pages import settings
from ihm.services import queries

def test_pages_settings_importable():
    assert hasattr(settings, "__doc__")


def test_settings_page_exposes_alpha_scanner_threshold_editor_helper() -> None:
    assert hasattr(settings, "_render_alpha_scanner_dependency_threshold_settings")
    assert hasattr(settings, "_apply_alpha_scanner_threshold_preset")


def test_alpha_scanner_dependency_default_thresholds_match_recommended_swing_cash_profile() -> None:
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_latest_quotes"]["coverage_warn_pct"] == 85.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_latest_quotes"]["coverage_error_pct"] == 60.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_latest_quotes"]["max_age_warn_days"] == 1.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_latest_quotes"]["max_age_error_days"] == 3.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_earnings_calendar"]["coverage_warn_pct"] == 15.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_earnings_calendar"]["coverage_error_pct"] == 5.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_earnings_calendar"]["min_horizon_warn_days"] == 14.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_earnings_calendar"]["min_horizon_error_days"] == 7.0


