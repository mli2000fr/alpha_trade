"""Frozen Oracle candidates and H20 memberships, exits at 5/10/20 sessions.

Research only: cached prices/outcomes, no SQL, API, fitting, production or orders.
Full 20-session qualified cohort is identical across durations. Even independent
controls keep the same 20-session spacing, not extra short-horizon re-entries.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from scripts.research import us_top10_symbol_reliability as gate
from scripts.research import us_tradable_symbol_reliability as base
from scripts.research import us_tradable_tp10_variants as previous
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

FULL = Path('artifacts/research/us_tradable_tp10_variants/20261019-v2')
TOP = Path('artifacts/research/us_oracle_top20pct_tp10/20261019-v2')
HORIZONS = (5, 10, 20)
KEYS = ['date', 'symbol', 'side']
FLAGS = ['symbol_pass', 'opposite_pass', 'chosen_side', 'rebalance_date']
RTOL = 1e-12
LOG = logging.getLogger(__name__)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def paths(bars, positions, side, *, horizon, tp=.10, sl=.10):
    """Generalized existing close-expiry contract, not train/barrier expiry-open."""
    if type(horizon) is not int or not 1 <= horizon <= 20:
        raise ValueError('Integer holding horizon from 1 to 20 required')
    if side not in ('LONG', 'SHORT') or not 0 < tp < 1 or (sl is not None and not 0 < sl < 1):
        raise ValueError('Invalid side/TP/SL')
    raw = np.asarray(positions)
    if raw.ndim != 1 or len(raw) == 0 or not np.isfinite(raw).all() or not np.equal(raw, np.floor(raw)).all():
        raise ValueError('Nonempty integer decision positions required')
    positions = raw.astype(int)
    if (positions < 0).any() or (positions+horizon >= len(bars)).any():
        raise ValueError('Incomplete future window')
    a = {k: sliding_window_view(bars[k].to_numpy(float), horizon)[positions+1] for k in ('open', 'high', 'low', 'close')}
    if any(not np.isfinite(v).all() or (v <= 0).any() for v in a.values()):
        raise ValueError('Invalid path prices')
    entry = a['open'][:, 0]; long = side == 'LONG'; sign = 1 if long else -1
    take = entry*(1+tp if long else 1-tp); tt = RTOL*np.abs(take)
    n = len(positions); stop = None if sl is None else entry*(1-sl if long else 1+sl)
    tol = None if sl is None else RTOL*np.abs(stop)
    hit_tp = a['high'] >= (take-tt)[:, None] if long else a['low'] <= (take+tt)[:, None]
    hit_sl = np.zeros((n, horizon), dtype=bool) if sl is None else (
        a['low'] <= (stop+tol)[:, None] if long else a['high'] >= (stop-tol)[:, None])
    code = np.zeros(n, dtype=np.int8); exit_price = a['close'][:, -1].copy()
    age = np.full(n, horizon, dtype=np.int16)
    ambiguous = np.zeros(n, dtype=bool); gap_stop = np.zeros(n, dtype=bool); at_open = np.zeros(n, dtype=bool)
    for k in range(horizon):
        active = code == 0
        os = np.zeros(n, dtype=bool) if k == 0 or sl is None else active & (
            a['open'][:, k] <= stop+tol if long else a['open'][:, k] >= stop-tol)
        ot = np.zeros(n, dtype=bool) if k == 0 else active & ~os & (
            a['open'][:, k] >= take-tt if long else a['open'][:, k] <= take+tt)
        st = active & ~os & ~ot & hit_sl[:, k]; target = active & ~os & ~ot & ~st & hit_tp[:, k]
        code[os | st] = 2; code[ot | target] = 1
        exit_price[os] = a['open'][os, k]
        if stop is not None: exit_price[st] = stop[st]
        exit_price[ot | target] = take[ot | target]; age[os | ot | st | target] = k+1
        ambiguous[st & hit_tp[:, k]] = True; gap_stop[os] = True; at_open[os | ot] = True
    adverse = 1-a['low']/entry[:, None] if long else a['high']/entry[:, None]-1
    day = np.arange(horizon)[None, :]
    prior = day < age[:, None]-1
    mae_before = np.maximum(0., np.where(prior, adverse, 0.).max(axis=1))
    mae_through = np.maximum(0., np.where(day < age[:, None], adverse, 0.).max(axis=1))
    open_adverse = np.maximum(0., -sign*(exit_price/entry-1))
    mae_through[at_open] = np.maximum(mae_before[at_open], open_adverse[at_open])
    terminal = sign*(a['close'][:, -1]/entry-1)
    return dict(outcome=np.array(['TIMEOUT', 'TP', 'SL'])[code], tp_first=code == 1, sl_first=code == 2,
        ambiguity=ambiguous, gap_stop=gap_stop, entry_price=entry, exit_price=exit_price, exit_session=age,
        path_return=sign*(exit_price/entry-1), terminal_direction_right=terminal > 0,
        mae_before_exit_bar=mae_before, mae_through_exit_bar=mae_through,
        terminal_signed_return=terminal)


def align_memberships(frame, reference):
    """Never learn/requalify symbols on the shorter horizon's outcomes."""
    if frame.duplicated(KEYS).any() or reference.duplicated(KEYS).any(): raise ValueError('Duplicate pair')
    result = frame.merge(reference[KEYS+FLAGS], on=KEYS, how='left', validate='one_to_one')
    if result[FLAGS].isna().any().any(): raise ValueError('Missing frozen membership')
    return result


