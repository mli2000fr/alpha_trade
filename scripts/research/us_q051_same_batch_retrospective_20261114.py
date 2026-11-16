"""Explicitly biased, same-batch Q051 replay. Research files ONLY, no serving SQL.

The user authorizes training overlap/future weights. Freeze the last Oracle
fold and the latest LONG head per symbol for the WHOLE period, instead of
pretending that unavailable annual models existed in 2021. Historical price
features and Q051 execution rules are unchanged. No thresholds are optimized.
"""
import argparse
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
import json
import logging
import math
from pathlib import Path
import time
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
import requests
from sqlalchemy import bindparam, text
from threadpoolctl import threadpool_limits

from backtesting.winner_campaign_replay import atomic_json, metrics, SqlIntradaySource
from modelFactory.oracle_path.train import digest

LOG = logging.getLogger(__name__)
MODE = 'RETROSPECTIVE_LOOKAHEAD_USER_AUTHORIZED'
WARNING = ('TEST RETROSPECTIF AVEC ANTICIPATION AUTORISEE : poids et AUC appris avec des données '
           'postérieures aux décisions. Ni hors échantillon, ni performance réalisable démontrée.')


def latest_heads(manifest):
    result = {}
    for row in manifest['models']:
        if row['side'] != 'long':
            continue
        if row['symbol'] not in result or row['year'] > result[row['symbol']]['year']:
            result[row['symbol']] = row
    return result


def rank_retrospective(frame, universe_size):
    """Same TOP10% -> TOP5 -> score/AUC gates; FUTURE availability retained openly."""
    out = frame.sort_values(['date', 'proba_extreme', 'symbol'], ascending=[True, False, True]).copy()
    out['oracle_rank'] = out.groupby('date').cumcount()+1
    out['long_rank'] = np.nan
    pool = out[out.oracle_rank.le(math.ceil(universe_size*.1)) & out.long_probability.notna()]
    pool = pool.sort_values(['date', 'long_probability', 'oracle_rank', 'symbol'], ascending=[True, False, True, True])
    out.loc[pool.index, 'long_rank'] = pool.groupby('date').cumcount()+1
    top = out.long_rank.le(5)
    out['selected'] = top & out.long_probability.gt(.5) & out.long_auc.ge(.5)
    out['rank'] = out.long_rank
    out['reason'] = np.where(out.selected, 'SELECTED_LONG_LOOKAHEAD', np.where(~top,
        'OUTSIDE_FIXED_TOP5', np.where(~out.long_probability.gt(.5), 'LONG_SCORE_NOT_ABOVE_THRESHOLD', 'LONG_AUC_BELOW_THRESHOLD')))
    out['evaluation_mode'] = MODE
    return out


