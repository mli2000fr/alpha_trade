"""ihm/pages/backtesting.py — Page dédiée au backtesting et au backfill PIT."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pandas as pd
import streamlit as st

from common.capital_presets import (
    CapitalPreset,
    DEFAULT_CAPITAL_PRESET_KEY,
    capital_preset_fingerprint,
    get_capital_preset_by_key,
    load_capital_presets,
    resolve_capital_preset_for_equity,
)
from ihm.components.db_controls import render_db_connection_form
from ihm.components.metrics import format_duration_hhmmss
from ihm.pages import run_page_if_standalone
from ihm.services.backtesting_registry import (
    backtesting_log_available,
    build_backtesting_log_download_name,
    get_backtesting_run_record,
    list_active_backtesting_runs,
    list_active_backtesting_runs_by_kind,
    load_backtesting_history,
    read_backtesting_logs,
    start_backtesting_run,
    stop_backtesting_run,
)
from ihm.services.backtesting_runner import (
    PROJECT_ROOT,
    BackfillScoresHistoryOptions,
    BacktestRunOptions,
    CalibrateConvictionWeightsOptions,
    CalibrateSentimentWeightsOptions,
    DiagnoseScreenerOptions,
    RecommendScreenerOptions,
    WalkForwardConvictionOptions,
    WalkForwardSentimentOptions,
    build_backtesting_command,
    format_command_for_display,
)
from ihm.services.db import get_runtime_db_config
from ihm.services.fractional_trading_preferences import (
    FractionalTradingPreferences,
    load_persisted_fractional_trading_preferences,
    save_persisted_fractional_trading_preferences,
)
from ihm.services.queries import get_backtesting_ml_coverage_diagnostic, get_backtesting_pit_history_diagnostic
from ihm.services.screener_artifact_history import (
    build_global_screener_artifact_history,
    build_screener_artifact_history_rows,
)
from ihm.services.screener_recommendations import build_screener_artifact_summary

SELECTED_RUN_KEY = "ihm_backtesting_selected_run_id"
LOG_FILTER_KEY = "ihm_backtesting_log_filter"
PENDING_SELECTED_RUN_KEY = "ihm_backtesting_pending_selected_run_id"
BACKTESTING_HISTORY_TABLE_KEY = "ihm_backtesting_runtime_history_table"
TAIL_LINES = 250
CAPITAL_PRESET_CUSTOM = "custom"
BT_RUN_CAPITAL_PRESET_KEY = "bt_run_capital_preset"
BT_RUN_CAPITAL_PRESET_SIGNATURE_KEY = "bt_run_capital_preset_signature"
BT_BACKFILL_CAPITAL_PRESET_KEY = "bt_backfill_capital_preset"
BT_BACKFILL_CAPITAL_PRESET_SIGNATURE_KEY = "bt_backfill_capital_preset_signature"
BT_RUN_CONFIGURATION_PRESET_KEY = "bt_run_configuration_preset"
BT_RUN_ALLOW_FRACTIONAL_SHARES_KEY = "bt_run_allow_fractional_shares"
LOAD_GLOBAL_SCREENER_HISTORY_KEY = "ihm_backtesting_load_global_screener_history"
RUNTIME_CENTER_AUTO_UPDATE_KEY = "ihm_backtesting_runtime_center_auto_update"

RUN_CONFIGURATION_PRESETS: dict[str, dict[str, object]] = {
    "pipeline_live_like": {
        "label": "Replay le plus proche du pipeline live aujourd'hui",
        "description": (
            "Préremplit `--engine-mode pipeline`, `--ml-pit-strategy use-persisted` et la chaîne "
            "Phase 2 → 3 → 4 → 5 → 7 pour rejouer au plus près le pipeline live aujourd'hui."
        ),
        "state_updates": {
            "bt_run_engine_mode": "pipeline",
            "bt_run_ml_pit_strategy": "use-persisted",
            "bt_run_phase2_mode": "risk_execution",
            "bt_run_phase3_mode": "execution_replay",
            "bt_run_phase4_mode": "protection_replay",
            "bt_run_phase5_mode": "watcher_replay",
            "bt_run_phase7_mode": "exit_lifecycle_replay",
        },
    },
    "production_parity": {
        "label": "Production parity — pré-live obligatoire",
        "description": (
            "Préremplit la chaîne complète de replay `risk → execution → protection → watcher → exit lifecycle` "
            "pour produire un run de parité backtest ↔ live/paper avant passage en production."
        ),
        "state_updates": {
            "bt_run_engine_mode": "pipeline",
            "bt_run_ml_pit_strategy": "use-persisted",
            "bt_run_phase2_mode": "risk_execution",
            "bt_run_phase3_mode": "execution_replay",
            "bt_run_phase4_mode": "protection_replay",
            "bt_run_phase5_mode": "watcher_replay",
            "bt_run_phase7_mode": "exit_lifecycle_replay",
        },
    },
    "standard_research": {
        "label": "Backtest standard (research)",
        "description": (
            "Réinitialise les options de fidélité opt-in sur le comportement standard : "
            "`research`, stratégie ML PIT `auto`, phases 2/3/4/5/7 désactivées."
        ),
        "state_updates": {
            "bt_run_engine_mode": "research",
            "bt_run_ml_pit_strategy": "auto",
            "bt_run_phase2_mode": "off",
            "bt_run_phase3_mode": "off",
            "bt_run_phase4_mode": "off",
            "bt_run_phase5_mode": "off",
            "bt_run_phase7_mode": "off",
        },
    },
}

PIPELINE_DEFENSIVE_OVERLAY_SESSION_KEYS = (
    "bt_run_max_portfolio_dd_pct",
    "bt_run_dd_recovery_pct",
    "bt_run_target_annual_vol_raw",
    "bt_run_min_ml_coverage_ratio_raw",
)


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return default


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(cast(Any, value))
    except (TypeError, ValueError):
        return default


def _parse_optional_int(raw_value: str, *, label: str) -> int | None:
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        st.warning(f"Valeur invalide pour `{label}` : `{raw_value}`. Le champ est ignoré.")
        return None


def _parse_optional_float(raw_value: str, *, label: str) -> float | None:
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        st.warning(f"Valeur invalide pour `{label}` : `{raw_value}`. Le champ est ignoré.")
        return None


def _get_capital_presets() -> tuple[CapitalPreset, ...]:
    try:
        return load_capital_presets()
    except Exception:
        return ()


def _get_capital_preset_options() -> list[str]:
    presets = _get_capital_presets()
    base_options = [preset.key for preset in presets]
    if DEFAULT_CAPITAL_PRESET_KEY in base_options:
        return [CAPITAL_PRESET_CUSTOM, *base_options]
    return [CAPITAL_PRESET_CUSTOM, DEFAULT_CAPITAL_PRESET_KEY, *base_options]


def _get_run_configuration_preset(preset_key: str) -> dict[str, object] | None:
    preset = RUN_CONFIGURATION_PRESETS.get(preset_key)
    return cast(dict[str, object] | None, preset)


def _ensure_run_configuration_preset_session_key() -> str:
    options = list(RUN_CONFIGURATION_PRESETS)
    current = str(st.session_state.get(BT_RUN_CONFIGURATION_PRESET_KEY, "pipeline_live_like") or "pipeline_live_like")
    if current not in options:
        current = "pipeline_live_like"
        st.session_state[BT_RUN_CONFIGURATION_PRESET_KEY] = current
    return current


def _format_run_configuration_preset_label(preset_key: str) -> str:
    preset = _get_run_configuration_preset(preset_key)
    if preset is None:
        return preset_key
    return str(preset.get("label", preset_key))


def _apply_run_configuration_preset(selected_preset_key: str) -> dict[str, object] | None:
    preset = _get_run_configuration_preset(selected_preset_key)
    if preset is None:
        return None
    updates = cast(dict[str, object], preset.get("state_updates", {}))
    for session_key, session_value in updates.items():
        st.session_state[session_key] = session_value
    if selected_preset_key in {"pipeline_live_like", "production_parity"}:
        for session_key in PIPELINE_DEFENSIVE_OVERLAY_SESSION_KEYS:
            st.session_state.pop(session_key, None)
    elif selected_preset_key == "standard_research":
        st.session_state["bt_run_max_portfolio_dd_pct"] = 0.0
        st.session_state["bt_run_dd_recovery_pct"] = 0.92
        st.session_state["bt_run_target_annual_vol_raw"] = ""
        st.session_state["bt_run_min_ml_coverage_ratio_raw"] = ""
    return preset


def _format_capital_preset_label(preset_key: str) -> str:
    if preset_key == CAPITAL_PRESET_CUSTOM:
        return "Personnalisé / auto"
    preset = get_capital_preset_by_key(preset_key)
    return preset.label if preset is not None else preset_key


def _resolve_default_capital_preset_key(equity: float | None) -> str:
    detected = resolve_capital_preset_for_equity(equity)
    if detected is not None:
        return detected.key
    return DEFAULT_CAPITAL_PRESET_KEY


def _ensure_capital_preset_session_key(session_key: str, equity: float | None) -> str:
    options = _get_capital_preset_options()
    current = str(st.session_state.get(session_key, "") or "")
    if current not in options:
        current = _resolve_default_capital_preset_key(equity)
        st.session_state[session_key] = current
    return current


def _apply_run_capital_preset(selected_preset_key: str, equity: float) -> CapitalPreset | None:
    preset = get_capital_preset_by_key(selected_preset_key) if selected_preset_key != CAPITAL_PRESET_CUSTOM else None
    # Inclure le fingerprint dans la signature pour détecter les changements du YAML
    fp = capital_preset_fingerprint(preset) if preset is not None else "custom"
    signature = f"{selected_preset_key}|{equity:.2f}|{fp}"
    if str(st.session_state.get(BT_RUN_CAPITAL_PRESET_SIGNATURE_KEY, "") or "") == signature:
        return preset
    if selected_preset_key == CAPITAL_PRESET_CUSTOM or preset is None:
        st.session_state[BT_RUN_CAPITAL_PRESET_SIGNATURE_KEY] = signature
        return preset
    values = preset.values
    current_account_type = str(st.session_state.get("bt_run_account_type", "margin") or "margin").strip().lower()
    if current_account_type not in {"margin", "cash"}:
        current_account_type = "margin"
    st.session_state["bt_run_account_type"] = current_account_type
    st.session_state["bt_run_swing_only"] = bool(values.get("execution_swing_only", st.session_state.get("bt_run_swing_only", False)))
    st.session_state["bt_run_max_positions"] = _to_int(
        values.get("risk_max_positions", st.session_state.get("bt_run_max_positions", 20)),
        20,
    )
    # Appliquer aussi le DD breaker et les paramètres de recovery du preset
    st.session_state["bt_run_max_portfolio_dd_pct"] = _to_float(
        values.get("backtesting_max_portfolio_dd_pct", values.get("risk_max_drawdown_pct", 0.12)),
        0.12,
    )
    st.session_state["bt_run_dd_recovery_pct"] = _to_float(
        values.get("backtesting_dd_recovery_pct", values.get("risk_dd_recovery_pct", 0.92)),
        0.92,
    )
    st.session_state[BT_RUN_CAPITAL_PRESET_SIGNATURE_KEY] = signature
    return preset


def _resolve_pipeline_backtest_defaults(
    *,
    engine_mode: str,
    selected_run_preset_key: str,
    auto_run_preset_key: str,
) -> dict[str, float | None]:
    defaults: dict[str, float | None] = {
        "max_portfolio_dd_pct": 0.0,
        "max_sector_exposure_pct": 0.0,
        "max_entry_gap_pct": 0.0,
        "dd_recovery_pct": 0.92,
        "target_annual_vol": None,
        "min_ml_coverage_ratio": None,
    }
    if str(engine_mode or "research").strip().lower() != "pipeline":
        return defaults

    effective_preset_key = (
        auto_run_preset_key
        if selected_run_preset_key == CAPITAL_PRESET_CUSTOM
        else selected_run_preset_key
    )
    preset = get_capital_preset_by_key(effective_preset_key)
    values = preset.values if preset is not None else {}
    return {
        "max_portfolio_dd_pct": _to_float(
            values.get("backtesting_max_portfolio_dd_pct", values.get("risk_max_drawdown_pct", 0.12)),
            0.12,
        ),
        "max_sector_exposure_pct": _to_float(
            values.get("backtesting_max_sector_exposure_pct", values.get("risk_max_sector_weight", 0.25)),
            0.25,
        ),
        "max_entry_gap_pct": _to_float(values.get("backtesting_max_entry_gap_pct", 0.03), 0.03),
        "dd_recovery_pct": _to_float(values.get("backtesting_dd_recovery_pct", 0.92), 0.92),
        "target_annual_vol": _to_float(values.get("backtesting_target_annual_vol", 0.15), 0.15),
        "min_ml_coverage_ratio": _to_float(values.get("backtesting_min_ml_coverage_ratio", 0.80), 0.80),
    }


def _apply_backfill_capital_preset(selected_preset_key: str, capital: float) -> CapitalPreset | None:
    signature = f"{selected_preset_key}|{capital:.2f}"
    if str(st.session_state.get(BT_BACKFILL_CAPITAL_PRESET_SIGNATURE_KEY, "") or "") == signature:
        return get_capital_preset_by_key(selected_preset_key) if selected_preset_key != CAPITAL_PRESET_CUSTOM else None
    if selected_preset_key == CAPITAL_PRESET_CUSTOM:
        st.session_state[BT_BACKFILL_CAPITAL_PRESET_SIGNATURE_KEY] = signature
        return None
    preset = get_capital_preset_by_key(selected_preset_key)
    if preset is None:
        st.session_state[BT_BACKFILL_CAPITAL_PRESET_SIGNATURE_KEY] = signature
        return None
    values = preset.values
    st.session_state["bt_backfill_selection_size"] = _to_int(
        values.get("selector_selection_size", st.session_state.get("bt_backfill_selection_size", 100)),
        100,
    )
    st.session_state[BT_BACKFILL_CAPITAL_PRESET_SIGNATURE_KEY] = signature
    return preset


def _tail_text(value: str, max_lines: int = TAIL_LINES) -> str:
    lines = value.splitlines()
    if len(lines) <= max_lines:
        return value
    return "\n".join(lines[-max_lines:])


def _file_cache_signature(path: Path) -> tuple[str, int, int] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    return (str(path), int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))), int(stat.st_size))


@st.cache_data(show_spinner=False)
def _read_cached_json_file(path_str: str, mtime_ns: int, size_bytes: int) -> dict[str, object] | None:
    del mtime_ns, size_bytes
    try:
        payload = json.loads(Path(path_str).read_text(encoding="utf-8"))
    except Exception:
        return None
    return cast(dict[str, object], payload) if isinstance(payload, dict) else None


@st.cache_data(show_spinner=False)
def _read_cached_csv_file(path_str: str, mtime_ns: int, size_bytes: int) -> pd.DataFrame:
    del mtime_ns, size_bytes
    return pd.read_csv(path_str)


def _should_preload_runtime_details(status: str) -> bool:
    return status in {"starting", "running"}


def _should_auto_refresh_runtime_center(*run_groups: list[dict[str, object]]) -> bool:
    return any(bool(group) for group in run_groups)


def _is_runtime_center_auto_update_enabled() -> bool:
    return bool(st.session_state.get(RUNTIME_CENTER_AUTO_UPDATE_KEY, True))


def _render_log_block(title: str, content: str, *, key: str, expanded: bool = False) -> None:
    tailed = _tail_text(content)
    suffix = ""
    if tailed != content:
        suffix = f" — affichage limite aux {TAIL_LINES} dernières lignes"
    with st.expander(f"{title}{suffix}", expanded=expanded):
        if tailed.strip():
            with st.container(height=320, key=f"{key}_container"):
                st.code(tailed, language="text")
        else:
            st.info("Aucun log disponible pour le moment.")


def _status_badge(status: str) -> str:
    return {
        "starting": "🟦 Démarrage",
        "running": "🟨 En cours",
        "completed": "🟢 Terminé",
        "failed": "🔴 Échec",
        "timeout": "🟠 Timeout",
        "stopped": "⏹️ Arrêté",
    }.get(status, status)


def _merge_runs() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    active_runs = list_active_backtesting_runs()
    merged: dict[str, dict[str, object]] = {str(run["run_id"]): run for run in load_backtesting_history()}
    for run in active_runs:
        merged[str(run["run_id"])] = run
    all_runs = sorted(
        merged.values(),
        key=lambda item: str(item.get("finished_at") or item.get("executed_at") or ""),
        reverse=True,
    )
    return active_runs, all_runs


def _prime_runtime_center_state(run_ids: list[str], labels: dict[str, str]) -> None:
    pending_selected = st.session_state.pop(PENDING_SELECTED_RUN_KEY, None)
    if isinstance(pending_selected, str) and pending_selected in labels:
        st.session_state[SELECTED_RUN_KEY] = pending_selected

    default_selected = st.session_state.get(SELECTED_RUN_KEY)
    if default_selected not in labels and run_ids:
        st.session_state[SELECTED_RUN_KEY] = run_ids[0]


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
    table_key: str = BACKTESTING_HISTORY_TABLE_KEY,
) -> str | None:
    if history_df.empty or "run_id" not in history_df.columns:
        return None
    row_index = _selected_dataframe_row_index(table_key)
    if row_index is None or row_index < 0 or row_index >= len(history_df):
        return None
    run_id = str(history_df.iloc[row_index].get("run_id") or "").strip()
    return run_id or None


def _parameter_reference_rows(kind: str) -> list[dict[str, str]]:
    if kind == "run":
        return [
            {"Paramètre": "start", "Explication": "Date de début du backtest (obligatoire).", "Défaut": "—"},
            {"Paramètre": "end", "Explication": "Date de fin, bornée par les données disponibles.", "Défaut": "aujourd'hui"},
            {"Paramètre": "equity", "Explication": "Capital initial simulé du portefeuille.", "Défaut": "100000"},
            {"Paramètre": "capital_preset_key", "Explication": "Preset capital utilisé pour lire `stock_scores_history` et aligner les contraintes compte/positions. Si absent, résolu depuis `equity`.", "Défaut": "auto depuis equity"},
            {"Paramètre": "tp", "Explication": "Take-profit en fraction (0.08 = 8%).", "Défaut": "0.08"},
            {"Paramètre": "ts", "Explication": "Trailing stop en fraction (0.05 = 5%).", "Défaut": "0.05"},
            {"Paramètre": "max_positions", "Explication": "Nombre maximal de positions simultanées.", "Défaut": "20"},
            {"Paramètre": "commission_bps", "Explication": "Commission explicite simulée par trade (bps).", "Défaut": "5.0 research / 15.0 pipeline"},
            {"Paramètre": "slippage_bps", "Explication": "Slippage fixe explicite simulé par trade (bps).", "Défaut": "5.0 research / 15.0 pipeline"},
            {"Paramètre": "fees", "Explication": "Champ legacy de compatibilité, remplacé par `commission_bps + slippage_bps`.", "Défaut": "None"},
            {
                "Paramètre": "account_type",
                "Explication": "Type de compte simulé : margin / cash.",
                "Défaut": "margin",
            },
            {
                "Paramètre": "swing_only",
                "Explication": "Interdit les sorties le jour même de l'entrée.",
                "Défaut": "False",
            },
            {
                "Paramètre": "allow_fractional_shares",
                "Explication": "Autorise les quantités fractionnaires côté sizing/replay backtest. Dans l'IHM, ce réglage est exposé via un switch persistant activé par défaut.",
                "Défaut": "False CLI / activé par défaut dans l'IHM",
            },
            {"Paramètre": "sentiment_lookback", "Explication": "Fenêtre historique sentiment passée à la CLI backtesting.", "Défaut": "365"},
            {"Paramètre": "no_save", "Explication": "Désactive l'écriture des artefacts PNG/CSV.", "Défaut": "False"},
            {"Paramètre": "ml_mode", "Explication": "auto/off/rebuild-missing pour la composante ML.", "Défaut": "auto"},
            {"Paramètre": "sentiment_mode", "Explication": "auto/off/rebuild-missing pour la composante sentiment.", "Défaut": "auto"},
            {"Paramètre": "engine_mode", "Explication": "research = tolérant/rapide, pipeline = strict PIT + diagnostics renforcés.", "Défaut": "research"},
            {"Paramètre": "scores_pit_mode", "Explication": "Résolution PIT des scores : `exact` = snapshots du jour uniquement, `asof_latest` = dernier snapshot `<= trade_date`.", "Défaut": "exact"},
            {"Paramètre": "macro_pit_mode", "Explication": "Politique PIT macro en backtest : `yaml_default` = suit `market_regimes.macro_pit_mode_backtest`, `asof_inclusive` = `<= trade_date`, `j_minus_1_strict` = strictement J-1.", "Défaut": "yaml_default"},
            {"Paramètre": "ml_pit_strategy", "Explication": "Stratégie PIT ML explicite : auto / use-persisted / rebuild-missing / walk-forward-train-then-predict.", "Défaut": "auto"},
            {"Paramètre": "phase2_mode", "Explication": "off = backtest standard, risk = bridge risk_management, risk_execution = risk + intents/fills d'exécution simulés.", "Défaut": "off"},
            {"Paramètre": "phase3_mode", "Explication": "off = comportement Phase 2, execution_replay = réinjecte chronologiquement les quantités exécutées simulées dans le moteur de backtest.", "Défaut": "off"},
            {"Paramètre": "phase4_mode", "Explication": "off = comportement Phase 3, protection_replay = rejoue les protections TP/stop/trailing issues des child intents d'exécution.", "Défaut": "off"},
            {"Paramètre": "phase5_mode", "Explication": "off = comportement Phase 4, watcher_replay = rejoue les transitions du watcher de protection (trigger -> promotion trailing) dans le moteur.", "Défaut": "off"},
            {"Paramètre": "phase7_mode", "Explication": "off = comportement Phase 5, exit_lifecycle_replay = rejoue l'issue terminale des child orders et l'annulation OCO du sibling.", "Défaut": "off"},
            {"Paramètre": "allow_neutral_fallback_on_missing_macro_data", "Explication": "Si vrai, le backtest continue quand la macro requise est indisponible et marque la séance en `data_quality=missing`. Sinon, il échoue explicitement.", "Défaut": "False"},
            {"Paramètre": "fidelity_baseline_id", "Explication": "Identifiant optionnel de baseline fidélité promue à comparer au run courant (Sprint 6).", "Défaut": "None"},
            {"Paramètre": "fidelity_baseline_catalog", "Explication": "Chemin optionnel vers le catalogue JSON des baselines fidélité. Convention stable recommandée : `config/fidelity_baseline_catalog.json` pointant vers `artifacts/fidelity_baselines/<baseline_id>/...`.", "Défaut": "None"},
            {"Paramètre": "artifacts_dir", "Explication": "Dossier des artefacts modèles utilisés pour rebuild-missing.", "Défaut": "artifacts/models"},
            {"Paramètre": "score_column", "Explication": "Colonne de score privilégiée pour le replay : auto / walk-forward / sentiment / final.", "Défaut": "auto"},
            {"Paramètre": "walk_forward_artifacts_dir", "Explication": "Répertoire racine optionnel des artefacts de calibration walk-forward à appliquer au run standard.", "Défaut": "None"},
            # Phase A (refactor) — reproductibilité.
            {"Paramètre": "risk_free_rate", "Explication": "Taux sans risque annualisé déduit avant Sharpe/Sortino (Phase A.6).", "Défaut": "0.0"},
            {"Paramètre": "seed", "Explication": "Seed reproductibilité consigné dans report.json[run_metadata] (Phase A.4).", "Défaut": "None"},
            # Phase B (refactor) — micro-structure.
            {"Paramètre": "slippage_model", "Explication": "fixed/linear/sqrt — slippage volume-aware additionnel (Phase B.1).", "Défaut": "fixed"},
            {"Paramètre": "slippage_base_bps", "Explication": "Composante fixe du slippage volume-aware (bps).", "Défaut": "0.0"},
            {"Paramètre": "slippage_impact_coef", "Explication": "Coefficient d'impact appliqué à size/ADV (bps).", "Défaut": "0.0"},
            {"Paramètre": "initial_stop_pct", "Explication": "Stop-loss initial dur en fraction (Phase B.2).", "Défaut": "0.0"},
            {"Paramètre": "max_entry_gap_pct", "Explication": "Skip entrée si gap d'open > seuil (Phase B.3).", "Défaut": "0.0"},
            {"Paramètre": "intrabar_priority", "Explication": "Politique TP vs TS intra-bar (Phase B.4).", "Défaut": "conservative"},
            # Phase C (refactor) — risk overlays.
            {"Paramètre": "sizing_mode", "Explication": "equal_weight | conviction_weighted (Phase C.1).", "Défaut": "equal_weight"},
            {"Paramètre": "regime_filter", "Explication": "Active le filtre régime SMA200 sur le benchmark (Phase C.3).", "Défaut": "False"},
            {"Paramètre": "max_sector_exposure_pct", "Explication": "Cap d'exposition par secteur en fraction (Phase C.4).", "Défaut": "0.0"},
            {"Paramètre": "max_portfolio_dd_pct", "Explication": "Drawdown max avant coupe-circuit nouvelles entrées (Phase C.5).", "Défaut": "0.0"},
            {"Paramètre": "target_annual_vol", "Explication": "Cible vol annualisée portefeuille (Phase C.2).", "Défaut": "None"},
        ]
    if kind == "diagnose-screener":
        return [
            {"Paramètre": "start", "Explication": "Date de début de l'analyse PIT screener.", "Défaut": "—"},
            {"Paramètre": "end", "Explication": "Date de fin de l'analyse.", "Défaut": "aujourd'hui"},
            {"Paramètre": "limit_days", "Explication": "Limiter à N séances pour une validation incrémentale.", "Défaut": "None"},
            {"Paramètre": "mode", "Explication": "Balayage `oat` (one-at-a-time) ou `grid`.", "Défaut": "oat"},
            {"Paramètre": "chunk_size", "Explication": "Taille des chunks symboles pour screener/scanner.", "Défaut": "500"},
            {"Paramètre": "selection_size", "Explication": "Nombre final de candidats selector par séance.", "Défaut": "100"},
            {"Paramètre": "max_positions", "Explication": "Nombre maximum de positions du portefeuille cible analysé.", "Défaut": "20"},
            {"Paramètre": "screener_workers", "Explication": "Nombre de workers ProcessPool pour le screener PIT.", "Défaut": "auto"},
            {"Paramètre": "max_scenarios", "Explication": "Garde-fou sur le nombre total de scénarios en mode grid.", "Défaut": "64"},
            {"Paramètre": "rs_values", "Explication": "Liste CSV des seuils de relative strength testés.", "Défaut": "100,102,105"},
            {"Paramètre": "range_lookback_values", "Explication": "Liste CSV des lookbacks historical range testés.", "Défaut": "252,504,756"},
            {"Paramètre": "historical_range_score_values", "Explication": "Liste CSV des seuils historical range score testés.", "Défaut": "65,70,75"},
            {"Paramètre": "liquidity_threshold_values", "Explication": "Liste CSV des seuils de liquidité testés.", "Défaut": "5000000,10000000,20000000"},
            {"Paramètre": "output_dir", "Explication": "Répertoire cible des artefacts diagnostics/recommandations screener.", "Défaut": "artifacts/screener_diagnostics"},
        ]
    if kind == "recommend-screener":
        return [
            {"Paramètre": "input_dir", "Explication": "Répertoire source contenant `summary_metrics.csv` et éventuellement `daily_metrics.csv`.", "Défaut": "artifacts/screener_diagnostics"},
            {"Paramètre": "summary_csv", "Explication": "Chemin explicite vers un `summary_metrics.csv`.", "Défaut": "auto depuis input_dir"},
            {"Paramètre": "daily_csv", "Explication": "Chemin explicite vers un `daily_metrics.csv` pour enrichir l'analyse.", "Défaut": "auto depuis input_dir"},
            {"Paramètre": "output_dir", "Explication": "Répertoire cible des artefacts de recommandation.", "Défaut": "même dossier que summary_metrics.csv"},
            {"Paramètre": "baseline_name", "Explication": "Nom explicite du scénario baseline si nécessaire.", "Défaut": "auto"},
            {"Paramètre": "target_horizon", "Explication": "Horizon forward prioritaire utilisé pour le compromis.", "Défaut": "20"},
        ]
    return [
        {"Paramètre": "start", "Explication": "Date de départ du backfill PIT (obligatoire).", "Défaut": "—"},
        {"Paramètre": "end", "Explication": "Date de fin explicite. Si vide, le service résout la borne utile.", "Défaut": "auto"},
        {"Paramètre": "capital", "Explication": "Capital de référence pour résoudre automatiquement un preset backfill PIT.", "Défaut": "100000"},
        {"Paramètre": "capital_preset_key", "Explication": "Preset explicite à utiliser pour reconstruire `stock_scores_history`. Si absent, résolu depuis `capital`.", "Défaut": "auto depuis capital"},
        {"Paramètre": "overwrite_existing", "Explication": "Recalcule aussi les dates déjà historisées.", "Défaut": "False"},
        {"Paramètre": "limit_days", "Explication": "Limite à N séances pour un test progressif.", "Défaut": "None"},
        {"Paramètre": "chunk_size", "Explication": "Taille des lots symboles pour screener/scanner.", "Défaut": "500"},
        {"Paramètre": "selection_size", "Explication": "Nombre final de candidats retenus par séance.", "Défaut": "100"},
        {"Paramètre": "screener_workers", "Explication": "Nombre de workers ProcessPool pour le screener PIT.", "Défaut": "auto"},
    ]


def _render_reference_table(kind: str) -> None:
    with st.expander("📘 Référence complète des paramètres", expanded=False):
        st.dataframe(pd.DataFrame(_parameter_reference_rows(kind)), use_container_width=True, hide_index=True)


def _default_fidelity_baseline_catalog_path() -> Path:
    return PROJECT_ROOT / "config" / "fidelity_baseline_catalog.json"


def _build_fidelity_baseline_catalog_rows(catalog_path: Path | None = None) -> pd.DataFrame:
    resolved_catalog_path = catalog_path or _default_fidelity_baseline_catalog_path()
    signature = _file_cache_signature(resolved_catalog_path)
    if signature is None:
        return pd.DataFrame()
    payload = _read_cached_json_file(*signature)
    if payload is None:
        return pd.DataFrame()
    baselines = payload.get("baselines", []) if isinstance(payload, dict) else []
    if not isinstance(baselines, list) or not baselines:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for entry in baselines:
        if not isinstance(entry, dict):
            continue
        requested_window = entry.get("requested_window", {})
        phase_modes = entry.get("phase_modes", {})
        promotion_manifest_path = entry.get("promotion_manifest_path")
        rows.append(
            {
                "Baseline": _coerce_metric_text(entry.get("baseline_id")),
                "Libellé": _coerce_metric_text(entry.get("label")),
                "Fenêtre": "{} → {}".format(
                    _coerce_metric_text(requested_window.get("start_date") if isinstance(requested_window, dict) else None),
                    _coerce_metric_text(requested_window.get("end_date") if isinstance(requested_window, dict) else None),
                ),
                "Phases": ", ".join(
                    f"{key}={value}"
                    for key, value in sorted(phase_modes.items())
                    if str(value or "").strip()
                ) if isinstance(phase_modes, dict) and phase_modes else "—",
                "Snapshot": _coerce_metric_text(entry.get("snapshot_path")),
                "Manifest": _coerce_metric_text(promotion_manifest_path),
            }
        )
    return pd.DataFrame(rows)


def _build_pipeline_pit_status_message(diagnostic: dict[str, object]) -> tuple[str, str]:
    status = str(diagnostic.get("status", "unknown") or "unknown")
    preset_key = str(diagnostic.get("capital_preset_key", "") or "auto")
    start = str(diagnostic.get("start", "?") or "?")
    end = str(diagnostic.get("end", "?") or "?")
    rows = _to_int(diagnostic.get("rows"))
    snapshot_days = _to_int(diagnostic.get("snapshot_days"))
    first_snapshot = str(diagnostic.get("first_snapshot_date", "") or "—")
    last_snapshot = str(diagnostic.get("last_snapshot_date", "") or "—")
    filtered_on_preset = bool(diagnostic.get("capital_preset_filtered", False))

    if status == "available":
        return (
            "success",
            "Couverture PIT détectée pour `stock_scores_history` sur [{start} → {end}]"
            " avec preset `{preset}`{preset_note} : {rows} ligne(s), {days} séance(s), première={first}, dernière={last}.".format(
                start=start,
                end=end,
                preset=preset_key,
                preset_note=" (filtrage actif)" if filtered_on_preset else "",
                rows=rows,
                days=snapshot_days,
                first=first_snapshot,
                last=last_snapshot,
            ),
        )
    if status == "missing":
        return (
            "error",
            "Aucun snapshot PIT candidat n'a été détecté dans `stock_scores_history` sur [{start} → {end}]"
            " pour le preset effectif `{preset}`{preset_note}. En mode `pipeline`, ce run échouera. "
            "Action recommandée : lancer l'onglet `Backfill scores history` avec la même plage et le même preset, "
            "ou repasser le backtest en mode `research`.".format(
                start=start,
                end=end,
                preset=preset_key,
                preset_note=" (filtrage actif)" if filtered_on_preset else "",
            ),
        )
    if status == "invalid_input":
        return (
            "warning",
            "Diagnostic PIT non exécutable tant que les dates de début/fin ne sont pas valides.",
        )
    return (
        "warning",
        "Diagnostic PIT indisponible : {}".format(str(diagnostic.get("reason", "erreur inconnue"))),
    )


def _build_ml_coverage_status_message(diagnostic: dict[str, object]) -> tuple[str, str]:
    status = str(diagnostic.get("status", "unknown") or "unknown")
    start = str(diagnostic.get("start", "?") or "?")
    end = str(diagnostic.get("end", "?") or "?")
    preset_key = str(diagnostic.get("capital_preset_key", "") or "auto")
    coverage_pct = _to_float(diagnostic.get("coverage_pct"))
    expected_pairs = _to_int(diagnostic.get("expected_candidate_symbol_dates"))
    covered_pairs = _to_int(diagnostic.get("covered_prediction_symbol_dates"))
    missing_pairs = _to_int(diagnostic.get("missing_prediction_symbol_dates"))
    effective_strategy = str(diagnostic.get("effective_strategy", "auto") or "auto")
    filtered_on_preset = bool(diagnostic.get("capital_preset_filtered", False))

    if status == "complete":
        return (
            "success",
            "Couverture ML PIT complète sur [{start} → {end}] avec preset `{preset}`{preset_note} : "
            "{covered}/{expected} paire(s) symbole×date couvertes ({coverage:.1f}%). "
            "La stratégie effective `{strategy}` peut partir en mode rapide sans dégradation ML.".format(
                start=start,
                end=end,
                preset=preset_key,
                preset_note=" (filtrage actif)" if filtered_on_preset else "",
                covered=covered_pairs,
                expected=expected_pairs,
                coverage=coverage_pct,
                strategy=effective_strategy,
            ),
        )
    if status == "partial":
        return (
            "warning",
            "Couverture ML PIT partielle sur [{start} → {end}] avec preset `{preset}`{preset_note} : "
            "{covered}/{expected} paire(s) couvertes ({coverage:.1f}%), {missing} manquante(s). "
            "Le mode rapide laissera ces trous sans ML ; `rebuild-missing` tentera de les reconstruire.".format(
                start=start,
                end=end,
                preset=preset_key,
                preset_note=" (filtrage actif)" if filtered_on_preset else "",
                covered=covered_pairs,
                expected=expected_pairs,
                coverage=coverage_pct,
                missing=missing_pairs,
            ),
        )
    if status == "missing":
        return (
            "error",
            "Aucune couverture ML PIT persistée n'a été trouvée sur [{start} → {end}] avec preset `{preset}`{preset_note}. "
            "Le mode rapide utilisera 0/{expected} paire(s) et laissera tout le run sans ML ; `rebuild-missing` est recommandé si les artefacts existent.".format(
                start=start,
                end=end,
                preset=preset_key,
                preset_note=" (filtrage actif)" if filtered_on_preset else "",
                expected=expected_pairs,
            ),
        )
    if status == "missing_expected_history":
        return (
            "error",
            "Préflight ML inexploitable : aucun candidat PIT attendu n'a été trouvé dans `stock_scores_history` sur la plage demandée.",
        )
    if status == "disabled":
        return (
            "info",
            str(diagnostic.get("reason", "Mode ML désactivé.")),
        )
    if status == "invalid_input":
        return (
            "warning",
            "Préflight ML non exécutable tant que les dates de début/fin ne sont pas valides.",
        )
    return (
        "warning",
        "Préflight ML indisponible : {}".format(str(diagnostic.get("reason", "erreur inconnue"))),
    )


def _render_pipeline_pit_hint(
    *,
    engine_mode: str,
    start: str,
    end: str | None,
    selected_run_preset_key: str,
    auto_run_preset_key: str,
) -> None:
    if engine_mode != "pipeline":
        return
    effective_preset_key = auto_run_preset_key if selected_run_preset_key == CAPITAL_PRESET_CUSTOM else selected_run_preset_key
    diagnostic = get_backtesting_pit_history_diagnostic(
        start=start,
        end=end,
        capital_preset_key=effective_preset_key,
    )
    level, message = _build_pipeline_pit_status_message(diagnostic)
    if level == "success":
        st.success(message)
    elif level == "error":
        st.error(message)
    else:
        st.warning(message)


def _render_ml_coverage_preflight(
    *,
    engine_mode: str,
    ml_mode: str,
    ml_pit_strategy: str,
    start: str,
    end: str | None,
    selected_run_preset_key: str,
    auto_run_preset_key: str,
) -> None:
    if engine_mode != "pipeline":
        st.info("Préflight couverture ML PIT disponible pour `engine-mode pipeline` uniquement.")
        return

    effective_preset_key = auto_run_preset_key if selected_run_preset_key == CAPITAL_PRESET_CUSTOM else selected_run_preset_key
    diagnostic = get_backtesting_ml_coverage_diagnostic(
        start=start,
        end=end,
        capital_preset_key=effective_preset_key,
        engine_mode=engine_mode,
        ml_mode=ml_mode,
        ml_pit_strategy=ml_pit_strategy,
    )
    level, message = _build_ml_coverage_status_message(diagnostic)
    if level == "success":
        st.success(message)
    elif level == "error":
        st.error(message)
    elif level == "info":
        st.info(message)
    else:
        st.warning(message)

    if str(diagnostic.get("status", "")) not in {"complete", "partial", "missing"}:
        return

    metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
    with metric_col1:
        st.metric("Attendus", _to_int(diagnostic.get("expected_candidate_symbol_dates")))
    with metric_col2:
        st.metric("Déjà couverts", _to_int(diagnostic.get("covered_prediction_symbol_dates")))
    with metric_col3:
        st.metric("Taux de couverture", f"{_to_float(diagnostic.get('coverage_pct')):.1f}%")
    with metric_col4:
        st.metric("Manquants", _to_int(diagnostic.get("missing_prediction_symbol_dates")))
    with metric_col5:
        st.metric("Séances manquantes", _to_int(diagnostic.get("missing_snapshot_days")))

    st.caption(
        "Mode rapide estimé : {}".format(
            str(((diagnostic.get("fast_mode_estimate") or {}) if isinstance(diagnostic.get("fast_mode_estimate"), dict) else {}).get("summary") or "—")
        )
    )
    st.caption(
        "Estimation `rebuild-missing` : {}".format(
            str(((diagnostic.get("rebuild_missing_estimate") or {}) if isinstance(diagnostic.get("rebuild_missing_estimate"), dict) else {}).get("summary") or "—")
        )
    )

    missing_days_sample = diagnostic.get("missing_days_sample")
    if isinstance(missing_days_sample, list) and missing_days_sample:
        with st.expander("📆 Jours incomplets (échantillon)", expanded=False):
            st.dataframe(pd.DataFrame(missing_days_sample), use_container_width=True, hide_index=True)

    missing_rows_sample = diagnostic.get("missing_rows_sample")
    if isinstance(missing_rows_sample, list) and missing_rows_sample:
        with st.expander("🧩 Symboles / jours manquants (échantillon)", expanded=False):
            st.dataframe(pd.DataFrame(missing_rows_sample), use_container_width=True, hide_index=True)


def _build_overlay_options(
    *,
    engine_mode: str,
    selected_run_preset_key: str,
    auto_run_preset_key: str,
    use_live_protection_logic: bool,
) -> dict[str, Any]:
    """Construit le sous-dict d'options pour les surcouches micro-structure / risk overlay.

    Affiche un expander unique avec deux blocs (Phase B et Phase C). Toutes les
    valeurs par défaut sont **neutres** : le backtest produit alors exactement
    les mêmes résultats que sans la surcouche.
    """
    pipeline_defaults = _resolve_pipeline_backtest_defaults(
        engine_mode=engine_mode,
        selected_run_preset_key=selected_run_preset_key,
        auto_run_preset_key=auto_run_preset_key,
    )
    max_portfolio_dd_default = (
        float(st.session_state["bt_run_max_portfolio_dd_pct"])
        if "bt_run_max_portfolio_dd_pct" in st.session_state
        else float(pipeline_defaults.get("max_portfolio_dd_pct") or 0.0)
    )
    max_sector_exposure_default = (
        float(st.session_state["bt_run_max_sector_exposure_pct"])
        if "bt_run_max_sector_exposure_pct" in st.session_state
        else float(pipeline_defaults.get("max_sector_exposure_pct") or 0.0)
    )
    max_entry_gap_default = (
        float(st.session_state["bt_run_max_entry_gap_pct"])
        if "bt_run_max_entry_gap_pct" in st.session_state
        else float(pipeline_defaults.get("max_entry_gap_pct") or 0.0)
    )
    dd_recovery_default = (
        float(st.session_state["bt_run_dd_recovery_pct"])
        if "bt_run_dd_recovery_pct" in st.session_state
        else float(pipeline_defaults.get("dd_recovery_pct") or 0.92)
    )
    target_annual_vol_default = pipeline_defaults.get("target_annual_vol")
    min_ml_coverage_ratio_default = pipeline_defaults.get("min_ml_coverage_ratio")
    target_annual_vol_default_raw = (
        cast(str, st.session_state.get("bt_run_target_annual_vol_raw", ""))
        if "bt_run_target_annual_vol_raw" in st.session_state
        else (
            f"{target_annual_vol_default:g}"
            if target_annual_vol_default is not None
            else ""
        )
    )
    min_ml_coverage_ratio_default_raw = (
        cast(str, st.session_state.get("bt_run_min_ml_coverage_ratio_raw", ""))
        if "bt_run_min_ml_coverage_ratio_raw" in st.session_state
        else (
            f"{min_ml_coverage_ratio_default:g}"
            if min_ml_coverage_ratio_default is not None
            else ""
        )
    )

    with st.expander("🧪 Reproductibilité & surcouches research-grade (Phase B/C)", expanded=False):
        st.caption(
            "Toutes ces options sont **opt-in** : laissées à zéro/désactivées, le backtest "
            "produit le même résultat qu'avant. Voir `refactor/backtesting/audit_plan_resume.md`."
        )

        # --- Reproductibilité (Phase A) ---
        repro_col1, repro_col2 = st.columns(2)
        with repro_col1:
            risk_free_rate = st.number_input(
                "Risk-free rate annualisé (Sharpe/Sortino)",
                min_value=0.0,
                max_value=0.20,
                value=float(st.session_state.get("bt_run_risk_free_rate", 0.0)),
                step=0.005,
                format="%.4f",
                key="bt_run_risk_free_rate",
                help="0.04 = 4% — déduit des returns avant Sharpe/Sortino.",
            )
        with repro_col2:
            seed_raw = st.text_input(
                "Seed reproductibilité (optionnel)",
                value=cast(str, st.session_state.get("bt_run_seed_raw", "")),
                key="bt_run_seed_raw",
                help="Entier consigné dans report.json[run_metadata]. Utilisé par les sorties intra-bar 'random'.",
            )

        st.markdown("**Phase B — Micro-structure**")
        micro_col1, micro_col2, micro_col3 = st.columns(3)
        with micro_col1:
            slippage_model = cast(
                str,
                st.selectbox(
                    "Modèle slippage volume-aware",
                    options=["fixed", "linear", "sqrt"],
                    index=["fixed", "linear", "sqrt"].index(
                        cast(str, st.session_state.get("bt_run_slippage_model", "fixed"))
                        if st.session_state.get("bt_run_slippage_model", "fixed") in {"fixed", "linear", "sqrt"}
                        else "fixed"
                    ),
                    key="bt_run_slippage_model",
                    help="`fixed` (défaut, neutre) ; `linear` = base + impact*(size/ADV) ; `sqrt` = Almgren-Chriss.",
                ),
            )
        with micro_col2:
            slippage_base_bps = st.number_input(
                "Slippage base (bps)",
                min_value=0.0,
                max_value=500.0,
                value=float(st.session_state.get("bt_run_slippage_base_bps", 0.0)),
                step=0.5,
                key="bt_run_slippage_base_bps",
            )
        with micro_col3:
            slippage_impact_coef = st.number_input(
                "Slippage impact coef (bps)",
                min_value=0.0,
                max_value=2000.0,
                value=float(st.session_state.get("bt_run_slippage_impact_coef", 0.0)),
                step=1.0,
                key="bt_run_slippage_impact_coef",
            )

        micro_col4, micro_col5, micro_col6 = st.columns(3)
        with micro_col4:
            if use_live_protection_logic:
                initial_stop_pct = 0.0
                st.caption(
                    "Stop-loss initial dur désactivé : en mode live-like, le SL initial est calculé depuis `stop_price_initial` / `risk_per_share`."
                )
            else:
                initial_stop_pct = st.number_input(
                    "Stop-loss initial dur (fraction)",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(st.session_state.get("bt_run_initial_stop_pct", 0.0)),
                    step=0.005,
                    format="%.4f",
                    key="bt_run_initial_stop_pct",
                    help="Ex 0.07 = 7%. 0 = désactivé.",
                )
        with micro_col5:
            max_entry_gap_pct = st.number_input(
                "Max gap d'ouverture (fraction)",
                min_value=0.0,
                max_value=1.0,
                value=max_entry_gap_default,
                step=0.005,
                format="%.4f",
                key="bt_run_max_entry_gap_pct",
                help="Ex 0.05 = annule l'entrée si l'open gap > 5%. 0 = désactivé.",
            )
        with micro_col6:
            intrabar_priority = cast(
                str,
                st.selectbox(
                    "Priorité intra-bar TP/TS",
                    options=["conservative", "tp_first", "ts_first", "random"],
                    index=["conservative", "tp_first", "ts_first", "random"].index(
                        cast(str, st.session_state.get("bt_run_intrabar_priority", "conservative"))
                        if st.session_state.get("bt_run_intrabar_priority", "conservative")
                        in {"conservative", "tp_first", "ts_first", "random"}
                        else "conservative"
                    ),
                    key="bt_run_intrabar_priority",
                    help="`conservative` = TS prioritaire (legacy). `random` requiert un seed.",
                ),
            )

        st.markdown("**Phase C — Risk overlays**")
        risk_col1, risk_col2, risk_col3 = st.columns(3)
        with risk_col1:
            sizing_mode = cast(
                str,
                st.selectbox(
                    "Mode sizing",
                    options=["equal_weight", "conviction_weighted"],
                    index=["equal_weight", "conviction_weighted"].index(
                        cast(str, st.session_state.get("bt_run_sizing_mode", "equal_weight"))
                        if st.session_state.get("bt_run_sizing_mode", "equal_weight")
                        in {"equal_weight", "conviction_weighted"}
                        else "equal_weight"
                    ),
                    key="bt_run_sizing_mode",
                ),
            )
        with risk_col2:
            sizing_min_weight_pct = st.number_input(
                "Sizing min weight",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state.get("bt_run_sizing_min_weight_pct", 0.005)),
                step=0.005,
                format="%.4f",
                key="bt_run_sizing_min_weight_pct",
            )
        with risk_col3:
            sizing_max_weight_pct = st.number_input(
                "Sizing max weight",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state.get("bt_run_sizing_max_weight_pct", 0.20)),
                step=0.01,
                format="%.4f",
                key="bt_run_sizing_max_weight_pct",
            )

        risk_col4, risk_col5, risk_col6 = st.columns(3)
        with risk_col4:
            regime_filter = st.checkbox(
                "Active le filtre régime SMA200",
                value=bool(st.session_state.get("bt_run_regime_filter", False)),
                key="bt_run_regime_filter",
                help="Bloque les nouvelles entrées si benchmark < SMA - threshold.",
            )
        with risk_col5:
            regime_sma_window = st.number_input(
                "SMA window",
                min_value=20,
                max_value=500,
                value=int(st.session_state.get("bt_run_regime_sma_window", 200)),
                step=10,
                key="bt_run_regime_sma_window",
            )
        with risk_col6:
            regime_bear_threshold = st.number_input(
                "Bear threshold",
                min_value=-0.50,
                max_value=0.10,
                value=float(st.session_state.get("bt_run_regime_bear_threshold", -0.02)),
                step=0.005,
                format="%.4f",
                key="bt_run_regime_bear_threshold",
            )

        risk_col7, risk_col8, risk_col9, risk_col10 = st.columns(4)
        with risk_col7:
            max_sector_exposure_pct = st.number_input(
                "Max exposure secteur",
                min_value=0.0,
                max_value=1.0,
                value=max_sector_exposure_default,
                step=0.05,
                format="%.4f",
                key="bt_run_max_sector_exposure_pct",
                help="Ex 0.30 = 30%. 0 = désactivé.",
            )
        with risk_col8:
            max_portfolio_dd_pct = st.number_input(
                "Max DD portefeuille",
                min_value=0.0,
                max_value=1.0,
                value=max_portfolio_dd_default,
                step=0.01,
                format="%.4f",
                key="bt_run_max_portfolio_dd_pct",
                help="Ex 0.20 = coupe les nouvelles entrées si DD > 20%. 0 = désactivé.",
            )
        with risk_col9:
            dd_recovery_pct = st.number_input(
                "DD recovery",
                min_value=0.0,
                max_value=1.0,
                value=dd_recovery_default,
                step=0.01,
                format="%.4f",
                key="bt_run_dd_recovery_pct",
            )
        with risk_col10:
            target_annual_vol_raw = st.text_input(
                "Target annual vol (optionnel)",
                value=target_annual_vol_default_raw,
                key="bt_run_target_annual_vol_raw",
                help="Ex 0.15 = cible 15% vol portefeuille. Vide = désactivé.",
            )

        risk_col11, risk_col12 = st.columns([1.5, 2.5])
        with risk_col11:
            min_ml_coverage_ratio_raw = st.text_input(
                "Min ML coverage ratio (pipeline)",
                value=min_ml_coverage_ratio_default_raw,
                key="bt_run_min_ml_coverage_ratio_raw",
                help="Ex 0.80 = bloque le run pipeline si la couverture ML passe sous 80%. Vide = désactivé.",
            )
        with risk_col12:
            if engine_mode == "pipeline":
                st.caption(
                    "Le preset capital préremplit ici les garde-fous pipeline : cap sectoriel, gap filter d'entrée, drawdown breaker, `vol targeting` et gating ML. "
                    "Vous pouvez modifier directement ces valeurs avant le lancement."
                )
            else:
                st.caption(
                    "Ces garde-fous sont surtout utiles pour les runs `pipeline`. En `research`, laissez-les à zéro / vides pour rester neutre."
                )

    seed_value: int | None = None
    if seed_raw.strip():
        try:
            seed_value = int(seed_raw.strip())
        except ValueError:
            st.warning(f"Seed invalide ignoré : `{seed_raw}`.")

    target_annual_vol_value = _parse_optional_float(str(target_annual_vol_raw or ""), label="Target annual vol")
    min_ml_coverage_ratio_value = _parse_optional_float(
        str(min_ml_coverage_ratio_raw or ""),
        label="Min ML coverage ratio (pipeline)",
    )

    return {
        "risk_free_rate": float(risk_free_rate),
        "seed": seed_value,
        "slippage_model": cast(Any, slippage_model),
        "slippage_base_bps": float(slippage_base_bps),
        "slippage_impact_coef": float(slippage_impact_coef),
        "initial_stop_pct": float(initial_stop_pct),
        "max_entry_gap_pct": float(max_entry_gap_pct),
        "intrabar_priority": cast(Any, intrabar_priority),
        "sizing_mode": cast(Any, sizing_mode),
        "sizing_min_weight_pct": float(sizing_min_weight_pct),
        "sizing_max_weight_pct": float(sizing_max_weight_pct),
        "regime_filter": bool(regime_filter),
        "regime_sma_window": int(regime_sma_window),
        "regime_bear_threshold": float(regime_bear_threshold),
        "max_sector_exposure_pct": float(max_sector_exposure_pct),
        "max_portfolio_dd_pct": float(max_portfolio_dd_pct),
        "dd_recovery_pct": float(dd_recovery_pct),
        "target_annual_vol": target_annual_vol_value,
        "min_ml_coverage_ratio": min_ml_coverage_ratio_value,
    }


def _build_run_options() -> BacktestRunOptions:
    st.subheader("▶️ Lancer un backtest")
    st.caption(
        "Le backtest exécute `python -m backtesting run ...` en arrière-plan. "
        "Tous les paramètres CLI sont exposés ci-dessous et les logs sont visibles plus bas dans la page."
    )
    fractional_prefs = load_persisted_fractional_trading_preferences()
    if BT_RUN_ALLOW_FRACTIONAL_SHARES_KEY not in st.session_state:
        st.session_state[BT_RUN_ALLOW_FRACTIONAL_SHARES_KEY] = bool(fractional_prefs.backtest_enabled)
    _ensure_run_configuration_preset_session_key()
    preset_col1, preset_col2 = st.columns([1.5, 3.5])
    with preset_col1:
        selected_run_configuration_preset = cast(
            str,
            st.selectbox(
                "Preset de configuration",
                options=list(RUN_CONFIGURATION_PRESETS),
                format_func=_format_run_configuration_preset_label,
                key=BT_RUN_CONFIGURATION_PRESET_KEY,
                help=(
                    "Raccourci IHM pour préremplir rapidement les flags `run`. "
                    "Le preset n'exécute rien tant que vous ne lancez pas explicitement le backtest."
                ),
            ),
        )
    with preset_col2:
        selected_preset = _get_run_configuration_preset(selected_run_configuration_preset)
        if selected_preset is not None:
            st.caption(str(selected_preset.get("description", "")))
        if st.button("Préremplir les options du backtest", key="bt_apply_run_configuration_preset", use_container_width=True):
            _apply_run_configuration_preset(selected_run_configuration_preset)
    if selected_run_configuration_preset in {"pipeline_live_like", "production_parity"}:
        st.info(
            "Ce preset correspond à un replay `pipeline` orienté parité avec le live/paper. "
            "Il ne fait pas partie de `backfill-scores-history`. Pour qu'il fonctionne en mode `pipeline`, "
            "il faut déjà disposer d'un historique PIT valide dans `stock_scores_history` — à reconstruire via l'onglet `Backfill scores history` si nécessaire."
        )
    _render_reference_table("run")

    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.text_input(
            "Date de début",
            value=cast(str, st.session_state.get("bt_run_start", "2020-01-01")),
            key="bt_run_start",
            help="Format YYYY-MM-DD. C'est la borne basse du backtest.",
        )
    with col2:
        end = st.text_input(
            "Date de fin",
            value=cast(str, st.session_state.get("bt_run_end", "2025-12-31")),
            key="bt_run_end",
            help="Format YYYY-MM-DD. Laissez une date future si vous voulez aller jusqu'au dernier bar dispo.",
        )
    with col3:
        equity = st.number_input(
            "Capital initial ($)",
            min_value=1_000.0,
            value=float(st.session_state.get("bt_run_equity", 2_000.0)),
            step=1_000.0,
            key="bt_run_equity",
            help="Capital de départ simulé du portefeuille.",
        )

    run_preset_options = _get_capital_preset_options()
    _ensure_capital_preset_session_key(BT_RUN_CAPITAL_PRESET_KEY, float(equity))
    run_preset_col1, run_preset_col2 = st.columns([1.4, 2.6])
    with run_preset_col1:
        selected_run_preset_key = cast(
            str,
            st.selectbox(
                "Preset capital PIT",
                options=run_preset_options,
                format_func=_format_capital_preset_label,
                key=BT_RUN_CAPITAL_PRESET_KEY,
                help=(
                    "`custom/auto` = le backend résout le preset à partir du capital saisi. "
                    "Sinon, le preset explicite est transmis au backtest et préremplit les contraintes compte/positions."
                ),
            ),
        )
    with run_preset_col2:
        auto_run_preset_key = _resolve_default_capital_preset_key(float(equity))
        if selected_run_preset_key == CAPITAL_PRESET_CUSTOM:
            st.caption(
                f"Résolution automatique active : capital `{float(equity):,.0f}$` → preset `{_format_capital_preset_label(auto_run_preset_key)}`."
            )
        else:
            _apply_run_capital_preset(selected_run_preset_key, float(equity))
            st.caption(
                f"Preset explicite transmis au backtest : `{_format_capital_preset_label(selected_run_preset_key)}`."
            )

    allow_fractional_shares = st.toggle(
        "Autoriser les quantités fractionnaires en backtest",
        value=bool(st.session_state.get(BT_RUN_ALLOW_FRACTIONAL_SHARES_KEY, fractional_prefs.backtest_enabled)),
        key=BT_RUN_ALLOW_FRACTIONAL_SHARES_KEY,
        help=(
            "Active `--allow-fractional-shares` pour le replay backtest. "
            "Valeur persistée côté serveur dans `artifacts/ihm_preferences/fractional_trading.json`."
        ),
    )
    if bool(allow_fractional_shares) != bool(fractional_prefs.backtest_enabled):
        save_persisted_fractional_trading_preferences(
            FractionalTradingPreferences(
                backtest_enabled=bool(allow_fractional_shares),
                pipeline_live_enabled=bool(fractional_prefs.pipeline_live_enabled),
            )
        )
    if allow_fractional_shares:
        st.success(
            "🧮 Mode fractionnaire backtest activé — l'IHM transmettra `--allow-fractional-shares` et le simulateur pourra conserver des tailles non entières."
        )
    else:
        st.warning(
            "🧮 Mode fractionnaire backtest désactivé — les tailles seront traitées comme entières pour les runs lancés depuis l'IHM."
        )

    current_engine_mode = str(st.session_state.get("bt_run_engine_mode", "research") or "research").strip().lower()

    use_live_protection_logic = st.toggle(
        "Aligner TP/SL/trailing sur la logique live",
        value=bool(st.session_state.get("bt_run_use_live_protection_logic", True)),
        key="bt_run_use_live_protection_logic",
        help=(
            "Activé (défaut) : TP, stop initial et trailing sont calculés comme dans le pipeline live. "
            "Désactivé : logique fixe historique via TP/TS/SL initial."
        ),
    )
    if use_live_protection_logic:
        st.info(
            "Mode live-like actif : les champs `Take-profit`, `Trailing stop` et `Stop-loss initial dur` ne sont pas utilisés."
        )

    tp = float(st.session_state.get("bt_run_tp", 0.08))
    ts = float(st.session_state.get("bt_run_ts", 0.05))
    atr_ts = float(st.session_state.get("bt_run_atr_ts", 0.0))
    col4, col5, col6, col7 = st.columns(4)
    with col4:
        if use_live_protection_logic:
            st.caption("Take-profit (fraction) ignoré en mode live-like.")
        else:
            tp = st.number_input(
                "Take-profit (fraction)",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state.get("bt_run_tp", 0.08)),
                step=0.01,
                format="%.4f",
                key="bt_run_tp",
                help="Exemple : 0.08 = 8%.",
            )
    with col5:
        if use_live_protection_logic:
            st.caption("Trailing stop (fraction) ignoré en mode live-like.")
        else:
            ts = st.number_input(
                "Trailing stop (fraction)",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state.get("bt_run_ts", 0.05)),
                step=0.01,
                format="%.4f",
                key="bt_run_ts",
                help="Exemple : 0.05 = 5%.",
            )
    with col6:
        max_positions = st.number_input(
            "Max positions",
            min_value=1,
            max_value=500,
            value=int(st.session_state.get("bt_run_max_positions", 20)),
            step=1,
            key="bt_run_max_positions",
            help="Nombre maximal de lignes simultanées du portefeuille.",
        )
    with col7:
        commission_bps = st.number_input(
            "Commission (bps)",
            min_value=0.0,
            max_value=500.0,
            value=float(
                st.session_state.get(
                    "bt_run_commission_bps",
                    15.0 if current_engine_mode == "pipeline" else 5.0,
                )
            ),
            step=1.0,
            format="%.1f",
            key="bt_run_commission_bps",
            help="Coût fixe explicite par trade. En mode pipeline, 15 bps est un défaut réaliste recommandé.",
        )

    # ── P1 — ATR trailing stop + disable walk-forward ──
    col4b, col5b, col6b, col7b = st.columns(4)
    with col4b:
        atr_ts = st.number_input(
            "ATR trailing stop (multiplicateur)",
            min_value=0.0,
            max_value=10.0,
            value=float(st.session_state.get("bt_run_atr_ts", 2.5)),
            step=0.5,
            format="%.1f",
            key="bt_run_atr_ts",
            help="0 = désactivé (utilise TS fixe). Ex: 2.0 → stop = peak − 2×ATR_20. Le stop le plus large des deux (fixe vs ATR) est utilisé.",
        )
    with col5b:
        disable_walk_forward = st.checkbox(
            "Désactiver l'overlay walk-forward",
            value=bool(st.session_state.get("bt_run_disable_walk_forward", False)),
            key="bt_run_disable_walk_forward",
            help="Si coché, le --walk-forward-artifacts-dir n'est PAS passé → le score brut (final_score ou autre) est utilisé sans overlay.",
        )
    with col6b:
        st.caption("")  # espace réservé
    with col7b:
        st.caption("")  # espace réservé

    col8, col9, col10, col11 = st.columns(4)
    with col8:
        slippage_bps = st.number_input(
            "Slippage explicite (bps)",
            min_value=0.0,
            max_value=500.0,
            value=float(
                st.session_state.get(
                    "bt_run_slippage_bps",
                    15.0 if current_engine_mode == "pipeline" else 5.0,
                )
            ),
            step=1.0,
            format="%.1f",
            key="bt_run_slippage_bps",
            help="Slippage fixe explicite, appliqué en plus du modèle microstructure si activé.",
        )
    with col9:
        account_type = cast(
            str,
            st.selectbox(
                "Type de compte",
                options=["margin", "cash"],
                index=["margin", "cash"].index(
                    cast(str, st.session_state.get("bt_run_account_type", "margin"))
                    if st.session_state.get("bt_run_account_type", "margin") in {"margin", "cash"}
                    else "margin"
                ),
                key="bt_run_account_type",
                help="`margin` = compte standard/margin ; `cash` = cash settled uniquement.",
            ),
        )
    with col10:
        swing_only = st.checkbox(
            "Swing only",
            value=bool(st.session_state.get("bt_run_swing_only", False)),
            key="bt_run_swing_only",
            help="Si coché, une position ne peut pas être revendue le jour même.",
        )
    with col11:
        sentiment_lookback = st.number_input(
            "Sentiment lookback (jours)",
            min_value=1,
            max_value=3650,
            value=int(st.session_state.get("bt_run_sentiment_lookback", 365)),
            step=1,
            key="bt_run_sentiment_lookback",
            help="Paramètre CLI exposé par le backtesting. À conserver cohérent avec vos hypothèses research.",
        )
    col12, col13, col14 = st.columns(3)
    with col12:
        ml_mode = cast(
            str,
            st.selectbox(
                "Mode ML",
                options=["auto", "off", "rebuild-missing"],
                index=["auto", "off", "rebuild-missing"].index(
                    cast(str, st.session_state.get("bt_run_ml_mode", "off"))
                    if st.session_state.get("bt_run_ml_mode", "off") in {"auto", "off", "rebuild-missing"}
                    else "off"
                ),
                key="bt_run_ml_mode",
                help="`auto` utilise ce qui existe, `off` ignore ML, `rebuild-missing` tente une reconstruction PIT des prédictions manquantes.",
            ),
        )
    with col13:
        sentiment_mode = cast(
            str,
            st.selectbox(
                "Mode sentiment",
                options=["auto", "off", "rebuild-missing"],
                index=["auto", "off", "rebuild-missing"].index(
                    cast(str, st.session_state.get("bt_run_sentiment_mode", "auto"))
                    if st.session_state.get("bt_run_sentiment_mode", "auto") in {"auto", "off", "rebuild-missing"}
                    else "auto"
                ),
                key="bt_run_sentiment_mode",
                help="`auto` garde le meilleur signal disponible, `off` neutralise le sentiment, `rebuild-missing` reconstruit les snapshots manquants si possible.",
            ),
        )

    with col14:
        no_save = st.checkbox(
            "Ne pas sauver les artefacts",
            value=bool(st.session_state.get("bt_run_no_save", False)),
            key="bt_run_no_save",
            help="Si coché, le PNG d'equity curve et le CSV des trades ne seront pas écrits dans `artifacts/backtesting/`.",
        )

    # ─── P2 (2026-06-27) filtre ML manquant ───
    st.markdown("---")
    filter_no_ml = st.checkbox(
        "🚫 Filtrer les candidats sans modèle ML entraîné",
        value=bool(st.session_state.get("bt_run_filter_no_ml", False)),
        key="bt_run_filter_no_ml",
        help="Exclut les candidats qui n'ont pas de prédictions dans model_predictions (pas encore entraînés). Les symboles filtrés sont loggués dans le backtest.",
    )

    mode_col1, mode_col2, mode_col3, mode_col4, mode_col5, mode_col6, mode_col7, mode_col8 = st.columns(8)
    with mode_col1:
        engine_mode = cast(
            str,
            st.selectbox(
                "Mode moteur",
                options=["research", "pipeline"],
                index=["research", "pipeline"].index(
                    cast(str, st.session_state.get("bt_run_engine_mode", "pipeline"))
                    if st.session_state.get("bt_run_engine_mode", "pipeline") in {"research", "pipeline"}
                    else "pipeline"
                ),
                key="bt_run_engine_mode",
                help="`research` conserve le comportement tolérant du backtest standard ; `pipeline` exige des snapshots PIT valides et évite les écritures implicites.",
            ),
        )
    with mode_col2:
        scores_pit_mode = cast(
            str,
            st.selectbox(
                "Mode PIT scores",
                options=["exact", "asof_latest"],
                index=["exact", "asof_latest"].index(
                    cast(str, st.session_state.get("bt_run_scores_pit_mode", "exact"))
                    if st.session_state.get("bt_run_scores_pit_mode", "exact") in {"exact", "asof_latest"}
                    else "exact"
                ),
                key="bt_run_scores_pit_mode",
                help="`exact` lit uniquement les snapshots du jour ; `asof_latest` réutilise le dernier snapshot `<= trade_date` disponible dans `stock_scores_history`.",
            ),
        )
    with mode_col3:
        ml_pit_strategy = cast(
            str,
            st.selectbox(
                "Stratégie ML PIT",
                options=["auto", "use-persisted", "rebuild-missing", "walk-forward-train-then-predict"],
                index=["auto", "use-persisted", "rebuild-missing", "walk-forward-train-then-predict"].index(
                    cast(str, st.session_state.get("bt_run_ml_pit_strategy", "auto"))
                    if st.session_state.get("bt_run_ml_pit_strategy", "auto") in {"auto", "use-persisted", "rebuild-missing", "walk-forward-train-then-predict"}
                    else "auto"
                ),
                key="bt_run_ml_pit_strategy",
                help="Permet d'expliciter comment le backtest doit traiter les prédictions ML en mode PIT. `walk-forward-train-then-predict` fail-fast tant qu'il n'est pas encore supporté.",
            ),
        )
    with mode_col4:
        phase2_mode = cast(
            str,
            st.selectbox(
                "Mode Phase 2",
                options=["off", "risk", "risk_execution"],
                index=["off", "risk", "risk_execution"].index(
                    cast(str, st.session_state.get("bt_run_phase2_mode", "risk_execution"))
                    if st.session_state.get("bt_run_phase2_mode", "risk_execution") in {"off", "risk", "risk_execution"}
                    else "risk_execution"
                ),
                key="bt_run_phase2_mode",
                help="Active de manière opt-in les bridges de fidélité Phase 2. `off` conserve strictement le replay historique ; `risk` réutilise `risk_management`; `risk_execution` ajoute les intents/fills simulés via `execution_engine`.",
            ),
        )
    with mode_col5:
        phase3_mode = cast(
            str,
            st.selectbox(
                "Mode Phase 3",
                options=["off", "execution_replay"],
                index=["off", "execution_replay"].index(
                    cast(str, st.session_state.get("bt_run_phase3_mode", "off"))
                    if st.session_state.get("bt_run_phase3_mode", "off") in {"off", "execution_replay"}
                    else "off"
                ),
                key="bt_run_phase3_mode",
                help="`execution_replay` reprend les cibles/fills simulés du bridge d'exécution pour rejouer les quantités dans le moteur de backtest. Exige `phase2_mode = risk_execution`.",
            ),
        )
    with mode_col6:
        phase4_mode = cast(
            str,
            st.selectbox(
                "Mode Phase 4",
                options=["off", "protection_replay"],
                index=["off", "protection_replay"].index(
                    cast(str, st.session_state.get("bt_run_phase4_mode", "off"))
                    if st.session_state.get("bt_run_phase4_mode", "off") in {"off", "protection_replay"}
                    else "off"
                ),
                key="bt_run_phase4_mode",
                help="`protection_replay` rejoue les child intents de protection (take-profit, initial stop, trailing) dans le moteur de backtest. Exige `phase3_mode = execution_replay`.",
            ),
        )
    with mode_col7:
        phase5_mode = cast(
            str,
            st.selectbox(
                "Mode Phase 5",
                options=["off", "watcher_replay"],
                index=["off", "watcher_replay"].index(
                    cast(str, st.session_state.get("bt_run_phase5_mode", "off"))
                    if st.session_state.get("bt_run_phase5_mode", "off") in {"off", "watcher_replay"}
                    else "off"
                ),
                key="bt_run_phase5_mode",
                help="`watcher_replay` rejoue la logique de transition du watcher de protection avec une temporalité conservative (promotion effective à partir de la séance suivante). Exige `phase4_mode = protection_replay`.",
            ),
        )
    with mode_col8:
        phase7_mode = cast(
            str,
            st.selectbox(
                "Mode Phase 7",
                options=["off", "exit_lifecycle_replay"],
                index=["off", "exit_lifecycle_replay"].index(
                    cast(str, st.session_state.get("bt_run_phase7_mode", "off"))
                    if st.session_state.get("bt_run_phase7_mode", "off") in {"off", "exit_lifecycle_replay"}
                    else "off"
                ),
                key="bt_run_phase7_mode",
                help="`exit_lifecycle_replay` matérialise l'exit terminal (TP/initial stop/trailing) et l'annulation OCO du sibling comme source de vérité de sortie. Exige `phase5_mode = watcher_replay`.",
            ),
        )

    macro_mode_col1, macro_mode_col2 = st.columns([1.5, 2.5])
    with macro_mode_col1:
        macro_pit_mode = cast(
            str,
            st.selectbox(
                "Mode PIT macro",
                options=["yaml_default", "asof_inclusive", "j_minus_1_strict"],
                index=["yaml_default", "asof_inclusive", "j_minus_1_strict"].index(
                    cast(str, st.session_state.get("bt_run_macro_pit_mode", "yaml_default"))
                    if st.session_state.get("bt_run_macro_pit_mode", "yaml_default") in {"yaml_default", "asof_inclusive", "j_minus_1_strict"}
                    else "yaml_default"
                ),
                key="bt_run_macro_pit_mode",
                help="`yaml_default` suit `market_regimes.macro_pit_mode_backtest`, `asof_inclusive` autorise la dernière valeur <= J, `j_minus_1_strict` force strictement J-1 pour VIX/VIX9D/10Y.",
            ),
        )
    with macro_mode_col2:
        st.caption(
            "Ce réglage agit uniquement sur les données macro du bridge régime en backtest ; il ne change pas la politique PIT des scores ni celle de la ML."
        )

    info_col1, info_col2 = st.columns(2)
    with info_col1:
        st.caption(
            "`cash` + `swing_only` est supporté : cash settled T+1 et aucune sortie le jour même."
        )

    macro_col1, macro_col2 = st.columns([1.7, 2.3])
    with macro_col1:
        allow_neutral_fallback_on_missing_macro_data = st.checkbox(
            "Tolérer macro indisponible (`data_quality=missing`)",
            value=bool(st.session_state.get("bt_run_allow_missing_macro_data", False)),
            key="bt_run_allow_missing_macro_data",
            help=(
                "Si coché, une séance sans macro requise (VIX / 10Y selon votre config) continue en mode dégradé "
                "et est marquée explicitement en `data_quality=missing`. Si décoché, le backtest échoue en fail-fast."
            ),
        )
    with macro_col2:
        if allow_neutral_fallback_on_missing_macro_data:
            st.caption(
                "Mode tolérant actif : le replay continue, mais chaque date touchée sera explicitement marquée en `data_quality=missing`."
            )
        else:
            st.caption(
                "Mode strict actif (défaut) : le run échoue dès qu'une macro requise est indisponible."
            )

    artifacts_dir = st.text_input(
        "Répertoire des artefacts modèles",
        value=cast(str, st.session_state.get("bt_run_artifacts_dir", "artifacts/models")),
        key="bt_run_artifacts_dir",
        help="Dossier contenant les checkpoints/scalers/configs de modèles pour `--ml-mode rebuild-missing`.",
    )

    extra_col1, extra_col2 = st.columns(2)
    with extra_col1:
        score_column = cast(
            str,
            st.selectbox(
                "Colonne de score",
                options=["auto", "final_score_walk_forward", "final_score_sentiment", "final_score"],
                index=["auto", "final_score_walk_forward", "final_score_sentiment", "final_score"].index(
                    cast(str, st.session_state.get("bt_run_score_column", "auto"))
                    if st.session_state.get("bt_run_score_column", "auto") in {"auto", "final_score_walk_forward", "final_score_sentiment", "final_score"}
                    else "auto"
                ),
                key="bt_run_score_column",
                help="Permet de forcer explicitement la source de score utilisée lors du replay des signaux.",
            ),
        )
    with extra_col2:
        # Walk-forward : toujours le répertoire racine (tous presets confondus).
        wf_root = Path("artifacts/sentiment_walk_forward")
        cal_root = Path("artifacts/sentiment_calibration")
        if (wf_root / "latest_best_weights.json").exists() or (wf_root / "walk_forward_best_weights_latest.json").exists():
            walk_forward_artifacts_dir = str(wf_root)
        elif (cal_root / "latest_best_weights.json").exists() or (cal_root / "sentiment_weight_calibration_best.json").exists():
            walk_forward_artifacts_dir = str(cal_root)
        else:
            walk_forward_artifacts_dir = str(wf_root)  # sera créé au prochain run
        st.caption(f"📁 Walk-forward : `{walk_forward_artifacts_dir}`")
    baseline_col1, baseline_col2 = st.columns(2)
    with baseline_col1:
        fidelity_baseline_id = st.text_input(
            "Baseline fidélité (optionnel)",
            value=cast(str, st.session_state.get("bt_run_fidelity_baseline_id", "")),
            key="bt_run_fidelity_baseline_id",
            help="Active le comparatif Sprint 6 contre une baseline versionnée si l'identifiant existe dans le catalogue choisi.",
        )
    with baseline_col2:
        fidelity_baseline_catalog = st.text_input(
            "Catalogue baseline fidélité (optionnel)",
            value=cast(str, st.session_state.get("bt_run_fidelity_baseline_catalog", "")),
            key="bt_run_fidelity_baseline_catalog",
            help="Chemin du catalogue JSON des baselines. Convention stable recommandée : `config/fidelity_baseline_catalog.json`, pointant vers des snapshots promus sous `artifacts/fidelity_baselines/`.",
        )
    default_catalog_rows = _build_fidelity_baseline_catalog_rows()
    st.caption(
        "Convention stable Sprint 6 : `config/fidelity_baseline_catalog.json` référence des snapshots promus dans `artifacts/fidelity_baselines/<baseline_id>/` (snapshot + promotion manifest)."
    )
    if not default_catalog_rows.empty:
        with st.expander("🧱 Baselines fidélité promues disponibles", expanded=False):
            st.dataframe(default_catalog_rows, use_container_width=True, hide_index=True)

    _render_pipeline_pit_hint(
        engine_mode=engine_mode,
        start=start.strip(),
        end=end.strip() or None,
        selected_run_preset_key=selected_run_preset_key,
        auto_run_preset_key=auto_run_preset_key,
    )
    show_ml_coverage_preflight = st.checkbox(
        "Afficher le préflight couverture ML PIT (lent)",
        value=bool(st.session_state.get("bt_run_show_ml_coverage_preflight", False)),
        key="bt_run_show_ml_coverage_preflight",
        help=(
            "Compare les paires candidat×date attendues depuis `stock_scores_history` à `model_predictions` "
            "avant lancement. Désactivé par défaut car ce calcul peut être coûteux."
        ),
    )
    if show_ml_coverage_preflight:
        _render_ml_coverage_preflight(
            engine_mode=engine_mode,
            ml_mode=ml_mode,
            ml_pit_strategy=ml_pit_strategy,
            start=start.strip(),
            end=end.strip() or None,
            selected_run_preset_key=selected_run_preset_key,
            auto_run_preset_key=auto_run_preset_key,
        )
    st.caption(
        "Préflight OHLCV appliqué au lancement : le backtest consomme uniquement `stock_bars_daily.data_source='eodhd_eod'`. "
        "Si la fenêtre demandée ne contient pas cette source, le run échoue explicitement."
    )

    options = BacktestRunOptions(
        start=start.strip(),
        end=end.strip() or None,
        equity=float(equity),
        capital_preset_key=None if selected_run_preset_key == CAPITAL_PRESET_CUSTOM else selected_run_preset_key,
        tp=float(tp),
        ts=float(ts),
        atr_ts=float(st.session_state.get("bt_run_atr_ts", 0.0) or 0.0),
        use_live_protection_logic=bool(use_live_protection_logic),
        max_positions=int(max_positions),
        fees=None,
        commission_bps=float(commission_bps),
        slippage_bps=float(slippage_bps),
        account_type=cast(Any, account_type),
        swing_only=bool(swing_only),
        allow_fractional_shares=bool(allow_fractional_shares),
        sentiment_lookback=int(sentiment_lookback),
        no_save=bool(no_save),
        filter_no_ml=bool(filter_no_ml),
        ml_mode=cast(Any, ml_mode),
        sentiment_mode=cast(Any, sentiment_mode),
        engine_mode=cast(Any, engine_mode),
        scores_pit_mode=cast(Any, scores_pit_mode),
        macro_pit_mode=cast(Any, macro_pit_mode),
        ml_pit_strategy=cast(Any, ml_pit_strategy),
        phase2_mode=cast(Any, phase2_mode),
        phase3_mode=cast(Any, phase3_mode),
        phase4_mode=cast(Any, phase4_mode),
        phase5_mode=cast(Any, phase5_mode),
        phase7_mode=cast(Any, phase7_mode),
        allow_neutral_fallback_on_missing_macro_data=bool(allow_neutral_fallback_on_missing_macro_data),
        fidelity_baseline_id=fidelity_baseline_id.strip() or None,
        fidelity_baseline_catalog=fidelity_baseline_catalog.strip() or None,
        artifacts_dir=artifacts_dir.strip() or "artifacts/models",
        score_column=cast(Any, score_column),
        walk_forward_artifacts_dir=walk_forward_artifacts_dir.strip() or None,
        disable_walk_forward=bool(st.session_state.get("bt_run_disable_walk_forward", False)),
        **_build_overlay_options(
            engine_mode=engine_mode,
            selected_run_preset_key=selected_run_preset_key,
            auto_run_preset_key=auto_run_preset_key,
            use_live_protection_logic=bool(use_live_protection_logic),
        ),
    )

    st.code(format_command_for_display(build_backtesting_command("run", options)), language="powershell")
    return options


def _build_backfill_options() -> BackfillScoresHistoryOptions:
    st.subheader("🧱 Backfill PIT de `stock_scores_history`")
    st.caption(
        "Cette commande reconstruit les snapshots historiques nécessaires pour un vrai backtest point-in-time. "
        "Elle exécute `python -m backtesting backfill-scores-history ...` en arrière-plan."
    )
    st.caption(
        "Même contrainte source que le backtest : la reconstruction PIT s'appuie sur `stock_bars_daily.data_source='eodhd_eod'`."
    )
    _render_reference_table("backfill")

    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.text_input(
            "Date de début du backfill",
            value=cast(str, st.session_state.get("bt_backfill_start", "2020-01-01")),
            key="bt_backfill_start",
            help="Première séance à reconstruire au format YYYY-MM-DD.",
        )
    with col2:
        end = st.text_input(
            "Date de fin du backfill",
            value=cast(str, st.session_state.get("bt_backfill_end", "2025-12-31")),
            key="bt_backfill_end",
            help="Laissez vide pour laisser le service résoudre la borne utile automatiquement.",
        )
    with col3:
        limit_days_raw = st.text_input(
            "Limiter à N séances (optionnel)",
            value=cast(str, st.session_state.get("bt_backfill_limit_days_raw", "")),
            key="bt_backfill_limit_days_raw",
            help="Très pratique pour un test sur 1, 5 ou 10 jours avant un run complet.",
        )

    capital = st.number_input(
        "Capital de référence pour le preset ($)",
        min_value=1_000.0,
        value=float(st.session_state.get("bt_backfill_capital", st.session_state.get("bt_run_equity", 100_000.0))),
        step=1_000.0,
        key="bt_backfill_capital",
        help="Utilisé pour résoudre automatiquement le preset si vous laissez `Personnalisé / auto`.",
    )
    backfill_preset_options = _get_capital_preset_options()
    _ensure_capital_preset_session_key(BT_BACKFILL_CAPITAL_PRESET_KEY, float(capital))
    backfill_preset_col1, backfill_preset_col2 = st.columns([1.4, 2.6])
    with backfill_preset_col1:
        selected_backfill_preset_key = cast(
            str,
            st.selectbox(
                "Preset capital PIT backfill",
                options=backfill_preset_options,
                format_func=_format_capital_preset_label,
                key=BT_BACKFILL_CAPITAL_PRESET_KEY,
                help=(
                    "Le backfill reconstruit `stock_scores_history` par preset. "
                    "`custom/auto` = résolution par le capital ci-dessus."
                ),
            ),
        )
    with backfill_preset_col2:
        auto_backfill_preset_key = _resolve_default_capital_preset_key(float(capital))
        if selected_backfill_preset_key == CAPITAL_PRESET_CUSTOM:
            st.caption(
                f"Résolution automatique active : capital `{float(capital):,.0f}$` → preset `{_format_capital_preset_label(auto_backfill_preset_key)}`."
            )
        else:
            _apply_backfill_capital_preset(selected_backfill_preset_key, float(capital))
            st.caption(
                f"Preset explicite utilisé pour écrire `stock_scores_history` : `{_format_capital_preset_label(selected_backfill_preset_key)}`."
            )

    col4, col5, col6, col7 = st.columns(4)
    with col4:
        overwrite_existing = st.checkbox(
            "Recalculer les dates déjà historisées",
            value=bool(st.session_state.get("bt_backfill_overwrite_existing", False)),
            key="bt_backfill_overwrite_existing",
            help="Supprime puis reconstruit les snapshots existants sur les dates ciblées.",
        )
    with col5:
        chunk_size = st.number_input(
            "Chunk size",
            min_value=1,
            max_value=50_000,
            value=int(st.session_state.get("bt_backfill_chunk_size", 500)),
            step=100,
            key="bt_backfill_chunk_size",
            help="Taille des lots symboles pour le screener/scanner PIT.",
        )
    with col6:
        selection_size = st.number_input(
            "Selection size",
            min_value=1,
            max_value=5_000,
            value=int(st.session_state.get("bt_backfill_selection_size", 100)),
            step=10,
            key="bt_backfill_selection_size",
            help="Nombre final de candidats conservés par séance backfillée.",
        )
    with col7:
        screener_workers_raw = st.text_input(
            "Screener workers (optionnel)",
            value=cast(str, st.session_state.get("bt_backfill_screener_workers_raw", "")),
            key="bt_backfill_screener_workers_raw",
            help="Nombre de workers ProcessPool. Laissez vide pour utiliser l'auto-détection du service.",
        )

    limit_days = _parse_optional_int(limit_days_raw, label="limit_days")
    screener_workers = _parse_optional_int(screener_workers_raw, label="screener_workers")

    options = BackfillScoresHistoryOptions(
        start=start.strip(),
        end=end.strip() or None,
        capital=float(capital),
        capital_preset_key=None if selected_backfill_preset_key == CAPITAL_PRESET_CUSTOM else selected_backfill_preset_key,
        overwrite_existing=bool(overwrite_existing),
        limit_days=limit_days,
        chunk_size=int(chunk_size),
        selection_size=int(selection_size),
        screener_workers=screener_workers,
    )

    st.code(format_command_for_display(build_backtesting_command("backfill-scores-history", options)), language="powershell")
    return options


def _build_diagnose_screener_options() -> DiagnoseScreenerOptions:
    st.subheader("🧪 Diagnose screener PIT")
    st.caption(
        "Cette commande exécute `python -m backtesting diagnose-screener ...` en arrière-plan pour recalculer les artefacts diagnostics/recommandations du screener."
    )
    _render_reference_table("diagnose-screener")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        start = st.text_input(
            "Date de début diagnostic",
            value=cast(str, st.session_state.get("bt_diag_start", "2020-01-01")),
            key="bt_diag_start",
        )
    with col2:
        end = st.text_input(
            "Date de fin diagnostic",
            value=cast(str, st.session_state.get("bt_diag_end", "2025-12-31")),
            key="bt_diag_end",
        )
    with col3:
        mode = cast(
            str,
            st.selectbox(
                "Mode de balayage",
                options=["oat", "grid"],
                index=["oat", "grid"].index(
                    cast(str, st.session_state.get("bt_diag_mode", "oat"))
                    if st.session_state.get("bt_diag_mode", "oat") in {"oat", "grid"}
                    else "oat"
                ),
                key="bt_diag_mode",
            ),
        )
    with col4:
        limit_days_raw = st.text_input(
            "Limiter à N séances (optionnel)",
            value=cast(str, st.session_state.get("bt_diag_limit_days_raw", "")),
            key="bt_diag_limit_days_raw",
        )

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        chunk_size = st.number_input(
            "Chunk size diagnostic",
            min_value=1,
            max_value=50_000,
            value=int(st.session_state.get("bt_diag_chunk_size", 500)),
            step=100,
            key="bt_diag_chunk_size",
        )
    with col6:
        selection_size = st.number_input(
            "Selection size diagnostic",
            min_value=1,
            max_value=5_000,
            value=int(st.session_state.get("bt_diag_selection_size", 100)),
            step=10,
            key="bt_diag_selection_size",
        )
    with col7:
        max_positions = st.number_input(
            "Max positions diagnostic",
            min_value=1,
            max_value=500,
            value=int(st.session_state.get("bt_diag_max_positions", 20)),
            step=1,
            key="bt_diag_max_positions",
        )
    with col8:
        max_scenarios = st.number_input(
            "Max scenarios",
            min_value=1,
            max_value=5_000,
            value=int(st.session_state.get("bt_diag_max_scenarios", 64)),
            step=1,
            key="bt_diag_max_scenarios",
        )

    col9, col10, col11, col12 = st.columns(4)
    with col9:
        screener_workers_raw = st.text_input(
            "Screener workers (optionnel)",
            value=cast(str, st.session_state.get("bt_diag_screener_workers_raw", "")),
            key="bt_diag_screener_workers_raw",
        )
    with col10:
        rs_values = st.text_input(
            "RS values (CSV)",
            value=cast(str, st.session_state.get("bt_diag_rs_values", "100,102,105")),
            key="bt_diag_rs_values",
        )
    with col11:
        range_lookback_values = st.text_input(
            "Range lookback values (CSV)",
            value=cast(str, st.session_state.get("bt_diag_range_lookback_values", "252,504,756")),
            key="bt_diag_range_lookback_values",
        )
    with col12:
        historical_range_score_values = st.text_input(
            "Historical range score values (CSV)",
            value=cast(str, st.session_state.get("bt_diag_historical_range_score_values", "65,70,75")),
            key="bt_diag_historical_range_score_values",
        )

    liquidity_threshold_values = st.text_input(
        "Liquidity threshold values (CSV)",
        value=cast(str, st.session_state.get("bt_diag_liquidity_threshold_values", "5000000,10000000,20000000")),
        key="bt_diag_liquidity_threshold_values",
    )

    diag_preset_options = _get_capital_preset_options()
    _ensure_capital_preset_session_key("bt_diag_capital_preset_key", None)
    selected_diag_preset = cast(
        str,
        st.selectbox(
            "Preset capital PIT",
            options=diag_preset_options,
            format_func=_format_capital_preset_label,
            key="bt_diag_capital_preset_key",
            help="Filtre les snapshots PIT par preset capital. Le répertoire artefacts est dérivé automatiquement.",
        ),
    )
    diag_preset_key = selected_diag_preset if selected_diag_preset != CAPITAL_PRESET_CUSTOM else None
    if diag_preset_key:
        output_dir = f"artifacts/screener_diagnostics/{diag_preset_key}"
        st.caption(f"📁 Artefacts : `{output_dir}`")
    else:
        output_dir = st.text_input(
            "Répertoire des artefacts screener",
            value=cast(str, st.session_state.get("bt_diag_output_dir", "artifacts/screener_diagnostics")),
            key="bt_diag_output_dir",
            help="Le dashboard Screening lira ce dossier par défaut.",
        )

    limit_days = _parse_optional_int(limit_days_raw, label="limit_days")
    screener_workers = _parse_optional_int(screener_workers_raw, label="screener_workers")

    options = DiagnoseScreenerOptions(
        start=start.strip(),
        end=end.strip() or None,
        limit_days=limit_days,
        mode=cast(Any, mode),
        chunk_size=int(chunk_size),
        selection_size=int(selection_size),
        max_positions=int(max_positions),
        screener_workers=screener_workers,
        max_scenarios=int(max_scenarios),
        rs_values=rs_values.strip() or "100,102,105",
        range_lookback_values=range_lookback_values.strip() or "252,504,756",
        historical_range_score_values=historical_range_score_values.strip() or "65,70,75",
        liquidity_threshold_values=liquidity_threshold_values.strip() or "5000000,10000000,20000000",
        output_dir=output_dir.strip() or "artifacts/screener_diagnostics",
        capital_preset_key=diag_preset_key,
    )

    st.code(format_command_for_display(build_backtesting_command("diagnose-screener", options)), language="powershell")
    return options


def _build_recommend_screener_options() -> RecommendScreenerOptions:
    st.subheader("🎯 Recommend screener")
    st.caption(
        "Cette commande exécute `python -m backtesting recommend-screener ...` en arrière-plan pour recalculer les recommandations à partir d'un diagnostic existant."
    )
    _render_reference_table("recommend-screener")

    col1, col2, col3 = st.columns(3)
    with col1:
        input_dir = st.text_input(
            "Répertoire source",
            value=cast(str, st.session_state.get("bt_reco_input_dir", "artifacts/screener_diagnostics")),
            key="bt_reco_input_dir",
        )
    with col2:
        output_dir = st.text_input(
            "Répertoire de sortie (optionnel)",
            value=cast(str, st.session_state.get("bt_reco_output_dir", "")),
            key="bt_reco_output_dir",
        )
    with col3:
        target_horizon = st.number_input(
            "Target horizon",
            min_value=1,
            max_value=252,
            value=int(st.session_state.get("bt_reco_target_horizon", 20)),
            step=1,
            key="bt_reco_target_horizon",
        )

    col4, col5, col6 = st.columns(3)
    with col4:
        summary_csv = st.text_input(
            "Summary CSV explicite (optionnel)",
            value=cast(str, st.session_state.get("bt_reco_summary_csv", "")),
            key="bt_reco_summary_csv",
        )
    with col5:
        daily_csv = st.text_input(
            "Daily CSV explicite (optionnel)",
            value=cast(str, st.session_state.get("bt_reco_daily_csv", "")),
            key="bt_reco_daily_csv",
        )
    with col6:
        baseline_name = st.text_input(
            "Baseline explicite (optionnel)",
            value=cast(str, st.session_state.get("bt_reco_baseline_name", "")),
            key="bt_reco_baseline_name",
        )

    reco_preset_options = _get_capital_preset_options()
    _ensure_capital_preset_session_key("bt_reco_capital_preset_key", None)
    selected_reco_preset = cast(
        str,
        st.selectbox(
            "Preset capital PIT",
            options=reco_preset_options,
            format_func=_format_capital_preset_label,
            key="bt_reco_capital_preset_key",
            help="Pour cohérence avec le diagnostic utilisé. Si un preset est sélectionné, le répertoire source est dérivé automatiquement.",
        ),
    )
    reco_preset_key = selected_reco_preset if selected_reco_preset != CAPITAL_PRESET_CUSTOM else None
    if reco_preset_key and (not input_dir.strip() or input_dir.strip() == "artifacts/screener_diagnostics"):
        input_dir = f"artifacts/screener_diagnostics/{reco_preset_key}"

    options = RecommendScreenerOptions(
        input_dir=input_dir.strip() or "artifacts/screener_diagnostics",
        summary_csv=summary_csv.strip() or None,
        daily_csv=daily_csv.strip() or None,
        output_dir=output_dir.strip() or None,
        baseline_name=baseline_name.strip() or None,
        target_horizon=int(target_horizon),
        capital_preset_key=reco_preset_key,
    )

    st.code(format_command_for_display(build_backtesting_command("recommend-screener", options)), language="powershell")
    return options


# ----------------------------------------------------------------------
# Sprint S26 — gap P2 : sentiment calibration + walk-forward sentiment
# ----------------------------------------------------------------------


def _build_calibrate_sentiment_options() -> "CalibrateSentimentWeightsOptions":
    from datetime import date, timedelta

    st.subheader("📰 Calibrate sentiment weights")
    st.caption(
        "Calibre les poids `sentiment_weight` / `macro_sector_weight` à partir de "
        "`stock_scores_history` et des forward returns. Lance `python -m backtesting calibrate-sentiment-weights ...`."
    )
    today = date.today()
    default_start = (today - timedelta(days=365 * 2)).isoformat()

    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.text_input(
            "Date de début (YYYY-MM-DD)",
            value=cast(str, st.session_state.get("bt_calibrate_start", default_start)),
            key="bt_calibrate_start",
        )
    with col2:
        end = st.text_input(
            "Date de fin (YYYY-MM-DD)",
            value=cast(str, st.session_state.get("bt_calibrate_end", today.isoformat())),
            key="bt_calibrate_end",
        )
    with col3:
        top_n = st.number_input(
            "Top N (titres / jour)",
            min_value=5,
            max_value=200,
            value=int(st.session_state.get("bt_calibrate_top_n", 20)),
            step=5,
            key="bt_calibrate_top_n",
        )

    col4, col5 = st.columns(2)
    with col4:
        horizons = st.text_input(
            "Horizons forward (CSV)",
            value=cast(str, st.session_state.get("bt_calibrate_horizons", "5,10,20")),
            key="bt_calibrate_horizons",
        )
    with col5:
        all_symbols = st.checkbox(
            "Univers entier (`--all-symbols`)",
            value=bool(st.session_state.get("bt_calibrate_all_symbols", False)),
            key="bt_calibrate_all_symbols",
            help="Sinon limité aux candidats historiques.",
        )

    output_dir = "artifacts/sentiment_calibration"

    options = CalibrateSentimentWeightsOptions(
        start=start.strip(),
        end=end.strip(),
        top_n=int(top_n),
        horizons=horizons.strip() or "5,10,20",
        output_dir=output_dir,
        all_symbols=bool(all_symbols),
        capital_preset_key=None,
    )
    st.code(
        format_command_for_display(build_backtesting_command("calibrate-sentiment-weights", options)),
        language="powershell",
    )
    return options


def _build_calibrate_conviction_options() -> "CalibrateConvictionWeightsOptions":
    """Construit les options pour la calibration conviction (quant/ML) + Kelly (P2 2026-06-25)."""
    from datetime import date, timedelta

    st.subheader("🎯 Calibrate conviction (quant/ML) + Kelly")
    st.caption(
        "Calibre les poids de fusion conviction (`score_weight` / `prediction_weight`) "
        "et les paramètres Kelly (`fraction_multiplier`, `payoff_ratio`, `min_probability`) "
        "via walk-forward backtest. Lance `python -m backtesting calibrate-conviction-weights ...`."
    )
    today = date.today()
    default_start = (today - timedelta(days=365 * 2)).isoformat()

    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.text_input(
            "Date de début (YYYY-MM-DD)",
            value=cast(str, st.session_state.get("bt_conv_start", default_start)),
            key="bt_conv_start",
        )
    with col2:
        end = st.text_input(
            "Date de fin (YYYY-MM-DD)",
            value=cast(str, st.session_state.get("bt_conv_end", today.isoformat())),
            key="bt_conv_end",
        )
    with col3:
        top_n = st.number_input(
            "Top N (titres / jour)",
            min_value=5,
            max_value=200,
            value=int(st.session_state.get("bt_conv_top_n", 20)),
            step=5,
            key="bt_conv_top_n",
        )

    col4, col5 = st.columns(2)
    with col4:
        horizons = st.text_input(
            "Horizons forward (CSV)",
            value=cast(str, st.session_state.get("bt_conv_horizons", "5,10,20")),
            key="bt_conv_horizons",
        )
    with col5:
        include_kelly = st.checkbox(
            "Inclure calibration Kelly",
            value=bool(st.session_state.get("bt_conv_include_kelly", True)),
            key="bt_conv_include_kelly",
            help="Active la calibration conjointe des paramètres Kelly "
            "(fraction_multiplier, payoff_ratio, min_probability). "
            "Désactiver pour ne calibrer que les poids conviction (score_weight / prediction_weight).",
        )

    scope = "all" if include_kelly else "conviction"

    col6, col7 = st.columns(2)
    with col6:
        top_n_long = st.number_input(
            "Top N longs (0=Top N)",
            min_value=0,
            max_value=200,
            value=int(st.session_state.get("bt_conv_top_n_long", 0)),
            step=5,
            key="bt_conv_top_n_long",
            help="Permet de surcharger le Top N global pour la jambe long.",
        )
    with col7:
        top_n_short = st.number_input(
            "Top N shorts (0=Top N)",
            min_value=0,
            max_value=200,
            value=int(st.session_state.get("bt_conv_top_n_short", 0)),
            step=5,
            key="bt_conv_top_n_short",
            help="Permet de surcharger le Top N global pour la jambe short.",
        )

    # Sprint 3 — backtest Kelly dans BacktestEngine
    backtest_kelly = st.checkbox(
        "Kelly via BacktestEngine (⚠️ coûteux, ~27 backtests/direction)",
        value=bool(st.session_state.get("bt_conv_backtest_kelly", False)),
        key="bt_conv_backtest_kelly",
        help="Quand coché, les paramètres Kelly sont raffinés via BacktestEngine "
        "(stops, corrélation, circuit breaker, slippage) au lieu du moteur simplifié. "
        "Multiplie le temps de calibration par ~10-50.",
    )

    output_dir = "artifacts/conviction_calibration"

    options = CalibrateConvictionWeightsOptions(
        start=start.strip(),
        end=end.strip(),
        top_n=int(top_n),
        horizons=horizons.strip() or "5,10,20",
        output_dir=output_dir,
        scope=scope,
        backtest_kelly=backtest_kelly,
        top_n_long=int(top_n_long) if int(top_n_long) > 0 else None,
        top_n_short=int(top_n_short) if int(top_n_short) > 0 else None,
    )
    st.code(
        format_command_for_display(build_backtesting_command("calibrate-conviction-weights", options)),
        language="powershell",
    )
    return options


def _build_walk_forward_conviction_options() -> "WalkForwardConvictionOptions":
    """Construit les options walk-forward conviction (Sprint 4)."""
    from datetime import date, timedelta

    st.subheader("🔄 Walk-forward conviction")
    st.caption(
        "Calibration walk-forward des scores conviction + Kelly via BacktestEngine. "
        "Chaque fold : calibration train → validation OOS avec BacktestEngine. "
        "Lance `python -m backtesting walk-forward-conviction ...`."
    )
    today = date.today()
    default_start = (today - timedelta(days=365 * 3)).isoformat()

    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.text_input(
            "Date de début (YYYY-MM-DD)",
            value=cast(str, st.session_state.get("bt_wfc_start", default_start)),
            key="bt_wfc_start",
        )
    with col2:
        end = st.text_input(
            "Date de fin (YYYY-MM-DD)",
            value=cast(str, st.session_state.get("bt_wfc_end", today.isoformat())),
            key="bt_wfc_end",
        )
    with col3:
        top_n = st.number_input(
            "Top N",
            min_value=5,
            max_value=200,
            value=int(st.session_state.get("bt_wfc_top_n", 20)),
            step=5,
            key="bt_wfc_top_n",
        )

    col4, col5, col6 = st.columns(3)
    with col4:
        horizons = st.text_input(
            "Horizons (CSV)",
            value=cast(str, st.session_state.get("bt_wfc_horizons", "5,10,20")),
            key="bt_wfc_horizons",
        )
    with col5:
        min_train_days = st.number_input(
            "Min train days / fold",
            min_value=63,
            max_value=2000,
            value=int(st.session_state.get("bt_wfc_min_train_days", 252)),
            step=21,
            key="bt_wfc_min_train_days",
        )
    with col6:
        test_days = st.number_input(
            "Test days / fold",
            min_value=21,
            max_value=504,
            value=int(st.session_state.get("bt_wfc_test_days", 63)),
            step=21,
            key="bt_wfc_test_days",
        )

    col7, col8 = st.columns(2)
    with col7:
        step_days = st.number_input(
            "Step days (0=auto)",
            min_value=0,
            max_value=504,
            value=int(st.session_state.get("bt_wfc_step_days", 0)),
            step=21,
            key="bt_wfc_step_days",
            help="Décalage entre folds. 0 = auto (utilise test_days).",
        )
    with col8:
        backtest_kelly = st.checkbox(
            "Kelly via BacktestEngine (⚠️ coûteux)",
            value=bool(st.session_state.get("bt_wfc_backtest_kelly", False)),
            key="bt_wfc_backtest_kelly",
            help="Quand coché, les paramètres Kelly sont raffinés via BacktestEngine "
            "(stops, corrélation, circuit breaker, slippage). Multiplie le temps par ~10-50.",
        )

    # ── Sprint 5/6 — Grilles symétriques & market-neutral ──────────
    st.markdown("---")
    st.caption("⚖️ **Market-neutral (Sprint 5/6)** — contraintes de neutralité nette et grilles symétriques.")

    col_grid, col_enforce = st.columns(2)
    with col_grid:
        symmetric_grid = st.selectbox(
            "Grille symétrique (optionnel)",
            options=["", "60/60", "80/80", "100/100", "40/40", "20/20"],
            index=0,
            key="bt_wfc_symmetric_grid",
            help="Surcharge top-n-long/top-n-short avec une grille prédéfinie. Laisser vide pour utiliser Top N.",
        )
    with col_enforce:
        enforce_net_exposure = st.checkbox(
            "Contraindre exposition nette",
            value=bool(st.session_state.get("bt_wfc_enforce_net", False)),
            key="bt_wfc_enforce_net",
            help="Active la réduction proportionnelle du côté surpondéré pour maintenir l'exposition nette dans le corridor.",
        )

    if enforce_net_exposure:
        col_target, col_tol = st.columns(2)
        with col_target:
            net_exposure_target = st.number_input(
                "Exposition nette cible",
                min_value=-1.0,
                max_value=1.0,
                value=float(st.session_state.get("bt_wfc_net_target", 0.0)),
                step=0.05,
                format="%.2f",
                key="bt_wfc_net_target",
                help="0.0 = market-neutral, 0.30 = biais long 30%.",
            )
    else:
        net_exposure_target = 0.0

    output_dir = "artifacts/walk_forward_conviction"

    options = WalkForwardConvictionOptions(
        start=start.strip(),
        end=end.strip(),
        top_n=int(top_n),
        horizons=horizons.strip() or "5,10,20",
        min_train_days=int(min_train_days),
        test_days=int(test_days),
        step_days=int(step_days) if int(step_days) > 0 else None,
        output_dir=output_dir,
        backtest_kelly=backtest_kelly,
        symmetric_grid=symmetric_grid.strip() if symmetric_grid and symmetric_grid.strip() else None,
        enforce_net_exposure=enforce_net_exposure,
        net_exposure_target=float(net_exposure_target) if enforce_net_exposure else 0.0,
    )
    st.code(
        format_command_for_display(build_backtesting_command("walk-forward-conviction", options)),
        language="powershell",
    )
    return options


def _build_walk_forward_sentiment_options() -> "WalkForwardSentimentOptions":
    from datetime import date, timedelta

    st.subheader("🚶 Walk-forward sentiment")
    st.caption(
        "Calibration walk-forward stricte avec backtest portefeuille hors échantillon. "
        "Lance `python -m backtesting walk-forward-sentiment ...`."
    )
    today = date.today()
    default_start = (today - timedelta(days=365 * 3)).isoformat()

    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.text_input(
            "Date de début (YYYY-MM-DD)",
            value=cast(str, st.session_state.get("bt_wfs_start", default_start)),
            key="bt_wfs_start",
        )
    with col2:
        end = st.text_input(
            "Date de fin (YYYY-MM-DD)",
            value=cast(str, st.session_state.get("bt_wfs_end", today.isoformat())),
            key="bt_wfs_end",
        )
    with col3:
        top_n = st.number_input(
            "Top N",
            min_value=5,
            max_value=200,
            value=int(st.session_state.get("bt_wfs_top_n", 20)),
            step=5,
            key="bt_wfs_top_n",
        )

    col4, col5, col6 = st.columns(3)
    with col4:
        horizons = st.text_input(
            "Horizons (CSV)",
            value=cast(str, st.session_state.get("bt_wfs_horizons", "5,10,20")),
            key="bt_wfs_horizons",
        )
    with col5:
        min_train_days = st.number_input(
            "Min train days / fold",
            min_value=63,
            max_value=2000,
            value=int(st.session_state.get("bt_wfs_min_train_days", 252)),
            step=21,
            key="bt_wfs_min_train_days",
        )
    with col6:
        test_days = st.number_input(
            "Test days / fold",
            min_value=21,
            max_value=504,
            value=int(st.session_state.get("bt_wfs_test_days", 63)),
            step=21,
            key="bt_wfs_test_days",
        )

    col7, col8, col9 = st.columns(3)
    with col7:
        max_positions = st.number_input(
            "Max positions",
            min_value=1,
            max_value=200,
            value=int(st.session_state.get("bt_wfs_max_positions", 20)),
            step=1,
            key="bt_wfs_max_positions",
        )
    with col8:
        equity = st.number_input(
            "Equity initial ($)",
            min_value=100.0,
            max_value=10_000_000.0,
            value=float(st.session_state.get("bt_wfs_equity", 100_000.0)),
            step=1000.0,
            key="bt_wfs_equity",
        )
    with col9:
        fees = st.number_input(
            "Fees (fraction)",
            min_value=0.0,
            max_value=0.05,
            value=float(st.session_state.get("bt_wfs_fees", 0.001)),
            step=0.0005,
            format="%.4f",
            key="bt_wfs_fees",
        )

    col10, col11, col12 = st.columns(3)
    with col10:
        tp = st.number_input(
            "TP (%)",
            min_value=0.0,
            max_value=1.0,
            value=float(st.session_state.get("bt_wfs_tp", 0.08)),
            step=0.01,
            format="%.3f",
            key="bt_wfs_tp",
        )
    with col11:
        ts = st.number_input(
            "TS (%)",
            min_value=0.0,
            max_value=1.0,
            value=float(st.session_state.get("bt_wfs_ts", 0.05)),
            step=0.01,
            format="%.3f",
            key="bt_wfs_ts",
        )
    with col12:
        atr_ts = st.number_input(
            "ATR TS (0=désactivé)",
            min_value=0.0,
            max_value=10.0,
            value=float(st.session_state.get("bt_wfs_atr_ts", 2.0)),
            step=0.5,
            format="%.1f",
            key="bt_wfs_atr_ts",
            help="Multiplicateur ATR pour trailing stop adaptatif. 0 = désactivé (utilise TS fixe). "
                 "2.0 recommandé pour microcaps. stop = peak - N×ATR_20.",
        )

    col13, col14, col15 = st.columns(3)
    with col13:
        all_symbols_wf = st.checkbox(
            "Univers entier (`--all-symbols`)",
            value=bool(st.session_state.get("bt_wfs_all_symbols", False)),
            key="bt_wfs_all_symbols",
        )

    output_dir = "artifacts/sentiment_walk_forward"

    options = WalkForwardSentimentOptions(
        start=start.strip(),
        end=end.strip(),
        top_n=int(top_n),
        horizons=horizons.strip() or "5,10,20",
        min_train_days=int(min_train_days),
        test_days=int(test_days),
        max_positions=int(max_positions),
        equity=float(equity),
        tp=float(tp),
        ts=float(ts),
        atr_ts=float(atr_ts),
        fees=float(fees),
        output_dir=output_dir,
        all_symbols=bool(all_symbols_wf),
        capital_preset_key=None,
    )
    st.code(
        format_command_for_display(build_backtesting_command("walk-forward-sentiment", options)),
        language="powershell",
    )
    return options


def _render_latest_artifacts() -> None:
    out_dir = PROJECT_ROOT / "artifacts" / "backtesting"
    equity_curve = out_dir / "equity_curve.png"
    trades_csv = out_dir / "trades.csv"

    if not equity_curve.exists() and not trades_csv.exists():
        return

    st.markdown("**Derniers artefacts backtesting détectés**")
    col1, col2 = st.columns([2, 3])
    with col1:
        if equity_curve.exists():
            st.image(str(equity_curve), caption="Equity curve la plus récente")
        else:
            st.info("Aucune equity curve PNG détectée.")
    with col2:
        if trades_csv.exists():
            try:
                trades_df = pd.read_csv(trades_csv)
                st.caption(f"`{trades_csv}` — {len(trades_df)} ligne(s)")
                st.dataframe(trades_df.head(200), use_container_width=True, hide_index=True)
            except Exception as exc:
                st.warning(f"Impossible de lire `trades.csv` : {exc}")
        else:
            st.info("Aucun `trades.csv` détecté.")


def _resolve_run_dir(run_record: dict[str, object]) -> Path | None:
    stdout_path = str(run_record.get("stdout_path", "") or "")
    if not stdout_path:
        return None
    path = Path(stdout_path)
    return path.parent if path.exists() or path.parent.exists() else None


def _resolve_run_artifact_path(run_dir: Path, filename: str) -> Path:
    nested_path = run_dir / "artifacts" / filename
    if nested_path.exists():
        return nested_path
    root_path = run_dir / filename
    if root_path.exists():
        return root_path
    return nested_path


def _load_run_report(run_record: dict[str, object]) -> dict[str, object] | None:
    run_dir = _resolve_run_dir(run_record)
    if run_dir is None:
        return None
    report_path = _resolve_run_artifact_path(run_dir, "report.json")
    signature = _file_cache_signature(report_path)
    if signature is None:
        return None
    payload = _read_cached_json_file(*signature)
    if payload is None:
        st.warning("Impossible de lire le rapport JSON du run.")
    return payload


def _load_equity_curve_df(run_record: dict[str, object]) -> pd.DataFrame:
    run_dir = _resolve_run_dir(run_record)
    if run_dir is None:
        return pd.DataFrame(columns=["trade_date", "portfolio_value"])
    equity_curve_csv = _resolve_run_artifact_path(run_dir, "equity_curve.csv")
    signature = _file_cache_signature(equity_curve_csv)
    if signature is None:
        return pd.DataFrame(columns=["trade_date", "portfolio_value"])
    try:
        df = _read_cached_csv_file(*signature).copy()
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
            df = df.sort_values("trade_date", kind="stable")
        return df
    except Exception as exc:
        st.warning(f"Impossible de lire l'equity curve du run : {exc}")
        return pd.DataFrame(columns=["trade_date", "portfolio_value"])


def _load_run_trades_df(run_record: dict[str, object]) -> pd.DataFrame:
    run_dir = _resolve_run_dir(run_record)
    if run_dir is None:
        return pd.DataFrame()
    trades_csv = _resolve_run_artifact_path(run_dir, "trades.csv")
    signature = _file_cache_signature(trades_csv)
    if signature is None:
        return pd.DataFrame()
    try:
        df = _read_cached_csv_file(*signature).copy()
        for column_name in (
            "trade_date",
            "signal_date",
            "execution_date",
            "entry_date",
            "exit_date",
            "replay_exit_date",
        ):
            if column_name in df.columns:
                df[column_name] = pd.to_datetime(df[column_name], errors="coerce")
        return df
    except Exception as exc:
        st.warning(f"Impossible de lire les trades du run : {exc}")
        return pd.DataFrame()


def _load_market_regimes_df(run_record: dict[str, object]) -> pd.DataFrame:
    run_dir = _resolve_run_dir(run_record)
    if run_dir is None:
        return pd.DataFrame(columns=["trade_date", "market_regime"])
    market_regimes_csv = _resolve_run_artifact_path(run_dir, "market_regimes.csv")
    signature = _file_cache_signature(market_regimes_csv)
    if signature is None:
        return pd.DataFrame(columns=["trade_date", "market_regime"])
    try:
        df = _read_cached_csv_file(*signature).copy()
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        return df
    except Exception as exc:
        st.warning(f"Impossible de lire les régimes marché du run : {exc}")
        return pd.DataFrame(columns=["trade_date", "market_regime"])


def _format_position_quantity(quantity: float) -> str:
    rounded_quantity = round(float(quantity), 8)
    if abs(rounded_quantity - round(rounded_quantity)) < 1e-8:
        return str(int(round(rounded_quantity)))
    return f"{rounded_quantity:.4f}".rstrip("0").rstrip(".")


def _format_position_notional(amount: float) -> str:
    return f"${float(amount):,.2f}"


def _resolve_trade_entry_notional(trade: object) -> float | None:
    entry_cost = getattr(trade, "entry_cost", float("nan"))
    if pd.notna(entry_cost):
        resolved_entry_cost = abs(float(entry_cost))
        if resolved_entry_cost >= 1e-8:
            return resolved_entry_cost
    entry_price = getattr(trade, "entry_price", float("nan"))
    quantity = getattr(trade, "quantity", float("nan"))
    if pd.notna(entry_price) and pd.notna(quantity):
        resolved_notional = abs(float(quantity)) * float(entry_price)
        if resolved_notional >= 1e-8:
            return resolved_notional
    return None


def _register_position_delta(
    position_deltas: dict[pd.Timestamp, dict[str, float]],
    trade_date: pd.Timestamp,
    symbol: str,
    quantity_delta: float,
) -> None:
    per_day = position_deltas.setdefault(trade_date, {})
    per_day[symbol] = per_day.get(symbol, 0.0) + float(quantity_delta)


def _build_position_detail_text(symbol: str, quantity: float, entry_notional: float | None) -> str:
    quantity_text = _format_position_quantity(quantity)
    if entry_notional is None or not pd.notna(entry_notional) or abs(float(entry_notional)) < 1e-8:
        return f"{symbol} ({quantity_text})"
    return f"{symbol} ({quantity_text} | {_format_position_notional(float(entry_notional))})"


def _build_daily_portfolio_snapshot_df(
    equity_curve_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    market_regimes_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    columns = [
        "trade_date",
        "market_regime",
        "portfolio_value",
        "open_positions",
        "position_units_total",
        "held_symbols",
        "positions_detail",
    ]
    if equity_curve_df.empty or not {"trade_date", "portfolio_value"}.issubset(equity_curve_df.columns):
        return pd.DataFrame(columns=columns)

    equity_df = equity_curve_df[["trade_date", "portfolio_value"]].copy()
    equity_df["trade_date"] = pd.to_datetime(equity_df["trade_date"], errors="coerce").dt.normalize()
    equity_df["portfolio_value"] = pd.to_numeric(equity_df["portfolio_value"], errors="coerce")
    equity_df = equity_df.dropna(subset=["trade_date"]).sort_values("trade_date", kind="stable")
    equity_df = equity_df.drop_duplicates(subset=["trade_date"], keep="last")
    if equity_df.empty:
        return pd.DataFrame(columns=columns)

    regime_by_date: dict[pd.Timestamp, str] = {}
    if market_regimes_df is not None and not market_regimes_df.empty:
        normalized_regimes_df = market_regimes_df.copy()
        if "trade_date" in normalized_regimes_df.columns:
            normalized_regimes_df["trade_date"] = pd.to_datetime(
                normalized_regimes_df["trade_date"], errors="coerce"
            ).dt.normalize()
        if {"trade_date", "market_regime"}.issubset(normalized_regimes_df.columns):
            normalized_regimes_df = normalized_regimes_df.dropna(subset=["trade_date"])
            normalized_regimes_df = normalized_regimes_df.drop_duplicates(subset=["trade_date"], keep="last")
            regime_by_date = {
                pd.Timestamp(row.trade_date).normalize(): str(row.market_regime or "").strip() or "—"
                for row in normalized_regimes_df.itertuples(index=False)
            }

    position_deltas: dict[pd.Timestamp, dict[str, float]] = {}
    position_notional_deltas: dict[pd.Timestamp, dict[str, float]] = {}
    if not trades_df.empty and "symbol" in trades_df.columns:
        normalized_trades_df = trades_df.copy()
        for column_name in ("execution_date", "entry_date", "trade_date", "exit_date", "replay_exit_date"):
            if column_name in normalized_trades_df.columns:
                normalized_trades_df[column_name] = pd.to_datetime(
                    normalized_trades_df[column_name], errors="coerce"
                ).dt.normalize()
        if "execution_date" not in normalized_trades_df.columns:
            if "entry_date" in normalized_trades_df.columns:
                normalized_trades_df["execution_date"] = normalized_trades_df["entry_date"]
            elif "trade_date" in normalized_trades_df.columns:
                normalized_trades_df["execution_date"] = normalized_trades_df["trade_date"]
        if "exit_date" not in normalized_trades_df.columns and "replay_exit_date" in normalized_trades_df.columns:
            normalized_trades_df["exit_date"] = normalized_trades_df["replay_exit_date"]
        normalized_trades_df["quantity"] = pd.to_numeric(
            normalized_trades_df.get("quantity", pd.Series(index=normalized_trades_df.index, dtype="float64")),
            errors="coerce",
        )

        for trade in normalized_trades_df.itertuples(index=False):
            symbol = str(getattr(trade, "symbol", "") or "").strip()
            execution_date = getattr(trade, "execution_date", pd.NaT)
            quantity = getattr(trade, "quantity", float("nan"))
            if not symbol or pd.isna(execution_date) or pd.isna(quantity):
                continue
            quantity_value = float(quantity)
            if abs(quantity_value) < 1e-8:
                continue
            execution_ts = pd.Timestamp(execution_date).normalize()
            _register_position_delta(position_deltas, execution_ts, symbol, quantity_value)
            entry_notional = _resolve_trade_entry_notional(trade)
            if entry_notional is not None:
                _register_position_delta(position_notional_deltas, execution_ts, symbol, entry_notional)

            exit_date = getattr(trade, "exit_date", pd.NaT)
            if not pd.isna(exit_date):
                exit_ts = pd.Timestamp(exit_date).normalize()
                _register_position_delta(position_deltas, exit_ts, symbol, -quantity_value)
                if entry_notional is not None:
                    _register_position_delta(position_notional_deltas, exit_ts, symbol, -entry_notional)

    active_positions: dict[str, float] = {}
    active_position_notionals: dict[str, float] = {}
    snapshot_rows: list[dict[str, object]] = []
    for equity_row in equity_df.itertuples(index=False):
        trade_date = pd.Timestamp(equity_row.trade_date).normalize()
        for symbol, delta in sorted(position_deltas.get(trade_date, {}).items()):
            updated_quantity = active_positions.get(symbol, 0.0) + float(delta)
            if abs(updated_quantity) < 1e-8:
                active_positions.pop(symbol, None)
            else:
                active_positions[symbol] = updated_quantity
        for symbol, delta in sorted(position_notional_deltas.get(trade_date, {}).items()):
            updated_notional = active_position_notionals.get(symbol, 0.0) + float(delta)
            if abs(updated_notional) < 1e-8:
                active_position_notionals.pop(symbol, None)
            else:
                active_position_notionals[symbol] = updated_notional

        held_symbols = sorted(active_positions)
        positions_detail = (
            ", ".join(
                _build_position_detail_text(symbol, active_positions[symbol], active_position_notionals.get(symbol))
                for symbol in held_symbols
            )
            if held_symbols
            else "—"
        )
        snapshot_rows.append(
            {
                "trade_date": trade_date,
                "market_regime": regime_by_date.get(trade_date, "—"),
                "portfolio_value": float(equity_row.portfolio_value) if pd.notna(equity_row.portfolio_value) else float("nan"),
                "open_positions": len(held_symbols),
                "position_units_total": sum(abs(float(quantity)) for quantity in active_positions.values()),
                "held_symbols": ", ".join(held_symbols) if held_symbols else "—",
                "positions_detail": positions_detail,
            }
        )

    return pd.DataFrame(snapshot_rows, columns=columns)


def _resolve_phase2_risk_summary(
    params: dict[str, object],
    artifacts: dict[str, object],
) -> dict[str, object]:
    phase2_payload = params.get("phase2", {})
    if isinstance(phase2_payload, dict):
        risk_bridge_payload = phase2_payload.get("risk_bridge")
        if isinstance(risk_bridge_payload, dict) and risk_bridge_payload:
            return risk_bridge_payload
    return _load_json_artifact_from_paths(artifacts, "phase2_risk_summary_json") or {}


def _render_report_summary(run_record: dict[str, object]) -> bool:
    report_payload = _load_run_report(run_record)
    if not report_payload:
        return False

    summary = cast(dict[str, object], report_payload.get("summary", {}))
    params = cast(dict[str, object], report_payload.get("params", {}))
    artifacts = cast(dict[str, object], report_payload.get("artifacts", {}))
    diagnostics = cast(dict[str, object], report_payload.get("diagnostics", {}))
    fidelity = cast(dict[str, object], report_payload.get("fidelity", {}))
    corporate_actions = cast(dict[str, object], report_payload.get("corporate_actions", {}))
    trade_export = cast(dict[str, object], report_payload.get("trade_export", {}))

    st.markdown("**📌 KPIs du rapport**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Valeur finale", f"${_to_float(summary.get('final_value')):,.2f}")
    col2.metric("Rendement total", f"{_to_float(summary.get('total_return_pct')):.2f}%")
    col3.metric("Sharpe Ratio", f"{_to_float(summary.get('sharpe_ratio')):.3f}")
    col4.metric("Max Drawdown", f"{_to_float(summary.get('max_drawdown_pct')):.2f}%")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Trades clôturés", _to_int(summary.get("total_trades")))
    col6.metric("Win Rate", f"{_to_float(summary.get('win_rate_pct')):.1f}%")
    col7.metric("Durée moy. (j)", f"{_to_float(summary.get('avg_trade_duration_days')):.1f}")
    col8.metric("Profit Factor", f"{_to_float(summary.get('profit_factor')):.2f}")

    # Phase A.5/A.6 (refactor) — métriques de risque enrichies (Calmar, Ulcer,
    # Sortino, CAGR) + risk-free utilisé pour Sharpe/Sortino. Tous "—" si
    # absents (ex : ancien rapport antérieur au refactor).
    st.markdown("**📊 Métriques avancées (Phase A/D refactor)**")

    def _format_calmar(value: object) -> str:
        if isinstance(value, str):  # sentinel "inf"
            return "∞" if value.lower().startswith("inf") else value
        try:
            num = float(cast(Any, value))
        except (TypeError, ValueError):
            return "—"
        if num != num or num in (float("inf"), float("-inf")):  # NaN / inf
            return "∞" if num > 0 else "—"
        return f"{num:.3f}"

    extra_col1, extra_col2, extra_col3, extra_col4 = st.columns(4)
    extra_col1.metric("CAGR", f"{_to_float(summary.get('cagr_pct')):.2f}%")
    extra_col2.metric("Sortino", f"{_to_float(summary.get('sortino_ratio')):.3f}")
    extra_col3.metric("Calmar", _format_calmar(summary.get("calmar_ratio")))
    extra_col4.metric("Ulcer Index", f"{_to_float(summary.get('ulcer_index')):.3f}")

    extra_col5, extra_col6, extra_col7, extra_col8 = st.columns(4)
    extra_col5.metric(
        "Dividendes encaissés",
        f"${_to_float(summary.get('dividends_received')):,.2f}",
    )
    extra_col6.metric(
        "Rendement total (avec div.)",
        f"{_to_float(summary.get('total_return_with_dividends_pct')):.2f}%",
    )
    extra_col7.metric(
        "Risk-free rate utilisé",
        f"{_to_float(summary.get('risk_free_rate')) * 100:.2f}%",
    )
    extra_col8.metric("Capital initial", f"${_to_float(summary.get('initial_equity')):,.0f}")

    phase2_risk_summary = _resolve_phase2_risk_summary(params, artifacts)
    if phase2_risk_summary:
        st.markdown("**🛡️ Phase 2 — régime / macro**")
        risk_col1, risk_col2, risk_col3, risk_col4 = st.columns(4)
        risk_col1.metric(
            "Régime activé",
            "oui" if bool(phase2_risk_summary.get("regime_enabled", False)) else "non",
        )
        risk_col2.metric("Snapshots régime", _to_int(phase2_risk_summary.get("snapshot_dates")))
        risk_col3.metric(
            "Macro indisponible",
            _to_int(phase2_risk_summary.get("macro_missing_dates_count")),
        )
        risk_col4.metric(
            "Entrées bloquées régime",
            _to_int(phase2_risk_summary.get("entries_blocked_by_regime")),
        )

        risk_col5, risk_col6, risk_col7, risk_col8 = st.columns(4)
        risk_col5.metric("Entries acceptées", _to_int(phase2_risk_summary.get("entries_accepted")))
        risk_col6.metric("Signals générés", _to_int(phase2_risk_summary.get("signals_generated")))
        risk_col7.metric(
            "Slots évités",
            _to_int(phase2_risk_summary.get("slots_rejected_avoided")),
        )
        macro_quality_distribution = phase2_risk_summary.get("macro_data_quality_distribution", {})
        macro_quality_summary = "—"
        if isinstance(macro_quality_distribution, dict) and macro_quality_distribution:
            macro_quality_summary = ", ".join(
                f"{key}={_to_int(value)}" for key, value in macro_quality_distribution.items()
            )
        risk_col8.metric("Qualité macro", macro_quality_summary)

        macro_missing_dates = phase2_risk_summary.get("macro_missing_dates", [])
        if isinstance(macro_missing_dates, list) and macro_missing_dates:
            preview = ", ".join(str(value) for value in macro_missing_dates[:10])
            if len(macro_missing_dates) > 10:
                preview += f" … (+{len(macro_missing_dates) - 10})"
            st.caption(f"Séances marquées `data_quality=missing` : {preview}")

    if corporate_actions:
        st.markdown("**🏦 Corporate actions / convention prix**")
        ca_col1, ca_col2, ca_col3, ca_col4 = st.columns(4)
        ca_col1.metric(
            "Prix split-adjusted",
            "oui" if bool(corporate_actions.get("split_adjusted_prices", False)) else "non",
        )
        ca_col2.metric(
            "Dividendes dans les prix",
            "oui" if bool(corporate_actions.get("dividends_reflected_in_prices", False)) else "non",
        )
        ca_col3.metric(
            "Cash dividendes",
            f"${_to_float(corporate_actions.get('dividend_cash_total')):,.2f}",
        )
        ca_col4.metric(
            "Cash in lieu",
            f"${_to_float(corporate_actions.get('cash_in_lieu_total')):,.2f}",
        )
        st.caption(
            "Convention unifiée : `stock_bars_daily` est consommée en prix ajustés des splits, "
            "et les flux cash corporate actions restent séparés dans `portfolio_cash_ledger`."
        )

    if trade_export:
        st.markdown("**🧾 Export trades réconcilié**")
        trade_col1, trade_col2, trade_col3, trade_col4 = st.columns(4)
        trade_col1.metric("Source export", _coerce_metric_text(trade_export.get("source")))
        trade_col2.metric("Lignes exportées", _to_int(trade_export.get("row_count")))
        trade_col3.metric("Trades clôturés", _to_int(trade_export.get("export_closed_rows")))
        trade_col4.metric("Écarts legacy", _to_int(trade_export.get("legacy_unmatched_rows")))
        if _to_int(trade_export.get("legacy_unmatched_rows")) > 0:
            st.caption(
                "`trades.csv` est désormais reconstruit depuis la vérité pipeline Phase 3→7 ; "
                "`legacy_unmatched_rows` mesure l'écart avec l'ancien export basé sur `closed_trades_df`."
            )

    # Phase A.4 — métadonnées de reproductibilité.
    run_metadata = report_payload.get("run_metadata")
    if isinstance(run_metadata, dict) and run_metadata:
        with st.expander("🧬 Métadonnées de reproductibilité (Phase A.4)", expanded=False):
            st.caption(
                "Conservées dans `report.json[run_metadata]` pour rejouer un run "
                "à l'identique (git SHA, version Python, hash dataset, seed)."
            )
            st.json(run_metadata)

    if fidelity:
        st.markdown("**🧪 Fidélité observable du run**")
        fidelity_summary = fidelity.get("summary", {})
        if not isinstance(fidelity_summary, dict):
            fidelity_summary = {}
        fidelity_col1, fidelity_col2, fidelity_col3, fidelity_col4 = st.columns(4)
        fidelity_col1.metric("Strict PIT demandé", "oui" if bool(fidelity.get("strict_pit_requested", False)) else "non")
        fidelity_col2.metric("Strict PIT satisfait", "oui" if bool(fidelity.get("strict_pit_satisfied", False)) else "non")
        fidelity_col3.metric("Run dégradé", "oui" if bool(fidelity.get("degraded", False)) else "non")
        degraded_components = fidelity_summary.get("degraded_components", [])
        fidelity_col4.metric(
            "Composants dégradés",
            len(degraded_components) if isinstance(degraded_components, list) else 0,
        )

        component_rows = _build_fidelity_component_rows(fidelity)
        if not component_rows.empty:
            with st.expander("Vue composant par composant", expanded=False):
                st.dataframe(component_rows, use_container_width=True, hide_index=True)

        coverage_rows = _build_fidelity_coverage_rows(fidelity)
        if not coverage_rows.empty:
            with st.expander("Coverage Sprint 1 — sentiment / ML", expanded=False):
                st.dataframe(coverage_rows, use_container_width=True, hide_index=True)

        provenance_rows = _build_fidelity_provenance_rows(fidelity)
        if not provenance_rows.empty:
            with st.expander("Provenance Sprint 2 — scores / sentiment / ML", expanded=False):
                st.dataframe(provenance_rows, use_container_width=True, hide_index=True)

        ml_cause_rows = _build_fidelity_ml_cause_rows(fidelity)
        if not ml_cause_rows.empty:
            with st.expander("Causes ML normalisées", expanded=False):
                st.dataframe(ml_cause_rows, use_container_width=True, hide_index=True)

        degraded_reason_details = fidelity.get("degraded_reason_details", [])
        if isinstance(degraded_reason_details, list) and degraded_reason_details:
            with st.expander("Motifs normalisés de dégradation", expanded=False):
                st.json(degraded_reason_details)

    replay_diagnostic_payload = _load_json_artifact_from_paths(artifacts, "replay_diagnostic_summary_json")
    if replay_diagnostic_payload:
        st.markdown("**🗓️ Replay diagnostique court par séance**")
        diag_col1, diag_col2, diag_col3 = st.columns(3)
        diag_col1.metric("Séances diagnostiquées", _to_int(replay_diagnostic_payload.get("session_count")))
        diag_col2.metric("Séances dégradées", _to_int(replay_diagnostic_payload.get("degraded_session_count")))
        diag_col3.metric("Mode moteur", _coerce_metric_text(replay_diagnostic_payload.get("engine_mode")))
        replay_rows = _build_replay_diagnostic_session_rows(replay_diagnostic_payload)
        if not replay_rows.empty:
            with st.expander("Aperçu du diagnostic par séance", expanded=False):
                st.dataframe(replay_rows, use_container_width=True, hide_index=True)
        # ── Drill-down analytique composant → symbole (post-Sprint 2)
        sessions_list = replay_diagnostic_payload.get("sessions", [])
        if isinstance(sessions_list, list) and sessions_list:
            with st.expander("🔍 Drill-down composant → symbole", expanded=False):
                _DRILLDOWN_COMPONENTS = ["sentiment", "ml", "scores", "walk_forward", "risk", "execution"]
                available_degraded_components: set[str] = set()
                for _s in sessions_list:
                    if isinstance(_s, dict):
                        for _c in _s.get("degraded_components", []):
                            available_degraded_components.add(str(_c))
                filter_components = sorted(available_degraded_components) if available_degraded_components else _DRILLDOWN_COMPONENTS
                selected_component = st.selectbox(
                    "Composant à analyser",
                    options=["(tous)"] + filter_components,
                    key="drilldown_component_select",
                )
                drilldown_rows: list[dict[str, object]] = []
                for session in sessions_list:
                    if not isinstance(session, dict):
                        continue
                    trade_date = session.get("trade_date", "")
                    critical_symbols = session.get("critical_symbols", [])
                    if not isinstance(critical_symbols, list):
                        continue
                    for sym_payload in critical_symbols:
                        if not isinstance(sym_payload, dict):
                            continue
                        sym_components = [str(c) for c in sym_payload.get("components", [])]
                        if selected_component != "(tous)" and selected_component not in sym_components:
                            continue
                        drilldown_rows.append(
                            {
                                "Séance": trade_date,
                                "Symbole": sym_payload.get("symbol", ""),
                                "Sélectionné": "oui" if bool(sym_payload.get("selected", False)) else "non",
                                "Composants dégradés": ", ".join(sym_components),
                                "Raisons": ", ".join(str(r) for r in sym_payload.get("reasons", [])),
                                "Source score": _coerce_metric_text(sym_payload.get("score_source")),
                            }
                        )
                if drilldown_rows:
                    st.dataframe(drilldown_rows, use_container_width=True, hide_index=True)
                else:
                    st.info("Aucun symbole critique trouvé pour ce filtre composant.")
        with st.expander("Payload brut replay_diagnostic_summary.json", expanded=False):
            st.json(replay_diagnostic_payload)

    # ── Matrice fidélité symbole × état PIT (anomalie 5.5)
    fidelity_symbol_matrix_payload = _load_json_artifact_from_paths(artifacts, "fidelity_symbol_matrix_json")
    if fidelity_symbol_matrix_payload:
        st.markdown("**🗺️ Matrice fidélité symbole × état PIT**")
        matrix_col1, matrix_col2, matrix_col3 = st.columns(3)
        matrix_col1.metric("Symboles analysés", _to_int(fidelity_symbol_matrix_payload.get("symbol_count")))
        matrix_col2.metric("Symboles dégradés", _to_int(fidelity_symbol_matrix_payload.get("degraded_symbol_count")))
        matrix_col3.metric("Mode moteur", _coerce_metric_text(fidelity_symbol_matrix_payload.get("engine_mode")))
        symbol_matrix_rows = _build_fidelity_symbol_matrix_rows(fidelity_symbol_matrix_payload)
        if not symbol_matrix_rows.empty:
            with st.expander("Aperçu de la matrice symbole × état PIT", expanded=False):
                st.dataframe(symbol_matrix_rows, use_container_width=True, hide_index=True)
        with st.expander("Payload brut fidelity_symbol_matrix.json", expanded=False):
            st.json(fidelity_symbol_matrix_payload)

    candidate_target_payload = _load_json_artifact_from_paths(artifacts, "candidate_target_parity_summary_json")
    if candidate_target_payload:
        st.markdown("**🎯 Parité candidate → target**")
        parity_col1, parity_col2, parity_col3 = st.columns(3)
        parity_col1.metric("Séances comparées", _to_int(candidate_target_payload.get("session_count")))
        parity_col2.metric("Séances divergentes", _to_int(candidate_target_payload.get("diverged_session_count")))
        parity_col3.metric("Mode Phase 2", _coerce_metric_text(candidate_target_payload.get("phase2_mode")))
        parity_rows = _build_candidate_target_parity_rows(candidate_target_payload)
        if not parity_rows.empty:
            with st.expander("Aperçu candidate → target", expanded=False):
                st.dataframe(parity_rows, use_container_width=True, hide_index=True)
        with st.expander("Payload brut candidate_target_parity_summary.json", expanded=False):
            st.json(candidate_target_payload)

    compare_to_live_payload = _load_json_artifact_from_paths(artifacts, "compare_to_live_summary_json")
    if compare_to_live_payload:
        st.markdown("**🛰️ Compare-to-live professionnel**")
        compare_col1, compare_col2, compare_col3 = st.columns(3)
        compare_col1.metric("Séances comparées", _to_int(compare_to_live_payload.get("session_count")))
        compare_col2.metric("Séances live exploitables", _to_int(compare_to_live_payload.get("live_session_count")))
        global_scores = compare_to_live_payload.get("global_scores", {})
        compare_col3.metric(
            "Score global",
            f"{_to_float(global_scores.get('fidelity_score') if isinstance(global_scores, dict) else 0.0):.3f}",
        )
        compare_rows = _build_compare_to_live_rows(compare_to_live_payload)
        if not compare_rows.empty:
            with st.expander("Aperçu compare-to-live", expanded=False):
                st.dataframe(compare_rows, use_container_width=True, hide_index=True)
        with st.expander("Payload brut compare_to_live_summary.json", expanded=False):
            st.json(compare_to_live_payload)

    fidelity_baseline_snapshot_payload = _load_json_artifact_from_paths(artifacts, "fidelity_baseline_snapshot_json")
    if fidelity_baseline_snapshot_payload:
        st.markdown("**🧷 Snapshot baseline fidélité (Sprint 6)**")
        snapshot_col1, snapshot_col2, snapshot_col3 = st.columns(3)
        snapshot_col1.metric("Mode moteur", _coerce_metric_text(fidelity_baseline_snapshot_payload.get("engine_mode")))
        snapshot_col2.metric(
            "Fenêtre",
            "{} → {}".format(
                _coerce_metric_text(
                    fidelity_baseline_snapshot_payload.get("requested_window", {}).get("start_date")
                    if isinstance(fidelity_baseline_snapshot_payload.get("requested_window"), dict)
                    else None
                ),
                _coerce_metric_text(
                    fidelity_baseline_snapshot_payload.get("requested_window", {}).get("end_date")
                    if isinstance(fidelity_baseline_snapshot_payload.get("requested_window"), dict)
                    else None
                ),
            ),
        )
        snapshot_col3.metric(
            "Sections disponibles",
            sum(
                1
                for value in fidelity_baseline_snapshot_payload.get("available_sections", {}).values()
                if bool(value)
            ) if isinstance(fidelity_baseline_snapshot_payload.get("available_sections"), dict) else 0,
        )
        snapshot_rows = _build_fidelity_baseline_snapshot_rows(fidelity_baseline_snapshot_payload)
        if not snapshot_rows.empty:
            with st.expander("Aperçu snapshot baseline fidélité", expanded=False):
                st.dataframe(snapshot_rows, use_container_width=True, hide_index=True)
        with st.expander("Payload brut fidelity_baseline_snapshot.json", expanded=False):
            st.json(fidelity_baseline_snapshot_payload)

    fidelity_baseline_comparison_payload = _load_json_artifact_from_paths(artifacts, "fidelity_baseline_comparison_json")
    if fidelity_baseline_comparison_payload:
        st.markdown("**🧪 Non-régression fidélité vs baseline**")
        baseline_col1, baseline_col2, baseline_col3, baseline_col4 = st.columns(4)
        baseline_col1.metric("Statut", _coerce_metric_text(fidelity_baseline_comparison_payload.get("status")))
        baseline_col2.metric("Baseline", _coerce_metric_text(fidelity_baseline_comparison_payload.get("baseline_id")))
        baseline_col3.metric("Checks", _to_int(fidelity_baseline_comparison_payload.get("checked_count")))
        baseline_col4.metric("Échecs", _to_int(fidelity_baseline_comparison_payload.get("failed_count")))
        fidelity_baseline_rows = _build_fidelity_baseline_check_rows(fidelity_baseline_comparison_payload)
        if not fidelity_baseline_rows.empty:
            with st.expander("Aperçu des checks baseline fidélité", expanded=False):
                st.dataframe(fidelity_baseline_rows, use_container_width=True, hide_index=True)
        with st.expander("Payload brut fidelity_baseline_comparison.json", expanded=False):
            st.json(fidelity_baseline_comparison_payload)

    execution_broker_like_payload = _load_json_artifact_from_paths(artifacts, "execution_broker_like_summary_json")
    if execution_broker_like_payload:
        st.markdown("**🏦 Exécution broker-like enrichie**")
        broker_col1, broker_col2, broker_col3, broker_col4 = st.columns(4)
        broker_col5, broker_col6, broker_col7, broker_col8 = st.columns(4)
        broker_col1.metric("Ordres journalisés", _to_int(execution_broker_like_payload.get("order_count")))
        broker_col2.metric(
            "Ordres filled",
            _to_int(
                execution_broker_like_payload.get("order_status_counts", {}).get("FILLED")
                if isinstance(execution_broker_like_payload.get("order_status_counts"), dict)
                else 0
            ),
        )
        broker_col3.metric(
            "Partial fills",
            _to_int(
                execution_broker_like_payload.get("broker_semantics", {}).get("partial_fill_orders")
                if isinstance(execution_broker_like_payload.get("broker_semantics"), dict)
                else 0
            ),
        )
        broker_col4.metric(
            "Ordres canceled",
            _to_int(
                execution_broker_like_payload.get("order_status_counts", {}).get("CANCELED")
                if isinstance(execution_broker_like_payload.get("order_status_counts"), dict)
                else 0
            ),
        )
        broker_col5.metric(
            "Retries",
            _to_int(
                execution_broker_like_payload.get("broker_semantics", {}).get("retry_orders")
                if isinstance(execution_broker_like_payload.get("broker_semantics"), dict)
                else 0
            ),
        )
        broker_col6.metric(
            "Ordres rejetés",
            _to_int(
                execution_broker_like_payload.get("broker_semantics", {}).get("rejected_orders")
                if isinstance(execution_broker_like_payload.get("broker_semantics"), dict)
                else 0
            ),
        )
        broker_col7.metric(
            "Ordres timeout",
            _to_int(
                execution_broker_like_payload.get("broker_semantics", {}).get("timed_out_orders")
                if isinstance(execution_broker_like_payload.get("broker_semantics"), dict)
                else 0
            ),
        )
        broker_col8.metric(
            "Ordres stale",
            _to_int(
                execution_broker_like_payload.get("broker_state_counts", {}).get("stale")
                if isinstance(execution_broker_like_payload.get("broker_state_counts"), dict)
                else 0
            ),
        )
        broker_rows = _build_execution_broker_like_session_rows(execution_broker_like_payload)
        if not broker_rows.empty:
            with st.expander("Aperçu lifecycle broker-like par séance", expanded=False):
                st.dataframe(broker_rows, use_container_width=True, hide_index=True)
        with st.expander("Payload brut execution_broker_like_summary.json", expanded=False):
            st.json(execution_broker_like_payload)

    # Glossaire local pour rappel des indicateurs (Phase G3).
    with st.expander("📚 Glossaire — comprendre les indicateurs", expanded=False):
        st.markdown(
            "- **Sharpe** : (rendement excédentaire moyen) / volatilité annualisée. "
            "≥ 1 = correct, ≥ 2 = excellent.\n"
            "- **Sortino** : variante du Sharpe ne pénalisant que la volatilité négative.\n"
            "- **Calmar** : CAGR / |Max Drawdown|. Mesure le rendement par unité de "
            "douleur historique. `∞` = aucun drawdown observé sur la période.\n"
            "- **Ulcer Index** : `sqrt(mean(drawdown²))`. Pénalise la durée et la "
            "profondeur des drawdowns (Martin & McCann, 1989).\n"
            "- **Profit Factor** : somme des gains / |somme des pertes|. ≥ 1.5 = sain.\n"
            "- **Risk-free rate** : taux annualisé déduit avant Sharpe/Sortino. "
            "Doit refléter le coût d'opportunité (ex T-Bill 4 %).\n"
            "- **CAGR** : taux de croissance annuel composé sur la période.\n"
            "- **Dividendes encaissés** : crédités séparément depuis "
            "`portfolio_cash_ledger`. Le rendement total *avec* dividendes inclut "
            "ce flux."
        )

    with st.expander("⚙️ Paramètres du run utilisés", expanded=False):
        if params:
            st.json(params)
        else:
            st.info("Aucun paramètre structuré disponible pour ce run.")

    if artifacts:
        with st.expander("📦 Artefacts structurés du run", expanded=False):
            st.json(artifacts)

    if diagnostics:
        with st.expander("🧭 Diagnostics des contraintes de compte", expanded=False):
            st.json(diagnostics)
    return True


def _render_live_artifacts(run_record: dict[str, object]) -> bool:
    equity_curve_df = _load_equity_curve_df(run_record)
    trades_df = _load_run_trades_df(run_record)
    market_regimes_df = _load_market_regimes_df(run_record)
    daily_snapshot_df = _build_daily_portfolio_snapshot_df(equity_curve_df, trades_df, market_regimes_df)
    rendered = False

    if not equity_curve_df.empty and {"trade_date", "portfolio_value"}.issubset(equity_curve_df.columns):
        rendered = True
        st.markdown("**📈 Graphique live des artefacts**")
        chart_df = equity_curve_df[["trade_date", "portfolio_value"]].dropna().copy()
        if not chart_df.empty:
            chart_df = chart_df.set_index("trade_date")
            st.line_chart(chart_df, y="portfolio_value", use_container_width=True, height=320)
            last_val = float(chart_df["portfolio_value"].iloc[-1])
            first_val = float(chart_df["portfolio_value"].iloc[0])
            delta_pct = ((last_val / first_val) - 1.0) * 100 if first_val else 0.0
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            metric_col1.metric("Points equity", len(chart_df))
            metric_col2.metric("Valeur initiale série", f"${first_val:,.2f}")
            metric_col3.metric("Variation série", f"{delta_pct:.2f}%")

    if not trades_df.empty:
        rendered = True
        st.markdown("**🧾 Aperçu des trades du run**")
        st.caption(f"{len(trades_df)} ligne(s) dans `trades.csv`.")
        st.dataframe(trades_df.head(200), use_container_width=True, hide_index=True)

    if not daily_snapshot_df.empty:
        rendered = True
        st.markdown("**📅 Journal quotidien portefeuille / positions**")
        st.caption(
            "Reconstruction en fin de séance à partir de `equity_curve.csv` et `trades.csv` : "
            "positions encore détenues, détail des titres (quantité + montant d'entrée cumulé quand disponible) "
            "et valeur de portefeuille."
        )
        display_df = daily_snapshot_df.rename(
            columns={
                "trade_date": "Date",
                "market_regime": "Régime",
                "portfolio_value": "Valeur portefeuille",
                "open_positions": "Positions ouvertes",
                "position_units_total": "Quantité totale",
                "held_symbols": "Titres détenus",
                "positions_detail": "Détail positions",
            }
        ).copy()
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        snapshot_csv = daily_snapshot_df.copy()
        snapshot_csv["trade_date"] = snapshot_csv["trade_date"].dt.strftime("%Y-%m-%d")
        st.download_button(
            label="⬇️ Télécharger le journal quotidien portefeuille / positions",
            data=snapshot_csv.to_csv(index=False).encode("utf-8"),
            file_name=f"{_coerce_metric_text(run_record.get('run_id')).replace('—', 'backtest')}_daily_portfolio_snapshot.csv",
            mime="text/csv",
            key=f"download_daily_portfolio_snapshot_{_coerce_metric_text(run_record.get('run_id'))}",
        )

    return rendered


def _coerce_metric_text(value: object) -> str:
    if value is None:
        return "—"
    text = str(value).strip()
    return text or "—"


def _format_fidelity_status(status: object) -> str:
    normalized = str(status or "").strip().lower()
    return {
        "ok": "🟢 OK",
        "degraded": "🟠 Dégradé",
        "disabled": "⚪ Désactivé",
    }.get(normalized, normalized or "—")


def _build_fidelity_component_rows(fidelity: dict[str, object]) -> pd.DataFrame:
    component_status = fidelity.get("component_status", {})
    if not isinstance(component_status, dict) or not component_status:
        return pd.DataFrame()
    ordered_components = fidelity.get("components")
    if isinstance(ordered_components, list) and ordered_components:
        component_names = [str(name) for name in ordered_components if str(name) in component_status]
    else:
        component_names = list(component_status)
    rows: list[dict[str, object]] = []
    for name in component_names:
        payload = component_status.get(name)
        if not isinstance(payload, dict):
            continue
        reasons = payload.get("degraded_reasons", [])
        if not isinstance(reasons, list):
            reasons = []
        rows.append(
            {
                "Composant": name,
                "État": _format_fidelity_status(payload.get("status")),
                "Activé": "oui" if bool(payload.get("enabled", False)) else "non",
                "Motifs": ", ".join(str(reason) for reason in reasons) if reasons else "—",
            }
        )
    return pd.DataFrame(rows)


def _build_fidelity_coverage_rows(fidelity: dict[str, object]) -> pd.DataFrame:
    coverage = fidelity.get("coverage", {})
    if not isinstance(coverage, dict) or not coverage:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for component_name in ("sentiment", "ml"):
        payload = coverage.get(component_name)
        if not isinstance(payload, dict):
            continue
        missing_after = payload.get("missing_symbols_after", [])
        if not isinstance(missing_after, list):
            missing_after = []
        rows.append(
            {
                "Couverture": component_name,
                "Lignes entrée": _to_int(payload.get("rows_input")),
                "Couverture finale": f"{_to_float(payload.get('coverage_ratio_after')) * 100:.1f}%",
                "Manquants finaux": _to_int(payload.get("rows_missing_after")),
                "Symboles dégradants": ", ".join(str(symbol) for symbol in missing_after) if missing_after else "—",
            }
        )
    return pd.DataFrame(rows)


def _build_fidelity_provenance_rows(fidelity: dict[str, object]) -> pd.DataFrame:
    provenance = fidelity.get("provenance", {})
    if not isinstance(provenance, dict) or not provenance:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for component_name in ("scores", "sentiment", "ml"):
        payload = provenance.get(component_name)
        if not isinstance(payload, dict):
            continue
        source_tags = payload.get("source_tags", [])
        if not isinstance(source_tags, list):
            source_tags = []
        rows.append(
            {
                "Composant": component_name,
                "Type": _coerce_metric_text(payload.get("provenance_kind") or payload.get("requested_mode") or payload.get("effective_strategy")),
                "Source / tags": ", ".join(str(tag) for tag in source_tags) if source_tags else _coerce_metric_text(payload.get("source_table")),
                "Détail clé": _coerce_metric_text(
                    payload.get("score_column_requested")
                    or payload.get("walk_forward_artifact_path")
                    or payload.get("effective_strategy")
                ),
            }
        )
    return pd.DataFrame(rows)


def _build_fidelity_ml_cause_rows(fidelity: dict[str, object]) -> pd.DataFrame:
    provenance = fidelity.get("provenance", {})
    if not isinstance(provenance, dict):
        return pd.DataFrame()
    ml_payload = provenance.get("ml", {})
    if not isinstance(ml_payload, dict):
        return pd.DataFrame()
    cause_breakdown = ml_payload.get("missing_cause_breakdown", {})
    if not isinstance(cause_breakdown, dict) or not cause_breakdown:
        return pd.DataFrame()
    rows = [
        {
            "Cause ML": str(cause),
            "Occurrences": _to_int(count),
        }
        for cause, count in cause_breakdown.items()
    ]
    return pd.DataFrame(rows)


def _load_json_artifact_from_paths(artifacts: dict[str, object], artifact_key: str) -> dict[str, object] | None:
    artifact_path = artifacts.get(artifact_key)
    if not artifact_path:
        return None
    try:
        path = Path(str(artifact_path))
    except Exception:
        return None
    signature = _file_cache_signature(path)
    if signature is None:
        return None
    return _read_cached_json_file(*signature)


def _build_replay_diagnostic_session_rows(payload: dict[str, object]) -> pd.DataFrame:
    sessions = payload.get("sessions", [])
    if not isinstance(sessions, list) or not sessions:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        rows.append(
            {
                "Séance": _coerce_metric_text(session.get("trade_date")),
                "Candidats": _to_int(session.get("candidate_rows")),
                "Sources score": _coerce_metric_text(session.get("score_source_counts")),
                "Prédictions": _to_int(session.get("predictions_rows")),
                "Manquants sentiment": _to_int(session.get("missing_sentiment_rows")),
                "Symboles ML manquants": ", ".join(
                    str(symbol) for symbol in cast(list[object], session.get("missing_ml_symbols", []))
                ) if isinstance(session.get("missing_ml_symbols", []), list) else "—",
                "Sélections": _to_int(session.get("selected_count")),
                "Composants dégradés": ", ".join(
                    str(component) for component in cast(list[object], session.get("degraded_components", []))
                ) if isinstance(session.get("degraded_components", []), list) else "—",
                "Symbole critique": _coerce_metric_text(
                    session.get("critical_symbol", {}).get("symbol")
                    if isinstance(session.get("critical_symbol"), dict)
                    else None
                ),
                "Réf provenance": _coerce_metric_text(
                    session.get("provenance_refs", {}).get("scores_snapshot_id")
                    if isinstance(session.get("provenance_refs"), dict)
                    else None
                ),
                "Dégradée": "oui" if bool(session.get("degraded", False)) else "non",
            }
        )
    return pd.DataFrame(rows)


def _build_candidate_target_parity_rows(payload: dict[str, object]) -> pd.DataFrame:
    sessions = payload.get("sessions", [])
    if not isinstance(sessions, list) or not sessions:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        rows.append(
            {
                "Séance": _coerce_metric_text(session.get("trade_date")),
                "Statut": _coerce_metric_text(session.get("parity_status")),
                "Research sélectionnés": _to_int(session.get("research_selected_count")),
                "Targets risk": _to_int(session.get("risk_target_count")),
                "Rejets risk": _to_int(session.get("risk_rejected_count")),
                "Research only": ", ".join(str(symbol) for symbol in cast(list[object], session.get("research_only_symbols", []))) if isinstance(session.get("research_only_symbols", []), list) else "—",
                "Risk only": ", ".join(str(symbol) for symbol in cast(list[object], session.get("risk_only_symbols", []))) if isinstance(session.get("risk_only_symbols", []), list) else "—",
                "Motifs divergence": ", ".join(str(reason) for reason in cast(list[object], session.get("divergence_reasons", []))) if isinstance(session.get("divergence_reasons", []), list) else "—",
            }
        )
    return pd.DataFrame(rows)


def _build_compare_to_live_rows(payload: dict[str, object]) -> pd.DataFrame:
    sessions = payload.get("sessions", [])
    if not isinstance(sessions, list) or not sessions:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        top_divergences = session.get("top_divergences", [])
        divergence_preview = "—"
        if isinstance(top_divergences, list) and top_divergences:
            preview_parts: list[str] = []
            for item in top_divergences[:3]:
                if not isinstance(item, dict):
                    continue
                preview_parts.append(
                    f"{_coerce_metric_text(item.get('component'))}:{_coerce_metric_text(item.get('symbol'))}:{_coerce_metric_text(item.get('divergence_kind'))}"
                )
            if preview_parts:
                divergence_preview = " | ".join(preview_parts)
        rows.append(
            {
                "Séance": _coerce_metric_text(session.get("trade_date")),
                "Score fidélité": f"{_to_float(session.get('fidelity_score')):.3f}",
                "Candidats": _coerce_metric_text(
                    session.get("candidate_compare", {}).get("status")
                    if isinstance(session.get("candidate_compare"), dict)
                    else None
                ),
                "Risk live": _coerce_metric_text(
                    session.get("risk_compare", {}).get("status")
                    if isinstance(session.get("risk_compare"), dict)
                    else None
                ),
                "Targets live": _coerce_metric_text(
                    session.get("portfolio_compare", {}).get("status")
                    if isinstance(session.get("portfolio_compare"), dict)
                    else None
                ),
                "Exécution live": _coerce_metric_text(
                    session.get("execution_compare", {}).get("status")
                    if isinstance(session.get("execution_compare"), dict)
                    else None
                ),
                "Fills live": _coerce_metric_text(
                    session.get("fills_compare", {}).get("status")
                    if isinstance(session.get("fills_compare"), dict)
                    else None
                ),
                "Exits live": _coerce_metric_text(
                    session.get("exits_compare", {}).get("status")
                    if isinstance(session.get("exits_compare"), dict)
                    else None
                ),
                "PnL live": _coerce_metric_text(
                    session.get("pnl_compare", {}).get("status")
                    if isinstance(session.get("pnl_compare"), dict)
                    else None
                ),
                "Divergences clés": divergence_preview,
            }
        )
    return pd.DataFrame(rows)


def _build_fidelity_baseline_snapshot_rows(payload: dict[str, object]) -> pd.DataFrame:
    metrics = payload.get("metrics", {})
    if not isinstance(metrics, dict) or not metrics:
        return pd.DataFrame()
    rows = [
        {
            "Métrique": str(metric_name),
            "Valeur": _coerce_metric_text(metric_value),
        }
        for metric_name, metric_value in metrics.items()
    ]
    return pd.DataFrame(rows)


def _build_fidelity_baseline_check_rows(payload: dict[str, object]) -> pd.DataFrame:
    checks = payload.get("checks", [])
    if not isinstance(checks, list) or not checks:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        rows.append(
            {
                "Check": _coerce_metric_text(check.get("label") or check.get("name")),
                "Type": _coerce_metric_text(check.get("check_type")),
                "Comparaison": _coerce_metric_text(check.get("comparison")),
                "Baseline": _coerce_metric_text(check.get("baseline_value")),
                "Courant": _coerce_metric_text(check.get("current_value")),
                "Delta": _coerce_metric_text(check.get("delta")),
                "Tolérance": _coerce_metric_text(check.get("tolerance_abs")),
                "Statut": _coerce_metric_text(check.get("status")),
            }
        )
    return pd.DataFrame(rows)


def _build_fidelity_symbol_matrix_rows(payload: dict[str, object]) -> pd.DataFrame:
    """Construit un DataFrame tabulaire depuis la matrice symbole × état PIT."""
    symbols = payload.get("symbols", [])
    if not isinstance(symbols, list) or not symbols:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for entry in symbols:
        if not isinstance(entry, dict):
            continue
        rows.append(
            {
                "Symbole": _coerce_metric_text(entry.get("symbol")),
                "Séances": _to_int(entry.get("session_count")),
                "Scores": _coerce_metric_text(entry.get("scores_state")),
                "Source score": _coerce_metric_text(entry.get("score_source")),
                "Sentiment": _coerce_metric_text(entry.get("sentiment_state")),
                "ML": _coerce_metric_text(entry.get("ml_state")),
                "Causes ML": ", ".join(
                    str(c) for c in cast(list[object], entry.get("ml_missing_causes", []))
                ) if isinstance(entry.get("ml_missing_causes"), list) else "—",
                "Walk-forward": _coerce_metric_text(entry.get("walk_forward_state")),
                "Dégradé": "oui" if bool(entry.get("degraded", False)) else "non",
            }
        )
    return pd.DataFrame(rows)


def _build_execution_broker_like_session_rows(payload: dict[str, object]) -> pd.DataFrame:
    sessions = payload.get("sessions", [])
    if not isinstance(sessions, list) or not sessions:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        rows.append(
            {
                "Séance": _coerce_metric_text(session.get("trade_date")),
                "Symboles": ", ".join(str(symbol) for symbol in cast(list[object], session.get("symbols", []))) if isinstance(session.get("symbols", []), list) else "—",
                "Sélections": _to_int(session.get("selected_signals")),
                "Ordres": _to_int(session.get("orders_total")),
                "Filled": _to_int(session.get("filled_orders")),
                "Partial fills": _to_int(session.get("partial_fill_orders")),
                "Retries": _to_int(session.get("retry_orders")),
                "Rejected": _to_int(session.get("rejected_orders")),
                "Timed out": _to_int(session.get("timed_out_orders")),
                "Working": _to_int(session.get("working_orders")),
                "Held": _to_int(session.get("held_orders")),
                "Canceled": _to_int(session.get("canceled_orders")),
                "Stale": _to_int(session.get("stale_orders")),
                "Exit fills": _to_int(session.get("exit_filled_orders")),
                "Triggers": _to_int(session.get("trigger_hits")),
                "Partial fill events": _to_int(session.get("partial_fill_events")),
                "Retry events": _to_int(session.get("retry_events")),
                "Cancel events": _to_int(session.get("cancel_events")),
                "Reject events": _to_int(session.get("reject_events")),
                "Timeout events": _to_int(session.get("timeout_events")),
                "OCO cancels": _to_int(session.get("oco_cancels")),
            }
        )
    return pd.DataFrame(rows)


def _resolve_screener_artifact_summary(run_record: dict[str, object]) -> dict[str, object] | None:
    summary = run_record.get("screener_artifact_summary")
    if isinstance(summary, dict):
        return cast(dict[str, object], summary)
    artifacts_dir = run_record.get("screener_artifacts_dir")
    if not artifacts_dir:
        return None
    return build_screener_artifact_summary(str(artifacts_dir))


def _build_screener_artifact_metric_rows(summary: dict[str, object]) -> list[tuple[str, str]]:
    market_regimes = summary.get("market_regimes")
    return [
        ("Scénarios", _coerce_metric_text(summary.get("scenario_count"))),
        ("Séances", _coerce_metric_text(summary.get("trading_days"))),
        ("Fichiers détectés", _coerce_metric_text(summary.get("file_count"))),
        ("Reco objectifs", _coerce_metric_text(summary.get("objective_count"))),
        ("Baseline", _coerce_metric_text(summary.get("baseline_name"))),
        ("Résumé CSV", _coerce_metric_text(summary.get("summary_rows"))),
        ("Daily CSV", _coerce_metric_text(summary.get("daily_rows"))),
        (
            "Régimes",
            _coerce_metric_text(len(market_regimes) if isinstance(market_regimes, list) else None),
        ),
    ]


def _build_screener_artifact_objective_rows(summary: dict[str, object]) -> pd.DataFrame:
    objective_rows = summary.get("objective_recommendations")
    if not isinstance(objective_rows, list) or not objective_rows:
        return pd.DataFrame()
    frame = pd.DataFrame(objective_rows)
    column_labels = {
        "objective_label": "Objectif",
        "objective_scope": "Périmètre",
        "scenario_name": "Scénario recommandé",
        "objective_score": "Score objectif",
        "overall_score": "Score global",
        "reason": "Pourquoi",
    }
    available_columns = [column for column in column_labels if column in frame.columns]
    if not available_columns:
        return pd.DataFrame()
    return frame.loc[:, available_columns].rename(columns=column_labels)


def _build_screener_artifact_file_rows(summary: dict[str, object]) -> pd.DataFrame:
    files = summary.get("files")
    if not isinstance(files, list) or not files:
        return pd.DataFrame()
    frame = pd.DataFrame(files)
    column_labels = {
        "label": "Fichier",
        "exists": "Présent",
        "kind": "Type",
        "row_count": "Lignes",
        "size_label": "Taille",
        "path": "Chemin",
    }
    available_columns = [column for column in column_labels if column in frame.columns]
    if not available_columns:
        return pd.DataFrame()
    formatted = frame.loc[:, available_columns].rename(columns=column_labels)
    if "Présent" in formatted.columns:
        formatted["Présent"] = formatted["Présent"].map(lambda value: "oui" if bool(value) else "non")
    return formatted


def _build_global_screener_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(build_screener_artifact_history_rows(history_entries))


def _render_screener_artifact_summary(run_record: dict[str, object]) -> bool:
    if str(run_record.get("run_kind", "")) not in {"diagnose-screener", "recommend-screener"}:
        return False

    summary = _resolve_screener_artifact_summary(run_record)
    st.markdown("**🧾 Résumé structuré des artefacts screener**")
    screener_artifacts_dir = run_record.get("screener_artifacts_dir")
    if screener_artifacts_dir:
        st.caption(f"Répertoire du run : `{screener_artifacts_dir}`")

    if not summary:
        st.info("Aucun résumé screener disponible pour ce run.")
        return True

    st.caption(
        f"Couverture : {summary.get('coverage_label', 'Période non renseignée')} · "
        f"MAJ : {summary.get('updated_at_label', 'inconnue')}"
    )

    metric_rows = _build_screener_artifact_metric_rows(summary)
    for offset in range(0, len(metric_rows), 4):
        chunk = metric_rows[offset : offset + 4]
        cols = st.columns(len(chunk))
        for col, (label, value) in zip(cols, chunk, strict=False):
            col.metric(label, value)

    best_compromise = summary.get("best_compromise")
    if isinstance(best_compromise, dict) and best_compromise.get("scenario_name"):
        st.success(
            "Meilleur compromis : `{}` · overall={} · robustesse={} · survie={} · forward={}".format(
                best_compromise.get("scenario_name"),
                _coerce_metric_text(best_compromise.get("overall_score")),
                _coerce_metric_text(best_compromise.get("robustness_score")),
                _coerce_metric_text(best_compromise.get("survival_score")),
                _coerce_metric_text(best_compromise.get("forward_quality_score")),
            )
        )

    best_cross_regime = summary.get("best_cross_regime")
    if isinstance(best_cross_regime, dict) and best_cross_regime.get("scenario_name"):
        st.info(
            "Leader cross-régimes : `{}` · score={} · rang={}".format(
                best_cross_regime.get("scenario_name"),
                _coerce_metric_text(best_cross_regime.get("overall_score")),
                _coerce_metric_text(best_cross_regime.get("rank")),
            )
        )

    objective_rows = _build_screener_artifact_objective_rows(summary)
    if not objective_rows.empty:
        st.dataframe(objective_rows, use_container_width=True, hide_index=True)

    file_rows = _build_screener_artifact_file_rows(summary)
    if not file_rows.empty:
        with st.expander("📁 Inventaire des fichiers screener du run", expanded=False):
            st.dataframe(file_rows, use_container_width=True, hide_index=True)

    errors = summary.get("errors")
    if isinstance(errors, list) and errors:
        with st.expander("ℹ️ Détails de lecture du snapshot", expanded=False):
            for error in errors:
                st.caption(f"- {error}")

    return True


def _render_runtime_center_body(*, auto_refresh_enabled: bool) -> None:
    active_runs, all_runs = _merge_runs()
    has_active_runs = bool(active_runs)

    st.subheader("🖥️ Runs & logs backtesting")
    auto_update_enabled = st.toggle(
        "Auto update",
        value=_is_runtime_center_auto_update_enabled(),
        key=RUNTIME_CENTER_AUTO_UPDATE_KEY,
        help=(
            "Active ou désactive le rafraîchissement automatique toutes les 2 secondes "
            "quand au moins un run backtest est en cours."
        ),
    )
    if auto_refresh_enabled:
        st.caption(
            "Rafraîchissement automatique toutes les 2 secondes car au moins un run est actif. "
            "Les commandes continuent en arrière-plan même si vous changez de page."
        )
    elif has_active_runs and not auto_update_enabled:
        st.caption(
            "Au moins un run est actif, mais l'auto-update est désactivé. "
            "Utilisez `Rafraîchir maintenant` pour relire l'état manuellement."
        )
    else:
        st.caption(
            "Aucun run actif : auto-refresh désactivé pour garder la page réactive. "
            "Utilisez `Rafraîchir maintenant` si vous voulez relire l'état manuellement."
        )

    if st.button("🔄 Rafraîchir maintenant", key=f"backtesting_manual_refresh_{'live' if auto_refresh_enabled else 'static'}"):
        st.rerun()

    if active_runs:
        st.markdown("**Runs actifs**")
        for run in active_runs:
            run_id = str(run.get("run_id", ""))
            cols = st.columns([3, 2, 2, 1.5])
            cols[0].markdown(f"`{run.get('run_label', run.get('run_kind', ''))}`  \\n`{run_id}`")
            cols[1].markdown(_status_badge(str(run.get("status", "running"))))
            cols[2].markdown(f"⏱️ {format_duration_hhmmss(run.get('duration_seconds'))}")
            if cols[3].button("⏹️ Arrêter", key=f"stop_backtesting_run_{run_id}", use_container_width=True):
                stop_backtesting_run(run_id)
                st.rerun()
    else:
        st.info("Aucun run backtesting actif pour le moment.")

    if not all_runs:
        st.info("Aucun run backtesting historisé pour le moment.")
        return

    labels = {
        str(run["run_id"]): (
            f"{run.get('run_label', run.get('run_kind', ''))} | {run.get('run_id')} | "
            f"{_status_badge(str(run.get('status', '')))} | {run.get('executed_at', '')}"
        )
        for run in all_runs
    }
    run_ids = list(labels.keys())
    _prime_runtime_center_state(run_ids, labels)

    control_col1, control_col2 = st.columns([2, 4])
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
        selected_run_id = st.selectbox(
            "Run à inspecter",
            options=run_ids,
            format_func=lambda rid: labels[rid],
            key=SELECTED_RUN_KEY,
        )

    stream_map = {"tout": "all", "stdout": "stdout", "stderr": "stderr"}
    selected_run = get_backtesting_run_record(selected_run_id)
    if selected_run is None:
        st.warning("Run introuvable.")
        return

    status = str(selected_run.get("status", ""))
    if status == "completed":
        st.success(f"Run sélectionné : {_status_badge(status)}")
    elif status in {"failed", "timeout", "stopped"}:
        st.error(f"Run sélectionné : {_status_badge(status)}")
    else:
        st.warning(f"Run sélectionné : {_status_badge(status)}")

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Commande", str(selected_run.get("run_kind", "—")))
    metric_col2.metric("Durée", format_duration_hhmmss(selected_run.get("duration_seconds")))
    metric_col3.metric("Lignes stdout", _to_int(selected_run.get("stdout_lines")))
    metric_col4.metric("Lignes stderr", _to_int(selected_run.get("stderr_lines")))

    st.caption(
        f"Commande : `{selected_run.get('command_display', '')}` | Retour : `{selected_run.get('returncode')}` | "
        f"Début : `{selected_run.get('executed_at', '')}` | Fin : `{selected_run.get('finished_at') or '—'}`"
    )
    load_logs_key = f"backtesting_load_logs_{selected_run_id}_{log_filter}"
    load_logs = st.toggle(
        "Charger les logs du run sélectionné",
        value=_should_preload_runtime_details(status),
        key=load_logs_key,
        help=(
            "Désactivez ce chargement pour éviter de relire immédiatement des fichiers de logs volumineux. "
            "Les runs actifs restent chargés par défaut pour conserver le suivi live."
        ),
    )
    if load_logs:
        selected_logs_preview = read_backtesting_logs(
            selected_run_id,
            stream=cast(Any, stream_map[log_filter]),
            tail_lines=TAIL_LINES,
        )
        selected_log_available = backtesting_log_available(selected_run_id, stream=cast(Any, stream_map[log_filter]))
        prepare_selected_log_download = st.toggle(
            f"Préparer le téléchargement du log ({log_filter})",
            value=False,
            key=f"prepare_download_backtesting_{selected_run_id}_{log_filter}",
            help="La lecture complète du fichier de log n'est faite qu'à la demande.",
        )
        if prepare_selected_log_download and selected_log_available:
            selected_logs_download = read_backtesting_logs(selected_run_id, stream=cast(Any, stream_map[log_filter]))
            st.download_button(
                label=f"⬇️ Télécharger le log ({log_filter})",
                data=selected_logs_download,
                file_name=build_backtesting_log_download_name(selected_run_id, stream=cast(Any, stream_map[log_filter])),
                mime="text/plain",
                key=f"download_backtesting_{selected_run_id}_{log_filter}",
            )
        elif not selected_log_available:
            st.caption("⚠️ Fichier de log indisponible pour ce flux.")
        _render_log_block(
            "Logs du run sélectionné",
            selected_logs_preview,
            key=f"backtesting_selected_logs_{selected_run_id}_{log_filter}",
            expanded=True,
        )
    else:
        st.caption(
            "Logs non chargés automatiquement pour éviter de relire des fichiers volumineux à chaque rafraîchissement."
        )

    load_details_key = f"backtesting_load_details_{selected_run_id}"
    load_details = st.toggle(
        "Charger le résumé détaillé et les artefacts du run sélectionné",
        value=_should_preload_runtime_details(status),
        key=load_details_key,
        help=(
            "Active la lecture de `report.json`, `equity_curve.csv`, `trades.csv` et des artefacts JSON annexes. "
            "Utile pour analyser un run, mais coûteux sur de gros backtests."
        ),
    )
    if load_details:
        if str(selected_run.get("run_kind", "")) == "run":
            has_report = _render_report_summary(selected_run)
            has_live_artifacts = _render_live_artifacts(selected_run)
            if status == "completed" and not (has_report or has_live_artifacts):
                _render_latest_artifacts()
        else:
            _render_screener_artifact_summary(selected_run)
    else:
        st.caption(
            "Résumé détaillé différé : cela évite de relire automatiquement les artefacts du dernier run à chaque ouverture de page."
        )

    history_df = pd.DataFrame(
        [
            {
                "run_id": run.get("run_id"),
                "commande": run.get("run_kind"),
                "libellé": run.get("run_label"),
                "statut": _status_badge(str(run.get("status", ""))),
                "début": run.get("executed_at"),
                "fin": run.get("finished_at") or "—",
                "durée": format_duration_hhmmss(run.get("duration_seconds")),
                "stdout": _to_int(run.get("stdout_lines")),
                "stderr": _to_int(run.get("stderr_lines")),
            }
            for run in all_runs
        ]
    )
    with st.expander("🗃️ Historique des exécutions backtesting", expanded=False):
        st.caption("Sélectionnez une ligne pour faire apparaître les boutons de téléchargement des logs du run historique.")
        st.dataframe(
            history_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key=BACKTESTING_HISTORY_TABLE_KEY,
        )

        selected_history_run_id = _resolve_history_selected_run_id(history_df)
        if selected_history_run_id is None:
            st.caption("ℹ️ Aucune ligne sélectionnée dans l'historique pour le moment.")
        else:
            selected_history_run = get_backtesting_run_record(selected_history_run_id)
            selected_history_status = _status_badge(str(selected_history_run.get("status") or "")) if isinstance(selected_history_run, dict) else "—"
            st.caption(f"Run historique sélectionné : `{selected_history_run_id}` | {selected_history_status}")

            history_download_specs = [
                ("⬇️ Log consolidé", "all", backtesting_log_available(selected_history_run_id, stream="all")),
                ("⬇️ Stdout", "stdout", backtesting_log_available(selected_history_run_id, stream="stdout")),
                ("⬇️ Stderr", "stderr", backtesting_log_available(selected_history_run_id, stream="stderr")),
            ]

            history_prepare_downloads = st.toggle(
                "Préparer les téléchargements de logs du run historique",
                value=False,
                key=f"history_backtesting_prepare_downloads_{selected_history_run_id}",
                help="Évite de relire les trois fichiers de log tant que vous n'avez pas réellement besoin de les télécharger.",
            )

            download_cols = st.columns(4)
            if history_prepare_downloads:
                for index, (label, stream, available) in enumerate(history_download_specs):
                    data = read_backtesting_logs(selected_history_run_id, stream=cast(Any, stream)) if available else ""
                    download_cols[index].download_button(
                        label=label,
                        data=data,
                        file_name=build_backtesting_log_download_name(selected_history_run_id, stream=cast(Any, stream)),
                        mime="text/plain",
                        key=f"history_backtesting_download_{selected_history_run_id}_{stream}",
                        use_container_width=True,
                        disabled=not available,
                    )
            else:
                for index, (label, _stream, available) in enumerate(history_download_specs):
                    download_cols[index].button(
                        f"{label}{' ✅' if available else ' —'}",
                        key=f"history_backtesting_download_placeholder_{selected_history_run_id}_{index}",
                        use_container_width=True,
                        disabled=True,
                    )

            if download_cols[3].button(
                "🔍 Inspecter ce run",
                key=f"history_backtesting_open_run_{selected_history_run_id}",
                use_container_width=True,
            ):
                st.session_state[PENDING_SELECTED_RUN_KEY] = selected_history_run_id
                st.rerun()

            if not any(spec[2] for spec in history_download_specs):
                st.caption("⚠️ Les artefacts de logs de ce run sont indisponibles (rotation, purge ou run incomplet).")

    if st.toggle(
        "Charger l'historique global des artefacts screener",
        value=False,
        key=LOAD_GLOBAL_SCREENER_HISTORY_KEY,
        help="Ce tableau rescane les répertoires screener connus et peut ralentir la page si les CSV sont volumineux.",
    ):
        screener_history_df = _build_global_screener_history_dataframe(build_global_screener_artifact_history())
        if not screener_history_df.empty:
            with st.expander("🗂️ Historique global des artefacts screener", expanded=False):
                st.caption(
                    "Vue transversale des répertoires screener connus par l'IHM, indépendamment du run actuellement sélectionné."
                )
                st.dataframe(screener_history_df, use_container_width=True, hide_index=True)
    else:
        st.caption(
            "Historique screener global non chargé automatiquement pour éviter de rescanner les gros artefacts à chaque rendu."
        )


@st.fragment(run_every="2s")
def _render_runtime_center_live() -> None:
    # Garde-fou : si l'auto-update a été désactivé entre-temps
    # (ex: toggle OFF pendant que le fragment était actif),
    # on rebascule immédiatement en mode statique.
    if not _is_runtime_center_auto_update_enabled():
        _render_runtime_center_static()
        return
    _render_runtime_center_body(auto_refresh_enabled=True)


@st.fragment
def _render_runtime_center_static() -> None:
    _render_runtime_center_body(auto_refresh_enabled=False)


def render() -> None:
    st.header("🧪 Backtesting intégré")
    st.caption(
        "Page opérateur dédiée au backtesting et aux diagnostics screener : configuration complète, lancement direct depuis l'IHM, "
        "suivi des runs et consultation des logs."
    )

    db_config_preview = get_runtime_db_config()
    source = db_config_preview.get("source")
    host = db_config_preview.get("host")
    name = db_config_preview.get("name")
    st.info(f"La commande lancée héritera de la configuration DB active : `{host}/{name}` via `{source}`.")

    with st.expander("🗄️ Connexion DB utilisée par les sous-processus", expanded=False):
        render_db_connection_form("backtesting_db_connection_form", show_host_fields=True)

    db_config = get_runtime_db_config()
    active_backtest_runs = list_active_backtesting_runs_by_kind("run")
    active_backfill_runs = list_active_backtesting_runs_by_kind("backfill-scores-history")
    active_diag_runs = list_active_backtesting_runs_by_kind("diagnose-screener")
    active_recommend_runs = list_active_backtesting_runs_by_kind("recommend-screener")
    active_calibrate_runs = list_active_backtesting_runs_by_kind("calibrate-sentiment-weights")
    active_conviction_runs = list_active_backtesting_runs_by_kind("calibrate-conviction-weights")
    active_walkfwd_runs = list_active_backtesting_runs_by_kind("walk-forward-sentiment")
    active_wfc_runs = list_active_backtesting_runs_by_kind("walk-forward-conviction")

    run_tab, backfill_tab, diagnose_tab, recommend_tab, calibrate_tab, conviction_tab, walkfwd_tab, walkforward_conviction_tab, quarterly_tab = st.tabs(
        [
            "▶️ Backtest",
            "🧱 Backfill scores history",
            "🧪 Diagnose screener",
            "🎯 Recommend screener",
            "📰 Calibrate sentiment",
            "🎯 Calibrate conviction",
            "🚶 Walk-forward sentiment",
            "🔄 Walk-forward conviction",
            "🎛️ Calibration trimestrielle poids",
        ]
    )
    with run_tab:
        run_options = _build_run_options()
        if active_backtest_runs:
            active_run_id = str(active_backtest_runs[0].get("run_id", ""))
            st.info(f"Un backtest est déjà en cours (`{active_run_id}`). Arrête-le ou attends sa fin pour relancer.")
        launch_backtest_clicked = st.button(
            "🚀 Lancer le backtest",
            key="launch_backtest_run",
            type="primary",
            use_container_width=True,
            disabled=bool(active_backtest_runs),
        )
        if launch_backtest_clicked:
            try:
                record = start_backtesting_run("run", "Backtest complet", run_options, db_config=db_config)
            except RuntimeError as exc:
                st.warning(str(exc))
            else:
                st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
                st.success(f"Backtest lancé en arrière-plan : `{record.run_id}`")
                st.rerun()

    with backfill_tab:
        backfill_options = _build_backfill_options()
        if active_backfill_runs:
            active_run_id = str(active_backfill_runs[0].get("run_id", ""))
            st.info(f"Un backfill PIT est déjà en cours (`{active_run_id}`). Arrête-le ou attends sa fin pour relancer.")
        launch_backfill_clicked = st.button(
            "🧱 Lancer le backfill PIT",
            key="launch_backfill_run",
            type="primary",
            use_container_width=True,
            disabled=bool(active_backfill_runs),
        )
        if launch_backfill_clicked:
            try:
                record = start_backtesting_run(
                    "backfill-scores-history",
                    "Backfill stock_scores_history",
                    backfill_options,
                    db_config=db_config,
                )
            except RuntimeError as exc:
                st.warning(str(exc))
            else:
                st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
                st.success(f"Backfill lancé en arrière-plan : `{record.run_id}`")
                st.rerun()

    with diagnose_tab:
        diagnose_options = _build_diagnose_screener_options()
        if active_diag_runs:
            active_run_id = str(active_diag_runs[0].get("run_id", ""))
            st.info(f"Un diagnostic screener est déjà en cours (`{active_run_id}`). Arrête-le ou attends sa fin pour relancer.")
        st.caption(
            "Conseil : garde `artifacts/screener_diagnostics` comme répertoire cible si tu veux que la page Screening relise automatiquement les nouveaux artefacts."
        )
        launch_diagnose_clicked = st.button(
            "🧪 Lancer diagnose-screener",
            key="launch_diagnose_screener_run",
            type="primary",
            use_container_width=True,
            disabled=bool(active_diag_runs),
        )
        if launch_diagnose_clicked:
            try:
                record = start_backtesting_run(
                    "diagnose-screener",
                    "Diagnostic screener PIT",
                    diagnose_options,
                    db_config=db_config,
                )
            except RuntimeError as exc:
                st.warning(str(exc))
            else:
                st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
                st.success(f"Diagnostic screener lancé en arrière-plan : `{record.run_id}`")
                st.rerun()

    with recommend_tab:
        recommend_options = _build_recommend_screener_options()
        if active_recommend_runs:
            active_run_id = str(active_recommend_runs[0].get("run_id", ""))
            st.info(f"Une recommandation screener est déjà en cours (`{active_run_id}`). Arrête-la ou attends sa fin pour relancer.")
        st.caption(
            "Utilise ce recalcul pour regénérer rapidement les recommandations sans rejouer tout le diagnostic PIT."
        )
        launch_recommend_clicked = st.button(
            "🎯 Lancer recommend-screener",
            key="launch_recommend_screener_run",
            type="primary",
            use_container_width=True,
            disabled=bool(active_recommend_runs),
        )
        if launch_recommend_clicked:
            try:
                record = start_backtesting_run(
                    "recommend-screener",
                    "Recommandation screener",
                    recommend_options,
                    db_config=db_config,
                )
            except RuntimeError as exc:
                st.warning(str(exc))
            else:
                st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
                st.success(f"Recommandation screener lancée en arrière-plan : `{record.run_id}`")
                st.rerun()

    with calibrate_tab:
        calibrate_options = _build_calibrate_sentiment_options()
        if active_calibrate_runs:
            active_run_id = str(active_calibrate_runs[0].get("run_id", ""))
            st.info(f"Une calibration sentiment est déjà en cours (`{active_run_id}`).")
        launch_calibrate_clicked = st.button(
            "📰 Lancer calibrate-sentiment-weights",
            key="launch_calibrate_sentiment_run",
            type="primary",
            use_container_width=True,
            disabled=bool(active_calibrate_runs),
        )
        if launch_calibrate_clicked:
            try:
                record = start_backtesting_run(
                    "calibrate-sentiment-weights",
                    "Calibration poids sentiment",
                    calibrate_options,
                    db_config=db_config,
                )
            except RuntimeError as exc:
                st.warning(str(exc))
            else:
                st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
                st.success(f"Calibration sentiment lancée : `{record.run_id}`")
                st.rerun()

    with conviction_tab:
        conviction_options = _build_calibrate_conviction_options()
        if active_conviction_runs:
            active_run_id = str(active_conviction_runs[0].get("run_id", ""))
            st.info(f"Une calibration conviction est déjà en cours (`{active_run_id}`).")
        launch_conviction_clicked = st.button(
            "🎯 Lancer calibrate-conviction-weights",
            key="launch_calibrate_conviction_run",
            type="primary",
            use_container_width=True,
            disabled=bool(active_conviction_runs),
        )
        if launch_conviction_clicked:
            try:
                record = start_backtesting_run(
                    "calibrate-conviction-weights",
                    "Calibration conviction (quant/ML) + Kelly",
                    conviction_options,
                    db_config=db_config,
                )
            except RuntimeError as exc:
                st.warning(str(exc))
            else:
                st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
                st.success(f"Calibration conviction lancée : `{record.run_id}`")
                st.rerun()

    with walkfwd_tab:
        walkfwd_options = _build_walk_forward_sentiment_options()
        if active_walkfwd_runs:
            active_run_id = str(active_walkfwd_runs[0].get("run_id", ""))
            st.info(f"Un walk-forward sentiment est déjà en cours (`{active_run_id}`).")
        launch_walkfwd_clicked = st.button(
            "🚶 Lancer walk-forward-sentiment",
            key="launch_walk_forward_sentiment_run",
            type="primary",
            use_container_width=True,
            disabled=bool(active_walkfwd_runs),
        )
        if launch_walkfwd_clicked:
            try:
                record = start_backtesting_run(
                    "walk-forward-sentiment",
                    "Walk-forward sentiment",
                    walkfwd_options,
                    db_config=db_config,
                )
            except RuntimeError as exc:
                st.warning(str(exc))
            else:
                st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
                st.success(f"Walk-forward sentiment lancé : `{record.run_id}`")
                st.rerun()

    with walkforward_conviction_tab:
        wfc_options = _build_walk_forward_conviction_options()
        if active_wfc_runs:
            active_run_id = str(active_wfc_runs[0].get("run_id", ""))
            st.info(f"Un walk-forward conviction est déjà en cours (`{active_run_id}`).")
        launch_wfc_clicked = st.button(
            "🔄 Lancer walk-forward-conviction",
            key="launch_walk_forward_conviction_run",
            type="primary",
            use_container_width=True,
            disabled=bool(active_wfc_runs),
        )
        if launch_wfc_clicked:
            try:
                record = start_backtesting_run(
                    "walk-forward-conviction",
                    "Walk-forward conviction",
                    wfc_options,
                    db_config=db_config,
                )
            except RuntimeError as exc:
                st.warning(str(exc))
            else:
                st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
                st.success(f"Walk-forward conviction lancé : `{record.run_id}`")
                st.rerun()

    with quarterly_tab:
        # Sprint S26 (gap P3) — script ops `run_quarterly_weights_calibration.py`.
        from ihm.components.ops_command_panel import render_ops_command_panel

        st.caption(
            "Lance `scripts/run_quarterly_weights_calibration.py` pour recalibrer "
            "les poids de score (Sharpe / hit-ratio / IC) sur les 4 derniers "
            "trimestres. Run tracé sous `ops:quarterly_weights_calibration`."
        )
        render_ops_command_panel("quarterly_weights_calibration")

    has_any_active_runs = _should_auto_refresh_runtime_center(
        active_backtest_runs,
        active_backfill_runs,
        active_diag_runs,
        active_recommend_runs,
        active_calibrate_runs,
        active_conviction_runs,
        active_walkfwd_runs,
        active_wfc_runs,
    )
    if has_any_active_runs and _is_runtime_center_auto_update_enabled():
        _render_runtime_center_live()
    else:
        _render_runtime_center_static()


run_page_if_standalone(__name__, render)


