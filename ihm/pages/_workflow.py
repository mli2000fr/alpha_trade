"""ihm/pages/_workflow.py — Phase 6.2 (Backlog L10).

Workflow launcher 1→14 + runtime center (suivi des runs en cours / historique)
extraits de ``pipeline.py``.
"""
from __future__ import annotations

from typing import Any, cast

import pandas as pd
import streamlit as st

from ihm.pages._shared import (
    COMPARE_RUNS_KEY,
    LOG_FILTER_KEY,
    PENDING_COMPARE_RUNS_KEY,
    PENDING_SELECTED_RUN_KEY,
    SELECTED_RUN_KEY,
    PipelineLaunchOptions,
    _is_workflow_run,
    _render_log_block,
    _render_run_summary,
    _sanitize_compare_ids,
    _status_badge,
    _workflow_progress,
    build_run_summary_caption,
    format_duration_hhmmss,
    to_int,
)
from ihm.services.process_registry import (
    build_log_download_name,
    get_pipeline_run_record,
    list_active_pipeline_runs,
    load_pipeline_history,
    read_pipeline_logs,
    start_pipeline_workflow,
    stop_pipeline_run,
)

__all__ = [
    "_build_history_rows",
    "_latest_run_by_step",
    "_merge_runs",
    "_prime_runtime_center_state",
    "_render_runtime_center",
    "_render_workflow_launcher",
]

WORKFLOW_INCLUDE_ML_TRAIN_KEY = "pipeline_workflow_include_ml_train"


def _workflow_mode_label(run: dict[str, object]) -> str:
    command = run.get("command")
    if isinstance(command, list) and any(str(token) == "ml_train" for token in command):
        return "1 → 14 avec ML Train"
    return "1 → 14 sans ML Train"


def _merge_runs() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    active_runs = list_active_pipeline_runs()
    merged: dict[str, dict[str, object]] = {str(run["run_id"]): run for run in load_pipeline_history()}
    for run in active_runs:
        merged[str(run["run_id"])] = run
    all_runs = sorted(
        merged.values(),
        key=lambda item: str(item.get("finished_at") or item.get("executed_at") or ""),
        reverse=True,
    )
    return active_runs, all_runs


def _latest_run_by_step(all_runs: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for run in all_runs:
        step_key = str(run.get("step_key", ""))
        if step_key and step_key not in latest:
            latest[step_key] = run
    return latest


def _build_history_rows(all_runs: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "run_id": run.get("run_id"),
                "type": "workflow" if _is_workflow_run(run) else "étape",
                "étape": run.get("step_label", run.get("step_key")),
                "progression": (
                    f"{to_int(run.get('workflow_completed_steps', 0))}/{to_int(run.get('workflow_total_steps', 0))}"
                    if _is_workflow_run(run)
                    else "—"
                ),
                "statut": _status_badge(str(run.get("status", ""))),
                "compte": run.get("account_id") or "global",
                "début": run.get("executed_at"),
                "fin": run.get("finished_at") or "—",
                "durée": format_duration_hhmmss(run.get("duration_seconds", 0.0)),
                "stdout": to_int(run.get("stdout_lines", 0)),
                "stderr": to_int(run.get("stderr_lines", 0)),
                "résumé métier": build_run_summary_caption(run),
            }
            for run in all_runs
        ]
    )


def _prime_runtime_center_state(run_ids: list[str], labels: dict[str, str]) -> list[str]:
    pending_selected = st.session_state.pop(PENDING_SELECTED_RUN_KEY, None)
    if isinstance(pending_selected, str) and pending_selected in labels:
        st.session_state[SELECTED_RUN_KEY] = pending_selected

    pending_compare = st.session_state.pop(PENDING_COMPARE_RUNS_KEY, None)
    if pending_compare is not None:
        st.session_state[COMPARE_RUNS_KEY] = _sanitize_compare_ids(run_ids, labels, pending_compare)

    default_selected = st.session_state.get(SELECTED_RUN_KEY)
    if default_selected not in labels:
        st.session_state[SELECTED_RUN_KEY] = run_ids[0]

    compare_defaults = _sanitize_compare_ids(run_ids, labels, st.session_state.get(COMPARE_RUNS_KEY, []))
    if compare_defaults != st.session_state.get(COMPARE_RUNS_KEY):
        st.session_state[COMPARE_RUNS_KEY] = compare_defaults

    return compare_defaults


