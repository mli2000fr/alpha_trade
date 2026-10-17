"""B3 historical Alpaca backfill, explicit feed and per-symbol transactional resume."""
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import argparse
import hashlib
import json
import logging
import math
import re
import pandas as pd
from sqlalchemy import text
from common.config_loader import load_config
from common.market_calendar import get_market_calendar
from core.run_summary import attach_schema_version
from database.connection import SessionLocal
from dataIntegrityEngine.import_eodhd_bar import _get_active_tradable_symbols,_upsert_stock_bars,_upsert_stock_bars_daily
from dataIntegrityEngine.import_alpaca_bar import _build_bar_records
from service.alpaca.daily_history import fetch_daily_history,DailyHistoryBlocked
from service.market.intraday_backfill import atomic_json


LOGGER=logging.getLogger(__name__)


def convert(symbol,bars,feed,start,end):
    qualified=_build_bar_records(symbol,bars,'1D')
    if len(qualified)!=len(bars):raise ValueError('Invalid daily bars: symbol transaction refused')
    daily=[];raw=[];seen=set()
    for original,row in zip(bars,qualified):
        stamp=pd.Timestamp(original['t'])
        if stamp.tzinfo is None:raise ValueError('Missing daily timestamp timezone')
        day=stamp.tz_convert('America/New_York').date()
        if not date.fromisoformat(start)<=day<=date.fromisoformat(end):continue
        if day in seen:raise ValueError('Duplicate daily date')
        seen.add(day)
        prices={key:float(original[key]) for key in ('o','h','l','c')}
        if not all(math.isfinite(x) and x>0 for x in prices.values()):raise ValueError('Invalid daily prices')
        # Match the existing canonical daily key: 09:30 NY and timeframe 1D.
        row={**row,'timestamp':day.isoformat()+' 09:30:00','timeframe':'1D',
             'data_source':'alpaca_'+feed,'data_adjustment':'split'}
        raw.append(row)
        daily.append(dict(symbol=symbol,date=day,open=prices['o'],high=prices['h'],low=prices['l'],close=prices['c'],
            volume=row['volume'],adj_close=prices['c'],vwap=row['vwa_price'],daily_return=None,
            is_filled=0,data_source='alpaca_'+feed,data_adjustment='split'))
    daily.sort(key=lambda row:row['date'])
    for previous,current in zip(daily,daily[1:]):current['daily_return']=current['close']/previous['close']-1
    return daily,raw


def completed_window(years,now=None):
    now=now or datetime.now(timezone.utc)
    local_day=pd.Timestamp(now).tz_convert('America/New_York').date()
    sessions=get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions(local_day-timedelta(days=15),local_day)
    closed=[s.session_date for s in sessions if s.is_open and s.close_at_utc+timedelta(minutes=20)<=now]
    if not closed:raise ValueError('No completed US session')
    end=max(closed)
    start=(pd.Timestamp(end)-pd.DateOffset(years=years)).date()
    return start.isoformat(),end.isoformat()


