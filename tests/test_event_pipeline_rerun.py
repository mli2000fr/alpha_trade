from datetime import UTC, date, datetime

import pandas as pd

from event_sentiment.config import EventSentimentConfig
from event_sentiment.models import ContextualSentimentRecord, MacroImpactRecord, SentimentRecord
from event_sentiment.pipeline import EventSentimentPipeline


class _InMemoryRepository:
    def __init__(self) -> None:
        self.candidates = ["AAPL"]
        self.checkpoints: dict[str, dict] = {}
        self.news_raw: dict[str, dict] = {}
        self.news_ticker_map: dict[tuple[str, str], dict] = {}
        self.news_sentiment: dict[str, dict] = {}
        self.news_ticker_sentiment: dict[tuple[str, str], dict] = {}
        self.macro_event_audit: dict[tuple[str, str, str], dict] = {}
        self.ticker_daily_features: dict[tuple[str, object], dict] = {}
        self.sector_daily_features: dict[tuple[str, object], dict] = {}
        self.feature_frame_requests: list[dict[str, object]] = []

    def get_checkpoint(self, source_name: str, symbol: str):
        return self.checkpoints.get(symbol)

    def get_checkpoints(self, source_name: str, symbols: list[str]):
        return {symbol: self.checkpoints[symbol] for symbol in symbols if symbol in self.checkpoints}

    def load_candidate_symbols(self) -> list[str]:
        return list(self.candidates)

    def upsert_news_raw(self, records):
        for record in records:
            self.news_raw[record["article_id"]] = dict(record)
        return len(records)

    def upsert_news_ticker_map(self, records):
        for record in records:
            self.news_ticker_map[(record["article_id"], record["symbol"])] = dict(record)
        return len(records)

    def load_pending_articles(
        self,
        limit: int = 1000,
        *,
        start_date=None,
        end_date=None,
        ingestion_source=None,
        symbols=None,
    ):
        pending = [
            row for article_id, row in sorted(self.news_raw.items())
            if article_id not in self.news_sentiment
        ]
        return pending[:limit]

    def upsert_news_sentiment(self, records):
        for record in records:
            self.news_sentiment[record["article_id"]] = dict(record)
        return len(records)

    def upsert_news_ticker_sentiment(self, records):
        for record in records:
            self.news_ticker_sentiment[(record["article_id"], record["symbol"])] = dict(record)
        return len(records)

    def load_pending_contextual_pairs(self, limit=5000, min_relevance=0.0):
        pending: list[dict] = []
        for (article_id, symbol), mapping in sorted(self.news_ticker_map.items()):
            if (article_id, symbol) in self.news_ticker_sentiment:
                continue
            raw = self.news_raw[article_id]
            pending.append(
                {
                    "article_id": article_id,
                    "symbol": symbol,
                    "headline": raw["headline"],
                    "summary": raw.get("summary"),
                    "content": raw.get("content"),
                    "source": raw["source"],
                    "published_at_utc": raw["published_at_utc"],
                    "event_timestamp_utc": raw["event_timestamp_utc"],
                    "event_timestamp_ny": raw["event_timestamp_ny"],
                    "effective_trade_date": raw["effective_trade_date"],
                    "market_session_tag": raw["market_session_tag"],
                    "is_major_event": raw["is_major_event"],
                    "company_name": f"{symbol} Inc.",
                    "relevance_score": mapping.get("relevance_score", 1.0),
                }
            )
        return [row for row in pending if float(row["relevance_score"]) >= float(min_relevance)][:limit]

    def upsert_macro_event_audit(self, records):
        for record in records:
            self.macro_event_audit[(record["article_id"], record["sector"], record["macro_event_type"])] = dict(record)
        return len(records)

    def load_feature_frames(self, start_date=None, end_date=None, trade_dates=None):
        ticker_rows: list[dict] = []
        sector_rows: list[dict] = []
        self.feature_frame_requests.append(
            {"start_date": start_date, "end_date": end_date, "trade_dates": list(trade_dates or [])}
        )

        selected_trade_dates = set(trade_dates or [])

        for article_id, raw in self.news_raw.items():
            sentiment = self.news_sentiment.get(article_id)
            if sentiment is None:
                continue
            if selected_trade_dates:
                if raw["effective_trade_date"] not in selected_trade_dates:
                    continue
            elif start_date is None or end_date is None or not (start_date <= raw["effective_trade_date"] <= end_date):
                continue

            for (mapped_article_id, symbol), mapping in self.news_ticker_map.items():
                if mapped_article_id != article_id:
                    continue
                joined = {
                    "article_id": article_id,
                    "effective_trade_date": raw["effective_trade_date"],
                    "event_timestamp_ny": raw["event_timestamp_ny"],
                    "market_session_tag": raw["market_session_tag"],
                    "source": raw["source"],
                    "is_major_event": raw["is_major_event"],
                    "symbol": symbol,
                    "sector": mapping.get("sector") or "Technology",
                    "sentiment_label": sentiment["sentiment_label"],
                    "positive_score": sentiment["positive_score"],
                    "neutral_score": sentiment["neutral_score"],
                    "negative_score": sentiment["negative_score"],
                    "sentiment_confidence": sentiment["sentiment_confidence"],
                    "sentiment_net_score": sentiment["sentiment_net_score"],
                }
                ticker_rows.append(joined)
                sector_rows.append({key: value for key, value in joined.items() if key != "symbol"})

        macro_rows = [
            record for record in self.macro_event_audit.values()
            if (
                record["trade_date"] in selected_trade_dates
                if selected_trade_dates
                else start_date is not None and end_date is not None and start_date <= record["trade_date"] <= end_date
            )
        ]
        return pd.DataFrame(ticker_rows), pd.DataFrame(sector_rows), pd.DataFrame(macro_rows)

    def upsert_ticker_daily_features(self, records):
        for record in records:
            self.ticker_daily_features[(record["symbol"], record["trade_date"])] = dict(record)
        return len(records)

    def upsert_sector_daily_features(self, records):
        for record in records:
            self.sector_daily_features[(record["sector"], record["trade_date"])] = dict(record)
        return len(records)


