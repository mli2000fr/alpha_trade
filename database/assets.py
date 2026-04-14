
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_connection
from service.alpaca.client import fetch_alpaca_assets

def insert_assets_to_db(assets):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for asset in assets:
                sql = '''
                INSERT INTO stock_metadata (symbol, id_alpaca, company_name, exchange, asset_class, status, tradable, bars_available)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    company_name=VALUES(company_name),
                    exchange=VALUES(exchange),
                    asset_class=VALUES(asset_class),
                    status=VALUES(status),
                    tradable=VALUES(tradable),
                    bars_available=VALUES(bars_available),
                    last_updated=CURRENT_TIMESTAMP
                '''
                cursor.execute(sql, (
                    asset['symbol'],
                    asset['id'],
                    asset.get('name', ''),
                    asset.get('exchange', ''),
                    asset.get('class', ''),
                    asset.get('status', ''),
                    asset.get('tradable', False),
                    True
                ))
            conn.commit()
    finally:
        conn.close()


# Nouvelle fonction pour mettre à jour bars_available à False pour un symbole donné
def update_bars_available_false(symbol):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
            UPDATE stock_metadata
            SET bars_available = FALSE
            WHERE symbol = %s
            """
            cursor.execute(sql, (symbol,))
        conn.commit()
    finally:
        conn.close()

