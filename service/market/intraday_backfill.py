"""Resumable raw intraday backfill (US); explicit per-slice SQL commits."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
import logging
import math
from pathlib import Path
import re
import sys
import time
import uuid
from zoneinfo import ZoneInfo
import requests
from common.market_calendar import get_market_calendar
from common.universe_files import load_universe_file_symbols, resolve_universe_file_path
from database.connection import get_sqlalchemy_engine
from database.intraday_bars import ensure_table, persist_rows
from service.eodhd.clientEodhd import fetch_intraday, EodhdPermissionError, _redact_sensitive_text
from service.eodhd.quota import EodhdQuotaExceeded, EodhdCircuitOpen
from service.eodhd.symbols import to_eodhd
from service.alpaca.intraday_bars import fetch_intraday as fetch_alpaca_intraday, AlpacaIntradayBlocked
from service._http_retry import CircuitOpenError
from common.config_loader import load_config
from common.verified_http import verified_session

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_SOURCE='universe-file:config/univers_batch/univers_filtred_tradable.txt'
INTERVAL_SECONDS={'1m':60,'5m':300,'1h':3600}
LOG=logging.getLogger(__name__)


def intraday_defaults():
    cfg=(load_config() or {}).get('intraday_backfill') or {}
    result=dict(provider=cfg.get('provider','alpaca'),alpaca_feed=cfg.get('alpaca_feed','sip'),
                account_id=cfg.get('account_id','default'))
    if result['provider'] not in ('alpaca','eodhd') or result['alpaca_feed'] != 'sip':
        raise ValueError('Configuration intraday provider/feed invalide')
    if not isinstance(result['account_id'],str) or not result['account_id'].strip():
        raise ValueError('Compte Alpaca intraday invalide')
    return result


def atomic_json(path, value):
    path=Path(path)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,default=str,allow_nan=False),encoding='utf-8')
    try:
        for attempt in range(12):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt==11: raise
                time.sleep(.1*(attempt+1))
    finally:
        temporary.unlink(missing_ok=True)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


@contextmanager
def run_lock(root):
    with (root/'run.lock').open('a+b') as lock:
        try:
            import msvcrt
        except ImportError:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        else:
            lock.seek(0)
            if not lock.read(1):
                lock.seek(0); lock.write(b'0'); lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        yield


def date_slices(start, end, chunk_days=30):
    if end<start or not 1<=chunk_days<=120:
        raise ValueError('Dates invalides ou tranche hors 1..120 jours')
    current=start
    while current<=end:
        stop=min(current+timedelta(days=chunk_days),end+timedelta(days=1))
        yield current, stop  # Local dates, half-open.
        current=stop


def utc_bounds(start,end_exclusive):
    ny=ZoneInfo('America/New_York')
    return tuple(datetime.combine(day,datetime.min.time(),ny).astimezone(timezone.utc)
                 for day in (start,end_exclusive))


def build_plan(start, end, source, interval, chunk_days, *, provider=None, alpaca_feed=None, account_id=None):
    defaults=intraday_defaults()
    provider=provider or defaults['provider']
    alpaca_feed=alpaca_feed or defaults['alpaca_feed']
    account_id=account_id or defaults['account_id']
    if provider not in ('alpaca','eodhd') or alpaca_feed != 'sip':
        raise ValueError('Fournisseur/flux intraday invalide')
    if interval not in INTERVAL_SECONDS: raise ValueError('Intervalle invalide')
    if provider=='eodhd' and interval=='1m' and chunk_days>119:
        raise ValueError('Tranche 1m limitee a 119 jours pour respecter 120 jours UTC lors du changement d heure')
    if end>=datetime.now(ZoneInfo('America/New_York')).date():
        raise ValueError('Fin au plus tard hier New York : pas de séance en cours')
    floor=date(2016,1,4) if provider=='alpaca' else date(2004,1,1) if interval=='1m' else date(2020,10,1)
    if start<floor: raise ValueError(f'Historique {interval} annoncé seulement depuis {floor}')
    symbols=load_universe_file_symbols(source,root=ROOT)
    if not symbols: raise ValueError('Univers vide')
    if any(not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-]{0,19}',s) for s in symbols):
        raise ValueError('Symbole univers invalide')
    if any(not to_eodhd(s).endswith('.US') for s in symbols):
        raise ValueError('Cette collecte est US uniquement : symbole EODHD non US')
    ranges=list(date_slices(start,end,chunk_days))
    path=resolve_universe_file_path(source,root=ROOT)
    plan=dict(version=2,market_code='US_EQ',database='alpha_trade',provider=provider,
        start_date=str(start),end_date=str(end),symbol_source=source,symbols=symbols,
        universe_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),interval=interval,
        chunk_days=chunk_days,ranges=[[str(a),str(b)] for a,b in ranges],
        tasks=len(symbols)*len(ranges),estimated_api_credits=5*len(symbols)*len(ranges) if provider=='eodhd' else None,
        timezone='America/New_York',data_adjustment='raw')
    if provider=='alpaca':plan.update(alpaca_feed=alpaca_feed,account_id=account_id,symbol_mapping='disabled')
    plan['plan_id']='intraday-'+digest(plan)[:20]
    return plan


def normalize_bars(payload, *, symbol, interval, start, end_exclusive, observed, run_id, sessions,
                   data_source='eodhd_intraday',provider_symbol=None,provider='eodhd'):
    """Validate each row. Missing bars never filled; conflicting duplicates rejected."""
    lower,upper=utc_bounds(start,end_exclusive)
    rows,errors,seen={},[],{}
    outside=0
    for index,item in enumerate(payload):
        try:
            timestamp=item.get('timestamp')
            if timestamp is None: raise ValueError('timestamp UTC absent')
            numeric=Decimal(str(timestamp))
            if not numeric.is_finite() or numeric!=numeric.to_integral_value(): raise ValueError('timestamp invalide')
            stamp=datetime.fromtimestamp(int(numeric),timezone.utc)
            if not lower<=stamp<upper:
                outside+=1; continue  # API endpoint boundary overlap; no duplicates across slices.
            values={key:Decimal(str(item[key])) for key in ('open','high','low','close')}
            if any(not x.is_finite() or x<=0 or x>=Decimal('1000000000000') for x in values.values()):
                raise ValueError('OHLC absent/non positif/hors DECIMAL(20,8)')
            values={key:value.quantize(Decimal('.00000001')) for key,value in values.items()}
            if any(x<=0 for x in values.values()):raise ValueError('OHLC arrondi a zero')
            if values['high']<max(values['open'],values['close']) or values['low']>min(values['open'],values['close']):
                raise ValueError('OHLC incoherent')
            volume=Decimal(str(item['volume']))
            if not volume.is_finite() or volume<0 or volume!=volume.to_integral_value() or volume>=2**64:
                raise ValueError('Volume invalide')
            local_day=stamp.astimezone(ZoneInfo('America/New_York')).date()
            bounds=sessions.get(local_day)
            tag='non_trading_day' if bounds is None else (
                'pre_market' if stamp<bounds[0] else 'regular' if stamp<bounds[1] else 'post_market')
            # Economic payload hash excludes retrieval time, so identical re-fetches are true no-ops.
            row=dict(symbol=symbol,bar_timestamp=stamp.replace(tzinfo=None),interval_code=interval,
                data_source=data_source,provider=provider,market_code='US_EQ',provider_symbol=provider_symbol or to_eodhd(symbol),
                bar_end_timestamp=(stamp+timedelta(seconds=INTERVAL_SECONDS[interval])).replace(tzinfo=None),
                trade_date=local_day,session_tag=tag,**values,volume=int(volume),data_adjustment='raw',is_filled=0)
            hash_=digest(row)
            if stamp in seen and seen[stamp]!=hash_: raise ValueError('Versions contradictoires au meme timestamp')
            seen[stamp]=hash_
            row.update(payload_hash=hash_,observed_at=observed,run_id=run_id)
            rows[stamp]=row
        except (KeyError,ValueError,TypeError,OverflowError,InvalidOperation,OSError) as exc:
            errors.append(dict(index=index,error=str(exc)))
            # Do not keep the first of conflicting versions as canonical.
            if 'stamp' in locals() and 'contradictoires' in str(exc): rows.pop(stamp,None)
    conflicting={e['index'] for e in errors if 'contradictoires' in e['error']}
    if conflicting:
        # Reject entire ambiguous response instead of arbitrarily resolving versions.
        return [],errors,outside
    return list(rows.values()),errors,outside


def emit(state):
    print('::alpha_trade_run_summary::'+json.dumps({
        'requested':state.get('total_tasks',0),'received':state.get('received',0),
        'persisted':state.get('persisted',0),'failed':state.get('failed_tasks',0),
        'warning_count':state.get('rejected',0),'status':state.get('status'),
        'details':{'completed_tasks':state.get('completed_tasks',0),'empty_tasks':state.get('empty_tasks',0),
                   'note':'requested=API slices; received/persisted=bars submitted, not new INSERT count'}}),flush=True)


def run(plan, *, refresh=False, sleep_seconds=1., max_tasks=None):
    if not math.isfinite(sleep_seconds) or sleep_seconds<.2: raise ValueError('Pause minimale 0,2 s')
    provider=plan.get('provider','eodhd')
    feed=plan.get('alpaca_feed','sip')
    if provider=='alpaca' and feed!='sip':
        raise ValueError('Ancien plan IEX : créer un nouveau plan SIP ; ne pas réétiqueter ni réutiliser le cache IEX')
    data_source='eodhd_intraday' if provider=='eodhd' else 'alpaca_'+feed
    root=ROOT/('artifacts/eodhd_intraday_backfill' if plan.get('version',1)==1 else 'artifacts/intraday_backfill')/plan['plan_id']
    root.mkdir(parents=True,exist_ok=True)
    with run_lock(root):
        plan_path=root/'plan.json'
        if plan_path.exists() and json.loads(plan_path.read_text(encoding='utf-8'))!=plan:
            raise ValueError('Plan deja present divergent')
        atomic_json(plan_path,plan)
        (root/'tasks').mkdir(exist_ok=True);(root/'raw').mkdir(exist_ok=True)
        state=dict(status='RUNNING',plan_id=plan['plan_id'],total_tasks=plan['tasks'],
            completed_tasks=0,failed_tasks=0,empty_tasks=0,received=0,persisted=0,rejected=0,skipped=0,
            provider=provider,data_source=data_source)
        engine=get_sqlalchemy_engine()
        attempted=0
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        try:
            ensure_table(engine)
            with verified_session() as http:
                for a,b in plan['ranges']:
                    start,stop=date.fromisoformat(a),date.fromisoformat(b)
                    sessions={s.session_date:(s.open_at_utc,s.close_at_utc)
                        for s in calendar.sessions(start,stop) if s.is_open}
                    lower,upper=utc_bounds(start,stop)
                    for symbol in plan['symbols']:
                        key=digest([symbol,a,b,plan['interval']])
                        checkpoint=root/'tasks'/f'{key}.json'
                        previous=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {}
                        if not refresh and previous.get('status') in ('COMPLETED','EMPTY'):
                            state['skipped']+=1
                            state['completed_tasks']+=1
                            state['empty_tasks']+=previous['status']=='EMPTY'
                            state['received']+=previous.get('received',0)
                            state['persisted']+=previous.get('persisted',0)
                            continue
                        if max_tasks is not None and attempted>=max_tasks:
                            state['status']='PAUSED_LIMIT';return finish(root,state)
                        attempted+=1
                        state['current']=dict(symbol=symbol,start=a,end_exclusive=b)
                        atomic_json(root/'progress.json',state)
                        LOG.info('%s %s -> %s (%s)',symbol,a,b,plan['interval'])
                        task=dict(status='FAILED',symbol=symbol,start=a,end_exclusive=b,received=0,persisted=0,rejected=0)
                        try:
                            raw_path=root/'raw'/f'{key}.json.gz'
                            if raw_path.exists() and not refresh:
                                with gzip.open(raw_path,'rt',encoding='utf-8') as stream: archive=json.load(stream)
                            else:
                                provider_symbol=to_eodhd(symbol) if provider=='eodhd' else symbol.removesuffix('.US')
                                if provider=='eodhd':
                                    payload=fetch_intraday(symbol,start_epoch=int(lower.timestamp()),end_epoch=int(upper.timestamp()),
                                        interval=plan['interval'],session=http)
                                else:
                                    payload=fetch_alpaca_intraday(provider_symbol,start_epoch=int(lower.timestamp()),end_epoch=int(upper.timestamp()),
                                        interval=plan['interval'],feed=feed,account_id=plan['account_id'],session=http,
                                        sleep_seconds=sleep_seconds)
                                archive=dict(observed_at=datetime.now(timezone.utc).isoformat(),symbol=symbol,
                                    provider=provider,data_source=data_source,provider_symbol=provider_symbol,
                                    start_utc=lower.isoformat(),end_utc=upper.isoformat(),
                                    interval=plan['interval'],payload=payload)
                                temporary=raw_path.with_name(raw_path.name+'.'+uuid.uuid4().hex+'.tmp')
                                with gzip.open(temporary,'wt',encoding='utf-8') as stream: json.dump(archive,stream)
                                if raw_path.exists():
                                    raw_path.replace(raw_path.with_name(key+'.previous-'+uuid.uuid4().hex+'.json.gz'))
                                temporary.replace(raw_path)
                                time.sleep(sleep_seconds)
                            observed=datetime.fromisoformat(archive['observed_at']).astimezone(timezone.utc).replace(tzinfo=None)
                            rows,errors,outside=normalize_bars(archive['payload'],symbol=symbol,interval=plan['interval'],
                                start=start,end_exclusive=stop,observed=observed,run_id=plan['plan_id'],sessions=sessions,
                                data_source=data_source,provider_symbol=archive.get('provider_symbol'),provider=provider)
                            task.update(received=len(archive['payload']),persisted=persist_rows(engine,rows),
                                rejected=len(errors),outside_window=outside,errors=errors[:100],
                                status='PARTIAL' if errors else 'COMPLETED' if rows else 'EMPTY')
                        except (EodhdPermissionError,EodhdQuotaExceeded,EodhdCircuitOpen,AlpacaIntradayBlocked,CircuitOpenError) as exc:
                            task['error']=_redact_sensitive_text(str(exc))
                            atomic_json(checkpoint,task)
                            state['failed_tasks']+=1;state['error']=task['error'];state['status']='BLOCKED'
                            return finish(root,state)
                        except Exception as exc:
                            task['error']=_redact_sensitive_text(str(exc))
                            LOG.error('Tranche en echec: %s',task['error'])
                        atomic_json(checkpoint,task)
                        state['received']+=task['received'];state['persisted']+=task['persisted'];state['rejected']+=task['rejected']
                        if task['status'] in ('COMPLETED','EMPTY'):
                            state['completed_tasks']+=1;state['empty_tasks']+=task['status']=='EMPTY'
                        else: state['failed_tasks']+=1
                        atomic_json(root/'progress.json',state)
            state['status']='PARTIAL_FAILED' if state['failed_tasks'] else 'COMPLETED'
            return finish(root,state)
        except Exception as exc:
            state.update(status='FAILED',error=_redact_sensitive_text(str(exc)))
            finish(root,state)
            raise
        finally:
            engine.dispose()


def finish(root,state):
    state['updated_at_utc']=datetime.now(timezone.utc).isoformat()
    atomic_json(root/'progress.json',state)
    atomic_json(root/'report.json',state)
    emit(state)
    return state


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-date',type=date.fromisoformat,required=True)
    parser.add_argument('--end-date',type=date.fromisoformat,required=True)
    parser.add_argument('--symbol-source',default=DEFAULT_SOURCE)
    parser.add_argument('--provider',choices=('alpaca','eodhd'),help='Défaut : config.yaml intraday_backfill.provider')
    parser.add_argument('--alpaca-feed',choices=('sip',),help='SIP uniquement, pas de fallback implicite')
    parser.add_argument('--account-id',help='Compte Alpaca, défaut configurable')
    parser.add_argument('--interval',choices=tuple(INTERVAL_SECONDS),default='5m')
    parser.add_argument('--chunk-days',type=int,default=30)
    parser.add_argument('--sleep-seconds',type=float,default=1.)
    parser.add_argument('--max-tasks',type=int)
    parser.add_argument('--refresh',action='store_true',help='Refetch even completed slices; idempotent upsert')
    parser.add_argument('--plan-only',action='store_true',help='No API or SQL')
    parser.add_argument('--expected-plan-id',help='Refuse changed universe/configuration after UI preview')
    args=parser.parse_args()
    if args.max_tasks is not None and args.max_tasks<1:parser.error('max-tasks >=1')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',stream=sys.stdout)
    plan=build_plan(args.start_date,args.end_date,args.symbol_source,args.interval,args.chunk_days,
                    provider=args.provider,alpaca_feed=args.alpaca_feed,account_id=args.account_id)
    if args.expected_plan_id and args.expected_plan_id!=plan['plan_id']:
        parser.error('Plan modifie depuis la previsualisation : recharger univers/options')
    if args.plan_only:
        print(json.dumps(plan,indent=2));return
    result=run(plan,refresh=args.refresh,sleep_seconds=args.sleep_seconds,max_tasks=args.max_tasks)
    if result['status'] in ('FAILED','BLOCKED','PARTIAL_FAILED'):raise SystemExit(1)


if __name__=='__main__':main()
