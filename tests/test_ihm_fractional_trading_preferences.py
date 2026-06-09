from __future__ import annotations

from pathlib import Path

from ihm.services import fractional_trading_preferences as prefs_module
from ihm.services.fractional_trading_preferences import (
    FractionalTradingPreferences,
    load_persisted_fractional_trading_preferences,
    save_persisted_fractional_trading_preferences,
)


def _configure_storage(tmp_path: Path, monkeypatch) -> Path:
    preferences_dir = tmp_path / "ihm_preferences"
    preferences_path = preferences_dir / "fractional_trading.json"
    monkeypatch.setattr(prefs_module, "PREFERENCES_DIR", preferences_dir)
    monkeypatch.setattr(prefs_module, "FRACTIONAL_TRADING_PREFERENCES_PATH", preferences_path)
    return preferences_path


def test_load_persisted_fractional_trading_preferences_defaults_to_enabled(tmp_path: Path, monkeypatch) -> None:
    _configure_storage(tmp_path, monkeypatch)

    prefs = load_persisted_fractional_trading_preferences()

    assert prefs == FractionalTradingPreferences(backtest_enabled=True, pipeline_live_enabled=True)


def test_save_persisted_fractional_trading_preferences_round_trip(tmp_path: Path, monkeypatch) -> None:
    preferences_path = _configure_storage(tmp_path, monkeypatch)

    saved = save_persisted_fractional_trading_preferences(
        FractionalTradingPreferences(
            backtest_enabled=False,
            pipeline_live_enabled=True,
        )
    )
    reloaded = load_persisted_fractional_trading_preferences()

    assert preferences_path.exists()
    assert saved == FractionalTradingPreferences(backtest_enabled=False, pipeline_live_enabled=True)
    assert reloaded == saved

