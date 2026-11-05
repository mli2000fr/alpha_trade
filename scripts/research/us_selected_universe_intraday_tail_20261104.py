"""Recover only the missing tails of the eight already archived TOP5 names."""
from pathlib import Path
from datetime import datetime,timezone
import gzip,json,hashlib,time
import pandas as pd
from service.alpaca.intraday_bars import fetch_intraday
from scripts.research.us_selected_universe_intraday_inputs_20261104 import OUT
from scripts.research.us_selected_universe_oracle_20261104 import END,save,digest


def main():
    folder=OUT/'tail-recovery';folder.mkdir(exist_ok=False)
    coverage=pd.read_csv(OUT/'inputs/coverage-counts.csv',parse_dates=['date'])
    results=[]
    for symbol,start in (coverage.groupby('symbol').date.max()+pd.Timedelta(days=1)).items():
        if start>END:continue
        time.sleep(1.)
        rows=fetch_intraday(symbol,start_epoch=int(start.tz_localize('America/New_York').tz_convert('UTC').timestamp()),
            end_epoch=int((END+pd.Timedelta(days=1)).tz_localize('America/New_York').tz_convert('UTC').timestamp()),
            interval='5m',feed='sip',account_id='default',sleep_seconds=1.)
        raw=folder/f'{symbol}.json.gz'
        with gzip.open(raw,'wt',encoding='utf-8') as stream:json.dump(rows,stream)
        a=pd.DataFrame(rows)
        if len(a):
            a['timestamp']=pd.to_datetime(a.timestamp,unit='s',utc=True)
            local=a.timestamp.dt.tz_convert('America/New_York')
            minutes=local.dt.hour*60+local.dt.minute
            a=a[minutes.ge(570)&minutes.lt(960)].copy()
            a['symbol']=symbol
            a['trade_date']=a.timestamp.dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
            a['bar_end_timestamp']=a.timestamp+pd.Timedelta(minutes=5)
            a['payload_hash']=digest(raw)
            a=a[['symbol','trade_date','timestamp','bar_end_timestamp','open','high','low','close','volume','payload_hash']]
            assert a.trade_date.ge(start).all() and a.trade_date.le(END).all()
        else:a=pd.DataFrame(columns=['symbol','trade_date','timestamp','bar_end_timestamp','open','high','low','close','volume','payload_hash'])
        path=folder/f'{symbol}.parquet';a.to_parquet(path,index=False)
        results.append(dict(symbol=symbol,start=str(start.date()),end=str(END.date()),rows=len(a),
            file=path.name,file_sha256=digest(path),raw_sha256=digest(raw)))
        print(symbol,'tail rows',len(a),flush=True)
    save(folder/'report.json',dict(status='COMPLETED',cases=results,script_sha256=digest(__file__),
        sql_writes=False,orders=0,observed_at=datetime.now(timezone.utc).isoformat()))


if __name__=='__main__':main()
