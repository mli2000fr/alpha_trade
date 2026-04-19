"""ihm/pages/screening.py — Consultation des scores stock_scores."""
from __future__ import annotations

import streamlit as st

from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.metrics import metric_row
from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.queries import get_stock_scores


def render() -> None:
    st.header("📊 Screening — Stock Scores")

    if not db_available():
        render_db_unavailable("Screening", form_key="screening_db_form")
        return

    df = get_stock_scores()
    if df.empty:
        render_query_diagnostic("Aucune donnée dans `stock_scores`.")
        return

    # --- KPI ---
    total = len(df)
    candidates = int(df["is_candidate"].sum()) if "is_candidate" in df.columns else 0
    sectors = df["sector"].nunique() if "sector" in df.columns else 0
    metric_row([
        ("Total symboles", total, None),
        ("Candidats", candidates, None),
        ("Secteurs", sectors, None),
    ])

    # --- Filtres ---
    st.subheader("Filtres")
    col1, col2, col3 = st.columns(3)
    with col1:
        symbol_filter = st.text_input("Symbole", "").upper().strip()
    with col2:
        sector_list = ["Tous"] + sorted(df["sector"].dropna().unique().tolist()) if "sector" in df.columns else ["Tous"]
        sector_filter = st.selectbox("Secteur", sector_list)
    with col3:
        candidates_only = st.checkbox("Candidats uniquement", value=False)

    col4, col5 = st.columns(2)
    with col4:
        min_score = st.slider("Score minimum (total_score)", 0.0, 1.0, 0.0, 0.01)
    with col5:
        sentiment_only = st.checkbox("Sentiment actif uniquement", value=False)

    # --- Appliquer filtres ---
    filtered = df.copy()
    if symbol_filter:
        filtered = filtered[filtered["symbol"].str.contains(symbol_filter, case=False, na=False)]
    if sector_filter != "Tous":
        filtered = filtered[filtered["sector"] == sector_filter]
    if candidates_only:
        filtered = filtered[filtered["is_candidate"] == 1]
    if min_score > 0 and "total_score" in filtered.columns:
        filtered = filtered[filtered["total_score"] >= min_score]
    if sentiment_only and "signal_active" in filtered.columns:
        filtered = filtered[filtered["signal_active"] == 1]

    show_dataframe(filtered, f"Résultats ({len(filtered)} lignes)", height=500)

