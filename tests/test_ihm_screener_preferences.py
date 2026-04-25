from __future__ import annotations

import json
from pathlib import Path


def test_save_and_load_persisted_selected_screener_artifacts_dir_roundtrip(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import screener_preferences

    preferences_dir = tmp_path / "prefs"
    preferences_path = preferences_dir / "screener_selection.json"

    monkeypatch.setattr(screener_preferences, "PREFERENCES_DIR", preferences_dir)
    monkeypatch.setattr(screener_preferences, "SCREENER_SELECTION_PREFERENCES_PATH", preferences_path)

    saved = screener_preferences.save_persisted_selected_screener_artifacts_dir(tmp_path / "screener_a")
    loaded = screener_preferences.load_persisted_selected_screener_artifacts_dir()

    assert saved == str(tmp_path / "screener_a")
    assert loaded == str(tmp_path / "screener_a")
    payload = json.loads(preferences_path.read_text(encoding="utf-8"))
    assert payload["selected_screener_artifacts_dir"] == str(tmp_path / "screener_a")
    assert payload["updated_at"]


def test_load_persisted_selected_screener_artifacts_dir_returns_none_for_invalid_payload(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import screener_preferences

    preferences_dir = tmp_path / "prefs"
    preferences_dir.mkdir(parents=True, exist_ok=True)
    preferences_path = preferences_dir / "screener_selection.json"
    preferences_path.write_text("not-json", encoding="utf-8")

    monkeypatch.setattr(screener_preferences, "PREFERENCES_DIR", preferences_dir)
    monkeypatch.setattr(screener_preferences, "SCREENER_SELECTION_PREFERENCES_PATH", preferences_path)

    assert screener_preferences.load_persisted_selected_screener_artifacts_dir() is None


def test_save_alpha_scanner_thresholds_persists_preset_metadata(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import screener_preferences

    preferences_dir = tmp_path / "prefs"
    preferences_path = preferences_dir / "alpha_scanner_dependency_thresholds.json"
    defaults = {
        "sync_latest_quotes": {"coverage_warn_pct": 85.0, "coverage_error_pct": 60.0, "max_age_warn_days": 1.0, "max_age_error_days": 3.0},
        "sync_earnings_calendar": {"coverage_warn_pct": 15.0, "coverage_error_pct": 5.0, "min_horizon_warn_days": 14.0, "min_horizon_error_days": 7.0},
    }

    monkeypatch.setattr(screener_preferences, "PREFERENCES_DIR", preferences_dir)
    monkeypatch.setattr(screener_preferences, "ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_PATH", preferences_path)

    screener_preferences.save_persisted_alpha_scanner_dependency_thresholds(
        defaults,
        defaults=defaults,
        selected_style="swing_cash_pro",
        selected_market_regime="normal",
        selection_mode="preset",
    )

    metadata = screener_preferences.load_persisted_alpha_scanner_dependency_preset_metadata()
    payload = json.loads(preferences_path.read_text(encoding="utf-8"))

    assert metadata == {
        "selected_style": "swing_cash_pro",
        "selected_market_regime": "normal",
        "selection_mode": "preset",
    }
    assert payload["selected_style"] == "swing_cash_pro"
    assert payload["selected_market_regime"] == "normal"
    assert payload["selection_mode"] == "preset"


