"""Identify provider-declared split-basis transitions, never infer from returns.

Compare identical SIP daily timestamps in raw and split-adjusted variants. The
result is a retrospective data-quality exclusion, not a historical live signal.
"""
from datetime import datetime,timezone
import gzip
import json
import logging
import time
import pandas as pd
import numpy as np
from service.alpaca.clientAlpaca import _build_headers
from common.verified_http import verified_session
from service._http_retry import request_with_retry,RetryPolicy
from scripts.research.us_selected_universe_intraday_inputs_20261104 import OUT
from scripts.research.us_selected_universe_oracle_20261104 import END,save,digest


def main():
    folder=OUT/'split-qualification';folder.mkdir(exist_ok=False)
    names=json.loads((OUT/'inputs/manifest.json').read_text())['symbols']
    records=[];files={};calls=0
    with verified_session() as http:
        for adjustment in ('raw','split'):
            params=dict(symbols=','.join(names),timeframe='1Day',feed='sip',adjustment=adjustment,
                asof='-',sort='asc',limit=10000,start='2024-01-01T00:00:00Z',
                end=(END+pd.Timedelta(days=1)).tz_localize('America/New_York').tz_convert('UTC').isoformat())
            tokens=set();page=0
            while True:
                time.sleep(1.)
                response=request_with_retry(http,'GET','https://data.alpaca.markets/v2/stocks/bars',
                    headers=_build_headers('default'),params=params,
                    policy=RetryPolicy(max_attempts=3,timeout_seconds=30,base_delay_seconds=2))
                calls+=1;page+=1
                response.raise_for_status();payload=response.json()
                path=folder/f'{adjustment}-{page:03d}.json.gz'
                with gzip.open(path,'wb') as stream:stream.write(response.content)
                files[path.name]=digest(path)
                assert set(payload['bars'])<=set(names)
                for symbol,rows in payload['bars'].items():
                    records.extend(dict(symbol=symbol,timestamp=row['t'],close=row['c'],adjustment=adjustment) for row in rows)
                token=payload.get('next_page_token')
                if not token:break
                assert token not in tokens and page<25
                tokens.add(token);params['page_token']=token
    frame=pd.DataFrame(records)
    assert not frame.duplicated(['symbol','timestamp','adjustment']).any()
    matrix=frame.pivot(index=['symbol','timestamp'],columns='adjustment',values='close').reset_index()
    assert matrix[['raw','split']].notna().all().all() and matrix[['raw','split']].gt(0).all().all()
    matrix['date']=pd.to_datetime(matrix.timestamp,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    matrix=matrix.sort_values(['symbol','date'])
    matrix['factor']=matrix['split']/matrix['raw']
    matrix['previous_factor']=matrix.groupby('symbol').factor.shift()
    matrix['factor_ratio']=matrix.factor/matrix.previous_factor
    transitions=matrix[(matrix.factor_ratio-1).abs()>.001].copy()
    matrix.to_parquet(folder/'basis-comparison.parquet',index=False)
    transitions.to_csv(folder/'transitions.csv',index=False)
    files.update({f:digest(folder/f) for f in ['basis-comparison.parquet','transitions.csv']})
    save(folder/'report.json',dict(status='COMPLETED',symbols=len(names),rows=len(matrix),api_calls=calls,
        transitions=len(transitions),files=files,script_sha256=digest(__file__),
        method='SIP provider raw versus split-adjusted daily closes at identical timestamps; factor transition >0.1%',
        observed_at=datetime.now(timezone.utc).isoformat(),not_point_in_time=True,
        sql_writes=False,orders=0))
    print(transitions[['symbol','date','factor_ratio']].to_string(index=False))


if __name__=='__main__':main()
