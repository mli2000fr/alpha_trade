"""Offline directional diagnostics on sealed US collection snapshots, no fitting."""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
import yaml

from scripts.research.us_options_equal_mix_20261026 import read,write,digest
from scripts.research.us_options_top20_refresh_20261030 import labels_for_path
from scripts.research.us_consensus_reliability_20261022 import row_quality
from service.options_directional.features import _rows,_latest,build_features,select_top
from service.options_directional.config import OptionsFilterConfig
from common.options_directional_contract import DTE_TARGET,ATM_MAX_DISTANCE
from modelFactory.oracle.security_continuity import load_security_discontinuities

KEY=['signal_day','symbol']
SCORES=['volume_score','oi_score','options_score','revisions30_score','eps30_score',
        'revenue_change_score','eps_change_score','sentiment1_score','sentiment3_score','options_consensus_score']


def independent_options(snapshots,volumes,spots,day,cutoff):
    """Same-tenor definitions as production, singles retained if other leg absent."""
    oi,flow=_rows(snapshots,day,cutoff),_rows(volumes,day,cutoff,volume=True)
    result={}
    if not oi.empty:
        oi['strike']=pd.to_numeric(oi.strike,errors='coerce')
        oi['open_interest']=pd.to_numeric(oi.open_interest,errors='coerce')
        oi=_latest(oi,['symbol','contract_symbol'],['open_interest','strike','expiration_date','option_type','payload_hash'])
        oi['distance']=(oi.strike/oi.symbol.map(spots)-1).abs()
        oi=oi[oi.distance.le(ATM_MAX_DISTANCE)&np.isfinite(oi.open_interest)&oi.open_interest.ge(0)]
        keys=['symbol','expiration_date','strike']
        pair=oi[oi.option_type.eq('CALL')].merge(oi[oi.option_type.eq('PUT')],on=keys,suffixes=('_call','_put'),validate='one_to_one')
        if not pair.empty:
            pair['tenor_distance']=(pair.dte_call-DTE_TARGET).abs()
            pair=pair.sort_values(['symbol','tenor_distance','distance_call','expiration_date','strike'],kind='stable').drop_duplicates('symbol')
            for r in pair.itertuples():
                result.setdefault(r.symbol,{})['oi_feature']=float(np.log1p(r.open_interest_call)-np.log1p(r.open_interest_put))
    if not flow.empty:
        flow['volume']=pd.to_numeric(flow.volume,errors='coerce')
        flow=_latest(flow,['symbol','contract_symbol','bar_timestamp'],['volume','payload_hash','option_type','expiration_date'])
        flow['bad']=~np.isfinite(flow.volume)|flow.volume.lt(0)
        flow=flow.groupby(['symbol','expiration_date','option_type'],as_index=False).agg(
            volume=('volume','sum'),bad=('bad','any'),dte=('dte','first'))
        flow=flow[~flow.bad]
        pair=flow[flow.option_type.eq('CALL')].merge(flow[flow.option_type.eq('PUT')],on=['symbol','expiration_date'],suffixes=('_call','_put'),validate='one_to_one')
        if not pair.empty:
            pair['tenor_distance']=(pair.dte_call-DTE_TARGET).abs()
            pair=pair.sort_values(['symbol','tenor_distance','expiration_date'],kind='stable').drop_duplicates('symbol')
            for r in pair.itertuples():
                result.setdefault(r.symbol,{})['volume_feature']=float(np.log1p(r.volume_call)-np.log1p(r.volume_put))
    return result


def qualify_consensus(raw,runs):
    checks={int(r['id']):row_quality(r,runs) for r in raw.to_dict('records')}
    f=raw.copy()
    f['known_at']=pd.to_datetime([checks[int(i)]['conservative_available'] for i in f.id],utc=True)
    f['raw_ok']=[checks[int(i)]['raw_normalization_ok'] and checks[int(i)]['run_receipt_ok'] for i in f.id]
    f['fiscal_period_end']=pd.to_datetime(f.fiscal_period_end)
    for col in ('eps_range_ok','revenue_range_ok'):
        f[col]=[checks[int(i)][col] for i in f.id]
    return f,checks


