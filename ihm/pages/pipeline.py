"""ihm/pages/pipeline.py — Vue séquentielle et pilotage asynchrone du pipeline métier.

**Phase 6.2 (Backlog L10)** : ce fichier a été découpé en sous-modules
``_shared``, ``_workflow``, ``_data_integrity``, ``_execution_center``,
``_alpha_scanner_diagnostics`` et ``_watcher_block``. Les imports historiques
``from ihm.pages.pipeline import X`` continuent de fonctionner via les
ré-exports ci-dessous.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Any, cast

import streamlit as st
from dataIntegrityEngine.sync_latest_quotes import estimate_sync_latest_quotes_cost
from database.connection import get_sqlalchemy_engine
from database.selector_reference import list_symbols_for_source, normalize_start_symbol
from modelFactory.db_registry import load_symbols_for_source

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
    _rerun_app,
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
    resolve_step_display_name,
)
from ihm.services.process_registry import stop_pipeline_run
from ihm.services.queries import get_alpha_scanner_dependency_diagnostic
from ihm.services.queries import get_execution_live_guard


ML_TRAIN_SYMBOL_SOURCE_OPTIONS = ("tradable-universe",)

ML_TRAIN_SYMBOL_SOURCE_LABELS = {
    "tradable-universe": "Univers tradable PIT canonique",
}

ML_TRAIN_SYMBOL_SOURCE_TO_CLI = {
    "tradable-universe": "tradable-universe",
}

DATA_INTEGRITY_SYMBOL_SOURCE_OPTIONS = (
    "active_tradable",
    *ML_TRAIN_SYMBOL_SOURCE_OPTIONS,
)

DATA_INTEGRITY_SYMBOL_SOURCE_LABELS = {
    "active_tradable": "Tous les symboles éligibles (stock_metadata)",
    **ML_TRAIN_SYMBOL_SOURCE_LABELS,
}

DATA_INTEGRITY_SYMBOL_SOURCE_TO_CLI = {
    "active_tradable": "active-tradable",
    **ML_TRAIN_SYMBOL_SOURCE_TO_CLI,
}

QUOTE_HISTORY_START_DATE_KEY = "pipeline_sync_latest_quotes_period_start_date"
QUOTE_HISTORY_END_DATE_KEY = "pipeline_sync_latest_quotes_period_end_date"
EARNINGS_HISTORY_START_DATE_KEY = "pipeline_sync_earnings_calendar_period_start_date"
EARNINGS_HISTORY_END_DATE_KEY = "pipeline_sync_earnings_calendar_period_end_date"
QUOTE_HISTORY_SYMBOL_SOURCE_KEY = "pipeline_sync_latest_quotes_symbol_source"
QUOTE_HISTORY_START_SYMBOL_KEY = "pipeline_sync_latest_quotes_start_symbol"
QUOTE_HISTORY_CONFIRM_LARGE_RUN_KEY = "pipeline_sync_latest_quotes_confirm_large_run"
EARNINGS_HISTORY_SYMBOL_SOURCE_KEY = "pipeline_sync_earnings_calendar_symbol_source"


def _coerce_ui_date(value: object, *, fallback: date) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return fallback
    return fallback


def _trade_date_or_today(options: PipelineLaunchOptions) -> date:
    trade_date_raw = str(options.trade_date or "").strip()
    if trade_date_raw:
        try:
            return date.fromisoformat(trade_date_raw)
        except ValueError:
            pass
    return date.today()


@st.cache_data(ttl=60, show_spinner=False)
def _resolve_data_integrity_scope_preview(symbol_source: str, start_symbol: str | None = None) -> dict[str, object]:
    cli_symbol_source = DATA_INTEGRITY_SYMBOL_SOURCE_TO_CLI.get(symbol_source, "active-tradable")
    normalized_start_symbol = normalize_start_symbol(start_symbol)
    symbols = list_symbols_for_source(cli_symbol_source, start_symbol=normalized_start_symbol)
    return {
        "symbol_count": len(symbols),
        "sample_symbols": symbols[:10],
        "start_symbol": normalized_start_symbol,
    }


def _is_large_quote_history_run(estimate: dict[str, object] | None) -> bool:
    if not isinstance(estimate, dict):
        return False
    return bool(estimate.get("warning_required"))


def _coerce_int_metric(value: object, *, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _coerce_float_metric(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _resolve_latest_selectbox_value(
    widget_key: str,
    widget_value: object,
    *,
    default: str,
    allowed_values: tuple[str, ...],
) -> str:
    session_value = str(st.session_state.get(widget_key, widget_value or default)).strip().lower()
    if session_value in allowed_values:
        return session_value
    candidate = str(widget_value or default).strip().lower()
    if candidate in allowed_values:
        return candidate
    return default


def _render_period_sync_block(
    step_key: str,
    options: PipelineLaunchOptions,
    *,
    workflow_active: bool,
    active_for_step: list[dict[str, object]],
    db_config: dict[str, str | None],
    all_runs: list[dict[str, object]],
) -> None:
    if step_key == "sync_latest_quotes":
        start_key = QUOTE_HISTORY_START_DATE_KEY
        end_key = QUOTE_HISTORY_END_DATE_KEY
        symbol_source_key = QUOTE_HISTORY_SYMBOL_SOURCE_KEY
        start_symbol_key = QUOTE_HISTORY_START_SYMBOL_KEY
        end_default = _trade_date_or_today(options)
        start_default = _coerce_ui_date(
            getattr(options, "data_integrity_quotes_from_date", None),
            fallback=end_default - timedelta(days=30),
        )
        end_default = _coerce_ui_date(
            getattr(options, "data_integrity_quotes_to_date", None),
            fallback=end_default,
        )
        caption = (
            "Alpaca est interrogé sur la période choisie, puis l'IHM conserve **la dernière quote disponible par symbole et par jour de marché** "
            "avant upsert dans `stock_quote_snapshots`."
        )
        button_label = "🗓️ Récupérer l'historique des quotes sur la période"
        launch_label = "4. Sync Latest Quotes — historique"
        override_keys = ("data_integrity_quotes_from_date", "data_integrity_quotes_to_date")
        source_attr = "data_integrity_quotes_symbol_source"
        start_symbol_attr = "data_integrity_quotes_start_symbol"
    elif step_key == "sync_earnings_calendar":
        start_key = EARNINGS_HISTORY_START_DATE_KEY
        end_key = EARNINGS_HISTORY_END_DATE_KEY
        symbol_source_key = EARNINGS_HISTORY_SYMBOL_SOURCE_KEY
        start_symbol_key = None
        end_default = _trade_date_or_today(options) + timedelta(days=30)
        start_default = _coerce_ui_date(options.data_integrity_earnings_from_date, fallback=end_default - timedelta(days=37))
        end_default = _coerce_ui_date(options.data_integrity_earnings_to_date, fallback=end_default)
        caption = (
            "Ce lancement applique une fenêtre `from/to` locale au run courant du calendrier earnings, sans modifier le bouton standard. "
            "Le réglage `resume` configuré dans les paramètres Data Integrity reste conservé."
        )
        button_label = "🗓️ Récupérer le calendrier earnings sur la période"
        launch_label = "5. Sync Earnings Calendar — historique"
        override_keys = ("data_integrity_earnings_from_date", "data_integrity_earnings_to_date")
        source_attr = "data_integrity_earnings_symbol_source"
        start_symbol_attr = None
    else:
        return

    disabled = workflow_active or bool(active_for_step)
    st.divider()
    st.markdown("##### Récupération historique sur période")
    st.caption(caption)
    if workflow_active:
        st.caption("Workflow complet en cours : le lancement historique manuel est temporairement désactivé.")
    elif active_for_step:
        st.caption("Un run de cette étape est déjà actif : le lancement historique attend sa fin.")

    current_symbol_source = str(
        st.session_state.get(symbol_source_key, getattr(options, source_attr, "candidates") or "candidates")
    ).strip().lower()
    if current_symbol_source not in DATA_INTEGRITY_SYMBOL_SOURCE_OPTIONS:
        current_symbol_source = "candidates"

    selected_symbol_source = str(
        st.selectbox(
            "Univers de symboles à synchroniser",
            options=DATA_INTEGRITY_SYMBOL_SOURCE_OPTIONS,
            index=DATA_INTEGRITY_SYMBOL_SOURCE_OPTIONS.index(current_symbol_source),
            key=symbol_source_key,
            format_func=lambda value: DATA_INTEGRITY_SYMBOL_SOURCE_LABELS.get(str(value), str(value)),
            help=(
                "Choisissez le périmètre ciblé : l'univers éligible courant (`stock_metadata`), les snapshots scores, "
                "l'historique PIT, les candidats du jour ou l'univers large `stock_bars_daily`."
            ),
        )
    )
    st.caption(
        "`active_tradable` = symboles `stock_metadata` actifs/tradables/éligibles ; `stock_scores_all` = union `stock_scores` + "
        "`stock_scores_history` ; `candidates` = candidats du jour ; `stock_bars_daily` = univers large."
    )

    normalized_start_symbol = None
    if start_symbol_key is not None and start_symbol_attr is not None:
        raw_start_symbol = st.text_input(
            "Commencer à partir du symbole (optionnel)",
            value=str(st.session_state.get(start_symbol_key, getattr(options, start_symbol_attr, "") or "")),
            key=start_symbol_key,
            help=(
                "Si renseigné, le run commencera au premier symbole alphabétiquement supérieur ou égal à cette valeur. "
                "Exemple : `AAG` saute `AAC`, `AAF`, etc."
            ),
        )
        normalized_start_symbol = normalize_start_symbol(raw_start_symbol)
        if normalized_start_symbol is not None:
            st.caption(f"Filtre de démarrage appliqué : symboles `>= {normalized_start_symbol}`.")

    try:
        scope_preview = _resolve_data_integrity_scope_preview(selected_symbol_source, normalized_start_symbol)
    except Exception as exc:
        st.warning(f"Impossible de prévisualiser l'univers ciblé : {exc}")
        scope_preview = None

    if isinstance(scope_preview, dict):
        symbol_count_raw = scope_preview.get("symbol_count", 0)
        symbol_count = int(symbol_count_raw) if isinstance(symbol_count_raw, (int, float, str)) else 0
        sample_symbols_values = scope_preview.get("sample_symbols", [])
        sample_symbols = [
            str(value)
            for value in (sample_symbols_values if isinstance(sample_symbols_values, (list, tuple)) else [])
            if str(value).strip()
        ]
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            st.metric("Symboles ciblés", symbol_count)
        with metric_col2:
            st.metric("Type d'univers", DATA_INTEGRITY_SYMBOL_SOURCE_LABELS.get(selected_symbol_source, selected_symbol_source))
        if symbol_count == 0:
            st.warning("Aucun symbole ne serait traité avec l'univers sélectionné.")
        elif sample_symbols:
            preview_suffix = " …" if symbol_count > len(sample_symbols) else ""
            st.caption("Extrait des premiers symboles ciblés : `" + ", ".join(sample_symbols) + preview_suffix + "`")

    period_col1, period_col2 = st.columns(2)
    with period_col1:
        start_picker = st.date_input(
            "Date de début",
            value=_coerce_ui_date(st.session_state.get(start_key), fallback=start_default),
            key=start_key,
            format="YYYY-MM-DD",
        )
    with period_col2:
        end_picker = st.date_input(
            "Date de fin",
            value=_coerce_ui_date(st.session_state.get(end_key), fallback=end_default),
            key=end_key,
            format="YYYY-MM-DD",
        )

    selected_start = _coerce_ui_date(st.session_state.get(start_key, start_picker), fallback=start_default)
    selected_end = _coerce_ui_date(st.session_state.get(end_key, end_picker), fallback=end_default)
    confirmed_large_run = True
    if selected_start > selected_end:
        st.error("Fenêtre invalide : la date de début doit être antérieure ou égale à la date de fin.")
        period_options = None
    else:
        st.caption(f"Fenêtre demandée : `{selected_start.isoformat()}` → `{selected_end.isoformat()}`.")
        if step_key == "sync_latest_quotes" and isinstance(scope_preview, dict):
            symbol_count = _coerce_int_metric(scope_preview.get("symbol_count", 0))
            quote_history_estimate = estimate_sync_latest_quotes_cost(
                symbol_count=symbol_count,
                batch_size=max(int(getattr(options, "data_integrity_quotes_batch_size", 1) or 1), 1),
                from_date=selected_start,
                to_date=selected_end,
            )
            est_col1, est_col2, est_col3 = st.columns(3)
            with est_col1:
                st.metric("Séances NYSE", _coerce_int_metric(quote_history_estimate.get("trading_days", 0)))
            with est_col2:
                st.metric("Appels API estimés", _coerce_int_metric(quote_history_estimate.get("estimated_api_calls", 0)))
            with est_col3:
                st.metric("Durée estimée", f"{_coerce_float_metric(quote_history_estimate.get('estimated_duration_minutes', 0.0)):.1f} min")
            if _is_large_quote_history_run(quote_history_estimate):
                st.warning(
                    "Run quotes historique volumineux détecté : coût API/durée potentiellement élevés. "
                    "Réduisez la fenêtre, utilisez `start_symbol` / `limit`, ou confirmez explicitement ci-dessous."
                )
                confirmed_large_run = st.checkbox(
                    "Je confirme le lancement d'un run historique quotes volumineux",
                    value=bool(st.session_state.get(QUOTE_HISTORY_CONFIRM_LARGE_RUN_KEY, False)),
                    key=QUOTE_HISTORY_CONFIRM_LARGE_RUN_KEY,
                )
            else:
                confirmed_large_run = True
        else:
            confirmed_large_run = True
        period_options = replace(
            options,
            **{
                source_attr: cast(Any, selected_symbol_source),
                override_keys[0]: cast(Any, selected_start.isoformat()),
                override_keys[1]: cast(Any, selected_end.isoformat()),
                **({start_symbol_attr: cast(Any, normalized_start_symbol)} if start_symbol_attr is not None else {}),
            },
        )
        st.code(format_command_for_display(build_pipeline_command(step_key, period_options)), language="powershell")

    if st.button(
        button_label,
        key=f"{step_key}_historical_period_launch",
        use_container_width=True,
        disabled=disabled or period_options is None or not confirmed_large_run,
    ) and period_options is not None:
        _launch_pipeline_step(
            step_key,
            (
                f"{launch_label} — {DATA_INTEGRITY_SYMBOL_SOURCE_LABELS.get(selected_symbol_source, selected_symbol_source)} "
                f"— {selected_start.isoformat()} → {selected_end.isoformat()}"
                f"{f' — depuis {normalized_start_symbol}' if normalized_start_symbol else ''}"
            ),
            period_options,
            db_config,
            all_runs,
        )


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
) -> tuple[str, str]:
    account_type = str(options.execution_account_type or "cash").strip().lower() or "cash"

    if account_type == "cash":
        severity = "success"
        message = (
            "🟢 **PARAMÈTRES COMPTE EXÉCUTION — PROFIL SWING CASH** — "
            f"l'étape 12 utilisera `type de compte={account_type}`."
        )
    elif account_type == "margin":
        severity = "warning"
        message = (
            "🟡 **PARAMÈTRES COMPTE EXÉCUTION — PROFIL MARGIN** — "
            f"l'étape 12 utilisera `type de compte={account_type}`."
        )
    else:
        severity = "info"
        message = (
            "ℹ️ **PARAMÈTRES COMPTE EXÉCUTION — CONFIGURATION SPÉCIFIQUE** — "
            f"l'étape 12 utilisera `type de compte={account_type}`."
        )

    detected_parts: list[str] = []
    mismatches: list[str] = []
    normalized_detected_account_type = (detected_account_type or "").strip().lower() or None
    if normalized_detected_account_type in {"margin", "cash"}:
        detected_parts.append(f"type broker détecté : `{normalized_detected_account_type}`")
        if account_type != normalized_detected_account_type:
            mismatches.append("type de compte")

    if detected_parts:
        message += " Préremplissage broker pour ce compte : " + " ; ".join(detected_parts) + "."
    if mismatches:
        severity = "error"
        labels = ", ".join(mismatches)
        message += (
            f" ⚠️ Incohérence critique : le réglage actuellement sélectionné diffère du broker détecté pour {labels}."
        )

    return severity, message


def _build_fractional_trading_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]:
    enabled = bool(getattr(options, "allow_fractional_shares", True))
    mode = str(getattr(options, "execution_mode", "simulate") or "simulate").strip().lower() or "simulate"
    if enabled:
        severity = "success" if mode in {"paper", "live"} else "info"
        return (
            severity,
            "🧮 **MODE FRACTIONNAIRE** — activé. Les lancements IHM propageront `--allow-fractional-shares` "
            "vers `risk_management` et `run_execution.py` pour ce workflow.",
        )
    return (
        "warning",
        "🧮 **MODE FRACTIONNAIRE** — désactivé. Les étapes risk/execution lancées depuis cette page resteront en quantités entières.",
    )


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


def _build_execution_protection_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]:
    take_profit_pct = float(getattr(options, "execution_take_profit_pct", 0.08) or 0.08)
    trailing_stop_pct = float(getattr(options, "execution_trailing_stop_pct", 0.05) or 0.05)
    submission_window = str(getattr(options, "execution_submission_window", "both") or "both")
    trailing_trigger = str(getattr(options, "execution_trailing_trigger", "multiple_r") or "multiple_r")
    if trailing_trigger == "profit_pct":
        trigger_label = f"`profit_pct` à +{float(getattr(options, 'execution_trailing_profit_pct', 0.03) or 0.03) * 100:.1f} %"
    else:
        trigger_label = f"`multiple_r` à {float(getattr(options, 'execution_trailing_r_multiple', 1.0) or 1.0):.2f}R"
    return (
        "info",
        "🎯 **PROTECTION POSITION** — "
        f"TP `+{take_profit_pct * 100:.1f} %` ; "
        f"trigger trailing {trigger_label} ; "
        f"trailing stop `-{trailing_stop_pct * 100:.1f} %` ; "
        f"fenêtre de soumission `{submission_window}`. "
        "Le **stop initial** est calculé automatiquement par le step 11 Risk "
        "(`stop_price_initial` / `risk_per_share`, basé sur l'ATR).",
    )


def _build_live_risk_guard_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]:
    drawdown_pct = float(getattr(options, "risk_max_portfolio_drawdown_pct", 0.15) or 0.15)
    daily_loss_pct = float(getattr(options, "risk_max_daily_loss_pct", 0.05) or 0.05)
    target_annual_vol = float(getattr(options, "risk_target_annual_vol", 0.0) or 0.0)
    min_ml_coverage_ratio = float(getattr(options, "risk_min_ml_coverage_ratio", 0.0) or 0.0)
    vol_lookback_days = int(getattr(options, "risk_vol_target_lookback_days", 60) or 60)
    vol_label = (
        f"cible `{target_annual_vol * 100:.1f} %` / lookback `{vol_lookback_days}j`"
        if target_annual_vol > 0
        else "désactivé"
    )
    ml_label = f"`{min_ml_coverage_ratio * 100:.0f} %` mini" if min_ml_coverage_ratio > 0 else "désactivé"
    severity = "warning" if target_annual_vol <= 0 or min_ml_coverage_ratio <= 0 else "success"
    return (
        severity,
        "🛡️ **GARDE-FOUS RISK LIVE** — "
        f"DD portefeuille `-{drawdown_pct * 100:.1f} %` ; "
        f"perte journalière `-{daily_loss_pct * 100:.1f} %` ; "
        f"vol targeting {vol_label} ; "
        f"gate couverture ML {ml_label}. "
        "Modification : **Pipeline > Paramètres Risk Management > Kelly sizing & options avancées**.",
    )


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
        detected_capital_preset = str(st.session_state.get(DETECTED_CAPITAL_PRESET_KEY) or "").strip() or None
        selected_capital_preset = str(st.session_state.get(CAPITAL_PRESET_KEY) or "").strip() or None
        detected_equity = float(options.risk_account_equity) if options.risk_account_equity > 0 else None
    else:
        detected_account_type = None
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
    fractional_severity, fractional_message = _build_fractional_trading_banner_payload(options)
    getattr(st, fractional_severity)(fractional_message)
    protection_severity, protection_message = _build_execution_protection_banner_payload(options)
    getattr(st, protection_severity)(protection_message)
    risk_severity, risk_message = _build_live_risk_guard_banner_payload(options)
    getattr(st, risk_severity)(risk_message)
    account_severity, account_message = _build_execution_account_banner_payload(
        options,
        detected_account_type=detected_account_type,
    )
    getattr(st, account_severity)(account_message)
    swing_severity, swing_message = _build_swing_only_banner_payload(options)
    getattr(st, swing_severity)(swing_message)


def _build_swing_only_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]:
    """Alerte si ``execution_swing_only=True`` (obsolète post-PDT FINRA 2026-06-04).

    Depuis la suppression de la règle PDT par la FINRA, le day trading intraday
    est autorisé sans restriction. Tous les presets de capital utilisent
    ``execution_swing_only=False``. Un opérateur qui active ``swing_only=True``
    se bride inutilement.
    """
    if options.execution_swing_only is True:
        return (
            "warning",
            "⚠️ **SWING ONLY ACTIF** — Ce mode restreint les achats/ventes intraday. "
            "Depuis le 4 juin 2026, la FINRA a **supprimé la règle PDT** : le day trading "
            "est libre pour tous les comptes, sans limite de 3 trades ni seuil de 25 000 $. "
            "Tous les presets de capital utilisent ``swing_only=False``. "
            "**Décochez cette option** sauf si vous voulez explicitement vous restreindre au swing seul.",
        )
    return "info", ""


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


@st.cache_data(ttl=60, show_spinner=False)
def _resolve_ml_train_scope_preview(
    symbol_source: str,
) -> dict[str, object]:
    engine = get_sqlalchemy_engine()
    cli_symbol_source = ML_TRAIN_SYMBOL_SOURCE_TO_CLI.get(symbol_source, "tradable-universe")
    resolved_symbols = load_symbols_for_source(engine, cli_symbol_source)
    return {
        "symbol_count": len(resolved_symbols),
        "raw_symbol_count": len(resolved_symbols),
        "sample_symbols": resolved_symbols[:10],
    }


def _render_ml_scope_block(
    options: PipelineLaunchOptions,
    *,
    workflow_active: bool,
    active_for_step: list[dict[str, object]],
    db_config: dict[str, str | None],
    all_runs: list[dict[str, object]],
    step_key: str,
    selectbox_key: str,
    button_key: str,
    button_label: str,
    label_prefix: str,
    source_attr: str,
    start_symbol_attr: str | None = None,
    historical_range: bool = False,
) -> None:
    disabled = workflow_active or bool(active_for_step)
    if workflow_active:
        st.caption("Workflow complet en cours : le lancement ML ciblé est temporairement désactivé.")
    elif active_for_step:
        st.caption(f"Un run `{label_prefix}` est déjà actif : le lancement ML ciblé attend la fin de ce run.")

    selected_symbol_source = "tradable-universe"
    st.caption(
        "Le scope ML est l'univers tradable PIT canonique. Les scores techniques enrichissent les features ou servent de veto; ils ne déterminent pas les symboles entraînés ou prédits."
    )

    # --- Start symbol (ML Train only) ---
    normalized_start_symbol: str | None = None
    start_symbol_session_key = f"{selectbox_key}_start_symbol"
    if start_symbol_attr is not None:
        raw_start_symbol = st.text_input(
            "Commencer à partir du symbole (optionnel)",
            value=str(st.session_state.get(start_symbol_session_key, getattr(options, start_symbol_attr, "") or "")),
            key=start_symbol_session_key,
            help=(
                "Si renseigné, l'entraînement commencera au premier symbole alphabétiquement supérieur ou égal à cette valeur. "
                "Exemple : `HGI` démarre à HGI et ignore les symboles précédents dans l'univers sélectionné."
            ),
        )
        normalized_start_symbol = normalize_start_symbol(raw_start_symbol)
        if normalized_start_symbol is not None:
            st.caption(f"Filtre de démarrage appliqué : symboles `>= {normalized_start_symbol}`.")

    try:
        scope_preview = _resolve_ml_train_scope_preview(selected_symbol_source)
    except Exception as exc:
        st.warning(f"Impossible de prévisualiser l'univers ML : {exc}")
        scope_preview = None

    if isinstance(scope_preview, dict):
        raw_symbol_count_raw = scope_preview.get("raw_symbol_count", 0)
        raw_symbol_count = int(raw_symbol_count_raw) if isinstance(raw_symbol_count_raw, (int, float, str)) else 0
        symbol_count_raw = scope_preview.get("symbol_count", 0)
        symbol_count = int(symbol_count_raw) if isinstance(symbol_count_raw, (int, float, str)) else 0
        sample_symbols_values = scope_preview.get("sample_symbols", [])
        sample_symbols = [
            str(value)
            for value in (sample_symbols_values if isinstance(sample_symbols_values, (list, tuple)) else [])
            if str(value).strip()
        ]
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            st.metric("Symboles résolus", raw_symbol_count)
        with metric_col2:
            st.metric("Symboles entraînés", symbol_count)

        if symbol_count == 0:
            st.warning("Aucun symbole ne serait entraîné avec les paramètres ML actuels.")
        elif sample_symbols:
            preview_suffix = " …" if symbol_count > len(sample_symbols) else ""
            verb = "prédits" if step_key == "ml_predict" else "entraînés"
            st.caption(f"Extrait des premiers symboles {verb} : `" + ", ".join(sample_symbols) + preview_suffix + "`")

    if historical_range:
        start_date = str(getattr(options, "ml_training_start_date", "") or "").strip()
        end_date = str(getattr(options, "ml_training_end_date", "") or "").strip()
        if start_date and end_date:
            st.caption(f"Fenêtre historique appliquée : `{start_date}` → `{end_date}`.")

    command_preview_overrides: dict[str, object] = {source_attr: cast(Any, selected_symbol_source)}
    if start_symbol_attr is not None:
        command_preview_overrides[start_symbol_attr] = normalized_start_symbol
    if step_key == "ml_predict":
        command_preview_overrides["ml_predict_use_historical_range"] = historical_range
    command_preview_options = replace(options, **command_preview_overrides)
    st.caption("Commande du bouton ci-dessous :")
    st.code(
        format_command_for_display(build_pipeline_command(step_key, command_preview_options)),
        language="powershell",
    )

    if st.button(
        button_label,
        key=button_key,
        use_container_width=True,
        disabled=disabled,
    ):
        overrides: dict[str, object] = {source_attr: cast(Any, selected_symbol_source)}
        if start_symbol_attr is not None:
            overrides[start_symbol_attr] = normalized_start_symbol
        if step_key == "ml_predict":
            overrides["ml_predict_use_historical_range"] = historical_range
        _launch_pipeline_step(
            step_key,
            f"{label_prefix} — {ML_TRAIN_SYMBOL_SOURCE_LABELS.get(selected_symbol_source, selected_symbol_source)}",
            replace(options, **overrides),
            db_config,
            all_runs,
        )


def _render_ml_train_scope_block(
    options: PipelineLaunchOptions,
    *,
    workflow_active: bool,
    active_for_step: list[dict[str, object]],
    db_config: dict[str, str | None],
    all_runs: list[dict[str, object]],
) -> None:
    _render_ml_scope_block(
        options,
        workflow_active=workflow_active,
        active_for_step=active_for_step,
        db_config=db_config,
        all_runs=all_runs,
        step_key="ml_train",
        selectbox_key="pipeline_ml_train_symbol_source",
        button_key="run_pipeline_step_ml_train_scoped",
        button_label="Entraîner l'univers sélectionné",
        label_prefix="9. ML Train (Model Factory)",
        source_attr="ml_train_symbol_source",
        start_symbol_attr="ml_train_start_symbol",
        historical_range=True,
    )


def _render_ml_predict_scope_block(
    options: PipelineLaunchOptions,
    *,
    workflow_active: bool,
    active_for_step: list[dict[str, object]],
    db_config: dict[str, str | None],
    all_runs: list[dict[str, object]],
) -> None:
    _render_ml_scope_block(
        options,
        workflow_active=workflow_active,
        active_for_step=active_for_step,
        db_config=db_config,
        all_runs=all_runs,
        step_key="ml_predict",
        selectbox_key="pipeline_ml_predict_symbol_source",
        button_key="run_pipeline_step_ml_predict_scoped",
        button_label="Prédire l'univers sélectionné",
        label_prefix="10. ML Predict",
        source_attr="ml_predict_symbol_source",
        historical_range=True,
    )


def _build_pipeline_run_context() -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, dict[str, object]],
    bool,
    dict[str, list[dict[str, object]]],
]:
    active_runs, all_runs = _merge_runs()
    latest_by_step = _latest_run_by_step(all_runs)
    workflow_active = any(_is_workflow_run(run) for run in active_runs)
    active_by_step: dict[str, list[dict[str, object]]] = {}
    for run in active_runs:
        active_by_step.setdefault(str(run.get("step_key", "")), []).append(run)
    return active_runs, all_runs, latest_by_step, workflow_active, active_by_step


_PIPELINE_SUCCESS_STATUSES = {"completed", "success", "succeeded", "done"}


def _normalize_pipeline_run_status(value: object) -> str:
    return str(value or "").strip().lower()


def _safe_iterable(value: object) -> list[object]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _previous_pipeline_step_key(step_key: str) -> str | None:
    ordered_steps = [step.key for step in get_pipeline_steps()]
    try:
        index = ordered_steps.index(step_key)
    except ValueError:
        return None
    if index <= 0:
        return None
    return ordered_steps[index - 1]


def _pipeline_state_machine_lock_reason(
    step_key: str,
    latest_by_step: dict[str, dict[str, object]],
) -> str | None:
    previous_step_key = _previous_pipeline_step_key(step_key)
    if previous_step_key is None:
        return None
    previous_run = latest_by_step.get(previous_step_key)
    if not previous_run:
        return (
            f"Étape verrouillée : l'étape précédente `{previous_step_key}` n'a encore aucun run `SUCCESS` / `COMPLETED`."
        )
    previous_status = _normalize_pipeline_run_status(previous_run.get("status"))
    if previous_status in _PIPELINE_SUCCESS_STATUSES:
        return None
    return (
        f"Étape verrouillée : `{previous_step_key}` est actuellement en statut `{previous_run.get('status', 'UNKNOWN')}`. "
        "Terminez l'étape précédente avec succès avant de lancer la suivante."
    )


def _render_live_execution_freeze_banner(live_guard: dict[str, object]) -> None:
    if not bool(live_guard.get("active", False)):
        return
    run_ids = ", ".join(f"`{value}`" for value in _safe_iterable(live_guard.get("run_ids")) if str(value).strip())
    accounts = ", ".join(f"`{value}`" for value in _safe_iterable(live_guard.get("accounts")) if str(value).strip())
    st.error(
        "🧊 **Gel pipeline actif** — un run d'exécution `live` reste `RUNNING`"
        f" sur {accounts or '`compte inconnu`'} ({run_ids or '`run inconnu`'}). "
        "Les lancements manuels sont temporairement désactivés pour éviter toute collision opérateur."
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
    live_guard: dict[str, object],
) -> None:
    command_preview = format_command_for_display(build_pipeline_command(step.key, options))
    with st.expander(f"**{step.num}. {resolve_step_display_name(step)}**", expanded=False):
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
                st.caption(
                    "⚖️ Contraintes d'exécution : "
                    f"compte=`{options.execution_account_type}` | swing_only=`{options.execution_swing_only}`"
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
            state_machine_lock_reason = _pipeline_state_machine_lock_reason(step.key, latest_by_step)
            live_guard_lock_reason = (
                "Gel IHM actif : un run d'exécution live est encore en cours."
                if bool(live_guard.get("active", False))
                else None
            )
            dependency_locked_reason = (
                _alpha_scanner_dependency_block_reason(dependency_diagnostic) if step.key == "alpha_scanner" else None
            )
            active_for_step = active_by_step.get(step.key, [])
            companion_active_runs = (
                [
                    *active_by_step.get("import_news_pending_loop", []),
                    *active_by_step.get("score_sentiment_only", []),
                    *active_by_step.get("score_history_relevance_backfill_auto", []),
                    *active_by_step.get("sentiment_standard_scoring", []),
                    *active_by_step.get("sentiment_relevance_backfill", []),
                    *active_by_step.get("rebuild_daily_sentiment_features_only", []),
                    *active_by_step.get("sentiment_contextual_scoring", []),
                ]
                if step.key == "sentiment_pipeline"
                else []
            )
            if active_for_step:
                st.info(f"{len(active_for_step)} run(s) actif(s) pour cette étape.")
                for run in active_for_step:
                    run_id = str(run.get("run_id", ""))
                    st.caption(f"Actif : `{run_id}`")
                    if st.button("⏹️ Arrêter ce run", key=f"stop_step_run_{run_id}", use_container_width=True):
                        stop_pipeline_run(run_id)
                        _rerun_app()
                st.caption("Le bouton de lancement est masque tant qu'un run de cette etape est en cours.")
            else:
                run_clicked = st.button(
                    "▶️ Lancer en arrière-plan",
                    key=f"run_pipeline_step_{step.key}",
                    type="primary",
                    use_container_width=True,
                    disabled=(
                        execution_locked
                        or workflow_active
                        or dependency_locked_reason is not None
                        or state_machine_lock_reason is not None
                        or live_guard_lock_reason is not None
                        or bool(companion_active_runs)
                    ),
                    help=dependency_locked_reason,
                )
                if execution_locked:
                    st.warning("Confirmez d'abord le mode LIVE dans les paramètres ci-dessus.")
                if workflow_active:
                    st.warning("Un workflow complet est en cours : le lancement manuel des étapes est temporairement désactivé.")
                if dependency_locked_reason is not None:
                    st.error(dependency_locked_reason)
                if state_machine_lock_reason is not None:
                    st.warning(state_machine_lock_reason)
                if live_guard_lock_reason is not None:
                    st.error(live_guard_lock_reason)
                if companion_active_runs:
                    run_ids = ", ".join(f"`{run.get('run_id', '')}`" for run in companion_active_runs)
                    st.warning(
                        "Le lancement manuel du Sentiment Pipeline est temporairement désactivé : "
                        "un outil manuel/backfill sentiment est déjà actif "
                        f"({run_ids})."
                    )

                if run_clicked:
                    _launch_pipeline_step(
                        step.key,
                        f"{step.num}. {resolve_step_display_name(step)}",
                        options,
                        db_config,
                        all_runs,
                    )

            if step.key == "ml_train":
                st.divider()
                _render_ml_train_scope_block(
                    options,
                    workflow_active=workflow_active,
                    active_for_step=active_for_step,
                    db_config=db_config,
                    all_runs=all_runs,
                )
            if step.key == "ml_predict":
                st.divider()
                _render_ml_predict_scope_block(
                    options,
                    workflow_active=workflow_active,
                    active_for_step=active_for_step,
                    db_config=db_config,
                    all_runs=all_runs,
                )

            if step.key in {"ml_train", "ml_predict"}:
                st.divider()
                _render_ml_inspection_link(step.key)

        if step.key in {"sync_latest_quotes", "sync_earnings_calendar"}:
            _render_period_sync_block(
                step.key,
                options,
                workflow_active=workflow_active,
                active_for_step=active_for_step,
                db_config=db_config,
                all_runs=all_runs,
            )

        _render_step_result(latest_by_step.get(step.key))


@st.fragment(run_every="2s")
def _render_step_panels(
    options: PipelineLaunchOptions,
    live_confirmed: bool,
    db_config: dict[str, str | None],
    live_guard: dict[str, object],
) -> None:
    active_runs, all_runs, latest_by_step, workflow_active, active_by_step = _build_pipeline_run_context()
    dependency_diagnostic = get_alpha_scanner_dependency_diagnostic()

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
                live_guard=live_guard,
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
            live_guard=live_guard,
        )
        if step.key == "execution":
            _render_watcher_handoff_panel(options)


def render() -> None:
    st.header("🔄 Pipeline Quotidien")
    st.caption("Ordre d'exécution strict — chaque étape dépend de la précédente.")

    options, live_confirmed = _build_launch_options()
    _render_execution_mode_banner(options)
    live_guard = get_execution_live_guard(account_id=str(options.account_id or "").strip() or None)
    _render_live_execution_freeze_banner(live_guard)
    db_config = get_runtime_db_config()

    _render_workflow_launcher(options, live_confirmed, db_config)
    _render_runtime_center()
    _render_step_panels(options, live_confirmed, db_config, live_guard)

    _, all_runs, latest_by_step, workflow_active, active_by_step = _build_pipeline_run_context()
    _render_import_news_panel(
        options,
        db_config,
        workflow_active=workflow_active,
        active_by_step=active_by_step,
        all_runs=all_runs,
        latest_by_step=latest_by_step,
    )


run_page_if_standalone(__name__, render)
