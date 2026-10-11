"""Persistence of raw intraday bars; never touches canonical daily prices."""
from pathlib import Path
from sqlalchemy import text

SCHEMA = Path(__file__).resolve().parent/'sql/stock/stock_bars_intraday.sql'
FIELDS = ('symbol','bar_timestamp','interval_code','data_source','market_code','provider_symbol',
    'bar_end_timestamp','trade_date','session_tag','open','high','low','close','volume',
    'data_adjustment','is_filled','observed_at','payload_hash','run_id')
UPDATE_FIELDS = ('provider_symbol','bar_end_timestamp','trade_date','session_tag','open','high','low',
                 'close','volume','observed_at','run_id')
UPSERT = text('INSERT INTO alpha_trade.stock_bars_intraday ('+','.join('`'+x+'`' for x in FIELDS)+') VALUES ('+
    ','.join(':'+x for x in FIELDS)+') ON DUPLICATE KEY UPDATE '+
    ','.join('`'+x+'`=IF(payload_hash<>VALUES(payload_hash),VALUES(`'+x+'`),`'+x+'`)' for x in UPDATE_FIELDS)+
    ',payload_hash=VALUES(payload_hash)')


def require_us(conn):
    if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
        raise RuntimeError('Intraday US requires alpha_trade; FR/CN databases forbidden')


def ensure_table(engine):
    with engine.begin() as conn:
        require_us(conn)
        conn.execute(text(SCHEMA.read_text(encoding='utf-8')))


def persist_rows(engine, rows, batch_size=500):
    """Short idempotent transactions. Count submitted qualified rows, not new inserts."""
    if batch_size < 1:
        raise ValueError('Invalid SQL tranche')
    total=0
    for offset in range(0,len(rows),batch_size):
        with engine.begin() as conn:
            require_us(conn)
            conn.execute(UPSERT,rows[offset:offset+batch_size])
        total+=len(rows[offset:offset+batch_size])
    return total