def prepare(root):
    if (root/'protocol.json').exists():
        p = read(root/'protocol.json'); verify_hashes(Path('.'), p['sources']); return p
    root.mkdir(parents=True, exist_ok=False)
    full = read(FULL/'protocol.json'); top = read(TOP/'protocol.json')
    verify_hashes(Path('.'), full['source_hashes']); verify_hashes(Path('.'), top['sources'])
    if read(TOP/'final-audit.json')['status'] != 'PASS_EXPLORATORY_ONLY': raise ValueError('Unaudited source')
    files = [Path(__file__), Path('tests/test_us_oracle_holding_horizons.py'), Path(base.__file__), Path(gate.__file__),
        Path(previous.__file__), FULL/'protocol.json', FULL/'report.json', TOP/'protocol.json', TOP/'report.json',
        TOP/'final-audit.json', Path(full['prices']), Path(full['universe_path'])]
    for name in previous.PROFILES:
        for source in (FULL, TOP):
            report = read(source/name/'report.json'); verify_hashes(source/name, report['files'])
            files += [source/name/'report.json', source/name/'evaluations.parquet']
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), sources={str(f): digest(f) for f in files},
        horizons=list(HORIZONS), profiles=previous.PROFILES, symbols=full['symbols'], universe_count=full['universe_count'],
        prices=full['prices'], annual_models=top['annual_models'], universe_path=full['universe_path'],
        test_years=[2025, 2026], last_mature_decision='2026-09-01', observation_end='2026-09-30',
        scopes=['FULL_TRADABLE', 'ORACLE_TOP20PCT'], model_target='UNCHANGED_ORACLE_PATH_H20',
        entries='Same qualified symbol/date/side pairs at all horizons; no new late-2026 H5-only entries',
        membership='Reuse H20 memberships per scope/profile exactly; no recalculation or new model fit',
        independent_control='Same H20 spacing and keys at all horizons, even if TP hit earlier; NOT horizon-specific re-entry rate',
        last_path_date='Original H20 cohort/maturity/spacing date; holding_last_date is actual max holding end',
        entry='J+1 open; entry counts as session 1; expire close session N', trailing=False,
        tp_gap='At limit, no favourable improvement', sl_gap='At open beyond stop; loss not capped',
        collision='Stop first unless open resolves first touch', boundary_relative_tolerance=RTOL,
        fees_per_leg=gate.COST_PER_LEG, borrow_annual=gate.BORROW_ANNUAL,
        direction='Terminal sign at N reported separately from TP/SL trade outcome; no claim of trained H5/H10 prediction',
        sql=False, api_calls=0, new_model_fit=False, production_changed=False, orders=False, portfolio_pnl=False,
        reserves=['Current survivor universe; previously explored years; not untouched validation',
            'Existing adjusted OHLC/OST price discontinuities remain unqualified, not fixed or clipped',
            'Repeated hypothetical entry outcomes, not capital return; real margin, borrow, dividends not reconstructed',
            'No-SL large loss possible; short losses may exceed entry notional; no forced margin liquidation',
            'Common H20-qualified population excludes incomplete paths even if H5 would be known'])
    atomic_json(root/'protocol.json', p)
    for name in p['profiles']:
        for horizon in HORIZONS: (root/name/f'H{horizon}'/'parts').mkdir(parents=True)
    return p


