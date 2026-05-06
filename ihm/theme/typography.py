"""Tokens typographiques pour l'IHM Alpha Trade (Sprint S20)."""
from __future__ import annotations

FONT_SANS = (
    '"Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif'
)
FONT_MONO = (
    '"JetBrains Mono", "Fira Code", "SF Mono", Consolas, monospace'
)

# Style CSS appliqué aux valeurs numériques (KPI, prix, sizing).
NUMERIC_STYLE = (
    f"font-family: {FONT_MONO}; "
    "font-variant-numeric: tabular-nums; "
    "letter-spacing: -0.01em;"
)

