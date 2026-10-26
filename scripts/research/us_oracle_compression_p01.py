"""Frozen FMZ P01 pilot: offline signals, unit paths and native cash/risk replay.

No SQL, provider, broker, training or production settings writes. The inherited
213-campaign research cohort is conditional, not all historical Oracle TOP10.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from common.trading_costs import TradingCostModel
from common.winner_pyramiding import confirmed_breakout
from risk_management.models import PriceInfo
from scripts.research import us_winner_context_headroom as history
from scripts.research import us_intraday_protection_grid_risk as risk
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_grid_robustness import specialize_cost_auditor

READ = history.READ
PARENT = history.OUTPUT
REFERENCE = history.REFERENCE
OUTPUT = Path('artifacts/research/us_oracle_compression_p01/20261022-v2')
ARMS = ('WINNER', 'WARMUP_CONTROL', 'P01')
RULE = dict(period=20, bb_std=2., kc_atr=1.5, squeeze_bars=3,
            release_valid_bars=6, confirmation_bars=2, entry_valid_sessions=20)
FEES = (8, 25)
END = pd.Timestamp('2026-09-30')


def bands(frame):
    """One completed regular session. No cross-session warmup or future access.

    BB population std; KC EMA20 (first-close seed), Wilder ATR20 (SMA seed).
    First true range is high-low; overnight gap excluded by the session reset.
    """
    p = RULE['period']
    close = frame.close.astype(float)
    tr = pd.concat([frame.high-frame.low, (frame.high-close.shift()).abs(),
                    (frame.low-close.shift()).abs()], axis=1).max(axis=1)
    atr = pd.Series(np.nan, index=frame.index)
    if len(frame) >= p:
        atr.iloc[p-1] = tr.iloc[:p].mean()
        for i in range(p, len(frame)):
            atr.iloc[i] = (atr.iloc[i-1]*(p-1)+tr.iloc[i])/p
    mean = close.rolling(p).mean()
    dev = close.rolling(p).std(ddof=0)*RULE['bb_std']
    ema = close.ewm(span=p, adjust=False, min_periods=p).mean()
    width = 2*dev
    ready = mean.notna() & atr.notna()
    inside = ready & (mean+dev < ema+RULE['kc_atr']*atr) & (mean-dev > ema-RULE['kc_atr']*atr)
    released = (ready & ~inside & inside.shift(1, fill_value=False)
                & width.gt(width.shift())
                & inside.shift(1, fill_value=False).rolling(RULE['squeeze_bars']).sum().eq(RULE['squeeze_bars']))
    return pd.DataFrame(dict(ready=ready, inside=inside, release=released, width=width,
        bb_upper=mean+dev, bb_lower=mean-dev, kc_upper=ema+RULE['kc_atr']*atr,
        kc_lower=ema-RULE['kc_atr']*atr, atr=atr))


def release_for_cross(features, cross):
    """Release must be known by the FIRST close above the frozen prior high.

    No release while a fresh squeeze is in progress, no future confirmation,
    no reuse beyond six bars. Most recent squeeze start supersedes old release.
    """
    if cross < 0 or bool(features.inside.iloc[cross]):
        return None
    lo = max(0, cross-RULE['release_valid_bars'])
    for j in range(cross, lo-1, -1):
        if bool(features.release.iloc[j]):
            if not features.inside.iloc[j:cross+1].any():
                return j
            return None
    return None


def session_signals(frame, prior_high):
    """Three completed bars prove fresh crossing + two closes; next open fill.

    Only prior closes/highs enter the signal. Next open is execution, not a
    filter. A last-bar confirmation cannot be filled at the next day's open.
    """
    features = bands(frame)
    found = {}
    for k in range(2, len(frame)-1):
        a = frame.close.iloc[k-2:k+1].to_numpy(float)
        if not (a[0] <= prior_high and a[1] > prior_high and a[2] > prior_high):
            continue
        stamp = frame.bar_timestamp.iloc[k+1]
        completed = [dict(timestamp=r.bar_timestamp.to_pydatetime(), close=r.close,
                          session_tag='regular') for r in frame.iloc[k-2:k+1].itertuples()]
        if not confirmed_breakout(completed, prior_high, history.BASE, now=stamp.to_pydatetime()):
            raise ValueError('Current Winner confirmation disagrees')
        base = dict(timestamp=stamp, price=float(frame.open.iloc[k+1]),
                    signal_close=float(frame.close.iloc[k]), signal_bar=frame.bar_timestamp.iloc[k],
                    prior_high=float(prior_high), cross_bar=frame.bar_timestamp.iloc[k-1])
        found.setdefault('WINNER', base)
        # All three evidence bars must have completed indicators in both arms.
        if features.ready.iloc[k-2:k+1].all():
            found.setdefault('WARMUP_CONTROL', base)
            release = release_for_cross(features, k-1)
            if release is not None:
                found.setdefault('P01', dict(base, release_bar=frame.bar_timestamp.iloc[release],
                    release_age_bars=k-1-release, squeeze_bars=RULE['squeeze_bars']))
        if len(found) == len(ARMS):
            break
    return found


def select_entries(row, groups, schedule):
    days = pd.DatetimeIndex(schedule.date)
    i = days.get_loc(row.oracle_date)
    found = {}
    for j in range(i+1, i+RULE['entry_valid_sessions']+1):
        day, prior = days[j], days[j-1]
        if day > END:
            return found, 'ENTRY_WINDOW_IMMATURE'
        g, prev = groups.get((row.symbol, day)), groups.get((row.symbol, prior))
        if g is None or prev is None:
            return found, 'MISSING_ENTRY_SCAN_SESSION'
        for arm, entry in session_signals(g, float(prev.high.max())).items():
            found.setdefault(arm, dict(entry, date=day, delay=j-i))
        if len(found) == len(ARMS):
            break
    return found, None


def common_reservation(row, entries, groups, schedule, actions):
    """Common coverage gate, not arm-specific survival after an early stop.

    Future completeness is an explicitly disclosed selection bias, NOT a live
    signal. Missing or immature paths reserve the campaign for ALL arms.
    """
    days = pd.DatetimeIndex(schedule.date)
    for e in entries.values():
        i = days.get_loc(e['date']); due = days[i+20]
        if due > END:
            return 'COMMON_H20_IMMATURE'
        if any((row.symbol, d) not in groups for d in days[i:i+21]):
            return 'COMMON_H20_MISSING_SESSION'
        if not actions.empty and ((actions.symbol == row.symbol) & actions.ex_date.between(e['date'], due)).any():
            return 'KNOWN_CORPORATE_ACTION'
    return None


def prepare(root):
    root = Path(root)
    if root.exists():
        raise ValueError('Fresh immutable output required')
    parent_report = READ(PARENT/'report.json')
    verify_hashes(PARENT, parent_report['files'])
    snap = READ(PARENT/'snapshot.json'); verify_hashes(PARENT, snap['files'])
    review = READ(REFERENCE/'final-review.json'); verify_hashes(REFERENCE, review['files'])
    ready = READ(REFERENCE/'prepared.json'); verify_hashes(REFERENCE, ready['files'])
    c = pd.read_parquet(PARENT/'campaigns.parquet')
    if len(c) != 213 or c.pair_id.duplicated().any() or not c.side.eq('buy').all():
        raise ValueError('Inherited cohort changed')
    paths = [Path(__file__), Path('tests/test_us_oracle_compression_p01.py'),
        Path('doc/ml/oracle_compression_p01_20261022.md'),
        Path('common/winner_pyramiding.py'), Path('core/direction.py'),
        Path('backtesting/research_intraday_native.py'), Path('backtesting/simulator.py'),
        Path('backtesting/production_risk_replay.py'), Path('backtesting/adaptive_breaker.py'),
        Path('scripts/research/us_intraday_protection_grid.py'),
        Path('scripts/research/us_intraday_protection_grid_1x.py'),
        Path('scripts/research/us_intraday_protection_grid_risk.py'),
        Path('scripts/research/us_intraday_protection_grid_risk_audit.py'),
        Path('scripts/research/us_intraday_protection_grid_audit.py'),
        Path('scripts/research/us_oracle_grid_robustness.py'),
        Path('scripts/research/us_winner_context_headroom.py'),
        Path('risk_management/position_sizer.py'), Path('risk_management/risk_checker.py'),
        Path('risk_management/constraints.py'), Path('risk_management/config.py'),
        Path('execution_engine/config.py'), Path('common/trading_costs.py'),
        Path('scripts/research/us_top10_intraday_breakout.py')]
    paths += [PARENT/n for n in ['protocol.json', 'prepared.json', 'snapshot.json', 'report.json']]
    paths += [REFERENCE/n for n in ['prepared.json', 'final-review.json', 'production-risk.json',
                                   'prior-context.parquet', 'risk-regimes.parquet']]
    root.mkdir(parents=True)
    protocol = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), rule=RULE, arms=ARMS,
        sources={str(p): digest(p) for p in paths}, parent=str(PARENT), reference=str(REFERENCE),
        selection='All213 inherited research CatBoost PATH_H20 TOP10 LONG campaigns before new outcomes. '
            'First eligible fresh breakout per arm during20sessions after Oracle; no retry after risk rejection, '
            'no replacement/rerank/TOP11. P01 may enter on a later fresh breakout, never buy retroactively.',
        indicators='Same-session BB20 population std2, KC EMA20 first-close seed +/-1.5WilderATR20 SMA seed. '
            'TR first bar high-low, reset at each real regular open; warmup20bars. '
            'Strict bilateral inside3consecutive bars, then outside with rising BBwidth. '
            'Release known no later than first above-high close; max6bars old and no new squeeze since. '
            'Three evidence bars warmed for WARMUP_CONTROL/P01. Two consecutive above-prior-raw-session-high '
            'closes preceded by at/below close; next contiguous same-session open, <=3%signal-fill gap.',
        protections='SL7%, trailing15% rounded cents, prior completed bars only, noTP/adds; '
            '20holding sessions entry included thenOPEN21. Hard stop wins adverse gap/collision.',
        portfolio='Annual4000USD restart,1x gross entry cap, full target max50%equity/risk4% thenHALF; '
            'native PositionSizer/ConstraintChecker/ledger and production B4DD15 with archived prior-SPY regimes. '
            'Identical formulas, not guaranteed identical share counts after cash/B4 paths diverge. '
            'Sector caps absent as in research reference; not full production/live parity.',
        costs_bps_per_leg=FEES,
        coverage='Existing sealed raw regular alpaca_sip unfilled5m only. No download/SQL. '
            'Common all-arm full-path qualification throughOPEN21, even if earlier exit. '
            'Reserve known corporate actions; absence in table does not certify complete event coverage. '
            'Missing entry-scan session reserves all arms; never skip gap to pick later favorable signal.',
        evaluation='2025/2026 already examined, exploratory only; no2024 simulation with absent archive. '
            'Include no-signal as cash/zero opportunity return. Publish all3arms at8/25bps and all exclusions. '
            'Unit paired per-opportunity P01 minus warmed control; monthly Oracle-date cluster bootstrap. '
            'Earliest Oracle per symbol, conservative block throughOracleJ+40open as nonoverlap sensitivity. '
            'No calibration/threshold search after outcomes.',
        continuation_gates=dict(min_p01_nonoverlap_per_year=30, min_p01_symbols_per_year=10,
            positive_portfolio_increment_both_years_both_fees=True,
            positive_nonoverlap_opportunity_increment_both_years=True,
            positive_2026_both_halves=True, monthly_bootstrap_lower95_gt_zero=True,
            minimum_months=6, bootstrap_draws=2000, bootstrap_seed=731),
        limitations=['Conditional213campaign/72symbol future-complete survivor cohort, NOT all dailyTOP10.',
            'Current split/restated daily ATR/ADV archive, historical application availability not certified.',
            'Common future coverage gate introduces selection bias;2026 not a pristine holdout.',
            '5mOHLC/fixed friction not NBBO/queue/tick fills. B4 cannot guarantee a15%DD ceiling.',
            'No SHORT inference, no winner reinforcement, no production LightGBM comparison.'],
        training=False, sql_writes=False, provider_calls=False, broker_calls=False, full_live_parity=False)
    atomic_json(root/'protocol.json', protocol)
    atomic_json(root/'progress.json', dict(status='PREPARED', completed=0, total=213))


def load_groups():
    snapshot = READ(PARENT/'snapshot.json')
    schedule = pd.read_parquet(PARENT/'calendar.parquet'); sch = schedule.set_index('date')
    groups, quality = {}, []
    for name in snapshot['files']:
        if not name.startswith('bars-'):
            continue
        f = pd.read_parquet(PARENT/name)
        for (symbol, day), g in f.groupby(['symbol', 'trade_date']):
            qualified, why = history.qualify_day(g, *sch.loc[day, ['market_open', 'market_close']])
            quality.append(dict(symbol=symbol, date=day, status=why))
            if qualified is not None:
                groups[symbol, day] = qualified.reset_index(drop=True)
    return groups, quality, schedule


def scalar_exit_cents(path, entry, expiry, c, maintenance=None):
    """Separate scalar reconstruction, not the native resolver/shared helper."""
    price = float(path.open.iloc[entry]); peak = price
    for i, r in enumerate(path.iloc[entry:].itertuples(), entry):
        stop = max(round(price*(1-.07), 2), round(peak*(1-.15), 2))
        if maintenance is not None and r.bar_timestamp == maintenance:
            return i, float(r.open), 'OPEN'
        if r.open <= stop:
            return i, float(r.open), 'OPEN'
        if r.bar_timestamp >= expiry:
            return i, float(r.open), 'OPEN'
        if r.low <= stop:
            return i, float(stop), 'INTRABAR'
        peak = max(peak, r.high)
    return None


class CentLedger(risk.ProductionRiskGridLedger):
    def known_stop(self, symbol):
        p = self.state.positions[symbol]
        # Same float expression and cent rounding as the shared Winner contract.
        # 151.5*(1-.07) rounds140.89, while151.5*.93 rounds140.90.
        return max(round(p.entry_price*(1-.07), 2), round(p.peak_high*(1-.15), 2))


def portfolio(root, arm, year, fee_bps, signals, groups, schedule):
    """Only locally constructed objects and frozen tapes; no runtime patch saved."""
    outbase = root/f'{arm}-fee{fee_bps}'
    out = outbase/'cases'/str(year); out.mkdir(parents=True)
    for n in ['production-risk.json', 'risk-regimes.parquet']:
        shutil.copyfile(REFERENCE/n, outbase/n)
    risk.PROFILE = READ(REFERENCE/'production-risk.json')
    risk.REGIMES = {r.date: dict(source_date=r.source_date, regime=None if pd.isna(r.regime) else str(r.regime))
        for r in pd.read_parquet(REFERENCE/'risk-regimes.parquet').itertuples()}
    risk.ACTIVE_OUTPUT = out
    cal = schedule[schedule.date.dt.year.eq(year) & schedule.date.le(END)].copy()
    pertime = defaultdict(dict)
    for (s, d), frame in groups.items():
        if d.year != year or d > END:
            continue
        for r in frame.itertuples():
            pertime[r.bar_timestamp][s] = (r.open, r.high, r.low, r.close)
    timeline = [(t, r.date, t == r.market_close-pd.Timedelta(minutes=5)) for r in cal.itertuples()
        for t in pd.date_range(r.market_open, r.market_close-pd.Timedelta(minutes=5), freq='5min')]
    ctx = {(r.symbol, r.date): r for r in pd.read_parquet(REFERENCE/'prior-context.parquet').itertuples()}
    eligible = signals[signals.arm.eq(arm) & signals.year.eq(year)].sort_values(['timestamp', 'rank', 'symbol', 'pair_id'])
    entries = defaultdict(list)
    for r in eligible.itertuples(): entries[r.timestamp].append(r)
    from dataclasses import replace
    costs = replace(TradingCostModel(), slippage_bps=fee_bps-6.)
    if not np.isclose(costs.per_leg_cost_pct, fee_bps/10000):
        raise ValueError('Fee schedule mismatch')
    ledger = CentLedger(cal, sl=.07, trailing=.15, tp=None, costs=costs)
    marks, blocked_day = [], None
    for i, (ts, day, last) in enumerate(timeline):
        bars = pertime[ts]
        ledger.bar_number = i
        due = {s for s, m in ledger.live_meta.items() if ts >= m['expiry']}
        ledger.begin_bar(ts, {s: a[0] for s, a in bars.items()}, expiry_symbols=due)
        if ledger.maintenance_pending and ts == ledger.calendar.at[day, 'market_open']:
            for s in list(ledger.state.positions): ledger.close(s, ledger.prices[s], 'MAINTENANCE_NEXT_OPEN')
            ledger.maintenance_pending = False; blocked_day = day
        ledger.resolve_open()
        for r in entries.get(ts, []):
            context = ctx.get((r.symbol, day))
            if blocked_day == day or context is None or not np.isfinite([context.atr, context.adv]).all():
                ledger.audit.append(dict(time=ts, symbol=r.symbol, status='BLOCKED', reasons=['MAINTENANCE_OR_PRIOR_CONTEXT']))
                continue
            info = PriceInfo(r.symbol, float(r.signal_close), float(context.atr), price_asof_date=day.date(),
                atr_asof_date=context.atr_date.date(), adv_usd=float(context.adv))
            ledger.entry_context = dict(pair_id=int(r.pair_id), oracle_date=r.oracle_date, rank=int(r.rank), expiry=r.due_open)
            ledger.enter(r.symbol, 'buy', info, sector='RESEARCH_NO_SECTOR_CAP', signal_time=ts,
                         quantity_fraction=.5, selection_rank=int(r.rank))
        eq = ledger.observe_bar(bars)
        if last: eq = ledger.finish_day()
        marks.append(dict(time=ts+pd.Timedelta(minutes=5), equity=eq, gross=ledger.gross(),
                          cash=ledger.state.settled_cash, unsettled=ledger.state.unsettled_cash, interest=ledger.interest))
    trades = pd.DataFrame(ledger.state.closed_trades)
    if trades.empty:
        trades = pd.DataFrame(columns=['symbol', 'pnl', 'net_return_pct', 'holding_sessions', 'holding_calendar_days'])
    opened = [dict(symbol=s, side='buy', qty=p.quantity, entry_price=p.entry_price,
        mark=ledger.prices[s], borrow_accrued_usd=0.,
        unrealized_pnl_usd=p.quantity*(ledger.prices[s]-p.entry_price)-p.quantity*p.entry_price*costs.per_leg_cost_pct,
        **ledger.live_meta[s]) for s,p in ledger.state.positions.items()]
    m = pd.DataFrame(marks)
    if not np.isclose(4000+trades.pnl.sum()+sum(r['unrealized_pnl_usd'] for r in opened)-ledger.interest,
                      m.equity.iloc[-1], atol=1e-6, rtol=1e-10):
        raise ValueError('Final native cash/MTM identity failed')
    trades.to_parquet(out/'trades.parquet', index=False); m.to_parquet(out/'marks.parquet', index=False)
    atomic_json(out/'open-positions.json', opened); atomic_json(out/'decisions.json', ledger.audit)
    atomic_json(out/'maintenance.json', ledger.margin_log)
    paths = {int(r.pair_id): pd.concat([g for (s, d), g in groups.items() if s == r.symbol and d.year == year]).sort_values('bar_timestamp').reset_index(drop=True)
             for r in eligible.itertuples()}
    tape = dict(calendar=cal, timeline=timeline, bars=[pertime[t] for t, _, _ in timeline], paths=paths)
    auditor = specialize_cost_auditor()
    auditor.__globals__['scalar_exit'] = scalar_exit_cents
    audit = auditor(out, dict(year=year, side='buy', sl=.07, trailing=.15, tp=None, fee_pct=fee_bps/10000), tape)
    allowed = {(int(r.pair_id), r.timestamp): r for r in eligible.itertuples()}
    for r in trades.itertuples():
        src = allowed[(int(r.pair_id), r.entry_timestamp)]
        if r.expiry != src.due_open or r.entry_timestamp < r.oracle_date.tz_localize('UTC'):
            raise ValueError('Trade lineage/expiry mismatch')
    result = dict(arm=arm, year=year, fee_bps=fee_bps, signals=len(eligible), **risk.base.metrics(m, trades, opened),
                  audit=audit, financing_usd=ledger.interest, full_live_parity=False)
    atomic_json(out/'done.json', result)
    return result


def opportunity_checks(unit):
    checks = []
    for year, g in unit.groupby('year'):
        selected = g[g.P01_signal]
        delta = g.P01-g.WARMUP_CONTROL
        ci = history.monthly_interval(g.oracle_date.dt.tz_localize('UTC'), delta) if len(g) else {}
        halves = {str(h): float((v.P01-v.WARMUP_CONTROL).mean()) for h, v in g.groupby(g.oracle_date.dt.month.le(6))}
        checks.append(dict(year=int(year), opportunities=len(g), p01_signals=len(selected),
            p01_symbols=int(selected.symbol.nunique()), mean_opportunity_increment_pp=float(delta.mean()),
            positive_stress_increment=bool((g.P01_cost25-g.WARMUP_CONTROL_cost25).mean() > 0),
            monthly_interval=ci, half_year_increments=halves))
    return checks


def analyze(root):
    root = Path(root)
    if (root/'report.json').exists(): raise ValueError('Analysis already sealed')
    protocol = READ(root/'protocol.json'); verify_hashes(Path('.'), protocol['sources'])
    verify_hashes(PARENT, READ(PARENT/'snapshot.json')['files'])
    verify_hashes(REFERENCE, READ(REFERENCE/'prepared.json')['files'])
    groups, quality, schedule = load_groups(); sch = schedule.set_index('date')
    cal = history.ArchiveCalendar(schedule)
    campaigns = pd.read_parquet(PARENT/'campaigns.parquet')
    actions = pd.read_parquet(PARENT/'corporate-actions.parquet')
    if not actions.empty: actions['ex_date'] = pd.to_datetime(actions.ex_date)
    units, signals, reservations = [], [], []
    days = pd.DatetimeIndex(schedule.date)
    for i, r in enumerate(campaigns.itertuples(), 1):
        found, why = select_entries(r, groups, schedule)
        why = why or common_reservation(r, found, groups, schedule, actions)
        if why:
            reservations.append(dict(pair_id=int(r.pair_id), symbol=r.symbol, oracle_date=r.oracle_date, reason=why))
        else:
            unit = dict(pair_id=int(r.pair_id), symbol=r.symbol, rank=int(r.rank), year=r.oracle_date.year,
                oracle_date=r.oracle_date, entry_time=sch.loc[days[days.get_loc(r.oracle_date)+1], 'market_open'],
                label_available=sch.loc[days[days.get_loc(r.oracle_date)+40], 'market_open'])
            for arm in ARMS:
                e = found.get(arm); unit[arm+'_signal'] = e is not None
                unit[arm] = unit[arm+'_cost25'] = 0.
                if e is None: continue
                j = days.get_loc(e['date']); due = sch.loc[days[j+20], 'market_open']
                path = pd.concat([groups[r.symbol, d] for d in days[j:j+21]], ignore_index=True)
                outcome = history.unit_outcome(path, e, history.BASE, cal)
                unit[arm] = outcome['net_pct']
                unit[arm+'_cost25'] = history.unit_outcome(path, e, history.BASE, cal, .0025)['net_pct']
                unit[arm+'_exit'] = outcome['exit_time']
                signals.append(dict(pair_id=int(r.pair_id), symbol=r.symbol, rank=int(r.rank), oracle_date=r.oracle_date,
                    year=e['date'].year, arm=arm, due_open=due, **e))
            units.append(unit)
        atomic_json(root/'progress.json', dict(status='SIGNALS_AND_UNIT_PATHS', completed=i, total=213))
    frame = pd.DataFrame(units)
    signal_frame = pd.DataFrame(signals, columns=['pair_id','symbol','rank','oracle_date','year','arm','due_open',
        'timestamp','price','signal_close','signal_bar','prior_high','cross_bar','release_bar','release_age_bars',
        'squeeze_bars','date','delay'])
    frame.to_parquet(root/'unit-results.parquet', index=False)
    signal_frame.to_parquet(root/'signals.parquet', index=False)
    pd.DataFrame(reservations).to_parquet(root/'reservations.parquet', index=False)
    pd.DataFrame(quality).to_parquet(root/'session-quality.parquet', index=False)
    if frame.empty: raise ValueError('No common qualified cohort')
    nonoverlap = history.spaced(frame); nonoverlap.to_parquet(root/'nonoverlap.parquet', index=False)
    checks = opportunity_checks(nonoverlap)
    results = []
    for fee in FEES:
        for year in (2025, 2026):
            for arm in ARMS:
                atomic_json(root/'progress.json', dict(status='PORTFOLIO_REPLAY', completed=len(results), total=12,
                    year=year, arm=arm, fee_bps=fee))
                result = portfolio(root, arm, year, fee, signal_frame, groups, schedule)
                results.append(result)
                print(f'{year} {arm} fee{fee}: {result["return_pct"]:.3f}% DD{result["max_drawdown_pct"]:.3f} trades{result["trades"]}', flush=True)
    table = pd.DataFrame([{k:v for k,v in r.items() if k!='audit'} for r in results])
    table.to_csv(root/'annual-summary.csv', index=False)
    increments = []
    for fee in FEES:
        for year in (2025, 2026):
            a = next(r for r in results if r['arm']=='P01' and r['year']==year and r['fee_bps']==fee)
            b = next(r for r in results if r['arm']=='WARMUP_CONTROL' and r['year']==year and r['fee_bps']==fee)
            increments.append(dict(year=year,fee_bps=fee,return_increment_pp=a['return_pct']-b['return_pct']))
    sufficient = all(any(c['year']==y and c['p01_signals']>=30 and c['p01_symbols']>=10 for c in checks) for y in [2025,2026])
    passes = sufficient and all(r['return_increment_pp']>0 for r in increments) and all(
        c['mean_opportunity_increment_pp']>0 and c['positive_stress_increment'] and
        c['monthly_interval'].get('months',0)>=6 and c['monthly_interval'].get('lower95',-1)>0 for c in checks)
    c26 = next((c for c in checks if c['year']==2026), {})
    passes = passes and len(c26.get('half_year_increments',{}))==2 and all(v>0 for v in c26['half_year_increments'].values())
    report = dict(status='EXPLORATORY_P01_WORTH_CONFIRMATION' if passes else 'INSUFFICIENT_P01_SAMPLE' if not sufficient else 'NO_GO_P01_NOT_CONFIRMED',
        original_campaigns=213, qualified_common_campaigns=len(frame), symbols=int(frame.symbol.nunique()),
        reserved=dict(Counter(r['reason'] for r in reservations)), nonoverlap=len(nonoverlap),
        nonoverlap_checks=checks, portfolio_increments=increments, portfolio_results=results,
        sufficient_sample=sufficient, production_promoted=False, full_live_parity=False,
        files={str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file() and p.name not in ['progress.json','report.json']})
    verify_hashes(Path('.'), protocol['sources'])
    verify_hashes(PARENT, READ(PARENT/'snapshot.json')['files'])
    verify_hashes(REFERENCE, READ(REFERENCE/'prepared.json')['files'])
    atomic_json(root/'report.json', report)
    atomic_json(root/'progress.json', dict(status=report['status'], completed=12, total=12, failed=0))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=['prepare','analyze','run'], default='run')
    p.add_argument('--output-dir', type=Path, default=OUTPUT)
    a = p.parse_args()
    try:
        if a.phase in ('prepare','run'): prepare(a.output_dir)
        if a.phase in ('analyze','run'): analyze(a.output_dir)
    except Exception as exc:
        if (a.output_dir/'protocol.json').exists() and not (a.output_dir/'report.json').exists():
            atomic_json(a.output_dir/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)))
        raise


if __name__ == '__main__': main()
