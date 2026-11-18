"""Frozen, retrospective daily research panel; no SQL, HTTP, orders or model fit.

All future outcomes stay in a separate file. Aggregate features are dated at J;
quality rates use explicit maturity dates, including missing outcomes in support.
"""
from pathlib import Path
from datetime import datetime,timezone
import json

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_q051_protection_feature_audit/20261118-v1')
GROUPS=Path('artifacts/research/us_q051_feature_groups/20261116-lot1')
SOURCE=Path('artifacts/research/us_q051_b_early_sl/20261116-v1')
ORIGINAL=Path('artifacts/research/us_q051_features173/20261116-v2')
FULL=Path('artifacts/research/us_q051_sl_pause/20261116-30sessions-pause100-v1/inputs')


def read(file):return json.loads(Path(file).read_text(encoding='utf-8'))


def prepare():
    if (ROOT/'protocol.json').exists():return read(ROOT/'protocol.json')
    ROOT.mkdir(parents=True,exist_ok=True);original=read(ORIGINAL/'protocol.json');years={}
    for year in range(2021,2027):
        if year<2026:root=Path(original['models'][str(year+1)]['source_root'])
        else:
            from scripts.research.us_q051_global_rank_h10_20261115 import FEATURE_2026
            root=FEATURE_2026
        profile=read(root/'feature_profile.json');protocol=read(root/'protocol.json')
        if protocol['horizon']!=10 or len(profile['feature_columns'])!=173:raise ValueError('Unexpected Oracle feature contract')
        years[str(year)]=dict(root=str(root),features=profile['feature_columns'],options=profile['generator_options'],
            protocol_sha256=digest(root/'protocol.json'),profile_sha256=digest(root/'feature_profile.json'))
    plan=dict(status='SEALED',years=years,start='2020-12-31',end='2026-09-30',
        discovery='2021-2022, labels mature before 2023-01-01',calibration='2023, labels mature before 2024-01-01',
        chronological_evaluation='2024, 2025, 2026 to September30; already explored history, not a new holdout',
        cohorts=['universe','oracle179','B10','SL10'],aggregation=['median','IQR'],
        targets=dict(risk20='future minimum shadow equity / equity J -1 < -5%',
            recovery20='future return20 positive AND future minimum20 >= -5%',secondary='forward 5/10/20 returns and troughs'),
        combinations='At most two features per independent family; train-only direction/selection; fixed equal-rank scores, independent ON/OFF hysteresis',
        rule_families=['market+internal+account','market+internal+account+sentinel','internal+account+sentinel'],
        rule_settings=dict(on_quantile_2023=.90,off_quantile_2023=.50,on_confirm=2,off_confirm=[1,2],minimum_hold_sessions=3),
        selection_guard='No use of2024-2026 outcomes for feature orientation/selection or calibration; one rule may be chosen on2024 then evaluated unchanged2025-2026',
        reliability_guard='Chronological year stability, block20 confidence intervals, nonoverlapping event support; no portfolio return fabricated from rejected trades',
        sentinels='Rank using 2021-2022 only, freeze top5/top10; calibration2023; evaluate2024-2026; no future-selected stock lists',
        no_promised_reliability=True,portfolio_counterfactual=False,training_Oracle=0,training_per_symbol=0,
        SQL_writes=0,provider_calls=0,orders=0,production_changes=False,
        price_basis='Frozen retrospective histories, contemporary universe, revised prices; not certified PIT',
        created_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'protocol.json',plan);return plan


def aggregate(frame,columns,cohort):
    groups=frame.groupby('date')[columns];count=groups.count();expected=frame.groupby('date').size()
    good=count.ge(.8*expected,axis=0)
    median=groups.median().where(good);iqr=(groups.quantile(.75)-groups.quantile(.25)).where(good)
    out=pd.concat([median.add_prefix(cohort+'__median__'),iqr.add_prefix(cohort+'__iqr__')],axis=1)
    out[cohort+'__count']=expected
    return out