class _InMemoryIngestionService:
    def __init__(self, repository, config) -> None:
        self.repository = repository
        self.calls = 0

    def run(
        self,
        start_utc,
        end_utc,
        symbols,
        symbol_start_overrides=None,
        symbol_resume_overrides=None,
        resume_checkpoints=True,
    ):
        self.calls += 1
        article_id = "alpaca:article-1"
        self.repository.upsert_news_raw([
            {
                "article_id": article_id,
                "headline": "Apple rallies after strong outlook",
                "summary": "Guidance beats expectations",
                "content": None,
                "source": "Reuters",
                "author": "Reporter",
                "published_at_utc": datetime(2026, 1, 1, 22, 0, 0),
                "event_timestamp_utc": datetime(2026, 1, 1, 22, 0, 0),
                "event_timestamp_ny": datetime(2026, 1, 1, 17, 0, 0),
                "effective_trade_date": date(2026, 1, 2),
                "market_session_tag": "post_market",
                "url": "https://example.test/article-1",
                "ingestion_source": "alpaca",
                "dedupe_hash": "dedupe-1",
                "is_major_event": 1,
                "raw_payload": {"id": "article-1"},
            }
        ])
        self.repository.upsert_news_ticker_map([
            {
                "article_id": article_id,
                "symbol": "AAPL",
                "sector": "Technology",
                "sector_source": "stock_metadata",
                "sector_updated_at": datetime(2026, 1, 1, 0, 0, 0),
                "is_primary_ticker": 1,
            }
        ])
        return {"fetched": 1, "deduped": 0, "landed": 1, "ticker_maps": 1}


class _InMemoryFinBERTSentimentService:
    def __init__(self, *args, **kwargs) -> None:
        self.calls: list[list[object]] = []

    def score_articles(self, articles):
        article_list = list(articles)
        self.calls.append(article_list)
        records = []
        for article in article_list:
            records.append(
                SentimentRecord(
                    article_id=article.article_id,
                    model_name="ProsusAI/finbert",
                    model_version="finbert_v1",
                    text_strategy="headline_summary",
                    text_hash="hash-1",
                    truncated=0,
                    max_length_tokens=256,
                    sentiment_label="positive",
                    positive_score=0.91,
                    neutral_score=0.07,
                    negative_score=0.02,
                    sentiment_confidence=0.91,
                    sentiment_net_score=0.89,
                )
            )
        return records


