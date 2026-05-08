import pandas as pd
import pytest
from event_sentiment.aggregation import build_sector_daily_features, build_ticker_daily_features


def test_ticker_aggregation_basic() -> None:
    ticker_df = pd.DataFrame([
        {
            "article_id": "a1",
            "effective_trade_date": "2026-01-02",
            "event_timestamp_ny": "2026-01-01 17:00:00",
            "market_session_tag": "post_market",
            "source": "Reuters",
            "is_major_event": 1,
            "symbol": "AAPL",
            "sector": "Technology",
            "sentiment_label": "positive",
            "positive_score": 0.9,
            "neutral_score": 0.08,
            "negative_score": 0.02,
            "sentiment_confidence": 0.9,
            "sentiment_net_score": 0.88,
        }
    ])
    result = build_ticker_daily_features(ticker_df)
    assert result.loc[0, "symbol"] == "AAPL"
    assert result.loc[0, "news_count_1d"] == 1
    assert result.loc[0, "after_close_news_count"] == 1


def test_sector_aggregation_deduplicates_same_article_same_sector() -> None:
    sector_df = pd.DataFrame([
        {
            "article_id": "a1",
            "effective_trade_date": "2026-01-02",
            "event_timestamp_ny": "2026-01-01 17:00:00",
            "market_session_tag": "post_market",
            "source": "Reuters",
            "is_major_event": 1,
            "sector": "Technology",
            "sentiment_label": "positive",
            "sentiment_confidence": 0.9,
            "sentiment_net_score": 0.88,
        },
        {
            "article_id": "a1",
            "effective_trade_date": "2026-01-02",
            "event_timestamp_ny": "2026-01-01 17:00:00",
            "market_session_tag": "post_market",
            "source": "Reuters",
            "is_major_event": 1,
            "sector": "Technology",
            "sentiment_label": "positive",
            "sentiment_confidence": 0.9,
            "sentiment_net_score": 0.88,
        },
    ])
    macro_df = pd.DataFrame([
        {
            "article_id": "a1",
            "trade_date": "2026-01-02",
            "sector": "Technology",
            "macro_event_type": "monetary_policy",
            "impact_direction": "positive",
            "impact_score": 0.4,
            "macro_event_intensity": 0.4,
        }
    ])
    result = build_sector_daily_features(sector_df, macro_df)
    assert result.loc[0, "sector_news_count_1d"] == 1
    assert result.loc[0, "macro_event_flag"] == 1


def test_ticker_aggregation_builds_multi_horizon_windows() -> None:
    ticker_df = pd.DataFrame([
        {
            "article_id": "a1",
            "effective_trade_date": "2026-01-02",
            "event_timestamp_ny": "2026-01-02 10:00:00",
            "market_session_tag": "regular",
            "source": "Reuters",
            "is_major_event": 0,
            "symbol": "AAPL",
            "sector": "Technology",
            "positive_score": 0.7,
            "neutral_score": 0.2,
            "negative_score": 0.1,
            "sentiment_confidence": 0.8,
            "sentiment_net_score": 0.6,
        },
        {
            "article_id": "a2",
            "effective_trade_date": "2026-01-03",
            "event_timestamp_ny": "2026-01-03 10:00:00",
            "market_session_tag": "regular",
            "source": "Reuters",
            "is_major_event": 1,
            "symbol": "AAPL",
            "sector": "Technology",
            "positive_score": 0.8,
            "neutral_score": 0.1,
            "negative_score": 0.1,
            "sentiment_confidence": 0.9,
            "sentiment_net_score": 0.8,
        },
    ])

    result = build_ticker_daily_features(ticker_df)

    last_row = result.iloc[-1]
    assert last_row["news_count_3d"] == 2
    assert last_row["sentiment_net_sum_3d"] == 1.4
    assert last_row["sentiment_net_mean_3d"] == 0.7
    assert last_row["major_event_day_count_3d"] == 1


