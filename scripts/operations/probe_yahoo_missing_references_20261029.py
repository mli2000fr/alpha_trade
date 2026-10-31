"""User-requested one-off Yahoo price coverage check; no SQL, batch or orders.

Normal public GET, no login, browser impersonation, host rotation or retry.
Stop on access denial/rate limit; untested symbols remain unknown, not missing.
Yahoo data/automated-use permissions are not granted by this diagnostic.
"""
import csv
from datetime import datetime,timezone,timedelta,date
import hashlib
import json
import math
from pathlib import Path
import time
from urllib.parse import quote
from zoneinfo import ZoneInfo

from common.verified_http import verified_session


SOURCE=Path('artifacts/operations/missing_option_reference_probe/20261029T203331Z/report.json')


def main():
    source=json.loads(SOURCE.read_text(encoding='utf-8'))
    symbols=sorted(source['rows'])
    if len(symbols)!=144 or source['session_date']!='2026-10-28':raise ValueError('Exact previous cohort required')
    day=date.fromisoformat(source['session_date'])
    start=datetime.combine(day,datetime.min.time(),ZoneInfo('America/New_York'))
    params=dict(period1=int(start.timestamp()),period2=int((start+timedelta(days=1)).timestamp()),
        interval='1d',events='div,splits',includeAdjustedClose='true')
    output=Path('artifacts/operations/yahoo_missing_option_reference_probe')/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (output/'raw').mkdir(parents=True,exist_ok=False)
    rows={s:dict(symbol=s,yahoo_symbol=s.replace('.','-'),status='NOT_TESTED',
        previous_eodhd_status=source['rows'][s]['eodhd_status']) for s in symbols}
    report=dict(status='RUNNING',provider='yahoo_finance_chart',purpose='User requested one-off verification of 144 symbols',
        session_date=str(day),source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        started_at_utc=datetime.now(timezone.utc).isoformat(),read_only=True,batches_unchanged=True,
        interval_seconds=1.5,max_symbols=144,params=params,rows=rows,requests_attempted=0)
    print(json.dumps(dict(phase='STARTED',directory=str(output.resolve()),symbols=len(symbols))),flush=True)
    def save():
        from collections import Counter
        report['counts']=dict(Counter(r['status'] for r in rows.values()))
        (output/'progress.json').write_text(json.dumps({k:report[k] for k in ('status','requests_attempted','counts')}),encoding='utf-8')
        (output/'report.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    save()
    failures=0
    with verified_session() as session:
        session.headers['User-Agent']='AlphaTrade-PriceCoverageCheck/1.0'
        for s,row in rows.items():
            report['requests_attempted']+=1
            url='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(row['yahoo_symbol'],safe='')
            try:
                response=session.get(url,params=params,timeout=20)
            except Exception as exc:
                row.update(status='TECHNICAL_ERROR',error_type=type(exc).__name__)
                failures+=1;save()
                if failures>=3:
                    report.update(status='INCOMPLETE_TECHNICAL_ERRORS',stop_reason='Three consecutive transport errors')
                    break
                time.sleep(1.5);continue
            row.update(http_status=response.status_code,received_at_utc=datetime.now(timezone.utc).isoformat())
            try:payload=response.json()
            except ValueError:payload=dict(non_json_body=response.text[:1000])
            (output/'raw'/f'{s}.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
            if response.status_code in (401,403,429):
                row['status']='ACCESS_DENIED' if response.status_code!=429 else 'RATE_LIMITED'
                report.update(status='BLOCKED_PROVIDER',stop_reason='HTTP '+str(response.status_code))
                save();break
            if response.status_code!=200:
                row['status']='NO_PROVIDER_HISTORY' if response.status_code==404 else 'TECHNICAL_HTTP_ERROR'
                failures+=response.status_code!=404
            else:
                failures=0
                chart=payload.get('chart') or {}
                result=chart.get('result') or []
                if chart.get('error') or not result:
                    row.update(status='NO_PROVIDER_HISTORY',provider_error=chart.get('error'))
                elif len(result)!=1:
                    row['status']='MALFORMED_RESPONSE'
                else:
                    result=result[0];meta=result.get('meta') or {}
                    row['metadata']={k:meta.get(k) for k in ('symbol','currency','exchangeName','fullExchangeName',
                        'instrumentType','exchangeTimezoneName','shortName','longName')}
                    timestamps=result.get('timestamp') or []
                    indicators=result.get('indicators') or {}
                    q=(indicators.get('quote') or [{}])[0]
                    adjusted=(indicators.get('adjclose') or [{}])[0].get('adjclose') or []
                    bars=[]
                    for i,ts in enumerate(timestamps):
                        stamp=datetime.fromtimestamp(ts,timezone.utc)
                        if stamp.astimezone(ZoneInfo('America/New_York')).date()!=day:continue
                        bar=dict(date=str(day),timestamp_utc=stamp.isoformat())
                        for k in ('open','high','low','close','volume'):
                            values=q.get(k) or [];bar[k]=values[i] if i<len(values) else None
                        bar['adjusted_close']=adjusted[i] if i<len(adjusted) else None
                        try:
                            op,hi,lo,cl=[float(bar[k]) for k in ('open','high','low','close')]
                            good=all(math.isfinite(v) and v>0 for v in (op,hi,lo,cl)) and lo<=min(op,cl)<=max(op,cl)<=hi
                        except (ValueError,TypeError):good=False
                        bar['valid_ohlc']=good;bars.append(bar)
                    row.update(bars=bars,events=result.get('events'),
                        status='EXACT_J_OHLC' if len(bars)==1 and bars[0]['valid_ohlc'] else
                            'NO_EXACT_J_BAR' if not bars else 'INVALID_OR_DUPLICATE_J_BAR')
                    if meta.get('symbol','').upper()!=row['yahoo_symbol']:
                        row['status']='SYMBOL_IDENTITY_UNQUALIFIED'
            save()
            if report['requests_attempted']%15==0:
                print(json.dumps(dict(phase='PROGRESS',completed=report['requests_attempted'],counts=report['counts'])),flush=True)
            if failures>=3:
                report.update(status='INCOMPLETE_TECHNICAL_ERRORS',stop_reason='Three consecutive technical errors')
                break
            time.sleep(1.5)
    if report['status']=='RUNNING':report['status']='COMPLETED'
    report['completed_at_utc']=datetime.now(timezone.utc).isoformat()
    save()
    with (output/'coverage_144.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        fields=['symbol','yahoo_symbol','status','http_status','previous_eodhd_status','close','volume','currency']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in rows.values():
            bars=row.get('bars') or [{}]
            writer.writerow({**{k:row.get(k) for k in fields[:5]},'close':bars[0].get('close'),
                'volume':bars[0].get('volume'),'currency':row.get('metadata',{}).get('currency')})
    print(json.dumps(dict(phase='FINISHED',status=report['status'],attempted=report['requests_attempted'],
        counts=report['counts'],report=str((output/'report.json').resolve()))),flush=True)


if __name__=='__main__':main()
