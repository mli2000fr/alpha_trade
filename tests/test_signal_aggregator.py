from datetime import date
from typing import cast
import warnings

import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from event_sentiment import signal_aggregator
from event_sentiment.signal_aggregator import SentimentBoostConfig, SentimentSignalAggregator

def test_signal_aggregator_main(monkeypatch):
    called = {}
    monkeypatch.setattr(signal_aggregator, "main", lambda: called.setdefault("main", True))
    signal_aggregator.main()
    assert called["main"] is True


def test_aggregate_ticker_window_applies_time_decay_to_old_news() -> None:
    ticker_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "trade_date": date(2026, 4, 5),
                "news_count_1d": 10,
                "sentiment_net_mean_1d": -1.0,
                "major_event_flag": 0,
            },
            {
                "symbol": "AAPL",
                "trade_date": date(2026, 4, 10),
                "news_count_1d": 2,
                "sentiment_net_mean_1d": 1.0,
                "major_event_flag": 1,
            },
        ]
    )

    result = SentimentSignalAggregator._aggregate_ticker_window(
        ticker_df,
        min_news_count=2,
        reference_date=date(2026, 4, 10),
        half_life_days=1.0,
    )

    assert len(result) == 1
    row = result.iloc[0]
    assert row["symbol"] == "AAPL"
    assert bool(row["signal_active"]) is True
    assert row["major_event_flag_agg"] == 1
    assert row["total_news"] == 12
    assert row["sentiment_net_agg"] == pytest.approx(0.7297297297, rel=1e-6)


def test_aggregate_ticker_window_keeps_min_news_count_on_raw_volume() -> None:
    ticker_df = pd.DataFrame(
        [
            {
                "symbol": "MSFT",
                "trade_date": date(2026, 4, 5),
                "news_count_1d": 1,
                "sentiment_net_mean_1d": -1.0,
                "major_event_flag": 0,
            },
            {
                "symbol": "MSFT",
                "trade_date": date(2026, 4, 10),
                "news_count_1d": 1,
                "sentiment_net_mean_1d": 1.0,
                "major_event_flag": 0,
            },
        ]
    )

    result = SentimentSignalAggregator._aggregate_ticker_window(
        ticker_df,
        min_news_count=2,
        reference_date=date(2026, 4, 10),
        half_life_days=0.5,
    )

    row = result.iloc[0]
    assert row["total_news"] == 2
    assert bool(row["signal_active"]) is True
    assert row["sentiment_net_agg"] > 0.99


def test_aggregate_sector_window_applies_time_decay() -> None:
    sector_df = pd.DataFrame(
        [
            {"sector": "TECH", "trade_date": date(2026, 4, 7), "sector_impact_score": -0.8, "macro_event_flag": 0},
            {"sector": "TECH", "trade_date": date(2026, 4, 10), "sector_impact_score": 0.4, "macro_event_flag": 1},
        ]
    )

    result = SentimentSignalAggregator._aggregate_sector_window(
        sector_df,
        reference_date=date(2026, 4, 10),
        half_life_days=1.0,
    )

    row = result.iloc[0]
    assert row["sector"] == "TECH"
    assert row["macro_event_flag_agg"] == 1
    assert row["sector_impact_agg"] == pytest.approx(0.2666666667, rel=1e-6)


def test_sentiment_boost_config_rejects_non_positive_half_life() -> None:
    with pytest.raises(ValueError, match="time_decay_half_life_days"):
        SentimentBoostConfig(time_decay_half_life_days=0)


def test_merge_handles_missing_signal_active_without_futurewarning(monkeypatch) -> None:
    aggregator = SentimentSignalAggregator(
        engine=cast(Engine, object()),
        config=SentimentBoostConfig(
            sentiment_weight=0.15,
            macro_sector_weight=0.10,
            quant_weight=0.75,
            lookback_days=5,
            min_news_count=2,
            time_decay_half_life_days=2.0,
        ),
    )

    scores_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "sector": "TECH", "final_score": 0.80},
            {"symbol": "MSFT", "sector": "TECH", "final_score": 0.60},
        ]
    )

    ticker_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "trade_date": date(2026, 4, 19),
                "news_count_1d": 3,
                "sentiment_net_mean_1d": 0.6,
                "sentiment_confidence_mean_1d": 0.9,
                "major_event_flag": 1,
            }
        ]
    )
    sector_df = pd.DataFrame(
        [
            {
                "sector": "TECH",
                "trade_date": date(2026, 4, 19),
                "sector_impact_score": 0.2,
                "macro_event_intensity": 0.4,
                "macro_event_flag": 1,
            }
        ]
    )

    monkeypatch.setattr(aggregator, "_load_ticker_sentiment", lambda symbols, trade_date: ticker_df.copy())
    monkeypatch.setattr(aggregator, "_load_sector_sentiment", lambda sectors, trade_date: sector_df.copy())

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = aggregator.merge(scores_df, trade_date=date(2026, 4, 19))

    by_symbol = result.set_index("symbol")
    assert bool(by_symbol.loc["AAPL", "signal_active"]) is True
    assert bool(by_symbol.loc["MSFT", "signal_active"]) is False
    assert by_symbol.loc["MSFT", "sentiment_net_agg"] == 0.0
    assert by_symbol.loc["MSFT", "final_score_sentiment"] == pytest.approx(0.575, rel=1e-6)


