"""ihm/pages/screening.py — Consultation des scores stock_scores."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.metrics import metric_row
from ihm.components.tables import show_dataframe
from ihm.services.screener_artifact_history import (
    SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY,
    build_global_screener_artifact_history,
    build_screener_artifact_history_rows,
    format_screener_artifact_history_label,
    resolve_selected_screener_artifacts_dir,
)
from ihm.services.screener_preferences import (
    load_persisted_selected_screener_artifacts_dir,
    save_persisted_selected_screener_artifacts_dir,
)
from ihm.services.screener_recommendations import (
    list_screener_csv_files,
    load_screener_csv_preview,
    load_screener_recommendation_report,
)
from ihm.services.db import db_available
from ihm.services.process_registry import list_active_pipeline_runs, load_pipeline_history
from ihm.services.run_summary import build_latest_run_summary_rows
from ihm.services.queries import get_stock_scores

SCREENER_ARTIFACT_SELECTBOX_KEY = "screening_screener_artifacts_dir_select"
SCREENER_CSV_PREVIEW_SELECTBOX_KEY = "screening_screener_csv_preview_select"
SCREENER_CSV_PREVIEW_ROWS_KEY = "screening_screener_csv_preview_rows"


def _merge_pipeline_runs() -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {str(run["run_id"]): run for run in load_pipeline_history()}
    for run in list_active_pipeline_runs():
        merged[str(run["run_id"])] = run
    return sorted(
        merged.values(),
        key=lambda item: str(item.get("finished_at") or item.get("executed_at") or ""),
        reverse=True,
    )


def _build_quality_summary_rows(runs: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(
        build_latest_run_summary_rows(
            runs,
            [
                {"label": "Import univers Alpaca", "step_keys": ["import_alpaca_assets"]},
                {"label": "Import Alpaca Bar", "step_keys": ["import_alpaca_bar"]},
                {"label": "Data Sanitizer Daily", "step_keys": ["data_sanitizer_daily"]},
                {"label": "Stock Screener", "step_keys": ["stock_screener"]},
                {"label": "Mise à jour fondamentaux", "step_keys": ["update_sector"]},
                {"label": "Sync Latest Quotes", "step_keys": ["sync_latest_quotes"]},
                {"label": "Sync Earnings Calendar", "step_keys": ["sync_earnings_calendar"]},
                {"label": "Alpha Scanner", "step_keys": ["alpha_scanner"]},
                {"label": "Workflow complet", "run_kind": "workflow"},
            ],
        )
    )


def _build_objective_recommendation_rows(report: dict[str, object]) -> pd.DataFrame:
    objective_rows = report.get("objective_rows_df")
    if not isinstance(objective_rows, pd.DataFrame) or objective_rows.empty:
        return pd.DataFrame()

    columns = [
        ("objective_label", "Objectif"),
        ("scenario_name", "Scénario recommandé"),
        ("objective_scope", "Périmètre"),
        ("objective_score", "Score objectif"),
        ("overall_score", "Score global"),
        ("reason", "Pourquoi"),
    ]
    available_columns = [column for column, _ in columns if column in objective_rows.columns]
    formatted = objective_rows.loc[:, available_columns].copy()
    return formatted.rename(columns={column: label for column, label in columns if column in formatted.columns})


def _build_objective_metric_cards(report: dict[str, object]) -> list[tuple[str, str, str | None]]:
    objective_rows = report.get("objective_rows_df")
    if not isinstance(objective_rows, pd.DataFrame) or objective_rows.empty:
        return []

    cards: list[tuple[str, str, str | None]] = []
    for _, row in objective_rows.iterrows():
        cards.append(
            (
                str(row.get("objective_label") or row.get("objective") or "Objectif"),
                str(row.get("scenario_name") or "—"),
                str(row.get("objective_scope") or "global"),
            )
        )
    return cards


def _build_artifact_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame:
    rows = build_screener_artifact_history_rows(history_entries)
    return pd.DataFrame(rows)


def _format_csv_preview_option(file_info: dict[str, object]) -> str:
    return "{} | lignes={} | {}".format(
        str(file_info.get("label") or file_info.get("key") or "csv"),
        file_info.get("row_count") if file_info.get("row_count") is not None else "?",
        str(file_info.get("size_label") or "—"),
    )


def _build_csv_preview_inventory_dataframe(files: list[dict[str, object]]) -> pd.DataFrame:
    if not files:
        return pd.DataFrame()
    frame = pd.DataFrame(files)
    column_labels = {
        "label": "Fichier",
        "row_count": "Lignes",
        "size_label": "Taille",
        "path": "Chemin",
    }
    available_columns = [column for column in column_labels if column in frame.columns]
    if not available_columns:
        return pd.DataFrame()
    return frame.loc[:, available_columns].rename(columns=column_labels)


def _render_screener_artifact_selector() -> tuple[str, dict[str, object]]:
    st.subheader("🗂️ Source d'artefacts screener")
    st.caption(
        "Sélectionne ici le dossier d'artefacts screener à explorer. La sélection est partagée avec la vue `Overview`."
    )
    history_entries = build_global_screener_artifact_history()
    session_selected_dir = str(st.session_state.get(SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY, "") or "").strip()
    persisted_selected_dir = load_persisted_selected_screener_artifacts_dir()
    preferred_dir = session_selected_dir or persisted_selected_dir
    selected_dir, entry_map = resolve_selected_screener_artifacts_dir(history_entries, preferred_dir)
    restored_from_persistence = not session_selected_dir and bool(persisted_selected_dir)
    options = list(entry_map.keys())
    st.session_state[SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY] = selected_dir
    if st.session_state.get(SCREENER_ARTIFACT_SELECTBOX_KEY) != selected_dir:
        st.session_state[SCREENER_ARTIFACT_SELECTBOX_KEY] = selected_dir
    selected_dir = st.selectbox(
        "Répertoire d'artefacts",
        options=options,
        format_func=lambda value: format_screener_artifact_history_label(entry_map[value]),
        index=options.index(selected_dir),
        key=SCREENER_ARTIFACT_SELECTBOX_KEY,
    )
    st.session_state[SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY] = selected_dir
    if persisted_selected_dir != selected_dir:
        save_persisted_selected_screener_artifacts_dir(selected_dir)

    selected_entry = entry_map[selected_dir]
    if restored_from_persistence:
        st.caption("Préférence restaurée depuis la dernière session IHM.")
    st.caption(
        f"Sélection active : `{selected_dir}` · Couverture : {selected_entry.get('coverage_label', 'Période non renseignée')} · "
        f"MAJ : {selected_entry.get('updated_at_label', 'inconnue')}"
    )

    history_df = _build_artifact_history_dataframe(list(entry_map.values()))
    if not history_df.empty:
        with st.expander("🗃️ Historique global des répertoires screener", expanded=False):
            st.dataframe(history_df, use_container_width=True, hide_index=True)
    return selected_dir, selected_entry


def _render_screener_csv_preview(artifacts_dir: str, selected_entry: dict[str, object]) -> None:
    st.subheader("🔎 Exploration détaillée des CSV screener")
    st.caption(
        "Prévisualisation bornée des CSV du répertoire screener sélectionné dans l'historique global."
    )
    summary = selected_entry.get("summary") if isinstance(selected_entry.get("summary"), dict) else None
    available_files = list_screener_csv_files(artifacts_dir, summary=summary)
    if not available_files:
        st.info("Aucun CSV screener prévisualisable détecté dans le répertoire sélectionné.")
        return

    file_map = {str(file_info.get("key") or ""): file_info for file_info in available_files}
    available_keys = [str(file_info.get("key") or "") for file_info in available_files]
    selected_file_key = str(st.session_state.get(SCREENER_CSV_PREVIEW_SELECTBOX_KEY, "") or "")
    if selected_file_key not in available_keys:
        selected_file_key = available_keys[0]
        st.session_state[SCREENER_CSV_PREVIEW_SELECTBOX_KEY] = selected_file_key

    col1, col2 = st.columns([3, 1])
    with col1:
        selected_file_key = st.selectbox(
            "CSV à explorer",
            options=available_keys,
            format_func=lambda value: _format_csv_preview_option(file_map[value]),
            index=available_keys.index(selected_file_key),
            key=SCREENER_CSV_PREVIEW_SELECTBOX_KEY,
        )
    with col2:
        preview_rows = st.number_input(
            "Lignes à prévisualiser",
            min_value=10,
            max_value=500,
            value=int(st.session_state.get(SCREENER_CSV_PREVIEW_ROWS_KEY, 100)),
            step=10,
            key=SCREENER_CSV_PREVIEW_ROWS_KEY,
            help="Lecture bornée pour éviter de charger tout le CSV en mémoire dans l'IHM.",
        )

    preview = load_screener_csv_preview(
        artifacts_dir,
        file_key=selected_file_key,
        max_rows=int(preview_rows),
        summary=summary,
    )
    selected_file = preview.get("selected_file")
    if isinstance(selected_file, dict):
        st.caption(
            f"Fichier actif : `{selected_file.get('path', '')}` · lignes totales : {selected_file.get('row_count', '—')} · taille : {selected_file.get('size_label', '—')}"
        )

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Lignes previewées", int(preview.get("preview_rows") or 0))
    metric_col2.metric("Lignes totales", preview.get("total_rows") if preview.get("total_rows") is not None else "—")
    metric_col3.metric("Colonnes", int(preview.get("column_count") or 0))

    inventory_df = _build_csv_preview_inventory_dataframe(preview.get("available_files") if isinstance(preview.get("available_files"), list) else [])
    if not inventory_df.empty:
        with st.expander("📁 Inventaire des CSV prévisualisables", expanded=False):
            st.dataframe(inventory_df, use_container_width=True, hide_index=True)

    preview_df = preview.get("preview_df")
    if isinstance(preview_df, pd.DataFrame) and not preview_df.empty:
        st.dataframe(preview_df, use_container_width=True, hide_index=True, height=320)
        if bool(preview.get("truncated")):
            st.caption(
                f"Prévisualisation limitée aux {preview.get('max_rows')} premières ligne(s)."
            )
    elif isinstance(selected_file, dict):
        path = Path(str(selected_file.get("path") or ""))
        if path.exists() and path.is_file():
            st.info("Le CSV sélectionné ne contient aucune ligne de données à prévisualiser.")

    errors = preview.get("errors")
    if isinstance(errors, list) and errors:
        with st.expander("ℹ️ Détails de lecture de la preview CSV", expanded=False):
            for error in errors:
                st.caption(f"- {error}")


def _render_objective_recommendations(artifacts_dir: str) -> None:
    report = load_screener_recommendation_report(artifacts_dir)
    if not bool(report.get("available")):
        st.info("Aucune recommandation screener phase 7/8 détectée pour le répertoire sélectionné.")
        artifacts_dir = report.get("artifacts_dir")
        if artifacts_dir:
            st.caption(f"Répertoire attendu : `{artifacts_dir}`")
        return

    st.subheader("🎯 Recommandations screener par objectif")
    st.caption(
        "Lecture directe des artefacts `recommend-screener` pour exposer les profils robuste / offensif / bear / exécutable dans l'IHM."
    )
    st.caption(
        "Pour recalculer ces artefacts depuis l'IHM, utilise la page `🧪 Backtesting` puis les onglets `Diagnose screener` ou `Recommend screener`."
    )
    st.caption(
        f"Artefacts : `{report.get('artifacts_dir')}` · Période : {report.get('coverage_label', 'Période non renseignée')} · "
        f"MAJ : {report.get('updated_at_label', 'inconnue')}"
    )

    metric_cards = _build_objective_metric_cards(report)
    if metric_cards:
        metric_row(metric_cards)

    objective_rows = _build_objective_recommendation_rows(report)
    if not objective_rows.empty:
        show_dataframe(objective_rows, "Leaders phase 7 par objectif", height=240)

    leaderboard = report.get("leaderboard_df")
    if isinstance(leaderboard, pd.DataFrame) and not leaderboard.empty:
        show_dataframe(leaderboard, "Classement détaillé phase 7", height=320)

    errors = report.get("errors")
    if isinstance(errors, list) and errors:
        with st.expander("ℹ️ Détails de chargement des artefacts", expanded=False):
            for error in errors:
                st.caption(f"- {error}")


def render() -> None:
    st.header("📊 Screening — Stock Scores")

    if not db_available():
        render_db_unavailable("Screening", form_key="screening_db_form")
        return

    df = get_stock_scores()
    if df.empty:
        render_query_diagnostic("Aucune donnée dans `stock_scores`.")
        return

    # --- KPI ---
    total = len(df)
    candidates = int(df["is_candidate"].sum()) if "is_candidate" in df.columns else 0
    sectors = df["sector"].nunique() if "sector" in df.columns else 0
    metric_row([
        ("Total symboles", total, None),
        ("Candidats", candidates, None),
        ("Secteurs", sectors, None),
    ])

    quality_rows = _build_quality_summary_rows(_merge_pipeline_runs())
    if not quality_rows.empty:
        st.subheader("🛡️ Contexte pipeline & qualité amont")
        show_dataframe(quality_rows)

    selected_artifacts_dir, selected_artifacts_entry = _render_screener_artifact_selector()
    _render_objective_recommendations(selected_artifacts_dir)
    _render_screener_csv_preview(selected_artifacts_dir, selected_artifacts_entry)

    # --- Filtres ---
    st.subheader("Filtres")
    col1, col2, col3 = st.columns(3)
    with col1:
        symbol_filter = st.text_input("Symbole", "").upper().strip()
    with col2:
        sector_list = ["Tous"] + sorted(df["sector"].dropna().unique().tolist()) if "sector" in df.columns else ["Tous"]
        sector_filter = st.selectbox("Secteur", sector_list)
    with col3:
        candidates_only = st.checkbox("Candidats uniquement", value=False)

    col4, col5 = st.columns(2)
    with col4:
        min_score = st.slider("Score minimum (total_score)", 0.0, 1.0, 0.0, 0.01)
    with col5:
        sentiment_only = st.checkbox("Sentiment actif uniquement", value=False)

    # --- Appliquer filtres ---
    filtered = df.copy()
    if symbol_filter:
        filtered = filtered[filtered["symbol"].str.contains(symbol_filter, case=False, na=False)]
    if sector_filter != "Tous":
        filtered = filtered[filtered["sector"] == sector_filter]
    if candidates_only:
        filtered = filtered[filtered["is_candidate"] == 1]
    if min_score > 0 and "total_score" in filtered.columns:
        filtered = filtered[filtered["total_score"] >= min_score]
    if sentiment_only and "signal_active" in filtered.columns:
        filtered = filtered[filtered["signal_active"] == 1]

    show_dataframe(filtered, f"Résultats ({len(filtered)} lignes)", height=500)


run_page_if_standalone(__name__, render)


