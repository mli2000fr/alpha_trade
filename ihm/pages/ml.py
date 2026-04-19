"""ihm/pages/ml.py — ML / Prédictions."""
from __future__ import annotations

import streamlit as st

from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.queries import get_model_metrics, get_predictions, get_training_runs


def render() -> None:
    st.header("🤖 Model Factory — ML / Prédictions")

    if not db_available():
        render_db_unavailable("ML / Prédictions", form_key="ml_db_form")
        return

    # --- Training runs ---
    st.subheader("🏋️ Runs d'entraînement")
    runs = get_training_runs()
    if runs.empty:
        render_query_diagnostic("Aucun run d'entraînement ML trouvé.")
    else:
        show_dataframe(runs, height=300)

    # --- Métriques ---
    st.subheader("📈 Métriques par symbole")
    metrics = get_model_metrics()
    if metrics.empty:
        render_query_diagnostic("Aucune métrique ML disponible.")
    else:
        show_dataframe(metrics, height=400)

    # --- Prédictions ---
    st.subheader("🔮 Prédictions récentes")
    preds = get_predictions()
    if preds.empty:
        render_query_diagnostic("Aucune prédiction récente disponible.")
    else:
        show_dataframe(preds, height=400)