class _InMemoryMacroRuleEngine:
    def __init__(self, *args, **kwargs) -> None:
        self.calls: list[tuple[object, object]] = []

    def classify(self, article, sentiment):
        self.calls.append((article, sentiment))
        return [
            MacroImpactRecord(
                article_id=article.article_id,
                trade_date=article.effective_trade_date,
                sector="Technology",
                macro_event_type="monetary_policy",
                impact_direction="positive",
                impact_score=0.4,
                macro_event_intensity=0.4,
                rule_version="macro_rules_v1",
                rule_hits={"keyword_hits": ["fed"]},
                explanation_text="synthetic test event",
            )
        ]


class _InMemoryContextualScorer:
    def __init__(self, *args, **kwargs) -> None:
        self.calls: list[list[tuple[object, str, str | None]]] = []

    def adopt_runtime_from(self, finbert) -> None:
        return None

    def score_pairs(self, pairs):
        pair_list = list(pairs)
        self.calls.append(pair_list)
        return [
            ContextualSentimentRecord(
                article_id=article.article_id,
                symbol=symbol,
                model_name="ProsusAI/finbert",
                model_version="finbert_contextual_v1",
                text_strategy="contextual_company",
                text_hash=f"ctx-{symbol.lower()}",
                truncated=0,
                max_length_tokens=256,
                sentiment_label="positive",
                positive_score=0.88,
                neutral_score=0.10,
                negative_score=0.02,
                sentiment_confidence=0.88,
                sentiment_net_score=0.86,
                scoring_version="contextual_v1",
            )
            for article, symbol, _company_name in pair_list
        ]


def test_pipeline_can_drain_multiple_pending_batches_in_single_run(monkeypatch) -> None:
    repository = _InMemoryRepository()
    for idx, trade_date in enumerate((date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4)), start=1):
        article_id = f"alpaca:article-{idx}"
        repository.upsert_news_raw([
            {
                "article_id": article_id,
                "headline": f"Headline {idx}",
                "summary": f"Summary {idx}",
                "content": None,
                "source": "Reuters",
                "author": "Reporter",
                "published_at_utc": datetime(2026, 1, idx, 22, 0, 0),
                "event_timestamp_utc": datetime(2026, 1, idx, 22, 0, 0),
                "event_timestamp_ny": datetime(2026, 1, idx, 17, 0, 0),
                "effective_trade_date": trade_date,
                "market_session_tag": "post_market",
                "url": f"https://example.test/article-{idx}",
                "ingestion_source": "alpaca",
                "dedupe_hash": f"dedupe-{idx}",
                "is_major_event": 0,
                "raw_payload": {"id": article_id},
            }
        ])
        repository.upsert_news_ticker_map([
            {
                "article_id": article_id,
                "symbol": "AAPL",
                "sector": "Technology",
                "sector_source": "stock_metadata",
                "sector_updated_at": datetime(2026, 1, 1, 0, 0, 0),
                "is_primary_ticker": 1,
            }
        ])

    config = EventSentimentConfig.for_provider(
        "alpaca",
        sentiment_pending_limit=1,
        sentiment_pending_max_batches_per_run=3,
    )
    fake_finbert = _InMemoryFinBERTSentimentService()

    class _NoOpMacroRuleEngine:
        def classify(self, article, sentiment):
            return []

    monkeypatch.setattr(
        "event_sentiment.pipeline.NewsIngestionService",
        lambda repository, config: _InMemoryIngestionService(repository, config),
    )
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", lambda *args, **kwargs: fake_finbert)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", lambda *args, **kwargs: _NoOpMacroRuleEngine())

    pipeline = EventSentimentPipeline(repository=repository, config=config)
    stats = pipeline.run(
        start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        end_utc=datetime(2026, 1, 5, tzinfo=UTC),
        symbols=["AAPL"],
        skip_ingestion=True,
    )

    assert stats["pending_batches_processed"] == 3
    assert stats["pending_articles_loaded"] == 3
    assert stats["sentiment_inferred"] == 3
    assert sorted(repository.news_sentiment) == [
        "alpaca:article-1",
        "alpaca:article-2",
        "alpaca:article-3",
    ]
    assert len(fake_finbert.calls) == 3
    assert all(len(call) == 1 for call in fake_finbert.calls)
    assert len(repository.feature_frame_requests) == 1
    assert repository.feature_frame_requests[0]["start_date"] == date(2025, 11, 18)
    assert repository.feature_frame_requests[0]["end_date"] == date(2026, 1, 4)


