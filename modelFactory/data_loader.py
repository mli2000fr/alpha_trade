"""modelFactory/data_loader.py — Chargement des bars depuis stock_bars_daily."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, cast

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)

SELECTOR_HISTORY_CONTEXT_COLUMNS: tuple[str, ...] = (
    "trend_score",
    "vcp_score",
    "final_score",
    "raw_final_score",
    "candidate_rank",
    "atr_pct_20",
    "weekly_trend_score",
    "high_52w_proximity",
    "volatility_ratio",
    "earnings_blackout",
    "selector_signal_mode",
)


def _get_table_columns(engine: Engine, table_name: str) -> set[str]:
    try:
        return {str(column.get("name")) for column in inspect(engine).get_columns(table_name)}
    except Exception:  # noqa: BLE001
        LOGGER.debug("_get_table_columns failed table=%s", table_name, exc_info=True)
        return set()


def _coerce_date_value(value: object) -> date | None:
    if value is None or bool(pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.Timestamp(cast(Any, value)).date()
    except Exception:  # noqa: BLE001
        LOGGER.debug("_coerce_date_value failed value=%r", value, exc_info=True)
        return None


def _subtract_years(anchor_date: date, years: int) -> date:
    try:
        return anchor_date.replace(year=anchor_date.year - years)
    except ValueError:
        return anchor_date.replace(year=anchor_date.year - years, month=2, day=28)


def resolve_training_start_date(
    anchor_date: date | None,
    training_start_date: date | None = None,
    history_window_years: int | None = None,
) -> date | None:
    if training_start_date is not None:
        return training_start_date
    if anchor_date is None or history_window_years is None:
        return None
    return _subtract_years(anchor_date, int(history_window_years))


def resolve_history_window_start_date(anchor_date: date | None, history_window_years: int | None) -> date | None:
    """Compatibilité legacy avec l'ancien contrat ``history_window_years``."""
    return resolve_training_start_date(anchor_date, history_window_years=history_window_years)


def _build_in_clause(symbols: list[str]) -> tuple[str, dict[str, object]]:
    params: dict[str, object] = {}
    placeholders: list[str] = []
    for idx, symbol in enumerate(symbols):
        key = f"sym_{idx}"
        params[key] = symbol
        placeholders.append(f":{key}")
    return ", ".join(placeholders), params


def load_symbol_latest_bar_date(engine: Engine, symbol: str, end_date: date | None = None) -> date | None:
    where_clause = "WHERE symbol = :sym"
    params: dict[str, object] = {"sym": symbol}
    if end_date is not None:
        where_clause += " AND `date` <= :end_date"
        params["end_date"] = end_date
    query = text(f"SELECT MAX(`date`) AS latest_date FROM stock_bars_daily {where_clause}")
    with engine.connect() as conn:
        row = conn.execute(query, params).mappings().first()
    latest_date = _coerce_date_value(row["latest_date"] if row else None)
    LOGGER.info("load_symbol_latest_bar_date symbol=%s latest_date=%s", symbol, latest_date)
    return latest_date


def load_symbol_latest_bar_dates(
    engine: Engine,
    symbols: list[str],
    end_date: date | None = None,
) -> dict[str, date]:
    if not symbols:
        return {}
    in_clause, params = _build_in_clause(symbols)
    where_clause = f"WHERE symbol IN ({in_clause})"
    if end_date is not None:
        where_clause += " AND `date` <= :end_date"
        params["end_date"] = end_date
    query = text(
        "SELECT symbol, MAX(`date`) AS latest_date "
        f"FROM stock_bars_daily {where_clause} GROUP BY symbol"
    )
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()
    result = {
        str(row["symbol"]): latest_date
        for row in rows
        if (latest_date := _coerce_date_value(row.get("latest_date"))) is not None
    }
    LOGGER.info("load_symbol_latest_bar_dates symbols=%d resolved=%d", len(symbols), len(result))
    return result


