"""ihm/pages/ml.py — ML / Prédictions."""
from __future__ import annotations

import json

import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_connection_form, render_query_diagnostic
from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.ml_artifacts import get_model_artifacts_dir, list_ml_artifact_symbols, load_ml_artifact_report
from ihm.services.queries import get_model_metrics, get_predictions, get_training_runs


def render() -> None:
    st.header("🤖 Model Factory — Entraînement & prédictions")
    st.caption(
        "Cette page affiche les tables DB de synthèse (`model_training_run`, `model_metrics`, `model_predictions`). "
        "Les détails riches de gouvernance multi-modèles (challengers, champion, routes d'artefacts) restent principalement dans les artefacts `config.json` / `metrics.json` par symbole."
    )

    st.subheader("🧭 Gouvernance & artefacts de serving")
    artifacts_dir = get_model_artifacts_dir()
    st.caption(
        f"Cette section lit directement les artefacts `modelFactory` sous `{artifacts_dir}` afin d'exposer le champion servi, les challengers et les routes d'inférence."
    )

    symbols = list_ml_artifact_symbols()
    if not symbols:
        st.info("Aucun artefact `modelFactory` détecté pour le moment. Lancez d'abord `ML Train` ou vérifiez le dossier des artefacts.")
    else:
        selected_symbol = st.selectbox(
            "Symbole à inspecter (artefacts)",
            options=symbols,
            format_func=lambda sym: f"{sym} — modèle global" if sym.startswith("__") else sym,
        )
        report = load_ml_artifact_report(selected_symbol)
        for error in report["errors"]:
            st.warning(error)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Symbole", str(report["symbol"]))
        col2.metric("Champion servi", str(report["selected_model"] or "—"))
        col3.metric("Mode de sélection", str(report["selection_mode"] or "—"))
        threshold = report["selected_decision_threshold"]
        col4.metric("Decision threshold", f"{float(threshold):.2f}" if threshold is not None else "—")

        champion = report["champion"] or {}
        st.caption(
            f"Run ID : `{report['run_id'] or '—'}` | "
            f"Métrique champion : `{champion.get('selection_metric', '—')}` | "
            f"Score champion : `{champion.get('selection_score', '—')}`"
        )
        st.caption(
            f"Config : `{report['config_path']}` | Metrics : `{report['metrics_path']}`"
        )

        st.markdown("**Routes d'inférence**")
        show_dataframe(report["routes_df"], height=260)

        st.markdown("**Ranking challengers**")
        show_dataframe(report["ranking_df"], height=260)

        with st.expander("📄 Manifestes bruts (config / metrics)", expanded=False):
            if report["config"]:
                st.markdown("**config.json**")
                st.code(json.dumps(report["config"], indent=2, default=str), language="json")
            if report["metrics"]:
                st.markdown("**metrics.json**")
                st.code(json.dumps(report["metrics"], indent=2, default=str), language="json")

    if not db_available():
        st.warning("La connexion MySQL est indisponible. Les tableaux SQL ci-dessous ne peuvent pas être chargés, mais la lecture des artefacts locaux reste disponible.")
        render_db_connection_form("ml_db_form")
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


