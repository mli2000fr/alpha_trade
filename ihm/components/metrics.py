"""ihm/components/metrics.py — Helpers pour afficher des métriques st.metric."""
from __future__ import annotations

from typing import cast

import streamlit as st


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(cast(float | int | str, value))
    except (TypeError, ValueError):
        return default


def to_int(value: object, default: int = 0) -> int:
    try:
        return int(cast(float | int | str, value))
    except (TypeError, ValueError):
        return default


def format_duration_hhmmss(value: object) -> str:
    """Formate une durée en secondes vers `hh:mm:ss`.

    Les valeurs invalides, négatives ou absentes sont normalisées à `00:00:00`.
    """
    total_seconds = max(0, int(round(_to_float(value))))

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def metric_row(metrics: list[tuple[str, str | int | float, str | None]]) -> None:
    """Affiche une ligne de st.metric. Chaque tuple = (label, value, delta)."""
    cols = st.columns(len(metrics))
    for col, (label, value, delta) in zip(cols, metrics):
        col.metric(label, value, delta)

