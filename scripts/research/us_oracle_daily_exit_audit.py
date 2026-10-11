"""Offline daily-exit opportunity audit. Fixed causal rules, no model or SQL."""
from __future__ import annotations
import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_oracle_amplitude_rerank import checked,read

POLICIES=['HOLD20_SL7','EXIT_AFTER3','EXIT_AFTER5','EXIT_AFTER10','LOSS_AFTER3','WEAKNESS_2_CLOSES','TRAILING_CLOSE20']
LOG=logging.getLogger(__name__)
EPS=1e-12


def simulate(prices,policy):
    """LONG, SL always active; closing signal executes next open, never same close."""
    if policy not in POLICIES: raise ValueError('Unknown policy')
    if prices.shape!=(20,4) or not np.isfinite(prices).all() or (prices<=0).any():
        raise ValueError('Exactly 20 qualified OHLC rows required')
    o,h,l,c=prices.T
    if ((h<np.maximum(o,c))|(l>np.minimum(o,c))|(h<l)).any(): raise ValueError('Incoherent OHLC')
    entry=o[0]
    stop=.93*entry
    pending=False
    highest=entry
    for i in range(20):
        if o[i]<=stop+EPS:
            return dict(exit_session=i+1,exit_reason='STOP_GAP',gross_return=float(o[i]/entry-1),decision_session=None)
        if pending:
            return dict(exit_session=i+1,exit_reason='DAILY_EXIT',gross_return=float(o[i]/entry-1),decision_session=i)
        if l[i]<=stop+EPS:
            return dict(exit_session=i+1,exit_reason='STOP_INTRADAY',gross_return=-.07,decision_session=None)
        highest=max(highest,h[i])
        if i<19:
            if policy.startswith('EXIT_AFTER'):
                pending=i+1==int(policy.removeprefix('EXIT_AFTER'))
            elif policy=='LOSS_AFTER3':
                pending=i+1>=3 and c[i]<entry
            elif policy=='WEAKNESS_2_CLOSES':
                pending=i>=2 and c[i]<entry and c[i]<c[i-1]<c[i-2]
            elif policy=='TRAILING_CLOSE20':
                pending=c[i]<=.8*highest+EPS
    return dict(exit_session=20,exit_reason='EXPIRY_CLOSE',gross_return=float(c[-1]/entry-1),decision_session=None)


def opportunity(prices,baseline):
    """Clairvoyant feasible-open bound, explicitly NOT a causal trading policy."""
    o=prices[:,0]
    entry=o[0]
    stop=.93*entry
    stopped=baseline['exit_reason'].startswith('STOP')
    last=baseline['exit_session']-1 if stopped else 19
    choices=[(i+1,float(o[i]/entry-1)) for i in range(1,last+1) if o[i]>stop+EPS]
    best=max([(baseline['exit_session'],baseline['gross_return'])]+choices,key=lambda x:x[1])
    return dict(daily_exit_feasible_before_stop=bool(stopped and choices),
        ideal_daily_open_return=best[1],ideal_exit_session=best[0],
        ideal_delta=best[1]-baseline['gross_return'])


def evaluate(rows,bars,sessions):
    bars=bars.copy()
    bars['date']=pd.to_datetime(bars.date)
    if bars.duplicated('date').any(): raise ValueError('Duplicate cached bars')
    factor=bars.adj_close.where(bars.adj_close.notna(),bars.close)/bars.close
    raw=bars[['open','high','low','close']].mul(factor,axis=0)
    raw.index=bars.date
    matrix=raw.reindex(sessions).to_numpy(dtype=float)
    output=[]
    for row in rows.to_dict('records'):
        pos=sessions.get_indexer([pd.Timestamp(row['date'])])[0]
        qualified=bool(row['path_qualified']) and pos>=0 and pos+20<len(sessions)
        base=None
        if qualified:
            window=matrix[pos+1:pos+21]
            base=simulate(window,'HOLD20_SL7')
            bound=opportunity(window,base)
        for policy in POLICIES:
            result={**row,'policy':policy,'qualified':qualified}
            if qualified:
                current=base if policy=='HOLD20_SL7' else simulate(window,policy)
                result.update(current,**bound,
                    baseline_return=base['gross_return'],baseline_stop=base['exit_reason'].startswith('STOP'),
                    baseline_stop_session=base['exit_session'] if base['exit_reason'].startswith('STOP') else None,
                    baseline_big_winner=base['gross_return']>=.2-EPS,
                    stop_avoided=base['exit_reason'].startswith('STOP') and not current['exit_reason'].startswith('STOP'),
                    delta_return=current['gross_return']-base['gross_return'],
                    big_winner_return_retained=base['gross_return']>=.2-EPS and current['gross_return']>=.8*base['gross_return'])
            output.append(result)
    return pd.DataFrame(output)