def build(root):
    p = read(root/'protocol.json'); verify_hashes(Path('.'), p['sources'])
    if (root/'paths-manifest.json').exists():
        verify_hashes(root, read(root/'paths-manifest.json')['files']); return
    from modelFactory.oracle.build_labels import nyse_sessions
    days = nyse_sessions('2023-01-01', '2026-10-09')
    keys = pd.read_parquet(FULL/'TP10_SL10'/'evaluations.parquet', columns=KEYS+['year', 'entry_date', 'last_path_date'])
    reference = keys[keys.side.eq('LONG')].copy()
    groups = {str(s): g for s, g in reference.groupby('symbol', observed=True)}
    price = pd.read_parquet(p['prices']); price.date = pd.to_datetime(price.date)
    bars_by_symbol = {str(s): g for s, g in price.groupby('symbol', observed=True)}
    files = {}; parity_rows = 0
    for offset in range(0, len(p['symbols']), 25):
        chunk = offset//25; marker = root/f'chunk-{chunk:04}.json'
        if marker.exists():
            done = read(marker); verify_hashes(root, done['files']); files.update(done['files']); parity_rows += done['parity_rows']; continue
        frames = {(name, h): [] for name in p['profiles'] for h in HORIZONS}
        for symbol in p['symbols'][offset:offset+25]:
            group = groups[symbol]; positions = days.get_indexer(pd.DatetimeIndex(group.date))
            if (positions < 0).any(): raise ValueError('Non-session original decision')
            bars = bars_by_symbol[symbol].set_index('date').reindex(days)
            for side in ('LONG', 'SHORT'):
                for name, protection in p['profiles'].items():
                    for h in HORIZONS:
                        outcome = paths(bars, positions, side, horizon=h, **protection)
                        if h == 20:
                            original = previous.paths(bars, positions, side, **protection)
                            for field, expected in original.items():
                                np.testing.assert_array_equal(outcome[field], expected)
                        frames[(name, h)].append(pd.DataFrame(dict(date=group.date.to_numpy(), symbol=symbol, side=side,
                            year=group.year.to_numpy(), entry_date=group.entry_date.to_numpy(),
                            last_path_date=group.last_path_date.to_numpy(), holding_last_date=days[positions+h], **outcome)))
        new_files = {}
        for (name, h), pieces in frames.items():
            part = root/name/f'H{h}'/'parts'/f'{chunk:04}.parquet'
            frame = pd.concat(pieces, ignore_index=True)
            frame['symbol'] = frame.symbol.astype('category'); frame['side'] = frame.side.astype('category')
            frame.to_parquet(part, index=False); new_files[str(part.relative_to(root))] = digest(part)
        count = sum(len(groups[s])*2 for s in p['symbols'][offset:offset+25])*len(p['profiles'])
        done = dict(files=new_files, parity_rows=count, symbols=p['symbols'][offset:offset+25])
        atomic_json(marker, done); files.update(new_files); parity_rows += count
        LOG.info('Built all six exits: %d/%d symbols', min(offset+25, len(p['symbols'])), len(p['symbols']))
        atomic_json(root/'progress.json', dict(status='RUNNING', phase='SIX_EXIT_VARIANTS', completed=min(offset+25, len(p['symbols'])), total=len(p['symbols'])))
    verify_hashes(Path('.'), p['sources'])
    atomic_json(root/'paths-manifest.json', dict(files=files, h20_formula_parity_rows=parity_rows, total_symbols=len(groups)))


def compare_h20(frame, reference, days):
    joined = frame.merge(reference[KEYS+['net_outcome', 'terminal_direction_right']], on=KEYS,
        validate='one_to_one', suffixes=('', '_h20'))
    if len(joined) != len(reference): raise ValueError('Different horizon comparison cohort')
    rows = []
    for year, group in joined.groupby('year'):
        for arm in gate.ARMS:
            g = gate.chosen(group, arm)
            if g.empty: continue
            daily = (g.net_outcome-g.net_outcome_h20).groupby(g.date).mean()
            rows.append(dict(year=int(year), arm=arm, n=len(g), net_gain_vs_h20=gate.block_interval(daily, days),
                terminal_right=float(g.terminal_direction_right.mean()),
                terminal_right_h20=float(g.terminal_direction_right_h20.mean()),
                terminal_sign_changed=float(g.terminal_direction_right.ne(g.terminal_direction_right_h20).mean())))
    return rows


