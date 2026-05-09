import io
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ihm.pages import settings
from ihm.services import queries

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

def test_pages_settings_importable():
    assert hasattr(settings, "__doc__")


def test_settings_page_exposes_alpha_scanner_threshold_editor_helper() -> None:
    assert hasattr(settings, "_render_alpha_scanner_dependency_threshold_settings")
    assert hasattr(settings, "_apply_alpha_scanner_threshold_preset")
    assert hasattr(settings, "_render_environment_variable_settings")


def test_alpha_scanner_dependency_default_thresholds_match_recommended_swing_cash_profile() -> None:
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_latest_quotes"]["coverage_warn_pct"] == 85.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_latest_quotes"]["coverage_error_pct"] == 60.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_latest_quotes"]["max_age_warn_days"] == 1.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_latest_quotes"]["max_age_error_days"] == 3.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_earnings_calendar"]["coverage_warn_pct"] == 15.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_earnings_calendar"]["coverage_error_pct"] == 5.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_earnings_calendar"]["min_horizon_warn_days"] == 14.0
    assert queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_earnings_calendar"]["min_horizon_error_days"] == 7.0


def test_prime_bars_provider_widget_state_consumes_pending_sync(monkeypatch) -> None:
    session_state = {
        settings.BARS_PROVIDER_WIDGET_KEY: "alpaca",
        settings.BARS_PROVIDER_PENDING_SYNC_KEY: settings.DEFAULT_BARS_PROVIDER,
    }
    monkeypatch.setattr(settings, "st", SimpleNamespace(session_state=session_state))

    selected = settings._prime_bars_provider_widget_state("alpaca")

    assert selected == settings.DEFAULT_BARS_PROVIDER
    assert session_state[settings.BARS_PROVIDER_WIDGET_KEY] == settings.DEFAULT_BARS_PROVIDER
    assert settings.BARS_PROVIDER_PENDING_SYNC_KEY not in session_state


def test_prime_alpha_scanner_dependency_threshold_state_consumes_pending_values_before_widgets(monkeypatch) -> None:
    pending_thresholds = deepcopy(queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS)
    pending_thresholds["sync_latest_quotes"]["coverage_warn_pct"] = 91.0
    session_state = {
        settings.ALPHA_SCANNER_PENDING_THRESHOLDS_KEY: pending_thresholds,
        settings.ALPHA_SCANNER_PENDING_MARKET_REGIME_KEY: "normal",
    }
    monkeypatch.setattr(settings, "st", SimpleNamespace(session_state=session_state))
    monkeypatch.setattr(settings, "get_alpha_scanner_dependency_thresholds", lambda: deepcopy(queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS))
    monkeypatch.setattr(
        settings,
        "load_persisted_alpha_scanner_dependency_preset_metadata",
        lambda: {"selected_style": "aggressive", "selected_market_regime": "weak"},
    )

    thresholds = settings._prime_alpha_scanner_dependency_threshold_state()

    assert thresholds["sync_latest_quotes"]["coverage_warn_pct"] == 91.0
    assert session_state[settings._threshold_widget_key("sync_latest_quotes", "coverage_warn_pct")] == 91.0
    assert session_state[settings.ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY] == "normal"
    assert settings.ALPHA_SCANNER_PENDING_THRESHOLDS_KEY not in session_state
    assert settings.ALPHA_SCANNER_PENDING_MARKET_REGIME_KEY not in session_state


def test_notifications_failure_log_download_payload_returns_none_when_empty(monkeypatch) -> None:
    monkeypatch.setattr(settings, "read_smtp_test_failure_log", lambda: "")

    assert settings._get_notifications_failure_log_download_payload() is None


def test_notifications_failure_log_download_payload_returns_filename_and_text(monkeypatch) -> None:
    monkeypatch.setattr(settings, "read_smtp_test_failure_log", lambda: "smtp boom")

    payload = settings._get_notifications_failure_log_download_payload()

    assert payload == ("smtp_test_email_failure.log", "smtp boom")


def test_prepare_var_env_export_reads_csv_only_on_explicit_call(monkeypatch, tmp_path: Path) -> None:
    sample_csv = b"Variable,Valeur\nLOGIN_DB,demo\n"

    from ihm.services import varEnv

    monkeypatch.setattr(varEnv, "get_var_env_streamlit", lambda: io.BytesIO(sample_csv))

    payload = settings._prepare_var_env_export()

    assert payload["file_name"] == "var_env.csv"
    assert payload["data"] == sample_csv


@pytest.mark.e2e
def test_environment_variable_settings_panel_renders(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOGIN_DB", "demo")
    monkeypatch.setenv("PASSWORD_DB", "secret")
    monkeypatch.setenv("ALPACA_API_KEY", "alpaca-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "alpaca-secret")
    monkeypatch.setenv("FINNHUB_API_KEY", "finnhub-key")

    def _runner() -> None:
        from ihm.services import varEnv

        varEnv.get_conf_var_env = lambda: ["LOGIN_DB", "PASSWORD_DB"]  # type: ignore[assignment]
        def _unexpected_call():
            raise AssertionError("get_var_env_streamlit ne doit pas être appelé au rendu initial")

        varEnv.get_var_env_streamlit = _unexpected_call  # type: ignore[assignment]
        from ihm.pages import settings as settings_page

        settings_page._render_environment_variable_settings()

    at = AppTest.from_function(_runner).run(timeout=15)

    assert not at.exception, f"Exception : {at.exception}"
    assert any("Variables d'environnement" in str(subheader.value) for subheader in at.subheader)
    assert len(at.file_uploader) == 1


@pytest.mark.e2e
def test_environment_variable_settings_panel_prepares_native_download_once(monkeypatch) -> None:
    monkeypatch.setenv("LOGIN_DB", "demo")

    def _runner() -> None:
        import io

        from ihm.services import varEnv

        varEnv.get_conf_var_env = lambda: ["LOGIN_DB"]  # type: ignore[assignment]
        varEnv.set_var_env = lambda csv_bytes, apply=True: {"applied": {}}  # type: ignore[assignment]

        def _fake_export_stream() -> io.BytesIO:
            return io.BytesIO(b"Variable,Valeur\nLOGIN_DB,demo\n")

        varEnv.get_var_env_streamlit = _fake_export_stream  # type: ignore[assignment]

        from ihm.pages import settings as settings_page

        settings_page._render_environment_variable_settings()

    at = AppTest.from_function(_runner).run(timeout=15)

    assert not at.exception, f"Exception : {at.exception}"
    assert len(at.button) == 1
    assert len(at.get("download_button")) == 0

    at.button[0].click().run(timeout=15)

    assert not at.exception, f"Exception après clic : {at.exception}"
    assert len(at.get("download_button")) == 1


