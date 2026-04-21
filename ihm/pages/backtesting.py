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
    build_backtesting_command,
    format_command_for_display,
)
from ihm.services.db import get_db_status, get_runtime_db_config

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
                "Paramètre": "account_constraint_mode",
                "Explication": "Contraintes de compte simulées : standard / pdt / swing / cash.",
                "Défaut": "standard",
            },
            {"Paramètre": "sentiment_lookback", "Explication": "Fenêtre historique sentiment passée à la CLI backtesting.", "Défaut": "365"},
            {"Paramètre": "no_save", "Explication": "Désactive l'écriture des artefacts PNG/CSV.", "Défaut": "False"},
            {"Paramètre": "ml_mode", "Explication": "auto/off/rebuild-missing pour la composante ML.", "Défaut": "auto"},
            {"Paramètre": "sentiment_mode", "Explication": "auto/off/rebuild-missing pour la composante sentiment.", "Défaut": "auto"},
            {"Paramètre": "artifacts_dir", "Explication": "Dossier des artefacts modèles utilisés pour rebuild-missing.", "Défaut": "artifacts/models"},
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
        account_constraint_mode = cast(
            str,
            st.selectbox(
                "Contraintes de compte",
                options=["standard", "pdt", "swing", "cash"],
                index=["standard", "pdt", "swing", "cash"].index(
                    cast(str, st.session_state.get("bt_run_account_constraint_mode", "standard"))
                    if st.session_state.get("bt_run_account_constraint_mode", "standard") in {"standard", "pdt", "swing", "cash"}
                    else "standard"
                ),
                key="bt_run_account_constraint_mode",
                help=(
                    "`standard` = comportement historique. `pdt` = max 3 day trades / 5 séances sous 25k. "
                    "`swing` = aucune sortie le jour même. `cash` = cash settled uniquement (T+1 par défaut)."
                ),
            ),
        )
    with col9:
        sentiment_lookback = st.number_input(
            "Sentiment lookback (jours)",
            min_value=1,
            max_value=3650,
            value=int(st.session_state.get("bt_run_sentiment_lookback", 365)),
            step=1,
            key="bt_run_sentiment_lookback",
            help="Paramètre CLI exposé par le backtesting. À conserver cohérent avec vos hypothèses research.",
        )
    with col10:
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
    with col11:
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

    col12, col13 = st.columns(2)
    with col12:
        no_save = st.checkbox(
            "Ne pas sauver les artefacts",
            value=bool(st.session_state.get("bt_run_no_save", False)),
            key="bt_run_no_save",
            help="Si coché, le PNG d'equity curve et le CSV des trades ne seront pas écrits dans `artifacts/backtesting/`.",
        )
    with col13:
        st.caption(
            "Mode `pdt` : la 4e tentative de day trade sur 5 séances est bloquée et reportée au lendemain."
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
        account_constraint_mode=cast(Any, account_constraint_mode),
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


def render() -> None:
    st.header("🧪 Backtesting intégré")
    st.caption(
        "Page opérateur dédiée au backtesting : configuration complète, lancement direct depuis l'IHM, "
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

    run_tab, backfill_tab = st.tabs(["▶️ Backtest", "🧱 Backfill scores history"])
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

    _render_runtime_center()


run_page_if_standalone(__name__, render)