def summarize(frame):
    output=[]
    for n in (10,20,50):
        selected=frame[frame.oracle_pool_rank.le(n)]
        for (source,year,policy),rows in selected.groupby(['source','year','policy']):
            valid=rows[rows.qualified]
            record=dict(source=source,year=int(year),top_n=n,policy=policy,selected=len(rows),qualified=len(valid),coverage=len(valid)/len(rows))
            if len(valid):
                stops=valid[valid.baseline_stop.eq(True)]
                winners=valid[valid.baseline_big_winner.eq(True)]
                record.update(mean_gross_return=float(valid.gross_return.mean()),median_gross_return=float(valid.gross_return.median()),
                    mean_net_10bps=float(valid.gross_return.mean()-.001),mean_net_25bps=float(valid.gross_return.mean()-.0025),
                    mean_delta_pp=float(valid.delta_return.mean()*100),loss_rate=float(valid.gross_return.lt(0).mean()),
                    worst_gross_return=float(valid.gross_return.min()),
                    stop_rate=float(valid.exit_reason.str.startswith('STOP').mean()),
                    baseline_stops=len(stops),big_winners=len(winners),
                    stop_avoided_fraction=float(stops.stop_avoided.astype(float).mean()) if len(stops) else None,
                    baseline_stop_delta_pp=float(stops.delta_return.mean()*100) if len(stops) else None,
                    feasible_daily_exit_fraction_of_stops=float(stops.daily_exit_feasible_before_stop.astype(float).mean()) if len(stops) else None,
                    big_winner_retained_fraction=float(winners.big_winner_return_retained.astype(float).mean()) if len(winners) else None,
                    big_winner_delta_pp=float(winners.delta_return.mean()*100) if len(winners) else None,
                    ideal_bound_delta_pp=float(valid.ideal_delta.mean()*100))
            output.append(record)
    return output


