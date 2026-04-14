from enum import Enum
from typing import Any

import pytz
from dateutil import parser

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


def _normalize_bar_timestamp(raw_timestamp: Any) -> Any:
    if not (isinstance(raw_timestamp, str) and 'T' in raw_timestamp):
        return raw_timestamp

    dt_utc = parser.isoparse(raw_timestamp)
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
    return dt_utc.astimezone(TZ_NEW_YORK).strftime('%Y-%m-%d %H:%M:%S')


def symbol_exists_in_stock_bars(conn, symbol: str) -> bool:
    """Wrapper legacy DB-API : vérifie l'existence du symbole dans stock_bars."""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 1 FROM stock_bars WHERE symbol=%s LIMIT 1
        """, (symbol,))
        return cursor.fetchone() is not None


def get_active_tradable_symbols(conn) -> list[str]:
    """Wrapper legacy DB-API : retourne les symboles actifs/tradables avec données disponibles."""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT symbol FROM stock_metadata WHERE status='active' AND tradable=1 AND bars_available=1
        """)
        return [row[0] for row in cursor.fetchall()]


def get_last_bar_timestamp(conn, symbol: str, time_frame: TimeFrame):
    """Wrapper legacy DB-API : retourne le dernier timestamp connu pour un symbole/timeframe."""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT MAX(timestamp) FROM stock_bars WHERE symbol=%s AND timeframe=%s
        """, (symbol, time_frame.db_value))
        result = cursor.fetchone()
        return result[0] if result and result[0] else None


def insert_bars(conn, symbol: str, bars: list[dict[str, Any]], timeframe: str) -> int:
    """Wrapper legacy DB-API : insère des bars avec upsert MySQL."""
    if not bars:
        return 0

    with conn.cursor() as cursor:
        sql = """
            INSERT INTO stock_bars (symbol, timestamp, timeframe, open_price, high_price, low_price, close_price, volume, trade_count, vwa_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE open_price=VALUES(open_price), high_price=VALUES(high_price), low_price=VALUES(low_price), close_price=VALUES(close_price), volume=VALUES(volume), trade_count=VALUES(trade_count), vwa_price=VALUES(vwa_price)
        """
        for bar in bars:
            timestamp = _normalize_bar_timestamp(bar['t'])
            cursor.execute(sql, (
                symbol,
                timestamp,
                timeframe,
                bar['o'],
                bar['h'],
                bar['l'],
                bar['c'],
                bar['v'],
                bar.get('n', 0),
                bar.get('vw', None)
            ))
    conn.commit()
    return len(bars)
