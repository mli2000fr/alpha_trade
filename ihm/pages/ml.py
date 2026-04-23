"""ihm/pages/ml.py — ML / Prédictions."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_connection_form, render_query_diagnostic
from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.ml_artifacts import get_model_artifacts_dir, list_ml_artifact_symbols, load_ml_artifact_report
from ihm.services.queries import (
    get_model_governance,
    get_model_metrics,
    get_prediction_governance_audit,
    get_prediction_symbols,
    get_predictions,
    get_training_runs,
)


ML_SELECTED_SYMBOL_KEY = "ihm_ml_selected_symbol"


def _summarize_prediction_governance_audit(audit_df: pd.DataFrame) -> dict[str, object]:
    if audit_df.empty:
        return {
            "latest_served_model": "—",
            "latest_governance_champion": "—",
            "latest_link_status": "—",
            "mismatch_count": 0,
        }
    latest = audit_df.iloc[0]
    status_series = audit_df["governance_link_status"] if "governance_link_status" in audit_df.columns else pd.Series(dtype="object")
    mismatch_count = int((status_series != "aligned").sum()) if not status_series.empty else 0
    return {
        "latest_served_model": latest.get("served_model", "—") or "—",
        "latest_governance_champion": latest.get("governance_champion_model", "—") or "—",
        "latest_link_status": latest.get("governance_link_status", "—") or "—",
        "mismatch_count": mismatch_count,
    }


def render() -> None:
    st.header("🤖 Model Factory — Entraînement & prédictions")
    st.caption(
        "Cette page combine les artefacts `modelFactory` et les tables DB de synthèse/audit "
        "(`model_training_run`, `model_metrics`, `model_governance`, `model_predictions`)."
    )

    st.subheader("🧭 Gouvernance & artefacts de serving")
    artifacts_dir = get_model_artifacts_dir()
    st.caption(
        f"Cette section lit directement les artefacts `modelFactory` sous `{artifacts_dir}` afin d'exposer le champion servi, les challengers et les routes d'inférence."
    )

    artifact_symbols = list_ml_artifact_symbols()
    db_symbols = get_prediction_symbols() if db_available() else []
    symbols = sorted(set(artifact_symbols) | set(db_symbols), key=lambda sym: (sym.startswith("__"), sym))
    if not symbols:
        st.info("Aucun artefact `modelFactory` détecté pour le moment. Lancez d'abord `ML Train` ou vérifiez le dossier des artefacts.")
    else:
        preselected_symbol = st.session_state.get(ML_SELECTED_SYMBOL_KEY)
        if preselected_symbol in symbols:
            st.session_state[ML_SELECTED_SYMBOL_KEY] = preselected_symbol
        elif ML_SELECTED_SYMBOL_KEY not in st.session_state:
            st.session_state[ML_SELECTED_SYMBOL_KEY] = symbols[0]
        selected_symbol = st.selectbox(
            "Symbole à inspecter (artefacts)",
            options=symbols,
            format_func=lambda sym: f"{sym} — modèle global" if sym.startswith("__") else sym,
            key=ML_SELECTED_SYMBOL_KEY,
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

    selected_symbol_for_db = st.session_state.get(ML_SELECTED_SYMBOL_KEY) if symbols else None

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

    # --- Gouvernance challengers / champion ---
    st.subheader("🏆 Gouvernance challengers / champion")
    st.caption(
        "La table `model_governance` persiste par run et par symbole le ranking challengers/champion, "
        "le backend d'inférence, l'éligibilité de sélection et les scores utiles à l'audit quotidien."
    )
    governance = get_model_governance(symbol=selected_symbol_for_db if isinstance(selected_symbol_for_db, str) else None)
    if governance.empty:
        render_query_diagnostic("Aucune gouvernance ML persistée en base pour le moment.")
    else:
        show_dataframe(governance, height=360)

    # --- Audit serving ↔ gouvernance ---
    st.subheader("🔗 Audit serving ↔ gouvernance")
    st.caption(
        "Cette vue relie chaque ligne de `model_predictions` au snapshot `model_governance` du même `run_id` et `symbol` "
        "afin d'expliquer quel champion a été servi et si la prédiction est alignée avec la gouvernance persistée."
    )
    prediction_audit = get_prediction_governance_audit(
        symbol=selected_symbol_for_db if isinstance(selected_symbol_for_db, str) else None
    )
    if prediction_audit.empty:
        render_query_diagnostic("Aucun audit joint prédiction/gouvernance disponible.")
    else:
        audit_summary = _summarize_prediction_governance_audit(prediction_audit)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Dernier modèle servi", str(audit_summary["latest_served_model"]))
        col2.metric("Champion gouvernance", str(audit_summary["latest_governance_champion"]))
        col3.metric("Statut du lien", str(audit_summary["latest_link_status"]))
        col4.metric("Lignes à investiguer", int(audit_summary["mismatch_count"]))
        if int(audit_summary["mismatch_count"]) > 0:
            st.warning(
                "Certaines prédictions servies ne sont pas parfaitement alignées avec le snapshot de gouvernance persistant. "
                "Vérifiez la colonne `governance_link_status` ci-dessous."
            )
        show_dataframe(prediction_audit, height=360)

    # --- Prédictions ---
    st.subheader("🔮 Prédictions récentes")
    st.caption("La table `model_predictions` contient désormais les champs d'audit de serving utiles au quotidien : `selected_model`, `decision_threshold`, `signal_label`, `calibration_method`.")
    preds = get_predictions(symbol=selected_symbol_for_db if isinstance(selected_symbol_for_db, str) else None)
    if preds.empty:
        render_query_diagnostic("Aucune prédiction récente disponible.")
    else:
        show_dataframe(preds, height=400)


run_page_if_standalone(__name__, render)


