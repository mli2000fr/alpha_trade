"""Offline trailing sensitivity on frozen TP/SL portfolios; never fit or contact a broker."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from functools import partial
import json
import logging
import math
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd

from execution_engine.models import IntentRole
from scripts.research import us_oracle_barrier_exit_grid as grid
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_oracle_barrier_comparison import freeze_candidates, read
from scripts.research.us_oracle_barrier_comparison_summary import portfolio_periods
from scripts.research.us_oracle_barrier_grid_summary import verify_trade_contract
from modelFactory.oracle.build_labels import nyse_sessions

PRIMARY_TRAIL = .10
SENSITIVITY_TRAILS = (.05, .15)
FIXED_PROFILE = ('TP20_SL10', .20, .10)
ACTIVATION_MODE = 'research_no_looser_than_initial_sl_next_session'


def activation_price(fill, stop, trailing_pct):
    """Native watcher replaces SL: delay activation until replacement cannot loosen it.

    The observed high activates only NEXT session. Thereafter a prior-session
    running maximum, not today's eventual high, determines the working stop.
    """
    values = (fill, stop, trailing_pct)
    if any(isinstance(v, bool) or not math.isfinite(v) for v in values) \
            or not 0 < trailing_pct < 1 or not 0 < stop < fill:
        raise ValueError('Invalid trailing anchor/fraction')
    return max(fill, float(np.nextafter(stop/(1-trailing_pct), np.inf)))


def trailing_protections(protection, trailing_pct):
    if trailing_pct is None:
        return protection  # OFF control must exactly preserve the old replay.
    if isinstance(trailing_pct, bool) or not math.isfinite(trailing_pct) or not 0 < trailing_pct < 1:
        raise ValueError('Invalid trailing fraction')
    signals, frame, orders = (protection.signals_df.copy(), protection.protection_frame.copy(),
                              protection.order_lifecycle_frame.copy())
    if not signals.empty:
        if not signals.symbol.is_unique or not signals.side.astype(str).str.lower().eq('buy').all():
            raise ValueError('Trailing study requires unique LONG signals')
        anchors = signals.apply(lambda r: activation_price(float(r.fill_price),
            float(r.replay_initial_stop_price), trailing_pct), axis=1)
        mapping = pd.Series(anchors.to_numpy(), index=signals.symbol)
        for f in (signals, frame):
            if not f.empty:
                f['replay_trailing_stop_pct'] = trailing_pct
                f['replay_trailing_activation_price'] = f.symbol.map(mapping)
                f['replay_trailing_activation_mode'] = ACTIVATION_MODE
        if not orders.empty:
            mask = orders.intent_role.eq(IntentRole.TRAILING_STOP)
            if not set(signals.symbol).issubset(set(orders.loc[mask, 'symbol'])):
                raise ValueError('Missing native trailing order')
            orders.loc[mask, 'trail_percent'] = 100*trailing_pct
    return replace(protection, signals_df=signals, protection_frame=frame, order_lifecycle_frame=orders,
        diagnostics=dict(protection.diagnostics, research_trailing_enabled=True,
            research_trailing_pct=trailing_pct, research_trailing_activation_mode=ACTIVATION_MODE,
            research_current_high_only_effective_next_session=True))


class TrailingGridLedger(grid.GridLedger):
    def __init__(self, *args, trailing_pct, **kwargs):
        if trailing_pct is not None and (isinstance(trailing_pct, bool)
                or not math.isfinite(trailing_pct) or not 0 < trailing_pct < 1):
            raise ValueError('Invalid trailing fraction')
        self.trailing_pct = trailing_pct
        super().__init__(*args, **kwargs)

    def _build_entry_protections(self, phase3, *, execution_config):
        original = super()._build_entry_protections(phase3, execution_config=execution_config)
        return trailing_protections(original, self.trailing_pct)


def planned_cases(smoke=False):
    name, tp, sl = FIXED_PROFILE
    if smoke:
        return [(2026, 10, arm, name, tp, sl, trail)
                for arm in ('OLD_TERMINAL_LONG', 'NEW_BARRIER_LONG') for trail in (None, PRIMARY_TRAIL)]
    return [(y, n, a, name, tp, sl, trail) for y in (2025, 2026) for n in (10, 20, 50)
            for a in ('OLD_TERMINAL_LONG','NEW_BARRIER_LONG')
            for trail in (PRIMARY_TRAIL, *SENSITIVITY_TRAILS)]


def key(case):
    return grid.case_key(case[:6]) + ('-TRAIL_OFF' if case[6] is None else f'-TRAIL{case[6]*100:g}')


def require_long_trades(trades):
    if trades.empty:
        return
    name = 'direction' if 'direction' in trades else 'side' if 'side' in trades else None
    if name is None or not trades[name].astype(str).str.lower().isin(['long','buy']).all():
        raise ValueError('Missing side or unexpected SHORT portfolio')


def run_case(case, output):
    y, n, arm, profile, tp, sl, trail = case
    root = Path(output)/key(case)
    root.mkdir(parents=True, exist_ok=True)
    if (root/'case-report.json').exists():
        previous = read(root/'case-report.json')
        if previous['status'] != 'FAILED':
            return previous
    cache = grid._CACHE
    candidates = freeze_candidates(cache['scores'].loc[cache['scores'].date.dt.year.eq(y)], n, arm)
    required = set(candidates.symbol) | {'SPY', 'VMRK'}
    prices = cache['prices'].loc[cache['prices'].symbol.isin(required)]
    if required-{'SPY'}-set(cache['sectors']):
        raise ValueError('Unqualified candidate sectors')
    calendar = cache['calendar']
    cutoff = '2025-12-31' if y == 2025 else '2026-09-03'
    final = calendar[calendar <= cutoff][-1]
    end = calendar[calendar.get_loc(final)+21]
    base = dict(year=y, count=n, arm=arm, profile=profile, tp_pct=tp, sl_pct=sl,
        trailing_pct=trail, side='LONG', decision_cutoff=cutoff, terminal_date=str(end.date()))
    attempts, started = [], time.monotonic()
    for policy in ('STRICT', 'UNVALUED_RECEIVABLE'):
        destination = root/policy
        destination.mkdir(parents=True, exist_ok=True)
        frames = {k: prices.pivot(index='date', columns='symbol', values=c).reindex(calendar)
            for k,c in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
        try:
            with (destination/'stderr.log').open('a', encoding='utf-8') as log:
                logging.basicConfig(level=logging.WARNING, stream=log, force=True)
                with redirect_stderr(log), redirect_stdout(log):
                    result = run_portfolio(frames=frames, scores=candidates, sectors=cache['sectors'],
                        macro=ArchivedMacro(cache['macro']), market_config=cache['market'],
                        policy='selected', variant='CURRENT_NO_EXPIRY', output=destination,
                        start_date=f'{y}-01-01', end_date=str(end.date()), decision_end_date=str(final.date()),
                        quality=prices[['date','symbol','is_filled','instrument_id']],
                        ledger_factory=partial(TrailingGridLedger, tp_pct=tp, sl_pct=sl,
                                               trailing_pct=trail, cash_policy=policy),
                        expiry_open_sessions=20,
                        protection_options=dict(take_profit_enabled=True,trailing_enabled=trail is not None))
        except Exception as exc:
            attempts.append(dict(policy=policy,error_type=type(exc).__name__,error=str(exc)))
            atomic_json(root/'attempts.json', attempts)
            if policy == 'STRICT' and 'Unqualified cash-in-lieu' in str(exc):
                continue
            result = dict(base,status='FAILED',failures=attempts,elapsed_seconds=time.monotonic()-started)
            atomic_json(root/'case-report.json',result)
            return result
        trades = pd.read_parquet(destination/'trades.parquet')
        require_long_trades(trades)
        if abs(result['cash_reconciliation_error']) > 1e-6:
            raise ValueError('Cash does not reconcile')
        result.update(base, cash_policy=policy, attempts=attempts, output=str(destination),
            periods=portfolio_periods(pd.read_parquet(destination/'daily.parquet'),y,cutoff),
            exit_reasons=trades.exit_reason.value_counts().to_dict() if not trades.empty else {},
            elapsed_seconds=time.monotonic()-started,
            status='COMPLETED' if result['account_wealth_complete'] else 'SCENARIO_UNVALUED_RECEIVABLE')
        atomic_json(root/'case-report.json',result)
        return result


def verify_baseline(inputs, baseline):
    protocol, report = read(baseline/'protocol.json'), read(baseline/'report.json')
    if report['status'] != 'COMPLETED' or not report['input_hashes_verified_after_all_runs'] \
            or read(baseline/'summary.json')['status'] != 'ALL_CASES_AND_TRADE_CONTRACTS_VERIFIED':
        raise ValueError('Unaudited/incomplete OFF baseline')
    if digest(inputs/'prepared.json') != protocol['prepared_sha256'] \
            or Path(protocol['inputs']).resolve() != inputs.resolve():
        raise ValueError('Baseline inputs differ')
    verify_hashes(Path('.'), protocol['source_hashes'])
    verify_hashes(Path('.'), read(baseline/'summary.json')['sources'])
    expected={(y,n,a,p) for y in (2025,2026) for n in (10,20,50)
              for a in ('OLD_TERMINAL_LONG','NEW_BARRIER_LONG') for p,_,_ in grid.PROFILES}
    actual={(r['year'],r['count'],r['arm'],r['profile']) for r in report['portfolios']}
    if actual != expected or len(report['portfolios']) != len(expected):
        raise ValueError('Invalid baseline case coverage')
    return report


def report_results(output, reports, total, verified=False, audited=False):
    complete = sum(r['status']=='COMPLETED' for r in reports)
    reserved = sum(r['status']=='SCENARIO_UNVALUED_RECEIVABLE' for r in reports)
    failed = sum(r['status']=='FAILED' for r in reports)
    status = ('RUNNING' if len(reports)<total else 'VERIFYING_INPUTS' if not verified else
              'PARTIAL_FAILED' if failed else 'AUDITING_TRADES' if not audited else
              'COMPLETED' if complete==total else 'COMPLETED_WITH_RESERVES')
    result = dict(status=status,finished=len(reports),total=total,complete=complete,
        reserved=reserved,failed=failed,portfolios=reports,input_hashes_verified=verified,trade_contracts_audited=audited,
        training=False,sql_writes=False,broker_orders=False,production_changed=False,promotion=False)
    atomic_json(output/'report.json',result)
    atomic_json(output/'progress.json',{k:v for k,v in result.items() if k!='portfolios'})
    return result


def validate_trailing_contract(trades, tp, sl, trail, calendar):
    check = verify_trade_contract(trades,tp,sl,calendar)
    if trades.empty or trail is None:
        return check
    if not np.isclose(trades.replay_trailing_stop_pct,trail,atol=1e-12).all():
        raise ValueError('Executed trailing fraction differs')
    expected = [activation_price(float(r.entry_price),float(r.replay_initial_stop_price),trail)
                for r in trades.itertuples()]
    if not np.isclose(trades.replay_trailing_activation_price,expected,atol=1e-7,rtol=1e-8).all():
        raise ValueError('Unsafe/different trailing activation anchor')
    if not trades.replay_trailing_activation_mode.eq(ACTIVATION_MODE).all():
        raise ValueError('Wrong trailing activation convention')
    # Intraday trailing fills cannot be below original SL; opening gaps CAN.
    intraday = trades.exit_reason.eq('trailing_stop')
    if trades.loc[intraday,'exit_price'].lt(trades.loc[intraday,'replay_initial_stop_price']-1e-7).any():
        raise ValueError('Trailing loosened the original SL')
    check['trailing_exits'] = int(trades.exit_reason.astype(str).str.startswith('trailing_stop').sum())
    return check


def summarize(output, baseline):
    protocol, report = read(output/'protocol.json'),read(output/'report.json')
    if report['status'] not in ('AUDITING_TRADES','COMPLETED','COMPLETED_WITH_RESERVES') or not report['input_hashes_verified']:
        raise ValueError('Trailing cases incomplete/unverified')
    base = verify_baseline(Path(protocol['inputs']),baseline)
    off={(r['year'],r['count'],r['arm'],r['profile']):r for r in base['portfolios']}
    actual=[(r['year'],r['count'],r['arm'],r['profile'],r['tp_pct'],r['sl_pct'],r['trailing_pct'])
            for r in report['portfolios']]
    if set(actual)!=set(map(tuple,protocol['cases'])) or len(actual)!=len(protocol['cases']):
        raise ValueError('Missing/duplicate trailing cases')
    calendar=nyse_sessions(pd.Timestamp('2024-01-01').date(),pd.Timestamp('2026-10-07').date())
    rows,checks,hashes=[],[],{}
    for r in sorted(report['portfolios'],key=lambda r:(r['trailing_pct'] or 0,r['year'],r['count'],r['profile'],r['arm'])):
        b=off[(r['year'],r['count'],r['arm'],r['profile'])]
        destination=Path(r['output'])
        trades=pd.read_parquet(destination/'trades.parquet')
        check=validate_trailing_contract(trades,r['tp_pct'],r['sl_pct'],r['trailing_pct'],calendar)
        checks.append(dict(year=r['year'],count=r['count'],arm=r['arm'],profile=r['profile'],
                           trailing_pct=r['trailing_pct'],**check))
        if r['trailing_pct'] is None:
            for measure in ('return_pct','max_drawdown','closed_positions'):
                if abs(r[measure]-b[measure])>1e-9:
                    raise ValueError('OFF control changed the baseline portfolio')
            pd.testing.assert_frame_equal(pd.read_parquet(destination/'daily.parquet'),
                                           pd.read_parquet(Path(b['output'])/'daily.parquet'))
        for filename in ('trades.parquet','daily.parquet'):
            path=destination/filename
            hashes[str(path)]=digest(path)
        rows.append(dict(year=r['year'],count=r['count'],arm=r['arm'],profile=r['profile'],
            trailing_pct=r['trailing_pct'],return_pct=r['return_pct'],off_return=b['return_pct'],
            delta_return=r['return_pct']-b['return_pct'],max_drawdown=r['max_drawdown'],
            off_max_drawdown=b['max_drawdown'],delta_drawdown=r['max_drawdown']-b['max_drawdown'],
            trades=len(trades),trailing_exits=check.get('trailing_exits',0),status=r['status']))
    summary=dict(status='ALL_TRAILING_CONTRACTS_VERIFIED',rows=rows,checks=checks,sources=hashes,
        complete_wealth=all(r['account_wealth_complete'] for r in report['portfolios']),
        max_cash_error=max(abs(r['cash_reconciliation_error']) for r in report['portfolios']),
        primary_trailing_pct=PRIMARY_TRAIL,comparison_is_exploratory=True,promotion=False)
    atomic_json(output/'summary.json',summary)
    lines=['# Trailing — comparaison contre OFF', '',
        'LONG uniquement. Rendements de cohortes closes, pas une promotion ni un optimum validé.',
        'TP20/SL10 fixé par l’utilisateur ; trail 10 % primaire, sensibilités 5 % / 15 %.', '',
        '| Année | N | Modèle | Profil | Trail | OFF | Avec | Delta pp | DD OFF | DD avec |',
        '| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        lines.append(f"| {r['year']} | {r['count']} | {r['arm']} | {r['profile']} | "
            f"{r['trailing_pct'] or 0:.0%} | {r['off_return']:+.2%} | {r['return_pct']:+.2%} | "
            f"{r['delta_return']*100:+.2f} | {r['off_max_drawdown']:.2%} | {r['max_drawdown']:.2%} |")
    (output/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return summary


def run(inputs, baseline, output, workers=3, smoke=False):
    if workers<1 or workers>3:
        raise ValueError('Use one to three research workers')
    output.mkdir(parents=True,exist_ok=True)
    verify_baseline(inputs,baseline)
    prepared=read(inputs/'prepared.json')
    verify_hashes(inputs,prepared['files'])
    lineage=read(inputs/'input-protocol.json')['source_hashes']
    verify_hashes(Path('.'),lineage)
    paths=[Path(__file__),Path(grid.__file__),Path('config.yaml'),
        Path('scripts/research/us_concentrated_fixed_stop.py'),
        Path('scripts/research/us_concentrated_live_portfolio.py'),
        Path('scripts/research/us_concentrated_contract_audit.py'),
        Path('scripts/research/us_oracle_merger_ledger.py'),
        Path('scripts/research/us_oracle_barrier_grid_summary.py'),
        Path('scripts/research/us_oracle_barrier_comparison.py'),
        Path('scripts/research/us_concentrated_historical_tapes.py'),
        Path('backtesting/oracle_portfolio_ledger.py'),Path('backtesting/oracle_portfolio_session.py'),
        Path('backtesting/execution_lifecycle_replay.py'),Path('backtesting/protection_watcher_replay.py'),
        Path('backtesting/exit_lifecycle_replay.py'),Path('backtesting/microstructure.py'),
        Path('backtesting/simulator.py')]
    hashes={str(p):digest(p) for p in paths}
    cases=planned_cases(smoke)
    protocol=dict(inputs=str(inputs),prepared_sha256=digest(inputs/'prepared.json'),
        baseline=str(baseline),baseline_report_sha256=digest(baseline/'report.json'),
        baseline_summary_sha256=digest(baseline/'summary.json'),source_hashes=hashes,
        cases=cases,smoke=smoke,primary_trailing_pct=PRIMARY_TRAIL,sensitivity=SENSITIVITY_TRAILS,
        fixed_tp_sl_profile=FIXED_PROFILE,
        activation=ACTIVATION_MODE,activation_formula='max(fill, initial_sl/(1-trail))',
        trail_anchor='highest observed high through PREVIOUS session; entry included',
        same_day_high_never_changes_working_stop=True,side='LONG',
        entry='J+1 open',expiry='21st session open including entry',
        native_atr_sizing_unchanged=True,frozen_models=True,promotion=False,
        sql_writes=False,broker_orders=False)
    canonical=json.loads(json.dumps(protocol,default=str))
    if (output/'protocol.json').exists() and read(output/'protocol.json')!=canonical:
        raise ValueError('Resume protocol changed; use a new output')
    atomic_json(output/'protocol.json',protocol)
    reports,pending=[],[]
    for case in cases:
        path=output/key(case)/'case-report.json'
        if path.exists() and read(path)['status']!='FAILED':
            reports.append(read(path))
        else:
            pending.append(case)
    report_results(output,reports,len(cases))
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name]='1'
    with ProcessPoolExecutor(max_workers=workers,initializer=grid.worker_init,initargs=(str(inputs),)) as executor:
        futures={executor.submit(run_case,c,str(output)):c for c in pending}
        for future in as_completed(futures):
            case=futures[future]
            try:
                r=future.result()
            except Exception as exc:
                r=dict(year=case[0],count=case[1],arm=case[2],profile=case[3],trailing_pct=case[6],
                       tp_pct=case[4],sl_pct=case[5],status='FAILED',error_type=type(exc).__name__,error=str(exc))
                folder=output/key(case)
                folder.mkdir(parents=True,exist_ok=True)
                atomic_json(folder/'case-report.json',r)
            reports.append(r)
            report_results(output,reports,len(cases))
            message=f'{len(reports)}/{len(cases)} {key(case)} {r["status"]}'
            print(message,flush=True)
            with (output/'events.log').open('a',encoding='utf-8') as log:
                log.write(message+'\n')
    verify_hashes(Path('.'),hashes)
    verify_hashes(Path('.'),lineage)
    verify_hashes(inputs,prepared['files'])
    for file,checksum in [('report.json',protocol['baseline_report_sha256']),
                          ('summary.json',protocol['baseline_summary_sha256'])]:
        if digest(baseline/file)!=checksum:
            raise ValueError('OFF baseline changed while running')
    result=report_results(output,reports,len(cases),verified=True)
    if result['status']=='AUDITING_TRADES':
        summarize(output,baseline)
        result=report_results(output,reports,len(cases),verified=True,audited=True)
    elif result['status']=='PARTIAL_FAILED':
        raise RuntimeError(f'Trailing campaign: {result["failed"]} failed cases; see report.json')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    try:
        run(**vars(args))
    except Exception as exc:
        if args.output.exists():
            atomic_json(args.output/'failure.json',dict(error_type=type(exc).__name__,error=str(exc)))
            current=read(args.output/'progress.json') if (args.output/'progress.json').exists() else {}
            atomic_json(args.output/'progress.json',dict(current,status='FAILED',error=str(exc)))
        raise
