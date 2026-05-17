from __future__ import annotations

import json
import sys

import pandas as pd

from database import connection as db_connection
from event_sentiment import cli, signal_aggregator
from event_sentiment.models import ContextualSentimentRecord


def _payload_from_stdout(stdout: str, prefix: str) -> dict[str, object]:
    assert stdout.startswith(prefix)
    return json.loads(stdout[len(prefix):])


def _payloads_from_output(output: str, prefix: str) -> list[dict[str, object]]:
    return [_payload_from_stdout(line, prefix) for line in output.splitlines() if line.strip()]


class _FakeEventSentimentPipeline:
    def __init__(self, repository=None, config=None, progress_callback=None) -> None:
        self.repository = repository
        self.config = config
        self.progress_callback = progress_callback

    def run(self, start_utc=None, end_utc=None, symbols=None, skip_ingestion=False, skip_features=False) -> dict[str, object]:
        return {
            "resolved_symbols": len(symbols or []),
            "start_utc": "2026-04-01T00:00:00+00:00",
            "end_utc": "2026-04-02T00:00:00+00:00",
            "ingestion": {
                "fetched": 24,
                "deduped": 20,
                "landed": 18,
                "ticker_maps": 14,
            },
            "sentiment_inferred": 17,
            "macro_rows": 4,
            "ticker_day_rows": 6,
            "sector_day_rows": 2,
        }


class _FakeSignalAggregator:
    def __init__(self, engine, config=None) -> None:
        self.engine = engine
        self.config = config

    def merge(self, scores_df: pd.DataFrame, trade_date=None) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "signal_active": True,
                    "total_news": 5,
                    "final_score_sentiment": 0.82,
                },
                {
                    "symbol": "MSFT",
                    "signal_active": False,
                    "total_news": 1,
                    "final_score_sentiment": 0.64,
                },
            ]
        )

    def save_to_db(self, enriched_df: pd.DataFrame) -> int:
        return int(len(enriched_df))


def test_event_sentiment_cli_main_emits_structured_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "EventSentimentRepository", lambda: object())

    class _FakeConfig:
        def __init__(self, **_: object) -> None:
            self.news_provider = "eodhd"
            self.source_name = "eodhd_news"
            self.provider_ticker_relevance_mode = "provider_default"

        @classmethod
        def for_provider(cls, news_provider: str, **overrides: object) -> "_FakeConfig":
            cfg = cls(**overrides)
            cfg.news_provider = news_provider
            cfg.source_name = f"{news_provider}_news"
            return cfg

    monkeypatch.setattr(cli, "EventSentimentConfig", _FakeConfig)
    monkeypatch.setattr(cli, "EventSentimentPipeline", _FakeEventSentimentPipeline)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "event_sentiment.py",
            "--start-utc",
            "2026-04-01T00:00:00Z",
            "--end-utc",
            "2026-04-02T00:00:00Z",
            "--symbols",
            "aapl,msft",
        ],
    )

    cli.main()

    payloads = _payloads_from_output(capsys.readouterr().out.strip(), cli.RUN_SUMMARY_PREFIX)
    payload = payloads[-1]
    assert payload["resolved_symbols"] == 2
    assert payload["fetched_articles"] == 24
    assert payload["landed_articles"] == 18
    assert payload["sentiment_inferred"] == 17
    assert payload["ticker_day_rows"] == 6
    assert payload["sector_day_rows"] == 2
    assert payload["news_provider"] == "eodhd"
    assert payload["source_name"] == "eodhd_news"


def test_event_sentiment_cli_main_forwards_perf_overrides(monkeypatch) -> None:
    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "EventSentimentRepository", lambda: object())

    captured_overrides: dict[str, object] = {}

    class _FakeConfig:
        def __init__(self, **_: object) -> None:
            self.news_provider = "eodhd"
            self.source_name = "eodhd_news"
            self.provider_ticker_relevance_mode = "provider_default"

        @classmethod
        def for_provider(cls, news_provider: str, **overrides: object) -> "_FakeConfig":
            captured_overrides.update(overrides)
            cfg = cls(**overrides)
            cfg.news_provider = news_provider
            cfg.source_name = f"{news_provider}_news"
            return cfg

    monkeypatch.setattr(cli, "EventSentimentConfig", _FakeConfig)
    monkeypatch.setattr(cli, "EventSentimentPipeline", _FakeEventSentimentPipeline)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "event_sentiment.py",
            "--skip-ingestion",
            "--scoring-mode",
            "contextual_only",
            "--sentiment-pending-limit",
            "6000",
            "--sentiment-pending-max-batches",
            "8",
            "--feature-flush-every-n-batches",
            "3",
            "--finbert-batch-size",
            "48",
        ],
    )

    cli.main()

    assert captured_overrides["scoring_mode"] == "contextual_only"
    assert captured_overrides["enable_contextual_scoring"] is True
    assert captured_overrides["sentiment_pending_limit"] == 6000
    assert captured_overrides["sentiment_pending_max_batches_per_run"] == 8
    assert captured_overrides["feature_flush_every_n_pending_batches"] == 3
    assert captured_overrides["finbert_batch_size"] == 48


