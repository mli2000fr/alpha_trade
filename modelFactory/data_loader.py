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


def load_universe_bars(
    engine: Engine,
    symbols: list[str] | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """Charge un panel historique minimal de l'univers pour les features cross-sectionnelles."""
    where_clauses: list[str] = []
    params: dict[str, object] = {}
    if symbols:
        symbol_params = []
        for idx, symbol in enumerate(symbols):
            key = f"sym_{idx}"
            params[key] = symbol
            symbol_params.append(f":{key}")
        where_clauses.append(f"symbol IN ({', '.join(symbol_params)})")
    if end_date is not None:
        where_clauses.append("`date` <= :end_date")
        params["end_date"] = end_date
    where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    query = text(
        "SELECT symbol, `date`, `open`, high, low, `close`, volume, adj_close, vwap, daily_return, is_filled "
        f"FROM stock_bars_daily {where_clause} ORDER BY symbol, `date`"
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params, parse_dates=["date"])
    LOGGER.info("load_universe_bars symbols=%s rows=%d", len(symbols) if symbols else "ALL", len(df))
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


def load_symbols_sentiment(
    engine: Engine,
    symbols: list[str],
    end_date: date | None = None,
) -> pd.DataFrame:
    """Charge les features sentiment pour une liste de symboles."""
    if not symbols:
        return pd.DataFrame(columns=["symbol", "trade_date", "news_count_1d", "sentiment_net_mean_1d", "sentiment_confidence_mean_1d", "major_event_flag"])
    symbol_params = []
    params: dict[str, object] = {}
    for idx, symbol in enumerate(symbols):
        key = f"sym_{idx}"
        params[key] = symbol
        symbol_params.append(f":{key}")
    where_clause = f"WHERE symbol IN ({', '.join(symbol_params)})"
    if end_date is not None:
        where_clause += " AND trade_date <= :end_date"
        params["end_date"] = end_date
    query = text(
        "SELECT symbol, trade_date, news_count_1d, sentiment_net_mean_1d, "
        "sentiment_confidence_mean_1d, major_event_flag "
        f"FROM ticker_daily_sentiment_features {where_clause} ORDER BY symbol, trade_date"
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params, parse_dates=["trade_date"])
    LOGGER.info("load_symbols_sentiment symbols=%d rows=%d", len(symbols), len(df))
    return df


