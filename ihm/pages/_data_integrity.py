"""ihm/pages/_data_integrity.py — Phase 6.2 (Backlog L10).

Panneau « 7.bis Import News » (event_sentiment.importe_news) extrait de
``pipeline.py``.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date as DateValue, timedelta
from typing import Literal, cast

import streamlit as st
from event_sentiment.db_io import EventSentimentRepository
from event_sentiment.importe_news import (
    STOCK_BARS_DAILY_WARNING_THRESHOLD,
    resolve_symbols_from_inputs,
)

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
from ihm.services.queries import get_backfill_completeness_diagnostic

__all__ = ["_render_import_news_panel"]


NEWS_IMPORT_SYMBOL_SOURCE_OPTIONS = (
    "stock_scores",
    "stock_scores_history",
    "stock_scores_all",
    "candidates",
    "stock_bars_daily",
)


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


@st.cache_data(ttl=60, show_spinner=False)
def _resolve_import_news_scope_preview(
    symbols_csv: str,
    symbol_source: str,
) -> dict[str, object]:
    repository = EventSentimentRepository()
    symbols, effective_source = resolve_symbols_from_inputs(
        symbols_csv=symbols_csv or None,
        symbol_source=symbol_source,
        repository=repository,
    )
    return {
        "effective_source": effective_source,
        "symbol_count": len(symbols),
        "sample_symbols": symbols[:10],
    }


def _backfill_diag_int(diag: dict[str, object], key: str, default: int = 0) -> int:
    """Extrait un int depuis un dict[str, object] sans avertissement de typage."""
    value = diag.get(key, default)
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _backfill_diag_float(diag: dict[str, object], key: str, default: float = 0.0) -> float:
    """Extrait un float depuis un dict[str, object] sans avertissement de typage."""
    value = diag.get(key, default)
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _render_backfill_completeness_panel(
    start_value: DateValue,
    end_value: DateValue,
) -> None:
    """Panneau de compteurs de complétude des backfills history + relevance."""

    with st.expander("📊 Compteurs de complétude — History & Relevance backfill", expanded=False):
        st.caption(
            "Ces compteurs interrogent la base en temps réel pour vérifier l'avancement "
            "des deux backfills sur la fenêtre configurée ci-dessus (date début → date fin). "
            "Le TTL de cache est de 30 s ; cliquez sur 🔄 pour forcer l'actualisation."
        )

        col_refresh, _ = st.columns([1, 5])
        with col_refresh:
            if st.button("🔄 Actualiser les compteurs", key="refresh_backfill_completeness"):
                get_backfill_completeness_diagnostic.clear()  # type: ignore[attr-defined]

        diag = get_backfill_completeness_diagnostic(
            start_date=start_value,
            end_date=end_value,
        )

        if diag.get("query_error"):
            st.error(f"Erreur lors du calcul des compteurs : {diag['query_error']}")
            return

        st.markdown("##### History backfill (`ticker_daily_sentiment_features`)")
        st.caption(
            "Compare les trade-dates scorées (articles avec `news_sentiment`) "
            "avec les trade-dates couvertes dans `ticker_daily_sentiment_features`. "
            "**Zéro date manquante = backfill complet** sur cette fenêtre."
        )
        h_scored = _backfill_diag_int(diag, "history_scored_dates")
        h_covered = _backfill_diag_int(diag, "history_covered_dates")
        h_missing = _backfill_diag_int(diag, "history_missing_dates")
        h_pct = _backfill_diag_float(diag, "history_pct", 100.0)

        h_col1, h_col2, h_col3 = st.columns(3)
        with h_col1:
            st.metric("Dates scorées (source)", h_scored)
        with h_col2:
            st.metric("Dates couvertes (features)", h_covered)
        with h_col3:
            st.metric(
                "Dates manquantes 🔴",
                h_missing,
                help="Nombre de trade-dates avec des articles scorés mais sans entrée dans ticker_daily_sentiment_features.",
            )

        if h_missing == 0 and h_scored > 0:
            st.success(f"✅ History backfill **complet** sur la période ({h_pct:.1f} % couvert).")
        elif h_missing == 0 and h_scored == 0:
            st.info("Aucun article scoré sur cette période — rien à reconstruire.")
        else:
            st.warning(
                f"⚠️ {h_missing} trade-date(s) manquante(s) dans `ticker_daily_sentiment_features` "
                f"({h_pct:.1f} % des dates scorées couvertes). "
                "→ Relancez **Rebuild daily sentiment features only** pour les combler."
            )
            if h_scored > 0:
                progress_val = min(1.0, max(0.0, h_covered / h_scored))
                st.progress(progress_val, text=f"{h_covered}/{h_scored} dates couvertes")

        st.divider()

        st.markdown("##### Relevance backfill — Niveau 2/3 (`news_ticker_map.relevance_score`)")
        st.caption(
            "Compte les paires article↔ticker dans `news_ticker_map` dont le "
            "`relevance_score` n'a pas encore été calculé. "
            "**Zéro NULL = backfill relevance complet** sur cette fenêtre."
        )
        r_null = _backfill_diag_int(diag, "relevance_null")
        r_scored = _backfill_diag_int(diag, "relevance_scored")
        r_total = _backfill_diag_int(diag, "relevance_total")
        r_pct = _backfill_diag_float(diag, "relevance_pct", 100.0)

        r_col1, r_col2, r_col3 = st.columns(3)
        with r_col1:
            st.metric("Total paires ticker_map", r_total)
        with r_col2:
            st.metric("Paires avec relevance_score", r_scored)
        with r_col3:
            st.metric(
                "Paires sans relevance_score 🔴",
                r_null,
                help="Paires pour lesquelles le relevance_score (Niveau 2/3) n'a pas encore été calculé.",
            )

        if r_null == 0 and r_total > 0:
            st.success(f"✅ Relevance backfill **complet** sur la période ({r_pct:.1f} % scoré).")
        elif r_total == 0:
            st.info("Aucune paire article↔ticker sur cette période.")
        else:
            st.warning(
                f"⚠️ {r_null} paire(s) sans `relevance_score` "
                f"({r_pct:.1f} % des paires scorées). "
                "→ Relancez **relevance_backfill** (étape 7bis) pour combler."
            )
            if r_total > 0:
                progress_val = min(1.0, max(0.0, r_scored / r_total))
                st.progress(progress_val, text=f"{r_scored}/{r_total} paires scorées")

        st.divider()

        st.markdown("##### Contextual backfill — Niveau 4 FinBERT (`news_ticker_sentiment`)")
        st.caption(
            "Compte les paires article↔ticker présentes dans `news_ticker_map` "
            "mais absentes de `news_ticker_sentiment`. "
            "**Zéro pending = backfill contextuel complet** sur cette fenêtre "
            "(uniquement pertinent si le scoring contextuel Niveau 4 est activé)."
        )
        c_pending = _backfill_diag_int(diag, "contextual_pending")
        c_scored = _backfill_diag_int(diag, "contextual_scored")
        c_total = _backfill_diag_int(diag, "contextual_total")
        c_pct = _backfill_diag_float(diag, "contextual_pct", 100.0)

        c_col1, c_col2, c_col3 = st.columns(3)
        with c_col1:
            st.metric("Total paires ticker_map", c_total)
        with c_col2:
            st.metric("Paires dans news_ticker_sentiment", c_scored)
        with c_col3:
            st.metric(
                "Paires en attente contextuel 🟡",
                c_pending,
                help="Paires absentes de news_ticker_sentiment (scoring FinBERT Niveau 4 non encore effectué).",
            )

        if c_pending == 0 and c_total > 0:
            st.success(f"✅ Contextual backfill **complet** sur la période ({c_pct:.1f} % scoré).")
        elif c_total == 0:
            st.info("Aucune paire article↔ticker sur cette période.")
        else:
            st.info(
                f"ℹ️ {c_pending} paire(s) sans score contextuel FinBERT "
                f"({c_pct:.1f} % des paires traitées). "
                "→ Activez `--rescore-contextual` sur le bouton **relevance_backfill** si nécessaire."
            )
            if c_total > 0:
                progress_val = min(1.0, max(0.0, c_scored / c_total))
                st.progress(progress_val, text=f"{c_scored}/{c_total} paires scorées contextuellement")


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
            "Le bouton scoring seul relance uniquement `python -m event_sentiment --skip-ingestion` sur la même fenêtre et le même univers 7.bis, "
            "en respectant le `mode de scoring` choisi dans le bloc `Event Sentiment`. "
            "Le bouton intermédiaire reprend uniquement le complément post-import (score + history backfill + relevance backfill). "
            "Le bouton `Rebuild daily sentiment features only` reconstruit uniquement les features journalières sentiment sur la fenêtre choisie. "
            "Le dernier bouton exécute un script PowerShell Windows qui enchaîne l'import brut puis relance "
            "`python -m event_sentiment` jusqu'à ce qu'il n'y ait plus d'articles pending dans `news_raw`/`news_sentiment`, "
            "puis lance automatiquement `python -m event_sentiment.history_backfill` sur la même fenêtre, suivi de "
            "`python -m event_sentiment.relevance_backfill` juste après ; "
            "c'est ce bouton qui reprend aussi le re-scoring FinBERT contextualisé (Niveau 4) quand il est activé."
        )
        with st.expander("Mini guide d'usage — quand lancer quoi ?", expanded=False):
            st.markdown(
                "- **`Standard only`** (étape 7) : **1er passage obligatoire** — remplit `news_sentiment` (1 score par article). "
                "Aucune dépendance au `relevance_score` : peut tourner avant le relevance backfill.\n"
                "- **7bis Phase 1 — relevance backfill sans contextual** : **2e passage** — calcule `relevance_score` dans `news_ticker_map`. "
                "À faire avant le contextual pour que le filtre `min-relevance` soit réel (sinon `COALESCE = 1.0` sur les NULL → filtre inopérant).\n"
                "- **`Rebuild daily sentiment features only`** : **3e passage** — reconstruit les agrégats journaliers `ticker_daily_sentiment_features` / `sector_daily_sentiment_features` "
                "pondérés par le vrai `relevance_score` (à faire après la Phase 1 ci-dessus).\n"
                "- **`Ajouter le contextual à ce backfill 7bis`** (coché par défaut) **ou `Contextual only`** : **4e passage** — scoring FinBERT par paire (article, ticker) → `news_ticker_sentiment`. "
                "Le filtre `min-relevance 0.3` est maintenant opérant car tous les `relevance_score` sont calculés.\n"
                "- **`Standard + contextual`** : pratique sur une fenêtre courte/moyenne quand vous voulez tout faire en un seul run (sans passer par les phases séparées)."
            )
            st.info(
                "**Ordre optimal (backfill complet) :** "
                "① Étape 7 `Standard only` → ② 7bis relevance backfill (sans contextual) → "
                "③ `Rebuild daily sentiment features only` → ④ 7bis avec `Ajouter le contextual` coché → "
                "⑤ `signal_aggregator` pour refléter dans `stock_scores`.\n\n"
                "⚠️ Faire le contextual **avant** le relevance backfill est possible mais déconseillé : "
                "le filtre `min-relevance` sera inopérant sur les paires sans `relevance_score` (traitées avec `COALESCE = 1.0`)."
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
        current_max_symbols = int(options.news_import_max_symbols or 0)
        current_symbol_source = str(
            st.session_state.get("pipeline_import_news_symbol_source", getattr(options, "news_import_symbol_source", "stock_scores_all"))
        ).strip().lower()
        if current_symbol_source not in NEWS_IMPORT_SYMBOL_SOURCE_OPTIONS:
            current_symbol_source = "stock_scores_all"
        with source_col:
            news_import_symbol_source = str(
                st.selectbox(
                    "Univers de symboles pour l'import",
                    options=NEWS_IMPORT_SYMBOL_SOURCE_OPTIONS,
                    index=NEWS_IMPORT_SYMBOL_SOURCE_OPTIONS.index(current_symbol_source),
                    key="pipeline_import_news_symbol_source",
                    help=(
                        "`stock_scores_all` (défaut) cible l'union dédupliquée des symboles présents dans `stock_scores` ou `stock_scores_history` ; "
                        "`stock_scores` limite l'import aux symboles du snapshot courant `stock_scores` ; "
                        "`stock_scores_history` cible les symboles déjà présents dans `stock_scores_history` ; "
                        "`candidates` limite aux seuls candidats ; `stock_bars_daily` réactive l'ancien comportement large."
                    ),
                )
            )
            st.caption(
                "Aide rapide : `stock_scores_all` = union `stock_scores` + `stock_scores_history` ; "
                "`stock_scores` = snapshot screener courant ; "
                "`stock_scores_history` = historique PIT ; "
                "un symbole présent dans l'une ou l'autre table est retenu avec `stock_scores_all`."
            )
        with cap_col:
            news_import_max_symbols_raw = st.number_input(
                "Cap sécurité symboles (0 = off)",
                min_value=0,
                max_value=100_000,
                step=50,
                value=int(current_max_symbols),
                key="pipeline_import_news_max_symbols",
                help="Si > 0, le CLI refuse l'import si l'univers résolu dépasse cette limite.",
            )
            news_import_max_symbols = int(news_import_max_symbols_raw) if news_import_max_symbols_raw is not None else 0

        news_import_resume_from_checkpoint = bool(
            st.checkbox(
                "Réutiliser `news_ingestion_checkpoint` pour l'import news",
                value=bool(st.session_state.get("pipeline_import_news_resume_from_checkpoint", False)),
                key="pipeline_import_news_resume_from_checkpoint",
                help=(
                    "Si coché, les boutons qui réimportent des news reprennent depuis le watermark/checkpoint connu par symbole au lieu de repartir systématiquement de la date de début. "
                    "Utile pour éviter un refetch complet quand la période est déjà presque à jour."
                ),
            )
        )
        st.caption(
            "Cette option ne s'applique qu'aux boutons qui contiennent réellement l'étape d'import news. "
            "Si le checkpoint couvre déjà la date de fin sélectionnée pour un symbole, l'import de ce symbole est sauté."
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
                "Utilisez de préférence `stock_scores_all`, `stock_scores`, une shortlist `CSV` ou un cap sécurité."
            )

        try:
            scope_preview = _resolve_import_news_scope_preview(
                news_import_symbols,
                news_import_symbol_source,
            )
        except Exception as exc:
            st.warning(f"Impossible de résoudre l'univers de symboles en live : {exc}")
            scope_preview = None

        if isinstance(scope_preview, dict):
            effective_source = str(scope_preview.get("effective_source") or news_import_symbol_source)
            raw_symbol_count = scope_preview.get("symbol_count")
            resolved_count = int(raw_symbol_count) if isinstance(raw_symbol_count, (int, float, str)) else 0
            raw_sample_symbols = scope_preview.get("sample_symbols")
            sample_symbols = [str(value) for value in raw_sample_symbols] if isinstance(raw_sample_symbols, list) else []

            metric_col1, metric_col2 = st.columns(2)
            with metric_col1:
                st.metric("Symboles réellement résolus", resolved_count)
            with metric_col2:
                st.metric("Source effective", effective_source)

            if news_import_max_symbols and resolved_count > news_import_max_symbols:
                st.error(
                    "Le cap sécurité empêchera le lancement : "
                    f"{resolved_count} symbole(s) résolus pour `max-symbols={news_import_max_symbols}`."
                )
            elif resolved_count == 0:
                st.warning("Aucun symbole ne serait importé avec les paramètres actuels.")
            elif (
                effective_source == "stock_bars_daily"
                and resolved_count > STOCK_BARS_DAILY_WARNING_THRESHOLD
            ):
                st.warning(
                    "Univers très large détecté avant lancement : "
                    f"{resolved_count} symbole(s) pour `stock_bars_daily` "
                    f"(seuil d'alerte={STOCK_BARS_DAILY_WARNING_THRESHOLD})."
                )
            else:
                st.caption(
                    f"Prévisualisation live : {resolved_count} symbole(s) seront ciblés si vous lancez maintenant."
                )

            if sample_symbols:
                preview_suffix = " …" if resolved_count > len(sample_symbols) else ""
                st.caption(
                    "Extrait des premiers symboles résolus : `"
                    + ", ".join(sample_symbols)
                    + preview_suffix
                    + "`"
                )

        import_options = replace(
            options,
            news_import_start_date=start_value.isoformat(),
            news_import_end_date=end_value.isoformat(),
            news_import_symbols=news_import_symbols or None,
            news_import_symbol_source=cast(
                Literal[
                    "stock_scores",
                    "stock_scores_history",
                    "stock_scores_all",
                    "candidates",
                    "stock_bars_daily",
                ],
                news_import_symbol_source,
            ),
            news_import_max_symbols=news_import_max_symbols or None,
            news_import_resume_from_checkpoint=news_import_resume_from_checkpoint,
        )
        import_command_preview = format_command_for_display(build_pipeline_command("import_news", import_options))
        score_only_command_preview = format_command_for_display(
            build_pipeline_command("score_sentiment_only", import_options)
        )
        auto_score_command_preview = format_command_for_display(
            build_pipeline_command("import_news_pending_loop", import_options)
        )
        auto_followup_command_preview = format_command_for_display(
            build_pipeline_command("score_history_relevance_backfill_auto", import_options)
        )
        rebuild_features_command_preview = format_command_for_display(
            build_pipeline_command("rebuild_daily_sentiment_features_only", import_options)
        )
        st.caption("Commande import brut seule (source news + mapping ticker, sans scoring contextuel)")
        st.code(import_command_preview, language="powershell")
        st.caption(
            "Commande dédiée — scoring sentiment seul sur le scope 7.bis "
            "(mode standard/contextual selon le paramétrage `Event Sentiment — mode de scoring` ; sans réimport)"
        )
        st.code(score_only_command_preview, language="powershell")
        st.caption("Commande dédiée — reconstruction seule des features sentiment journalières")
        st.code(rebuild_features_command_preview, language="powershell")
        st.caption(
            "Commande PowerShell score + history backfill + relevance backfill auto "
            "(sans import brut ; traite le backlog déjà importé dans la fenêtre)"
        )
        st.code(auto_followup_command_preview, language="powershell")
        st.caption("Commande PowerShell import + scoring auto jusqu'à `pending=0`, puis history backfill suivi de relevance backfill (reprend aussi le scoring contextuel si activé)")
        st.code(auto_score_command_preview, language="powershell")

        import_active_runs = active_by_step.get("import_news", [])
        score_only_active_runs = active_by_step.get("score_sentiment_only", [])
        rebuild_features_active_runs = active_by_step.get("rebuild_daily_sentiment_features_only", [])
        auto_followup_active_runs = active_by_step.get("score_history_relevance_backfill_auto", [])
        auto_score_active_runs = active_by_step.get("import_news_pending_loop", [])
        locked_by_sentiment = bool(active_by_step.get("sentiment_pipeline"))
        import_locked = workflow_active or locked_by_sentiment or bool(score_only_active_runs) or bool(auto_score_active_runs) or bool(auto_followup_active_runs) or bool(rebuild_features_active_runs)
        score_only_locked = workflow_active or locked_by_sentiment or bool(import_active_runs) or bool(auto_followup_active_runs) or bool(auto_score_active_runs) or bool(rebuild_features_active_runs)
        rebuild_features_locked = workflow_active or locked_by_sentiment or bool(import_active_runs) or bool(score_only_active_runs) or bool(auto_followup_active_runs) or bool(auto_score_active_runs)
        auto_followup_locked = workflow_active or locked_by_sentiment or bool(import_active_runs) or bool(score_only_active_runs) or bool(auto_score_active_runs) or bool(rebuild_features_active_runs)
        auto_score_locked = workflow_active or locked_by_sentiment or bool(import_active_runs) or bool(score_only_active_runs) or bool(auto_followup_active_runs) or bool(rebuild_features_active_runs)

        if workflow_active:
            st.warning("Un workflow complet est en cours : l'import manuel de news est temporairement désactivé.")
        elif locked_by_sentiment:
            st.warning("Le Sentiment Pipeline est déjà actif : attendez sa fin avant de relancer un import de news.")
        elif auto_followup_active_runs:
            st.warning(
                "Le script PowerShell score + history backfill + relevance backfill auto est déjà actif : "
                "attendez sa fin avant de relancer un import brut ou le run auto complet."
            )
        elif score_only_active_runs:
            st.warning(
                "Un scoring sentiment seul sur le scope 7.bis est déjà actif : "
                "attendez sa fin avant de relancer un import brut ou un autre run 7.bis."
            )
        elif rebuild_features_active_runs:
            st.warning(
                "Une reconstruction dédiée des features sentiment journalières est déjà active : "
                "attendez sa fin avant de relancer un autre run 7.bis."
            )
        elif auto_score_active_runs:
            st.warning("Le script PowerShell import + scoring + backfill auto est déjà actif : attendez sa fin avant de relancer un import brut.")
        elif import_active_runs:
            st.warning("Un import brut est déjà actif : attendez sa fin avant de lancer un script PowerShell auto complémentaire ou complet.")

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
        elif auto_followup_active_runs:
            st.info(f"{len(auto_followup_active_runs)} run(s) auto score + backfill déjà actif(s).")
            for run in auto_followup_active_runs:
                run_id = str(run.get("run_id", ""))
                st.caption(f"Actif : `{run_id}`")
                if st.button(
                    "⏹️ Arrêter ce run auto score + backfill",
                    key=f"stop_score_history_relevance_backfill_auto_run_{run_id}",
                    use_container_width=True,
                ):
                    stop_pipeline_run(run_id)
                    st.rerun()
        elif score_only_active_runs:
            st.info(f"{len(score_only_active_runs)} run(s) de scoring sentiment seul déjà actif(s).")
            for run in score_only_active_runs:
                run_id = str(run.get("run_id", ""))
                st.caption(f"Actif : `{run_id}`")
                if st.button(
                    "⏹️ Arrêter ce scoring seul",
                    key=f"stop_score_sentiment_only_run_{run_id}",
                    use_container_width=True,
                ):
                    stop_pipeline_run(run_id)
                    st.rerun()
        elif rebuild_features_active_runs:
            st.info(f"{len(rebuild_features_active_runs)} reconstruction(s) de features déjà active(s).")
            for run in rebuild_features_active_runs:
                run_id = str(run.get("run_id", ""))
                st.caption(f"Actif : `{run_id}`")
                if st.button(
                    "⏹️ Arrêter ce rebuild features",
                    key=f"stop_rebuild_daily_sentiment_features_only_run_{run_id}",
                    use_container_width=True,
                ):
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
            import_col, score_only_col, rebuild_col, followup_col, auto_col = st.columns(5)
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
            with score_only_col:
                score_only_clicked = st.button(
                    "🧠 Scorer sentiment seulement",
                    key="run_pipeline_score_sentiment_only",
                    use_container_width=True,
                    disabled=score_only_locked or start_value > end_value,
                    help="Réutilise le `mode de scoring` du bloc Event Sentiment sur la fenêtre + l'univers 7.bis, sans réimport.",
                )
                if score_only_clicked:
                    record = start_pipeline_run(
                        "score_sentiment_only",
                        "7.bis Score sentiment only",
                        import_options,
                        db_config=db_config,
                    )
                    _register_new_run(record, all_runs)
                    st.success(f"Scoring sentiment seul démarré en arrière-plan : `{record.run_id}`")
                    st.rerun()
            with rebuild_col:
                rebuild_clicked = st.button(
                    "🧱 Rebuild daily sentiment features only",
                    key="run_pipeline_rebuild_daily_sentiment_features_only",
                    use_container_width=True,
                    disabled=rebuild_features_locked or start_value > end_value,
                )
                if rebuild_clicked:
                    record = start_pipeline_run(
                        "rebuild_daily_sentiment_features_only",
                        "7.bis Rebuild daily sentiment features only",
                        import_options,
                        db_config=db_config,
                    )
                    _register_new_run(record, all_runs)
                    st.success(f"Rebuild des features sentiment démarré en arrière-plan : `{record.run_id}`")
                    st.rerun()
            with followup_col:
                auto_followup_clicked = st.button(
                    "⚙️ Score + history_backfill + relevance_backfill auto",
                    key="run_pipeline_score_history_relevance_backfill_auto",
                    use_container_width=True,
                    disabled=auto_followup_locked or start_value > end_value,
                )
                if auto_followup_clicked:
                    record = start_pipeline_run(
                        "score_history_relevance_backfill_auto",
                        "7.bis Score + history_backfill + relevance_backfill auto",
                        import_options,
                        db_config=db_config,
                    )
                    _register_new_run(record, all_runs)
                    st.success(f"Score + backfill auto démarrés en arrière-plan : `{record.run_id}`")
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
        st.caption("Dernier run — scoring sentiment seul")
        _render_step_result(latest_by_step.get("score_sentiment_only"))
        st.caption("Dernier run — rebuild daily sentiment features only")
        _render_step_result(latest_by_step.get("rebuild_daily_sentiment_features_only"))
        st.caption("Dernier run — score + history_backfill + relevance_backfill auto")
        _render_step_result(latest_by_step.get("score_history_relevance_backfill_auto"))
        st.caption("Dernier run — import + scoring + backfill auto")
        _render_step_result(latest_by_step.get("import_news_pending_loop"))

        st.divider()
        _render_backfill_completeness_panel(start_value, end_value)

