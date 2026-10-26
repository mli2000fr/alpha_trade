"""Controlled start-state decomposition of the sealed TOP20 SL5/H20 replay.

Local archived inputs and archived legacy engines ONLY. Do not modify the old
study or production. Observation hooks return original decisions unchanged.
The guard reset is an explicit counterfactual, NOT a proposed trading rule.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import time

PARENT = Path('artifacts/research/us_winner_monthly_selector/20261024-v1')
ROOT = Path('artifacts/research/us_winner_start_state_audit/20261025-v1')
CONTROL = 'SHADOW_SL5_TROFF_H20_TPOFF'
COLD = 'FIXED_REFERENCE'
CUTOFF = date(2019, 12, 31)
DOC = Path('doc/ml/winner_ecart_dates_depart_audit_20261025.md')
TEST = Path('tests/test_us_winner_start_state_audit_20261025.py')
ARMS = ('CONTROL_FULL_REPRODUCTION', 'FRESH_2020_MATCHED_CAPITAL', 'WARM_RESET_GUARD_ONLY')


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def broker_snapshot(book, store):
    """Diagnostic evidence, not a claim of a portable/restartable checkpoint."""
    names = ('cash', 'unsettled', 'orders', 'lots', 'claims', 'trades', 'events',
             'marks', 'now', 'fees', 'interest', 'dividends')
    return dict(broker={k: deepcopy(getattr(book, k)) for k in names},
                intents={k: asdict(v) for k, v in book.intents.items()},
                campaigns=deepcopy(store.records), equity=book.equity(),
                gross=book.gross(), positions=book.positions())


def reset_guard_only(guard, day, equity, regime, constructor):
    """Re-seed from ONE observed close; never alter broker/campaign history."""
    fresh = constructor(guard.cfg, observations=[(day, equity)], regimes={day: regime})
    guard.__dict__.clear()
    guard.__dict__.update(fresh.__dict__)


class ObservationHooks:
    def __init__(self, native):
        self.native = native
        self.book = self.store = self.guard = None
        self.risk_rows, self.guard_days = [], {}
        self.current_trace = None
        self.last_regime = None

    @contextmanager
    def installed(self):
        import risk_management.risk_checker as check_module
        old_book, old_store, old_guard = self.native.ReplayBroker, self.native.MemoryCampaignStore, self.native.CampaignRiskState
        old_approve = self.native.reapprove_campaign
        old_check = check_module.RiskCheckerImpl.check_position_size
        self.raw_guard_constructor = old_guard
        owner = self

        class ObservedBook(old_book):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                owner.book = self

        class ObservedStore(old_store):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                owner.store = self

        class ObservedGuard(old_guard):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                owner.guard = self

            def evaluate(self, day, equity, regime, *, daily_pnl):
                outcome = super().evaluate(day, equity, regime, daily_pnl=daily_pnl)
                key = str(day)
                row = owner.guard_days.setdefault(key, dict(date=key, samples=0,
                    minimum_allocation=1., maximum_allocation=0., tripped_samples=0,
                    minimum_equity=equity, maximum_equity=equity, maximum_reference_peak=0.))
                row['samples'] += 1
                row['minimum_allocation'] = min(row['minimum_allocation'], outcome['allocation_scale'])
                row['maximum_allocation'] = max(row['maximum_allocation'], outcome['allocation_scale'])
                row['tripped_samples'] += int(bool(self.data['tripped']))
                row['minimum_equity'] = min(row['minimum_equity'], equity)
                row['maximum_equity'] = max(row['maximum_equity'], equity)
                row['maximum_reference_peak'] = max(row['maximum_reference_peak'], outcome['reference_peak'])
                row['regime'] = regime
                owner.last_regime = regime
                return outcome

        def checked(checker, *args, **kwargs):
            result = old_check(checker, *args, **kwargs)
            if owner.current_trace is not None:
                owner.current_trace['constraint_reason'] = checker.get_last_decision_reason()
            return result

        def approved(state, version, proposed, snapshot, now, kind, *, context):
            from common.winner_pyramiding import WinnerPyramidingConfig
            cfg = context['risk_config']
            trace = dict(time=now, symbol=state['symbol'], campaign_id=state['campaign_id'],
                kind=kind, proposed=proposed, equity=context['equity'],
                available_buying_power=context['available_buying_power'],
                allocation_scale=context['allocation_scale'],
                volatility_scale=context['volatility_allocation_scale'],
                frozen_risk_budget=state['risk_budget'],
                min_notional=cfg.effective_min_notional,
                concentration_allowed=context['concentration_allowed'],
                breaker_tripped=bool(context['circuit_breaker']._tripped))
            owner.current_trace = trace
            try:
                outcome = old_approve(state, version, proposed, snapshot, now, kind, context=context)
                trace.update(max_quantity=outcome['max_quantity'], reason=outcome['reason'],
                             limit_price=outcome['limit_price'])
                fee = max(WinnerPyramidingConfig(**state['policy']).fee, float(context['cost_reserve_pct']))
                budget = min(state['risk_budget'], cfg.account_equity*cfg.risk_per_trade_pct*
                    cfg.risk_multiplier*context['allocation_scale']*context['volatility_allocation_scale'])
                trace['current_risk_budget'] = budget
                trace['risk_only_notional_ceiling'] = budget/(state['policy']['stop_loss_pct']+2.05*fee)
                trace['risk_ceiling_below_min_notional'] = trace['risk_only_notional_ceiling'] < cfg.effective_min_notional
                return outcome
            except Exception as exc:
                trace.update(reason=str(exc), error_type=type(exc).__name__)
                raise
            finally:
                owner.risk_rows.append(trace)
                owner.current_trace = None

        self.native.ReplayBroker, self.native.MemoryCampaignStore, self.native.CampaignRiskState = ObservedBook, ObservedStore, ObservedGuard
        self.native.reapprove_campaign = approved
        check_module.RiskCheckerImpl.check_position_size = checked
        try:
            yield self
        finally:
            self.native.ReplayBroker, self.native.MemoryCampaignStore, self.native.CampaignRiskState = old_book, old_store, old_guard
            self.native.reapprove_campaign = old_approve
            check_module.RiskCheckerImpl.check_position_size = old_check

    def checkpoint(self, day, *, reset=False):
        before = broker_snapshot(self.book, self.store)
        original = deepcopy(self.guard.data)
        if reset:
            reset_guard_only(self.guard, day, self.book.equity(), self.last_regime, self.raw_guard_constructor)
        after = broker_snapshot(self.book, self.store)
        if stable_hash(before) != stable_hash(after):
            raise ValueError('Guard counterfactual changed broker/campaign state')
        return dict(date=str(day), diagnostic_not_restart_checkpoint=True,
                    account=before, guard_before=original, guard_after=deepcopy(self.guard.data),
                    guard_reset=reset, unchanged_account_hash=stable_hash(before))


def independent_cash(events, initial):
    """Explicit deposit; never reuse the predecessor's hard-coded $4,000 audit."""
    held, cash, fees = {}, float(initial), 0.
    for row in events.itertuples():
        if row.event == 'BUY_FILL':
            if held.get(row.symbol, 0) or row.quantity < 1 or not float(row.quantity).is_integer():
                raise ValueError('Repeated/fractional entry')
            held[row.symbol] = row.quantity
            cash -= row.quantity*row.price+row.costs
            fees += row.costs
        elif row.event == 'SELL_FILL':
            if row.quantity > held.get(row.symbol, 0):
                raise ValueError('Oversell')
            held[row.symbol] -= row.quantity
            cash += row.quantity*row.price-row.costs
            fees += row.costs
        elif row.event == 'FINANCING':
            cash -= row.costs
        else:
            raise ValueError('Unqualified accounting event: '+str(row.event))
    return cash, fees, {s:q for s,q in held.items() if q}


