"""ihm/pages/overview.py — Vue d'ensemble."""
from __future__ import annotations

import os

import streamlit as st

from ihm.components.metrics import metric_row
from ihm.components.status_badges import env_badge, run_status_badge
from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.queries import (
    get_candidates_count,
    get_latest_exec_run,
    get_latest_risk_run_id,
    get_top_candidates,
)


def render() -> None:
    st.header("🏠 Vue d'ensemble")

    # --- Environnement ---
    with st.expander("Variables d'environnement", expanded=False):
        for var in ("LOGIN_DB", "PASSWORD_DB", "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "FINNHUB_API_KEY"):
            st.markdown(env_badge(var, os.getenv(var)))

    # --- Santé DB ---
    if not db_available():
        st.error("🔴 Base de données indisponible. Vérifiez LOGIN_DB / PASSWORD_DB et que MySQL est démarré.")
        return

    st.success("🟢 Connexion DB OK")

    # --- KPI ---
    candidates = get_candidates_count()
    risk_run = get_latest_risk_run_id()
    exec_df = get_latest_exec_run()

    exec_run_id = str(exec_df.iloc[0]["exec_run_id"]) if not exec_df.empty else "—"
    exec_status = str(exec_df.iloc[0]["status"]) if not exec_df.empty else None
    total_filled = int(exec_df.iloc[0]["total_filled"]) if not exec_df.empty else 0

    metric_row([
        ("Candidats", candidates, None),
        ("Dernier risk_run_id", risk_run or "—", None),
        ("Dernier exec_run_id", exec_run_id, None),
        ("Fills dernier run", total_filled, None),
    ])

    # --- Alertes ---
    if candidates == 0:
        st.warning("⚠️ Aucun candidat (`is_candidate=1`) dans stock_scores.")
    if exec_status and exec_status.upper() not in ("COMPLETED", "SUCCESS"):
        st.warning(f"⚠️ Dernière exécution : {run_status_badge(exec_status)}")

    # --- Top candidats ---
    st.subheader("🏆 Top 10 candidats par score sentiment")
    show_dataframe(get_top_candidates(10))

