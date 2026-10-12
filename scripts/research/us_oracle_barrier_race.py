"""Offline descriptive +/-20% target versus 7% stop races; no training/PnL."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_oracle_amplitude_rerank import checked,read

LOG=logging.getLogger(__name__)
TARGET=.20
STOP=.07
EPS=1e-12


def race(window,side):
    """20 bars starting at entry, known opens precede unknown intrabar sequence."""
    if side not in ('LONG','SHORT'): raise ValueError('Invalid side')
    if len(window)!=20: raise ValueError('Exactly 20 entry-inclusive sessions required')
    prices=window[['open','high','low','close']].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or (prices<=0).any(): raise ValueError('Invalid prices')
    o,h,l,c=prices.T
    if ((h<np.maximum(o,c))|(l>np.minimum(o,c))|(h<l)).any(): raise ValueError('Incoherent OHLC')
    entry=o[0]
    sign=1 if side=='LONG' else -1
    tp=entry*(1+sign*TARGET)
    sl=entry*(1-sign*STOP)
    result=dict(entry_price=float(entry),target_price=float(tp),stop_price=float(sl),
        terminal_side_return=float(sign*(c[-1]/entry-1)),outcome='NEITHER',
        conservative_outcome='NEITHER',optimistic_outcome='NEITHER',touch_session=None,
        touch_date=None,opening_side_return=None,gap_stop=False,same_day_ambiguous=False,
        target_touched_ever=bool((h>=tp-EPS).any() if sign==1 else (l<=tp+EPS).any()),
        stop_touched_ever=bool((l<=sl+EPS).any() if sign==1 else (h>=sl-EPS).any()))
    for i in range(20):
        open_target=o[i]>=tp-EPS if sign==1 else o[i]<=tp+EPS
        open_stop=o[i]<=sl+EPS if sign==1 else o[i]>=sl-EPS
        target_hit=h[i]>=tp-EPS if sign==1 else l[i]<=tp+EPS
        stop_hit=l[i]<=sl+EPS if sign==1 else h[i]>=sl-EPS
        if open_target or open_stop:
            outcome='TARGET_FIRST' if open_target else 'STOP_FIRST'
            result.update(outcome=outcome,conservative_outcome=outcome,optimistic_outcome=outcome,
                touch_session=i+1,touch_date=window.index[i],opening_side_return=float(sign*(o[i]/entry-1)),
                gap_stop=bool(open_stop and sign*(o[i]/entry-1)<-STOP-EPS))
            break
        if target_hit or stop_hit:
            ambiguous=bool(target_hit and stop_hit)
            outcome='AMBIGUOUS' if ambiguous else 'TARGET_FIRST' if target_hit else 'STOP_FIRST'
            result.update(outcome=outcome,conservative_outcome='STOP_FIRST' if ambiguous else outcome,
                optimistic_outcome='TARGET_FIRST' if ambiguous else outcome,touch_session=i+1,
                touch_date=window.index[i],same_day_ambiguous=ambiguous)
            break
    return result


def evaluate(selected,bars,sessions):
    bars=bars.copy()
    bars['date']=pd.to_datetime(bars.date)
    if bars.duplicated('date').any(): raise ValueError('Duplicate bars')
    adjusted=bars.adj_close.where(bars.adj_close.notna(),bars.close)/bars.close
    prices=bars[['date','open','high','low','close']].copy()
    prices[['open','high','low','close']]=prices[['open','high','low','close']].mul(adjusted,axis=0)
    prices=prices.set_index('date').reindex(sessions)
    output=[]
    for row in selected.to_dict('records'):
        day=pd.Timestamp(row['date'])
        pos=sessions.get_indexer([day])[0]
        for side in ('LONG','SHORT'):
            flags=row['path_flags'] if not row['path_qualified'] else ''
            if pos<0 or pos+20>=len(sessions): flags='OUTSIDE_CALENDAR'
            detail=dict(side=side,entry_date=sessions[pos+1] if pos>=0 and pos+1<len(sessions) else None,
                terminal_date=sessions[pos+20] if pos>=0 and pos+20<len(sessions) else None,
                qualified=not bool(flags),qualification_flags=flags)
            if not flags:
                detail.update(race(prices.iloc[pos+1:pos+21],side))
            output.append({**row,**detail})
    return pd.DataFrame(output)


def summary(frame):
    rows=[]
    for (source,year,side),part in frame.groupby(['source','year','side']):
        valid=part[part.qualified]
        row=dict(source=source,year=int(year),side=side,selected=len(part),qualified=len(valid),
            coverage=len(valid)/len(part),dates=part.date.nunique())
        if len(valid):
            for outcome in ('TARGET_FIRST','STOP_FIRST','AMBIGUOUS','NEITHER'):
                row[outcome.lower()]=float(valid.outcome.eq(outcome).astype(float).mean())
            row['target_first_conservative']=float(valid.conservative_outcome.eq('TARGET_FIRST').mean())
            row['stop_first_conservative']=float(valid.conservative_outcome.eq('STOP_FIRST').mean())
            row['target_first_optimistic']=float(valid.optimistic_outcome.eq('TARGET_FIRST').mean())
            row['target_touched_ever']=float(valid.target_touched_ever.astype(float).mean())
            row['stop_touched_ever']=float(valid.stop_touched_ever.astype(float).mean())
            row['gap_stop_rate']=float(valid.gap_stop.astype(float).mean())
            stopped=valid[valid.gap_stop.eq(True)]
            row['worst_gap_stop_side_return']=float(stopped.opening_side_return.min()) if len(stopped) else None
            wins=valid[valid.outcome.eq('TARGET_FIRST')]
            losses=valid[valid.conservative_outcome.eq('STOP_FIRST')]
            row['median_target_first_session']=float(wins.touch_session.median()) if len(wins) else None
            row['median_stop_first_session']=float(losses.touch_session.median()) if len(losses) else None
            row['mean_terminal_side_return_neither']=float(valid.loc[valid.outcome.eq('NEITHER'),'terminal_side_return'].mean()) if valid.outcome.eq('NEITHER').any() else None
        rows.append(row)
    return rows


def run(args):
    from modelFactory.oracle.build_labels import nyse_sessions
    output=args.output
    output.mkdir(parents=True,exist_ok=True)
    prior=read(args.source/'report.json')
    if prior['status']!='COMPLETED_READ_ONLY_PATH_AUDIT': raise ValueError('Completed corrected path audit required')
    frames=[]
    hashes={}
    directories=sorted(args.source.glob('chunk-*'))
    for directory in directories:
        marker=read(directory/'done.json')
        for name in ('paths.parquet','bars.parquet'):
            checked(directory/name,marker[name])
            hashes[str(directory/name)]=marker[name]
        frames.append(pd.read_parquet(directory/'paths.parquet'))
    frame=pd.concat(frames,ignore_index=True)
    selected=frame[frame.oracle_pool_rank.le(10)].copy()
    if selected.duplicated(['date','symbol']).any(): raise ValueError('Duplicate frozen selections')
    sessions=nyse_sessions(selected.date.min().date(),(selected.date.max()+pd.Timedelta(days=60)).date())
    protocol=dict(source=str(args.source),source_protocol_sha256=digest(args.source/'protocol.json'),
        input_hashes=hashes,code_sha256=digest(__file__),target=TARGET,stop=STOP,n=10,
        pool='Frozen Oracle TOP20% intersect ATR TOP20%, first 10 by Oracle score',
        sides=['LONG','SHORT'],entry='J+1 adjusted opening price',
        horizon='20 observed NYSE sessions entry-inclusive: J+1 through J+20',
        gap_handling='Known opening barrier crossing wins ordering over later high/low; gap stop may exceed 7%',
        ambiguity='If open inside barriers and both high/low cross, reserve AMBIGUOUS; conservative stop first, optimistic target first',
        target_semantics='Share-price percentage relative to entry; SHORT return = 1-price/entry',
        sensitivity='Exclude paths marked high/low>=1.5; exploratory price-review robustness, not error certification',
        selection='Frozen before future outcomes, missing paths reserved, never replaced',
        sql_writes=False,sql_reads=False,training=False,serving_modified=False,
        limitations=['Daily OHLC cannot establish intrabar ordering or actual fills',
            'Independent LONG and SHORT counterfactuals, no directional model chooses side',
            'No sizing, portfolio limits, spread, commissions, borrow, slippage or PnL',
            'Repeated overlapping title/date paths, not independent trades',
            'No entry gap veto or actual risk-manager eligibility filter',
            'Historical cleaned universe and adjustments, not independently certified PIT prices',
            '2026 already examined; second half 2024 absent',
            'Entry-inclusive 20 sessions is not a sale at J+21 open after 20 elapsed sessions'])
    path=output/'protocol.json'
    if path.exists() and read(path)!=protocol: raise ValueError('Resume protocol mismatch')
    atomic_json(path,protocol)
    parts=[]
    for i,directory in enumerate(directories):
        atomic_json(output/'progress.json',dict(status='RUNNING',phase='barrier_races',completed=i,total=len(directories)))
        result=output/directory.name
        result.mkdir(exist_ok=True)
        marker=result/'done.json'
        if marker.exists():
            checked(result/'races.parquet',read(marker)['races.parquet'])
            races=pd.read_parquet(result/'races.parquet')
        else:
            paths=pd.read_parquet(directory/'paths.parquet')
            paths=paths[paths.oracle_pool_rank.le(10)]
            bars=pd.read_parquet(directory/'bars.parquet')
            grouped={symbol:part for symbol,part in bars.groupby('symbol')}
            races=pd.concat([evaluate(part,grouped.get(symbol,bars.iloc[:0]),sessions)
                for symbol,part in paths.groupby('symbol')],ignore_index=True) if len(paths) else pd.DataFrame()
            races.to_parquet(result/'races.parquet',index=False)
            atomic_json(marker,{'races.parquet':digest(result/'races.parquet')})
        if len(races): parts.append(races)
        LOG.info('Race chunk %d/%d observations=%d',i+1,len(directories),len(races))
    races=pd.concat(parts,ignore_index=True)
    races['year']=pd.to_datetime(races.date).dt.year
    races.to_parquet(output/'races.parquet',index=False)
    annual=summary(races)
    pd.DataFrame(annual).to_parquet(output/'annual.parquet',index=False)
    sensitivity=races.copy()
    sensitivity['qualified'] &= ~sensitivity.large_intraday_range_review
    sensitivity_annual=summary(sensitivity)
    pd.DataFrame(sensitivity_annual).to_parquet(output/'annual_range_sensitivity.parquet',index=False)
    ambiguous=races[races.outcome.eq('AMBIGUOUS')]
    ambiguous.to_parquet(output/'ambiguous.parquet',index=False)
    atomic_json(output/'report.json',dict(status='COMPLETED_OFFLINE_BARRIER_AUDIT',annual=annual,
        range_sensitivity=sensitivity_annual,observations=len(races),qualified=int(races.qualified.sum()),
        ambiguous=len(ambiguous),limitations=protocol['limitations'],training=False,sql_writes=False,
        policy='No training or promotion authorized by descriptive barrier frequencies'))
    atomic_json(output/'progress.json',dict(status='COMPLETED',completed=len(directories),total=len(directories)))
    LOG.info('Barrier race audit complete: %s',output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('artifacts/research/us_amplitude_rerank/path-excursions-h20-20261011-v2'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try: run(args)
    except Exception as exc:
        if args.output.exists(): atomic_json(args.output/'progress.json',dict(status='FAILED',error=str(exc)))
        raise


if __name__=='__main__': main()
