import logging
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from event_sentiment.aggregation import build_sector_daily_features, build_ticker_daily_features
from event_sentiment.ingestion import NewsIngestionService
from event_sentiment.macro_rules import MacroRuleEngine
from event_sentiment.models import NormalizedNewsArticle
from event_sentiment.scoring import FinBERTSentimentService

LOGGER = logging.getLogger(__name__)


class EventSentimentPipeline:
    def __init__(self, repository, config) -> None:
        self.repository = repository
        self.config = config
        self.ingestion = NewsIngestionService(repository=repository, config=config)
        self.finbert = FinBERTSentimentService(
            model_name=config.finbert_model_name,
            model_version=config.finbert_model_version,
            batch_size=config.finbert_batch_size,
            max_length=config.finbert_max_length,
        )
        self.macro_engine = MacroRuleEngine(rule_version=config.macro_rule_version)

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

    def run(self, start_utc: datetime | None = None, end_utc: datetime | None = None, symbols: list[str] | None = None) -> dict:
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

        stats: dict[str, object] = {}
        if resolved_symbols:
            stats["ingestion"] = self.ingestion.run(
                start_utc=None,
                end_utc=end_utc,
                symbols=resolved_symbols,
                symbol_start_overrides=symbol_windows,
                symbol_resume_overrides=symbol_resume_modes,
                resume_checkpoints=start_utc is None,
            )
        else:
            stats["ingestion"] = {"fetched": 0, "deduped": 0, "landed": 0, "ticker_maps": 0}

        pending_rows = self.repository.load_pending_articles(limit=self.config.sentiment_pending_limit)
        articles = [
            NormalizedNewsArticle(
                article_id=row["article_id"],
                headline=row["headline"],
                summary=row["summary"],
                content=row["content"],
                source=row["source"],
                author=row["author"],
                url=row["url"],
                published_at_utc=row["published_at_utc"],
                event_timestamp_utc=row["event_timestamp_utc"],
                event_timestamp_ny=row["event_timestamp_ny"],
                effective_trade_date=row["effective_trade_date"],
                market_session_tag=row["market_session_tag"],
                tickers=[],
                raw_payload={},
                is_major_event=int(row["is_major_event"] or 0),
            )
            for row in pending_rows
        ]

        sentiment_records = self.finbert.score_articles(articles)
        stats["sentiment_inferred"] = self.repository.upsert_news_sentiment([asdict(record) for record in sentiment_records])
        sentiment_map = {record.article_id: record for record in sentiment_records}
        macro_records = []
        for article in articles:
            sentiment = sentiment_map.get(article.article_id)
            if sentiment is None:
                continue
            macro_records.extend(self.macro_engine.classify(article, sentiment))

        stats["macro_rows"] = self.repository.upsert_macro_event_audit([asdict(record) for record in macro_records])
        ticker_df, sector_df, macro_df = self.repository.load_feature_frames(
            start_date=aggregation_start.date(),
            end_date=end_utc.date() + timedelta(days=5),
        )

        ticker_features = build_ticker_daily_features(ticker_df, feature_version=self.config.feature_version)
        sector_features = build_sector_daily_features(sector_df, macro_df, feature_version=self.config.feature_version)
        stats["ticker_day_rows"] = self.repository.upsert_ticker_daily_features(ticker_features.to_dict(orient="records"))
        stats["sector_day_rows"] = self.repository.upsert_sector_daily_features(sector_features.to_dict(orient="records"))
        LOGGER.info("Event sentiment pipeline summary | stats=%s", stats)
        return stats
