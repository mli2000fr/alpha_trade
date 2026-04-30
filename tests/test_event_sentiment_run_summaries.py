from __future__ import annotations

import json
import sys

import pandas as pd

from database import connection as db_connection
from event_sentiment import cli, signal_aggregator


def _payload_from_stdout(stdout: str, prefix: str) -> dict[str, object]:
    assert stdout.startswith(prefix)
    return json.loads(stdout[len(prefix):])


class _FakeEventSentimentPipeline:
    def __init__(self, repository=None, config=None) -> None:
        self.repository = repository
        self.config = config

    def run(self, start_utc=None, end_utc=None, symbols=None) -> dict[str, object]:
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
    monkeypatch.setattr(cli, "EventSentimentConfig", lambda: object())
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

    payload = _payload_from_stdout(capsys.readouterr().out.strip(), cli.RUN_SUMMARY_PREFIX)
    assert payload["resolved_symbols"] == 2
    assert payload["fetched_articles"] == 24
    assert payload["landed_articles"] == 18
    assert payload["sentiment_inferred"] == 17
    assert payload["ticker_day_rows"] == 6
    assert payload["sector_day_rows"] == 2


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

    stdout = capsys.readouterr().out.strip().splitlines()
    payload = _payload_from_stdout(stdout[0], signal_aggregator.RUN_SUMMARY_PREFIX)
    assert result == 0
    assert payload["trade_date"] == "2026-04-19"
    assert payload["all_symbols"] is True
    assert payload["loaded_symbols"] == 2
    assert payload["updated_symbols"] == 2
    assert payload["signal_active_symbols"] == 1
    assert payload["total_news"] == 6
    assert payload["avg_final_score_sentiment"] == 0.73
    assert payload["max_final_score_sentiment"] == 0.82

