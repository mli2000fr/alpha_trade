"""Isolated LONG-only T0/A/B experiment. No orders, HTTP, or SQL writes.

Oracle scores remain frozen. All three fits use identical past-only rows;
only their ordered input columns differ. Own-stock fits are lazy-cached for
symbols requested by the fixed Oracle pool, never selected by future returns.
"""
import argparse
from copy import deepcopy
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

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_q051_features173_20261116 import read,shared,link
from scripts.research.us_q051_global_rank_h10_20261115 import FEATURE_2026
from scripts.research.us_q051_features173_sip_replay_20261116 import ROOT as PRICES,provider_frame

ROOT=Path('artifacts/research/us_q051_feature_groups/20261116-lot1')
ORIGINAL=Path('artifacts/research/us_q051_features173/20261116-v2')
GROUPS={'T0':[],
 'A':['beta_252','r_squared_252','alpha_252','momentum_252_vs_market'],
 'B':['rolling_volatility_60','rolling_volatility_120','rolling_volatility_20_zscore',
      'rolling_volatility_60_zscore','rolling_volatility_120_zscore']}


def no_http(*args,**kwargs):raise ValueError('Provider and broker HTTP forbidden in this experiment')


def common_panel(bars,benchmark,calendar):
    from common.daily_bar_sources import select_daily_bars
    from modelFactory.features import compute_features
    from modelFactory.oracle_path.directional import INPUTS,DELTAS
    bars=select_daily_bars(bars.copy()).sort_values('date')
    symbol=str(bars.symbol.iloc[0]);grid=bars.set_index('date').reindex(calendar).rename_axis('date').reset_index()
    grid['symbol']=symbol
    for c in ['open','high','low','close','adj_close','volume','is_filled']:grid[c]=pd.to_numeric(grid[c],errors='coerce')
    if 'vwap' not in grid:grid['vwap']=grid.close
    good=(grid[['open','high','low','close']].notna().all(axis=1)&grid[['open','high','low','close']].gt(0).all(axis=1)
        &grid.is_filled.eq(0)&grid.volume.gt(0)&grid.instrument_id.notna())
    grid.loc[~good,['open','high','low','close','adj_close','volume','vwap']]=np.nan
    f=compute_features(grid,benchmark_df=benchmark,feature_set='expert',include_factors=True).set_index('date').reindex(calendar)
    for c in DELTAS:f[c+'_delta5']=(f[c]-f[c].shift(5)).where(f[c].notna().rolling(6).sum().eq(6))
    additions=list(dict.fromkeys(GROUPS['A']+GROUPS['B']))
    # One shared input-only eligibility mask; no future labels or returns here.
    eligible=(good.rolling(60,min_periods=60).sum().eq(60).to_numpy()
        &f[INPUTS].notna().mean(axis=1).ge(.8).to_numpy()
        &np.isfinite(f[additions].to_numpy(float)).all(axis=1))
    out=f.loc[eligible,[*INPUTS,*additions]].rename_axis('date').reset_index();out['symbol']=symbol
    return out


def repair_bars(bars):
    """Exact-date SIP split-price substitutions, identical for all variants."""
    from common.daily_bar_sources import select_daily_bars
    bars=select_daily_bars(bars.copy()).sort_values(['symbol','date']).reset_index(drop=True)
    for symbol in bars.symbol.unique():
        evidence=PRICES/'evidence'/(symbol+'.json')
        if not evidence.exists():continue
        f=provider_frame(evidence).set_index('date')
        mask=bars.symbol.eq(symbol)&bars.date.isin(f.index)
        for c in ['open','high','low','close','volume']:bars.loc[mask,c]=bars.loc[mask,'date'].map(f[c]).to_numpy()
        bars.loc[mask,'adj_close']=bars.loc[mask,'close']
        bars.loc[mask,'data_source']='alpaca_sip'
        bars.loc[mask,'data_adjustment']='split'
        bars.loc[mask,'is_filled']=0
    if bars.duplicated(['symbol','date']).any():raise ValueError('Ambiguous repaired daily bars')
    return bars