def run_backfill(*,years=30,symbols=None,dry_run=True,resume=True,feed='sip',account_id='default',
                 output_root=Path('artifacts/alpaca_backfill'),session=None,now=None):
    if not 1<=years<=30 or feed != 'sip':raise ValueError('Invalid history years/feed: SIP required')
    start,end=completed_window(years,now)
    own=session is None;db=session or SessionLocal()
    result=dict(provider='alpaca',feed=feed,mode='dry_run' if dry_run else 'write',start_date=start,end_date=end,
        requested=0,received=0,persisted=0,failed=0,empty=0,symbols_skipped_resumed=0,
        rows_upserted_stock_bars_daily=0,rows_upserted_stock_bars=0,errors=0)
    try:
        if db.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':raise ValueError('US database alpha_trade required')
        universe=sorted(set(s.strip().upper() for s in (symbols or _get_active_tradable_symbols(db)) if s.strip()))
        if any(not re.fullmatch(r'[A-Z0-9][A-Z0-9.-]{0,19}',symbol) for symbol in universe):
            raise ValueError('Invalid US symbol; path characters forbidden')
        result['requested']=len(universe)
        signature=dict(provider='alpaca',feed=feed,account_id=account_id,start=start,end=end,symbols=universe,
            mode=result['mode'],adjustment='split',asof='-')
        identity=hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()[:20]
        output=Path(output_root)/identity;output.mkdir(parents=True,exist_ok=True)
        atomic_json(output/'protocol.json',signature)
        state_path=output/'state.json'
        state=json.loads(state_path.read_text()) if resume and state_path.exists() else dict(completed_symbols=[],empty_symbols=[])
        result['bookmark_path']=str(state_path)
        for symbol in universe:
            if symbol in state['completed_symbols']:
                result['symbols_skipped_resumed']+=1;continue
            cache=output/(symbol+'.json')
            try:
                if resume and cache.exists():bars=json.loads(cache.read_text())
                else:
                    bars=fetch_daily_history(symbol,start=start,end=end,feed=feed,account_id=account_id,now=now)
                    atomic_json(cache,bars)
                daily,raw=convert(symbol,bars,feed,start,end)
                result['received']+=len(daily)
                if not daily:
                    result['empty']+=1
                    state['empty_symbols']=sorted(set([*state['empty_symbols'],symbol]))
                if not dry_run and daily:
                    n_daily=_upsert_stock_bars_daily(db,daily)
                    n_raw=_upsert_stock_bars(db,raw)
                    db.commit()  # Bookmark advances only after both tables commit.
                    result['persisted']+=n_daily
                    result['rows_upserted_stock_bars_daily']+=n_daily
                    result['rows_upserted_stock_bars']+=n_raw
                state['completed_symbols'].append(symbol)
                atomic_json(state_path,state)
            except DailyHistoryBlocked:
                db.rollback();result['failed']+=1;result['stopped_reason']='account_rights_or_quota';break
            except Exception as exc:
                db.rollback();result['failed']+=1
                LOGGER.error('Backfill %s failed: %s',symbol,type(exc).__name__)
            result['errors']=result['failed']
            result['status']='RUNNING'
            atomic_json(output/'progress.json',result)
            LOGGER.info('Backfill %s/%s %s received=%d persisted=%d failed=%d',
                len(state['completed_symbols']),len(universe),symbol,result['received'],result['persisted'],result['failed'])
        result['errors']=result['failed']
        result['status']='FAILED' if result['failed'] else 'PARTIAL' if state['empty_symbols'] else 'COMPLETED'
        result['empty_symbols']=state['empty_symbols']
        atomic_json(output/'progress.json',result);atomic_json(output/'report.json',result)
        return result
    finally:
        if own:db.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--years',type=int,default=30);parser.add_argument('--symbols',nargs='+')
    parser.add_argument('--account',default='default');parser.add_argument('--feed',choices=('sip',))
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--write',action='store_true');mode.add_argument('--dry-run',action='store_true')
    group=parser.add_mutually_exclusive_group();group.add_argument('--resume',dest='resume',action='store_true',default=True)
    group.add_argument('--no-resume',dest='resume',action='store_false')
    args=parser.parse_args(argv);cfg=load_config() or {}
    logging.basicConfig(level=logging.INFO,stream=__import__('sys').stdout)
    result=run_backfill(years=args.years,symbols=args.symbols,dry_run=not args.write,resume=args.resume,
        feed=args.feed or (cfg.get('market_data') or {}).get('alpaca_backfill_feed','sip'),account_id=args.account)
    print('::alpha_trade_run_summary::'+json.dumps(attach_schema_version(result),default=str),flush=True)
    return 1 if result['failed'] else 0


if __name__=='__main__':raise SystemExit(main())
