"""ihm/pages/pipeline.py — Vue séquentielle et pilotage asynchrone du pipeline métier."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Any, cast

import pandas as pd
import streamlit as st

from ihm.components.alpha_scanner_dependency import (
    dependency_badge,
    format_dependency_latest_date,
    format_dependency_symbol_count,
    get_dependency_payload,
    render_dependency_metrics,
)
from ihm.components.metrics import format_duration_hhmmss, to_int
from ihm.components.run_summary import render_run_summary_block
from ihm.pages import run_page_if_standalone
from ihm.services.account_defaults import (
    PDT_EQUITY_THRESHOLD,
    PipelineExecutionDefaults,
    get_pipeline_execution_defaults,
)
from ihm.services.db import get_runtime_db_config
from ihm.services.db import reset_db_caches
from ihm.services.ml_artifacts import list_ml_artifact_symbols
from ihm.services.pipeline_runner import (
    DEFAULT_DATA_INTEGRITY_FUNDAMENTALS_LOG_EVERY,
    DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS,
    DEFAULT_DATA_INTEGRITY_QUOTES_BATCH_SIZE,
    DEFAULT_SCREENER_BENCHMARK_SYMBOL,
    DEFAULT_SCREENER_CHUNK_SIZE,
    DEFAULT_SCREENER_ENABLE_TWO_PASS_LOADING,
    DEFAULT_SCREENER_FIRST_PASS_WINDOW_DAYS,
    DEFAULT_SCREENER_HISTORICAL_RANGE_LOOKBACK_DAYS,
    DEFAULT_SCREENER_LIQUIDITY_THRESHOLD_USD,
    DEFAULT_SCREENER_MIN_HISTORICAL_RANGE_SCORE,
    DEFAULT_SCREENER_MIN_RELATIVE_STRENGTH_INDEX,
    DEFAULT_SIGNAL_AGGREGATOR_LOG_LEVEL,
    DEFAULT_SIGNAL_AGGREGATOR_LOOKBACK_DAYS,
    DEFAULT_SIGNAL_AGGREGATOR_MACRO_WEIGHT,
    DEFAULT_SIGNAL_AGGREGATOR_MIN_NEWS_COUNT,
    DEFAULT_SIGNAL_AGGREGATOR_SENTIMENT_WEIGHT,
    DEFAULT_SIGNAL_AGGREGATOR_TIME_DECAY_HALF_LIFE_DAYS,
    DEFAULT_SELECTOR_CHUNK_SIZE,
    DEFAULT_SELECTOR_EARNINGS_BLACKOUT_DAYS,
    DEFAULT_SELECTOR_LIQUIDITY_THRESHOLD,
    DEFAULT_SELECTOR_LOG_LEVEL,
    DEFAULT_SELECTOR_MAX_ANOMALY_COUNT,
    DEFAULT_SELECTOR_MAX_ATR_PCT_20,
    DEFAULT_SELECTOR_MAX_SPREAD_BPS,
    DEFAULT_SELECTOR_MAX_VOLATILITY_RATIO,
    DEFAULT_SELECTOR_MIN_ATR_PCT_20,
    DEFAULT_SELECTOR_MIN_BETA_126,
    DEFAULT_SELECTOR_MIN_CLOSE,
    DEFAULT_SELECTOR_MIN_HIGH_52W_PROXIMITY,
    DEFAULT_SELECTOR_MIN_MARKET_CAP,
    DEFAULT_SELECTOR_MIN_RELATIVE_STRENGTH_INDEX,
    DEFAULT_SELECTOR_MIN_WEEKLY_TREND_SCORE,
    DEFAULT_SELECTOR_SECTOR_CAP_RATIO,
    DEFAULT_SELECTOR_SELECTION_SIZE,
    PipelineLaunchOptions,
    build_pipeline_command,
    format_command_for_display,
    get_pipeline_auxiliary_steps,
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
from ihm.services.queries import (
    ALPHA_SCANNER_DEPENDENCY_THRESHOLDS,
    get_alpha_scanner_dependency_diagnostic,
    get_alpha_scanner_dependency_thresholds,
)
from ihm.services.run_summary import build_run_summary_caption, get_run_summary
from ihm.services.screener_preferences import (
    reset_persisted_alpha_scanner_dependency_thresholds,
    save_persisted_alpha_scanner_dependency_thresholds,
)

SELECTED_RUN_KEY = "ihm_pipeline_selected_run_id"
COMPARE_RUNS_KEY = "ihm_pipeline_compare_run_ids"
LOG_FILTER_KEY = "ihm_pipeline_log_filter"
PENDING_SELECTED_RUN_KEY = "ihm_pipeline_pending_selected_run_id"
PENDING_COMPARE_RUNS_KEY = "ihm_pipeline_pending_compare_run_ids"
TAIL_LINES = 250
EXECUTION_DEFAULTS_ACCOUNT_KEY = "pipeline_execution_defaults_applied_account_id"
IMPORT_NEWS_START_DATE_KEY = "pipeline_import_news_start_date"
IMPORT_NEWS_END_DATE_KEY = "pipeline_import_news_end_date"
ML_SELECTED_SYMBOL_KEY = "ihm_ml_selected_symbol"
NAVIGATION_TARGET_PAGE_KEY = "ihm_navigation_target_page"
EARNINGS_CUSTOM_WINDOW_KEY = "pipeline_data_integrity_earnings_custom_window"
ALPHA_SCANNER_DEPENDENCY_ACTION_RUNS_KEY = "pipeline_alpha_scanner_dependency_action_runs"
ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY = "pipeline_alpha_scanner_dependency_thresholds_flash"


def _tail_text(value: str, max_lines: int = TAIL_LINES) -> str:
    lines = value.splitlines()
    if len(lines) <= max_lines:
        return value
    return "\n".join(lines[-max_lines:])


def _to_optional_positive_int(value: int | float | None) -> int | None:
    if value is None:
        return None
    normalized = int(value)
    return normalized if normalized > 0 else None


def _render_run_summary(record: dict[str, object] | None, *, compact: bool = False) -> None:
    summary = get_run_summary(record)
    if not summary:
        return

    render_run_summary_block(record, title="**Résumé métier**", max_metrics=6, heading_level="markdown", show_caption=False)

    if "history_status_counts" in summary and isinstance(summary["history_status_counts"], dict):
        st.caption("Répartition history_status")
        st.dataframe(
            pd.DataFrame(
                [
                    {"statut": key, "compteur": value}
                    for key, value in cast(dict[str, object], summary["history_status_counts"]).items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    if "status_breakdown" in summary and isinstance(summary["status_breakdown"], dict):
        st.caption("Répartition des statuts")
        st.dataframe(
            pd.DataFrame(
                [
                    {"statut": key, "compteur": value}
                    for key, value in cast(dict[str, object], summary["status_breakdown"]).items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    workflow_step_summaries = summary.get("workflow_step_summaries")
    if isinstance(workflow_step_summaries, list) and workflow_step_summaries:
        st.caption("Résumé agrégé par sous-run workflow")
        rows = []
        for step_summary in workflow_step_summaries:
            if not isinstance(step_summary, dict):
                continue
            rows.append(
                {
                    "étape": step_summary.get("step_label") or step_summary.get("step_key") or "—",
                    "statut": step_summary.get("status") or "—",
                    "run_id": step_summary.get("run_id") or "—",
                    "résumé métier": step_summary.get("caption") or "—",
                }
            )
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if not compact:
        with st.expander("Voir le payload résumé brut", expanded=False):
            st.json(summary)


def _render_log_block(title: str, content: str, *, key: str, expanded: bool = False) -> None:
    tailed = _tail_text(content)
    suffix = ""
    if tailed != content:
        suffix = f" — affichage limité aux {TAIL_LINES} dernières lignes"
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


def _alpha_scanner_dependency_block_reason(dependency_diagnostic: dict[str, object] | None) -> str | None:
    if not isinstance(dependency_diagnostic, dict) or not bool(dependency_diagnostic.get("all_red")):
        return None
    return (
        "Alpha Scanner est désactivé : `stock_quote_snapshots` et `stock_earnings_calendar` sont tous deux rouges "
        "(vides, trop peu couverts ou trop anciens). Lancez d'abord les synchronisations depuis le diagnostic ci-dessous."
    )


def _pipeline_step_label(step_key: str) -> str:
    for step in (*get_pipeline_auxiliary_steps(), *get_pipeline_steps()):
        if step.key == step_key:
            return f"{step.num}. {step.name}"
    return step_key


def _threshold_widget_key(step_key: str, metric_key: str) -> str:
    return f"pipeline_alpha_scanner_threshold_{step_key}_{metric_key}"


def _prime_alpha_scanner_dependency_threshold_state() -> dict[str, dict[str, float]]:
    thresholds = get_alpha_scanner_dependency_thresholds()
    for step_key, metrics in thresholds.items():
        for metric_key, metric_value in metrics.items():
            widget_key = _threshold_widget_key(step_key, metric_key)
            if widget_key not in st.session_state:
                st.session_state[widget_key] = float(metric_value)
    return thresholds


def _collect_alpha_scanner_dependency_threshold_inputs() -> dict[str, dict[str, float]]:
    payload: dict[str, dict[str, float]] = {}
    for step_key, metrics in ALPHA_SCANNER_DEPENDENCY_THRESHOLDS.items():
        payload[step_key] = {}
        for metric_key, default_value in metrics.items():
            widget_key = _threshold_widget_key(step_key, metric_key)
            payload[step_key][metric_key] = float(st.session_state.get(widget_key, default_value))
    return payload


def _set_alpha_scanner_dependency_threshold_state(thresholds: dict[str, dict[str, float]]) -> None:
    for step_key, metrics in thresholds.items():
        for metric_key, metric_value in metrics.items():
            st.session_state[_threshold_widget_key(step_key, metric_key)] = float(metric_value)


def _render_alpha_scanner_dependency_threshold_editor() -> None:
    current_thresholds = _prime_alpha_scanner_dependency_threshold_state()
    flash_message = st.session_state.pop(ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY, None)
    if isinstance(flash_message, str) and flash_message.strip():
        st.success(flash_message)

    with st.expander("🧪 Seuils du diagnostic Alpha Scanner", expanded=False):
        st.caption(
            "Ces seuils pilotent les états vert / orange / rouge du diagnostic quotes/earnings affiché dans `Pipeline`, `Screening` et `Overview`."
        )
        quotes_col1, quotes_col2 = st.columns(2)
        with quotes_col1:
            st.markdown("**Sync Latest Quotes**")
            st.number_input(
                "Quotes — couverture orange (%)",
                min_value=0.0,
                value=float(current_thresholds["sync_latest_quotes"]["coverage_warn_pct"]),
                step=1.0,
                format="%.1f",
                key=_threshold_widget_key("sync_latest_quotes", "coverage_warn_pct"),
            )
            st.number_input(
                "Quotes — couverture rouge (%)",
                min_value=0.0,
                value=float(current_thresholds["sync_latest_quotes"]["coverage_error_pct"]),
                step=1.0,
                format="%.1f",
                key=_threshold_widget_key("sync_latest_quotes", "coverage_error_pct"),
            )
        with quotes_col2:
            st.markdown("**Fraîcheur quotes**")
            st.number_input(
                "Quotes — âge orange (jours)",
                min_value=0.0,
                value=float(current_thresholds["sync_latest_quotes"]["max_age_warn_days"]),
                step=1.0,
                format="%.1f",
                key=_threshold_widget_key("sync_latest_quotes", "max_age_warn_days"),
            )
            st.number_input(
                "Quotes — âge rouge (jours)",
                min_value=0.0,
                value=float(current_thresholds["sync_latest_quotes"]["max_age_error_days"]),
                step=1.0,
                format="%.1f",
                key=_threshold_widget_key("sync_latest_quotes", "max_age_error_days"),
            )

        earnings_col1, earnings_col2 = st.columns(2)
        with earnings_col1:
            st.markdown("**Sync Earnings Calendar**")
            st.number_input(
                "Earnings — couverture orange (%)",
                min_value=0.0,
                value=float(current_thresholds["sync_earnings_calendar"]["coverage_warn_pct"]),
                step=1.0,
                format="%.1f",
                key=_threshold_widget_key("sync_earnings_calendar", "coverage_warn_pct"),
            )
            st.number_input(
                "Earnings — couverture rouge (%)",
                min_value=0.0,
                value=float(current_thresholds["sync_earnings_calendar"]["coverage_error_pct"]),
                step=1.0,
                format="%.1f",
                key=_threshold_widget_key("sync_earnings_calendar", "coverage_error_pct"),
            )
        with earnings_col2:
            st.markdown("**Horizon earnings**")
            st.number_input(
                "Earnings — horizon orange (jours)",
                min_value=0.0,
                value=float(current_thresholds["sync_earnings_calendar"]["min_horizon_warn_days"]),
                step=1.0,
                format="%.1f",
                key=_threshold_widget_key("sync_earnings_calendar", "min_horizon_warn_days"),
            )
            st.number_input(
                "Earnings — horizon rouge (jours)",
                min_value=0.0,
                value=float(current_thresholds["sync_earnings_calendar"]["min_horizon_error_days"]),
                step=1.0,
                format="%.1f",
                key=_threshold_widget_key("sync_earnings_calendar", "min_horizon_error_days"),
            )

        action_col1, action_col2 = st.columns([2, 1])
        with action_col1:
            if st.button("💾 Enregistrer les seuils diagnostic", key="save_alpha_scanner_dependency_thresholds", use_container_width=True):
                normalized = save_persisted_alpha_scanner_dependency_thresholds(
                    _collect_alpha_scanner_dependency_threshold_inputs(),
                    defaults=ALPHA_SCANNER_DEPENDENCY_THRESHOLDS,
                )
                _set_alpha_scanner_dependency_threshold_state(normalized)
                get_alpha_scanner_dependency_diagnostic.clear()
                reset_db_caches()
                st.session_state[ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY] = "Seuils du diagnostic Alpha Scanner enregistrés."
                st.rerun()
        with action_col2:
            if st.button("↩️ Reset défauts", key="reset_alpha_scanner_dependency_thresholds", use_container_width=True):
                reset_persisted_alpha_scanner_dependency_thresholds()
                _set_alpha_scanner_dependency_threshold_state(ALPHA_SCANNER_DEPENDENCY_THRESHOLDS)
                get_alpha_scanner_dependency_diagnostic.clear()
                reset_db_caches()
                st.session_state[ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY] = "Seuils du diagnostic Alpha Scanner réinitialisés aux valeurs par défaut."
                st.rerun()


def _record_dependency_action_run(step_key: str, run_id: str) -> None:
    existing = st.session_state.get(ALPHA_SCANNER_DEPENDENCY_ACTION_RUNS_KEY, {})
    tracked = dict(existing) if isinstance(existing, dict) else {}
    tracked[step_key] = run_id
    st.session_state[ALPHA_SCANNER_DEPENDENCY_ACTION_RUNS_KEY] = tracked


def _launch_pipeline_step(
    step_key: str,
    step_label: str,
    options: PipelineLaunchOptions,
    db_config: dict[str, str | None],
    all_runs: list[dict[str, object]],
    *,
    track_dependency_action: bool = False,
) -> None:
    record = start_pipeline_run(
        step_key,
        step_label,
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
    if track_dependency_action:
        _record_dependency_action_run(step_key, record.run_id)
    st.success(f"Run demarre en arriere-plan : `{record.run_id}`")
    st.rerun()


def _render_dependency_health_inline(step_key: str, dependency_diagnostic: dict[str, object] | None) -> None:
    payload = get_dependency_payload(dependency_diagnostic, step_key)
    if not payload:
        return
    st.caption(dependency_badge(str(payload.get("status") or "red"), str(payload.get("label") or step_key)))
    render_dependency_metrics(payload)


def _render_dependency_action_feedback(latest_by_step: dict[str, dict[str, object]]) -> None:
    tracked = st.session_state.get(ALPHA_SCANNER_DEPENDENCY_ACTION_RUNS_KEY, {})
    if not isinstance(tracked, dict) or not tracked:
        return

    rendered_feedback = False
    for step_key, run_id in tracked.items():
        if not isinstance(step_key, str) or not isinstance(run_id, str):
            continue
        record = latest_by_step.get(step_key)
        if not record or str(record.get("run_id", "")) != run_id:
            continue
        status = str(record.get("status", ""))
        label = _pipeline_step_label(step_key)
        if status == "completed":
            st.success(
                f"{label} terminé. Recharger les indicateurs dans ~60s (TTL cache IHM) ou utilisez le bouton ci-dessous."
            )
            rendered_feedback = True
        elif status in {"failed", "timeout", "stopped"}:
            st.error(f"{label} a échoué. Inspectez les logs du run `{run_id}` avant de relancer.")
            rendered_feedback = True
        elif status in {"starting", "running"}:
            st.info(f"{label} est en cours (`{run_id}`). Les indicateurs se mettront à jour automatiquement après succès.")
            rendered_feedback = True

    if rendered_feedback and st.button(
        "🔄 Rafraîchir maintenant",
        key="alpha_scanner_dependency_refresh_now",
        use_container_width=False,
    ):
        reset_db_caches()
        st.rerun()


def _render_alpha_scanner_dependency_diagnostic(
    dependency_diagnostic: dict[str, object] | None,
    options: PipelineLaunchOptions,
    db_config: dict[str, str | None],
    *,
    workflow_active: bool,
    active_by_step: dict[str, list[dict[str, object]]],
    all_runs: list[dict[str, object]],
    latest_by_step: dict[str, dict[str, object]],
) -> None:
    quotes_payload = get_dependency_payload(dependency_diagnostic, "sync_latest_quotes")
    earnings_payload = get_dependency_payload(dependency_diagnostic, "sync_earnings_calendar")
    if not quotes_payload or not earnings_payload:
        return

    statuses = [str(quotes_payload.get("status") or "red"), str(earnings_payload.get("status") or "red")]
    if all(status == "green" for status in statuses):
        st.success("Dépendances Alpha Scanner OK : quotes et earnings sont alimentés pour les filtres stricts.")
    elif all(status == "red" for status in statuses):
        st.error(
            "Alpha Scanner verrouillé : `stock_quote_snapshots` et `stock_earnings_calendar` sont tous deux rouges. "
            "Le lancement manuel est bloqué tant que les deux dépendances restent dans cet état."
        )
    else:
        st.warning(
            "Alpha Scanner détecte une couverture partielle sur ses dépendances quotes/earnings. "
            "Le scan reste visible mais le diagnostic ci-dessous est recommandé avant un run strict."
        )

    st.caption(
        f"{dependency_badge(str(quotes_payload.get('status') or 'red'), 'Quotes')} | "
        f"{dependency_badge(str(earnings_payload.get('status') or 'red'), 'Earnings')}"
    )

    with st.expander(
        "🩺 Diagnostic détaillé des dépendances Alpha Scanner",
        expanded=bool(dependency_diagnostic and dependency_diagnostic.get("all_red")),
    ):
        st.caption(
            "Pourquoi rouge/orange : une dépendance est vide, trop peu couverte ou trop ancienne. "
            "Le scan strict s'appuie sur ces tables pour `spread_bps` et `earnings_blackout`."
        )
        dep_col1, dep_col2 = st.columns(2)
        with dep_col1:
            st.markdown(f"**{dependency_badge(str(quotes_payload.get('status') or 'red'), 'Sync Latest Quotes')}**")
            render_dependency_metrics(quotes_payload)
            st.code(str(quotes_payload.get("command") or "python -m dataIntegrityEngine.sync_latest_quotes"), language="powershell")
        with dep_col2:
            st.markdown(f"**{dependency_badge(str(earnings_payload.get('status') or 'red'), 'Sync Earnings Calendar')}**")
            render_dependency_metrics(earnings_payload)
            st.code(str(earnings_payload.get("command") or "python -m dataIntegrityEngine.sync_earnings_calendar"), language="powershell")

        if workflow_active:
            st.warning("Un workflow complet est déjà actif : les actions rapides ci-dessous sont temporairement désactivées.")

        action_col1, action_col2 = st.columns(2)
        quick_actions = (
            ("sync_latest_quotes", action_col1, "⚡ Lancer Sync Latest Quotes"),
            ("sync_earnings_calendar", action_col2, "⚡ Lancer Sync Earnings Calendar"),
        )
        for dependency_step_key, column, button_label in quick_actions:
            active_runs = active_by_step.get(dependency_step_key, [])
            with column:
                if active_runs:
                    st.info(f"{_pipeline_step_label(dependency_step_key)} déjà actif.")
                if st.button(
                    button_label,
                    key=f"alpha_scanner_dependency_action_{dependency_step_key}",
                    type="primary",
                    use_container_width=True,
                    disabled=workflow_active or bool(active_runs),
                    help="Lance directement la synchronisation corrective depuis ce diagnostic.",
                ):
                    _launch_pipeline_step(
                        dependency_step_key,
                        _pipeline_step_label(dependency_step_key),
                        options,
                        db_config,
                        all_runs,
                        track_dependency_action=True,
                    )

        _render_dependency_action_feedback(latest_by_step)


def _build_launch_options() -> tuple[PipelineLaunchOptions, bool]:
    selected_account_id = cast(str | None, st.session_state.get("selected_account_id"))
    execution_defaults = _apply_execution_prefills(selected_account_id)

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

        st.markdown("#### Paramètres Model Factory")
        st.caption(
            "Ces options pilotent directement `python -m modelFactory --mode train`. "
            "L'objectif est d'aligner l'IHM sur la gouvernance multi-modèles réellement disponible côté backend."
        )

        ml_opt_col1, ml_opt_col2, ml_opt_col3 = st.columns(3)
        with ml_opt_col1:
            ml_include_sentiment = st.checkbox(
                "Inclure les features sentiment",
                value=bool(st.session_state.get("pipeline_ml_include_sentiment", True)),
                key="pipeline_ml_include_sentiment",
                help="Ajoute `--include-sentiment` à `ml_train`.",
            )
            ml_enable_lightgbm = st.checkbox(
                "Comparer LightGBM local",
                value=bool(st.session_state.get("pipeline_ml_enable_lightgbm", True)),
                key="pipeline_ml_enable_lightgbm",
                help="Ajoute `--compare-lightgbm`.",
            )
            ml_enable_catboost = st.checkbox(
                "Comparer CatBoost local",
                value=bool(st.session_state.get("pipeline_ml_enable_catboost", True)),
                key="pipeline_ml_enable_catboost",
                help="Ajoute `--enable-catboost`.",
            )
        with ml_opt_col2:
            ml_select_champion = st.checkbox(
                "Activer la sélection automatique du champion",
                value=bool(st.session_state.get("pipeline_ml_select_champion", True)),
                key="pipeline_ml_select_champion",
                help="Ajoute `--select-champion` et permet de servir automatiquement le meilleur modèle éligible.",
            )
            ml_champion_selection_metric = cast(
                str,
                st.selectbox(
                    "Métrique de sélection du champion",
                    options=["selection_score", "business_score", "auc"],
                    index=["selection_score", "business_score", "auc"].index(
                        cast(str, st.session_state.get("pipeline_ml_champion_selection_metric", "selection_score"))
                        if st.session_state.get("pipeline_ml_champion_selection_metric", "selection_score") in {"selection_score", "business_score", "auc"}
                        else "selection_score"
                    ),
                    key="pipeline_ml_champion_selection_metric",
                    disabled=not ml_select_champion,
                ),
            )
            ml_optimize_thresholds = st.checkbox(
                "Optimiser le seuil de décision",
                value=bool(st.session_state.get("pipeline_ml_optimize_thresholds", True)),
                key="pipeline_ml_optimize_thresholds",
                help="Ajoute `--optimize-thresholds` pour sélectionner le meilleur `decision_threshold` sur validation.",
            )
        with ml_opt_col3:
            ml_enable_global_model = st.checkbox(
                "Entraîner aussi un modèle global multi-symboles",
                value=bool(st.session_state.get("pipeline_ml_enable_global_model", False)),
                key="pipeline_ml_enable_global_model",
                help="Ajoute `--enable-global-model`.",
            )
            ml_global_model_name = cast(
                str,
                st.selectbox(
                    "Backend du modèle global",
                    options=["catboost", "lightgbm"],
                    index=["catboost", "lightgbm"].index(
                        cast(str, st.session_state.get("pipeline_ml_global_model_name", "catboost"))
                        if st.session_state.get("pipeline_ml_global_model_name", "catboost") in {"catboost", "lightgbm"}
                        else "catboost"
                    ),
                    key="pipeline_ml_global_model_name",
                    disabled=not ml_enable_global_model,
                ),
            )
            ml_enable_cross_sectional = st.checkbox(
                "Activer les features cross-sectionnelles",
                value=bool(st.session_state.get("pipeline_ml_enable_cross_sectional", False)),
                key="pipeline_ml_enable_cross_sectional",
                help="Ajoute `--enable-cross-sectional` pour enrichir les features séquentielles et le modèle global.",
            )

        ml_adv_col1, ml_adv_col2 = st.columns(2)
        with ml_adv_col1:
            ml_optimize_target = st.checkbox(
                "Optimiser l'horizon / la target swing",
                value=bool(st.session_state.get("pipeline_ml_optimize_target", False)),
                key="pipeline_ml_optimize_target",
                help="Ajoute `--optimize-target`.",
            )
        with ml_adv_col2:
            st.info(
                "`ML Predict` n'entraîne rien : il réutilise le `selected_model` présent dans les artefacts symbole. "
                "Si `ml_train` a activé les challengers et la sélection champion, l'inférence quotidienne suivra automatiquement ce routage."
            )

        st.caption(
            "Alpha Scanner part du profil partagé strict (`STRICT_SWING_CASH_FILTERS`) depuis l'IHM. "
            "Les paramètres ci-dessous permettent de reproduire explicitement — et si besoin de surcharger — les seuils backend réellement supportés par `selector.alpha_scanner`."
        )
        _render_alpha_scanner_dependency_threshold_editor()

        st.markdown("#### Paramètres Alpha Scanner")
        st.caption(
            "Ces réglages reflètent les options opérationnelles réellement disponibles côté `selector.alpha_scanner`. "
            "`0` sur `max workers` signifie : auto. Le preset strict reste la base implicite côté backend."
        )

        selector_col1, selector_col2, selector_col3, selector_col4 = st.columns(4)
        with selector_col1:
            selector_chunk_size = int(
                st.number_input(
                    "Alpha Scanner — taille de chunk",
                    min_value=1,
                    value=int(st.session_state.get("pipeline_selector_chunk_size", DEFAULT_SELECTOR_CHUNK_SIZE)),
                    step=50,
                    key="pipeline_selector_chunk_size",
                )
            )
            selector_selection_size = int(
                st.number_input(
                    "Alpha Scanner — taille de sélection finale",
                    min_value=1,
                    value=int(st.session_state.get("pipeline_selector_selection_size", DEFAULT_SELECTOR_SELECTION_SIZE)),
                    step=5,
                    key="pipeline_selector_selection_size",
                )
            )
            selector_max_workers = int(
                st.number_input(
                    "Alpha Scanner — max workers (0 = auto)",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_selector_max_workers", 0)),
                    step=1,
                    key="pipeline_selector_max_workers",
                )
            )
            selector_log_level = cast(
                str,
                st.selectbox(
                    "Alpha Scanner — niveau de log",
                    options=["DEBUG", "INFO", "WARNING", "ERROR"],
                    index=["DEBUG", "INFO", "WARNING", "ERROR"].index(
                        cast(str, st.session_state.get("pipeline_selector_log_level", DEFAULT_SELECTOR_LOG_LEVEL)).upper()
                        if str(st.session_state.get("pipeline_selector_log_level", DEFAULT_SELECTOR_LOG_LEVEL)).upper() in {"DEBUG", "INFO", "WARNING", "ERROR"}
                        else DEFAULT_SELECTOR_LOG_LEVEL
                    ),
                    key="pipeline_selector_log_level",
                ),
            )
        with selector_col2:
            selector_liquidity_threshold = float(
                st.number_input(
                    "Alpha Scanner — liquidité mini",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_selector_liquidity_threshold", DEFAULT_SELECTOR_LIQUIDITY_THRESHOLD)),
                    step=1_000_000.0,
                    format="%.2f",
                    key="pipeline_selector_liquidity_threshold",
                )
            )
            selector_min_close = float(
                st.number_input(
                    "Alpha Scanner — prix mini",
                    min_value=0.01,
                    value=float(st.session_state.get("pipeline_selector_min_close", DEFAULT_SELECTOR_MIN_CLOSE)),
                    step=1.0,
                    format="%.2f",
                    key="pipeline_selector_min_close",
                )
            )
            selector_max_volatility_ratio = float(
                st.number_input(
                    "Alpha Scanner — volatilité relative max",
                    min_value=0.01,
                    value=float(st.session_state.get("pipeline_selector_max_volatility_ratio", DEFAULT_SELECTOR_MAX_VOLATILITY_RATIO)),
                    step=0.05,
                    format="%.2f",
                    key="pipeline_selector_max_volatility_ratio",
                )
            )
            selector_min_relative_strength_index = float(
                st.number_input(
                    "Alpha Scanner — RS mini",
                    min_value=0.01,
                    value=float(st.session_state.get("pipeline_selector_min_relative_strength_index", DEFAULT_SELECTOR_MIN_RELATIVE_STRENGTH_INDEX)),
                    step=1.0,
                    format="%.2f",
                    key="pipeline_selector_min_relative_strength_index",
                )
            )
        with selector_col3:
            selector_min_high_52w_proximity = float(
                st.number_input(
                    "Alpha Scanner — proximité min du high 52w",
                    min_value=0.01,
                    max_value=1.0,
                    value=float(st.session_state.get("pipeline_selector_min_high_52w_proximity", DEFAULT_SELECTOR_MIN_HIGH_52W_PROXIMITY)),
                    step=0.01,
                    format="%.2f",
                    key="pipeline_selector_min_high_52w_proximity",
                )
            )
            selector_min_weekly_trend_score = float(
                st.number_input(
                    "Alpha Scanner — weekly trend mini",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(st.session_state.get("pipeline_selector_min_weekly_trend_score", DEFAULT_SELECTOR_MIN_WEEKLY_TREND_SCORE)),
                    step=0.05,
                    format="%.2f",
                    key="pipeline_selector_min_weekly_trend_score",
                )
            )
            selector_min_atr_pct_20 = float(
                st.number_input(
                    "Alpha Scanner — ATR%20 min",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_selector_min_atr_pct_20", DEFAULT_SELECTOR_MIN_ATR_PCT_20)),
                    step=0.005,
                    format="%.4f",
                    key="pipeline_selector_min_atr_pct_20",
                )
            )
            selector_max_atr_pct_20 = float(
                st.number_input(
                    "Alpha Scanner — ATR%20 max",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_selector_max_atr_pct_20", DEFAULT_SELECTOR_MAX_ATR_PCT_20)),
                    step=0.005,
                    format="%.4f",
                    key="pipeline_selector_max_atr_pct_20",
                )
            )
        with selector_col4:
            selector_min_market_cap = float(
                st.number_input(
                    "Alpha Scanner — market cap mini",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_selector_min_market_cap", DEFAULT_SELECTOR_MIN_MARKET_CAP)),
                    step=100_000_000.0,
                    format="%.2f",
                    key="pipeline_selector_min_market_cap",
                )
            )
            selector_min_beta_126 = float(
                st.number_input(
                    "Alpha Scanner — beta 126 mini",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_selector_min_beta_126", DEFAULT_SELECTOR_MIN_BETA_126)),
                    step=0.1,
                    format="%.2f",
                    key="pipeline_selector_min_beta_126",
                )
            )
            selector_max_spread_bps = float(
                st.number_input(
                    "Alpha Scanner — spread max (bps)",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_selector_max_spread_bps", DEFAULT_SELECTOR_MAX_SPREAD_BPS)),
                    step=1.0,
                    format="%.2f",
                    key="pipeline_selector_max_spread_bps",
                )
            )
            selector_earnings_blackout_days = int(
                st.number_input(
                    "Alpha Scanner — earnings blackout (jours)",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_selector_earnings_blackout_days", DEFAULT_SELECTOR_EARNINGS_BLACKOUT_DAYS)),
                    step=1,
                    key="pipeline_selector_earnings_blackout_days",
                )
            )

        selector_adv_col1, selector_adv_col2 = st.columns(2)
        with selector_adv_col1:
            selector_max_anomaly_count = int(
                st.number_input(
                    "Alpha Scanner — anomalies max",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_selector_max_anomaly_count", DEFAULT_SELECTOR_MAX_ANOMALY_COUNT)),
                    step=1,
                    key="pipeline_selector_max_anomaly_count",
                )
            )
        with selector_adv_col2:
            selector_sector_cap_ratio = float(
                st.number_input(
                    "Alpha Scanner — cap sectoriel",
                    min_value=0.01,
                    max_value=1.0,
                    value=float(st.session_state.get("pipeline_selector_sector_cap_ratio", DEFAULT_SELECTOR_SECTOR_CAP_RATIO)),
                    step=0.01,
                    format="%.2f",
                    key="pipeline_selector_sector_cap_ratio",
                )
            )

        st.markdown("#### Paramètres Event Sentiment")
        st.caption(
            "Ces réglages reflètent les options réellement supportées par `python -m event_sentiment`. "
            "Si les symboles sont laissés vides, le backend consomme automatiquement les candidats `stock_scores.is_candidate=1`."
        )

        sentiment_col1, sentiment_col2, sentiment_col3 = st.columns(3)
        with sentiment_col1:
            sentiment_start_utc = str(
                st.text_input(
                    "Event Sentiment — start UTC",
                    value=str(st.session_state.get("pipeline_sentiment_start_utc", "")),
                    key="pipeline_sentiment_start_utc",
                    help="Exemple : 2026-01-01T00:00:00Z",
                )
            ).strip()
        with sentiment_col2:
            sentiment_end_utc = str(
                st.text_input(
                    "Event Sentiment — end UTC",
                    value=str(st.session_state.get("pipeline_sentiment_end_utc", "")),
                    key="pipeline_sentiment_end_utc",
                    help="Exemple : 2026-01-31T23:59:59Z",
                )
            ).strip()
        with sentiment_col3:
            sentiment_symbols = str(
                st.text_input(
                    "Event Sentiment — symboles (CSV)",
                    value=str(st.session_state.get("pipeline_sentiment_symbols", "")),
                    key="pipeline_sentiment_symbols",
                    help="Exemple : AAPL,MSFT,NVDA",
                )
            ).strip().upper()

        st.markdown("#### Paramètres Signal Aggregator")
        st.caption(
            "Ces réglages reflètent les options réellement supportées par `python -m event_sentiment.signal_aggregator`. "
            "La `trade date` réutilise le champ global situé en haut du formulaire quand il est renseigné."
        )

        signal_agg_col1, signal_agg_col2, signal_agg_col3 = st.columns(3)
        with signal_agg_col1:
            signal_aggregator_all_symbols = st.checkbox(
                "Signal Aggregator — traiter tous les symboles",
                value=bool(st.session_state.get("pipeline_signal_aggregator_all_symbols", False)),
                key="pipeline_signal_aggregator_all_symbols",
            )
            signal_aggregator_log_level = cast(
                str,
                st.selectbox(
                    "Signal Aggregator — niveau de log",
                    options=["DEBUG", "INFO", "WARNING", "ERROR"],
                    index=["DEBUG", "INFO", "WARNING", "ERROR"].index(
                        cast(str, st.session_state.get("pipeline_signal_aggregator_log_level", DEFAULT_SIGNAL_AGGREGATOR_LOG_LEVEL)).upper()
                        if str(st.session_state.get("pipeline_signal_aggregator_log_level", DEFAULT_SIGNAL_AGGREGATOR_LOG_LEVEL)).upper() in {"DEBUG", "INFO", "WARNING", "ERROR"}
                        else DEFAULT_SIGNAL_AGGREGATOR_LOG_LEVEL
                    ),
                    key="pipeline_signal_aggregator_log_level",
                ),
            )
        with signal_agg_col2:
            signal_aggregator_sentiment_weight = float(
                st.number_input(
                    "Signal Aggregator — poids sentiment",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(st.session_state.get("pipeline_signal_aggregator_sentiment_weight", DEFAULT_SIGNAL_AGGREGATOR_SENTIMENT_WEIGHT)),
                    step=0.01,
                    format="%.2f",
                    key="pipeline_signal_aggregator_sentiment_weight",
                )
            )
            signal_aggregator_macro_weight = float(
                st.number_input(
                    "Signal Aggregator — poids macro sectoriel",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(st.session_state.get("pipeline_signal_aggregator_macro_weight", DEFAULT_SIGNAL_AGGREGATOR_MACRO_WEIGHT)),
                    step=0.01,
                    format="%.2f",
                    key="pipeline_signal_aggregator_macro_weight",
                )
            )
        with signal_agg_col3:
            signal_aggregator_lookback_days = int(
                st.number_input(
                    "Signal Aggregator — lookback (jours)",
                    min_value=1,
                    value=int(st.session_state.get("pipeline_signal_aggregator_lookback_days", DEFAULT_SIGNAL_AGGREGATOR_LOOKBACK_DAYS)),
                    step=1,
                    key="pipeline_signal_aggregator_lookback_days",
                )
            )
            signal_aggregator_min_news_count = int(
                st.number_input(
                    "Signal Aggregator — news mini",
                    min_value=1,
                    value=int(st.session_state.get("pipeline_signal_aggregator_min_news_count", DEFAULT_SIGNAL_AGGREGATOR_MIN_NEWS_COUNT)),
                    step=1,
                    key="pipeline_signal_aggregator_min_news_count",
                )
            )

        signal_agg_decay_col1, signal_agg_decay_col2 = st.columns(2)
        with signal_agg_decay_col1:
            signal_aggregator_time_decay_half_life_days = float(
                st.number_input(
                    "Signal Aggregator — demi-vie décroissance (jours)",
                    min_value=0.1,
                    value=float(st.session_state.get("pipeline_signal_aggregator_time_decay_half_life_days", DEFAULT_SIGNAL_AGGREGATOR_TIME_DECAY_HALF_LIFE_DAYS)),
                    step=0.1,
                    format="%.2f",
                    key="pipeline_signal_aggregator_time_decay_half_life_days",
                )
            )
        with signal_agg_decay_col2:
            derived_quant_weight = round(1.0 - signal_aggregator_sentiment_weight - signal_aggregator_macro_weight, 4)
            if derived_quant_weight < 0:
                st.error(
                    "Configuration invalide côté Signal Aggregator : `poids sentiment + poids macro > 1.0`. "
                    "Le backend rejettera ce lancement."
                )
            else:
                st.info(f"Poids quantitatif implicite côté backend : `{derived_quant_weight}`")

        st.markdown("#### Paramètres Screener")
        st.caption(
            "Ces réglages reflètent les options réellement disponibles côté `screener.stock_screener`. "
            "`0` sur `max workers` signifie : auto (`os.cpu_count()`)."
        )

        screener_col1, screener_col2, screener_col3 = st.columns(3)
        with screener_col1:
            screener_chunk_size = int(
                st.number_input(
                    "Screener — taille de chunk",
                    min_value=1,
                    value=int(st.session_state.get("pipeline_screener_chunk_size", DEFAULT_SCREENER_CHUNK_SIZE)),
                    step=50,
                    key="pipeline_screener_chunk_size",
                )
            )
            screener_max_workers = int(
                st.number_input(
                    "Screener — max workers (0 = auto)",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_screener_max_workers", 0)),
                    step=1,
                    key="pipeline_screener_max_workers",
                )
            )
            screener_benchmark_symbol = str(
                st.text_input(
                    "Screener — benchmark",
                    value=str(st.session_state.get("pipeline_screener_benchmark_symbol", DEFAULT_SCREENER_BENCHMARK_SYMBOL)),
                    key="pipeline_screener_benchmark_symbol",
                )
            ).strip().upper()
        with screener_col2:
            screener_liquidity_threshold_usd = float(
                st.number_input(
                    "Screener — liquidité mini (USD)",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_screener_liquidity_threshold_usd", DEFAULT_SCREENER_LIQUIDITY_THRESHOLD_USD)),
                    step=1_000_000.0,
                    format="%.2f",
                    key="pipeline_screener_liquidity_threshold_usd",
                )
            )
            screener_min_relative_strength_index = float(
                st.number_input(
                    "Screener — RS mini vs benchmark",
                    min_value=0.01,
                    value=float(st.session_state.get("pipeline_screener_min_relative_strength_index", DEFAULT_SCREENER_MIN_RELATIVE_STRENGTH_INDEX)),
                    step=1.0,
                    format="%.2f",
                    key="pipeline_screener_min_relative_strength_index",
                )
            )
            screener_enable_two_pass_loading = st.checkbox(
                "Screener — activer le chargement en 2 passes",
                value=bool(st.session_state.get("pipeline_screener_enable_two_pass_loading", DEFAULT_SCREENER_ENABLE_TWO_PASS_LOADING)),
                key="pipeline_screener_enable_two_pass_loading",
            )
        with screener_col3:
            screener_historical_range_lookback_days = int(
                st.number_input(
                    "Screener — fenêtre range historique (jours)",
                    min_value=2,
                    value=int(st.session_state.get("pipeline_screener_historical_range_lookback_days", DEFAULT_SCREENER_HISTORICAL_RANGE_LOOKBACK_DAYS)),
                    step=21,
                    key="pipeline_screener_historical_range_lookback_days",
                )
            )
            screener_min_historical_range_score = float(
                st.number_input(
                    "Screener — score mini range historique",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.get("pipeline_screener_min_historical_range_score", DEFAULT_SCREENER_MIN_HISTORICAL_RANGE_SCORE)),
                    step=1.0,
                    format="%.2f",
                    key="pipeline_screener_min_historical_range_score",
                )
            )
            screener_first_pass_window_days = int(
                st.number_input(
                    "Screener — fenêtre passe 1 (jours)",
                    min_value=252,
                    value=int(st.session_state.get("pipeline_screener_first_pass_window_days", DEFAULT_SCREENER_FIRST_PASS_WINDOW_DAYS)),
                    step=21,
                    key="pipeline_screener_first_pass_window_days",
                )
            )

        st.markdown("#### Paramètres Data Integrity")
        st.caption(
            "Ces réglages reflètent les options réellement disponibles côté `dataIntegrityEngine` pour les étapes quotes, earnings et fondamentaux. "
            "`0` sur un champ `limit` signifie : univers complet éligible."
        )

        di_col1, di_col2, di_col3 = st.columns(3)
        with di_col1:
            data_integrity_quotes_limit = int(
                st.number_input(
                    "Latest Quotes — limite optionnelle",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_data_integrity_quotes_limit", 0)),
                    step=50,
                    key="pipeline_data_integrity_quotes_limit",
                )
            )
            data_integrity_quotes_batch_size = int(
                st.number_input(
                    "Latest Quotes — taille de batch",
                    min_value=1,
                    value=int(st.session_state.get("pipeline_data_integrity_quotes_batch_size", DEFAULT_DATA_INTEGRITY_QUOTES_BATCH_SIZE)),
                    step=25,
                    key="pipeline_data_integrity_quotes_batch_size",
                )
            )
            data_integrity_earnings_limit = int(
                st.number_input(
                    "Earnings — limite optionnelle",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_data_integrity_earnings_limit", 0)),
                    step=25,
                    key="pipeline_data_integrity_earnings_limit",
                )
            )
        with di_col2:
            data_integrity_earnings_sleep_seconds = float(
                st.number_input(
                    "Earnings — pause Finnhub (s)",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_data_integrity_earnings_sleep_seconds", DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS)),
                    step=0.1,
                    format="%.2f",
                    key="pipeline_data_integrity_earnings_sleep_seconds",
                )
            )
            data_integrity_fundamentals_limit = int(
                st.number_input(
                    "Fondamentaux — limite optionnelle",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_data_integrity_fundamentals_limit", 0)),
                    step=25,
                    key="pipeline_data_integrity_fundamentals_limit",
                )
            )
            data_integrity_fundamentals_sleep_seconds = float(
                st.number_input(
                    "Fondamentaux — pause Finnhub (s)",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_data_integrity_fundamentals_sleep_seconds", DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS)),
                    step=0.1,
                    format="%.2f",
                    key="pipeline_data_integrity_fundamentals_sleep_seconds",
                )
            )
        with di_col3:
            data_integrity_fundamentals_log_every = int(
                st.number_input(
                    "Fondamentaux — journaliser tous les N symboles",
                    min_value=1,
                    value=int(st.session_state.get("pipeline_data_integrity_fundamentals_log_every", DEFAULT_DATA_INTEGRITY_FUNDAMENTALS_LOG_EVERY)),
                    step=5,
                    key="pipeline_data_integrity_fundamentals_log_every",
                )
            )
            data_integrity_earnings_custom_window = st.checkbox(
                "Earnings — utiliser une fenêtre de dates personnalisée",
                value=bool(st.session_state.get(EARNINGS_CUSTOM_WINDOW_KEY, False)),
                key=EARNINGS_CUSTOM_WINDOW_KEY,
            )

        effective_earnings_from_date: str | None = None
        effective_earnings_to_date: str | None = None
        if data_integrity_earnings_custom_window:
            earnings_date_col1, earnings_date_col2 = st.columns(2)
            with earnings_date_col1:
                earnings_from_date_value = cast(
                    date,
                    st.date_input(
                        "Earnings — date de début",
                        value=cast(date, st.session_state.get("pipeline_data_integrity_earnings_from_date", date.today() - timedelta(days=7))),
                        key="pipeline_data_integrity_earnings_from_date",
                        format="YYYY-MM-DD",
                    ),
                )
            with earnings_date_col2:
                earnings_to_date_value = cast(
                    date,
                    st.date_input(
                        "Earnings — date de fin",
                        value=cast(date, st.session_state.get("pipeline_data_integrity_earnings_to_date", date.today() + timedelta(days=30))),
                        key="pipeline_data_integrity_earnings_to_date",
                        format="YYYY-MM-DD",
                    ),
                )
            if earnings_from_date_value <= earnings_to_date_value:
                effective_earnings_from_date = earnings_from_date_value.isoformat()
                effective_earnings_to_date = earnings_to_date_value.isoformat()
            else:
                st.error("Fenêtre earnings invalide : la date de début doit être antérieure ou égale à la date de fin. La fenêtre custom sera ignorée.")
        else:
            st.caption("Sans fenêtre personnalisée, `sync_earnings_calendar` conserve sa plage backend par défaut : J-7 → J+30.")

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
            execution_account_type=cast(Any, execution_account_type),
            execution_pdt_rule=cast(Any, execution_pdt_rule),
            execution_swing_only=bool(execution_swing_only),
            ml_accelerator=cast(Any, ml_accelerator),
            ml_include_sentiment=bool(ml_include_sentiment),
            ml_enable_lightgbm=bool(ml_enable_lightgbm),
            ml_enable_catboost=bool(ml_enable_catboost),
            ml_enable_global_model=bool(ml_enable_global_model),
            ml_global_model_name=cast(Any, ml_global_model_name),
            ml_enable_cross_sectional=bool(ml_enable_cross_sectional),
            ml_select_champion=bool(ml_select_champion),
            ml_champion_selection_metric=cast(Any, ml_champion_selection_metric),
            ml_optimize_thresholds=bool(ml_optimize_thresholds),
            ml_optimize_target=bool(ml_optimize_target),
            sentiment_start_utc=sentiment_start_utc or None,
            sentiment_end_utc=sentiment_end_utc or None,
            sentiment_symbols=sentiment_symbols or None,
            selector_chunk_size=int(selector_chunk_size),
            selector_selection_size=int(selector_selection_size),
            selector_max_workers=_to_optional_positive_int(selector_max_workers),
            selector_liquidity_threshold=float(selector_liquidity_threshold),
            selector_min_close=float(selector_min_close),
            selector_max_volatility_ratio=float(selector_max_volatility_ratio),
            selector_min_relative_strength_index=float(selector_min_relative_strength_index),
            selector_min_high_52w_proximity=float(selector_min_high_52w_proximity),
            selector_min_weekly_trend_score=float(selector_min_weekly_trend_score),
            selector_min_atr_pct_20=float(selector_min_atr_pct_20),
            selector_max_atr_pct_20=float(selector_max_atr_pct_20),
            selector_min_market_cap=float(selector_min_market_cap),
            selector_min_beta_126=float(selector_min_beta_126),
            selector_max_spread_bps=float(selector_max_spread_bps),
            selector_earnings_blackout_days=int(selector_earnings_blackout_days),
            selector_max_anomaly_count=int(selector_max_anomaly_count),
            selector_sector_cap_ratio=float(selector_sector_cap_ratio),
            selector_log_level=str(selector_log_level).upper(),
            signal_aggregator_all_symbols=bool(signal_aggregator_all_symbols),
            signal_aggregator_sentiment_weight=float(signal_aggregator_sentiment_weight),
            signal_aggregator_macro_weight=float(signal_aggregator_macro_weight),
            signal_aggregator_lookback_days=int(signal_aggregator_lookback_days),
            signal_aggregator_min_news_count=int(signal_aggregator_min_news_count),
            signal_aggregator_time_decay_half_life_days=float(signal_aggregator_time_decay_half_life_days),
            signal_aggregator_log_level=str(signal_aggregator_log_level).upper(),
            screener_chunk_size=int(screener_chunk_size),
            screener_max_workers=_to_optional_positive_int(screener_max_workers),
            screener_benchmark_symbol=screener_benchmark_symbol or DEFAULT_SCREENER_BENCHMARK_SYMBOL,
            screener_liquidity_threshold_usd=float(screener_liquidity_threshold_usd),
            screener_min_relative_strength_index=float(screener_min_relative_strength_index),
            screener_historical_range_lookback_days=int(screener_historical_range_lookback_days),
            screener_min_historical_range_score=float(screener_min_historical_range_score),
            screener_first_pass_window_days=int(screener_first_pass_window_days),
            screener_enable_two_pass_loading=bool(screener_enable_two_pass_loading),
            data_integrity_quotes_limit=_to_optional_positive_int(data_integrity_quotes_limit),
            data_integrity_quotes_batch_size=int(data_integrity_quotes_batch_size),
            data_integrity_earnings_from_date=effective_earnings_from_date,
            data_integrity_earnings_to_date=effective_earnings_to_date,
            data_integrity_earnings_limit=_to_optional_positive_int(data_integrity_earnings_limit),
            data_integrity_earnings_sleep_seconds=float(data_integrity_earnings_sleep_seconds),
            data_integrity_fundamentals_limit=_to_optional_positive_int(data_integrity_fundamentals_limit),
            data_integrity_fundamentals_sleep_seconds=float(data_integrity_fundamentals_sleep_seconds),
            data_integrity_fundamentals_log_every=int(data_integrity_fundamentals_log_every),
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
        st.subheader("🚀 Workflow complet 1 → 14")
        st.caption(
            "Lance automatiquement les 14 étapes du pipeline dans l'ordre. "
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
            workflow_cols[0].metric("Type", "Workflow 1 → 14")
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
    _render_run_summary(record, compact=True)


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
        st.session_state[ML_SELECTED_SYMBOL_KEY] = selected_symbol
        st.session_state[NAVIGATION_TARGET_PAGE_KEY] = "ml"
        st.rerun()


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

    st.subheader("🪜 Étapes du workflow quotidien 1 → 14")
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


def render() -> None:
    st.header("🔄 Pipeline Quotidien")
    st.caption("Ordre d'exécution strict — chaque étape dépend de la précédente.")

    options, live_confirmed = _build_launch_options()
    db_config = get_runtime_db_config()

    _render_workflow_launcher(options, live_confirmed, db_config)
    _render_runtime_center()
    _render_step_panels(options, live_confirmed, db_config)


run_page_if_standalone(__name__, render)