def fit_variants(panel,year,seed):
    from lightgbm import LGBMClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from sklearn.linear_model import LogisticRegression
    from modelFactory.oracle_path.directional import INPUTS,split
    from modelFactory.oracle_path.directional_metrics import predict,classification_metrics
    fit,cal=split(panel,year,'long')
    if (len(fit)<756 or len(cal)<126 or fit.long.value_counts().reindex([0.,1.],fill_value=0).min()<40
        or cal.long.value_counts().reindex([0.,1.],fill_value=0).min()<15):
        return {},dict(reason='INSUFFICIENT_COMMON_HISTORY_OR_CLASSES',fit_rows=len(fit),calibration_rows=len(cal))
    if not fit.available.lt(pd.Timestamp(year-1,1,1)).all() or not cal.available.lt(pd.Timestamp(year,1,1)).all():
        raise ValueError('Future label in fit or calibration')
    weights={};metrics={}
    for variant,extra in GROUPS.items():
        cols=[*INPUTS,*extra];lo,hi=fit[cols].quantile(.01),fit[cols].quantile(.99)
        x=fit[cols].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
        z=cal[cols].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
        model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True).set_output(transform='pandas'),
            LGBMClassifier(n_estimators=120,max_depth=3,num_leaves=7,learning_rate=.03,min_child_samples=60,
                reg_alpha=1.,reg_lambda=10.,verbosity=-1,n_jobs=1,random_state=seed))
        model.fit(x,fit.long.astype(int))
        from modelFactory.oracle_path.named_prediction import predict_proba
        cp=np.clip(predict_proba(model,z,cols)[:,1],1e-6,1-1e-6)
        if np.std(cp)<=1e-6:return {},dict(reason='CONSTANT_CALIBRATION_COMMON_ABSTENTION',variant=variant)
        calibrator=LogisticRegression(C=1.,random_state=seed).fit(np.log(cp/(1-cp)).reshape(-1,1),cal.long.astype(int))
        w=dict(model=model,calibrator=calibrator,lo=lo,hi=hi,features=cols)
        weights[variant]=w;metrics[variant]=classification_metrics(cal.long,predict(w,cal))
    return weights,dict(fit_rows=len(fit),calibration_rows=len(cal),fit_start=str(fit.date.min().date()),
        fit_end=str(fit.date.max().date()),fit_available_max=str(fit.available.max().date()),
        calibration_start=str(cal.date.min().date()),calibration_end=str(cal.date.max().date()),
        available=str(cal.available.max().date()),metrics=metrics)


