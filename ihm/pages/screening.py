"""ihm/pages/screening.py — Consultation des scores stock_scores."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.metrics import metric_row
from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.process_registry import list_active_pipeline_runs, load_pipeline_history
from ihm.services.run_summary import build_run_summary_caption, find_latest_run_with_summary
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
    rows: list[dict[str, object]] = []
    for label, step_key in (
        ("Import Alpaca Bar", "import_alpaca_bar"),
        ("Data Sanitizer Daily", "data_sanitizer_daily"),
        ("Workflow complet", "pipeline_workflow"),
    ):
        record = find_latest_run_with_summary(runs, run_kind="workflow" if step_key == "pipeline_workflow" else None, step_keys=None if step_key == "pipeline_workflow" else [step_key])
        if not record:
            continue
        rows.append(
            {
                "scope": label,
                "statut": str(record.get("status", "—") or "—"),
                "run_id": str(record.get("run_id", "—") or "—"),
                "résumé métier": build_run_summary_caption(record),
            }
        )
    return pd.DataFrame(rows)


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


