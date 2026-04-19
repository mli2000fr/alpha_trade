"""ihm/pages/risk.py — Décisions de risque et portefeuille cible."""
from __future__ import annotations

import streamlit as st

from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.queries import get_portfolio_targets, get_risk_decisions, get_risk_run_ids


def render() -> None:
    st.header("⚖️ Risk Management")

    if not db_available():
        st.error("DB indisponible.")
        return

    # --- Sélecteur de run ---
    run_ids = get_risk_run_ids()
    selected_run = None
    if run_ids:
        selected_run = st.selectbox("Run ID", ["Dernier run"] + run_ids)
        if selected_run == "Dernier run":
            selected_run = run_ids[0] if run_ids else None
    else:
        st.info("Aucun run de risque trouvé dans risk_decisions.")
        return

    # --- Décisions ---
    st.subheader("📋 Décisions de risque")
    decisions = get_risk_decisions(selected_run)
    if not decisions.empty:
        # Colorisation
        if "decision" in decisions.columns:
            accepted = len(decisions[decisions["decision"].str.upper() == "ACCEPTED"])
            rejected = len(decisions[decisions["decision"].str.upper() == "REJECTED"])
            reduced = len(decisions[decisions["decision"].str.upper() == "REDUCED"])
            c1, c2, c3 = st.columns(3)
            c1.metric("🟢 Accepted", accepted)
            c2.metric("🟡 Reduced", reduced)
            c3.metric("🔴 Rejected", rejected)

        # Synthèse par secteur
        if "sector" in decisions.columns and "decision" in decisions.columns:
            with st.expander("Synthèse par secteur"):
                pivot = decisions.groupby(["sector", "decision"]).size().unstack(fill_value=0)
                st.dataframe(pivot, use_container_width=True)

        show_dataframe(decisions, height=400)
    else:
        st.info("Aucune décision pour ce run.")

    # --- Portefeuille cible ---
    st.subheader("🎯 Portefeuille cible")
    targets = get_portfolio_targets(selected_run)
    if not targets.empty:
        cols_show = [c for c in [
            "symbol", "shares", "entry_price", "target_weight", "sector",
            "conviction_score", "sizing_method", "kelly_fraction", "score_used", "score_source",
        ] if c in targets.columns]
        show_dataframe(targets[cols_show] if cols_show else targets, height=400)
    else:
        st.info("Aucun portefeuille cible pour ce run.")

