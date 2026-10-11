"""Resumable ATM option daily bars backfill; inserts only stock_option_bars_delayed.

Historical bar time is never confused with its actual retrieval/availability time.
Raw API responses, plan and checkpoints are archived outside the production DB.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import math
import os
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import text

from common.market_calendar import get_market_calendar
from database.connection import get_sqlalchemy_engine
from service.alpaca.accounts import AccountRegistry
from service.alpaca.clientAlpaca import get_alpaca_credentials
from service.forward_pit.batch import _configure_alpaca_session

LOGGER = logging.getLogger(__name__)
NY = ZoneInfo('America/New_York')
DATA = 'https://data.alpaca.markets'
TABLE = 'alpha_trade.stock_option_bars_delayed'


def atomic_json(path: Path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf-8')
    for attempt in range(12):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 11:
                raise
            time.sleep(.15*(attempt+1))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def failure_limit_reached(statuses, limit):
    if limit < 1:
        raise ValueError('Failure limit must be positive')
    return sum(value.get('status') == 'FAILED' for value in statuses.values()) >= limit


def monthly_ranges(start: date, end: date):
    current = start
    while current <= end:
        next_month = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
        last = min(end, next_month-timedelta(days=1))
        yield current, last
        current = next_month


def select_pairs(contracts, spot, day, targets=(5,10,20), tolerance=5):
    """Select matched, standard-root ATM pairs from a catalog, without future returns."""
    paired = {}
    for item in contracts:
        expiry = date.fromisoformat(item['expiration_date'])
        strike = float(item['strike_price'])
        if expiry <= day or not math.isfinite(strike) or strike <= 0:
            continue
        paired.setdefault((expiry, strike), {})[item['type']] = item
    paired = {key:value for key,value in paired.items() if {'call','put'} <= value.keys()}
    selected = {}
    for target in targets:
        expiries = {expiry for expiry,strike in paired if abs((expiry-day).days-target) <= tolerance}
        if not expiries:
            continue
        expiry = min(expiries, key=lambda x:(abs((x-day).days-target), x))
        strike = min((k[1] for k in paired if k[0]==expiry), key=lambda x:(abs(x-spot),x))
        for item in paired[(expiry,strike)].values():
            selected[item['symbol']] = item
    return list(selected.values())


def normalized_row(contract, item, *, observed, run_id):
    values = {key:float(item[key]) for key in ('o','h','l','c')}
    if not all(math.isfinite(x) and x>0 for x in values.values()):
        raise ValueError('Nonpositive/nonfinite option OHLC')
    if values['h'] < max(values['o'],values['c']) or values['l'] > min(values['o'],values['c']):
        raise ValueError('Inconsistent option OHLC')
    volume = item.get('v')
    trades = item.get('n')
    if volume is None or int(volume)<0 or float(volume)!=int(volume):
        raise ValueError('Missing/invalid option volume')
    if trades is not None and (int(trades)<0 or float(trades)!=int(trades)):
        raise ValueError('Invalid trade count')
    vwap = float(item['vw']) if item.get('vw') is not None else None
    if vwap is not None and (not math.isfinite(vwap) or vwap<=0):
        raise ValueError('Invalid VWAP')
    ts = datetime.fromisoformat(item['t'].replace('Z','+00:00'))
    if ts.tzinfo is None:
        raise ValueError('Bar timestamp has no timezone')
    return {'provider':'alpaca','feed':'historical_default','provenance':'UNVERIFIED_OPRA',
        'underlying':contract['underlying_symbol'],'contract':contract['symbol'],
        'expiry':contract['expiration_date'],'strike':float(contract['strike_price']),
        'otype':contract['type'].upper(),'timeframe':'1Day','ts':ts.astimezone(timezone.utc).replace(tzinfo=None),
        'observed':observed,'open':values['o'],'high':values['h'],'low':values['l'],'close':values['c'],
        'volume':int(volume),'trades':int(trades) if trades is not None else None,
        'vwap':vwap,'hash':digest(item),'run':run_id}


INSERT = text(f'''INSERT IGNORE INTO {TABLE}
    (provider,feed,provenance_status,underlying_symbol,contract_symbol,expiration_date,strike,option_type,
     timeframe,bar_timestamp,observed_at,available_at,open,high,low,close,volume,trade_count,vwap,payload_hash,run_id)
    VALUES (:provider,:feed,:provenance,:underlying,:contract,:expiry,:strike,:otype,:timeframe,:ts,
     :observed,:observed,:open,:high,:low,:close,:volume,:trades,:vwap,:hash,:run)''')


class ArchiveClient:
    def __init__(self, root, session, pause=.4):
        self.root,self.session,self.pause = root,session,pause
        self.requests = 0

    def pages(self, url, params):
        """Page cache preserves original observed_at even when replayed after a crash."""
        records = []
        for _ in range(100):
            key = digest({'url':url,'params':params})
            path = self.root/(key+'.json.gz')
            if path.exists():
                with gzip.open(path,'rt',encoding='utf-8') as stream:
                    record = json.load(stream)
            else:
                for attempt in range(5):
                    response = self.session.get(url,params=params,timeout=(15,90))
                    self.requests += 1
                    if response.status_code in (429,500,502,503,504):
                        if attempt==4:
                            raise RuntimeError(f'HTTP {response.status_code} after retries')
                        time.sleep(min(45, 2**attempt*3))
                        continue
                    if response.status_code!=200:
                        raise RuntimeError(f'HTTP {response.status_code}: {response.text[:250]}')
                    break
                record = {'endpoint':url,'params':params,'observed_at':datetime.now(timezone.utc).isoformat(),
                    'http_status':200,'payload':response.json()}
                temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
                with gzip.open(temporary,'wt',encoding='utf-8') as stream:
                    json.dump(record,stream,separators=(',',':'))
                temporary.replace(path)
                time.sleep(self.pause)
            records.append(record)
            token=record['payload'].get('next_page_token')
            if not token:
                return records
            params=params|{'page_token':token}
        raise RuntimeError('Pagination capped: refuse incomplete task')


def last_completed_session(calendar):
    today=datetime.now(NY).date()
    now=datetime.now(timezone.utc)
    return max(day for day in calendar.session_dates(today-timedelta(days=14),today)
        if calendar.session_bounds(day)[1]+timedelta(minutes=16) <= now)


def run(args):
    root=Path(args.output_dir);root.mkdir(parents=True,exist_ok=True)
    archive=root/'raw';archive.mkdir(exist_ok=True)
    # An OS lock is released automatically after process death; never delete another run's lock.
    lock=(root/'run.lock').open('a+b')
    if os.name=='nt':
        import msvcrt
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        return run_locked(args,root,archive)
    finally:
        lock.close()


def run_locked(args, root, archive):
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    start=date.fromisoformat(args.start_date)
    end=date.fromisoformat(args.end_date) if args.end_date else last_completed_session(calendar)
    if end>last_completed_session(calendar) or start>end:
        raise ValueError('Backfill requires a completed historical range')
    source=Path(args.symbols_file).read_bytes()
    symbols=sorted(set(x.upper() for x in re.split(r'[,;\s]+',source.decode('utf-8-sig').strip()) if x))
    expected={'symbols_file':args.symbols_file,'universe_sha256':hashlib.sha256(source).hexdigest(),
        'symbols':symbols,'start_date':start.isoformat(),'end_date':end.isoformat(),
        'table':TABLE,'timeframe':'1Day','account_id':'default','target_dtes':[5,10,20],'dte_tolerance':5,
        'spot':'historical IEX daily raw close, used only to select ATM strike; not consolidated stock volume',
        'provenance':'UNVERIFIED_OPRA','available_at':'actual archived API retrieval timestamp',
        'contract_filter':'matching standard root, size 100, same-strike call/put pairs',
        'sql_effect':'INSERT IGNORE only; no overwrite/delete/DDL; raw and metadata kept in files'}
    plan_path=root/'plan.json'
    if plan_path.exists():
        if json.loads(plan_path.read_text(encoding='utf-8'))!=expected:
            raise ValueError('Existing plan differs: use identical range/universe or a new output directory')
    else:
        atomic_json(plan_path,expected)
    months=list(monthly_ranges(start,end))
    total=len(months)*len(symbols)
    key,secret=get_alpaca_credentials('default')
    account=AccountRegistry.get().resolve('default')
    broker='https://paper-api.alpaca.markets' if account.mode=='paper' else 'https://api.alpaca.markets'
    engine=get_sqlalchemy_engine()
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
            raise ValueError('Refuse non-US database')
        # Verify idempotency constraint before any insertion.
        indexes=conn.execute(text(f'SHOW INDEX FROM {TABLE}')).mappings().all()
        keys={}
        for item in indexes:
            if item['Non_unique']==0:keys.setdefault(item['Key_name'],[]).append(item['Column_name'])
        identity=['provider','feed','contract_symbol','timeframe','bar_timestamp','payload_hash']
        if identity not in keys.values():raise ValueError('Expected unique identity+hash index missing')
    statuses={}
    for path in (root/'tasks').glob('*.json') if (root/'tasks').exists() else []:
        statuses[path.stem]=json.loads(path.read_text(encoding='utf-8'))
    (root/'tasks').mkdir(exist_ok=True)
    run_id='options-backfill-'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')+'-'+uuid.uuid4().hex[:6]
    processed=0
    def progress(status='RUNNING', current=None):
        done=[v for v in statuses.values() if v.get('status') in ('COMPLETED','EMPTY')]
        failures=[{'task':k,**v} for k,v in statuses.items() if v.get('status')=='FAILED']
        atomic_json(root/'progress.json',{'status':status,'run_id':run_id,'current':current,
            'total_symbol_months':total,'completed_symbol_months':len(done),'failed_symbol_months':len(failures),
            'max_failed_tasks':args.max_failed_tasks,
            'empty_symbol_months':sum(v.get('status')=='EMPTY' for v in done),
            'received':sum(v.get('received',0) for v in done),'persisted':sum(v.get('persisted',0) for v in done),
            'missing_selected_bars':sum(v.get('missing_selected_bars',0) for v in done),
            'requests_this_process':client.requests,'recent_errors':failures[-10:],
            'updated_at':datetime.now(timezone.utc).isoformat()})
    with requests.Session() as session:
        _configure_alpaca_session(session,use_system_trust_store=True)
        session.headers.update({'APCA-API-KEY-ID':key,'APCA-API-SECRET-KEY':secret})
        client=ArchiveClient(archive,session,args.request_interval)
        try:
            progress()
            for month_start,month_end in months:
                days=calendar.session_dates(month_start,month_end)
                if not days:continue
                month=month_start.strftime('%Y-%m')
                remaining=[s for s in symbols if statuses.get(month+'_'+s,{}).get('status') not in ('COMPLETED','EMPTY')]
                if not remaining:continue
                spots={}
                for offset in range(0,len(remaining),100):
                    records=client.pages(DATA+'/v2/stocks/bars',{'symbols':','.join(remaining[offset:offset+100]),
                        'timeframe':'1Day','start':datetime.combine(month_start,datetime.min.time(),NY).isoformat(),
                        'end':datetime.combine(month_end+timedelta(days=1),datetime.min.time(),NY).isoformat(),
                        'adjustment':'raw','feed':'iex','limit':10000,'sort':'asc'})
                    for rec in records:
                        for symbol,items in (rec['payload'].get('bars') or {}).items():
                            for item in items:
                                day=datetime.fromisoformat(item['t'].replace('Z','+00:00')).astimezone(NY).date()
                                spot=float(item['c'])
                                if day in days and math.isfinite(spot) and spot>0:
                                    spots[(symbol,day)]=spot
                for symbol in remaining:
                    task=month+'_'+symbol
                    progress(current=task)
                    try:
                        catalog=[]
                        states=['inactive'] if month_end+timedelta(days=25)<datetime.now(NY).date() else ['inactive','active']
                        for state in states:
                            records=client.pages(broker+'/v2/options/contracts',{'underlying_symbols':symbol,
                                'status':state,'expiration_date_gte':(month_start+timedelta(days=1)).isoformat(),
                                'expiration_date_lte':(month_end+timedelta(days=25)).isoformat(),'limit':1000})
                            catalog.extend(x for r in records for x in r['payload'].get('option_contracts',[])
                                if x.get('root_symbol')==symbol.replace('.','')
                                and x.get('underlying_symbol')==symbol and str(x.get('size')) in ('100','100.0'))
                        catalog=list({x['symbol']:x for x in catalog}.values())
                        daily={day:{x['symbol']:x for x in select_pairs(catalog,spots[(symbol,day)],day)}
                            for day in days if (symbol,day) in spots}
                        chosen={name:item for items in daily.values() for name,item in items.items()}
                        rows=[];seen=set();rejected=0
                        names=sorted(chosen)
                        for offset in range(0,len(names),100):
                            records=client.pages(DATA+'/v1beta1/options/bars',{'symbols':','.join(names[offset:offset+100]),
                                'timeframe':'1Day','start':datetime.combine(month_start,datetime.min.time(),NY).isoformat(),
                                'end':datetime.combine(month_end+timedelta(days=1),datetime.min.time(),NY).isoformat(),
                                'limit':10000,'sort':'asc'})
                            for rec in records:
                                observed=datetime.fromisoformat(rec['observed_at']).astimezone(timezone.utc).replace(tzinfo=None)
                                for name,items in (rec['payload'].get('bars') or {}).items():
                                    for item in items:
                                        day=datetime.fromisoformat(item['t'].replace('Z','+00:00')).astimezone(NY).date()
                                        if name not in daily.get(day,{}) or (name,day) in seen:continue
                                        try:row=normalized_row(chosen[name],item,observed=observed,run_id=run_id)
                                        except (ValueError,KeyError,TypeError):rejected+=1;continue
                                        rows.append(row);seen.add((name,day))
                        persisted=0
                        if args.write:
                            for offset in range(0,len(rows),200):
                                with engine.begin() as conn:
                                    result=conn.execute(INSERT,rows[offset:offset+200])
                                    persisted+=max(0,result.rowcount)
                        missing=sum(len(x) for x in daily.values())-len(seen)
                        # Missing spots are explicit. No empty task silently masquerades as full coverage.
                        result={'status':'COMPLETED' if rows else 'EMPTY','received':len(rows),'persisted':persisted,
                            'catalog_contracts':len(catalog),'selected_contracts':len(chosen),
                            'session_count':len(days),'missing_spot_days':len(days)-len(daily),
                            'missing_selected_bars':missing,'rejected_bars':rejected,'write':args.write,
                            'reason':None if rows else ('NO_RAW_IEX_SPOT' if not daily else 'NO_SELECTED_BARS_OR_STANDARD_PAIRS')}
                        statuses[task]=result
                        if args.write:atomic_json(root/'tasks'/f'{task}.json',result)
                        LOGGER.info('%s rows=%s inserted=%s missing=%s completed=%s/%s',task,len(rows),persisted,missing,
                            sum(v.get('status') in ('COMPLETED','EMPTY') for v in statuses.values()),total)
                    except Exception as exc:
                        result={'status':'FAILED','error_type':type(exc).__name__,'error':str(exc)[:500]}
                        statuses[task]=result
                        if args.write:atomic_json(root/'tasks'/f'{task}.json',result)
                        LOGGER.exception('Task failed %s',task)
                        if 'HTTP 401' in str(exc) or 'HTTP 403' in str(exc):raise
                    processed+=1;progress()
                    if args.max_tasks and processed>=args.max_tasks:
                        progress(status='PAUSED_LIMIT');return
                    if failure_limit_reached(statuses,args.max_failed_tasks):
                        raise RuntimeError(f'{args.max_failed_tasks} failed tasks: configured stop threshold reached')
            final='PARTIAL_FAILED' if any(v.get('status')=='FAILED' for v in statuses.values()) else 'COMPLETED'
            progress(status=final)
            atomic_json(root/'report.json',json.loads((root/'progress.json').read_text(encoding='utf-8')))
        except Exception:
            progress(status='FAILED');raise
        finally:
            engine.dispose()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols-file',default='config/univers_batch/univers_filtred_tradable.txt')
    parser.add_argument('--start-date',default='2024-01-20')
    parser.add_argument('--end-date')
    parser.add_argument('--output-dir',default='artifacts/research/alpaca_options_history/backfill-20240120-20261009-v1')
    parser.add_argument('--request-interval',type=float,default=.4)
    parser.add_argument('--max-tasks',type=int,default=0)
    parser.add_argument('--max-failed-tasks',type=int,default=1000,
        help='Stop at this total of unresolved failed symbol/month tasks, not consecutive failures')
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    if args.max_failed_tasks < 1:
        parser.error('--max-failed-tasks must be positive')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if not args.write:
        raise ValueError('Explicit --write required: use tests to validate transformations without persistence')
    run(args)


if __name__=='__main__':
    main()
