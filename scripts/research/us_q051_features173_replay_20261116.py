"""Frozen-data inference and matched Q051 replays for fresh 173-input bundles."""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
import gc
import json
import logging
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from scripts.research.us_q051_features173_20261116 import ROOT,read,shared
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_q051_global_rank_h10_20261115 import cached_features,FEATURE_2026


def no_http(*a,**kw):raise ValueError('Network forbidden: frozen 173-feature research only')


def matched_control(year):
    """Old 24-input weights, new identical Oracle scores and frozen price inputs."""
    import joblib
    from modelFactory.oracle_path import directional as d
    from modelFactory.oracle_path.directional_metrics import predict
    from modelFactory.oracle.build_labels import nyse_sessions
    from backtesting.per_symbol_selection import attach_calibration_auc,select_per_symbol,PerSymbolSelection
    from common.config_loader import replay_market_registry
    plan=read(ROOT/'protocol.json');item=plan['models'][str(year)];folder=ROOT/'predictions'/str(year)
    def tick(status,**kw):atomic_json(folder/'control-progress.json',dict(status=status,year=year,**kw))
    receipt=folder/'control-receipt.json'
    if receipt.exists():
        r=read(receipt)
        for file,h in r['outputs'].items():
            if digest(folder/file)!=h:raise ValueError('Changed matched control')
        return r
    tick('LOADING_MATCHED_COMPACT_MODELS')
    root=Path(item['source_root']);m,mhash=d.load_manifest(root)
    if m['features']!=d.INPUTS:raise ValueError('24-input control required')
    scores=pd.read_parquet(folder/'oracle.parquet');dates=pd.DatetimeIndex(scores.date.unique()).sort_values()
    pool=scores.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True]).groupby('date').head(179)
    names=set(pool.symbol);start=dates.min()-pd.Timedelta(days=650)
    source=Path(plan['models'][str(year+1)]['source_root']) if year<2026 else FEATURE_2026
    benchmark_file=(Path(plan['models'][str(year+1)]['benchmark']) if year<2026
        else source/'directional/benchmark.parquet')
    benchmark=pd.read_parquet(benchmark_file)
    records={(r['symbol'],r['year'],r['side']):r for r in m['models']};pieces=[];examples=[];bar_hashes={};processed=0
    with replay_market_registry(shared.restore_registry(shared.ROOT)),patch.object(requests.Session,'request',no_http):
        calendar=nyse_sessions(start.date(),dates.max().date())
        for path in sorted((source/'chunks').glob('*/bars.parquet')):
            if digest(path)!=read(path.parent/'done.json')['files']['bars.parquet']:raise ValueError('Changed control bars')
            bar_hashes[str(path)]=digest(path)
            bars=pd.read_parquet(path,filters=[('date','>=',start),('date','<=',dates.max())]);bars=bars[bars.symbol.isin(names)]
            for symbol,g in bars.groupby('symbol'):
                f=d.panels(g,benchmark,calendar)
                f=pool.loc[pool.symbol.eq(symbol),['date','symbol']].merge(f,on=['date','symbol'],validate='one_to_one')
                for y,a in f.groupby(f.date.dt.year):
                    out=a[['date','symbol']].copy()
                    for side in ['long','short']:
                        out[side+'_probability']=np.nan;out[side+'_model_sha256']=None
                        r=records.get((symbol,int(y),side))
                        if r is None:continue
                        if not a.date.gt(pd.Timestamp(r['available'])).all():raise ValueError('Future control model')
                        out[side+'_probability']=predict(joblib.load(root/r['file']),a)
                        out[side+'_model_sha256']=r['sha256']
                    pieces.append(out)
                if len(examples)<3:examples.append(g)
                processed+=1
                if processed%25==0:tick('SCORING_MATCHED_24',completed=processed,total=len(names))
        probs=pd.concat(pieces,ignore_index=True)
        ranked=d.rank(scores,probs,d.Settings(**m['contract']));ranked['manifest_sha256']=mhash
        sample_names=[str(g.symbol.iloc[0]) for g in examples]
        sample=pool[pool.symbol.isin(sample_names)].groupby('symbol').head(2)
        with patch('modelFactory.data_loader.load_benchmark_bars',return_value=benchmark):
            native=d.infer(None,root,sample,bar_frame=pd.concat(examples,ignore_index=True))
        check=native.merge(probs,on=['date','symbol'],suffixes=('_native','_vector'),validate='one_to_one')
        for side in ['long','short']:
            if not np.allclose(check[side+'_probability_native'].astype(float),check[side+'_probability_vector'].astype(float),
                rtol=0,atol=1e-12,equal_nan=True):raise ValueError('Control vector/native differs')
        d.validate_saved(root,scores,ranked);ranked=attach_calibration_auc(ranked,root)
        selected=select_per_symbol(ranked,PerSymbolSelection(oracle_top_n=179,long_top_n=10,
            allow_long=True,allow_short=False,min_long_probability=.5,min_long_auc=.5))
        selected=selected[selected.selected].rename(columns={'date':'trade_date'}).copy()
        selected['rank']=selected['rank'].astype(int);selected['oracle_amplitude_rank']=selected.oracle_rank
        selected['oracle_batch_id']=item['batch_id'];selected['directional_batch_id']=item['source_batch']
        selected['source_run_id']='features24-matched-'+str(year);selected['entry_year']=year
        ranked.to_parquet(folder/'control-ranking.parquet',index=False);selected.to_parquet(folder/'control-signals.parquet',index=False)
        result=dict(year=year,features=24,oracle_batch=item['batch_id'],directional_batch=item['source_batch'],
            manifest_sha256=mhash,benchmark_sha256=digest(benchmark_file),bar_sources=bar_hashes,
            native_equivalence_rows=len(check),signals=len(selected),symbols=int(selected.symbol.nunique()),
            outputs={n:digest(folder/n) for n in ['control-ranking.parquet','control-signals.parquet']})
        atomic_json(receipt,result)
        tick('COMPLETED',signals=len(selected))
        return result