def prepare():
    if (ROOT/'protocol.json').exists():return read(ROOT/'protocol.json')
    from modelFactory.oracle_path.directional import INPUTS
    ROOT.mkdir(parents=True,exist_ok=True)
    original=read(ORIGINAL/'protocol.json');models={};tasks=[];sources={}
    inputs=ROOT/'inputs';inputs.mkdir(exist_ok=True)
    for year in range(2021,2027):
        item=original['models'][str(year)];source=Path(item['root'])
        future=Path(original['models'][str(year+1)]['source_root']) if year<2026 else FEATURE_2026
        scores=pd.read_parquet(ORIGINAL/'predictions'/str(year)/'oracle.parquet')
        pool=scores.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True]).groupby('date').head(179)
        folder=ROOT/'years'/str(year);folder.mkdir(parents=True,exist_ok=True)
        scores.to_parquet(folder/'oracle.parquet',index=False);pool.to_parquet(folder/'pool.parquet',index=False)
        sources[str(folder/'oracle.parquet')]=digest(folder/'oracle.parquet')
        sources[str(folder/'pool.parquet')]=digest(folder/'pool.parquet')
        paths={}
        for path in sorted((future/'chunks').glob('*/bars.parquet')):
            for symbol in pd.read_parquet(path,columns=['symbol']).symbol.unique():paths[symbol]=str(path)
            sources[str(path)]=digest(path)
        cfg=read(source/'protocol.json')['training_config']
        for path in sorted((source/'chunks').glob('*/bars.parquet')):
            symbols=sorted(set(pd.read_parquet(path,columns=['symbol']).symbol)&set(pool.symbol))
            if not symbols:continue
            key=str(year)+'-'+path.parent.name
            tasks.append(dict(key=key,year=year,source=str(path),symbols=symbols,
                future=sorted({paths[s] for s in symbols if s in paths})))
            sources[str(path)]=digest(path)
        models[str(year)]=dict(oracle_batch=item['batch_id'],training_start=cfg['data']['training_start_date'],
            training_end=cfg['data']['training_end_date'],seed=cfg['reproducibility']['seed'],benchmark=item['benchmark'])
        sources[item['benchmark']]=digest(Path(item['benchmark']))
        next_benchmark=(Path(original['models'][str(year+1)]['benchmark']) if year<2026 else FEATURE_2026/'directional/benchmark.parquet')
        sources[str(next_benchmark)]=digest(next_benchmark)
    for base,pattern in [('backtesting','*.py'),('risk_management','*.py'),('modelFactory/oracle_path','*.py')]:
        sources.update({str(p):digest(p) for p in Path(base).glob(pattern)})
    for p in [Path(__file__),Path('scripts/research/us_q051_feature_groups_replay_20261116.py'),
        Path('modelFactory/features.py'),Path('modelFactory/factor_features.py'),Path('common/winner_pyramiding.py')]:sources[str(p)]=digest(p)
    sources.update({str(p):digest(p) for p in (PRICES/'evidence').glob('*.json')})
    plan=dict(status='SEALED',start='2021-01-01',end='2026-10-01',initial_equity=4000.,groups=GROUPS,
        features={k:[*INPUTS,*v] for k,v in GROUPS.items()},models=models,tasks=tasks,sources=sources,
        reference=read(PRICES/'replay-protocol.json')['reference'],
        selection='TOP10% Oracle -> TOP10 LONG; probability>.50; calibration AUC>=.50; no refill',
        common_rows=True,common_model_eligibility=True,fit_target='Net profitable LONG SL5/open11/8bp per leg',
        compute_scope='Lazy per-symbol annual cache for the frozen Oracle candidates; no return-based universe selection',
        provider_calls=0,LLM_calls=0,orders=0,SQL_writes=0,production_changes=False,
        created_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'progress.json',dict(status='READY',total_training_jobs=len(tasks),variants=list(GROUPS)))
    return plan


