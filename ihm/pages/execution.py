"""ihm/pages/execution.py — Suivi des runs d'exécution."""
from __future__ import annotations

import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.metrics import metric_row
from ihm.components.status_badges import run_status_badge
from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.queries import (
    get_broker_positions,
    get_execution_events,
    get_execution_fills,
    get_execution_runs,
)


def render() -> None:
    st.header("🚀 Execution Engine")

    if not db_available():
        render_db_unavailable("Execution Engine", form_key="execution_db_form")
        return

    account_id = st.session_state.get("selected_account_id")
    runs = get_execution_runs(account_id=account_id)
    if runs.empty:
        render_query_diagnostic("Aucun run d'exécution trouvé.")
        return

    # --- Sélection du run ---
    run_ids = runs["exec_run_id"].tolist()
    selected = st.selectbox("Exec Run ID", run_ids)

    row = runs[runs["exec_run_id"] == selected].iloc[0]
    status = str(row.get("status", ""))

    # --- KPI ---
    metric_row([
        ("Statut", run_status_badge(status), None),
        ("Targets", int(row.get("total_targets", 0)), None),
        ("Submitted", int(row.get("total_submitted", 0)), None),
        ("Filled", int(row.get("total_filled", 0)), None),
    ])

    if row.get("error_message"):
        st.error(f"Erreur : {row['error_message']}")

    # --- Runs récents ---
    with st.expander("Historique des runs", expanded=False):
        show_dataframe(runs, height=300)

    # --- Événements ---
    st.subheader("📝 Événements")
    events = get_execution_events(selected)
    show_dataframe(events, height=300)

    # --- Fills ---
    st.subheader("💰 Fills")
    fills = get_execution_fills(selected)
    if not fills.empty and "slippage_bps" in fills.columns:
        avg_slip = fills["slippage_bps"].mean()
        st.metric("Slippage moyen (bps)", f"{avg_slip:.1f}")
    show_dataframe(fills, height=300)

    # --- Positions broker ---
    st.subheader("📦 Positions broker (dernier snapshot)")
    show_dataframe(get_broker_positions(account_id=account_id), height=300)


run_page_if_standalone(__name__, render)


