"""One continuous native Winner portfolio, six frozen annual Oracle bundles.

Prepare reads model artifacts and SQL only. Replay uses frozen local inputs,
retains cash/positions/risk state across years, and never contacts a broker.
"""
from dataclasses import asdict
from datetime import date,timedelta,datetime,timezone
from functools import lru_cache
from pathlib import Path
import argparse
import json
import logging
import time

import numpy as np
import pandas as pd
from sqlalchemy import text,bindparam

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_winner_continuous_annual_models/20261108-v2')
RUNS={2021:'20261108_090441_57f9e2b2',2022:'20261108_091552_f146212e',
    2023:'20261108_093814_765b1b66',2024:'20261108_094643_52aa43f9',
    2025:'20261107_225127_babce5b8',2026:'20261108_101309_93f8fb1b'}
START,END=date(2021,1,1),date(2026,10,1)
POLICIES=('recorded','uniform20pct')
LOG=logging.getLogger(__name__)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def source_folder(run):return Path('artifacts/ihm_backtesting_runs/run')/run/'artifacts'


def selection_size(policy,universe_size,original):
    if policy not in POLICIES:raise ValueError('Politique de sélection inconnue')
    return original if policy=='recorded' else int(np.ceil(universe_size*.2))


def annual_signal_days(calendar,year):
    start=max(START,date(year,1,1));end=min(END,date(year,12,31))
    actual=[s.session_date for s in calendar.sessions(start,end) if s.is_open]
    prior=calendar.previous_session(actual[0])
    return actual,[prior,*actual[:-1]]


def same_settings(protocols):
    reference=next(iter(protocols.values()))
    for year,p in protocols.items():
        for section in ('winner_policy','risk','leverage','drawdown_controller','initial_entry'):
            if p[section]!=reference[section]:raise ValueError(f'Réglages {section} différents pour {year}')
        for key in ('account_type','max_leverage','margin_interest_annual','cost_per_leg_bps','max_positions',
                    'daily_entry','drawdown_controller','factor_model','ignore_missing_intraday','options_filter'):
            if p['arguments'][key]!=reference['arguments'][key]:raise ValueError(f'Argument {key} différent pour {year}')
    return reference


def prepare(root):
    from common.market_calendar import get_market_calendar
    from modelFactory.oracle_path.predict import load_contract
    from modelFactory.oracle_path.directional import load_manifest
    from backtesting.winner_campaign_replay import validate_scores,SqlIntradaySource
    from backtesting.per_symbol_selection import PerSymbolSelection,select_per_symbol,attach_calibration_auc
    from backtesting.winner_data import daily_bars
    from backtesting.isolation import ReadOnlyReplay
    from database.connection import get_sqlalchemy_engine
    from common.daily_bar_sources import preferred_daily_source
    root.mkdir(parents=True,exist_ok=False);inputs=root/'inputs';inputs.mkdir()
    protocols={y:read(source_folder(i)/'protocol.json') for y,i in RUNS.items()}
    reference=same_settings(protocols)
    if not reference['arguments']['daily_entry'] or reference['arguments']['factor_model'] or reference['arguments']['options_filter']:
        raise ValueError('Ce replay attend entrée daily, sans facteurs ni filtre options')
    if any(p['daily_bars_preference']!=preferred_daily_source() for p in protocols.values()):
        raise ValueError('La préférence daily actuelle diffère de celle des runs sources')
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    annual={};sources={};selections={k:[] for k in POLICIES};names=set();all_days=[]
    for year,ident in RUNS.items():
        atomic_json(root/'progress.json',dict(status='VERIFYING_ANNUAL_MODELS',year=year,completed=year-2021,total=6))
        folder=source_folder(ident);p=protocols[year];args=p['arguments'];batch=args['oracle_batch_id']
        model_root,contract,_,folds=load_contract(args['artifacts_dir'],batch)
        manifest,manifest_hash=load_manifest(model_root)
        trained_end=pd.Timestamp(contract['training_config']['data']['training_end_date'])
        if trained_end>=pd.Timestamp(year,1,1):raise ValueError(f'Modèle {year} entraîné sur son année de test')
        if contract['horizon']!=10 or contract['directional_contract']['horizon_sessions']!=10:
            raise ValueError('Les six runs demandés doivent conserver leur horizon H10')
        if digest(model_root/'protocol.json')!=p['model_protocol_sha256']:raise ValueError('Protocole de modèle modifié')
        if digest(folder/'signals.csv')!=p['signals_sha256']:
            # This hash was computed on the exact original CSV output bytes.
            raise ValueError('Signaux du run source modifiés : '+ident)
        actual,expected=annual_signal_days(cal,year);all_days.extend(actual)
        ranking=pd.read_csv(folder/'per-symbol-ranking.csv',parse_dates=['date'],low_memory=False)
        validate_scores(ranking.rename(columns={'date':'trade_date'}),profile_hash=digest(model_root/'feature_profile.json'),
            folds=folds,expected_days=expected,top_n=args['top_n'],horizon=10,
            universe_size=len(contract['universe']),min_coverage=args['min_oracle_coverage'])
        records={(r['symbol'],r['year'],r['side']):r for r in manifest['models']}
        # Older bundles keep their verified AUCs in supplemental diagnostics,
        # exactly as the IHM does; do not assume metrics are in the manifest.
        proof=ranking[['date','symbol']].copy();proof['_year']=proof.date.dt.year
        proof=proof.drop_duplicates(['symbol','_year']).drop(columns='_year')
        proof=attach_calibration_auc(proof,model_root)
        expected_auc={(r.symbol,r.date.year):(r.long_auc,r.long_auc_available_date) for r in proof.itertuples()}
        for side in ('long','short'):
            scored=ranking[ranking[side+'_probability'].notna()]
            for (symbol,model_year),g in scored.groupby(['symbol',scored.date.dt.year]):
                rec=records.get((symbol,int(model_year),side))
                if rec is None or not g[side+'_model_sha256'].eq(rec['sha256']).all() or not g.date.gt(pd.Timestamp(rec['available'])).all():
                    raise ValueError('Prédictions per-symbol non causales ou autre modèle')
                if side=='long' and g.long_auc.notna().any():
                    auc,available=expected_auc.get((symbol,int(model_year)),(None,None))
                    known=g[g.long_auc.notna()]
                    if (auc is None or not np.isclose(known.long_auc,auc,rtol=1e-10,atol=1e-12).all()
                            or not pd.to_datetime(known.long_auc_available_date).eq(pd.Timestamp(available)).all()):
                        raise ValueError('AUC archivée différente de la calibration du modèle')
        observed=pd.read_csv(folder/'signals.csv',parse_dates=['trade_date'])
        counts={}
        for policy in POLICIES:
            settings=PerSymbolSelection(**{**p['per_symbol_selection'],
                'oracle_top_n':selection_size(policy,len(contract['universe']),args['top_n'])})
            chosen=select_per_symbol(ranking,settings)
            chosen=chosen[chosen.selected].rename(columns={'date':'trade_date'}).copy()
            chosen['oracle_amplitude_rank']=chosen.oracle_rank;chosen['rank']=chosen['rank'].astype(int)
            if not chosen.trade_date.dt.date.isin(expected).all():raise ValueError('Signaux hors année d’entrée')
            if policy=='recorded':
                if set(zip(chosen.trade_date,chosen.symbol))!=set(zip(observed.trade_date,observed.symbol)):
                    raise ValueError('Sélection source non reproduite : '+ident)
                a=chosen.sort_values(['trade_date','symbol']);b=observed.sort_values(['trade_date','symbol'])
                if not np.array_equal(a['rank'],b['rank']) or not np.allclose(a.long_probability,b.long_probability):
                    raise ValueError('Classement source différent : '+ident)
            chosen['source_run_id']=ident;chosen['oracle_batch_id']=batch;chosen['entry_year']=year
            chosen.to_parquet(inputs/f'signals-{policy}-{year}.parquet',index=False)
            selections[policy].append(chosen);names.update(chosen.symbol)
            counts[policy]=dict(oracle_top_n=settings.oracle_top_n,signals=len(chosen),symbols=int(chosen.symbol.nunique()))
        annual[str(year)]=dict(run_id=ident,batch_id=batch,training_start=contract['training_config']['data']['training_start_date'],
            training_end=str(trained_end.date()),universe_size=len(contract['universe']),horizon=10,
            model_manifest_sha256=manifest_hash,selection=counts,
            first_signal=str(expected[0]),last_signal=str(expected[-1]))
        for file in (folder/'protocol.json',folder/'signals.csv',folder/'per-symbol-ranking.csv',
                     model_root/'protocol.json',model_root/'feature_profile.json',model_root/'directional/manifest.json'):
            sources[str(file)]=digest(file)
        supplemental=model_root/'directional/diagnostics/report.json'
        if supplemental.exists():sources[str(supplemental)]=digest(supplemental)
        LOG.info('Modèle %d vérifié : %s ; signaux %s',year,batch,counts)
    for policy,parts in selections.items():
        combined=pd.concat(parts,ignore_index=True).sort_values(['trade_date','rank','symbol'])
        if combined.duplicated(['trade_date','symbol']).any():raise ValueError('Signaux dupliqués entre années')
        combined.to_parquet(inputs/f'signals-{policy}.parquet',index=False)
    dependencies=[Path(__file__),Path('backtesting/simulator.py'),Path('backtesting/per_symbol_selection.py'),
        Path('backtesting/production_risk_replay.py'),Path('backtesting/adaptive_breaker.py'),
        Path('backtesting/regime_trailing.py'),Path('execution_engine/config.py'),Path('common/trading_costs.py')]
    for directory,pattern in [('backtesting','winner*.py'),('risk_management','*.py'),('execution_engine','winner*.py'),('common','winner*.py')]:
        dependencies.extend(Path(directory).glob(pattern))
    sources.update({str(p):digest(p) for p in dependencies})
    atomic_json(root/'protocol.json',dict(schema_version=1,start=str(START),end=str(END),initial_equity=4000.,
        annual_reset=False,positions_carried=True,risk_state_carried=True,model_switch='YEAR_OF_NEXT_ENTRY_SESSION',
        reference=reference,annual_models=annual,sources=sources,selected_symbols=len(names),
        prepared_at_utc=datetime.now(timezone.utc).isoformat(),SQL_writes=0,provider_calls=0,broker_calls=0,
        training=False,strict_pit=False))
    names=sorted(names|{'SPY'});prior=cal.previous_session(all_days[0])
    with ReadOnlyReplay(root).install():
        engine=get_sqlalchemy_engine(db_name='alpha_trade')
        with engine.connect() as conn,conn.begin():
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':raise ValueError('Base US requise')
            daily=daily_bars(conn,names,prior-timedelta(days=650),END)
            daily.to_parquet(inputs/'daily.parquet',index=False)
            sectors=pd.read_sql(text('SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols')
                .bindparams(bindparam('symbols',expanding=True)),conn,params=dict(symbols=names))
            if sectors.duplicated('symbol').any():raise ValueError('Secteurs ambigus')
            sectors.to_parquet(inputs/'sectors.parquet',index=False)
            actions=pd.read_sql(text('SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency '
                'FROM corporate_actions_events WHERE symbol IN :symbols AND ex_date BETWEEN :start AND :end')
                .bindparams(bindparam('symbols',expanding=True)),conn,params=dict(symbols=names,start=prior,end=END))
            actions.to_parquet(inputs/'actions.parquet',index=False)
            src=SqlIntradaySource(conn,discard_unqualified=True,allow_daily_fallback=True)
            (inputs/'intraday').mkdir()
            for i,day in enumerate(all_days):
                frames=[src(day,names[j:j+100]) for j in range(0,len(names),100)]
                frames=[f for f in frames if not f.empty]
                frame=pd.concat(frames,ignore_index=True).sort_values(['symbol','timestamp']).reset_index(drop=True) if frames else pd.DataFrame()
                frame.to_parquet(inputs/'intraday'/f'{day}.parquet',index=False)
                atomic_json(root/'progress.json',dict(status='FREEZING_PRICES_READ_ONLY',completed=i+1,total=len(all_days),last_date=str(day),symbols=len(names)))
                if i%20==0:LOG.info('Prix figés %d/%d %s',i+1,len(all_days),day)
            atomic_json(inputs/'data-receipts.json',src.receipts)
    files={str(p.relative_to(inputs)):digest(p) for p in inputs.rglob('*') if p.is_file()}
    atomic_json(inputs/'manifest.json',dict(files=files,symbols=names,sessions=len(all_days),
        transaction='ONE_REPEATABLE_READ_READ_ONLY',price_source_preference=reference['daily_bars_preference']))
    atomic_json(root/'progress.json',dict(status='INPUTS_FROZEN',policies=list(POLICIES),sessions=len(all_days)))
    return annual


class FrozenIntraday:
    def __init__(self,root):self.root=root
    @lru_cache(maxsize=6)
    def groups(self,day):
        f=pd.read_parquet(self.root/'inputs/intraday'/f'{day}.parquet')
        return {s:g for s,g in f.groupby('symbol')} if not f.empty else {}
    def __call__(self,day,symbols):
        groups=self.groups(day);parts=[groups[s] for s in sorted(symbols) if s in groups]
        return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()


def replay(root,policy):
    from common.winner_pyramiding import WinnerPyramidingConfig
    from risk_management.config import RiskConfig
    from execution_engine.config import ExecutionConfig,LeverageConfig
    from backtesting.simulator import BacktestConfig,BacktestEngine,BacktestResult
    from backtesting.trading_constraints import TradingConstraintConfig
    from backtesting.winner_campaign_replay import metrics
    from backtesting.isolation import ReadOnlyReplay
    plan=read(root/'protocol.json');manifest=read(root/'inputs/manifest.json')
    for file,sha in plan['sources'].items():
        if digest(Path(file))!=sha:raise ValueError('Source modifiée : '+file)
    for name,sha in manifest['files'].items():
        if digest(root/'inputs'/name)!=sha:raise ValueError('Entrée modifiée : '+name)
    out=root/('continuous-'+policy);out.mkdir(exist_ok=False)
    ref=plan['reference'];args=ref['arguments'];risk=RiskConfig(**ref['risk'])
    execution=ExecutionConfig(winner_pyramiding=WinnerPyramidingConfig(**ref['winner_policy']),
        account_type=args['account_type'],dry_run=True,simulated_account_equity=4000.,
        leverage=LeverageConfig(**ref['leverage']),simulated_margin_buying_power_multiplier=ref['allowed_max_leverage'])
    cfg=BacktestConfig(start_date=START,end_date=END,initial_equity=4000.,risk_config=risk,exec_config=execution,
        use_canonical_costs=True,cost_round_trip_bps=2*args['cost_per_leg_bps'],
        winner_daily_entry_enabled=args['daily_entry'],winner_drawdown_controller_enabled=args['drawdown_controller'],
        margin_interest_rate_annual=args['margin_interest_annual'],
        trading_constraints=TradingConstraintConfig(account_type=args['account_type'],swing_only=False))
    bars=pd.read_parquet(root/'inputs/daily.parquet')
    pivots={k:bars.pivot(index='date',columns='symbol',values=k).astype(float) for k in ('open','high','low','close','volume')}
    sectors=pd.read_parquet(root/'inputs/sectors.parquet').set_index('symbol').sector.to_dict()
    actions=pd.read_parquet(root/'inputs/actions.parquet').to_dict('records')
    signals=pd.read_parquet(root/'inputs'/f'signals-{policy}.parquet')
    atomic_json(out/'configuration.json',dict(policy=policy,portfolio=asdict(cfg),source_protocol_sha256=digest(root/'protocol.json')))
    import requests
    from unittest.mock import patch
    def no_http(*a,**kw):raise ValueError('HTTP interdit dans ce replay figé')
    with ReadOnlyReplay(root).install(),patch.object(requests.Session,'request',no_http):
        def progress(done,total,day):
            state=dict(status='REPLAYING_CONTINUOUS',policy=policy,completed=done,total=total,last_date=str(day))
            atomic_json(out/'progress.json',state);atomic_json(root/'progress.json',state)
        result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
            volume=pivots['volume'],signals_df=signals,sector_map=sectors,intraday_source=FrozenIntraday(root),
            winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=actions)
        result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
        result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
        result.closed_trades_df.to_csv(out/'trades.csv',index=False)
        result.trade_events_df.to_csv(out/'events.csv',index=False)
        result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
        report=metrics(result,4000.);annual=[];opening=4000.
        for year in sorted(result.equity_curve.index.year.unique()):
            daily=result.equity_curve[result.equity_curve.index.year==year]
            trades=result.closed_trades_df
            closed=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(year)] if len(trades) else trades
            marks=result.intraday_equity_curve
            part=BacktestResult(equity_curve=daily,closed_trades_df=closed,
                intraday_equity_curve=marks[pd.to_datetime(marks.timestamp,utc=True).dt.year.eq(year)],
                tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
            row=metrics(part,opening);row.update(year=int(year),model=plan['annual_models'][str(year)]['batch_id'])
            annual.append(row);opening=float(daily.iloc[-1])
        pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
        report.update(policy=policy,annual_reset=False,positions_carried=True,risk_state_carried=True,
            annual_models=plan['annual_models'],selected_signals=len(signals),provider_calls=0,broker_calls=0,SQL_writes=0,
            strict_pit=False,finished_at_utc=datetime.now(timezone.utc).isoformat())
        atomic_json(out/'report.json',report)
        atomic_json(out/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
        atomic_json(root/'progress.json',dict(status='COMPLETED_EXPLORATORY',policy=policy))
    return {k:report[k] for k in ('status','final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','average_gross_capital')}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['prepare','replay'])
    parser.add_argument('--output-dir',type=Path,default=ROOT);parser.add_argument('--selection-policy',choices=POLICIES)
    a=parser.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if a.phase=='replay' and a.selection_policy is None:parser.error('--selection-policy requis')
    try:result=prepare(a.output_dir) if a.phase=='prepare' else replay(a.output_dir,a.selection_policy)
    except Exception as exc:
        if a.output_dir.is_dir():atomic_json(a.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
    print(json.dumps(result,ensure_ascii=False,default=str))


if __name__=='__main__':main()
