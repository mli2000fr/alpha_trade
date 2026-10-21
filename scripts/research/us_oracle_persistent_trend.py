"""One frozen prior-session trend gate; offline paired annual portfolio replay.

No training, provider access, SQL, broker calls or production settings changes.
The old conditional 213-campaign cohort is retained, not full TOP10 coverage.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd

from modelFactory.features import _adx
from scripts.research import us_intraday_protection_grid_risk as risk
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

BASE = risk.base
REFERENCE = Path('artifacts/research/us_intraday_protection_grid/20261021-1x-risk-dd15-v1')
DEFAULT_OUTPUT = Path('artifacts/research/us_oracle_persistent_trend/20261021-v1')
RULE = dict(ema_fast=20, ema_slow=50, slope_sessions=5, persistence_sessions=3,
            adx_period=14, adx_minimum=20., warmup_contiguous_sessions=60)
ORIGINAL_CACHE = None
ELIGIBILITY = None


def replay_sources(previous):
    """Preserve historic hashes; explicitly record later dormant runtime changes.

    No blanket hash bypass: each changed file must have a byte-exact historic
    snapshot, be one of the four known winner integration changes, and the
    replay must then reproduce all four original transaction tapes exactly.
    """
    permitted = {'backtesting/simulator.py', 'execution_engine/config.py',
                 'execution_engine/executor.py', 'config.yaml'}
    manifest_path = REFERENCE/'source-snapshot-before-pyramiding.json'
    snapshots = BASE.READ(manifest_path)['files']
    by_original = {str(Path(r['original']).resolve()).lower(): r for r in snapshots}
    sources = {}; drift = []
    for name, expected in previous['sources'].items():
        actual = digest(name)
        if actual != expected:
            relative = str(Path(name).resolve().relative_to(Path('.').resolve())).replace('\\', '/')
            snapshot = by_original.get(str(Path(name).resolve()).lower())
            if relative not in permitted or snapshot is None or snapshot['sha256'] != expected:
                raise ValueError('Unqualified source change: '+name)
            if digest(snapshot['snapshot']) != expected:
                raise ValueError('Historic source snapshot changed: '+name)
            sources[snapshot['snapshot']] = expected
            drift.append(dict(source=name, historical_sha256=expected, replay_sha256=actual,
                              historical_snapshot=snapshot['snapshot']))
        sources[name] = actual
    sources[str(manifest_path)] = digest(manifest_path)
    return sources, drift


def trend_features(frame):
    """Input must be indexed by every exchange session. Never fill missing prices.

    EMA and ADX restart after invalid/missing bars. Every calculation is causal;
    the caller separately shifts its lookup to the previous exchange session.
    """
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise ValueError('Unique ordered exchange-session index required')
    g = frame.copy()
    prices = ['open', 'high', 'low', 'close', 'volume']
    valid = (np.isfinite(g[prices]).all(axis=1) & g[prices].gt(0).all(axis=1)
             & g.high.ge(g[['open', 'close']].max(axis=1))
             & g.low.le(g[['open', 'close']].min(axis=1)) & g.is_filled.eq(0))
    out = pd.DataFrame(index=g.index, columns=['ema20', 'ema50', 'ema20_5ago', 'adx14'], dtype=float)
    out['close'] = g.close.where(valid)
    out['qualified'] = False
    out['long_pass'] = False
    out['short_pass'] = False
    for _, part in g[valid].groupby((~valid).cumsum()[valid]):
        ema20 = part.close.ewm(span=20, adjust=False, min_periods=20).mean()
        ema50 = part.close.ewm(span=50, adjust=False, min_periods=50).mean()
        slope = ema20.shift(5)
        adx = _adx(part.high, part.low, part.close, 14)
        warmed = pd.Series(np.arange(1, len(part)+1) >= 60, index=part.index)
        long_day = part.close.gt(ema20) & ema20.gt(ema50) & ema20.gt(slope) & adx.ge(20)
        short_day = part.close.lt(ema20) & ema20.lt(ema50) & ema20.lt(slope) & adx.ge(20)
        out.loc[part.index, ['ema20', 'ema50', 'ema20_5ago', 'adx14']] = pd.DataFrame(
            dict(ema20=ema20, ema50=ema50, ema20_5ago=slope, adx14=adx))
        out.loc[part.index, 'qualified'] = warmed
        out.loc[part.index, 'long_pass'] = warmed & long_day.rolling(3, min_periods=3).sum().eq(3)
        out.loc[part.index, 'short_pass'] = warmed & short_day.rolling(3, min_periods=3).sum().eq(3)
    return out


def qualify_candidates(candidates, daily, sessions):
    """Exactly previous session, never asof-forward-fill across a missing bar."""
    sessions = pd.DatetimeIndex(sessions)
    daily = daily[daily.symbol.isin(candidates.symbol.unique())].copy()
    daily['date'] = pd.to_datetime(daily.date)
    if daily.duplicated(['symbol', 'date']).any():
        raise ValueError('Ambiguous daily prices')
    features = {s: trend_features(g.set_index('date').reindex(sessions))
                for s, g in daily.groupby('symbol')}
    rows = []
    for r in candidates.itertuples():
        decision = pd.Timestamp(r.decision_time)
        day = pd.Timestamp(decision.tz_convert('America/New_York').date())
        i = sessions.get_loc(day)
        if not i:
            raise ValueError('No prior exchange session')
        source = sessions[i-1]
        f = features[r.symbol].loc[source] if r.symbol in features else None
        qualified = bool(f is not None and f.qualified)
        accepted = bool(qualified and f['long_pass' if r.side == 'buy' else 'short_pass'])
        row = dict(pair_id=int(r.pair_id), symbol=r.symbol, side=r.side, year=int(r.year),
                   oracle_date=r.oracle_date, decision_time=decision, source_date=source,
                   qualified=qualified, accepted=accepted,
                   reason='PASS' if accepted else 'TREND_NOT_CONFIRMED' if qualified else 'MISSING_OR_INSUFFICIENT_DAILY')
        for name in ['close', 'ema20', 'ema50', 'ema20_5ago', 'adx14']:
            row[name] = float(f[name]) if f is not None and pd.notna(f[name]) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def prepare(root):
    root = Path(root)
    if root.resolve() == REFERENCE.resolve() or REFERENCE.resolve() in root.resolve().parents:
        raise ValueError('Preserve sealed reference')
    if root.exists() and any(p.name != 'run.lock' for p in root.iterdir()):
        raise ValueError('Fresh output required; no mixed or silently resumed experiment')
    review = BASE.READ(REFERENCE/'final-review.json')
    verify_hashes(REFERENCE, review['files'])
    report = BASE.READ(REFERENCE/'report.json')
    if report['completed'] != 576 or report['failed'] or review['status'] != 'PASS_COMPLETED_RISK_GRID_REVIEW':
        raise ValueError('Complete sealed DD15 reference required')
    previous = BASE.READ(REFERENCE/'protocol.json')
    sources, drift = replay_sources(previous)
    ready = BASE.READ(REFERENCE/'prepared.json')
    verify_hashes(REFERENCE, ready['files'])
    sources.update({str(p): digest(p) for p in [Path(__file__), BASE.PRICE,
        Path('modelFactory/features.py'), Path('tests/test_us_oracle_persistent_trend.py'),
        REFERENCE/'report.json', REFERENCE/'final-review.json']})
    root.mkdir(parents=True, exist_ok=True)
    atomic_json(root/'protocol.json', dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources=sources, paired_reference=str(REFERENCE), rule=RULE,
        explicitly_recorded_runtime_source_changes=drift,
        source_change_guard='Old snapshots hash-verified; current replay source bytes frozen. '
                            'Exact baseline transactions and metrics required; no assumption of unchanged behavior.',
        hypothesis='One entry-only persistent trend filter, LONG/SHORT mirrored; no new model.',
        signal='At the ORIGINAL first two-close5m breakout entry, gate using previous exchange session only. '
               'For EACH of its last3sessions: LONG close>EMA20>EMA50, EMA20>EMA20[5sessions earlier], ADX14>=20. '
               'SHORT mirrored price/EMA/slope; same ADX strength.60consecutive valid bars required. '
               'Failed gate consumes original signal, no delayed re-entry/retry or TOP11 replacement.',
        unchanged='Same conditional213campaigns/72symbols, annual4000USD,1x,HALF target,SL7,TR15,noTP,OracleJ+20expiry, '
                  'B4DD15/fees8bps perleg/borrow0.3%annual252/financing6.5%ACT360. No holding-time trend exit or adds.',
        comparison='Four baseline annual sides rerun and must match sealed results/trades; four trend arms. '
                   'Same sizing FORMULA, not guaranteed same sizes/trades: different cash and B4 paths.',
        limitations=previous.get('limitations', [])+[
            'Retrospective hypothesis:2025/2026 already studied, NOT fresh holdout. No threshold search.',
            'Daily archive restated, causal date lookup not certification of historical application receipt.',
            'Original expiry counts waiting from Oracle J, NOT new runtime20holding sessions/21stopen.',
            'Two years are not independent trade-level replicates; no claims from naive IID significance.'],
        full_live_parity=False, training=False, sql_writes=False, provider_calls=False, broker_calls=False))
    for name in ready['files']:
        shutil.copyfile(REFERENCE/name, root/name)
    daily = pd.read_parquet(BASE.PRICE)
    from modelFactory.oracle.build_labels import nyse_sessions
    sessions = nyse_sessions(pd.to_datetime(daily.date).min(), pd.to_datetime(daily.date).max())
    eligible = qualify_candidates(pd.read_parquet(root/'candidates.parquet'), daily, sessions)
    eligible.to_parquet(root/'eligibility.parquet', index=False)
    hashes = dict(ready['files']); hashes['eligibility.parquet'] = digest(root/'eligibility.parquet')
    atomic_json(root/'prepared.json', dict(files=hashes, signals=len(eligible),
        qualified=int(eligible.qualified.sum()), accepted=int(eligible.accepted.sum())))
    for arm in ['baseline', 'trend']:
        target = root/arm; target.mkdir()
        for name in ['production-risk.json', 'risk-regimes.parquet']:
            shutil.copyfile(root/name, target/name)
    return eligible


def worker_init(root):
    global ORIGINAL_CACHE, ELIGIBILITY
    risk.worker_init(root)
    ORIGINAL_CACHE = BASE.CACHE
    ELIGIBILITY = pd.read_parquet(Path(root)/'eligibility.parquet')


def worker_case(root, arm, year, side):
    c = dict(year=year, side=side, sl=.07, trailing=.15, horizon=20, tp=None)
    tape = dict(ORIGINAL_CACHE[year])
    if arm == 'trend':
        accepted = ELIGIBILITY[ELIGIBILITY.accepted][['pair_id', 'side', 'decision_time']]
        tape['candidates'] = tape['candidates'].merge(accepted, on=['pair_id', 'side', 'decision_time'],
                                                     how='inner', validate='one_to_one')
    BASE.CACHE = dict(ORIGINAL_CACHE); BASE.CACHE[year] = tape
    directory = Path(root)/arm
    risk.ACTIVE_OUTPUT = directory/'cases'/BASE.case_key(c)
    result = BASE.run_case(directory, c)
    result['arm'] = arm
    if result['status'] == 'COMPLETED_EXPLORATORY':
        trades = pd.read_parquet(risk.ACTIVE_OUTPUT/'trades.parquet')
        opened = BASE.READ(risk.ACTIVE_OUTPUT/'open-positions.json')
        rows = trades.to_dict('records')+opened
        allowed = {(int(r.pair_id), r.side, r.decision_time)
                   for r in tape['candidates'].itertuples()}
        for r in rows:
            if (int(r['pair_id']), r['side'], pd.Timestamp(r['entry_timestamp'])) not in allowed:
                raise ValueError('Trade not admitted by frozen candidate gate')
        if arm == 'baseline':
            old = next(r for r in BASE.READ(REFERENCE/'report.json')['cases'] if r['case'] == result['case'])
            for key in ['return_pct', 'final_capital_usd', 'net_pnl_usd', 'max_drawdown_pct',
                        'trades', 'winners', 'losers', 'mean_capital_used_usd', 'open_positions']:
                if not np.isclose(result[key], old[key], atol=1e-7, rtol=1e-12):
                    raise ValueError('Baseline no longer reproduces '+key)
            pd.testing.assert_frame_equal(trades, pd.read_parquet(REFERENCE/'cases'/result['case']/'trades.parquet'))
            if opened != BASE.READ(REFERENCE/'cases'/result['case']/'open-positions.json'):
                raise ValueError('Baseline open positions changed')
        result['entry_gate_audit'] = 'PASS'
        result['baseline_reproduction'] = 'PASS' if arm == 'baseline' else 'NOT_APPLICABLE'
    return result


def run(root, workers=2):
    from scripts.research.oracle_path_confirmation import exclusive_run
    root = Path(root)
    with exclusive_run(root):
        prepare(root)
        plan = [(arm, year, side) for arm in ['baseline', 'trend'] for year in [2025, 2026] for side in ['buy', 'sell']]
        rows = []; started = time.monotonic()
        atomic_json(root/'progress.json', dict(status='RUNNING', completed=0, failed=0, total=8))
        with ProcessPoolExecutor(max_workers=workers, initializer=worker_init, initargs=(str(root),)) as pool:
            for future in as_completed([pool.submit(worker_case, str(root), *case) for case in plan]):
                row = future.result(); rows.append(row)
                atomic_json(root/'progress.json', dict(status='RUNNING', completed=len(rows),
                    failed=sum(r['status'] != 'COMPLETED_EXPLORATORY' for r in rows), total=8,
                    last=row['arm']+'/'+row['case'], elapsed_seconds=time.monotonic()-started))
        verify_hashes(Path('.'), BASE.READ(root/'protocol.json')['sources'])
        verify_hashes(root, BASE.READ(root/'prepared.json')['files'])
        for row in rows:
            if row['status'] == 'COMPLETED_EXPLORATORY':
                verify_hashes(root/row['arm']/'cases'/row['case'], row['files'])
        ok = [r for r in rows if r['status'] == 'COMPLETED_EXPLORATORY']
        status = 'COMPLETED_EXPLORATORY' if len(ok) == 8 else 'PARTIAL_FAILED'
        pd.DataFrame([{k: v for k, v in r.items() if k not in ('files', 'audit', 'traceback')}
                      for r in rows]).to_csv(root/'annual-summary.csv', index=False)
        report = dict(status=status, completed=len(ok), failed=8-len(ok), total=8, cases=rows,
                      full_live_parity=False, elapsed_seconds=time.monotonic()-started)
        atomic_json(root/'report.json', report)
        atomic_json(root/'progress.json', {k: v for k, v in report.items() if k != 'cases'})
        atomic_json(root/'final-review.json', dict(status='PASS_PAIRED_TREND_RESEARCH' if len(ok) == 8 else 'FAILED',
            baseline_exact_reproduction=len(ok) == 8, independent_human_review=False,
            files={n: digest(root/n) for n in ['protocol.json', 'prepared.json', 'report.json', 'annual-summary.csv']}))
        return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    p.add_argument('--workers', type=int, choices=range(1, 5), default=2)
    a = p.parse_args()
    run(a.output, a.workers)
