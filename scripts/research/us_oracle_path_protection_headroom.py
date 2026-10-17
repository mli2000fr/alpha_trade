"""Bounded counterfactual protection headroom, not training or portfolio PnL.

Frozen CatBoost TOP5, three profiles, common 60/20-session windows.
All writes are separate research artifacts. No SQL, network or broker access.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.microstructure import resolve_intrabar_exit
from common.trading_costs import DEFAULT_COST_MODEL
from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_trailing_grid import activation_price
from scripts.research.us_oracle_path_top5_leverage_grid import read

SOURCE = Path('artifacts/research/us_oracle_path_backend_economic/20261014-v1')
GRID = Path('artifacts/research/us_oracle_path_top5_leverage/20261014-v3')
PROFILES = {'COURT': (.10, .10), 'REFERENCE': (.15, .20), 'LARGE': (.20, .30)}
SL, HORIZONS, AS_OF = .05, (60, 20), '2026-10-09'
LOG = logging.getLogger(__name__)
# These authorized changes occurred AFTER the input research was completed.
# They are not used to regenerate its scores, and old hashes are never edited.
KNOWN_CODE_DRIFT = {
    'config.yaml', 'modelFactory/config.py', 'modelFactory/cli.py',
    'modelFactory/oracle_path/train.py', 'modelFactory/oracle_path/predict.py',
    'ihm/services/pipeline_runner.py', 'ihm/pages/_execution_center/__init__.py',
}
ARCHIVED_BATCHES = {'model-factory-20261014052407-a4bd20', 'model-factory-20261014052414-155d09',
                    'model-factory-20261014052423-4df571'}


def missing_archived_model(name):
    parts = Path(name).parts
    return len(parts) >= 4 and parts[:2] == ('artifacts', 'models') and parts[2] in ARCHIVED_BATCHES


def source_contract(output):
    output.mkdir(parents=True, exist_ok=True)
    marker = output/'protocol.json'
    if marker.exists():
        saved = read(marker)
        verify_hashes(Path('.'), saved['sources'])
        if saved['profiles'] != {k: list(v) for k, v in PROFILES.items()} or saved['horizons'] != list(HORIZONS):
            raise ValueError('Changed study contract: choose fresh output')
        return saved
    ready = read(SOURCE/'ready.json')
    if read(SOURCE/'report.json')['status'] != 'COMPLETED_EXPLORATORY':
        raise ValueError('Incomplete archived paired backend study')
    verify_hashes(SOURCE, ready['files'])
    sources, drift, unavailable = {}, [], []
    for name, expected in ready['sources'].items():
        if not Path(name).exists():
            if not missing_archived_model(name):
                raise ValueError(f'Missing required research input: {name}')
            unavailable.append(dict(path=name, historical_sha256=expected,
                                    reason='original model removed; use hash-verified archived TOP5, no rescoring'))
            continue
        actual = digest(name)
        if actual != expected:
            normalized = Path(name).as_posix()
            if normalized not in KNOWN_CODE_DRIFT:
                raise ValueError(f'Unexplained input drift: {name}')
            drift.append(dict(path=name, historical_sha256=expected, current_sha256=actual,
                              reason='authorized explicit training backend/UI choice; archived scores reused'))
        sources[name] = actual
    grid = read(GRID/'ready.json')
    paths = [SOURCE/'ready.json', SOURCE/'report.json', SOURCE/'protocol.json',
             SOURCE/'candidates.parquet', GRID/'ready.json', Path(grid['prices']),
             Path(__file__), Path('tests/test_us_oracle_path_protection_headroom.py'),
             Path('backtesting/microstructure.py'), Path('common/trading_costs.py'),
             Path('scripts/research/us_oracle_barrier_trailing_grid.py'),
             Path('scripts/research/us_concentrated_historical_tapes.py')]
    for year in (2024, 2025, 2026):
        root = SOURCE/'catboost'/f'{year}-SL5-TRAIL15-TP20'
        case = read(root/'case-report.json')
        if case['status'] != 'COMPLETED_SIMULATED_ASSUMPTIONS':
            raise ValueError('Incomplete fixed CatBoost portfolio')
        verify_hashes(root, case['files'])
        paths += [root/'case-report.json', root/'trades.parquet']
    sources.update({str(p): digest(p) for p in paths})
    contracts = read(SOURCE/'protocol.json')['contracts']
    if {c['batch_id'] for c in contracts.values()} != ARCHIVED_BATCHES:
        raise ValueError('Different archived model lineage')
    for year, c in contracts.items():
        if any(pd.Timestamp(c[k]) >= pd.Timestamp(f'{year}-01-01') for k in ('train_available_max', 'val_available_max')):
            raise ValueError('Noncausal archived fold metadata')
    protocol = dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(), source=str(SOURCE),
        profiles=PROFILES, sl=SL, horizons=HORIZONS, primary_horizon=60, backend='catboost', top=5,
        as_of=AS_OF, entry='J+1 open, max absolute gap 3%', observation='entry included; MTM not forced exit',
        reference='REFERENCE', common_labels_available='final session close, even for early exits',
        costs=DEFAULT_COST_MODEL.to_dict(), financing_sensitivity=dict(debit_fraction=.5, rate=.065, basis='ACT/360'),
        bootstrap=dict(block_sessions=63, replications=999, seed=731),
        material_gate=dict(ceiling_minus_best_constant_mean_pct_gt=1.,
                           reference_gain_over_1pct_share_gt=.10, two_winner_shares_gt=.10),
        sources=sources, historical_code_drift=drift, price_path=grid['prices'], events=grid['events'],
        unavailable_original_model_files=unavailable, original_weights_reverified=not bool(unavailable),
        archived_contracts=contracts, scores_recomputed=False,
        protocol_document_sha256_at_freeze=digest('doc/ml/oracle_path_protections_apprentissage_faisabilite_20261014.md'),
        training=False, sql_writes=False, broker_calls=False, production_changed=False,
        learnability_proven=False, independent_holdout=False, portfolio_performance=False,
        future_quality_filter=True, dividend_history_complete=False)
    atomic_json(marker, protocol)
    verify_hashes(Path('.'), sources)
    return protocol


def price_arrays(prices, symbols, days):
    subset = prices[prices.symbol.isin(symbols)].copy()
    if subset.duplicated(['symbol', 'date']).any():
        raise ValueError('Duplicate bar key')
    names = ['open', 'high', 'low', 'close', 'volume', 'is_filled', 'instrument_id']
    return {symbol: g.set_index('date')[names].reindex(days).to_numpy(dtype=object)
            for symbol, g in subset.groupby('symbol')}


def qualify_window(data):
    numeric = np.asarray(data[:, :6], dtype=float)
    o, h, l, c, v, filled = numeric.T
    if not np.isfinite(numeric).all() or (numeric[:, :5] <= 0).any():
        return 'MISSING_OR_NONPOSITIVE_OHLCV'
    if (filled != 0).any():
        return 'FILLED_BAR'
    if (h < np.maximum(o, c)).any() or (l > np.minimum(o, c)).any() or (h < l).any():
        return 'INCONSISTENT_OHLC'
    identity = pd.Series(data[:, 6], dtype='string')
    if identity.isna().any() or identity.str.strip().eq('').any() or identity.nunique() != 1:
        return 'MISSING_OR_CHANGED_IDENTITY'
    return None


def resolve_unit(window, dates, trail, tp, *, fill=None):
    """Shared intrabar resolver, same prior-high/gap convention as native ledger.

    Stop/TP prices are gross, as in the archived Phase3/7 portfolio. Flat costs
    are booked separately. No expiry or fictitious liquidation at the boundary.
    Full-window qualification belongs to the common-cohort caller.
    """
    if len(window) != len(dates) or len(window) == 0:
        raise ValueError('Empty/misaligned path')
    fill = float(window[0, 0]) if fill is None else float(fill)
    if not np.isfinite(fill) or fill <= 0:
        raise ValueError('Invalid fill')
    stop, target = fill*(1-SL), fill*(1+tp)
    activation = activation_price(fill, stop, trail)
    peak, active_from = fill, None
    for i, row in enumerate(window):
        o, h, l, c = map(float, row[:4])
        if not np.isfinite([o, h, l, c]).all() or not 0 < l <= min(o, c) <= max(o, c) <= h:
            raise ValueError('Invalid observed price')
        active = active_from is not None and i >= active_from
        working_stop = peak*(1-trail) if active else stop
        reason = 'trailing_stop' if active else 'initial_stop'
        if i > 0 and o <= working_stop:
            return outcome(fill, o, dates, i, reason+'_gap_open', True)
        if i > 0 and o >= target:
            return outcome(fill, target, dates, i, 'take_profit_gap_limit', True)
        exit_ = resolve_intrabar_exit(day_high=h, day_low=l, take_profit_price=target,
            trailing_stop_price=working_stop if active else -np.inf,
            initial_stop_price=None if active else stop, priority='conservative', side='buy', rng=None)
        if exit_.triggered:
            return outcome(fill, exit_.exit_price, dates, i, exit_.exit_reason, True)
        if active_from is None and h >= activation:
            active_from = i+1
        peak = max(peak, h)
    return outcome(fill, float(window[-1, 3]), dates, len(window)-1, 'OPEN_MTM', False)


def outcome(fill, price, dates, index, reason, closed):
    cost = DEFAULT_COST_MODEL.per_leg_cost_pct
    # Fractions of the original gross entry notional. Never pretend open MTM
    # proceeds are settled cash, nor charge an executed sell that didn't happen.
    ratio = price/fill
    net = ratio*(1-cost if closed else 1)-(1+cost)
    calendar_days = (pd.Timestamp(dates[index])-pd.Timestamp(dates[0])).days+1
    liquidation_net = ratio*(1-cost)-(1+cost)
    financing = .5*.065*calendar_days/360.
    return dict(value_date=dates[index], value_price=float(price), closed=closed, reason=reason,
                holding_sessions=index+1, gross_pct=100*(ratio-1), net_pct=100*net,
                liquidation_net_pct=100*liquidation_net,
                financing_net_pct=100*(liquidation_net-financing))


def build_chunk(candidates, arrays, days, events, horizon):
    rows, excluded = [], []
    for row in candidates.itertuples(index=False):
        base = dict(date=row.date, symbol=row.symbol, year=int(row.year), oracle_rank=int(row.oracle_rank),
                    score=float(row.score), horizon=horizon)
        j = days.get_indexer([row.date])[0]
        if j < 0:
            raise ValueError('Decision date outside calendar')
        start, end = j+1, j+horizon
        reason = None
        if not row.selected:
            reason = 'J_HISTORY_UNQUALIFIED'
        elif end >= len(days):
            reason = 'IMMATURE_COMMON_WINDOW'
        elif row.symbol not in arrays:
            reason = 'MISSING_SYMBOL_TAPE'
        else:
            dates = days[start:end+1]
            window = arrays[row.symbol][start:end+1]
            reason = qualify_window(window)
            if not reason:
                previous = float(arrays[row.symbol][j, 3])
                if not np.isfinite(previous) or previous <= 0 or abs(float(window[0, 0])/previous-1) > .03:
                    reason = 'NEXT_OPEN_GAP_GT3PCT_OR_INVALID_J_CLOSE'
            if not reason and any(e['source'] == row.symbol and dates[0] <= pd.Timestamp(e['day']) <= dates[-1]
                                  for e in events):
                reason = 'CORPORATE_ACTION_WINDOW_RESERVED'
        if reason:
            excluded.append(dict(base, reason=reason)); continue
        base.update(entry_date=dates[0], label_available=dates[-1], entry_price=float(window[0, 0]))
        for name, (trail, tp) in PROFILES.items():
            values = resolve_unit(window, dates, trail, tp)
            base.update({f'{name}_{k}': v for k, v in values.items()})
        rows.append(base)
    return pd.DataFrame(rows), pd.DataFrame(excluded)


def nonoverlap(frame, days):
    """Date/symbol rule only, never exit/winner-based sampling."""
    keep, next_allowed = [], {}
    for index, row in frame.sort_values(['date', 'symbol']).iterrows():
        j = days.get_loc(row.date)
        if j >= next_allowed.get(row.symbol, -1):
            keep.append(index)
            next_allowed[row.symbol] = j+int(row.horizon)
    return frame.loc[keep].copy()


def ceiling_arrays(frame, metric='net_pct'):
    values = frame[[f'{p}_{metric}' for p in PROFILES]].to_numpy(dtype=float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('Empty/nonfinite common profile matrix')
    best = values.max(axis=1)
    tied = np.isclose(values, best[:, None], rtol=0, atol=1e-10)
    shares = (tied/tied.sum(axis=1)[:, None]).mean(axis=0)
    margin = np.sort(values, axis=1)[:, -1]-np.sort(values, axis=1)[:, -2]
    return values, best, tied, shares, margin


def block_interval(frame, days):
    values, best, *_ = ceiling_arrays(frame)
    grouped = pd.DataFrame(values, columns=list(PROFILES), index=frame.date)
    grouped['CEILING'] = best
    stats = grouped.groupby(level=0).sum().reindex(days, fill_value=0).to_numpy()
    counts = grouped.groupby(level=0).size().reindex(days, fill_value=0).to_numpy()
    blocks = [np.arange(i, min(i+63, len(days))) for i in range(0, len(days), 63)]
    rng, samples = np.random.default_rng(731), []
    for _ in range(999):
        indices = np.concatenate([blocks[k] for k in rng.integers(0, len(blocks), size=len(blocks))])
        count = counts[indices].sum()
        if count:
            means = stats[indices].sum(axis=0)/count
            samples.append(means[-1]-means[:-1].max())
    return dict(low_pct=float(np.quantile(samples, .025)), high_pct=float(np.quantile(samples, .975)),
                usable_replications=len(samples), distinct_blocks=len(blocks), predictive_significance=False)


def summarize(frame, days, *, interval=True, metric='net_pct'):
    values, best, tied, shares, margin = ceiling_arrays(frame, metric)
    names = list(PROFILES)
    means = values.mean(axis=0)
    reference = values[:, names.index('REFERENCE')]
    gain = best-reference
    best_constant = names[int(means.argmax())]
    by_symbol = pd.Series(gain, index=frame.symbol).groupby(level=0).sum().sort_values(ascending=False)
    total_gain = float(gain.sum())
    top_count = max(1, int(np.ceil(len(gain)*.01)))
    result = dict(count=len(frame), decision_dates=int(frame.date.nunique()), symbols=int(frame.symbol.nunique()),
        decision_start=str(frame.date.min().date()), decision_end=str(frame.date.max().date()),
        profiles={name: dict(mean_pct=float(means[k]), median_pct=float(np.median(values[:, k])),
                             best_share=float(shares[k]), open_mtm_share=float((~frame[f'{name}_closed']).mean()))
                  for k, name in enumerate(names)},
        best_constant_hindsight=best_constant, ceiling_mean_pct=float(best.mean()),
        ceiling_median_pct=float(np.median(best)),
        ceiling_minus_reference_mean_pct=float(gain.mean()),
        ceiling_minus_best_constant_mean_pct=float(best.mean()-means.max()),
        tied_best_share=float((tied.sum(axis=1) > 1).mean()),
        reference_gain_gt1pct_share=float((gain > 1).mean()), decisive_margin_gt1pct_share=float((margin > 1).mean()),
        gain_top1pct_share=float(np.sort(gain)[-top_count:].sum()/total_gain) if total_gain else None,
        gain_top_symbol_share=float(by_symbol.iloc[0]/total_gain) if total_gain else None,
        gain_top5_symbols_share=float(by_symbol.head(5).sum()/total_gain) if total_gain else None,
        top_gain_symbols=by_symbol.head(10).to_dict(), metric=metric,
        learnability_proven=False, portfolio_return=False)
    result['material_space_gate'] = (result['ceiling_minus_best_constant_mean_pct'] > 1 and
        result['reference_gain_gt1pct_share'] > .10 and int((shares > .10).sum()) >= 2)
    if interval:
        result['descriptive_block_interval'] = block_interval(frame, days)
    return result


def verify_native_parity(arrays, days):
    checks, skips, mismatches = Counter(), Counter(), []
    for year in (2024, 2025, 2026):
        trades = pd.read_parquet(SOURCE/'catboost'/f'{year}-SL5-TRAIL15-TP20'/'trades.parquet')
        for row in trades.itertuples(index=False):
            if row.exit_reason not in {'initial_stop', 'trailing_stop', 'take_profit',
                    'initial_stop_gap_open', 'trailing_stop_gap_open', 'take_profit_gap_limit'}:
                skips['OTHER_NATIVE_EXIT'] += 1; continue
            start, end = days.get_indexer([pd.Timestamp(row.entry_date), pd.Timestamp(row.exit_date)])
            if start < 0 or end < start or row.symbol not in arrays:
                skips['CHANGED_IDENTITY_OR_MISSING_TAPE'] += 1; continue
            window = arrays[row.symbol][start:end+1]
            if qualify_window(window):
                skips['UNQUALIFIED_PARITY_PATH'] += 1; continue
            result = resolve_unit(window, days[start:end+1], .15, .20, fill=row.entry_price)
            if result['reason'] != row.exit_reason or result['value_date'] != row.exit_date or not np.isclose(
                    result['value_price'], row.exit_price, rtol=1e-9, atol=1e-7):
                mismatches.append(dict(year=year, symbol=row.symbol, entry=str(row.entry_date),
                    expected_reason=row.exit_reason, actual_reason=result['reason'],
                    expected_price=row.exit_price, actual_price=result['value_price']))
            checks[row.exit_reason] += 1
    if sum(checks.values()) < 100 or not {'initial_stop', 'take_profit', 'trailing_stop'} <= set(checks):
        raise ValueError('Insufficient native exit parity canaries')
    if mismatches:
        raise ValueError(f'Native protection parity failed: {mismatches[:8]}')
    return dict(checked=sum(checks.values()), checked_by_reason=dict(checks), skips=dict(skips),
                date_price_reason_exact=True, full_portfolio_parity=False)


def run(output):
    output = Path(output)
    with exclusive_run(output):
        if not (output/'report.json').exists():
            atomic_json(output/'progress.json', dict(status='VERIFYING_INPUTS', completed=0, total=6))
        protocol = source_contract(output)
        if (output/'report.json').exists():
            report = read(output/'report.json')
            verify_hashes(output, report['files'])
            return report
        days = nyse_sessions('2023-01-01', AS_OF)
        candidates = pd.read_parquet(SOURCE/'candidates.parquet')
        candidates = candidates[candidates.backend.eq('catboost')].copy()
        candidates.date = pd.to_datetime(candidates.date)
        if candidates.duplicated(['date', 'symbol']).any() or not candidates.groupby('date').size().eq(5).all():
            raise ValueError('Invalid frozen TOP5 coverage')
        prices = pd.read_parquet(protocol['price_path']); prices.date = pd.to_datetime(prices.date)
        arrays = price_arrays(prices, set(candidates.symbol), days)
        parity = verify_native_parity(arrays, days)
        atomic_json(output/'native-parity.json', parity)
        summaries, all_rows, all_excluded = [], [], []
        for year in (2024, 2025, 2026):
            cohort = candidates[candidates.year.eq(year)]
            year_days = days[(days >= f'{year}-01-01') & (days <= cohort.date.max())]
            for horizon in HORIZONS:
                folder = output/f'{year}-H{horizon}'; folder.mkdir(exist_ok=True)
                marker = folder/'done.json'
                if marker.exists():
                    saved = read(marker); verify_hashes(folder, saved['files'])
                    rows = pd.read_parquet(folder/'counterfactuals.parquet')
                    excluded = pd.read_parquet(folder/'excluded.parquet')
                else:
                    rows, excluded = build_chunk(cohort, arrays, days, protocol['events'], horizon)
                    if len(rows)+len(excluded) != len(cohort):
                        raise ValueError('Lost candidate accounting')
                    rows.to_parquet(folder/'counterfactuals.parquet', index=False)
                    excluded.to_parquet(folder/'excluded.parquet', index=False)
                    saved = dict(files={n: digest(folder/n) for n in ['counterfactuals.parquet', 'excluded.parquet']})
                    atomic_json(marker, saved)
                if rows.empty:
                    raise ValueError(f'Empty qualified cohort: {year}/{horizon}')
                disjoint = nonoverlap(rows, days)
                summary = dict(year=year, horizon=horizon, requested=len(cohort), qualified=len(rows),
                    exclusions=excluded.reason.value_counts().to_dict() if len(excluded) else {},
                    all_candidates=summarize(rows, year_days),
                    nonoverlapping_candidates=summarize(disjoint, year_days),
                    hypothetical_liquidation=summarize(rows, year_days, interval=False, metric='liquidation_net_pct'),
                    hypothetical_financing=summarize(rows, year_days, interval=False, metric='financing_net_pct'))
                atomic_json(folder/'summary.json', summary)
                summaries.append(summary); all_rows.append(rows); all_excluded.append(excluded)
                atomic_json(output/'progress.json', dict(status='RUNNING', completed=len(summaries), total=6,
                                                        year=year, horizon=horizon, qualified=len(rows)))
                LOG.info('Finished %s H%s: %s qualified / %s', year, horizon, len(rows), len(cohort))
        pd.concat(all_rows, ignore_index=True).to_parquet(output/'counterfactuals.parquet', index=False)
        pd.concat(all_excluded, ignore_index=True).to_parquet(output/'excluded.parquet', index=False)
        primary = [s for s in summaries if s['horizon'] == 60]
        gate = all(s['all_candidates']['material_space_gate'] for s in primary)
        report = dict(status='COMPLETED_EXPLORATORY',
            verdict='MATERIAL_HINDSIGHT_SPACE_NOT_LEARNABILITY' if gate else 'NO_TRANSVERSAL_MATERIAL_HEADROOM',
            summaries=summaries, native_parity=parity, training=False, sql_writes=False,
            broker_calls=False, production_changed=False, learnability_proven=False,
            gate_is_all_years=gate, independent_holdout=False, source_hashes_verified=True,
            files={str(p.relative_to(output)): digest(p) for p in output.rglob('*')
                   if p.suffix in {'.json', '.parquet'} and p.name not in {'progress.json', 'report.json'}})
        verify_hashes(Path('.'), protocol['sources'])
        atomic_json(output/'report.json', report)
        atomic_json(output/'progress.json', dict(status=report['status'], completed=6, total=6, verdict=report['verdict']))
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler(Path(args.output)/'stderr.log', encoding='utf-8')])
    try:
        run(args.output)
    except Exception as exc:
        Path(args.output).mkdir(parents=True, exist_ok=True)
        atomic_json(Path(args.output)/'failure.json', dict(status='FAILED', error=str(exc), error_type=type(exc).__name__))
        raise
