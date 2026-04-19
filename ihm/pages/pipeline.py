"""ihm/pages/pipeline.py — Vue séquentielle et pilotage asynchrone du pipeline métier."""
from __future__ import annotations

from typing import Any, cast

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.services.db import get_runtime_db_config
from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command, format_command_for_display, get_pipeline_steps
from ihm.services.process_registry import (
    build_log_download_name,
    get_pipeline_run_record,
    list_active_pipeline_runs,
    load_pipeline_history,
    read_pipeline_logs,
    start_pipeline_run,
    stop_pipeline_run,
)

SELECTED_RUN_KEY = "ihm_pipeline_selected_run_id"
COMPARE_RUNS_KEY = "ihm_pipeline_compare_run_ids"
LOG_FILTER_KEY = "ihm_pipeline_log_filter"
PENDING_SELECTED_RUN_KEY = "ihm_pipeline_pending_selected_run_id"
PENDING_COMPARE_RUNS_KEY = "ihm_pipeline_pending_compare_run_ids"
TAIL_LINES = 250


def _tail_text(value: str, max_lines: int = TAIL_LINES) -> str:
    lines = value.splitlines()
    if len(lines) <= max_lines:
        return value
    return "\n".join(lines[-max_lines:])


def _render_log_block(title: str, content: str, *, key: str, expanded: bool = False) -> None:
    tailed = _tail_text(content)
    suffix = ""
    if tailed != content:
        suffix = f" — affichage limite aux {TAIL_LINES} dernieres lignes"
    with st.expander(f"{title}{suffix}", expanded=expanded):
        if tailed.strip():
            with st.container(height=320, key=f"{key}_container"):
                st.code(tailed, language="text")
        else:
            st.info("Aucun log disponible pour le moment. Le contenu apparaitra ici des que le processus ecrira sur stdout/stderr.")


def _build_launch_options() -> tuple[PipelineLaunchOptions, bool]:
    selected_account_id = cast(str | None, st.session_state.get("selected_account_id"))

    with st.expander("⚙️ Paramètres d'exécution", expanded=True):
        st.caption(
            "Les pipelines sont lancés en arrière-plan depuis l'IHM. Ils héritent de la configuration DB active et, "
            "pour les étapes concernées, du compte Alpaca sélectionné dans la sidebar."
        )

        if selected_account_id:
            st.info(f"Compte Alpaca actuellement sélectionné : `{selected_account_id}`")
        else:
            st.info("Aucun compte Alpaca explicitement sélectionné — le compte par défaut sera utilisé si nécessaire.")

        col1, col2, col3 = st.columns(3)
        with col1:
            trade_date = st.text_input(
                "Trade date / as-of (YYYY-MM-DD)",
                key="pipeline_trade_date",
                help="Utilisé par Signal Aggregator, ML Predict, Risk, Execution et Corporate Actions Apply.",
            )
        with col2:
            risk_account_equity = st.number_input(
                "Equity pour le module Risk",
                min_value=0.0,
                value=float(st.session_state.get("pipeline_risk_account_equity", 100_000.0)),
                step=1_000.0,
                format="%.2f",
                key="pipeline_risk_account_equity",
            )
        with col3:
            execution_mode = cast(
                str,
                st.selectbox(
                    "Mode Execution",
                    options=["simulate", "paper", "live"],
                    index=["simulate", "paper", "live"].index(
                        cast(str, st.session_state.get("pipeline_execution_mode", "simulate"))
                        if st.session_state.get("pipeline_execution_mode", "simulate") in {"simulate", "paper", "live"}
                        else "simulate"
                    ),
                    key="pipeline_execution_mode",
                ),
            )

        col4, col5, col6 = st.columns(3)
        with col4:
            execution_run_id = st.text_input(
                "Execution — risk_run_id optionnel",
                key="pipeline_execution_run_id",
                help="Laissez vide pour exécuter sur le dernier run disponible.",
            )
        with col5:
            allow_outside_rth = st.checkbox(
                "Execution hors RTH",
                value=bool(st.session_state.get("pipeline_allow_outside_rth", False)),
                key="pipeline_allow_outside_rth",
            )
        with col6:
            auto_rebalance = st.checkbox(
                "Auto rebalance",
                value=bool(st.session_state.get("pipeline_auto_rebalance", False)),
                key="pipeline_auto_rebalance",
            )

        live_confirmed = True
        if execution_mode == "live":
            st.warning("Mode LIVE sélectionné : cette action peut envoyer de vrais ordres chez le broker.")
            live_confirmed = st.checkbox(
                "Je confirme explicitement le lancement en LIVE",
                value=bool(st.session_state.get("pipeline_live_confirmed", False)),
                key="pipeline_live_confirmed",
            )

    return (
        PipelineLaunchOptions(
            account_id=selected_account_id,
            trade_date=trade_date,
            risk_account_equity=float(risk_account_equity),
            execution_mode=cast(Any, execution_mode),
            execution_run_id=execution_run_id,
            allow_outside_rth=bool(allow_outside_rth),
            auto_rebalance=bool(auto_rebalance),
        ),
        live_confirmed,
    )


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


