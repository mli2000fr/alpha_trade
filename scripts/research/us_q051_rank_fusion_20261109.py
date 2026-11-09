"""Prespecified 50/50 relative rank fusion and matched no-threshold controls.

Only verified archived scores, unchanged Q051 native risk/Winner, no new model,
provider, SQL, order or production setting. Existing experiments are immutable.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from dataclasses import asdict
from datetime import date,datetime,timezone
import json
from multiprocessing import get_context
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from scripts.research import us_q051_per_sector_20261109 as sector_exp
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_winner_q051_risk_budget_20261109 import daily_metrics

BASE=sector_exp.BASE
SECTOR=Path('artifacts/research/us_q051_per_sector/20261109-v4')
ROOT=Path('artifacts/research/us_q051_rank_fusion/20261109-v1')
YEARS=tuple(range(2021,2026))
CASES={
    'Q051_FUSION50':dict(selection='FUSION50',protected=False),
    'VOL20_FUSION50':dict(selection='FUSION50',protected=True),
    'Q051_RELATIVE_SYMBOL':dict(selection='RELATIVE_SYMBOL',protected=False),
    'VOL20_RELATIVE_SYMBOL':dict(selection='RELATIVE_SYMBOL',protected=True),
}
LABELS={
    'Q051_FUSION50':'Q051 — TOP5 fusion rangs 50/50',
    'VOL20_FUSION50':'Volatilité 20 % + régime — TOP5 fusion rangs 50/50',
    'Q051_RELATIVE_SYMBOL':'Q051 — TOP5 per-symbol relatif, mêmes candidats, sans seuils',
    'VOL20_RELATIVE_SYMBOL':'Volatilité 20 % + régime — TOP5 per-symbol relatif, sans seuils',
}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def fuse(frame,top_n=5):
    """Rank both finite scores in the same fixed cohort, before any outcome."""
    f=frame.copy()
    if f.duplicated(['date','symbol']).any():raise ValueError('Duplicate fusion candidate')
    for col in ['symbol_probability','sector_probability']:
        values=pd.to_numeric(f[col],errors='coerce')
        if (f[col].notna()&~values.between(0,1)).any():raise ValueError('Invalid model probability')
        f[col]=values
    f['eligible']=f[['symbol_probability','sector_probability']].notna().all(axis=1)
    eligible=f[f.eligible].copy()
    for name in ['symbol','sector']:
        eligible[name+'_percentile']=eligible.groupby('date')[name+'_probability'].transform(
            lambda s:(s.rank(method='average')-.5)/len(s))
    eligible['fusion_score']=.5*eligible.symbol_percentile+.5*eligible.sector_percentile
    for col,out in [('fusion_score','fusion_rank'),('symbol_probability','relative_symbol_rank')]:
        order=eligible.sort_values(['date',col,'oracle_rank','symbol'],ascending=[True,False,True,True]).copy()
        order[out]=order.groupby('date').cumcount()+1
        eligible=eligible.merge(order[['date','symbol',out]],on=['date','symbol'],validate='one_to_one')
    eligible['selected_fusion']=eligible.fusion_rank.le(top_n)
    eligible['selected_relative_symbol']=eligible.relative_symbol_rank.le(top_n)
    cols=['date','symbol','symbol_percentile','sector_percentile','fusion_score','fusion_rank',
        'relative_symbol_rank','selected_fusion','selected_relative_symbol']
    out=f.merge(eligible[cols],on=['date','symbol'],how='left',validate='one_to_one')
    for col in ['selected_fusion','selected_relative_symbol']:out[col]=out[col].fillna(False).astype(bool)
    return out


def validate_probabilities(frame,records,*,sector=False):
    """Bind every present probability to its causal, matching archived weights."""
    label='sector' if sector else 'symbol'
    for (key,year),g in frame[frame.long_probability.notna()].groupby(
            ['sector' if sector else 'symbol',frame.loc[frame.long_probability.notna(),'date'].dt.year]):
        record=records.get((key,int(year)))
        if record is None or not g.long_model_sha256.eq(record['sha256']).all():
            raise ValueError('Missing/mismatched '+label+' weights')
        if not g.date.gt(pd.Timestamp(record['available'])).all():raise ValueError('Future '+label+' model')
        weight=Path(record['file'])
        if digest(weight)!=record['sha256']:raise ValueError('Changed '+label+' weights')


def prepare(root):
    from service.options_directional.runner import validate_oracle_lineage
    root.mkdir(parents=True,exist_ok=False);inputs=root/'inputs';inputs.mkdir()
    atomic_json(root/'progress.json',dict(status='VERIFYING_SCORES_AND_SELECTING',completed=0,total=5))
    original=read(BASE/'protocol.json');sector_request=read(SECTOR/'request.json')
    manifest=read(BASE/'inputs/manifest.json');frozen_files={k.replace('\\','/'):v for k,v in manifest['files'].items()}
    sources={str(Path(__file__)):digest(Path(__file__))};parts=[];counts=[];annual_models={}
    for year in YEARS:
        spec=sector_request['annual_models'][str(year)];batch=original['annual_models'][str(year)]['batch_id']
        if batch!=spec['batch_id']:raise ValueError('Annual Oracle differs')
        annual_models[str(year)]=original['annual_models'][str(year)]
        file=BASE/'inputs/rankings'/f'{year}.parquet'
        if digest(file)!=frozen_files[f'rankings/{year}.parquet']:raise ValueError('Changed ranking archive')
        raw=pd.read_parquet(file);raw['date']=pd.to_datetime(raw.date)
        root_model=Path(spec['root']);own_manifest=read(root_model/'directional/manifest.json')
        symbol_records={}
        for row in own_manifest['models']:
            if row['side']=='long':symbol_records[row['symbol'],row['year']]={**row,'file':str(root_model/row['file'])}
        for day,g in raw.groupby('date'):
            if g.symbol.duplicated().any() or len(g)<int(np.ceil(.9*1790)):raise ValueError('Bad Oracle coverage/duplicates')
            validate_oracle_lineage(g.to_dict('records'),day.date(),spec['features_sha256'],spec['folds'],horizon=10)
        raw=raw.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True]).copy()
        raw['oracle_rank']=raw.groupby('date').cumcount()+1
        pool=raw[raw.oracle_rank.le(179)].copy()
        validate_probabilities(pool,symbol_records)
        sector_folder=SECTOR/'years'/str(year)
        receipt=read(sector_folder/'prediction-receipt.json')
        if digest(sector_folder/'signals.parquet')!=receipt['signals_sha256']:raise ValueError('Sector prediction receipt changed')
        sector_manifest=read(sector_folder/'manifest.json')
        if digest(sector_folder/'manifest.json')!=receipt['sector_manifest_sha256']:raise ValueError('Sector manifest changed')
        records={(r['sector'],r['year']):r for r in sector_manifest['models']}
        probabilities=pd.read_parquet(sector_folder/'probabilities.parquet')
        validate_probabilities(probabilities,records,sector=True)
        left=pool[['date','symbol','proba_extreme','oracle_rank','long_probability','long_model_sha256']].rename(
            columns={'long_probability':'symbol_probability','long_model_sha256':'symbol_model_sha256'})
        right=probabilities[['date','symbol','long_probability','long_model_sha256','sector']].rename(
            columns={'long_probability':'sector_probability','long_model_sha256':'sector_model_sha256'})
        joined=left.merge(right,on=['date','symbol'],how='left',validate='one_to_one')
        outcome=fuse(joined);outcome['entry_year']=year;outcome['oracle_batch_id']=batch;parts.append(outcome)
        daily=outcome.groupby('date').agg(candidates=('symbol','size'),eligible=('eligible','sum'),
            fusion_selected=('selected_fusion','sum'),relative_selected=('selected_relative_symbol','sum')).reset_index()
        if not daily.fusion_selected.eq(5).all() or not daily.relative_selected.eq(5).all():
            raise ValueError('Actual data cannot produce fixed TOP5; do not fabricate missing scores')
        daily['year']=year;counts.append(daily)
        for path in [file,root_model/'directional/manifest.json',sector_folder/'prediction-receipt.json',
                     sector_folder/'manifest.json',sector_folder/'probabilities.parquet']:
            sources[str(path)]=digest(path)
        atomic_json(root/'progress.json',dict(status='VERIFYING_SCORES_AND_SELECTING',completed=year-2020,total=5,year=year))
    selection=pd.concat(parts,ignore_index=True);selection.to_parquet(inputs/'ranking.parquet',index=False)
    pd.concat(counts,ignore_index=True).to_csv(inputs/'coverage-daily.csv',index=False)
    for key,flag,rank in [('FUSION50','selected_fusion','fusion_rank'),('RELATIVE_SYMBOL','selected_relative_symbol','relative_symbol_rank')]:
        selected=selection[selection[flag]].rename(columns={'date':'trade_date'}).copy()
        selected['rank']=selected[rank].astype(int);selected['oracle_amplitude_rank']=selected.oracle_rank
        selected['side']='long';selected['selected']=True;selected['selection_method']=key
        selected.to_parquet(inputs/f'signals-{key}.parquet',index=False)
    for name in ['backtesting/simulator.py','backtesting/winner_intraday.py','backtesting/winner_daily_entry.py',
        'backtesting/winner_portfolio_budget.py','backtesting/winner_campaign_replay.py',
        'scripts/research/us_q051_per_sector_20261109.py','scripts/research/us_winner_vol20_extensions_20261109.py',
        'scripts/research/us_winner_continuous_q051_q088_20261108.py','scripts/research/us_winner_ui_grid_20261107.py']:
        sources[name]=digest(Path(name))
    for name in ['request.json','validation.json']:sources[str(SECTOR/name)]=digest(SECTOR/name)
    protocol=dict(start='2021-01-01',end='2025-12-31',initial_equity=4000.,annual_reset=False,annual_models=annual_models,
        cases=CASES,features='Existing probabilities only; no fitting, labels or future returns in selection',
        formula='0.5*((rank_symbol-0.5)/joint_n) + 0.5*((rank_sector-0.5)/joint_n), rank ascending by probability, average ties',
        tie_break='Oracle amplitude rank ascending, then symbol ascending',oracle_pool=179,final_top_n=5,
        eligibility='Both finite causal model scores on the SAME fixed TOP179 Oracle pool; missing values excluded, no refill outside pool',
        absolute_probability_gate=None,calibration_auc_gate=None,
        probability_warning='Relative percentile score is not a calibrated chance of profit; low absolute probabilities can be selected',
        matched_control='Per-symbol TOP5 in identical joint cohort, same absence of probability/AUC gates',
        existing_controls='Original filtered per-symbol, per-sector and no-directional-filter results retained; different gate policies acknowledged',
        risk='Exact Q051, full initial position, daily J+1, SL5, no TP/trailing/reinforcement, open11, entry cap 1x, margin capacity 2x, B4 off',
        protected='Same Q051 plus 20% annual portfolio covariance budget on 60 prior sessions, SPY J >98% SMA200, new entries only',
        costs='8bps/leg, 6.5% annual margin financing',sources=sources,
        retrospective=True,independent_holdout=False,production_changes=False,SQL_calls=0,model_training=0,provider_calls=0,orders=0,
        created_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(root/'request.json',protocol)
    atomic_json(inputs/'manifest.json',dict(files={p.name:digest(p) for p in inputs.iterdir() if p.is_file()}))
    atomic_json(root/'progress.json',dict(status='INPUTS_FROZEN',sessions=len(pd.concat(counts)),signals_per_case=5*len(pd.concat(counts)),cases=list(CASES)))
    return protocol


def replay_case(root,name):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.winner_campaign_replay import metrics
    from backtesting.winner_portfolio_budget import replay_protections
    from common.config_loader import replay_market_registry
    from scripts.research.us_winner_vol20_extensions_20261109 import ExtendedPrices
    root=Path(root);plan=read(root/'request.json');case=CASES[name]
    for file,sha in plan['sources'].items():
        if digest(Path(file))!=sha:raise ValueError('Source changed since selection: '+file)
    for file,sha in read(root/'inputs/manifest.json')['files'].items():
        if digest(root/'inputs'/file)!=sha:raise ValueError('Frozen selection changed')
    folder=root/'cases'/name;out=folder/'result';out.mkdir(parents=True,exist_ok=False)
    shared=sector_exp.shared;source_plan=read(BASE/'protocol.json');profile=deepcopy(shared.CASES['Q051_050'])
    cfg=shared.configuration(source_plan['reference'],profile);cfg.end_date=date(2025,12,31)
    pivots,sectors,actions=shared.market_data(BASE);extra=pd.read_parquet(sector_exp.EXT/'inputs/daily.parquet')
    for field in pivots:pivots[field]=pd.concat([pivots[field],extra.pivot(index='date',columns='symbol',values=field)],axis=1).sort_index()
    sectors=pd.concat([sectors,pd.read_parquet(sector_exp.EXT/'inputs/sectors.parquet')],ignore_index=True)
    actions=pd.concat([actions,pd.read_parquet(sector_exp.EXT/'inputs/actions.parquet')],ignore_index=True)
    signals=pd.read_parquet(root/'inputs'/f'signals-{case["selection"]}.parquet')
    policy,gate=replay_protections(pivots['close'],daily_entry=True,target=.2 if case['protected'] else None,regime=case['protected'])
    reference=deepcopy(source_plan['reference']);reference['risk']=asdict(cfg.risk_config)
    reference['arguments'].update(top_n=179,per_symbol_long=False,per_sector_long=False,per_symbol_min_long_probability=None,
        per_symbol_min_long_auc=None,drawdown_controller=False,portfolio_vol_target=.2 if case['protected'] else None,entry_regime_filter=case['protected'])
    reference['per_symbol_selection']=None;reference['rank_fusion_selection']=dict(method=case['selection'],top_n=5,weight_symbol=.5,weight_sector=.5,probability_gate=None,auc_gate=None)
    protocol=dict(start=plan['start'],end=plan['end'],initial_equity=4000.,annual_reset=False,annual_models=plan['annual_models'],
        reference=reference,profile=name,selection_protocol_sha256=digest(root/'request.json'),
        replay_command=[sys.executable,'-m','scripts.research.us_q051_rank_fusion_20261109','--phase','run','--output-dir',str(root)])
    atomic_json(folder/'protocol.json',protocol);atomic_json(out/'configuration.json',dict(profile=name,portfolio=asdict(cfg)))
    def no_http(*args,**kwargs):raise ValueError('No provider requests in fused replay')
    with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(BASE)),patch.object(requests.Session,'request',no_http):
        def progress(done,total,day):
            state=dict(status='RUNNING',completed=done,total=total,last_date=str(day));atomic_json(folder/'progress.json',state);atomic_json(out/'progress.json',state)
        result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],volume=pivots['volume'],
            signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),intraday_source=ExtendedPrices(sector_exp.EXT),
            winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=actions.to_dict('records'),
            winner_selection_source=gate,winner_entry_risk_policy=policy)
        result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv');result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
        result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
        result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
        pd.DataFrame(policy.receipts if policy else []).to_csv(out/'portfolio-risk-decisions.csv',index=False)
        pd.DataFrame(gate.receipts if gate else []).to_csv(out/'regime-decisions.csv',index=False)
        report=metrics(result,4000.);report.update(daily_metrics(result.equity_curve));annual=[];opening=4000.
        for year in YEARS:
            curve=result.equity_curve[result.equity_curve.index.year==year];trades=result.closed_trades_df;marks=result.intraday_equity_curve
            closed=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(year)] if len(trades) else trades
            part=BacktestResult(equity_curve=curve,closed_trades_df=closed,
                intraday_equity_curve=marks[pd.to_datetime(marks.timestamp,utc=True).dt.year.eq(year)],
                tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
            row=metrics(part,opening);row.update(year=year,model=plan['annual_models'][str(year)]['batch_id']);annual.append(row);opening=float(curve.iloc[-1])
        pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
        report.update(profile=name,annual_models=plan['annual_models'],annual_reset=False,selected_signals=len(signals),
            finished_at_utc=datetime.now(timezone.utc).isoformat(),provider_calls=0,SQL_writes=0,orders=0)
        atomic_json(out/'report.json',report);atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
    from ihm.services.backtesting_import import import_continuous_winner
    record=import_continuous_winner(folder,run_id=f'20261109_{name.lower()}_fusion_v1',label='Continu 2021–2025 — '+LABELS[name],result_subdir='result')
    return dict(profile=name,folder=str(folder),ihm_run_id=record['run_id'])


def consolidate(root,results):
    existing=pd.read_csv(SECTOR/'comparison.csv');annual=pd.read_csv(SECTOR/'annual-comparison.csv')
    reports=[];parts=[annual];columns=list(existing.columns)
    for result in results:
        folder=Path(result['folder'])/'result';report=read(folder/'report.json');reports.append({k:report.get(k) for k in columns})
        frame=pd.read_csv(folder/'annual-summary.csv');frame['profile']=result['profile'];parts.append(frame)
    pd.concat([existing,pd.DataFrame(reports)],ignore_index=True).to_csv(root/'comparison.csv',index=False)
    pd.concat(parts,ignore_index=True).to_csv(root/'annual-comparison.csv',index=False)
    plot(root,results)
    report=dict(status='COMPLETED_EXPLORATORY',results=reports,imports=results,failures=[],
        comparison='Original six references plus four fixed TOP5 relative trials; causal scores only, changed threshold policy explicit',
        chart=str(root/'charts/capital-comparison.png'),provider_calls=0,SQL_writes=0,orders=0,training=False,production_changes=False)
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',report)


def plot(root,results):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    charts=root/'charts';charts.mkdir()
    fig,axes=plt.subplots(2,1,figsize=(15,11),sharex=True)
    frames={}
    for protected,ax in zip([False,True],axes):
        baseline=(Path('artifacts/research/us_winner_q051_risk_budget/20261109-v1/REGIME_VOL20/result')
            if protected else BASE/'cases/Q051_050/result')
        sources={'Per-symbol avec seuils (référence)':baseline/'equity-daily.csv'}
        for r in results:
            if CASES[r['profile']]['protected']==protected:
                label='Fusion 50/50, sans seuils' if CASES[r['profile']]['selection']=='FUSION50' else 'Per-symbol relatif, sans seuils'
                sources[label]=Path(r['folder'])/'result/equity-daily.csv'
        for label,file in sources.items():
            series=pd.read_csv(file,index_col=0,parse_dates=True).iloc[:,0].loc['2021-01-01':'2025-12-31']
            series.loc[pd.Timestamp('2021-01-01')]=4000.;series=series.sort_index()
            ax.plot(series.index,series,label=label,linewidth=1.6);frames[('VOL20_' if protected else 'Q051_')+label]=series
        ax.set_title('Volatilité 20 % + régime' if protected else 'Q051 sans B4/régime supplémentaire')
        ax.set_ylabel('Capital valorisé ($)');ax.grid(alpha=.2);ax.legend()
    fig.suptitle('TOP5 relatif — fusion des classements 50/50 — 2021–2025 — départ 4 000 $')
    fig.text(.07,.015,'Frais et financement inclus. Les trois sélections n’ont pas les mêmes seuils absolus. Couverture intraday partielle ; exploratoire.',fontsize=9)
    fig.tight_layout(rect=(0,.035,1,.97));fig.savefig(charts/'capital-comparison.png',dpi=150);fig.savefig(charts/'capital-comparison.svg');plt.close(fig)
    pd.DataFrame(frames).to_csv(charts/'capital-comparison.csv',index_label='date')


def run(root,workers):
    plan=read(root/'request.json')
    for file,sha in plan['sources'].items():
        if digest(Path(file))!=sha:raise ValueError('Source changed: '+file)
    atomic_json(root/'progress.json',dict(status='REPLAYING_FOUR_CASES',completed=0,total=4,cases=list(CASES)))
    results=[];failures=[]
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        tasks={pool.submit(replay_case,str(root),case):case for case in CASES}
        for future in as_completed(tasks):
            try:results.append(future.result())
            except Exception as exc:
                failure=dict(profile=tasks[future],error_type=type(exc).__name__,error=str(exc));failures.append(failure)
                folder=root/'cases'/tasks[future];folder.mkdir(parents=True,exist_ok=True);atomic_json(folder/'progress.json',dict(status='FAILED',**failure))
            atomic_json(root/'progress.json',dict(status='REPLAYING_FOUR_CASES',completed=len(results)+len(failures),total=4,results=results,failures=failures))
    if failures:
        atomic_json(root/'report.json',dict(status='INCOMPLETE_CASES',results=results,failures=failures));raise ValueError('Replay failures: '+str(failures))
    consolidate(root,results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=['prepare','run'],required=True)
    parser.add_argument('--output-dir',type=Path,default=ROOT);parser.add_argument('--workers',type=int,default=2);args=parser.parse_args()
    try:
        if args.phase=='prepare':prepare(args.output_dir)
        else:run(args.output_dir,args.workers)
    except Exception as exc:
        if args.output_dir.exists():atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
