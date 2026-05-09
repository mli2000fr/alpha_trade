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
    get_capital_preset_by_key,
    load_capital_presets,
    resolve_capital_preset_for_equity,
)
from ihm.components.db_controls import render_db_connection_form
from ihm.components.metrics import format_duration_hhmmss
from ihm.pages import run_page_if_standalone
from ihm.services.backtesting_registry import (
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
    CalibrateSentimentWeightsOptions,
    DiagnoseScreenerOptions,
    RecommendScreenerOptions,
    WalkForwardSentimentOptions,
    build_backtesting_command,
    format_command_for_display,
)
from ihm.services.db import get_db_status, get_runtime_db_config
from ihm.services.queries import get_backtesting_pit_history_diagnostic
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
    signature = f"{selected_preset_key}|{equity:.2f}"
    if str(st.session_state.get(BT_RUN_CAPITAL_PRESET_SIGNATURE_KEY, "") or "") == signature:
        return get_capital_preset_by_key(selected_preset_key) if selected_preset_key != CAPITAL_PRESET_CUSTOM else None
    if selected_preset_key == CAPITAL_PRESET_CUSTOM:
        st.session_state[BT_RUN_CAPITAL_PRESET_SIGNATURE_KEY] = signature
        return None
    preset = get_capital_preset_by_key(selected_preset_key)
    if preset is None:
        st.session_state[BT_RUN_CAPITAL_PRESET_SIGNATURE_KEY] = signature
        return None
    values = preset.values
    st.session_state["bt_run_account_type"] = str(values.get("execution_account_type", st.session_state.get("bt_run_account_type", "margin")))
    st.session_state["bt_run_pdt_rule"] = str(values.get("execution_pdt_rule", st.session_state.get("bt_run_pdt_rule", "auto")))
    st.session_state["bt_run_swing_only"] = bool(values.get("execution_swing_only", st.session_state.get("bt_run_swing_only", False)))
    st.session_state["bt_run_max_positions"] = int(values.get("risk_max_positions", st.session_state.get("bt_run_max_positions", 20)))
    st.session_state[BT_RUN_CAPITAL_PRESET_SIGNATURE_KEY] = signature
    return preset


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
    st.session_state["bt_backfill_selection_size"] = int(values.get("selector_selection_size", st.session_state.get("bt_backfill_selection_size", 100)))
    st.session_state[BT_BACKFILL_CAPITAL_PRESET_SIGNATURE_KEY] = signature
    return preset


def _tail_text(value: str, max_lines: int = TAIL_LINES) -> str:
    lines = value.splitlines()
    if len(lines) <= max_lines:
        return value
    return "\n".join(lines[-max_lines:])


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
            {"Paramètre": "fees", "Explication": "Frais/slippage simulés par trade.", "Défaut": "0.001"},
            {
                "Paramètre": "account_type",
                "Explication": "Type de compte simulé : margin / cash.",
                "Défaut": "margin",
            },
            {
                "Paramètre": "pdt_rule",
                "Explication": "Application de la règle PDT sur un compte margin : auto / off.",
                "Défaut": "auto",
            },
            {
                "Paramètre": "swing_only",
                "Explication": "Interdit les sorties le jour même de l'entrée.",
                "Défaut": "False",
            },
            {"Paramètre": "sentiment_lookback", "Explication": "Fenêtre historique sentiment passée à la CLI backtesting.", "Défaut": "365"},
            {"Paramètre": "no_save", "Explication": "Désactive l'écriture des artefacts PNG/CSV.", "Défaut": "False"},
            {"Paramètre": "ml_mode", "Explication": "auto/off/rebuild-missing pour la composante ML.", "Défaut": "auto"},
            {"Paramètre": "sentiment_mode", "Explication": "auto/off/rebuild-missing pour la composante sentiment.", "Défaut": "auto"},
            {"Paramètre": "engine_mode", "Explication": "research = tolérant/rapide, pipeline = strict PIT + diagnostics renforcés.", "Défaut": "research"},
            {"Paramètre": "ml_pit_strategy", "Explication": "Stratégie PIT ML explicite : auto / use-persisted / rebuild-missing / walk-forward-train-then-predict.", "Défaut": "auto"},
            {"Paramètre": "phase2_mode", "Explication": "off = backtest standard, risk = bridge risk_management, risk_execution = risk + intents/fills d'exécution simulés.", "Défaut": "off"},
            {"Paramètre": "phase3_mode", "Explication": "off = comportement Phase 2, execution_replay = réinjecte chronologiquement les quantités exécutées simulées dans le moteur de backtest.", "Défaut": "off"},
            {"Paramètre": "phase4_mode", "Explication": "off = comportement Phase 3, protection_replay = rejoue les protections TP/stop/trailing issues des child intents d'exécution.", "Défaut": "off"},
            {"Paramètre": "phase5_mode", "Explication": "off = comportement Phase 4, watcher_replay = rejoue les transitions du watcher de protection (trigger -> promotion trailing) dans le moteur.", "Défaut": "off"},
            {"Paramètre": "phase7_mode", "Explication": "off = comportement Phase 5, exit_lifecycle_replay = rejoue l'issue terminale des child orders et l'annulation OCO du sibling.", "Défaut": "off"},
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


