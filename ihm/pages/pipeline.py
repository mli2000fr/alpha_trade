"""ihm/pages/pipeline.py — Vue séquentielle et pilotage asynchrone du pipeline métier.

**Phase 6.2 (Backlog L10)** : ce fichier a été découpé en sous-modules
``_shared``, ``_workflow``, ``_data_integrity``, ``_execution_center``,
``_alpha_scanner_diagnostics`` et ``_watcher_block``. Les imports historiques
``from ihm.pages.pipeline import X`` continuent de fonctionner via les
ré-exports ci-dessous.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import streamlit as st

from ihm.components.watcher_documentation import render_watcher_documentation_panel
from ihm.pages import run_page_if_standalone
from ihm.pages._alpha_scanner_diagnostics import (
    _alpha_scanner_dependency_block_reason,
    _collect_alpha_scanner_dependency_threshold_inputs,
    _prime_alpha_scanner_dependency_threshold_state,
    _render_alpha_scanner_dependency_diagnostic,
    _render_alpha_scanner_dependency_threshold_editor,
    _render_dependency_action_feedback,
    _render_dependency_health_inline,
    _set_alpha_scanner_dependency_threshold_state,
    _threshold_widget_key,
)
from ihm.pages._data_integrity import _render_import_news_panel
from ihm.pages._execution_center import (
    CAPITAL_PRESET_KEY,
    DETECTED_CAPITAL_PRESET_ACCOUNT_KEY,
    DETECTED_CAPITAL_PRESET_KEY,
    DETECTED_ACCOUNT_TYPE_KEY,
    DETECTED_PDT_RULE_KEY,
    _apply_execution_prefills,
    _build_execution_prefill_caption,
    _format_capital_preset_label,
    _build_launch_options,
)
from ihm.pages._shared import (
    ALPHA_SCANNER_DEPENDENCY_ACTION_RUNS_KEY,
    ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY,
    ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_CAPTION,
    ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_TITLE,
    ALPHA_SCANNER_PARAMS_CAPTION,
    ALPHA_SCANNER_PARAMS_TITLE,
    COMPARE_RUNS_KEY,
    EARNINGS_CUSTOM_WINDOW_KEY,
    EXECUTION_DEFAULTS_ACCOUNT_KEY,
    IMPORT_NEWS_END_DATE_KEY,
    IMPORT_NEWS_START_DATE_KEY,
    LOG_FILTER_KEY,
    ML_PENDING_SELECTED_SYMBOL_KEY,
    NAVIGATION_TARGET_PAGE_KEY,
    PENDING_COMPARE_RUNS_KEY,
    PENDING_SELECTED_RUN_KEY,
    PipelineLaunchOptions,
    SCREENER_PARAMS_CAPTION,
    SCREENER_PARAMS_TITLE,
    SELECTED_RUN_KEY,
    TAIL_LINES,
    _is_workflow_run,
    _launch_pipeline_step,
    _pipeline_step_label,
    _record_dependency_action_run,
    _render_log_block,
    _render_run_summary,
    _render_step_result,
    _sanitize_compare_ids,
    _status_badge,
    _tail_text,
    _to_optional_positive_int,
    _workflow_progress,
    get_pipeline_auxiliary_steps,
    get_pipeline_steps,
)
from ihm.pages._watcher_block import (
    _build_watcher_handoff_rows,
    _render_watcher_handoff_panel,
)
from ihm.pages._workflow import (
    _build_history_rows,
    _latest_run_by_step,
    _merge_runs,
    _prime_runtime_center_state,
    _render_runtime_center,
    _render_workflow_launcher,
)
from ihm.services.db import get_runtime_db_config
from ihm.services.ml_artifacts import list_ml_artifact_symbols
from ihm.services.pipeline_runner import (
    build_pipeline_command,
    format_command_for_display,
)
from ihm.services.process_registry import stop_pipeline_run
from ihm.services.queries import get_alpha_scanner_dependency_diagnostic


def _build_execution_mode_banner_payload(
    options: PipelineLaunchOptions,
    *,
    detected_broker_mode: str | None = None,
) -> tuple[str, str]:
    mode = str(options.execution_mode or "simulate").strip().lower() or "simulate"
    account_id = str(options.account_id or "default")
    detected = (detected_broker_mode or "").strip().lower() or None

    if mode == "live":
        severity = "error"
        message = (
            f"🔴 **MODE LIVE ACTIF** — les lancements de l'étape 12 enverront de vrais ordres Alpaca "
            f"sur le compte `{account_id}`."
        )
    elif mode == "paper":
        severity = "success"
        message = (
            f"🟢 **MODE PAPER ACTIF** — les lancements de l'étape 12 enverront des ordres sur le compte "
            f"paper Alpaca `{account_id}`."
        )
    else:
        severity = "warning"
        message = (
            f"🟡 **MODE SIMULATION ACTIF** — aucun ordre ne sera envoyé à Alpaca pour le compte `{account_id}` ; "
            "l'étape 12 reste un dry-run local."
        )

    if detected in {"paper", "live"}:
        message += f" Mode broker détecté pour ce compte : `{detected}`."
        if mode in {"paper", "live"} and mode != detected:
            severity = "error"
            message += (
                " ⚠️ Incohérence : le mode d'exécution choisi ne correspond pas au mode broker configuré pour ce compte. "
                "Basculez le sélecteur `Mode Execution` sur la même valeur pour éviter un run invalide."
            )

    return severity, message


def _build_execution_account_banner_payload(
    options: PipelineLaunchOptions,
    *,
    detected_account_type: str | None = None,
    detected_pdt_rule: str | None = None,
) -> tuple[str, str]:
    account_type = str(options.execution_account_type or "cash").strip().lower() or "cash"
    pdt_rule = str(options.execution_pdt_rule or "off").strip().lower() or "off"

    if account_type == "cash" and pdt_rule == "off":
        severity = "success"
        message = (
            "🟢 **PARAMÈTRES COMPTE EXÉCUTION — PROFIL SWING CASH** — "
            f"l'étape 12 utilisera `type de compte={account_type}` et `règle PDT={pdt_rule}`."
        )
    elif account_type == "margin" and pdt_rule == "auto":
        severity = "warning"
        message = (
            "🟡 **PARAMÈTRES COMPTE EXÉCUTION — PROFIL MARGIN / PDT** — "
            f"l'étape 12 utilisera `type de compte={account_type}` et `règle PDT={pdt_rule}`."
        )
    else:
        severity = "info"
        message = (
            "ℹ️ **PARAMÈTRES COMPTE EXÉCUTION — CONFIGURATION SPÉCIFIQUE** — "
            f"l'étape 12 utilisera `type de compte={account_type}` et `règle PDT={pdt_rule}`."
        )

    detected_parts: list[str] = []
    mismatches: list[str] = []
    normalized_detected_account_type = (detected_account_type or "").strip().lower() or None
    normalized_detected_pdt_rule = (detected_pdt_rule or "").strip().lower() or None
    if normalized_detected_account_type in {"margin", "cash"}:
        detected_parts.append(f"type broker détecté : `{normalized_detected_account_type}`")
        if account_type != normalized_detected_account_type:
            mismatches.append("type de compte")
    if normalized_detected_pdt_rule in {"auto", "off"}:
        detected_parts.append(f"PDT détecté : `{normalized_detected_pdt_rule}`")
        if pdt_rule != normalized_detected_pdt_rule:
            mismatches.append("règle PDT")

    if detected_parts:
        message += " Préremplissage broker pour ce compte : " + " ; ".join(detected_parts) + "."
    if mismatches:
        severity = "error"
        labels = ", ".join(mismatches)
        message += (
            f" ⚠️ Incohérence critique : le réglage actuellement sélectionné diffère du broker détecté pour {labels}."
        )

    return severity, message


def _build_capital_preset_banner_payload(
    selected_preset_key: str | None,
    *,
    detected_preset_key: str | None = None,
    detected_equity: float | None = None,
) -> tuple[str, str] | None:
    selected_key = str(selected_preset_key or "").strip() or None
    detected_key = str(detected_preset_key or "").strip() or None
    selected_label = _format_capital_preset_label(selected_key or "custom") if selected_key else None
    detected_label = _format_capital_preset_label(detected_key) if detected_key else None
    equity_suffix = f" (equity détectée ≈ `{detected_equity:,.2f}` $)" if detected_equity is not None else ""

    if selected_key is None and detected_key is None:
        return None
    if selected_key == "custom":
        message = "ℹ️ **PANIER CAPITAL** — mode `Personnalisé` actif"
        if detected_label is not None:
            message += f" ; panier recommandé pour ce compte : `{detected_label}`{equity_suffix}."
        else:
            message += "."
        return "info", message
    if selected_label is None:
        return None
    if detected_key is not None and selected_key == detected_key:
        return "success", f"🧺 **PANIER CAPITAL APPLIQUÉ** — `{selected_label}`{equity_suffix}."
    if detected_label is not None:
        return (
            "warning",
            f"🧺 **PANIER CAPITAL FORCÉ** — `{selected_label}`. Panier recommandé pour ce compte : `{detected_label}`{equity_suffix}.",
        )
    return "info", f"🧺 **PANIER CAPITAL SÉLECTIONNÉ** — `{selected_label}`."


def _build_pipeline_scope_alert_lines() -> tuple[str, str]:
    return (
        "⚠️ Les étapes **3→10** recalculent des données globales partagées entre comptes.",
        "✅ Les étapes **11→12** restent spécifiques au compte sélectionné.",
    )


def _render_execution_mode_banner(options: PipelineLaunchOptions) -> None:
    detected_mode = None
    detected_account = str(st.session_state.get("pipeline_detected_broker_mode_account_id") or "").strip()
    if detected_account == str(options.account_id or "").strip():
        detected_mode = str(st.session_state.get("pipeline_detected_broker_mode") or "").strip() or None
        detected_account_type = str(st.session_state.get(DETECTED_ACCOUNT_TYPE_KEY) or "").strip() or None
        detected_pdt_rule = str(st.session_state.get(DETECTED_PDT_RULE_KEY) or "").strip() or None
        detected_capital_preset = str(st.session_state.get(DETECTED_CAPITAL_PRESET_KEY) or "").strip() or None
        selected_capital_preset = str(st.session_state.get(CAPITAL_PRESET_KEY) or "").strip() or None
        detected_equity = float(options.risk_account_equity) if options.risk_account_equity > 0 else None
    else:
        detected_account_type = None
        detected_pdt_rule = None
        detected_capital_preset = None
        selected_capital_preset = None
        detected_equity = None
    severity, message = _build_execution_mode_banner_payload(options, detected_broker_mode=detected_mode)
    getattr(st, severity)(message)
    capital_preset_banner = _build_capital_preset_banner_payload(
        selected_capital_preset,
        detected_preset_key=detected_capital_preset,
        detected_equity=detected_equity,
    )
    if capital_preset_banner is not None:
        preset_severity, preset_message = capital_preset_banner
        getattr(st, preset_severity)(preset_message)
    account_severity, account_message = _build_execution_account_banner_payload(
        options,
        detected_account_type=detected_account_type,
        detected_pdt_rule=detected_pdt_rule,
    )
    getattr(st, account_severity)(account_message)


def _render_ml_inspection_link(step_key: str) -> None:
    if step_key not in {"ml_train", "ml_predict"}:
        return
    symbols = list_ml_artifact_symbols()
    if not symbols:
        st.caption("Aucun artefact ML détecté pour proposer une navigation ciblée vers la page ML.")
        return
    inspect_key = f"pipeline_ml_inspect_symbol_{step_key}"
    selected_symbol = st.selectbox(
        "Inspecter un symbole dans la page ML",
        options=symbols,
        format_func=lambda sym: f"{sym} — modèle global" if sym.startswith("__") else sym,
        key=inspect_key,
    )
    if st.button("🔎 Ouvrir dans la page ML", key=f"pipeline_open_ml_{step_key}", use_container_width=True):
        st.session_state[ML_PENDING_SELECTED_SYMBOL_KEY] = selected_symbol
        st.session_state[NAVIGATION_TARGET_PAGE_KEY] = "ml"
        st.rerun()


def _render_ml_train_all_symbols_block(
    options: PipelineLaunchOptions,
    *,
    workflow_active: bool,
    active_for_step: list[dict[str, object]],
    db_config: dict[str, str | None],
    all_runs: list[dict[str, object]],
) -> None:
    # NOTE: l'ancien comptage `SELECT COUNT(DISTINCT symbol) FROM stock_bars_daily`
    # a été retiré car il ralentissait l'affichage de la page Pipeline (12k+ lignes
    # à scanner à chaque rendu). Le CLI `ml_train --symbol-source stock_bars_daily`
    # gère lui-même le cas "univers vide" et journalise le résultat.
    disabled = workflow_active or bool(active_for_step)
    if workflow_active:
        st.caption("Workflow complet en cours : le lancement 'tous les symbols' est temporairement désactivé.")
    elif active_for_step:
        st.caption("Un run `ML Train` est déjà actif : le lancement 'tous les symbols' attend la fin de ce run.")

    if st.button(
        "Entrainer tous les symbols",
        key="run_pipeline_step_ml_train_all_symbols",
        use_container_width=True,
        disabled=disabled,
    ):
        _launch_pipeline_step(
            "ml_train",
            "9. ML Train (Model Factory) — tous les symbols",
            replace(options, ml_train_symbol_source="stock_bars_daily"),
            db_config,
            all_runs,
        )


def _render_launchable_step_panel(
    step: Any,
    options: PipelineLaunchOptions,
    live_confirmed: bool,
    db_config: dict[str, str | None],
    *,
    workflow_active: bool,
    active_by_step: dict[str, list[dict[str, object]]],
    all_runs: list[dict[str, object]],
    latest_by_step: dict[str, dict[str, object]],
    dependency_diagnostic: dict[str, object] | None,
) -> None:
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
            if step.key in {"sync_latest_quotes", "sync_earnings_calendar"}:
                _render_dependency_health_inline(step.key, dependency_diagnostic)
            if step.key == "execution":
                effective_pdt = "off" if options.execution_account_type == "cash" else options.execution_pdt_rule
                st.caption(
                    "⚖️ Contraintes d'exécution : "
                    f"compte=`{options.execution_account_type}` | pdt=`{effective_pdt}` | swing_only=`{options.execution_swing_only}`"
                )
            if step.key == "alpha_scanner":
                _render_alpha_scanner_dependency_diagnostic(
                    dependency_diagnostic,
                    options,
                    db_config,
                    workflow_active=workflow_active,
                    active_by_step=active_by_step,
                    all_runs=all_runs,
                    latest_by_step=latest_by_step,
                )
            st.code(command_preview, language="powershell")

        with action_col:
            execution_locked = step.key == "execution" and options.execution_mode == "live" and not live_confirmed
            dependency_locked_reason = (
                _alpha_scanner_dependency_block_reason(dependency_diagnostic) if step.key == "alpha_scanner" else None
            )
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
                    disabled=execution_locked or workflow_active or dependency_locked_reason is not None,
                    help=dependency_locked_reason,
                )
                if execution_locked:
                    st.warning("Confirmez d'abord le mode LIVE dans les paramètres ci-dessus.")
                if workflow_active:
                    st.warning("Un workflow complet est en cours : le lancement manuel des étapes est temporairement désactivé.")
                if dependency_locked_reason is not None:
                    st.error(dependency_locked_reason)

                if run_clicked:
                    _launch_pipeline_step(
                        step.key,
                        f"{step.num}. {step.name}",
                        options,
                        db_config,
                        all_runs,
                    )

            if step.key == "ml_train":
                st.divider()
                _render_ml_train_all_symbols_block(
                    options,
                    workflow_active=workflow_active,
                    active_for_step=active_for_step,
                    db_config=db_config,
                    all_runs=all_runs,
                )

            if step.key in {"ml_train", "ml_predict"}:
                st.divider()
                _render_ml_inspection_link(step.key)

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


@st.fragment(run_every="2s")
def _render_step_panels(options: PipelineLaunchOptions, live_confirmed: bool, db_config: dict[str, str | None]) -> None:
    active_runs, all_runs = _merge_runs()
    latest_by_step = _latest_run_by_step(all_runs)
    dependency_diagnostic = get_alpha_scanner_dependency_diagnostic()
    workflow_active = any(_is_workflow_run(run) for run in active_runs)
    active_by_step: dict[str, list[dict[str, object]]] = {}
    for run in active_runs:
        active_by_step.setdefault(str(run.get("step_key", "")), []).append(run)

    auxiliary_steps = get_pipeline_auxiliary_steps()
    if auxiliary_steps:
        st.subheader("🧱 Bootstrap / maintenance Data Integrity")
        st.caption(
            "Ces entrées correspondent aux scripts supplémentaires du module `dataIntegrityEngine`. "
            "Elles ne font pas partie du workflow quotidien 1 → 14, mais elles sont pilotables depuis l'IHM avec leurs options réelles pour les remises à plat, réinitialisations ou rafraîchissements ciblés."
        )
        for step in auxiliary_steps:
            _render_launchable_step_panel(
                step,
                options,
                live_confirmed,
                db_config,
                workflow_active=workflow_active,
                active_by_step=active_by_step,
                all_runs=all_runs,
                latest_by_step=latest_by_step,
                dependency_diagnostic=dependency_diagnostic,
            )

    st.subheader("🪜 Étapes pilotables — cœur quotidien 1 → 12 + options 13/14")
    st.caption(
        "Les étapes 1 à 12 constituent le workflow quotidien principal. "
        "Les étapes 13 et 14 sont des extensions post-exécution, pilotables séparément et non incluses par défaut dans le lancement workflow."
    )
    for step in get_pipeline_steps():
        _render_launchable_step_panel(
            step,
            options,
            live_confirmed,
            db_config,
            workflow_active=workflow_active,
            active_by_step=active_by_step,
            all_runs=all_runs,
            latest_by_step=latest_by_step,
            dependency_diagnostic=dependency_diagnostic,
        )
        if step.key == "execution":
            _render_watcher_handoff_panel(options)


def render() -> None:
    st.header("🔄 Pipeline Quotidien")
    st.caption("Ordre d'exécution strict — chaque étape dépend de la précédente.")

    options, live_confirmed = _build_launch_options()
    _render_execution_mode_banner(options)
    db_config = get_runtime_db_config()

    _render_workflow_launcher(options, live_confirmed, db_config)
    _render_runtime_center()
    scope_alert_global, scope_alert_account = _build_pipeline_scope_alert_lines()
    st.warning(scope_alert_global)
    st.success(scope_alert_account)
    _render_step_panels(options, live_confirmed, db_config)


run_page_if_standalone(__name__, render)
