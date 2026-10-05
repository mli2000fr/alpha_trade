"""Archived predictions only: repetition and operational probability reliability.

No SQL connection, fitting, blacklist, portfolio replay or production changes.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from scripts.research.us_original_directional_monthly_audit import long_mask

BASE=Path('artifacts/research/us_common_degradation/original-monthly-20261005-v1')
ROOT=Path('artifacts/research/us_common_degradation/repetition-reliability-20261005-v2')
BINS=[0,.35,.55,.65,.75,.85,.95,1]


def episode_selection(frame, sessions, horizon=20):
    """Continuous signal episodes and causal first-signal H20 cooldown."""
    if frame.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate signal keys')
    frame=frame.sort_values(['symbol','date']).copy()
    positions=pd.Series(np.arange(len(sessions)),index=sessions)
    frame['session']=frame.date.map(positions)
    if frame.session.isna().any():
        raise ValueError('Signal outside calendar')
    gap=frame.groupby('symbol').session.diff()
    frame['episode_start']=gap.isna()|gap.gt(1)
    frame['episode_number']=frame.episode_start.groupby(frame.symbol).cumsum()
    frame['first_h20_signal']=False
    for _,group in frame.groupby('symbol'):
        last=None
        for index,row in group.iterrows():
            if last is None or row.session-last>=horizon:
                frame.loc[index,'first_h20_signal']=True
                last=row.session
    return frame


def performance(frame):
    valid=frame[frame.target_quality_valid.eq(1)&frame.future_return.notna()&frame.oracle_decile.notna()]
    daily=valid.groupby('date').future_return.mean()
    return dict(events=len(frame),valid_events=len(valid),days=len(daily),symbols=valid.symbol.nunique(),
        mean_h20_pct=float(100*valid.future_return.mean()) if len(valid) else None,
        mean_daily_h20_pct=float(100*daily.mean()) if len(daily) else None,
        positive_pct=float(100*valid.future_return.gt(0).mean()) if len(valid) else None,
        d1_pct=float(100*valid.oracle_decile.eq(1).mean()) if len(valid) else None,
        d10_pct=float(100*valid.oracle_decile.eq(10).mean()) if len(valid) else None)


def capped_day_weight(frame, cap=.10):
    """Equal candidate/day budget capped per name, residual cash not reinvested."""
    valid=frame[frame.target_quality_valid.eq(1)&frame.future_return.notna()].copy()
    if valid.empty:
        return dict(mean_daily_budget_h20_pct=None,mean_cash_fraction=None,days=0)
    count=valid.groupby('date').symbol.transform('size')
    valid['weight']=np.minimum(1/count,cap)
    daily=(valid.future_return*valid.weight).groupby(valid.date).sum()
    invested=valid.weight.groupby(valid.date).sum()
    return dict(mean_daily_budget_h20_pct=float(100*daily.mean()),
        mean_cash_fraction=float((1-invested).mean()),days=len(daily))


def reliability(frame, prevalence):
    valid=frame[frame.target_quality_valid.eq(1)&frame.future_return.notna()&frame.proba_long.notna()].copy()
    if not valid.proba_long.between(0,1).all():
        raise ValueError('Probability outside [0,1]')
    valid['bin']=pd.cut(valid.proba_long,BINS,include_lowest=True,right=True)
    bins=[]
    for name,group in valid.groupby('bin',observed=True):
        bins.append(dict(bin=str(name),events=len(group),dates=group.date.nunique(),symbols=group.symbol.nunique(),
            mean_p_long=float(group.proba_long.mean()),positive_h20_pct=float(100*group.future_return.gt(0).mean()),
            above_3pct_h20_pct=float(100*group.future_return.gt(.03).mean()),
            mean_h20_pct=float(100*group.future_return.mean()),
            d1_pct=float(100*group.oracle_decile.eq(1).mean()),d10_pct=float(100*group.oracle_decile.eq(10).mean())))
    metrics={}
    for event,threshold in [('positive',0),('above_3pct',.03)]:
        y=valid.future_return.gt(threshold).astype(int)
        p=valid.proba_long
        metrics[event]=dict(prevalence=float(y.mean()) if len(y) else None,
            auc=float(roc_auc_score(y,p)) if len(y) and y.nunique()==2 else None,
            brier_operational=float(((p-y)**2).mean()) if len(y) else None,
            frozen_2024_2025_constant_brier=float(((prevalence[event]-y)**2).mean()) if len(y) else None)
    return dict(**performance(valid),events_by_bin=bins,metrics=metrics,
        rho_p_return=float(spearmanr(valid.proba_long,valid.future_return).statistic)
            if len(valid)>2 and valid.proba_long.nunique()>1 and valid.future_return.nunique()>1 else None)


def run():
    ROOT.mkdir(parents=True,exist_ok=False)
    protocol=dict(horizon=20,no_sql_reads_or_writes=True,no_training=True,
        episode='new episode after >=1 missing signal session; first observation left censored',
        cooldown='first signal then wait >=20 observed Oracle sessions, no outcome used',
        cap='10% per symbol per signal-day initial budget, residual cash, not portfolio simulator',
        bins=BINS,operational_targets=['H20 adjusted return >0','H20 adjusted return >3%'],
        historical_target_identity_verified=False,
        no_blacklist=True,no_threshold_optimization=True,no_independence_claim=True)
    (ROOT/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    frame=pd.read_parquet(BASE/'joined_diagnostic.parquet')
    oracle=pd.read_parquet(BASE/'oracle_snapshot.parquet')
    sessions=pd.DatetimeIndex(sorted(oracle.date.unique()))
    eligible=frame[frame._merge.eq('both')].copy()
    selected=episode_selection(eligible[long_mask(eligible)],sessions)
    selections={'ALL_SIGNALS':selected,'FIRST_CONTINUOUS_EPISODE':selected[selected.episode_start],
        'FIRST_SIGNAL_COOLDOWN20':selected[selected.first_h20_signal]}
    scopes={'2024H2':('2024-07-01','2024-12-31'),'2025H1':('2025-01-01','2025-06-30'),
        '2025H2':('2025-07-01','2025-12-31'),'2026Q1':('2026-01-01','2026-03-31'),
        '2026Q2':('2026-04-01','2026-06-30')}
    repetitions={}
    for key,(start,end) in scopes.items():
        repetitions[key]={name:performance(g[g.date.between(start,end)]) for name,g in selections.items()}
        repetitions[key]['CAPPED10_CASH']=capped_day_weight(selected[selected.date.between(start,end)])
    monthly={m:{name:performance(g[g.date.dt.strftime('%Y-%m').eq(m)]) for name,g in selections.items()}
        for m in sorted(selected.date.dt.strftime('%Y-%m').unique())}
    episodes=[]
    for (symbol,number),g in selected.groupby(['symbol','episode_number']):
        episodes.append(dict(symbol=symbol,episode=int(number),first_date=str(g.date.min().date()),
            last_date=str(g.date.max().date()),signals=len(g),first_p_long=float(g.proba_long.iloc[0]),
            first_h20_return_pct=float(100*g.future_return.iloc[0]) if pd.notna(g.future_return.iloc[0]) else None,
            mean_overlapping_h20_pct=float(100*g.future_return.mean())))
    develop=eligible[eligible.date.lt('2026-01-01')&eligible.target_quality_valid.eq(1)&eligible.future_return.notna()]
    prevalence={name:float(develop.future_return.gt(t).mean()) for name,t in [('positive',0),('above_3pct',.03)]}
    reliability_by_scope={}
    for population,data in {'ALL_SERVABLE_ORACLE':eligible,'FILTERED_LONG':selected,
                            'FILTERED_LONG_COOLDOWN20':selections['FIRST_SIGNAL_COOLDOWN20']}.items():
        reliability_by_scope[population]={scope:reliability(data[data.date.between(start,end)],prevalence)
            for scope,(start,end) in scopes.items()}
    persymbol=[]
    for (year,symbol),g in eligible.groupby([eligible.date.dt.year,'symbol']):
        y=g.future_return.gt(0)
        valid=g.target_quality_valid.eq(1)&g.future_return.notna()
        g=g[valid]; y=y[valid]
        persymbol.append(dict(year=int(year),symbol=symbol,events=len(g),mean_p_long=float(g.proba_long.mean()),
            p_long_std=float(g.proba_long.std()),p_long_min=float(g.proba_long.min()),p_long_max=float(g.proba_long.max()),
            positive_pct=float(100*y.mean()),mean_h20_pct=float(100*g.future_return.mean()),
            auc=float(roc_auc_score(y,g.proba_long)) if y.nunique()==2 else None))
    selected.to_parquet(ROOT/'selected_episode_flags.parquet',index=False)
    pd.DataFrame(episodes).to_csv(ROOT/'episodes.csv',index=False)
    pd.DataFrame(persymbol).to_csv(ROOT/'symbol_reliability.csv',index=False)
    result=dict(status='COMPLETED_DIAGNOSTIC_NO_PRODUCTION_GO',protocol=protocol,
        source_sha256=hashlib.sha256((BASE/'joined_diagnostic.parquet').read_bytes()).hexdigest(),
        development_prevalence=prevalence,repetition_windows=repetitions,repetition_months=monthly,
        reliability=reliability_by_scope,episodes=episodes,
        limitations=['Cooldown windows nonoverlapping within symbol but correlated across symbols',
            'Continuous signal episode is not economically independent or a realized position',
            'Repeated signal-day budgets overlap; cap/cash illustration is not tradable portfolio PnL',
            'P(LONG) compared to operational returns, not certified original training label calibration',
            'Independent LONG/SHORT branches probabilities not normalized into a single distribution',
            'Archived model manifest absent; conditional training target and calibrator version unverified',
            'No pristine OOS period; no ranking threshold selected from outputs'])
    (ROOT/'report.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    print('COMPLETED',ROOT,flush=True)
    print('REPETITION',json.dumps(repetitions),flush=True)
    print('RELIABILITY',json.dumps({p:{s:r['metrics'] for s,r in v.items()} for p,v in reliability_by_scope.items()}),flush=True)


if __name__=='__main__':
    run()
