"""
backtesting/data_loader.py
===========================
Charge les données historiques depuis la base MySQL pour le backtest :
  - OHLCV (stock_bars_daily) : jusqu'à 10 ans
  - Scores quantitatifs (stock_scores) : is_candidate, score, secteur
  - Sentiment ticker (ticker_daily_sentiment_features) : 365 jours de lookback
  - Prédictions ML (model_predictions)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)


def _table_exists(engine: Engine, table_name: str) -> bool:
    """Retourne True si la table existe."""
    try:
        return inspect(engine).has_table(table_name)
    except Exception:
        LOGGER.debug("Impossible d'inspecter la table %s.", table_name, exc_info=True)
        return False


def _get_table_columns(engine: Engine, table_name: str) -> set[str]:
    """Retourne l'ensemble des colonnes d'une table."""
    try:
        return {str(col["name"]) for col in inspect(engine).get_columns(table_name)}
    except Exception:
        LOGGER.debug("Impossible d'inspecter les colonnes de %s.", table_name, exc_info=True)
        return set()


def load_ohlcv(engine: Engine, start: date, end: date) -> pd.DataFrame:
    """Charge les barres OHLCV journalières.

    Returns
    -------
    DataFrame avec colonnes : symbol, trade_date, open, high, low, close, volume
    """
    columns = _get_table_columns(engine, "stock_bars_daily")
    if not columns:
        raise RuntimeError("La table stock_bars_daily est introuvable ou inaccessible.")

    date_col = "trade_date" if "trade_date" in columns else "date" if "date" in columns else None
    if date_col is None:
        raise RuntimeError("Aucune colonne date compatible dans stock_bars_daily (attendu: trade_date ou date).")

    close_expr = "COALESCE(adj_close, `close`)" if "adj_close" in columns else "`close`"
    query = text(f"""
        SELECT symbol,
               `{date_col}` AS trade_date,
               `open` AS open,
               `high` AS high,
               `low` AS low,
               {close_expr} AS `close`,
               volume
        FROM stock_bars_daily
        WHERE `{date_col}` BETWEEN :start AND :end
        ORDER BY `{date_col}`, symbol
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"start": start, "end": end}, parse_dates=["trade_date"])
    LOGGER.info("OHLCV chargé : %d lignes, %d symboles, [%s → %s]",
                len(df), df["symbol"].nunique() if len(df) else 0, start, end)
    return df


def load_scores(engine: Engine, start: date, end: date) -> pd.DataFrame:
    """Charge les scores candidats.

    Priorité :
    1. `stock_scores_history` (point-in-time correct pour le backtest)
    2. `stock_scores` avec fallback sur les horodatages de mise à jour
    """
    history_exists = _table_exists(engine, "stock_scores_history")
    if history_exists:
        history_query = text("""
            SELECT symbol,
                   snapshot_date AS trade_date,
                   final_score,
                   final_score_sentiment,
                   sector,
                   is_candidate
            FROM stock_scores_history
            WHERE snapshot_date BETWEEN :start AND :end
              AND is_candidate = 1
            ORDER BY snapshot_date, symbol
        """)
        with engine.connect() as conn:
            df = pd.read_sql(history_query, conn, params={"start": start, "end": end}, parse_dates=["trade_date"])
        if not df.empty:
            LOGGER.info("Scores candidats chargés depuis stock_scores_history : %d lignes", len(df))
            return df
        LOGGER.warning(
            "stock_scores_history existe mais aucune ligne n'a ete trouvee sur [%s → %s] — fallback sur stock_scores.",
            start,
            end,
        )

    LOGGER.warning(
        "Lecture des scores depuis stock_scores (snapshot courant). "
        "Le backtest ne sera pas strictement point-in-time."
    )
    query = text("""
        SELECT symbol,
               DATE(COALESCE(last_updated_sentiment, last_updated_scan, last_updated_score)) AS trade_date,
               final_score,
               final_score_sentiment,
               sector,
               is_candidate
        FROM stock_scores
        WHERE DATE(COALESCE(last_updated_sentiment, last_updated_scan, last_updated_score)) BETWEEN :start AND :end
          AND is_candidate = 1
        ORDER BY trade_date, symbol
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"start": start, "end": end}, parse_dates=["trade_date"])
    LOGGER.info("Scores candidats chargés : %d lignes", len(df))
    return df


def load_sentiment(engine: Engine, start: date, end: date, lookback_days: int = 365) -> pd.DataFrame:
    """Charge les features sentiment ticker avec lookback étendu (365j par défaut)."""
    sentiment_start = start - timedelta(days=lookback_days)
    columns = _get_table_columns(engine, "ticker_daily_sentiment_features")
    if not columns:
        LOGGER.warning("ticker_daily_sentiment_features introuvable — sentiment externe ignoré.")
        return pd.DataFrame(columns=["symbol", "trade_date", "sentiment_net_mean", "news_count"])

    sentiment_col = (
        "sentiment_net_mean_5d" if "sentiment_net_mean_5d" in columns
        else "sentiment_net_mean_1d" if "sentiment_net_mean_1d" in columns
        else None
    )
    news_col = "news_count_5d" if "news_count_5d" in columns else "news_count_1d" if "news_count_1d" in columns else None
    if sentiment_col is None or news_col is None:
        LOGGER.warning("Colonnes sentiment compatibles absentes — sentiment externe ignoré.")
        return pd.DataFrame(columns=["symbol", "trade_date", "sentiment_net_mean", "news_count"])

    query = text(f"""
        SELECT symbol,
               trade_date,
               {sentiment_col} AS sentiment_net_mean,
               {news_col} AS news_count
        FROM ticker_daily_sentiment_features
        WHERE trade_date BETWEEN :start AND :end
        ORDER BY trade_date, symbol
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"start": sentiment_start, "end": end}, parse_dates=["trade_date"])
    LOGGER.info("Sentiment chargé : %d lignes (lookback %dj)", len(df), lookback_days)
    return df


def load_predictions(engine: Engine, start: date, end: date) -> pd.DataFrame:
    """Charge les prédictions ML."""
    columns = _get_table_columns(engine, "model_predictions")
    if not columns:
        LOGGER.warning("model_predictions introuvable — prédictions ML ignorées.")
        return pd.DataFrame(columns=["symbol", "trade_date", "predicted_proba", "predicted_class"])

    date_col = "trade_date" if "trade_date" in columns else "prediction_date" if "prediction_date" in columns else None
    if date_col is None:
        LOGGER.warning("Aucune colonne date compatible dans model_predictions — prédictions ML ignorées.")
        return pd.DataFrame(columns=["symbol", "trade_date", "predicted_proba", "predicted_class"])

    query = text(f"""
        SELECT symbol,
               {date_col} AS trade_date,
               predicted_proba,
               predicted_class
        FROM model_predictions
        WHERE {date_col} BETWEEN :start AND :end
        ORDER BY {date_col}, symbol
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"start": start, "end": end}, parse_dates=["trade_date"])
    LOGGER.info("Prédictions ML chargées : %d lignes", len(df))
    return df


def pivot_ohlcv(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Pivote les OHLCV en DataFrames indexés par date, colonnes = symboles.

    Returns
    -------
    dict avec clés 'open', 'high', 'low', 'close', 'volume'
    """
    result = {}
    for col in ("open", "high", "low", "close", "volume"):
        pivoted = df.pivot_table(index="trade_date", columns="symbol", values=col)
        pivoted.sort_index(inplace=True)
        result[col] = pivoted
    return result