def consensus_for_candidate(f,day,decision,prior_decision):
    missing=dict(consensus_reason='NO_FRESH_QUALIFIED_RECEIPT',consensus_id=None,
                 revisions30=np.nan,eps30=np.nan,revenue_change=np.nan,eps_change=np.nan)
    eligible=f[f.raw_ok & f.known_at.lt(decision)&f.known_at.ge(decision-pd.Timedelta(hours=72))
        & f.fiscal_period_end.between(day-pd.Timedelta(days=100),day+pd.Timedelta(days=100))]
    if eligible.empty:return missing
    r=eligible.sort_values(['fiscal_period_end','known_at','id']).iloc[-1]
    result=dict(missing,consensus_reason='RESEARCH_ONLY_BASIS_NOT_IDENTIFIED',consensus_id=int(r.id),consensus_known_at=r.known_at)
    count=r.eps_analyst_count
    if pd.notna(count) and count>=3 and r.eps_range_ok:
        up,down=r.revisions_up_30d,r.revisions_down_30d
        if all(pd.notna(x) and np.isfinite(x) and x>=0 for x in (up,down)):
            result['revisions30']=float((up-down)/(up+down)) if up+down else 0.
        now,prior=r.eps_current,r.eps_30d_ago
        if all(pd.notna(x) and np.isfinite(x) for x in (now,prior)) and prior!=0:
            result['eps30']=float((now-prior)/abs(prior))
    older=f[f.raw_ok&f.fiscal_period_end.eq(r.fiscal_period_end)&f.known_at.lt(prior_decision)
        &f.known_at.ge(prior_decision-pd.Timedelta(hours=72))]
    if not older.empty:
        old=older.sort_values(['known_at','id']).iloc[-1]
        result['consensus_old_id']=int(old.id)
        for metric in ('eps','revenue'):
            a,b=old[metric+'_avg'],r[metric+'_avg'];c,d=old[metric+'_analyst_count'],r[metric+'_analyst_count']
            if (old[metric+'_range_ok'] and r[metric+'_range_ok'] and all(pd.notna(x) and np.isfinite(x) for x in (a,b,c,d))
                    and a!=0 and c==d and c>=3 and (metric!='revenue' or min(a,b)>0)):
                result[metric+'_change']=float((b-a)/abs(a))
    return result


def score_cohort(frame):
    """Freeze ranks before outcomes, with equal weights and no missing-leg imputation."""
    f=frame.copy()
    features={'volume':'volume_feature','oi':'oi_feature','revisions30':'revisions30',
              'eps30':'eps30','revenue_change':'revenue_change','eps_change':'eps_change',
              'sentiment1':'sentiment1','sentiment3':'sentiment3'}
    for name,col in features.items():
        f[name+'_score']=f.groupby('signal_day')[col].transform(lambda s:(s.rank(method='average')-.5)/s.notna().sum() if s.notna().any() else s)
    # Production ranks on the doubly-covered cohort, not on different denominators.
    f['options_score']=np.nan
    for _,g in f.groupby('signal_day'):
        both=g[g[['volume_feature','oi_feature']].notna().all(axis=1)]
        if len(both)>=4:
            vr=(both.volume_feature.rank(method='average')-.5)/len(both)
            oi=(both.oi_feature.rank(method='average')-.5)/len(both)
            f.loc[both.index,'options_score']=.5*vr+.5*oi
    f['options_consensus_score']=.5*f.options_score+.5*f.revisions30_score
    return f


