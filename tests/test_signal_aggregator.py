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


def test_sentiment_boost_config_rejects_unsorted_horizon_weights() -> None:
    with pytest.raises(ValueError, match="ticker_horizon_weights"):
        SentimentBoostConfig(ticker_horizon_weights=((5, 0.5), (1, 0.5)))


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
    assert by_symbol["AAPL"]["company_idio_signal_norm"] == pytest.approx(0.8, rel=1e-6)
    assert by_symbol["AAPL"]["macro_regime_signal_norm"] == pytest.approx(0.6, rel=1e-6)
    assert by_symbol["AAPL"]["company_idio_component"] == pytest.approx(0.12, rel=1e-6)
    assert by_symbol["AAPL"]["macro_regime_component"] == pytest.approx(0.06, rel=1e-6)
    assert by_symbol["AAPL"]["quant_component"] == pytest.approx(0.6, rel=1e-6)
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
                company_idio_score REAL,
                macro_regime_score REAL,
                sentiment_signal_norm REAL,
                macro_signal_norm REAL,
                company_idio_signal_norm REAL,
                macro_regime_signal_norm REAL,
                company_idio_component REAL,
                macro_regime_component REAL,
                quant_component REAL,
                final_score_sentiment REAL,
                final_score_walk_forward REAL,
                walk_forward_sentiment_weight REAL,
                walk_forward_macro_weight REAL,
                walk_forward_quant_weight REAL,
                calibration_run_id TEXT,
                calibration_source TEXT,
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
                "company_idio_score": 0.8,
                "macro_regime_score": 0.3,
                "sentiment_signal_norm": 0.9,
                "macro_signal_norm": 0.7,
                "company_idio_signal_norm": 0.9,
                "macro_regime_signal_norm": 0.7,
                "company_idio_component": 0.18,
                "macro_regime_component": 0.07,
                "quant_component": 0.56,
                "final_score_sentiment": 0.81,
                "final_score_walk_forward": 0.83,
                "walk_forward_sentiment_weight": 0.2,
                "walk_forward_macro_weight": 0.1,
                "walk_forward_quant_weight": 0.7,
                "calibration_run_id": "wf-run-1",
                "calibration_source": "walk_forward",
                "signal_active": True,
                "major_event_flag_agg": True,
                "macro_event_flag_agg": False,
                "total_news": 4,
            },
            {
                "symbol": "MSFT",
                "sentiment_net_agg": 0.0,
                "sector_impact_agg": -0.1,
                "company_idio_score": 0.0,
                "macro_regime_score": -0.1,
                "sentiment_signal_norm": 0.5,
                "macro_signal_norm": 0.4,
                "company_idio_signal_norm": 0.5,
                "macro_regime_signal_norm": 0.4,
                "company_idio_component": 0.075,
                "macro_regime_component": 0.04,
                "quant_component": 0.505,
                "final_score_sentiment": 0.62,
                "final_score_walk_forward": 0.61,
                "walk_forward_sentiment_weight": 0.2,
                "walk_forward_macro_weight": 0.1,
                "walk_forward_quant_weight": 0.7,
                "calibration_run_id": "wf-run-1",
                "calibration_source": "walk_forward",
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
                "SELECT symbol, signal_active, major_event_flag_agg, macro_event_flag_agg, total_news, "
                "company_idio_score, macro_regime_score, company_idio_component, macro_regime_component, "
                "quant_component, final_score_sentiment, final_score_walk_forward, calibration_run_id, calibration_source "
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
    assert by_symbol["AAPL"]["company_idio_score"] == pytest.approx(0.8)
    assert by_symbol["AAPL"]["macro_regime_score"] == pytest.approx(0.3)
    assert by_symbol["AAPL"]["company_idio_component"] == pytest.approx(0.18)
    assert by_symbol["AAPL"]["macro_regime_component"] == pytest.approx(0.07)
    assert by_symbol["AAPL"]["quant_component"] == pytest.approx(0.56)
    assert by_symbol["AAPL"]["final_score_sentiment"] == pytest.approx(0.81)
    assert by_symbol["AAPL"]["final_score_walk_forward"] == pytest.approx(0.83)
    assert by_symbol["AAPL"]["calibration_run_id"] == "wf-run-1"
    assert by_symbol["AAPL"]["calibration_source"] == "walk_forward"


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


def test_merge_prefers_multi_horizon_features_when_available(monkeypatch) -> None:
    aggregator = SentimentSignalAggregator(
        engine=cast(Engine, object()),
        config=SentimentBoostConfig(),
    )

    scores_df = pd.DataFrame([
        {"symbol": "AAPL", "sector": "TECH", "final_score": 0.8},
    ])
    ticker_df = pd.DataFrame([
        {
            "symbol": "AAPL",
            "trade_date": date(2026, 4, 19),
            "news_count_1d": 1,
            "news_count_3d": 3,
            "news_count_5d": 5,
            "news_count_10d": 10,
            "news_count_20d": 12,
            "sentiment_net_mean_1d": 1.0,
            "sentiment_net_mean_3d": 0.6,
            "sentiment_net_mean_5d": 0.2,
            "sentiment_net_mean_10d": 0.1,
            "sentiment_net_mean_20d": 0.0,
            "sentiment_confidence_mean_1d": 0.9,
            "sentiment_confidence_mean_3d": 0.8,
            "sentiment_confidence_mean_5d": 0.8,
            "sentiment_confidence_mean_10d": 0.8,
            "sentiment_confidence_mean_20d": 0.8,
            "major_event_flag": 1,
            "major_event_day_count_3d": 1,
            "major_event_day_count_5d": 1,
            "major_event_day_count_10d": 1,
            "major_event_day_count_20d": 1,
        }
    ])
    sector_df = pd.DataFrame([
        {
            "sector": "TECH",
            "trade_date": date(2026, 4, 19),
            "sector_impact_score": 0.2,
            "sector_impact_score_3d": 0.3,
            "sector_impact_score_5d": 0.1,
            "sector_impact_score_10d": 0.0,
            "sector_impact_score_20d": -0.1,
            "macro_event_intensity": 0.4,
            "macro_event_intensity_3d": 0.4,
            "macro_event_intensity_5d": 0.4,
            "macro_event_intensity_10d": 0.4,
            "macro_event_intensity_20d": 0.4,
            "macro_event_flag": 1,
            "macro_event_day_count_3d": 1,
            "macro_event_day_count_5d": 1,
            "macro_event_day_count_10d": 1,
            "macro_event_day_count_20d": 1,
        }
    ])

    monkeypatch.setattr(aggregator, "_load_ticker_sentiment", lambda symbols, trade_date: ticker_df.copy())
    monkeypatch.setattr(aggregator, "_load_sector_sentiment", lambda sectors, trade_date: sector_df.copy())

    result = aggregator.merge(scores_df, trade_date=date(2026, 4, 19))

    row = result.iloc[0]
    assert bool(row["signal_active"]) is True
    assert row["total_news"] == 12
    assert row["sentiment_net_agg"] == pytest.approx(0.4545454545, rel=1e-6)
    assert row["sector_impact_agg"] == pytest.approx(0.17, rel=1e-6)
    assert row["sentiment_signal_norm"] == pytest.approx((0.4545454545 + 1.0) / 2.0, rel=1e-6)