def load_universe_latest_bar_date(
    engine: Engine,
    symbols: list[str] | None = None,
    end_date: date | None = None,
) -> date | None:
    where_clauses: list[str] = []
    params: dict[str, object] = {}
    if symbols:
        in_clause, symbol_params = _build_in_clause(symbols)
        params.update(symbol_params)
        where_clauses.append(f"symbol IN ({in_clause})")
    if end_date is not None:
        where_clauses.append("`date` <= :end_date")
        params["end_date"] = end_date
    where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    query = text(f"SELECT MAX(`date`) AS latest_date FROM stock_bars_daily {where_clause}")
    with engine.connect() as conn:
        row = conn.execute(query, params).mappings().first()
    latest_date = _coerce_date_value(row["latest_date"] if row else None)
    LOGGER.info("load_universe_latest_bar_date symbols=%s latest_date=%s", len(symbols) if symbols else "ALL", latest_date)
    return latest_date


def load_available_trading_dates(
    engine: Engine,
    symbols: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[date]:
    """Retourne les dates de trading distinctes disponibles dans ``stock_bars_daily``."""
    where_clauses: list[str] = []
    params: dict[str, object] = {}
    if symbols:
        in_clause, symbol_params = _build_in_clause(symbols)
        params.update(symbol_params)
        where_clauses.append(f"symbol IN ({in_clause})")
    if start_date is not None:
        where_clauses.append("`date` >= :start_date")
        params["start_date"] = start_date
    if end_date is not None:
        where_clauses.append("`date` <= :end_date")
        params["end_date"] = end_date
    where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    query = text(
        "SELECT DISTINCT `date` AS trading_date "
        f"FROM stock_bars_daily {where_clause} ORDER BY `date`"
    )
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()
    trading_dates = [
        trading_date
        for row in rows
        if (trading_date := _coerce_date_value(row.get("trading_date"))) is not None
    ]
    LOGGER.info(
        "load_available_trading_dates symbols=%s start_date=%s end_date=%s count=%d",
        len(symbols) if symbols else "ALL",
        start_date,
        end_date,
        len(trading_dates),
    )
    return trading_dates


def load_symbol_bars(
    engine: Engine,
    symbol: str,
    end_date: date | None = None,
    start_date: date | None = None,
) -> pd.DataFrame:
    """Charge l'historique complet d'un symbole depuis stock_bars_daily.

    Retourne un DataFrame trié par date avec colonnes :
    symbol, date, open, high, low, close, volume, adj_close, vwap, daily_return, is_filled
    """
    where_clause = "WHERE symbol = :sym"
    params: dict[str, object] = {"sym": symbol}
    if start_date is not None:
        where_clause += " AND `date` >= :start_date"
        params["start_date"] = start_date
    if end_date is not None:
        where_clause += " AND `date` <= :end_date"
        params["end_date"] = end_date
    query = text(
        "SELECT symbol, `date`, `open`, high, low, `close`, volume, adj_close, vwap, daily_return, is_filled "
        f"FROM stock_bars_daily {where_clause} ORDER BY `date`"
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params, parse_dates=["date"])
    LOGGER.info("load_symbol_bars symbol=%s start_date=%s end_date=%s rows=%d", symbol, start_date, end_date, len(df))
    return df


def load_benchmark_bars(
    engine: Engine,
    benchmark_symbol: str = "SPY",
    end_date: date | None = None,
    start_date: date | None = None,
) -> pd.DataFrame:
    """Charge les barres du benchmark marché utilisé pour les features contextuelles."""
    df = load_symbol_bars(engine, benchmark_symbol, end_date=end_date, start_date=start_date)
    LOGGER.info("load_benchmark_bars benchmark_symbol=%s start_date=%s end_date=%s rows=%d", benchmark_symbol, start_date, end_date, len(df))
    return df


def load_universe_bars(
    engine: Engine,
    symbols: list[str] | None = None,
    end_date: date | None = None,
    start_date: date | None = None,
) -> pd.DataFrame:
    """Charge un panel historique minimal de l'univers pour les features cross-sectionnelles."""
    where_clauses: list[str] = []
    params: dict[str, object] = {}
    if symbols:
        in_clause, symbol_params = _build_in_clause(symbols)
        params.update(symbol_params)
        where_clauses.append(f"symbol IN ({in_clause})")
    if start_date is not None:
        where_clauses.append("`date` >= :start_date")
        params["start_date"] = start_date
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
    LOGGER.info(
        "load_universe_bars symbols=%s start_date=%s end_date=%s rows=%d",
        len(symbols) if symbols else "ALL",
        start_date,
        end_date,
        len(df),
    )
    return df


def load_symbol_sentiment(
    engine: Engine,
    symbol: str,
    end_date: date | None = None,
    start_date: date | None = None,
) -> pd.DataFrame:
    """Charge les features sentiment quotidiennes depuis ticker_daily_sentiment_features.

    Retourne un DataFrame avec colonnes :
    symbol, trade_date, news_count_1d, sentiment_net_mean_1d, sentiment_confidence_mean_1d, major_event_flag
    """
    where_clause = "WHERE symbol = :sym"
    params: dict[str, object] = {"sym": symbol}
    if start_date is not None:
        where_clause += " AND trade_date >= :start_date"
        params["start_date"] = start_date
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
    LOGGER.info("load_symbol_sentiment symbol=%s start_date=%s end_date=%s rows=%d", symbol, start_date, end_date, len(df))
    return df


def load_symbols_sentiment(
    engine: Engine,
    symbols: list[str],
    end_date: date | None = None,
    start_date: date | None = None,
) -> pd.DataFrame:
    """Charge les features sentiment pour une liste de symboles."""
    if not symbols:
        return pd.DataFrame(columns=["symbol", "trade_date", "news_count_1d", "sentiment_net_mean_1d", "sentiment_confidence_mean_1d", "major_event_flag"])
    in_clause, params = _build_in_clause(symbols)
    where_clause = f"WHERE symbol IN ({in_clause})"
    if start_date is not None:
        where_clause += " AND trade_date >= :start_date"
        params["start_date"] = start_date
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
    LOGGER.info("load_symbols_sentiment symbols=%d start_date=%s end_date=%s rows=%d", len(symbols), start_date, end_date, len(df))
    return df


def load_symbols_selector_context(
    engine: Engine,
    symbols: list[str],
    end_date: date | None = None,
    start_date: date | None = None,
) -> pd.DataFrame:
    """Charge le contexte selector PIT-safe depuis stock_scores_history.

    Retourne un DataFrame avec au minimum :
    - symbol
    - date (projection de snapshot_date)
    - sous-ensemble des colonnes selector disponibles dans le schéma courant
    """
    expected_columns = ["symbol", "date", *SELECTOR_HISTORY_CONTEXT_COLUMNS]
    if not symbols:
        return pd.DataFrame(columns=expected_columns)

    available_columns = _get_table_columns(engine, "stock_scores_history")
    if "symbol" not in available_columns or "snapshot_date" not in available_columns:
        LOGGER.info("load_symbols_selector_context unavailable missing_required_columns=%s", sorted(available_columns))
        return pd.DataFrame(columns=expected_columns)

    selected_columns = [
        column for column in SELECTOR_HISTORY_CONTEXT_COLUMNS if column in available_columns
    ]
    in_clause, params = _build_in_clause(symbols)
    where_clauses = [f"symbol IN ({in_clause})"]
    if start_date is not None:
        where_clauses.append("snapshot_date >= :start_date")
        params["start_date"] = start_date
    if end_date is not None:
        where_clauses.append("snapshot_date <= :end_date")
        params["end_date"] = end_date
    where_clause = " AND ".join(where_clauses)
    select_list = ["symbol", "snapshot_date AS `date`", *selected_columns]
    query = text(
        "SELECT "
        + ", ".join(select_list)
        + f" FROM stock_scores_history WHERE {where_clause} ORDER BY symbol, snapshot_date"
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params, parse_dates=["date"])

    if df.empty:
        return pd.DataFrame(columns=["symbol", "date", *selected_columns])

    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df = df[df["symbol"] != ""].copy()
    for missing_column in SELECTOR_HISTORY_CONTEXT_COLUMNS:
        if missing_column not in df.columns:
            df[missing_column] = pd.NA
    LOGGER.info(
        "load_symbols_selector_context symbols=%d start_date=%s end_date=%s rows=%d cols=%d",
        len(symbols),
        start_date,
        end_date,
        len(df),
        len(df.columns),
    )
    return df.loc[:, expected_columns].copy()


def load_symbol_selector_context(
    engine: Engine,
    symbol: str,
    end_date: date | None = None,
    start_date: date | None = None,
) -> pd.DataFrame:
    """Wrapper mono-symbole autour de load_symbols_selector_context."""
    normalized_symbol = str(symbol).strip().upper()
    if not normalized_symbol:
        return pd.DataFrame(columns=["symbol", "date", *SELECTOR_HISTORY_CONTEXT_COLUMNS])
    return load_symbols_selector_context(
        engine,
        [normalized_symbol],
        end_date=end_date,
        start_date=start_date,
    )