def _render_workflow_launcher(options: PipelineLaunchOptions, live_confirmed: bool, db_config: dict[str, str | None]) -> None:
    active_runs, _ = _merge_runs()
    active_workflows = [run for run in active_runs if _is_workflow_run(run)]
    has_other_active_runs = any(not _is_workflow_run(run) for run in active_runs)
    execution_locked = options.execution_mode == "live" and not live_confirmed

    with st.container(border=True):
        st.subheader("🚀 Workflow complet 1 → 14")
        include_ml_train = st.checkbox(
            "Inclure l'étape 9 — ML Train (Model Factory)",
            value=bool(st.session_state.get(WORKFLOW_INCLUDE_ML_TRAIN_KEY, False)),
            key=WORKFLOW_INCLUDE_ML_TRAIN_KEY,
            disabled=bool(active_runs),
            help="Par défaut, le workflow quotidien complet saute l'étape 9 pour éviter un retrain ML inutile chaque jour.",
        )
        effective_steps = 14 if include_ml_train else 13
        st.caption(
            f"Lance automatiquement le workflow quotidien 1 → 14 dans l'ordre, avec {effective_steps} étape(s) réellement exécutée(s) "
            f"({'ML Train inclus' if include_ml_train else 'ML Train exclu'}). "
            "Les sous-runs restent historisés individuellement, et ce workflow fournit une vue globale avec logs consolidés."
        )

        if active_workflows:
            workflow_run = active_workflows[0]
            _, _, progress_fraction, progress_label = _workflow_progress(workflow_run)
            st.info(f"Workflow déjà actif : `{workflow_run.get('run_id', '')}`")
            st.progress(progress_fraction)
            st.caption(progress_label)
            st.caption(f"Mode actif : {_workflow_mode_label(workflow_run)}")
        elif has_other_active_runs:
            st.warning("Un run pipeline unitaire est déjà en cours. Attendez sa fin avant de lancer le workflow complet.")

        if execution_locked:
            st.warning("Confirmez d'abord le mode LIVE dans les paramètres ci-dessus pour inclure l'étape Execution dans le workflow.")

        launch_clicked = st.button(
            "▶️ Lancer le workflow complet",
            key="run_pipeline_workflow_all_steps",
            type="primary",
            use_container_width=True,
            disabled=bool(active_runs) or execution_locked,
        )
        if launch_clicked:
            try:
                record = start_pipeline_workflow(options, db_config=db_config, include_ml_train=include_ml_train)
            except RuntimeError as exc:
                st.warning(str(exc))
            else:
                st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
                existing_compare = cast(list[str], st.session_state.get(COMPARE_RUNS_KEY, [])) if isinstance(st.session_state.get(COMPARE_RUNS_KEY, []), list) else []
                st.session_state[PENDING_COMPARE_RUNS_KEY] = [record.run_id, *existing_compare][:2]
                st.success(f"Workflow lancé en arrière-plan : `{record.run_id}`")
                st.rerun()



