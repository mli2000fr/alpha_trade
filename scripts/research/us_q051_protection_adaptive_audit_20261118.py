"""Secondary declared diagnostic: past-only relative levels and 2023 stability.

Addresses calibration-level shifts identified in the initial audit. All years
have already been examined; cannot constitute a new independent confirmation.
"""
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.research import us_q051_protection_feature_audit_20261118 as base
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=base.ROOT/'adaptive-secondary-v1'


def relative_levels(features):
    # J is observed: ranking it among the preceding252 observations and J is
    # causal. No centered window, future fit or filling of missing observations.
    return features.rolling(253,min_periods=64).rank(pct=True)


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    atomic_json(ROOT/'protocol.json',dict(script_sha256=digest(Path(__file__)),
        status='SECONDARY_EXPLORATORY_AFTER_PRIMARY_AUDIT',already_observed_years=[2021,2022,2023,2024,2025,2026],
        rationale='Absolute annual model/cohort levels drift; test relative trailing levels and require past2023 stability',
        transform='rank of observed J within prior252+J, minimum64 observations, no future',
        selection='direction2021; AUC>=.55 on2021/22 and>=.53 on2023; rank by minimum AUC2021-23',
        rules=dict(groups=[['market','internal','account'],['market','internal','account','sentinel']],
            on_quantile2023=.85,off_quantile2023=.50,on_confirm=2,off_confirm=[1,2],minimum_hold=3),
        outcome='Same future shadow equity risk20/recovery20 as primary, not portfolio counterfactual',
        independent_holdout=False,production_changes=False))
    raw=pd.read_parquet(base.ROOT/'all-audit-features.parquet')
    outcome=pd.read_parquet(base.ROOT/'future-outcomes.parquet').reindex(raw.index)
    features=relative_levels(raw)
    for cut in ['2023-12-29','2024-11-29','2025-05-30']:
        pd.testing.assert_frame_equal(features.loc[:cut],relative_levels(raw.loc[:cut]))
    features.to_parquet(ROOT/'relative-features.parquet')
    with patch.object(base,'ROOT',ROOT):table=base.screen(features,outcome)
    table['eligible']=table.eligible&table.auc_2023.ge(.53)
    table['discovery_score']=table[['auc_2021','auc_2022','auc_2023']].min(axis=1)
    table.to_csv(ROOT/'relative-feature-screen.csv',index=False)
    training=(features.index.year>=2021)&(features.index.year<=2022)&outcome.SL10__available20.lt('2023-01-01')
    calibration=(features.index.year==2023)&outcome.SL10__available20.lt('2024-01-01')
    with patch.object(base,'ROOT',ROOT):selected=base.select_features(table,features,training)
    results=[];events=[];contracts=[]
    for groups in [['market','internal','account'],['market','internal','account','sentinel']]:
        streams={};votes={};used={}
        for target,name,q in [('risk20','risk',.75),('recovery20','recovery',.5)]:
            chosen=selected[selected.target.eq(target)&selected.family.isin(groups)]
            if set(chosen.family)!=set(groups):break
            p=pd.DataFrame({r.feature:base.empirical(features.loc[training,r.feature],features[r.feature],r.direction) for r in chosen.itertuples()},index=features.index)
            streams[name]=p.mean(axis=1).where(p.notna().sum(axis=1).ge(2))
            votes[name+'_votes']=p.ge(p.loc[calibration].quantile(q),axis=1).sum(axis=1)
            used[name]=chosen[['feature','direction']].to_dict('records')
        if len(streams)!=2:continue
        score=pd.DataFrame({**streams,**votes});on=float(score.loc[calibration,'risk'].quantile(.85));off=float(score.loc[calibration,'recovery'].quantile(.5))
        for confirmation in [1,2]:
            name='_'.join(groups)+'_OFF'+str(confirmation)
            state=base.state_machine(score.loc['2024-01-01':],on,off,off_confirm=confirmation)
            state.join(score).to_parquet(ROOT/(name+'-timeline.parquet'))
            rows,changes=base.rule_metrics(name,score,state,outcome);results+=rows;events+=changes
            contracts.append(dict(rule=name,features=used,on=on,off=off,confirmation=confirmation))
    atomic_json(ROOT/'rule-contracts.json',contracts)
    metrics=pd.DataFrame(results);metrics.to_csv(ROOT/'rule-metrics.csv',index=False)
    pd.DataFrame(events).to_csv(ROOT/'rule-events.csv',index=False)
    if metrics.empty:conclusion=dict(status='NO_SUPPORTED_FAMILY_COMBINATION',rules=len(contracts))
    else:
        a=metrics[metrics.family.eq('SL10')&metrics.scope.eq('2024')]
        eligible=a[a.auc.ge(.55)&a.balanced_accuracy.ge(.55)&a.active_pct.le(40)&a.on_events.ge(2)&a.off_events.ge(2)]
        conclusion=dict(status='NO_RULE_PASSES_2024_VALIDATION',rules=len(contracts))
        if not eligible.empty:
            selected=eligible.sort_values(['balanced_accuracy','auc','rule'],ascending=[False,False,True]).iloc[0].rule
            later=metrics[metrics.rule.eq(selected)&metrics.family.eq('SL10')&metrics.scope.isin(['2025','2026','2025-2026'])]
            combined=later[later.scope.eq('2025-2026')].iloc[0]
            passed=bool(later.auc.gt(.5).all() and combined.ci_low>.5 and combined.on_events>=10 and combined.off_events>=10 and combined.off_positive20>=.7)
            conclusion=dict(status='EXPLORATORY_ONLY' if passed else 'NOT_RELIABLE_ON_2025_2026',rule=selected,criterion_passed=passed)
    atomic_json(ROOT/'conclusion.json',dict(**conclusion,independent_holdout=False,economic_replay=False))
    print(conclusion,flush=True)


if __name__=='__main__':main()
