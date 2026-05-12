"""ihm/pages/overview.py — Vue d'ensemble."""
from __future__ import annotations

import os
from typing import cast

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.alpha_scanner_dependency import render_alpha_scanner_dependency_panel
from ihm.components.db_controls import render_db_unavailable
from ihm.components.screener_artifacts import (
    build_screener_artifact_history_dataframe,
    render_shared_screener_artifact_selector,
)
from ihm.components.run_summary import render_run_summary_block
from ihm.components.metrics import metric_row
from ihm.components.status_badges import env_badge, run_status_badge
from ihm.components.tables import show_dataframe
from ihm.components.symbol_table import render_symbol_table
from ihm.services.process_registry import list_active_pipeline_runs, load_pipeline_history
from ihm.services.pipeline_runner import get_pipeline_steps, parse_pipeline_step_number
from ihm.services.screener_recommendations import load_screener_recommendation_report
from ihm.services.run_summary import (
    build_pipeline_flow_caption,
    build_latest_run_summary_rows,
    find_latest_run_with_summary,
)
from ihm.services.db import db_available, get_last_query_error
from ihm.services.queries import (
    get_alpha_scanner_dependency_diagnostic,
    get_candidates_count,
    get_latest_exec_run,
    get_latest_risk_run_id,
    get_top_candidates,
)

SCREENER_ARTIFACT_SELECTBOX_KEY = "overview_screener_artifacts_dir_select"

_PIPELINE_SUMMARY_LABEL_OVERRIDES = {
    "import_alpaca_bar": "Import Alpaca Bar",
}


def _pipeline_summary_label(step) -> str:
    return _PIPELINE_SUMMARY_LABEL_OVERRIDES.get(step.key, step.name)


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
    scopes = [{"label": "Workflow complet", "run_kind": "workflow", "step_keys": ["pipeline_workflow"]}]
    scopes.extend(
        {"label": _pipeline_summary_label(step), "step_keys": [step.key]}
        for step in get_pipeline_steps()
        if (step_number := parse_pipeline_step_number(step.num)) is not None and step_number <= 8
    )
    return pd.DataFrame(
        build_latest_run_summary_rows(
            runs,
            scopes,
        )
    )


def _build_screener_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame:
    return build_screener_artifact_history_dataframe(history_entries)


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


def render() -> None:
    st.header("🏠 Vue d'ensemble")
    st.caption(
        "Lecture opérateur alignée sur le flux pipeline : santé amont, artefacts screener partagés, calibration et candidats finaux."
    )

    # --- Bannière régime marché (Axe C plan/prompt/parttern/plan.md) ---
    try:
        from ihm.components.market_regime_banner import render_market_regime_banner
        render_market_regime_banner(compact=True)
    except Exception:  # pragma: no cover - jamais bloquant
        pass

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

    alerts: list[str] = []
    if candidates == 0:
        alerts.append("⚠️ Aucun candidat (`is_candidate=1`) dans `stock_scores`.")
    if exec_status and exec_status.upper() not in ("COMPLETED", "SUCCESS"):
        alerts.append(f"⚠️ Dernière exécution : {run_status_badge(exec_status)}")
    for alert in alerts:
        st.warning(alert)

    pipeline_runs = _merge_pipeline_runs()
    latest_workflow = find_latest_run_with_summary(pipeline_runs, run_kind="workflow")
    summary_rows = _build_pipeline_summary_rows(pipeline_runs)
    with st.container(border=True):
        st.subheader("1. Santé pipeline amont")
        st.caption(
            "Ordre métier affiché ici : "
            f"{build_pipeline_flow_caption(max_main_step=8)}"
        )
        render_run_summary_block(latest_workflow, title="🧭 Dernier workflow pipeline", max_metrics=4)
        if not summary_rows.empty:
            show_dataframe(summary_rows, "Derniers résumés par étape")
        render_alpha_scanner_dependency_panel(
            get_alpha_scanner_dependency_diagnostic(),
            title="Étapes 4 → 5 · détail quotes / earnings",
            expanded=False,
            show_commands=True,
        )

    selected_screener_dir = ""
    with st.container(border=True):
        selected_screener_dir, _ = render_shared_screener_artifact_selector(
            selectbox_key=SCREENER_ARTIFACT_SELECTBOX_KEY,
            title="2. Source screener active",
            caption="Même sélection que la page `Screening` pour éviter les écarts entre synthèse et analyse détaillée.",
            empty_message="Aucun répertoire d'artefacts screener détecté pour le moment.",
            history_title="🗃️ Historique global des artefacts screener",
        )

    screener_report = load_screener_recommendation_report(selected_screener_dir)
    screener_objective_rows = _build_screener_objective_rows(screener_report)
    with st.container(border=True):
        st.subheader("3. Calibration screener")
        if screener_objective_rows.empty:
            st.info("Aucune recommandation screener exploitable détectée pour la source actuellement sélectionnée.")
        else:
            st.caption(
                f"Derniers objectifs exportés depuis `{screener_report.get('artifacts_dir')}` · "
                f"Période : {screener_report.get('coverage_label', 'Période non renseignée')} · "
                f"MAJ : {screener_report.get('updated_at_label', 'inconnue')}"
            )
            screener_metrics = _build_screener_objective_metrics(screener_report)
            if screener_metrics:
                metric_row(screener_metrics)
            show_dataframe(screener_objective_rows, height=220)

    with st.container(border=True):
        st.subheader("4. Top candidats")
        st.caption("Vue courte des meilleurs scores sentiment déjà passés par le flux amont.")
        render_symbol_table(
            get_top_candidates(10),
            key="overview_top_candidates",
            symbol_col="symbol",
            title="Top 10 candidats par score sentiment",
            height=320,
        )


run_page_if_standalone(__name__, render)

