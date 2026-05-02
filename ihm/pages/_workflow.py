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
    "_build_workflow_child_run_payload",
    "_latest_run_by_step",
    "_merge_runs",
    "_prime_runtime_center_state",
    "_prepare_workflow_child_run_state",
    "_render_runtime_center",
    "_render_workflow_launcher",
]

WORKFLOW_INCLUDE_ML_TRAIN_KEY = "pipeline_workflow_include_ml_train"
WORKFLOW_CHILD_AUTOFOLLOW_KEY_PREFIX = "workflow_child_run_autofollow_"
WORKFLOW_CHILD_LAST_AUTO_KEY_PREFIX = "workflow_child_run_last_auto_"


def _workflow_mode_label(run: dict[str, object]) -> str:
    command = run.get("command")
    if isinstance(command, list) and any(str(token) == "ml_train" for token in command):
        return "1 → 14 avec ML Train"
    return "1 → 14 sans ML Train"


def _build_workflow_child_run_payload(workflow_run: dict[str, object]) -> tuple[list[str], dict[str, str]]:
    raw_child_ids = workflow_run.get("workflow_child_run_ids", [])
    if not isinstance(raw_child_ids, list):
        return [], {}

    child_run_ids: list[str] = []
    seen: set[str] = set()
    for raw_child_id in reversed(raw_child_ids):
        if not isinstance(raw_child_id, str):
            continue
        child_id = raw_child_id.strip()
        if not child_id or child_id in seen:
            continue
        seen.add(child_id)
        child_run_ids.append(child_id)

    labels: dict[str, str] = {}
    for child_id in child_run_ids:
        child_run = get_pipeline_run_record(child_id) or {}
        child_label = str(child_run.get("step_label") or child_run.get("step_key") or "Sous-run")
        child_status = _status_badge(str(child_run.get("status") or "inconnu"))
        child_started_at = str(child_run.get("executed_at") or "—")
        labels[child_id] = f"{child_label} | {child_id} | {child_status} | {child_started_at}"

    return child_run_ids, labels


