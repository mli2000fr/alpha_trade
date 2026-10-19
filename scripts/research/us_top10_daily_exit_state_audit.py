"""Daily LONG position-state audit, no fitting or new executable exit strategy.

Four-close Oracle H10 TOP10, entry J+3, existing TP10/SL5 and ten-session expiry.
Only past/current OHLCV features; future counterfactual labels kept separate.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import logging

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research import us_top10_four_session_confirmation as parent
from scripts.research import us_top10_confirmation_protection_grid as protection
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

SOURCE=Path('artifacts/research/us_top10_four_session_confirmation/20261019-v1')
READ=parent.previous.prior.read
FEATURES=['holding_age','current_pnl','mfe_so_far','mae_so_far','giveback_atr',
    'return_1d','return_3d','return_5d','momentum_change_3d','relative_spy_1d','relative_spy_3d','relative_spy_5d',
    'volume_ratio_20','down_volume_pressure','close_location','prior3low_distance_atr','atr20_pct','atr5_over20',
    'distance_sl_atr','distance_tp_atr']
LABELS=['exit_advantage_remaining','exit_advantage_next3']
LOG=logging.getLogger(__name__)


def finite_float(value):
    return float(value) if np.isfinite(value) else None


def price_features(grid,spy):
    """Prefix-causal features. Historical windows are not truncated to trade entry."""
    f=pd.DataFrame(index=grid.index)
    o,h,l,c=[pd.to_numeric(grid[k],errors='coerce') for k in ('open','high','low','close')]
    v=pd.to_numeric(grid.volume,errors='coerce')
    valid=(np.isfinite(pd.concat([o,h,l,c],axis=1)).all(axis=1)&(o>0)&(h>0)&(l>0)&(c>0)
        & h.ge(pd.concat([o,l,c],axis=1).max(axis=1)) & l.le(pd.concat([o,h,c],axis=1).min(axis=1))
        & v.gt(0) & grid.is_filled.eq(0))
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1).where(valid)
    atr=tr.rolling(20,min_periods=20).mean()
    history=valid.astype(int).rolling(21,min_periods=21).sum().eq(21)
    # Adjacent metadata changes invalidate windows; no forward filling.
    for field in ('instrument_id','data_source','data_adjustment'):
        codes=pd.Series(pd.factorize(grid[field])[0],index=grid.index,dtype=float)
        history &= codes.rolling(21,min_periods=21).min().eq(codes.rolling(21,min_periods=21).max()) & codes.ge(0)
        if field!='instrument_id':
            known=~grid[field].astype(str).str.upper().isin(['UNKNOWN','','NAN','NONE'])
            history &= known.astype(int).rolling(21,min_periods=21).sum().eq(21)
    atr=atr.where(history & atr.gt(0)); f['atr']=atr
    for n in (1,3,5):
        ret=c/c.shift(n)-1
        supported=valid.astype(int).rolling(n+1,min_periods=n+1).sum().eq(n+1)
        f[f'return_{n}d']=ret.where(supported)
        f[f'relative_spy_{n}d']=f[f'return_{n}d']-spy/spy.shift(n)+1
    f['momentum_change_3d']=f.return_3d-f.return_3d.shift(3)
    f['volume_ratio_20']=(v/v.shift().rolling(20,min_periods=20).mean()).where(history)
    f['down_volume_pressure']=(-f.return_1d).clip(lower=0)*f.volume_ratio_20
    f['close_location']=((c-l)/(h-l)).where(valid & h.gt(l))
    f['prior3low_distance_atr']=(c-l.shift().rolling(3,min_periods=3).min())/atr
    f['atr20_pct']=atr/c
    f['atr5_over20']=tr.rolling(5,min_periods=5).mean()/atr
    return f.replace([np.inf,-np.inf],np.nan).where(history,axis=0)


def net_return(exit_price,entry,cost=.0008):
    return exit_price/entry-1-cost*(1+exit_price/entry)


def trade_states(row,grid,features,days,cost=.0008):
    """A state exists only AFTER surviving today's TP/SL, before forced expiry.

    The immediate-next-open counterfactual preserves gap protections. A future
    opening protection makes the decision ineffective, not a deleted bad state.
    """
    start=days.get_loc(row.entry_date); last=days.get_loc(row.last_path_date)
    exit_pos=start+int(row.exit_session)-1; entry=float(row.entry_price)
    if last!=start+9 or exit_pos>last: raise ValueError('Unexpected baseline expiry')
    prices=grid[['open','high','low','close']].to_numpy(float)
    if not np.isfinite(prices[start:last+1]).all(): raise ValueError('Unqualified baseline path')
    stop=entry*.95; take=entry*1.10; states=[]
    for age in range(1,int(row.exit_session)):
        current=start+age-1; nxt=current+1
        op=float(prices[nxt,0]); priority='NONE'
        if op<=stop+abs(stop)*1e-12: immediate=op; priority='SL_GAP'
        elif op>=take-abs(take)*1e-12: immediate=take; priority='TP_AT_OPEN'
        else: immediate=op
        until=min(current+3,last)
        keep3=float(row.exit_price) if exit_pos<=until else float(prices[until,3])
        close=float(prices[current,3]); high=max(entry,float(prices[start:current+1,1].max()))
        low=min(entry,float(prices[start:current+1,2].min()))
        obs=features.iloc[current]; atr=float(obs.atr)
        atr_ok=np.isfinite(atr) and atr>0
        state=dict(trade_id=f'{pd.Timestamp(row.date).date()}:{row.symbol}',symbol=str(row.symbol),
            signal_date=row.date,signal_year=int(row.year),entry_date=row.entry_date,state_date=days[current],
            execution_date=days[nxt],label_available_date=days[last+1],baseline_exit_date=days[exit_pos],
            last_path_date=row.last_path_date,holding_age=age,remaining_sessions=10-age,
            current_pnl=close/entry-1,mfe_so_far=high/entry-1,mae_so_far=1-low/entry,
            giveback_atr=(high-close)/atr if atr_ok else np.nan,
            distance_sl_atr=(close-stop)/atr if atr_ok else np.nan,distance_tp_atr=(take-close)/atr if atr_ok else np.nan,
            immediate_exit_net=net_return(immediate,entry,cost),keep_remaining_net=float(row.net_outcome),
            keep_next3_net=net_return(keep3,entry,cost),next_open_priority=priority,
            baseline_stopped=bool(row.sl_first),baseline_winner=bool(row.net_outcome>0))
        for column in FEATURES:
            if column in obs.index: state[column]=float(obs[column])
        state['exit_advantage_remaining']=state['immediate_exit_net']-state['keep_remaining_net']
        state['exit_advantage_next3']=state['immediate_exit_net']-state['keep_next3_net']
        states.append(state)
    return states


def weighted_mean(values,weights):
    v=np.asarray(values,dtype=float); w=np.asarray(weights,dtype=float)
    good=np.isfinite(v)&np.isfinite(w)&(w>0)
    return float(np.average(v[good],weights=w[good])) if good.any() else None


def weighted_quantiles(values,weights):
    order=np.argsort(np.asarray(values),kind='stable'); v=np.asarray(values)[order]; w=np.asarray(weights)[order]
    good=np.isfinite(v)&np.isfinite(w)&(w>0); v=v[good]; w=w[good]
    if not len(v): return []
    mass=(w.cumsum()-.5*w)/w.sum()
    return sorted(set(float(x) for x in np.interp([1/3,2/3],mass,v)))


def cut_bins(values,thresholds):
    return np.searchsorted(np.asarray(thresholds),np.asarray(values,dtype=float),side='right')


def discovery_states(states):
    return states[states.signal_year.eq(2024)&states.state_date.lt('2025-01-01')&states.label_available_date.lt('2025-01-01')]


def context_delta(frame,mask,label):
    """Tail-v-rest comparison within fixed age/PnL strata, not a fitted model."""
    parts=[]
    for _,g in frame.groupby('context',observed=True):
        a=g[mask.reindex(g.index)]; b=g[~mask.reindex(g.index)]
        if a.trade_id.nunique()<3 or b.trade_id.nunique()<3: continue
        diff=weighted_mean(a[label],a.weight)-weighted_mean(b[label],b.weight)
        parts.append((diff,float(a.weight.sum())))
    return float(np.average([v for v,w in parts],weights=[w for v,w in parts])) if parts else None


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json'); verify_hashes(Path('.'),p['sources']); return p
    source=READ(SOURCE/'protocol.json'); audit=READ(SOURCE/'final-audit.json')
    if audit['status']!='PASS_EXPLORATORY_ONLY' or audit['report_sha256']!=digest(SOURCE/'report.json'):
        raise ValueError('Unqualified source')
    verify_hashes(Path('.'),source['sources']); verify_hashes(SOURCE,READ(SOURCE/'report.json')['files'])
    files=[Path(__file__),Path('tests/test_us_top10_daily_exit_state_audit.py'),Path(parent.__file__),Path(protection.__file__),
        Path(parent.previous.execution.base.__file__),SOURCE/'protocol.json',SOURCE/'final-audit.json',SOURCE/'report.json',
        SOURCE/'evaluations.parquet',Path(source['prices'])]
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in files},
        side='LONG',tp=.10,sl=.05,holding_sessions=10,trailing=False,
        population='Same four-close confirmed LONG H10 TOP10 entries J+3; no new selection or re-entry',
        state='Only closes before native TP/SL/expiry; first possible decision at entry close; execute next open',
        gap_priority='Opening SL/TP remains prior to daily exit, ineffective decisions retained with zero advantage',
        labels=LABELS,label_definition='Exit now at next open net minus keep net; remaining baseline and next3 sessions with same hard barriers/expiry',
        features=FEATURES,events='News/consensus/sector PIT not injected; no certified historical vintages provided for this cohort',
        discovery='Signal year2024, state before2025 and full window label available strictly before2025-01-01',
        validation='Signal years2025 and2026 through Sep1; historical years already examined, not untouched holdout',
        bins='Weighted tertiles fitted on2024 only, weight1/states per position; low/high tail direction chosen on2024 only',
        independence='Same earliest-first nonoverlap per symbol/side as source, full ten-session windows',
        context='Age1-2/3-5/6-9 times PnL negative/nonnegative; compare tail/rest only with at least3 trades each stratum',
        interpretation='Univariate/temporal stability audit, no trained estimator, new exit policy, portfolio PnL or promotion',
        costs_per_leg=source['costs_per_leg'],prices=source['prices'],price_reserves=source['price_reserves'],identity_events=source['identity_events'],
        sql=False,new_fit=False,api_calls=0,orders=False,production_changes=False,
        reserves=source['reserves']+['20 features times2 labels and several diagnostic views, no multiple-test corrected discovery'])
    root.mkdir(parents=True,exist_ok=False); atomic_json(root/'protocol.json',p); return p


def build(root):
    p=READ(root/'protocol.json'); verify_hashes(Path('.'),p['sources'])
    if (root/'data-ready.json').exists(): verify_hashes(root,READ(root/'data-ready.json')['files']); return
    trades=pd.read_parquet(SOURCE/'evaluations.parquet'); trades=trades[trades.side.eq('LONG')&trades.direction.eq('LONG')].copy()
    trades['trade_id']=trades.date.dt.strftime('%Y-%m-%d')+':'+trades.symbol
    independent=parent.previous.execution.base.independent_fast(trades)
    ind_ids=set(independent.trade_id)
    days=nyse_sessions('2023-01-01','2026-10-09')
    symbols=sorted(set(trades.symbol)|{'SPY'})
    raw=pd.read_parquet(p['prices'],filters=[('symbol','in',symbols)])
    groups={str(s):g for s,g in raw.groupby('symbol',observed=True)}
    spy_raw=groups['SPY'].set_index('date').reindex(days)
    spy=pd.to_numeric(spy_raw.adj_close,errors='coerce').where(spy_raw.is_filled.eq(0)&spy_raw.volume.gt(0))
    states=[]
    for i,(symbol,t) in enumerate(trades.groupby('symbol',observed=True),1):
        pos=days.get_indexer(t.date)
        grid,direction,reason=parent.qualify(groups[str(symbol)],days,pos,
            identity_events=p['identity_events'].get(str(symbol),[]),price_reserve=p['price_reserves'].get(str(symbol)))
        assert (reason=='').all() and (direction=='LONG').all()
        f=price_features(grid,spy)
        for event in p['identity_events'].get(str(symbol),[]):
            positions=np.arange(len(days)); starts=np.maximum(0,positions-20)
            crosses=(days>=pd.Timestamp(event['first_successor_date'])) & (days[starts]<=pd.Timestamp(event['last_predecessor_date']))
            f.loc[crosses,:]=np.nan
        for row in t.itertuples(): states.extend(trade_states(row,grid,f,days,p['costs_per_leg']))
        if i%25==0:
            LOG.info('Daily states %d symbols, %d rows',i,len(states))
            atomic_json(root/'progress.json',dict(status='RUNNING',phase='DAILY_STATES',symbols=i,states=len(states)))
    s=pd.DataFrame(states)
    s['independent_trade']=s.trade_id.isin(ind_ids)
    s['weight']=1/s.groupby('trade_id').trade_id.transform('size')
    s['context']=pd.cut(s.holding_age,[0,2,5,9],labels=['AGE1_2','AGE3_5','AGE6_9']).astype(str)+'_'+np.where(s.current_pnl.lt(0),'NEG','NONNEG')
    s.to_parquet(root/'position-states.parquet',index=False); trades.to_parquet(root/'baseline-trades.parquet',index=False)
    verify_hashes(Path('.'),p['sources'])
    atomic_json(root/'data-ready.json',dict(files={n:digest(root/n) for n in ['position-states.parquet','baseline-trades.parquet']},
        baseline_trades=len(trades),states=len(s),trades_with_states=s.trade_id.nunique(),independent_baseline_trades=len(independent)))


def analyze(root):
    p=READ(root/'protocol.json'); verify_hashes(Path('.'),p['sources']); ready=READ(root/'data-ready.json'); verify_hashes(root,ready['files'])
    s=pd.read_parquet(root/'position-states.parquet'); trades=pd.read_parquet(root/'baseline-trades.parquet')
    discovery=discovery_states(s)
    contracts={}; bins=[]; feature_rows=[]; yearly=[]
    for feature in FEATURES:
        d=discovery[np.isfinite(discovery[feature])].copy()
        cuts=weighted_quantiles(d[feature],d.weight)
        contracts[feature]=dict(cuts=cuts,n=len(d),trades=d.trade_id.nunique(),tails={})
        d['bin']=cut_bins(d[feature],cuts)
        for label in LABELS:
            means={int(k):weighted_mean(g[label],g.weight) for k,g in d.groupby('bin')}
            low=0; high=len(cuts)
            chosen=low if means.get(low,-np.inf)>=means.get(high,-np.inf) else high
            contracts[feature]['tails'][label]=dict(bin=chosen,discovery_mean_exit_advantage=means.get(chosen),
                auc_orientation=1 if weighted_mean(d[label],d.weight) is None or len(d[label].unique())<2 else (
                    1 if len(np.unique(d[label].gt(1e-12)))<2 or roc_auc_score(d[label].gt(1e-12),d[feature],sample_weight=d.weight)>=.5 else -1))
        for population in ('ALL_STATES','NONOVERLAPPING_TRADES'):
            for year in (2024,2025,2026):
                all_year=discovery if year==2024 else s[s.signal_year.eq(year)]
                if population=='NONOVERLAPPING_TRADES': all_year=all_year[all_year.independent_trade]
                f=all_year[np.isfinite(all_year[feature])].copy(); f['bin']=cut_bins(f[feature],cuts)
                for label in LABELS:
                    tail_contract=contracts[feature]['tails'][label]; selected=f.bin.eq(tail_contract['bin'])
                    tail=f[selected]; rest=f[~selected]
                    auc=None
                    if len(f) and f[label].gt(1e-12).nunique()==2:
                        auc=float(roc_auc_score(f[label].gt(1e-12),f[feature]*tail_contract['auc_orientation'],sample_weight=f.weight))
                    feature_rows.append(dict(feature=feature,label=label,population=population,year=year,states=len(f),
                        trades=f.trade_id.nunique(),coverage=len(f)/len(all_year) if len(all_year) else 0.,
                        tail_bin=tail_contract['bin'],tail_states=len(tail),tail_trades=tail.trade_id.nunique(),
                        tail_mean_exit_advantage=weighted_mean(tail[label],tail.weight),rest_mean_exit_advantage=weighted_mean(rest[label],rest.weight),
                        tail_exit_better_rate=weighted_mean(tail[label].gt(1e-12),tail.weight),
                        context_delta=context_delta(f,selected,label),oriented_auc=auc))
                    for k,g in f.groupby('bin'):
                        bins.append(dict(feature=feature,label=label,population=population,year=year,bin=int(k),states=len(g),trades=g.trade_id.nunique(),
                            mean_exit_advantage=weighted_mean(g[label],g.weight),exit_better_rate=weighted_mean(g[label].gt(1e-12),g.weight)))
    atomic_json(root/'2024-feature-contract.json',dict(features=contracts,protocol_sha256=digest(root/'protocol.json'),discovery_states=len(discovery)))
    pd.DataFrame(feature_rows).to_csv(root/'feature-stability.csv',index=False); pd.DataFrame(bins).to_csv(root/'feature-tertiles.csv',index=False)
    for year,t in trades.groupby('year'):
        v=s[s.signal_year.eq(year)]; kept=t[t.trade_id.isin(set(v.trade_id))]
        stopped=t[t.sl_first]
        for label in LABELS:
            yearly.append(dict(year=int(year),label=label,baseline_trades=len(t),trades_with_states=v.trade_id.nunique(),states=len(v),
                no_daily_decision_trades=len(t)-v.trade_id.nunique(),baseline_mean_net=float(t.net_outcome.mean()),
                states_with_next_open_priority=int(v.next_open_priority.ne('NONE').sum()),
                weighted_exit_better_rate=weighted_mean(v[label].gt(1e-12),v.weight),
                weighted_mean_exit_advantage=weighted_mean(v[label],v.weight),
                stopped_trades=len(stopped),stopped_with_states=int(stopped.trade_id.isin(set(v.trade_id)).sum()),
                stopped_with_any_better_exit=int(stopped.trade_id.isin(set(v.loc[v[label].gt(1e-12),'trade_id'])).sum())))
    candidates=[]
    for feature in FEATURES:
        for label in LABELS:
            rows=[r for r in feature_rows if r['feature']==feature and r['label']==label]
            passing=all(r['tail_trades']>=20 and r['tail_mean_exit_advantage'] is not None and r['tail_mean_exit_advantage']>0
                and r['context_delta'] is not None and r['context_delta']>0 and r['oriented_auc'] is not None and r['oriented_auc']>.5 for r in rows)
            candidates.append(dict(feature=feature,label=label,all_years_and_populations_positive_descriptive=passing,
                reserve='Descriptive screen across40 feature/label pairs, not corrected significance or promotion'))
    atomic_json(root/'report.json',dict(status='COMPLETED_AUDIT_NO_TRAINING',protocol_sha256=digest(root/'protocol.json'),
        annual=yearly,candidates=candidates,discovery_states=len(discovery),discovery_trades=discovery.trade_id.nunique(),
        coverage={c:float(np.isfinite(s[c]).mean()) for c in FEATURES},
        files={n:digest(root/n) for n in ['2024-feature-contract.json','feature-stability.csv','feature-tertiles.csv']},
        claim='Daily state/target feasibility and univariate stability only; no learned exit policy or portfolio PnL'))
    verify_hashes(Path('.'),p['sources']); atomic_json(root/'progress.json',dict(status='COMPLETED_AUDIT_NO_TRAINING',phase='DONE'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','build','analyze','all'],default='all'); args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    for name,function in [('prepare',prepare),('build',build),('analyze',analyze)]:
        if args.phase in ('all',name): function(args.output)
