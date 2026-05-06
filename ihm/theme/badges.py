"""Helpers de badges de statut harmonisés (Sprint S20).

Tous les statuts (broker health, preflight, DR drill, CVE, parity score,
…) doivent passer par ``status_badge`` afin d'obtenir un rendu unifié.
"""
from __future__ import annotations

from typing import Literal

BadgeLevel = Literal["ok", "warning", "danger", "neutral", "info"]

BADGE_LEVELS: tuple[BadgeLevel, ...] = ("ok", "warning", "danger", "neutral", "info")

_ICONS: dict[str, str] = {
    "ok": "🟢",
    "warning": "🟡",
    "danger": "🔴",
    "neutral": "⚪",
    "info": "🔵",
}


def status_badge(label: str, level: str = "neutral") -> str:
    """Retourne un badge markdown ``"<icône> **label**"``.

    ``level`` non reconnu → fallback ``neutral`` (sans exception).
    """
    icon = _ICONS.get(level, _ICONS["neutral"])
    return f"{icon} **{label}**"

