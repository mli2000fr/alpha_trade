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
ML_AUDIT_FILTER_SOURCE_LIMIT = 500


def _sorted_non_empty_strings(values: list[object], *, reverse: bool = False) -> list[str]:
    normalized = {str(value).strip() for value in values if str(value).strip()}
    return sorted(normalized, reverse=reverse)


def _build_prediction_audit_filter_options(
    audit_df: pd.DataFrame,
    governance_df: pd.DataFrame,
) -> dict[str, list[str]]:
    audit_run_ids = audit_df["run_id"].tolist() if "run_id" in audit_df.columns else []
    governance_run_ids = governance_df["run_id"].tolist() if "run_id" in governance_df.columns else []
    audit_selection_modes = (
        audit_df["governance_selection_mode"].tolist() if "governance_selection_mode" in audit_df.columns else []
    )
    governance_selection_modes = governance_df["selection_mode"].tolist() if "selection_mode" in governance_df.columns else []
    return {
        "governance_link_statuses": _sorted_non_empty_strings(
            audit_df["governance_link_status"].tolist() if "governance_link_status" in audit_df.columns else []
        ),
        "selection_modes": _sorted_non_empty_strings(audit_selection_modes + governance_selection_modes),
        "served_models": _sorted_non_empty_strings(audit_df["served_model"].tolist() if "served_model" in audit_df.columns else []),
        "run_ids": _sorted_non_empty_strings(audit_run_ids + governance_run_ids, reverse=True),
    }


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
    symbol_filter = selected_symbol_for_db if isinstance(selected_symbol_for_db, str) else None

    governance_filter_source = get_model_governance(limit=ML_AUDIT_FILTER_SOURCE_LIMIT, symbol=symbol_filter)
    prediction_audit_filter_source = get_prediction_governance_audit(limit=ML_AUDIT_FILTER_SOURCE_LIMIT, symbol=symbol_filter)
    filter_options = _build_prediction_audit_filter_options(prediction_audit_filter_source, governance_filter_source)

    st.subheader("🎛️ Filtres d'audit DB")
    st.caption(
        "Ces filtres pilotent les vues `model_governance`, l'audit joint `model_predictions ↔ model_governance` "
        "et, quand pertinent, la table des prédictions récentes."
    )
    col1, col2, col3, col4 = st.columns(4)
    selected_link_statuses = col1.multiselect(
        "governance_link_status",
        options=filter_options["governance_link_statuses"],
        key="ml_audit_filter_link_status",
    )
    selected_selection_modes = col2.multiselect(
        "selection_mode",
        options=filter_options["selection_modes"],
        key="ml_audit_filter_selection_mode",
    )
    selected_served_models = col3.multiselect(
        "served_model",
        options=filter_options["served_models"],
        key="ml_audit_filter_served_model",
    )
    selected_run_ids = col4.multiselect(
        "run_id",
        options=filter_options["run_ids"],
        key="ml_audit_filter_run_id",
    )

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
    governance = get_model_governance(
        limit=ML_AUDIT_FILTER_SOURCE_LIMIT,
        symbol=symbol_filter,
        run_ids=selected_run_ids or None,
        selection_modes=selected_selection_modes or None,
    )
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
        limit=ML_AUDIT_FILTER_SOURCE_LIMIT,
        symbol=symbol_filter,
        run_ids=selected_run_ids or None,
        selection_modes=selected_selection_modes or None,
        served_models=selected_served_models or None,
        governance_link_statuses=selected_link_statuses or None,
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
    preds = get_predictions(
        limit=ML_AUDIT_FILTER_SOURCE_LIMIT,
        symbol=symbol_filter,
        run_ids=selected_run_ids or None,
        served_models=selected_served_models or None,
    )
    if preds.empty:
        render_query_diagnostic("Aucune prédiction récente disponible.")
    else:
        show_dataframe(preds, height=400)


run_page_if_standalone(__name__, render)