def infer_year(engine, model_root, protocol, profile, fold, heads, start, end, folder, progress):
    from modelFactory.oracle_path.predict import build_inference_features
    from modelFactory.oracle_path.train import model_probabilities
    from modelFactory.oracle_path.directional import panels, INPUTS
    from modelFactory.oracle_path.named_prediction import predict_proba
    from modelFactory.oracle_path.labels import load_bars
    from modelFactory.data_loader import load_benchmark_bars
    from modelFactory.oracle.build_labels import nyse_sessions
    features = build_inference_features(engine, protocol['universe'], str(start), str(end), profile['generator_options'])
    if features.empty:
        raise ValueError('Aucune feature historique pour '+str(start))
    features['date'] = pd.to_datetime(features.date).dt.normalize()
    features = features.loc[features.date.between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    if features.duplicated(['date','symbol']).any():
        raise ValueError('Clés de features dupliquées')
    columns = profile['feature_columns']
    if fold['backend'] == 'lightgbm':
        import lightgbm as lgb
        model = lgb.Booster(model_file=fold['model_file'])
        actual = model.feature_name()
    else:
        from catboost import CatBoostClassifier
        model = CatBoostClassifier().load_model(fold['model_file'])
        actual = model.feature_names_
    if actual != columns:
        raise ValueError('Ordre des variables Oracle différent du contrat')
    scores = features[['date','symbol']].copy()
    scores['proba_extreme'] = model_probabilities(model,fold['backend'],
        features[columns].replace([np.inf,-np.inf],np.nan).astype(np.float32))
    del features
    first = pd.Timestamp(start)-pd.Timedelta(days=650)
    benchmark = load_benchmark_bars(engine,benchmark_symbol=protocol['training_config']['data']['benchmark_symbol'],
                                   start_date=str(first.date()),end_date=str(end))
    calendar = nyse_sessions(first.date(),end)
    names = sorted(set(scores.symbol)); parts=[]
    for offset in range(0,len(names),25):
        bars = load_bars(engine,names[offset:offset+25],str(first.date()),str(end))
        if not bars.empty:
            for symbol, group in bars.groupby('symbol'):
                record = heads.get(symbol)
                if record is None:
                    continue
                panel = panels(group,benchmark,calendar)
                panel = panel[panel.date.between(pd.Timestamp(start),pd.Timestamp(end))]
                if panel.empty:
                    continue
                weights = joblib.load(model_root/record['file'])
                x = panel[INPUTS].replace([np.inf,-np.inf],np.nan).clip(weights['lo'],weights['hi'],axis=1)
                raw = np.clip(predict_proba(weights['model'],x,INPUTS)[:,1],1e-6,1-1e-6)
                probability = weights['calibrator'].predict_proba(np.log(raw/(1-raw)).reshape(-1,1))[:,1]
                auc = (record.get('metrics') or {}).get('calibration',{}).get('auc')
                # The original manifest schema is checked by load_manifest;
                # use its calibration metric, never any test-year outcome.
                if auc is None:
                    auc = record.get('calibration_metrics',{}).get('auc')
                part = panel[['date','symbol']].copy()
                part['long_probability'] = probability
                part['long_auc'] = auc
                part['long_model_year'] = record['year']
                part['long_model_available_date'] = record['available']
                part['long_model_sha256'] = record['sha256']
                parts.append(part)
        progress('DIRECTIONAL_INFERENCE',min(offset+25,len(names)),len(names),str(end))
    if not parts:
        raise ValueError('Aucune prédiction LONG historique calculable')
    probabilities = pd.concat(parts,ignore_index=True)
    result = scores.merge(probabilities,on=['date','symbol'],how='left',validate='one_to_one')
    result['oracle_fold'] = fold['metrics']['fold_start']
    result['oracle_model_sha256'] = fold['model_sha256']
    result['oracle_model_available_date'] = max(fold['metrics'][k] for k in ('train_available_max','val_available_max'))
    result['evaluation_mode'] = MODE
    result.to_parquet(folder,index=False)
    return result


def replay_config(start,end):
    from common.q051_paper import reference
    from scripts.research.us_winner_ui_grid_20261107 import configuration
    p=reference()
    frozen=dict(winner_policy=p['winner'],risk=p['risk'],leverage=p['leverage'],
                arguments=dict(margin_interest_annual=.065))
    cfg=configuration(frozen,dict(policy={},risk={},daily=True,controller=False))
    cfg.start_date=start;cfg.end_date=end;cfg.cost_round_trip_bps=16.
    from backtesting.risk_overlay import RegimeFilterConfig
    cfg.risk_overlay.regime_filter=RegimeFilterConfig(enabled=True,sma_window=200,bear_threshold=-.02)
    return cfg


def run(args):
    if not args.allow_in_sample_lookahead:
        raise ValueError('Autorisation explicite --allow-in-sample-lookahead requise')
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_data import daily_bars
    from backtesting.winner_portfolio_budget import PortfolioRiskPolicy,RegimeEntryGate
    from modelFactory.oracle_path.predict import load_contract,prediction_coverage_ratio
    from modelFactory.oracle_path.directional import load_manifest
    from modelFactory.oracle.build_labels import nyse_sessions
    from common.market_calendar import get_market_calendar
    from common.q051_paper import reference
    from database.connection import get_sqlalchemy_engine
    root=Path(args.output_dir).resolve();root.mkdir(parents=True,exist_ok=True)
    out=root/'result';out.mkdir(exist_ok=True)
    started=time.monotonic()
    def progress(phase,completed=0,total=0,last=None):
        atomic_json(root/'progress.json',dict(status='RUNNING',phase=phase,completed=completed,total=total,
            last_date=last,evaluation_mode=MODE,elapsed_seconds=time.monotonic()-started))
        if phase!='DIRECTIONAL_INFERENCE' or completed%250==0 or completed==total:
            LOG.info('%s %s/%s %s',phase,completed,total,last)
    def no_http(*a,**kw):raise ValueError('Aucun téléchargement ni appel broker autorisé dans ce test')
    try:
        with ReadOnlyReplay(root).install(),patch.object(requests.Session,'request',no_http),threadpool_limits(limits=1):
            model_root,protocol,profile,folds=load_contract(args.artifacts_dir,args.batch_id)
            if protocol['horizon']!=10:raise ValueError('Q051 de référence exige H10')
            manifest,_=load_manifest(model_root);heads=latest_heads(manifest)
            fold=folds[max(folds,key=pd.Timestamp)]
            cfg=replay_config(args.start,args.end)
            ref=reference();ref['winner_policy']=ref['winner']
            ref['arguments']=dict(cost_per_leg_bps=8.,margin_interest_annual=.065)
            base=dict(evaluation_mode=MODE,lookahead_authorized=True,independent_holdout=False,
                warning=WARNING,batch_id=args.batch_id,start=str(args.start),end=str(args.end),initial_equity=4000.,
                reference=ref,annual_models={str(y):dict(batch_id=args.batch_id,same_fixed_weights=True)
                    for y in range(args.start.year,args.end.year+1)},annual_reset=False,
                oracle_model=fold,heads={s:{k:r.get(k) for k in ['year','available','file','sha256']}
                    for s,r in heads.items()},profile_sha256=ref['sha256'],
                model_protocol_sha256=digest(model_root/'protocol.json'),manifest_sha256=digest(model_root/'directional/manifest.json'),
                canonical_prediction_writes=0,broker_calls=0,source_script_sha256=digest(Path(__file__)),
                source_price_preference='canonical daily source preference, no fabricated bars',
                replay_command=['python','-m','scripts.research.us_q051_same_batch_retrospective_20261114',
                    '--batch-id',args.batch_id,'--start',str(args.start),'--end',str(args.end),
                    '--output-dir',str(root),'--allow-in-sample-lookahead'])
            frozen=root/'protocol.json'
            if frozen.exists() and json.loads(frozen.read_text(encoding='utf-8'))!=base:
                raise ValueError('Reprise refusée : contrat de recherche modifié')
            if not frozen.exists():atomic_json(frozen,base)
            atomic_json(out/'configuration.json',dict(portfolio=asdict(cfg),evaluation_mode=MODE))
            sessions=[s.session_date for s in get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions(
                args.start-timedelta(days=14),args.end) if s.is_open]
            actual=[d for d in sessions if d>=args.start];prior=max(d for d in sessions if d<actual[0])
            signal_days=[prior]+actual[:-1]
            engine=get_sqlalchemy_engine(db_name='alpha_trade');scores=[]
            for year in range(args.start.year,args.end.year+1):
                days=[d for d in signal_days if d.year==year or (year==args.start.year and d<args.start)]
                if not days:continue
                output=root/f'scores-{year}.parquet';seal=root/f'scores-{year}.seal.json'
                progress('ORACLE_INFERENCE',0,len(days),str(days[-1]))
                if output.exists() and seal.exists():
                    if json.loads(seal.read_text())['sha256']!=digest(output):raise ValueError('Scores locaux modifiés')
                    frame=pd.read_parquet(output)
                else:
                    frame=infer_year(engine,model_root,protocol,profile,fold,heads,days[0],days[-1],output,progress)
                    atomic_json(seal,dict(sha256=digest(output),evaluation_mode=MODE))
                scores.append(frame)
            all_scores=pd.concat(scores,ignore_index=True)
            ranked=rank_retrospective(all_scores,len(protocol['universe']))
            ranked.to_parquet(root/'ranking.parquet',index=False)
            selected=ranked[ranked.selected].copy().rename(columns={'date':'trade_date'})
            selected['rank']=selected['rank'].astype(int)
            selected.to_csv(out/'signals.csv',index=False)
            if selected.empty:raise ValueError('Sélection LONG vide : vérifier métriques de calibration')
            minimum=math.ceil(len(protocol['universe'])*prediction_coverage_ratio())
            counts=all_scores.groupby('date').symbol.nunique().reindex(pd.DatetimeIndex(signal_days),fill_value=0)
            coverage=pd.DataFrame(dict(date=counts.index,observed=counts.to_numpy(),model_universe=len(protocol['universe']),
                minimum=minimum,qualified=counts.to_numpy()>=minimum))
            coverage.to_csv(out/'oracle-coverage.csv',index=False)
            progress('LOADING_PRICES',0,len(actual))
            names=sorted(set(selected.symbol)|{'SPY'})
            with engine.connect() as conn,conn.begin():
                conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
                daily=daily_bars(conn,names,prior-timedelta(days=650),args.end)
                daily.to_parquet(root/'daily.parquet',index=False)
                pivots={k:daily.pivot(index='date',columns='symbol',values=k).astype(float) for k in ['open','close','high','low','volume']}
                sectors=pd.read_sql(text('SELECT symbol,sector FROM stock_metadata WHERE symbol IN :names').bindparams(
                    bindparam('names',expanding=True)),conn,params=dict(names=names))
                actions=pd.read_sql(text('SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency FROM corporate_actions_events '
                    'WHERE symbol IN :names AND ex_date BETWEEN :start AND :end').bindparams(bindparam('names',expanding=True)),
                    conn,params=dict(names=names,start=args.start,end=args.end))
                gate=RegimeEntryGate(pivots['close']['SPY'],cfg.risk_overlay.regime_filter)
                budget=PortfolioRiskPolicy(pivots['close'],target=.2,lookback=60)
                source=SqlIntradaySource(conn,discard_unqualified=True,allow_daily_fallback=True)
                def tick(done,total,day):progress('REPLAYING',done,total,str(day))
                result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],
                    low=pivots['low'],volume=pivots['volume'],signals_df=selected,sector_map=sectors.set_index('symbol').sector.to_dict(),
                    intraday_source=source,winner_research_assumptions=True,winner_progress=tick,
                    winner_corporate_actions=actions.to_dict('records'),winner_selection_source=gate,winner_entry_risk_policy=budget)
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False)
            result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
            pd.DataFrame(gate.receipts).to_csv(out/'regime-decisions.csv',index=False)
            pd.DataFrame(budget.receipts).to_csv(out/'portfolio-risk-decisions.csv',index=False)
            report=metrics(result,4000.);annual=[];opening=4000.
            for year in sorted(result.equity_curve.index.year.unique()):
                curve=result.equity_curve[result.equity_curve.index.year==year]
                trades=result.closed_trades_df
                closed=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(year)] if len(trades) else trades
                marks=result.intraday_equity_curve
                part=BacktestResult(equity_curve=curve,closed_trades_df=closed,
                    intraday_equity_curve=marks[pd.to_datetime(marks.timestamp,utc=True).dt.year.eq(year)],
                    tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
                annual.append(dict(metrics(part,opening),year=int(year),model=args.batch_id,evaluation_mode=MODE))
                opening=float(curve.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
            if not coverage.qualified.all():report['status']='INCOMPLETE_COVERAGE'
            report.update(evaluation_mode=MODE,lookahead_authorized=True,independent_holdout=False,strict_pit=False,
                warning=WARNING,limitations=[WARNING,'Couverture Oracle historique incomplète signalée, aucun score manquant inventé.',
                    'Protections 5m quand qualifiées, repli OHLC daily conservateur sinon ; frais8pb/opération ; secteurs actuels.',
                    'Même poids Oracle et même tête LONG par titre sur toutes les années, sans réentraînement ni optimisation.',
                    'Capital final valorisé, positions ouvertes non liquidées artificiellement.'],
                oracle_coverage_insufficient_dates=int((~coverage.qualified).sum()),oracle_coverage_minimum=minimum,
                selected_signals=len(selected),selected_symbols=int(selected.symbol.nunique()),initial_equity=4000.,
                annual_models=base['annual_models'],annual_reset=False,broker_calls=0,provider_calls=0,SQL_writes=0,
                finished_at_utc=datetime.now(UTC).isoformat(),elapsed_seconds=time.monotonic()-started)
            atomic_json(out/'report.json',report)
            atomic_json(root/'progress.json',dict(status='COMPLETED_EXPLORATORY',evaluation_mode=MODE))
            engine.dispose()
        from ihm.services.backtesting_import import import_continuous_winner
        record=import_continuous_winner(root,run_id=args.history_id,
            label='Q051 vol20 + régime — même batch c59bed — AVEC ANTICIPATION — 2021–2026',result_subdir='result')
        atomic_json(root/'ihm.json',dict(run_id=record['run_id']))
        print(json.dumps(dict(run_id=record['run_id'],report=report),default=str),flush=True)
    except BaseException as exc:
        atomic_json(root/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc),evaluation_mode=MODE))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-id',required=True)
    parser.add_argument('--artifacts-dir',default='artifacts/models')
    parser.add_argument('--start',type=date.fromisoformat,default=date(2021,1,1))
    parser.add_argument('--end',type=date.fromisoformat,default=date(2026,11,13))
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--history-id',default='20261114_q051_c59bed_retrospective')
    parser.add_argument('--allow-in-sample-lookahead',action='store_true')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    run(parser.parse_args())
