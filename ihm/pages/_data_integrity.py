"""ihm/pages/_data_integrity.py — Phase 6.2 (Backlog L10).

Panneau auxiliaire « 7.bis Traitement par étape » pour piloter manuellement
les sous-étapes de l'étape 7 Sentiment Pipeline.
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

_IMPORT_NEWS_START_DATE_WIDGET_KEY = f"{IMPORT_NEWS_START_DATE_KEY}__widget"
_IMPORT_NEWS_END_DATE_WIDGET_KEY = f"{IMPORT_NEWS_END_DATE_KEY}__widget"


def _coerce_date(value: object, fallback: DateValue) -> DateValue:
    return value if isinstance(value, DateValue) else fallback


def _prime_date_widget_state(widget_key: str, persisted_key: str, fallback: DateValue) -> DateValue:
    persisted_value = _coerce_date(st.session_state.get(persisted_key), fallback)
    widget_value = _coerce_date(st.session_state.get(widget_key), persisted_value)
    if widget_key not in st.session_state or not isinstance(st.session_state.get(widget_key), DateValue):
        st.session_state[widget_key] = widget_value
    return widget_value


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
                "→ Relancez **Calcul relevance_score (Niveau 2/3)** dans le panneau de maintenance pour combler."
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
                "→ Relancez **Scoring FinBERT contextuel (Niveau 4)** dans le panneau de maintenance si nécessaire."
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
    start_widget_value = _prime_date_widget_state(_IMPORT_NEWS_START_DATE_WIDGET_KEY, IMPORT_NEWS_START_DATE_KEY, default_start)
    end_widget_value = _prime_date_widget_state(_IMPORT_NEWS_END_DATE_WIDGET_KEY, IMPORT_NEWS_END_DATE_KEY, default_end)

    with st.container(border=True):
        st.markdown("**7.bis Traitement par étape**")
        st.caption(
            "Ce bloc auxiliaire permet de lancer **pas à pas** les 5 sous-étapes de la nouvelle étape 7, "
            "en réutilisant les paramètres déjà saisis dans l'IHM (provider, fenêtre, symboles, seuils, batch sizes, caps contextuels, etc.). "
            "Il ne matérialise pas une étape cœur supplémentaire du workflow : c'est un outil de maintenance et de pilotage manuel."
        )
        with st.expander("Mini guide d'usage — quand lancer quoi ?", expanded=False):
            st.markdown(
                "1. **Import news** : importe les news brutes sur la fenêtre ciblée et alimente déjà `news_raw` + `news_ticker_map`.\n"
                "2. **Calcul `relevance_score` (Niveau 2/3)** : complète/backfill `news_ticker_map.relevance_score` en pur Python sur les lignes de `news_ticker_map` déjà créées par l'import.\n"
                "3. **Scoring FinBERT standard (sans features)** : remplit `news_sentiment` sans encore reconstruire les agrégats journaliers.\n"
                "4. **Agrégation features journalières** : reconstruit `ticker_daily_sentiment_features` / `sector_daily_sentiment_features`.\n"
                "5. **Scoring FinBERT contextuel (Niveau 4)** : enrichit `news_ticker_sentiment` sur les couples `(article, symbole)` compatibles avec le scope et les seuils configurés."
            )
            st.info(
                "**Ordre recommandé :** ① Import news → ② relevance backfill → ③ scoring standard → ④ agrégation journalière → ⑤ scoring contextuel.\n\n"
                "⚠️ Le scoring contextuel est volontairement placé en dernier dans cet outil manuel pour refléter la nouvelle orchestration métier visible dans l'IHM Pipeline."
            )

        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_value_raw = st.date_input(
                "Date de début",
                value=start_widget_value,
                key=_IMPORT_NEWS_START_DATE_WIDGET_KEY,
                format="YYYY-MM-DD",
            )
            start_value = _coerce_date(start_value_raw, default_start)
        with date_col2:
            end_value_raw = st.date_input(
                "Date de fin",
                value=end_widget_value,
                key=_IMPORT_NEWS_END_DATE_WIDGET_KEY,
                format="YYYY-MM-DD",
            )
            end_value = _coerce_date(end_value_raw, default_end)
        # Persiste les dernières dates validées sur des clés dédiées aux previews
        # / commandes. Les widgets utilisent des shadow keys distinctes afin de
        # permettre des mises à jour successives sans heurter les contraintes de
        # mutation Streamlit sur une clé déjà liée à un widget.
        st.session_state[IMPORT_NEWS_START_DATE_KEY] = start_value
        st.session_state[IMPORT_NEWS_END_DATE_KEY] = end_value

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
                value=bool(
                    st.session_state.get(
                        "pipeline_import_news_resume_from_checkpoint",
                        getattr(options, "news_import_resume_from_checkpoint", True),
                    )
                ),
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
        step_specs = [
            {
                "key": "import_news",
                "label": "📰 Import news",
                "run_label": "7.bis Traitement par étape — 1. Import news",
                "caption": "Sous-étape 1 — Import news",
                "preview": format_command_for_display(build_pipeline_command("import_news", import_options)),
                "success": "Import news démarré en arrière-plan",
                "stop": "⏹️ Arrêter l'import news",
            },
            {
                "key": "sentiment_relevance_backfill",
                "label": "🧮 Calcul relevance_score (Niveau 2/3)",
                "run_label": "7.bis Traitement par étape — 2. Calcul relevance_score (Niveau 2/3)",
                "caption": "Sous-étape 2 — Calcul `relevance_score` (Niveau 2/3)",
                "preview": format_command_for_display(build_pipeline_command("sentiment_relevance_backfill", import_options)),
                "success": "Calcul relevance_score démarré en arrière-plan",
                "stop": "⏹️ Arrêter le relevance backfill",
            },
            {
                "key": "sentiment_standard_scoring",
                "label": "🧠 Scoring FinBERT standard (sans features)",
                "run_label": "7.bis Traitement par étape — 3. Scoring FinBERT standard (sans features)",
                "caption": "Sous-étape 3 — Scoring FinBERT standard (sans features)",
                "preview": format_command_for_display(build_pipeline_command("sentiment_standard_scoring", import_options)),
                "success": "Scoring FinBERT standard démarré en arrière-plan",
                "stop": "⏹️ Arrêter le scoring standard",
            },
            {
                "key": "rebuild_daily_sentiment_features_only",
                "label": "🧱 Agrégation features journalières",
                "run_label": "7.bis Traitement par étape — 4. Agrégation features journalières",
                "caption": "Sous-étape 4 — Agrégation features journalières (ticker/secteur)",
                "preview": format_command_for_display(build_pipeline_command("rebuild_daily_sentiment_features_only", import_options)),
                "success": "Agrégation des features journalières démarrée en arrière-plan",
                "stop": "⏹️ Arrêter l'agrégation journalière",
            },
            {
                "key": "sentiment_contextual_scoring",
                "label": "🎯 Scoring FinBERT contextuel (Niveau 4)",
                "run_label": "7.bis Traitement par étape — 5. Scoring FinBERT contextuel (Niveau 4)",
                "caption": "Sous-étape 5 — Scoring FinBERT contextuel (Niveau 4 — `news_ticker_sentiment`)",
                "preview": format_command_for_display(build_pipeline_command("sentiment_contextual_scoring", import_options)),
                "success": "Scoring FinBERT contextuel démarré en arrière-plan",
                "stop": "⏹️ Arrêter le scoring contextuel",
            },
        ]
        for spec in step_specs:
            st.caption(str(spec["caption"]))
            st.code(str(spec["preview"]), language="powershell")

        locked_by_sentiment = bool(active_by_step.get("sentiment_pipeline"))
        related_active_keys = [
            *(str(spec["key"]) for spec in step_specs),
            "score_sentiment_only",
            "relevance_backfill",
            "score_history_relevance_backfill_auto",
            "import_news_pending_loop",
        ]
        active_related_runs = {
            key: active_by_step.get(key, [])
            for key in related_active_keys
            if active_by_step.get(key)
        }

        if workflow_active:
            st.warning("Un workflow complet est en cours : le traitement manuel par sous-étape est temporairement désactivé.")
        elif locked_by_sentiment:
            st.warning("Le Sentiment Pipeline est déjà actif : attendez sa fin avant de lancer un traitement pas à pas.")
        elif active_related_runs:
            st.warning("Un outil manuel/backfill sentiment est déjà actif : terminez-le ou arrêtez-le avant de relancer une autre sous-étape.")

        if start_value > end_value:
            st.error("La date de début doit être antérieure ou égale à la date de fin.")
        elif active_related_runs:
            for spec in step_specs:
                runs = active_by_step.get(str(spec["key"]), [])
                if not runs:
                    continue
                st.info(f"{len(runs)} run(s) actif(s) pour {spec['caption']}.")
                for run in runs:
                    run_id = str(run.get("run_id", ""))
                    st.caption(f"Actif : `{run_id}`")
                    if st.button(str(spec["stop"]), key=f"stop_{spec['key']}_{run_id}", use_container_width=True):
                        stop_pipeline_run(run_id)
                        st.rerun()
            for legacy_key, legacy_label in (
                ("score_sentiment_only", "Scoring sentiment seul (legacy maintenance)"),
                ("relevance_backfill", "Contextual/relevance backfill (legacy maintenance)"),
                ("score_history_relevance_backfill_auto", "Wrapper auto score + backfills (legacy maintenance)"),
                ("import_news_pending_loop", "Wrapper auto import + score + backfills (legacy maintenance)"),
            ):
                runs = active_by_step.get(legacy_key, [])
                if not runs:
                    continue
                st.info(f"{len(runs)} run(s) actif(s) pour {legacy_label}.")
                for run in runs:
                    run_id = str(run.get("run_id", ""))
                    st.caption(f"Actif : `{run_id}`")
                    if st.button(
                        f"⏹️ Arrêter {legacy_label}",
                        key=f"stop_{legacy_key}_{run_id}",
                        use_container_width=True,
                    ):
                        stop_pipeline_run(run_id)
                        st.rerun()
        else:
            button_columns = st.columns(5)
            for column, spec in zip(button_columns, step_specs):
                with column:
                    clicked = st.button(
                        str(spec["label"]),
                        key=f"run_{spec['key']}",
                        use_container_width=True,
                    )
                    if clicked:
                        record = start_pipeline_run(
                            str(spec["key"]),
                            str(spec["run_label"]),
                            import_options,
                            db_config=db_config,
                        )
                        _register_new_run(record, all_runs)
                        st.success(f"{spec['success']} : `{record.run_id}`")
                        st.rerun()

        for spec in step_specs:
            st.caption(f"Dernier run — {spec['caption']}")
            _render_step_result(latest_by_step.get(str(spec["key"])))

        st.divider()
        _render_backfill_completeness_panel(start_value, end_value)

