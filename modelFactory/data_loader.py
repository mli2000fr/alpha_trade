"""modelFactory/data_loader.py — Chargement des bars depuis stock_bars_daily."""
from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)


def load_symbol_bars(engine: Engine, symbol: str) -> pd.DataFrame:
    """Charge l'historique complet d'un symbole depuis stock_bars_daily.

    Retourne un DataFrame trié par date avec colonnes :
    symbol, date, open, high, low, close, volume, adj_close, vwap, daily_return, is_filled
    """
    query = text(
        "SELECT symbol, `date`, `open`, high, low, `close`, volume, adj_close, vwap, daily_return, is_filled "
        "FROM stock_bars_daily WHERE symbol = :sym ORDER BY `date`"
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"sym": symbol}, parse_dates=["date"])
    LOGGER.info("load_symbol_bars symbol=%s rows=%d", symbol, len(df))
    return df