def _prepare_workflow_child_run_state(
    workflow_run: dict[str, object],
    child_run_ids: list[str],
    child_labels: dict[str, str],
) -> tuple[str | None, bool, str | None, str | None, str | None]:
    workflow_run_id = str(workflow_run.get("run_id") or "").strip()
    if not workflow_run_id or not child_run_ids:
        return None, False, None, None, None

    current_child_run_id = str(workflow_run.get("workflow_current_child_run_id") or "").strip() or None
    workflow_status = str(workflow_run.get("status") or "")
    workflow_active = workflow_status in {"starting", "running"}
    child_select_key = f"workflow_child_run_select_{workflow_run_id}"
    follow_key = f"{WORKFLOW_CHILD_AUTOFOLLOW_KEY_PREFIX}{workflow_run_id}"
    last_auto_key = f"{WORKFLOW_CHILD_LAST_AUTO_KEY_PREFIX}{workflow_run_id}"

    default_child_run_id = current_child_run_id if current_child_run_id in child_labels else child_run_ids[0]

    follow_value = st.session_state.get(follow_key)
    if not isinstance(follow_value, bool):
        st.session_state[follow_key] = workflow_active and current_child_run_id is not None

    if st.session_state.get(child_select_key) not in child_labels:
        st.session_state[child_select_key] = default_child_run_id

    if workflow_active and bool(st.session_state.get(follow_key)) and current_child_run_id in child_labels:
        st.session_state[child_select_key] = current_child_run_id
        st.session_state[last_auto_key] = current_child_run_id

    selected_child_run_id = st.session_state.get(child_select_key)
    if not isinstance(selected_child_run_id, str) or selected_child_run_id not in child_labels:
        selected_child_run_id = default_child_run_id
        st.session_state[child_select_key] = selected_child_run_id

    return child_select_key, bool(st.session_state.get(follow_key)), current_child_run_id, selected_child_run_id, last_auto_key


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
            value=bool(st.session_state.get(WORKFLOW_INCLUDE_ML_TRAIN_KEY, True)),
            key=WORKFLOW_INCLUDE_ML_TRAIN_KEY,
            disabled=bool(active_runs),
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

            child_run_ids, child_labels = _build_workflow_child_run_payload(selected_run)
            if child_run_ids:
                st.markdown("**Logs détaillés d’un sous-run workflow**")
                st.caption(
                    "Le log consolidé du workflow reste disponible plus bas. "
                    "Ce panneau affiche le log brut d’une étape précise, comme lors d’un lancement unitaire."
                )
                child_select_key, follow_current_child, current_child_run_id, _, last_auto_key = _prepare_workflow_child_run_state(
                    selected_run,
                    child_run_ids,
                    child_labels,
                )
                if child_select_key is None:
                    current_child_run_id = None
                    follow_current_child = False
                    child_select_key = f"workflow_child_run_select_{selected_label}"

                workflow_active = status in {"starting", "running"}
                child_control_cols = st.columns([2.2, 1.2, 1.2])
                with child_control_cols[0]:
                    follow_current_child = cast(
                        bool,
                        st.checkbox(
                            "Suivre automatiquement le sous-run courant",
                            key=f"{WORKFLOW_CHILD_AUTOFOLLOW_KEY_PREFIX}{selected_label}",
                            disabled=not (workflow_active and current_child_run_id),
                            help=(
                                "Quand activé, la vue bascule automatiquement sur l’étape en cours à chaque rafraîchissement. "
                                "Désactivez-le pour inspecter un sous-run précédent sans être ramené sur l’étape active."
                            ),
                        ),
                    )
                with child_control_cols[1]:
                    if current_child_run_id:
                        st.caption(f"Sous-run courant : `{current_child_run_id}`")
                with child_control_cols[2]:
                    if current_child_run_id and not follow_current_child and st.button(
                        "↩️ Revenir au courant",
                        key=f"workflow_child_run_back_to_current_{selected_label}",
                        use_container_width=True,
                    ):
                        st.session_state[child_select_key] = current_child_run_id
                        st.session_state[f"{WORKFLOW_CHILD_AUTOFOLLOW_KEY_PREFIX}{selected_label}"] = True
                        if last_auto_key is not None:
                            st.session_state[last_auto_key] = current_child_run_id
                        st.rerun()

                if workflow_active and follow_current_child and current_child_run_id in child_labels:
                    st.session_state[child_select_key] = current_child_run_id
                    if last_auto_key is not None:
                        st.session_state[last_auto_key] = current_child_run_id
                selected_child_run_id = cast(
                    str,
                    st.selectbox(
                        "Sous-run à inspecter",
                        options=child_run_ids,
                        format_func=lambda rid: child_labels[rid],
                        key=child_select_key,
                    ),
                )
                if workflow_active and follow_current_child and current_child_run_id and selected_child_run_id != current_child_run_id:
                    st.session_state[f"{WORKFLOW_CHILD_AUTOFOLLOW_KEY_PREFIX}{selected_label}"] = False
                    follow_current_child = False
                    st.caption("Suivi automatique suspendu après sélection manuelle d’un sous-run différent.")
                selected_child_run = get_pipeline_run_record(selected_child_run_id)
                if selected_child_run is not None:
                    selected_child_logs = read_pipeline_logs(selected_child_run_id, stream=cast(Any, stream_map[log_filter]))
                    child_metric_col1, child_metric_col2, child_metric_col3, child_metric_col4 = st.columns(4)
                    child_metric_col1.metric(
                        "Étape détaillée",
                        str(selected_child_run.get("step_label", selected_child_run.get("step_key", ""))),
                    )
                    child_metric_col2.metric("Durée", format_duration_hhmmss(selected_child_run.get("duration_seconds", 0.0)))
                    child_metric_col3.metric("Lignes stdout", to_int(selected_child_run.get("stdout_lines", 0)))
                    child_metric_col4.metric("Lignes stderr", to_int(selected_child_run.get("stderr_lines", 0)))
                    _render_run_summary(selected_child_run, compact=True)
                    st.download_button(
                        label=f"⬇️ Télécharger le log détaillé du sous-run ({log_filter})",
                        data=selected_child_logs,
                        file_name=build_log_download_name(selected_child_run_id, stream=cast(Any, stream_map[log_filter])),
                        mime="text/plain",
                        key=f"download_workflow_child_{selected_child_run_id}_{log_filter}",
                    )
                    _render_log_block(
                        "Logs détaillés du sous-run sélectionné",
                        selected_child_logs,
                        key=f"workflow_child_logs_{selected_child_run_id}_{log_filter}",
                        expanded=True,
                    )

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
