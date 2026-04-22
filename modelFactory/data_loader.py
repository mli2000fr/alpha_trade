"""modelFactory/data_loader.py — Chargement des bars depuis stock_bars_daily."""
from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)


def load_symbol_bars(engine: Engine, symbol: str, end_date: date | None = None) -> pd.DataFrame:
    """Charge l'historique complet d'un symbole depuis stock_bars_daily.

    Retourne un DataFrame trié par date avec colonnes :
    symbol, date, open, high, low, close, volume, adj_close, vwap, daily_return, is_filled
    """
    where_clause = "WHERE symbol = :sym"
    params: dict[str, object] = {"sym": symbol}
    if end_date is not None:
        where_clause += " AND `date` <= :end_date"
        params["end_date"] = end_date
    query = text(
        "SELECT symbol, `date`, `open`, high, low, `close`, volume, adj_close, vwap, daily_return, is_filled "
        f"FROM stock_bars_daily {where_clause} ORDER BY `date`"
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params, parse_dates=["date"])
    LOGGER.info("load_symbol_bars symbol=%s rows=%d", symbol, len(df))
    return df


def load_benchmark_bars(engine: Engine, benchmark_symbol: str = "SPY", end_date: date | None = None) -> pd.DataFrame:
    """Charge les barres du benchmark marché utilisé pour les features contextuelles."""
    df = load_symbol_bars(engine, benchmark_symbol, end_date=end_date)
    LOGGER.info("load_benchmark_bars benchmark_symbol=%s rows=%d", benchmark_symbol, len(df))
    return df


def load_symbol_sentiment(engine: Engine, symbol: str, end_date: date | None = None) -> pd.DataFrame:
    """Charge les features sentiment quotidiennes depuis ticker_daily_sentiment_features.

    Retourne un DataFrame avec colonnes :
    symbol, trade_date, news_count_1d, sentiment_net_mean_1d, sentiment_confidence_mean_1d, major_event_flag
    """
    where_clause = "WHERE symbol = :sym"
    params: dict[str, object] = {"sym": symbol}
    if end_date is not None:
        where_clause += " AND trade_date <= :end_date"
        params["end_date"] = end_date
    query = text(
        "SELECT symbol, trade_date, news_count_1d, sentiment_net_mean_1d, "
        "sentiment_confidence_mean_1d, major_event_flag "
        f"FROM ticker_daily_sentiment_features {where_clause} ORDER BY trade_date"
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params, parse_dates=["trade_date"])
    LOGGER.info("load_symbol_sentiment symbol=%s rows=%d", symbol, len(df))
    return df


