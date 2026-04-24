"""ihm/pages/corporate_actions.py — Suivi des corporate actions."""
from __future__ import annotations

import streamlit as st

from ihm.components.metrics import metric_row
from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.queries import (
    get_ca_applications,
    get_ca_events,
    get_ca_events_summary,
    get_latest_run_business_summary,
    get_run_business_summaries,
    get_total_dividends,
)
from ihm.services.run_summary import get_run_summary, get_run_summary_metric_items


def render() -> None:
    st.header("📑 Corporate Actions")

    if not db_available():
        render_db_unavailable("Corporate Actions", form_key="ca_db_form")
        return

    # --- Résumé ---
    summary = get_ca_events_summary()
    if summary.empty:
        render_query_diagnostic(
            "Aucun événement corporate action en base. "
            "Les tables `corporate_actions_events` sont peut-être absentes ou vides."
        )
        return

    st.subheader("Résumé par statut / type")
    st.dataframe(summary, use_container_width=True)

    latest_sync = get_latest_run_business_summary(step_key="corporate_actions_sync")
    latest_apply = get_latest_run_business_summary(step_key="corporate_actions_apply")
    latest_run = get_latest_run_business_summary(step_key="corporate_actions_run")
    for title, record in (
        ("🔄 Dernière sync corporate actions", latest_sync),
        ("✅ Dernier apply corporate actions", latest_apply),
        ("🧭 Dernier run corporate actions", latest_run),
    ):
        summary_payload = get_run_summary(record)
        if not summary_payload:
            continue
        st.subheader(title)
        metric_items = get_run_summary_metric_items(record)
        if metric_items:
            metric_row([(label, value, None) for label, value in metric_items[:6]])
        st.caption(str(record.get("summary_caption", "—") or "—"))

    # --- Dividendes cumulés ---
    total_div = get_total_dividends()
    st.metric("💵 Dividendes cumulés", f"${total_div:,.2f}")

    history = get_run_business_summaries(step_keys=["corporate_actions_sync", "corporate_actions_apply", "corporate_actions_run"], limit=20)
    if not history.empty:
        st.subheader("🗃️ Historique résumés corporate actions")
        show_dataframe(history[["step_key", "status", "trade_date", "summary_caption"]], height=240)

    # --- Événements ---
    st.subheader("📋 Événements récents")
    events = get_ca_events()
    show_dataframe(events, height=400)

    # --- Applications ---
    st.subheader("✅ Applications récentes")
    apps = get_ca_applications()
    show_dataframe(apps, height=300)


run_page_if_standalone(__name__, render)


