"""ihm/pages/_shared.py — Phase 6.2 (Backlog L10).

Constantes ``st.session_state`` et helpers UI partagés entre les sous-modules
extraits de ``ihm/pages/pipeline.py`` (workflow, runtime center, exécution,
data integrity, alpha scanner diagnostics, watcher).

Les noms publics et privés sont ré-exportés par ``ihm.pages.pipeline`` pour
préserver la rétro-compatibilité (``from ihm.pages.pipeline import
TAIL_LINES, _render_run_summary, ...``).
"""
from __future__ import annotations

from typing import cast

import pandas as pd
import streamlit as st

from ihm.components.metrics import format_duration_hhmmss, to_int
from ihm.components.run_summary import render_run_summary_block
from ihm.services.pipeline_runner import (
    PipelineLaunchOptions,
    get_pipeline_auxiliary_steps,
    get_pipeline_steps,
)
from ihm.services.process_registry import start_pipeline_run
from ihm.services.run_summary import build_run_summary_caption, get_run_summary

__all__ = [
    "ALPHA_SCANNER_DEPENDENCY_ACTION_RUNS_KEY",
    "ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY",
    "ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_CAPTION",
    "ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_TITLE",
    "ALPHA_SCANNER_PARAMS_CAPTION",
    "ALPHA_SCANNER_PARAMS_TITLE",
    "COMPARE_RUNS_KEY",
    "EARNINGS_CUSTOM_WINDOW_KEY",
    "EXECUTION_DEFAULTS_ACCOUNT_KEY",
    "IMPORT_NEWS_END_DATE_KEY",
    "IMPORT_NEWS_START_DATE_KEY",
    "LOG_FILTER_KEY",
    "ML_SELECTED_SYMBOL_KEY",
    "NAVIGATION_TARGET_PAGE_KEY",
    "PENDING_COMPARE_RUNS_KEY",
    "PENDING_SELECTED_RUN_KEY",
    "PipelineLaunchOptions",
    "SCREENER_PARAMS_CAPTION",
    "SCREENER_PARAMS_TITLE",
    "SELECTED_RUN_KEY",
    "TAIL_LINES",
    "_is_workflow_run",
    "_launch_pipeline_step",
    "_pipeline_step_label",
    "_record_dependency_action_run",
    "_render_log_block",
    "_render_run_summary",
    "_render_step_result",
    "_sanitize_compare_ids",
    "_status_badge",
    "_tail_text",
    "_to_optional_positive_int",
    "_workflow_progress",
    "build_run_summary_caption",
    "format_duration_hhmmss",
    "get_pipeline_auxiliary_steps",
    "get_pipeline_steps",
    "get_run_summary",
    "render_run_summary_block",
    "start_pipeline_run",
    "to_int",
]


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
ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_TITLE = "🧪 Diagnostic dépendances Alpha Scanner — seuils quotes/earnings"
ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_CAPTION = (
    "Bloc diagnostic uniquement : il ne change pas les filtres du scanner, "
    "il règle seulement quand `quotes` et `earnings` sont jugés assez fiables dans l'IHM."
)
ALPHA_SCANNER_PARAMS_TITLE = "#### Alpha Scanner — sélection finale stricte (`selector.alpha_scanner`)"
ALPHA_SCANNER_PARAMS_CAPTION = (
    "Sélection finale stricte : applique les filtres swing tradables sur l'univers déjà préparé par le screener amont."
)
SCREENER_PARAMS_TITLE = "#### Screener amont — univers & scores de base (`screener.stock_screener`)"
SCREENER_PARAMS_CAPTION = (
    "Préfiltrage large : construit un univers quantitatif propre avant `quotes`, `earnings` et la sélection finale Alpha Scanner."
)


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


def _pipeline_step_label(step_key: str) -> str:
    for step in (*get_pipeline_auxiliary_steps(), *get_pipeline_steps()):
        if step.key == step_key:
            return f"{step.num}. {step.name}"
    return step_key


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
    _render_risk_snapshot_freshness_warning(record)
    _render_run_summary(record, compact=True)


def _render_risk_snapshot_freshness_warning(record: dict[str, object]) -> None:
    """Avertit si l'étape risk_management a utilisé un snapshot equity plus ancien que le trade_date.

    Lit le ``run_summary`` produit par ``risk_management.cli`` (champs
    ``account_snapshot_trade_date`` et ``trade_date``) et affiche un warning IHM
    quand le snapshot est antérieur, ce qui indique qu'aucun snapshot du jour
    n'était disponible (compte vide → fallback ``--account-equity``).
    """
    if str(record.get("step_key", "")) != "risk_management":
        return
    summary = get_run_summary(record)
    if not summary:
        return
    trade_date_raw = str(summary.get("trade_date") or "").strip()
    snapshot_raw = summary.get("account_snapshot_trade_date")
    snapshot_str = str(snapshot_raw).strip() if snapshot_raw else ""
    if not trade_date_raw:
        return
    if not snapshot_str:
        st.info(
            f"ℹ️ Aucun snapshot equity broker disponible pour `trade_date={trade_date_raw}` — "
            f"sizing calculé sur `--account-equity` (paramètre IHM). "
            "Comportement **normal au premier run de la journée** : la table `broker_account_snapshots` "
            "n'est alimentée qu'après l'étape **12 — Execution**, qui s'exécute logiquement *après* le risk management. "
            "Aux runs suivants, l'equity broker réel sera utilisé automatiquement."
        )
        return
    try:
        from datetime import date as _date
        snapshot_date = _date.fromisoformat(snapshot_str)
        trade_date = _date.fromisoformat(trade_date_raw)
    except ValueError:
        return
    if snapshot_date < trade_date:
        delta_days = (trade_date - snapshot_date).days
        st.info(
            f"ℹ️ Étape 11 (Risk Management) a utilisé un snapshot equity broker daté du "
            f"`{snapshot_str}`, antérieur à `trade_date={trade_date_raw}` (écart : {delta_days} jour(s)). "
            "Comportement attendu : `broker_account_snapshots` n'est rafraîchi que par l'étape **12 — Execution**. "
            "Le sizing reste cohérent tant que l'écart d'equity réel est faible."
        )