def annual_features(year):
    plan=read(ROOT/'protocol.json');meta=plan['years'][str(year)];root=Path(meta['root']);columns=meta['features']
    out=ROOT/'years'/str(year);out.mkdir(parents=True,exist_ok=True)
    if (out/'done.json').exists():return
    pool=pd.read_parquet(GROUPS/'years'/str(year)/'pool.parquet');days=pd.DatetimeIndex(sorted(pool.date.unique()))
    pieces=[];label_parts=[];files={}
    raw_columns=[c for c in columns if not c.endswith('_xs_rank')]
    all_files=sorted((root/'chunks').glob('*/features.parquet'))
    for number,file in enumerate(all_files):
        f=pd.read_parquet(file,columns=['date','symbol',*raw_columns],filters=[('date','>=',days[0]),('date','<=',days[-1])])
        pieces.append(f);files[str(file)]=digest(file)
        label=file.parent/'labels.parquet'
        label_parts.append(pd.read_parquet(label,filters=[('date','>=',days[0]),('date','<=',days[-1])]))
        files[str(label)]=digest(label)
        if number%8==0:atomic_json(out/'progress.json',dict(status='LOAD_FEATURES',completed=number,total=len(all_files)))
    frame=pd.concat(pieces,ignore_index=True);frame=frame[frame.date.isin(days)].copy()
    if frame.duplicated(['date','symbol']).any():raise ValueError('Ambiguous archived Oracle features')
    rank_cols=[c[:-8] for c in columns if c.endswith('_xs_rank')]
    ranks=frame.groupby('date')[rank_cols].rank(pct=True);ranks.columns=[c+'_xs_rank' for c in rank_cols]
    frame=pd.concat([frame,ranks],axis=1)
    for c in columns:frame[c]=pd.to_numeric(frame[c],errors='coerce').replace([np.inf,-np.inf],np.nan).astype(np.float32)
    cohorts={'universe':None,'oracle179':pool[['date','symbol']]}
    for name,case in [('B10','CONTROL'),('SL10','SL10')]:
        f=pd.read_parquet(SOURCE/'variants'/case/'signals.parquet',columns=['trade_date','symbol']).rename(columns={'trade_date':'date'})
        cohorts[name]=f[f.date.isin(days)]
    rows=[];index=pd.MultiIndex.from_frame(frame[['date','symbol']])
    for name,keys in cohorts.items():
        atomic_json(out/'progress.json',dict(status='AGGREGATING',cohort=name))
        f=frame if keys is None else frame.loc[index.isin(pd.MultiIndex.from_frame(keys))]
        rows.append(aggregate(f,columns,name))
    features=pd.concat(rows,axis=1).reindex(days);features.index.name='date'
    # Actual B / path variables were repaired/qualified in the original study.
    path_columns=read(SOURCE/'protocol.json')['features']['PATH10'];parts=[]
    for file in sorted((SOURCE/'jobs').glob(str(year)+'-*/testing.parquet')):
        parts.append(pd.read_parquet(file,columns=['date','symbol',*path_columns]));files[str(file)]=digest(file)
    context=pd.concat(parts,ignore_index=True)
    if context.duplicated(['date','symbol']).any():raise ValueError('Ambiguous B/anti-SL context')
    for name,keys in list(cohorts.items())[1:]:
        keys=keys if keys is not None else pool[['date','symbol']]
        f=context.merge(keys,on=['date','symbol'],how='inner',validate='one_to_one')
        features=features.join(aggregate(f,path_columns,'actual_'+name))
    from modelFactory.oracle_path.labels import classify
    labels=classify(pd.concat(label_parts,ignore_index=True),horizon=10)
    labels=pool[['date','symbol']].merge(labels,on=['date','symbol'],how='left',validate='one_to_one')
    labels[['date','symbol','oracle_available_date','oracle_path_extreme10']].to_parquet(out/'oracle-outcomes.parquet',index=False)
    features.to_parquet(out/'features.parquet')
    atomic_json(out/'done.json',dict(year=year,days=len(features),columns=len(features.columns),source_files=files,
        feature_sha256=digest(out/'features.parquet'),outcomes_sha256=digest(out/'oracle-outcomes.parquet')))
    atomic_json(out/'progress.json',dict(status='COMPLETED',days=len(features),features=len(features.columns)))


def mature_series(rows,calendar,value,available,windows=(5,10,20,60)):
    """Known-date aggregation; unknown observations stay in the denominator."""
    a=rows[[value,available]].copy();a[available]=pd.to_datetime(a[available]);a=a[a[available].notna()]
    g=a.groupby(available)[value].agg(expected='size',known='count',total='sum').reindex(calendar,fill_value=0)
    result=pd.DataFrame(index=calendar)
    for w in windows:
        roll=g.rolling(w,min_periods=w).sum();coverage=roll.known/roll.expected.replace(0,np.nan)
        result[f'rate{w}']=(roll.total/roll.known.replace(0,np.nan)).where(coverage.ge(.8)&roll.known.ge(max(10,w)))
        result[f'coverage{w}']=coverage
    return result


