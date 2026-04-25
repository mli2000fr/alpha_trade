"""ihm/pages/screening.py — Consultation des scores stock_scores."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.metrics import metric_row
from ihm.components.tables import show_dataframe
from ihm.services.screener_recommendations import load_screener_recommendation_report
from ihm.services.db import db_available
from ihm.services.process_registry import list_active_pipeline_runs, load_pipeline_history
from ihm.services.run_summary import build_latest_run_summary_rows
from ihm.services.queries import get_stock_scores


def _merge_pipeline_runs() -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {str(run["run_id"]): run for run in load_pipeline_history()}
    for run in list_active_pipeline_runs():
        merged[str(run["run_id"])] = run
    return sorted(
        merged.values(),
        key=lambda item: str(item.get("finished_at") or item.get("executed_at") or ""),
        reverse=True,
    )


def _build_quality_summary_rows(runs: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(
        build_latest_run_summary_rows(
            runs,
            [
                {"label": "Import Alpaca Bar", "step_keys": ["import_alpaca_bar"]},
                {"label": "Data Sanitizer Daily", "step_keys": ["data_sanitizer_daily"]},
                {"label": "Workflow complet", "run_kind": "workflow"},
            ],
        )
    )


def _build_objective_recommendation_rows(report: dict[str, object]) -> pd.DataFrame:
    objective_rows = report.get("objective_rows_df")
    if not isinstance(objective_rows, pd.DataFrame) or objective_rows.empty:
        return pd.DataFrame()

    columns = [
        ("objective_label", "Objectif"),
        ("scenario_name", "Scénario recommandé"),
        ("objective_scope", "Périmètre"),
        ("objective_score", "Score objectif"),
        ("overall_score", "Score global"),
        ("reason", "Pourquoi"),
    ]
    available_columns = [column for column, _ in columns if column in objective_rows.columns]
    formatted = objective_rows.loc[:, available_columns].copy()
    return formatted.rename(columns={column: label for column, label in columns if column in formatted.columns})


def _build_objective_metric_cards(report: dict[str, object]) -> list[tuple[str, str, str | None]]:
    objective_rows = report.get("objective_rows_df")
    if not isinstance(objective_rows, pd.DataFrame) or objective_rows.empty:
        return []

    cards: list[tuple[str, str, str | None]] = []
    for _, row in objective_rows.iterrows():
        cards.append(
            (
                str(row.get("objective_label") or row.get("objective") or "Objectif"),
                str(row.get("scenario_name") or "—"),
                str(row.get("objective_scope") or "global"),
            )
        )
    return cards


def _render_objective_recommendations() -> None:
    report = load_screener_recommendation_report()
    if not bool(report.get("available")):
        st.info("Aucune recommandation screener phase 7/8 détectée pour le moment.")
        artifacts_dir = report.get("artifacts_dir")
        if artifacts_dir:
            st.caption(f"Répertoire attendu : `{artifacts_dir}`")
        return

    st.subheader("🎯 Recommandations screener par objectif")
    st.caption(
        "Lecture directe des artefacts `recommend-screener` pour exposer les profils robuste / offensif / bear / exécutable dans l'IHM."
    )
    st.caption(
        "Pour recalculer ces artefacts depuis l'IHM, utilise la page `🧪 Backtesting` puis les onglets `Diagnose screener` ou `Recommend screener`."
    )
    st.caption(
        f"Artefacts : `{report.get('artifacts_dir')}` · Période : {report.get('coverage_label', 'Période non renseignée')} · "
        f"MAJ : {report.get('updated_at_label', 'inconnue')}"
    )

    metric_cards = _build_objective_metric_cards(report)
    if metric_cards:
        metric_row(metric_cards)

    objective_rows = _build_objective_recommendation_rows(report)
    if not objective_rows.empty:
        show_dataframe(objective_rows, "Leaders phase 7 par objectif", height=240)

    leaderboard = report.get("leaderboard_df")
    if isinstance(leaderboard, pd.DataFrame) and not leaderboard.empty:
        show_dataframe(leaderboard, "Classement détaillé phase 7", height=320)

    errors = report.get("errors")
    if isinstance(errors, list) and errors:
        with st.expander("ℹ️ Détails de chargement des artefacts", expanded=False):
            for error in errors:
                st.caption(f"- {error}")


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

    quality_rows = _build_quality_summary_rows(_merge_pipeline_runs())
    if not quality_rows.empty:
        st.subheader("🛡️ Contexte pipeline & qualité amont")
        show_dataframe(quality_rows)

    _render_objective_recommendations()

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


run_page_if_standalone(__name__, render)