def audit_case(study, result, summary, metadata, tape, initial, end):
    import numpy as np
    import pandas as pd
    near = study.near
    events = result.trade_events_df
    cash, fees, held = independent_cash(events[events.event.notna()], initial)
    near(cash, summary['settled_cash']); near(fees, summary['costs'])
    if held != {p['symbol']: p['qty'] for p in summary['open_positions']}:
        raise ValueError('Final holdings mismatch')
    near(summary['final_equity'], cash+sum(p['qty']*p['mark'] for p in summary['open_positions']))
    if summary['dividends_accrued'] or summary['unsettled_cash']:
        raise ValueError('Reserved accounting lifecycle used')
    for trade in result.closed_trades_df.itertuples():
        policy = metadata[trade.campaign_id]['policy']
        day = pd.Timestamp(trade.entry_date).tz_convert('America/New_York').date()
        due = pd.Timestamp([s for s in study.inputs.sessions(start=day) if s.session_date >= day][policy['horizon_sessions']].open_at_utc)
        got = study.scalar_exit(tape.path(trade.symbol, pd.Timestamp(trade.entry_date), pd.Timestamp(trade.exit_date)),
            pd.Timestamp(trade.entry_date), trade.entry_price, due, sl=policy['stop_loss_pct'],
            tp=policy['take_profit_pct'], trail=policy['trailing_stop_pct'])
        if got is None or got[0] != trade.exit_date or got[2] != trade.exit_reason:
            raise ValueError('Independent exit mismatch: '+str((trade.symbol, got, trade.exit_reason)))
        near(got[1], trade.exit_price)
        near(trade.pnl, trade.quantity*(trade.exit_price-trade.entry_price)-trade.entry_fees-trade.exit_fees+trade.dividends)
    filled = {(m['symbol'], pd.Timestamp(m['first_fill_at'])) for m in metadata.values() if m.get('first_fill_at')}
    days = sorted(tape.schedule); idx = {d:i for i,d in enumerate(days)}
    buys = events[events.event.eq('BUY_FILL')]
    for buy in buys.itertuples():
        stamp = pd.Timestamp(buy.time); day = stamp.tz_convert('America/New_York').date()
        frame = tape.day(buy.symbol, day).reset_index(drop=True)
        where = np.flatnonzero(frame.bar_timestamp.eq(stamp))
        if (buy.symbol, stamp) not in filled or len(where) != 1 or where[0] < 3:
            raise ValueError('Entry not observable/frozen')
        i = int(where[0]); level = tape.day(buy.symbol, days[idx[day]-1]).high.max()
        if not (frame.close.iloc[i-3] <= level and frame.close.iloc[i-2] > level and frame.close.iloc[i-1] > level):
            raise ValueError('Entry lacks two fresh completed confirmations')
        near(buy.price, frame.open.iloc[i]); near(buy.costs, buy.quantity*buy.price*.0008)
    study.capacity.audit_held_coverage(result, summary['coverage_gaps'], end)
    values = np.r_[initial, result.intraday_equity_curve.equity.to_numpy()]
    near(summary['max_drawdown_pct'], 100*np.min(values/np.maximum.accumulate(values)-1))
    near(summary['return_pct'], 100*(summary['final_equity']/initial-1))
    return dict(status='PASS_EXPLICIT_DEPOSIT_CASH_FEES_SCALAR_EXITS_ENTRIES_COVERAGE',
                initial_equity=initial, exits=len(result.closed_trades_df), buys=len(buys))


