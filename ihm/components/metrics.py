"""ihm/components/metrics.py — Helpers pour afficher des métriques st.metric."""
from __future__ import annotations

import streamlit as st


def metric_row(metrics: list[tuple[str, str | int | float, str | None]]) -> None:
    """Affiche une ligne de st.metric. Chaque tuple = (label, value, delta)."""
    cols = st.columns(len(metrics))
    for col, (label, value, delta) in zip(cols, metrics):
        col.metric(label, value, delta)

