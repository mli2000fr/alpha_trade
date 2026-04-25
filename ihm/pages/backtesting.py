"""ihm/pages/backtesting.py — Page dédiée au backtesting et au backfill PIT."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pandas as pd
import streamlit as st

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
    DiagnoseScreenerOptions,
    RecommendScreenerOptions,
    build_backtesting_command,
    format_command_for_display,
)
from ihm.services.db import get_db_status, get_runtime_db_config
from ihm.services.screener_artifact_history import (
    build_global_screener_artifact_history,
    build_screener_artifact_history_rows,
)
from ihm.services.screener_recommendations import build_screener_artifact_summary

SELECTED_RUN_KEY = "ihm_backtesting_selected_run_id"
LOG_FILTER_KEY = "ihm_backtesting_log_filter"
PENDING_SELECTED_RUN_KEY = "ihm_backtesting_pending_selected_run_id"
TAIL_LINES = 250


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


def _parameter_reference_rows(kind: str) -> list[dict[str, str]]:
    if kind == "run":
        return [
            {"Paramètre": "start", "Explication": "Date de début du backtest (obligatoire).", "Défaut": "—"},
            {"Paramètre": "end", "Explication": "Date de fin, bornée par les données disponibles.", "Défaut": "aujourd'hui"},
            {"Paramètre": "equity", "Explication": "Capital initial simulé du portefeuille.", "Défaut": "100000"},
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
            {"Paramètre": "artifacts_dir", "Explication": "Dossier des artefacts modèles utilisés pour rebuild-missing.", "Défaut": "artifacts/models"},
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
        {"Paramètre": "overwrite_existing", "Explication": "Recalcule aussi les dates déjà historisées.", "Défaut": "False"},
        {"Paramètre": "limit_days", "Explication": "Limite à N séances pour un test progressif.", "Défaut": "None"},
        {"Paramètre": "chunk_size", "Explication": "Taille des lots symboles pour screener/scanner.", "Défaut": "500"},
        {"Paramètre": "selection_size", "Explication": "Nombre final de candidats retenus par séance.", "Défaut": "100"},
        {"Paramètre": "screener_workers", "Explication": "Nombre de workers ProcessPool pour le screener PIT.", "Défaut": "auto"},
    ]


def _render_reference_table(kind: str) -> None:
    with st.expander("📘 Référence complète des paramètres", expanded=False):
        st.dataframe(pd.DataFrame(_parameter_reference_rows(kind)), use_container_width=True, hide_index=True)


def _build_run_options() -> BacktestRunOptions:
    st.subheader("▶️ Lancer un backtest")
    st.caption(
        "Le backtest exécute `python -m backtesting run ...` en arrière-plan. "
        "Tous les paramètres CLI sont exposés ci-dessous et les logs sont visibles plus bas dans la page."
    )
    _render_reference_table("run")

    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.text_input(
            "Date de début",
            value=cast(str, st.session_state.get("bt_run_start", "2025-04-21")),
            key="bt_run_start",
            help="Format YYYY-MM-DD. C'est la borne basse du backtest.",
        )
    with col2:
        end = st.text_input(
            "Date de fin",
            value=cast(str, st.session_state.get("bt_run_end", "2026-04-20")),
            key="bt_run_end",
            help="Format YYYY-MM-DD. Laissez une date future si vous voulez aller jusqu'au dernier bar dispo.",
        )
    with col3:
        equity = st.number_input(
            "Capital initial ($)",
            min_value=1_000.0,
            value=float(st.session_state.get("bt_run_equity", 100_000.0)),
            step=1_000.0,
            key="bt_run_equity",
            help="Capital de départ simulé du portefeuille.",
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

    options = BacktestRunOptions(
        start=start.strip(),
        end=end.strip() or None,
        equity=float(equity),
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
        artifacts_dir=artifacts_dir.strip() or "artifacts/models",
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
            value=cast(str, st.session_state.get("bt_backfill_start", "2025-04-21")),
            key="bt_backfill_start",
            help="Première séance à reconstruire au format YYYY-MM-DD.",
        )
    with col2:
        end = st.text_input(
            "Date de fin du backfill",
            value=cast(str, st.session_state.get("bt_backfill_end", "2026-04-16")),
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
            value=cast(str, st.session_state.get("bt_diag_start", "2025-04-21")),
            key="bt_diag_start",
        )
    with col2:
        end = st.text_input(
            "Date de fin diagnostic",
            value=cast(str, st.session_state.get("bt_diag_end", "2026-04-20")),
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
        st.dataframe(history_df, use_container_width=True, hide_index=True)

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

    run_tab, backfill_tab, diagnose_tab, recommend_tab = st.tabs(
        ["▶️ Backtest", "🧱 Backfill scores history", "🧪 Diagnose screener", "🎯 Recommend screener"]
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

    _render_runtime_center()


run_page_if_standalone(__name__, render)