def test_pipeline_flushes_features_every_n_pending_batches(monkeypatch) -> None:
    repository = _InMemoryRepository()
    for idx, trade_date in enumerate((date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4)), start=1):
        article_id = f"alpaca:feature-flush-{idx}"
        repository.upsert_news_raw([
            {
                "article_id": article_id,
                "headline": f"Headline {idx}",
                "summary": f"Summary {idx}",
                "content": None,
                "source": "Reuters",
                "author": "Reporter",
                "published_at_utc": datetime(2026, 1, idx, 22, 0, 0),
                "event_timestamp_utc": datetime(2026, 1, idx, 22, 0, 0),
                "event_timestamp_ny": datetime(2026, 1, idx, 17, 0, 0),
                "effective_trade_date": trade_date,
                "market_session_tag": "post_market",
                "url": f"https://example.test/feature-flush-{idx}",
                "ingestion_source": "alpaca",
                "dedupe_hash": f"feature-flush-{idx}",
                "is_major_event": 0,
                "raw_payload": {"id": article_id},
            }
        ])
        repository.upsert_news_ticker_map([
            {
                "article_id": article_id,
                "symbol": "AAPL",
                "sector": "Technology",
                "sector_source": "stock_metadata",
                "sector_updated_at": datetime(2026, 1, 1, 0, 0, 0),
                "is_primary_ticker": 1,
            }
        ])

    config = EventSentimentConfig.for_provider(
        "alpaca",
        sentiment_pending_limit=1,
        sentiment_pending_max_batches_per_run=3,
        feature_flush_every_n_pending_batches=2,
    )
    fake_finbert = _InMemoryFinBERTSentimentService()

    class _NoOpMacroRuleEngine:
        def classify(self, article, sentiment):
            return []

    monkeypatch.setattr(
        "event_sentiment.pipeline.NewsIngestionService",
        lambda repository, config: _InMemoryIngestionService(repository, config),
    )
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", lambda *args, **kwargs: fake_finbert)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", lambda *args, **kwargs: _NoOpMacroRuleEngine())

    pipeline = EventSentimentPipeline(repository=repository, config=config)
    stats = pipeline.run(
        start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        end_utc=datetime(2026, 1, 5, tzinfo=UTC),
        symbols=["AAPL"],
        skip_ingestion=True,
    )

    assert stats["feature_flushes_completed"] == 1
    assert len(repository.feature_frame_requests) == 2
    assert repository.feature_frame_requests[0]["end_date"] == date(2026, 1, 3)
    assert repository.feature_frame_requests[1]["end_date"] == date(2026, 1, 4)
    assert set(repository.ticker_daily_features) == {
        ("AAPL", date(2026, 1, 2)),
        ("AAPL", date(2026, 1, 3)),
        ("AAPL", date(2026, 1, 4)),
    }


def test_pipeline_rerun_is_idempotent_end_to_end(monkeypatch) -> None:
    repository = _InMemoryRepository()
    config = EventSentimentConfig()
    fake_ingestion = _InMemoryIngestionService(repository, config)
    fake_finbert = _InMemoryFinBERTSentimentService()
    fake_macro = _InMemoryMacroRuleEngine()

    monkeypatch.setattr("event_sentiment.pipeline.NewsIngestionService", lambda repository, config: fake_ingestion)
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", lambda *args, **kwargs: fake_finbert)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", lambda *args, **kwargs: fake_macro)

    pipeline = EventSentimentPipeline(repository=repository, config=config)
    start_utc = datetime(2026, 1, 1, tzinfo=UTC)
    end_utc = datetime(2026, 1, 3, tzinfo=UTC)

    first_stats = pipeline.run(start_utc=start_utc, end_utc=end_utc, symbols=None)
    second_stats = pipeline.run(start_utc=start_utc, end_utc=end_utc, symbols=None)

    assert first_stats["sentiment_inferred"] == 1
    assert second_stats["sentiment_inferred"] == 0
    assert len(repository.news_raw) == 1
    assert len(repository.news_ticker_map) == 1
    assert len(repository.news_sentiment) == 1
    assert len(repository.macro_event_audit) == 1
    assert len(repository.ticker_daily_features) == 1
    assert len(repository.sector_daily_features) == 1
    assert first_stats["impacted_trade_dates"] == ["2026-01-02"]
    assert second_stats["impacted_trade_dates"] == []
    assert len(repository.feature_frame_requests) == 1
    assert repository.feature_frame_requests[0]["trade_dates"] == []
    assert repository.feature_frame_requests[0]["start_date"] == date(2025, 11, 18)
    assert repository.feature_frame_requests[0]["end_date"] == date(2026, 1, 2)
    assert fake_ingestion.calls == 2
    assert len(fake_finbert.calls) == 1
    assert len(fake_finbert.calls[0]) == 1


