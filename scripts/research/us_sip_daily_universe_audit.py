"""Resumable whole-universe SIP/local comparison; SQL strictly read-only."""
from datetime import date
from pathlib import Path
import argparse
import hashlib
import json
import logging
import time
import numpy as np
import pandas as pd
from sqlalchemy import event
from common.market_calendar import get_market_calendar
from common.universe_files import load_universe_file_symbols,resolve_universe_file_path
from common.verified_http import verified_session
from database.connection import get_sqlalchemy_engine
from service.alpaca.clientAlpaca import _build_headers
from service._http_retry import request_with_retry,RetryPolicy
from service.market.intraday_backfill import atomic_json
from scripts.research.us_prospective_directional_collection_audit import query

FIELDS=('open','high','low','close','volume','vwap')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fetch(session,symbols,start,end,adjustment='split',asof='-'):
    params=dict(symbols=','.join(symbols),timeframe='1Day',feed='sip',adjustment=adjustment,
        asof=asof,start=start+'T00:00:00Z',end=end+'T23:59:59Z',limit=10000,sort='asc')
    rows={symbol:[] for symbol in symbols};seen=set();pages=0
    while True:
        response=request_with_retry(session,'GET','https://data.alpaca.markets/v2/stocks/bars',
            headers=_build_headers('default'),params=params,
            policy=RetryPolicy(max_attempts=3,timeout_seconds=45))
        payload=response.json();pages+=1
        if set(payload.get('bars',{}))-set(symbols):raise ValueError('Unexpected provider symbols')
        for symbol,part in payload.get('bars',{}).items():rows[symbol].extend(part)
        token=payload.get('next_page_token')
        if not token:break
        if token in seen:raise ValueError('Repeated pagination token')
        seen.add(token);params['page_token']=token
        time.sleep(.35)
    return rows,pages


def download(session,symbols,start,end):
    """Isolate invalid symbols, but never hide permission/rate/network failures."""
    try:
        rows,pages=fetch(session,symbols,start,end)
        return dict(bars=rows,errors=[],pages=pages)
    except Exception as exc:
        status=getattr(getattr(exc,'response',None),'status_code',None)
        if status not in (400,404,422):raise
        if len(symbols)==1:
            return dict(bars={},errors=[dict(symbol=symbols[0],http_status=status,error_type=type(exc).__name__)],pages=0)
        mid=len(symbols)//2
        first=download(session,symbols[:mid],start,end)
        second=download(session,symbols[mid:],start,end)
        return dict(bars={**first['bars'],**second['bars']},errors=first['errors']+second['errors'],pages=first['pages']+second['pages'])


