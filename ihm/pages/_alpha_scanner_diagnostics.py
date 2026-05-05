"""ihm/pages/_alpha_scanner_diagnostics.py — Phase 6.2 (Backlog L10).

Diagnostic des dépendances Alpha Scanner (quotes / earnings) extrait de
``pipeline.py`` : éditeur de seuils, badges de santé, panneau diagnostic.
"""
from __future__ import annotations

import streamlit as st

from ihm.components.alpha_scanner_dependency import (
    dependency_badge,
    get_dependency_payload,
    render_dependency_metrics,
)
from ihm.pages._shared import (
    ALPHA_SCANNER_DEPENDENCY_ACTION_RUNS_KEY,
    ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY,
    ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_CAPTION,
    ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_TITLE,
    PipelineLaunchOptions,
    _launch_pipeline_step,
    _pipeline_step_label,
)
from ihm.services.db import reset_db_caches
from ihm.services.queries import (
    ALPHA_SCANNER_DEPENDENCY_THRESHOLDS,
    get_alpha_scanner_dependency_diagnostic,
    get_alpha_scanner_dependency_thresholds,
)
from ihm.services.screener_preferences import (
    reset_persisted_alpha_scanner_dependency_thresholds,
    save_persisted_alpha_scanner_dependency_thresholds,
)

__all__ = [
    "_alpha_scanner_dependency_block_reason",
    "_collect_alpha_scanner_dependency_threshold_inputs",
    "_prime_alpha_scanner_dependency_threshold_state",
    "_render_alpha_scanner_dependency_diagnostic",
    "_render_alpha_scanner_dependency_threshold_editor",
    "_render_dependency_action_feedback",
    "_render_dependency_health_inline",
    "_set_alpha_scanner_dependency_threshold_state",
    "_threshold_widget_key",
]

ALPHA_SCANNER_PENDING_THRESHOLDS_KEY = "pipeline_alpha_scanner_pending_thresholds"


def _alpha_scanner_dependency_block_reason(dependency_diagnostic: dict[str, object] | None) -> str | None:
    if not isinstance(dependency_diagnostic, dict) or not bool(dependency_diagnostic.get("all_red")):
        return None
    return (
        "Alpha Scanner est désactivé : `stock_quote_snapshots` et `stock_earnings_calendar` sont tous deux rouges "
        "(vides, trop peu couverts ou trop anciens). Lancez d'abord les synchronisations depuis le diagnostic ci-dessous."
    )


def _threshold_widget_key(step_key: str, metric_key: str) -> str:
    return f"pipeline_alpha_scanner_threshold_{step_key}_{metric_key}"


def _apply_alpha_scanner_dependency_threshold_state_to_session(thresholds: dict[str, dict[str, float]]) -> None:
    for step_key, metrics in thresholds.items():
        for metric_key, metric_value in metrics.items():
            st.session_state[_threshold_widget_key(step_key, metric_key)] = float(metric_value)


def _prime_alpha_scanner_dependency_threshold_state() -> dict[str, dict[str, float]]:
    thresholds = get_alpha_scanner_dependency_thresholds()
    pending_thresholds = st.session_state.pop(ALPHA_SCANNER_PENDING_THRESHOLDS_KEY, None)
    if isinstance(pending_thresholds, dict) and pending_thresholds:
        _apply_alpha_scanner_dependency_threshold_state_to_session(pending_thresholds)
        thresholds = pending_thresholds
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
    _apply_alpha_scanner_dependency_threshold_state_to_session(thresholds)


def _render_alpha_scanner_dependency_threshold_editor() -> None:
    current_thresholds = _prime_alpha_scanner_dependency_threshold_state()
    flash_message = st.session_state.pop(ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY, None)
    if isinstance(flash_message, str) and flash_message.strip():
        st.success(flash_message)

    with st.expander(ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_TITLE, expanded=False):
        st.caption(ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_CAPTION)
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
                st.session_state[ALPHA_SCANNER_PENDING_THRESHOLDS_KEY] = normalized
                get_alpha_scanner_dependency_diagnostic.clear()
                reset_db_caches()
                st.session_state[ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY] = "Seuils du diagnostic Alpha Scanner enregistrés."
                st.rerun()
        with action_col2:
            if st.button("↩️ Reset défauts", key="reset_alpha_scanner_dependency_thresholds", use_container_width=True):
                reset_persisted_alpha_scanner_dependency_thresholds()
                st.session_state[ALPHA_SCANNER_PENDING_THRESHOLDS_KEY] = ALPHA_SCANNER_DEPENDENCY_THRESHOLDS
                get_alpha_scanner_dependency_diagnostic.clear()
                reset_db_caches()
                st.session_state[ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY] = "Seuils du diagnostic Alpha Scanner réinitialisés aux valeurs par défaut."
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