def _status_badge(status: str) -> str:
    return {
        "starting": "🟦 Démarrage",
        "running": "🟨 En cours",
        "completed": "🟢 Terminé",
        "failed": "🔴 Échec",
        "timeout": "🟠 Timeout",
        "stopped": "⏹️ Arrêté",
    }.get(status, status)


def _sanitize_compare_ids(run_ids: list[str], labels: dict[str, str], value: object) -> list[str]:
    candidates = value if isinstance(value, list) else []
    return [rid for rid in candidates if isinstance(rid, str) and rid in labels and rid in run_ids][:2]


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
            cols = st.columns([3, 2, 2, 2, 1.5])
            cols[0].markdown(f"`{run.get('step_label', run.get('step_key', ''))}`  \\n`{run_id}`")
            cols[1].markdown(_status_badge(str(run.get("status", "running"))))
            cols[2].markdown(f"⏱️ {float(run.get('duration_seconds', 0.0)):.2f}s")
            cols[3].markdown(f"🏦 `{run.get('account_id') or 'global'}`")
            if cols[4].button("⏹️ Arrêter", key=f"stop_run_{run_id}", use_container_width=True):
                stop_pipeline_run(run_id)
                st.rerun()
    else:
        st.info("Aucun run actif pour le moment.")

    if not all_runs:
        st.info("Aucun run IHM historisé pour le moment.")
        return

    labels = {
        str(run["run_id"]): (
            f"{run.get('step_label', run.get('step_key', ''))} | {run.get('run_id')} | "
            f"{_status_badge(str(run.get('status', '')))} | {run.get('executed_at', '')}"
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

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        metric_col1.metric("Étape", str(selected_run.get("step_label", selected_run.get("step_key", ""))))
        metric_col2.metric("Durée", f"{float(selected_run.get('duration_seconds', 0.0)):.2f}s")
        metric_col3.metric("Lignes stdout", int(selected_run.get("stdout_lines", 0)))
        metric_col4.metric("Lignes stderr", int(selected_run.get("stderr_lines", 0)))

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

    history_df = pd.DataFrame(
        [
            {
                "run_id": run.get("run_id"),
                "étape": run.get("step_label", run.get("step_key")),
                "statut": _status_badge(str(run.get("status", ""))),
                "compte": run.get("account_id") or "global",
                "début": run.get("executed_at"),
                "fin": run.get("finished_at") or "—",
                "durée_s": float(run.get("duration_seconds", 0.0)),
                "stdout": int(run.get("stdout_lines", 0)),
                "stderr": int(run.get("stderr_lines", 0)),
            }
            for run in all_runs
        ]
    )
    with st.expander("🗃️ Historique centralisé des exécutions IHM", expanded=False):
        st.dataframe(history_df, use_container_width=True, hide_index=True)


def _render_step_result(record: dict[str, object] | None) -> None:
    if not record:
        st.caption("Aucune exécution historisée pour cette étape.")
        return

    status = str(record.get("status", ""))
    message = f"Dernier run IHM : {_status_badge(status)}"
    if status == "completed":
        st.success(message)
    elif status in {"failed", "timeout", "stopped"}:
        st.error(message)
    else:
        st.warning(message)

    cols = st.columns(4)
    cols[0].metric("Run ID", str(record.get("run_id", "—")))
    cols[1].metric("Durée", f"{float(record.get('duration_seconds', 0.0)):.2f}s")
    cols[2].metric("stdout", int(record.get("stdout_lines", 0)))
    cols[3].metric("stderr", int(record.get("stderr_lines", 0)))
    st.caption(
        f"Début : `{record.get('executed_at', '—')}` | Fin : `{record.get('finished_at') or '—'}` | "
        f"Compte : `{record.get('account_id') or 'global'}`"
    )


@st.fragment(run_every="2s")
def _render_step_panels(options: PipelineLaunchOptions, live_confirmed: bool, db_config: dict[str, str | None]) -> None:
    active_runs, all_runs = _merge_runs()
    latest_by_step = _latest_run_by_step(all_runs)
    active_by_step: dict[str, list[dict[str, object]]] = {}
    for run in active_runs:
        active_by_step.setdefault(str(run.get("step_key", "")), []).append(run)

    for step in get_pipeline_steps():
        command_preview = format_command_for_display(build_pipeline_command(step.key, options))
        with st.expander(f"**{step.num}. {step.name}**", expanded=False):
            info_col, action_col = st.columns([5, 2])

            with info_col:
                st.markdown(f"**Description** : {step.desc}")
                st.markdown(f"**Tables impactées** : `{step.tables}`")
                st.markdown(f"**Dépendances** : {step.deps}")
                if step.account_usage == "alpaca":
                    st.caption(f"🏦 Cette étape utilise le compte Alpaca sélectionné : `{options.account_id or 'default'}`")
                else:
                    st.caption("🌐 Cette étape est globale et n'utilise pas le sélecteur de compte Alpaca.")
                st.code(command_preview, language="powershell")

            with action_col:
                execution_locked = step.key == "execution" and options.execution_mode == "live" and not live_confirmed
                active_for_step = active_by_step.get(step.key, [])
                if active_for_step:
                    st.info(f"{len(active_for_step)} run(s) actif(s) pour cette étape.")
                    for run in active_for_step:
                        run_id = str(run.get("run_id", ""))
                        st.caption(f"Actif : `{run_id}`")
                        if st.button("⏹️ Arrêter ce run", key=f"stop_step_run_{run_id}", use_container_width=True):
                            stop_pipeline_run(run_id)
                            st.rerun()
                    st.caption("Le bouton de lancement est masque tant qu'un run de cette etape est en cours.")
                else:
                    run_clicked = st.button(
                        "▶️ Lancer en arrière-plan",
                        key=f"run_pipeline_step_{step.key}",
                        type="primary",
                        use_container_width=True,
                        disabled=execution_locked,
                    )
                    if execution_locked:
                        st.warning("Confirmez d'abord le mode LIVE dans les paramètres ci-dessus.")

                    if run_clicked:
                        record = start_pipeline_run(
                            step.key,
                            f"{step.num}. {step.name}",
                            options,
                            db_config=db_config,
                        )
                        st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
                        compare_ids = _sanitize_compare_ids(
                            [str(run.get("run_id", "")) for run in all_runs if run.get("run_id")],
                            {str(run.get("run_id", "")): "" for run in all_runs if run.get("run_id")},
                            st.session_state.get(COMPARE_RUNS_KEY, []),
                        )
                        if record.run_id not in compare_ids:
                            st.session_state[PENDING_COMPARE_RUNS_KEY] = [record.run_id, *compare_ids][:2]
                        st.success(f"Run demarre en arriere-plan : `{record.run_id}`")
                        st.rerun()

            _render_step_result(latest_by_step.get(step.key))


def render() -> None:
    st.header("🔄 Pipeline Quotidien")
    st.caption("Ordre d'exécution strict — chaque étape dépend de la précédente.")

    options, live_confirmed = _build_launch_options()
    db_config = get_runtime_db_config()

    _render_runtime_center()
    _render_step_panels(options, live_confirmed, db_config)


run_page_if_standalone(__name__, render)