def run_case(root, name, horizon):
    folder = root/name/f'H{horizon}'
    if (folder/'report.json').exists():
        report = read(folder/'report.json'); verify_hashes(folder, report['files']); return report
    manifest = read(root/'paths-manifest.json')['files']
    files = {n: h for n, h in manifest.items() if Path(n).parts[:2] == (name, f'H{horizon}')}
    verify_hashes(root, files)
    raw = pd.concat([pd.read_parquet(root/n) for n in files], ignore_index=True)
    raw['symbol'] = raw.symbol.astype('category'); raw['side'] = raw.side.astype('category')
    raw = gate.attach_costs(raw)
    full = pd.read_parquet(FULL/name/'evaluations.parquet')
    top = pd.read_parquet(TOP/name/'evaluations.parquet')
    if len(raw) != len(full): raise ValueError('Full population changed')
    full_scoped = align_memberships(raw, full)
    # Original TOP20% already frozen before future outcomes. Only matching pairs.
    top_raw = raw.merge(top[KEYS+['oracle_rank', 'scored_count', 'selected_count']], on=KEYS, validate='one_to_one')
    if len(top_raw) != len(top): raise ValueError('TOP20% population changed')
    top_scoped = align_memberships(top_raw, top)
    from modelFactory.oracle.build_labels import nyse_sessions
    days = nyse_sessions('2023-01-01', '2026-10-09')
    results = {}; new_files = []
    for scope, frame, old in [('FULL_TRADABLE', full_scoped, full), ('ORACLE_TOP20PCT', top_scoped, top)]:
        results[scope] = dict(**base.summary_bundle(frame, days), risk=previous.risk_summary(frame),
            paired_h20=compare_h20(frame, old, days))
        path = folder/f'{scope}.parquet'; frame.to_parquet(path, index=False); new_files.append(path.name)
        # Existing H20 outcome/cost/flags must match exactly, not just aggregate PnL.
        if horizon == 20:
            left = frame[old.columns].sort_values(KEYS).reset_index(drop=True)
            right = old.sort_values(KEYS).reset_index(drop=True)
            pd.testing.assert_frame_equal(left, right, check_dtype=False, check_categorical=False)
    report = dict(status='COMPLETED_EXPLORATORY_PRICE_RESERVE_NO_PROMOTION', horizon=horizon, profile=name,
        protocol_sha256=digest(root/'protocol.json'), files={n: digest(folder/n) for n in new_files}, results=results,
        full_rows=len(full_scoped), top20pct_rows=len(top_scoped), h20_population_and_memberships_frozen=True,
        no_model_training=True, interpretation='Per hypothetical entry after assumed costs; not annual portfolio return or validation of H5/H10 prediction')
    atomic_json(folder/'report.json', report); LOG.info('Completed %s H%d, both scopes', name, horizon)
    return report


def run(root):
    p = read(root/'protocol.json'); verify_hashes(Path('.'), p['sources'])
    if (root/'report.json').exists(): raise ValueError('Immutable completed report exists')
    rows = []; reports = {}; compact = []
    for name in p['profiles']:
        for h in HORIZONS:
            atomic_json(root/'progress.json', dict(status='RUNNING', phase='SUMMARIES_AND_PAIRED_COMPARISONS', profile=name, horizon=h))
            report = run_case(root, name, h)
            key = f'{name}/H{h}/report.json'; reports[key] = digest(root/key)
            for scope, result in report['results'].items():
                for row in result['summary']:
                    paired = next(r for r in result['paired_h20'] if r['year'] == row['year'] and r['arm'] == row['arm'])
                    rows.append(dict(profile=name, horizon=h, scope=scope, **row, **{k: v for k, v in paired.items() if k not in ('year', 'arm', 'n')}))
                    compact.append(dict(profile=name, horizon=h, scope=scope, year=row['year'], arm=row['arm'], n=row['n'],
                        win_rate=row['profitable_rate'], mean_net=row['mean_net_outcome'], tp_rate=row['tp_rate'], sl_rate=row['sl_rate'],
                        terminal_right=paired['terminal_right'], terminal_sign_changed=paired['terminal_sign_changed'],
                        delta_daily_vs_h20=paired['net_gain_vs_h20']['delta']))
    pd.DataFrame(compact).to_csv(root/'comparison.csv', index=False)
    verify_hashes(Path('.'), p['sources']); verify_hashes(root, read(root/'paths-manifest.json')['files'])
    atomic_json(root/'report.json', dict(status='COMPLETED_EXPLORATORY_PRICE_RESERVE_NO_PROMOTION',
        protocol_sha256=digest(root/'protocol.json'), comparison=rows, case_reports=reports,
        files={'comparison.csv': digest(root/'comparison.csv')},
        claim='Exit-duration comparison only; no trained H5/H10 Oracle or certified directional edge'))
    atomic_json(root/'progress.json', dict(status='COMPLETED_EXPLORATORY_PRICE_RESERVE_NO_PROMOTION', phase='DONE'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['prepare', 'build', 'run'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    {'prepare': prepare, 'build': build, 'run': run}[args.phase](args.output)


if __name__ == '__main__': main()
