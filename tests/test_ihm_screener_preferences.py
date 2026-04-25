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

