"""One bounded historical DATA read per already configured account; no orders."""
from pathlib import Path
from datetime import datetime,timezone
from common.verified_http import verified_session
from service.alpaca.clientAlpaca import _build_headers
from scripts.research.us_concentrated_historical_tapes import atomic_json

ROOT=Path('artifacts/research/us_q051_features173/20261116-v3-sip')

if __name__=='__main__':
    params=dict(symbols='DD',timeframe='1Day',feed='sip',adjustment='split',asof='-',
        start='2019-03-22T00:00:00Z',end='2026-10-02T00:00:00Z',limit=10000,sort='asc')
    results=[]
    with verified_session() as session:
        for account in ['test1','test2']:
            response=session.get('https://data.alpaca.markets/v2/stocks/bars',headers=_build_headers(account),params=params,timeout=(10,45))
            row=dict(account=account,status=response.status_code);results.append(row)
            if response.status_code==200:
                payload=response.json()
                if payload.get('next_page_token'):raise ValueError('Truncated probe')
                atomic_json(ROOT/'evidence/DD.json',dict(status='COMPLETED',symbol='DD',params=params,body=payload,
                    account_id=account,observed_at_utc=datetime.now(timezone.utc).isoformat(),http_status=200))
                break
    atomic_json(ROOT/'account-data-access.json',dict(results=results,endpoint='historical_daily_bars',broker_calls=0))
    print(results)
