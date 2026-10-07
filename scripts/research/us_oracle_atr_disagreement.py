"""Frozen Oracle/ATR disagreement audit from existing panels. No fit, SELECT only."""
import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import event,text

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.extreme_gate import compute_extreme_gate
from scripts.research.us_2026_regime_refresh import forbid_writes
from scripts.research.us_sector_breadth_confirmation import regime_mask
from scripts.research.us_intersection_sentiment_deciles import ROOT

DEST=ROOT/'oracle-atr-disagreement-20261004-v1'
PROTOCOL=Path('doc/ml/us_oracle_atr_desaccord_protocole.md')
GROUPS=['BOTH','ORACLE_ONLY','ATR_ONLY','NEITHER']


def classify(frame):
    if frame.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate panel keys')
    cols=['proba_extreme','atr20_pct','rolling_volatility_60']
    finite=np.isfinite(frame[cols].astype(float)).all(axis=1)
    data=compute_extreme_gate(frame[finite])
    data['atr_pct']=data.groupby('date').atr20_pct.rank(pct=True)
    data['vol_pct']=data.groupby('date').rolling_volatility_60.rank(pct=True)
    atr=data.atr_pct.ge(.8)
    oracle=data.extreme_gate
    data['cohort']=np.select([oracle&atr,oracle&~atr,~oracle&atr],GROUPS[:3],default='NEITHER')
    data['atr_bin']=np.ceil(data.atr_pct*10).clip(1,10).astype(int)
    data['vol_bin']=np.ceil(data.vol_pct*3).clip(1,3).astype(int)
    return data,len(frame)-len(data)


def daily_metrics(data):
    valid=data.target_quality_valid.eq(1)&data.future_return.notna()&data.oracle_decile.notna()
    data=data.copy()
    data['valid']=valid.astype(int)
    data['d10']=(valid&data.oracle_decile.eq(10)).astype(int)
    data['d1']=(valid&data.oracle_decile.eq(1)).astype(int)
    data['extreme']=(valid&data.oracle_extreme10.eq(1)).astype(int)
    data['ret_sum']=data.future_return.where(valid,0)
    data['abs_sum']=data.ret_sum.abs()
    return data.groupby(['date','cohort','regime_label'],dropna=False).agg(
        selected=('symbol','size'),valid=('valid','sum'),d10=('d10','sum'),d1=('d1','sum'),
        extreme=('extreme','sum'),ret_sum=('ret_sum','sum'),abs_sum=('abs_sum','sum')).reset_index()


def summarize(daily):
    output={}
    for name,g in daily.groupby('cohort'):
        n=int(g.valid.sum())
        total=int(g.selected.sum())
        output[name]={'selected':total,'valid':n,'unknown':total-n,'dates':g.date.nunique(),
                      **{k:100*float(g[col].sum()/n) if n else None for k,col in
                         [('d10_pct','d10'),('d1_pct','d1'),('extreme_pct','extreme'),
                          ('mean_return_pct','ret_sum'),('mean_abs_return_pct','abs_sum')]}}
    return output


def matched(frame):
    valid=frame.target_quality_valid.eq(1)&frame.future_return.notna()&frame.oracle_decile.notna()
    data=frame[valid].copy()
    data['d10']=data.oracle_decile.eq(10).astype(float)
    data['d1']=data.oracle_decile.eq(1).astype(float)
    data['extreme']=data.oracle_extreme10.eq(1).astype(float)
    data['abs_return']=data.future_return.abs()
    columns=['d10','d1','extreme','future_return','abs_return']
    pairs={'WITHIN_ATR_TOP20':('BOTH','ATR_ONLY'),
           'OUTSIDE_ATR_TOP20':('ORACLE_ONLY','NEITHER'),
           'ORACLE_VS_NOT':('ORACLE','NOT_ORACLE')}
    rows=[]
    for name,(left,right) in pairs.items():
        temp=data.copy()
        if name=='ORACLE_VS_NOT':
            temp['side']=np.where(temp.extreme_gate,'ORACLE','NOT_ORACLE')
        else:
            temp=temp[temp.cohort.isin([left,right])].copy()
            temp['side']=temp.cohort
        groups=temp.groupby(['date','atr_bin','vol_bin','side'])
        means=groups[columns].mean().unstack('side')
        counts=groups.size().unstack('side')
        if left not in counts or right not in counts:
            continue
        support=counts[left].ge(5)&counts[right].ge(5)
        counts=counts[support]
        means=means.loc[counts.index]
        weights=counts[[left,right]].min(axis=1)
        deltas=pd.DataFrame({c:(means[(c,left)]-means[(c,right)])*weights for c in columns})
        dates=deltas.groupby(level='date').sum().div(weights.groupby(level='date').sum(),axis=0)
        dates['cells']=weights.groupby(level='date').size()
        dates['paired_weight']=weights.groupby(level='date').sum()
        dates['supported_rows']=counts[[left,right]].sum(axis=1).groupby(level='date').sum()
        dates['comparison']=name
        dates=dates.reset_index()
        rows.append(dates)
    return pd.concat(rows,ignore_index=True) if rows else pd.DataFrame()


