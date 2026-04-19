"""ihm/pages/ml.py — ML / Prédictions."""
from __future__ import annotations

import streamlit as st

from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.queries import get_model_metrics, get_predictions, get_training_runs


def render() -> None:
    st.header("🤖 Model Factory — ML / Prédictions")

    if not db_available():
        st.error("DB indisponible.")
        return

    # --- Training runs ---
    st.subheader("🏋️ Runs d'entraînement")
    runs = get_training_runs()
    show_dataframe(runs, height=300)

    # --- Métriques ---
    st.subheader("📈 Métriques par symbole")
    metrics = get_model_metrics()
    show_dataframe(metrics, height=400)

    # --- Prédictions ---
    st.subheader("🔮 Prédictions récentes")
    preds = get_predictions()
    show_dataframe(preds, height=400)

