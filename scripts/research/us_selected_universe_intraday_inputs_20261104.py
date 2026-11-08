"""Freeze existing SIP five-minute bars, SELECT-only, no provider requests."""
from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import time

import pandas as pd
from sqlalchemy import text, bindparam

from database.connection import get_sqlalchemy_engine
from common.daily_bar_sources import select_daily_bars
from scripts.research.us_selected_universe_oracle_20261104 import OUT as PRIOR, digest, save, END

OUT=Path(__file__).resolve().parents[2]/'artifacts/research/us_selected_universe_oracle/20261104-winner-dd15-v1'
LOG=logging.getLogger(__name__)


def main():
    folder=OUT/'inputs'
    folder.mkdir(parents=True,exist_ok=True)
    if (folder/'manifest.json').exists():
        p=json.loads((folder/'manifest.json').read_text())
        assert all(digest(folder/f)==h for f,h in p['files'].items())
        print('Verified frozen input archive',len(p['symbols']))
        return
    names=set()
    source_hashes={}
    for case in ('winner_h10','parcours_h20'):
        path=PRIOR/case/'daily-top5.csv'
        source_hashes[str(path)]=digest(path)
        names.update(pd.read_csv(path).symbol)
    names=sorted(names)
    months=pd.period_range('2024-01','2026-10',freq='M')
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    files,stats,receipts={},{},[]
    started=time.monotonic()
    query=text("SELECT symbol, trade_date, bar_timestamp AS timestamp, bar_end_timestamp, "
        "open,high,low,close,volume,payload_hash FROM stock_bars_intraday "
        "WHERE trade_date BETWEEN :start AND :end AND symbol IN :symbols "
        "AND interval_code='5m' AND data_source='alpaca_sip' AND provider='alpaca' "
        "AND market_code='US_EQ' AND session_tag='regular' AND data_adjustment='raw' "
        "AND is_filled=0 ORDER BY trade_date,symbol,bar_timestamp").bindparams(bindparam('symbols',expanding=True))
    with engine.connect() as conn:
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        assert conn.execute(text('SELECT DATABASE()')).scalar()=='alpha_trade'
        spy=pd.read_sql(text("SELECT symbol,date,open,high,low,close,volume,adj_close,is_filled,data_source,instrument_id "
            "FROM stock_bars_daily WHERE symbol='SPY' AND date BETWEEN '2023-01-01' AND :end"),conn,
            params={'end':str(END.date())},parse_dates=['date'])
        spy=select_daily_bars(spy).sort_values('date')
        assert not spy.date.duplicated().any() and len(spy)>700
        spy.to_parquet(folder/'spy-daily.parquet',index=False)
        files['spy-daily.parquet']=digest(folder/'spy-daily.parquet')
        for number,month in enumerate(months):
            lo=month.start_time.date();hi=min(month.end_time.date(),END.date())
            path=folder/f'{month}.parquet'
            if path.exists():
                frame=pd.read_parquet(path)
            else:
                frame=pd.read_sql(query,conn,params={'start':lo,'end':hi,'symbols':names})
                if not frame.empty:
                    frame['timestamp']=pd.to_datetime(frame.timestamp,utc=True)
                    frame['bar_end_timestamp']=pd.to_datetime(frame.bar_end_timestamp,utc=True)
                    frame['trade_date']=pd.to_datetime(frame.trade_date)
                    assert not frame.duplicated(['symbol','timestamp']).any()
                    assert (frame.bar_end_timestamp-frame.timestamp).eq(pd.Timedelta(minutes=5)).all()
                    assert frame.payload_hash.notna().all()
                frame.to_parquet(path,index=False)
            files[path.name]=digest(path)
            counts=frame.groupby(['symbol','trade_date']).size() if len(frame) else pd.Series(dtype=int)
            receipts.extend(dict(symbol=s,date=str(pd.Timestamp(d).date()),rows=int(n)) for (s,d),n in counts.items())
            stats[str(month)]=len(frame)
            save(OUT/'progress.json',dict(status='RUNNING',phase='FREEZE_INTRADAY',completed=number+1,
                total=len(months),rows=sum(stats.values()),month=str(month),elapsed_seconds=time.monotonic()-started))
            LOG.info('%s rows=%s total=%s',month,len(frame),sum(stats.values()))
        conn.rollback()
    engine.dispose()
    pd.DataFrame(receipts).to_csv(folder/'coverage-counts.csv',index=False)
    files['coverage-counts.csv']=digest(folder/'coverage-counts.csv')
    save(folder/'manifest.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),symbols=names,
        start='2024-01-01',end=str(END.date()),monthly_rows=stats,rows=sum(stats.values()),files=files,
        source_hashes=source_hashes,read_only_transaction=True,sql_writes=False,provider_calls=0,orders=0,
        script_sha256=digest(__file__),price_basis='SIP raw five-minute bars; daily proxy retained separately'))
    print(json.dumps(dict(status='INPUTS_FROZEN',symbols=len(names),rows=sum(stats.values()))))


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    main()
