"""ihm/pages/pipeline.py — Vue séquentielle et pilotage asynchrone du pipeline métier."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Any, cast

import pandas as pd
import streamlit as st

from ihm.components.metrics import format_duration_hhmmss, to_int
from ihm.pages import run_page_if_standalone
from ihm.services.account_defaults import (
    PDT_EQUITY_THRESHOLD,
    PipelineExecutionDefaults,
    get_pipeline_execution_defaults,
)
from ihm.services.db import get_runtime_db_config
from ihm.services.pipeline_runner import (
    PipelineLaunchOptions,
    build_pipeline_command,
    format_command_for_display,
    get_pipeline_steps,
    is_gpu_available,
)
from ihm.services.process_registry import (
    build_log_download_name,
    get_pipeline_run_record,
    list_active_pipeline_runs,
    load_pipeline_history,
    read_pipeline_logs,
    start_pipeline_run,
    start_pipeline_workflow,
    stop_pipeline_run,
)

SELECTED_RUN_KEY = "ihm_pipeline_selected_run_id"
COMPARE_RUNS_KEY = "ihm_pipeline_compare_run_ids"
LOG_FILTER_KEY = "ihm_pipeline_log_filter"
PENDING_SELECTED_RUN_KEY = "ihm_pipeline_pending_selected_run_id"
PENDING_COMPARE_RUNS_KEY = "ihm_pipeline_pending_compare_run_ids"
TAIL_LINES = 250
EXECUTION_DEFAULTS_ACCOUNT_KEY = "pipeline_execution_defaults_applied_account_id"
ALPHA_SCANNER_PRESET_PREFS_KEY = "pipeline_alpha_scanner_strict_preset_by_account"
ALPHA_SCANNER_PRESET_LAST_ACCOUNT_KEY = "pipeline_alpha_scanner_strict_preset_last_account"
ALPHA_SCANNER_PRESET_WIDGET_KEY = "pipeline_alpha_scanner_use_strict_preset"
IMPORT_NEWS_START_DATE_KEY = "pipeline_import_news_start_date"
IMPORT_NEWS_END_DATE_KEY = "pipeline_import_news_end_date"


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


def _apply_execution_prefills(selected_account_id: str | None) -> PipelineExecutionDefaults | None:
    cleaned_account_id = (selected_account_id or "").strip() or None
    if cleaned_account_id is None:
        return None

    try:
        defaults = get_pipeline_execution_defaults(cleaned_account_id)
    except Exception:
        st.session_state[EXECUTION_DEFAULTS_ACCOUNT_KEY] = cleaned_account_id
        return None

    if defaults is None:
        st.session_state[EXECUTION_DEFAULTS_ACCOUNT_KEY] = cleaned_account_id
        return None

    account_changed = st.session_state.get(EXECUTION_DEFAULTS_ACCOUNT_KEY) != cleaned_account_id
    if defaults.account_type in {"margin", "cash"} and (
        account_changed or "pipeline_execution_account_type" not in st.session_state
    ):
        st.session_state["pipeline_execution_account_type"] = defaults.account_type
    if defaults.pdt_rule in {"auto", "off"} and (
        account_changed or "pipeline_execution_pdt_rule" not in st.session_state
    ):
        st.session_state["pipeline_execution_pdt_rule"] = defaults.pdt_rule
    if defaults.swing_only is not None and (
        account_changed or "pipeline_execution_swing_only" not in st.session_state
    ):
        st.session_state["pipeline_execution_swing_only"] = defaults.swing_only

    st.session_state[EXECUTION_DEFAULTS_ACCOUNT_KEY] = cleaned_account_id
    return defaults


def _build_execution_prefill_caption(defaults: PipelineExecutionDefaults | None) -> str | None:
    if defaults is None:
        return None

    notes: list[str] = []
    if defaults.account_type:
        notes.append(f"type de compte prérempli via broker : `{defaults.account_type}`")
    if defaults.pdt_rule:
        notes.append(f"règle PDT préremplie : `{defaults.pdt_rule}`")
    if defaults.equity is not None:
        notes.append(f"equity broker ≈ `{defaults.equity:,.2f}` (seuil PDT `{PDT_EQUITY_THRESHOLD:,.0f}`)")
    notes.append("`swing only` reste manuel car ce choix ne se déduit pas fiablement du seul montant du compte")
    return " | ".join(notes)


def _normalize_alpha_scanner_preset_account_bucket(account_id: str | None) -> str:
    cleaned = (account_id or "").strip()
    return cleaned or "default"


def _sync_alpha_scanner_strict_preset_preference(
    selected_account_id: str | None,
    session_state: dict[str, Any],
) -> bool:
    bucket = _normalize_alpha_scanner_preset_account_bucket(selected_account_id)
    prefs_raw = session_state.get(ALPHA_SCANNER_PRESET_PREFS_KEY)
    prefs = dict(prefs_raw) if isinstance(prefs_raw, dict) else {}
    last_bucket = session_state.get(ALPHA_SCANNER_PRESET_LAST_ACCOUNT_KEY)

    if last_bucket != bucket:
        restored_value = bool(prefs.get(bucket, False))
        session_state[ALPHA_SCANNER_PRESET_WIDGET_KEY] = restored_value
        session_state[ALPHA_SCANNER_PRESET_LAST_ACCOUNT_KEY] = bucket
        prefs.setdefault(bucket, restored_value)
        session_state[ALPHA_SCANNER_PRESET_PREFS_KEY] = prefs
        return restored_value

    current_value = bool(session_state.get(ALPHA_SCANNER_PRESET_WIDGET_KEY, prefs.get(bucket, False)))
    prefs[bucket] = current_value
    session_state[ALPHA_SCANNER_PRESET_PREFS_KEY] = prefs
    session_state[ALPHA_SCANNER_PRESET_LAST_ACCOUNT_KEY] = bucket
    return current_value


def _build_launch_options() -> tuple[PipelineLaunchOptions, bool]:
    selected_account_id = cast(str | None, st.session_state.get("selected_account_id"))
    execution_defaults = _apply_execution_prefills(selected_account_id)
    alpha_scanner_strict_default = _sync_alpha_scanner_strict_preset_preference(selected_account_id, st.session_state)

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
                "Execution hors RTH (file d'attente pour l'ouverture)",
                value=bool(st.session_state.get("pipeline_allow_outside_rth", False)),
                key="pipeline_allow_outside_rth",
                help="Soumet les ordres meme si le marche est ferme. En paper/live, ils restent en attente et seront traites a l'ouverture suivante.",
            )
        with col6:
            auto_rebalance = st.checkbox(
                "Auto rebalance",
                value=bool(st.session_state.get("pipeline_auto_rebalance", False)),
                key="pipeline_auto_rebalance",
            )

        exec_col1, exec_col2, exec_col3 = st.columns(3)
        st.warning(
            "⚠️ différence potentiellement forte entre margin et cash\n\n"
            "- `margin` utilise le buying power broker ; `cash` se limite au cash settled / non-marginable buying power.\n"
            "- À equity identique, cela peut changer fortement le nombre d'ordres soumis et la capacité de rebalancing.\n"
            "- Sur un compte `margin` < 25k, la logique PDT peut différer les sorties le jour même ; `swing only` force aussi ce comportement.\n"
            "- Résultat : les fills, les exits armés (TP/TS) et donc les performances observées peuvent diverger fortement entre `margin` et `cash`."
        )
        prefill_caption = _build_execution_prefill_caption(execution_defaults)
        if prefill_caption:
            st.caption(prefill_caption)
        with exec_col1:
            execution_account_type = cast(
                str,
                st.selectbox(
                    "Execution — type de compte",
                    options=["margin", "cash"],
                    index=["margin", "cash"].index(
                        cast(str, st.session_state.get("pipeline_execution_account_type", "margin"))
                        if st.session_state.get("pipeline_execution_account_type", "margin") in {"margin", "cash"}
                        else "margin"
                    ),
                    key="pipeline_execution_account_type",
                    help="`margin` utilise le buying power ; `cash` utilise uniquement le cash settled disponible.",
                ),
            )
        with exec_col2:
            execution_pdt_rule = cast(
                str,
                st.selectbox(
                    "Execution — règle PDT",
                    options=["auto", "off"],
                    index=["auto", "off"].index(
                        cast(str, st.session_state.get("pipeline_execution_pdt_rule", "auto"))
                        if st.session_state.get("pipeline_execution_pdt_rule", "auto") in {"auto", "off"}
                        else "auto"
                    ),
                    key="pipeline_execution_pdt_rule",
                    help="`auto` applique la règle PDT sur un compte margin < 25k ; `off` la neutralise côté exécution.",
                ),
            )
        with exec_col3:
            execution_swing_only = st.checkbox(
                "Execution — swing only",
                value=bool(st.session_state.get("pipeline_execution_swing_only", False)),
                key="pipeline_execution_swing_only",
                help="Si coché, le moteur diffère l'armement des sorties le jour même du fill.",
            )

        effective_execution_pdt_rule = "off" if execution_account_type == "cash" else execution_pdt_rule
        constraint_notes = [
            f"Type de compte : `{execution_account_type}`",
            f"Règle PDT effective : `{effective_execution_pdt_rule}`",
            f"Swing only : `{bool(execution_swing_only)}`",
        ]
        if execution_account_type == "cash":
            constraint_notes.append("En `cash`, le moteur se base sur le cash settled / non-marginable buying power.")
        else:
            constraint_notes.append("En `margin`, le moteur se base sur le buying power broker.")
        if effective_execution_pdt_rule == "auto":
            constraint_notes.append("Si l'equity broker est < 25k, le quota de day trades peut différer les exits le jour même.")
        if execution_swing_only:
            constraint_notes.append("Les children TP/TS sont différés le jour même du fill.")
        st.info(" | ".join(constraint_notes))

        ml_col1, ml_col2 = st.columns([2, 3])
        with ml_col1:
            ml_accelerator = cast(
                str,
                st.selectbox(
                    "Accélérateur ML",
                    options=["auto", "cpu", "gpu"],
                    index=["auto", "cpu", "gpu"].index(
                        cast(str, st.session_state.get("pipeline_ml_accelerator", "auto"))
                        if st.session_state.get("pipeline_ml_accelerator", "auto") in {"auto", "cpu", "gpu"}
                        else "auto"
                    ),
                    key="pipeline_ml_accelerator",
                    help="Appliqué aux étapes ML Train et ML Predict. 'auto' utilise le GPU si CUDA est disponible, sinon CPU.",
                ),
            )
        with ml_col2:
            gpu_detected = is_gpu_available()
            if gpu_detected:
                st.success("GPU CUDA détecté dans l'environnement de l'IHM : les jobs ML peuvent être lancés en mode `auto` ou `gpu`.")
            else:
                st.info("Aucun GPU CUDA détecté dans l'environnement de l'IHM : le mode `auto` retombera sur CPU.")

        alpha_scanner_use_strict_preset = st.checkbox(
            "Alpha Scanner — activer le preset strict",
            value=bool(alpha_scanner_strict_default),
            key=ALPHA_SCANNER_PRESET_WIDGET_KEY,
            help="Ajoute `--preset strict` lors du lancement IHM de l'étape Alpha Scanner et du workflow complet.",
        )
        _sync_alpha_scanner_strict_preset_preference(selected_account_id, st.session_state)
        if alpha_scanner_use_strict_preset:
            st.caption(
                "Le workflow IHM lancera `selector.alpha_scanner --preset strict` : "
                "`min_close=10`, `ADV20>=30M`, `max_volatility_ratio<=0.90`."
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
            alpha_scanner_use_strict_preset=bool(alpha_scanner_use_strict_preset),
            risk_account_equity=float(risk_account_equity),
            execution_mode=cast(Any, execution_mode),
            execution_run_id=execution_run_id,
            allow_outside_rth=bool(allow_outside_rth),
            auto_rebalance=bool(auto_rebalance),
            execution_account_type=cast(Any, execution_account_type),
            execution_pdt_rule=cast(Any, execution_pdt_rule),
            execution_swing_only=bool(execution_swing_only),
            ml_accelerator=cast(Any, ml_accelerator),
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


def _is_workflow_run(run: dict[str, object]) -> bool:
    return str(run.get("run_kind", "step")) == "workflow"


def _workflow_progress(run: dict[str, object]) -> tuple[int, int, float, str]:
    total = max(to_int(run.get("workflow_total_steps", 0)), 0)
    completed = max(to_int(run.get("workflow_completed_steps", 0)), 0)
    fraction = min((completed / total), 1.0) if total else 0.0
    current_step = str(run.get("workflow_current_step_label") or "").strip()
    label = f"{completed}/{total} étapes terminées" if total else "Progression indisponible"
    if total and current_step and str(run.get("status", "")) in {"starting", "running"}:
        label = f"{label} — en cours : {current_step}"
    return completed, total, fraction, label


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


def _render_workflow_launcher(options: PipelineLaunchOptions, live_confirmed: bool, db_config: dict[str, str | None]) -> None:
    active_runs, _ = _merge_runs()
    active_workflows = [run for run in active_runs if _is_workflow_run(run)]
    has_other_active_runs = any(not _is_workflow_run(run) for run in active_runs)
    execution_locked = options.execution_mode == "live" and not live_confirmed

    with st.container(border=True):
        st.subheader("🚀 Workflow complet 1 → 12")
        st.caption(
            "Lance automatiquement les 12 étapes du pipeline dans l'ordre. "
            "Les sous-runs restent historisés individuellement, et ce workflow fournit une vue globale avec logs consolidés."
        )

        if active_workflows:
            workflow_run = active_workflows[0]
            _, _, progress_fraction, progress_label = _workflow_progress(workflow_run)
            st.info(f"Workflow déjà actif : `{workflow_run.get('run_id', '')}`")
            st.progress(progress_fraction)
            st.caption(progress_label)
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
                record = start_pipeline_workflow(options, db_config=db_config)
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
            workflow_cols[0].metric("Type", "Workflow 1 → 12")
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
    cols[1].metric("Durée", format_duration_hhmmss(record.get("duration_seconds", 0.0)))
    cols[2].metric("stdout", to_int(record.get("stdout_lines", 0)))
    cols[3].metric("stderr", to_int(record.get("stderr_lines", 0)))
    st.caption(
        f"Début : `{record.get('executed_at', '—')}` | Fin : `{record.get('finished_at') or '—'}` | "
        f"Compte : `{record.get('account_id') or 'global'}`"
    )


def _render_import_news_panel(
    options: PipelineLaunchOptions,
    db_config: dict[str, str | None],
    *,
    workflow_active: bool,
    active_by_step: dict[str, list[dict[str, object]]],
    all_runs: list[dict[str, object]],
    latest_by_step: dict[str, dict[str, object]],
) -> None:
    today = date.today()
    default_start = cast(date, st.session_state.get(IMPORT_NEWS_START_DATE_KEY, today - timedelta(days=7)))
    default_end = cast(date, st.session_state.get(IMPORT_NEWS_END_DATE_KEY, today))

    with st.container(border=True):
        st.markdown("**5.bis Import des news brutes**")
        st.caption(
            "Lance `event_sentiment/importe_news.py` avec une date de début et une date de fin. "
            "Ce run peut être utilisé avant le Sentiment Pipeline complet pour réinjecter une période précise."
        )

        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_value = cast(
                date,
                st.date_input(
                    "Date de début",
                    value=default_start,
                    key=IMPORT_NEWS_START_DATE_KEY,
                    format="YYYY-MM-DD",
                ),
            )
        with date_col2:
            end_value = cast(
                date,
                st.date_input(
                    "Date de fin",
                    value=default_end,
                    key=IMPORT_NEWS_END_DATE_KEY,
                    format="YYYY-MM-DD",
                ),
            )

        import_options = replace(
            options,
            news_import_start_date=start_value.isoformat(),
            news_import_end_date=end_value.isoformat(),
        )
        import_command_preview = format_command_for_display(build_pipeline_command("import_news", import_options))
        st.code(import_command_preview, language="powershell")

        import_active_runs = active_by_step.get("import_news", [])
        locked_by_sentiment = bool(active_by_step.get("sentiment_pipeline"))
        import_locked = workflow_active or locked_by_sentiment

        if workflow_active:
            st.warning("Un workflow complet est en cours : l'import manuel de news est temporairement désactivé.")
        elif locked_by_sentiment:
            st.warning("Le Sentiment Pipeline est déjà actif : attendez sa fin avant de relancer un import de news.")

        if start_value > end_value:
            st.error("La date de début doit être antérieure ou égale à la date de fin.")
        elif import_active_runs:
            st.info(f"{len(import_active_runs)} import(s) de news déjà actif(s).")
            for run in import_active_runs:
                run_id = str(run.get("run_id", ""))
                st.caption(f"Actif : `{run_id}`")
                if st.button("⏹️ Arrêter cet import", key=f"stop_import_news_run_{run_id}", use_container_width=True):
                    stop_pipeline_run(run_id)
                    st.rerun()
        else:
            run_clicked = st.button(
                "📰 Importer les news sur la période",
                key="run_pipeline_import_news",
                type="primary",
                use_container_width=True,
                disabled=import_locked or start_value > end_value,
            )
            if run_clicked:
                record = start_pipeline_run(
                    "import_news",
                    "5.bis Import News",
                    import_options,
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
                st.success(f"Import news démarré en arrière-plan : `{record.run_id}`")
                st.rerun()

        _render_step_result(latest_by_step.get("import_news"))


@st.fragment(run_every="2s")
def _render_step_panels(options: PipelineLaunchOptions, live_confirmed: bool, db_config: dict[str, str | None]) -> None:
    active_runs, all_runs = _merge_runs()
    latest_by_step = _latest_run_by_step(all_runs)
    workflow_active = any(_is_workflow_run(run) for run in active_runs)
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
                if step.key == "alpha_scanner":
                    st.caption(
                        "🎛️ Preset strict Alpha Scanner : "
                        f"`{'activé' if options.alpha_scanner_use_strict_preset else 'désactivé'}`"
                    )
                if step.key == "execution":
                    effective_pdt = "off" if options.execution_account_type == "cash" else options.execution_pdt_rule
                    st.caption(
                        "⚖️ Contraintes d'exécution : "
                        f"compte=`{options.execution_account_type}` | pdt=`{effective_pdt}` | swing_only=`{options.execution_swing_only}`"
                    )
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
                        disabled=execution_locked or workflow_active,
                    )
                    if execution_locked:
                        st.warning("Confirmez d'abord le mode LIVE dans les paramètres ci-dessus.")
                    if workflow_active:
                        st.warning("Un workflow complet est en cours : le lancement manuel des étapes est temporairement désactivé.")

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
            if step.key == "sentiment_pipeline":
                _render_import_news_panel(
                    options,
                    db_config,
                    workflow_active=workflow_active,
                    active_by_step=active_by_step,
                    all_runs=all_runs,
                    latest_by_step=latest_by_step,
                )


def render() -> None:
    st.header("🔄 Pipeline Quotidien")
    st.caption("Ordre d'exécution strict — chaque étape dépend de la précédente.")

    options, live_confirmed = _build_launch_options()
    db_config = get_runtime_db_config()

    _render_workflow_launcher(options, live_confirmed, db_config)
    _render_runtime_center()
    _render_step_panels(options, live_confirmed, db_config)


run_page_if_standalone(__name__, render)
