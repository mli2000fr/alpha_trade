"""Mapping iconographique cohérent (inspiré Lucide)."""
from __future__ import annotations

ICONS: dict[str, str] = {
    # Navigation
    "home": "🏠",
    "trading": "📈",
    "research": "🔬",
    "config": "⚙️",
    "compliance": "🛡️",
    # Statuts
    "ok": "🟢",
    "warning": "🟡",
    "danger": "🔴",
    "neutral": "⚪",
    "info": "🔵",
    # Domaines
    "broker": "🏦",
    "risk": "⚖️",
    "screener": "🔎",
    "selector": "🎯",
    "ml": "🤖",
    "backtest": "🧪",
    "parity": "🔀",
    "audit": "📜",
    "tax": "💰",
    "glossary": "📚",
    "data": "💾",
    "supervision": "🛟",
    "workflow": "🧭",
    "pipeline": "🔄",
}


def get_icon(name: str, default: str = "•") -> str:
    """Retourne l'icône associée ou un fallback discret."""
    return ICONS.get(name, default)

