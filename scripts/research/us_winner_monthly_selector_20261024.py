"""Monthly 30/50-session mark-to-market profile selection, TOP20 2020-2024.

Six continuous shadow accounts, two adaptive accounts and two fixed controls.
Native risk/execution, run-local adapters, READ ONLY input snapshots, no orders.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import logging
import math
import os

import numpy as np
import pandas as pd

from scripts.research import us_winner_top20_capacity_2017_20261024 as capacity
from scripts.research import us_winner_monthly_inputs_20261024 as inputs
from scripts.research.us_winner_sl3_tp7_tr3_open11_audit_20261023 import scalar_exit, near
from scripts.research.us_winner_bottom_rank_filter_audit_20261022 import event_cash
from execution_engine.models import ExecutionTarget
from execution_engine.winner_plans import plan_from_target
from common.winner_pyramiding import aware
import backtesting.winner_intraday as native

ROOT = Path('artifacts/research/us_winner_monthly_selector/20261024-v1')
DOC = Path('doc/ml/winner_selection_mensuelle_30_50_20261024.md')
TEST = Path('tests/test_us_winner_monthly_selector_20261024.py')
PROFILES = [
    dict(name='SL5_TROFF_H20_TPOFF', stop_loss_pct=.05, trailing_stop_pct=None, horizon_sessions=20, take_profit_pct=None),
    dict(name='SL5_TR15_H20_TPOFF', stop_loss_pct=.05, trailing_stop_pct=.15, horizon_sessions=20, take_profit_pct=None),
    dict(name='SL5_TROFF_H20_TP20', stop_loss_pct=.05, trailing_stop_pct=None, horizon_sessions=20, take_profit_pct=.20),
    dict(name='SL3_TR10_H10_TP7', stop_loss_pct=.03, trailing_stop_pct=.10, horizon_sessions=10, take_profit_pct=.07),
    dict(name='SL5_TR15_H15_TPOFF', stop_loss_pct=.05, trailing_stop_pct=.15, horizon_sessions=15, take_profit_pct=None),
    dict(name='SL7_TROFF_H20_TPOFF', stop_loss_pct=.07, trailing_stop_pct=None, horizon_sessions=20, take_profit_pct=None),
]
CATALOG = {p['name']: p for p in PROFILES}
REFERENCE = PROFILES[0]['name']
ARMS = ['SHADOW_'+p['name'] for p in PROFILES]+['MONTHLY_30', 'MONTHLY_50', 'FIXED_REFERENCE', 'FIXED_TRAILING15']


def profile_policy(config, name):
    return replace(config.winner_pyramiding, **{k: v for k, v in CATALOG[name].items() if k != 'name'})


def configuration(protocol, start):
    # Admission uses the smallest candidate SL so a fundable SL3 plan is not
    # prematurely rejected by a SL5 shadow. Every target is then resized under
    # its actual chosen SL, and reapproved again by the native risk module.
    cfg = capacity.grid.configuration(protocol, 2020, dict(PROFILES[3], trailing_stop_pct=None, horizon_sessions=20, take_profit_pct=None))
    risk = replace(cfg.risk_config, max_positions=20, max_long_positions=20, concentration_max_trades_per_symbol=10)
    wp = replace(cfg.exec_config.winner_pyramiding, initial_position_fraction=1., reinforcement_enabled=False)
    return replace(cfg, start_date=start, end_date=inputs.END, risk_config=risk,
                   exec_config=replace(cfg.exec_config, winner_pyramiding=wp))


def choose_profile(curves, cutoff, window, previous=REFERENCE):
    """Only N realized daily portfolio RETURNS ending at cutoff (N+1 closes)."""
    scores, dates = {}, {}
    for name in CATALOG:
        series = curves[name].copy()
        series.index = pd.to_datetime(series.index).normalize()
        if series.index.duplicated().any():
            raise ValueError('Duplicate shadow valuation dates')
        series = series.sort_index().loc[:pd.Timestamp(cutoff)].tail(window+1)
        if len(series) != window+1 or not np.isfinite(series.to_numpy(float)).all() or (series <= 0).any():
            raise ValueError('Insufficient comparable shadow valuations for '+name)
        dates[name] = tuple(series.index)
        scores[name] = float(series.iloc[-1]/series.iloc[0]-1)
    if len(set(dates.values())) != 1:
        raise ValueError('Shadow calendars differ; no cherry-picking dates by profile')
    best = max(scores.values())
    ties = [name for name in CATALOG if abs(scores[name]-best) <= 1e-12]
    selected = previous if previous in ties else ties[0]
    return dict(profile=selected, scores=scores, window=window,
                window_start=str(next(iter(dates.values()))[0].date()),
                cutoff=str(next(iter(dates.values()))[-1].date()))


def monthly_decisions(curves, window):
    schedule = [s for s in inputs.sessions(start=inputs.START) if s.session_date <= inputs.END]
    result, previous = {}, REFERENCE
    months = sorted({s.session_date.strftime('%Y-%m') for s in schedule if s.session_date >= inputs.START})
    for month in months:
        first = min((s for s in schedule if s.session_date.strftime('%Y-%m') == month),
                    key=lambda s: s.session_date)
        prior = max((s for s in schedule if s.session_date < first.session_date), key=lambda s: s.session_date)
        row = choose_profile(curves, prior.session_date, window, previous)
        if pd.Timestamp(row['cutoff']) != pd.Timestamp(prior.session_date):
            raise ValueError('Missing latest shadow close at monthly cutoff')
        row.update(month=month, first_session=str(first.session_date),
                   available_at=prior.close_at_utc.isoformat(), effective_open=first.open_at_utc.isoformat())
        if aware(row['available_at']) >= aware(row['effective_open']):
            raise ValueError('Decision uses information beyond first monthly opening')
        result[month] = row; previous = row['profile']
    return result


def resize_target(target, config, policy):
    price = float(target.entry_price)
    fee = max(policy.fee, .0008)
    full = min(math.floor(float(target.risk_budget_dollars)/(price*(policy.stop_loss_pct+2.05*fee))),
               int(target.target_shares))
    # Admission used the smallest SL and already enforced the actual signal
    # equity/weight cap. Preserve that exact ceiling, not a recomputed deposit.
    weight = target.target_weight*full/target.target_shares if target.target_shares else 0.
    return replace(target, target_shares=max(full, 0), target_weight=weight)


def unfilled_rearm_allowed(state, now):
    return (not state['lots'] and not state.get('initial_attempted') and not state['operations']
            and state['status'] not in ('CLOSED', 'EXPIRED', 'CANCELED')
            and aware(now) < aware(state['entry_expires_at']))


@contextmanager
def campaign_adapter(config, selector):
    """Freeze selection per actual entry; rearm only untouched pending plans.

    Never mutate the policy of a funded/attempted campaign or reset its expiry.
    Process-local classes and target wrappers, not production source edits.
    """
    old_stage, old_runtime = native.stage_targets, native.WinnerCampaignRuntime
    metadata = {}

    def name_at(now):
        return selector(pd.Timestamp(now).tz_convert('America/New_York').date())

    def register(store, name, originals):
        for row in store.rows(active_only=False):
            state = row['state']
            if state['campaign_id'] not in metadata:
                metadata[state['campaign_id']] = dict(profile=name, signal_date=state['signal_date'],
                    policy=deepcopy(state['policy']), entry_expires_at=state['entry_expires_at'],
                    admission_target=asdict(originals[(state['target']['risk_run_id'], state['symbol'])]))

    def stage(store, targets, cfg, exec_run_id, *, now=None, calendar=None):
        name = name_at(now); policy = profile_policy(cfg, name)
        originals = {(t.risk_run_id, t.symbol): t for t in targets}
        resized = [resize_target(t, cfg, policy) for t in targets]
        resized = [t for t in resized if t.target_shares >= 1]
        result = old_stage(store, resized, replace(cfg, winner_pyramiding=policy), exec_run_id, now=now, calendar=calendar)
        register(store, name, originals)
        return result

    class MonthlyRuntime(old_runtime):
        def run(self, records):
            name = name_at(self.now)
            for record in records:
                current = self.store.get(record['state']['campaign_id'])
                state = current['state']
                if not unfilled_rearm_allowed(state, self.now) or metadata[state['campaign_id']]['profile'] == name:
                    continue
                original_expiry = state['entry_expires_at']
                state['status'] = 'CANCELED'; self.store.save(state, current['version'])
                target = ExecutionTarget(**metadata[state['campaign_id']]['admission_target'])
                origin = target.risk_run_id.split('|monthly:')[0]
                target = replace(target, risk_run_id=origin+'|monthly:'+self.now.strftime('%Y-%m')+'|'+name)
                stage(self.store, [target], self.config, state['exec_run_id'], now=self.now,
                      calendar=capacity.grid.whole.CachedCalendar(capacity.grid.calendar()))
                new = [r['state'] for r in self.store.rows() if r['state']['symbol'] == state['symbol']]
                if new and new[0]['entry_expires_at'] != original_expiry:
                    raise ValueError('Monthly rearm must not extend original signal expiry')
            return super().run(self.store.rows())

        def book_buy(self, intent, operation, raw):
            super().book_buy(intent, operation, raw)
            if self.state['lots']:
                item = metadata[self.state['campaign_id']]
                item.update(first_fill_at=self.state['first_fill_at'], symbol=self.state['symbol'], due_open=self.state['due_open'])
                entry_name = name_at(aware(self.state['first_fill_at']))
                if item['profile'] != entry_name:
                    raise ValueError('Actual entry policy differs from monthly selection')

    native.stage_targets, native.WinnerCampaignRuntime = stage, MonthlyRuntime
    try:
        yield metadata
    finally:
        native.stage_targets, native.WinnerCampaignRuntime = old_stage, old_runtime


def audit(result, summary, metadata, tape):
    events = result.trade_events_df
    cash, fees, held = event_cash(events[events.event.notna()])
    near(cash, summary['settled_cash']); near(fees, summary['costs'])
    if held != {p['symbol']: p['qty'] for p in summary['open_positions']}:
        raise ValueError('Holdings mismatch')
    near(summary['final_equity'], cash+sum(p['qty']*p['mark'] for p in summary['open_positions']))
    if summary['dividends_accrued'] or summary['unsettled_cash']:
        raise ValueError('Reserved accounting lifecycle unexpectedly used')
    checks = 0
    for t in result.closed_trades_df.itertuples():
        item = metadata[t.campaign_id]; policy = item['policy']
        day = pd.Timestamp(t.entry_date).tz_convert('America/New_York').date()
        due_sessions = [s for s in inputs.sessions(start=day) if s.session_date >= day]
        due = pd.Timestamp(due_sessions[policy['horizon_sessions']].open_at_utc)
        path = tape.path(t.symbol, pd.Timestamp(t.entry_date), pd.Timestamp(t.exit_date))
        got = scalar_exit(path, pd.Timestamp(t.entry_date), t.entry_price, due,
            sl=policy['stop_loss_pct'], tp=policy['take_profit_pct'], trail=policy['trailing_stop_pct'])
        if got is None or got[0] != t.exit_date or got[2] != t.exit_reason:
            raise ValueError('Scalar exit mismatch: '+str((t.symbol, got, t.exit_reason)))
        near(got[1], t.exit_price)
        near(t.pnl, t.quantity*(t.exit_price-t.entry_price)-t.entry_fees-t.exit_fees+t.dividends)
        checks += 1
    filled = {(m['symbol'], pd.Timestamp(m['first_fill_at'])): m for m in metadata.values() if m.get('first_fill_at')}
    days = sorted(tape.schedule); idx = {d: i for i, d in enumerate(days)}
    buys = events[events.event.eq('BUY_FILL')]
    for b in buys.itertuples():
        stamp = pd.Timestamp(b.time); day = stamp.tz_convert('America/New_York').date()
        if (b.symbol, stamp) not in filled:
            raise ValueError('Unrecorded entry policy')
        f = tape.day(b.symbol, day).reset_index(drop=True)
        positions = np.flatnonzero(f.bar_timestamp.eq(stamp))
        if len(positions) != 1 or positions[0] < 3:
            raise ValueError('No complete confirmation at entry')
        i = int(positions[0]); prior = tape.day(b.symbol, days[idx[day]-1]); level = prior.high.max()
        if not (f.close.iloc[i-3] <= level and f.close.iloc[i-2] > level and f.close.iloc[i-1] > level):
            raise ValueError('False breakout')
        near(b.price, f.open.iloc[i]); near(b.costs, b.quantity*b.price*.0008)
    capacity.audit_held_coverage(result, summary['coverage_gaps'], inputs.END)
    curve = result.intraday_equity_curve; values = np.r_[4000., curve.equity.to_numpy()]
    near(summary['max_drawdown_pct'], 100*np.min(values/np.maximum.accumulate(values)-1))
    return dict(status='PASS_SCALAR_CASH_FEES_ENTRIES_FROZEN_POLICIES', exits=checks, buys=len(buys))


def run_case(protocol, arm, tape, selector, start):
    folder = ROOT/'cases'/arm; folder.mkdir(parents=True, exist_ok=True)
    if (folder/'report.json').exists():
        report = capacity.read_json(folder/'report.json')
        capacity.grid.base.verify({str(folder/n): h for n, h in report['files'].items()})
        return report
    cfg = configuration(protocol, start)
    signals = tape.cohort[['date', 'symbol', 'rank', 'selected']].rename(columns={'date': 'trade_date'}).copy()
    prior = max(d for d in tape.schedule if d < start)
    signals = signals[signals.trade_date.ge(pd.Timestamp(prior))]; signals['side'] = 'long'
    def progress(done, total, day):
        capacity.grid.atomic_json(ROOT/'progress.json', dict(status='RUNNING', arm=arm,
            completed_runs=sum((ROOT/'cases'/a/'report.json').exists() for a in ARMS), total_runs=len(ARMS),
            completed_sessions=done, total_sessions=total, last_date=day,
            updated_at_utc=datetime.now(timezone.utc).isoformat()))
    with capacity.grid.runtime_adapter(start.year, arm), capacity.corrected_runtime(), campaign_adapter(cfg.exec_config, selector) as metadata:
        result = capacity.grid.base.BacktestEngine(cfg).run(open_df=tape.pivots['open'], close=tape.pivots['close'],
            high=tape.pivots['high'], low=tape.pivots['low'], volume=tape.pivots['volume'], signals_df=signals,
            sector_map=tape.sectors, intraday_source=tape, winner_research_assumptions=True,
            winner_progress=progress, winner_corporate_actions=tape.actions.to_dict('records'))
    summary = capacity.grid.metrics(result, 4000.)
    checks = audit(result, summary, metadata, tape)
    summary['outer_admission_policy'] = summary.pop('policy')
    summary['policy_mode'] = 'Actual entry policy per campaign; outer minimum-SL policy is admission sizing only'
    result.equity_curve.to_frame().to_parquet(folder/'equity-daily.parquet')
    result.intraday_equity_curve.to_parquet(folder/'equity-5m.parquet', index=False)
    result.closed_trades_df.to_parquet(folder/'trades.parquet', index=False)
    result.trade_events_df.to_csv(folder/'events.csv', index=False)
    capacity.grid.atomic_json(folder/'campaign-policies.json', metadata)
    summary.update(arm=arm, start=str(start), end=str(inputs.END), audit=checks,
        future_coverage_selection_bias=True, independent_holdout=False,
        files={p.name: capacity.grid.base.digest(p) for p in folder.iterdir() if p.is_file() and p.name != 'report.json'})
    capacity.grid.base.save_new(folder/'report.json', summary)
    return summary


def annual_results(arm):
    folder = ROOT/'cases'/arm
    daily = pd.read_parquet(folder/'equity-daily.parquet').iloc[:, 0]
    daily.index = pd.to_datetime(daily.index)
    bars = pd.read_parquet(folder/'equity-5m.parquet')
    bars['date'] = bars.timestamp.dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    trades = pd.read_parquet(folder/'trades.parquet')
    rows = []
    for year in range(2020, 2025):
        year_values = daily[daily.index.year == year]
        prior = daily[daily.index < pd.Timestamp(year, 1, 1)]
        opening = float(prior.iloc[-1]) if len(prior) else 4000.
        b = bars[bars.date.dt.year.eq(year)]
        eq = np.r_[opening, b.equity.to_numpy()]
        closed = trades[pd.to_datetime(trades.exit_date, utc=True).dt.tz_convert('America/New_York').dt.year.eq(year)] if len(trades) else trades
        pnl = closed.pnl if len(closed) else pd.Series(dtype=float)
        rows.append(dict(arm=arm, year=year, starting_equity=opening, final_equity=float(year_values.iloc[-1]),
            return_pct=100*(year_values.iloc[-1]/opening-1), max_drawdown_pct=100*np.min(eq/np.maximum.accumulate(eq)-1),
            average_gross_capital=float(b.gross.mean()), average_gross_equity_pct=float((b.gross/b.equity).mean()*100),
            trades=len(pnl), win_pct=100*float(pnl.gt(0).mean()) if len(pnl) else None,
            winning_pnl=float(pnl[pnl > 0].sum()), losing_pnl=float(pnl[pnl < 0].sum())))
    return rows


def prepare():
    if (ROOT/'protocol.json').exists():
        p = capacity.read_json(ROOT/'protocol.json'); capacity.grid.base.verify(p['sources']); return p
    p = deepcopy(capacity.read_json(capacity.ROOT/'protocol.json'))
    capacity.grid.base.verify(p['sources'])
    paths = [Path(__file__), Path(inputs.__file__), DOC, TEST, capacity.ROOT/'protocol.json',
             inputs.ARCHIVE/'scores.json', inputs.ARCHIVE/'top100.parquet']
    p['sources'].update({str(path): capacity.grid.base.digest(path) for path in paths})
    p.update(experiment='TOP20_MONTHLY_MTM_30_50_2020_2024', profiles=PROFILES, windows=[30, 50],
        total_runs=len(ARMS), shadow_start=str(inputs.SHADOW_START), start=str(inputs.START), end=str(inputs.END),
        monthly_score='Trailing N close-to-close portfolio returns, includes unrealized positions, after fees',
        common_initial_capital=4000., annual_reset=False, TOP=20,
        policy_freeze='Actual entry month; unattempted pending plan may rearm without changing original expiry',
        ranking='Largest trailing portfolio return; exact tie retains prior profile, then catalog order',
        independent_holdout=False, no_training=True, provider_calls=0, SQL_writes=False, production_changed=False,
        sources_are_previously_examined=True, future_coverage_selection_bias=True)
    ROOT.mkdir(parents=True, exist_ok=True); capacity.grid.base.save_new(ROOT/'protocol.json', p)
    return p


def run():
    ROOT.mkdir(parents=True, exist_ok=True)
    try:
        with capacity.grid.run_lock(ROOT), capacity.safe_reads():
            p = prepare()
            if (ROOT/'report.json').exists():
                return
            import requests
            def forbidden(*_a, **_k):
                raise RuntimeError('No provider/broker/LLM HTTP requests in monthly experiment')
            requests.Session.request = forbidden
            capacity.grid.atomic_json(ROOT/'progress.json', dict(status='INPUT_PREPARATION', completed_runs=0, total_runs=10))
            inputs.prepare(ROOT)
            tape = inputs.Tape(ROOT)
            for profile in PROFILES:
                name = profile['name']
                run_case(p, 'SHADOW_'+name, tape, lambda _d, n=name: n, inputs.SHADOW_START)
                tape.month.cache_clear()
            curves = {pr['name']: pd.read_parquet(ROOT/'cases'/('SHADOW_'+pr['name'])/'equity-daily.parquet').iloc[:, 0] for pr in PROFILES}
            for window in [30, 50]:
                decisions = monthly_decisions(curves, window)
                path = ROOT/f'decisions-{window}.json'
                if path.exists():
                    if capacity.read_json(path) != decisions:
                        raise ValueError('Monthly decisions changed on resume')
                else:
                    capacity.grid.base.save_new(path, decisions)
                run_case(p, f'MONTHLY_{window}', tape, lambda d, m=decisions: m[d.strftime('%Y-%m')]['profile'],
                         min(s.session_date for s in inputs.sessions(start=inputs.START) if s.session_date >= inputs.START))
                tape.month.cache_clear()
            for arm, name in [('FIXED_REFERENCE', REFERENCE), ('FIXED_TRAILING15', PROFILES[1]['name'])]:
                run_case(p, arm, tape, lambda _d, n=name: n,
                         min(s.session_date for s in inputs.sessions(start=inputs.START) if s.session_date >= inputs.START))
                tape.month.cache_clear()
            rows = [r for arm in ARMS[6:] for r in annual_results(arm)]
            pd.DataFrame(rows).to_csv(ROOT/'annual-summary.csv', index=False)
            summaries = [capacity.read_json(ROOT/'cases'/arm/'report.json') for arm in ARMS[6:]]
            pd.DataFrame([{k: v for k, v in s.items() if not isinstance(v, (list, dict))} for s in summaries]).to_csv(ROOT/'cumulative-summary.csv', index=False)
            capacity.grid.base.verify(p['sources'])
            capacity.grid.base.save_new(ROOT/'report.json', dict(status='COMPLETED_AUDITED_EXPLORATORY',
                annual=rows, cumulative=[{k: v for k, v in s.items() if not isinstance(v, (list, dict))} for s in summaries],
                independent_holdout=False, future_coverage_selection_bias=True, full_live_parity=False,
                files={n: capacity.grid.base.digest(ROOT/n) for n in ['annual-summary.csv', 'cumulative-summary.csv']}))
            capacity.grid.atomic_json(ROOT/'progress.json', dict(status='COMPLETED_AUDITED_EXPLORATORY', completed_runs=10, total_runs=10))
    except BaseException as exc:
        capacity.grid.atomic_json(ROOT/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)))
        raise


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    if os.name == 'nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR, force=True)
    run()