def test_pipeline_preserves_multiple_macro_event_types_for_same_article_and_sector(monkeypatch) -> None:
    repository = _InMemoryRepository()
    config = EventSentimentConfig()
    fake_ingestion = _InMemoryIngestionService(repository, config)
    fake_finbert = _InMemoryFinBERTSentimentService()

    class _MultiMacroRuleEngine:
        def classify(self, article, sentiment):
            return [
                MacroImpactRecord(
                    article_id=article.article_id,
                    trade_date=article.effective_trade_date,
                    sector="Technology",
                    macro_event_type="monetary_policy",
                    impact_direction="positive",
                    impact_score=0.4,
                    macro_event_intensity=0.4,
                    rule_version="macro_rules_v1",
                    rule_hits={"keyword_hits": ["fed"]},
                    explanation_text="synthetic monetary policy event",
                ),
                MacroImpactRecord(
                    article_id=article.article_id,
                    trade_date=article.effective_trade_date,
                    sector="Technology",
                    macro_event_type="inflation_employment",
                    impact_direction="negative",
                    impact_score=-0.3,
                    macro_event_intensity=0.3,
                    rule_version="macro_rules_v1",
                    rule_hits={"keyword_hits": ["cpi"]},
                    explanation_text="synthetic inflation event",
                ),
            ]

    monkeypatch.setattr("event_sentiment.pipeline.NewsIngestionService", lambda repository, config: fake_ingestion)
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", lambda *args, **kwargs: fake_finbert)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", lambda *args, **kwargs: _MultiMacroRuleEngine())

    pipeline = EventSentimentPipeline(repository=repository, config=config)
    stats = pipeline.run(
        start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        end_utc=datetime(2026, 1, 3, tzinfo=UTC),
        symbols=None,
    )

    assert stats["macro_rows"] == 2
    assert len(repository.macro_event_audit) == 2
    assert (
        "alpaca:article-1",
        "Technology",
        "monetary_policy",
    ) in repository.macro_event_audit
    assert (
        "alpaca:article-1",
        "Technology",
        "inflation_employment",
    ) in repository.macro_event_audit


def test_pipeline_contextual_only_rebuilds_features_without_standard_pending_scoring(monkeypatch) -> None:
    repository = _InMemoryRepository()
    article_id = "alpaca:contextual-only-1"
    repository.upsert_news_raw([
        {
            "article_id": article_id,
            "headline": "Apple suppliers rally",
            "summary": "Contextual rerating",
            "content": None,
            "source": "Reuters",
            "author": "Reporter",
            "published_at_utc": datetime(2026, 1, 2, 22, 0, 0),
            "event_timestamp_utc": datetime(2026, 1, 2, 22, 0, 0),
            "event_timestamp_ny": datetime(2026, 1, 2, 17, 0, 0),
            "effective_trade_date": date(2026, 1, 3),
            "market_session_tag": "post_market",
            "url": "https://example.test/contextual-only-1",
            "ingestion_source": "alpaca",
            "dedupe_hash": "contextual-only-1",
            "is_major_event": 0,
            "raw_payload": {"id": article_id},
        }
    ])
    repository.upsert_news_ticker_map([
        {
            "article_id": article_id,
            "symbol": "AAPL",
            "sector": "Technology",
            "sector_source": "stock_metadata",
            "sector_updated_at": datetime(2026, 1, 1, 0, 0, 0),
            "is_primary_ticker": 1,
            "relevance_score": 0.9,
        }
    ])
    repository.upsert_news_sentiment([
        {
            "article_id": article_id,
            "model_name": "ProsusAI/finbert",
            "model_version": "finbert_v1",
            "text_strategy": "headline_summary",
            "text_hash": "base-hash",
            "truncated": 0,
            "max_length_tokens": 256,
            "sentiment_label": "positive",
            "positive_score": 0.81,
            "neutral_score": 0.15,
            "negative_score": 0.04,
            "sentiment_confidence": 0.81,
            "sentiment_net_score": 0.77,
        }
    ])

    config = EventSentimentConfig.for_provider(
        "alpaca",
        scoring_mode="contextual_only",
        contextual_scoring_min_relevance=0.2,
        contextual_scoring_max_pairs_per_run=100,
    )
    fake_finbert = _InMemoryFinBERTSentimentService()
    fake_contextual = _InMemoryContextualScorer()

    monkeypatch.setattr(
        "event_sentiment.pipeline.NewsIngestionService",
        lambda repository, config: _InMemoryIngestionService(repository, config),
    )
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", lambda *args, **kwargs: fake_finbert)
    monkeypatch.setattr("event_sentiment.pipeline.ContextualFinBERTScorer", lambda *args, **kwargs: fake_contextual)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", lambda *args, **kwargs: _InMemoryMacroRuleEngine())

    pipeline = EventSentimentPipeline(repository=repository, config=config)
    stats = pipeline.run(
        start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        end_utc=datetime(2026, 1, 5, tzinfo=UTC),
        symbols=["AAPL"],
        skip_ingestion=True,
    )

    assert stats["scoring_mode"] == "contextual_only"
    assert stats["pending_batches_processed"] == 0
    assert stats["sentiment_inferred"] == 0
    assert stats["contextual_pairs_loaded"] == 1
    assert stats["contextual_scored"] == 1
    assert len(fake_finbert.calls) == 0
    assert len(fake_contextual.calls) == 1
    assert repository.news_ticker_sentiment[(article_id, "AAPL")]["scoring_version"] == "contextual_v1"
    assert len(repository.feature_frame_requests) == 1
    assert repository.feature_frame_requests[0]["end_date"] == date(2026, 1, 3)