def comparison_summary(frame):
    result={}
    cols=['d10','d1','extreme','future_return','abs_return']
    for name,g in frame.groupby('comparison'):
        g=g.sort_values('date')
        values=g[cols].to_numpy()
        n=len(g)
        rng=np.random.default_rng(20261004)
        samples=[]
        if n>=42:
            for _ in range(500):
                starts=rng.integers(0,n-21+1,size=int(np.ceil(n/21)))
                indices=np.concatenate([np.arange(s,s+21) for s in starts])[:n]
                samples.append(values[indices].mean(axis=0))
        result[name]={'dates':n,'cells':int(g.cells.sum()),'supported_rows':int(g.supported_rows.sum()),
                      'delta_pp':{c:float(values[:,i].mean()*100) for i,c in enumerate(cols)},
                      'positive_extreme_dates_pct':float(g.extreme.gt(0).mean()*100),
                      'ci95_exploratory_pp':{c:[float(x*100) for x in np.quantile(np.array(samples)[:,i],[.025,.975])] for i,c in enumerate(cols)} if samples else None}
    return result


def main():
    logging.basicConfig(level=logging.INFO)
    DEST.mkdir(parents=True,exist_ok=False)
    def progress(phase,**details):
        payload={'phase':phase,**details}
        logging.info('%s',payload)
        (DEST/'progress.json').write_text(json.dumps(payload),encoding='utf-8')
    progress('LOAD_MACRO')
    engine=get_sqlalchemy_engine()
    event.listen(engine,'before_cursor_execute',forbid_writes)
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
            raise ValueError('US database required')
        macro=pd.read_sql(text("SELECT trade_date AS date,mode,allow_new_entries,vix,vxn,vix3m,move FROM stock_macro_indicators_daily WHERE trade_date BETWEEN '2019-01-01' AND '2026-03-31'"),conn)
    macro['date']=pd.to_datetime(macro.date)
    if macro.date.duplicated().any():
        raise ValueError('Duplicate macro dates')
    macro.to_parquet(DEST/'macro_snapshot.parquet',index=False)
    daily_all=[]
    comparisons=[]
    evidence={}
    for year in range(2019,2027):
        root=ROOT/('combination-history-2026q1-20261004-v1' if year==2026 else 'combination-history-2019-2025-20261004-v1')/str(year)
        p=root/'panel.parquet'
        l=root/'labels.parquet'
        progress('YEAR',year=year)
        frame,excluded=classify(pd.read_parquet(p))
        labels=pd.read_parquet(l).rename(columns={'prediction_date':'date'})
        labels['date']=pd.to_datetime(labels.date)
        frame=frame.merge(labels[['date','symbol','oracle_decile','oracle_extreme10','future_return','target_quality_valid']],
                          on=['date','symbol'],how='left',validate='one_to_one').merge(macro,on='date',how='left',validate='many_to_one')
        known,allowed=regime_mask(frame)
        frame['regime_label']=np.where(~known,'UNKNOWN',np.where(allowed,'LONG_ALLOWED','LONG_BLOCKED'))
        daily_all.append(daily_metrics(frame))
        comparisons.append(matched(frame))
        evidence[str(year)]={'panel_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                             'labels_sha256':hashlib.sha256(l.read_bytes()).hexdigest(),
                             'excluded_nonfinite':excluded,'rows':len(frame),
                             'missing_macro_rows':int(frame[['vix','vxn','vix3m','move']].isna().any(axis=1).sum())}
        keep=['date','symbol','cohort','extreme_gate','atr_pct','vol_pct','atr_bin','vol_bin',
              'oracle_decile','oracle_extreme10','target_quality_valid','future_return','regime_label']
        frame[keep].to_parquet(DEST/f'cohorts_{year}.parquet',index=False)
    daily=pd.concat(daily_all,ignore_index=True)
    paired=pd.concat(comparisons,ignore_index=True)
    progress('SUMMARIZE')
    def csum(mask):
        return comparison_summary(paired[mask])
    result={'status':'COMPLETED_EXPLORATORY_NO_PRODUCTION_DECISION',
            'protocol_sha256':hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),'evidence':evidence,
            'overall':summarize(daily),
            'years':{str(y):summarize(g) for y,g in daily.groupby(daily.date.dt.year)},
            'semesters':{str(y):summarize(g) for y,g in daily.groupby(daily.date.dt.year.astype(str)+'H'+np.where(daily.date.dt.month.le(6),'1','2'))},
            'months':{str(m):summarize(g) for m,g in daily.groupby(daily.date.dt.to_period('M'))},
            'regimes':{str(r):summarize(g) for r,g in daily.groupby('regime_label')},
            'matched':comparison_summary(paired),
            'matched_years':{str(y):comparison_summary(g) for y,g in paired.groupby(paired.date.dt.year)},
            'matched_windows':{'2019_2022':csum(paired.date.lt('2023-01-01')),
                               '2023_2025':csum(paired.date.ge('2023-01-01')&paired.date.lt('2026-01-01')),
                               '2026Q1':csum(paired.date.ge('2026-01-01'))},
            'notes':['Native tail extreme label and terminal absolute return, not MFE/MAE',
                     'Matched on daily ATR decile and volatility60 tercile; minimum5 labels per side',
                     'CI moving blocks21 on supported daily contrasts,500 draws seed20261004, exploratory',
                     'Fixed current surviving universe; already explored periods; no causal claim',
                     'Archived signalJ regime, no J+1 fills/risk/portfolio; PIT vintage reserves',
                     'No fit, new model prediction, SQL write, refilling or tuning']}
    daily.to_parquet(DEST/'daily_groups.parquet',index=False)
    paired.to_parquet(DEST/'daily_matched.parquet',index=False)
    (DEST/'report.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    progress('COMPLETED')
    print(DEST)


if __name__=='__main__':
    main()
