"""Isolated TOP20/2017 capacity experiment; frozen archives, no SQL/API/orders."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import logging
import time

import numpy as np
import pandas as pd

from scripts.research import us_winner_native_grid_2017_2026_20261023 as grid
from scripts.research import us_winner_topn_2017_comparison_20261023 as topn
from scripts.research.us_winner_2020_cent_repair_20261023 import corrected_runtime
from scripts.research.us_winner_grid_supervisor_repair_20261023 import read_json, safe_reads
import backtesting.winner_intraday as native

ROOT = Path('artifacts/research/us_winner_top20_capacity_2017/20261024-v1')
PARENT = topn.ROOT/'top20'
DOC = Path('doc/ml/winner_top20_capacity_2017_protocole_20261024.md')
TEST = Path('tests/test_us_winner_top20_capacity_2017_20261024.py')
PROFILE = dict(name='SL5_TROFF_H20_TPOFF', stop_loss_pct=.05, trailing_stop_pct=None,
               horizon_sessions=20, take_profit_pct=None)
ARMS = ('FULL_20POS_10ENTRIES_STRICT40', 'FULL_20POS_10ENTRIES_ENTRY20')


def configuration(protocol):
    cfg = grid.configuration(protocol, 2017, PROFILE)
    risk = replace(cfg.risk_config, max_positions=20, max_long_positions=20,
                   concentration_max_trades_per_symbol=10)
    wp = replace(cfg.exec_config.winner_pyramiding, initial_position_fraction=1., reinforcement_enabled=False)
    return replace(cfg, risk_config=risk, exec_config=replace(cfg.exec_config, winner_pyramiding=wp))


def relaxed_signals(signals, groups, actions, sectors, days):
    """No blanket J..J+40 coverage gate; preserve signal data and reserved CA gate."""
    indices = {d: i for i, d in enumerate(days)}
    rows = []
    for row in signals.itertuples():
        day = pd.Timestamp(row.date).date()
        i = indices[day]
        window = days[i:min(i+41, len(days))]
        reason = ''
        if not sectors.get(row.symbol):
            reason = 'CURRENT_SECTOR_MISSING'
        elif (row.symbol, day) not in groups:
            reason = 'SIGNAL_SESSION_SIP_MISSING'
        elif not actions.empty and ((actions.symbol == row.symbol) & actions.ex_date.between(
                pd.Timestamp(window[0]), pd.Timestamp(window[-1]))).any():
            reason = 'CORPORATE_ACTION_LIFECYCLE_RESERVED'
        rows.append(dict(date=row.date, symbol=row.symbol, selected=not reason, coverage_reason=reason))
    return signals.merge(pd.DataFrame(rows), on=['date', 'symbol'], validate='one_to_one')


def holding_window_available(symbol, day, groups, days, horizon=20):
    """Coverage metadata ONLY. This is explicitly future-dependent research eligibility.

    Twenty holding sessions plus the exit-open session, clipped at year end.
    No future return, stop outcome or early-exit shortening enters this rule.
    """
    indices = {d: i for i, d in enumerate(days)}
    if day not in indices:
        return False
    i = indices[day]
    return all((symbol, d) in groups for d in days[i:min(i+horizon+1, len(days))])


@contextmanager
def entry_coverage_gate(groups, days):
    original = native.reapprove_campaign
    refused = set()
    def reapprove(state, version, proposed, snapshot, now, kind, *, context):
        day = pd.Timestamp(now).tz_convert('America/New_York').date()
        if kind == 'ENTRY' and not holding_window_available(state['symbol'], day, groups, days):
            refused.add((str(day), state['symbol']))
            raise ValueError('RESEARCH_HOLDING_WINDOW_SIP_MISSING: entry blocked; no synthetic bars')
        return original(state, version, proposed, snapshot, now, kind, context=context)
    native.reapprove_campaign = reapprove
    try:
        yield refused
    finally:
        native.reapprove_campaign = original


def audit_held_coverage(result, gaps, end):
    """Candidate data gaps must never conceal an unobservable held position."""
    spans = [(str(t.symbol), pd.Timestamp(t.entry_date).tz_convert('America/New_York').date(),
              pd.Timestamp(t.exit_date).tz_convert('America/New_York').date())
             for t in result.closed_trades_df.itertuples()]
    events = result.trade_events_df
    lots = {}
    for event in events[events.event.isin(['BUY_FILL', 'SELL_FILL'])].sort_values('time', kind='stable').itertuples():
        symbol, quantity = str(event.symbol), float(event.quantity)
        if event.event == 'BUY_FILL':
            lots.setdefault(symbol, []).append([quantity, pd.Timestamp(event.time).tz_convert('America/New_York').date()])
        else:
            while quantity > 1e-8:
                if not lots.get(symbol):
                    raise ValueError('Exit without an observable entry')
                lot = lots[symbol][0]
                used = min(lot[0], quantity); lot[0] -= used; quantity -= used
                if lot[0] < 1e-8:
                    lots[symbol].pop(0)
    actual = {x['symbol']: float(x['qty']) for x in result.tracker_snapshot['winner_replay']['open_positions']}
    if set(actual)-set(lots):
        raise ValueError('Open holding without an observable entry')
    for symbol, remaining in lots.items():
        quantity = sum(lot[0] for lot in remaining)
        if abs(quantity-actual.get(symbol, 0.)) > 1e-8:
            raise ValueError('Open lot coverage accounting mismatch')
        spans.extend((symbol, lot[1], end) for lot in remaining)
    for gap in gaps:
        day = date.fromisoformat(gap['date'])
        if any(s == gap['symbol'] and a <= day <= b for s, a, b in spans):
            raise ValueError('Coverage gap intersects held lifecycle: '+str(gap))
    return dict(status='PASS_NO_HELD_POSITION_COVERAGE_GAPS', candidate_gap_count=len(gaps))


def load_inputs():
    folder = PARENT/'inputs/2017'
    manifest = read_json(folder/'snapshot.json')
    grid.base.verify({str(folder/n): v for n, v in manifest['files'].items()})
    signals = pd.read_parquet(folder/'signals.parquet')
    names = set(signals.symbol)
    start, end = grid.bounds(2017)
    sessions = [s for s in grid.calendar().sessions(start-timedelta(days=14), end+timedelta(days=100)) if s.is_open]
    schedule = {s.session_date: s for s in sessions}
    groups, raw = {}, {}
    for receipt in manifest['receipts']:
        if receipt['symbol'] not in names:
            continue
        frame = pd.read_parquet(folder/receipt['file'])
        frame['session_close'] = frame.trade_date.map({pd.Timestamp(d): s.close_at_utc for d, s in schedule.items()})
        raw[receipt['symbol']] = frame
        for stamp, g in frame.groupby('trade_date', sort=True):
            day = pd.Timestamp(stamp).date()
            if day in schedule and grid.base.qualify_session(g, schedule[day]):
                groups[receipt['symbol'], day] = g.rename(columns={'bar_timestamp': 'timestamp'}).copy()
    sectors = {str(x.symbol): str(x.sector) for x in pd.read_parquet(folder/'sectors.parquet').dropna().itertuples()}
    actions = pd.read_parquet(folder/'actions.parquet')
    actions['ex_date'] = pd.to_datetime(actions.ex_date)
    actions['payable_date'] = pd.to_datetime(actions.payable_date).dt.date
    daily = pd.read_parquet(folder/'daily.parquet'); daily['date'] = pd.to_datetime(daily.date)
    if daily.duplicated(['symbol', 'date']).any():
        raise ValueError('Duplicate daily prices')
    values = daily[['open', 'high', 'low', 'close', 'volume']].to_numpy(float)
    valid = (np.isfinite(values).all(axis=1) & (values > 0).all(axis=1) & daily.is_filled.eq(0)
             & daily.data_adjustment.eq('split') & ~daily.data_source.str.contains('iex', case=False, na=True))
    daily.loc[~valid, ['open', 'high', 'low', 'close', 'volume']] = np.nan
    pivots = {k: daily.pivot(index='date', columns='symbol', values=k).astype(float)
              for k in ['open', 'high', 'low', 'close', 'volume']}
    days = [d for d in schedule if d <= end]
    cohorts = {ARMS[0]: grid.qualify_cohort(signals, groups, actions, sectors, days),
               ARMS[1]: relaxed_signals(signals, groups, actions, sectors, days)}
    # The control must exactly reuse the originally qualified population.
    prior = pd.read_parquet(folder/'qualified-signals.parquet')
    pd.testing.assert_frame_equal(cohorts[ARMS[0]], prior, check_exact=True)
    return cohorts, groups, raw, actions, sectors, pivots, sessions, days


def prepare():
    parent = read_json(PARENT/'protocol.json'); grid.base.verify(parent['sources'])
    baseline = PARENT/'cases'/('2017-'+PROFILE['name'])/'report.json'
    report = read_json(baseline)
    grid.base.verify({str(baseline.parent/n): v for n, v in report['files'].items()})
    paths = [Path(__file__), DOC, TEST, PARENT/'protocol.json', baseline,
             PARENT/'inputs/2017/snapshot.json', PARENT/'inputs/2017/qualified-signals.parquet',
             Path('scripts/research/us_winner_2020_cent_repair_20261023.py')]
    sources = dict(parent['sources']); sources.update({str(n): grid.base.digest(n) for n in paths})
    protocol = deepcopy(parent)
    protocol.update(sources=sources, experiment='TOP20_2017_FULL_CAPACITY', arms=list(ARMS), profiles=[PROFILE],
        requested_changes=dict(initial_position_fraction=1., max_positions=20,
            max_long_positions=20, concentration_max_trades_per_symbol=10,
            concentration_window_calendar_days=180), effective_gross_cap=1.,
        total_runs=2, baseline_report=str(baseline), future_coverage_selection_bias=True,
        data_relaxation='Signal J full session, current/prior execution data unchanged; gate holding coverage at actual entry Jentry..Jentry+20, not blanket Jsignal..Jsignal+40.',
        holdout=False, production_changed=False, SQL_reads=False, SQL_writes=False, provider_calls=0, orders=False)
    if (ROOT/'protocol.json').exists():
        old = read_json(ROOT/'protocol.json'); grid.base.verify(old['sources']); return old
    ROOT.mkdir(parents=True, exist_ok=True)
    grid.base.save_new(ROOT/'protocol.json', protocol)
    grid.atomic_json(ROOT/'progress.json', dict(status='PREPARED', completed_runs=0, total_runs=2))
    return protocol


def run_arm(protocol, arm, inputs):
    folder = ROOT/arm
    if (folder/'report.json').exists():
        report = read_json(folder/'report.json')
        grid.base.verify({str(folder/n): v for n, v in report['files'].items()})
        return report
    folder.mkdir(exist_ok=True)
    cohorts, groups, raw, actions, sectors, pivots, sessions, days = inputs
    cohort = cohorts[arm]
    cohort.to_parquet(folder/'qualified-signals.parquet', index=False)
    def bars(day, symbols):
        frames = [groups[s, day] for s in symbols if (s, day) in groups]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    started = time.monotonic()
    def progress(done, total, day):
        grid.atomic_json(ROOT/'progress.json', dict(status='RUNNING', arm=arm,
            completed_runs=sum((ROOT/a/'report.json').exists() for a in ARMS), total_runs=2,
            completed_sessions=done, total_sessions=total, last_date=day,
            arm_elapsed_seconds=time.monotonic()-started, updated_at_utc=datetime.now(timezone.utc).isoformat()))
    selected = cohort[['date', 'symbol', 'rank', 'selected']].rename(columns={'date': 'trade_date'}).copy()
    selected['side'] = 'long'
    cfg = configuration(protocol)
    with grid.runtime_adapter(2017, arm) as refusals, corrected_runtime(), entry_coverage_gate(groups, days) as denied:
        result = grid.base.BacktestEngine(cfg).run(open_df=pivots['open'], close=pivots['close'],
            high=pivots['high'], low=pivots['low'], volume=pivots['volume'], signals_df=selected,
            sector_map=sectors, intraday_source=bars, winner_research_assumptions=True,
            winner_progress=progress, winner_corporate_actions=actions.to_dict('records'))
        grid.atomic_json(folder/'whole-share-refusals.json', refusals)
    summary = grid.metrics(result, 4000.)
    coverage_audit = audit_held_coverage(result, summary['coverage_gaps'], cfg.end_date)
    audit = grid.audit_result(result, summary, PROFILE, cohort, raw, sessions)
    if summary['coverage_gaps']:
        summary['status'] = 'COMPLETED_AUDITED_EXPLORATORY_WITH_CANDIDATE_GAPS'
    result.closed_trades_df.to_parquet(folder/'trades.parquet', index=False)
    result.trade_events_df.to_csv(folder/'events.csv', index=False)
    result.intraday_equity_curve.to_parquet(folder/'equity-5m.parquet', index=False)
    result.drawdown_breaker_df.to_parquet(folder/'breaker.parquet', index=False)
    grid.atomic_json(folder/'entry-data-refusals.json', sorted(denied))
    summary.update(arm=arm, audit=audit, coverage_audit=coverage_audit,
        signal_observations=len(cohort), eligible_signals=int(cohort.selected.sum()),
        future_coverage_selection_bias=True, independent_holdout=False,
        average_winning_holding_sessions=audit['average_winning_holding_sessions'],
        average_losing_holding_sessions=audit['average_losing_holding_sessions'],
        parameters=protocol['requested_changes'], entry_data_refusal_day_symbols=len(denied),
        files={x.name: grid.base.digest(x) for x in folder.iterdir() if x.is_file() and x.name != 'report.json'})
    grid.base.save_new(folder/'report.json', summary)
    return summary


def run():
    ROOT.mkdir(parents=True, exist_ok=True)
    try:
        with grid.run_lock(ROOT), safe_reads():
            protocol = prepare()
            if (ROOT/'report.json').exists():
                return
            import requests
            requests.Session.request = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('No provider/broker calls allowed'))
            grid.atomic_json(ROOT/'progress.json', dict(status='READING_FROZEN_INPUTS', completed_runs=0, total_runs=2))
            inputs = load_inputs()
            reports = []
            for arm in ARMS:
                reports.append(run_arm(protocol, arm, inputs))
            baseline = read_json(protocol['baseline_report'])
            rows = [dict(arm='ARCHIVED_HALF_8POS_5ENTRIES_STRICT40', **{
                k: v for k, v in baseline.items() if not isinstance(v, (dict, list))})]
            rows += [{k: v for k, v in r.items() if not isinstance(v, (dict, list))} for r in reports]
            pd.DataFrame(rows).to_csv(ROOT/'comparison.csv', index=False)
            grid.base.verify(protocol['sources'])
            grid.base.save_new(ROOT/'report.json', dict(status='COMPLETED_AUDITED_EXPLORATORY',
                comparison=rows, future_coverage_selection_bias=True, full_live_parity=False,
                independent_holdout=False, files={'comparison.csv': grid.base.digest(ROOT/'comparison.csv')}))
            grid.atomic_json(ROOT/'progress.json', dict(status='COMPLETED_AUDITED_EXPLORATORY', completed_runs=2, total_runs=2))
    except BaseException as exc:
        grid.atomic_json(ROOT/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)))
        raise


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    logging.basicConfig(level=logging.ERROR, force=True)
    run()