def forecast(year):
    import joblib
    from modelFactory.oracle_path.predict import load_contract,select_fold
    from modelFactory.oracle_path.train import model_probabilities
    from modelFactory.oracle_path.directional import load_manifest,rank,infer,validate_saved,Settings
    from modelFactory.oracle_path.directional_features import oracle_panels
    from modelFactory.oracle_path.directional_metrics import predict
    from modelFactory.oracle.build_labels import nyse_sessions
    from backtesting.per_symbol_selection import attach_calibration_auc,select_per_symbol,PerSymbolSelection
    from common.config_loader import replay_market_registry
    plan=read(ROOT/'protocol.json');item=plan['models'][str(year)]
    folder=ROOT/'predictions'/str(year);folder.mkdir(parents=True,exist_ok=True)
    if (folder/'receipt.json').exists():
        r=read(folder/'receipt.json')
        for file,h in r['outputs'].items():
            if digest(folder/file)!=h:raise ValueError('Changed prediction output')
        matched_control(year)
        return r
    def tick(status,**kw):atomic_json(folder/'progress.json',dict(status=status,year=year,**kw))
    root,p,profile,folds=load_contract('artifacts/models',item['batch_id'])
    manifest,mhash=load_manifest(root);columns=profile['feature_columns']
    if manifest['features']!=columns or len(columns)!=173:raise ValueError('Wrong input vector')
    if pd.Timestamp(p['training_config']['data']['training_end_date'])>=pd.Timestamp(year,1,1):raise ValueError('Future annual training')
    tick('VERIFYING_ALL_FITTED_FEATURE_VECTORS',total=len(manifest['models']))
    for record in manifest['models']:
        w=joblib.load(root/record['file'])
        if (w.get('features')!=columns or w['model'].n_features_in_!=173
                or w['model'][-1].n_features_in_!=173
                or list(w['model'][-1].feature_names_in_)!=columns):
            raise ValueError('A fitted LONG/SHORT model has a different actual input vector')
    model_summary=pd.DataFrame([dict(symbol=r['symbol'],model_year=r['year'],side=r['side'],
        fit_rows=r['fit_rows'],calibration_rows=r['calibration_rows'],available=r['available'],
        fit_start=r['fit_start'],fit_end=r['fit_end'],calibration_start=r['calibration_start'],calibration_end=r['calibration_end'],
        calibration_auc=r['metrics']['calibration']['auc'],features=173) for r in manifest['models']])
    model_summary.to_csv(folder/'models.csv',index=False)
    prior_file=Path(item['source_root'])/'directional/manifest.json'
    if digest(prior_file)!=item['original_annual_record']['model_manifest_sha256']:raise ValueError('Old comparison manifest changed')
    old={(r['symbol'],r['year'],r['side']):r for r in read(prior_file)['models'] if r['year'] in item['directional_years']}
    new={(r['symbol'],r['year'],r['side']):r for r in manifest['models']}
    common=set(old)&set(new)
    atomic_json(folder/'training-audit.json',dict(status='PASS',actual_173_vectors_checked=len(manifest['models']),
        model_counts=model_summary.groupby(['model_year','side']).size().rename('count').reset_index().to_dict('records'),
        skipped=len(manifest['skipped']),old_compact_models=len(old),common_model_keys=len(common),
        only_173_model_keys=len(set(new)-set(old)),only_24_model_keys=len(set(old)-set(new)),
        common_models_with_changed_fit_rows=sum(new[k]['fit_rows']!=old[k]['fit_rows'] for k in common),
        common_models_with_changed_calibration_rows=sum(new[k]['calibration_rows']!=old[k]['calibration_rows'] for k in common),
        eligibility_note='Native past-only guards unchanged; 80% availability over a larger input vector can change training membership'))
    old=pd.read_parquet(shared.ROOT/'inputs/rankings'/f'{year}.parquet',columns=['date'])
    dates=pd.DatetimeIndex(old.date.unique()).sort_values().normalize()
    source=Path(plan['models'][str(year+1)]['source_root']) if year<2026 else FEATURE_2026
    sp=read(source/'protocol.json');sf=read(source/'feature_profile.json')
    if (sp['universe']!=p['universe'] or sf['generator_options']!=profile['generator_options']
            or sf['feature_columns']!=columns):raise ValueError('Feature-only cache contract mismatch')
    with replay_market_registry(shared.restore_registry(shared.ROOT)),patch.object(requests.Session,'request',no_http):
        tick('READING_FULL_UNIVERSE_PAST_FEATURES')
        features,feature_hashes,_=cached_features(source,dates.min(),dates.max(),columns,
            lambda n,t:tick('READING_FULL_UNIVERSE_PAST_FEATURES',completed=n,total=t))
        features=features[features.date.isin(dates)].reset_index(drop=True)
        coverage=features.groupby('date').size().reindex(dates,fill_value=0)
        if (coverage<np.ceil(.9*len(p['universe']))).any():raise ValueError('Insufficient full-universe feature coverage')
        if features[columns].isna().all(axis=1).any():raise ValueError('Entirely missing feature row')
        scores=features[['date','symbol']].copy();scores['fold_start']=scores.date.map(lambda d:select_fold(d,folds))
        for name,g in scores.groupby('fold_start'):
            fold=folds[name]
            if fold['backend']=='catboost':
                from catboost import CatBoostClassifier
                model=CatBoostClassifier().load_model(fold['model_file']);names=model.feature_names_
            else:
                import lightgbm as lgb
                model=lgb.Booster(model_file=fold['model_file']);names=model.feature_name()
            if names!=columns:raise ValueError('Oracle fitted input order differs')
            scores.loc[g.index,'proba_extreme']=model_probabilities(model,fold['backend'],features.loc[g.index,columns])
            scores.loc[g.index,'model_sha256']=fold['model_sha256']
            available=max(pd.Timestamp(fold['metrics'][k]) for k in ('train_available_max','val_available_max'))
            scores.loc[g.index,'model_available_date']=available
        scores['feature_profile_sha256']=digest(root/'feature_profile.json')
        scores=scores.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True])
        pool=scores.groupby('date').head(179)
        names=set(pool.symbol);start=dates.min()-pd.Timedelta(days=650)
        calendar=nyse_sessions(start.date(),dates.max().date())
        records={(r['symbol'],r['year'],r['side']):r for r in manifest['models']}
        feature_groups=features.groupby('symbol',sort=False).indices
        result=[];bar_hashes={};sample_bars=[];processed=0
        tick('SCORING_LONG_SHORT',completed=0,total=len(names))
        for path in sorted((source/'chunks').glob('*/bars.parquet')):
            if digest(path)!=read(path.parent/'done.json')['files']['bars.parquet']:raise ValueError('Changed historical bars')
            bar_hashes[str(path)]=digest(path)
            bars=pd.read_parquet(path,filters=[('date','>=',start),('date','<=',dates.max())])
            bars=bars[bars.symbol.isin(names)]
            for symbol,b in bars.groupby('symbol'):
                f=oracle_panels(b,calendar,features.iloc[feature_groups[symbol]],columns)
                requested=pool.loc[pool.symbol.eq(symbol),['date','symbol']]
                f=requested.merge(f,on=['date','symbol'],how='inner',validate='one_to_one')
                for y,g in f.groupby(f.date.dt.year):
                    out=g[['date','symbol']].copy()
                    for side in ['long','short']:
                        out[side+'_probability']=np.nan;out[side+'_model_sha256']=None
                        r=records.get((symbol,int(y),side))
                        if r is None:continue
                        if not g.date.gt(pd.Timestamp(r['available'])).all():raise ValueError('Future per-symbol model')
                        w=joblib.load(root/r['file'])
                        if w['features']!=columns or w['model'].n_features_in_!=173:raise ValueError('Not a 173-input fitted model')
                        out[side+'_probability']=predict(w,g);out[side+'_model_sha256']=r['sha256']
                    result.append(out)
                if len(sample_bars)<3:sample_bars.append(b)
                processed+=1
                if processed%25==0:tick('SCORING_LONG_SHORT',completed=processed,total=len(names))
        cols=['date','symbol','long_probability','short_probability','long_model_sha256','short_model_sha256']
        probs=pd.concat(result,ignore_index=True) if result else pd.DataFrame(columns=cols)
        verified=rank(scores,probs,Settings(**manifest['contract']));verified['manifest_sha256']=mhash
        # Validate vectorized scoring against unmodified native one-row inference.
        sample_names=[str(b.symbol.iloc[0]) for b in sample_bars]
        sample_scores=pool[pool.symbol.isin(sample_names)].groupby('symbol').head(2)
        native=infer(None,root,sample_scores,oracle_features=features,bar_frame=pd.concat(sample_bars,ignore_index=True))
        check=native.merge(probs,on=['date','symbol'],suffixes=('_native','_vector'),validate='one_to_one')
        for side in ['long','short']:
            if not np.allclose(check[side+'_probability_native'].astype(float),check[side+'_probability_vector'].astype(float),
                    rtol=0,atol=1e-12,equal_nan=True):raise ValueError('Vector/native scoring differs')
        validate_saved(root,scores,verified)
        verified=attach_calibration_auc(verified,root)
        selected=select_per_symbol(verified,PerSymbolSelection(oracle_top_n=179,long_top_n=10,
            allow_long=True,allow_short=False,min_long_probability=.5,min_long_auc=.5))
        selected=selected[selected.selected].rename(columns={'date':'trade_date'}).copy()
        selected['rank']=selected['rank'].astype(int);selected['oracle_amplitude_rank']=selected.oracle_rank
        selected['oracle_batch_id']=item['batch_id'];selected['source_run_id']='features173-'+str(year);selected['entry_year']=year
        scores.to_parquet(folder/'oracle.parquet',index=False)
        verified.to_parquet(folder/'ranking.parquet',index=False)
        selected.to_parquet(folder/'signals.parquet',index=False)
        coverage.rename('covered').to_csv(folder/'coverage.csv')
        oldrank=shared.normalize_ranking_dates(pd.read_parquet(shared.ROOT/'inputs/rankings'/f'{year}.parquet'))
        same=scores[['date','symbol','proba_extreme']].merge(oldrank[['date','symbol','proba_extreme']],on=['date','symbol'],suffixes=('_new','_old'))
        delta=(same.proba_extreme_new-same.proba_extreme_old).abs()
        r=dict(year=year,batch_id=item['batch_id'],features=columns,feature_sources=feature_hashes,bar_sources=bar_hashes,
            feature_only_source=str(source),signals=len(selected),oracle_rows=len(scores),symbols=int(selected.symbol.nunique()),
            native_equivalence_rows=len(check),native_equivalence_tolerance=1e-12,
            oracle_comparison_rows=len(same),oracle_max_probability_difference=float(delta.max()),
            oracle_mean_probability_difference=float(delta.mean()),manifest_sha256=mhash,
            model_timing_oos=True,strict_data_vintage_pit=False,provider_calls=0,SQL_writes=0,orders=0,
            outputs={n:digest(folder/n) for n in ['oracle.parquet','ranking.parquet','signals.parquet','coverage.csv','models.csv','training-audit.json']})
        atomic_json(folder/'receipt.json',r);tick('COMPLETED',signals=len(selected))
        matched_control(year)
        return r


