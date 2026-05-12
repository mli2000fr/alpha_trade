"""Provider DB de sentiment agrégé pour le circuit breaker market-aware.

Le but est de brancher un vrai ``sentiment_score_provider`` dans le flux live
et l'IHM, sans coupler ``service.market`` au pipeline d'agrégation lui-même.

Source principale : ``ticker_daily_sentiment_features``
Fallback : ``sector_daily_sentiment_features``

Le score retourné reste dans l'échelle historique ``[-1, 1]`` et correspond à
une moyenne pondérée par le volume de news quotidien sur la fenêtre demandée.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MarketSentimentReading:
    score: float | None
    source: str | None
    lookback_days: int
    total_news_count: int = 0
    row_count: int = 0
    covered_days: int = 0
    latest_trade_date: date | None = None
    data_quality: str = "missing"

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "source": self.source,
            "lookback_days": self.lookback_days,
            "total_news_count": self.total_news_count,
            "row_count": self.row_count,
            "covered_days": self.covered_days,
            "latest_trade_date": self.latest_trade_date.isoformat() if self.latest_trade_date else None,
            "data_quality": self.data_quality,
        }


def _normalize_trade_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _query_market_sentiment(
    engine: Engine,
    *,
    trade_date: date,
    lookback_days: int,
    table_name: str,
    news_col: str,
    sentiment_col: str,
) -> MarketSentimentReading:
    start_date = trade_date - timedelta(days=max(int(lookback_days) - 1, 0))
    stmt = text(
        f"""
        SELECT
            MAX(trade_date) AS latest_trade_date,
            COUNT(*) AS row_count,
            COUNT(DISTINCT trade_date) AS covered_days,
            SUM(COALESCE({news_col}, 0)) AS total_news_count,
            SUM(
                CASE
                    WHEN {sentiment_col} IS NOT NULL THEN COALESCE({news_col}, 0) * {sentiment_col}
                    ELSE 0
                END
            ) AS weighted_sum,
            SUM(
                CASE
                    WHEN {sentiment_col} IS NOT NULL AND COALESCE({news_col}, 0) > 0 THEN COALESCE({news_col}, 0)
                    ELSE 0
                END
            ) AS total_weight
        FROM {table_name}
        WHERE trade_date >= :start_date
          AND trade_date <= :trade_date
        """
    )
    with engine.connect() as conn:
        row = conn.execute(stmt, {"start_date": start_date, "trade_date": trade_date}).mappings().first()
    if not row:
        return MarketSentimentReading(
            score=None,
            source=table_name,
            lookback_days=lookback_days,
            data_quality="missing",
        )
    total_weight = float(row.get("total_weight") or 0.0)
    if total_weight <= 0:
        return MarketSentimentReading(
            score=None,
            source=table_name,
            lookback_days=lookback_days,
            total_news_count=int(row.get("total_news_count") or 0),
            row_count=int(row.get("row_count") or 0),
            covered_days=int(row.get("covered_days") or 0),
            latest_trade_date=_normalize_trade_date(row.get("latest_trade_date")),
            data_quality="missing",
        )
    score = float(row.get("weighted_sum") or 0.0) / total_weight
    score = max(-1.0, min(score, 1.0))
    return MarketSentimentReading(
        score=score,
        source=table_name,
        lookback_days=lookback_days,
        total_news_count=int(row.get("total_news_count") or 0),
        row_count=int(row.get("row_count") or 0),
        covered_days=int(row.get("covered_days") or 0),
        latest_trade_date=_normalize_trade_date(row.get("latest_trade_date")),
        data_quality="ok",
    )


def load_market_sentiment_reading(
    trade_date: date,
    lookback_days: int,
    *,
    engine: Engine | None = None,
) -> MarketSentimentReading:
    """Charge le sentiment agrégé marché sur ``lookback_days`` jours.

    Politique de fallback :
    1. ``ticker_daily_sentiment_features`` (plus proche du breadth marché)
    2. ``sector_daily_sentiment_features``
    """
    resolved_engine = engine
    if resolved_engine is None:
        try:
            from database.connection import get_sqlalchemy_engine

            resolved_engine = get_sqlalchemy_engine()
        except Exception:
            LOGGER.debug("Engine SQLAlchemy indisponible pour le provider sentiment.", exc_info=True)
            return MarketSentimentReading(
                score=None,
                source=None,
                lookback_days=lookback_days,
                data_quality="no_engine",
            )

    attempts = (
        ("ticker_daily_sentiment_features", "news_count_1d", "sentiment_net_mean_1d"),
        ("sector_daily_sentiment_features", "sector_news_count_1d", "sector_sentiment_net_mean_1d"),
    )
    fallback_reading: MarketSentimentReading | None = None
    for table_name, news_col, sentiment_col in attempts:
        try:
            reading = _query_market_sentiment(
                resolved_engine,
                trade_date=trade_date,
                lookback_days=lookback_days,
                table_name=table_name,
                news_col=news_col,
                sentiment_col=sentiment_col,
            )
        except Exception:
            LOGGER.debug("Lecture sentiment impossible depuis %s.", table_name, exc_info=True)
            fallback_reading = MarketSentimentReading(
                score=None,
                source=table_name,
                lookback_days=lookback_days,
                data_quality="query_error",
            )
            continue
        if reading.score is not None:
            return reading
        fallback_reading = reading
    return fallback_reading or MarketSentimentReading(
        score=None,
        source=None,
        lookback_days=lookback_days,
        data_quality="missing",
    )


class DbSentimentScoreProvider:
    """Callable compatible ``sentiment_score_provider`` avec cache local."""

    def __init__(self, trade_date: date, *, engine: Engine | None = None) -> None:
        self.trade_date = trade_date
        self.engine = engine
        self.last_reading: MarketSentimentReading | None = None
        self._cache: dict[int, MarketSentimentReading] = {}

    def __call__(self, lookback_days: int) -> float | None:
        normalized_days = max(int(lookback_days or 1), 1)
        reading = self._cache.get(normalized_days)
        if reading is None:
            reading = load_market_sentiment_reading(
                self.trade_date,
                normalized_days,
                engine=self.engine,
            )
            self._cache[normalized_days] = reading
        self.last_reading = reading
        return reading.score


__all__ = [
    "MarketSentimentReading",
    "DbSentimentScoreProvider",
    "load_market_sentiment_reading",
]
