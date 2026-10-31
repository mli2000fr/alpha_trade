"""Bounded READ ONLY check of SIP entitlement cutoffs on the principal account.

GET market data only, no orders or SQL. Archives contain no authentication data.
Five-minute bar times identify the START of the bar; incomplete bars excluded.
"""
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from common.verified_http import verified_session
from service.alpaca.clientAlpaca import _build_headers


def main():
    account='default'
    output=Path('artifacts/operations/alpaca_sip_delay_probe')/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output.mkdir(parents=True,exist_ok=False)
    report=dict(account_id=account,read_only=True,feed='sip',symbols=['AAPL','TXG','SDGR'],
        started_at_utc=datetime.now(timezone.utc).isoformat(),requests=[])
    print(json.dumps(dict(phase='STARTED',directory=str(output.resolve()))),flush=True)
    headers=_build_headers(account)
    with verified_session() as session:
        for seconds in (0,840,899,900,901,960,1200):
            started=datetime.now(timezone.utc)
            end=started-timedelta(seconds=seconds)
            params=dict(symbols=','.join(report['symbols']),feed='sip',timeframe='5Min',adjustment='raw',
                asof='-',sort='asc',limit=10000,start=(started-timedelta(minutes=70)).isoformat(),end=end.isoformat())
            response=session.get('https://data.alpaca.markets/v2/stocks/bars',headers=headers,params=params,timeout=25)
            received=datetime.now(timezone.utc)
            try:payload=response.json()
            except ValueError:payload=dict(non_json_error=response.text[:500])
            (output/f'delay-{seconds}-raw.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
            result=dict(request_delay_seconds=seconds,start_utc=params['start'],end_utc=params['end'],
                requested_at_utc=started.isoformat(),received_at_utc=received.isoformat(),http_status=response.status_code,
                server_date=response.headers.get('Date'),elapsed_seconds=(received-started).total_seconds(),bars=[])
            if response.headers.get('Date'):
                try:result['server_time_minus_requested_end_seconds']=(parsedate_to_datetime(response.headers['Date'])-end).total_seconds()
                except (ValueError,TypeError):pass
            if response.status_code!=200:
                result.update(error_code=payload.get('code'),error_message=payload.get('message',payload.get('non_json_error')))
            else:
                if payload.get('next_page_token'):raise ValueError('Unexpected truncated probe: no complete conclusion')
                bars=payload.get('bars')
                if not isinstance(bars,dict) or set(bars)-set(report['symbols']):raise ValueError('Malformed response')
                for symbol in report['symbols']:
                    rows=bars.get(symbol,[])
                    complete=[r for r in rows if datetime.fromisoformat(r['t'].replace('Z','+00:00'))+timedelta(minutes=5)<=end]
                    last=complete[-1] if complete else None
                    item=dict(symbol=symbol,rows_received=len(rows),complete_bars=len(complete),
                        last_raw_bar_start_utc=rows[-1]['t'] if rows else None,
                        rows_not_complete_by_requested_end=len(rows)-len(complete))
                    if last:
                        bar_start=datetime.fromisoformat(last['t'].replace('Z','+00:00'))
                        bar_end=bar_start+timedelta(minutes=5)
                        item.update(last_completed_start_utc=bar_start.isoformat(),last_completed_end_utc=bar_end.isoformat(),
                            last_completed_end_paris=bar_end.astimezone(ZoneInfo('Europe/Paris')).isoformat(),
                            age_since_bar_end_seconds=(received-bar_end).total_seconds(),
                            close=last['c'],volume=last['v'])
                    result['bars'].append(item)
            report['requests'].append(result)
            print(json.dumps(result),flush=True)
            (output/'progress.json').write_text(json.dumps(dict(completed=len(report['requests']),total=7)),encoding='utf-8')
            if response.status_code in (401,429):break
    report['completed_at_utc']=datetime.now(timezone.utc).isoformat()
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(phase='FINISHED',report=str((output/'report.json').resolve()))),flush=True)


if __name__=='__main__':main()
