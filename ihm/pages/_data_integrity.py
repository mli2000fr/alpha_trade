"""ihm/pages/_data_integrity.py — Phase 6.2 (Backlog L10).

Panneau « 7.bis Import News » (event_sentiment.importe_news) extrait de
``pipeline.py``.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date as DateValue, timedelta
from typing import Literal, cast

import streamlit as st

from ihm.pages._shared import (
    COMPARE_RUNS_KEY,
    IMPORT_NEWS_END_DATE_KEY,
    IMPORT_NEWS_START_DATE_KEY,
    PENDING_COMPARE_RUNS_KEY,
    PENDING_SELECTED_RUN_KEY,
    PipelineLaunchOptions,
    _render_step_result,
    _sanitize_compare_ids,
    start_pipeline_run,
)
from ihm.services.pipeline_runner import build_pipeline_command, format_command_for_display
from ihm.services.process_registry import PipelineRunRecord, stop_pipeline_run

__all__ = ["_render_import_news_panel"]


def _coerce_date(value: object, fallback: DateValue) -> DateValue:
    return value if isinstance(value, DateValue) else fallback


def _register_new_run(record: PipelineRunRecord, all_runs: list[dict[str, object]]) -> None:
    st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
    compare_ids = _sanitize_compare_ids(
        [str(run.get("run_id", "")) for run in all_runs if run.get("run_id")],
        {str(run.get("run_id", "")): "" for run in all_runs if run.get("run_id")},
        st.session_state.get(COMPARE_RUNS_KEY, []),
    )
    if record.run_id not in compare_ids:
        st.session_state[PENDING_COMPARE_RUNS_KEY] = [record.run_id, *compare_ids][:2]


def _render_import_news_panel(
    options: PipelineLaunchOptions,
    db_config: dict[str, str | None],
    *,
    workflow_active: bool,
    active_by_step: dict[str, list[dict[str, object]]],
    all_runs: list[dict[str, object]],
    latest_by_step: dict[str, dict[str, object]],
) -> None:
    today = DateValue.today()
    default_start = _coerce_date(st.session_state.get(IMPORT_NEWS_START_DATE_KEY), today - timedelta(days=7))
    default_end = _coerce_date(st.session_state.get(IMPORT_NEWS_END_DATE_KEY), today)

    with st.container(border=True):
        st.markdown("**7.bis Import des news brutes**")
        st.caption(
            "Lance `event_sentiment/importe_news.py` avec une date de début et une date de fin. "
            "Le bouton import brut réutilise la source news et le mode de mapping ticker configurés dans l'étape 7. "
            "Le second bouton exécute un script PowerShell Windows qui enchaîne l'import brut puis relance "
            "`python -m event_sentiment` jusqu'à ce qu'il n'y ait plus d'articles pending dans `news_raw`/`news_sentiment`, "
            "puis lance automatiquement `python -m event_sentiment.history_backfill` sur la même fenêtre, suivi de "
            "`python -m event_sentiment.relevance_backfill` juste après ; "
            "c'est ce bouton qui reprend aussi le re-scoring FinBERT contextualisé (Niveau 4) quand il est activé."
        )

        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_value_raw = st.date_input(
                "Date de début",
                value=default_start,
                key=IMPORT_NEWS_START_DATE_KEY,
                format="YYYY-MM-DD",
            )
            start_value = _coerce_date(start_value_raw, default_start)
        with date_col2:
            end_value_raw = st.date_input(
                "Date de fin",
                value=default_end,
                key=IMPORT_NEWS_END_DATE_KEY,
                format="YYYY-MM-DD",
            )
            end_value = _coerce_date(end_value_raw, default_end)

        source_col, cap_col = st.columns(2)
        symbol_source_options = ("stock_scores", "candidates", "stock_bars_daily")
        current_max_symbols = options.news_import_max_symbols if options.news_import_max_symbols is not None else 0
        current_symbol_source = str(
            st.session_state.get("pipeline_import_news_symbol_source", getattr(options, "news_import_symbol_source", "stock_scores"))
        ).strip().lower()
        if current_symbol_source not in symbol_source_options:
            current_symbol_source = "stock_scores"
        with source_col:
            news_import_symbol_source = str(
                st.selectbox(
                    "Univers de symboles pour l'import",
                    options=symbol_source_options,
                    index=symbol_source_options.index(current_symbol_source),
                    key="pipeline_import_news_symbol_source",
                    help=(
                        "`stock_scores` (défaut) limite l'import aux symboles suivis par le screener ; "
                        "`candidates` aux seuls candidats ; `stock_bars_daily` réactive l'ancien comportement large."
                    ),
                )
            )
        with cap_col:
            news_import_max_symbols = int(
                st.number_input(
                    "Cap sécurité symboles (0 = off)",
                    min_value=0,
                    max_value=100_000,
                    step=50,
                    value=int(current_max_symbols),
                    key="pipeline_import_news_max_symbols",
                    help="Si > 0, le CLI refuse l'import si l'univers résolu dépasse cette limite.",
                )
            )

        news_import_symbols = str(
            st.text_input(
                "Liste explicite de symboles (CSV, prioritaire)",
                value=str(st.session_state.get("pipeline_import_news_symbols", getattr(options, "news_import_symbols", "") or "")),
                key="pipeline_import_news_symbols",
                help="Exemple : AAPL,MSFT,NVDA. Si renseigné, cette liste prime sur l'univers choisi ci-dessus.",
            )
        ).strip().upper()
        if news_import_symbol_source == "stock_bars_daily":
            st.warning(
                "Mode large activé : `stock_bars_daily` peut déclencher un import très volumineux. "
                "Utilisez de préférence `stock_scores`, une shortlist `CSV` ou un cap sécurité."
            )

        import_options = replace(
            options,
            news_import_start_date=start_value.isoformat(),
            news_import_end_date=end_value.isoformat(),
            news_import_symbols=news_import_symbols or None,
            news_import_symbol_source=cast(Literal["stock_scores", "candidates", "stock_bars_daily"], news_import_symbol_source),
            news_import_max_symbols=news_import_max_symbols or None,
        )
        import_command_preview = format_command_for_display(build_pipeline_command("import_news", import_options))
        auto_score_command_preview = format_command_for_display(
            build_pipeline_command("import_news_pending_loop", import_options)
        )
        st.caption("Commande import brut seule (source news + mapping ticker, sans scoring contextuel)")
        st.code(import_command_preview, language="powershell")
        st.caption("Commande PowerShell import + scoring auto jusqu'à `pending=0`, puis history backfill suivi de relevance backfill (reprend aussi le scoring contextuel si activé)")
        st.code(auto_score_command_preview, language="powershell")

        import_active_runs = active_by_step.get("import_news", [])
        auto_score_active_runs = active_by_step.get("import_news_pending_loop", [])
        locked_by_sentiment = bool(active_by_step.get("sentiment_pipeline"))
        import_locked = workflow_active or locked_by_sentiment or bool(auto_score_active_runs)
        auto_score_locked = workflow_active or locked_by_sentiment or bool(import_active_runs)

        if workflow_active:
            st.warning("Un workflow complet est en cours : l'import manuel de news est temporairement désactivé.")
        elif locked_by_sentiment:
            st.warning("Le Sentiment Pipeline est déjà actif : attendez sa fin avant de relancer un import de news.")
        elif auto_score_active_runs:
            st.warning("Le script PowerShell import + scoring + backfill auto est déjà actif : attendez sa fin avant de relancer un import brut.")
        elif import_active_runs:
            st.warning("Un import brut est déjà actif : attendez sa fin avant de lancer le script PowerShell auto complet.")

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
        elif auto_score_active_runs:
            st.info(f"{len(auto_score_active_runs)} run(s) auto import + scoring + backfill déjà actif(s).")
            for run in auto_score_active_runs:
                run_id = str(run.get("run_id", ""))
                st.caption(f"Actif : `{run_id}`")
                if st.button(
                    "⏹️ Arrêter ce run auto import + scoring + backfill",
                    key=f"stop_import_news_pending_loop_run_{run_id}",
                    use_container_width=True,
                ):
                    stop_pipeline_run(run_id)
                    st.rerun()
        else:
            import_col, auto_col = st.columns(2)
            with import_col:
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
                        "7.bis Import News",
                        import_options,
                        db_config=db_config,
                    )
                    _register_new_run(record, all_runs)
                    st.success(f"Import news démarré en arrière-plan : `{record.run_id}`")
                    st.rerun()
            with auto_col:
                auto_clicked = st.button(
                    "⚙️ Import + score + history_backfill + relevance_backfill auto",
                    key="run_pipeline_import_news_pending_loop",
                    use_container_width=True,
                    disabled=auto_score_locked or start_value > end_value,
                )
                if auto_clicked:
                    record = start_pipeline_run(
                        "import_news_pending_loop",
                        "7.bis Import News + scoring + backfill auto",
                        import_options,
                        db_config=db_config,
                    )
                    _register_new_run(record, all_runs)
                    st.success(f"Import + scoring + backfill auto démarrés en arrière-plan : `{record.run_id}`")
                    st.rerun()

        st.caption("Dernier run — import brut")
        _render_step_result(latest_by_step.get("import_news"))
        st.caption("Dernier run — import + scoring + backfill auto")
        _render_step_result(latest_by_step.get("import_news_pending_loop"))
