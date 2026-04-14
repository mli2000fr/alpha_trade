from database.connection import get_sqlalchemy_engine, SessionLocal
from service.alpaca.client import fetch_bars
from dateutil import parser
from database.assets import update_bars_available_false
from database.bar_metadata import TimeFrame
from sqlalchemy import Table, Column, String, Boolean, TIMESTAMP, MetaData, select, func, and_, insert as sa_insert
from sqlalchemy.dialects.mysql import insert as mysql_insert
from common.utils import getLastDateMarche
import pytz

# Définition de la table stock_metadata (pour get_active_tradable_symbols)
engine = get_sqlalchemy_engine()
metadata = MetaData()
stock_metadata = Table(
    'stock_metadata', metadata,
    autoload_with=engine
)
stock_bars = Table(
    'stock_bars', metadata,
    autoload_with=engine
)

def get_active_tradable_symbols(session):
    q = select(stock_metadata.c.symbol).where(
        and_(
            stock_metadata.c.status == 'active',
            stock_metadata.c.tradable == True,
            stock_metadata.c.bars_available == True
        )
    )
    return [r[0] for r in session.execute(q).all()]

def symbol_exists_in_stock_bars(session, symbol):
    q = select(stock_bars.c.symbol).where(stock_bars.c.symbol == symbol).limit(1)
    return session.execute(q).first() is not None

def get_last_bar_timestamp(session, symbol, timeFrame):
    q = select(func.max(stock_bars.c.timestamp)).where(
        and_(stock_bars.c.symbol == symbol, stock_bars.c.timeframe == timeFrame.db_value)
    )
    result = session.execute(q).scalar_one_or_none()
    return result

def insert_bars(session, symbol, bars, timeframe):
    if not bars:
        return
    tz_ny = pytz.timezone('America/New_York')
    for bar in bars:
        timestamp = bar['t']
        if isinstance(timestamp, str) and 'T' in timestamp:
            dt_utc = parser.isoparse(timestamp)
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
            dt_ny = dt_utc.astimezone(tz_ny)
            timestamp = dt_ny.strftime('%Y-%m-%d %H:%M:%S')
        stmt = mysql_insert(stock_bars).values(
            symbol=symbol,
            timestamp=timestamp,
            timeframe=timeframe,
            open_price=bar['o'],
            high_price=bar['h'],
            low_price=bar['l'],
            close_price=bar['c'],
            volume=bar['v'],
            trade_count=bar.get('n', 0),
            vwa_price=bar.get('vw', None)
        )
        update_dict = {
            'open_price': stmt.inserted.open_price,
            'high_price': stmt.inserted.high_price,
            'low_price': stmt.inserted.low_price,
            'close_price': stmt.inserted.close_price,
            'volume': stmt.inserted.volume,
            'trade_count': stmt.inserted.trade_count,
            'vwa_price': stmt.inserted.vwa_price
        }
        ondup = stmt.on_duplicate_key_update(**update_dict)
        session.execute(ondup)
    session.commit()

def import_alpaca_bars(timeFrame):
    session = SessionLocal()
    try:
        symbols = get_active_tradable_symbols(session)
        total = len(symbols)
        for idx, symbol in enumerate(symbols, 1):
            print(f"Traitement du symbole ({idx} / {total}) : {symbol}")
            last_timestamp = get_last_bar_timestamp(session, symbol, timeFrame)
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
                    if not symbol_exists_in_stock_bars(session, symbol):
                        print(f"Aucun bar trouvé pour {symbol}, mise à jour bars_available à False.")
                        update_bars_available_false(symbol)
                    break
                insert_bars(session, symbol, bars, timeFrame.db_value)
                all_bars.extend(bars)
                # Préparer la date de début pour le prochain appel (bar le plus récent)
                last_bar_time = bars[-1]['t']
                next_start = last_bar_time
            print(f"{len(all_bars)} bars insérés pour {symbol}")
    finally:
        session.close()

def main():
    import_alpaca_bars(TimeFrame.ONE_DAY)
    #import_alpaca_bars(TimeFrame.THIRTY_MINS)
    
    
if __name__ == "__main__":
    main()
