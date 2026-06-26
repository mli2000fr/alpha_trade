"""ihm/pages/_workflow.py — Phase 6.2 (Backlog L10).

Workflow launcher configurable 1→12 / 3→12 (+ options 13/14) + runtime center (suivi des runs en cours / historique)
extraits de ``pipeline.py``.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, time as dt_time, timedelta
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
    _render_watchdog_status,
    _status_badge,
    _workflow_progress,
    build_run_summary_caption,
    format_duration_hhmmss,
    to_int,
)
from ihm.services.run_summary import get_stooq_cross_check_status
from ihm.services.process_registry import (
    build_log_download_name,
    get_pipeline_run_record,
    list_active_pipeline_runs,
    load_pipeline_history,
    pipeline_log_available,
    read_pipeline_logs,
    start_pipeline_workflow,
    stop_pipeline_run,
)
from ihm.services.pipeline_runner import (
    get_pipeline_steps,
    get_pipeline_workflow_steps,
    is_workflow_core_step_number,
)

__all__ = [
    "_build_workflow_scope_help_lines",
    "_build_history_rows",
    "_build_workflow_child_run_payload",
    "_build_run_provider_badge",
    "_build_run_stooq_badge",
    "_build_run_symbol_progress_payload",
    "_build_run_symbol_progress_caption",
    "_latest_run_by_step",
    "_merge_runs",
    "_prime_runtime_center_state",
    "_prepare_workflow_child_run_state",
    "_render_runtime_center",
    "_render_workflow_launcher",
    "_should_render_active_run_live_progress",
]

WORKFLOW_INCLUDE_ML_TRAIN_KEY = "pipeline_workflow_include_ml_train"
WORKFLOW_RANGE_KEY = "pipeline_workflow_range"
WORKFLOW_INCLUDE_CA_SYNC_KEY = "pipeline_workflow_include_ca_sync"
WORKFLOW_INCLUDE_CA_APPLY_KEY = "pipeline_workflow_include_ca_apply"
WORKFLOW_DELAYED_START_ENABLED_KEY = "pipeline_workflow_delayed_start_enabled"
WORKFLOW_DELAYED_START_TIME_KEY = "pipeline_workflow_delayed_start_time"
WORKFLOW_CHILD_AUTOFOLLOW_KEY_PREFIX = "workflow_child_run_autofollow_"
WORKFLOW_CHILD_LAST_AUTO_KEY_PREFIX = "workflow_child_run_last_auto_"
WORKFLOW_CHILD_PENDING_SELECT_KEY_PREFIX = "workflow_child_run_pending_select_"
WORKFLOW_CHILD_PENDING_AUTOFOLLOW_KEY_PREFIX = "workflow_child_run_pending_autofollow_"
WORKFLOW_RUNTIME_AUTO_SELECTED_RUN_KEY = "pipeline_workflow_runtime_auto_selected_run_id"
WORKFLOW_RUNTIME_LAST_ACTIVE_COUNT_KEY = "pipeline_workflow_runtime_last_active_count"
WORKFLOW_HISTORY_TABLE_KEY = "pipeline_workflow_runtime_history_table"
WORKFLOW_CUSTOM_STEP_KEY_PREFIX = "pipeline_workflow_custom_step_"
WORKFLOW_RANGE_OPTIONS: tuple[str, ...] = ("1", "3")
_GENERIC_PROGRESS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"processed=(?P<current>\d+)/(?:\s*)?(?P<total>\d+)(?:.*?latest_symbol=(?P<symbol>[A-Za-z0-9._-]+))?", re.IGNORECASE),
    re.compile(r"current=(?P<current>\d+)/(?:\s*)?(?P<total>\d+)(?:.*?latest_symbol=(?P<symbol>[A-Za-z0-9._-]+))?", re.IGNORECASE),
    re.compile(r"progress=(?P<current>\d+)/(?:\s*)?(?P<total>\d+)(?:.*?latest_symbol=(?P<symbol>[A-Za-z0-9._-]+))?", re.IGNORECASE),
    re.compile(r"Traitement(?: du symbole)? \((?P<current>\d+)/(?:\s*)?(?P<total>\d+)\)\s*:\s*(?P<symbol>[A-Za-z0-9._-]+)", re.IGNORECASE),
    re.compile(r"Traitement (?P<current>\d+)/(?:\s*)?(?P<total>\d+)\s*:\s*(?P<symbol>[A-Za-z0-9._-]+)", re.IGNORECASE),
)
_RUN_PROGRESS_SUMMARY_SPECS: dict[str, tuple[tuple[str, ...], tuple[str, ...], str]] = {
    "import_alpaca_bar": (("current_symbol_total", "targeted_symbols"), ("current_symbol_index",), " Progression live import bars"),
    "data_sanitizer_daily": (("targeted_symbols",), ("successful_symbols", "skipped_symbols", "failed_symbols"), " Progression sanitizeur"),
    "sync_earnings_calendar": (("symbols",), ("completed_symbols", "failed_symbols"), " Progression earnings"),
    "update_sector": (("total",), ("updated", "skipped", "failed"), "️ Progression mise à jour fondamentaux"),
    "risk_management": (("targeted_symbols",), ("accepted_symbols", "reduced_symbols", "rejected_symbols"), "️ Progression risk management"),
    "execution": (("targeted_symbols",), ("filled_orders", "failed_orders", "skipped_orders"), " Progression execution"),
    "signal_aggregator": (("loaded_symbols",), ("updated_symbols",), " Progression signal aggregator"),
    "ml_train": (("symbols_total",), ("symbols_completed", "symbols_skipped", "symbols_failed"), " Progression ML Train"),
    "ml_predict": (("symbols_total",), ("symbols_completed", "symbols_skipped", "symbols_failed"), " Progression ML Predict"),
}


def _resolve_delayed_workflow_start(target_time: dt_time, *, now: datetime | None = None) -> datetime:
    current = now or datetime.now()
    scheduled_for = datetime.combine(current.date(), target_time)
    if scheduled_for <= current:
        scheduled_for = datetime.combine(current.date() + timedelta(days=1), target_time)
    return scheduled_for


def _parse_iso_datetime(value: object) -> datetime | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


def _format_countdown(total_seconds: int) -> str:
    normalized = max(int(total_seconds), 0)
    days, remainder = divmod(normalized, 24 * 3600)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    hhmmss = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{days}j {hhmmss}" if days else hhmmss


def _rerun_app() -> None:
    try:
        st.rerun(scope="app")
    except TypeError:
        st.rerun()


def _build_scheduled_countdown_caption(run: dict[str, object], *, now: datetime | None = None) -> str | None:
    if str(run.get("status") or "") != "scheduled":
        return None
    scheduled_at = _parse_iso_datetime(run.get("scheduled_for"))
    if scheduled_at is None:
        return None
    current = now or datetime.now()
    remaining_seconds = max(math.ceil((scheduled_at - current).total_seconds()), 0)
    scheduled_label = scheduled_at.strftime("%Y-%m-%d %H:%M:%S")
    if remaining_seconds <= 0:
        return f"⏰ Démarrage planifié pour `{scheduled_label}` — lancement imminent."
    return f"⏰ Démarrage planifié pour `{scheduled_label}` — départ dans `{_format_countdown(remaining_seconds)}`."


def _build_actual_start_caption(run: dict[str, object]) -> str | None:
    scheduled_at = _parse_iso_datetime(run.get("scheduled_for"))
    actual_started_at = _parse_iso_datetime(run.get("actual_started_at"))
    if scheduled_at is None or actual_started_at is None:
        return None
    if str(run.get("status") or "") == "scheduled":
        return None
    return f" Démarrage réel à `{actual_started_at.strftime('%Y-%m-%d %H:%M:%S')}` (planifié pour `{scheduled_at.strftime('%Y-%m-%d %H:%M:%S')}`)."


def _build_workflow_scope_help_lines() -> tuple[str, str, str]:
    return (
        "• `1 → 12` = cycle quotidien complet : import bars, sanitation, sélection, risk et exécution.",
        "• `3 → 12` = reprise rapide : saute les étapes 1 et 2 si les données marché sont déjà prêtes, pratique après changement de compte Alpaca.",
        "• `13` et `14` = extensions post-exécution optionnelles : non incluses par défaut ; `14` nécessite toujours `13`.",
    )


def _build_workflow_scope_alert_lines() -> tuple[str, str]:
    return (
        "⚠️ Les étapes **3→10** recalculent des données globales partagées entre comptes.",
        "✅ Les étapes **11→12** restent spécifiques au compte sélectionné.",
    )


def _workflow_mode_label(run: dict[str, object]) -> str:
    explicit_label = str(run.get("step_label") or "").strip()
    if explicit_label.startswith("Workflow personnalisé"):
        return explicit_label

    command = run.get("command")
    if not isinstance(command, list):
        return "Workflow personnalisé"

    normalized_command = [str(token).strip() for token in command if str(token).strip()]
    if not normalized_command:
        return "Workflow personnalisé"

    starts_at_3 = "import_alpaca_bar" not in normalized_command and "data_sanitizer_daily" not in normalized_command
    scope = "3 → 12" if starts_at_3 else "1 → 12"
    if "corporate_actions_apply" in normalized_command:
        scope = f"{scope} + 13 → 14"
    elif "corporate_actions_sync" in normalized_command:
        scope = f"{scope} + 13"
    ml_mode = "avec ML Train" if "ml_train" in normalized_command else "sans ML Train"
    return f"{scope} {ml_mode}"


def _custom_workflow_checkbox_key(step_key: str) -> str:
    return f"{WORKFLOW_CUSTOM_STEP_KEY_PREFIX}{step_key}"


def _build_run_provider_badge(run: dict[str, object] | None) -> str | None:
    if not isinstance(run, dict):
        return None

    summary = run.get("run_summary")
    if isinstance(summary, dict):
        provider = str(summary.get("provider") or "").strip().lower()
        if provider:
            return f"provider={provider}"
        eodhd_payload = summary.get("eodhd")
        if isinstance(eodhd_payload, dict):
            data_source = str(eodhd_payload.get("data_source") or "").strip().lower()
            if data_source.startswith("eodhd"):
                return "provider=eodhd"

    command = run.get("command")
    tokens = [str(token).strip().lower() for token in command] if isinstance(command, list) else []
    command_display = str(run.get("command_display") or "").strip().lower()
    searchable = " ".join(tokens + ([command_display] if command_display else []))
    if "import_eodhd_bar" in searchable:
        return "provider=eodhd"
    if "import_alpaca_bar" in searchable:
        return "provider=alpaca"
    return None


def _build_run_stooq_badge(run: dict[str, object] | None) -> str | None:
    status = get_stooq_cross_check_status(run)
    if status is None:
        return None
    return f"cross-check stooq={status}"


def _build_run_symbol_progress_caption(run: dict[str, object] | None) -> str | None:
    payload = _build_run_symbol_progress_payload(run)
    if payload is None:
        return None
    _, caption = payload
    return caption


def _build_run_symbol_progress_payload(run: dict[str, object] | None) -> tuple[float, str] | None:
    if not isinstance(run, dict):
        return None

    summary = run.get("run_summary")
    if isinstance(summary, dict):
        explicit_progress = _build_run_progress_payload_from_explicit_summary(summary)
        if explicit_progress is not None:
            return explicit_progress

        current_index = summary.get("current_symbol_index")
        total_symbols = summary.get("current_symbol_total") or summary.get("targeted_symbols")
        current_symbol = str(summary.get("current_symbol") or "").strip()
        if isinstance(current_index, int) and isinstance(total_symbols, int) and current_index > 0 and total_symbols > 0:
            percent = min(max((current_index / total_symbols) * 100.0, 0.0), 100.0)
            symbol_suffix = f" — symbole courant `{current_symbol}`" if current_symbol else ""
            return (percent / 100.0, f" Progression live import bars : {current_index}/{total_symbols} ({percent:.1f} %){symbol_suffix}")

        step_key = str(run.get("step_key") or "").strip()
        progress_from_summary = _build_run_progress_payload_from_summary(step_key, summary)
        if progress_from_summary is not None:
            return progress_from_summary

    return _build_run_progress_payload_from_logs(run)


def _to_non_negative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        normalized = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return normalized if normalized >= 0 else None


def _build_run_progress_payload_from_explicit_summary(summary: dict[str, object]) -> tuple[float, str] | None:
    total = _to_non_negative_int(summary.get("progress_total"))
    current = _to_non_negative_int(summary.get("progress_current"))
    if total is None or current is None or total <= 0:
        return None

    clamped_current = min(max(current, 0), total)
    percent = min(max((clamped_current / total) * 100.0, 0.0), 100.0)
    label = str(summary.get("progress_label") or " Progression live").strip()
    item = str(summary.get("progress_item") or summary.get("current_symbol") or "").strip()
    item_suffix = f" — élément courant `{item}`" if item else ""
    return (percent / 100.0, f"{label} : {clamped_current}/{total} ({percent:.1f} %){item_suffix}")


def _build_run_progress_payload_from_summary(step_key: str, summary: dict[str, object]) -> tuple[float, str] | None:
    spec = _RUN_PROGRESS_SUMMARY_SPECS.get(step_key)
    if spec is None:
        return None

    total: int | None = None
    for total_key in spec[0]:
        total = _to_non_negative_int(summary.get(total_key))
        if total is not None:
            break
    if total is None or total <= 0:
        return None

    current = 0
    for current_key in spec[1]:
        current += _to_non_negative_int(summary.get(current_key)) or 0
    if current <= 0:
        return None

    clamped_current = min(current, total)
    percent = min(max((clamped_current / total) * 100.0, 0.0), 100.0)
    return (percent / 100.0, f"{spec[2]} : {clamped_current}/{total} ({percent:.1f} %)")


def _build_run_progress_payload_from_logs(run: dict[str, object]) -> tuple[float, str] | None:
    tail_parts = []
    for key in ("stdout_tail", "stderr_tail"):
        raw_value = run.get(key)
        if isinstance(raw_value, str) and raw_value.strip():
            tail_parts.append(raw_value)
    if not tail_parts:
        return None

    step_key = str(run.get("step_key") or "").strip()
    title = {
        "data_sanitizer_daily": " Progression sanitizeur",
        "sync_earnings_calendar": " Progression earnings",
        "update_sector": "️ Progression mise à jour fondamentaux",
    }.get(step_key, " Progression live")

    for line in reversed("\n".join(tail_parts).splitlines()):
        cleaned = line.strip()
        if not cleaned:
            continue
        for pattern in _GENERIC_PROGRESS_PATTERNS:
            match = pattern.search(cleaned)
            if match is None:
                continue
            current = _to_non_negative_int(match.groupdict().get("current"))
            total = _to_non_negative_int(match.groupdict().get("total"))
            if current is None or total is None or total <= 0:
                continue
            clamped_current = min(current, total)
            percent = min(max((clamped_current / total) * 100.0, 0.0), 100.0)
            symbol = str(match.groupdict().get("symbol") or "").strip()
            suffix = f" — élément courant `{symbol}`" if symbol else ""
            return (percent / 100.0, f"{title} : {clamped_current}/{total} ({percent:.1f} %){suffix}")
    return None


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
    pending_select_key = f"{WORKFLOW_CHILD_PENDING_SELECT_KEY_PREFIX}{workflow_run_id}"
    pending_follow_key = f"{WORKFLOW_CHILD_PENDING_AUTOFOLLOW_KEY_PREFIX}{workflow_run_id}"

    default_child_run_id = current_child_run_id if current_child_run_id in child_labels else child_run_ids[0]

    pending_child_run_id = st.session_state.pop(pending_select_key, None)
    if isinstance(pending_child_run_id, str) and pending_child_run_id in child_labels:
        st.session_state[child_select_key] = pending_child_run_id

    pending_follow_value = st.session_state.pop(pending_follow_key, None)
    if isinstance(pending_follow_value, bool):
        st.session_state[follow_key] = pending_follow_value

    follow_value = st.session_state.get(follow_key)
    if not isinstance(follow_value, bool):
        st.session_state[follow_key] = workflow_active and current_child_run_id is not None

    if st.session_state.get(child_select_key) not in child_labels:
        st.session_state[child_select_key] = default_child_run_id

    current_selection = st.session_state.get(child_select_key)
    if workflow_active and bool(st.session_state.get(follow_key)) and current_child_run_id in child_labels:
        if isinstance(current_selection, str) and current_selection in child_labels and current_selection != current_child_run_id:
            st.session_state[follow_key] = False
        else:
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
                "run_id": str(run.get("run_id") or ""),
                "type": "workflow" if _is_workflow_run(run) else "étape",
                "étape": str(run.get("step_label") or run.get("step_key") or ""),
                "progression": (
                    f"{to_int(run.get('workflow_completed_steps', 0))}/{to_int(run.get('workflow_total_steps', 0))}"
                    if _is_workflow_run(run)
                    else "—"
                ),
                "statut": _status_badge(str(run.get("status", ""))),
                "compte": str(run.get("account_id") or "global"),
                "début": str(run.get("executed_at") or "—"),
                "fin": str(run.get("finished_at") or "—"),
                "durée": format_duration_hhmmss(run.get("duration_seconds", 0.0)),
                "stdout": to_int(run.get("stdout_lines", 0)),
                "stderr": to_int(run.get("stderr_lines", 0)),
                "résumé métier": build_run_summary_caption(run),
            }
            for run in all_runs
        ]
    )


def _should_render_active_run_live_progress(
    run: dict[str, object],
    *,
    active_workflow_run_ids: set[str] | None = None,
) -> bool:
    if _is_workflow_run(run):
        return False

    parent_run_id = str(run.get("parent_run_id") or "").strip()
    if parent_run_id and parent_run_id in (active_workflow_run_ids or set()):
        return False

    return True


def _active_workflow_run_id(all_runs: list[dict[str, object]]) -> str | None:
    for run in all_runs:
        if not _is_workflow_run(run):
            continue
        if str(run.get("status") or "") not in {"scheduled", "starting", "running"}:
            continue
        run_id = str(run.get("run_id") or "").strip()
        if run_id:
            return run_id
    return None


def _resolve_runtime_center_default_selected_run_id(all_runs: list[dict[str, object]], run_ids: list[str]) -> str:
    active_workflow_run_id = _active_workflow_run_id(all_runs)
    if active_workflow_run_id is not None and active_workflow_run_id in run_ids:
        return active_workflow_run_id

    for run in all_runs:
        run_id = str(run.get("run_id") or "").strip()
        if run_id in run_ids and str(run.get("status") or "") in {"scheduled", "starting", "running"}:
            return run_id

    return run_ids[0]


def _prime_runtime_center_state(all_runs: list[dict[str, object]], run_ids: list[str], labels: dict[str, str]) -> list[str]:
    pending_selected = st.session_state.pop(PENDING_SELECTED_RUN_KEY, None)
    if isinstance(pending_selected, str) and pending_selected in labels:
        st.session_state[SELECTED_RUN_KEY] = pending_selected
        st.session_state[WORKFLOW_RUNTIME_AUTO_SELECTED_RUN_KEY] = pending_selected

    pending_compare = st.session_state.pop(PENDING_COMPARE_RUNS_KEY, None)
    if pending_compare is not None:
        st.session_state[COMPARE_RUNS_KEY] = _sanitize_compare_ids(run_ids, labels, pending_compare)

    preferred_selected = _resolve_runtime_center_default_selected_run_id(all_runs, run_ids)
    default_selected = st.session_state.get(SELECTED_RUN_KEY)
    if default_selected not in labels:
        st.session_state[SELECTED_RUN_KEY] = preferred_selected
        st.session_state[WORKFLOW_RUNTIME_AUTO_SELECTED_RUN_KEY] = preferred_selected
    else:
        active_workflow_run_id = _active_workflow_run_id(all_runs)
        run_by_id = {
            str(run.get("run_id") or "").strip(): run
            for run in all_runs
            if str(run.get("run_id") or "").strip()
        }
        selected_run = run_by_id.get(str(default_selected))
        selected_parent_run_id = str(selected_run.get("parent_run_id") or "").strip() if isinstance(selected_run, dict) else ""
        auto_selected_run_id = st.session_state.get(WORKFLOW_RUNTIME_AUTO_SELECTED_RUN_KEY)
        if (
            active_workflow_run_id is not None
            and selected_parent_run_id == active_workflow_run_id
            and (auto_selected_run_id is None or auto_selected_run_id == default_selected)
        ):
            st.session_state[SELECTED_RUN_KEY] = active_workflow_run_id
            st.session_state[WORKFLOW_RUNTIME_AUTO_SELECTED_RUN_KEY] = active_workflow_run_id

    compare_defaults = _sanitize_compare_ids(run_ids, labels, st.session_state.get(COMPARE_RUNS_KEY, []))
    if compare_defaults != st.session_state.get(COMPARE_RUNS_KEY):
        st.session_state[COMPARE_RUNS_KEY] = compare_defaults

    return compare_defaults


def _selected_dataframe_row_index(table_key: str) -> int | None:
    state = st.session_state.get(table_key)
    if state is None:
        return None
    selection = getattr(state, "selection", None) or (state.get("selection") if isinstance(state, dict) else None)
    if not selection:
        return None
    rows = getattr(selection, "rows", None) or (selection.get("rows") if isinstance(selection, dict) else None)
    if not rows:
        return None
    try:
        return int(rows[0])
    except (TypeError, ValueError, IndexError):
        return None


def _resolve_history_selected_run_id(
    history_df: pd.DataFrame,
    *,
    table_key: str = WORKFLOW_HISTORY_TABLE_KEY,
) -> str | None:
    if history_df.empty or "run_id" not in history_df.columns:
        return None
    row_index = _selected_dataframe_row_index(table_key)
    if row_index is None or row_index < 0 or row_index >= len(history_df):
        return None
    run_id = str(history_df.iloc[row_index].get("run_id") or "").strip()
    return run_id or None


def _render_workflow_launcher(options: PipelineLaunchOptions, live_confirmed: bool, db_config: dict[str, str | None]) -> None:
    active_runs, _ = _merge_runs()
    active_workflows = [run for run in active_runs if _is_workflow_run(run)]
    has_other_active_runs = any(not _is_workflow_run(run) for run in active_runs)
    execution_locked = options.execution_mode == "live" and not live_confirmed

    with st.container(border=True):
        st.subheader(" Workflow complet configurable")
        for help_line in _build_workflow_scope_help_lines():
            st.caption(help_line)
        scope_alert_global, scope_alert_account = _build_workflow_scope_alert_lines()
        st.warning(scope_alert_global)
        st.success(scope_alert_account)
        workflow_range = st.selectbox(
            "Périmètre du workflow",
            options=WORKFLOW_RANGE_OPTIONS,
            index=WORKFLOW_RANGE_OPTIONS.index(str(st.session_state.get(WORKFLOW_RANGE_KEY, "1")))
            if str(st.session_state.get(WORKFLOW_RANGE_KEY, "1")) in WORKFLOW_RANGE_OPTIONS
            else 0,
            format_func=lambda value: f"Workflow complet {value} → 12",
            key=WORKFLOW_RANGE_KEY,
            disabled=bool(active_runs),
        )
        include_ml_train = st.checkbox(
            "Inclure l'étape 9 — ML Train (Model Factory)",
            value=bool(st.session_state.get(WORKFLOW_INCLUDE_ML_TRAIN_KEY, False)),
            key=WORKFLOW_INCLUDE_ML_TRAIN_KEY,
            disabled=bool(active_runs),
        )
        include_corporate_actions_sync = st.checkbox(
            "Inclure l'étape 13 — Corporate Actions Sync",
            value=bool(st.session_state.get(WORKFLOW_INCLUDE_CA_SYNC_KEY, False)),
            key=WORKFLOW_INCLUDE_CA_SYNC_KEY,
            disabled=bool(active_runs),
        )
        if not include_corporate_actions_sync and bool(st.session_state.get(WORKFLOW_INCLUDE_CA_APPLY_KEY, False)):
            st.session_state[WORKFLOW_INCLUDE_CA_APPLY_KEY] = False
        include_corporate_actions_apply = st.checkbox(
            "Inclure l'étape 14 — Corporate Actions Apply",
            value=bool(st.session_state.get(WORKFLOW_INCLUDE_CA_APPLY_KEY, False)),
            key=WORKFLOW_INCLUDE_CA_APPLY_KEY,
            disabled=bool(active_runs) or not include_corporate_actions_sync,
            help=(
                "Disponible après activation de l'étape 13, car l'application dépend de la synchronisation des corporate actions."
            ),
        )
        effective_steps = len(
            get_pipeline_workflow_steps(
                start_step="3" if workflow_range == "3" else "1",
                include_ml_train=include_ml_train,
                include_corporate_actions_sync=include_corporate_actions_sync,
                include_corporate_actions_apply=include_corporate_actions_apply,
            )
        )
        scope_suffix = " + 13 → 14" if include_corporate_actions_apply else " + 13" if include_corporate_actions_sync else ""
        workflow_kind = "cycle quotidien complet" if workflow_range == "1" else "reprise rapide sans relancer 1 et 2"
        st.caption(
            f"Lance {workflow_kind} {workflow_range} → 12{scope_suffix} dans l'ordre, avec {effective_steps} étape(s) réellement exécutée(s) "
            f"({'ML Train inclus' if include_ml_train else 'ML Train exclu'}). "
            "Les sous-runs restent historisés individuellement, et ce workflow fournit une vue globale avec logs consolidés."
        )
        delayed_start_enabled = st.checkbox(
            "Départ différé",
            value=bool(st.session_state.get(WORKFLOW_DELAYED_START_ENABLED_KEY, False)),
            key=WORKFLOW_DELAYED_START_ENABLED_KEY,
            disabled=bool(active_runs),
            help="Permet de préparer le workflow maintenant et de le lancer automatiquement plus tard, par exemple pendant la nuit.",
        )
        scheduled_for = None
        if delayed_start_enabled:
            delayed_start_time = cast(
                dt_time,
                st.time_input(
                    "Heure de démarrage souhaitée",
                    value=cast(dt_time, st.session_state.get(WORKFLOW_DELAYED_START_TIME_KEY, dt_time(hour=2, minute=0))),
                    key=WORKFLOW_DELAYED_START_TIME_KEY,
                    disabled=bool(active_runs),
                    help="Si l'heure choisie est déjà passée aujourd'hui, le workflow sera planifié pour demain à cette heure.",
                ),
            )
            scheduled_for = _resolve_delayed_workflow_start(delayed_start_time)
            st.info(
                "⏰ Départ différé actif — le workflow complet démarrera automatiquement le "
                f"`{scheduled_for.strftime('%Y-%m-%d %H:%M')}`."
            )

        if active_workflows:
            workflow_run = active_workflows[0]
            _, _, progress_fraction, progress_label = _workflow_progress(workflow_run)
            st.info(f"Workflow déjà actif : `{workflow_run.get('run_id', '')}`")
            st.progress(progress_fraction)
            st.caption(progress_label)
            st.caption(f"Mode actif : {_workflow_mode_label(workflow_run)}")
            scheduled_caption = _build_scheduled_countdown_caption(workflow_run)
            if scheduled_caption:
                st.caption(scheduled_caption)
            actual_start_caption = _build_actual_start_caption(workflow_run)
            if actual_start_caption:
                st.caption(actual_start_caption)
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
                record = start_pipeline_workflow(
                    options,
                    db_config=db_config,
                    start_step="3" if workflow_range == "3" else "1",
                    include_ml_train=include_ml_train,
                    include_corporate_actions_sync=include_corporate_actions_sync,
                    include_corporate_actions_apply=include_corporate_actions_apply,
                    scheduled_for=scheduled_for,
                )
            except RuntimeError as exc:
                st.warning(str(exc))
            else:
                st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
                existing_compare = cast(list[str], st.session_state.get(COMPARE_RUNS_KEY, [])) if isinstance(st.session_state.get(COMPARE_RUNS_KEY, []), list) else []
                st.session_state[PENDING_COMPARE_RUNS_KEY] = [record.run_id, *existing_compare][:2]
                if scheduled_for is not None:
                    st.success(
                        f"Workflow planifié en arrière-plan : `{record.run_id}` — démarrage prévu le `{scheduled_for.strftime('%Y-%m-%d %H:%M')}`"
                    )
                else:
                    st.success(f"Workflow lancé en arrière-plan : `{record.run_id}`")
                _rerun_app()

        st.divider()
        st.markdown("#### Sélection personnalisée des pipelines 1 → 12")
        st.caption(
            "Coche uniquement les étapes à exécuter. Le lancement respecte toujours l'ordre numérique 1 → 12, "
            "sans inclure automatiquement les extensions 13/14."
        )
        selectable_steps = tuple(
            step
            for step in get_pipeline_steps()
            if is_workflow_core_step_number(step.num)
        )
        selection_columns = st.columns(3)
        selected_step_keys: list[str] = []
        for index, step in enumerate(selectable_steps):
            checkbox_key = _custom_workflow_checkbox_key(step.key)
            # Étape 9 (ML Train) décochée par défaut (lourde, pas nécessaire au quotidien)
            default_checked = False if step.key == "ml_train" else True
            with selection_columns[index % len(selection_columns)]:
                is_selected = st.checkbox(
                    f"{step.num}. {step.name}",
                    value=bool(st.session_state.get(checkbox_key, default_checked)),
                    key=checkbox_key,
                    disabled=bool(active_runs),
                    help=step.desc,
                )
            if is_selected:
                selected_step_keys.append(step.key)

        if selected_step_keys:
            selected_step_labels = [
                str(step.num)
                for step in selectable_steps
                if step.key in set(selected_step_keys)
            ]
            st.caption(
                "Étapes sélectionnées : "
                + ", ".join(f"`{step_num}`" for step_num in selected_step_labels)
                + ". Elles seront exécutées dans cet ordre."
            )
        else:
            st.warning("Sélection vide : cochez au moins une étape entre 1 et 12 pour lancer un workflow personnalisé.")

        custom_execution_locked = execution_locked and "execution" in selected_step_keys
        if custom_execution_locked:
            st.warning(
                "Le workflow personnalisé inclut l'étape 12 — confirmez d'abord le mode LIVE dans les paramètres ci-dessus."
            )

        launch_selected_clicked = st.button(
            "▶️ Lancer les pipelines sélectionnés",
            key="run_pipeline_workflow_selected_steps",
            use_container_width=True,
            disabled=bool(active_runs) or not selected_step_keys or custom_execution_locked,
        )
        if launch_selected_clicked:
            try:
                record = start_pipeline_workflow(
                    options,
                    db_config=db_config,
                    selected_step_keys=tuple(selected_step_keys),
                )
            except RuntimeError as exc:
                st.warning(str(exc))
            else:
                st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
                existing_compare = cast(list[str], st.session_state.get(COMPARE_RUNS_KEY, [])) if isinstance(st.session_state.get(COMPARE_RUNS_KEY, []), list) else []
                st.session_state[PENDING_COMPARE_RUNS_KEY] = [record.run_id, *existing_compare][:2]
                st.success(f"Workflow personnalisé lancé en arrière-plan : `{record.run_id}`")
                _rerun_app()



@st.fragment(run_every="2s")
def _render_runtime_center() -> None:
    active_runs, all_runs = _merge_runs()
    active_runs_count = len(active_runs)
    previous_active_runs_count = int(st.session_state.get(WORKFLOW_RUNTIME_LAST_ACTIVE_COUNT_KEY, 0) or 0)
    st.session_state[WORKFLOW_RUNTIME_LAST_ACTIVE_COUNT_KEY] = active_runs_count
    active_workflow_run_ids = {
        str(run.get("run_id") or "").strip()
        for run in active_runs
        if _is_workflow_run(run)
    }

    st.subheader("️ Centre d'exécution & d'investigation")
    st.caption(
        "Rafraîchissement automatique toutes les 2 secondes pour les runs actifs. "
        "Vous pouvez changer de page : les pipelines continuent à tourner en arrière-plan."
    )

    if st.button(" Rafraîchir maintenant", key="pipeline_manual_refresh", use_container_width=False):
        _rerun_app()

    if active_runs:
        st.markdown("**Runs actifs**")
        for run in active_runs:
            run_id = str(run.get("run_id", ""))
            with st.container(border=True):
                cols = st.columns([3, 2, 2, 2, 1.5])
                cols[0].markdown(f"`{run.get('step_label', run.get('step_key', ''))}`  \\n`{run_id}`")
                cols[1].markdown(_status_badge(str(run.get("status", "running"))))
                cols[2].markdown(f"⏱️ {format_duration_hhmmss(run.get('duration_seconds', 0.0))}")
                cols[3].markdown(f" `{run.get('account_id') or 'global'}`")
                if cols[4].button("⏹️ Arrêter", key=f"stop_run_{run_id}", use_container_width=True):
                    stop_pipeline_run(run_id)
                    _rerun_app()
                scheduled_caption = _build_scheduled_countdown_caption(run)
                if scheduled_caption:
                    st.caption(scheduled_caption)
                actual_start_caption = _build_actual_start_caption(run)
                if actual_start_caption:
                    st.caption(actual_start_caption)
                provider_badge = _build_run_provider_badge(run)
                stooq_badge = _build_run_stooq_badge(run)
                if provider_badge:
                    st.caption(f"️ `{provider_badge}`")
                if stooq_badge:
                    st.caption(f" `{stooq_badge}`")
                if _should_render_active_run_live_progress(run, active_workflow_run_ids=active_workflow_run_ids):
                    symbol_progress_payload = _build_run_symbol_progress_payload(run)
                    if symbol_progress_payload is not None:
                        progress_fraction, progress_caption = symbol_progress_payload
                        st.progress(progress_fraction)
                        st.caption(progress_caption)
                if _is_workflow_run(run):
                    _, _, progress_fraction, progress_label = _workflow_progress(run)
                    st.progress(progress_fraction)
                    st.caption(progress_label)
    else:
        st.info("Aucun run actif pour le moment.")

    if previous_active_runs_count > 0 and active_runs_count == 0:
        _rerun_app()

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
    compare_defaults = _prime_runtime_center_state(all_runs, run_ids, labels)

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
            _rerun_app()

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
        _render_watchdog_status(selected_run)

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
            scheduled_caption = _build_scheduled_countdown_caption(selected_run)
            if scheduled_caption:
                st.caption(scheduled_caption)
            actual_start_caption = _build_actual_start_caption(selected_run)
            if actual_start_caption:
                st.caption(actual_start_caption)
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
                        st.session_state[f"{WORKFLOW_CHILD_PENDING_SELECT_KEY_PREFIX}{selected_label}"] = current_child_run_id
                        st.session_state[f"{WORKFLOW_CHILD_PENDING_AUTOFOLLOW_KEY_PREFIX}{selected_label}"] = True
                        _rerun_app()

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
                if workflow_active and not follow_current_child and current_child_run_id and selected_child_run_id != current_child_run_id:
                    st.caption("Suivi automatique suspendu après sélection manuelle d’un sous-run différent.")
                selected_child_run = get_pipeline_run_record(selected_child_run_id)
                if selected_child_run is not None:
                    selected_child_logs = read_pipeline_logs(selected_child_run_id, stream=cast(Any, stream_map[log_filter]))
                    provider_badge = _build_run_provider_badge(selected_child_run)
                    stooq_badge = _build_run_stooq_badge(selected_child_run)
                    symbol_progress_payload = _build_run_symbol_progress_payload(selected_child_run)
                    if provider_badge:
                        st.caption(f"️ `{provider_badge}`")
                    if stooq_badge:
                        st.caption(f" `{stooq_badge}`")
                    _render_watchdog_status(selected_child_run)
                    if symbol_progress_payload is not None:
                        progress_fraction, symbol_progress_caption = symbol_progress_payload
                        st.progress(progress_fraction)
                        st.caption(symbol_progress_caption)
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
        selected_run_provider_badge = _build_run_provider_badge(selected_run)
        selected_run_stooq_badge = _build_run_stooq_badge(selected_run)
        selected_run_progress_payload = _build_run_symbol_progress_payload(selected_run)
        if selected_run_provider_badge:
            st.caption(f"️ `{selected_run_provider_badge}`")
        if selected_run_stooq_badge:
            st.caption(f" `{selected_run_stooq_badge}`")
        if selected_run_progress_payload is not None:
            progress_fraction, selected_run_progress_caption = selected_run_progress_payload
            st.progress(progress_fraction)
            st.caption(selected_run_progress_caption)
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
    with st.expander("️ Historique centralisé des exécutions IHM", expanded=False):
        st.caption("Sélectionnez une ligne pour télécharger immédiatement les logs du run correspondant.")
        st.dataframe(
            history_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key=WORKFLOW_HISTORY_TABLE_KEY,
        )

        selected_history_run_id = _resolve_history_selected_run_id(history_df)
        if selected_history_run_id is None:
            st.caption("ℹ️ Aucune ligne sélectionnée dans l’historique pour le moment.")
            return

        selected_history_run = get_pipeline_run_record(selected_history_run_id)
        selected_history_status = _status_badge(str(selected_history_run.get("status") or "")) if isinstance(selected_history_run, dict) else "—"
        st.caption(f"Run historique sélectionné : `{selected_history_run_id}` | {selected_history_status}")

        history_download_specs: list[tuple[str, str, str, bool]] = []
        for label, stream in (
            ("⬇️ Log consolidé", "all"),
            ("⬇️ Stdout", "stdout"),
            ("⬇️ Stderr", "stderr"),
        ):
            available = pipeline_log_available(selected_history_run_id, stream=cast(Any, stream))
            data = read_pipeline_logs(selected_history_run_id, stream=cast(Any, stream)) if available else ""
            history_download_specs.append((label, stream, data, available))

        download_cols = st.columns(4)
        for index, (label, stream, data, available) in enumerate(history_download_specs):
            download_cols[index].download_button(
                label=label,
                data=data,
                file_name=build_log_download_name(selected_history_run_id, stream=cast(Any, stream)),
                mime="text/plain",
                key=f"history_download_{selected_history_run_id}_{stream}",
                use_container_width=True,
                disabled=not available,
            )

        if download_cols[3].button(
            " Inspecter ce run",
            key=f"history_open_run_{selected_history_run_id}",
            use_container_width=True,
        ):
            st.session_state[PENDING_SELECTED_RUN_KEY] = selected_history_run_id
            _rerun_app()

        if not any(spec[3] for spec in history_download_specs):
            st.caption("⚠️ Les artefacts de logs de ce run sont indisponibles (rotation, purge ou run incomplet).")
