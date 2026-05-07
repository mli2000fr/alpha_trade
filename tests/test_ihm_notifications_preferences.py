"""Tests Sprint S27 — préférences notifications email IHM."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ihm.services import notifications_preferences as np_mod
from ihm.services.notifications_preferences import (
    DEFAULT_NOTIFY_ON,
    DEFAULT_RECIPIENTS,
    NotificationPreferences,
    format_recipients,
    is_valid_email,
    load_persisted_notification_preferences,
    parse_recipients,
    save_persisted_notification_preferences,
)


@pytest.fixture(autouse=True)
def _isolate_preferences(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "notifications.json"
    monkeypatch.setattr(np_mod, "PREFERENCES_DIR", tmp_path)
    monkeypatch.setattr(np_mod, "NOTIFICATIONS_PREFERENCES_PATH", target)


def test_parse_recipients_split_semicolon_and_dedupe() -> None:
    raw = "  a@b.com ;c@d.fr;A@B.com,, e@f.io\n"
    assert parse_recipients(raw) == ["a@b.com", "c@d.fr", "e@f.io"]


def test_parse_recipients_filters_invalid() -> None:
    assert parse_recipients("garbage; ok@example.com; nope@; another") == ["ok@example.com"]


def test_is_valid_email() -> None:
    assert is_valid_email("foo@bar.baz")
    assert not is_valid_email("nope")
    assert not is_valid_email("a@b")


def test_format_recipients_round_trip() -> None:
    recipients = ["a@b.com", "c@d.fr"]
    assert format_recipients(recipients) == "a@b.com;c@d.fr"
    assert parse_recipients(format_recipients(recipients)) == recipients


def test_load_default_when_missing() -> None:
    prefs = load_persisted_notification_preferences()
    assert prefs.recipients == list(DEFAULT_RECIPIENTS)
    assert prefs.enabled is True
    assert prefs.notify_on == list(DEFAULT_NOTIFY_ON)


def test_save_and_reload_round_trip() -> None:
    prefs = NotificationPreferences(
        recipients=["x@y.com", "z@w.fr"],
        enabled=False,
        notify_on=["failed", "timeout"],
    )
    save_persisted_notification_preferences(prefs)
    reloaded = load_persisted_notification_preferences()
    assert reloaded.recipients == ["x@y.com", "z@w.fr"]
    assert reloaded.enabled is False
    assert reloaded.notify_on == ["failed", "timeout"]


def test_save_normalizes_invalid_inputs() -> None:
    prefs = NotificationPreferences(
        recipients=["bad", "good@ok.io"],
        enabled=True,
        notify_on=["nope", "completed", "completed"],
    )
    saved = save_persisted_notification_preferences(prefs)
    assert saved.recipients == ["good@ok.io"]
    assert saved.notify_on == ["completed"]


def test_save_falls_back_to_default_recipients_when_all_invalid() -> None:
    prefs = NotificationPreferences(recipients=["x", "y"], enabled=True, notify_on=["failed"])
    saved = save_persisted_notification_preferences(prefs)
    assert saved.recipients == list(DEFAULT_RECIPIENTS)


def test_load_handles_corrupt_json(monkeypatch) -> None:
    np_mod.NOTIFICATIONS_PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    np_mod.NOTIFICATIONS_PREFERENCES_PATH.write_text("not-json", encoding="utf-8")
    prefs = load_persisted_notification_preferences()
    assert prefs.recipients == list(DEFAULT_RECIPIENTS)


def test_load_accepts_legacy_recipients_string() -> None:
    np_mod.NOTIFICATIONS_PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    np_mod.NOTIFICATIONS_PREFERENCES_PATH.write_text(
        json.dumps({"recipients": "a@b.com;c@d.fr", "enabled": True, "notify_on": ["failed"]}),
        encoding="utf-8",
    )
    prefs = load_persisted_notification_preferences()
    assert prefs.recipients == ["a@b.com", "c@d.fr"]
    assert prefs.notify_on == ["failed"]