def run(args):
    from modelFactory.oracle.build_labels import nyse_sessions
    source=args.source
    output=args.output
    output.mkdir(parents=True,exist_ok=True)
    directories=sorted(source.glob('chunk-*'))
    if read(source/'report.json')['status']!='COMPLETED_READ_ONLY_PATH_AUDIT': raise ValueError('Corrected audit source required')
    hashes={}
    bounds=[]
    for directory in directories:
        marker=read(directory/'done.json')
        for name in ('paths.parquet','bars.parquet'):
            checked(directory/name,marker[name])
            hashes[str(directory/name)]=marker[name]
        paths=pd.read_parquet(directory/'paths.parquet',columns=['date','oracle_pool_rank'])
        paths=paths[paths.oracle_pool_rank.le(50)]
        if len(paths): bounds.extend([paths.date.min(),paths.date.max()])
    sessions=nyse_sessions(min(bounds).date(),(max(bounds)+pd.Timedelta(days=60)).date())
    protocol=dict(source=str(source),input_hashes=hashes,source_protocol_sha256=digest(source/'protocol.json'),
        code_sha256=digest(__file__),top_n=[10,20,50],side='LONG',stop=.07,tp=None,policies=POLICIES,
        entry='J+1 adjusted opening price',expiry='Close of 20th entry-inclusive NYSE session J+20; not live J+21 open parity',
        timing='Closes observed after session; scheduled exit at NEXT open; active SL has priority on opening gap',
        loss_after3='From close session3 onward, exit next open when close below entry',
        weakness='Close below entry and 2 consecutive declining closes, at earliest close session3',
        trailing='Close <=80% of highest observed high since entry, exit next open; SL7 remains active',
        ideal_bound='Retrospective best feasible exit OPEN after first daily observation before initial stop, or baseline; not a tradable policy',
        cost_scenarios_roundtrip_bps=[10,25],costs='Illustrative fixed bps per notional, not broker-qualified commission or live portfolio costs',
        sensitivity='exclude marked high/low>=1.5 paths, exploratory not price-error certification',
        sql_reads=False,sql_writes=False,training=False,serving_modified=False,
        limitations=['Unit-return diagnostics only: no capital, sizing, overlapping-position constraints or portfolio PnL',
            'Current historical universe and adjustments not independently PIT-certified; 2026 already examined',
            'Second half 2024 missing; no macro/sector features qualified for learned decisions yet',
            'SL assumed touched fill at threshold except opening gaps; intrabar liquidity/slippage not certified',
            'Small fixed rule family not optimization; future optimum ONLY an unattainable bound',
            'No direction/entry abstention learned; all LONG counterfactuals',
            'Potential stop avoidance does not guarantee the model could predict that stop'])
    if (output/'protocol.json').exists() and read(output/'protocol.json')!=protocol: raise ValueError('Resume protocol mismatch')
    atomic_json(output/'protocol.json',protocol)
    parts=[]
    for i,directory in enumerate(directories):
        atomic_json(output/'progress.json',dict(status='RUNNING',phase='daily_exit_rules',completed=i,total=len(directories)))
        destination=output/directory.name
        destination.mkdir(exist_ok=True)
        marker=destination/'done.json'
        if marker.exists():
            checked(destination/'decisions.parquet',read(marker)['decisions.parquet'])
            decisions=pd.read_parquet(destination/'decisions.parquet')
        else:
            rows=pd.read_parquet(directory/'paths.parquet')
            rows=rows[rows.oracle_pool_rank.le(50)]
            bars=pd.read_parquet(directory/'bars.parquet')
            grouped={symbol:part for symbol,part in bars.groupby('symbol')}
            parts_symbol=[evaluate(group,grouped.get(symbol,bars.iloc[:0]),sessions) for symbol,group in rows.groupby('symbol')]
            decisions=pd.concat(parts_symbol,ignore_index=True) if parts_symbol else pd.DataFrame()
            decisions.to_parquet(destination/'decisions.parquet',index=False)
            atomic_json(marker,{'decisions.parquet':digest(destination/'decisions.parquet')})
        if len(decisions): parts.append(decisions)
        LOG.info('Daily exit chunk %d/%d rows=%d',i+1,len(directories),len(decisions))
    frame=pd.concat(parts,ignore_index=True)
    frame['year']=pd.to_datetime(frame.date).dt.year
    frame.to_parquet(output/'decisions.parquet',index=False)
    annual=summarize(frame)
    pd.DataFrame(annual).to_parquet(output/'annual.parquet',index=False)
    sensitivity=frame.copy()
    sensitivity['qualified'] &= ~sensitivity.large_intraday_range_review
    sensitivity_annual=summarize(sensitivity)
    pd.DataFrame(sensitivity_annual).to_parquet(output/'annual_range_sensitivity.parquet',index=False)
    atomic_json(output/'report.json',dict(status='COMPLETED_OFFLINE_DAILY_EXIT_AUDIT',annual=annual,
        sensitivity=sensitivity_annual,limitations=protocol['limitations'],sql_writes=False,training=False,
        note='Next learned-exit model requires separate causal feature/PIT protocol; no automatic promotion'))
    atomic_json(output/'progress.json',dict(status='COMPLETED',completed=len(directories),total=len(directories)))
    LOG.info('Daily exit audit completed: %s',output)


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
