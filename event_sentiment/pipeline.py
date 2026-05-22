import logging
from math import ceil
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Callable, Sequence, cast

from core.run_summary import attach_live_progress
from event_sentiment.aggregation import build_sector_daily_features, build_ticker_daily_features
from event_sentiment.ingestion import NewsIngestionService
from event_sentiment.macro_rules import MacroRuleEngine
from event_sentiment.models import NormalizedNewsArticle
from event_sentiment.scoring import ContextualFinBERTScorer, FinBERTSentimentService

LOGGER = logging.getLogger(__name__)


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        return int(value)
    return 0


class EventSentimentPipeline:
    def __init__(self, repository, config, progress_callback: Callable[[dict[str, object]], None] | None = None) -> None:
        self.repository = repository
        self.config = config
        self.progress_callback = progress_callback
        self.ingestion = NewsIngestionService(repository=repository, config=config)
        self.finbert = FinBERTSentimentService(
            model_name=config.finbert_model_name,
            model_version=config.finbert_model_version,
            batch_size=config.finbert_batch_size,
            max_length=config.finbert_max_length,
            model_revision=getattr(config, "finbert_model_revision", None),
        )
        self.macro_engine = MacroRuleEngine(rule_version=config.macro_rule_version)

        # Niveau 4 — scorer contextualisé partagé avec FinBERT (réutilise la
        # même config modèle / batch). Instancié paresseusement uniquement
        # si ``enable_contextual_scoring`` est True (économise mémoire en
        # mode legacy).
        self._contextual_scorer: ContextualFinBERTScorer | None = None

    def _touch_checkpoint_stage_if_supported(self, symbols: list[str], *, stage: str) -> int:
        if not symbols:
            return 0
        toucher = getattr(self.repository, "touch_checkpoint_stage", None)
        if not callable(toucher):
            LOGGER.debug("Repository sans touch_checkpoint_stage ; checkpoint stage ignoré | stage=%s", stage)
            return 0
        return int(toucher(self.config.source_name, symbols, stage=stage) or 0)

    @staticmethod
    def _coerce_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _resolve_symbols(self, symbols: list[str] | None) -> list[str]:
        def _normalize(symbol_values: list[str]) -> list[str]:
            return sorted({symbol.strip().upper() for symbol in symbol_values if symbol and symbol.strip()})

        if symbols is not None:
            return _normalize(symbols)

        candidates = self.repository.load_candidate_symbols()
        normalized_candidates = _normalize(candidates)
        if not normalized_candidates:
            LOGGER.warning(
                "Aucun symbole candidat dans stock_scores (is_candidate=1) ; ingestion news ignorée pour ce run."
            )
            return []
        LOGGER.info("Symboles candidats chargés depuis stock_scores | count=%s", len(normalized_candidates))
        return normalized_candidates

    def _resolve_time_window(
        self,
        start_utc: datetime | None,
        end_utc: datetime | None,
    ) -> tuple[datetime, datetime]:
        resolved_end = self._coerce_utc(end_utc) or datetime.now(UTC)
        resolved_start = self._coerce_utc(start_utc)
        if resolved_start is None:
            resolved_start = resolved_end - timedelta(days=self.config.initial_backfill_days)
            LOGGER.info(
                "Fenêtre news fallback initial | backfill_days=%s start=%s end=%s",
                self.config.initial_backfill_days,
                resolved_start,
                resolved_end,
            )

        if resolved_start >= resolved_end:
            adjusted_start = resolved_end - timedelta(minutes=max(self.config.checkpoint_overlap_minutes, 60))
            LOGGER.warning(
                "Fenêtre news invalide détectée, ajustement automatique | start=%s end=%s adjusted_start=%s",
                resolved_start,
                resolved_end,
                adjusted_start,
            )
            resolved_start = adjusted_start

        return resolved_start, resolved_end

    def _build_pending_scope(
        self,
        *,
        start_utc: datetime | None,
        end_utc: datetime | None,
        symbols: list[str] | None,
        skip_ingestion: bool,
    ) -> dict[str, object]:
        scope: dict[str, object] = {
            "ingestion_source": getattr(self.config, "provider_name", getattr(self.config, "news_provider", None)),
        }
        if start_utc is not None:
            scope["start_date"] = start_utc.date()
        if end_utc is not None:
            scope["end_date"] = end_utc.date()
        if symbols is not None:
            scope["symbols"] = list(symbols)
        return scope

    def _resolve_symbol_windows(
        self,
        start_utc: datetime | None,
        end_utc: datetime | None,
        symbols: list[str],
    ) -> tuple[dict[str, datetime], dict[str, bool], datetime]:
        explicit_start = self._coerce_utc(start_utc)
        resolved_end = self._coerce_utc(end_utc) or datetime.now(UTC)
        if explicit_start is not None:
            return {symbol: explicit_start for symbol in symbols}, {symbol: False for symbol in symbols}, resolved_end

        checkpoints = self.repository.get_checkpoints(self.config.source_name, symbols)
        windows: dict[str, datetime] = {}
        resume_by_symbol: dict[str, bool] = {}
        for symbol in symbols:
            checkpoint = checkpoints.get(symbol)
            watermark = self._coerce_utc(
                checkpoint.get("watermark_published_at_utc") if checkpoint else None
            )
            updated_at = self._coerce_utc(
                checkpoint.get("updated_at") if checkpoint else None
            )
            checkpoint_anchor = watermark or updated_at
            reactivation_threshold = timedelta(days=self.config.candidate_reactivation_backfill_days)

            if checkpoint_anchor is not None and resolved_end - checkpoint_anchor > reactivation_threshold:
                resolved_start = checkpoint_anchor
                resume_by_symbol[symbol] = False
                LOGGER.info(
                    "Backfill réactivation forcé | source=%s symbol=%s last_checkpoint=%s threshold_days=%s start=%s end=%s",
                    self.config.source_name,
                    symbol,
                    checkpoint_anchor,
                    self.config.candidate_reactivation_backfill_days,
                    resolved_start,
                    resolved_end,
                )
            elif watermark is not None:
                resolved_start = watermark - timedelta(minutes=self.config.checkpoint_overlap_minutes)
                resume_by_symbol[symbol] = True
                LOGGER.info(
                    "Fenêtre news dérivée du checkpoint symbole | source=%s symbol=%s watermark=%s overlap_minutes=%s start=%s end=%s",
                    self.config.source_name,
                    symbol,
                    watermark,
                    self.config.checkpoint_overlap_minutes,
                    resolved_start,
                    resolved_end,
                )
            else:
                resolved_start = resolved_end - timedelta(days=self.config.initial_backfill_days)
                resume_by_symbol[symbol] = False
                LOGGER.info(
                    "Fenêtre news fallback initial symbole | symbol=%s backfill_days=%s start=%s end=%s",
                    symbol,
                    self.config.initial_backfill_days,
                    resolved_start,
                    resolved_end,
                )

            if resolved_start >= resolved_end:
                adjusted_start = resolved_end - timedelta(minutes=max(self.config.checkpoint_overlap_minutes, 60))
                LOGGER.warning(
                    "Fenêtre news invalide détectée pour symbole, ajustement automatique | symbol=%s start=%s end=%s adjusted_start=%s",
                    symbol,
                    resolved_start,
                    resolved_end,
                    adjusted_start,
                )
                resolved_start = adjusted_start
            windows[symbol] = resolved_start
        return windows, resume_by_symbol, resolved_end

    @staticmethod
    def _rows_to_articles(pending_rows: list[dict[str, object]]) -> list[NormalizedNewsArticle]:
        return [
            NormalizedNewsArticle(
                article_id=str(row["article_id"]),
                headline=str(row["headline"]),
                summary=cast(str | None, row.get("summary")),
                content=cast(str | None, row.get("content")),
                source=str(row["source"]),
                author=cast(str | None, row.get("author")),
                url=cast(str | None, row.get("url")),
                published_at_utc=cast(datetime, row["published_at_utc"]),
                event_timestamp_utc=cast(datetime, row["event_timestamp_utc"]),
                event_timestamp_ny=cast(datetime, row["event_timestamp_ny"]),
                effective_trade_date=cast(date, row["effective_trade_date"]),
                market_session_tag=str(row["market_session_tag"]),
                tickers=[],
                raw_payload={},
                is_major_event=_coerce_int(row.get("is_major_event")),
            )
            for row in pending_rows
        ]

    def _capture_finbert_runtime_stats(self, stats: dict[str, object]) -> None:
        stats["finbert_model_fingerprint"] = getattr(self.finbert, "model_fingerprint", None)
        stats["finbert_effective_batch_size"] = int(getattr(self.finbert, "batch_size", 0) or 0)
        stats["finbert_runtime_device"] = getattr(self.finbert, "device", None)
        stats["finbert_gpu_oom_batch_fallbacks"] = list(
            getattr(self.finbert, "gpu_oom_batch_fallbacks", []) or []
        )

    def _resolve_scoring_mode(self) -> str:
        configured = str(getattr(self.config, "scoring_mode", "") or "").strip().lower()
        if getattr(self.config, "enable_contextual_scoring", False):
            if configured == "contextual_only":
                return "contextual_only"
            return "standard_and_contextual"
        if configured in {"standard_only", "contextual_only", "standard_and_contextual"}:
            return configured
        return "standard_only"

    def _score_pending_batches(
        self,
        pending_scope: dict[str, object],
        stats: dict[str, object],
        *,
        resolved_symbols: list[str],
        skip_features: bool = False,
    ) -> tuple[int, list[date], list[date]]:
        max_batches = int(getattr(self.config, "sentiment_pending_max_batches_per_run", 1))
        unlimited_batches = max_batches <= 0
        feature_flush_every_n_batches = int(getattr(self.config, "feature_flush_every_n_pending_batches", 0) or 0)
        impacted_trade_dates: set[date] = set()
        pending_feature_flush_dates: set[date] = set()
        processed_articles_count = 0
        batches_processed = 0
        total_sentiment_inferred = 0
        total_macro_rows = 0
        feature_flushes_completed = 0

        while unlimited_batches or batches_processed < max_batches:
            pending_rows = self.repository.load_pending_articles(
                limit=self.config.sentiment_pending_limit,
                start_date=pending_scope.get("start_date"),
                end_date=pending_scope.get("end_date"),
                ingestion_source=pending_scope.get("ingestion_source"),
                symbols=pending_scope.get("symbols"),
            )
            if not pending_rows:
                break

            articles = self._rows_to_articles(pending_rows)
            sentiment_records = self.finbert.score_articles(articles)
            sentiment_upserts = self.repository.upsert_news_sentiment([asdict(record) for record in sentiment_records])
            if articles and sentiment_upserts <= 0:
                raise RuntimeError(
                    "Aucun score FinBERT persisté sur un batch pending non vide ; arrêt pour éviter une boucle stagnante."
                )

            sentiment_map = {record.article_id: record for record in sentiment_records}
            batch_impacted_trade_dates = {
                article.effective_trade_date
                for article in articles
                if article.article_id in sentiment_map
            }
            macro_records = []
            for article in articles:
                sentiment = sentiment_map.get(article.article_id)
                if sentiment is None:
                    continue
                macro_records.extend(self.macro_engine.classify(article, sentiment))

            total_sentiment_inferred += int(sentiment_upserts)
            total_macro_rows += int(
                self.repository.upsert_macro_event_audit([asdict(record) for record in macro_records])
            )
            impacted_trade_dates.update(batch_impacted_trade_dates)
            pending_feature_flush_dates.update(batch_impacted_trade_dates)
            processed_articles_count += len(articles)
            batches_processed += 1

            stats["pending_articles_loaded"] = processed_articles_count
            stats["pending_batches_processed"] = batches_processed
            stats["sentiment_inferred"] = total_sentiment_inferred
            stats["macro_rows"] = total_macro_rows
            self._capture_finbert_runtime_stats(stats)
            self._emit_progress(
                stats,
                current=max(processed_articles_count, 1),
                total=max(processed_articles_count, 1),
                label="📰 Progression sentiment pipeline — scoring FinBERT",
                phase="finbert_scoring",
            )

            if (
                not skip_features
                and feature_flush_every_n_batches > 0
                and pending_feature_flush_dates
                and batches_processed % feature_flush_every_n_batches == 0
            ):
                feature_flushes_completed += 1
                self._flush_feature_aggregation(
                    impacted_trade_dates=sorted(pending_feature_flush_dates),
                    resolved_symbols=resolved_symbols,
                    stats=stats,
                    is_final=False,
                    flush_index=feature_flushes_completed,
                )
                pending_feature_flush_dates.clear()

            if len(pending_rows) < int(self.config.sentiment_pending_limit):
                break

        stats.setdefault("pending_articles_loaded", 0)
        stats.setdefault("pending_batches_processed", 0)
        stats.setdefault("sentiment_inferred", 0)
        stats.setdefault("macro_rows", 0)
        stats["feature_flushes_completed"] = int(feature_flushes_completed)
        self._capture_finbert_runtime_stats(stats)
        return processed_articles_count, sorted(impacted_trade_dates), sorted(pending_feature_flush_dates)

    @staticmethod
    def _chunk_trade_dates(trade_dates: Sequence[date], batch_days: int) -> list[list[date]]:
        if batch_days <= 0:
            return [list(trade_dates)] if trade_dates else []
        return [list(trade_dates[index:index + batch_days]) for index in range(0, len(trade_dates), batch_days)]

    def _flush_feature_aggregation(
        self,
        *,
        impacted_trade_dates: list[date],
        resolved_symbols: list[str],
        stats: dict[str, object],
        is_final: bool,
        flush_index: int | None = None,
    ) -> None:
        if not impacted_trade_dates:
            stats.setdefault("ticker_day_rows", 0)
            stats.setdefault("sector_day_rows", 0)
            return
        pending_articles_loaded = _coerce_int(stats.get("pending_articles_loaded"))
        self._emit_progress(
            stats,
            current=max(pending_articles_loaded, 1),
            total=max(pending_articles_loaded, 1),
            label=(
                "📰 Progression sentiment pipeline — agrégation features"
                if is_final
                else f"📰 Progression sentiment pipeline — flush intermédiaire features #{int(flush_index or 0)}"
            ),
            phase="feature_aggregation" if is_final else "feature_aggregation_flush",
        )
        effective_batch_days = int(getattr(self.config, "bootstrap_batch_days", 63) or 63)
        feature_date_batches = self._chunk_trade_dates(sorted(impacted_trade_dates), effective_batch_days)
        total_ticker_rows = 0
        total_sector_rows = 0

        for target_dates in feature_date_batches:
            target_date_set = set(target_dates)
            feature_window_start = min(target_dates) - timedelta(days=self.config.feature_history_buffer_days)
            feature_window_end = max(target_dates)
            stats["feature_window_start"] = feature_window_start.isoformat()
            stats["feature_window_end"] = feature_window_end.isoformat()
            ticker_df, sector_df, macro_df = self.repository.load_feature_frames(
                start_date=feature_window_start,
                end_date=feature_window_end,
            )

            ticker_features = build_ticker_daily_features(
                ticker_df,
                feature_version=self.config.feature_version,
                rolling_windows=self.config.feature_rolling_windows,
            )
            sector_features = build_sector_daily_features(
                sector_df,
                macro_df,
                feature_version=self.config.feature_version,
                rolling_windows=self.config.feature_rolling_windows,
            )
            ticker_features = ticker_features[ticker_features["trade_date"].isin(target_date_set)].copy()
            sector_features = sector_features[sector_features["trade_date"].isin(target_date_set)].copy()
            total_ticker_rows += self.repository.upsert_ticker_daily_features(ticker_features.to_dict(orient="records"))
            total_sector_rows += self.repository.upsert_sector_daily_features(sector_features.to_dict(orient="records"))

        stats["ticker_day_rows"] = total_ticker_rows
        stats["sector_day_rows"] = total_sector_rows
        stats["last_feature_flush_trade_dates"] = [trade_date.isoformat() for trade_date in impacted_trade_dates]
        self._emit_progress(
            stats,
            current=max(len(resolved_symbols), 1),
            total=max(len(resolved_symbols), 1),
            label=(
                "📰 Progression sentiment pipeline — persistance finale"
                if is_final
                else f"📰 Progression sentiment pipeline — persistance flush #{int(flush_index or 0)}"
            ),
            phase="persist_features" if is_final else "persist_features_flush",
        )

    def _finalize_feature_aggregation(
        self,
        *,
        impacted_trade_dates: list[date],
        remaining_impacted_trade_dates: list[date],
        resolved_symbols: list[str],
        stats: dict[str, object],
    ) -> None:
        stats["impacted_trade_dates"] = [trade_date.isoformat() for trade_date in impacted_trade_dates]
        self._flush_feature_aggregation(
            impacted_trade_dates=remaining_impacted_trade_dates,
            resolved_symbols=resolved_symbols,
            stats=stats,
            is_final=True,
        )

    def run(
        self,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
        symbols: list[str] | None = None,
        *,
        skip_ingestion: bool = False,
        skip_features: bool = False,
    ) -> dict:
        if skip_ingestion:
            resolved_symbols = sorted({symbol.strip().upper() for symbol in (symbols or []) if symbol and symbol.strip()})
            symbol_windows: dict[str, datetime] = {}
            symbol_resume_modes: dict[str, bool] = {}
            aggregation_start, end_utc = self._resolve_time_window(start_utc=start_utc, end_utc=end_utc)
        else:
            resolved_symbols = self._resolve_symbols(symbols)
            symbol_windows, symbol_resume_modes, end_utc = self._resolve_symbol_windows(
                start_utc=start_utc,
                end_utc=end_utc,
                symbols=resolved_symbols,
            )
            aggregation_start = (
                min(symbol_windows.values())
                if symbol_windows
                else self._coerce_utc(start_utc) or self._resolve_time_window(start_utc=start_utc, end_utc=end_utc)[0]
            )
        LOGGER.info(
            "Début event sentiment run | start_utc=%s end_utc=%s symbol_count=%s",
            aggregation_start,
            end_utc,
            len(resolved_symbols),
        )

        stats: dict[str, object] = {
            "resolved_symbols": len(resolved_symbols),
            "start_utc": aggregation_start.isoformat(),
            "end_utc": end_utc.isoformat(),
            "scoring_mode": self._resolve_scoring_mode(),
            "symbol_source": "explicit" if symbols is not None else "candidates",
            "resume_from_checkpoints": start_utc is None,
            "ingestion_skipped": bool(skip_ingestion),
            "feature_flush_every_n_pending_batches": int(
                getattr(self.config, "feature_flush_every_n_pending_batches", 0) or 0
            ),
        }
        self._emit_progress(
            stats,
            current=0,
            total=max(len(resolved_symbols), 1),
            label="📰 Progression sentiment pipeline — ingestion news",
            phase="ingestion",
        )
        if skip_ingestion:
            stats["ingestion"] = {"fetched": 0, "deduped": 0, "landed": 0, "ticker_maps": 0}
        elif resolved_symbols:
            ingestion_kwargs: dict[str, object] = {
                "start_utc": None,
                "end_utc": end_utc,
                "symbols": resolved_symbols,
                "symbol_start_overrides": symbol_windows,
                "symbol_resume_overrides": symbol_resume_modes,
                "resume_checkpoints": start_utc is None,
            }
            # S10.2 — progress_callback est optionnel : ne le transmet pas si la
            # pipeline n'a pas été configurée avec un callback (compat tests/fakes
            # qui n'acceptent pas ce kwarg). En production, NewsIngestionService
            # accepte progress_callback et le forwarder est conservé.
            if callable(self.progress_callback):
                ingestion_kwargs["progress_callback"] = (
                    lambda payload: self._emit_ingestion_progress(stats, payload)
                )
            stats["ingestion"] = self.ingestion.run(**ingestion_kwargs)
        else:
            stats["ingestion"] = {"fetched": 0, "deduped": 0, "landed": 0, "ticker_maps": 0}

        pending_scope = self._build_pending_scope(
            start_utc=self._coerce_utc(start_utc) if (start_utc is not None or skip_ingestion) else None,
            end_utc=end_utc if (end_utc is not None or skip_ingestion) else None,
            symbols=resolved_symbols if symbols is not None else None,
            skip_ingestion=skip_ingestion,
        )
        stats["pending_scope"] = {
            key: (value if not isinstance(value, list) else list(value))
            for key, value in pending_scope.items()
            if value not in (None, [])
        }
        stats["pending_batch_limit"] = int(self.config.sentiment_pending_limit)
        stats["pending_max_batches_per_run"] = int(
            getattr(self.config, "sentiment_pending_max_batches_per_run", 1)
        )
        scoring_mode = self._resolve_scoring_mode()
        if scoring_mode == "contextual_only":
            articles = []
            impacted_trade_dates = []
            remaining_impacted_trade_dates = []
            stats.setdefault("pending_articles_loaded", 0)
            stats.setdefault("pending_batches_processed", 0)
            stats.setdefault("sentiment_inferred", 0)
            stats.setdefault("macro_rows", 0)
            self._capture_finbert_runtime_stats(stats)
        else:
            _processed_articles_count, impacted_trade_dates, remaining_impacted_trade_dates = self._score_pending_batches(
                pending_scope,
                stats,
                resolved_symbols=resolved_symbols,
                skip_features=skip_features,
            )

        # Niveau 4 — re-scoring FinBERT contextualisé par couple (article, symbol).
        # Étape opt-in via config.enable_contextual_scoring. Garde-fous perf :
        # filtre par relevance_score + cap dur sur le nombre de paires.
        if scoring_mode in {"contextual_only", "standard_and_contextual"}:
            contextual_stats, contextual_impacted_trade_dates = self._run_contextual_scoring(pending_scope, stats)
            stats.update(contextual_stats)
            if contextual_impacted_trade_dates:
                contextual_trade_dates_set = set(contextual_impacted_trade_dates)
                impacted_trade_dates = sorted(set(impacted_trade_dates).union(contextual_trade_dates_set))
                remaining_impacted_trade_dates = sorted(
                    set(remaining_impacted_trade_dates).union(contextual_trade_dates_set)
                )
        if skip_features:
            stats["impacted_trade_dates"] = [d.isoformat() for d in impacted_trade_dates]
            stats.setdefault("ticker_day_rows", 0)
            stats.setdefault("sector_day_rows", 0)
            LOGGER.info(
                "Agrégation features ignorée (--skip-features) : sera effectuée par la commande suivante (history_backfill)."
            )
        else:
            self._finalize_feature_aggregation(
                impacted_trade_dates=impacted_trade_dates,
                remaining_impacted_trade_dates=remaining_impacted_trade_dates,
                resolved_symbols=resolved_symbols,
                stats=stats,
            )
        checkpoint_scope_symbols = resolved_symbols or self.repository.list_ticker_map_symbols(
            start_date=cast(date | None, pending_scope.get("start_date")),
            end_date=cast(date | None, pending_scope.get("end_date")),
            ingestion_source=str(pending_scope.get("ingestion_source") or self.config.source_name),
            symbols=cast(list[str] | None, pending_scope.get("symbols")),
        )
        if checkpoint_scope_symbols and not skip_ingestion:
            self._touch_checkpoint_stage_if_supported(checkpoint_scope_symbols, stage="news_ingested")
        if checkpoint_scope_symbols and scoring_mode in {"contextual_only", "standard_and_contextual"}:
            self._touch_checkpoint_stage_if_supported(checkpoint_scope_symbols, stage="contextual_scored")
        if checkpoint_scope_symbols and not skip_features:
            self._touch_checkpoint_stage_if_supported(checkpoint_scope_symbols, stage="features_aggregated")
        LOGGER.info(
            "Event sentiment pipeline summary | symbols=%s pending_batches=%s pending_articles=%s sentiment=%s contextual=%s ticker_day_rows=%s sector_day_rows=%s macro_rows=%s impacted_trade_dates=%s",
            len(resolved_symbols),
            _coerce_int(stats.get("pending_batches_processed")),
            _coerce_int(stats.get("pending_articles_loaded")),
            _coerce_int(stats.get("sentiment_inferred")),
            _coerce_int(stats.get("contextual_scored")),
            _coerce_int(stats.get("ticker_day_rows")),
            _coerce_int(stats.get("sector_day_rows")),
            _coerce_int(stats.get("macro_rows")),
            len(impacted_trade_dates),
        )
        return stats

    def _ensure_contextual_scorer(self) -> ContextualFinBERTScorer:
        if self._contextual_scorer is None:
            self._contextual_scorer = ContextualFinBERTScorer(
                model_name=self.config.finbert_model_name,
                model_version=self.config.finbert_model_version,
                batch_size=self.config.finbert_batch_size,
                max_length=self.config.finbert_max_length,
                model_revision=getattr(self.config, "finbert_model_revision", None),
            )
        self._contextual_scorer.adopt_runtime_from(self.finbert)
        scorer = self._contextual_scorer
        assert scorer is not None
        return scorer

    def _count_pending_contextual_pairs(self, **kwargs: object) -> int | None:
        counter = getattr(self.repository, "count_pending_contextual_pairs", None)
        if not callable(counter):
            return None
        return int(counter(**kwargs) or 0)

    def _run_contextual_scoring(
        self,
        pending_scope: dict[str, object],
        stats: dict[str, object],
    ) -> tuple[dict[str, object], list[date]]:
        """Niveau 4 — pipeline scoring contextualisé (article, symbol).

        Charge les paires en attente via ``load_pending_contextual_pairs``
        (lot interne borné par ``contextual_scoring_max_pairs_per_run`` et seuil
        ``contextual_scoring_min_relevance``), invoque le scorer contextuel
        FinBERT, persiste dans ``news_ticker_sentiment`` puis reboucle
        automatiquement jusqu'à épuisement du backlog contextuel sur le scope.
        Retourne les compteurs agrégés pour le summary.
        """
        cap = max(int(getattr(self.config, "contextual_scoring_max_pairs_per_run", 5000) or 5000), 1)
        min_relevance = float(getattr(self.config, "contextual_scoring_min_relevance", 0.0))
        contextual_scope = {
            key: (value if not isinstance(value, list) else list(value))
            for key, value in pending_scope.items()
            if value not in (None, [])
        }
        scorer = self._ensure_contextual_scorer()
        total_loaded = 0
        total_scored = 0
        batch_count = 0
        impacted_trade_dates: set[date] = set()
        contextual_query_kwargs = {
            "start_date": cast(date | None, pending_scope.get("start_date")),
            "end_date": cast(date | None, pending_scope.get("end_date")),
            "symbols": cast(list[str] | None, pending_scope.get("symbols")),
            "ingestion_source": cast(str | None, pending_scope.get("ingestion_source")),
        }
        initial_pending_pairs = self._count_pending_contextual_pairs(
            min_relevance=min_relevance,
            **contextual_query_kwargs,
        )
        estimated_batches = (
            int(ceil(initial_pending_pairs / cap))
            if initial_pending_pairs is not None and initial_pending_pairs > 0
            else 0
        )

        stats.update(
            {
                "contextual_pairs_loaded": 0,
                "contextual_scored": 0,
                "contextual_batches_processed": 0,
                "contextual_min_relevance": min_relevance,
                "contextual_cap": cap,
                "contextual_scope": contextual_scope,
                "contextual_total_pending_pairs": int(initial_pending_pairs or 0),
                "contextual_pairs_remaining": int(initial_pending_pairs or 0),
                "contextual_estimated_batches": int(estimated_batches),
                "contextual_current_batch": 0,
                "contextual_last_batch_size": 0,
            }
        )
        if initial_pending_pairs is not None:
            self._emit_progress(
                stats,
                current=0,
                total=max(initial_pending_pairs, 1),
                label=(
                    "📰 Progression sentiment pipeline — scoring contextuel"
                    if estimated_batches <= 0
                    else f"📰 Progression sentiment pipeline — scoring contextuel (lot 0/{estimated_batches})"
                ),
                phase="contextual_scoring",
                unit="paires",
            )

        while True:
            pending = self.repository.load_pending_contextual_pairs(
                limit=cap,
                min_relevance=min_relevance,
                **contextual_query_kwargs,
            )
            if not pending:
                break

            batch_count += 1
            total_loaded += len(pending)
            pairs: list[tuple[NormalizedNewsArticle, str, str | None]] = []
            for row in pending:
                article = NormalizedNewsArticle(
                    article_id=row["article_id"],
                    headline=row.get("headline") or "",
                    summary=row.get("summary"),
                    content=row.get("content"),
                    source=row.get("source") or "",
                    author=None,
                    url=None,
                    published_at_utc=row["published_at_utc"],
                    event_timestamp_utc=row["event_timestamp_utc"],
                    event_timestamp_ny=row["event_timestamp_ny"],
                    effective_trade_date=row["effective_trade_date"],
                    market_session_tag=row.get("market_session_tag") or "regular",
                    tickers=[],
                    raw_payload={},
                    is_major_event=int(row.get("is_major_event") or 0),
                )
                pairs.append((article, str(row["symbol"]), row.get("company_name")))
                if row.get("effective_trade_date") is not None:
                    impacted_trade_dates.add(cast(date, row["effective_trade_date"]))

            records = scorer.score_pairs(pairs)
            scored = int(self.repository.upsert_news_ticker_sentiment([asdict(record) for record in records]))
            if scored <= 0:
                raise RuntimeError(
                    "Scoring contextuel bloqué : aucune paire persistée sur le dernier lot. "
                    "Le backlog ne peut pas être drainé automatiquement."
                )
            total_scored += scored

            remaining_pending_pairs = self._count_pending_contextual_pairs(
                min_relevance=min_relevance,
                **contextual_query_kwargs,
            )
            processed_pairs = total_scored
            if initial_pending_pairs is not None and remaining_pending_pairs is not None:
                processed_pairs = max(total_scored, initial_pending_pairs - remaining_pending_pairs)

            stats.update(
                {
                    "contextual_pairs_loaded": total_loaded,
                    "contextual_scored": total_scored,
                    "contextual_batches_processed": batch_count,
                    "contextual_current_batch": batch_count,
                    "contextual_last_batch_size": len(pending),
                    "contextual_pairs_remaining": int(
                        remaining_pending_pairs if remaining_pending_pairs is not None else 0
                    ),
                }
            )
            total_for_progress = (
                initial_pending_pairs
                if initial_pending_pairs is not None and initial_pending_pairs > 0
                else max(total_loaded, total_scored, 1)
            )
            batch_label = (
                f"lot {batch_count}/{estimated_batches}"
                if estimated_batches > 0
                else f"lot {batch_count}"
            )
            self._emit_progress(
                stats,
                current=processed_pairs,
                total=total_for_progress,
                label=f"📰 Progression sentiment pipeline — scoring contextuel ({batch_label})",
                phase="contextual_scoring",
                unit="paires",
            )

        return (
            {
                "contextual_pairs_loaded": total_loaded,
                "contextual_scored": total_scored,
                "contextual_batches_processed": batch_count,
                "contextual_min_relevance": min_relevance,
                "contextual_cap": cap,
                "contextual_scope": contextual_scope,
                "contextual_total_pending_pairs": int(initial_pending_pairs or 0),
                "contextual_pairs_remaining": 0,
                "contextual_estimated_batches": int(estimated_batches),
                "contextual_current_batch": int(batch_count),
                "contextual_last_batch_size": int(len(pending) if "pending" in locals() and pending else 0),
            },
            sorted(impacted_trade_dates),
        )

    def _emit_ingestion_progress(self, stats: dict[str, object], payload: dict[str, object]) -> None:
        ingestion = payload.get("ingestion") if isinstance(payload.get("ingestion"), dict) else {}
        merged_stats = dict(stats)
        if ingestion:
            merged_stats["ingestion"] = dict(cast(dict[str, object], ingestion))
        self._emit_progress(
            merged_stats,
            current=_coerce_int(payload.get("current_symbol_index")),
            total=max(_coerce_int(payload.get("current_symbol_total")), 1),
            label="📰 Progression sentiment pipeline — ingestion news",
            phase="ingestion",
            item=str(payload.get("current_symbol") or "").strip() or None,
        )

    def _emit_progress(
        self,
        stats: dict[str, object],
        *,
        current: int,
        total: int,
        label: str,
        phase: str,
        unit: str | None = None,
        item: str | None = None,
    ) -> None:
        if not callable(self.progress_callback):
            return
        self.progress_callback(
            attach_live_progress(
                stats,
                current=current,
                total=total,
                label=label,
                phase=phase,
                unit=unit or ("symboles" if phase == "ingestion" else "articles"),
                item=item,
            )
        )