def test_event_sentiment_pipeline_emits_live_progress(monkeypatch) -> None:
    class _DummyRepository:
        def load_candidate_symbols(self):
            return ["AAPL", "MSFT"]

        def load_pending_articles(self, limit=None, **kwargs):
            return []

        def upsert_news_sentiment(self, rows):
            return 0

        def upsert_macro_event_audit(self, rows):
            return 0

        def load_feature_frames(self, start_date=None, end_date=None):
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        def upsert_ticker_daily_features(self, rows):
            return 0

        def upsert_sector_daily_features(self, rows):
            return 0

    class _DummyConfig:
        finbert_model_name = "dummy"
        finbert_model_version = "1"
        finbert_batch_size = 4
        finbert_max_length = 128
        finbert_model_revision = None
        macro_rule_version = "1"
        initial_backfill_days = 2
        checkpoint_overlap_minutes = 60
        candidate_reactivation_backfill_days = 5
        sentiment_pending_limit = 100
        sentiment_pending_max_batches_per_run = 1
        feature_history_buffer_days = 2
        feature_version = "v1"
        feature_rolling_windows = [3]
        source_name = "alpaca_news"
        regular_session_maps_to_same_day = True

    progress_payloads: list[dict[str, object]] = []
    pipeline = cli.EventSentimentPipeline(
        repository=_DummyRepository(),
        config=_DummyConfig(),
        progress_callback=progress_payloads.append,
    )

    monkeypatch.setattr(
        pipeline,
        "_resolve_symbol_windows",
        lambda start_utc, end_utc, symbols: ({symbol: cli.dateutil.parser.isoparse("2026-04-01T00:00:00Z") for symbol in symbols}, {symbol: False for symbol in symbols}, cli.dateutil.parser.isoparse("2026-04-02T00:00:00Z")),
    )
    monkeypatch.setattr(
        pipeline.ingestion,
        "run",
        lambda **kwargs: kwargs["progress_callback"]({
            "ingestion": {"fetched": 10, "deduped": 8, "landed": 7, "ticker_maps": 6},
            "current_symbol": "AAPL",
            "current_symbol_index": 1,
            "current_symbol_total": 2,
        }) or {"fetched": 20, "deduped": 16, "landed": 14, "ticker_maps": 12},
    )
    monkeypatch.setattr(pipeline.finbert, "score_articles", lambda articles: [])

    stats = pipeline.run(symbols=["AAPL", "MSFT"])

    assert stats["resolved_symbols"] == 2
    assert progress_payloads
    assert any(payload.get("progress_phase") == "ingestion" for payload in progress_payloads)
    ingestion_payload = next(
        payload
        for payload in progress_payloads
        if payload.get("progress_phase") == "ingestion" and payload.get("progress_current") == 1
    )
    assert ingestion_payload["progress_current"] == 1
    assert ingestion_payload["progress_total"] == 2
    assert ingestion_payload["progress_item"] == "AAPL"


def test_event_sentiment_pipeline_contextual_only_forwards_scope_to_repository(monkeypatch) -> None:
    class _DummyRepository:
        def __init__(self) -> None:
            self.contextual_kwargs: dict[str, object] | None = None

        def load_candidate_symbols(self):
            return ["AAPL"]

        def load_pending_contextual_pairs(self, **kwargs):
            self.contextual_kwargs = dict(kwargs)
            return []

        def upsert_news_ticker_sentiment(self, rows):
            return 0

    class _DummyConfig:
        finbert_model_name = "dummy"
        finbert_model_version = "1"
        finbert_batch_size = 4
        finbert_max_length = 128
        finbert_model_revision = None
        macro_rule_version = "1"
        initial_backfill_days = 2
        checkpoint_overlap_minutes = 60
        candidate_reactivation_backfill_days = 5
        sentiment_pending_limit = 100
        sentiment_pending_max_batches_per_run = 1
        feature_history_buffer_days = 2
        feature_version = "v1"
        feature_rolling_windows = [3]
        source_name = "alpaca_news"
        provider_name = "alpaca"
        regular_session_maps_to_same_day = True
        scoring_mode = "contextual_only"
        enable_contextual_scoring = True
        contextual_scoring_min_relevance = 0.35
        contextual_scoring_max_pairs_per_run = 250

    repository = _DummyRepository()
    pipeline_instance = cli.EventSentimentPipeline(
        repository=repository,
        config=_DummyConfig(),
        progress_callback=None,
    )

    stats = pipeline_instance.run(
        start_utc=cli.dateutil.parser.isoparse("2026-04-01T00:00:00Z"),
        end_utc=cli.dateutil.parser.isoparse("2026-04-02T00:00:00Z"),
        symbols=["AAPL"],
        skip_ingestion=True,
        skip_features=True,
    )

    assert stats["contextual_pairs_loaded"] == 0
    assert repository.contextual_kwargs == {
        "limit": 250,
        "min_relevance": 0.35,
        "start_date": cli.dateutil.parser.isoparse("2026-04-01T00:00:00Z").date(),
        "end_date": cli.dateutil.parser.isoparse("2026-04-02T00:00:00Z").date(),
        "symbols": ["AAPL"],
        "ingestion_source": "alpaca",
    }


