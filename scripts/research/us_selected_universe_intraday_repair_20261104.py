"""Bounded SIP-only historical recovery for the missing research TOP5 names."""
from datetime import datetime, timezone
from pathlib import Path
import gzip
import hashlib
import json
import logging
import time

import pandas as pd
import requests

from common.verified_http import verified_session
from service.alpaca.intraday_bars import fetch_intraday, AlpacaIntradayBlocked
from scripts.research.us_selected_universe_intraday_inputs_20261104 import OUT
from scripts.research.us_selected_universe_oracle_20261104 import digest,save,END

LOG=logging.getLogger(__name__)


def main():
    inputs=OUT/'inputs'
    meta=json.loads((inputs/'manifest.json').read_text())
    coverage=pd.read_csv(inputs/'coverage-counts.csv')
    missing=sorted(set(meta['symbols'])-set(coverage.symbol))
    folder=OUT/'recovery';folder.mkdir(exist_ok=True)
    summaries=[];started=time.monotonic()
    for symbol in missing:
        dest=folder/symbol;dest.mkdir(exist_ok=True)
        if (dest/'receipt.json').exists():
            r=json.loads((dest/'receipt.json').read_text())
            if r['status']=='COMPLETED':
                assert digest(dest/'regular.parquet')==r['file_sha256']
                summaries.append(r);continue
            if r.get('error')!='Per-symbol recovery request ceiling exceeded':
                raise ValueError('Failed/partial recovery requires explicit review, not a silent retry')
            # Reviewed: Alpaca returns partial pages (~2500 bars) despite limit10000.
            # Replay the archived response chain locally, then request only its tail.
            backup=dest/'receipt-before-page-limit-repair.json'
            if not backup.exists():backup.write_bytes((dest/'receipt.json').read_bytes())
            old_report=folder/'report.json'
            if old_report.exists() and not (folder/'report-before-page-limit-repair.json').exists():
                (folder/'report-before-page-limit-repair.json').write_bytes(old_report.read_bytes())
        count=0;pages=[]
        with verified_session() as http:
            original=http.request
            def recorded(*args,**kwargs):
                nonlocal count
                count+=1
                name=f'page-{count:04d}.json.gz'
                cached=dest/name
                if cached.exists():
                    body=gzip.decompress(cached.read_bytes())
                    response=requests.Response();response.status_code=200;response._content=body
                    response.url='https://data.alpaca.markets/v2/stocks/bars'
                    response.headers['Content-Type']='application/json'
                    if count>1:
                        previous=json.loads(gzip.decompress((dest/f'page-{count-1:04d}.json.gz').read_bytes()))
                        assert kwargs['params'].get('page_token')==previous['next_page_token']
                else:
                    # Pacing includes first request, retries and symbol transitions.
                    time.sleep(1.)
                    response=original(*args,**kwargs)
                    body=response.content
                    with gzip.open(cached,'wb') as stream:stream.write(body)
                pages.append(dict(file=name,http_status=response.status_code,sha256=hashlib.sha256(body).hexdigest(),
                    retrieved_at_utc=datetime.now(timezone.utc).isoformat()))
                if count>100:raise RuntimeError('Per-symbol recovery request ceiling exceeded')
                return response
            http.request=recorded
            try:
                rows=fetch_intraday(symbol,start_epoch=int(pd.Timestamp('2024-01-01',tz='UTC').timestamp()),
                    end_epoch=int((END+pd.Timedelta(days=1)).tz_localize('America/New_York').tz_convert('UTC').timestamp()),
                    interval='5m',feed='sip',account_id='default',session=http,sleep_seconds=.2)
                frame=pd.DataFrame(rows)
                if frame.empty:
                    frame=pd.DataFrame(columns=['symbol','trade_date','timestamp','bar_end_timestamp','open','high','low','close','volume','payload_hash'])
                else:
                    frame['timestamp']=pd.to_datetime(frame.timestamp,unit='s',utc=True)
                    local=frame.timestamp.dt.tz_convert('America/New_York')
                    minutes=local.dt.hour*60+local.dt.minute
                    frame=frame[minutes.ge(570)&minutes.lt(960)].copy()
                    frame['symbol']=symbol
                    frame['trade_date']=frame.timestamp.dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
                    frame['bar_end_timestamp']=frame.timestamp+pd.Timedelta(minutes=5)
                    frame['payload_hash']=[hashlib.sha256(json.dumps(r,sort_keys=True,default=str).encode()).hexdigest() for r in frame.to_dict('records')]
                    frame=frame[['symbol','trade_date','timestamp','bar_end_timestamp','open','high','low','close','volume','payload_hash']]
                    assert not frame.duplicated(['symbol','timestamp']).any()
                frame.to_parquet(dest/'regular.parquet',index=False)
                receipt=dict(symbol=symbol,status='COMPLETED',rows=len(frame),api_calls=count,pages=pages,
                    file_sha256=digest(dest/'regular.parquet'),feed='sip',adjustment='raw',
                    retrieved_at_utc=datetime.now(timezone.utc).isoformat(),sql_writes=False)
            except Exception as exc:
                receipt=dict(symbol=symbol,status='FAILED',api_calls=count,pages=pages,error_type=type(exc).__name__,error=str(exc))
                save(dest/'receipt.json',receipt)
                save(folder/'report.json',dict(status='FAILED',cases=summaries+[receipt],sql_writes=False))
                raise
        save(dest/'receipt.json',receipt)
        summaries.append(receipt)
        save(OUT/'progress.json',dict(status='RUNNING',phase='RECOVER_MISSING_SIP',completed=len(summaries),
            total=len(missing),symbol=symbol,rows=sum(r['rows'] for r in summaries),
            api_calls=sum(r['api_calls'] for r in summaries),elapsed_seconds=time.monotonic()-started))
        LOG.info('%s recovered rows=%s calls=%s (%s/%s)',symbol,len(frame),count,len(summaries),len(missing))
    save(folder/'report.json',dict(status='COMPLETED',cases=summaries,api_calls=sum(r['api_calls'] for r in summaries),
        sql_writes=False,production_changed=False,script_sha256=digest(__file__)))


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    main()