def _build_overlay_options() -> dict[str, Any]:
    """Construit le sous-dict d'options pour les surcouches micro-structure / risk overlay.

    Affiche un expander unique avec deux blocs (Phase B et Phase C). Toutes les
    valeurs par défaut sont **neutres** : le backtest produit alors exactement
    les mêmes résultats que sans la surcouche.
    """
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
                value=float(st.session_state.get("bt_run_max_entry_gap_pct", 0.0)),
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
                value=float(st.session_state.get("bt_run_max_sector_exposure_pct", 0.0)),
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
                value=float(st.session_state.get("bt_run_max_portfolio_dd_pct", 0.0)),
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
                value=float(st.session_state.get("bt_run_dd_recovery_pct", 0.95)),
                step=0.01,
                format="%.4f",
                key="bt_run_dd_recovery_pct",
            )
        with risk_col10:
            target_annual_vol_raw = st.text_input(
                "Target annual vol (optionnel)",
                value=cast(str, st.session_state.get("bt_run_target_annual_vol_raw", "")),
                key="bt_run_target_annual_vol_raw",
                help="Ex 0.15 = cible 15% vol portefeuille. Vide = désactivé.",
            )

    seed_value: int | None = None
    if seed_raw.strip():
        try:
            seed_value = int(seed_raw.strip())
        except ValueError:
            st.warning(f"Seed invalide ignoré : `{seed_raw}`.")

    target_annual_vol_value: float | None = None
    cleaned_vol = target_annual_vol_raw.strip()
    if cleaned_vol:
        try:
            target_annual_vol_value = float(cleaned_vol)
        except ValueError:
            st.warning(f"Target annual vol invalide ignorée : `{cleaned_vol}`.")

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
    }


