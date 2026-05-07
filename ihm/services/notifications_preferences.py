"""Préférences persistantes IHM — notifications email fin de workflow.

Sprint S27 / Notifications pipeline :
- Persistance JSON dans ``artifacts/ihm_preferences/notifications.json``.
- Destinataires multiples séparés par ``;``.
- Statuts déclencheurs configurables (``completed``, ``failed``, ``timeout``,
  ``stopped``).
- Valeur par défaut destinataire : ``gamer.2000.fr@gmail.com``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from ihm.services.pipeline_runner import PROJECT_ROOT

PREFERENCES_DIR = PROJECT_ROOT / "artifacts" / "ihm_preferences"
NOTIFICATIONS_PREFERENCES_PATH = PREFERENCES_DIR / "notifications.json"

DEFAULT_RECIPIENTS: tuple[str, ...] = ("gamer.2000.fr@gmail.com",)
DEFAULT_NOTIFY_ON: tuple[str, ...] = ("completed", "failed", "timeout", "stopped")
ALLOWED_STATUSES: frozenset[str] = frozenset({"completed", "failed", "timeout", "stopped"})

_EMAIL_RE = re.compile(r"^[^@\s;,]+@[^@\s;,]+\.[^@\s;,]+$")


def _ensure_storage() -> None:
    PREFERENCES_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class NotificationPreferences:
    """Préférences notifications email persistées côté IHM."""

    recipients: list[str] = field(default_factory=lambda: list(DEFAULT_RECIPIENTS))
    enabled: bool = True
    notify_on: list[str] = field(default_factory=lambda: list(DEFAULT_NOTIFY_ON))

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipients": list(self.recipients),
            "enabled": bool(self.enabled),
            "notify_on": list(self.notify_on),
        }

    def recipients_string(self) -> str:
        return format_recipients(self.recipients)


def is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(str(value).strip()))


def parse_recipients(raw: str | Iterable[str] | None) -> list[str]:
    """Parse une chaîne séparée par ``;`` (ou un itérable) en liste d'emails valides.

    Tolère espaces, virgules ``,``, retours-ligne. Filtre silencieusement les
    entrées vides. Conserve l'ordre, dédoublonne (case-insensitive).
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        candidates = re.split(r"[;,\n]+", raw)
    else:
        candidates = list(raw)
    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        cleaned = str(candidate).strip()
        if not cleaned:
            continue
        if not is_valid_email(cleaned):
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def format_recipients(recipients: Iterable[str]) -> str:
    return ";".join(str(item).strip() for item in recipients if str(item).strip())


def _normalize_notify_on(raw: object) -> list[str]:
    if not isinstance(raw, (list, tuple, set)):
        return list(DEFAULT_NOTIFY_ON)
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        cleaned = str(item).strip().lower()
        if cleaned in ALLOWED_STATUSES and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out or list(DEFAULT_NOTIFY_ON)


def load_persisted_notification_preferences() -> NotificationPreferences:
    path = NOTIFICATIONS_PREFERENCES_PATH
    if not path.exists() or not path.is_file():
        return NotificationPreferences()
    try:
        payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return NotificationPreferences()
    if not isinstance(payload, dict):
        return NotificationPreferences()

    recipients_raw = payload.get("recipients")
    if isinstance(recipients_raw, str):
        recipients = parse_recipients(recipients_raw)
    elif isinstance(recipients_raw, (list, tuple)):
        recipients = parse_recipients(list(recipients_raw))
    else:
        recipients = list(DEFAULT_RECIPIENTS)
    if not recipients:
        recipients = list(DEFAULT_RECIPIENTS)

    enabled = bool(payload.get("enabled", True))
    notify_on = _normalize_notify_on(payload.get("notify_on"))
    return NotificationPreferences(recipients=recipients, enabled=enabled, notify_on=notify_on)


def save_persisted_notification_preferences(prefs: NotificationPreferences) -> NotificationPreferences:
    _ensure_storage()
    recipients = parse_recipients(prefs.recipients) or list(DEFAULT_RECIPIENTS)
    notify_on = _normalize_notify_on(prefs.notify_on)
    normalized = NotificationPreferences(
        recipients=recipients,
        enabled=bool(prefs.enabled),
        notify_on=notify_on,
    )
    payload: dict[str, Any] = {
        **normalized.to_dict(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    NOTIFICATIONS_PREFERENCES_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return normalized


__all__ = [
    "ALLOWED_STATUSES",
    "DEFAULT_NOTIFY_ON",
    "DEFAULT_RECIPIENTS",
    "NOTIFICATIONS_PREFERENCES_PATH",
    "NotificationPreferences",
    "PREFERENCES_DIR",
    "format_recipients",
    "is_valid_email",
    "load_persisted_notification_preferences",
    "parse_recipients",
    "save_persisted_notification_preferences",
]


