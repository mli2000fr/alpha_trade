from database.connection import get_db_connection
from service.alpaca.client import fetch_bars
from dateutil import parser
from database.import_alpaca_assets import update_bars_available_false
from enum import Enum


class TimeFrame(Enum):
    ONE_DAY = ('1D', '1Day')
    ONE_HOUR = ('1H', '1Hour')

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
    with conn.cursor() as cursor:
        sql = """
            INSERT INTO stock_bars (symbol, timestamp, timeframe, open_price, high_price, low_price, close_price, volume, trade_count, vwa_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE open_price=VALUES(open_price), high_price=VALUES(high_price), low_price=VALUES(low_price), close_price=VALUES(close_price), volume=VALUES(volume), trade_count=VALUES(trade_count), vwa_price=VALUES(vwa_price)
        """
        for bar in bars:
            timestamp = bar['t']
            if isinstance(timestamp, str) and 'T' in timestamp:
                timestamp = parser.isoparse(timestamp).strftime('%Y-%m-%d %H:%M:%S')
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

def import_alpaca_bars(timeFrame):
    conn = get_db_connection()
    try:
        symbols = get_active_tradable_symbols(conn)
        total = len(symbols)
        for idx, symbol in enumerate(symbols, 1):
            print(f"Traitement du symbole ({idx} / {total}) : {symbol}")
            last_timestamp = get_last_bar_timestamp(conn, symbol, timeFrame)
            print(f"Last bar : {symbol} {last_timestamp}")
            start_date = None
            if last_timestamp:
                # Alpaca attend un format ISO 8601, conversion si besoin
                start_date = last_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ') if hasattr(last_timestamp, 'strftime') else str(last_timestamp)
            all_bars = []
            next_start = start_date
            while True:
                # Ajouter une minute à next_start si défini
                if next_start:
                    import dateutil.parser
                    import datetime
                    dt = dateutil.parser.isoparse(next_start)
                    dt_plus = dt + datetime.timedelta(minutes=1)
                    next_start_call = dt_plus.strftime('%Y-%m-%dT%H:%M:%SZ')
                else:
                    next_start_call = None
                print(f"Traitement du symbole : {symbol} {next_start_call}")
                bars = fetch_bars(symbol, timeFrame.api_value, next_start_call)
                print(f"Traitement du symbole : {symbol} {len(bars)} bars récupérés")
                if not bars:
                    # Si aucun bar n'est retourné et que le symbole n'existe pas dans stock_bars, on met à jour bars_available à False
                    if not symbol_exists_in_stock_bars(conn, symbol):
                        print(f"Aucun bar trouvé pour {symbol}, mise à jour bars_available à False.")
                        update_bars_available_false(symbol)
                    break
                insert_bars(conn, symbol, bars, timeFrame.db_value)
                all_bars.extend(bars)
                # Préparer la date de début pour le prochain appel (bar le plus récent)
                last_bar_time = bars[-1]['t']
                next_start = last_bar_time
            print(f"{len(all_bars)} bars insérés pour {symbol}")
    finally:
        conn.close()

def main():
    import_alpaca_bars(TimeFrame.ONE_DAY)
    import_alpaca_bars(TimeFrame.ONE_HOUR)
    
    
if __name__ == "__main__":
    main()
