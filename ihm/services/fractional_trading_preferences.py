"""Préférences persistantes IHM — activation des quantités fractionnaires."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import streamlit as st

from ihm.services.pipeline_runner import PROJECT_ROOT

PREFERENCES_DIR = PROJECT_ROOT / "artifacts" / "ihm_preferences"
FRACTIONAL_TRADING_PREFERENCES_PATH = PREFERENCES_DIR / "fractional_trading.json"


def _ensure_storage() -> None:
    PREFERENCES_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FractionalTradingPreferences:
    """Préférences d'activation fractionnaire persistées côté IHM."""

    backtest_enabled: bool = True
    pipeline_live_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "backtest_enabled": bool(self.backtest_enabled),
            "pipeline_live_enabled": bool(self.pipeline_live_enabled),
        }


@st.cache_resource(show_spinner=False)
def load_persisted_fractional_trading_preferences() -> FractionalTradingPreferences:
    path = FRACTIONAL_TRADING_PREFERENCES_PATH
    if not path.exists() or not path.is_file():
        return FractionalTradingPreferences()
    try:
        payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return FractionalTradingPreferences()
    if not isinstance(payload, dict):
        return FractionalTradingPreferences()
    return FractionalTradingPreferences(
        backtest_enabled=bool(payload.get("backtest_enabled", True)),
        pipeline_live_enabled=bool(payload.get("pipeline_live_enabled", True)),
    )


def save_persisted_fractional_trading_preferences(
    prefs: FractionalTradingPreferences,
) -> FractionalTradingPreferences:
    _ensure_storage()
    normalized = FractionalTradingPreferences(
        backtest_enabled=bool(prefs.backtest_enabled),
        pipeline_live_enabled=bool(prefs.pipeline_live_enabled),
    )
    payload: dict[str, Any] = {
        **normalized.to_dict(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    FRACTIONAL_TRADING_PREFERENCES_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Invalide le cache_resource pour que le prochain appel relise le fichier
    load_persisted_fractional_trading_preferences.clear()
    return normalized


__all__ = [
    "FRACTIONAL_TRADING_PREFERENCES_PATH",
    "FractionalTradingPreferences",
    "PREFERENCES_DIR",
    "load_persisted_fractional_trading_preferences",
    "save_persisted_fractional_trading_preferences",
]

