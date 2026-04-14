from dateutil import parser
from enum import Enum
import pytz


class TimeFrame(Enum):
    ONE_MIN = ('1M', '1Min')
    ONE_DAY = ('1D', '1Day')
    ONE_HOUR = ('1H', '1Hour')
    FIFTEEN_MINS = ('15M', '15Min')
    THIRTY_MINS = ('30M', '30Min')

    def __init__(self, db_value, api_value):
        self.db_value = db_value
        self.api_value = api_value


def symbol_exists_in_stock_bars(conn, symbol):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 1 FROM stock_bars WHERE symbol=%s LIMIT 1
        """, (symbol,))
        return cursor.fetchone() is not None

def get_active_tradable_symbols(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT symbol FROM stock_metadata WHERE status='active' AND tradable=1 AND bars_available=1
        """)
        return [row[0] for row in cursor.fetchall()]

def get_last_bar_timestamp(conn, symbol, timeFrame):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT MAX(timestamp) FROM stock_bars WHERE symbol=%s AND timeframe=%s
        """, (symbol, timeFrame.db_value))
        result = cursor.fetchone()
        return result[0] if result and result[0] else None

def insert_bars(conn, symbol, bars, timeframe):
    if not bars:
        return
    tz_ny = pytz.timezone('America/New_York')
    with conn.cursor() as cursor:
        sql = """
            INSERT INTO stock_bars (symbol, timestamp, timeframe, open_price, high_price, low_price, close_price, volume, trade_count, vwa_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE open_price=VALUES(open_price), high_price=VALUES(high_price), low_price=VALUES(low_price), close_price=VALUES(close_price), volume=VALUES(volume), trade_count=VALUES(trade_count), vwa_price=VALUES(vwa_price)
        """
        for bar in bars:
            timestamp = bar['t']
            if isinstance(timestamp, str) and 'T' in timestamp:
                dt_utc = parser.isoparse(timestamp)
                if dt_utc.tzinfo is None:
                    dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
                dt_ny = dt_utc.astimezone(tz_ny)
                timestamp = dt_ny.strftime('%Y-%m-%d %H:%M:%S')
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
