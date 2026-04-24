"""ihm/components/run_summary.py — Rendu commun des blocs de résumé métier persistant."""
from __future__ import annotations

from typing import Mapping

import streamlit as st

from ihm.components.metrics import metric_row
from ihm.services.run_summary import build_run_summary_caption, get_run_summary, get_run_summary_metric_items


def render_persistent_business_summary(
    record: Mapping[str, object] | None,
    *,
    title: str = "🧭 Résumé métier persistant",
    max_metrics: int = 6,
) -> bool:
    """Affiche un bloc homogène de résumé métier persistant.

    Retourne `True` si un résumé a été rendu, sinon `False`.
    """
    summary = get_run_summary(record)
    if not summary:
        return False

    st.subheader(title)
    metric_items = get_run_summary_metric_items(record)
    if metric_items:
        metric_row([(label, value, None) for label, value in metric_items[:max_metrics]])

    caption = str((record or {}).get("summary_caption", "") or "").strip()
    st.caption(caption or build_run_summary_caption(record))
    return True