def _build_run_options() -> BacktestRunOptions:
    st.subheader("▶️ Lancer un backtest")
    st.caption(
        "Le backtest exécute `python -m backtesting run ...` en arrière-plan. "
        "Tous les paramètres CLI sont exposés ci-dessous et les logs sont visibles plus bas dans la page."
    )
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
    if selected_run_configuration_preset == "pipeline_live_like":
        st.info(
            "Ce preset correspond à la commande `python -m backtesting run ...` la plus proche du pipeline live aujourd'hui. "
            "Il ne fait pas partie de `backfill-scores-history`. Pour qu'il fonctionne en mode `pipeline`, "
            "il faut déjà disposer d'un historique PIT valide dans `stock_scores_history` — à reconstruire via l'onglet `Backfill scores history` si nécessaire."
        )
    _render_reference_table("run")

    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.text_input(
            "Date de début",
            value=cast(str, st.session_state.get("bt_run_start", "2024-01-01")),
            key="bt_run_start",
            help="Format YYYY-MM-DD. C'est la borne basse du backtest.",
        )
    with col2:
        end = st.text_input(
            "Date de fin",
            value=cast(str, st.session_state.get("bt_run_end", "2024-01-31")),
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

    col4, col5, col6, col7 = st.columns(4)
    with col4:
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
        fees = st.number_input(
            "Frais (fraction)",
            min_value=0.0,
            max_value=1.0,
            value=float(st.session_state.get("bt_run_fees", 0.001)),
            step=0.0005,
            format="%.4f",
            key="bt_run_fees",
            help="Exemple : 0.001 = 10 bps par trade.",
        )

    col8, col9, col10, col11 = st.columns(4)
    with col8:
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
                help="`margin` = compte standard/margin ; `cash` = cash settled uniquement, sans PDT.",
            ),
        )
    with col9:
        pdt_rule = cast(
            str,
            st.selectbox(
                "Règle PDT",
                options=["auto", "off"],
                index=["auto", "off"].index(
                    cast(str, st.session_state.get("bt_run_pdt_rule", "auto"))
                    if st.session_state.get("bt_run_pdt_rule", "auto") in {"auto", "off"}
                    else "auto"
                ),
                key="bt_run_pdt_rule",
                help="`auto` applique la règle PDT sur compte margin < 25k ; `off` la désactive dans le backtest.",
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
                    cast(str, st.session_state.get("bt_run_ml_mode", "auto"))
                    if st.session_state.get("bt_run_ml_mode", "auto") in {"auto", "off", "rebuild-missing"}
                    else "auto"
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

    mode_col1, mode_col2, mode_col3, mode_col4, mode_col5, mode_col6, mode_col7 = st.columns(7)
    with mode_col1:
        engine_mode = cast(
            str,
            st.selectbox(
                "Mode moteur",
                options=["research", "pipeline"],
                index=["research", "pipeline"].index(
                    cast(str, st.session_state.get("bt_run_engine_mode", "research"))
                    if st.session_state.get("bt_run_engine_mode", "research") in {"research", "pipeline"}
                    else "research"
                ),
                key="bt_run_engine_mode",
                help="`research` conserve le comportement tolérant du backtest standard ; `pipeline` exige des snapshots PIT valides et évite les écritures implicites.",
            ),
        )
    with mode_col2:
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
    with mode_col3:
        phase2_mode = cast(
            str,
            st.selectbox(
                "Mode Phase 2",
                options=["off", "risk", "risk_execution"],
                index=["off", "risk", "risk_execution"].index(
                    cast(str, st.session_state.get("bt_run_phase2_mode", "off"))
                    if st.session_state.get("bt_run_phase2_mode", "off") in {"off", "risk", "risk_execution"}
                    else "off"
                ),
                key="bt_run_phase2_mode",
                help="Active de manière opt-in les bridges de fidélité Phase 2. `off` conserve strictement le replay historique ; `risk` réutilise `risk_management`; `risk_execution` ajoute les intents/fills simulés via `execution_engine`.",
            ),
        )
    with mode_col4:
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
    with mode_col5:
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
    with mode_col6:
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
    with mode_col7:
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

    info_col1, info_col2 = st.columns(2)
    with info_col1:
        st.caption(
            "Règle `PDT` : en mode `auto`, la 4e tentative de day trade sur 5 séances est bloquée pour un compte margin < 25k."
        )
    with info_col2:
        st.caption(
            "`cash` + `swing_only` est supporté : cash settled T+1 et aucune sortie le jour même."
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
        walk_forward_artifacts_dir = st.text_input(
            "Répertoire artefacts walk-forward (optionnel)",
            value=cast(str, st.session_state.get("bt_run_walk_forward_artifacts_dir", "")),
            key="bt_run_walk_forward_artifacts_dir",
            help="Si renseigné, le backtest standard cherchera explicitement les meilleurs poids walk-forward dans ce répertoire.",
        )

    _render_pipeline_pit_hint(
        engine_mode=engine_mode,
        start=start.strip(),
        end=end.strip() or None,
        selected_run_preset_key=selected_run_preset_key,
        auto_run_preset_key=auto_run_preset_key,
    )

    options = BacktestRunOptions(
        start=start.strip(),
        end=end.strip() or None,
        equity=float(equity),
        capital_preset_key=None if selected_run_preset_key == CAPITAL_PRESET_CUSTOM else selected_run_preset_key,
        tp=float(tp),
        ts=float(ts),
        max_positions=int(max_positions),
        fees=float(fees),
        account_type=cast(Any, account_type),
        pdt_rule=cast(Any, pdt_rule),
        swing_only=bool(swing_only),
        sentiment_lookback=int(sentiment_lookback),
        no_save=bool(no_save),
        ml_mode=cast(Any, ml_mode),
        sentiment_mode=cast(Any, sentiment_mode),
        engine_mode=cast(Any, engine_mode),
        ml_pit_strategy=cast(Any, ml_pit_strategy),
        phase2_mode=cast(Any, phase2_mode),
        phase3_mode=cast(Any, phase3_mode),
        phase4_mode=cast(Any, phase4_mode),
        phase5_mode=cast(Any, phase5_mode),
        phase7_mode=cast(Any, phase7_mode),
        artifacts_dir=artifacts_dir.strip() or "artifacts/models",
        score_column=cast(Any, score_column),
        walk_forward_artifacts_dir=walk_forward_artifacts_dir.strip() or None,
        **_build_overlay_options(),
    )

    st.code(format_command_for_display(build_backtesting_command("run", options)), language="powershell")
    return options


def _build_backfill_options() -> BackfillScoresHistoryOptions:
    st.subheader("🧱 Backfill PIT de `stock_scores_history`")
    st.caption(
        "Cette commande reconstruit les snapshots historiques nécessaires pour un vrai backtest point-in-time. "
        "Elle exécute `python -m backtesting backfill-scores-history ...` en arrière-plan."
    )
    _render_reference_table("backfill")

    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.text_input(
            "Date de début du backfill",
            value=cast(str, st.session_state.get("bt_backfill_start", "2024-01-01")),
            key="bt_backfill_start",
            help="Première séance à reconstruire au format YYYY-MM-DD.",
        )
    with col2:
        end = st.text_input(
            "Date de fin du backfill",
            value=cast(str, st.session_state.get("bt_backfill_end", "2024-01-31")),
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
            value=cast(str, st.session_state.get("bt_diag_start", "2024-01-01")),
            key="bt_diag_start",
        )
    with col2:
        end = st.text_input(
            "Date de fin diagnostic",
            value=cast(str, st.session_state.get("bt_diag_end", "2024-01-31")),
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
    output_dir = st.text_input(
        "Répertoire des artefacts screener",
        value=cast(str, st.session_state.get("bt_diag_output_dir", "artifacts/screener_diagnostics")),
        key="bt_diag_output_dir",
        help="Le dashboard Screening lira ce dossier par défaut s'il correspond à `artifacts/screener_diagnostics`.",
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

    options = RecommendScreenerOptions(
        input_dir=input_dir.strip() or "artifacts/screener_diagnostics",
        summary_csv=summary_csv.strip() or None,
        daily_csv=daily_csv.strip() or None,
        output_dir=output_dir.strip() or None,
        baseline_name=baseline_name.strip() or None,
        target_horizon=int(target_horizon),
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

    col4, col5, col6 = st.columns(3)
    with col4:
        horizons = st.text_input(
            "Horizons forward (CSV)",
            value=cast(str, st.session_state.get("bt_calibrate_horizons", "5,10,20")),
            key="bt_calibrate_horizons",
        )
    with col5:
        output_dir = st.text_input(
            "Répertoire artefacts",
            value=cast(str, st.session_state.get("bt_calibrate_output_dir", "artifacts/sentiment_calibration")),
            key="bt_calibrate_output_dir",
        )
    with col6:
        all_symbols = st.checkbox(
            "Univers entier (`--all-symbols`)",
            value=bool(st.session_state.get("bt_calibrate_all_symbols", False)),
            key="bt_calibrate_all_symbols",
            help="Sinon limité aux candidats historiques.",
        )

    options = CalibrateSentimentWeightsOptions(
        start=start.strip(),
        end=end.strip(),
        top_n=int(top_n),
        horizons=horizons.strip() or "5,10,20",
        output_dir=output_dir.strip() or "artifacts/sentiment_calibration",
        all_symbols=bool(all_symbols),
    )
    st.code(
        format_command_for_display(build_backtesting_command("calibrate-sentiment-weights", options)),
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
        all_symbols_wf = st.checkbox(
            "Univers entier (`--all-symbols`)",
            value=bool(st.session_state.get("bt_wfs_all_symbols", False)),
            key="bt_wfs_all_symbols",
        )

    output_dir = st.text_input(
        "Répertoire artefacts",
        value=cast(str, st.session_state.get("bt_wfs_output_dir", "artifacts/sentiment_walk_forward")),
        key="bt_wfs_output_dir",
    )

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
        fees=float(fees),
        output_dir=output_dir.strip() or "artifacts/sentiment_walk_forward",
        all_symbols=bool(all_symbols_wf),
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


def _load_run_report(run_record: dict[str, object]) -> dict[str, object] | None:
    run_dir = _resolve_run_dir(run_record)
    if run_dir is None:
        return None
    report_path = run_dir / "artifacts" / "report.json"
    if not report_path.exists():
        return None
    try:
        return cast(dict[str, object], json.loads(report_path.read_text(encoding="utf-8")))
    except Exception as exc:
        st.warning(f"Impossible de lire le rapport JSON du run : {exc}")
        return None


def _load_equity_curve_df(run_record: dict[str, object]) -> pd.DataFrame:
    run_dir = _resolve_run_dir(run_record)
    if run_dir is None:
        return pd.DataFrame(columns=["trade_date", "portfolio_value"])
    equity_curve_csv = run_dir / "artifacts" / "equity_curve.csv"
    if not equity_curve_csv.exists():
        return pd.DataFrame(columns=["trade_date", "portfolio_value"])
    try:
        df = pd.read_csv(equity_curve_csv)
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        return df
    except Exception as exc:
        st.warning(f"Impossible de lire l'equity curve du run : {exc}")
        return pd.DataFrame(columns=["trade_date", "portfolio_value"])


def _load_run_trades_df(run_record: dict[str, object]) -> pd.DataFrame:
    run_dir = _resolve_run_dir(run_record)
    if run_dir is None:
        return pd.DataFrame()
    trades_csv = run_dir / "artifacts" / "trades.csv"
    if not trades_csv.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(trades_csv)
    except Exception as exc:
        st.warning(f"Impossible de lire les trades du run : {exc}")
        return pd.DataFrame()


def _render_report_summary(run_record: dict[str, object]) -> bool:
    report_payload = _load_run_report(run_record)
    if not report_payload:
        return False

    summary = cast(dict[str, object], report_payload.get("summary", {}))
    params = cast(dict[str, object], report_payload.get("params", {}))
    artifacts = cast(dict[str, object], report_payload.get("artifacts", {}))
    diagnostics = cast(dict[str, object], report_payload.get("diagnostics", {}))

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

    # Phase A.4 — métadonnées de reproductibilité.
    run_metadata = report_payload.get("run_metadata")
    if isinstance(run_metadata, dict) and run_metadata:
        with st.expander("🧬 Métadonnées de reproductibilité (Phase A.4)", expanded=False):
            st.caption(
                "Conservées dans `report.json[run_metadata]` pour rejouer un run "
                "à l'identique (git SHA, version Python, hash dataset, seed)."
            )
            st.json(run_metadata)

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

    return rendered


def _coerce_metric_text(value: object) -> str:
    if value is None:
        return "—"
    text = str(value).strip()
    return text or "—"


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


@st.fragment(run_every="2s")
def _render_runtime_center() -> None:
    active_runs, all_runs = _merge_runs()

    st.subheader("🖥️ Runs & logs backtesting")
    st.caption(
        "Rafraîchissement automatique toutes les 2 secondes pour les runs actifs. "
        "Les commandes continuent en arrière-plan même si vous changez de page."
    )

    if st.button("🔄 Rafraîchir maintenant", key="backtesting_manual_refresh"):
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

    selected_logs = read_backtesting_logs(selected_run_id, stream=cast(Any, stream_map[log_filter]))
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
    st.download_button(
        label=f"⬇️ Télécharger le log ({log_filter})",
        data=selected_logs,
        file_name=build_backtesting_log_download_name(selected_run_id, stream=cast(Any, stream_map[log_filter])),
        mime="text/plain",
        key=f"download_backtesting_{selected_run_id}_{log_filter}",
    )
    _render_log_block(
        "Logs du run sélectionné",
        selected_logs,
        key=f"backtesting_selected_logs_{selected_run_id}_{log_filter}",
        expanded=True,
    )

    if str(selected_run.get("run_kind", "")) == "run":
        has_report = _render_report_summary(selected_run)
        has_live_artifacts = _render_live_artifacts(selected_run)
        if status == "completed" and not (has_report or has_live_artifacts):
            _render_latest_artifacts()
    else:
        _render_screener_artifact_summary(selected_run)

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

            history_download_specs: list[tuple[str, str, str, bool]] = []
            for label, stream in (
                ("⬇️ Log consolidé", "all"),
                ("⬇️ Stdout", "stdout"),
                ("⬇️ Stderr", "stderr"),
            ):
                data = read_backtesting_logs(selected_history_run_id, stream=cast(Any, stream))
                available = bool(data)
                history_download_specs.append((label, stream, data, available))

            download_cols = st.columns(4)
            for index, (label, stream, data, available) in enumerate(history_download_specs):
                download_cols[index].download_button(
                    label=label,
                    data=data,
                    file_name=build_backtesting_log_download_name(selected_history_run_id, stream=cast(Any, stream)),
                    mime="text/plain",
                    key=f"history_backtesting_download_{selected_history_run_id}_{stream}",
                    use_container_width=True,
                    disabled=not available,
                )

            if download_cols[3].button(
                "🔍 Inspecter ce run",
                key=f"history_backtesting_open_run_{selected_history_run_id}",
                use_container_width=True,
            ):
                st.session_state[PENDING_SELECTED_RUN_KEY] = selected_history_run_id
                st.rerun()

            if not any(spec[3] for spec in history_download_specs):
                st.caption("⚠️ Les artefacts de logs de ce run sont indisponibles (rotation, purge ou run incomplet).")

    screener_history_df = _build_global_screener_history_dataframe(build_global_screener_artifact_history())
    if not screener_history_df.empty:
        with st.expander("🗂️ Historique global des artefacts screener", expanded=False):
            st.caption(
                "Vue transversale des répertoires screener connus par l'IHM, indépendamment du run actuellement sélectionné."
            )
            st.dataframe(screener_history_df, use_container_width=True, hide_index=True)


def render() -> None:
    st.header("🧪 Backtesting intégré")
    st.caption(
        "Page opérateur dédiée au backtesting et aux diagnostics screener : configuration complète, lancement direct depuis l'IHM, "
        "suivi des runs et consultation des logs."
    )

    status = get_db_status()
    source = status.get("source")
    host = status.get("host")
    name = status.get("name")
    st.info(f"La commande lancée héritera de la configuration DB active : `{host}/{name}` via `{source}`.")

    with st.expander("🗄️ Connexion DB utilisée par les sous-processus", expanded=False):
        render_db_connection_form("backtesting_db_connection_form", show_host_fields=True)

    db_config = get_runtime_db_config()
    active_backtest_runs = list_active_backtesting_runs_by_kind("run")
    active_backfill_runs = list_active_backtesting_runs_by_kind("backfill-scores-history")
    active_diag_runs = list_active_backtesting_runs_by_kind("diagnose-screener")
    active_recommend_runs = list_active_backtesting_runs_by_kind("recommend-screener")
    active_calibrate_runs = list_active_backtesting_runs_by_kind("calibrate-sentiment-weights")
    active_walkfwd_runs = list_active_backtesting_runs_by_kind("walk-forward-sentiment")

    run_tab, backfill_tab, diagnose_tab, recommend_tab, calibrate_tab, walkfwd_tab, quarterly_tab = st.tabs(
        [
            "▶️ Backtest",
            "🧱 Backfill scores history",
            "🧪 Diagnose screener",
            "🎯 Recommend screener",
            "📰 Calibrate sentiment",
            "🚶 Walk-forward sentiment",
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

    with quarterly_tab:
        # Sprint S26 (gap P3) — script ops `run_quarterly_weights_calibration.py`.
        from ihm.components.ops_command_panel import render_ops_command_panel

        st.caption(
            "Lance `scripts/run_quarterly_weights_calibration.py` pour recalibrer "
            "les poids de score (Sharpe / hit-ratio / IC) sur les 4 derniers "
            "trimestres. Run tracé sous `ops:quarterly_weights_calibration`."
        )
        render_ops_command_panel("quarterly_weights_calibration")

    _render_runtime_center()


run_page_if_standalone(__name__, render)


