from database.connection import get_db_connection
from service.alpaca.client import fetch_bars
from dateutil import parser
from database.assets import update_bars_available_false
from database.bar_metadata import TimeFrame, symbol_exists_in_stock_bars, get_active_tradable_symbols, get_last_bar_timestamp, insert_bars
from enum import Enum
from common.utils import getLastDateMarche
import pytz


def import_alpaca_bars(timeFrame):
    conn = get_db_connection()
    try:
        symbols = get_active_tradable_symbols(conn)
        total = len(symbols)
        for idx, symbol in enumerate(symbols, 1):
            print(f"Traitement du symbole ({idx} / {total}) : {symbol}")
            last_timestamp = get_last_bar_timestamp(conn, symbol, timeFrame)
            print(f"Last bar : {symbol} {last_timestamp}")
            # Vérification de la dernière date d'ouverture du marché
            if last_timestamp:
                last_date = last_timestamp.date() if hasattr(last_timestamp, 'date') else last_timestamp
                marche_date = getLastDateMarche()
                if str(last_date) == str(marche_date):
                    print(f"{symbol} déjà à jour pour la dernière date de marché ({marche_date}), passage au suivant.")
                    continue
                # Alpaca attend un format ISO 8601, conversion si besoin
                start_date = last_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ') if hasattr(last_timestamp, 'strftime') else str(last_timestamp)
            else:
                start_date = None
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
    #import_alpaca_bars(TimeFrame.THIRTY_MINS)
    
    
if __name__ == "__main__":
    main()
