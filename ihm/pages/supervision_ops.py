"""ihm/pages/supervision_ops.py — Supervision opérationnelle cross-run."""
from __future__ import annotations
import streamlit as st
from ihm.components.db_controls import render_db_unavailable
from ihm.components.metrics import metric_row
from ihm.components.tables import show_dataframe
from ihm.pages import run_page_if_standalone
from ihm.services.db import db_available
from ihm.services.ops_supervision import build_ops_supervision_snapshot
def render() -> None:
    st.header("🛟 Supervision Ops")
    st.caption(
        "Vue dédiée à la supervision opérationnelle : état des services, heartbeats stale, derniers runs critiques et alertes synthétiques."
    )
    st.info(
        "Cette page supervise l'exécution et la santé des services. L'installation Task Scheduler / NSSM, la gestion des secrets Windows et le packaging runtime restent pilotés par les scripts PowerShell."
    )
    if not db_available():
        render_db_unavailable("Supervision Ops", form_key="ops_supervision_db_form")
        return
    account_id = st.session_state.get("selected_account_id")
    snapshot = build_ops_supervision_snapshot(account_id=account_id)
    metrics = dict(snapshot.get("metrics", {}))
    metric_row([
        ("Services suivis", int(metrics.get("services_monitored", 0) or 0), None),
        ("Services stale", int(metrics.get("services_stale", 0) or 0), None),
        ("Services à surveiller", int(metrics.get("services_warn", 0) or 0), None),
        ("Alertes critiques", int(metrics.get("critical_alerts", 0) or 0), None),
        ("Runs IHM actifs", int(metrics.get("active_runs", 0) or 0), None),
    ])
    alerts = list(snapshot.get("alerts", []))
    with st.container(border=True):
        st.subheader("🚨 Alertes synthétiques")
        if not alerts:
            st.success("🟢 Aucun signal d'alerte critique détecté pour le moment.")
        else:
            for alert in alerts:
                severity = str(alert.get("severity", "info") or "info")
                message = str(alert.get("message", "") or "").strip()
                if not message:
                    continue
                if severity == "error":
                    st.error(message)
                elif severity == "warn":
                    st.warning(message)
                else:
                    st.info(message)
    with st.container(border=True):
        st.subheader("🫀 État des services")
        st.caption("Le heartbeat est colorisé automatiquement en vert / orange / rouge selon sa fraîcheur et le statut du service.")
        show_dataframe(snapshot.get("service_health"), height=280)
    with st.container(border=True):
        st.subheader("🧭 Derniers runs critiques")
        st.caption("Vue synthétique des derniers runs métier structurants pour l'opérationnel quotidien.")
        show_dataframe(snapshot.get("latest_runs"), height=260)
    with st.container(border=True):
        st.subheader("🏃 Runs IHM en cours")
        st.caption("Pipelines ou workflows lancés depuis l'IHM encore actifs au moment de la consultation.")
        show_dataframe(snapshot.get("active_runs"), height=220)
run_page_if_standalone(__name__, render)