def signal_metrics(frame,score,cal,horizon):
    covered=frame[frame[score].notna()]
    f=covered[covered.status.eq('LABEL')].copy()
    result=dict(covered=len(covered),valid_n=len(f),symbols=int(f.symbol.nunique()),dates=int(f.signal_day.nunique()),
        statuses=covered.status.value_counts().to_dict(),long_share=float(f.dominant_direction.eq('LONG').mean()) if len(f) else None)
    daily=[]; selections=[]
    for day,g in f.groupby('signal_day'):
        if len(g)>=4 and g.dominant_direction.nunique()==2:
            daily.append(dict(day=str(day.date()),n=len(g),auc=float(roc_auc_score(g.dominant_direction.eq('LONG'),g[score]))))
    # Selection uses all observable scores, never only mature/non-ambiguous labels.
    for day,g in covered.groupby('signal_day'):
        if len(g)<4:continue
        g=g.sort_values([score,'oracle_rank'],ascending=[False,True])
        chosen=g.iloc[:len(g)//2]; baseline=g[g.status.eq('LABEL')]; chosen=chosen[chosen.status.eq('LABEL')]
        if len(chosen) and len(baseline):
            selections.append(dict(day=str(day.date()),selected_n=len(chosen),baseline_n=len(baseline),
                selected_long_n=int(chosen.dominant_direction.eq('LONG').sum()),baseline_long_n=int(baseline.dominant_direction.eq('LONG').sum()),
                selected_long_share=float(chosen.dominant_direction.eq('LONG').mean()),
                baseline_long_share=float(baseline.dominant_direction.eq('LONG').mean())))
    result.update(informative_dates=len(daily),daily=daily,mean_daily_auc=float(np.mean([r['auc'] for r in daily])) if daily else None,
        pooled_auc=float(roc_auc_score(f.dominant_direction.eq('LONG'),f[score])) if len(f) and f.dominant_direction.nunique()==2 else None,
        top_half=selections)
    if selections:
        result['selected_long_share']=sum(r['selected_long_n'] for r in selections)/sum(r['selected_n'] for r in selections)
        result['matched_baseline_long_share']=sum(r['baseline_long_n'] for r in selections)/sum(r['baseline_n'] for r in selections)
        result['equal_date_selection_lift']=float(np.mean([r['selected_long_share']-r['baseline_long_share'] for r in selections]))
    # Only report descriptive uncertainty; overlap is not independent evidence.
    if len(daily)>=2:
        values=np.array([r['auc'] for r in daily]);rng=np.random.default_rng(20261105)
        result['date_bootstrap_ci95_descriptive']=np.quantile(rng.choice(values,(2000,len(values)),replace=True).mean(axis=1),[.025,.975]).tolist()
    session_idx={d:i for i,d in enumerate(cal.day)}
    spaced=[]
    for day in sorted(f.signal_day.unique()):
        if not spaced or session_idx[day]-session_idx[spaced[-1]]>=horizon:spaced.append(day)
    reduced=f[f.signal_day.isin(spaced)]
    result['nonoverlap']=dict(dates=[str(pd.Timestamp(d).date()) for d in spaced],n=len(reduced),
        pooled_auc=float(roc_auc_score(reduced.dominant_direction.eq('LONG'),reduced[score])) if len(reduced) and reduced.dominant_direction.nunique()==2 else None)
    # One outcome per independent company is a separate sensitivity, not extra observations.
    first=f.sort_values(KEY).drop_duplicates('symbol')
    result['first_per_symbol']=dict(n=len(first),auc=float(roc_auc_score(first.dominant_direction.eq('LONG'),first[score])) if len(first) and first.dominant_direction.nunique()==2 else None)
    return result


def analyze(root):
    output=root/'analysis-v2';output.mkdir(exist_ok=False)
    seal=read(root/'snapshot-seal.json')
    for name,h in seal['files'].items():
        if digest(root/name)!=h:raise ValueError('Snapshot changed '+name)
    for name,h in seal['sources'].items():
        if digest(name)!=h:raise ValueError('Source changed '+name)
    p=read(root/'protocol.json');sp=read(root/'snapshot-protocol.json');cutoff=pd.Timestamp(p['cutoff'])
    write(output/'protocol.json',dict(parent_seal=digest(root/'snapshot-seal.json'),
        source_sha256=digest(__file__),scores=SCORES,primary_target='Dominant protected excursion before SL10',
        extra_targets=['Dominant absolute high/low during full H (no stop)','Terminal close H sign, descriptive'],
        training=False,threshold_search=False,api_calls=0,llm_calls=0,SQL_reads=0,SQL_writes=0))
    cal=pd.read_parquet(root/'calendar.parquet');sessions=list(cal.day)
    top=pd.read_parquet(root/'oracle-top50.parquet')
    # A full historical ranking requires all its scores to predate decision.
    raw=pd.read_parquet(root/'oracle-raw.parquet');raw['signal_day']=pd.to_datetime(raw.signal_day)
    physical={}
    for day,g in raw.groupby('signal_day'):
        relevant=top[top.signal_day.eq(day)]
        if relevant.empty:continue
        decision=relevant.decision_at.iloc[0]
        physical[day]=bool((pd.to_datetime(g.prediction_created_at,utc=True).lt(decision)
            &pd.to_datetime(g.lineage_created_at,utc=True).lt(decision)).all())
    top['physical_oracle']=top.signal_day.map(physical).fillna(False)
    from common.daily_bar_sources import select_daily_bars
    prices=select_daily_bars(pd.read_parquet(root/'prices.parquet'),config=yaml.safe_load(Path('config.yaml').read_text(encoding='utf-8')))
    prices['date']=pd.to_datetime(prices.date)
    prices_by_symbol={s:g.set_index('date') for s,g in prices.groupby('symbol')}
    snap=pd.read_parquet(root/'snapshots.parquet');vol=pd.read_parquet(root/'volumes.parquet')
    for f in (snap,vol):f['receipt_day']=pd.to_datetime(f.available_at,utc=True).dt.tz_convert('America/New_York').dt.date
    consensus=pd.read_parquet(root/'consensus.parquet');runs={r['run_id']:r for r in pd.read_parquet(root/'runs.parquet').to_dict('records')}
    consensus,checks=qualify_consensus(consensus,runs)
    pd.DataFrame([dict(id=i,**q) for i,q in checks.items()]).to_parquet(output/'consensus-quality.parquet',index=False)
    con_groups={s:g for s,g in consensus.groupby('symbol')}
    sent=pd.read_parquet(root/'sentiment.parquet');sent['trade_date']=pd.to_datetime(sent.trade_date)
    sent['known_at']=pd.to_datetime(sent[['created_at','updated_at']].max(axis=1),utc=True)
    rows=[];parity=0
    for day,g in top.groupby('signal_day',sort=True):
        decision=g.decision_at.iloc[0];prior=cal.set_index('day').loc[day,'opened']-pd.Timedelta(minutes=5)
        refs=prices[prices.date.eq(day)&prices.is_filled.eq(0)]
        spots={r.symbol:float(r.close) for r in refs.itertuples() if pd.notna(r.close) and r.close>0}
        sn=snap[snap.receipt_day.eq(day.date())];vo=vol[vol.receipt_day.eq(day.date())]
        features=independent_options(sn,vo,spots,day.date(),decision)
        prod=build_features(sn,vo,spots,day.date(),decision)
        for symbol,value in prod.items():
            for field in ('volume_feature','oi_feature'):
                if not np.isclose(features[symbol][field],value[field],rtol=0,atol=1e-12):raise ValueError('Production feature mismatch')
            parity+=1
        ss=sent[sent.trade_date.eq(day)&sent.known_at.lt(decision)]
        if ss.duplicated('symbol').any():raise ValueError('Duplicate sentiment features')
        ss=ss.set_index('symbol').to_dict('index')
        for r in g.to_dict('records'):
            sym=r['symbol'];item=dict(r,**features.get(sym,{}))
            item.update(consensus_for_candidate(con_groups.get(sym,consensus.iloc[:0]),day,decision,prior))
            for n in (1,3):
                row=ss.get(sym,{})
                item['sentiment'+str(n)]=row.get(f'sentiment_net_mean_{n}d',np.nan) if row.get(f'news_count_{n}d',0)>0 else np.nan
            rows.append(item)
    features=pd.DataFrame(rows)
    for name in ('volume_feature','oi_feature'):
        if name not in features:features[name]=np.nan
    features.to_parquet(output/'observable-features.parquet',index=False)
    # Signals are now frozen; only then construct all price outcomes.
    registry=load_security_discontinuities();paths=[]
    for r in top.to_dict('records'):
        offset=sessions.index(r['entry_day'])
        for h in p['horizons']:
            window=cal.iloc[offset:offset+h];path=prices_by_symbol.get(r['symbol'])
            if len(window)<h or not window.closed.lt(cutoff).all():label=dict(status='NOT_MATURE')
            elif path is None:label=dict(status='MISSING_PRICES')
            elif any(e.crosses(window.day.iloc[0],window.day.iloc[-1]) for e in registry.get(r['symbol'],())):
                label=dict(status='KNOWN_IDENTITY_BREAK')
            else:label=labels_for_path(path,window)
            paths.append({**{k:r[k] for k in KEY},'horizon':h,**label})
    labels=pd.DataFrame(paths);labels.to_parquet(output/'labels.parquet',index=False)
    report=dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',cutoff=p['cutoff'],
        universe=len(p['symbols']),oracle_dates=int(top.signal_day.nunique()),
        oracle_signal_dates=sorted(top.signal_day.dt.strftime('%Y-%m-%d').unique()),
        physical_oracle_dates=sorted(top.loc[top.physical_oracle,'signal_day'].dt.strftime('%Y-%m-%d').unique()),
        production_feature_parity_pairs=parity,
        consensus_quality=dict(rows=len(checks),normalization_ok=sum(q['raw_normalization_ok'] for q in checks.values()),
            completed_receipt_ok=sum(q['run_receipt_ok'] for q in checks.values()),
            error_counts=pd.Series([x for q in checks.values() for x in q['errors']],dtype=str).value_counts().to_dict()),
        results={},limitations=['Not an independent holdout; repeated overlapping company paths',
            'Current tradable universe survivorship; missing Oracle dates not inferred',
            'Indicative options OI, unsigned volumes; not certified OPRA or signed buying',
            'Consensus rolling comparison points are provider snapshots, not recreated as-of vintages',
            'EPS basis/currency not identified per record; unitless comparisons research-only',
            'News table is mutable; only rows whose last update predates decision admitted',
            'Canonical current-vintage split-adjusted daily bars, not full intraday chronology',
            'Ambiguous stop-day order excluded from protected-direction metric',
            'AUC and peak direction are not net trading profits; cannot sell at future maximum',
            'Many scores/horizons/cohorts; no best variant promoted, no optimized weights'])
    summary=[]
    for n in p['ranks']:
        f=score_cohort(features[features.oracle_rank.le(n)])
        f['options_selected']=False
        for _,g in f.groupby('signal_day'):
            inputs={r['symbol']:{k:r[k] for k in ('volume_feature','oi_feature')}
                for r in g.to_dict('records') if pd.notna(r['volume_feature']) and pd.notna(r['oi_feature'])}
            decisions=select_top(g.to_dict('records'),inputs,replace(OptionsFilterConfig(**sp['options_config']),oracle_top_n=n))
            lookup={r['symbol']:r for r in decisions}
            for idx,r in g.iterrows():
                decision=lookup[r.symbol];f.loc[idx,'options_selected']=decision['selected']
                production_score=decision.get('combined_score',np.nan)
                if not (pd.isna(production_score) and pd.isna(r.options_score)) and not np.isclose(production_score,r.options_score,rtol=0,atol=1e-12):
                    raise ValueError('Production ranking parity mismatch')
        f.to_csv(output/f'top{n}-scores.csv',index=False)
        panel=f.merge(labels,on=KEY,validate='one_to_many');panel.to_parquet(output/f'top{n}-paths.parquet',index=False)
        report['results'][str(n)]={}
        for h in p['horizons']:
            q=panel[panel.horizon.eq(h)]
            for scope,cohort in [('all',q),('october_onward',q[q.signal_day.ge('2026-10-01')]),
                                  ('physical',q[q.physical_oracle]),('coverage95',q[q.oracle_coverage.ge(.95)])]:
                item={}
                for score in SCORES:
                    metrics=signal_metrics(cohort,score,cal,h);item[score]=metrics
                    summary.append(dict(top_n=n,horizon=h,scope=scope,score=score,**{k:metrics.get(k) for k in
                        ('covered','valid_n','symbols','dates','informative_dates','mean_daily_auc','pooled_auc',
                         'selected_long_share','matched_baseline_long_share','equal_date_selection_lift')}))
                report['results'][str(n)].setdefault(str(h),{})[scope]=item
                common=cohort[cohort[['options_score','revisions30_score']].notna().all(axis=1)]
                report['results'][str(n)][str(h)].setdefault('common_comparison',{})[scope]={score:signal_metrics(common,score,cal,h)
                    for score in ('options_score','revisions30_score','options_consensus_score')}
                chosen=cohort[cohort.options_selected];valid=chosen[chosen.status.eq('LABEL')]
                baseline=cohort[cohort.options_score.notna()&cohort.signal_day.isin(chosen.signal_day)&cohort.status.eq('LABEL')]
                report['results'][str(n)][str(h)].setdefault('production_filter',{})[scope]=dict(
                    selected=len(chosen),valid_n=len(valid),symbols=int(valid.symbol.nunique()),dates=int(valid.signal_day.nunique()),
                    statuses=chosen.status.value_counts().to_dict(),selected_long_n=int(valid.dominant_direction.eq('LONG').sum()),
                    selected_long_share=float(valid.dominant_direction.eq('LONG').mean()) if len(valid) else None,
                    baseline_valid_n=len(baseline),baseline_long_share=float(baseline.dominant_direction.eq('LONG').mean()) if len(baseline) else None)
            # No-stop and terminal targets are distinct sensitivities, not replacements.
            for target,column in [('unprotected','dominant_unprotected'),('terminal','terminal_return_pct')]:
                alt=q[q.status.isin(['LABEL','AMBIGUOUS_PATH'])].copy()
                alt['dominant_direction']=alt[column] if target=='unprotected' else np.where(alt[column]>0,'LONG',np.where(alt[column]<0,'SHORT','TIE'))
                alt['status']=np.where(alt.dominant_direction.eq('TIE'),'AMBIGUOUS_PATH','LABEL')
                report['results'][str(n)][str(h)][target]={score:signal_metrics(alt,score,cal,h) for score in SCORES}
    pd.DataFrame(summary).to_csv(output/'summary.csv',index=False)
    write(output/'report.json',report)
    write(output/'seal.json',dict(files={f.name:digest(f) for f in output.iterdir() if f.is_file()},
        parent_snapshot_seal=digest(root/'snapshot-seal.json'),source_sha256=digest(__file__)))
    print('ANALYSIS_COMPLETE '+str(output),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--snapshot',type=Path,required=True)
    analyze(parser.parse_args().snapshot)
