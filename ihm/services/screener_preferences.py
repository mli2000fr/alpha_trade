"""Préférences persistantes IHM liées à la navigation screener."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ihm.services.pipeline_runner import PROJECT_ROOT
from ihm.services.screener_recommendations import get_screener_artifacts_dir

PREFERENCES_DIR = PROJECT_ROOT / "artifacts" / "ihm_preferences"
SCREENER_SELECTION_PREFERENCES_PATH = PREFERENCES_DIR / "screener_selection.json"
ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_PATH = PREFERENCES_DIR / "alpha_scanner_dependency_thresholds.json"


def _ensure_storage() -> None:
    PREFERENCES_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_optional_dir(artifacts_dir: Path | str | None) -> str | None:
    if artifacts_dir is None:
        return None
    text = str(artifacts_dir).strip()
    if not text:
        return None
    return str(get_screener_artifacts_dir(text))


def load_persisted_selected_screener_artifacts_dir() -> str | None:
    path = SCREENER_SELECTION_PREFERENCES_PATH
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return _normalize_optional_dir(payload.get("selected_screener_artifacts_dir"))


def save_persisted_selected_screener_artifacts_dir(artifacts_dir: Path | str | None) -> str | None:
    normalized_dir = _normalize_optional_dir(artifacts_dir)
    _ensure_storage()
    payload: dict[str, Any] = {
        "selected_screener_artifacts_dir": normalized_dir,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    SCREENER_SELECTION_PREFERENCES_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return normalized_dir


def _normalize_thresholds_payload(
    payload: object,
    *,
    defaults: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    normalized: dict[str, dict[str, float]] = {
        step_key: {metric_key: float(metric_value) for metric_key, metric_value in values.items()}
        for step_key, values in defaults.items()
    }
    if not isinstance(payload, dict):
        return normalized

    for step_key, step_defaults in defaults.items():
        step_payload = payload.get(step_key)
        if not isinstance(step_payload, dict):
            continue
        for metric_key, default_value in step_defaults.items():
            raw_value = step_payload.get(metric_key)
            try:
                normalized[step_key][metric_key] = float(raw_value)
            except (TypeError, ValueError):
                normalized[step_key][metric_key] = float(default_value)
    return normalized


def load_persisted_alpha_scanner_dependency_thresholds(
    defaults: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    path = ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_PATH
    if not path.exists() or not path.is_file():
        return _normalize_thresholds_payload({}, defaults=defaults)
    try:
        payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return _normalize_thresholds_payload({}, defaults=defaults)
    return _normalize_thresholds_payload(payload, defaults=defaults)


def load_persisted_alpha_scanner_dependency_preset_metadata() -> dict[str, str | None]:
    path = ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_PATH
    if not path.exists() or not path.is_file():
        return {"selected_style": None, "selected_market_regime": None, "selection_mode": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {"selected_style": None, "selected_market_regime": None, "selection_mode": None}
    if not isinstance(payload, dict):
        return {"selected_style": None, "selected_market_regime": None, "selection_mode": None}
    return {
        "selected_style": str(payload.get("selected_style") or "").strip() or None,
        "selected_market_regime": str(payload.get("selected_market_regime") or "").strip() or None,
        "selection_mode": str(payload.get("selection_mode") or "").strip() or None,
    }


def save_persisted_alpha_scanner_dependency_thresholds(
    thresholds: dict[str, dict[str, float]],
    *,
    defaults: dict[str, dict[str, float]],
    selected_style: str | None = None,
    selected_market_regime: str | None = None,
    selection_mode: str | None = None,
) -> dict[str, dict[str, float]]:
    normalized = _normalize_thresholds_payload(thresholds, defaults=defaults)
    _ensure_storage()
    payload: dict[str, Any] = {
        **normalized,
        "selected_style": (selected_style or "").strip() or None,
        "selected_market_regime": (selected_market_regime or "").strip() or None,
        "selection_mode": (selection_mode or "").strip() or None,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return normalized


def reset_persisted_alpha_scanner_dependency_thresholds() -> None:
    path = ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_PATH
    if path.exists() and path.is_file():
        path.unlink()


__all__ = [
    "ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_PATH",
    "PREFERENCES_DIR",
    "SCREENER_SELECTION_PREFERENCES_PATH",
    "load_persisted_alpha_scanner_dependency_preset_metadata",
    "load_persisted_alpha_scanner_dependency_thresholds",
    "load_persisted_selected_screener_artifacts_dir",
    "reset_persisted_alpha_scanner_dependency_thresholds",
    "save_persisted_alpha_scanner_dependency_thresholds",
    "save_persisted_selected_screener_artifacts_dir",
]

