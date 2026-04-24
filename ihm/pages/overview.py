"""ihm/pages/overview.py — Vue d'ensemble."""
from __future__ import annotations

import os
from typing import cast

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable
from ihm.components.metrics import metric_row
from ihm.components.status_badges import env_badge, run_status_badge
from ihm.components.tables import show_dataframe
from ihm.services.process_registry import list_active_pipeline_runs, load_pipeline_history
from ihm.services.run_summary import (
    build_run_summary_caption,
    find_latest_run_with_summary,
    get_run_summary,
)
from ihm.services.db import db_available, get_last_query_error
from ihm.services.queries import (
    get_candidates_count,
    get_latest_exec_run,
    get_latest_risk_run_id,
    get_top_candidates,
)


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
    latest_workflow = find_latest_run_with_summary(runs, run_kind="workflow")
    latest_import = find_latest_run_with_summary(runs, step_keys=["import_alpaca_bar"])
    latest_sanitizer = find_latest_run_with_summary(runs, step_keys=["data_sanitizer_daily"])

    rows: list[dict[str, object]] = []
    for label, record in (
        ("Workflow complet", latest_workflow),
        ("Import Alpaca Bar", latest_import),
        ("Data Sanitizer Daily", latest_sanitizer),
    ):
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
    workflow_summary = get_run_summary(latest_workflow)
    if workflow_summary:
        st.subheader("🧭 Dernier workflow pipeline")
        workflow_metrics = [
            ("Étapes résumées", int(workflow_summary.get("workflow_steps_with_summary", 0)), None),
            ("Cibles", int(workflow_summary.get("targeted_symbols", 0)), None),
            ("Succès", int(workflow_summary.get("successful_symbols", 0)), None),
            ("Échecs", int(workflow_summary.get("failed_symbols", 0)), None),
        ]
        metric_row(workflow_metrics)
        st.caption(build_run_summary_caption(latest_workflow))

    summary_rows = _build_pipeline_summary_rows(pipeline_runs)
    if not summary_rows.empty:
        st.subheader("📋 Résumés pipeline récents")
        show_dataframe(summary_rows)

    # --- Top candidats ---
    st.subheader("🏆 Top 10 candidats par score sentiment")
    show_dataframe(get_top_candidates(10))


run_page_if_standalone(__name__, render)