def test_pipeline_final_feature_aggregation_is_chunked_for_large_trade_date_ranges(monkeypatch) -> None:
    repository = _InMemoryRepository()
    for idx, trade_date in enumerate(
        (date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4), date(2026, 1, 5), date(2026, 1, 6)),
        start=1,
    ):
        article_id = f"alpaca:chunked-feature-flush-{idx}"
        repository.upsert_news_raw([
            {
                "article_id": article_id,
                "headline": f"Headline {idx}",
                "summary": f"Summary {idx}",
                "content": None,
                "source": "Reuters",
                "author": "Reporter",
                "published_at_utc": datetime(2026, 1, idx, 22, 0, 0),
                "event_timestamp_utc": datetime(2026, 1, idx, 22, 0, 0),
                "event_timestamp_ny": datetime(2026, 1, idx, 17, 0, 0),
                "effective_trade_date": trade_date,
                "market_session_tag": "post_market",
                "url": f"https://example.test/chunked-feature-flush-{idx}",
                "ingestion_source": "alpaca",
                "dedupe_hash": f"chunked-feature-flush-{idx}",
                "is_major_event": 0,
                "raw_payload": {"id": article_id},
            }
        ])
        repository.upsert_news_ticker_map([
            {
                "article_id": article_id,
                "symbol": "AAPL",
                "sector": "Technology",
                "sector_source": "stock_metadata",
                "sector_updated_at": datetime(2026, 1, 1, 0, 0, 0),
                "is_primary_ticker": 1,
            }
        ])

    config = EventSentimentConfig.for_provider(
        "alpaca",
        sentiment_pending_limit=1,
        sentiment_pending_max_batches_per_run=5,
        bootstrap_batch_days=2,
    )
    fake_finbert = _InMemoryFinBERTSentimentService()

    class _NoOpMacroRuleEngine:
        def classify(self, article, sentiment):
            return []

    monkeypatch.setattr(
        "event_sentiment.pipeline.NewsIngestionService",
        lambda repository, config: _InMemoryIngestionService(repository, config),
    )
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", lambda *args, **kwargs: fake_finbert)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", lambda *args, **kwargs: _NoOpMacroRuleEngine())

    pipeline = EventSentimentPipeline(repository=repository, config=config)
    stats = pipeline.run(
        start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        end_utc=datetime(2026, 1, 7, tzinfo=UTC),
        symbols=["AAPL"],
        skip_ingestion=True,
    )

    assert stats["pending_articles_loaded"] == 5
    assert len(repository.feature_frame_requests) == 3
    assert [request["end_date"] for request in repository.feature_frame_requests] == [
        date(2026, 1, 3),
        date(2026, 1, 5),
        date(2026, 1, 6),
    ]
    assert set(repository.ticker_daily_features) == {
        ("AAPL", date(2026, 1, 2)),
        ("AAPL", date(2026, 1, 3)),
        ("AAPL", date(2026, 1, 4)),
        ("AAPL", date(2026, 1, 5)),
        ("AAPL", date(2026, 1, 6)),
    }


