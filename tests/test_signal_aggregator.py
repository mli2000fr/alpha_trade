from datetime import date
from typing import cast
import warnings

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from event_sentiment import signal_aggregator
from event_sentiment.signal_aggregator import SentimentBoostConfig, SentimentSignalAggregator


def test_signal_aggregator_main_rejects_invalid_weight_sum(monkeypatch) -> None:
    monkeypatch.setattr(signal_aggregator, "configure_root_logging", lambda **_: None)

    result = signal_aggregator.main(["--sentiment-weight", "0.8", "--macro-weight", "0.3"])

    assert result == 1


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

    by_symbol = {
        str(row["symbol"]): row
        for row in result.to_dict(orient="records")
    }
    assert bool(by_symbol["AAPL"]["signal_active"]) is True
    assert bool(by_symbol["MSFT"]["signal_active"]) is False
    assert by_symbol["MSFT"]["sentiment_net_agg"] == 0.0
    assert by_symbol["AAPL"]["sentiment_signal_norm"] == pytest.approx(0.8, rel=1e-6)
    assert by_symbol["AAPL"]["macro_signal_norm"] == pytest.approx(0.6, rel=1e-6)
    assert by_symbol["MSFT"]["macro_signal_norm"] == pytest.approx(0.6, rel=1e-6)
    assert by_symbol["MSFT"]["final_score_sentiment"] == pytest.approx(0.585, rel=1e-6)


def test_normalize_to_01_returns_neutral_value_for_constant_series() -> None:
    series = pd.Series([7.0, 7.0, 7.0])

    normalized = SentimentSignalAggregator._normalize_to_01(series)

    assert normalized.tolist() == [0.5, 0.5, 0.5]


def test_normalize_signed_signal_maps_neutral_and_clips_extremes() -> None:
    series = pd.Series([-2.0, -1.0, 0.0, 0.25, 1.0, 4.0, None])

    normalized = SentimentSignalAggregator._normalize_signed_signal(series)

    assert normalized.tolist() == [0.0, 0.0, 0.5, 0.625, 1.0, 1.0, 0.5]


def test_save_to_db_updates_existing_rows_and_casts_boolean_flags() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE stock_scores (
                symbol TEXT PRIMARY KEY,
                sentiment_net_agg REAL,
                sector_impact_agg REAL,
                sentiment_signal_norm REAL,
                macro_signal_norm REAL,
                final_score_sentiment REAL,
                signal_active INTEGER,
                major_event_flag_agg INTEGER,
                macro_event_flag_agg INTEGER,
                total_news INTEGER,
                last_updated_sentiment TIMESTAMP
            )
            """
        ))
        conn.execute(text("INSERT INTO stock_scores (symbol) VALUES ('AAPL'), ('MSFT')"))

    aggregator = SentimentSignalAggregator(engine=engine)
    enriched_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "sentiment_net_agg": 0.8,
                "sector_impact_agg": 0.3,
                "sentiment_signal_norm": 0.9,
                "macro_signal_norm": 0.7,
                "final_score_sentiment": 0.81,
                "signal_active": True,
                "major_event_flag_agg": True,
                "macro_event_flag_agg": False,
                "total_news": 4,
            },
            {
                "symbol": "MSFT",
                "sentiment_net_agg": 0.0,
                "sector_impact_agg": -0.1,
                "sentiment_signal_norm": 0.5,
                "macro_signal_norm": 0.4,
                "final_score_sentiment": 0.62,
                "signal_active": False,
                "major_event_flag_agg": False,
                "macro_event_flag_agg": True,
                "total_news": 0,
            },
        ]
    )

    updated = aggregator.save_to_db(enriched_df)

    assert updated == 2
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT symbol, signal_active, major_event_flag_agg, macro_event_flag_agg, total_news, final_score_sentiment "
                "FROM stock_scores ORDER BY symbol"
            )
        ).mappings().all()

    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["AAPL"]["signal_active"] == 1
    assert by_symbol["AAPL"]["major_event_flag_agg"] == 1
    assert by_symbol["AAPL"]["macro_event_flag_agg"] == 0
    assert by_symbol["MSFT"]["signal_active"] == 0
    assert by_symbol["MSFT"]["macro_event_flag_agg"] == 1
    assert by_symbol["MSFT"]["total_news"] == 0
    assert by_symbol["AAPL"]["final_score_sentiment"] == pytest.approx(0.81)


def test_save_to_db_rejects_missing_required_columns() -> None:
    aggregator = SentimentSignalAggregator(engine=cast(Engine, object()))

    with pytest.raises(ValueError, match="colonnes manquantes"):
        aggregator.save_to_db(pd.DataFrame([{"symbol": "AAPL"}]))


def test_merge_sanitizes_symbols_scores_and_missing_sectors(monkeypatch) -> None:
    aggregator = SentimentSignalAggregator(
        engine=cast(Engine, object()),
        config=SentimentBoostConfig(),
    )

    scores_df = pd.DataFrame(
        [
            {"symbol": " AAPL ", "sector": " TECH ", "final_score": 1.4},
            {"symbol": None, "sector": "TECH", "final_score": 0.8},
            {"symbol": "MSFT", "sector": None, "final_score": "bad"},
        ]
    )

    ticker_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "trade_date": date(2026, 4, 19),
                "news_count_1d": 2,
                "sentiment_net_mean_1d": 1.8,
                "sentiment_confidence_mean_1d": 0.9,
                "major_event_flag": 1,
            },
        ]
    )
    sector_df = pd.DataFrame(
        [
            {
                "sector": "TECH",
                "trade_date": date(2026, 4, 19),
                "sector_impact_score": -3.0,
                "macro_event_intensity": 1.0,
                "macro_event_flag": 1,
            },
        ]
    )

    monkeypatch.setattr(aggregator, "_load_ticker_sentiment", lambda symbols, trade_date: ticker_df.copy())
    monkeypatch.setattr(aggregator, "_load_sector_sentiment", lambda sectors, trade_date: sector_df.copy())

    result = aggregator.merge(scores_df, trade_date=date(2026, 4, 19))

    assert result["symbol"].tolist() == ["AAPL", "MSFT"]
    by_symbol = {row["symbol"]: row for row in result.to_dict(orient="records")}
    assert by_symbol["AAPL"]["final_score"] == 1.0
    assert by_symbol["AAPL"]["sentiment_signal_norm"] == 1.0
    assert by_symbol["AAPL"]["macro_signal_norm"] == 0.0
    assert by_symbol["MSFT"]["final_score"] == 0.0
    assert by_symbol["MSFT"]["sector_impact_agg"] == 0.0
    assert by_symbol["MSFT"]["macro_signal_norm"] == 0.5