def assemble():
    plan=read(ROOT/'protocol.json');parts=[];control_parts=[];annual={};control_annual={}
    for year,item in plan['models'].items():
        folder=ROOT/'predictions'/year;r=read(folder/'receipt.json')
        for file,h in r['outputs'].items():
            if digest(folder/file)!=h:raise ValueError('Changed prediction archive')
        parts.append(pd.read_parquet(folder/'signals.parquet'))
        control=matched_control(int(year));control_parts.append(pd.read_parquet(folder/'control-signals.parquet'))
        original=item['original_annual_record'];model_root=Path(item['root'])
        contract=read(model_root/'protocol.json')['directional_contract']
        old_contract=read(Path(item['source_root'])/'protocol.json')['directional_contract']
        for target in [contract,old_contract]:
            if (target['horizon_sessions']!=10 or abs(target['stop_loss_pct']-.05)>1e-12
                    or abs(target['fee_per_leg']-.0008)>1e-12):
                raise ValueError('Annual directional labels differ from SL5/open11/8bp reference')
        annual[year]=dict(batch_id=item['batch_id'],run_id='features173-'+year,
            training_start=original['training_start'],training_end=original['training_end'],
            universe_size=len(plan['universe']),horizon=10,
            model_manifest_sha256=r['manifest_sha256'],model_protocol_sha256=digest(model_root/'protocol.json'),
            first_signal=original['first_signal'],last_signal=original['last_signal'],
            selection=dict(signals=r['signals'],symbols=r['symbols'],oracle_top_n=179,long_top_n=10,
                min_long_probability=.5,min_long_auc=.5))
        control_annual[year]={**annual[year],'directional_batch_id':item['source_batch'],
            'model_manifest_sha256':control['manifest_sha256'],'directional_feature_count':24,
            'selection':dict(signals=control['signals'],symbols=control['symbols'],oracle_top_n=179,long_top_n=10,
                min_long_probability=.5,min_long_auc=.5)}
    out=ROOT/'inputs';out.mkdir(exist_ok=True)
    f=pd.concat(parts,ignore_index=True).sort_values(['trade_date','rank','symbol']).reset_index(drop=True)
    f.to_parquet(out/'signals.parquet',index=False)
    control_frame=pd.concat(control_parts,ignore_index=True).sort_values(['trade_date','rank','symbol']).reset_index(drop=True)
    control_frame.to_parquet(out/'control-signals.parquet',index=False)
    sources={str(Path(__file__)):digest(Path(__file__)),str(out/'signals.parquet'):digest(out/'signals.parquet')}
    sources[str(out/'control-signals.parquet')]=digest(out/'control-signals.parquet')
    for year,item in plan['models'].items():
        file=Path(item['benchmark']);sources[str(file)]=digest(file)
        for name in ['receipt.json','control-receipt.json','training-audit.json']:
            file=ROOT/'predictions'/year/name;sources[str(file)]=digest(file)
    for base,pattern in [('backtesting','*.py'),('risk_management','*.py'),('common','winner*.py')]:
        sources.update({str(p):digest(p) for p in Path(base).glob(pattern)})
    from scripts.research.us_q051_vol20_regime_h5_20261115 import EXT
    for base in [shared.ROOT,EXT]:
        file=base/'inputs/manifest.json';sources[str(file)]=digest(file)
        for relative,h in read(file)['files'].items():
            if digest(base/'inputs'/relative)!=h:raise ValueError('Changed frozen market input: '+relative)
    # Distinguish a legitimately empty provider response from an unqueried cache.
    # Never screen signals using future prices or silently treat an unqueried
    # symbol/day as a genuine historical data gap.
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    from datetime import date
    with replay_market_registry(shared.restore_registry(shared.ROOT)):
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=[s.session_date for s in calendar.sessions(date(2021,1,1),date(2026,10,1)) if s.is_open]
    windows=shared.supplemental_windows([f,control_frame],sessions,set(),horizon=10)
    base_manifest=read(shared.ROOT/'inputs/manifest.json');fully=set(base_manifest['known_symbols'])
    extra={d:set() for d in sessions}
    for r in read(shared.ROOT/'inputs/extra-price-receipts.json'):extra[date.fromisoformat(r['day'])].update(r['symbols'])
    missing=[]
    for day in sessions:
        queried=set(read(EXT/'inputs/intraday'/f'{day}.receipt.json')['queried'])
        for symbol in sorted(windows[day]-fully-extra[day]-queried):missing.append(dict(date=str(day),symbol=symbol))
    daily_files=[shared.ROOT/'inputs/base/daily.parquet',shared.ROOT/'inputs/extra-daily.parquet',EXT/'inputs/daily.parquet']
    known_daily=set().union(*(set(pd.read_parquet(p,columns=['symbol']).symbol) for p in daily_files))
    unknown_daily=sorted((set(f.symbol)|set(control_frame.symbol))-known_daily)
    atomic_json(ROOT/'market-inventory-audit.json',dict(status='PASS' if not missing and not unknown_daily else 'NEEDS_SUPPLEMENT',
        unqueried_intraday=missing,unqueried_daily_symbols=unknown_daily,selection_was_not_changed=True))
    if missing or unknown_daily:raise ValueError('New selections require a read-only SQL market supplement; see market-inventory-audit.json')
    study=Path('artifacts/research/us_winner_q051_risk_budget/20261109-v1')
    for file in [study/'spy-benchmark.json',study/'charts/q051-temoin-volatilite20-regime-vs-spy-2021-2026.csv']:
        sources[str(file)]=digest(file)
    atomic_json(ROOT/'replay-protocol.json',dict(start=plan['start'],end=plan['end'],initial_equity=4000.,
        reference=read(shared.ROOT/'protocol.json')['reference'],annual_models=annual,control_annual_models=control_annual,sources=sources,
        cases=['SIMPLE','VOL20_REGIME','CONTROL_SIMPLE','CONTROL_VOL20_REGIME'],selection='Oracle TOP10% (179) -> TOP10 LONG; score>.50; calibration AUC>=.50; no refill',
        annual_reset=False,provider_calls=0,orders=0,production_changes=False))
    # Training journal only: separate from read-only simulations and prediction
    # archives. Lack of SQL access must not invalidate otherwise frozen replays.
    try:
        from scripts.research.us_q051_features173_registry_20261116 import register
        if not (ROOT/'registry.json').is_file():register()
    except Exception as exc:
        atomic_json(ROOT/'registry-pending.json',dict(status='PENDING',error_type=type(exc).__name__,
            action='Run scripts.research.us_q051_features173_registry_20261116 with access to the local training journal',
            production_activation=False))


