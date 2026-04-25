"""ihm/pages/overview.py — Vue d'ensemble."""
from __future__ import annotations

import os
from typing import cast

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable
from ihm.components.run_summary import render_run_summary_block
from ihm.components.metrics import metric_row
from ihm.components.status_badges import env_badge, run_status_badge
from ihm.components.tables import show_dataframe
from ihm.services.process_registry import list_active_pipeline_runs, load_pipeline_history
from ihm.services.screener_artifact_history import (
    SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY,
    build_global_screener_artifact_history,
    build_screener_artifact_history_rows,
    format_screener_artifact_history_label,
    resolve_selected_screener_artifacts_dir,
)
from ihm.services.screener_preferences import (
    load_persisted_selected_screener_artifacts_dir,
    save_persisted_selected_screener_artifacts_dir,
)
from ihm.services.screener_recommendations import load_screener_recommendation_report
from ihm.services.run_summary import (
    build_latest_run_summary_rows,
    find_latest_run_with_summary,
)
from ihm.services.db import db_available, get_last_query_error
from ihm.services.queries import (
    get_candidates_count,
    get_latest_exec_run,
    get_latest_risk_run_id,
    get_top_candidates,
)

SCREENER_ARTIFACT_SELECTBOX_KEY = "overview_screener_artifacts_dir_select"


def _merge_pipeline_runs() -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {str(run["run_id"]): run for run in load_pipeline_history()}
    for run in list_active_pipeline_runs():
        merged[str(run["run_id"])] = run
    return sorted(
        merged.values(),
        key=lambda item: str(item.get("finished_at") or item.get("executed_at") or ""),
        reverse=True,
    )