def provider_frame(payload):
    records=[dict(symbol=symbol,**bar) for symbol,bars in payload.items() for bar in bars]
    if not records:return pd.DataFrame(columns=['symbol','date',*FIELDS])
    frame=pd.DataFrame(records).rename(columns=dict(o='open',h='high',l='low',c='close',v='volume',vw='vwap'))
    frame['date']=pd.to_datetime(frame.t,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    for field in FIELDS:frame[field]=pd.to_numeric(frame[field],errors='coerce')
    if frame.duplicated(['symbol','date']).any():raise ValueError('Duplicate provider daily bars')
    return frame[['symbol','date',*FIELDS]]


def stats(values):
    values=np.asarray(values,dtype=float);values=values[np.isfinite(values)]
    return dict(n=int(len(values)),mean=float(values.mean()) if len(values) else None,
        median=float(np.median(values)) if len(values) else None,
        p95=float(np.quantile(values,.95)) if len(values) else None,
        p99=float(np.quantile(values,.99)) if len(values) else None,
        maximum=float(values.max()) if len(values) else None)


def price_valid(frame,suffix=''):
    cols=[name+suffix for name in ('open','high','low','close')]
    prices=frame[cols]
    return (np.isfinite(prices).all(axis=1)&prices.gt(0).all(axis=1)
        &frame['high'+suffix].add(1e-6).ge(frame[['open'+suffix,'close'+suffix]].max(axis=1))
        &frame['low'+suffix].sub(1e-6).le(frame[['open'+suffix,'close'+suffix]].min(axis=1)))


def metrics(pairs):
    result=dict(rows=int(len(pairs)))
    for field in ('open','high','low','close'):
        delta=(pairs[field+'_sip']/pairs[field+'_local']-1).abs()*10000
        result[field+'_absolute_bps']=stats(delta)
        result[field+'_above_10bps_pct']=float(delta.gt(10).mean()*100) if len(delta) else None
        result[field+'_above_100bps_pct']=float(delta.gt(100).mean()*100) if len(delta) else None
    share=pairs.volume_sip/pairs.volume_local.where(pairs.volume_local.gt(0))
    result['sip_to_local_volume_ratio']=stats(share)
    result['vwap_absolute_bps']=stats((pairs.vwap_sip/pairs.vwap_local.where(pairs.vwap_local.gt(0))-1).abs()*10000)
    return result


def run(args):
    output=Path(args.output_dir);output.mkdir(parents=True,exist_ok=True)
    protocol_path=output/'protocol.json'
    if protocol_path.exists():
        protocol=json.loads(protocol_path.read_text())
        if any(protocol[k]!=getattr(args,k) for k in ('symbol_source','start_date','end_date')):
            raise ValueError('Protocol mismatch: choose another output directory')
        symbols=protocol['symbols']
    else:
        symbols=sorted(load_universe_file_symbols(args.symbol_source))
        protocol=dict(symbol_source=args.symbol_source,start_date=args.start_date,end_date=args.end_date,
            symbols=symbols,universe_file=str(resolve_universe_file_path(args.symbol_source)),
            universe_sha256=digest(resolve_universe_file_path(args.symbol_source)),chunk_size=25,
            feed='sip',account_id='default',adjustment='split',asof='-',
            local_table='alpha_trade.stock_bars_daily',
            rules='No SQL writes; snapshot before API calls; exclude filled/invalid/non-split/non-session rows from primary price comparison; no missing-day fill; all exclusions archived; no model inference',
            limitations=['Local source is not independent ground truth','Current universe, no historical listing eligibility proof',
                'Split adjustment revisions may differ between collection dates','Missing history is not automatically a provider error'])
        atomic_json(protocol_path,protocol)
    engine=get_sqlalchemy_engine()
    event.listen(engine,'begin',lambda conn:conn.exec_driver_sql('SET TRANSACTION READ ONLY'))
    snapshot=output/'local-bars.parquet'
    if not snapshot.exists():
        parts=[]
        with engine.connect() as conn:
            for offset in range(0,len(symbols),250):
                part=pd.DataFrame(query(conn,'SELECT symbol,date,open,high,low,close,volume,adj_close,vwap,is_filled,data_source,data_adjustment '
                    'FROM stock_bars_daily WHERE symbol IN :symbols AND date BETWEEN :start AND :end',
                    symbols=symbols[offset:offset+250],start=args.start_date,end=args.end_date))
                if not part.empty:parts.append(part)
        if not parts:raise ValueError('Empty local daily table for this universe/period')
        local=pd.concat(parts,ignore_index=True);local['date']=pd.to_datetime(local.date)
        for field in (*FIELDS,'adj_close','is_filled'):local[field]=pd.to_numeric(local[field],errors='coerce')
        local.to_parquet(snapshot,index=False)
        atomic_json(output/'local-snapshot.json',dict(sha256=digest(snapshot),rows=len(local),captured_at_utc=pd.Timestamp.now(tz='UTC').isoformat()))
    local=pd.read_parquet(snapshot)
    if local.duplicated(['symbol','date']).any():raise ValueError('Duplicate local daily bars')
    days=get_market_calendar('US_EQ',allow_us_weekday_fallback=False).session_dates(date.fromisoformat(args.start_date),date.fromisoformat(args.end_date))
    sessions=pd.DatetimeIndex(days)
    chunks=[symbols[i:i+protocol['chunk_size']] for i in range(0,len(symbols),protocol['chunk_size'])]
    session=verified_session();frames=[];errors=[];empty=[]
    for index,chunk in enumerate(chunks):
        cache=output/'cache'/f'chunk-{index:04d}.json';cache.parent.mkdir(parents=True,exist_ok=True)
        if cache.exists():payload=json.loads(cache.read_text())
        else:
            payload=download(session,chunk,args.start_date,args.end_date);atomic_json(cache,payload)
            time.sleep(.4)
        frames.append(provider_frame(payload['bars']));errors.extend(payload['errors'])
        empty.extend(symbol for symbol,rows in payload['bars'].items() if not rows)
        atomic_json(output/'progress.json',dict(status='DOWNLOADING',completed_chunks=index+1,total_chunks=len(chunks),
            requested_symbols=len(symbols),received_symbols=sum(f.symbol.nunique() for f in frames),
            received_bars=sum(len(f) for f in frames),failed_symbols=len(errors),empty_symbols=len(empty)))
        logging.info('SIP chunk %d/%d bars=%d',index+1,len(chunks),sum(len(f) for f in frames))
    sip=pd.concat(frames,ignore_index=True)
    if sip.duplicated(['symbol','date']).any():raise ValueError('Duplicate SIP snapshot')
    sip.to_parquet(output/'sip-bars.parquet',index=False)
    atomic_json(output/'progress.json',dict(status='COMPARING',received_bars=len(sip),requested_symbols=len(symbols)))
    joined=local.merge(sip,on=['symbol','date'],how='outer',suffixes=('_local','_sip'),indicator=True)
    joined['eligible']=joined['_merge'].eq('both')&joined.is_filled.eq(0)&joined.data_adjustment.eq('split')&joined.date.isin(sessions)
    joined['eligible'] &= price_valid(joined,'_local')&price_valid(joined,'_sip')
    for field in ('open','high','low','close'):
        joined[field+'_difference_bps']=(joined[field+'_sip']/joined[field+'_local']-1)*10000
    joined['max_price_difference_bps']=joined[[f+'_difference_bps' for f in ('open','high','low','close')]].abs().max(axis=1)
    joined.to_parquet(output/'comparison-all.parquet',index=False)
    joined[joined['_merge'].ne('both')].to_csv(output/'missing-pairs.csv',index=False)
    joined[~joined.eligible].to_csv(output/'excluded-pairs.csv',index=False)
    eligible=joined[joined.eligible].copy()
    outliers=eligible[eligible.max_price_difference_bps.gt(100)].sort_values('max_price_difference_bps',ascending=False)
    outliers.to_csv(output/'price-outliers-above-1pct.csv',index=False)
    coverage=[]
    for symbol in symbols:
        l=local[local.symbol.eq(symbol)];a=sip[sip.symbol.eq(symbol)]
        part=joined[joined.symbol.eq(symbol)]
        coverage.append(dict(symbol=symbol,local_rows=len(l),sip_rows=len(a),
            local_only=int(part['_merge'].eq('left_only').sum()),sip_only=int(part['_merge'].eq('right_only').sum()),
            eligible_rows=int(part.eligible.sum()),local_first=str(l.date.min().date()) if len(l) else None,
            local_last=str(l.date.max().date()) if len(l) else None,sip_first=str(a.date.min().date()) if len(a) else None,
            sip_last=str(a.date.max().date()) if len(a) else None))
    pd.DataFrame(coverage).to_csv(output/'coverage-by-symbol.csv',index=False)
    symbol_diagnostics=eligible.groupby('symbol').agg(rows=('date','size'),
        outlier_days=('max_price_difference_bps',lambda x:int(x.gt(100).sum())),
        max_price_bps=('max_price_difference_bps','max'),median_close_bps=('close_difference_bps','median')).reset_index()
    symbol_diagnostics.sort_values('max_price_bps',ascending=False).to_csv(output/'price-by-symbol.csv',index=False)
    report=dict(protocol=protocol,local_snapshot_sha256=digest(snapshot),sessions=len(sessions),
        requested_symbols=len(symbols),local_symbols=int(local.symbol.nunique()),sip_symbols=int(sip.symbol.nunique()),
        local_rows=len(local),sip_rows=len(sip),matched_rows=int(joined['_merge'].eq('both').sum()),
        local_only_rows=int(joined['_merge'].eq('left_only').sum()),sip_only_rows=int(joined['_merge'].eq('right_only').sum()),
        failed_symbols=errors,empty_symbols=empty,eligible_rows=len(eligible),
        excluded_matched_rows=int((joined['_merge'].eq('both')&~joined.eligible).sum()),
        local_provenance=local.groupby(['data_source','data_adjustment'],dropna=False).size().reset_index(name='rows').to_dict('records'),
        global_metrics=metrics(eligible),
        by_source={str(source):metrics(part) for source,part in eligible.groupby('data_source',dropna=False)},
        by_month={str(month):metrics(part) for month,part in eligible.groupby(eligible.date.dt.strftime('%Y-%m'))},
        outlier_rows_above_1pct=len(outliers),outlier_symbols=int(outliers.symbol.nunique()),
        largest_outliers=outliers[['symbol','date','data_source','open_local','open_sip','close_local','close_sip','max_price_difference_bps']].head(30).assign(date=lambda x:x.date.astype(str)).to_dict('records'))
    atomic_json(output/'report.json',report)
    atomic_json(output/'progress.json',dict(status='COMPLETED',requested_symbols=len(symbols),sip_symbols=report['sip_symbols'],
        compared_rows=len(eligible),failed_symbols=len(errors),empty_symbols=len(empty)))
    engine.dispose();logging.info('Audit complete %s',output/'report.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--symbol-source',default='universe-file:univers_filtred_tradable.txt')
    parser.add_argument('--start-date',default='2026-01-01');parser.add_argument('--end-date',default='2026-09-30')
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args();logging.basicConfig(level=logging.INFO)
    try:run(args)
    except Exception as exc:
        atomic_json(Path(args.output_dir)/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,
            http_status=getattr(getattr(exc,'response',None),'status_code',None)))
        logging.error('Audit stopped: %s (no credentials or request URLs logged)',type(exc).__name__)
        raise SystemExit(1)
