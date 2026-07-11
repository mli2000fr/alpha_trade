"""ihm/pages/_data_integrity.py — Phase 6.2 (Backlog L10).

Panneau auxiliaire « News-Sentiement Traitement par étape » pour piloter
manuellement les sous-étapes de l'étape 7 Sentiment Pipeline.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
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
    _rerun_app,
    _sanitize_compare_ids,
    start_pipeline_run,
)
from ihm.services.pipeline_runner import build_pipeline_command, format_command_for_display
from ihm.services.process_registry import PipelineRunRecord, stop_pipeline_run
from ihm.services.queries import get_backfill_completeness_diagnostic

__all__ = ["_render_import_news_panel"]


NEWS_IMPORT_SYMBOL_SOURCE_OPTIONS = (
    "tradable-universe",
    "stock_scores",
    "stock_scores_history",
    "stock_scores_all",
    "stock_bars_daily",
)

IMPORT_NEWS_START_DATE_WIDGET_KEY = f"{IMPORT_NEWS_START_DATE_KEY}_widget"
IMPORT_NEWS_END_DATE_WIDGET_KEY = f"{IMPORT_NEWS_END_DATE_KEY}_widget"


def _coerce_date(value: object, fallback: DateValue) -> DateValue:
    return value if isinstance(value, DateValue) else fallback


def _coerce_date_text(value: object, fallback: DateValue) -> str:
    if isinstance(value, DateValue):
        return value.isoformat()
    text = str(value or "").strip()
    return text or fallback.isoformat()


def _parse_iso_date_text(value: object) -> DateValue | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _date_last_synced_key(widget_key: str) -> str:
    return f"{widget_key}_last_synced"


def _ensure_date_input_state(canonical_key: str, widget_key: str, fallback: DateValue) -> str:
    """Initialise l'état date sans écraser une saisie utilisateur en cours.

    Le bloc 7.bis est rendu hors du `st.fragment(run_every="2s")` de la page
    Pipeline pour éviter qu'un auto-refresh n'écrase une saisie en cours.
    On garde néanmoins une clé widget séparée de la clé métier persistée afin
    que, si le widget est recréé après un rerun classique, il reparte de la
    dernière date validée et non du défaut `today-7/today`.
    """
    had_persisted_canonical = canonical_key in st.session_state and bool(str(st.session_state.get(canonical_key) or "").strip())
    canonical_value = _coerce_date_text(st.session_state.get(canonical_key), fallback)
    if canonical_key not in st.session_state or not str(st.session_state.get(canonical_key) or "").strip():
        st.session_state[canonical_key] = canonical_value

    last_synced_key = _date_last_synced_key(widget_key)
    if widget_key not in st.session_state:
        if had_persisted_canonical:
            st.session_state[widget_key] = canonical_value
            st.session_state[last_synced_key] = canonical_value
    else:
        previous_synced = str(st.session_state.get(last_synced_key) or "").strip()
        current_widget_value = str(st.session_state.get(widget_key) or "").strip()
        if canonical_value != previous_synced and current_widget_value == previous_synced:
            st.session_state[widget_key] = canonical_value
            st.session_state[last_synced_key] = canonical_value
    return str(st.session_state.get(widget_key) or canonical_value)


def _sync_date_input(canonical_key: str, widget_key: str, raw_value: str) -> None:
    st.session_state[canonical_key] = raw_value
    st.session_state[_date_last_synced_key(widget_key)] = raw_value


def _format_date_input_status(raw_value: str, parsed_value: DateValue | None) -> str:
    if parsed_value is not None:
        return parsed_value.isoformat()
    return f"invalide ({raw_value})" if raw_value else "invalide"


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


@st.cache_data(ttl=120, show_spinner=False)
def _resolve_symbols_for_diagnostic(
    symbols_csv: str | None,
    symbol_source: str,
) -> list[str]:
    """Résout la liste complète des symboles pour filtrer les compteurs."""
    repository = EventSentimentRepository()
    symbols, _ = resolve_symbols_from_inputs(
        symbols_csv=symbols_csv or None,
        symbol_source=symbol_source,
        repository=repository,
    )
    return symbols


def _render_backfill_completeness_panel(
    start_value: DateValue,
    end_value: DateValue,
    *,
    use_expander: bool = True,
    import_options: PipelineLaunchOptions | None = None,
    db_config: dict[str, str | None] | None = None,
    all_runs: list[dict[str, object]] | None = None,
) -> None:
    """Panneau de compteurs de complétude des backfills history + relevance."""

    panel_title = "📊 Compteurs de complétude — History & Relevance backfill"
    panel_context = st.expander(panel_title, expanded=False) if use_expander else st.container(border=True)
    with panel_context:
        if not use_expander:
            st.markdown(f"**{panel_title}**")

        # Résoudre les symboles de l'univers sélectionné pour filtrer les compteurs
        diag_symbols: list[str] | None = None
        if import_options is not None:
            diag_symbols = _resolve_symbols_for_diagnostic(
                symbols_csv=import_options.news_import_symbols or None,
                symbol_source=import_options.news_import_symbol_source or "",
            )
            if not diag_symbols:
                diag_symbols = None  # fallback : pas de filtre si résolution vide

        st.caption(
            "Le TTL de cache est de 30 s ; cliquez sur 🔄 pour forcer l'actualisation."
        )

        col_refresh, _ = st.columns([1, 5])
        with col_refresh:
            if st.button("🔄 Actualiser les compteurs", key="refresh_backfill_completeness"):
                get_backfill_completeness_diagnostic.clear()  # type: ignore[attr-defined]
                if import_options is not None:
                    _resolve_symbols_for_diagnostic.clear()  # type: ignore[attr-defined]

        # Seuil de pertinence contextuelle : aligné sur le job de scoring (Niveau 4)
        diag_contextual_min_relevance: float | None = None
        if import_options is not None:
            # Priorité au seuil configuré dans l'IHM (sentiment_contextual_min_relevance),
            # sinon utiliser celui du backfill relevance (backfill_relevance_contextual_min_relevance).
            diag_contextual_min_relevance = (
                import_options.sentiment_contextual_min_relevance
                or import_options.backfill_relevance_contextual_min_relevance
                or None
            )
            if diag_contextual_min_relevance is not None and diag_contextual_min_relevance <= 0.0:
                diag_contextual_min_relevance = None

        diag = get_backfill_completeness_diagnostic(
            start_date=start_value,
            end_date=end_value,
            symbols=diag_symbols,
            contextual_min_relevance=diag_contextual_min_relevance,
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
            if import_options is not None and db_config is not None and all_runs is not None:
                quick_options = replace(import_options, news_import_start_date=None, news_import_end_date=None)  # type: ignore[arg-type]
                quick_command = build_pipeline_command("sentiment_relevance_backfill", quick_options)
                st.caption("Commande qui sera exécutée (tout l'historique, sans filtre de date) :")
                st.code(format_command_for_display(quick_command), language="powershell")
                if st.button(
                    "🚀 Lancer le backfill relevance maintenant",
                    key="quick_launch_relevance_backfill",
                    use_container_width=True,
                    help="Lance la commande affichée ci-dessus pour combler les `relevance_score` manquants.",
                ):
                    record = start_pipeline_run(
                        "sentiment_relevance_backfill",
                        "News-Sentiement — Backfill relevance (Niveau 2/3) [lancé depuis les compteurs]",
                        quick_options,
                        db_config=db_config,
                    )
                    _register_new_run(record, all_runs)
                    st.success(f"Backfill relevance démarré : `{record.run_id}`")
                    _rerun_app()
            if r_total > 0:
                progress_val = min(1.0, max(0.0, r_scored / r_total))
                st.progress(progress_val, text=f"{r_scored}/{r_total} paires scorées")

        st.divider()

        st.markdown("##### Contextual backfill — Niveau 4 FinBERT (`news_ticker_sentiment`)")
        if diag_contextual_min_relevance is not None and diag_contextual_min_relevance > 0.0:
            st.caption(
                f"Compte les paires article↔ticker avec `relevance_score ≥ {diag_contextual_min_relevance:g}` "
                "absentes de `news_ticker_sentiment`. "
                "**Zéro pending = backfill contextuel complet** sur cette fenêtre."
            )
        else:
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
            if import_options is not None and db_config is not None and all_runs is not None:
                quick_options = replace(import_options, news_import_start_date=None, news_import_end_date=None)  # type: ignore[arg-type]
                quick_command = build_pipeline_command("sentiment_contextual_scoring", quick_options)
                st.caption("Commande qui sera exécutée (tout l'historique, sans filtre de date) :")
                st.code(format_command_for_display(quick_command), language="powershell")
                if st.button(
                    "🚀 Lancer le scoring contextuel maintenant",
                    key="quick_launch_contextual_scoring",
                    use_container_width=True,
                    help="Lance la commande affichée ci-dessus pour combler les scores contextuels FinBERT manquants. ⚠️ Opération lourde (FinBERT).",
                ):
                    record = start_pipeline_run(
                        "sentiment_contextual_scoring",
                        "News-Sentiement — Scoring contextuel (Niveau 4) [lancé depuis les compteurs]",
                        quick_options,
                        db_config=db_config,
                    )
                    _register_new_run(record, all_runs)
                    st.success(f"Scoring contextuel démarré : `{record.run_id}`")
                    _rerun_app()
            if c_total > 0:
                progress_val = min(1.0, max(0.0, c_scored / c_total))
                st.progress(progress_val, text=f"{c_scored}/{c_total} paires scorées contextuellement")


def _latest_step_run_for_panel(
    latest_by_step: dict[str, dict[str, object]],
    step_specs: list[dict[str, object]],
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    """Retourne le run le plus récent parmi les sous-étapes affichées du panneau."""

    candidates: list[tuple[tuple[str, str, str, int], dict[str, object], dict[str, object]]] = []
    for index, spec in enumerate(step_specs):
        step_key = str(spec.get("key") or "")
        run = latest_by_step.get(step_key)
        if not isinstance(run, dict) or not run:
            continue
        sort_key = (
            str(run.get("finished_at") or ""),
            str(run.get("actual_started_at") or run.get("started_at") or ""),
            str(run.get("executed_at") or ""),
            index,
        )
        candidates.append((sort_key, spec, run))

    if not candidates:
        return None, None

    _sort_key, winning_spec, winning_run = max(candidates, key=lambda item: item[0])
    return winning_spec, winning_run


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
    default_start = today - timedelta(days=7)
    default_end = today
    _ensure_date_input_state(IMPORT_NEWS_START_DATE_KEY, IMPORT_NEWS_START_DATE_WIDGET_KEY, default_start)
    _ensure_date_input_state(IMPORT_NEWS_END_DATE_KEY, IMPORT_NEWS_END_DATE_WIDGET_KEY, default_end)

    with st.expander("**News-Sentiement Traitement par étape**", expanded=False):
        st.caption(
            "Ce bloc auxiliaire permet de lancer **pas à pas** les 5 sous-étapes de la nouvelle étape 7, "
            "en réutilisant les paramètres déjà saisis dans l'IHM (provider, fenêtre, symboles, seuils, batch sizes, caps contextuels, etc.). "
            "Il ne matérialise pas une étape cœur supplémentaire du workflow : c'est un outil de maintenance et de pilotage manuel."
        )
        with st.container(border=True):
            st.markdown("**Mini guide d'usage — quand lancer quoi ?**")
            st.markdown(
                "1. **Import news** : importe les news brutes sur la fenêtre ciblée et alimente déjà `news_raw` + `news_ticker_map`.\n"
                "2. **Calcul `relevance_score` (Niveau 2/3)** : complète/backfill `news_ticker_map.relevance_score` en pur Python sur les lignes de `news_ticker_map` déjà créées par l'import.\n"
                "3. **Scoring FinBERT standard (sans features)** : remplit `news_sentiment` sans encore reconstruire les agrégats journaliers.\n"
                "4. **Scoring FinBERT contextuel (Niveau 4)** : enrichit `news_ticker_sentiment` sur les couples `(article, symbole)` compatibles avec le scope et les seuils configurés.\n"
                "5. **Agrégation features journalières** : reconstruit `ticker_daily_sentiment_features` / `sector_daily_sentiment_features` en tenant compte du fallback `COALESCE(news_ticker_sentiment, news_sentiment)`."
            )
            st.info(
                "**Ordre recommandé :** ① Import news → ② relevance backfill → ③ scoring standard → ④ scoring contextuel → ⑤ agrégation journalière.\n\n"
                "ℹ️ L'agrégation journalière doit rester en dernier pour reconstruire les features ticker/secteur à partir des scores contextuels déjà persistés quand ils existent."
            )

        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_widget_return = st.text_input(
                "Date de début",
                key=IMPORT_NEWS_START_DATE_WIDGET_KEY,
                help="Format attendu : YYYY-MM-DD (ex: 2020-01-01)",
            )
        with date_col2:
            end_widget_return = st.text_input(
                "Date de fin",
                key=IMPORT_NEWS_END_DATE_WIDGET_KEY,
                help="Format attendu : YYYY-MM-DD (ex: 2020-01-31)",
            )
        st.caption(
            "ℹ️ Les changements de dates sont appliqués dès que vous quittez le champ "
            "(Tab, clic ailleurs, lancement d'un job, etc.)."
        )
        start_raw = str(st.session_state.get(IMPORT_NEWS_START_DATE_WIDGET_KEY, start_widget_return) or "").strip()
        end_raw = str(st.session_state.get(IMPORT_NEWS_END_DATE_WIDGET_KEY, end_widget_return) or "").strip()
        _sync_date_input(IMPORT_NEWS_START_DATE_KEY, IMPORT_NEWS_START_DATE_WIDGET_KEY, start_raw)
        _sync_date_input(IMPORT_NEWS_END_DATE_KEY, IMPORT_NEWS_END_DATE_WIDGET_KEY, end_raw)
        start_value = _parse_iso_date_text(start_raw)
        end_value = _parse_iso_date_text(end_raw)
        date_inputs_valid = True
        if start_value is None:
            st.error("Date de début invalide. Utilisez le format ISO `YYYY-MM-DD`.")
            date_inputs_valid = False
        if end_value is None:
            st.error("Date de fin invalide. Utilisez le format ISO `YYYY-MM-DD`.")
            date_inputs_valid = False

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
                        "`tradable-universe` cible l'univers PIT canonique ; `stock_scores_all` cible l'union dédupliquée des symboles présents dans `stock_scores` ou `stock_scores_history` ; "
                        "`stock_scores` limite l'import aux symboles du snapshot courant `stock_scores` ; "
                        "`stock_scores_history` cible les symboles déjà présents dans `stock_scores_history` ; "
                        "`stock_bars_daily` réactive l'ancien comportement large."
                    ),
                )
            )
            st.caption(
                "Aide rapide : `tradable-universe` = univers PIT canonique ; `stock_scores_all` = union `stock_scores` + `stock_scores_history` ; "
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

        if not date_inputs_valid:
            st.caption(
                "Fenêtre appliquée : "
                f"{_format_date_input_status(start_raw, start_value)} → "
                f"{_format_date_input_status(end_raw, end_value)}"
            )
            return

        import_options = replace(
            options,
            news_import_start_date=cast(DateValue, start_value).isoformat(),
            news_import_end_date=cast(DateValue, end_value).isoformat(),
            news_import_symbols=news_import_symbols or None,
            news_import_symbol_source=cast(
                Literal[
                    "stock_scores",
                    "stock_scores_history",
                    "stock_scores_all",
                    "stock_bars_daily",
                    "tradable-universe",
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
                "run_label": "News-Sentiement Traitement par étape — 1. Import news",
                "caption": "Sous-étape 1 — Import news",
                "preview": format_command_for_display(build_pipeline_command("import_news", import_options)),
                "success": "Import news démarré en arrière-plan",
                "stop": "⏹️ Arrêter l'import news",
            },
            {
                "key": "sentiment_relevance_backfill",
                "label": "🧮 Calcul relevance_score (Niveau 2/3)",
                "run_label": "News-Sentiement Traitement par étape — 2. Calcul relevance_score (Niveau 2/3)",
                "caption": "Sous-étape 2 — Calcul `relevance_score` (Niveau 2/3)",
                "preview": format_command_for_display(build_pipeline_command("sentiment_relevance_backfill", import_options)),
                "success": "Calcul relevance_score démarré en arrière-plan",
                "stop": "⏹️ Arrêter le relevance backfill",
            },
            {
                "key": "sentiment_standard_scoring",
                "label": "🧠 Scoring FinBERT standard (sans features)",
                "run_label": "News-Sentiement Traitement par étape — 3. Scoring FinBERT standard (sans features)",
                "caption": "Sous-étape 3 — Scoring FinBERT standard (sans features)",
                "preview": format_command_for_display(build_pipeline_command("sentiment_standard_scoring", import_options)),
                "success": "Scoring FinBERT standard démarré en arrière-plan",
                "stop": "⏹️ Arrêter le scoring standard",
            },
            {
                "key": "sentiment_contextual_scoring",
                "label": "🎯 Scoring FinBERT contextuel (Niveau 4)",
                "run_label": "News-Sentiement Traitement par étape — 4. Scoring FinBERT contextuel (Niveau 4)",
                "caption": "Sous-étape 4 — Scoring FinBERT contextuel (Niveau 4 — `news_ticker_sentiment`)",
                "preview": format_command_for_display(build_pipeline_command("sentiment_contextual_scoring", import_options)),
                "success": "Scoring FinBERT contextuel démarré en arrière-plan",
                "stop": "⏹️ Arrêter le scoring contextuel",
            },
            {
                "key": "rebuild_daily_sentiment_features_only",
                "label": "🧱 Agrégation features journalières",
                "run_label": "News-Sentiement Traitement par étape — 5. Agrégation features journalières",
                "caption": "Sous-étape 5 — Agrégation features journalières (ticker/secteur)",
                "preview": format_command_for_display(build_pipeline_command("rebuild_daily_sentiment_features_only", import_options)),
                "success": "Agrégation des features journalières démarrée en arrière-plan",
                "stop": "⏹️ Arrêter l'agrégation journalière",
            },
        ]
        st.caption(f"Fenêtre appliquée : {cast(DateValue, start_value).isoformat()} → {cast(DateValue, end_value).isoformat()}")
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

        if cast(DateValue, start_value) > cast(DateValue, end_value):
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
                        _rerun_app()
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
                        _rerun_app()
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
                        _rerun_app()

        latest_spec, latest_run = _latest_step_run_for_panel(latest_by_step, step_specs)
        if latest_spec is not None:
            st.caption(f"Dernier run — {latest_spec['caption']}")
        else:
            st.caption("Dernier run")
        _render_step_result(latest_run)

        st.divider()
        _render_backfill_completeness_panel(
            cast(DateValue, start_value),
            cast(DateValue, end_value),
            use_expander=False,
            import_options=import_options,
            db_config=db_config,
            all_runs=all_runs,
        )