def test_event_sentiment_pipeline_emits_contextual_batch_progress(monkeypatch) -> None:
    class _DummyRepository:
        def __init__(self) -> None:
            self.pending_pairs = [
                {
                    "article_id": "alpaca:ctx-1",
                    "symbol": "AAPL",
                    "headline": "Headline 1",
                    "summary": "Summary 1",
                    "content": None,
                    "source": "Reuters",
                    "published_at_utc": cli.dateutil.parser.isoparse("2026-04-01T12:00:00Z").replace(tzinfo=None),
                    "event_timestamp_utc": cli.dateutil.parser.isoparse("2026-04-01T12:00:00Z").replace(tzinfo=None),
                    "event_timestamp_ny": cli.dateutil.parser.isoparse("2026-04-01T08:00:00Z").replace(tzinfo=None),
                    "effective_trade_date": cli.dateutil.parser.isoparse("2026-04-01T00:00:00Z").date(),
                    "market_session_tag": "regular",
                    "is_major_event": 0,
                    "company_name": "Apple Inc.",
                    "relevance_score": 0.9,
                },
                {
                    "article_id": "alpaca:ctx-2",
                    "symbol": "MSFT",
                    "headline": "Headline 2",
                    "summary": "Summary 2",
                    "content": None,
                    "source": "Reuters",
                    "published_at_utc": cli.dateutil.parser.isoparse("2026-04-01T13:00:00Z").replace(tzinfo=None),
                    "event_timestamp_utc": cli.dateutil.parser.isoparse("2026-04-01T13:00:00Z").replace(tzinfo=None),
                    "event_timestamp_ny": cli.dateutil.parser.isoparse("2026-04-01T09:00:00Z").replace(tzinfo=None),
                    "effective_trade_date": cli.dateutil.parser.isoparse("2026-04-01T00:00:00Z").date(),
                    "market_session_tag": "regular",
                    "is_major_event": 0,
                    "company_name": "Microsoft Corp.",
                    "relevance_score": 0.9,
                },
                {
                    "article_id": "alpaca:ctx-3",
                    "symbol": "NVDA",
                    "headline": "Headline 3",
                    "summary": "Summary 3",
                    "content": None,
                    "source": "Reuters",
                    "published_at_utc": cli.dateutil.parser.isoparse("2026-04-01T14:00:00Z").replace(tzinfo=None),
                    "event_timestamp_utc": cli.dateutil.parser.isoparse("2026-04-01T14:00:00Z").replace(tzinfo=None),
                    "event_timestamp_ny": cli.dateutil.parser.isoparse("2026-04-01T10:00:00Z").replace(tzinfo=None),
                    "effective_trade_date": cli.dateutil.parser.isoparse("2026-04-02T00:00:00Z").date(),
                    "market_session_tag": "regular",
                    "is_major_event": 0,
                    "company_name": "NVIDIA Corp.",
                    "relevance_score": 0.9,
                },
            ]
            self.scored_pairs: set[tuple[str, str]] = set()

        def load_candidate_symbols(self):
            return ["AAPL", "MSFT", "NVDA"]

        def load_pending_contextual_pairs(self, limit=None, **kwargs):
            pending = [
                dict(row)
                for row in self.pending_pairs
                if (str(row["article_id"]), str(row["symbol"])) not in self.scored_pairs
            ]
            return pending[: int(limit or len(pending))]

        def count_pending_contextual_pairs(self, **kwargs):
            return sum(
                1
                for row in self.pending_pairs
                if (str(row["article_id"]), str(row["symbol"])) not in self.scored_pairs
            )

        def upsert_news_ticker_sentiment(self, rows):
            for row in rows:
                self.scored_pairs.add((str(row["article_id"]), str(row["symbol"])))
            return len(rows)

    class _DummyConfig:
        finbert_model_name = "dummy"
        finbert_model_version = "1"
        finbert_batch_size = 4
        finbert_max_length = 128
        finbert_model_revision = None
        macro_rule_version = "1"
        initial_backfill_days = 2
        checkpoint_overlap_minutes = 60
        candidate_reactivation_backfill_days = 5
        sentiment_pending_limit = 100
        sentiment_pending_max_batches_per_run = 1
        feature_history_buffer_days = 2
        feature_version = "v1"
        feature_rolling_windows = [3]
        source_name = "alpaca_news"
        provider_name = "alpaca"
        regular_session_maps_to_same_day = True
        scoring_mode = "contextual_only"
        enable_contextual_scoring = True
        contextual_scoring_min_relevance = 0.2
        contextual_scoring_max_pairs_per_run = 2

    class _FakeContextualScorer:
        def adopt_runtime_from(self, finbert) -> None:
            return None

        def score_pairs(self, pairs):
            scored = []
            for article, symbol, _company_name in pairs:
                scored.append(
                    ContextualSentimentRecord(
                        article_id=article.article_id,
                        symbol=symbol,
                        model_name="dummy",
                        model_version="1",
                        text_strategy="contextual_company",
                        text_hash=f"ctx-{symbol.lower()}",
                        truncated=0,
                        max_length_tokens=128,
                        sentiment_label="positive",
                        positive_score=0.9,
                        neutral_score=0.08,
                        negative_score=0.02,
                        sentiment_confidence=0.9,
                        sentiment_net_score=0.88,
                        scoring_version="contextual_v1",
                    )
                )
            return scored

    progress_payloads: list[dict[str, object]] = []
    pipeline_instance = cli.EventSentimentPipeline(
        repository=_DummyRepository(),
        config=_DummyConfig(),
        progress_callback=progress_payloads.append,
    )
    monkeypatch.setattr(
        pipeline_instance,
        "_ensure_contextual_scorer",
        lambda: _FakeContextualScorer(),
    )

    stats = pipeline_instance.run(
        start_utc=cli.dateutil.parser.isoparse("2026-04-01T00:00:00Z"),
        end_utc=cli.dateutil.parser.isoparse("2026-04-03T00:00:00Z"),
        symbols=["AAPL", "MSFT", "NVDA"],
        skip_ingestion=True,
        skip_features=True,
    )

    contextual_payloads = [
        payload for payload in progress_payloads if payload.get("progress_phase") == "contextual_scoring"
    ]
    assert stats["contextual_scored"] == 3
    assert stats["contextual_batches_processed"] == 2
    assert contextual_payloads
    assert contextual_payloads[0]["progress_unit"] == "paires"
    assert any("lot 1/2" in str(payload.get("progress_label")) for payload in contextual_payloads)
    assert any("lot 2/2" in str(payload.get("progress_label")) for payload in contextual_payloads)
    assert any(payload.get("progress_current") == 2 and payload.get("progress_total") == 3 for payload in contextual_payloads)
    assert contextual_payloads[-1]["progress_current"] == 3
    assert contextual_payloads[-1]["contextual_pairs_remaining"] == 0


