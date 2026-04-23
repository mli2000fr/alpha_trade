"""ihm/pages/ml.py — ML / Prédictions."""
from __future__ import annotations

import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.queries import get_model_metrics, get_predictions, get_training_runs


def render() -> None:
    st.header("🤖 Model Factory — Entraînement & prédictions")
    st.caption(
        "Cette page affiche les tables DB de synthèse (`model_training_run`, `model_metrics`, `model_predictions`). "
        "Les détails riches de gouvernance multi-modèles (challengers, champion, routes d'artefacts) restent principalement dans les artefacts `config.json` / `metrics.json` par symbole."
    )

    if not db_available():
        render_db_unavailable("ML / Prédictions", form_key="ml_db_form")
        return

    # --- Training runs ---
    st.subheader("🏋️ Runs d'entraînement")
    st.caption("Historique des runs `modelFactory` persistés en base, quel que soit le backend finalement servi en inférence.")
    runs = get_training_runs()
    if runs.empty:
        render_query_diagnostic("Aucun run d'entraînement ML trouvé.")
    else:
        show_dataframe(runs, height=300)

    # --- Métriques ---
    st.subheader("📈 Métriques par symbole")
    st.caption("Vue DB résumée par split (`val`, `test`, `wf`). Les comparatifs détaillés challengers/champion sont stockés dans les artefacts disque du symbole.")
    metrics = get_model_metrics()
    if metrics.empty:
        render_query_diagnostic("Aucune métrique ML disponible.")
    else:
        show_dataframe(metrics, height=400)

    # --- Prédictions ---
    st.subheader("🔮 Prédictions récentes")
    st.caption("La table `model_predictions` reste volontairement compacte. Elle trace la sortie servie, mais pas encore tout le détail de routage du champion sélectionné.")
    preds = get_predictions()
    if preds.empty:
        render_query_diagnostic("Aucune prédiction récente disponible.")
    else:
        show_dataframe(preds, height=400)


run_page_if_standalone(__name__, render)