def test_sector_aggregation_builds_multi_horizon_windows() -> None:
    sector_df = pd.DataFrame([
        {
            "article_id": "a1",
            "effective_trade_date": "2026-01-02",
            "event_timestamp_ny": "2026-01-02 10:00:00",
            "market_session_tag": "regular",
            "source": "Reuters",
            "is_major_event": 0,
            "sector": "Technology",
            "sentiment_label": "positive",
            "sentiment_confidence": 0.8,
            "sentiment_net_score": 0.6,
        },
        {
            "article_id": "a2",
            "effective_trade_date": "2026-01-03",
            "event_timestamp_ny": "2026-01-03 10:00:00",
            "market_session_tag": "regular",
            "source": "Reuters",
            "is_major_event": 1,
            "sector": "Technology",
            "sentiment_label": "negative",
            "sentiment_confidence": 0.9,
            "sentiment_net_score": -0.2,
        },
    ])
    macro_df = pd.DataFrame([
        {
            "article_id": "a2",
            "trade_date": "2026-01-03",
            "sector": "Technology",
            "macro_event_type": "monetary_policy",
            "impact_direction": "positive",
            "impact_score": 0.4,
            "macro_event_intensity": 0.4,
        }
    ])

    result = build_sector_daily_features(sector_df, macro_df)

    last_row = result.iloc[-1]
    assert last_row["sector_news_count_3d"] == 2
    assert last_row["sector_sentiment_net_sum_3d"] == pytest.approx(0.4, rel=1e-9)
    assert last_row["sector_sentiment_net_mean_3d"] == pytest.approx(0.2, rel=1e-9)
    assert last_row["sector_impact_score_3d"] == pytest.approx(0.2, rel=1e-9)
    assert last_row["macro_event_day_count_3d"] == 1


def test_ticker_aggregation_uses_relevance_score_as_weight() -> None:
    """Niveau 2/3 : moyenne pondérée par ``relevance_score``."""
    ticker_df = pd.DataFrame([
        {
            "article_id": "a1",
            "effective_trade_date": "2026-01-02",
            "event_timestamp_ny": "2026-01-02 10:00:00",
            "market_session_tag": "regular",
            "source": "Reuters",
            "is_major_event": 0,
            "symbol": "AAPL",
            "sector": "Technology",
            "relevance_score": 0.9,
            "positive_score": 0.7,
            "neutral_score": 0.2,
            "negative_score": 0.1,
            "sentiment_confidence": 0.8,
            "sentiment_net_score": 1.0,
        },
        {
            "article_id": "a2",
            "effective_trade_date": "2026-01-02",
            "event_timestamp_ny": "2026-01-02 11:00:00",
            "market_session_tag": "regular",
            "source": "Reuters",
            "is_major_event": 0,
            "symbol": "AAPL",
            "sector": "Technology",
            "relevance_score": 0.1,
            "positive_score": 0.1,
            "neutral_score": 0.2,
            "negative_score": 0.7,
            "sentiment_confidence": 0.8,
            "sentiment_net_score": -1.0,
        },
    ])

    result = build_ticker_daily_features(ticker_df)

    row = result.iloc[0]
    # Moyenne pondérée : (1.0 * 0.9 + (-1.0) * 0.1) / (0.9 + 0.1) = 0.8
    assert row["sentiment_net_mean_1d"] == pytest.approx(0.8, rel=1e-6)
    # Compte d'articles brut conservé
    assert row["news_count_1d"] == 2
    # Somme pondérée
    assert row["sentiment_net_sum_1d"] == pytest.approx(0.8, rel=1e-6)
    # Poids cumulé
    assert row["relevance_weight_sum_1d"] == pytest.approx(1.0, rel=1e-6)


def test_ticker_aggregation_backward_compatible_without_relevance_column() -> None:
    """Rétro-compat : pas de colonne ``relevance_score`` ⇒ moyenne arithmétique."""
    ticker_df = pd.DataFrame([
        {
            "article_id": "a1",
            "effective_trade_date": "2026-01-02",
            "event_timestamp_ny": "2026-01-02 10:00:00",
            "market_session_tag": "regular",
            "source": "Reuters",
            "is_major_event": 0,
            "symbol": "AAPL",
            "sector": "Technology",
            "positive_score": 0.7,
            "neutral_score": 0.2,
            "negative_score": 0.1,
            "sentiment_confidence": 0.8,
            "sentiment_net_score": 1.0,
        },
        {
            "article_id": "a2",
            "effective_trade_date": "2026-01-02",
            "event_timestamp_ny": "2026-01-02 11:00:00",
            "market_session_tag": "regular",
            "source": "Reuters",
            "is_major_event": 0,
            "symbol": "AAPL",
            "sector": "Technology",
            "positive_score": 0.1,
            "neutral_score": 0.2,
            "negative_score": 0.7,
            "sentiment_confidence": 0.8,
            "sentiment_net_score": -1.0,
        },
    ])

    result = build_ticker_daily_features(ticker_df)
    row = result.iloc[0]
    # Sans poids, moyenne classique = 0.0
    assert row["sentiment_net_mean_1d"] == pytest.approx(0.0, abs=1e-6)
    assert row["news_count_1d"] == 2
    assert row["relevance_weight_sum_1d"] == pytest.approx(2.0, rel=1e-6)
