"""Chronological warning/recovery discovery; no fabricated portfolio replay.

2021 discovers directions, 2022 confirms features, 2023 fixes thresholds.
2024 can nominate one of six predeclared rules; 2025-2026 evaluate it unchanged.
All periods have already been explored: this is not a new independent holdout.
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from scripts.research.us_q051_protection_features_data_20261118 import ROOT,GROUPS,SOURCE,FULL,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def auc(x,y):
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float);keep=np.isfinite(x)&np.isfinite(y);x=x[keep];y=y[keep]
    pos=y==1;n=int(pos.sum());m=len(y)-n
    if min(n,m)<10 or len(np.unique(x))<2:return np.nan,len(y)
    ranks=rankdata(x);return float((ranks[pos].sum()-n*(n+1)/2)/(n*m)),len(y)


def period_mask(outcome,year):
    boundary=pd.Timestamp(year+1,1,1)
    return (outcome.index.year==year)&outcome.SL10__available20.lt(boundary)


def empirical(train,values,direction):
    fitted=np.sort(np.asarray(train,dtype=float)*direction);fitted=fitted[np.isfinite(fitted)]
    v=np.asarray(values,dtype=float)*direction;result=np.full(len(v),np.nan)
    if len(fitted)<80:return result
    good=np.isfinite(v);result[good]=(np.searchsorted(fitted,v[good],side='left')+np.searchsorted(fitted,v[good],side='right'))/(2*len(fitted))
    return result


def family(name):
    if name.startswith('sentinel__'):return 'sentinel'
    if name.startswith('account_'):return 'account'
    if name.startswith(('quality_','internal_','anti_','scores_')):return 'internal'
    return 'market'  # market + universe/Oracle/B cohort technical distributions


def sentinel_panel(outcome):
    close=pd.read_parquet(FULL/'close.parquet');returns=close.pct_change(fill_method=None)
    eligible=(close.loc['2021':'2022'].notna().mean().ge(.95)&returns.loc['2021':'2022'].abs().gt(.5).sum().eq(0)
        &returns.loc['2021':'2022'].eq(0).mean().lt(.8))
    metrics={}
    for h in [3,5,10,20]:metrics['return'+str(h)]=close/close.shift(h)-1
    metrics['distance_sma20']=close/close.rolling(20,min_periods=20).mean()-1
    metrics['drawdown20']=close/close.rolling(20,min_periods=20).max()-1
    metrics['relative20']=metrics['return20'].sub(metrics['return20'].SPY,axis=0)
    metrics['vol_ratio5_20']=returns.rolling(5).std()/returns.rolling(20).std()
    records=[];calendar=outcome.index;training=(calendar.year<=2022)&(calendar.year>=2021)&outcome.SL10__available20.lt('2023-01-01')
    for metric,values in metrics.items():
        f=values.reindex(calendar)
        for symbol in close.columns[eligible]:
            if symbol=='SPY':continue
            x=f[symbol].to_numpy(float)
            for target in ['risk20','recovery20']:
                row=dict(symbol=symbol,metric=metric,target=target)
                first,_=auc(x[period_mask(outcome,2021)],outcome.loc[period_mask(outcome,2021),'SL10__'+target])
                direction=1 if first>=.5 else -1;row['direction']=direction
                for year in range(2021,2027):
                    keep=period_mask(outcome,year);value,n=auc(direction*x[keep],outcome.loc[keep,'SL10__'+target])
                    row['auc_'+str(year)]=value;row['n_'+str(year)]=n
                row['discovery_score']=min(row['auc_2021'],row['auc_2022']) if np.isfinite(row['auc_2021']) and np.isfinite(row['auc_2022']) else np.nan
                row['eligible']=bool(row['n_2021']>=80 and row['n_2022']>=100 and row['discovery_score']>=.55)
                records.append(row)
    table=pd.DataFrame(records);table.to_csv(ROOT/'sentinel-single-stock-audit.csv',index=False)
    baskets=pd.DataFrame(index=calendar);selected=[]
    for target in ['risk20','recovery20']:
        ranking=table[table.target.eq(target)&table.eligible].sort_values(['discovery_score','auc_2022','symbol','metric'],ascending=[False,False,True,True])
        ranking=ranking.drop_duplicates('symbol').head(10)
        for k in [5,10]:
            chosen=ranking.head(k);parts=[]
            if len(chosen)<k:continue
            for row in chosen.itertuples():
                x=metrics[row.metric][row.symbol].reindex(calendar)
                parts.append(pd.Series(empirical(x.loc[training],x,row.direction),index=calendar,name=row.symbol))
                selected.append(dict(basket=target+'_top'+str(k),symbol=row.symbol,metric=row.metric,direction=row.direction,
                    discovery_score=row.discovery_score,auc_2023=row.auc_2023,auc_2024=row.auc_2024,auc_2025=row.auc_2025,auc_2026=row.auc_2026))
            frame=pd.concat(parts,axis=1);baskets['sentinel__'+target+'_top'+str(k)]=frame.mean(axis=1).where(frame.notna().sum(axis=1).ge(.8*k))
    pd.DataFrame(selected).to_csv(ROOT/'sentinel-frozen-baskets.csv',index=False)
    baskets.to_parquet(ROOT/'sentinel-features.parquet');return baskets


def model_score_features():
    ranking=pd.read_parquet(GROUPS/'variants/B/rankings.parquet',columns=['date','symbol','proba_extreme','long_probability','long_auc','long_auc_available_date'])
    known=ranking.long_probability.notna()
    if not pd.to_datetime(ranking.loc[known,'long_auc_available_date']).lt(ranking.loc[known,'date']).all():raise ValueError('Future per-symbol quality score')
    cohorts={'universe':ranking[['date','symbol']],
        'oracle179':pd.concat([pd.read_parquet(GROUPS/'years'/str(y)/'pool.parquet',columns=['date','symbol']) for y in range(2021,2027)])}
    for name,case in [('B10','CONTROL'),('SL10','SL10')]:cohorts[name]=pd.read_parquet(SOURCE/'variants'/case/'signals.parquet',columns=['trade_date','symbol']).rename(columns={'trade_date':'date'})
    result=[]
    for name,keys in cohorts.items():
        f=ranking.merge(keys,on=['date','symbol'],how='inner',validate='one_to_one')
        g=f.groupby('date')[['proba_extreme','long_probability','long_auc']]
        for agg in ['median','mean','std']:
            result.append(getattr(g,agg)().add_prefix('scores_'+name+'__'+agg+'__'))
        for col in ['long_probability','long_auc']:
            a=f.assign(share=f[col].gt(.5).where(f[col].notna()))
            result.append(a.groupby('date').share.mean().rename('scores_'+name+'__'+col+'_above50'))
    return pd.concat(result,axis=1)


def extended_panel(base,extra):
    f=base.join(extra);f=f.apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan).astype(float)
    good=f.notna().rolling(6,min_periods=6).sum().eq(6)
    delta=(f-f.shift(5)).where(good).add_suffix('__delta5')
    smooth=f.rolling(5,min_periods=5).mean().add_suffix('__mean5')
    return pd.concat([f,delta,smooth],axis=1)


def screen(features,outcome):
    records=[]
    for number,col in enumerate(features):
        x=features[col].to_numpy(float)
        if np.isfinite(x).sum()<180 or np.nanstd(x)==0:continue
        for target in ['risk20','recovery20']:
            row=dict(feature=col,family=family(col),target=target)
            first,_=auc(x[period_mask(outcome,2021)],outcome.loc[period_mask(outcome,2021),'SL10__'+target])
            direction=1 if first>=.5 else -1;row['direction']=direction
            for year in range(2021,2027):
                keep=period_mask(outcome,year);value,n=auc(direction*x[keep],outcome.loc[keep,'SL10__'+target])
                row['auc_'+str(year)]=value;row['n_'+str(year)]=n
            row['discovery_score']=min(row['auc_2021'],row['auc_2022']) if np.isfinite(row['auc_2021']) and np.isfinite(row['auc_2022']) else np.nan
            row['eligible']=bool(row['n_2021']>=80 and row['n_2022']>=100 and row['discovery_score']>=.55)
            records.append(row)
        if number%500==0:
            atomic_json(ROOT/'audit-progress.json',dict(status='SCREENING',completed=number,total=len(features.columns)))
    result=pd.DataFrame(records);result.to_csv(ROOT/'feature-screen-all-years.csv',index=False);return result


def select_features(screening,features,training):
    selected=[]
    for target in ['risk20','recovery20']:
        previous=[]
        for group in ['market','internal','account','sentinel']:
            candidates=screening[screening.target.eq(target)&screening.family.eq(group)&screening.eligible]
            candidates=candidates.sort_values(['discovery_score','auc_2022','feature'],ascending=[False,False,True])
            for _,row in candidates.iterrows():
                pair=features.loc[training,previous+[row.feature]].corr(method='spearman')
                if previous and pair.loc[row.feature,previous].abs().gt(.8).any():continue
                selected.append(row.to_dict());previous.append(row.feature);break
    result=pd.DataFrame(selected,columns=screening.columns)
    result.to_csv(ROOT/'frozen-selected-features.csv',index=False)
    return result


def state_machine(scores,on_threshold,off_threshold,*,off_confirm):
    active=False;down=up=age=0;records=[]
    for day,row in scores.iterrows():
        transition=''
        if not active:
            down=down+1 if pd.notna(row.risk) and row.risk>on_threshold and row.risk_votes>=2 else 0
            up=0
            if down>=2:active=True;transition='ON';age=0;down=0
        else:
            age+=1;down=0
            up=up+1 if pd.notna(row.recovery) and row.recovery>=off_threshold and row.recovery_votes>=2 else 0
            if age>=3 and up>=off_confirm:active=False;transition='OFF';up=0;age=0
        records.append(dict(date=day,active=active,transition=transition))
    return pd.DataFrame(records).set_index('date')


def block_auc(x,y,seed=42,repeats=300):
    rng=np.random.default_rng(seed);x=np.asarray(x,float);y=np.asarray(y,float);values=[];n=len(x)
    if n<60:return [np.nan,np.nan]
    for _ in range(repeats):
        starts=rng.integers(0,max(n-19,1),size=int(np.ceil(n/20)))
        idx=np.concatenate([np.arange(s,min(s+20,n)) for s in starts])[:n]
        value,_=auc(x[idx],y[idx])
        if np.isfinite(value):values.append(value)
    return list(np.quantile(values,[.025,.975])) if values else [np.nan,np.nan]


def rule_metrics(name,score,states,outcome):
    rows=[];events=[]
    for family_name in ['B','SL10']:
        for scope,keep in [('2024',outcome.index.year==2024),('2025',outcome.index.year==2025),('2026',outcome.index.year==2026),('2025-2026',outcome.index.year>=2025)]:
            a=states.reindex(outcome.index);mask=keep&a.active.notna()&outcome[family_name+'__risk20'].notna()
            y=outcome.loc[mask,family_name+'__risk20'];flag=a.loc[mask,'active'].astype(bool)
            tp=float(flag[y.eq(1)].mean()) if y.eq(1).any() else np.nan
            tn=float((~flag[y.eq(0)]).mean()) if y.eq(0).any() else np.nan
            value,n=auc(score.reindex(outcome.index).loc[mask,'risk'],y)
            changes=a.loc[mask].loc[lambda f:f.transition.isin(['ON','OFF'])]
            ons=changes.index[changes.transition.eq('ON')];offs=changes.index[changes.transition.eq('OFF')]
            on_good=outcome.loc[ons,family_name+'__risk20'];off_good=outcome.loc[offs,family_name+'__recovery20']
            rows.append(dict(rule=name,family=family_name,scope=scope,days=int(mask.sum()),auc=value,
                balanced_accuracy=(tp+tn)/2,active_pct=100*flag.mean(),on_events=len(ons),off_events=len(offs),
                on_risk_precision=float(on_good.mean()) if len(ons) else np.nan,
                off_safe_recovery_precision=float(off_good.mean()) if len(offs) else np.nan,
                off_positive20=float(outcome.loc[offs,family_name+'__return20'].gt(0).mean()) if len(offs) else np.nan,
                flagged_mean_forward20=float(outcome.loc[mask,family_name+'__return20'][flag].mean()),
                other_mean_forward20=float(outcome.loc[mask,family_name+'__return20'][~flag].mean()),
                ci_low=block_auc(score.reindex(outcome.index).loc[mask,'risk'],y)[0] if scope=='2025-2026' else np.nan))
        for day,row in states.loc[states.transition.isin(['ON','OFF'])].iterrows():
            if day not in outcome.index:continue
            events.append(dict(rule=name,family=family_name,date=str(day.date()),event=row.transition,
                future_return20=outcome.loc[day,family_name+'__return20'],future_trough20=outcome.loc[day,family_name+'__trough20']))
    return rows,events


def evaluate_rules(features,outcome,screening):
    train=(features.index.year>=2021)&(features.index.year<=2022)&outcome.SL10__available20.lt('2023-01-01')
    calibration=(features.index.year==2023)&outcome.SL10__available20.lt('2024-01-01')
    selected=select_features(screening,features,train);all_rows=[];all_events=[];contracts=[]
    sets=[['market','internal','account'],['market','internal','account','sentinel'],['internal','account','sentinel']]
    for groups in sets:
        streams={};votes={};used={}
        for target,score_name,q in [('risk20','risk',.75),('recovery20','recovery',.50)]:
            chosen=selected[selected.target.eq(target)&selected.family.isin(groups)]
            if set(chosen.family)!=set(groups):break
            parts={}
            for row in chosen.itertuples():parts[row.feature]=empirical(features.loc[train,row.feature],features[row.feature],row.direction)
            p=pd.DataFrame(parts,index=features.index)
            thresholds=p.loc[calibration].quantile(q)
            streams[score_name]=p.mean(axis=1).where(p.notna().sum(axis=1).ge(2))
            votes[score_name+'_votes']=p.ge(thresholds,axis=1).sum(axis=1)
            used[score_name]=chosen[['feature','direction']].to_dict('records')
        if len(streams)!=2:continue
        scores=pd.DataFrame({**streams,**votes});on=float(scores.loc[calibration,'risk'].quantile(.90));off=float(scores.loc[calibration,'recovery'].quantile(.50))
        for confirmation in [1,2]:
            name='_'.join(groups)+'_OFF'+str(confirmation);test=scores.loc['2024-01-01':]
            states=state_machine(test,on,off,off_confirm=confirmation)
            for cut in ['2024-11-29','2025-05-30']:
                pd.testing.assert_frame_equal(states.loc[:cut],state_machine(test.loc[:cut],on,off,off_confirm=confirmation))
            states.join(test).to_parquet(ROOT/(name+'-timeline.parquet'))
            rows,events=rule_metrics(name,scores,states,outcome);all_rows+=rows;all_events+=events
            contracts.append(dict(rule=name,features=used,on_threshold=on,off_threshold=off,on_confirm=2,off_confirm=confirmation,
                minimum_hold=3,calibration_end='2023-12-31',evaluation_start='2024-01-01',economic_replay=False))
    atomic_json(ROOT/'rule-contracts.json',contracts)
    table=pd.DataFrame(all_rows);table.to_csv(ROOT/'rule-metrics.csv',index=False);pd.DataFrame(all_events).to_csv(ROOT/'rule-events.csv',index=False)
    if table.empty:return dict(status='NO_SUPPORTED_COMBINATION',reason='Insufficient stable independent feature families')
    validation=table[table.family.eq('SL10')&table.scope.eq('2024')].copy()
    eligible=validation[validation.auc.ge(.55)&validation.balanced_accuracy.ge(.55)&validation.active_pct.le(40)&validation.on_events.ge(2)&validation.off_events.ge(2)]
    if eligible.empty:return dict(status='NO_RULE_PASSES_2024_VALIDATION',selection_uses='2024 only',rules=len(contracts))
    champion=eligible.sort_values(['balanced_accuracy','auc','rule'],ascending=[False,False,True]).iloc[0].rule
    evaluation=table[table.rule.eq(champion)&table.family.eq('SL10')&table.scope.isin(['2025','2026','2025-2026'])]
    combined=evaluation[evaluation.scope.eq('2025-2026')].iloc[0]
    reliable=bool(evaluation.auc.gt(.5).all() and combined.ci_low>.5 and combined.on_events>=10 and combined.off_events>=10 and combined.off_positive20>=.7)
    return dict(status='EXPLORATORY_SIGNAL_ONLY' if reliable else 'NOT_RELIABLE_ON_2025_2026',rule=champion,
        selection_uses='2024 only',evaluation_uses='2025-2026',strict_independent_holdout=False,
        reliable_criterion_passed=reliable,economic_replay=False)


def main():
    atomic_json(ROOT/'analysis-protocol.json',dict(
        script_sha256=digest(Path(__file__)),direction_discovery=2021,feature_confirmation=2022,threshold_calibration=2023,
        nomination_year=2024,evaluation_years=[2025,2026],target_family='SL10',other_family_control='B',
        feature_selection=dict(min_auc_both_discovery_years=.55,min_n2021=80,min_n2022=100,
            max_absolute_spearman=.8,max_features_per_family=1,family_order=['market','internal','account','sentinel']),
        sentinel_selection=dict(coverage2021_2022=.95,max_daily_jump=.5,max_zero_return_fraction=.8,
            baskets=[5,10],direction_and_ranking_uses_only=[2021,2022],no_replacement_in_future=True),
        rules=dict(count=6,on_quantile=.90,off_quantile=.50,on_confirm=2,off_confirm=[1,2],minimum_hold=3,
            on_family_vote_quantile=.75,off_family_vote_quantile=.50,min_family_votes=2),
        nomination=dict(min_auc2024=.55,min_balanced_accuracy2024=.55,max_active_pct2024=40,min_on=2,min_off=2,
            ranking='balanced_accuracy then AUC then lexical rule name; 2024 only'),
        confirmation=dict(each2025_2026_auc_above=.5,combined_block20_auc_ci_low_above=.5,min_on_events=10,
            min_off_events=10,min_positive_off20=.7,bootstrap=300,independent_holdout=False),
        no_economic_backtest=True,no_Oracle_per_symbol_training=True,production_changes=False))
    atomic_json(ROOT/'audit-progress.json',dict(status='SENTINELS'))
    base=pd.read_parquet(ROOT/'daily-features.parquet');outcome=pd.read_parquet(ROOT/'future-outcomes.parquet').reindex(base.index)
    sentinel=sentinel_panel(outcome)
    features=extended_panel(base,model_score_features()).join(sentinel)
    features.to_parquet(ROOT/'all-audit-features.parquet')
    inventory=pd.DataFrame({'feature':features.columns,'family':[family(c) for c in features],
        'known':features.notna().sum().to_numpy(),'unique':features.nunique().to_numpy()})
    inventory.to_csv(ROOT/'complete-feature-inventory.csv',index=False)
    table=screen(features,outcome)
    atomic_json(ROOT/'audit-progress.json',dict(status='COMBINATIONS',features=len(features.columns),screened=len(table)))
    result=evaluate_rules(features,outcome,table)
    atomic_json(ROOT/'audit-conclusion.json',dict(**result,features=len(features.columns),single_stock_tests=len(pd.read_csv(ROOT/'sentinel-single-stock-audit.csv')),
        no_Oracle_training=True,no_per_symbol_training=True,production_changes=False,provider_calls=0,SQL_writes=0,
        feature_sha256=digest(ROOT/'all-audit-features.parquet')))
    atomic_json(ROOT/'audit-progress.json',dict(status='COMPLETED_RESEARCH_AUDIT',conclusion=result))
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
