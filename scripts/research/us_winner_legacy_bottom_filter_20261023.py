"""Exact +12.92% HALF_CONTROL replication, then one frozen J-only ranking veto."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from pathlib import Path
import logging
import math
import json

import numpy as np
import pandas as pd

from scripts.research import us_oracle_pyramiding as original
from scripts.research.us_oracle_pyramiding_audit import audit_arm
from scripts.research.us_oracle_path_trend_ranking_20261022 import (
    read,digest,verify,save,recent_inputs,
)
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.security_continuity import DEFAULT_REGISTRY_PATH,load_security_discontinuities

ROOT=Path('artifacts/research/us_winner_legacy_bottom_filter/20261023-v1')
REFERENCE=Path('artifacts/research/us_oracle_pyramiding/20261020-v1')
TREND=Path('artifacts/research/us_oracle_path_trend_ranking/20261022-v2')
FEATURE_PRICES=Path('artifacts/research/us_news_gpt_bullish_portfolio/20261015-v1/prices.parquet')
DOC=Path('doc/ml/winner_legacy_filtre_protocole_20261023.md')
ARMS={'WINNER_LEGACY_ONLY':10,'DROP_BOTTOM3_KEEP7':7,'DROP_BOTTOM5_KEEP5':5}
LOG=logging.getLogger(__name__)


def frozen_filter(pool):
    required=['date','symbol','rank','vol_ratio_20_60','J_qualified']
    a=pool[required].copy()
    if a.duplicated(['date','symbol']).any() or not a.groupby('date')['rank'].apply(lambda x:sorted(x)==list(range(1,11))).all():
        raise ValueError('Old complete TOP10 required before qualification')
    a['known']=a.J_qualified & np.isfinite(a.vol_ratio_20_60) & a.vol_ratio_20_60.gt(0)
    a['all_ten_known']=a.groupby('date').known.transform('all')
    a['priority']=a.vol_ratio_20_60.where(a.known,np.inf)
    a=a.sort_values(['date','priority','rank','symbol'])
    a['estimated_rank']=a.groupby('date').cumcount()+1
    for arm,n in ARMS.items():
        a[arm]=~a.all_ten_known | a.estimated_rank.le(n)
    a['filter_reason']=np.where(a.all_ten_known,'QUALIFIED_J_RANKING','PASSTHROUGH_UNKNOWN_J_TOP10')
    return a.sort_values(['date','rank','symbol']).reset_index(drop=True)


def veto_tape(tape,kept):
    """Only suppress initial attempts; bars/meta/expiry/timeline never change."""
    result=dict(tape)
    result['starts']={t:[pid for pid in ids if pid in kept] for t,ids in tape['starts'].items()}
    return result


def exact_control(result,cost):
    label=f'HALF_CONTROL-{round(cost*10000)}bps'
    for name,frame in result.items():
        archived=pd.read_parquet(REFERENCE/label/f'{name}.parquet')
        pd.testing.assert_frame_equal(frame,archived,check_exact=True)
    annual=original.annual_summary(**{k:result[k] for k in ['marks','lots','orders','fills']})
    previous=[r for r in read(REFERENCE/'report.json')['summaries'] if r['arm']=='HALF_CONTROL' and r['cost_bps']==round(cost*10000)]
    if len(annual)!=len(previous):raise AssertionError('Archived annual control count changed')
    for a,b in zip(annual,previous):
        for key,value in a.items():
            if isinstance(value,(int,float)) and key in b and not math.isclose(float(value),float(b[key]),abs_tol=1e-10,rel_tol=0):
                raise AssertionError(f'Archived annual control changed: {key}')
    return dict(cost_bps=round(cost*10000),all_four_frames_exact=True,annual_metrics_reproduced=True,
                returns={str(x['year']):x['return_pct'] for x in annual})


def prepare(root):
    if root.exists():raise FileExistsError('Fresh immutable output required')
    old=read(REFERENCE/'protocol.json');verify(old['sources'])
    ready=read(REFERENCE/'prepared.json');verify({str(REFERENCE/k):v for k,v in ready['files'].items()})
    report=read(REFERENCE/'report.json');verify({str(REFERENCE/k):v for k,v in report['files'].items()})
    audit=read(REFERENCE/'final-audit.json')
    if audit['status']!='PASS_SHARED_CASH_RESEARCH_AUDIT' or audit['report_sha256']!=digest(REFERENCE/'report.json'):
        raise ValueError('Old cash audit absent')
    prior=read(TREND/'protocol.json');verify(prior['sources'])
    source={**old['sources'],str(FEATURE_PRICES):digest(FEATURE_PRICES)}
    expected=next(v for k,v in prior['sources'].items() if Path(k)==FEATURE_PRICES)
    if source[str(FEATURE_PRICES)]!=expected:raise ValueError('Auxiliary price cache drift')
    files=[Path(__file__),Path('tests/test_us_winner_legacy_bottom_filter_20261023.py'),DOC,
        REFERENCE/'protocol.json',REFERENCE/'prepared.json',REFERENCE/'report.json',REFERENCE/'final-audit.json',
        TREND/'protocol.json',TREND/'observable-top10.parquet',DEFAULT_REGISTRY_PATH,
        Path('scripts/research/us_oracle_path_trend_ranking_20261022.py'),
        Path('scripts/research/us_oracle_path_protection_dataset.py'),Path('modelFactory/features.py'),
        Path('modelFactory/oracle/security_continuity.py')]
    files.extend(REFERENCE/k for k in ready['files'])
    files.extend(REFERENCE/k for k in report['files'] if k.startswith('HALF_CONTROL-'))
    source.update({str(x):digest(x) for x in files})
    root.mkdir(parents=True)
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=source,
        reference=str(REFERENCE),original_portfolio_contract=old,filter='low vol20/60 first, retain7or5, preserve original Oracle priority',
        unknown_J='Whole date passthrough; never arbitrary loser or baseline exclusion',arms=ARMS,costs=[.0008,.0025],
        exact_control_required=True,training=False,SQL_reads=0,SQL_writes=False,provider_calls=0,
        broker_calls=0,production_changed=False,new_holdout=False)
    save(root/'protocol.json',p)
    pool=pd.read_parquet(original.PARENT/'selected.parquet',columns=['date','symbol','rank','score'])
    pool=pool.loc[pool.date.dt.year.ge(2025)].copy()
    pool['oracle_rank']=pool['rank'];pool['fold_start']=pd.NaT
    prices=pd.read_parquet(FEATURE_PRICES)
    days=nyse_sessions('2023-01-03','2026-10-09')
    features,checks=recent_inputs(pool,prices,days,load_security_discontinuities())
    common=pd.read_parquet(TREND/'observable-top10.parquet',columns=['date','symbol','vol_ratio_20_60','J_qualified'])
    compared=features[['date','symbol','vol_ratio_20_60','J_qualified']].merge(common,on=['date','symbol'],suffixes=('_new','_old'),validate='one_to_one')
    good=compared.J_qualified_new & compared.J_qualified_old
    if not np.allclose(compared.loc[good,'vol_ratio_20_60_new'],compared.loc[good,'vol_ratio_20_60_old'],rtol=0,atol=1e-12):
        raise ValueError('Ratio definition differs from frozen prior audit')
    decisions=frozen_filter(features)
    candidates=pd.read_parquet(REFERENCE/'candidates.parquet')
    candidates=candidates.merge(decisions,on=['date','symbol','rank'],how='left',validate='one_to_one')
    if len(candidates)!=213 or candidates[list(ARMS)].isna().any().any():raise ValueError('Lost original213campaigns')
    decisions.to_parquet(root/'all-original-top10-decisions.parquet',index=False)
    candidates.to_parquet(root/'campaign-filter.parquet',index=False)
    save(root/'prefix-checks.json',dict(checks=checks,shared_qualified_ratio_comparisons=int(good.sum()),
        same_ratio_tolerance=1e-12,known_dates=int(decisions.loc[decisions.all_ten_known,'date'].nunique()),
        passthrough_dates=int(decisions.loc[~decisions.all_ten_known,'date'].nunique())))
    save(root/'prepared.json',dict(files={x.name:digest(x) for x in root.iterdir() if x.name!='progress.json'},
        original_candidates=213,selected_all_top10_rows=len(decisions)))
    return p,candidates


def extended(annual,result):
    marks,lots=result['marks'],result['lots']
    for row in annual:
        year=row['year'];g=marks[marks.year.eq(year)]
        row['mean_gross_capital_usd']=float(g.gross.mean())
        exited=lots[pd.to_datetime(lots.exit_time,utc=True).dt.year.eq(year)].copy()
        for name,mask in [('winning',exited.net.gt(original.EPS)),('losing',exited.net.lt(-original.EPS))]:
            sub=exited[mask]
            row[f'mean_{name}_pnl_usd']=float(sub.net.mean()) if len(sub) else None
            row[f'mean_{name}_return_pct']=float((100*sub.net/(sub.quantity*sub.entry_price)).mean()) if len(sub) else None
            row[f'mean_{name}_calendar_days']=float(((sub.exit_time-sub.entry_time).dt.total_seconds()/86400).mean()) if len(sub) else None
    return annual


def run(root):
    p,candidates=prepare(root)
    bars=pd.read_parquet(REFERENCE/'bars.parquet');calendar=pd.read_parquet(REFERENCE/'calendar.parquet')
    originals=pd.read_parquet(REFERENCE/'candidates.parquet')
    tape=original.tapes(bars,originals,calendar)
    summaries=[];audits=[];control=[];files={}
    for arm in ARMS:(root/arm).mkdir()
    completed=0
    # BOTH exact baselines must pass before any filtered economic result.
    jobs=[('WINNER_LEGACY_ONLY',c) for c in (.0008,.0025)]+[(a,c) for c in (.0008,.0025) for a in list(ARMS)[1:]]
    for arm,cost in jobs:
        retained=set(candidates.loc[candidates[arm],'pair_id'])
        selected_tape=tape if arm=='WINNER_LEGACY_ONLY' else veto_tape(tape,retained)
        result=original.simulate(selected_tape,'HALF_CONTROL',cost)
        if arm=='WINNER_LEGACY_ONLY':control.append(exact_control(result,cost))
        label=f'HALF_CONTROL-{round(cost*10000)}bps';folder=root/arm/label;folder.mkdir()
        for name,frame in result.items():
            frame.to_parquet(folder/f'{name}.parquet',index=False)
            files[str((folder/f'{name}.parquet').relative_to(root))]=digest(folder/f'{name}.parquet')
        annual=original.annual_summary(**{k:result[k] for k in ['marks','lots','orders','fills']})
        local=[dict(arm='HALF_CONTROL',cost_bps=round(cost*10000),**x) for x in annual]
        record_path=root/arm/'report.json'
        # Per-arm summary can be written only once, after its second cost case.
        summaries.extend([dict(policy=arm,cost_bps=round(cost*10000),retained_campaigns=len(retained),**x) for x in extended(annual,result)])
        if cost==.0025:
            all_local=[dict(arm='HALF_CONTROL',**{k:v for k,v in x.items() if k not in ['policy']}) for x in summaries if x['policy']==arm]
            save(record_path,dict(summaries=all_local))
        completed+=1
        original.atomic_json(root/'progress.json',dict(status='REPLAYING',completed=completed,total=6,current=f'{arm}-{round(cost*10000)}bps',
            baseline_reproductions=len(control)))
        pd.DataFrame(summaries).to_csv(root/'annual-summary.partial.csv',index=False)
        LOG.info('%s %sbps: %s',arm,round(cost*10000),[(x['year'],round(x['return_pct'],4)) for x in annual])
    save(root/'exact-control-audit.json',control)
    # Existing independent sizing/stop/cash reconstruction; no weakened checks.
    for arm in ARMS:
        subset=originals[originals.pair_id.isin(set(candidates.loc[candidates[arm],'pair_id']))]
        for bps in (8,25):
            a=audit_arm(root/arm,f'HALF_CONTROL-{bps}bps',bars,subset,calendar);a['policy']=arm;audits.append(a)
            original.atomic_json(root/'progress.json',dict(status='AUDITING',completed=len(audits),total=6))
    pd.DataFrame(summaries).to_csv(root/'annual-summary.csv',index=False)
    verify(p['sources'])
    files.update({str((root/arm/'report.json').relative_to(root)):digest(root/arm/'report.json') for arm in ARMS})
    files.update({x.name:digest(x) for x in root.iterdir() if x.suffix in ('.json','.parquet','.csv') and x.name not in ['progress.json','report.json','final-audit.json']})
    save(root/'report.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',summaries=summaries,files=files,
        exact_reference_reproduced=True,primary_bps=8,stress_bps=25,independent_holdout=False,
        SQL_writes=False,provider_calls=0,training=False,production_changed=False))
    save(root/'final-audit.json',dict(status='PASS_EXACT_REFERENCE_AND_FILTERED_SHARED_CASH_RECONSTRUCTION',
        exact_controls=control,results=audits,report_sha256=digest(root/'report.json'),independent_human_review=False))
    original.atomic_json(root/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',completed=6,total=6))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT)
    args=parser.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbidden(*args,**kwargs):raise RuntimeError('Offline research; HTTP forbidden')
    requests.Session.request=forbidden
    try:run(args.output)
    except Exception as exc:
        if args.output.exists():original.atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
