import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import Table, Column, String, Boolean, TIMESTAMP, MetaData
from sqlalchemy.dialects.mysql import insert as mysql_insert
from database.connection import get_sqlalchemy_engine, SessionLocal, metadata
from service.alpaca.client import fetch_alpaca_assets

# Définition de la table stock_metadata (reflection ou déclaration explicite)
engine = get_sqlalchemy_engine()
stock_metadata = Table(
    'stock_metadata', metadata,
    Column('symbol', String(100), primary_key=True),
    Column('id_alpaca', String(88)),
    Column('company_name', String(255)),
    Column('exchange', String(20)),
    Column('asset_class', String(20)),
    Column('status', String(20)),
    Column('tradable', Boolean),
    Column('bars_available', Boolean),
    Column('last_updated', TIMESTAMP),
    autoload_with=engine
)

def insert_assets_to_db(assets):
    session = SessionLocal()
    try:
        for asset in assets:
            stmt = mysql_insert(stock_metadata).values(
                symbol=asset['symbol'],
                id_alpaca=asset['id'],
                company_name=asset.get('name', ''),
                exchange=asset.get('exchange', ''),
                asset_class=asset.get('class', ''),
                status=asset.get('status', ''),
                tradable=asset.get('tradable', False),
                bars_available=True
            )
            update_dict = {
                'company_name': stmt.inserted.company_name,
                'exchange': stmt.inserted.exchange,
                'asset_class': stmt.inserted.asset_class,
                'status': stmt.inserted.status,
                'tradable': stmt.inserted.tradable,
                'bars_available': stmt.inserted.bars_available,
                'last_updated': stmt.inserted.last_updated
            }
            ondup = stmt.on_duplicate_key_update(**update_dict)
            session.execute(ondup)
        session.commit()
    finally:
        session.close()


# Nouvelle fonction pour mettre à jour bars_available à False pour un symbole donné
def update_bars_available_false(symbol):
    session = SessionLocal()
    try:
        stmt = stock_metadata.update().where(stock_metadata.c.symbol == symbol).values(bars_available=False)
        session.execute(stmt)
        session.commit()
    finally:
        session.close()
