"""ihm/components/run_summary.py — Rendu commun des blocs de résumé métier persistant."""
from __future__ import annotations

from typing import Mapping

import streamlit as st

from ihm.components.metrics import metric_row
from ihm.services.run_summary import (
    build_run_summary_caption,
    get_run_summary,
    get_run_summary_detail_lines,
    get_run_summary_metric_items,
)


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        return int(value)
    return 0


def _coerce_float(value: object) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float, str)):
        return float(value)
    return 0.0


def _build_live_progress_text(summary: Mapping[str, object]) -> str:
    progress_label = str(summary.get("progress_label") or "Progression en cours").strip()
    progress_current = _coerce_int(summary.get("progress_current"))
    progress_total = _coerce_int(summary.get("progress_total"))
    progress_unit = str(summary.get("progress_unit") or "éléments").strip()
    progress_item = str(summary.get("progress_item") or "").strip()
    progress_phase = str(summary.get("progress_phase") or "").strip()
    progress_text = f"{progress_label} — {progress_current}/{progress_total} {progress_unit}"

    if progress_phase == "contextual_scoring":
        batch_index = _coerce_int(summary.get("contextual_current_batch"))
        batch_total = _coerce_int(summary.get("contextual_estimated_batches"))
        batch_size = _coerce_int(summary.get("contextual_last_batch_size"))
        remaining_pairs = _coerce_int(summary.get("contextual_pairs_remaining"))
        contextual_parts: list[str] = []
        if batch_index > 0 and "lot" not in progress_label.lower():
            contextual_parts.append(
                f"lot {batch_index}/{batch_total}" if batch_total > 0 else f"lot {batch_index}"
            )
        if batch_size > 0:
            contextual_parts.append(f"dernier lot={batch_size}")
        contextual_parts.append(f"reste={remaining_pairs}")
        if contextual_parts:
            progress_text += " — " + " — ".join(contextual_parts)

    if progress_item:
        progress_text += f" — {progress_item}"
    return progress_text


def render_run_summary_block(
    record: Mapping[str, object] | None,
    *,
    title: str | None = None,
    max_metrics: int = 6,
    heading_level: str = "subheader",
    show_caption: bool = True,
) -> bool:
    """Affiche un bloc homogène de résumé métier.

    `heading_level` accepte `subheader` (par défaut) ou `markdown`.
    Retourne `True` si un résumé a été rendu, sinon `False`.
    """
    summary = get_run_summary(record)
    if not summary:
        return False

    status = str((record or {}).get("status") or "").strip().lower()
    progress_live = bool(summary.get("progress_live"))
    show_progress = progress_live and status in {"", "starting", "running"}

    if title:
        if heading_level == "markdown":
            st.markdown(title)
        else:
            st.subheader(title)

    metric_items = get_run_summary_metric_items(record)
    if metric_items:
        display_metrics: list[tuple[str, str | int | float, str | None]] = []
        for label, value in metric_items[:max_metrics]:
            display_value = value if isinstance(value, (str, int, float)) else str(value)
            display_metrics.append((label, display_value, None))
        metric_row(display_metrics)

    if show_progress:
        try:
            progress_ratio = _coerce_float(summary.get("progress_ratio"))
        except (TypeError, ValueError):
            progress_ratio = 0.0
        progress_ratio = min(max(progress_ratio, 0.0), 1.0)
        st.progress(progress_ratio, text=_build_live_progress_text(summary))

    if show_caption:
        caption = str((record or {}).get("summary_caption", "") or "").strip()
        st.caption(caption or build_run_summary_caption(record))
    for detail_line in get_run_summary_detail_lines(record):
        st.caption(detail_line)
    return True


def render_persistent_business_summary(
    record: Mapping[str, object] | None,
    *,
    title: str = "🧭 Résumé métier persistant",
    max_metrics: int = 6,
) -> bool:
    """Affiche un bloc homogène de résumé métier persistant.

    Retourne `True` si un résumé a été rendu, sinon `False`.
    """
    return render_run_summary_block(record, title=title, max_metrics=max_metrics, heading_level="subheader", show_caption=True)