def features_internal():
    from scripts.research.us_q051_b_market_warning_audit_20261117 import market_features,health_features
    from scripts.research.us_q051_winrate_recovery_audit_20261117 import mature_rates
    close=pd.read_parquet(FULL/'close.parquet');calendar=close.index
    start,end=pd.Timestamp('2020-12-31'),pd.Timestamp('2026-09-30');dates=calendar[(calendar>=start)&(calendar<=end)]
    price,_=market_features(close);spy=close.SPY;market=pd.DataFrame(index=calendar)
    for h in [1,3,5,10,20,50,60,120,200]:
        market[f'market__spy_return{h}']=spy/spy.shift(h)-1
        market[f'market__spy_distance_sma{h}']=spy/spy.rolling(h,min_periods=h).mean()-1
    ret=spy.pct_change(fill_method=None)
    for h in [5,10,20,60,120]:
        market[f'market__spy_vol{h}']=ret.rolling(h,min_periods=h).std()*np.sqrt(252)
    for h in [20,63,126]:market[f'market__spy_dd{h}']=spy/spy.rolling(h,min_periods=h).max()-1
    for h in [5,20,50,200]:
        eligible=close.notna().rolling(h).sum().eq(h)
        ratio=close.gt(close.rolling(h).mean()).where(eligible)
        market[f'market__breadth_sma{h}']=ratio.drop(columns='SPY').mean(axis=1).where(eligible.drop(columns='SPY').mean(axis=1).ge(.8))
    features=market.loc[dates].copy();outcomes=pd.DataFrame(index=calendar)
    for family,case in [('B','CONTROL'),('SL10','SL10')]:
        folder=SOURCE/'cases'/case/'result';equity=pd.read_csv(folder/'equity-daily.csv',index_col=0,parse_dates=True).equity
        equity.loc[pd.Timestamp('2020-12-31')]=4000.;equity=equity.sort_index()
        health=health_features(pd.read_csv(folder/'trades.csv'),equity)
        for h in [1,3,5,10,20,60]:health[f'return{h}']=equity/equity.shift(h)-1
        for h in [10,20,63,126]:health[f'drawdown{h}']=equity/equity.rolling(h,min_periods=h).max()-1
        features=features.join(health.drop(columns=['last_exit_available']).add_prefix('account_'+family+'__'))
        for h in [5,10,20]:
            forward=equity.shift(-h)/equity-1;trough=equity.rolling(h,min_periods=h).min().shift(-h)/equity-1
            outcomes[family+f'__return{h}']=forward
            outcomes[family+f'__trough{h}']=trough
            outcomes[family+f'__available{h}']=pd.Series(equity.index,index=equity.index).shift(-h)
        outcomes[family+'__risk20']=(outcomes[family+'__trough20']<-.05).astype(float).where(outcomes[family+'__trough20'].notna())
        outcomes[family+'__recovery20']=((outcomes[family+'__return20']>0)&(outcomes[family+'__trough20']>=-.05)).astype(float).where(outcomes[family+'__trough20'].notna())
    labels=pd.read_parquet(SOURCE/'test-labels-and-risks.parquet')
    pool=pd.concat([pd.read_parquet(GROUPS/'years'/str(y)/'pool.parquet',columns=['date','symbol']) for y in range(2021,2027)],ignore_index=True)
    sets={'oracle179':pool}
    for name,case in [('B10','CONTROL'),('SL10','SL10')]:sets[name]=pd.read_parquet(SOURCE/'variants'/case/'signals.parquet',columns=['trade_date','symbol']).rename(columns={'trade_date':'date'})
    for name,keys in sets.items():
        a=keys.merge(labels,on=['date','symbol'],how='left',validate='one_to_one')
        index=calendar.get_indexer(a.date)
        # Expected calendar maturity is retained even if an archived outcome is missing.
        for value,lag in [('net_long',11),('first_session_sl',2)]:
            available=pd.Series(pd.NaT,index=a.index,dtype='datetime64[ns]');inside=(index>=0)&(index+lag<len(calendar))
            available.loc[inside]=calendar.take(index[inside]+lag).to_numpy();a['expected_available']=available
            known=a[value].notna();stored='long_available' if value=='net_long' else 'event_available'
            if not pd.to_datetime(a.loc[known,stored]).eq(available.loc[known]).all():raise ValueError('Unexpected internal label maturity')
            rates=mature_series(a,calendar,value,'expected_available').add_prefix('internal_'+name+'__'+value+'__')
            features=features.join(rates.loc[dates])
        for name_field in ['SL10_risk','SLJ_risk']:
            avail='SL10_available' if name_field=='SL10_risk' else 'SLJ_available'
            known=a[name_field].notna()
            if not pd.to_datetime(a.loc[known,avail]).lt(a.loc[known,'date']).all():raise ValueError('Future anti-SL risk')
            agg=a.groupby('date')[name_field].agg(['median','mean','std'])
            features=features.join(agg.add_prefix('anti_'+name+'__'+name_field+'__'))
        veto=a.SL10_risk.gt(a.SL10_threshold).where(a.SL10_risk.notna())
        features=features.join(a.assign(veto=veto).groupby('date').veto.mean().rename('anti_'+name+'__veto_share'))
    oracle=pd.concat([pd.read_parquet(ROOT/'years'/str(y)/'oracle-outcomes.parquet') for y in range(2021,2027)],ignore_index=True)
    features=features.join(mature_series(oracle,calendar,'oracle_path_extreme10','oracle_available_date').loc[dates].add_prefix('internal_amplitude__'))
    for name in ['ORACLE179','PER_B10','PER_SL10','TRADED_B','TRADED_SL10']:
        file=Path('artifacts/research/us_q051_winrate_recovery_audit/20261117-v1')/(name+'-timeline.parquet')
        r=pd.read_parquet(file)[['recent_rate','reference_rate','recent_coverage','reference_coverage']]
        r['rate_gap']=r.recent_rate-r.reference_rate
        features=features.join(r.add_prefix('quality_'+name+'__'))
    features.replace([np.inf,-np.inf],np.nan).to_parquet(ROOT/'internal-features.parquet')
    outcomes.loc[dates].to_parquet(ROOT/'future-outcomes.parquet')
    # Diagnostic availability only; these series are not certified decision-time vintages.
    macro=read(Path('artifacts/research/us_q051_b_market_warning_audit/20261117-v2/macro-inventory.json'))
    atomic_json(ROOT/'external-availability.json',dict(macro=macro,
        options_consensus_news='Not retroprojected into2021-2026: PIT snapshots too short/unqualified; no historical data invented',
        current_SQL_inventory='No SQL needed for the frozen historical feature audit',used_in_main_rules=False))


