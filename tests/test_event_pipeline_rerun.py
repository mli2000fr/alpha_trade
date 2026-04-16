from datetime import UTC, date, datetime

import pandas as pd

from event_sentiment.config import EventSentimentConfig
from event_sentiment.models import MacroImpactRecord, SentimentRecord
from event_sentiment.pipeline import EventSentimentPipeline


class _InMemoryRepository:
    def __init__(self) -> None:
        self.candidates = ["AAPL"]
        self.checkpoint = None
        self.news_raw: dict[str, dict] = {}
        self.news_ticker_map: dict[tuple[str, str], dict] = {}
        self.news_sentiment: dict[str, dict] = {}
        self.macro_event_audit: dict[tuple[str, str], dict] = {}
        self.ticker_daily_features: dict[tuple[str, object], dict] = {}
        self.sector_daily_features: dict[tuple[str, object], dict] = {}

    def get_checkpoint(self, source_name: str):
        return self.checkpoint

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

    def load_pending_articles(self, limit: int = 1000):
        pending = [
            row for article_id, row in sorted(self.news_raw.items())
            if article_id not in self.news_sentiment
        ]
        return pending[:limit]

    def upsert_news_sentiment(self, records):
        for record in records:
            self.news_sentiment[record["article_id"]] = dict(record)
        return len(records)

    def upsert_macro_event_audit(self, records):
        for record in records:
            self.macro_event_audit[(record["article_id"], record["sector"])] = dict(record)
        return len(records)

    def load_feature_frames(self, start_date, end_date):
        ticker_rows: list[dict] = []
        sector_rows: list[dict] = []

        for article_id, raw in self.news_raw.items():
            sentiment = self.news_sentiment.get(article_id)
            if sentiment is None:
                continue
            if not (start_date <= raw["effective_trade_date"] <= end_date):
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
            if start_date <= record["trade_date"] <= end_date
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

    def run(self, start_utc, end_utc, symbols):
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
    assert fake_ingestion.calls == 2
    assert len(fake_finbert.calls) == 2
    assert len(fake_finbert.calls[0]) == 1
    assert len(fake_finbert.calls[1]) == 0


