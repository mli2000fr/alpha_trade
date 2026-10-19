"""One frozen first-close failed-start exit, not a learned daily model.

Fixed entries/costs and native TP10/SL5. No reinvestment, portfolio PnL, API,
SQL, training or production changes. Prior feature discovery already saw tests.
"""
from datetime import datetime,timezone
from pathlib import Path
import argparse
import logging

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research import us_top10_daily_exit_state_audit as source
from scripts.research import us_top10_three_session_confirmation_audit as independent_scalar
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

SOURCE=Path('artifacts/research/us_top10_daily_exit_state_audit/20261019-v1')
POLICIES=['BASELINE','FAILED_START_FIRST_CLOSE','EXIT_ALL_FIRST_CLOSE']
READ=source.READ
LOG=logging.getLogger(__name__)


def simulate(path,policy,threshold,cost=.0008):
    a=np.asarray(path,dtype=float)
    if policy not in POLICIES or not 0<threshold<.10: raise ValueError('Invalid policy/threshold')
    if a.shape!=(10,4) or not np.isfinite(a).all() or (a<=0).any(): raise ValueError('Ten valid OHLC sessions required')
    if (a[:,1]<np.maximum.reduce([a[:,0],a[:,2],a[:,3]])).any() or (a[:,2]>np.minimum.reduce([a[:,0],a[:,1],a[:,3]])).any():
        raise ValueError('Invalid OHLC')
    entry=a[0,0]; stop=entry*.95; take=entry*1.10
    st=1e-12*abs(stop); tt=1e-12*abs(take)
    pending=False; requested=False; observed_mfe=None
    def result(price,age,outcome,gap=False):
        return dict(entry_price=float(entry),exit_price=float(price),exit_session=age,outcome=outcome,
            net_outcome=source.net_return(price,entry,cost),gap_stop=gap,
            exit_requested=requested,first_close_mfe=observed_mfe,
            native_open_priority=bool(requested and age==2 and outcome in ('SL','TP')),
            daily_exit_executed=outcome=='DAILY_EXIT')
    for i,(op,high,low,close) in enumerate(a):
        if i>0 and op<=stop+st: return result(op,i+1,'SL',True)
        if i>0 and op>=take-tt: return result(take,i+1,'TP')
        if pending: return result(op,i+1,'DAILY_EXIT')
        if low<=stop+st: return result(stop,i+1,'SL')
        if high>=take-tt: return result(take,i+1,'TP')
        if i==0:
            observed_mfe=max(entry,high)/entry-1
            requested=policy=='EXIT_ALL_FIRST_CLOSE' or (policy=='FAILED_START_FIRST_CLOSE' and observed_mfe<threshold)
            pending=requested
    return result(a[-1,3],10,'TIMEOUT')


def paired_interval(frame,days):
    origin=days.searchsorted(pd.Timestamp(f'{int(frame.year.iloc[0])}-01-01'))
    blocks=(days.get_indexer(frame.entry_date)-origin)//20
    totals=pd.DataFrame(dict(block=blocks,delta=frame.delta_net.to_numpy(),n=1)).groupby('block')[['delta','n']].sum()
    interval=[None,None]
    if len(totals)>=5:
        rng=np.random.default_rng(20261019); draws=rng.integers(0,len(totals),size=(2000,len(totals)))
        sampled=totals.to_numpy()[draws].sum(axis=1); values=sampled[:,0]/sampled[:,1]
        interval=[float(x) for x in np.quantile(values,[.025,.975])]
    return dict(delta=float(frame.delta_net.mean()),ci95=interval,blocks=len(totals),method='Entry20-session block ratio bootstrap, per-trade means')


