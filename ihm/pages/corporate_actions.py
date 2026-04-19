"""ihm/pages/corporate_actions.py — Suivi des corporate actions."""
from __future__ import annotations

import streamlit as st

from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.queries import get_ca_applications, get_ca_events, get_ca_events_summary, get_total_dividends


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

    # --- Dividendes cumulés ---
    total_div = get_total_dividends()
    st.metric("💵 Dividendes cumulés", f"${total_div:,.2f}")

    # --- Événements ---
    st.subheader("📋 Événements récents")
    events = get_ca_events()
    show_dataframe(events, height=400)

    # --- Applications ---
    st.subheader("✅ Applications récentes")
    apps = get_ca_applications()
    show_dataframe(apps, height=300)