def _build_pipeline_summary_rows(runs: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(
        build_latest_run_summary_rows(
            runs,
            [
                {"label": "Workflow complet", "run_kind": "workflow"},
                {"label": "Import univers Alpaca", "step_keys": ["import_alpaca_assets"]},
                {"label": "Import Alpaca Bar", "step_keys": ["import_alpaca_bar"]},
                {"label": "Data Sanitizer Daily", "step_keys": ["data_sanitizer_daily"]},
                {"label": "Stock Screener", "step_keys": ["stock_screener"]},
                {"label": "Mise à jour fondamentaux", "step_keys": ["update_sector"]},
                {"label": "Sync Latest Quotes", "step_keys": ["sync_latest_quotes"]},
                {"label": "Sync Earnings Calendar", "step_keys": ["sync_earnings_calendar"]},
                {"label": "Alpha Scanner", "step_keys": ["alpha_scanner"]},
            ],
        )
    )


def _build_screener_objective_rows(report: dict[str, object]) -> pd.DataFrame:
    objective_rows = report.get("objective_rows_df")
    if not isinstance(objective_rows, pd.DataFrame) or objective_rows.empty:
        return pd.DataFrame()

    columns = [
        ("objective", "objectif"),
        ("objective_label", "label"),
        ("scenario_name", "scénario"),
        ("objective_scope", "périmètre"),
        ("objective_score", "score objectif"),
        ("overall_score", "score global"),
    ]
    available_columns = [column for column, _ in columns if column in objective_rows.columns]
    preview = objective_rows.loc[:, available_columns].copy()
    return preview.rename(columns={column: label for column, label in columns if column in preview.columns})


def _build_screener_objective_metrics(report: dict[str, object]) -> list[tuple[str, str, str | None]]:
    rows = _build_screener_objective_rows(report)
    if rows.empty:
        return []
    metrics: list[tuple[str, str, str | None]] = []
    for _, row in rows.iterrows():
        metrics.append((str(row.get("label") or row.get("objectif") or "Objectif"), str(row.get("scénario") or "—"), str(row.get("périmètre") or "global")))
    return metrics


def _build_screener_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(build_screener_artifact_history_rows(history_entries))


def render() -> None:
    st.header("🏠 Vue d'ensemble")

    # --- Environnement ---
    with st.expander("Variables d'environnement", expanded=False):
        for var in ("LOGIN_DB", "PASSWORD_DB", "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "FINNHUB_API_KEY"):
            st.markdown(env_badge(var, os.getenv(var)))

    # --- Santé DB ---
    if not db_available():
        render_db_unavailable("Vue d'ensemble", form_key="overview_db_form")
        return

    st.success("🟢 Connexion DB OK")

    # --- KPI ---
    candidates = get_candidates_count()
    risk_run = get_latest_risk_run_id()
    exec_df = get_latest_exec_run()

    if get_last_query_error() and exec_df.empty and not risk_run and candidates == 0:
        st.warning(get_last_query_error())
        st.caption("La connexion DB existe, mais certaines tables attendues par la vue d'ensemble semblent absentes ou incompatibles.")

    latest_exec = exec_df.iloc[0].to_dict() if not exec_df.empty else None
    exec_run_id = str(latest_exec["exec_run_id"]) if latest_exec is not None else "—"
    exec_status = str(latest_exec["status"]) if latest_exec is not None else None
    total_filled = int(latest_exec["total_filled"]) if latest_exec is not None else 0

    candidates_value = int(candidates)
    risk_run_value = risk_run or "—"
    metrics = cast(
        list[tuple[str, str | int | float, str | None]],
        [
            ("Candidats", candidates_value, None),
            ("Dernier risk_run_id", risk_run_value, None),
            ("Dernier exec_run_id", exec_run_id, None),
            ("Fills dernier run", total_filled, None),
        ],
    )
    metric_row(metrics)

    # --- Alertes ---
    if candidates == 0:
        st.warning("⚠️ Aucun candidat (`is_candidate=1`) dans stock_scores.")
    if exec_status and exec_status.upper() not in ("COMPLETED", "SUCCESS"):
        st.warning(f"⚠️ Dernière exécution : {run_status_badge(exec_status)}")

    pipeline_runs = _merge_pipeline_runs()
    latest_workflow = find_latest_run_with_summary(pipeline_runs, run_kind="workflow")
    render_run_summary_block(latest_workflow, title="🧭 Dernier workflow pipeline", max_metrics=4)

    summary_rows = _build_pipeline_summary_rows(pipeline_runs)
    if not summary_rows.empty:
        st.subheader("📋 Résumés pipeline récents")
        show_dataframe(summary_rows)

    screener_history = build_global_screener_artifact_history()
    session_selected_dir = str(st.session_state.get(SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY, "") or "").strip()
    persisted_selected_dir = load_persisted_selected_screener_artifacts_dir()
    preferred_dir = session_selected_dir or persisted_selected_dir
    selected_screener_dir, screener_entry_map = resolve_selected_screener_artifacts_dir(screener_history, preferred_dir)
    restored_from_persistence = not session_selected_dir and bool(persisted_selected_dir)
    if screener_entry_map:
        st.subheader("🗂️ Source screener active")
        st.session_state[SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY] = selected_screener_dir
        if st.session_state.get(SCREENER_ARTIFACT_SELECTBOX_KEY) != selected_screener_dir:
            st.session_state[SCREENER_ARTIFACT_SELECTBOX_KEY] = selected_screener_dir
        selected_screener_dir = st.selectbox(
            "Répertoire d'artefacts screener",
            options=list(screener_entry_map.keys()),
            format_func=lambda value: format_screener_artifact_history_label(screener_entry_map[value]),
            index=list(screener_entry_map.keys()).index(selected_screener_dir),
            key=SCREENER_ARTIFACT_SELECTBOX_KEY,
        )
        st.session_state[SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY] = selected_screener_dir
        if persisted_selected_dir != selected_screener_dir:
            save_persisted_selected_screener_artifacts_dir(selected_screener_dir)
        selected_entry = screener_entry_map[selected_screener_dir]
        if restored_from_persistence:
            st.caption("Préférence restaurée depuis la dernière session IHM.")
        st.caption(
            f"Source partagée avec `Screening` · Couverture : {selected_entry.get('coverage_label', 'Période non renseignée')} · "
            f"MAJ : {selected_entry.get('updated_at_label', 'inconnue')}"
        )
        history_df = _build_screener_history_dataframe(screener_history)
        if not history_df.empty:
            with st.expander("🗃️ Historique global des artefacts screener", expanded=False):
                st.dataframe(history_df, use_container_width=True, hide_index=True)

    screener_report = load_screener_recommendation_report(selected_screener_dir)
    screener_objective_rows = _build_screener_objective_rows(screener_report)
    if not screener_objective_rows.empty:
        st.subheader("🎯 Calibration screener")
        st.caption(
            f"Derniers objectifs exportés depuis `{screener_report.get('artifacts_dir')}` · "
            f"Période : {screener_report.get('coverage_label', 'Période non renseignée')} · "
            f"MAJ : {screener_report.get('updated_at_label', 'inconnue')}"
        )
        screener_metrics = _build_screener_objective_metrics(screener_report)
        if screener_metrics:
            metric_row(screener_metrics)
        show_dataframe(screener_objective_rows, height=220)

    # --- Top candidats ---
    st.subheader("🏆 Top 10 candidats par score sentiment")
    show_dataframe(get_top_candidates(10))


run_page_if_standalone(__name__, render)