def annual_rows(result, initial):
    import numpy as np
    import pandas as pd
    daily = result.equity_curve
    dates = pd.to_datetime(daily.index)
    bars = result.intraday_equity_curve
    years = pd.to_datetime(bars.timestamp, utc=True).dt.tz_convert('America/New_York').dt.year
    output = []
    previous = initial
    for year in sorted(set(dates.year)):
        ending = float(daily[dates.year == year].iloc[-1])
        curve = bars[years == year]
        values = np.r_[previous, curve.equity.to_numpy()]
        output.append(dict(year=int(year), starting_equity=previous, final_equity=ending,
            return_pct=100*(ending/previous-1), max_drawdown_pct=100*np.min(values/np.maximum.accumulate(values)-1),
            average_gross_equity_pct=float((curve.gross/curve.equity).mean()*100)))
        previous = ending
    return output


def initial_evidence(study):
    import pandas as pd
    base = study.capacity.grid.base
    output = {}
    policies = []
    for arm in [CONTROL, COLD]:
        folder = PARENT/'cases'/arm
        report = base.read(folder/'report.json')
        base.verify({str(folder/n):h for n,h in report['files'].items()})
        meta = base.read(folder/'campaign-policies.json')
        unique = {json.dumps(m['policy'], sort_keys=True) for m in meta.values()}
        if len(unique) != 1:
            raise ValueError('Mixed reference policies')
        policies.append(next(iter(unique)))
        events = pd.read_csv(folder/'events.csv', low_memory=False)
        daily = pd.read_parquet(folder/'equity-daily.parquet').iloc[:,0]
        value = float(daily.loc[:'2019-12-31'].iloc[-1]) if arm == CONTROL else 4000.
        filled = events[events.event.eq('BUY_FILL')]
        y2022 = events[events.time.str.startswith('2022', na=False)]
        output[arm] = dict(initial_equity=report['initial_equity'], equity_before_2020=value,
            final_equity=report['final_equity'], return_2020_2024_pct=100*(report['final_equity']/value-1),
            max_drawdown_whole_run_pct=report['max_drawdown_pct'],
            buys_2022=int(filled.time.str.startswith('2022').sum()),
            refusal_attempts_2022={str(k):int(v) for k,v in y2022.reason.value_counts().items()},
            actual_campaign_policy=json.loads(policies[-1]))
    if policies[0] != policies[1]:
        raise ValueError('Protections differ, stop causal comparison')
    output['same_actual_policy'] = True
    output['attempts_are_not_unique_symbols'] = True
    output['causal_verdict'] = 'PENDING_CONTROLLED_REPLAYS; capital, inherited positions/plans and native guard histories differ.'
    return output


