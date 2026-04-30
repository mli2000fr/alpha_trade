from enum import Enum
from typing import Any


import pytz
from dateutil import parser
from sqlalchemy import MetaData, Table, text, Engine, and_, select

from database.assets import build_eligible_stock_metadata_filters

TZ_NEW_YORK = pytz.timezone('America/New_York')


class TimeFrame(Enum):
    ONE_MIN = ('1M', '1Min')
    ONE_DAY = ('1D', '1Day')
    ONE_HOUR = ('1H', '1Hour')
    FIFTEEN_MINS = ('15M', '15Min')
    THIRTY_MINS = ('30M', '30Min')

    def __init__(self, db_value: str, api_value: str):
        self.db_value = db_value
        self.api_value = api_value


SUPPORTED_DATA_INTEGRITY_TIMEFRAMES: tuple[TimeFrame, ...] = (TimeFrame.ONE_DAY,)


def validate_data_integrity_timeframe(time_frame: TimeFrame) -> None:
    if time_frame not in SUPPORTED_DATA_INTEGRITY_TIMEFRAMES:
        supported = ", ".join(tf.db_value for tf in SUPPORTED_DATA_INTEGRITY_TIMEFRAMES)
        raise ValueError(
            f"dataIntegrityEngine supporte uniquement les timeframes daily pour l'instant: {supported}."
        )


def _normalize_bar_timestamp(raw_timestamp: Any) -> Any:
    if not (isinstance(raw_timestamp, str) and 'T' in raw_timestamp):
        return raw_timestamp

    dt_utc = parser.isoparse(raw_timestamp)
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
    return dt_utc.astimezone(TZ_NEW_YORK).strftime('%Y-%m-%d %H:%M:%S')


def symbol_exists_in_stock_bars(conn, symbol: str) -> bool:
    """Vérifie l'existence du symbole dans stock_bars (SQLAlchemy Core)."""
    sql = text("SELECT 1 FROM stock_bars WHERE symbol=:symbol LIMIT 1")
    result = conn.execute(sql, {"symbol": symbol})
    return result.first() is not None


def get_active_tradable_symbols(conn) -> list[str]:
    """Retourne les symboles actifs/tradables avec données disponibles (SQLAlchemy Core)."""
    stock_metadata = Table("stock_metadata", MetaData(), autoload_with=conn.engine)
    stmt = select(stock_metadata.c.symbol).where(and_(*build_eligible_stock_metadata_filters(stock_metadata)))
    result = conn.execute(stmt)
    return [row[0] for row in result.fetchall()]


def get_last_bar_timestamp(conn, symbol: str, time_frame: TimeFrame):
    """Retourne le dernier timestamp connu pour un symbole/timeframe (SQLAlchemy Core)."""
    sql = text("SELECT MAX(timestamp) FROM stock_bars WHERE symbol=:symbol AND timeframe=:tf")
    result = conn.execute(sql, {"symbol": symbol, "tf": time_frame.db_value})
    row = result.first()
    return row[0] if row and row[0] else None


def insert_bars(conn, symbol: str, bars: list[dict[str, Any]], timeframe: str) -> int:
    """Insère des bars avec upsert MySQL (SQLAlchemy Core)."""
    if not bars:
        return 0
    sql = text("""
        INSERT INTO stock_bars (symbol, timestamp, timeframe, open_price, high_price, low_price, close_price, volume, trade_count, vwa_price)
        VALUES (:symbol, :timestamp, :timeframe, :open_price, :high_price, :low_price, :close_price, :volume, :trade_count, :vwa_price)
        ON DUPLICATE KEY UPDATE open_price=VALUES(open_price), high_price=VALUES(high_price), low_price=VALUES(low_price), close_price=VALUES(close_price), volume=VALUES(volume), trade_count=VALUES(trade_count), vwa_price=VALUES(vwa_price)
    """)
    params = []
    for bar in bars:
        timestamp = _normalize_bar_timestamp(bar['t'])
        params.append({
            "symbol": symbol,
            "timestamp": timestamp,
            "timeframe": timeframe,
            "open_price": bar['o'],
            "high_price": bar['h'],
            "low_price": bar['l'],
            "close_price": bar['c'],
            "volume": bar['v'],
            "trade_count": bar.get('n', 0),
            "vwa_price": bar.get('vw', None)
        })
    with conn.begin():
        for param in params:
            conn.execute(sql, param)
    return len(bars)
