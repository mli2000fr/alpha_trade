"""P05: previous ten complete regular-session lows, offline LONG comparison.

No provider, SQL, training, broker or production changes. Parent replay is
injected only in this serial process; its sealed source is never modified.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from common.config_loader import load_config
from scripts.research import us_oracle_compression_p01 as parent
from scripts.research.us_oracle_partial_p02 import validate_config
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

READ = parent.READ
REFERENCE = parent.OUTPUT
OUTPUT = Path('artifacts/research/us_oracle_low_channel_p05/20261022-v2')
ARMS = ('WINNER', 'COMMON_WINNER', 'P05')
FEES = (8, 25)
RULE = dict(stop_pct=.07, lookback_sessions=10, horizon_sessions=20,
            first_update='ENTRY_SESSION_CLOSE', effective='NEXT_SESSION_OPEN', rounding='CENT')
ORIGINAL_LEDGER = parent.CentLedger
ORIGINAL_SCALAR = parent.scalar_exit_cents
# Populated from immutable, qualified regular raw SIP bars, not adjusted daily bars.
CHANNELS = {}
CLOSES = {}
NEXT_OPENS = {}


def build_channels(groups, schedule):
    days = list(schedule.date)
    lows = {key: float(frame.low.min()) for key, frame in groups.items()}
    channels = {}
    for (symbol, day) in groups:
        i = days.index(day)
        prior = days[max(0, i-9):i+1]
        if len(prior) == 10 and all((symbol, d) in lows for d in prior):
            channels[symbol, day] = round(min(lows[symbol, d] for d in prior), 2)
    return channels


def install_history(groups, schedule):
    global CHANNELS, CLOSES, NEXT_OPENS
    CHANNELS = build_channels(groups, schedule)
    CLOSES = dict(zip(schedule.date, schedule.market_close))
    NEXT_OPENS = dict(zip(schedule.date.iloc[:-1], schedule.market_open.iloc[1:]))
    from scripts.research.us_oracle_low_channel_p05_audit import configure_history
    configure_history(groups, schedule)


def common_cohort(signals, schedule):
    days = list(schedule.date); accepted = []; reserves = []
    for s in signals.itertuples():
        i = days.index(s.date)
        missing = [d for d in days[i:i+20] if (s.symbol, d) not in CHANNELS]
        if missing:
            reserves.append(dict(pair_id=int(s.pair_id), symbol=s.symbol, oracle_date=s.oracle_date,
                                 reason='INCOMPLETE_TEN_PRIOR_REGULAR_SESSIONS', missing_channel_dates=missing))
        else:
            accepted.append(int(s.pair_id))
    return signals[signals.pair_id.isin(accepted)].copy(), reserves


class LowChannelLedger(ORIGINAL_LEDGER):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_stops = {}; self.channel_events = []

    def known_stop(self, symbol):
        p = self.state.positions[symbol]
        key = (symbol, self.live_meta[symbol]['entry_timestamp'])
        return self.channel_stops.get(key, round(p.entry_price*(1-.07), 2))

    def finish_day(self):
        value = super().finish_day()
        # Current day's low is now complete. No execution at this close using
        # the new stop: the next begin_bar resolves it at the next real open.
        for symbol, position in self.state.positions.items():
            key = (symbol, self.live_meta[symbol]['entry_timestamp'])
            prior = self.known_stop(symbol)
            channel = CHANNELS[symbol, self.day]  # fail closed; never ffill
            stop = max(prior, round(position.entry_price*(1-.07), 2), channel)
            self.channel_stops[key] = stop
            self.channel_events.append(dict(symbol=symbol, pair_id=int(self.live_meta[symbol]['pair_id']),
                entry_timestamp=key[1], asof_session=self.day, observed_at=CLOSES[self.day],
                effective_at=NEXT_OPENS[self.day], channel_low=channel, previous_stop=prior,
                stop=stop, entry_price=position.entry_price, expiry=self.live_meta[symbol]['expiry']))
        if self.day == self.days[-1]:
            atomic_json(self.guard_output/'channel-updates.json', self.channel_events)
        return value


def unit_outcome(path, entry, expiry, fee):
    price = float(entry['price']); stop = round(price*(1-.07), 2)
    prior_day = None; tightened = False; symbol = str(path.symbol.iloc[0])
    for r in path.itertuples():
        day = pd.Timestamp(r.bar_timestamp.tz_convert('America/New_York').date())
        if prior_day is not None and day != prior_day:
            new_stop = max(stop, CHANNELS[symbol, prior_day])
            tightened = tightened or new_stop > stop
            stop = new_stop
        prior_day = day
        if r.open <= stop: fill, stamp = float(r.open), r.bar_timestamp
        elif r.bar_timestamp >= expiry: fill, stamp = float(r.open), r.bar_timestamp
        elif r.low <= stop: fill, stamp = stop, r.bar_end_timestamp
        else: continue
        return dict(net_pct=100*((fill-price)/price-fee*(1+fill/price)), price=fill,
                    time=stamp, tightened=tightened)
    raise ValueError('Mature path must exit')


@contextmanager
def replay_variant(arm):
    from scripts.research.us_oracle_low_channel_p05_audit import scalar_exit
    old = parent.CentLedger, parent.scalar_exit_cents
    try:
        if arm == 'P05': parent.CentLedger, parent.scalar_exit_cents = LowChannelLedger, scalar_exit
        elif arm in ('WINNER', 'COMMON_WINNER'):
            parent.CentLedger, parent.scalar_exit_cents = ORIGINAL_LEDGER, ORIGINAL_SCALAR
        else: raise ValueError('Unknown frozen arm')
        yield
    finally:
        parent.CentLedger, parent.scalar_exit_cents = old


def prepare(root):
    root = Path(root)
    if root.exists(): raise ValueError('Fresh immutable output required')
    verify_hashes(REFERENCE, READ(REFERENCE/'report.json')['files'])
    audit = READ(REFERENCE/'final-audit.json')
    if audit['status'] != 'PASS_P01_SEPARATE_ARITHMETIC_AND_PORTFOLIO_AUDITS' or audit['primary_report_sha256'] != digest(REFERENCE/'report.json'):
        raise ValueError('Verified reference required')
    config = load_config()['winner_pyramiding']; validate_config(config)
    sources = dict(READ(REFERENCE/'protocol.json')['sources'])
    files = [Path(__file__), Path('scripts/research/us_oracle_low_channel_p05_audit.py'),
        Path('tests/test_us_oracle_low_channel_p05.py'), Path('doc/ml/oracle_low_channel_p05_20261022.md'),
        Path('config.yaml'), Path('scripts/research/us_oracle_partial_p02.py'),
        Path('risk_management/concentration.py'), REFERENCE/'report.json', REFERENCE/'final-audit.json']
    sources.update({str(p): digest(p) for p in files})
    root.mkdir(parents=True)
    atomic_json(root/'protocol.json', dict(created_at_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
        reference=str(REFERENCE), rule=RULE, arms=ARMS, fees_bps_per_leg=FEES,
        intervention='Replace TR15 only by prior10daily lows. Entry day hardSL only, '
            'after each complete session stop=max(previous,round(E*(1-.07),2),round(min10low,2)). '
            'Effective next session open; never current-day low intraday; no loosening/add/partial/TP.',
        entry='Frozen WINNER entries, fresh prior raw-session high crossing, two regular5m closes, next contiguous open.',
        coverage='Local sealed raw regular unfilled SIP only. Daily lows aggregated from COMPLETE '
            'qualified5m sessions, including early closes. Require channels for ALL20holding sessions '
            'before outcomes, even if an eventual stop would occur earlier. Missing history reserved '
            'identically in COMMON_WINNER/P05. Full WINNER anchor must reproduce byte-exactly.',
        unchanged='Annual4000USD,1x entry gross cap, HALF/noadd/native SL7sizing/constraints/B4DD15, '
            '20holding sessions entry included thenOPEN21, 8/25bps perleg. No2024 absent frozen archive.',
        evaluation='One N10 rule, no parameter search; paired units and conservativeOracleJ40 '
            'nonoverlap/monthly bootstrap2000seed731. Known2025/2026, not pristine holdout.',
        criteria=dict(min_nonoverlap_per_year=30, min_tightened_per_year=10,
            positive_return_increment_both_years_both_fees=True, dd_not_worse_both_years_fee8=True,
            positive_unit_increment_both_years_fee25=True, monthly_lower95_gt_zero=True, minimum_months=6),
        limitations=READ(REFERENCE/'protocol.json')['limitations']+[
            'Future-path and ten-session complete-history conditional sample, not all daily TOP10.',
            'Research CatBoost PATH_H20 campaigns, not production LightGBM.',
            'No historical NBBO/queue/stop-replacement latency qualification; not full live parity.'],
        configured_winner=config, training=False, sql_writes=False, provider_calls=False,
        broker_calls=False, production_changes=False, full_live_parity=False))
    atomic_json(root/'progress.json', dict(status='PREPARED', completed=0, total=12))


def unit_results(root, signals, groups, schedule):
    days = pd.DatetimeIndex(schedule.date); sch = schedule.set_index('date'); rows = []
    for s in signals.itertuples():
        i = days.get_loc(s.date)
        frame = pd.concat([groups[s.symbol, d] for d in days[i:i+21]], ignore_index=True)
        frame = frame[frame.bar_timestamp.between(s.timestamp, s.due_open)].reset_index(drop=True)
        row = dict(pair_id=int(s.pair_id), symbol=s.symbol, rank=int(s.rank), year=s.oracle_date.year,
            oracle_date=s.oracle_date, entry_time=s.timestamp,
            label_available=sch.loc[days[days.get_loc(s.oracle_date)+40], 'market_open'])
        for fee in FEES:
            entry = dict(timestamp=s.timestamp, price=s.price)
            b = parent.history.unit_outcome(frame, entry, parent.history.BASE,
                                           parent.history.ArchiveCalendar(schedule), fee/10000)
            p = unit_outcome(frame, entry, s.due_open, fee/10000)
            row[f'WINNER_{fee}'] = b['net_pct']; row[f'P05_{fee}'] = p['net_pct']
            row.update(tightened=p['tightened'], P05_exit=p['time'], P05_exit_price=p['price'])
        rows.append(row)
    units = pd.DataFrame(rows); units.to_parquet(root/'unit-results.parquet', index=False)
    spaced = parent.history.spaced(units); spaced.to_parquet(root/'nonoverlap.parquet', index=False)
    checks = []
    for year, g in spaced.groupby('year'):
        ci = parent.history.monthly_interval(g.oracle_date.dt.tz_localize('UTC'), g.P05_8-g.WINNER_8)
        checks.append(dict(year=int(year), n=len(g), tightened=int(g.tightened.sum()),
            increment_pp=float((g.P05_8-g.WINNER_8).mean()),
            stress_increment_pp=float((g.P05_25-g.WINNER_25).mean()), ci=ci))
    return checks


def analyze(root):
    root = Path(root)
    if (root/'report.json').exists(): raise ValueError('Already sealed')
    protocol = READ(root/'protocol.json'); verify_hashes(Path('.'), protocol['sources'])
    verify_hashes(REFERENCE, READ(REFERENCE/'report.json')['files'])
    groups, _, schedule = parent.load_groups(); install_history(groups, schedule)
    original = pd.read_parquet(REFERENCE/'signals.parquet'); original = original[original.arm.eq('WINNER')].copy()
    common, reserves = common_cohort(original, schedule)
    original.to_parquet(root/'full-entry-signals.parquet', index=False)
    common.to_parquet(root/'entry-signals.parquet', index=False)
    atomic_json(root/'coverage-reserves.json', reserves)
    lows = pd.DataFrame([dict(symbol=s, date=d, low=float(g.low.min())) for (s, d), g in groups.items()])
    lows.to_parquet(root/'complete-session-lows.parquet', index=False)
    pd.DataFrame([dict(symbol=s, date=d, channel=c) for (s, d), c in CHANNELS.items()]).to_parquet(root/'channels.parquet', index=False)
    signals = pd.concat([original.assign(arm='WINNER'), common.assign(arm='COMMON_WINNER'), common.assign(arm='P05')], ignore_index=True)
    checks = unit_results(root, common, groups, schedule); results = []
    for fee in FEES:
        for year in (2025, 2026):
            for arm in ARMS:
                atomic_json(root/'progress.json', dict(status='RUNNING', completed=len(results), total=12, year=year, arm=arm, fee_bps=fee))
                with replay_variant(arm): r = parent.portfolio(root, arm, year, fee, signals, groups, schedule)
                out = root/f'{arm}-fee{fee}'/'cases'/str(year)
                if arm == 'WINNER':
                    old = REFERENCE/f'WINNER-fee{fee}'/'cases'/str(year)
                    for name in ['trades.parquet', 'marks.parquet', 'decisions.json', 'maintenance.json', 'production-risk-events.json']:
                        if digest(out/name) != digest(old/name): raise ValueError('Exact baseline changed:'+name)
                r['baseline_exact_reproduction'] = arm == 'WINNER'
                r['channel_updates'] = len(READ(out/'channel-updates.json')) if arm == 'P05' else 0
                results.append(r)
                print(f'{year} {arm} fee{fee}: {r["return_pct"]:.3f}% DD{r["max_drawdown_pct"]:.3f} trades{r["trades"]}', flush=True)
    comparisons = []
    for fee in FEES:
        for year in (2025, 2026):
            b = next(r for r in results if r['arm']=='COMMON_WINNER' and r['year']==year and r['fee_bps']==fee)
            p = next(r for r in results if r['arm']=='P05' and r['year']==year and r['fee_bps']==fee)
            comparisons.append(dict(year=year, fee_bps=fee, return_increment_pp=p['return_pct']-b['return_pct'],
                                    dd_increment_pp=p['max_drawdown_pct']-b['max_drawdown_pct']))
    sufficient = all(any(c['year']==y and c['n']>=30 and c['tightened']>=10 for c in checks) for y in (2025, 2026))
    passes = sufficient and all(c['return_increment_pp']>0 for c in comparisons) and all(
        c['dd_increment_pp']<=0 for c in comparisons if c['fee_bps']==8) and all(
        c['stress_increment_pp']>0 and c['ci']['months']>=6 and c['ci']['lower95']>0 for c in checks)
    pd.DataFrame([{k:v for k,v in r.items() if k!='audit'} for r in results]).to_csv(root/'annual-summary.csv', index=False)
    verify_hashes(Path('.'), protocol['sources']); verify_hashes(REFERENCE, READ(REFERENCE/'report.json')['files'])
    report = dict(status='EXPLORATORY_P05_WORTH_CONFIRMATION' if passes else 'INSUFFICIENT_P05_SAMPLE' if not sufficient else 'NO_GO_P05_NOT_CONFIRMED',
        full_campaigns=len(original), common_campaigns=len(common), reserved_campaigns=len(reserves),
        symbols=int(common.symbol.nunique()), results=results, comparisons=comparisons, unit_checks=checks,
        production_promoted=False, files={str(p.relative_to(root)):digest(p) for p in root.rglob('*')
            if p.is_file() and p.name not in ['run.lock','progress.json','report.json']})
    atomic_json(root/'report.json', report)
    atomic_json(root/'progress.json', dict(status=report['status'], completed=12, total=12, failed=0))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=OUTPUT)
    parser.add_argument('--phase', choices=['prepare','analyze','run'], default='run'); args = parser.parse_args()
    from scripts.research.oracle_path_confirmation import exclusive_run
    try:
        if args.phase in ('prepare','run'): prepare(args.output_dir)
        if args.phase in ('analyze','run'):
            with exclusive_run(args.output_dir): analyze(args.output_dir)
    except Exception as exc:
        if (args.output_dir/'protocol.json').exists() and not (args.output_dir/'report.json').exists():
            atomic_json(args.output_dir/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)))
        raise


if __name__ == '__main__': main()
