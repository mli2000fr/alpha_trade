"""Check exact 144 missing option-discovery references; SQL/HTTP reads only.

Stores diagnostic artifacts and normal EODHD quota accounting, never market
tables, configuration, option selection or broker orders. No IEX substitution.
"""
from collections import Counter
from datetime import datetime,timezone,timedelta,date
import hashlib
import json
import math
from pathlib import Path
import time
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam,event,inspect,text

from common.config_loader import load_config
from common.verified_http import verified_session
from database.connection import get_sqlalchemy_engine
from service.alpaca.clientAlpaca import _build_headers
from service.eodhd.clientEodhd import fetch_eod,EodhdPermissionError,EodhdSymbolNotFound
from service.eodhd.quota import get_default_tracker,EodhdCircuitOpen,EodhdQuotaExceeded


SOURCE=Path('artifacts/operations/options_universe_coverage/20261029T202119Z/report.json')


def valid_ohlc(row,keys):
    try:
        op,hi,lo,cl=[float(row[k]) for k in keys]
        return all(math.isfinite(x) and x>0 for x in (op,hi,lo,cl)) and lo<=min(op,cl)<=max(op,cl)<=hi
    except (ValueError,TypeError,KeyError):return False


def main():
    source=json.loads(SOURCE.read_text(encoding='utf-8'))
    symbols=sorted(r['symbol'] for r in source['missing_snapshots_detail'] if r['reason']=='NO_RECENT_SIP_REFERENCE')
    if len(symbols)!=144 or len(set(symbols))!=144:raise ValueError('Exact 144-symbol cohort required')
    day=date.fromisoformat(source['session_date'])
    root=Path('artifacts/operations/missing_option_reference_probe')/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root.mkdir(parents=True,exist_ok=False)
    (root/'raw').mkdir()
    rows={s:dict(symbol=s,local_rows=[],sip_status='NOT_TESTED',eodhd_status='NOT_TESTED') for s in symbols}
    report=dict(read_only=True,session_date=str(day),started_at_utc=datetime.now(timezone.utc).isoformat(),
        source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),requests=[],rows=rows)
    print(json.dumps(dict(phase='STARTED',symbols=len(symbols),day=str(day),directory=str(root.resolve()))),flush=True)
    def save():
        (root/'progress.json').write_text(json.dumps(dict(
            local_symbols=sum(bool(r['local_rows']) for r in rows.values()),
            sip_status=dict(Counter(r['sip_status'] for r in rows.values())),
            eodhd_status=dict(Counter(r['eodhd_status'] for r in rows.values())))),encoding='utf-8')
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    def readonly(conn,cursor,statement,parameters,context,many):
        if statement.lstrip().split()[0].upper() not in ('SELECT','SHOW','DESCRIBE','SET'):
            raise ValueError('SQL writes forbidden in reference probe')
    event.listen(engine,'before_cursor_execute',readonly)
    columns={c['name'] for c in inspect(engine).get_columns('stock_bars_daily')}
    fields=['symbol','date','open','high','low','close','volume','is_filled','data_source']
    fields += [c for c in ('adjustment','adjustment_type','split_factor','observed_at','available_at','ingestion_at','instrument_id') if c in columns]
    with engine.connect() as conn:
        data=[dict(r) for r in conn.execute(text('SELECT '+','.join(fields)+' FROM stock_bars_daily '
            'WHERE symbol IN :symbols AND date=:day').bindparams(bindparam('symbols',expanding=True)),
            dict(symbols=symbols,day=day)).mappings()]
    for r in data:
        r['valid_ohlc']=valid_ohlc(r,('open','high','low','close')) and not r['is_filled']
        rows[r['symbol']]['local_rows'].append(r)
    save()
    print(json.dumps(dict(phase='LOCAL',symbols=sum(bool(r['local_rows']) for r in rows.values()),
        sources=dict(Counter(r['data_source'] for r in data)))),flush=True)
    engine.dispose()
    with verified_session() as session:
        headers=_build_headers('default')
        start=datetime.combine(day,datetime.min.time(),ZoneInfo('America/New_York'))
        end=start+timedelta(days=1)
        def sip_query(subset):
            params=dict(symbols=','.join(subset),feed='sip',timeframe='1Day',adjustment='raw',asof='-',
                start=start.astimezone(timezone.utc).isoformat(),end=(end-timedelta(microseconds=1)).astimezone(timezone.utc).isoformat(),
                limit=10000,sort='asc')
            try:
                response=session.get('https://data.alpaca.markets/v2/stocks/bars',headers=headers,params=params,timeout=30)
                try:payload=response.json()
                except ValueError:payload=dict(error=response.text[:300])
            except Exception as exc:
                for s in subset:rows[s].update(sip_status='TECHNICAL_ERROR',sip_error=type(exc).__name__)
                return
            idx=len(report['requests'])+1
            (root/'raw'/f'sip-{idx}.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
            report['requests'].append(dict(provider='alpaca_sip',symbols=subset,params=params,http_status=response.status_code))
            if response.status_code in (400,422) and len(subset)>1:
                half=len(subset)//2;sip_query(subset[:half]);sip_query(subset[half:]);return
            if response.status_code!=200:
                for s in subset:rows[s].update(sip_status='HTTP_'+str(response.status_code),sip_error=payload.get('message',payload.get('error')))
                return
            if payload.get('next_page_token'):raise ValueError('Unexpected truncated daily probe')
            bars=payload.get('bars') or {}
            if not isinstance(bars,dict) or set(bars)-set(subset):raise ValueError('Malformed SIP symbols')
            for s in subset:
                matching=[r for r in bars.get(s,[]) if datetime.fromisoformat(r['t'].replace('Z','+00:00')).astimezone(
                    ZoneInfo('America/New_York')).date()==day]
                valid=[r for r in matching if valid_ohlc(r,('o','h','l','c'))]
                if len(valid)==1:rows[s].update(sip_status='EXACT_J_RAW_BAR',sip_bar=valid[0])
                else:rows[s].update(sip_status='NO_EXACT_J_BAR' if not matching else 'INVALID_OR_DUPLICATE_J_BAR')
        for offset in range(0,len(symbols),48):sip_query(symbols[offset:offset+48])
        save()
        print(json.dumps(dict(phase='SIP',status=dict(Counter(r['sip_status'] for r in rows.values())))),flush=True)
        cfg=load_config().get('eodhd',{})
        tracker=get_default_tracker(cache_dir=Path(cfg.get('cache_dir','artifacts/eodhd_cache')))
        feature='missing_option_reference_probe_20261029'
        try:
            tracker.ensure_capacity(estimated_cost=len(symbols),feature=feature)
            stop=None
        except (EodhdCircuitOpen,EodhdQuotaExceeded) as exc:
            stop=type(exc).__name__
            report['eodhd_blocker']=str(exc)
        for index,s in enumerate(symbols,1):
            if stop:
                rows[s]['eodhd_status']='NOT_TESTED_'+stop
                continue
            try:
                result=fetch_eod(s,start=str(day),end=str(day),session=session,tracker=tracker,feature=feature)
                (root/'raw'/f'eodhd-{s}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
                matching=[r for r in result if r.get('date')==str(day)]
                valid=[r for r in matching if valid_ohlc(r,('open','high','low','close'))]
                if len(valid)==1:rows[s].update(eodhd_status='EXACT_J_RAW_BAR',eodhd_bar=valid[0])
                else:rows[s]['eodhd_status']='NO_EXACT_J_BAR' if not matching else 'INVALID_OR_DUPLICATE_J_BAR'
            except EodhdPermissionError as exc:
                rows[s].update(eodhd_status='ACCESS_DENIED',eodhd_error=str(exc))
                stop='ACCESS_DENIED';report['eodhd_blocker']='Provider denied EOD access; remaining requests not sent'
            except EodhdSymbolNotFound:
                rows[s]['eodhd_status']='SYMBOL_NOT_FOUND'
            except (EodhdCircuitOpen,EodhdQuotaExceeded) as exc:
                stop=type(exc).__name__;rows[s].update(eodhd_status=stop,eodhd_error=str(exc))
            except Exception as exc:
                rows[s].update(eodhd_status='TECHNICAL_ERROR',eodhd_error=str(exc)[:500])
            if index%15==0 or index==1:
                save();print(json.dumps(dict(phase='EODHD',completed=index,total=len(symbols),
                    statuses=dict(Counter(r['eodhd_status'] for r in rows.values())))),flush=True)
            time.sleep(.35)
    report['summary']=dict(local_any=sum(bool(r['local_rows']) for r in rows.values()),
        local_valid=sum(any(x['valid_ohlc'] for x in r['local_rows']) for r in rows.values()),
        sip=dict(Counter(r['sip_status'] for r in rows.values())),eodhd=dict(Counter(r['eodhd_status'] for r in rows.values())),
        provider_union=sum(r['sip_status']=='EXACT_J_RAW_BAR' or r['eodhd_status']=='EXACT_J_RAW_BAR' for r in rows.values()))
    report['completed_at_utc']=datetime.now(timezone.utc).isoformat()
    (root/'report.json').write_text(json.dumps(report,default=str,indent=2),encoding='utf-8')
    save()
    print(json.dumps(dict(phase='FINISHED',summary=report['summary'],report=str((root/'report.json').resolve()))),flush=True)


if __name__=='__main__':main()