def test_signal_aggregator_main_emits_structured_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(signal_aggregator, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(db_connection, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(
        signal_aggregator,
        "_load_scores_from_db",
        lambda engine, all_symbols: pd.DataFrame(
            [
                {"symbol": "AAPL", "sector": "Tech", "final_score": 0.75},
                {"symbol": "MSFT", "sector": "Tech", "final_score": 0.62},
            ]
        ),
    )
    monkeypatch.setattr(signal_aggregator, "SentimentSignalAggregator", _FakeSignalAggregator)

    result = signal_aggregator.main(
        [
            "--trade-date",
            "2026-04-19",
            "--all-symbols",
            "--allow-rerun",
            "--sentiment-weight",
            "0.2",
            "--macro-weight",
            "0.1",
            "--lookback-days",
            "7",
            "--min-news-count",
            "3",
            "--time-decay-half-life-days",
            "1.5",
            "--log-level",
            "DEBUG",
        ]
    )

    payloads = _payloads_from_output(capsys.readouterr().out.strip(), signal_aggregator.RUN_SUMMARY_PREFIX)
    progress_payloads = [payload for payload in payloads if payload.get("progress_live")]
    payload = next(payload for payload in reversed(payloads) if not payload.get("progress_live"))
    assert result == 0
    assert progress_payloads
    assert any(progress.get("progress_phase") == "load_scores" for progress in progress_payloads)
    assert any(progress.get("progress_phase") == "finalize" for progress in progress_payloads)
    assert payload["trade_date"] == "2026-04-19"
    assert payload["all_symbols"] is True
    assert payload["loaded_symbols"] == 2
    assert payload["updated_symbols"] == 2
    assert payload["signal_active_symbols"] == 1
    assert payload["total_news"] == 6
    assert payload["avg_final_score_sentiment"] == 0.73
    assert payload["max_final_score_sentiment"] == 0.82