def prepare(root, study, repair, legacy):
    base = study.capacity.grid.base
    if (root/'protocol.json').exists():
        sealed = base.read(root/'protocol.json'); base.verify(sealed['sources']); return sealed
    parent = base.read(PARENT/'protocol.json'); base.verify(parent['sources'])
    amendment = base.read(PARENT/'scope-repair-20261024-v1/amendment.json'); base.verify(amendment['sources'])
    evidence = initial_evidence(study)
    sources = dict(parent['sources'])
    for path in [Path(__file__), TEST, DOC, Path(legacy.__file__), Path(repair.__file__),
            PARENT/'protocol.json', PARENT/'inputs/manifest.json', PARENT/'scope-repair-20261024-v1/amendment.json']:
        sources[str(path)] = base.digest(path)
    for arm in [CONTROL, COLD]:
        folder = PARENT/'cases'/arm
        sources[str(folder/'report.json')] = base.digest(folder/'report.json')
        sources.update({str(folder/n):h for n,h in base.read(folder/'report.json')['files'].items()})
    protocol = dict(reference_config=parent['reference_config'], sources=sources,
        created_at_utc=datetime.now(timezone.utc).isoformat(), experiment='START_STATE_CAUSAL_AUDIT',
        arms=list(ARMS), matched_initial_equity=evidence[CONTROL]['equity_before_2020'],
        loaded_core={m:dict(path=str(p),sha256=h) for m,(_,p,h) in legacy.legacy_paths().items()},
        cutoff=str(CUTOFF), end=str(study.inputs.END), TOP=20, initial_position_fraction=1.,
        stop_loss_pct=.05, trailing_stop_pct=None, take_profit_pct=None, horizon_sessions=20,
        outer_admission_unchanged='FULL SL3 resized once to SL5, identical to parent',
        reset_definition='At 2019-12-31 AFTER close, financing and daily admission: re-seed ONLY native guard from actual observed equity and known regime.',
        initial_counterfactual='FRESH_2020 deposit equals original 2019-12-31 equity; no inherited holdings, plans or guard/concentration history.',
        comparator='Reuse sealed fresh $4,000; reproduce full warm reference and require daily cash/event parity.',
        production_changed=False, SQL_reads=0, SQL_writes=0, provider_calls=0, LLM_calls=0, orders=False,
        full_live_parity=False, future_coverage_selection_bias=True, current_sectors_non_PIT=True,
        independent_holdout=False, reset_is_diagnostic_not_recommended_strategy=True)
    root.mkdir(parents=True, exist_ok=False)
    base.save_new(root/'protocol.json', protocol)
    base.save_new(root/'initial-evidence.json', evidence)
    study.capacity.grid.atomic_json(root/'progress.json', dict(status='PREPARED', completed_runs=0,total_runs=len(ARMS)))
    return protocol


