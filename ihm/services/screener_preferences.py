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


__all__ = [
    "PREFERENCES_DIR",
    "SCREENER_SELECTION_PREFERENCES_PATH",
    "load_persisted_selected_screener_artifacts_dir",
    "save_persisted_selected_screener_artifacts_dir",
]

