"""Classic blue Q051 witness: matched TOP5/TOP10, no volatility/regime overlay.

Replay the old witness alongside the new variant because implementation files
have changed since its archive. No provider, model, SQL or broker mutation.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
import json
import logging
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from scripts.research.us_q051_vol20_regime_h5_20261115 import shared,EXT,market_data,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_q051_classic_top10/20261115-v1')
OLD=shared.ROOT/'cases/Q051_050'
SELECTION=Path('artifacts/research/us_q051_selection_variants/20261115-v1')
CASES={'CONTROL_TOP5':'REFERENCE','TOP10':'TOP10_SCORE050'}


def meaningful(value):
    if isinstance(value,dict):return {k:meaningful(v) for k,v in value.items() if v is not None}
    if isinstance(value,list):return [meaningful(v) for v in value]
    return value


def configuration():
    cfg=shared.configuration(read(shared.ROOT/'protocol.json')['reference'],shared.CASES['Q051_050'])
    actual=json.loads(json.dumps(asdict(cfg),default=str))
    expected=read(OLD/'result/configuration.json')['portfolio']
    if meaningful(actual)!=meaningful(expected):raise ValueError('Classic archived configuration differs')
    if cfg.winner_drawdown_controller_enabled or cfg.risk_config.max_gross_exposure!=1.:
        raise ValueError('Classic witness must keep B4 disabled and gross cap 1x')
    return cfg


def prepare():
    ROOT.mkdir(parents=True,exist_ok=False)
    prior=read(shared.ROOT/'protocol.json');recent=read(SELECTION/'protocol.json')
    if read(SELECTION/'validation-independent.json')['status']!='PASS':raise ValueError('Selections unvalidated')
    configuration();sources={};changes=[]
    for p,h in prior['sources'].items():
        current=digest(Path(p));sources[p]=current
        if current!=h:changes.append(p)
    for p in [Path(__file__),Path('scripts/research/us_q051_vol20_regime_h5_20261115.py'),
              OLD/'protocol.json',OLD/'result/report.json',OLD/'result/configuration.json',
              SELECTION/'protocol.json',SELECTION/'validation-independent.json']:
        sources[str(p)]=digest(p)
    for name in CASES.values():
        p=SELECTION/'inputs'/f'signals-{name}.parquet'
        if digest(p)!=recent['sources'][str(p)]:raise ValueError('Changed validated selection')
        sources[str(p)]=digest(p)
    # The enlarged market archive only adds previously unqueried symbol/days.
    # It never overwrites original prices; control replay verifies economics.
    manifests={}
    for base in [shared.ROOT,EXT]:
        p=base/'inputs/manifest.json';manifests[str(p)]=digest(p)
        for relative,h in read(p)['files'].items():
            if digest(base/'inputs'/relative)!=h:raise ValueError('Changed frozen price: '+relative)
    atomic_json(ROOT/'protocol.json',dict(start=prior['start'],end=prior['end'],initial_equity=4000.,
        reference=read(OLD/'protocol.json')['reference'],annual_models=prior['annual_models'],
        cases=CASES,sources=sources,market_manifests=manifests,old_witness=str(OLD),
        changed_implementations_since_old_witness=changes,
        configuration_comparison='All effective fields identical; new optional null fields ignored only for archive comparison',
        selection='TOP10% Oracle (179) -> TOP5 or TOP10 LONG; score>.50; calibration AUC>=.50; no refill',
        overlays=dict(portfolio_volatility=False,SPY_regime=False,B4_DD15=False,global_liquidation=False),
        annual_reset=False,training=False,new_inference=False,provider_calls=0,SQL_writes=0,orders=0,
        production_changes=False,prepared_at_utc=datetime.now(timezone.utc).isoformat()))
    atomic_json(ROOT/'progress.json',dict(status='READY',cases=list(CASES)))


def run_case(name):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from scripts.research.us_winner_vol20_extensions_20261109 import ExtendedPrices
    plan=read(ROOT/'protocol.json');folder=ROOT/'cases'/name;folder.mkdir(parents=True,exist_ok=False)
    out=folder/'result';out.mkdir()
    try:
        for p,h in plan['sources'].items():
            if digest(Path(p))!=h:raise ValueError('Changed sealed source: '+p)
        cfg=configuration();signals=pd.read_parquet(SELECTION/'inputs'/f'signals-{CASES[name]}.parquet')
        ref=deepcopy(plan['reference']);ref['per_symbol_selection']['long_top_n']=5 if name=='CONTROL_TOP5' else 10
        ref['arguments']['per_symbol_top_long']=ref['per_symbol_selection']['long_top_n']
        atomic_json(folder/'protocol.json',{**plan,'case':name,'reference':ref})
        atomic_json(out/'configuration.json',dict(profile=name,portfolio=asdict(cfg)))
        atomic_json(folder/'progress.json',dict(status='LOADING_MARKET_INPUTS'))
        pivots,sectors,actions=market_data()
        def no_http(*a,**kw):raise ValueError('Network forbidden in frozen classic Q051 replay')
        with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(shared.ROOT)),patch.object(requests.Session,'request',no_http):
            def progress(done,total,day):
                atomic_json(folder/'progress.json',dict(status='REPLAYING',completed=done,total=total,last_date=str(day),case=name))
            result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
                volume=pivots['volume'],signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),
                intraday_source=ExtendedPrices(EXT),winner_research_assumptions=True,winner_progress=progress,
                winner_corporate_actions=actions.to_dict('records'))
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
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
        # Completion precedes the importer; original economic files stay intact.
        atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
        from ihm.services.backtesting_import import import_continuous_winner
        record=import_continuous_winner(folder,run_id='20261115_q051_classic_'+name.lower(),
            label='Q051 simple — '+name+' / score>0,50 / AUC≥0,50 — 2021–2026',result_subdir='result')
        atomic_json(folder/'ihm.json',dict(run_id=record['run_id']))
        print(json.dumps({k:report[k] for k in ['case','final_equity','return_pct','max_drawdown_pct','win_pct']}))
    except BaseException as exc:
        atomic_json(folder/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','case'],required=True)
    p.add_argument('--case',choices=list(CASES));args=p.parse_args()
    if args.phase=='prepare':prepare()
    else:run_case(args.case)