def run_case(name):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.winner_portfolio_budget import replay_protections
    from backtesting.risk_overlay import RegimeFilterConfig
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from scripts.research.us_q051_vol20_regime_h5_20261115 import market_data,EXT
    from scripts.research.us_winner_vol20_extensions_20261109 import ExtendedPrices
    plan=read(ROOT/'replay-protocol.json');folder=ROOT/'cases'/name;folder.mkdir(parents=True,exist_ok=False)
    plan['replay_command']=[sys.executable,'-X','utf8','-m','scripts.research.us_q051_features173_replay_20261116',
        '--phase','case','--case',name]
    out=folder/'result';out.mkdir()
    try:
        for file,h in plan['sources'].items():
            if digest(Path(file))!=h:raise ValueError('Changed sealed replay source: '+file)
        cfg=shared.configuration(plan['reference'],shared.CASES['Q051_050'])
        from backtesting.per_symbol_selection import PerSymbolSelection
        ref=deepcopy(plan['reference'])
        ref['per_symbol_selection']=PerSymbolSelection(oracle_top_n=179,long_top_n=10,
            allow_long=True,allow_short=False,min_long_probability=.5,min_long_auc=.5).snapshot()
        ref['arguments'].update(top_n=179,per_symbol_top_long=10,per_symbol_min_long_probability=.5,
            per_symbol_min_long_auc=.5,drawdown_controller=False,start_date=plan['start'],end_date=plan['end'],output_dir=str(folder))
        ref['drawdown_controller'].update(enabled=False,active_components=[],liquidation_enabled=False)
        ref['risk']=asdict(cfg.risk_config);ref['settings_profile']='Q051_173_'+name
        ref['risk_overrides']=asdict(cfg.risk_config)
        ref['arguments']['risk_overrides_json']=json.dumps(asdict(cfg.risk_config),default=str)
        ref['signals_sha256']=digest(ROOT/'inputs/signals.parquet')
        ref['model_protocol_sha256']=plan['annual_models']['2025']['model_protocol_sha256']
        ref['arguments']['oracle_batch_id']=plan['annual_models']['2025']['batch_id']
        ref['selection']=plan['selection']
        protected=name.endswith('VOL20_REGIME');control=name.startswith('CONTROL_')
        ref['directional_feature_count']=24 if control else 173
        if control:
            ref['settings_profile']='Q051_24_RECALCULATED_'+name
            ref['signals_sha256']=digest(ROOT/'inputs/control-signals.parquet')
        ref['arguments'].update(portfolio_vol_target=.20 if protected else None,portfolio_vol_lookback=60,
            entry_regime_filter=protected,entry_regime_sma_window=200,entry_regime_bear_threshold=-.02)
        if protected:cfg.risk_overlay.regime_filter=RegimeFilterConfig(enabled=True,sma_window=200,bear_threshold=-.02)
        from scripts.research.us_q051_classic_top10_20261115 import meaningful
        old=(Path('artifacts/research/us_q051_selection_variants/20261115-v1/cases/TOP10_SCORE050') if protected
            else Path('artifacts/research/us_q051_classic_top10/20261115-v1/cases/TOP10'))
        if meaningful(json.loads(json.dumps(asdict(cfg),default=str)))!=meaningful(read(old/'result/configuration.json')['portfolio']):
            raise ValueError('Portfolio parameters differ from 24-input control')
        atomic_json(folder/'protocol.json',{**plan,'case':name,'reference':ref})
        atomic_json(out/'configuration.json',dict(profile=name,portfolio=asdict(cfg)))
        atomic_json(folder/'progress.json',dict(status='LOADING_MARKET_INPUTS'))
        pivots,sectors,actions=market_data();signals=pd.read_parquet(ROOT/'inputs'/('control-signals.parquet' if control else 'signals.parquet'))
        if control:
            plan['annual_models']=plan['control_annual_models']
            atomic_json(folder/'protocol.json',{**plan,'case':name,'reference':ref})
        budget,gate=replay_protections(pivots['close'],daily_entry=True,target=.20,regime=True) if protected else (None,None)
        with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(shared.ROOT)),patch.object(requests.Session,'request',no_http):
            def tick(done,total,day):atomic_json(folder/'progress.json',dict(status='REPLAYING',case=name,completed=done,total=total,last_date=str(day)))
            result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
                volume=pivots['volume'],signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),
                intraday_source=ExtendedPrices(EXT),winner_research_assumptions=True,winner_progress=tick,
                winner_corporate_actions=actions.to_dict('records'),winner_selection_source=gate,winner_entry_risk_policy=budget)
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
            if protected:
                pd.DataFrame(budget.receipts).to_csv(out/'portfolio-risk-decisions.csv',index=False)
                pd.DataFrame(gate.receipts).to_csv(out/'regime-decisions.csv',index=False)
            report=metrics(result,4000.);annual=[];opening=4000.
            for year in range(2021,2027):
                curve=result.equity_curve[result.equity_curve.index.year==year];t=result.closed_trades_df;m=result.intraday_equity_curve
                part=BacktestResult(equity_curve=curve,closed_trades_df=t[pd.to_datetime(t.exit_date,utc=True).dt.year.eq(year)],
                    intraday_equity_curve=m[pd.to_datetime(m.timestamp,utc=True).dt.year.eq(year)],
                    tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
                row=metrics(part,opening);row.update(year=year,model=plan['annual_models'][str(year)]['batch_id'])
                annual.append(row);opening=float(curve.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
            report.update(case=name,selected_signals=len(signals),annual_models=plan['annual_models'],annual_reset=False,
                provider_calls=0,SQL_writes=0,orders=0,strict_pit=False,model_timing_oos=True,
                finished_at_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(out/'report.json',report)
        atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
        from ihm.services.backtesting_import import import_continuous_winner
        record=import_continuous_winner(folder,run_id='20261116_q051_173_'+name.lower(),
            label='Q051 '+('24 variables, témoin recalculé' if control else '173 variables')+' — TOP10 — '+name+' — 2021–2026',result_subdir='result')
        atomic_json(folder/'ihm.json',dict(run_id=record['run_id']))
    except BaseException as exc:
        atomic_json(folder/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


def compare():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for name in ['CONTROL_SIMPLE','CONTROL_VOL20_REGIME']:
        if not (ROOT/'cases'/name/'result/report.json').is_file():run_case(name)
    reports={
        '24 — témoin':Path('artifacts/research/us_q051_classic_top10/20261115-v1/cases/TOP10'),
        '173 — témoin':ROOT/'cases/SIMPLE',
        '24 recalculé — témoin':ROOT/'cases/CONTROL_SIMPLE',
        '24 — vol20 + régime':Path('artifacts/research/us_q051_selection_variants/20261115-v1/cases/TOP10_SCORE050'),
        '173 — vol20 + régime':ROOT/'cases/VOL20_REGIME',
        '24 recalculé — vol20 + régime':ROOT/'cases/CONTROL_VOL20_REGIME'}
    rows=[];annual=[];curves=[];checks=[]
    cols=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','winners','losers',
        'average_winning_pnl','average_losing_pnl','average_winning_holding_days','average_losing_holding_days',
        'average_gross_capital','maximum_gross_capital','average_gross_equity_ratio','costs','margin_interest']
    fig,(ax,ddax)=plt.subplots(2,1,figsize=(13,9),sharex=True,gridspec_kw={'height_ratios':[2,1]})
    for label,folder in reports.items():
        r=read(folder/'result/report.json');e=pd.read_csv(folder/'result/equity-daily.csv',index_col=0,parse_dates=True).equity
        a=pd.read_csv(folder/'result/annual-summary.csv');a['variant']=label;annual.append(a)
        m=pd.read_parquet(folder/'result/equity-5m.parquet');t=pd.read_csv(folder/'result/trades.csv')
        v=pd.concat([pd.Series([4000.]),m.equity],ignore_index=True)
        dd=100*(v/v.cummax()-1).min()
        if not np.isclose(dd,r['max_drawdown_pct'],atol=1e-9):raise ValueError('DD reconstruction differs')
        if not np.isclose(4000*np.prod(1+a.return_pct/100),r['final_equity'],atol=1e-6):raise ValueError('Annual compounding differs')
        if not np.isclose(e.iloc[-1],r['final_equity'],atol=1e-7):raise ValueError('Final valuation differs')
        if len(t)!=r['closed_lot_trades'] or int(t.pnl.gt(0).sum())!=r['winners']:raise ValueError('Trade statistics differ')
        if not t.side.eq('buy').all():raise ValueError('Unexpected non-LONG trade')
        checks.append(dict(variant=label,trade_count=len(t),recomputed_dd_pct=float(dd),annual_compounding=True))
        rows.append(dict(variant=label,**{c:r.get(c) for c in cols}))
        e.loc[pd.Timestamp('2021-01-01')]=4000.;e=e.sort_index()
        ax.plot(e.index,e,label=label);ddax.plot(e.index,100*(e/e.cummax().clip(lower=4000)-1))
        curves.append(e.rename(label))
    study=Path('artifacts/research/us_winner_q051_risk_budget/20261109-v1')
    spy=pd.read_csv(study/'charts/q051-temoin-volatilite20-regime-vs-spy-2021-2026.csv',
        index_col=0,parse_dates=True)['SPY_hors_dividendes_frais_USD'].astype(float)
    if not np.isclose(spy.iloc[-1],read(study/'spy-benchmark.json')['final_equity'],atol=1e-6):raise ValueError('SPY archive differs')
    ax.plot(spy.index,spy,label='SPY — sans frais/dividendes',color='#e58b24',alpha=.7)
    ddax.plot(spy.index,100*(spy/spy.cummax().clip(lower=4000)-1),color='#e58b24',alpha=.7)
    curves.append(spy.rename('SPY'))
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    pd.concat(curves,axis=1).to_csv(ROOT/'capital-curves.csv')
    ax.set_title('Q051 TOP10 — 24 ou 173 entrées par modèle LONG/SHORT')
    ax.set_ylabel('Capital valorisé ($)');ax.grid(alpha=.2);ax.legend(fontsize=9)
    ddax.set_ylabel('DD aux clôtures (%)');ddax.grid(alpha=.2)
    fig.text(.06,.01,'2021–1 octobre 2026 · 4 000 $ · modèles annuels · SL5/open11 · frais et financement inclus.\nDD maximal du bilan mesuré en intraday. Univers actuel, prix révisés, couverture 5m partielle : exploratoire.',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,1));fig.savefig(ROOT/'capital-comparison.png',dpi=145);plt.close(fig)
    atomic_json(ROOT/'economic-validation.json',dict(status='PASS',checks=checks))
    train_audits={str(y):read(ROOT/'predictions'/str(y)/'training-audit.json') for y in range(2021,2027)}
    oracle_deltas={str(y):read(ROOT/'predictions'/str(y)/'receipt.json')['oracle_max_probability_difference'] for y in range(2021,2027)}
    fits={}
    for year,item in read(ROOT/'protocol.json')['models'].items():
        pairs=[]
        for file in sorted((Path(item['root'])/'folds').glob('*/done.json')):
            new=read(file);old=read(Path(item['source_root'])/'folds'/file.parent.name/'done.json')
            n=new['champion']['model_file'];o=old['champion']['model_file']
            pairs.append(dict(fold=file.parent.name,old_backend=old['champion']['backend'],new_backend=new['champion']['backend'],
                selected_weights_binary_identical=n==o and new['files'][n]==old['files'][o]))
        fits[year]=pairs
    atomic_json(ROOT/'comparison-method-audit.json',dict(training=train_audits,oracle_max_differences=oracle_deltas,
        oracle_fit_comparison=fits,
        targets_and_hyperparameters_unchanged=True,model_weights_refitted=True,selection_policy_unchanged=True,
        training_membership_may_differ_due_to_feature_availability=True))
    lines=['# Q051 TOP10 — résultats 24 contre 173 variables','',
        '2021-01-01–2026-10-01 ; 4 000 $ continus ; modèles annuels hors entraînement ; LONG uniquement.',
        'Oracle TOP10 % (179) → TOP10 LONG ; score >0,50 ; AUC de calibration ≥0,50 ; sans remplacement.',
        'SL5/open11 ; pas de confirmation, TP, trailing ou B4 ; plafond d’achat 1×, capacité margin 2×.',
        'Frais et financement inclus. Vol20 + régime : budget covariance 60 séances et filtre SPY/SMA200.', '',
        '| Profil | Capital final | Rendement | DD intraday max | Trades | Gagnants | Capital engagé moyen |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        lines.append(f"| {r['variant']} | {r['final_equity']:.2f} $ | {r['return_pct']:+.2f} % | {r['max_drawdown_pct']:.2f} % | {r['closed_lot_trades']} | {r['win_pct']:.2f} % | {r['average_gross_capital']:.2f} $ |")
    lines+=['','Courbes : `capital-comparison.png`. Détails : `comparison.csv` et `annual-comparison.csv`.',
        'Les références à 24 entrées sont les TOP10, pas le témoin TOP5 à +206,51 %.','',
        'Les témoins « 24 recalculé » utilisent exactement le même Oracle recalculé et les mêmes archives',
        'de prix que les branches à 173 entrées. Ils servent à isoler le changement de branche par titre.',
        'Les anciennes courbes à 24 entrées sont conservées comme comparaison historique distincte.','',
        'Les cibles et réglages des estimateurs sont conservés. Le nombre de colonnes change aussi les dates',
        'où 80 % des entrées sont disponibles : les échantillons et titres qualifiés peuvent donc différer.',
        'Les comptes exacts figurent dans `comparison-method-audit.json`. Écart maximal des nouvelles',
        f"probabilités Oracle contre les anciennes : {max(oracle_deltas.values()):.12g}.",'',
        'Limites : univers contemporain, cours ajustés/révisés, secteurs actuels et archives 5m partielles.',
        'Les protections OHLC de repli sont conservées et comptées. Ce test reste exploratoire ; il ne',
        'certifie pas une disponibilité historique parfaite, des exécutions réelles ou un rendement futur.',
        'Aucun changement des réglages ni du modèle de production.']
    report_text='\n'.join(lines)+'\n'
    (ROOT/'results.md').write_text(report_text,encoding='utf-8')
    note=Path('doc/ml/q051_features173_20261116.md');marker='<!-- RESULTS_173_20261116 -->'
    if marker not in note.read_text(encoding='utf-8'):
        text=note.read_text(encoding='utf-8').replace(
            "Campagne en cours le 16 novembre 2026. Aucun rendement nouveau n'est encore\nvalidé.",
            'Campagne terminée le 16 novembre 2026. Les résultats comparatifs validés figurent en fin de note.')
        note.write_text(text+'\n'+marker+'\n\n'+report_text,encoding='utf-8')
    experience=Path('doc/ml/experiences_done.md')
    if marker not in experience.read_text(encoding='utf-8'):
        with experience.open('a',encoding='utf-8') as stream:
            stream.write('\n'+marker+'\n\n'+report_text+'\nProtocole détaillé : `doc/ml/q051_features173_20261116.md`.\n')
    guide=Path('doc/Q051.md')
    if marker not in guide.read_text(encoding='utf-8'):
        with guide.open('a',encoding='utf-8') as stream:
            stream.write('\n'+marker+'\n\n## Bundles expérimentaux à 173 variables par titre\n\n'
                'Le nombre de variables dépend du batch, pas du profil du portefeuille. Les références '
                'historiques à 24 entrées restent conservées. Six nouveaux bundles annuels Oracle H10 + '
                'LONG/SHORT utilisent les mêmes 173 entrées ordonnées pour les trois branches. '
                'Ils ont été comparés en TOP10 sur 2021–2026, avec et sans volatilité 20 % + régime, '
                'et avec des témoins à 24 entrées recalculés sur le même Oracle. '
                'Les modèles de production ne sont pas remplacés automatiquement.\n\n'
                'Résultats, identifiants et limites : [note de comparaison](ml/q051_features173_20261116.md).\n')
    atomic_json(ROOT/'completion.json',dict(status='COMPLETED_EXPLORATORY',comparison=rows,
        finished_at_utc=datetime.now(timezone.utc).isoformat()))
    return rows


def all_phases():
    """Continue this specific authorized campaign, never launch a second training."""
    plan=read(ROOT/'protocol.json')
    def execute(args,log):
        with (ROOT/(log+'.stdout.log')).open('ab') as stdout,(ROOT/(log+'.stderr.log')).open('ab') as stderr:
            p=subprocess.Popen([sys.executable,'-X','utf8','-u','-m',
                'scripts.research.us_q051_features173_replay_20261116',*args],stdout=stdout,stderr=stderr,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            while p.poll() is None:time.sleep(5)
            if p.returncode:raise RuntimeError('Phase failed: '+log+'; inspect its logs')
    for year in plan['models']:
        state=ROOT/f'{year}-progress.json'
        while not state.is_file() or read(state).get('status')!='TRAINED':
            if state.is_file() and read(state).get('status')=='FAILED':raise RuntimeError('Training failed: '+year)
            atomic_json(ROOT/'continuation-progress.json',dict(status='WAITING_TRAINING',year=int(year)))
            time.sleep(10)
        atomic_json(ROOT/'continuation-progress.json',dict(status='PREDICTING',year=int(year)))
        execute(['--phase','predict','--year',year],year+'-predict')
    execute(['--phase','assemble'],'assemble')
    # Native portfolios own their independent capital and risk state.
    for name in ['SIMPLE','VOL20_REGIME']:
        atomic_json(ROOT/'continuation-progress.json',dict(status='REPLAYING',case=name))
        execute(['--phase','case','--case',name],'replay-'+name)
    execute(['--phase','compare'],'compare')
    atomic_json(ROOT/'continuation-progress.json',dict(status='COMPLETED_EXPLORATORY'))


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['predict','control','assemble','case','compare','all'],required=True)
    p.add_argument('--year',type=int);p.add_argument('--case',choices=['SIMPLE','VOL20_REGIME','CONTROL_SIMPLE','CONTROL_VOL20_REGIME']);a=p.parse_args()
    if a.phase=='predict':forecast(a.year)
    elif a.phase=='control':matched_control(a.year)
    elif a.phase=='assemble':assemble()
    elif a.phase=='case':run_case(a.case)
    elif a.phase=='compare':compare()
    else:all_phases()