def worker(key):
    import joblib
    from common.config_loader import replay_market_registry
    from modelFactory.oracle.build_labels import nyse_sessions
    from modelFactory.oracle_path import directional as d
    from modelFactory.oracle_path.directional_metrics import predict
    from modelFactory.oracle.security_continuity import load_security_discontinuities
    plan=read(ROOT/'protocol.json');task=next(t for t in plan['tasks'] if t['key']==key)
    folder=ROOT/'jobs'/key;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'done.json').exists():
        for file,h in read(folder/'done.json')['outputs'].items():
            if digest(folder/file)!=h:raise ValueError('Changed completed job '+key)
        return
    try:
        for name in [task['source'],*task['future'],str(Path(__file__)),*[
            file for file in plan['sources'] if file.endswith('.py')]]:
            if digest(Path(name))!=plan['sources'][name]:raise ValueError('Changed input '+name)
        year=task['year'];item=plan['models'][str(year)];end=pd.Timestamp(min(plan['end'],f'{year}-12-31'))
        pieces=[pd.read_parquet(task['source'])]
        for path in task['future']:
            f=pd.read_parquet(path);pieces.append(f[f.date.gt(pd.Timestamp(item['training_end']))&f.date.le(end)])
        bars=pd.concat(pieces,ignore_index=True);bars=bars[bars.symbol.isin(task['symbols'])&bars.date.le(end)]
        bars=repair_bars(bars);benchmark=pd.read_parquet(item['benchmark'])
        # Benchmark must include the test year, using the next frozen archive,
        # never its fitted weights or labels.
        original=read(ORIGINAL/'protocol.json')
        bench_next=(Path(original['models'][str(year+1)]['benchmark']) if year<2026 else FEATURE_2026/'directional/benchmark.parquet')
        newer=pd.read_parquet(bench_next);benchmark=pd.concat([benchmark,newer[newer.date.gt(benchmark.date.max())]],ignore_index=True)
        if benchmark.date.duplicated().any():raise ValueError('Duplicate benchmark')
        pool=pd.read_parquet(ROOT/'years'/str(year)/'pool.parquet');registry=load_security_discontinuities()
        probabilities={v:[] for v in GROUPS};labels=[];records=[];skipped=[]
        with replay_market_registry(shared.restore_registry(shared.ROOT)),patch.object(requests.Session,'request',no_http):
            calendar=nyse_sessions(pd.Timestamp(item['training_start']).date(),end.date())
            for n,(symbol,g) in enumerate(bars.groupby('symbol')):
                atomic_json(folder/'progress.json',dict(status='TRAINING',year=year,symbol=symbol,completed=n,total=len(task['symbols'])))
                f=common_panel(g,benchmark,calendar)
                targets=d.labels(g,calendar,d.Settings(horizon_sessions=10),registry.get(symbol,()))
                panel=f.merge(targets,on='date',how='left',validate='one_to_one')
                wanted=pool[pool.symbol.eq(symbol)][['date','symbol']].merge(f,on=['date','symbol'],validate='one_to_one')
                for model_year,a in wanted.groupby(wanted.date.dt.year):
                    weights,meta=fit_variants(panel,int(model_year),item['seed'])
                    if not weights:
                        skipped.append(dict(symbol=symbol,year=int(model_year),**meta));continue
                    if not a.date.gt(pd.Timestamp(meta['available'])).all():raise ValueError('Future fitted model')
                    safe=hashlib.sha256(symbol.encode()).hexdigest()[:16]
                    for variant,w in weights.items():
                        path=folder/'models'/safe/f'{variant}-long-{model_year}.joblib';path.parent.mkdir(parents=True,exist_ok=True)
                        joblib.dump(w,path,compress=3);h=digest(path)
                        record=dict(symbol=symbol,model_year=int(model_year),variant=variant,file=str(path),sha256=h,
                            **{k:v for k,v in meta.items() if k!='metrics'},calibration=meta['metrics'][variant],features=w['features'])
                        records.append(record)
                        p=a[['date','symbol']].copy();p['long_probability']=predict(w,a);p['long_model_sha256']=h
                        p['long_auc']=meta['metrics'][variant]['auc'];p['long_auc_available_date']=meta['available']
                        p['long_auc_source']='calibration';p['long_auc_model_sha256']=h;probabilities[variant].append(p)
                labels.append(panel[panel.date.isin(wanted.date)][['date','symbol','available','long']])
        outputs={}
        for variant,parts in probabilities.items():
            f=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame(columns=['date','symbol','long_probability','long_model_sha256','long_auc','long_auc_available_date','long_auc_source','long_auc_model_sha256'])
            path=folder/(variant+'-probabilities.parquet');f.to_parquet(path,index=False);outputs[path.name]=digest(path)
        path=folder/'labels.parquet';pd.concat(labels,ignore_index=True).to_parquet(path,index=False);outputs[path.name]=digest(path)
        atomic_json(folder/'models.json',dict(models=records,skipped=skipped));outputs['models.json']=digest(folder/'models.json')
        atomic_json(folder/'done.json',dict(status='COMPLETED',outputs=outputs,models=len(records),skipped=len(skipped)))
        atomic_json(folder/'progress.json',dict(status='COMPLETED',models=len(records)))
    except BaseException as exc:
        atomic_json(folder/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


def assemble():
    from backtesting.per_symbol_selection import select_per_symbol,PerSymbolSelection
    from modelFactory.oracle_path.directional_metrics import classification_metrics
    plan=read(ROOT/'protocol.json');summaries=[]
    for variant in GROUPS:
        all_signals=[];all_ranks=[];annual={}
        for year in range(2021,2027):
            tasks=[t for t in plan['tasks'] if t['year']==year];parts=[];targets=[];model_files={}
            for task in tasks:
                folder=ROOT/'jobs'/task['key'];done=read(folder/'done.json')
                for file,h in done['outputs'].items():
                    if digest(folder/file)!=h:raise ValueError('Changed training output')
                parts.append(pd.read_parquet(folder/(variant+'-probabilities.parquet')));targets.append(pd.read_parquet(folder/'labels.parquet'))
                for r in read(folder/'models.json')['models']:
                    if r['variant']==variant:model_files[r['file']]=r['sha256']
            probs=pd.concat(parts,ignore_index=True);labels=pd.concat(targets,ignore_index=True)
            scores=pd.read_parquet(ROOT/'years'/str(year)/'oracle.parquet')
            ranking=scores.merge(probs,on=['date','symbol'],how='left',validate='one_to_one');ranking['short_probability']=np.nan
            selected=select_per_symbol(ranking,PerSymbolSelection(oracle_top_n=179,long_top_n=10,allow_short=False,min_long_probability=.5,min_long_auc=.5))
            signals=selected[selected.selected].rename(columns={'date':'trade_date'}).copy();signals['rank']=signals['rank'].astype(int)
            signals['oracle_amplitude_rank']=signals.oracle_rank;signals['entry_year']=year;signals['oracle_batch_id']=plan['models'][str(year)]['oracle_batch']
            signals['source_run_id']='feature-groups-'+variant+'-'+str(year)
            all_signals.append(signals);all_ranks.append(selected)
            sample=selected[selected.oracle_rank.le(179)].merge(labels,on=['date','symbol'],how='left',validate='one_to_one')
            sample=sample[sample.long.notna()&sample.long_probability.notna()&pd.to_datetime(sample.available).le(pd.Timestamp(min(plan['end'],f'{year}-12-31')))]
            summaries.append(dict(variant=variant,year=year,scope='Oracle TOP10%',**classification_metrics(sample.long,sample.long_probability)))
            annual[str(year)]=dict(batch_id=plan['models'][str(year)]['oracle_batch'],run_id=f'feature-groups-{variant}-{year}',
                training_start=plan['models'][str(year)]['training_start'],training_end=plan['models'][str(year)]['training_end'],
                universe_size=1790,horizon=10,first_signal=str(scores.date.min().date()),last_signal=str(scores.date.max().date()),
                research_directional_features=plan['features'][variant],research_model_files=model_files)
        folder=ROOT/'variants'/variant;folder.mkdir(parents=True,exist_ok=True)
        pd.concat(all_signals,ignore_index=True).sort_values(['trade_date','rank','symbol']).to_parquet(folder/'signals.parquet',index=False)
        pd.concat(all_ranks,ignore_index=True).to_parquet(folder/'rankings.parquet',index=False)
        atomic_json(folder/'models.json',annual)
    pd.DataFrame(summaries).to_csv(ROOT/'classification-by-year.csv',index=False)


def launch_tasks(tasks,limit,phase):
    waiting=list(tasks);running=[]
    try:
        while waiting or running:
            while waiting and len(running)<limit:
                key=waiting.pop(0);log=ROOT/'logs';log.mkdir(exist_ok=True)
                out=(log/(key+'.stdout.log')).open('ab');err=(log/(key+'.stderr.log')).open('ab')
                cmd=[sys.executable,'-X','utf8','-u','-m',__spec__.name,'--phase',phase,'--key',key]
                p=subprocess.Popen(cmd,cwd=Path.cwd(),stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                running.append((key,p,out,err))
            for key,p,out,err in running[:]:
                if p.poll() is None:continue
                out.close();err.close();running.remove((key,p,out,err))
                if p.returncode:raise RuntimeError('Worker failed: '+key+'; see its log')
            atomic_json(ROOT/'progress.json',dict(status='TRAINING' if phase=='worker' else 'REPLAYING',
                completed=len(tasks)-len(waiting)-len(running),total=len(tasks),active=[key for key,p,out,err in running],
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
            if running:time.sleep(2)
    finally:
        for key,p,out,err in running:
            if p.poll() is None:p.terminate();p.wait()
            out.close();err.close()


def run():
    plan=prepare()
    try:
        launch_tasks([t['key'] for t in plan['tasks']],4,'worker')
        atomic_json(ROOT/'progress.json',dict(status='ASSEMBLING_IDENTICAL_ORACLE_SELECTIONS'))
        assemble()
        from scripts.research import us_q051_feature_groups_replay_20261116 as replay
        replay.prepare_market()
        launch_tasks([v+'_'+p for v in GROUPS for p in ['SIMPLE','VOL20_REGIME']],3,'case')
        replay.finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['all','prepare','worker','case'],required=True);parser.add_argument('--key')
    args=parser.parse_args()
    if args.phase=='all':run()
    elif args.phase=='prepare':prepare()
    elif args.phase=='worker':worker(args.key)
    else:
        from scripts.research.us_q051_feature_groups_replay_20261116 import run_case
        run_case(args.key)
