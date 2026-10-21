"""Bounded robustness audit of sealed DD15 grid; no strategy promotion.

Read existing full grid; replay anchor/one-step neighbors under fixed stresses.
No database, provider, LLM, model fitting, production mutation or parameter search.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import inspect
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd

from common.trading_costs import TradingCostModel
from risk_management.models import PriceInfo
from scripts.research import us_intraday_protection_grid_risk_audit as sealed_audit
from scripts.research import us_oracle_persistent_trend as prior
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

BASE, RISK, REFERENCE = prior.BASE, prior.risk, prior.REFERENCE
OUTPUT = Path('artifacts/research/us_oracle_grid_robustness/20261021-v2')
AXES = dict(sl=[.03, .05, .07], trailing=[None, .10, .15, .20],
            horizon=[5, 10, 15, 20], tp=[None, .10, .20])
ANCHOR = dict(sl=.07, trailing=.15, horizon=20, tp=None)
ORIGINAL_CACHE = AUDITOR = None


def profile_key(c):
    return BASE.case_key(dict(year=2025, side='buy', **{k: c[k] for k in AXES})).split('LONG-', 1)[1]


def neighbors(c):
    out = []
    for axis, choices in AXES.items():
        i = choices.index(c[axis])
        for j in [i-1, i+1]:
            if 0 <= j < len(choices):
                d = {k: c[k] for k in AXES}; d[axis] = choices[j]; out.append(d)
    return out


def specialize_cost_auditor(function=sealed_audit.audit_case):
    """Parameterize ONLY the three fixed fee constants of the sealed audit.

    Exact AST transformation is declared and tested; every cash/exit/risk
    assertion remains intact. Do not mutate the historical module/file.
    """
    tree = ast.parse(inspect.getsource(function))
    class Fees(ast.NodeTransformer):
        count = 0
        def visit_Constant(self, node):
            if isinstance(node.value, float) and node.value == .0008:
                self.count += 1
                return ast.copy_location(ast.Subscript(value=ast.Name(id='c', ctx=ast.Load()),
                    slice=ast.Constant(value='fee_pct'), ctx=ast.Load()), node)
            return node
    change = Fees(); tree = change.visit(tree)
    if change.count != 3:
        raise ValueError('Audit source changed: exactly three fixed execution-fee constants expected')
    ast.fix_missing_locations(tree)
    namespace = dict(function.__globals__)
    exec(compile(tree, str(Path(sealed_audit.__file__).resolve()), 'exec'), namespace)
    return namespace[function.__name__]


def read_grid():
    review = BASE.READ(REFERENCE/'final-review.json')
    verify_hashes(REFERENCE, review['files'])
    report = BASE.READ(REFERENCE/'report.json')
    if report['completed'] != 576 or report['failed'] or len(report['cases']) != 576:
        raise ValueError('Complete sealed576-case grid required')
    return report


def describe_grid(root, report):
    """All144profiles per direction, no ranking-based champion selection."""
    rows = []
    for side in ['buy', 'sell']:
        yearly = {(r['year'], profile_key(r)): r for r in report['cases'] if r['side'] == side}
        for c in [c for c in BASE.cases() if c['year'] == 2025 and c['side'] == side]:
            key = profile_key(c); adjacent = neighbors(c)
            family = [yearly[y, profile_key(n)] for n in adjacent for y in [2025, 2026]]
            a, b = yearly[2025, key], yearly[2026, key]
            positive = [all(yearly[y, profile_key(n)]['return_pct'] > 0 for y in [2025, 2026])
                        for n in adjacent]
            fraction = sum(positive)/len(positive)
            rows.append(dict(side=side, profile=key, neighbors=len(adjacent),
                return_2025=a['return_pct'], return_2026=b['return_pct'],
                dd_2025=a['max_drawdown_pct'], dd_2026=b['max_drawdown_pct'],
                both_years_positive=a['return_pct'] > 0 and b['return_pct'] > 0,
                neighbors_both_years_positive_fraction=fraction,
                descriptive_positive_plateau=a['return_pct'] > 0 and b['return_pct'] > 0 and fraction >= .75,
                neighbor_min_return=min(r['return_pct'] for r in family),
                neighbor_max_dd=max(r['max_drawdown_pct'] for r in family),
                neighbor_median_return_2025=float(np.median([yearly[2025, profile_key(n)]['return_pct'] for n in adjacent])),
                neighbor_median_return_2026=float(np.median([yearly[2026, profile_key(n)]['return_pct'] for n in adjacent]))))
    pd.DataFrame(rows).to_csv(root/'neighborhoods.csv', index=False)


def symbol_attribution(reference_case):
    folder = REFERENCE/'cases'/reference_case['case']
    for name in ['trades.parquet', 'open-positions.json']:
        if digest(folder/name) != reference_case['files'][name]:
            raise ValueError('Sealed contribution source changed')
    trades = pd.read_parquet(folder/'trades.parquet')
    result = trades.groupby('symbol').pnl.sum().to_dict()
    for row in BASE.READ(folder/'open-positions.json'):
        result[row['symbol']] = result.get(row['symbol'], 0.)+row['unrealized_pnl_usd']
    return sorted(result.items(), key=lambda x: (-x[1], x[0]))


def fixed_plan(report):
    family = [ANCHOR]+neighbors(ANCHOR)
    plan = []; contributors = []
    for year in [2025, 2026]:
        for side in ['buy', 'sell']:
            group = dict(year=year, side=side)
            plan.append(dict(**group, **ANCHOR, scenario='baseline', fee_bps=8., delay_bars=0,
                             excluded_symbols=[], excluded_quarter=None))
            for c in family:
                for scenario, fee, delay in [('cost25', 25., 0), ('delay5m', 8., 1)]:
                    plan.append(dict(**group, **c, scenario=scenario, fee_bps=fee, delay_bars=delay,
                                     excluded_symbols=[], excluded_quarter=None))
            plan.append(dict(**group, **ANCHOR, scenario='cost25_delay5m', fee_bps=25., delay_bars=1,
                             excluded_symbols=[], excluded_quarter=None))
            source = next(r for r in report['cases'] if r['case'] == BASE.case_key(dict(**group, **ANCHOR)))
            ranked = symbol_attribution(source)
            contributors.extend(dict(**group, symbol=s, net_contribution_usd=p, rank=i+1)
                                for i, (s, p) in enumerate(ranked))
            top = [s for s, p in ranked if p > 0][:3]
            if len(top) != 3:
                raise ValueError('The bounded predeclared diagnostic needs three positive contributors')
            for i, s in enumerate(top):
                plan.append(dict(**group, **ANCHOR, scenario=f'without_top{i+1}', fee_bps=8., delay_bars=0,
                                 excluded_symbols=[s], excluded_quarter=None))
            plan.append(dict(**group, **ANCHOR, scenario='without_top3_joint', fee_bps=8., delay_bars=0,
                             excluded_symbols=top, excluded_quarter=None))
            for quarter in range(1, 5 if year == 2025 else 4):
                plan.append(dict(**group, **ANCHOR, scenario=f'without_entry_Q{quarter}', fee_bps=8., delay_bars=0,
                                 excluded_symbols=[], excluded_quarter=quarter))
    if len(plan) != 86:
        raise ValueError('Frozen86-case plan changed')
    return plan, contributors


def prepare(root):
    root = Path(root)
    if root.resolve() == REFERENCE.resolve() or REFERENCE.resolve() in root.resolve().parents:
        raise ValueError('Preserve sealed reference')
    if root.exists() and any(p.name != 'run.lock' for p in root.iterdir()):
        raise ValueError('Fresh output required')
    report = read_grid()
    sources, drift = prior.replay_sources(BASE.READ(REFERENCE/'protocol.json'))
    ready = BASE.READ(REFERENCE/'prepared.json'); verify_hashes(REFERENCE, ready['files'])
    for p in [__file__, 'tests/test_us_oracle_grid_robustness.py', 'scripts/research/us_oracle_persistent_trend.py',
              'scripts/research/us_intraday_protection_grid_risk_audit.py', REFERENCE/'report.json',
              REFERENCE/'final-review.json']:
        sources[str(p)] = digest(p)
    plan, contributors = fixed_plan(report)
    root.mkdir(parents=True, exist_ok=True)
    atomic_json(root/'protocol.json', dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources=sources, declared_source_changes=drift, reference=str(REFERENCE), anchor=ANCHOR,
        axis_order=AXES, cases=plan, total_cases=86,
        question='Does the already-inspected strategy have a neighborhood, fee/execution and concentration robustness plateau?',
        neighborhood='All144profiles/side. One axis changed one adjacent discrete level; OFF is an explicit level. '
                     'Descriptive positive plateau: centre positive BOTH years and >=75%neighbors also positive BOTH. '
                     'DD/ranges published separately, never claimed acceptable solely from this label. No new champion selected.',
        stresses='Anchor+5immediate neighbors:25bps/leg instead of8, OR one5m-entry-delay. '
                 'Anchor also joint25bps+5m. Same-day contiguous next bar only; no rollover/retry. '
                 'Original signal close/lineage retained, native gap guard rechecked vs delayed actual open.',
        concentration='Anchor leave-one-top1/2/3-symbol-out and jointtop3, chosen from original net symbol PnL incl MTM. '
                      'Explicit hindsight sensitivity, NOT deployable blacklists. Also suppress entries in each calendar '
                      'quarter independently, preserving all prices and prior holdings/B4/cash (not subtracting PnL).',
        audit_specialization='Only three hardcoded0.0008 fee constants of historical audit become case fee_pct. '
                             'AST count guard, unchanged scalar exits/cash/risk assertions. No old files modified.',
        fees='Same canonical commission1/spread5;slippage2->19bps;native cost model passes actual fees through '
             'sizing buying-power constraints, booking, equity, B4 and open positions. Not fixed-trade fee subtraction.',
        unchanged='213campaigns/72symbols, current survivor universe, researchCatBoostPATH_H20,4kUSDannual,1x,HALF, '
                  'B4DD15/0.3%annual252borrow/6.5%ACT360finance. OracleJ+Hexpiry includes waiting, NOT newholdingHruntime.',
        limitations=['Full future-path-price qualification creates coverage/survivor bias; not original entireTOP10.',
                     '2025 and2026toSept30 already examined, NOT fresh holdout, no p-value or win-rate independence claim.',
                     'Restated histories, hypothetical fills/borrow/CA, not full live parity;2024 intraday unqualified.',
                     'No statistical-family search correction certified here; report all grid, no newlyoptimized deployment.',
                     'Quarter-ablation cannot isolate all regime effects and is not an independent future-year test.',
                     'Actual archived gaps reported, no arbitrary artificial gap price shocks fabricated.'],
        training=False, provider_calls=False, sql_writes=False, broker_calls=False, full_live_parity=False))
    for name in ready['files']:
        shutil.copyfile(REFERENCE/name, root/name)
    atomic_json(root/'prepared.json', dict(files=ready['files'], anchor_cases=4, source_cases=576))
    pd.DataFrame(contributors).to_csv(root/'original-symbol-contributions.csv', index=False)
    describe_grid(root, report)
    atomic_json(root/'progress.json', dict(status='PREPARED', completed=0, failed=0, total=86))


def scenario_candidates(tape, c):
    kept = []; events = []
    for r in tape['candidates'][tape['candidates'].side.eq(c['side'])].itertuples(index=False):
        row = r._asdict(); old = r.decision_time
        day = pd.Timestamp(old.tz_convert('America/New_York').date())
        new = old+pd.Timedelta(minutes=5*c['delay_bars'])
        reason = 'KEEP'
        if r.symbol in c['excluded_symbols']:
            reason = 'SYMBOL_HINDSIGHT_ABLATION'
        elif c['excluded_quarter'] is not None and day.quarter == c['excluded_quarter']:
            reason = 'ENTRY_QUARTER_ABLATION'
        elif c['delay_bars']:
            path = tape['paths'][int(r.pair_id)]
            old_match = path[path.bar_timestamp.eq(old)]
            new_match = path[path.bar_timestamp.eq(new)]
            if (len(old_match) != 1 or len(new_match) != 1
                    or new.tz_convert('America/New_York').date() != old.tz_convert('America/New_York').date()):
                reason = 'NO_CONTIGUOUS_SAME_SESSION_DELAY'
        if reason == 'KEEP' and new >= tape['expiry'][r.pair_id, c['horizon']]:
            reason = 'EXPIRES_BEFORE_ENTRY'
        events.append(dict(pair_id=int(r.pair_id), symbol=r.symbol, side=r.side,
                           original_time=old, decision_time=new, reason=reason))
        if reason == 'KEEP':
            row['decision_time'] = new; kept.append(row)
    frame = pd.DataFrame(kept, columns=tape['candidates'].columns)
    return frame, events


def case_key(c):
    return c['scenario']+'__'+BASE.case_key(c)


def worker_init(root):
    global ORIGINAL_CACHE, AUDITOR
    RISK.worker_init(root)
    ORIGINAL_CACHE = BASE.CACHE
    AUDITOR = specialize_cost_auditor()


def verify_baseline_exports(out, source):
    """Compare stored artifacts on both sides, never memory dates to JSON text."""
    for name in ['trades.parquet', 'marks.parquet']:
        pd.testing.assert_frame_equal(pd.read_parquet(out/name), pd.read_parquet(source/name))
    if BASE.READ(out/'open-positions.json') != BASE.READ(source/'open-positions.json'):
        raise ValueError('Baseline open positions changed')


def replay_case(root, c):
    out = Path(root)/'cases'/case_key(c); out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    try:
        tape = dict(ORIGINAL_CACHE[c['year']])
        tape['candidates'], eligibility = scenario_candidates(tape, c)
        atomic_json(out/'entry-eligibility.json', eligibility)
        fee = c['fee_bps']/10000
        cost_model = replace(TradingCostModel(), slippage_bps=c['fee_bps']-6.)
        if not np.isclose(cost_model.per_leg_cost_pct, fee):
            raise ValueError('Cost model not the predeclared per-leg fee')
        RISK.ACTIVE_OUTPUT = out
        ledger = RISK.ProductionRiskGridLedger(tape['calendar'], sl=c['sl'], trailing=c['trailing'],
                                               tp=c['tp'], costs=cost_model)
        entries = defaultdict(list)
        for r in tape['candidates'].itertuples():
            entries[r.decision_time].append((r, tape['expiry'][r.pair_id, c['horizon']]))
        marks = []; blocked_day = None
        for i, ((ts, day, last), ohlc) in enumerate(zip(tape['timeline'], tape['bars'])):
            ledger.bar_number = i
            due = {s for s, m in ledger.live_meta.items() if ts >= m['expiry']}
            ledger.begin_bar(ts, {s: a[0] for s, a in ohlc.items()}, expiry_symbols=due)
            if ledger.maintenance_pending and ts == ledger.calendar.at[day, 'market_open']:
                for s in list(ledger.state.positions):
                    ledger.close(s, ledger.prices[s], 'MAINTENANCE_NEXT_OPEN')
                ledger.maintenance_pending = False; blocked_day = day
            ledger.resolve_open()
            for r, expiry in entries.get(ts, []):
                if blocked_day == day:
                    ledger.audit.append(dict(time=ts, symbol=r.symbol, status='BLOCKED', reasons=['MAINTENANCE_SESSION']))
                    continue
                context = tape['context'].get((r.symbol, day))
                if context is None or not np.isfinite(context.atr) or not np.isfinite(context.adv):
                    ledger.audit.append(dict(time=ts, symbol=r.symbol, status='BLOCKED', reasons=['MISSING_PRIOR_ATR_ADV']))
                    continue
                p = PriceInfo(r.symbol, float(r.signal_close), float(context.atr), price_asof_date=day.date(),
                              atr_asof_date=context.atr_date.date(), adv_usd=float(context.adv))
                ledger.entry_context = dict(pair_id=int(r.pair_id), oracle_date=r.oracle_date, rank=int(r.rank), expiry=expiry)
                ledger.enter(r.symbol, c['side'], p, sector='RESEARCH_NO_SECTOR_CAP', signal_time=ts,
                             quantity_fraction=.5, selection_rank=int(r.rank))
            equity = ledger.observe_bar(ohlc)
            if last:
                equity = ledger.finish_day()
            marks.append(dict(time=ts+pd.Timedelta(minutes=5), equity=equity, gross=ledger.gross(),
                              cash=ledger.state.settled_cash, unsettled=ledger.state.unsettled_cash, interest=ledger.interest))
        trades = pd.DataFrame(ledger.state.closed_trades)
        if trades.empty:
            trades = pd.DataFrame(columns=['symbol', 'pnl', 'net_return_pct', 'holding_sessions', 'holding_calendar_days'])
        opened = []; open_borrow = 0.
        for s, p in ledger.state.positions.items():
            sign = -1 if p.side == 'sell' else 1
            borrow = (p.quantity*p.entry_price*.003*(ledger.days.get_loc(ledger.day)-ledger.days.get_loc(p.entry_date))/252
                      if p.side == 'sell' else 0.)
            open_borrow += borrow
            opened.append(dict(symbol=s, side=p.side, qty=p.quantity, entry_price=p.entry_price,
                mark=ledger.prices[s], borrow_accrued_usd=borrow,
                unrealized_pnl_usd=sign*p.quantity*(ledger.prices[s]-p.entry_price)-p.quantity*p.entry_price*fee-borrow,
                **ledger.live_meta[s]))
        marks[-1]['cash'] -= open_borrow; marks[-1]['equity'] -= open_borrow
        m = pd.DataFrame(marks)
        if not np.isclose(4000+trades.pnl.sum()+sum(r['unrealized_pnl_usd'] for r in opened)-ledger.interest,
                          m.equity.iloc[-1], atol=1e-6, rtol=1e-10):
            raise ValueError('Cash/MTM identity failed')
        trades.to_parquet(out/'trades.parquet', index=False)
        m.to_parquet(out/'marks.parquet', index=False)
        atomic_json(out/'open-positions.json', opened)
        atomic_json(out/'decisions.json', ledger.audit)
        atomic_json(out/'maintenance.json', ledger.margin_log)
        audited = dict(c, fee_pct=fee)
        audit = AUDITOR(out, audited, tape)
        if c['scenario'] == 'baseline':
            verify_baseline_exports(out, REFERENCE/'cases'/BASE.case_key(c))
        result = dict(case=case_key(c), status='COMPLETED_EXPLORATORY', **c,
            **BASE.metrics(m, trades, opened), financing_usd=ledger.interest,
            borrow_usd=(float(trades.borrow_cost.sum()) if len(trades) else 0.)+open_borrow,
            audit=audit, elapsed_seconds=time.monotonic()-start,
            eligibility_rejections=sum(r['reason'] != 'KEEP' for r in eligibility),
            files={p.name: digest(p) for p in out.iterdir() if p.suffix in ['.json', '.parquet']})
        atomic_json(out/'done.json', result)
        return result
    except Exception as exc:
        import traceback
        result = dict(case=case_key(c), status='FAILED', **c, error=repr(exc), traceback=traceback.format_exc())
        atomic_json(out/'failed.json', result)
        return result


def run(root, workers=2):
    from scripts.research.oracle_path_confirmation import exclusive_run
    root = Path(root)
    with exclusive_run(root):
        prepare(root); protocol = BASE.READ(root/'protocol.json'); plan = protocol['cases']
        rows = []; start = time.monotonic()
        atomic_json(root/'progress.json', dict(status='RUNNING', completed=0, failed=0, total=len(plan)))
        with ProcessPoolExecutor(max_workers=workers, initializer=worker_init, initargs=(str(root),)) as pool:
            futures = {pool.submit(replay_case, str(root), c): c for c in plan}
            for future in as_completed(futures):
                try:
                    row = future.result()
                except Exception as exc:
                    c = futures[future]; row = dict(case=case_key(c), status='FAILED', **c, error=repr(exc))
                rows.append(row)
                ok = sum(r['status'] == 'COMPLETED_EXPLORATORY' for r in rows)
                elapsed = time.monotonic()-start
                atomic_json(root/'progress.json', dict(status='RUNNING', completed=ok, failed=len(rows)-ok,
                    attempted=len(rows), total=len(plan), last=row['case'], elapsed_seconds=elapsed,
                    remaining_seconds_estimate=elapsed/len(rows)*(len(plan)-len(rows))))
                pd.DataFrame([{k: v for k, v in r.items() if k not in ['files', 'audit', 'traceback']}
                              for r in rows]).to_csv(root/'annual-summary.partial.csv', index=False)
        verify_hashes(Path('.'), protocol['sources'])
        verify_hashes(root, BASE.READ(root/'prepared.json')['files'])
        for row in rows:
            if row['status'] == 'COMPLETED_EXPLORATORY':
                verify_hashes(root/'cases'/row['case'], row['files'])
        ok = sum(r['status'] == 'COMPLETED_EXPLORATORY' for r in rows)
        pd.DataFrame([{k: v for k, v in r.items() if k not in ['files', 'audit', 'traceback']}
                      for r in rows]).to_csv(root/'annual-summary.csv', index=False)
        report = dict(status='COMPLETED_EXPLORATORY' if ok == len(plan) else 'PARTIAL_FAILED',
            completed=ok, failed=len(rows)-ok, total=len(plan), cases=rows,
            elapsed_seconds=time.monotonic()-start, full_live_parity=False)
        atomic_json(root/'report.json', report)
        atomic_json(root/'progress.json', {k: v for k, v in report.items() if k != 'cases'})
        atomic_json(root/'final-review.json', dict(status='PASS_BOUNDED_ROBUSTNESS_REPLAYS' if ok == len(plan) else 'FAILED',
            independent_human_review=False,
            files={n: digest(root/n) for n in ['protocol.json', 'prepared.json', 'neighborhoods.csv',
                'original-symbol-contributions.csv', 'annual-summary.csv', 'report.json']}))
        return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=OUTPUT)
    p.add_argument('--workers', type=int, choices=range(1, 5), default=2)
    a = p.parse_args()
    run(a.output, a.workers)