def assemble():
    frame=pd.concat([pd.read_parquet(ROOT/'years'/str(y)/'features.parquet') for y in range(2021,2027)])
    if frame.index.has_duplicates:raise ValueError('Duplicate annual decision dates')
    frame=frame.join(pd.read_parquet(ROOT/'internal-features.parquet')).sort_index()
    frame.to_parquet(ROOT/'daily-features.parquet')
    inventory=pd.DataFrame(dict(feature=frame.columns,known_days=frame.notna().sum().to_numpy(),
        unique_values=frame.nunique().to_numpy(),coverage_pct=100*frame.notna().mean().to_numpy()))
    inventory.to_csv(ROOT/'feature-inventory.csv',index=False)
    atomic_json(ROOT/'data-ready.json',dict(status='PASS',days=len(frame),features=len(frame.columns),
        nonconstant_features=int(inventory.unique_values.gt(1).sum()),
        feature_sha256=digest(ROOT/'daily-features.parquet'),outcome_sha256=digest(ROOT/'future-outcomes.parquet')))


if __name__=='__main__':
    from concurrent.futures import ThreadPoolExecutor,as_completed
    prepare();atomic_json(ROOT/'progress.json',dict(status='EXTRACTING',completed=0,total=6))
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures={pool.submit(annual_features,y):y for y in range(2021,2027)}
            for completed,future in enumerate(as_completed(futures),1):
                future.result();print('Annual feature aggregates ready:',futures[future],flush=True)
                atomic_json(ROOT/'progress.json',dict(status='EXTRACTING',completed=completed,total=6,last_year=futures[future]))
        atomic_json(ROOT/'progress.json',dict(status='INTERNAL_FEATURES'))
        features_internal();assemble();atomic_json(ROOT/'progress.json',{**read(ROOT/'data-ready.json'),'status':'DATA_READY'})
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise
