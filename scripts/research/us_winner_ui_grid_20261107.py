"""Matched 2025 Winner UI sweep; frozen inputs, native engine, no live changes."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from itertools import product
import json
import logging
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from backtesting.winner_campaign_replay import atomic_json, metrics
from backtesting.per_symbol_selection import PerSymbolSelection, select_per_symbol

REFERENCE = Path('artifacts/ihm_backtesting_runs/run/20261107_095041_0b38b8de/artifacts')
ROOT = Path('artifacts/research/us_winner_ui_grid/20261107-v3')
LOG = logging.getLogger(__name__)
DATA = None


def digest(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def cases():
    result = []
    for probability, auc, budget, weight, sl, horizon, controller in product(
            [.6, .7], [None, .6], [.0125, .025], [.2, .4], [.03, .05], [10, 20], [False, True]):
        result.append(dict(name=f'F{len(result):03}', family='FACTORIAL',
            selection=dict(min_long_probability=probability, min_long_auc=auc),
            risk=dict(risk_per_trade_pct=budget, max_position_weight=weight,
                      force_close_on_breaker=controller, force_close_pct=.5),
            policy=dict(stop_loss_pct=sl, horizon_sessions=horizon), controller=controller, daily=True))
    supplemental = [
        ('POOL5PCT', 'selection', dict(oracle_top_n=90)),
        ('POOL20PCT', 'selection', dict(oracle_top_n=358)),
        ('LONG5', 'selection', dict(long_top_n=5)),
        ('LONG20', 'selection', dict(long_top_n=20)),
        ('PROBA55', 'selection', dict(min_long_probability=.55)),
        ('PROBA65', 'selection', dict(min_long_probability=.65)),
        ('AUC55', 'selection', dict(min_long_auc=.55)),
        ('SL1', 'policy', dict(stop_loss_pct=.01)),
        ('SL7', 'policy', dict(stop_loss_pct=.07)),
        ('TP10', 'policy', dict(take_profit_pct=.10)),
        ('TP20', 'policy', dict(take_profit_pct=.20)),
        ('TR3', 'policy', dict(trailing_stop_pct=.03)),
        ('TR7', 'policy', dict(trailing_stop_pct=.07)),
        ('TR15', 'policy', dict(trailing_stop_pct=.15)),
        ('H5', 'policy', dict(horizon_sessions=5)),
        ('H15', 'policy', dict(horizon_sessions=15)),
        ('HALF', 'policy', dict(initial_position_fraction=.5)),
        ('HALF_ADD5', 'policy', dict(initial_position_fraction=.5, reinforcement_enabled=True)),
        ('BUDGET05', 'risk', dict(risk_per_trade_pct=.005)),
        ('BUDGET5', 'risk', dict(risk_per_trade_pct=.05)),
        ('WEIGHT10', 'risk', dict(max_position_weight=.1)),
        ('MIN25', 'risk', dict(min_position_notional=25.)),
        ('MIN100', 'risk', dict(min_position_notional=100.)),
        ('POSITIONS30', 'risk', dict(max_positions=30)),
        ('CORRELATION90', 'risk', dict(correlation_check_enabled=True)),
        ('SECTOR50', 'risk', dict(sector_weight_limit_enabled=True)),
        ('SECTOR3', 'risk', dict(sector_ticker_limit_enabled=True, max_tickers_per_sector=3)),
        ('REPEAT_RELAXED', 'risk', dict(concentration_max_trades_per_symbol=20,
            concentration_window_calendar_days=180, concentration_max_consecutive_losses=5,
            concentration_blacklist_duration_days=20)),
        ('INTRADAY0_DELAY930', 'policy', dict(confirmation_bars=0, market_data_delay_seconds=930)),
        ('INTRADAY2_DELAY930', 'policy', dict(confirmation_bars=2, market_data_delay_seconds=930)),
        ('SL3_TP15', 'policy', dict(stop_loss_pct=.03, take_profit_pct=.15)),
        ('TR15_H20', 'policy', dict(trailing_stop_pct=.15, horizon_sessions=20)),
    ]
    for name, section, changes in supplemental:
        case = dict(name='S_'+name, family='SUPPLEMENTAL_PREDECLARED',
            selection=dict(min_long_probability=.6, min_long_auc=.6),
            risk=dict(risk_per_trade_pct=.025, max_position_weight=.4, force_close_on_breaker=False),
            policy={}, controller=False, daily=not name.startswith('INTRADAY'))
        case[section].update(changes)
        result.append(case)
    # User amendment before any financial replay: jointly cross all three
    # selector thresholds, including the requested LONG list length.
    for pool, probability, auc, count in product([90,179,358],[.55,.6,.65,.7],[None,.55,.6],[5,10,20]):
        result.append(dict(name=f'Q{len(result)-160:03}',family='JOINT_SELECTION_GRID',
            selection=dict(oracle_top_n=pool,min_long_probability=probability,min_long_auc=auc,long_top_n=count),
            risk=dict(risk_per_trade_pct=.025,max_position_weight=.4,force_close_on_breaker=False),
            policy={},controller=False,daily=True))
    # Run the reference first, before any optimization result is consulted.
    reference = dict(name='REFERENCE', family='EXACT_REFERENCE', selection={}, risk={}, policy={},
                     controller=False, daily=True)
    return [reference, *result]


def selection_settings(protocol, case):
    args = protocol['arguments']
    base = PerSymbolSelection(oracle_top_n=args['top_n'], long_top_n=args['per_symbol_top_long'],
        short_top_n=args['per_symbol_top_short'], allow_long=True, allow_short=False,
        min_long_probability=args['per_symbol_min_long_probability'],
        min_long_auc=args['per_symbol_min_long_auc'])
    return replace(base, **case['selection'])


def selection_id(settings):
    import hashlib
    return hashlib.sha256(json.dumps(settings.snapshot(), sort_keys=True).encode()).hexdigest()[:16]


def partitioned_intraday(source,day,symbols):
    """Keep the canonical per-symbol qualification, avoid MySQL IN>=200 plans."""
    names=sorted(set(symbols))
    parts=[source(day,names[i:i+100]) for i in range(0,len(names),100)]
    parts=[frame for frame in parts if not frame.empty]
    return pd.concat(parts,ignore_index=True).sort_values(['symbol','timestamp']).reset_index(drop=True) if parts else pd.DataFrame()


def freeze_plan(root):
    root.mkdir(parents=True, exist_ok=True)
    path = root/'protocol.json'
    dependencies = [Path(__file__), REFERENCE/'protocol.json', REFERENCE/'report.json',
        REFERENCE/'per-symbol-ranking.csv', REFERENCE/'signals.csv', Path('config.yaml')]
    for directory, pattern in [('backtesting', 'winner*.py'), ('risk_management', '*.py'),
                                ('execution_engine', 'winner*.py'), ('common', 'winner*.py')]:
        dependencies.extend(Path(directory).glob(pattern))
    dependencies += [Path('backtesting/simulator.py'), Path('execution_engine/config.py'),
                     Path('backtesting/production_risk_replay.py'), Path('common/trading_costs.py'),
                     Path('backtesting/per_symbol_selection.py'),Path('common/market_calendar.py'),
                     Path('backtesting/adaptive_breaker.py'),Path('backtesting/regime_trailing.py')]
    sources = {str(p): digest(p) for p in dependencies}
    if path.exists():
        plan = read(path)
        if plan['sources'] != sources or plan['cases'] != cases():
            raise ValueError('Sources or frozen grid changed; use a fresh experiment directory')
        return plan
    reference = read(REFERENCE/'protocol.json')
    plan = dict(status='FROZEN_BEFORE_RESULTS', reference_run='20261107_095041_0b38b8de',
        reference=reference, sources=sources, cases=cases(),
        batch_id=reference['arguments']['oracle_batch_id'], start='2025-01-01', end='2025-12-31',
        initial_equity=4000., leverage=2., workers=3,
        ranking='Pareto return/MAX_DD; recommend balanced positive-return >=30-trade cases; report quarterly stability and exposure',
        native_engine_unchanged=True, training=False, provider_calls=0, sql_writes=False, broker_calls=0,
        production_changed=False, independent_holdout=False,
        limitations=['2025 repeatedly inspected: in-sample parameter exploration, not future performance proof.',
            'Some protections use adverse-first daily OHLC fallback; no invented intraday ordering.',
            'Current sectors and revised daily data; same frozen tape for all arms.',
            'SL gaps can exceed the stop; DD15 is a trigger, not a guaranteed maximum.',
            'Oracle remains H10 even for 5/15/20-session exit policies.',
            'Technical timeliness and fee-reserve settings are not tuned to manufacture profit.'])
    atomic_json(path, plan)
    atomic_json(root/'progress.json', dict(status='PREPARED', completed=0, total=len(plan['cases'])))
    return plan


def prepare(root):
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.winner_campaign_replay import SqlIntradaySource, validate_scores
    from backtesting.winner_data import daily_bars
    from common.market_calendar import get_market_calendar
    from database.connection import get_sqlalchemy_engine
    from modelFactory.oracle_path.predict import load_contract
    from modelFactory.oracle_path.directional import load_manifest

    plan = freeze_plan(root)
    inputs = root/'inputs'; inputs.mkdir(exist_ok=True)
    if (inputs/'manifest.json').exists():
        verify_inputs(root)
        return
    ref = plan['reference']; args = ref['arguments']
    model_root, model_protocol, _, folds = load_contract(args['artifacts_dir'], args['oracle_batch_id'])
    manifest, manifest_hash = load_manifest(model_root)
    ranking = pd.read_csv(REFERENCE/'per-symbol-ranking.csv', parse_dates=['date'])
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    start, end = date(2025,1,1), date(2025,12,31)
    actual = [s.session_date for s in cal.sessions(start,end) if s.is_open]
    prior = max(s.session_date for s in cal.sessions(start-timedelta(days=14),start) if s.is_open)
    validate_scores(ranking.rename(columns={'date':'trade_date'}),
        profile_hash=digest(model_root/'feature_profile.json'), folds=folds, expected_days=[prior,*actual[:-1]],
        top_n=args['top_n'], horizon=10, universe_size=len(model_protocol['universe']), min_coverage=.93)
    records = {(r['symbol'],r['year'],r['side']): r for r in manifest['models']}
    for side in ('long','short'):
        scored = ranking[ranking[side+'_probability'].notna()]
        for (symbol,year), group in scored.groupby(['symbol',scored.date.dt.year]):
            record = records[symbol,year,side]
            if (not group[side+'_model_sha256'].eq(record['sha256']).all()
                    or not group.date.gt(pd.Timestamp(record['available'])).all()):
                raise ValueError('Noncausal or incompatible archived per-symbol model')
    selection_files = {}; symbols = set()
    for case in plan['cases']:
        settings = selection_settings(ref,case); key = selection_id(settings)
        if key in selection_files:
            continue
        frame = select_per_symbol(ranking,settings)
        frame = frame.loc[frame.selected].rename(columns={'date':'trade_date'})
        frame['oracle_amplitude_rank'] = frame.oracle_rank
        path = inputs/f'signals-{key}.parquet'; frame.to_parquet(path,index=False)
        selection_files[key] = str(path.relative_to(inputs)); symbols.update(frame.symbol)
        atomic_json(root/'progress.json',dict(status='PREPARING_SELECTIONS',
            selections=len(selection_files),symbols=len(symbols),completed=0,total=len(plan['cases'])))
    names = sorted(symbols|{'SPY'})
    with ReadOnlyReplay(root).install():
        engine = get_sqlalchemy_engine(db_name='alpha_trade')
        with engine.connect() as conn, conn.begin():
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            bars = daily_bars(conn,names,prior-timedelta(days=650),end)
            bars.to_parquet(inputs/'daily.parquet',index=False)
            sectors = pd.read_sql(text('SELECT symbol, sector FROM stock_metadata WHERE symbol IN :symbols')
                .bindparams(bindparam('symbols',expanding=True)),conn,params={'symbols':names})
            if sectors.duplicated('symbol').any():
                raise ValueError('Duplicate sector metadata')
            sectors.to_parquet(inputs/'sectors.parquet',index=False)
            actions = pd.read_sql(text('SELECT symbol, ca_type, ex_date, payable_date, amount_per_share, currency '
                'FROM corporate_actions_events WHERE symbol IN :symbols AND ex_date BETWEEN :start AND :end')
                .bindparams(bindparam('symbols',expanding=True)),conn,params=dict(symbols=names,start=prior,end=end))
            actions.to_parquet(inputs/'actions.parquet',index=False)
            source = SqlIntradaySource(conn,discard_unqualified=True,allow_daily_fallback=True)
            tape = inputs/'intraday'; tape.mkdir(exist_ok=True)
            for i, day in enumerate(actual):
                path = tape/f'{day}.parquet'
                # These are availability snapshots, never future-return entry gates.
                frame = partitioned_intraday(source,day,symbols)
                frame.to_parquet(path,index=False)
                atomic_json(root/'progress.json',dict(status='SNAPSHOT_READ_ONLY',completed_days=i+1,
                    total_days=len(actual),symbols=len(symbols),last_date=day,completed=0,total=len(plan['cases'])))
                LOG.info('SNAPSHOT %s %d/%d rows=%d symbols=%d',day,i+1,len(actual),len(frame),len(symbols))
    ranking.to_parquet(inputs/'ranked-source.parquet',index=False)
    files = {str(p.relative_to(inputs)):digest(p) for p in inputs.rglob('*.parquet')}
    atomic_json(inputs/'manifest.json',dict(files=files,selections=selection_files,symbols=names,
        snapshots_qualified_by='canonical SqlIntradaySource; missing sessions remain missing',
        model_manifest_sha256=manifest_hash, observed_at_utc=datetime.now(timezone.utc),
        transaction='One read-only repeatable-read transaction; current archived data vintage'))
    atomic_json(root/'progress.json',dict(status='INPUTS_FROZEN',completed=0,total=len(plan['cases'])))


def verify_inputs(root):
    manifest = read(root/'inputs/manifest.json')
    for name, checksum in manifest['files'].items():
        if digest(root/'inputs'/name) != checksum:
            raise ValueError('Frozen input changed: '+name)
    return manifest


class FrozenIntraday:
    def __init__(self,root):
        self.root = Path(root)

    @lru_cache(maxsize=250)
    def groups(self,day):
        path = self.root/'inputs/intraday'/f'{day}.parquet'
        frame = pd.read_parquet(path)
        return {symbol: group for symbol,group in frame.groupby('symbol')} if not frame.empty else {}

    def __call__(self,day,symbols):
        parts = [self.groups(day)[s] for s in sorted(symbols) if s in self.groups(day)]
        return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()


def initialize_worker(root):
    global DATA
    root=Path(root)
    plan=read(root/'protocol.json')
    bars=pd.read_parquet(root/'inputs/daily.parquet')
    pivots={k:bars.pivot(index='date',columns='symbol',values=k).astype(float)
            for k in ('open','high','low','close','volume')}
    sectors=pd.read_parquet(root/'inputs/sectors.parquet').set_index('symbol').sector.to_dict()
    actions=pd.read_parquet(root/'inputs/actions.parquet').to_dict('records')
    DATA=dict(root=root,plan=plan,pivots=pivots,sectors=sectors,actions=actions,source=FrozenIntraday(root))
    import requests
    def forbidden(*args,**kwargs):
        raise RuntimeError('Provider/broker HTTP forbidden in this frozen replay sweep')
    requests.Session.request=forbidden


def configuration(reference,case):
    from backtesting.simulator import BacktestConfig
    from backtesting.trading_constraints import TradingConstraintConfig
    from common.winner_pyramiding import WinnerPyramidingConfig
    from execution_engine.config import ExecutionConfig, LeverageConfig
    from risk_management.config import RiskConfig
    from backtesting.winner_settings import apply_policy_settings,apply_risk_settings

    policy=apply_policy_settings(WinnerPyramidingConfig(**reference['winner_policy']),case['policy'])
    risk_changes=dict(case['risk']); positions=risk_changes.pop('max_positions',None)
    risk=apply_risk_settings(RiskConfig(**reference['risk']),risk_changes)
    if positions is not None:
        if type(positions) is not int or positions<1:
            raise ValueError('Invalid position count')
        risk=replace(risk,max_positions=positions,max_long_positions=positions,effective_max_positions_override=None)
    risk=replace(risk,fixed_stop_pct=policy.stop_loss_pct)
    leverage=LeverageConfig(**reference['leverage'])
    exec_cfg=ExecutionConfig(winner_pyramiding=policy,account_type='margin',dry_run=True,
        simulated_account_equity=4000.,leverage=leverage,simulated_margin_buying_power_multiplier=2.)
    return BacktestConfig(start_date=date(2025,1,1),end_date=date(2025,12,31),initial_equity=4000.,
        risk_config=risk,exec_config=exec_cfg,use_canonical_costs=True,
        winner_drawdown_controller_enabled=case['controller'],winner_daily_entry_enabled=case['daily'],
        margin_interest_rate_annual=reference['arguments']['margin_interest_annual'],
        trading_constraints=TradingConstraintConfig(account_type='margin',swing_only=False))


def run_case(case):
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.simulator import BacktestEngine

    root=DATA['root']; folder=root/'cases'/case['name']
    if (folder/'report.json').exists():
        return read(folder/'report.json')
    folder.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    with ReadOnlyReplay(folder).install():
        try:
            settings=selection_settings(DATA['plan']['reference'],case)
            signals=pd.read_parquet(root/'inputs'/f'signals-{selection_id(settings)}.parquet')
            cfg=configuration(DATA['plan']['reference'],case)
            atomic_json(folder/'configuration.json',dict(case=case,selection=settings.snapshot(),
                risk=asdict(cfg.risk_config),policy=asdict(cfg.exec_config.winner_pyramiding),
                leverage=asdict(cfg.exec_config.leverage),daily_entry=case['daily'],controller=case['controller']))
            def progress(done,total,day):
                atomic_json(folder/'progress.json',dict(status='RUNNING',completed=done,total=total,last_date=day,
                    elapsed_seconds=time.monotonic()-started))
            result=BacktestEngine(cfg).run(open_df=DATA['pivots']['open'],close=DATA['pivots']['close'],
                high=DATA['pivots']['high'],low=DATA['pivots']['low'],volume=DATA['pivots']['volume'],
                signals_df=signals,sector_map=DATA['sectors'],intraday_source=DATA['source'],
                winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=DATA['actions'])
            report=metrics(result,4000.)
            events=result.trade_events_df
            report.update(name=case['name'],family=case['family'],case=case,elapsed_seconds=time.monotonic()-started,
                selected_signals=len(signals),selected_symbols=int(signals.symbol.nunique()),
                sql_writes=False,provider_calls=0,broker_calls=0,independent_holdout=False,
                average_available_leverage_utilization=report['average_gross_equity_ratio']/2,
                rejection_counts=events.reason.dropna().value_counts().to_dict() if 'reason' in events else {})
            result.equity_curve.rename('equity').to_csv(folder/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(folder/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(folder/'trades.csv',index=False)
            events.to_csv(folder/'events.csv',index=False)
            previous=result.equity_curve.shift(1).fillna(4000.)
            report['quarters']={str(q):dict(start_equity=float(previous.loc[g.index[0]]),end_equity=float(g.iloc[-1]),
                mark_return_pct=float(100*(g.iloc[-1]/previous.loc[g.index[0]]-1)))
                for q,g in result.equity_curve.groupby(pd.DatetimeIndex(result.equity_curve.index).to_period('Q'))}
            if case['name']=='REFERENCE':
                original=read(REFERENCE/'report.json')
                for key in ('final_equity','return_pct','max_drawdown_pct','average_gross_capital','costs','margin_interest'):
                    if not np.isclose(report[key],original[key],rtol=1e-10,atol=1e-6):
                        raise ValueError(f'Reference reproduction differs: {key}={report[key]} expected={original[key]}')
                if report['closed_lot_trades']!=original['closed_lot_trades']:
                    raise ValueError('Reference trade count differs')
                report['reference_reproduction']='PASS_IDENTICAL_FINANCIAL_RESULTS'
            atomic_json(folder/'report.json',report)
            atomic_json(folder/'progress.json',dict(status=report['status'],completed=250,total=250))
            return report
        except Exception as exc:
            report=dict(name=case['name'],family=case['family'],case=case,status='FAILED',
                error_type=type(exc).__name__,error=str(exc),elapsed_seconds=time.monotonic()-started)
            (folder/'traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
            atomic_json(folder/'report.json',report)
            atomic_json(folder/'progress.json',report)
            return report


def consolidate(root):
    reports=[read(p) for p in sorted((root/'cases').glob('*/report.json'))]
    rows=[]
    for r in reports:
        keys=('name','family','status','final_equity','return_pct','max_drawdown_pct','closed_lot_trades',
            'win_pct','average_winning_pnl','average_losing_pnl','average_gross_capital','maximum_gross_capital',
            'average_gross_equity_ratio','average_available_leverage_utilization','costs','margin_interest',
            'selected_signals','selected_symbols','elapsed_seconds','error')
        row={k:r.get(k) for k in keys}
        for section in ('selection','risk','policy'):
            row.update({f'{section}.{k}':v for k,v in r['case'][section].items()})
        row.update(controller=r['case']['controller'],daily_entry=r['case']['daily'])
        rows.append(row)
    frame=pd.DataFrame(rows)
    frame.to_csv(root/'comparison.csv',index=False)
    valid=frame[frame.return_pct.notna() & frame.name.ne('REFERENCE')].copy() if 'return_pct' in frame else pd.DataFrame()
    if len(valid):
        valid['pareto']=[not ((valid.return_pct>=r.return_pct)&(valid.max_drawdown_pct>=r.max_drawdown_pct)&
            ((valid.return_pct>r.return_pct)|(valid.max_drawdown_pct>r.max_drawdown_pct))).any() for r in valid.itertuples()]
        valid.loc[valid.pareto].sort_values('return_pct',ascending=False).to_csv(root/'pareto.csv',index=False)
    return reports


def run(root,workers):
    plan=freeze_plan(root);verify_inputs(root);initialize_worker(root)
    atomic_json(root/'progress.json',dict(status='REFERENCE_RUNNING',completed=0,total=len(plan['cases'])))
    reference=run_case(plan['cases'][0])
    if reference.get('reference_reproduction')!='PASS_IDENTICAL_FINANCIAL_RESULTS':
        raise ValueError('Reference reproduction must pass before the cross-tests: '+str(reference))
    pending=[c for c in plan['cases'][1:] if not (root/'cases'/c['name']/'report.json').exists()]
    started=time.monotonic()
    with ProcessPoolExecutor(max_workers=workers,initializer=initialize_worker,initargs=(str(root),)) as pool:
        future_map={pool.submit(run_case,c):c['name'] for c in pending}
        for future in as_completed(future_map):
            report=future.result()
            reports=consolidate(root)
            atomic_json(root/'progress.json',dict(status='RUNNING',completed=len(reports),total=len(plan['cases']),
                failed=sum(r['status']=='FAILED' for r in reports),last=report['name'],last_status=report['status'],
                elapsed_seconds=time.monotonic()-started))
            LOG.info('CASE %s status=%s return=%s DD=%s (%d/%d)',report['name'],report['status'],
                report.get('return_pct'),report.get('max_drawdown_pct'),len(reports),len(plan['cases']))
    reports=consolidate(root)
    failed=[r['name'] for r in reports if r['status']=='FAILED']
    atomic_json(root/'report.json',dict(status='COMPLETED_EXPLORATORY' if not failed else 'COMPLETED_WITH_FAILED_CASES',
        completed=len(reports),total=len(plan['cases']),failed=failed,sql_writes=False,provider_calls=0,broker_calls=0,
        independent_holdout=False,full_live_parity=False,reference_reproduction=reference['reference_reproduction']))
    atomic_json(root/'progress.json',read(root/'report.json'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','reference','run','summarize','all'],required=True)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--workers',type=int,default=3,choices=range(1,5))
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try:
        if args.phase=='all':
            prepare(args.root)
            run(args.root,args.workers)
        elif args.phase=='prepare':prepare(args.root)
        elif args.phase=='reference':
            freeze_plan(args.root);verify_inputs(args.root);initialize_worker(args.root)
            report=run_case(cases()[0])
            print(json.dumps({k:report.get(k) for k in ('name','status','final_equity','max_drawdown_pct',
                'elapsed_seconds','error','reference_reproduction')},default=str))
        elif args.phase=='run':run(args.root,args.workers)
        else:consolidate(args.root)
    except Exception as exc:
        atomic_json(args.root/'progress.json',dict(status='FAILED',phase=args.phase,
            error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':main()
