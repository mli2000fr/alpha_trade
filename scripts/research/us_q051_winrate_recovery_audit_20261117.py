"""Causal internal activation/recovery diagnostics, no new portfolio replay.

Net LONG profitability of frozen Oracle/per-symbol selections, not Oracle
amplitude accuracy. Every label waits for common open11 maturity, including SL.
Unknown year-boundary labels remain unknown. Unprotected accounts serve as
continuous shadow accounts; real protected balances are reported separately.
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_q051_b_market_warning_audit_20261117 import measure

ROOT=Path('artifacts/research/us_q051_winrate_recovery_audit/20261117-v1')
SOURCE=Path('artifacts/research/us_q051_b_early_sl/20261116-v1')
SWITCH=Path('artifacts/research/us_q051_b_spy_switch/20261117-v1')
GROUPS=Path('artifacts/research/us_q051_feature_groups/20261116-lot1')
PREVIOUS=Path('artifacts/research/us_q051_b_market_warning_audit/20261117-v2')
FULL=Path('artifacts/research/us_q051_sl_pause/20261116-30sessions-pause100-v1/inputs')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def mature_rates(rows,calendar,*,min_recent=40):
    """20 maturity sessions versus previous120, with >=80% labels known.

    Windows use expected exchange-calendar maturity even when label unknown;
    dropping unknown labels before forming windows would silently alter support.
    """
    a=rows[rows.available.notna()].copy()
    if a.empty:raise ValueError('No mature cohort calendar')
    g=a.groupby('available').outcome.agg(expected='size',known='count',wins='sum').reindex(calendar,fill_value=0)
    recent=g.rolling(20,min_periods=20).sum();reference=g.shift(20).rolling(120,min_periods=120).sum()
    r=pd.DataFrame(index=calendar)
    for prefix,f in [('recent',recent),('reference',reference)]:
        r[prefix+'_expected']=f.expected;r[prefix+'_known']=f.known
        r[prefix+'_coverage']=f.known/f.expected.replace(0,np.nan)
        r[prefix+'_rate']=f.wins/f.known.replace(0,np.nan)
    first=calendar.get_indexer([a.available.min()])[0]
    r['qualified']=(np.arange(len(r))>=first+139)&r.recent_known.ge(min_recent)&r.reference_known.ge(4*min_recent)&r.recent_coverage.ge(.8)&r.reference_coverage.ge(.8)
    r.loc[~r.qualified,['recent_rate','reference_rate']]=np.nan
    return r


def rate_switch(rates):
    """One declared rule: drop5pp/3closes ON, frozen reference-2pp/5 OFF."""
    active=False;anchor=np.nan;down=up=0;out=[]
    for day,row in rates.iterrows():
        transition=''
        if bool(row.qualified):
            down=down+1 if row.recent_rate<row.reference_rate-.05 else 0
            up=up+1 if active and row.recent_rate>=anchor-.02 else 0
            if not active and down>=3:
                active=True;anchor=float(row.reference_rate);transition='ON';down=up=0
            elif active and up>=5:
                active=False;transition='OFF';down=up=0
        else:down=up=0
        out.append(dict(date=day,qualified=bool(row.qualified),active=active,anchor=anchor,transition=transition))
    return pd.DataFrame(out).set_index('date')


def first_confirmed(series,start,*,confirm=5,max_sessions=120):
    f=series.loc[series.index>start].head(max_sessions);count=0
    for day,v in f.items():
        count=count+1 if pd.notna(v) and bool(v) else 0
        if count>=confirm:return day
    return pd.NaT


def main():
    ROOT.mkdir(parents=True,exist_ok=False)
    atomic_json(ROOT/'protocol.json',dict(rolling_maturity_sessions=20,reference_previous_maturity_sessions=120,
        min_label_coverage=.8,activation='rate20 < reference120-5pp for3closes',
        recovery='rate20 >= frozen_reference_at_activation-2pp for5closes',
        account_recovery='return20>5% for5closes',maturity='signalJ+11 exchange sessions, full open11 even early SL',
        episode_recovery_limit=120,new_replays=0,training=0,threshold_search=False,production_changes=False))
    close=pd.read_parquet(FULL/'close.parquet',columns=['SPY']);calendar=close.index
    labels=pd.read_parquet(SOURCE/'test-labels-and-risks.parquet')
    pool=pd.concat([pd.read_parquet(GROUPS/'years'/str(y)/'pool.parquet')[['date','symbol']] for y in range(2021,2027)],ignore_index=True)
    if pool.duplicated(['date','symbol']).any():raise ValueError('Duplicate Oracle pool')
    cohorts={'ORACLE179':pool.merge(labels[['date','symbol','net_long','long_available']],on=['date','symbol'],how='left',validate='one_to_one')}
    for name,case in [('PER_B10','CONTROL'),('PER_SL10','SL10')]:
        s=pd.read_parquet(SOURCE/'variants'/case/'signals.parquet')[['trade_date','symbol']].rename(columns={'trade_date':'date'})
        cohorts[name]=s.merge(labels[['date','symbol','net_long','long_available']],on=['date','symbol'],how='left',validate='one_to_one')
    equities={};protected={};all_inputs=[FULL/'close.parquet',SOURCE/'test-labels-and-risks.parquet']
    for family,case in [('B','CONTROL'),('SL10','SL10')]:
        folder=SOURCE/'cases'/case/'result';t=pd.read_csv(folder/'trades.csv')
        ev=pd.read_csv(folder/'events.csv',low_memory=False);buys=ev[ev.event.eq('BUY_FILL')][['symbol','time','signal_date']]
        buys=buys.rename(columns={'time':'entry_date','signal_date':'date'})
        x=buys.merge(t[['symbol','entry_date','pnl']],on=['symbol','entry_date'],how='left',validate='one_to_one')
        x.date=pd.to_datetime(x.date);x['net_long']=x.pnl.gt(0).astype(float).where(x.pnl.notna());x['long_available']=pd.NaT
        cohorts['TRADED_'+family]=x
        equities[family]=pd.read_csv(folder/'equity-daily.csv',index_col=0,parse_dates=True).equity
        p=SWITCH/'cases'/(family+'_MA50')/'result/equity-daily.csv'
        protected[family]=pd.read_csv(p,index_col=0,parse_dates=True).equity
        all_inputs += [folder/'trades.csv',folder/'events.csv',folder/'equity-daily.csv',p,
            SOURCE/'variants'/case/'signals.parquet']
    rates={};states={};rows=[];maturity_checks=[]
    for name,a in cohorts.items():
        a=a.copy();a.date=pd.to_datetime(a.date);i=calendar.get_indexer(a.date)
        if (i<0).any():raise ValueError('Unknown signal session')
        expected=pd.Series(pd.NaT,index=a.index,dtype='datetime64[ns]');inside=i+11<len(calendar)
        expected.loc[inside]=calendar.take(i[inside]+11).to_numpy()
        actual=pd.to_datetime(a.long_available);known=actual.notna()
        if not actual[known].eq(expected[known]).all():raise ValueError('Stored H10 maturity differs from declared calendar')
        a['available']=expected;a['outcome']=a.net_long
        limit=20 if name.startswith('TRADED_') else 40
        r=mature_rates(a[['available','outcome']],calendar,min_recent=limit)
        state=rate_switch(r)
        for cut in ['2023-12-29','2024-11-29','2025-03-31']:
            sub=a[a.available.le(pd.Timestamp(cut))]
            rp=mature_rates(sub[['available','outcome']],calendar[calendar<=cut],min_recent=limit)
            pd.testing.assert_frame_equal(rp,r.loc[:cut]);pd.testing.assert_frame_equal(rate_switch(rp),state.loc[:cut])
        combined=r.join(state[['active','anchor','transition']]);combined.to_parquet(ROOT/(name+'-timeline.parquet'))
        rates[name]=r;states[name]=state
        maturity_checks.append(dict(cohort=name,signals=len(a),known_outcomes=int(a.net_long.notna().sum()),
            missing_outcomes=int(a.net_long.isna().sum()),qualified_days=int(r.loc['2021-01-01':'2026-09-30'].qualified.sum()),
            first_qualified=str(r[r.qualified].index.min())))
        all_inputs += [GROUPS/'years'/str(y)/'pool.parquet' for y in range(2021,2027)] if name=='ORACLE179' else []
    pd.DataFrame(maturity_checks).to_csv(ROOT/'cohort-coverage.csv',index=False)
    quality=[];activation=[];recovery=[];episode=[]
    for name,r in rates.items():
        state=states[name];changes=state[state.transition.ne('')].loc['2021-01-01':'2026-09-30']
        for day,row in changes.iterrows():
            for family,e in equities.items():
                p=e.index.get_indexer([day])[0]
                if p<0:continue
                for h in [10,20]:
                    if p+h>=len(e):continue
                    quality.append(dict(cohort=name,event=row.transition,date=str(day.date()),family=family,horizon=h,
                        future_shadow_return_pct=100*(e.iloc[p+h]/e.loc[day]-1),
                        future_shadow_min_return_pct=100*(e.iloc[p+1:p+h+1].min()/e.loc[day]-1),
                        known_rate=r.loc[day,'recent_rate'],anchor=row.anchor))
        for family in ['B','SL10']:
            t=pd.read_parquet(PREVIOUS/(family+'-actual-trade-context.parquet'));t=t[t.mature].copy()
            flag=state.active.astype('boolean').where(state.qualified).rename('RATE_PROTECTION')
            t=t.join(flag,on='signal_date')
            target=t.entry_day.between('2024-11-01','2025-06-30')
            for scope,g in [('target',t[target]),('outside_target',t[~target]),('all',t)]:
                activation.append(dict(cohort=name,family=family,scope=scope,**measure(g,'RATE_PROTECTION')))
        for family in ['B','SL10']:
            spy_state=pd.read_parquet(SWITCH/'inputs/spy-states-MA50.parquet')
            on=spy_state[spy_state.transition.eq('ON')].loc['2021-01-01':'2026-09-30'].index
            for day in on:
                at=calendar.get_loc(day);previous=calendar[at-1];baseline=r.loc[previous,'recent_rate']
                criterion=r.recent_rate.ge(baseline-.02).where(r.qualified) if pd.notna(baseline) else pd.Series(pd.NA,index=r.index,dtype='boolean')
                off=first_confirmed(criterion,day)
                episode.append(dict(cohort=name,family=family,spy_on=str(day.date()),reference_day=str(previous.date()),
                    pre_protection_known_rate=baseline,recovered_rate_date=str(off.date()) if pd.notna(off) else None))
    for family,e in equities.items():
        spy_state=pd.read_parquet(SWITCH/'inputs/spy-states-MA50.parquet')
        on=spy_state[spy_state.transition.eq('ON')].loc['2021-01-01':'2026-09-30'].index
        for day in on:
            for kind,curve in [('CONTINUOUS_SHADOW',e),('PROTECTED_ACCOUNT_MA50',protected[family])]:
                ret=curve/curve.shift(20)-1;criterion=ret.gt(.05).where(ret.notna());off=first_confirmed(criterion,day)
                row=dict(cohort=kind,family=family,spy_on=str(day.date()),recovery_date=str(off.date()) if pd.notna(off) else None)
                if pd.notna(off):
                    p=e.index.get_loc(off)
                    for h in [10,20]:
                        if p+h<len(e):row[f'shadow_future_return{h}']=100*(e.iloc[p+h]/e.loc[off]-1)
                recovery.append(row)
    pd.DataFrame(quality).to_csv(ROOT/'on-off-future-shadow-diagnostics.csv',index=False)
    pd.DataFrame(activation).to_csv(ROOT/'activation-trade-diagnostics.csv',index=False)
    pd.DataFrame(episode).to_csv(ROOT/'rate-return-to-pre-protection-level.csv',index=False)
    pd.DataFrame(recovery).to_csv(ROOT/'account-return20-plus5-recovery.csv',index=False)
    # Full daily observations retained to distinguish five-day confirmation from
    # the first isolated crossing, without hindsight shortening the confirmation.
    account=pd.DataFrame(index=equities['B'].index)
    for family,e in equities.items():
        account[family+'_shadow_ret20']=e/e.shift(20)-1
        account[family+'_protected_ret20']=protected[family]/protected[family].shift(20)-1
    account.to_parquet(ROOT/'account-recovery-timeline.parquet')
    atomic_json(ROOT/'sources.json',{str(p):digest(p) for p in [*set(all_inputs),Path(__file__),
        Path('scripts/research/us_q051_b_market_warning_audit_20261117.py')]})
    atomic_json(ROOT/'validation.json',dict(status='PASS',maturity_calendar_checks=5,prefix_checks=15,
        prefix_state_checks=15,unknowns_not_losses=True,threshold_optimization=False,new_replays=0,
        predictive_holdout=False,full_live_parity=False))
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_AUDIT',cohorts=list(cohorts),production_changes=False))
    print(pd.DataFrame(maturity_checks).to_string(index=False))
    print('Target recovery +5%:');print(pd.DataFrame(recovery)[pd.DataFrame(recovery).spy_on.between('2024-11-01','2025-06-30')].to_string(index=False))
    print('Target mature-rate transitions:')
    for name,state in states.items():print(name,state[state.transition.ne('')].loc['2024-11-01':'2025-06-30'].to_string())


if __name__=='__main__':main()
