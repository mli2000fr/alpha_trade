from __future__ import annotations

import json
import sys

import pandas as pd

from database import connection as db_connection
from event_sentiment import cli, signal_aggregator


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

