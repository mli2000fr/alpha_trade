"""Fixed annual OOS Global H10 / Q051 comparison, local archived inputs only.

No SQL, provider, broker or production-model writes. Global is a cross-sectional
LightGBM LambdaRank (not a LONG probability); only its ordering is introduced.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import asdict
from datetime import date, datetime, timezone
import gc
import json
import logging
from multiprocessing import get_context
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from scripts.research import us_winner_continuous_q051_q088_20261108 as shared
from scripts.research.q051_global_rank_selection import POLICIES, select
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

ROOT=Path('artifacts/research/us_q051_global_rank_h10/20261115-v1')
BASE=shared.ROOT
EXT=Path('artifacts/research/us_winner_vol20_extensions/20261109-v1')
FEATURE_2026=Path('artifacts/models/model-factory-20261114122842-c59bed/oracle_path')
YEARS=tuple(range(2021,2027))
PARAMS=dict(objective='lambdarank',label_gain=list(range(10)),n_estimators=200,
    learning_rate=.03,max_depth=5,num_leaves=31,min_child_samples=150,
    reg_alpha=.1,reg_lambda=.1,subsample=.8,colsample_bytree=.7,
    random_state=42,n_jobs=4,verbosity=-1,deterministic=True,force_col_wise=True)


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def no_http(*args,**kwargs):raise ValueError('Provider and broker HTTP forbidden in frozen Global experiment')


def feature_contract():
    from modelFactory.config import TrainingConfig,DataConfig
    from modelFactory.global_ranking import _get_ranking_feature_columns
    cfg=TrainingConfig(data=DataConfig(feature_set='expert',include_score_components=False,
        include_factors_features=True))
    return _get_ranking_feature_columns(cfg)


def exact_session_targets(frame,sessions,horizon=10,breaks=None):
    """Actual J+h session endpoint, never h subsequent observations across gaps."""
    f=frame[['date','symbol','close','rolling_volatility_20']].copy()
    if f.duplicated(['date','symbol']).any():raise ValueError('Duplicate target key')
    days=pd.DatetimeIndex(sessions).normalize()
    future=dict(zip(days[:-horizon],days[horizon:]))
    f['label_available_date']=f.date.map(future)
    endpoints=f[['date','symbol','close']].rename(columns={'date':'label_available_date','close':'future_close'})
    f=f.merge(endpoints,on=['label_available_date','symbol'],how='left',validate='many_to_one')
    f['raw_return']=f.future_close/f.close-1
    f['scaled_return']=f.raw_return/f.rolling_volatility_20.clip(lower=.001)
    f.loc[~f.close.gt(0)|~f.future_close.gt(0),'scaled_return']=np.nan
    for symbol,events in (breaks or {}).items():
        for event in events:
            mask=f.symbol.eq(symbol)&f.date.le(event.last_predecessor_date)&f.label_available_date.ge(event.first_successor_date)
            f.loc[mask,['raw_return','scaled_return']]=np.nan
    return f[['date','symbol','label_available_date','raw_return','scaled_return']]


def label_deciles(frame):
    f=frame.copy()
    by=f.groupby('date').scaled_return
    bounds=by.quantile([.01,.99]).unstack()
    values=f.scaled_return.clip(f.date.map(bounds[.01]),f.date.map(bounds[.99]))
    f['target_percentile']=values.groupby(f.date).rank(pct=True)
    f['label']=np.floor(f.target_percentile*10).clip(0,9).astype('int32')
    return f


def chronological_split(frame,signal_start,sessions,validation_sessions=126):
    days=pd.DatetimeIndex(sessions).normalize()
    cutoff=days[days<pd.Timestamp(signal_start)].max()
    if pd.isna(cutoff):raise ValueError('No causal training cutoff')
    eligible=frame[frame.label_available_date.le(cutoff)].copy()
    val_days=days[days<=cutoff][-validation_sessions-10:-10]
    if len(val_days)!=validation_sessions:raise ValueError('Validation calendar too short')
    val_start=val_days[0]
    fit=eligible[eligible.date.lt(val_start)&eligible.label_available_date.lt(val_start)].copy()
    val=eligible[eligible.date.isin(val_days)].copy()
    if fit.empty or val.empty or fit.label_available_date.max()>=val.date.min():raise ValueError('Invalid purged split')
    return fit,val,cutoff


def cached_features(model_root,start,end,columns,progress=None):
    """Use only named past-price features; no targets, fitted weights or scores."""
    import pyarrow.parquet as pq
    source=Path(model_root);options=read(source/'feature_profile.json')['generator_options']
    direct=[c for c in columns if not c.endswith('_xs_rank')]
    wanted=list(dict.fromkeys(['date','symbol','close','rolling_volatility_20',*direct]))
    pieces=[];sources={};files=sorted((source/'chunks').glob('*/features.parquet'))
    for i,path in enumerate(files):
        if digest(path)!=read(path.parent/'done.json')['files']['features.parquet']:raise ValueError('Changed archived features')
        sources[str(path)]=digest(path)
        missing=set(wanted)-set(pq.read_schema(path).names)
        if missing:raise ValueError('Missing historical feature columns: '+str(sorted(missing)))
        f=pd.read_parquet(path,columns=wanted,filters=[('date','>=',pd.Timestamp(start)),('date','<=',pd.Timestamp(end))])
        pieces.append(f)
        if progress:progress(i+1,len(files))
    frame=pd.concat(pieces,ignore_index=True).sort_values(['date','symbol']).reset_index(drop=True)
    if frame.duplicated(['date','symbol']).any():raise ValueError('Duplicate archived features')
    # Recompute percentiles over the full model universe, never the 25-title chunks.
    sources_xs=[c[:-8] for c in columns if c.endswith('_xs_rank')]
    ranked=frame.groupby('date')[sources_xs].rank(pct=True).astype('float32')
    ranked.columns=[c+'_xs_rank' for c in sources_xs]
    frame=pd.concat([frame,ranked],axis=1)
    frame[columns]=frame[columns].replace([np.inf,-np.inf],np.nan).astype('float32')
    return frame,sources,options


def prepare(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    if (root/'request.json').exists():return read(root/'request.json')
    base=read(BASE/'protocol.json');columns=feature_contract()
    models={}
    for year in YEARS:
        batch=base['annual_models'][str(year)]['batch_id']
        train=Path('artifacts/models')/batch/'oracle_path'
        contract=read(train/'protocol.json')
        if len(contract['universe'])!=1790:raise ValueError('Different Oracle universe')
        next_root=(Path('artifacts/models')/base['annual_models'][str(year+1)]['batch_id']/'oracle_path' if year<2026 else FEATURE_2026)
        other=read(next_root/'protocol.json')
        if set(other['universe'])!=set(contract['universe']):raise ValueError('Feature-only cache universe mismatch')
        if read(next_root/'feature_profile.json')['generator_options']!=read(train/'feature_profile.json')['generator_options']:
            raise ValueError('Train/test feature generators differ')
        models[str(year)]=dict(oracle_batch_id=batch,train_root=str(train),test_features_root=str(next_root),
            training_start=contract['training_config']['data']['training_start_date'],
            training_end=contract['training_config']['data']['training_end_date'],universe=contract['universe'])
    paths=[Path(__file__),Path('scripts/research/q051_global_rank_selection.py'),Path('modelFactory/global_ranking.py'),
        Path('modelFactory/features.py'),Path('modelFactory/factor_features.py'),Path('config/data_quality/security_discontinuities.json')]
    sources={str(p):digest(p) for p in paths}
    # Freeze every native replay/risk source used by the reference before training.
    for folder,pattern in [('backtesting','*.py'),('risk_management','*.py'),('execution_engine','winner*.py'),('common','winner*.py')]:
        sources.update({str(p):digest(p) for p in Path(folder).glob(pattern)})
    request=dict(start='2021-01-01',end='2026-10-01',initial_equity=4000.,annual_reset=False,
        created_at_utc=datetime.now(timezone.utc).isoformat(),annual_models=models,policies=list(POLICIES),
        model=dict(backend='lightgbm',parameters=PARAMS,early_stopping_rounds=20,validation_sessions=126,
            refit_after_validation=False,target='pure H10 closing-return rank scaled by trailing volatility20; decile labels; no horizon smoothing or sector/factor target neutralization',
            features=columns,training='annual rolling windows same as annual Oracle, purged 126-session validation, labels available before test signal',
            test_scores='full-universe genuine percentiles, missing scores stay absent',time_weights='exp(-calendar_days/360) on fit only'),
        selection=dict(oracle_top_n=179,final_top_n=5,min_long_probability_strict=.5,min_long_auc_inclusive=.5,refill=False),
        reference_root=str(BASE),market_extension_root=str(EXT),sources=sources,
        limitations=['Fixed contemporary universe / survivorship risk; not certified full PIT.',
            'Revised/adjusted archived prices; model timing is OOS, not historical data-vintage certification.',
            '2026 feature-only cache comes from c59bed; NO c59bed fitted weights, AUC or predictions used.',
            'Terminal Global H10 target differs from path-dependent SL5/open11 trading outcome.'],
        provider_calls=0,broker_calls=0,SQL_writes=0,production_changes=False)
    atomic_json(root/'request.json',request)
    atomic_json(root/'progress.json',dict(status='PROTOCOL_FROZEN',models=6,policies=list(POLICIES)))
    return request


def train_year(root,year):
    import lightgbm as lgb
    from scipy.stats import spearmanr
    from modelFactory.oracle.security_continuity import load_security_discontinuities
    from modelFactory.oracle.build_labels import nyse_sessions
    from common.config_loader import replay_market_registry
    from backtesting.isolation import ReadOnlyReplay
    root=Path(root);folder=root/'years'/str(year);folder.mkdir(parents=True,exist_ok=True)
    if (folder/'receipt.json').exists():
        r=read(folder/'receipt.json')
        for path,sha in r['outputs'].items():
            if digest(folder/path)!=sha:raise ValueError('Changed annual output')
        return r
    plan=read(root/'request.json');spec=plan['annual_models'][str(year)];columns=plan['model']['features']
    raw=pd.read_parquet(BASE/'inputs/rankings'/f'{year}.parquet');dates=pd.DatetimeIndex(raw.date.unique()).sort_values()
    def tick(stage,done=0,total=0):
        atomic_json(folder/'progress.json',dict(status=stage,year=year,completed=done,total=total))
    with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(BASE)),patch.object(requests.Session,'request',no_http):
        days=nyse_sessions(pd.Timestamp(spec['training_start']).date(),pd.Timestamp(spec['training_end']).date())
        tick('READING_VERIFIED_TRAIN_FEATURES')
        f,sources,options=cached_features(spec['train_root'],spec['training_start'],spec['training_end'],columns,
            lambda n,t:tick('READING_VERIFIED_TRAIN_FEATURES',n,t))
        target=exact_session_targets(f,days,breaks=load_security_discontinuities())
        eligible=f.merge(target,on=['date','symbol'],validate='one_to_one').dropna(subset=[*columns,'scaled_return','label_available_date'])
        eligible=label_deciles(eligible)
        fit,val,cutoff=chronological_split(eligible,dates[0],days)
        fit=fit.sort_values(['date','symbol']);val=val.sort_values(['date','symbol'])
        del eligible,f,target;gc.collect()
        tick('TRAINING_GLOBAL_H10',0,200)
        model=lgb.LGBMRanker(**plan['model']['parameters'])
        def callback(env):
            if env.iteration%5==0:tick('TRAINING_GLOBAL_H10',env.iteration+1,200)
        weights=np.exp(-(fit.date.max()-fit.date).dt.days.to_numpy()/360.)
        model.fit(fit[columns],fit.label,group=fit.groupby('date',sort=True).size().to_numpy(),sample_weight=weights,
            eval_set=[(val[columns],val.label)],eval_group=[val.groupby('date',sort=True).size().to_numpy()],
            eval_at=[5,20,50],callbacks=[lgb.early_stopping(20,first_metric_only=True,verbose=False),callback])
        model.booster_.save_model(str(folder/'global_h10.txt'))
        vp=model.predict(val[columns],num_iteration=model.best_iteration_,num_threads=4)
        vf=val[['date','symbol','raw_return','target_percentile']].copy();vf['prediction']=vp
        ic=[spearmanr(g.prediction,g.target_percentile).statistic for _,g in vf.groupby('date') if g.prediction.nunique()>1]
        vf.to_parquet(folder/'validation.parquet',index=False)
        receipt=dict(year=year,oracle_batch_id=spec['oracle_batch_id'],model_available_date=str(cutoff.date()),
            first_signal=str(dates[0].date()),fit_start=str(fit.date.min().date()),fit_end=str(fit.date.max().date()),
            fit_label_available_max=str(fit.label_available_date.max().date()),fit_rows=len(fit),
            validation_start=str(val.date.min().date()),validation_end=str(val.date.max().date()),
            validation_label_available_max=str(val.label_available_date.max().date()),validation_rows=len(val),
            validation_daily_rank_ic_mean=float(np.nanmean(ic)),best_iteration=model.best_iteration_,feature_count=len(columns),
            parameters=plan['model']['parameters'],features=columns,train_sources=sources,generator_options=options,
            model_sha256=digest(folder/'global_h10.txt'))
        if pd.Timestamp(receipt['model_available_date'])>=dates[0]:raise ValueError('Future Global model')
        del fit,val,vf,weights;gc.collect()
        tick('READING_VERIFIED_TEST_FEATURES')
        f,test_sources,_=cached_features(spec['test_features_root'],dates[0],dates[-1],columns,
            lambda n,t:tick('READING_VERIFIED_TEST_FEATURES',n,t))
        f=f[f.date.isin(dates)].copy();complete=f[columns].notna().all(axis=1)
        scores=f.loc[complete,['date','symbol']].copy()
        scores['raw_global_score']=model.predict(f.loc[complete,columns],num_iteration=model.best_iteration_,num_threads=4)
        scores['global_rank_10']=scores.groupby('date').raw_global_score.rank(pct=True)
        scores['global_model_sha256']=receipt['model_sha256'];scores['global_model_available_date']=cutoff
        scores.to_parquet(folder/'scores.parquet',index=False)
        oracle_pool=raw.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True]).groupby('date').head(179)
        coverage=oracle_pool[['date','symbol']].merge(scores[['date','symbol','global_rank_10']],on=['date','symbol'],how='left',validate='one_to_one')
        coverage['covered']=coverage.global_rank_10.notna()
        coverage.groupby('date').agg(oracle_candidates=('symbol','size'),global_covered=('covered','sum')).reset_index().to_csv(folder/'coverage.csv',index=False)
        receipt.update(test_sources=test_sources,test_rows=len(scores),oracle_pool_rows=len(coverage),
            oracle_pool_missing=int((~coverage.covered).sum()),outputs={p.name:digest(p) for p in [folder/'global_h10.txt',folder/'validation.parquet',folder/'scores.parquet',folder/'coverage.csv']})
        atomic_json(folder/'receipt.json',receipt);tick('COMPLETED_GLOBAL_H10')
    return receipt


def selections(root):
    root=Path(root);parts={p:[] for p in POLICIES};cover=[]
    for year in YEARS:
        r=read(root/'years'/str(year)/'receipt.json');file=root/'years'/str(year)/'scores.parquet'
        if digest(file)!=r['outputs']['scores.parquet']:raise ValueError('Changed Global scores')
        base_file=BASE/'inputs/rankings'/f'{year}.parquet'
        manifest=read(BASE/'inputs/manifest.json')['files']
        if digest(base_file)!=manifest.get(f'rankings/{year}.parquet',manifest.get(f'rankings\\{year}.parquet')):raise ValueError('Changed Oracle ranking')
        f=pd.read_parquet(base_file);f['date']=pd.to_datetime(f.date)
        scores=pd.read_parquet(file)
        if not scores.date.gt(pd.to_datetime(scores.global_model_available_date)).all():raise ValueError('Future Global scores')
        joined=f.merge(scores,on=['date','symbol'],how='left',validate='one_to_one')
        for policy in POLICIES:
            ranked=select(joined,policy);chosen=ranked[ranked.selected].copy()
            chosen['rank']=chosen['rank'].astype(int);chosen['side']='long';chosen['oracle_amplitude_rank']=chosen.oracle_rank
            chosen['entry_year']=year;chosen['oracle_batch_id']=read(root/'request.json')['annual_models'][str(year)]['oracle_batch_id']
            parts[policy].append(chosen.rename(columns={'date':'trade_date'}))
            (root/'rankings').mkdir(exist_ok=True)
            ranked.to_parquet(root/'rankings'/f'{year}-{policy}.parquet',index=False)
        c=pd.read_csv(root/'years'/str(year)/'coverage.csv');c['year']=year;cover.append(c)
    (root/'inputs').mkdir(exist_ok=True)
    for policy in POLICIES:
        f=pd.concat(parts[policy],ignore_index=True);f.to_parquet(root/'inputs'/f'signals-{policy}.parquet',index=False)
    actual=pd.concat(parts['Q051_REFERENCE'],ignore_index=True).sort_values(['trade_date','symbol'])
    old=pd.read_parquet(BASE/'inputs/signals-Q051_050.parquet').sort_values(['trade_date','symbol'])
    for c in ['trade_date','symbol','rank']:
        a=actual[c].astype(int).to_numpy() if c=='rank' else actual[c].to_numpy()
        b=old[c].astype(int).to_numpy() if c=='rank' else old[c].to_numpy()
        if not np.array_equal(a,b):raise ValueError('Reference selection differs: '+c)
    pd.concat(cover,ignore_index=True).to_csv(root/'coverage.csv',index=False)
    atomic_json(root/'selection-receipt.json',dict(reference_exact_match=True,
        cases={p:dict(signals=sum(map(len,parts[p])),symbols=int(pd.concat(parts[p]).symbol.nunique())) for p in POLICIES}))


def market_data():
    pivots,sectors,actions=shared.market_data(BASE)
    extra=pd.read_parquet(EXT/'inputs/daily.parquet')
    for field in pivots:
        e=extra.pivot(index='date',columns='symbol',values=field)
        if set(e)&set(pivots[field]):raise ValueError('Market supplement would overwrite reference')
        pivots[field]=pd.concat([pivots[field],e],axis=1).sort_index()
    sectors=pd.concat([sectors,pd.read_parquet(EXT/'inputs/sectors.parquet')],ignore_index=True)
    actions=pd.concat([actions,pd.read_parquet(EXT/'inputs/actions.parquet')],ignore_index=True)
    if sectors.symbol.duplicated().any():raise ValueError('Duplicate sector metadata')
    return pivots,sectors,actions


def replay(root,policy_name):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.winner_portfolio_budget import replay_protections
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from scripts.research.us_winner_vol20_extensions_20261109 import ExtendedPrices
    root=Path(root);folder=root/'cases'/policy_name;out=folder/'result'
    if (folder/'progress.json').exists() and read(folder/'progress.json').get('status')=='COMPLETED_EXPLORATORY':return str(folder)
    out.mkdir(parents=True,exist_ok=True)
    plan=read(root/'request.json');base=read(BASE/'protocol.json')
    for file,sha in plan['sources'].items():
        if digest(Path(file))!=sha:raise ValueError('Changed experiment/native source: '+file)
    cfg=shared.configuration(base['reference'],shared.CASES['Q051_050'])
    from backtesting.risk_overlay import RegimeFilterConfig
    cfg.risk_overlay.regime_filter=RegimeFilterConfig(enabled=True,sma_window=200,bear_threshold=-.02)
    pivots,sectors,actions=market_data()
    signals=pd.read_parquet(root/'inputs'/f'signals-{policy_name}.parquet')
    missing=set(signals.symbol)-set(pivots['close'])
    if missing:raise ValueError('Missing frozen market symbols: '+str(sorted(missing)))
    budget,gate=replay_protections(pivots['close'],daily_entry=True,target=.2,regime=True)
    reference=deepcopy(base['reference']);reference['risk']=asdict(cfg.risk_config)
    reference['arguments'].update(top_n=179,per_symbol_top_long=5,per_symbol_min_long_probability=.5,per_symbol_min_long_auc=.5,
        drawdown_controller=False,portfolio_vol_target=.2,entry_regime_filter=True)
    protocol=dict(start=plan['start'],end=plan['end'],initial_equity=4000.,annual_reset=False,
        annual_models=base['annual_models'],global_models=plan['annual_models'],reference=reference,
        selection_policy=policy_name,request_sha256=digest(root/'request.json'),
        evaluation_mode='ANNUAL_MODEL_TIMING_OOS_FIXED_CURRENT_UNIVERSE',limitations=plan['limitations'])
    atomic_json(folder/'protocol.json',protocol)
    atomic_json(out/'configuration.json',dict(profile=policy_name,portfolio=asdict(cfg)))
    try:
        with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(BASE)),patch.object(requests.Session,'request',no_http):
            def tick(done,total,day):
                s=dict(status='REPLAYING',completed=done,total=total,last_date=str(day),case=policy_name)
                atomic_json(folder/'progress.json',s);atomic_json(out/'progress.json',s)
            result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
                volume=pivots['volume'],signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),
                intraday_source=ExtendedPrices(EXT),winner_research_assumptions=True,winner_progress=tick,
                winner_corporate_actions=actions.to_dict('records'),winner_selection_source=gate,winner_entry_risk_policy=budget)
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
            pd.DataFrame(budget.receipts).to_csv(out/'portfolio-risk-decisions.csv',index=False)
            pd.DataFrame(gate.receipts).to_csv(out/'regime-decisions.csv',index=False)
            report=metrics(result,4000.);annual=[];opening=4000.
            for year in YEARS:
                curve=result.equity_curve[result.equity_curve.index.year==year];trades=result.closed_trades_df;marks=result.intraday_equity_curve
                closed=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(year)] if len(trades) else trades
                part=BacktestResult(equity_curve=curve,closed_trades_df=closed,
                    intraday_equity_curve=marks[pd.to_datetime(marks.timestamp,utc=True).dt.year.eq(year)],
                    tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
                row=metrics(part,opening);row.update(year=year,model=base['annual_models'][str(year)]['batch_id']);annual.append(row)
                opening=float(curve.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
            report.update(case=policy_name,selected_signals=len(signals),selected_symbols=int(signals.symbol.nunique()),
                annual_models=base['annual_models'],annual_reset=False,strict_pit=False,model_timing_oos=True,
                provider_calls=0,SQL_writes=0,orders=0,limitations=plan['limitations'],finished_at_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(out/'report.json',report);atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
    except BaseException as exc:
        atomic_json(folder/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise
    if policy_name=='Q051_REFERENCE':
        expected=read('artifacts/research/us_winner_q051_risk_budget/20261109-v1/REGIME_VOL20/result/report.json')
        keys=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','winners','losers','costs','average_gross_capital']
        diffs={k:dict(actual=report[k],expected=expected[k]) for k in keys if not np.isclose(report[k],expected[k],atol=1e-6,rtol=1e-10)}
        atomic_json(root/'economic-baseline-validation.json',dict(status='PASS' if not diffs else 'DIFFERENCE',differences=diffs))
        if diffs:raise ValueError('Native economic reference differs; investigate before concluding')
    from ihm.services.backtesting_import import import_continuous_winner
    record=import_continuous_winner(folder,run_id=f'20261115_q051_global_{policy_name.lower()}',
        label='Q051 vol20 + régime 2021–2026 — '+policy_name+' — Global H10 annuel OOS',result_subdir='result')
    atomic_json(folder/'ihm.json',dict(run_id=record['run_id']))
    return str(folder)


def consolidate(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root=Path(root);reports=[];annual=[];curves={}
    keys=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','winners','losers','average_gross_capital','average_gross_exposure_pct','costs']
    for policy in POLICIES:
        out=root/'cases'/policy/'result';r=read(out/'report.json')
        reports.append(dict(policy=policy,**{k:r.get(k) for k in keys}))
        a=pd.read_csv(out/'annual-summary.csv');a['policy']=policy;annual.append(a)
        curves[policy]=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
    pd.DataFrame(reports).to_csv(root/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(root/'annual-comparison.csv',index=False)
    frame=pd.DataFrame(curves);frame.to_csv(root/'capital-comparison.csv',index_label='date')
    fig,axes=plt.subplots(2,1,figsize=(13,9),sharex=True,gridspec_kw={'height_ratios':[2,1]})
    for name,s in curves.items():
        axes[0].plot(s.index,s,label=name);axes[1].plot(s.index,100*(s/s.cummax().clip(lower=4000)-1),label=name)
    axes[0].set_title('Q051 volatilité 20 % + régime — Global H10 — 2021 au 1 octobre 2026')
    axes[0].set_ylabel('Capital ($), départ 4 000');axes[1].set_ylabel('Drawdown clôture (%)')
    for ax in axes:ax.grid(alpha=.2);ax.legend()
    fig.text(.07,.01,'Même TOP10 % Oracle, TOP5 puis seuils LONG/AUC. Modèles annuels causaux ; univers actuel et couverture intraday partielle.',fontsize=8)
    fig.tight_layout(rect=(0,.03,1,1));fig.savefig(root/'capital-comparison.png',dpi=140);plt.close(fig)
    atomic_json(root/'report.json',dict(status='COMPLETED_EXPLORATORY',results=reports,model_timing_oos=True,strict_pit=False,
        SQL_writes=0,provider_calls=0,orders=0,production_changes=False))
    atomic_json(root/'progress.json',read(root/'report.json'))


def run(root,workers):
    root=Path(root);prepare(root)
    for file,sha in read(root/'request.json')['sources'].items():
        if digest(Path(file))!=sha:raise ValueError('Changed frozen source before resume: '+file)
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        tasks={pool.submit(train_year,str(root),y):y for y in YEARS}
        done=0
        for task in as_completed(tasks):
            receipt=task.result();done+=1
            atomic_json(root/'progress.json',dict(status='TRAINING_ANNUAL_GLOBALS',completed=done,total=6,last_year=receipt['year']))
    selections(root)
    # Verify unchanged native reference first, then launch the two new sorters.
    replay(root,'Q051_REFERENCE')
    with ProcessPoolExecutor(max_workers=2,mp_context=get_context('spawn')) as pool:
        tasks=[pool.submit(replay,str(root),p) for p in POLICIES[1:]]
        for task in as_completed(tasks):task.result()
    consolidate(root)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',default=str(ROOT));p.add_argument('--workers',type=int,default=2)
    p.add_argument('--phase',choices=['all','prepare','select','replay','consolidate'],default='all');p.add_argument('--policy',choices=POLICIES)
    args=p.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if args.phase=='prepare':prepare(Path(args.output_dir))
    elif args.phase=='select':selections(args.output_dir)
    elif args.phase=='replay':replay(args.output_dir,args.policy)
    elif args.phase=='consolidate':consolidate(args.output_dir)
    else:
        try:run(args.output_dir,args.workers)
        except BaseException as exc:
            atomic_json(Path(args.output_dir)/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise
