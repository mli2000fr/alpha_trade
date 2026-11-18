"""Frozen B / LONG path10 / first-session SL meta-filter, research only.

No application configuration, SQL writes, provider/LLM calls or broker orders.
All decision inputs end at signal J; the entry remains the next daily open.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from scripts.research import us_q051_feature_groups_20261116 as base
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_q051_b_early_sl/20261116-v1')
REFERENCE=base.ROOT
FULL=Path('artifacts/research/us_q051_sl_pause/20261116-30sessions-pause100-v1')
CASES=['CONTROL','LONG10','SLJ','SL10']
PATH_SOURCES=['return_5d','rsi_14','vol_ratio_20_60','range_position_20','rolling_volatility_20_zscore']
PATH_COLUMNS=[c+'_path10_'+stat for c in PATH_SOURCES for stat in ['delta','slope','std']]


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def columns(path=False):
    from modelFactory.oracle_path.directional_features import compact_columns
    return compact_columns('compact_volatility')+(PATH_COLUMNS if path else [])


def path_panel(frame,calendar):
    """Exactly ten consecutive exchange sessions, never ten non-missing rows."""
    f=frame.set_index('date').reindex(calendar);x=np.arange(10,dtype=float)-4.5
    for c in PATH_SOURCES:
        s=pd.to_numeric(f[c],errors='coerce');valid=s.notna().rolling(10).sum().eq(10)
        f[c+'_path10_delta']=(s-s.shift(9)).where(valid)
        f[c+'_path10_slope']=s.rolling(10).apply(lambda a:float(a@x/(x@x)),raw=True).where(valid)
        f[c+'_path10_std']=s.rolling(10).std().where(valid)
    return f.loc[pd.DatetimeIndex(frame.date)].rename_axis('date').reset_index()


def early_labels(bars,calendar,breaks=()):
    """J+1 entry, rounded Winner SL5; availability conservatively at J+2."""
    from common.daily_bar_sources import select_daily_bars
    a=select_daily_bars(bars.copy()).set_index('date').reindex(calendar)
    p=a[['open','high','low','close','volume','is_filled']].apply(pd.to_numeric,errors='coerce')
    good=np.isfinite(p).all(axis=1)&p[['open','high','low','close','volume']].gt(0).all(axis=1)&p.is_filled.eq(0)
    good &= p.high.ge(p[['open','close','low']].max(axis=1))&p.low.le(p[['open','close','high']].min(axis=1))
    valid=(good&good.shift(-1,fill_value=False)).to_numpy()[:-2]
    for c in ['instrument_id','data_source','data_adjustment']:
        s=a[c];valid &= (s.notna()&s.eq(s.shift(-1))).to_numpy()[:-2]
        if c!='instrument_id':valid &= ~s.astype(str).str.upper().isin(['UNKNOWN','']).to_numpy()[:-2]
    days=pd.DatetimeIndex(calendar);entry=p.open.shift(-1).to_numpy()[:-2]
    # Same cent rounding as common.winner_pyramiding's booked initial stop.
    stop=np.array([round(float(v)*.95,2) if np.isfinite(v) else np.nan for v in entry])
    low=p.low.shift(-1).to_numpy()[:-2]
    for e in breaks:valid &= ~((days[:-2]<=e.last_predecessor_date)&(days[1:-1]>=e.first_successor_date))
    return pd.DataFrame(dict(date=days[:-2],event_available=days[2:],entry_day=days[1:-1],
        entry_open=entry,entry_low=low,first_session_sl=np.where(valid,(low<=stop).astype(float),np.nan)))


def temporal_split(frame,year,target,available):
    a,b=pd.Timestamp(year-1,1,1),pd.Timestamp(year,1,1)
    f=frame[frame[target].notna()].copy()
    return (f[f.date.lt(a)&f[available].lt(a)],f[f.date.ge(a)&f.date.lt(b)&f[available].lt(b)])


def fit_model(fit,cal,cols,target,seed=42):
    from lightgbm import LGBMClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from sklearn.linear_model import LogisticRegression
    from modelFactory.oracle_path.named_prediction import predict_proba
    from modelFactory.oracle_path.directional_metrics import predict,classification_metrics
    lo,hi=fit[cols].quantile(.01),fit[cols].quantile(.99)
    x=fit[cols].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
    z=cal[cols].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
    model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True).set_output(transform='pandas'),
        LGBMClassifier(n_estimators=120,max_depth=3,num_leaves=7,learning_rate=.03,min_child_samples=60,
            reg_alpha=1.,reg_lambda=10.,verbosity=-1,n_jobs=1,random_state=seed))
    model.fit(x,fit[target].astype(int))
    p=np.clip(predict_proba(model,z,cols)[:,1],1e-6,1-1e-6)
    if np.std(p)<=1e-6:return None,dict(reason='CONSTANT_CALIBRATION')
    calibrator=LogisticRegression(C=1.,random_state=seed).fit(np.log(p/(1-p)).reshape(-1,1),cal[target].astype(int))
    weights=dict(model=model,calibrator=calibrator,lo=lo,hi=hi,features=cols)
    return weights,classification_metrics(cal[target],predict(weights,cal))


def meta_filter(selected,probabilities,head):
    """A fixed past-calibrated cutoff, after TOP10, never promote rank11."""
    risk=probabilities[['date','symbol',head+'_risk',head+'_threshold',head+'_available']]
    a=selected.merge(risk,on=['date','symbol'],how='left',validate='one_to_one')
    known=a[head+'_risk'].notna()&a[head+'_threshold'].notna()
    if (known&pd.to_datetime(a[head+'_available']).ge(a.date)).any():raise ValueError('Future SL model')
    a['sl_model_known']=known
    a['excluded_by_sl']=known&a[head+'_risk'].gt(a[head+'_threshold'])
    a['selected']=~a.excluded_by_sl
    return a


def prepare():
    if (ROOT/'protocol.json').exists():
        p=read(ROOT/'protocol.json')
        if p['sources'][str(Path(__file__))]!=digest(Path(__file__)):raise ValueError('Sealed launcher changed')
        return p
    ROOT.mkdir(parents=True,exist_ok=True)
    old=read(REFERENCE/'protocol.json');full=read(FULL/'protocol.json');original=read(base.ORIGINAL/'protocol.json')
    sources={};fold_audit=[]
    for y in range(2021,2027):
        root=Path(original['models'][str(y)]['root'])
        f=pd.read_parquet(root/'oof_predictions.parquet')
        sources[str(root/'oof_predictions.parquet')]=digest(root/'oof_predictions.parquet')
        keep=[]
        for fold,g in f.groupby('fold_start'):
            folder=root/'folds'/str(fold);done=read(folder/'done.json');m=done['metrics']
            for file,h in done['files'].items():
                if digest(folder/file)!=h:raise ValueError('Changed Oracle fold')
            if not (pd.Timestamp(m['train_available_max'])<pd.Timestamp(m['test_start'])
                    and pd.Timestamp(m['val_available_max'])<pd.Timestamp(m['test_start'])
                    and g.date.between(m['test_start'],m['test_end']).all()):raise ValueError('Noncausal Oracle OOF fold')
            sources[str(folder/'done.json')]=digest(folder/'done.json')
            keep.append(g[['date','symbol','proba_path_extreme']].rename(columns={'proba_path_extreme':'proba_extreme'}))
            fold_audit.append(dict(entry_year=y,fold=str(fold),first=str(g.date.min().date()),last=str(g.date.max().date()),
                train_available_max=m['train_available_max'],val_available_max=m['val_available_max']))
        oof=pd.concat(keep,ignore_index=True)
        if oof.duplicated(['date','symbol']).any():raise ValueError('Duplicate OOF date/symbol')
        counts=oof.groupby('date').size();valid=set(counts[counts.ge(179)].index)
        pool=oof[oof.date.isin(valid)].sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True]).groupby('date').head(179)
        folder=ROOT/'years'/str(y);folder.mkdir(parents=True,exist_ok=True)
        pool.to_parquet(folder/'oof-pool.parquet',index=False);sources[str(folder/'oof-pool.parquet')]=digest(folder/'oof-pool.parquet')
        for file in [REFERENCE/'years'/str(y)/'oracle.parquet',REFERENCE/'years'/str(y)/'pool.parquet']:
            sources[str(file)]=digest(file)
    # Reuse historical data, not historical code hashes after the authorized B UI change.
    tasks=deepcopy(full['tasks'])
    for task in tasks:
        # Historical meta-training must not depend on which symbols later
        # appeared in the test-year Oracle pool. Read the complete raw chunk.
        task['symbols']=sorted(set(pd.read_parquet(task['source'],columns=['symbol']).symbol)&set(original['universe']))
        for file in [task['source'],*task['future']]:
            h=full['sources'][file]
            if digest(Path(file))!=h:raise ValueError('Changed frozen raw data')
            sources[file]=h
        oldjob=REFERENCE/'jobs'/task['key']
        if (oldjob/'models.json').exists():
            done=read(oldjob/'done.json')
            for name in ['models.json','B-probabilities.parquet']:
                if digest(oldjob/name)!=done['outputs'][name]:raise ValueError('Changed reference B cache')
                sources[str(oldjob/name)]=done['outputs'][name]
    for item in old['models'].values():sources[item['benchmark']]=digest(Path(item['benchmark']))
    for item in original['models'].values():
        p=Path(item['benchmark']);sources[str(p)]=digest(p)
    from scripts.research.us_q051_global_rank_h10_20261115 import FEATURE_2026
    sources[str(FEATURE_2026/'directional/benchmark.parquet')]=digest(FEATURE_2026/'directional/benchmark.parquet')
    for file in [REFERENCE/'variants/B/signals.parquet',REFERENCE/'variants/B/cases/B_SIMPLE/protocol.json',
        REFERENCE/'variants/B/cases/B_SIMPLE/result/equity-daily.csv',Path('tests/test_q051_b_early_sl.py')]:sources[str(file)]=digest(file)
    for parent in ['backtesting','risk_management','modelFactory/oracle_path']:
        sources.update({str(p):digest(p) for p in Path(parent).glob('*.py')})
    for file in [Path(__file__),Path(base.__file__),Path('modelFactory/features.py'),Path('modelFactory/factor_features.py'),
        Path('scripts/research/us_q051_feature_groups_cd_20261116.py')]:sources[str(file)]=digest(file)
    plan=dict(start=old['start'],end=old['end'],initial_equity=4000.,universe=original['universe'],models=old['models'],
        tasks=tasks,sources=sources,cases=CASES,reference_root=str(REFERENCE),reference='B_SIMPLE',
        reference_settings=read(REFERENCE/'variants/B/cases/B_SIMPLE/protocol.json')['reference'],
        selection='Fixed TOP179 Oracle -> TOP10 LONG, score>.50/AUCcal>=.50 -> optional early-SL veto, no refill',
        features=dict(B=columns(),PATH10=columns(True)),trajectory_sources=PATH_SOURCES,
        trajectory='J-9..J: delta9, OLS slope10, std10; missing sessions stay missing, past-only imputed',
        learning=dict(LONG10='Annual per-symbol fits on frozen qualified B model cohort and exact B fit/calibration rows',
            SLJ='P(first entry session hits rounded SL5), shared model on historical causal Oracle OOF TOP179',
            SL10='Same event and exact fit/calibration rows, 44 inputs instead29',
            availability='First-session SL label only known on next exchange session J+2; LONG label maturity unchanged',
            split='Fit before year-1, calibration year-1, both labels available strictly before their boundaries',
            threshold='Strictly above 90th percentile of calibrated risks in previous-year calibration; fixed quantile, no threshold sweep',
            unknown='Keep B unchanged if SL model or score is unqualified; never call an unknown event a non-SL',
            missing_path='Keep B historical training rows; impute past-only absent trajectory columns'),
        portfolio='Same B_SIMPLE: full position, daily J+1, SL5/open11, cap1x, no vol20/regime/B4/trailing/TP/pause100',
        provider_calls=0,LLM_calls=0,orders=0,SQL_writes=0,production_changes=False,new_holdout=False,
        strict_pit=False,created_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'protocol.json',plan);atomic_json(ROOT/'oracle-oof-causality.json',dict(status='PASS',folds=fold_audit))
    atomic_json(ROOT/'progress.json',dict(status='READY',training_jobs=len(plan['tasks']),cases=CASES))
    return plan


def worker(key):
    import joblib
    from modelFactory.oracle.build_labels import nyse_sessions
    from modelFactory.oracle_path import directional as d
    from modelFactory.oracle_path.directional_metrics import predict
    from modelFactory.oracle.security_continuity import load_security_discontinuities
    from common.config_loader import replay_market_registry
    from scripts.research.us_q051_global_rank_h10_20261115 import FEATURE_2026
    plan=read(ROOT/'protocol.json');task=next(t for t in plan['tasks'] if t['key']==key)
    folder=ROOT/'jobs'/key;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'done.json').exists():
        for f,h in read(folder/'done.json')['outputs'].items():
            if digest(folder/f)!=h:raise ValueError('Changed completed output')
        return
    try:
        for f,h in plan['sources'].items():
            if f.endswith('.py') and digest(Path(f))!=h:raise ValueError('Changed sealed source '+f)
        year=task['year'];item=plan['models'][str(year)];end=pd.Timestamp(min(plan['end'],f'{year}-12-31'))
        pieces=[pd.read_parquet(task['source'])]
        for file in task['future']:
            f=pd.read_parquet(file);pieces.append(f[f.date.gt(item['training_end'])&f.date.le(end)])
        bars=base.repair_bars(pd.concat(pieces,ignore_index=True));bars=bars[bars.symbol.isin(task['symbols'])&bars.date.le(end)]
        bench=pd.read_parquet(item['benchmark']);original=read(base.ORIGINAL/'protocol.json')
        newer=pd.read_parquet(Path(original['models'][str(year+1)]['benchmark']) if year<2026 else FEATURE_2026/'directional/benchmark.parquet')
        bench=pd.concat([bench,newer[newer.date.gt(bench.date.max())]],ignore_index=True)
        pool=pd.read_parquet(REFERENCE/'years'/str(year)/'pool.parquet');oof=pd.read_parquet(ROOT/'years'/str(year)/'oof-pool.parquet')
        old=REFERENCE/'jobs'/key
        meta=read(old/'models.json') if (old/'models.json').exists() else {'models':[]}
        records={(r['symbol'],r['model_year']):r for r in meta['models'] if r['variant']=='B'}
        prior=pd.read_parquet(old/'B-probabilities.parquet') if (old/'B-probabilities.parquet').exists() else pd.DataFrame()
        training=[];testing=[];predictions=[];fitted=[];audit=[];skipped=[]
        with replay_market_registry(base.shared.restore_registry(base.shared.ROOT)),patch.object(requests.Session,'request',base.no_http):
            calendar=nyse_sessions(pd.Timestamp(item['training_start']).date(),end.date());registry=load_security_discontinuities()
            for n,(symbol,g) in enumerate(bars.groupby('symbol')):
                atomic_json(folder/'progress.json',dict(status='PREPARING_AND_TRAINING',symbol=symbol,completed=n,total=len(task['symbols'])))
                f=base.common_panel(g,bench,calendar);f=path_panel(f,calendar)
                targets=early_labels(g,calendar,registry.get(symbol,()))
                panel=f.merge(targets,on='date',how='left',validate='one_to_one')
                train=oof[oof.symbol.eq(symbol)][['date','symbol']].merge(panel,on=['date','symbol'],validate='one_to_one')
                training.append(train[['date','symbol',*columns(True),'first_session_sl','event_available']])
                wanted=pool[pool.symbol.eq(symbol)][['date','symbol']].merge(panel,on=['date','symbol'],validate='one_to_one')
                longlabels=d.labels(g,calendar,d.Settings(horizon_sessions=10),registry.get(symbol,()))
                longpanel=f.merge(longlabels,on='date',how='left',validate='one_to_one')
                test=wanted.merge(longlabels[['date','long','available']].rename(columns={'long':'net_long','available':'long_available'}),
                    on='date',how='left',validate='one_to_one')
                testing.append(test[['date','symbol',*columns(True),'first_session_sl','event_available',
                    'entry_day','entry_open','entry_low','net_long','long_available']])
                for model_year,a in wanted.groupby(wanted.date.dt.year):
                    r=records.get((symbol,int(model_year)))
                    if r is None:continue
                    if digest(Path(r['file']))!=r['sha256']:raise ValueError('Changed B weights')
                    oldp=prior[prior.symbol.eq(symbol)&prior.date.dt.year.eq(model_year)]
                    matches=oldp.merge(f,on=['date','symbol'],validate='one_to_one')
                    if len(matches)!=len(oldp) or not np.allclose(predict(joblib.load(r['file']),matches),matches.long_probability,rtol=0,atol=1e-12):
                        raise ValueError('B reference prediction mismatch')
                    fit,cal=d.split(longpanel,int(model_year),'long')
                    for field,value in dict(fit_rows=len(fit),calibration_rows=len(cal),fit_start=str(fit.date.min().date()),
                        fit_end=str(fit.date.max().date()),calibration_start=str(cal.date.min().date()),
                        calibration_end=str(cal.date.max().date()),available=str(cal.available.max().date())).items():
                        if r[field]!=value:raise ValueError('B fit/calibration membership changed: '+field)
                    weights,metric=fit_model(fit,cal,columns(True),'long',item['seed'])
                    audit.append(dict(symbol=symbol,model_year=int(model_year),reference_predictions=len(matches),same_fit_calibration_rows=True))
                    if weights is None:skipped.append(dict(symbol=symbol,year=int(model_year),**metric));continue
                    file=folder/'models'/(hashlib.sha256(symbol.encode()).hexdigest()[:16]+f'-long-{model_year}.joblib')
                    file.parent.mkdir(exist_ok=True);joblib.dump(weights,file,compress=3);h=digest(file)
                    fitted.append(dict(symbol=symbol,model_year=int(model_year),file=str(file),sha256=h,features=columns(True),
                        fit_rows=len(fit),calibration_rows=len(cal),available=r['available'],calibration=metric))
                    a=a[['date','symbol',*columns(True)]].copy();p=a[['date','symbol']].copy()
                    p['long_probability']=predict(weights,a);p['long_model_sha256']=h;p['long_auc']=metric['auc']
                    p['long_auc_available_date']=r['available'];p['long_auc_model_sha256']=h;p['long_auc_source']='calibration'
                    predictions.append(p)
        outputs={}
        empty_prob=pd.DataFrame(columns=['date','symbol','long_probability','long_model_sha256','long_auc','long_auc_available_date','long_auc_model_sha256','long_auc_source'])
        for name,data in [('training.parquet',pd.concat(training,ignore_index=True)),('testing.parquet',pd.concat(testing,ignore_index=True)),
                          ('LONG10-probabilities.parquet',pd.concat(predictions,ignore_index=True) if predictions else empty_prob)]:
            data.to_parquet(folder/name,index=False);outputs[name]=digest(folder/name)
        atomic_json(folder/'models.json',dict(models=fitted,skipped=skipped,reference_checks=audit));outputs['models.json']=digest(folder/'models.json')
        atomic_json(folder/'done.json',dict(status='COMPLETED',outputs=outputs,models=len(fitted),reference_predictions=sum(a['reference_predictions'] for a in audit)))
        atomic_json(folder/'progress.json',dict(status='COMPLETED',models=len(fitted)))
    except BaseException as exc:
        atomic_json(folder/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


def train_heads(year):
    import joblib
    from modelFactory.oracle_path.directional_metrics import predict,classification_metrics
    plan=read(ROOT/'protocol.json');folder=ROOT/'heads'/str(year);folder.mkdir(parents=True,exist_ok=True)
    if (folder/'done.json').exists():return
    train=[];test=[]
    for task in (t for t in plan['tasks'] if t['year']==year):
        job=ROOT/'jobs'/task['key'];done=read(job/'done.json')
        for name in ['training.parquet','testing.parquet']:
            if digest(job/name)!=done['outputs'][name]:raise ValueError('Corrupt prepared panel')
        train.append(pd.read_parquet(job/'training.parquet'));test.append(pd.read_parquet(job/'testing.parquet'))
    train=pd.concat(train,ignore_index=True);test=pd.concat(test,ignore_index=True)
    if train.duplicated(['date','symbol']).any() or test.duplicated(['date','symbol']).any():raise ValueError('Duplicate pooled panel')
    model_records=[];pred=[];metrics=[]
    for model_year,g in test.groupby(test.date.dt.year):
        fit,cal=temporal_split(train,int(model_year),'first_session_sl','event_available')
        qualified=(len(fit)>=2000 and len(cal)>=500 and fit.first_session_sl.value_counts().reindex([0.,1.],fill_value=0).min()>=30
            and cal.first_session_sl.value_counts().reindex([0.,1.],fill_value=0).min()>=10)
        frame=g[['date','symbol','first_session_sl','event_available','entry_day','entry_open','entry_low','net_long','long_available']].copy()
        for variant,use_path in [('SLJ',False),('SL10',True)]:
            w,m=fit_model(fit,cal,columns(use_path),'first_session_sl',plan['models'][str(year)]['seed']) if qualified else (None,dict(reason='INSUFFICIENT_PAST_OOF_HISTORY'))
            if w is None:
                frame[variant+'_risk']=np.nan;frame[variant+'_threshold']=np.nan;frame[variant+'_available']=pd.NaT
                model_records.append(dict(variant=variant,model_year=int(model_year),**m));continue
            file=folder/(f'{variant}-{model_year}.joblib');joblib.dump(w,file,compress=3)
            threshold=float(np.quantile(predict(w,cal),.90))
            available=str(cal.event_available.max().date())
            if not g.date.gt(pd.Timestamp(available)).all():raise ValueError('Future event model calibration')
            frame[variant+'_risk']=predict(w,g);frame[variant+'_threshold']=threshold;frame[variant+'_available']=available
            model_records.append(dict(variant=variant,model_year=int(model_year),file=str(file),sha256=digest(file),
                fit_rows=len(fit),calibration_rows=len(cal),fit_available_max=str(fit.event_available.max()),available=available,
                threshold=threshold,calibration=m,features=columns(use_path)))
            # Outcomes are diagnostic only, after all weights and thresholds are frozen.
            known=g.first_session_sl.notna()&g.event_available.le(pd.Timestamp(plan['end']))
            metrics.append(dict(variant=variant,entry_year=year,model_year=int(model_year),
                scope='Original Oracle TOP179 candidates with mature first-session labels',
                **classification_metrics(g.loc[known,'first_session_sl'],frame.loc[known,variant+'_risk'])))
        pred.append(frame)
    result=pd.concat(pred,ignore_index=True);result.to_parquet(folder/'probabilities.parquet',index=False)
    atomic_json(folder/'models.json',dict(models=model_records,diagnostics=metrics))
    atomic_json(folder/'done.json',dict(status='COMPLETED',probabilities_sha256=digest(folder/'probabilities.parquet')))


def assemble():
    from backtesting.per_symbol_selection import select_per_symbol,PerSymbolSelection
    plan=read(ROOT/'protocol.json');settings=PerSymbolSelection(oracle_top_n=179,long_top_n=10,allow_short=False,min_long_probability=.5,min_long_auc=.5)
    allsignals={k:[] for k in CASES};decisions=[];labels=[]
    expected=pd.read_parquet(REFERENCE/'variants/B/signals.parquet')
    for year in range(2021,2027):
        folder=ROOT/'heads'/str(year)
        if digest(folder/'probabilities.parquet')!=read(folder/'done.json')['probabilities_sha256']:raise ValueError('Changed pooled prediction file')
        risks=pd.read_parquet(folder/'probabilities.parquet');labels.append(risks)
        longparts=[]
        for task in (t for t in plan['tasks'] if t['year']==year):
            job=ROOT/'jobs'/task['key'];done=read(job/'done.json')
            if digest(job/'LONG10-probabilities.parquet')!=done['outputs']['LONG10-probabilities.parquet']:raise ValueError('Changed LONG10 scores')
            longparts.append(pd.read_parquet(job/'LONG10-probabilities.parquet'))
        oracle=pd.read_parquet(REFERENCE/'years'/str(year)/'oracle.parquet')
        b=expected[expected.entry_year.eq(year)].rename(columns={'trade_date':'date'}).copy()
        allsignals['CONTROL'].append(b)
        a=oracle.merge(pd.concat(longparts,ignore_index=True),on=['date','symbol'],how='left',validate='one_to_one');a['short_probability']=np.nan
        selected=select_per_symbol(a,settings);allsignals['LONG10'].append(selected[selected.selected].copy())
        for case in ['SLJ','SL10']:
            checked=meta_filter(b,risks,case);checked['case']=case;checked['entry_year']=year;decisions.append(checked)
            allsignals[case].append(checked[checked.selected].copy())
    for case,parts in allsignals.items():
        f=pd.concat(parts,ignore_index=True).rename(columns={'date':'trade_date'})
        f['rank']=f['rank'].astype(int);f['side']='long';f['selected']=True
        target=ROOT/'variants'/case;target.mkdir(parents=True,exist_ok=True)
        f.sort_values(['trade_date','rank','symbol']).to_parquet(target/'signals.parquet',index=False)
    pd.concat(decisions,ignore_index=True).to_parquet(ROOT/'filter-decisions.parquet',index=False)
    pd.concat(labels,ignore_index=True).to_parquet(ROOT/'test-labels-and-risks.parquet',index=False)
    atomic_json(ROOT/'selection-validation.json',dict(status='PASS',reference_signals_reused=True,
        counts={k:len(pd.read_parquet(ROOT/'variants'/k/'signals.parquet')) for k in CASES},no_refill=True))


def prepare_market():
    from sqlalchemy import text
    from database.connection import get_sqlalchemy_engine
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.winner_campaign_replay import SqlIntradaySource
    from common.config_loader import replay_market_registry
    from scripts.research.us_q051_feature_groups_cd_20261116 import ReferencePrices,missing_pairs,EXT
    inputs=ROOT/'inputs';inputs.mkdir(exist_ok=True);tape=inputs/'intraday';tape.mkdir(exist_ok=True)
    if (inputs/'manifest.json').exists():return
    close=pd.read_parquet(FULL/'inputs/close.parquet');sessions=[d.date() for d in close.index if '2021-01-01'<=str(d.date())<='2026-10-01']
    signals=[pd.read_parquet(ROOT/'variants'/k/'signals.parquet') for k in CASES]
    windows=base.shared.supplemental_windows(signals,sessions,set(),horizon=10);old=ReferencePrices(EXT)
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    with ReadOnlyReplay(ROOT).install(),replay_market_registry(base.shared.restore_registry(base.shared.ROOT)),engine.connect() as conn,conn.begin():
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        source=SqlIntradaySource(conn,discard_unqualified=True,allow_daily_fallback=True)
        for i,day in enumerate(sessions):
            receipt=tape/(str(day)+'.json')
            if not receipt.exists():
                missing=missing_pairs(day,windows[day],old.day(day));f=source(day,missing)
                f.to_parquet(tape/(str(day)+'.parquet'),index=False)
                atomic_json(receipt,dict(requested=missing,rows=len(f),provider_calls=0,SQL_writes=0))
            atomic_json(ROOT/'progress.json',dict(status='FREEZING_COMMON_5M_READ_ONLY',completed=i+1,total=len(sessions),last_date=str(day)))
    files={str(p):digest(p) for p in tape.glob('*')}
    for name in ['open','high','low','close','volume','sectors','actions']:
        p=FULL/'inputs'/(name+'.parquet');files[str(p)]=digest(p)
    atomic_json(inputs/'manifest.json',dict(files=files,common_daily=str(FULL/'inputs'),provider_calls=0,SQL_writes=0))


def run_case(case):
    from functools import lru_cache
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from scripts.research.us_q051_feature_groups_cd_20261116 import ReferencePrices,EXT
    folder=ROOT/'cases'/case;folder.mkdir(parents=True,exist_ok=False);out=folder/'result';out.mkdir()
    plan=read(ROOT/'protocol.json')
    for file,h in {**plan['sources'],**read(ROOT/'inputs/manifest.json')['files']}.items():
        if digest(Path(file))!=h:raise ValueError('Changed sealed replay source '+file)
    cfg=base.shared.configuration(plan['reference_settings'],base.shared.CASES['Q051_050'])
    pivots={c:pd.read_parquet(FULL/'inputs'/(c+'.parquet')) for c in ['open','high','low','close','volume']}
    sectors=pd.read_parquet(FULL/'inputs/sectors.parquet');actions=pd.read_parquet(FULL/'inputs/actions.parquet')
    signals=pd.read_parquet(ROOT/'variants'/case/'signals.parquet')
    class Tape(ReferencePrices):
        @lru_cache(maxsize=6)
        def day(self,day):
            groups=dict(super().day(day));extra=pd.read_parquet(ROOT/'inputs/intraday'/(str(day)+'.parquet'))
            for s,g in extra.groupby('symbol') if not extra.empty else []:
                if s in groups:raise ValueError('Common supplement overwrites frozen tape')
                groups[s]=g
            return groups
    atomic_json(folder/'protocol.json',{**plan,'case':case,'signals_sha256':digest(ROOT/'variants'/case/'signals.parquet')})
    atomic_json(out/'configuration.json',dict(profile='B_EARLY_SL_'+case,portfolio=asdict(cfg)))
    try:
        with ReadOnlyReplay(folder).install(),replay_market_registry(base.shared.restore_registry(base.shared.ROOT)),patch.object(requests.Session,'request',base.no_http):
            def tick(done,total,day):atomic_json(folder/'progress.json',dict(status='REPLAYING',completed=done,total=total,last_date=str(day)))
            result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
                volume=pivots['volume'],signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),
                intraday_source=Tape(EXT),winner_research_assumptions=True,winner_progress=tick,winner_corporate_actions=actions.to_dict('records'))
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False);report=metrics(result,4000.);annual=[];opening=4000.
            for y in range(2021,2027):
                curve=result.equity_curve[result.equity_curve.index.year==y];t=result.closed_trades_df;m=result.intraday_equity_curve
                part=BacktestResult(equity_curve=curve,closed_trades_df=t[pd.to_datetime(t.exit_date,utc=True).dt.year.eq(y)],
                    intraday_equity_curve=m[pd.to_datetime(m.timestamp,utc=True).dt.year.eq(y)],
                    tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
                annual.append(dict(year=y,**metrics(part,opening)));opening=float(curve.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
            report.update(case=case,provider_calls=0,orders=0,SQL_writes=0,production_changes=False,model_timing_oos=True,
                strict_pit=False,new_holdout=False,selected_signals=len(signals))
            trades=result.closed_trades_df
            stops=trades.exit_reason.isin(['STOP','STOP_GAP'])
            same_day=pd.to_datetime(trades.entry_date,utc=True).dt.tz_convert('America/New_York').dt.date.eq(
                pd.to_datetime(trades.exit_date,utc=True).dt.tz_convert('America/New_York').dt.date)
            report.update(stop_exits=int(stops.sum()),first_session_stop_exits=int((stops&same_day).sum()),
                first_session_stop_pct=100*float((stops&same_day).mean()))
            atomic_json(out/'report.json',report)
        from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
        validate_case(folder)
        if case=='CONTROL':
            a=pd.read_csv(out/'equity-daily.csv');b=pd.read_csv(REFERENCE/'variants/B/cases/B_SIMPLE/result/equity-daily.csv')
            if not a.iloc[:,0].equals(b.iloc[:,0]) or not np.allclose(a.equity,b.equity,rtol=0,atol=1e-8):raise ValueError('B control capital curve changed')
        atomic_json(folder/'validation.json',dict(status='PASS',arithmetic=True,control_equivalence=case=='CONTROL'))
        atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
    except BaseException as exc:
        atomic_json(folder/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


def finish():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[];curves=[]
    for case in CASES:
        if read(ROOT/'cases'/case/'validation.json')['status']!='PASS':raise ValueError('Unvalidated case')
        out=ROOT/'cases'/case/'result';r=read(out/'report.json')
        rows.append(dict(case=case,**{k:r.get(k) for k in ['final_equity','return_pct','max_drawdown_pct','win_pct',
            'closed_lot_trades','average_gross_capital','average_gross_equity_ratio','average_winning_pnl','average_losing_pnl',
            'stop_exits','first_session_stop_exits','first_session_stop_pct']}))
        curves.append(pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity.rename(case))
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False);f=pd.concat(curves,axis=1);f.to_csv(ROOT/'capital-curves.csv')
    ax=f.plot(figsize=(13,7),title='B / LONG trajectoire10 / filtres SL première séance J et trajectoire10')
    ax.set_ylabel('Capital ($)');ax.grid(alpha=.2);ax.figure.tight_layout();ax.figure.savefig(ROOT/'capital-comparison.png',dpi=140);plt.close(ax.figure)
    decisions=pd.read_parquet(ROOT/'filter-decisions.parquet');labels=pd.read_parquet(ROOT/'test-labels-and-risks.parquet')
    audit=decisions.merge(labels[['date','symbol','first_session_sl','net_long','long_available']],on=['date','symbol'],how='left',validate='many_to_one')
    summary=[]
    for (case,excluded),g in audit.groupby(['case','excluded_by_sl']):
        known=g.first_session_sl.notna();mature=g.net_long.notna()&g.long_available.le(pd.Timestamp(read(ROOT/'protocol.json')['end']))
        summary.append(dict(case=case,excluded=bool(excluded),signals=len(g),
            known_event_labels=int(known.sum()),first_session_sl_pct=100*g.loc[known,'first_session_sl'].mean(),
            known_net_long_labels=int(mature.sum()),profitable_long_labels=int(g.loc[mature,'net_long'].sum()),
            profitable_long_pct=100*g.loc[mature,'net_long'].mean(),risk_score_coverage_pct=100*g.sl_model_known.mean()))
    pd.DataFrame(summary).to_csv(ROOT/'filter-diagnostics.csv',index=False)
    review=post_review(labels)
    text=['# B — trajectoire dix séances et détection de SL première séance','',
        '2021–1er octobre2026,4000$ continus, TOP10% Oracle → TOP10 LONG, score>0,50/AUC calibration≥0,50, '
        'entrée J+1, SL5/open11, plafond achats1×, frais et financement inclus. Sans vol20/régime/B4/pause100.',
        'Les périodes sont rétrospectives et déjà explorées. Aucun modèle, ordre ou réglage de production modifié.','',
        '| Cas | Capital final | Rendement | DD max | Gagnants | Trades | SL première séance |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:text.append(f"| {r['case']} | {r['final_equity']:.2f}$ | {r['return_pct']:+.2f}% | {r['max_drawdown_pct']:.2f}% | {r['win_pct']:.2f}% | {r['closed_lot_trades']} | {r['first_session_stop_exits']} |")
    text+=['',f"Revue : {review['status']}. Réserves de prix : {len(review['price_reserves'])}. "
        f"Écarts de labels première séance : {review['event_label_mismatches']}/{review['known_event_labels']}.",
        'Les labels gagnants écartés sont des occasions théoriques sans contraintes de capital, pas des trades exécutés. '
        'La différence économique vient du replay complet avec réallocation du capital. Intraday partiel/repli OHLC, '
        'univers contemporain et prix révisés ; pas de certification PIT ou parité live.',
        'Archives : `'+str(ROOT)+'`. Voir `comparison.csv`, `filter-diagnostics.csv`, `post-run-review.json`, `capital-comparison.png`.']
    message='\n'.join(text)+'\n';(ROOT/'results.md').write_text(message,encoding='utf-8')
    marker='<!-- Q051_B_EARLY_SL_RESULTS_20261116 -->'
    for path in [Path('doc/ml/q051_b_early_sl_20261116.md'),Path('doc/ml/experiences_done.md')]:
        if marker not in path.read_text(encoding='utf-8'):
            with path.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+message)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',cases=rows,review=review['status'],production_changes=False))


def post_review(labels):
    from scripts.research.us_q051_features173_finalize_20261116 import observed_windows
    from scripts.research.us_h10_price_readiness import FLAGGED
    from scripts.research.us_q051_feature_groups_cd_20261116 import PRICE_EVIDENCE,provider_frame
    from modelFactory.oracle.build_labels import nyse_sessions
    plan=read(ROOT/'protocol.json');calendar=[d.date() for d in nyse_sessions(pd.Timestamp('2020-01-01').date(),pd.Timestamp('2027-01-01').date())]
    previous={calendar[i]:calendar[i-1] for i in range(1,len(calendar))}
    evidence={p.stem:provider_frame(p) for p in (PRICE_EVIDENCE/'evidence').glob('*.json')}
    reserves=[];known_total=0;mismatches=0;checks=[]
    for file,h in plan['sources'].items():
        if digest(Path(file))!=h:raise ValueError('Changed source at final review '+file)
    for case in CASES:
        out=ROOT/'cases'/case/'result';t=pd.read_csv(out/'trades.csv');events=pd.read_csv(out/'events.csv')
        equity=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
        windows=observed_windows(t,events,equity.index[-1].tz_localize('America/New_York')+pd.Timedelta(hours=16))
        start=pd.to_datetime(windows.entry_date,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
        end=pd.to_datetime(windows.exit_date,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
        for i in windows.index[windows.symbol.eq('DD')&start.lt('2025-11-03')&end.ge('2025-11-03')]:reserves.append(dict(case=case,symbol='DD',reason='UNQUALIFIED_QNITY_ENTITLEMENT'))
        for i in windows.index[windows.symbol.eq('TOELY')&end.ge('2026-07-13')]:reserves.append(dict(case=case,symbol='TOELY',reason='UNSUPPORTED_ADR_BASIS',entry=str(start[i].date()),exit=str(end[i].date())))
        for symbol,g in windows.groupby('symbol'):
            if symbol not in FLAGGED:continue
            if symbol not in evidence or evidence[symbol].empty:
                reserves.append(dict(case=case,symbol=symbol,reason='FLAGGED_WITHOUT_SIP_EVIDENCE'));continue
            known=set(evidence[symbol].date)
            for i in g.index:
                missing=[str(d.date()) for d in equity.index[(equity.index>=start[i])&(equity.index<=end[i])] if d not in known]
                if missing:reserves.append(dict(case=case,symbol=symbol,reason='SIP_HOLDING_WINDOW_GAP',dates=missing))
        t['date']=pd.to_datetime(pd.to_datetime(t.entry_date,utc=True).dt.tz_convert('America/New_York').dt.date.map(previous))
        a=t.merge(labels[['date','symbol','first_session_sl']],on=['date','symbol'],how='left',validate='many_to_one')
        a['observed_first_session_sl']=a.exit_reason.isin(['STOP','STOP_GAP'])&pd.to_datetime(a.entry_date,utc=True).dt.date.eq(pd.to_datetime(a.exit_date,utc=True).dt.date)
        known=a.first_session_sl.notna();bad=known&a.first_session_sl.ne(a.observed_first_session_sl.astype(float))
        a.loc[bad].to_csv(out/'event-label-mismatches.csv',index=False);known_total+=int(known.sum());mismatches+=int(bad.sum())
        checks.append(dict(case=case,trades=len(t),known_event_labels=int(known.sum()),event_label_mismatches=int(bad.sum()),open_lots=int(windows.open_at_end.sum())))
    status='ARITHMETIC_CONTROL_AND_SCOPE_CHECKED_RESEARCH_ONLY' if not reserves and not mismatches else 'ARITHMETIC_CONTROL_PASS_WITH_PRICE_OR_EVENT_RESERVES'
    result=dict(status=status,checks=checks,price_reserves=reserves,known_event_labels=known_total,event_label_mismatches=mismatches,
        strict_pit=False,full_live_parity=False,entire_corpus_certified=False)
    atomic_json(ROOT/'post-run-review.json',result);return result


def launch(keys,phase,limit):
    waiting=list(keys);active=[];done=0
    try:
        while waiting or active:
            while waiting and len(active)<limit:
                key=str(waiting.pop(0));logs=ROOT/'logs';logs.mkdir(exist_ok=True)
                out=(logs/(phase+'-'+key+'.stdout.log')).open('ab');err=(logs/(phase+'-'+key+'.stderr.log')).open('ab')
                cmd=[sys.executable,'-X','utf8','-u','-m',__spec__.name,'--phase',phase,'--key',key]
                child=subprocess.Popen(cmd,cwd=Path.cwd(),stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                active.append((key,child,out,err))
            for item in active[:]:
                key,child,out,err=item
                if child.poll() is None:continue
                active.remove(item);out.close();err.close()
                if child.returncode:raise RuntimeError(phase+' '+key+' failed; inspect its log')
                done+=1
            atomic_json(ROOT/'progress.json',dict(status=phase.upper(),completed=done,total=len(keys),active=[x[0] for x in active],updated_at_utc=datetime.now(timezone.utc).isoformat()))
            if active:time.sleep(2)
    finally:
        for _,child,out,err in active:
            if child.poll() is None:child.terminate();child.wait()
            out.close();err.close()


def run():
    plan=prepare()
    try:
        launch([t['key'] for t in plan['tasks'] if not (ROOT/'jobs'/t['key']/'done.json').exists()],'worker',4)
        launch([y for y in range(2021,2027) if not (ROOT/'heads'/str(y)/'done.json').exists()],'head',2)
        assemble();prepare_market()
        if not (ROOT/'cases/CONTROL/validation.json').exists():launch(['CONTROL'],'case',1)
        launch([c for c in CASES[1:] if not (ROOT/'cases'/c/'validation.json').exists()],'case',3)
        finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['all','prepare','worker','head','case'],required=True);p.add_argument('--key');args=p.parse_args()
    if args.phase=='all':run()
    elif args.phase=='prepare':prepare()
    elif args.phase=='worker':worker(args.key)
    elif args.phase=='head':train_heads(int(args.key))
    else:run_case(args.key)
