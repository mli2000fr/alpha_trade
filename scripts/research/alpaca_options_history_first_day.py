"""Find the earliest observed option bar across fixed liquid-contract probes."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from service.alpaca.accounts import AccountRegistry
from service.alpaca.clientAlpaca import get_alpaca_credentials
from service.forward_pit.batch import _configure_alpaca_session

OUTPUT = Path('artifacts/research/alpaca_options_history/20261010-first-day')


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    contracts = [f'{root}{expiry}{side}{strike}'
        for root, strike in [('AAPL','00180000'),('MSFT','00400000'),('SPY','00480000')]
        for expiry in ['240216','240315'] for side in ['C','P']]
    key, secret = get_alpaca_credentials('default')
    account = AccountRegistry.get().resolve('default')
    broker = 'https://paper-api.alpaca.markets' if account.mode=='paper' else 'https://api.alpaca.markets'
    report = {'observed_at':datetime.now(timezone.utc).isoformat(),'account_id':'default',
        'contracts':contracts,'sql_writes':False,'orders_submitted':False,
        'scope':'earliest observed for this 12-contract sample, not a universal provider guarantee',
        'tests':[]}
    with requests.Session() as session:
        _configure_alpaca_session(session,use_system_trust_store=True)
        session.headers.update({'APCA-API-KEY-ID':key,'APCA-API-SECRET-KEY':secret})
        def fetch(name,url,params=None):
            response=session.get(url,params=params,timeout=40)
            try:payload=response.json()
            except ValueError:payload={'non_json_body':response.text[:1000]}
            (OUTPUT/f'{name}.json').write_text(json.dumps({'endpoint':url,'params':params,
                'http_status':response.status_code,'payload':payload},indent=2),encoding='utf-8')
            report['tests'].append({'test':name,'http_status':response.status_code,
                'error':payload.get('message') if response.status_code>=400 else None})
            time.sleep(.3)
            return response.status_code,payload
        # Validate actual contract identities without treating guessed OCC codes as a chain.
        for contract in contracts:
            status,payload=fetch(f'identity-{contract}',broker+'/v2/options/contracts/'+contract)
            report['tests'][-1]['returned_symbol']=payload.get('symbol')
        params={'symbols':','.join(contracts),'timeframe':'1Day','start':'2023-01-01T00:00:00Z',
            'end':'2024-03-01T00:00:00Z','limit':10000,'sort':'asc'}
        rows=[]
        for page in range(10):
            status,payload=fetch(f'wide-bars-{page}','https://data.alpaca.markets/v1beta1/options/bars',params)
            if status!=200:break
            rows.extend({'contract':contract,**row} for contract,items in (payload.get('bars') or {}).items() for row in items)
            token=payload.get('next_page_token')
            if not token:break
            params=params|{'page_token':token}
        else:raise RuntimeError('Incomplete pagination; no boundary conclusion permitted')
        report['bar_count']=len(rows)
        if rows:
            frame=pd.DataFrame(rows)
            frame['local_date']=pd.to_datetime(frame.t,utc=True).dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
            first=frame.local_date.min()
            report['first_observed_session']=first
            report['per_contract']={contract:{'first_session':part.local_date.min(),'bars':len(part)}
                for contract,part in frame.groupby('contract')}
            frame.to_parquet(OUTPUT/'bars.parquet',index=False)
            start=pd.Timestamp(first,tz='America/New_York').tz_convert('UTC')
            prior_params={'symbols':','.join(contracts),'timeframe':'1Day','start':'2023-01-01T00:00:00Z',
                'end':(start-pd.Timedelta(seconds=1)).isoformat(),'limit':10000,'sort':'asc'}
            prior_status,prior=fetch('before-first-session','https://data.alpaca.markets/v1beta1/options/bars',prior_params)
            report['prior_query_http_status']=prior_status
            report['prior_query_bar_count']=sum(len(x) for x in (prior.get('bars') or {}).values())
            minute_params={'symbols':','.join(contracts),'timeframe':'1Min','start':start.isoformat(),
                'end':(start+pd.Timedelta(days=1)-pd.Timedelta(seconds=1)).isoformat(),'limit':10000,'sort':'asc'}
            minute_status,minute=fetch('first-session-minute','https://data.alpaca.markets/v1beta1/options/bars',minute_params)
            timestamps=[x['t'] for items in (minute.get('bars') or {}).values() for x in items]
            report['minute_query_http_status']=minute_status
            report['first_minute_timestamp_observed_utc']=min(timestamps) if timestamps else None
            report['minute_response_paginated']=bool(minute.get('next_page_token'))
        report['status']='BOUNDARY_OBSERVED' if rows else 'NO_HISTORICAL_BARS_RETURNED'
    (OUTPUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    run()
