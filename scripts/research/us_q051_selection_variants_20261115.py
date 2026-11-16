"""Two matched selection-only variants of Q051 vol20/regime, archived inputs.

Never trains, predicts, downloads, mutates production or submits orders.
Each case owns its capital, policy state, reports and IHM history record.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_q051_vol20_regime_h5_20261115 import (
    shared, WITNESS, GLOBAL_ARCHIVE, EXT, market_data, read)

ROOT=Path('artifacts/research/us_q051_selection_variants/20261115-v1')
CASES={
    'TOP10_SCORE050':dict(long_top_n=10,min_long_probability=.50,min_long_auc=.50),
    'TOP5_SCORE060':dict(long_top_n=5,min_long_probability=.60,min_long_auc=.50),
}
LABELS={'REFERENCE':'Référence — TOP5, score >0,50',
        'TOP10_SCORE050':'TOP10, score >0,50', 'TOP5_SCORE060':'TOP5, score >0,60'}


def configuration():
    from backtesting.risk_overlay import RegimeFilterConfig
    cfg=shared.configuration(read(shared.ROOT/'protocol.json')['reference'],shared.CASES['Q051_050'])
    cfg.risk_overlay.regime_filter=RegimeFilterConfig(enabled=True,sma_window=200,bear_threshold=-.02)
    if json.loads(json.dumps(asdict(cfg),default=str))!=read(WITNESS/'result/configuration.json')['portfolio']:
        raise ValueError('Portfolio configuration differs from validated witness')
    return cfg


def prepare():
    from backtesting.per_symbol_selection import PerSymbolSelection,select_per_symbol
    from modelFactory.oracle_path.directional import load_manifest
    ROOT.mkdir(parents=True,exist_ok=False);inputs=ROOT/'inputs';inputs.mkdir()
    if read(GLOBAL_ARCHIVE/'economic-baseline-validation.json')['status']!='PASS':
        raise ValueError('Economic reference unqualified')
    sources=read(GLOBAL_ARCHIVE/'request.json')['sources'].copy()
    for p in [Path(__file__),Path('scripts/research/us_q051_vol20_regime_h5_20261115.py'),
              WITNESS/'protocol.json',WITNESS/'result/configuration.json',WITNESS/'result/report.json']:
        sources[str(p)]=digest(p)
    for path,sha in sources.items():
        if digest(Path(path))!=sha:raise ValueError('Changed reference source: '+path)
    manifests={}
    for base in [shared.ROOT,EXT]:
        manifest=base/'inputs/manifest.json';manifests[str(manifest)]=digest(manifest)
        for relative,sha in read(manifest)['files'].items():
            if digest(base/'inputs'/relative)!=sha:raise ValueError('Changed market/ranking archive: '+relative)
    witness=read(WITNESS/'protocol.json');configuration()
    selected={name:[] for name in ['REFERENCE',*CASES]};counts=[]
    for year,annual in witness['annual_models'].items():
        atomic_json(ROOT/'progress.json',dict(status='PREPARING_SELECTIONS',year=int(year)))
        path=shared.ROOT/'inputs/rankings'/f'{year}.parquet';sources[str(path)]=digest(path)
        frame=pd.read_parquet(path);frame=shared.normalize_ranking_dates(frame)
        root=Path('artifacts/models')/annual['batch_id']/'oracle_path'
        manifest,mhash=load_manifest(root)
        if mhash!=annual['model_manifest_sha256']:raise ValueError('Annual manifest changed')
        if pd.Timestamp(annual['training_end'])>=pd.Timestamp(int(year),1,1):raise ValueError('Future training')
        shared.verify_branches(frame,manifest)
        if not frame.model_available_date.lt(frame.date).all():raise ValueError('Future Oracle fold')
        for name,case in {'REFERENCE':dict(long_top_n=5,min_long_probability=.5,min_long_auc=.5),**CASES}.items():
            policy=PerSymbolSelection(oracle_top_n=179,allow_long=True,allow_short=False,**case)
            ranked=select_per_symbol(frame,policy)
            choice=ranked[ranked.selected].rename(columns={'date':'trade_date'}).copy()
            choice['rank']=choice['rank'].astype(int);choice['oracle_amplitude_rank']=choice.oracle_rank
            choice['source_run_id']=annual['run_id'];choice['oracle_batch_id']=annual['batch_id'];choice['entry_year']=int(year)
            selected[name].append(choice)
            counts.append(dict(case=name,year=int(year),signals=len(choice),symbols=int(choice.symbol.nunique()),
                signal_dates=int(choice.trade_date.nunique()),policy=policy.snapshot()))
    reference=None
    for name,parts in selected.items():
        f=pd.concat(parts,ignore_index=True).sort_values(['trade_date','rank','symbol']).reset_index(drop=True)
        f.to_parquet(inputs/f'signals-{name}.parquet',index=False)
        sources[str(inputs/f'signals-{name}.parquet')]=digest(inputs/f'signals-{name}.parquet')
        if name=='REFERENCE':reference=f
    old=pd.read_parquet(GLOBAL_ARCHIVE/'inputs/signals-Q051_REFERENCE.parquet').sort_values(
        ['trade_date','rank','symbol']).reset_index(drop=True)
    for c in ['trade_date','symbol','rank','oracle_amplitude_rank','long_probability','long_auc','long_model_sha256']:
        if not old[c].equals(reference[c]):raise ValueError('Baseline selection reproduction failed: '+c)
    if len(reference)!=6073:raise ValueError('Reference signal count changed')
    plan=dict(start=witness['start'],end=witness['end'],initial_equity=4000.,annual_reset=False,
        reference=witness['reference'],annual_models=witness['annual_models'],cases=CASES,
        baseline_root=str(WITNESS),baseline_signals_reproduced=len(reference),sources=sources,
        market_manifests=manifests,selection_counts=counts,
        invariants='Identical portfolio configuration; TOP10% Oracle (179); AUC>=.50; H10/open11; no refill',
        full_portfolio_replay=True,provider_calls=0,SQL_writes=0,orders=0,production_changes=False,
        training=False,new_inference=False,prepared_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'protocol.json',plan)
    pd.DataFrame([{k:v for k,v in row.items() if k!='policy'} for row in counts]).to_csv(ROOT/'selection-counts.csv',index=False)
    atomic_json(ROOT/'progress.json',dict(status='READY',baseline_signals=len(reference)))
    print(json.dumps(dict(status='READY',counts=counts),ensure_ascii=False),flush=True)


def run_case(name):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.winner_portfolio_budget import replay_protections
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from scripts.research.us_winner_vol20_extensions_20261109 import ExtendedPrices
    plan=read(ROOT/'protocol.json');folder=ROOT/'cases'/name;folder.mkdir(parents=True,exist_ok=False)
    out=folder/'result';out.mkdir()
    try:
        cfg=configuration()
        for file,sha in plan['sources'].items():
            if digest(Path(file))!=sha:raise ValueError('Changed input: '+file)
        for file,sha in plan['market_manifests'].items():
            if digest(Path(file))!=sha:raise ValueError('Changed market manifest')
        signals=pd.read_parquet(ROOT/'inputs'/f'signals-{name}.parquet')
        reference=deepcopy(plan['reference']);reference.pop('global_ranking_comparison',None)
        reference['per_symbol_selection'].update(**CASES[name])
        reference['arguments'].update(per_symbol_top_long=CASES[name]['long_top_n'],
            per_symbol_min_long_probability=CASES[name]['min_long_probability'],per_symbol_min_long_auc=.5)
        local={**plan,'case':name,'reference':reference,'selection_variant':CASES[name]}
        atomic_json(folder/'protocol.json',local)
        atomic_json(out/'configuration.json',dict(profile=name,portfolio=asdict(cfg)))
        atomic_json(folder/'progress.json',dict(status='LOADING_MARKET_INPUTS'))
        pivots,sectors,actions=market_data()
        budget,gate=replay_protections(pivots['close'],daily_entry=True,target=.20,regime=True)
        def no_http(*a,**kw):raise ValueError('HTTP forbidden in matched Q051 variants')
        with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(shared.ROOT)),patch.object(requests.Session,'request',no_http):
            def tick(done,total,day):
                state=dict(status='REPLAYING',case=name,completed=done,total=total,last_date=str(day))
                atomic_json(folder/'progress.json',state)
            result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],
                low=pivots['low'],volume=pivots['volume'],signals_df=signals,
                sector_map=sectors.set_index('symbol').sector.to_dict(),intraday_source=ExtendedPrices(EXT),
                winner_research_assumptions=True,winner_progress=tick,winner_corporate_actions=actions.to_dict('records'),
                winner_selection_source=gate,winner_entry_risk_policy=budget)
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
            pd.DataFrame(budget.receipts).to_csv(out/'portfolio-risk-decisions.csv',index=False)
            pd.DataFrame(gate.receipts).to_csv(out/'regime-decisions.csv',index=False)
            report=metrics(result,4000.);annual=[];opening=4000.
            for year in range(2021,2027):
                curve=result.equity_curve[result.equity_curve.index.year==year]
                t=result.closed_trades_df;m=result.intraday_equity_curve
                closed=t[pd.to_datetime(t.exit_date,utc=True).dt.year.eq(year)] if len(t) else t
                part=BacktestResult(equity_curve=curve,closed_trades_df=closed,
                    intraday_equity_curve=m[pd.to_datetime(m.timestamp,utc=True).dt.year.eq(year)],
                    tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
                row=metrics(part,opening);row.update(year=year,model=plan['annual_models'][str(year)]['batch_id'])
                annual.append(row);opening=float(curve.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
            report.update(case=name,selected_signals=len(signals),selection_variant=CASES[name],
                annual_models=plan['annual_models'],annual_reset=False,
                exit_reasons=result.closed_trades_df.exit_reason.value_counts().to_dict(),
                strict_pit=False,model_timing_oos=True,provider_calls=0,SQL_writes=0,orders=0,
                finished_at_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(out/'report.json',report)
        from ihm.services.backtesting_import import import_continuous_winner
        run_id='20261115_q051_vol20_'+name.lower()
        record=import_continuous_winner(folder,run_id=run_id,
            label='Q051 vol20 + régime — '+LABELS[name]+' — annuel 2021–2026',result_subdir='result')
        atomic_json(folder/'ihm.json',dict(run_id=record['run_id']))
        atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
        print(json.dumps({k:report[k] for k in ['case','final_equity','return_pct','max_drawdown_pct','win_pct']},ensure_ascii=False))
    except BaseException as exc:
        atomic_json(folder/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


def compare():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    columns=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','winners','losers',
        'average_winning_pnl','average_losing_pnl','average_gross_capital','average_gross_equity_ratio','costs','margin_interest']
    rows=[];annual=[];curves=[];fig,(ax,ddax)=plt.subplots(2,1,figsize=(13,9),sharex=True,
        gridspec_kw={'height_ratios':[2,1]})
    for name,folder in {'REFERENCE':WITNESS,**{k:ROOT/'cases'/k for k in CASES}}.items():
        r=read(folder/'result/report.json');e=pd.read_csv(folder/'result/equity-daily.csv',index_col=0,parse_dates=True).equity
        a=pd.read_csv(folder/'result/annual-summary.csv');a['variant']=name;annual.append(a)
        if not np.isclose(4000*np.prod(1+a.return_pct/100),r['final_equity'],atol=1e-6):raise ValueError('Annual composition mismatch')
        rows.append(dict(variant=name,label=LABELS[name],**{c:r[c] for c in columns}))
        ax.plot(e.index,e,label=LABELS[name]);ddax.plot(e.index,100*(e/e.cummax().clip(lower=4000)-1))
        curves.append(e.rename(name))
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    pd.concat(curves,axis=1).to_csv(ROOT/'capital-curves.csv')
    ax.set_title('Q051 volatilité 20 % + régime — variantes de sélection LONG')
    ax.set_ylabel('Capital valorisé ($), départ 4 000');ax.legend();ax.grid(alpha=.2)
    ddax.set_ylabel('DD aux clôtures (%)');ddax.grid(alpha=.2)
    fig.text(.06,.01,'2021–1 octobre 2026. SL5/open11, AUC ≥0,50 inchangée. Frais inclus. DD maximal du bilan mesuré en intraday.\nArchives 5m partielles, repli OHLC qualifié ; modèles annuels, univers actuel rétrospectif.',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,1));fig.savefig(ROOT/'capital-comparison.png',dpi=145);plt.close(fig)
    return rows


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','case','compare'],required=True)
    p.add_argument('--case',choices=list(CASES));args=p.parse_args()
    if args.phase=='prepare':prepare()
    elif args.phase=='case':run_case(args.case)
    else:print(json.dumps(compare(),ensure_ascii=False))
