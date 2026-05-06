"""Palette unifiée pour l'IHM Alpha Trade (Sprint S20)."""
from __future__ import annotations

from typing import Literal

ThemeName = Literal["light", "dark"]

LIGHT: dict[str, str] = {
    "bg": "#FFFFFF",
    "surface": "#F8FAFC",
    "primary": "#1E40AF",       # blue-800
    "success": "#16A34A",       # green-600
    "warning": "#CA8A04",       # yellow-600
    "danger": "#DC2626",        # red-600
    "info": "#2563EB",          # blue-600
    "text": "#0F172A",
    "text_muted": "#64748B",
    "border": "#E2E8F0",
}

DARK: dict[str, str] = {
    "bg": "#0F172A",
    "surface": "#1E293B",
    "primary": "#60A5FA",
    "success": "#4ADE80",
    "warning": "#FACC15",
    "danger": "#F87171",
    "info": "#93C5FD",
    "text": "#F1F5F9",
    "text_muted": "#94A3B8",
    "border": "#334155",
}


def get_palette(theme: ThemeName = "light") -> dict[str, str]:
    """Retourne le mapping de couleurs pour le thème demandé."""
    return DARK if theme == "dark" else LIGHT

