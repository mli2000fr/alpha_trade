"""Offline diagnostic of actual SL5 exits; no fit, SQL, network or portfolio run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.features import _atr_value, _build_adjusted_price_frame
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.security_continuity import (
    DEFAULT_REGISTRY_PATH, load_security_discontinuities,
    path_crosses_known_discontinuity, split_frame_on_discontinuities,
)
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_path_protection_headroom import qualify_window, price_arrays
from scripts.research.us_oracle_path_top5_leverage_grid import read

SOURCE = Path('artifacts/research/us_oracle_path_protection_selector/20261014-v1')
AS_OF, HORIZONS = '2026-10-09', (20, 60)
STOP_REASONS = ('initial_stop', 'initial_stop_gap_open')
LOG = logging.getLogger(__name__)


def bucket(multiple):
    if not np.isfinite(multiple) or multiple <= 0:
        raise ValueError('Invalid ATR distance')
    return 'LT1_ATR' if multiple < 1 else '1_TO_LT2_ATR' if multiple < 2 else 'GE2_ATR'


def recovery_path(window, dates, exit_date, fill):
    """Only sessions STRICTLY after the actual stop: intraday order is unknown.

    Low on the first target-touch session cannot be ordered relative to high.
    Therefore expose both bounds, never claim that a high touch was tradable.
    The SL10 sensitivity starts at entry, ignores trailing, and resolves collisions
    conservatively. It is a path diagnostic, not a replacement portfolio.
    """
    prices = np.asarray(window[:, :4], float)
    opening, high, low, close = prices.T
    after = np.asarray(dates > pd.Timestamp(exit_date))
    if not after.any():
        raise ValueError('No subsequent session in the fixed entry window')
    target = fill*1.2
    hits = np.flatnonzero(after & (high >= target))
    close_hits = np.flatnonzero(after & (close >= target))
    out = dict(recovered_high20=bool(len(hits)), recovered_close20=bool(len(close_hits)),
        first_target_date=None, sessions_after_stop_to_target=None,
        min_after_stop_pct=float(100*(low[after].min()/fill-1)),
        max_after_stop_pct=float(100*(high[after].max()/fill-1)),
        min_before_target_excluding_hit_day_pct=None,
        min_before_target_including_hit_day_pct=None,
        target_day_low_before_high_unknown=False,
        additional_loss_from_sl5_before_target_lower_pp=None,
        additional_loss_from_sl5_before_target_upper_pp=None,
        sl10_before_target=True, sl10_target_collision=False)
    if len(hits):
        k = int(hits[0])
        before = low[:k]
        lower = min(0., float(100*(before.min()/fill-1))) if k else 0.
        upper = min(lower, float(100*(low[k]/fill-1)))
        out.update(first_target_date=str(dates[k].date()),
            sessions_after_stop_to_target=int(after[:k+1].sum()),
            min_before_target_excluding_hit_day_pct=lower,
            min_before_target_including_hit_day_pct=upper,
            target_day_low_before_high_unknown=bool(upper < lower),
            additional_loss_from_sl5_before_target_lower_pp=max(0., -lower-5),
            additional_loss_from_sl5_before_target_upper_pp=max(0., -upper-5))
    # Could SL10 have survived FROM ENTRY to a target hit AFTER the observed SL5?
    for k, (o, h, l, _) in enumerate(prices):
        if o <= fill*.9:
            break
        if o >= target:
            out['sl10_before_target'] = not bool(after[k])
            break
        if l <= fill*.9:
            out['sl10_target_collision'] = bool(h >= target)
            break
        if h >= target:
            out['sl10_before_target'] = not bool(after[k])
            break
    else:
        out['sl10_before_target'] = True
    out['recovered_high20_without_prior_sl10'] = bool(
        out['recovered_high20'] and not out['sl10_before_target'])
    return out


def freeze(output):
    marker = output/'protocol.json'
    if marker.exists():
        p = read(marker); verify_hashes(Path('.'), p['sources']); return p
    original = read(SOURCE/'protocol.json')
    report = read(SOURCE/'report.json')
    verify_hashes(SOURCE, report['files'])
    if report['status'] != 'COMPLETED_EXPLORATORY' or read(SOURCE/'completion-audit.json')[
            'status'] != 'TWELVE_CASES_AND_FROZEN_DECISIONS_VERIFIED':
        raise ValueError('Completed audited annual portfolios required')
    prices = Path(original['prices'])
    matches = [v for k, v in original['sources'].items() if Path(k) == prices]
    if len(set(matches)) != 1 or digest(prices) != matches[0]:
        raise ValueError('Original price tape changed')
    paths = [SOURCE/'protocol.json', SOURCE/'report.json', SOURCE/'completion-audit.json',
        SOURCE/'annual-features.parquet', prices, DEFAULT_REGISTRY_PATH, Path(__file__),
        Path('tests/test_us_oracle_path_stop_recovery.py'), Path('modelFactory/features.py'),
        Path('modelFactory/oracle/security_continuity.py'),
        Path('doc/ml/oracle_path_stop_recovery_20261014.md')]
    for year in (2024, 2025, 2026):
        folder = SOURCE/f'{year}-FIXED_REFERENCE'
        case = read(folder/'case-report.json'); verify_hashes(folder, case['files'])
        if case['status'] != 'COMPLETED':
            raise ValueError('Incomplete reference portfolio')
        paths.extend([folder/'case-report.json', folder/'trades.parquet', folder/'opened-profiles.json'])
    p = dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(), source=str(SOURCE),
        annual_models=original['annual_models'], prices=str(prices), events=original['events'],
        as_of=AS_OF, horizons=HORIZONS, primary_horizon=20,
        observation='20/60 NYSE sessions INCLUDING entry; not reset at stop',
        recovery='high >=120% actual entry fill, strictly after exit session; close sensitivity',
        reference='actual FIXED_REFERENCE LONG TOP5; SL5/TR15/TP20; native costs/risk/lev2',
        stop_reasons=STOP_REASONS, atr_buckets=['LT1_ATR', '1_TO_LT2_ATR', 'GE2_ATR'],
        atr='backward 20-session rolling mean true range on adjusted feature prices at J; prefix recheck',
        future_quality='full-window OHLCV positive, nonfilled, stable identity; quarantine, no refill',
        censorship='no shortened window, no recovery inference from immature/missing windows',
        wider_stop_sensitivity='SL10 from entry, TP20, NO trailing; conservative OHLC collision',
        no_fit=True, no_sql=True, no_broker=True, no_portfolio_run=True,
        independent_holdout=False, sources={str(p): digest(p) for p in paths},
        reserves=original['reserves'],
        interpretation='post-stop recovery is hindsight, not a winning trade or a live selection signal')
    atomic_json(marker, p)
    return p


def atr_context(trade, bars, features, registry):
    day = pd.Timestamp(trade.signal_date)
    if not day < trade.entry_date or features.duplicated(['date', 'symbol']).any():
        raise ValueError('Noncausal/duplicate J feature context')
    key = (day, trade.symbol)
    known = features.set_index(['date', 'symbol']).loc[key]
    if not known.selected or not np.isfinite(known.atr20_pct) or known.atr20_pct <= 0:
        raise ValueError('Opened trade without qualified ATR at J')
    prefix = bars[bars.date.le(day)]
    part = list(split_frame_on_discontinuities(prefix, trade.symbol, registry))[-1]
    adjusted = _build_adjusted_price_frame(part.reset_index(drop=True))
    value = (_atr_value(adjusted.high, adjusted.low, adjusted.close, 20)/adjusted.close).iloc[-1]
    if part.date.iloc[-1] != day or not np.isclose(value, known.atr20_pct, rtol=1e-10, atol=1e-12):
        raise ValueError('ATR prefix differs from archived decision feature')
    j_close = float(part.close.iloc[-1])
    multiple = .05*float(trade.entry_price)/(float(value)*j_close)
    return dict(atr20_j_pct=float(value*100), sl5_atr_multiple_at_fill=multiple,
        sl5_atr_multiple_at_j=.05/float(value), atr_bucket=bucket(multiple), atr_prefix_verified=True)


def nonoverlapping(frame, days):
    keep, next_entry = [], {}
    for i, row in frame.sort_values(['entry_date', 'symbol']).iterrows():
        j = days.get_loc(row.entry_date)
        if j >= next_entry.get(row.symbol, -1):
            keep.append(i); next_entry[row.symbol] = j+int(row.horizon)
    return frame.loc[keep]


def statistics(frame):
    recovered = frame[frame.recovered_high20.eq(True)]
    def median(column, subset=frame):
        values = subset[column].dropna()
        return float(values.median()) if len(values) else None
    return dict(qualified_stops=len(frame), distinct_symbols=int(frame.symbol.nunique()),
        recovered_high20=int(frame.recovered_high20.sum()),
        recovered_high20_pct=float(100*frame.recovered_high20.mean()),
        recovered_close20=int(frame.recovered_close20.sum()),
        recovered_close20_pct=float(100*frame.recovered_close20.mean()),
        recovered_without_prior_sl10=int(frame.recovered_high20_without_prior_sl10.sum()),
        recovered_without_prior_sl10_pct=float(100*frame.recovered_high20_without_prior_sl10.mean()),
        median_atr20_j_pct=median('atr20_j_pct'), median_stop_atr=median('sl5_atr_multiple_at_fill'),
        median_post_stop_min_pct=median('min_after_stop_pct'),
        median_recovered_min_before_target_lower_pct=median('min_before_target_excluding_hit_day_pct', recovered),
        median_recovered_min_before_target_upper_pct=median('min_before_target_including_hit_day_pct', recovered),
        median_sessions_after_stop_to_target=median('sessions_after_stop_to_target', recovered),
        target_hit_day_order_ambiguous=int(recovered.target_day_low_before_high_unknown.sum()))


def run(output):
    output = Path(output)
    with exclusive_run(output):
        p = freeze(output)
        features = pd.read_parquet(SOURCE/'annual-features.parquet')
        prices = pd.read_parquet(p['prices']); prices.date = pd.to_datetime(prices.date)
        days = nyse_sessions('2023-01-01', '2027-03-31')
        registry = load_security_discontinuities()
        groups = {s: f.sort_values('date') for s, f in prices.groupby('symbol')}
        atr_rows, rows, counts = [], [], []
        for year in (2024, 2025, 2026):
            folder = SOURCE/f'{year}-FIXED_REFERENCE'
            trades = pd.read_parquet(folder/'trades.parquet')
            arrays = price_arrays(prices, set(trades.symbol), days)
            counts.append(dict(year=year, closed=len(trades), reasons=trades.exit_reason.value_counts().to_dict()))
            for n, t in enumerate(trades.itertuples(index=False)):
                if t.side != 'buy' or not np.isclose(t.replay_initial_stop_price, t.entry_price*.95):
                    raise ValueError('Non-SL5 LONG reference lot')
                # Reserve transformed lots for ATR context: current symbol may not
                # have been the name originally approved at J.
                opened = read(folder/'opened-profiles.json')
                origin = [o['symbol'] for o in opened if pd.Timestamp(o['fill_date']) == t.entry_date
                          and o['symbol'] == t.symbol]
                if len(origin) != 1:
                    context = dict(atr20_j_pct=None, sl5_atr_multiple_at_fill=None,
                        sl5_atr_multiple_at_j=None, atr_bucket='IDENTITY_RESERVED', atr_prefix_verified=False)
                else:
                    context = atr_context(t, groups[t.symbol], features, registry)
                base = dict(year=year, symbol=t.symbol, signal_date=t.signal_date, entry_date=t.entry_date,
                    exit_date=t.exit_date, entry_price=float(t.entry_price), exit_price=float(t.exit_price),
                    exit_reason=t.exit_reason, pnl_usd=float(t.pnl), **context)
                atr_rows.append(base)
                if t.exit_reason not in STOP_REASONS:
                    continue
                j = days.get_loc(t.entry_date)
                for horizon in HORIZONS:
                    dates = days[j:j+horizon]
                    b = dict(base, horizon=horizon, observation_end=dates[-1])
                    reason = None
                    if dates[-1] > pd.Timestamp(AS_OF):
                        reason = 'IMMATURE_WINDOW'
                    elif t.exit_date >= dates[-1]:
                        reason = 'STOP_ON_OR_AFTER_WINDOW_END'
                    elif not context['atr_prefix_verified']:
                        reason = 'ENTRY_IDENTITY_RESERVED'
                    elif path_crosses_known_discontinuity(t.symbol, t.signal_date, dates[-1], registry):
                        reason = 'SECURITY_DISCONTINUITY'
                    elif any(e['source'] == t.symbol and t.entry_date <= pd.Timestamp(e['day']) <= dates[-1]
                             for e in p['events']):
                        reason = 'CORPORATE_ACTION_WINDOW_RESERVED'
                    window = arrays[t.symbol][j:j+horizon]
                    if not reason:
                        reason = qualify_window(window)
                    if reason:
                        rows.append(dict(b, status=reason)); continue
                    if not np.isclose(float(window[0, 0]), t.entry_price, atol=1e-8):
                        raise ValueError('Historical entry price differs from raw open')
                    if not np.isclose(t.exit_price, t.entry_price*.95, atol=1e-8) and t.exit_reason == 'initial_stop':
                        raise ValueError('Non-gap initial stop fill differs from SL5')
                    rows.append(dict(b, status='QUALIFIED', **recovery_path(window, dates, t.exit_date, t.entry_price)))
                if n % 30 == 0:
                    atomic_json(output/'progress.json', dict(status='RUNNING', year=year, inspected_lots=n, total_lots=len(trades)))
            LOG.info('Year %s: inspected %s closed lots', year, len(trades))
        frame, atr = pd.DataFrame(rows), pd.DataFrame(atr_rows)
        if frame.duplicated(['year', 'symbol', 'entry_date', 'horizon']).any():
            raise ValueError('Duplicate stopped lot/horizon')
        summaries, strata, contexts = [], [], []
        for year in (2024, 2025, 2026):
            a = atr[atr.year.eq(year) & atr.atr_prefix_verified.eq(True)]
            contexts.append(dict(year=year, qualified_atr_lots=len(a),
                median_atr20_j_pct=float(a.atr20_j_pct.median()),
                median_sl5_atr_multiple=float(a.sl5_atr_multiple_at_fill.median()),
                below_one_atr_pct=float(100*a.sl5_atr_multiple_at_fill.lt(1).mean()),
                stopped_below_one_atr_pct=float(100*a[a.exit_reason.isin(STOP_REASONS)].sl5_atr_multiple_at_fill.lt(1).mean())))
            for horizon in HORIZONS:
                sub = frame[frame.year.eq(year) & frame.horizon.eq(horizon)]
                valid = sub[sub.status.eq('QUALIFIED')]
                if valid.empty:
                    raise ValueError('No qualified stopped lots for a year/horizon')
                selected = nonoverlapping(valid, days)
                summaries.append(dict(year=year, horizon=horizon, actual_stopped_lots=len(sub),
                    statuses=sub.status.value_counts().to_dict(), **statistics(valid),
                    nonoverlapping=statistics(selected)))
                frame.loc[selected.index, 'nonoverlapping'] = True
                for name, group in valid.groupby('atr_bucket'):
                    strata.append(dict(year=year, horizon=horizon, atr_bucket=name, **statistics(group)))
        frame['nonoverlapping'] = frame.nonoverlapping.fillna(False).astype(bool)
        frame.to_parquet(output/'stopped-lots.parquet', index=False)
        atr.to_parquet(output/'closed-lot-atr.parquet', index=False)
        pd.DataFrame(strata).to_csv(output/'atr-strata.csv', index=False)
        verify_hashes(Path('.'), p['sources'])
        report = dict(status='COMPLETED_DIAGNOSTIC', verdict='HINDSIGHT_RECOVERY_NOT_STRATEGY_PROFIT',
            closed_lot_counts=counts, atr_context=contexts, summaries=summaries, atr_strata=strata,
            atr_prefix_checks=int(atr.atr_prefix_verified.sum()), original_inputs_hash_verified=True,
            training=False, sql_writes=False, broker_calls=False, portfolio_variant_launched=False,
            independent_holdout=False, sl10_sensitivity_costs_or_trailing=False,
            files={name: digest(output/name) for name in ['protocol.json', 'stopped-lots.parquet',
                   'closed-lot-atr.parquet', 'atr-strata.csv']})
        atomic_json(output/'report.json', report)
        verify_hashes(output, report['files'])
        atomic_json(output/'completion-audit.json', dict(status='INPUTS_ATR_PREFIXES_LOT_COUNTS_AND_OUTPUT_HASHES_VERIFIED',
            stopped_lots=len(frame)//2, closed_lots=len(atr), horizons=list(HORIZONS),
            qualified=int(frame.status.eq('QUALIFIED').sum()), quarantined=int(frame.status.ne('QUALIFIED').sum())))
        atomic_json(output/'progress.json', dict(status=report['status'], completed=3, total=3))
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--output', required=True)
    args = parser.parse_args(); Path(args.output).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(),
        logging.FileHandler(Path(args.output)/'stderr.log', encoding='utf-8')])
    try:
        run(args.output)
    except Exception as exc:
        atomic_json(Path(args.output)/'progress.json', dict(status='FAILED', error=str(exc), error_type=type(exc).__name__))
        raise