def summarize_pairs(frame,days):
    n=len(frame); base_win=frame.baseline_net.gt(0); base_loss=frame.baseline_net.lt(0)
    changed=frame.delta_net.abs().gt(1e-12); improved=frame.delta_net.gt(1e-12); harmed=frame.delta_net.lt(-1e-12)
    wins=frame.net_outcome.gt(0); gain=frame.loc[wins,'net_outcome']; loss=frame.loc[~wins,'net_outcome']
    return dict(n=n,mean_net=float(frame.net_outcome.mean()),baseline_mean_net=float(frame.baseline_net.mean()),
        delta_mean=float(frame.delta_net.mean()),win_rate=float(wins.mean()),baseline_win_rate=float(base_win.mean()),
        mean_win=float(gain.mean()) if len(gain) else None,mean_loss=float(loss.mean()) if len(loss) else None,
        profit_factor=float(gain.sum()/-loss.sum()) if len(loss) and loss.sum()<0 else None,
        worst=float(frame.net_outcome.min()),requested=int(frame.exit_requested.sum()),
        daily_exits=int(frame.daily_exit_executed.sum()),open_priority=int(frame.native_open_priority.sum()),
        changed=int(changed.sum()),improved=int(improved.sum()),harmed=int(harmed.sum()),
        baseline_losers_helped=int((base_loss&improved).sum()),losers_turned_winners=int((base_loss&wins).sum()),
        baseline_winners_harmed=int((base_win&harmed).sum()),winners_turned_losers=int((base_win&~wins).sum()),
        delta_on_baseline_losers=float(frame.loc[base_loss,'delta_net'].mean()) if base_loss.any() else None,
        delta_on_baseline_winners=float(frame.loc[base_win,'delta_net'].mean()) if base_win.any() else None,
        paired_interval=paired_interval(frame,days))


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json'); verify_hashes(Path('.'),p['sources']); return p
    old=READ(SOURCE/'protocol.json'); audit=READ(SOURCE/'final-audit.json')
    if audit['status']!='PASS_EXPLORATORY_AUDIT_ONLY' or audit['report_sha256']!=digest(SOURCE/'report.json'):
        raise ValueError('Unqualified state audit')
    verify_hashes(Path('.'),old['sources']); verify_hashes(SOURCE,READ(SOURCE/'data-ready.json')['files']); verify_hashes(SOURCE,READ(SOURCE/'report.json')['files'])
    contract=READ(SOURCE/'2024-feature-contract.json'); threshold=contract['features']['mfe_so_far']['cuts'][0]
    files=[Path(__file__),Path('tests/test_us_top10_failed_start_replay.py'),Path(source.__file__),Path(independent_scalar.__file__),
        Path(source.parent.__file__),SOURCE/'protocol.json',SOURCE/'report.json',SOURCE/'final-audit.json',
        SOURCE/'2024-feature-contract.json',SOURCE/'baseline-trades.parquet',SOURCE/'position-states.parquet',Path(old['prices'])]
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in files},
        policies=POLICIES,threshold=threshold,threshold_origin='Exact first2024 weighted MFE tertile, no rounding or retuning',
        rule='Only first surviving entry close: if observed maximum high/entry-1 strictly below threshold, exit next open',
        control='Exit every first surviving entry close next open, to distinguish information from duration',
        side='LONG',tp=.10,sl=.05,holding_sessions=10,entry='Same J+3 opens, no new ranking or entries',
        first_close='Close entry session1, exit open session2 if protection has not already closed the position',
        protections='SL/TP active intraday and gap protections priority next open; no cancelled past stops, no favourable gap TP',
        expiry='Native session10 close; unchanged for positions not exited',costs_per_leg=old['costs_per_leg'],
        prices=old['prices'],price_reserves=old['price_reserves'],identity_events=old['identity_events'],
        independence='Frozen original earliest-first ten-session trade membership across years; no extra reentries from shorter holds',
        validation='2024 is discovery; 2025/26 already examined during feature selection, explicitly NOT independent confirmation',
        interpretation='Matched per-opportunity replay only; no sizing, leverage, portfolio DD, freed-capital reinvestment or live parities claimed',
        sql=False,new_fit=False,api_calls=0,orders=False,production_changes=False,
        reserves=old['reserves']+['MFE hypothesis itself selected after inspecting all three historical years'])
    root.mkdir(parents=True,exist_ok=False); atomic_json(root/'protocol.json',p); return p


