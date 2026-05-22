"""ihm/pages/corporate_actions.py — Suivi des corporate actions."""
from __future__ import annotations

import streamlit as st

from ihm.components.run_summary import render_persistent_business_summary
from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.ops_command_panel import render_ops_command_panel
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

    # ---- Sprint S26 (gap P3) — Statut formaté + apply manuel -------------
    with st.expander("⚙️ Lancer une commande corporate_actions", expanded=False):
        st.caption(
            "Exécute directement les sous-commandes CLI `python -m corporate_actions`."
            " Chaque run est tracé dans `artifacts/ihm_pipeline_runs/` (préfixe `ops:`)."
        )
        ops_tabs = st.tabs(["🔄 sync", "📑 status", "✅ apply"])
        with ops_tabs[0]:
            sync_symbols = st.text_input(
                "Symboles explicites (séparés par des virgules, optionnel)",
                value="",
                key="ca_sync_symbols",
            )
            sync_start = st.text_input("start (YYYY-MM-DD, optionnel)", value="", key="ca_sync_start")
            sync_end = st.text_input("end (YYYY-MM-DD, optionnel)", value="", key="ca_sync_end")
            sync_batch_size = st.number_input(
                "Batch size",
                min_value=1,
                max_value=200,
                value=25,
                step=5,
                key="ca_sync_batch_size",
            )
            sync_cross_check = st.selectbox(
                "Cross-check dividendes",
                options=["none", "yahoo"],
                index=0,
                key="ca_sync_cross_check",
            )
            render_ops_command_panel(
                "corporate_actions_sync",
                command_kwargs={
                    "portfolio_only": True,
                    "symbols": sync_symbols,
                    "start": sync_start,
                    "end": sync_end,
                    "batch_size": int(sync_batch_size or 25),
                    "cross_check": sync_cross_check,
                },
            )
        with ops_tabs[1]:
            render_ops_command_panel("corporate_actions_status")
        with ops_tabs[2]:
            apply_as_of = st.text_input(
                "as-of (YYYY-MM-DD, vide = aujourd'hui)",
                value="",
                key="ca_apply_as_of",
            )
            render_ops_command_panel(
                "corporate_actions_apply",
                command_kwargs={"as_of": apply_as_of} if apply_as_of else None,
            )

    latest_sync = get_latest_run_business_summary(step_key="corporate_actions_sync")
    latest_apply = get_latest_run_business_summary(step_key="corporate_actions_apply")
    latest_run = get_latest_run_business_summary(step_key="corporate_actions_run")
    for title, record in (
        ("🧭 Résumé métier persistant — Synchronisation", latest_sync),
        ("🧭 Résumé métier persistant — Application", latest_apply),
        ("🧭 Résumé métier persistant — Workflow", latest_run),
    ):
        render_persistent_business_summary(record, title=title)

    latest_apply_summary = latest_apply.get("run_summary") if isinstance(latest_apply, dict) else None
    if isinstance(latest_apply_summary, dict):
        apply_preflight = latest_apply_summary.get("apply_preflight")
        if isinstance(apply_preflight, dict) and str(apply_preflight.get("status") or "") == "blocked_no_positions_snapshot":
            st.warning(
                str(
                    apply_preflight.get("warning")
                    or "Le dernier apply corporate actions a été bloqué : snapshot positions indisponible."
                )
            )

    latest_sync_summary = latest_sync.get("run_summary") if isinstance(latest_sync, dict) else None
    if isinstance(latest_sync_summary, dict):
        provider = str(latest_sync_summary.get("provider") or "").strip().lower()
        cross_check = str(latest_sync_summary.get("cross_check") or "none").strip().lower()
        if provider == "eodhd":
            st.caption(
                "Scope provider corporate actions : `eodhd` — la sync globale sans univers explicite est bloquée ; "
                "utilisez `portfolio-only` ou une liste `symbols`."
            )
        if cross_check == "yahoo":
            st.caption("Cross-check Yahoo activé sur la dernière synchronisation corporate actions.")

    # --- Dividendes cumulés ---
    total_div = get_total_dividends()
    st.metric("💵 Dividendes cumulés", f"${total_div:,.2f}")

    history = get_run_business_summaries(step_keys=["corporate_actions_sync", "corporate_actions_apply", "corporate_actions_run"], limit=20)
    if not history.empty:
        st.subheader("🗃️ Historique des résumés métier")
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


