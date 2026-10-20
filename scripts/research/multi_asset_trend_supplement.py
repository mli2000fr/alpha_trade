"""Warmup SELECT-only and four licensed dividend queries; no bars/order writes."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import bindparam, create_engine, text

from scripts.research.multi_asset_trend_data import prepare, READ
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest


def run(root):
    cfg = prepare(root)['config']; out = root / 'supplement-v1'
    if out.exists(): raise ValueError('Supplement output immutable, use explicit new version on error')
    out.mkdir()
    sources = [Path(__file__), root / 'protocol.json', root / 'download.json']
    atomic_json(out / 'protocol.json', dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(p):digest(p) for p in sources},
        purpose='Existing DB2014Dec-2016Jan8 warmup/overlap plus EODHD2014Dec-2026Oct19 dividend/paydate records. No rules, universe or test window change.',
        sql='UTC READ ONLY REPEATABLE READ, max15s statement, SELECT-only, rollback',
        supplier_limit=4, no_orders=True, no_sql_writes=True))
    from database.connection import get_sqlalchemy_engine
    base = get_sqlalchemy_engine(db_name='alpha_trade')
    engine = create_engine(base.url, pool_size=1, max_overflow=0,
        connect_args={'connect_timeout':10,'read_timeout':25}, echo=False)
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            conn.execute(text('SET TRANSACTION READ ONLY')); conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade': raise ValueError('US only')
            query = text('''SELECT symbol,date,open,high,low,close,volume,adj_close,is_filled,data_source,data_adjustment
                FROM stock_bars_daily WHERE symbol IN :symbols AND date>=:start AND date<=:end ORDER BY symbol,date''').bindparams(bindparam('symbols',expanding=True))
            frame = pd.DataFrame([dict(r) for r in conn.execute(query,
                dict(symbols=cfg['symbols'],start=cfg['history_start'],end='2016-01-08')).mappings()])
            conn.rollback()
    finally: engine.dispose()
    frame.to_parquet(out / 'warmup-local.parquet', index=False)
    from common.verified_http import verified_session
    from service.eodhd.clientEodhd import _get_token
    token = _get_token(); receipts = []
    with verified_session() as session:
        for symbol in cfg['symbols']:
            public = dict(fmt='json', **{'from':cfg['history_start'],'to':cfg['actions_end']})
            response = session.get(f'https://eodhd.com/api/div/{symbol}.US',
                params=dict(public, api_token=token), timeout=(10,45))
            value = dict(symbol=symbol,endpoint=f'/api/div/{symbol}.US', params=public,
                observed_at_utc=datetime.now(timezone.utc).isoformat(),status_code=response.status_code,
                payload=response.json() if response.status_code == 200 else None)
            atomic_json(out / (symbol + '-dividends.json'), value)
            if response.status_code != 200 or not isinstance(value['payload'],list):
                raise RuntimeError(f'EODHD dividends unavailable HTTP {response.status_code}; no empty-history inference')
            print('Dividends',symbol,'records',len(value['payload']),flush=True)
            receipts.append(symbol)
    atomic_json(out / 'report.json',dict(status='SOURCES_CAPTURED_NOT_YET_QUALIFIED',
        warmup_rows=len(frame),symbols=receipts,provider_requests=4,sql_writes=False,orders=False,
        files={p.name:digest(p) for p in out.iterdir() if p.is_file()}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    run(parser.parse_args().root)