@st.fragment(run_every="2s")
def _render_runtime_center() -> None:
    active_runs, all_runs = _merge_runs()

    st.subheader("🖥️ Centre d'exécution & d'investigation")
    st.caption(
        "Rafraîchissement automatique toutes les 2 secondes pour les runs actifs. "
        "Vous pouvez changer de page : les pipelines continuent à tourner en arrière-plan."
    )

    if st.button("🔄 Rafraîchir maintenant", key="pipeline_manual_refresh", use_container_width=False):
        st.rerun()

    if active_runs:
        st.markdown("**Runs actifs**")
        for run in active_runs:
            run_id = str(run.get("run_id", ""))
            with st.container(border=True):
                cols = st.columns([3, 2, 2, 2, 1.5])
                cols[0].markdown(f"`{run.get('step_label', run.get('step_key', ''))}`  \\n`{run_id}`")
                cols[1].markdown(_status_badge(str(run.get("status", "running"))))
                cols[2].markdown(f"⏱️ {format_duration_hhmmss(run.get('duration_seconds', 0.0))}")
                cols[3].markdown(f"🏦 `{run.get('account_id') or 'global'}`")
                if cols[4].button("⏹️ Arrêter", key=f"stop_run_{run_id}", use_container_width=True):
                    stop_pipeline_run(run_id)
                    st.rerun()
                if _is_workflow_run(run):
                    _, _, progress_fraction, progress_label = _workflow_progress(run)
                    st.progress(progress_fraction)
                    st.caption(progress_label)
    else:
        st.info("Aucun run actif pour le moment.")

    if not all_runs:
        st.info("Aucun run IHM historisé pour le moment.")
        return

    labels = {
        str(run["run_id"]): (
            f"{run.get('step_label', run.get('step_key', ''))} | {run.get('run_id')} | "
            f"{_status_badge(str(run.get('status', '')))}"
            f"{' | ' + _workflow_progress(run)[3] if _is_workflow_run(run) else ''} | {run.get('executed_at', '')}"
        )
        for run in all_runs
    }
    run_ids = list(labels.keys())
    compare_defaults = _prime_runtime_center_state(run_ids, labels)

    control_col1, control_col2 = st.columns([2, 3])
    with control_col1:
        log_filter = cast(
            str,
            st.radio(
                "Flux à afficher",
                options=["tout", "stdout", "stderr"],
                horizontal=True,
                key=LOG_FILTER_KEY,
            ),
        )
    with control_col2:
        selected_label = st.selectbox(
            "Run à inspecter",
            options=run_ids,
            format_func=lambda rid: labels[rid],
            key=SELECTED_RUN_KEY,
        )
        compare_ids = st.multiselect(
            "Comparer 2 runs maximum",
            options=run_ids,
            default=compare_defaults,
            format_func=lambda rid: labels[rid],
            key=COMPARE_RUNS_KEY,
        )
        if len(compare_ids) > 2:
            compare_ids = compare_ids[:2]
            st.session_state[PENDING_COMPARE_RUNS_KEY] = compare_ids
            st.warning("La comparaison est limitée à 2 runs.")
            st.rerun()

    stream_map = {"tout": "all", "stdout": "stdout", "stderr": "stderr"}
    selected_run = get_pipeline_run_record(selected_label)
    if selected_run is not None:
        selected_logs = read_pipeline_logs(selected_label, stream=cast(Any, stream_map[log_filter]))
        status = str(selected_run.get("status", ""))
        if status == "completed":
            st.success(f"Run sélectionné : {_status_badge(status)}")
        elif status in {"failed", "timeout", "stopped"}:
            st.error(f"Run sélectionné : {_status_badge(status)}")
        else:
            st.warning(f"Run sélectionné : {_status_badge(status)}")

        if _is_workflow_run(selected_run):
            completed, total, progress_fraction, progress_label = _workflow_progress(selected_run)
            st.markdown("**Progression globale**")
            st.progress(progress_fraction)
            st.caption(progress_label)
            workflow_cols = st.columns(3)
            child_run_ids = selected_run.get("workflow_child_run_ids", [])
            child_runs_count = len(child_run_ids) if isinstance(child_run_ids, list) else 0
            workflow_cols[0].metric("Mode", _workflow_mode_label(selected_run))
            workflow_cols[1].metric("Progression", f"{completed}/{total}")
            workflow_cols[2].metric("Sous-runs", child_runs_count)
            current_step_label = str(selected_run.get("workflow_current_step_label") or "").strip()
            if current_step_label:
                st.caption(f"Étape en cours : `{current_step_label}`")

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        metric_col1.metric("Étape", str(selected_run.get("step_label", selected_run.get("step_key", ""))))
        metric_col2.metric("Durée", format_duration_hhmmss(selected_run.get("duration_seconds", 0.0)))
        metric_col3.metric("Lignes stdout", to_int(selected_run.get("stdout_lines", 0)))
        metric_col4.metric("Lignes stderr", to_int(selected_run.get("stderr_lines", 0)))
        _render_run_summary(selected_run)

        st.caption(
            f"Commande : `{selected_run.get('command_display', '')}` | "
            f"Compte : `{selected_run.get('account_id') or 'global'}` | "
            f"Retour : `{selected_run.get('returncode')}`"
        )
        st.download_button(
            label=f"⬇️ Télécharger le log ({log_filter})",
            data=selected_logs,
            file_name=build_log_download_name(selected_label, stream=cast(Any, stream_map[log_filter])),
            mime="text/plain",
            key=f"download_selected_{selected_label}_{log_filter}",
        )
        _render_log_block(
            "Logs du run selectionne",
            selected_logs,
            key=f"selected_logs_{selected_label}_{log_filter}",
            expanded=True,
        )

    if len(compare_ids) == 2:
        st.markdown("**Comparaison de runs**")
        compare_col1, compare_col2 = st.columns(2)
        for col, run_id in zip((compare_col1, compare_col2), compare_ids):
            run = get_pipeline_run_record(run_id)
            logs = read_pipeline_logs(run_id, stream=cast(Any, stream_map[log_filter]))
            with col:
                st.markdown(f"`{labels[run_id]}`")
                st.download_button(
                    label="⬇️ Télécharger",
                    data=logs,
                    file_name=build_log_download_name(run_id, stream=cast(Any, stream_map[log_filter])),
                    mime="text/plain",
                    key=f"download_compare_{run_id}_{log_filter}",
                )
                _render_log_block(
                    f"Logs {run_id}",
                    logs,
                    key=f"compare_logs_{run_id}_{log_filter}",
                )

    history_df = _build_history_rows(all_runs)
    with st.expander("🗃️ Historique centralisé des exécutions IHM", expanded=False):
        st.dataframe(history_df, use_container_width=True, hide_index=True)