def run(root):
    p=READ(root/'protocol.json'); verify_hashes(Path('.'),p['sources'])
    trades=pd.read_parquet(SOURCE/'baseline-trades.parquet'); states=pd.read_parquet(SOURCE/'position-states.parquet')
    first=states[states.holding_age.eq(1)].set_index('trade_id')
    independent=source.parent.previous.execution.base.independent_fast(trades); ids=set(independent.trade_id)
    days=nyse_sessions('2023-01-01','2026-10-09')
    prices=pd.read_parquet(p['prices'],filters=[('symbol','in',sorted(trades.symbol.unique()))])
    groups={str(s):g for s,g in prices.groupby('symbol',observed=True)}; pieces=[]; parity=0
    for symbol,t in trades.groupby('symbol',observed=True):
        positions=days.get_indexer(t.date)
        grid,side,reasons=source.parent.qualify(groups[str(symbol)],days,positions,
            identity_events=p['identity_events'].get(str(symbol),[]),price_reserve=p['price_reserves'].get(str(symbol)))
        assert (side=='LONG').all() and (reasons=='').all()
        for row in t.itertuples():
            start=days.get_loc(row.entry_date); path=grid[['open','high','low','close']].iloc[start:start+10].to_numpy(float)
            for policy in p['policies']:
                current=simulate(path,policy,p['threshold'],p['costs_per_leg'])
                if policy=='BASELINE':
                    assert current['exit_price']==row.exit_price and current['exit_session']==row.exit_session and current['outcome']==row.outcome
                    assert current['net_outcome']==row.net_outcome; parity+=1
                if current['first_close_mfe'] is not None:
                    assert row.trade_id in first.index and abs(current['first_close_mfe']-first.loc[row.trade_id,'mfe_so_far'])<1e-12
                else: assert row.trade_id not in first.index
                pieces.append(dict(trade_id=row.trade_id,date=row.date,year=int(row.year),symbol=str(symbol),side='LONG',policy=policy,
                    entry_date=row.entry_date,last_path_date=row.last_path_date,exit_date=days[start+current['exit_session']-1],
                    baseline_net=row.net_outcome,baseline_outcome=row.outcome,baseline_exit_date=days[start+row.exit_session-1],
                    delta_net=current['net_outcome']-row.net_outcome,independent_trade=row.trade_id in ids,**current))
        if len(pieces)%150==0: LOG.info('Failed-start replay %d rows',len(pieces))
    frame=pd.DataFrame(pieces); frame.to_parquet(root/'matched-trades.parquet',index=False)
    annual=[]
    for (year,policy),g in frame.groupby(['year','policy']):
        for population in ['ALL_TRADES','NONOVERLAPPING_TRADES']:
            f=g if population=='ALL_TRADES' else g[g.independent_trade]
            annual.append(dict(year=int(year),policy=policy,population=population,**summarize_pairs(f,days)))
    pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,dict)} for r in annual]).to_csv(root/'annual-comparison.csv',index=False)
    verify_hashes(Path('.'),p['sources'])
    atomic_json(root/'report.json',dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',protocol_sha256=digest(root/'protocol.json'),
        threshold=p['threshold'],baseline_parity=parity,annual=annual,
        files={n:digest(root/n) for n in ['matched-trades.parquet','annual-comparison.csv']},
        claim='Exactly one first-close decision with next-open protections, fixed matched entries; not independent holdout or annual capital return'))
    atomic_json(root/'progress.json',dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',phase='DONE'))


def audit(root):
    p=READ(root/'protocol.json'); report=READ(root/'report.json'); verify_hashes(Path('.'),p['sources']); verify_hashes(root,report['files'])
    f=pd.read_parquet(root/'matched-trades.parquet'); original=pd.read_parquet(SOURCE/'baseline-trades.parquet')
    first=pd.read_parquet(SOURCE/'position-states.parquet'); first=first[first.holding_age.eq(1)].set_index('trade_id')
    assert report['protocol_sha256']==digest(root/'protocol.json') and len(f)==3*len(original)
    assert not f.duplicated(['trade_id','policy']).any()
    base=f[f.policy.eq('BASELINE')].set_index('trade_id'); assert set(base.index)==set(original.trade_id)
    for row in f.itertuples():
        prior=base.loc[row.trade_id]
        assert row.entry_date==prior.entry_date and row.entry_price==prior.entry_price and row.independent_trade==prior.independent_trade
        scheduled=row.policy=='EXIT_ALL_FIRST_CLOSE' or (row.policy=='FAILED_START_FIRST_CLOSE' and row.trade_id in first.index and first.loc[row.trade_id,'mfe_so_far']<p['threshold'])
        scheduled=bool(scheduled and row.trade_id in first.index)
        assert row.exit_requested==scheduled
        if not scheduled or row.policy=='BASELINE':
            assert row.exit_price==prior.exit_price and row.exit_date==prior.exit_date and row.net_outcome==prior.net_outcome
        else:
            state=first.loc[row.trade_id]
            assert row.exit_date==state.execution_date and row.exit_session==2
            assert abs(row.net_outcome-state.immediate_exit_net)<1e-12
            assert row.native_open_priority==(state.next_open_priority!='NONE')
            assert row.daily_exit_executed==(state.next_open_priority=='NONE')
            if row.native_open_priority: assert row.net_outcome==prior.net_outcome
        assert abs(row.delta_net-(row.net_outcome-row.baseline_net))<1e-12
    # Scalar baseline already audited upstream; independently verify source parity again.
    assert report['baseline_parity']==len(original)
    for result in report['annual']:
        g=f[f.year.eq(result['year'])&f.policy.eq(result['policy'])]
        if result['population']=='NONOVERLAPPING_TRADES': g=g[g.independent_trade]
        assert result['n']==len(g) and abs(result['mean_net']-g.net_outcome.mean())<1e-12
        assert abs(result['delta_mean']-g.delta_net.mean())<1e-12
    answer=dict(status='PASS_EXPLORATORY_REPLAY_ONLY',baseline_parity=len(original),policy_rows=len(f),
        first_close_only=True,entry_costs_and_keys_identical=True,frozen_independent_membership=True,
        no_reinvestment=True,source_state_immediate_exits_reproduced=True,
        protocol_sha256=digest(root/'protocol.json'),report_sha256=digest(root/'report.json'),
        sql=False,new_fit=False,production_changes=False,api_calls=0,
        reserve='Hypothesis chosen after viewing historical tests; no untouched confirmation or capital-return claim')
    atomic_json(root/'final-audit.json',answer); return answer


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','run','audit','all'],default='all'); args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    for name,function in [('prepare',prepare),('run',run),('audit',audit)]:
        if args.phase in ('all',name): value=function(args.output)
    if args.phase in ('audit','all'): print(value)