def run_case(root, protocol, arm, tape, study, repair):
    import numpy as np
    import pandas as pd
    grid, base = study.capacity.grid, study.capacity.grid.base
    folder = root/'cases'/arm
    if (folder/'report.json').exists():
        old = base.read(folder/'report.json'); base.verify({str(folder/n):h for n,h in old['files'].items()}); return old
    folder.mkdir(parents=True, exist_ok=False)
    warm = arm != 'FRESH_2020_MATCHED_CAPITAL'
    start = study.inputs.SHADOW_START if warm else study.inputs.START
    initial = 4000. if warm else protocol['matched_initial_equity']
    cfg = study.configuration(protocol, start)
    cfg = replace(cfg, initial_equity=initial, risk_config=replace(cfg.risk_config,account_equity=initial))
    signals = tape.cohort[['date','symbol','rank','selected']].rename(columns={'date':'trade_date'}).copy()
    signals = signals[signals.trade_date.ge(pd.Timestamp(max(d for d in tape.schedule if d < start)))]
    signals['side'] = 'long'
    reference_daily = pd.read_parquet(PARENT/'cases'/CONTROL/'equity-daily.parquet').iloc[:,0]
    reference_events = pd.read_csv(PARENT/'cases'/CONTROL/'events.csv', low_memory=False)
    reference_events = reference_events[reference_events.event.notna()].reset_index(drop=True)
    reference_days = pd.to_datetime(reference_events.time,utc=True).dt.tz_convert('America/New_York').dt.date
    checked_events = 0
    started = time.monotonic()
    hooks = ObservationHooks(study.native)
    daily_rows = []

    def progress(done, total, day):
        nonlocal checked_events
        current = date.fromisoformat(str(day))
        book = hooks.book
        daily_rows.append(dict(date=str(current),equity=book.equity(),gross=book.gross(),cash=book.cash))
        verify = arm == ARMS[0] or (arm == ARMS[2] and current <= CUTOFF)
        if verify:
            study.near(book.equity(), reference_daily.loc[pd.Timestamp(current)])
            expected_count = int((reference_days <= current).sum())
            if len(book.events) != expected_count:
                raise ValueError('Baseline fill/financing count divergence on '+str(current))
            for i in range(checked_events, expected_count):
                actual, expected = book.events[i], reference_events.iloc[i]
                if (pd.Timestamp(actual['time']) != pd.Timestamp(expected.time)
                        or actual['event'] != expected.event
                        or actual.get('symbol') != (None if pd.isna(expected.symbol) else expected.symbol)):
                    raise ValueError('Baseline chronology/identity divergence at '+str(i))
                for field in ['quantity','price','costs']:
                    if field in actual:
                        study.near(actual[field],expected[field])
            checked_events = expected_count
        if warm and current == CUTOFF:
            checkpoint = hooks.checkpoint(current, reset=arm == ARMS[2])
            study.near(checkpoint['account']['equity'], protocol['matched_initial_equity'])
            base.save_new(folder/'checkpoint-20191231.json', checkpoint)
        if done % 20 == 0 or done == total or current == CUTOFF:
            grid.atomic_json(folder/'guard-daily.json', list(hooks.guard_days.values()))
            grid.atomic_json(folder/'account-daily.json', daily_rows)
        elapsed = time.monotonic()-started
        grid.atomic_json(root/'progress.json', dict(status='RUNNING',arm=arm,
            completed_runs=sum((root/'cases'/a/'report.json').exists() for a in ARMS),total_runs=len(ARMS),
            completed_sessions=done,total_sessions=total,last_date=str(current),
            elapsed_case_seconds=elapsed,estimated_case_remaining_seconds=elapsed*(total-done)/done,
            parity_checked_through=str(current) if verify else None,
            updated_at_utc=datetime.now(timezone.utc).isoformat()))

    with grid.runtime_adapter(start.year,arm), study.capacity.corrected_runtime(), repair.campaign_adapter(
            cfg.exec_config,lambda _d:study.REFERENCE) as metadata, hooks.installed():
        result = base.BacktestEngine(cfg).run(open_df=tape.pivots['open'],close=tape.pivots['close'],
            high=tape.pivots['high'],low=tape.pivots['low'],volume=tape.pivots['volume'],signals_df=signals,
            sector_map=tape.sectors,intraday_source=tape,winner_research_assumptions=True,
            winner_progress=progress,winner_corporate_actions=tape.actions.to_dict('records'))
    grid.atomic_json(root/'progress.json',dict(status='AUDITING',arm=arm,
        completed_runs=sum((root/'cases'/a/'report.json').exists() for a in ARMS),total_runs=len(ARMS)))
    summary = grid.metrics(result,initial)
    checks = audit_case(study,result,summary,metadata,tape,initial,cfg.end_date)
    if arm == ARMS[0]:
        original = base.read(PARENT/'cases'/CONTROL/'report.json')
        for key in ['final_equity','max_drawdown_pct','costs','settled_cash']:
            study.near(summary[key],original[key])
        expected = pd.read_parquet(PARENT/'cases'/CONTROL/'equity-5m.parquet')
        got = result.intraday_equity_curve
        if not pd.to_datetime(got.timestamp,utc=True).equals(pd.to_datetime(expected.timestamp,utc=True)):
            raise ValueError('5m valuation chronology differs')
        np.testing.assert_allclose(got[['equity','gross']],expected[['equity','gross']],rtol=1e-10,atol=1e-7)
        checks['exact_archived_control_curve_parity'] = True
    summary['outer_admission_policy'] = summary.pop('policy')
    summary.update(arm=arm,start=str(start),end=str(cfg.end_date),audit=checks,
        actual_campaign_policy=asdict(study.profile_policy(cfg.exec_config,study.REFERENCE)),
        annual=annual_rows(result,initial),only_guard_reset=arm == ARMS[2],
        initial_equity=initial,future_coverage_selection_bias=True,full_live_parity=False)
    result.equity_curve.to_frame().to_parquet(folder/'equity-daily.parquet')
    result.intraday_equity_curve.to_parquet(folder/'equity-5m.parquet',index=False)
    result.closed_trades_df.to_parquet(folder/'trades.parquet',index=False)
    result.trade_events_df.to_csv(folder/'events.csv',index=False)
    result.drawdown_breaker_df.to_parquet(folder/'breaker-5m.parquet',index=False)
    pd.DataFrame(hooks.risk_rows).to_parquet(folder/'risk-decisions.parquet',index=False)
    grid.atomic_json(folder/'guard-daily.json',list(hooks.guard_days.values()))
    grid.atomic_json(folder/'account-daily.json',daily_rows)
    grid.atomic_json(folder/'campaign-policies.json',metadata)
    summary['files'] = {p.name:base.digest(p) for p in folder.iterdir() if p.is_file()}
    base.save_new(folder/'report.json',summary)
    return summary


