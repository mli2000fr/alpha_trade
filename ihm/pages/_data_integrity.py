"""ihm/pages/_data_integrity.py — Phase 6.2 (Backlog L10).

Panneau « 5.bis Import News » (event_sentiment.importe_news) extrait de
``pipeline.py``.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import cast

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
from ihm.services.pipeline_runner import (
    build_pipeline_command,
    format_command_for_display,
)
from ihm.services.process_registry import stop_pipeline_run

__all__ = ["_render_import_news_panel"]


def _render_import_news_panel(
    options: PipelineLaunchOptions,
    db_config: dict[str, str | None],
    *,
    workflow_active: bool,
    active_by_step: dict[str, list[dict[str, object]]],
    all_runs: list[dict[str, object]],
    latest_by_step: dict[str, dict[str, object]],
) -> None:
    today = date.today()
    default_start = cast(date, st.session_state.get(IMPORT_NEWS_START_DATE_KEY, today - timedelta(days=7)))
    default_end = cast(date, st.session_state.get(IMPORT_NEWS_END_DATE_KEY, today))

    with st.container(border=True):
        st.markdown("**5.bis Import des news brutes**")
        st.caption(
            "Lance `event_sentiment/importe_news.py` avec une date de début et une date de fin. "
            "Ce run peut être utilisé avant le Sentiment Pipeline complet pour réinjecter une période précise."
        )

        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_value = cast(
                date,
                st.date_input(
                    "Date de début",
                    value=default_start,
                    key=IMPORT_NEWS_START_DATE_KEY,
                    format="YYYY-MM-DD",
                ),
            )
        with date_col2:
            end_value = cast(
                date,
                st.date_input(
                    "Date de fin",
                    value=default_end,
                    key=IMPORT_NEWS_END_DATE_KEY,
                    format="YYYY-MM-DD",
                ),
            )

        import_options = replace(
            options,
            news_import_start_date=start_value.isoformat(),
            news_import_end_date=end_value.isoformat(),
        )
        import_command_preview = format_command_for_display(build_pipeline_command("import_news", import_options))
        st.code(import_command_preview, language="powershell")

        import_active_runs = active_by_step.get("import_news", [])
        locked_by_sentiment = bool(active_by_step.get("sentiment_pipeline"))
        import_locked = workflow_active or locked_by_sentiment

        if workflow_active:
            st.warning("Un workflow complet est en cours : l'import manuel de news est temporairement désactivé.")
        elif locked_by_sentiment:
            st.warning("Le Sentiment Pipeline est déjà actif : attendez sa fin avant de relancer un import de news.")

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
        else:
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
                    "5.bis Import News",
                    import_options,
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
                st.success(f"Import news démarré en arrière-plan : `{record.run_id}`")
                st.rerun()

        _render_step_result(latest_by_step.get("import_news"))