def run(root, study, repair, legacy):
    grid, base = study.capacity.grid, study.capacity.grid.base
    protocol = prepare(root,study,repair,legacy)
    with grid.run_lock(root):
        if (root/'report.json').exists():
            raise FileExistsError('Completed audit is immutable')
        grid.atomic_json(root/'process.json',dict(pid=os.getpid(),started_at_utc=datetime.now(timezone.utc).isoformat()))
        grid.atomic_json(root/'progress.json',dict(status='VERIFYING_FROZEN_LOCAL_INPUTS',completed_runs=0,total_runs=len(ARMS)))
        tape = study.inputs.Tape(PARENT)
        if not tape.cohort.groupby('date')['rank'].apply(lambda ranks:sorted(ranks) == list(range(1,21))).all():
            raise ValueError('Frozen TOP20 differs')
        cases = []
        for arm in ARMS:
            base.verify(protocol['sources'])
            cases.append(run_case(root,protocol,arm,tape,study,repair))
            tape.month.cache_clear()
        base.verify(protocol['sources'])
        base.save_new(root/'report.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',cases=cases,
            cold_4000_reused=base.read(PARENT/'cases'/COLD/'report.json'),
            control_reproduced=True,capital_effect_isolated=True,
            residual_bundle='Warm positions + pending plans + guard + concentration history; not separable additively.',
            guard_effect_conditional_on_original_warm_state=True,
            full_live_parity=False,future_coverage_selection_bias=True,independent_holdout=False,
            sources=protocol['sources']))
        grid.atomic_json(root/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',completed_runs=len(ARMS),total_runs=len(ARMS)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','run'],default='run')
    parser.add_argument('--output',type=Path,default=ROOT)
    args = parser.parse_args()
    from scripts.research import us_winner_legacy_resume_20261024 as legacy
    legacy.install_legacy()
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    study = repair.study
    import requests
    requests.Session.request = lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No HTTP in start-state audit'))
    os.environ['SSLKEYLOGFILE'] = ''
    if os.name == 'nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    try:
        prepare(args.output,study,repair,legacy) if args.phase == 'prepare' else run(args.output,study,repair,legacy)
    except BaseException as exc:
        if args.output.exists():
            study.capacity.grid.atomic_json(args.output/'failure.json',dict(status='FAILED',
                error_type=type(exc).__name__,error=str(exc),at_utc=datetime.now(timezone.utc).isoformat()))
            study.capacity.grid.atomic_json(args.output/'progress.json',dict(status='FAILED',error=str(exc)))
        raise


if __name__ == '__main__':
    main()
