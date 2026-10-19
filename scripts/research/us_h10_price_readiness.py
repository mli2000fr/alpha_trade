"""Bounded SIP cross-check and research-only split normalization before H10 fit.

No SQL, production, model, account or universe changes. Never clip real jumps.
Official event factors are fixed below, not estimated to improve trade returns.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import logging

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research import us_oracle_holding_horizons as holding

PRICE = Path('artifacts/research/us_oracle_tp20_sl10_new/20261012-v6/prices.parquet')
SIP = Path('artifacts/research/us_sip_daily_universe/audit-20260101-20260930-20261011-v1/sip-bars.parquet')
FLAGGED = ['AVNS', 'CRNX', 'DD', 'KLAC', 'KSS', 'MLI', 'MLTX', 'SATS', 'SBS', 'SEMR', 'TOELY', 'UTZ']
SPLITS = {
    'KLAC': dict(factor=.1, ex_date='2026-06-12',
        url='https://ir.kla.com/sec-filings/all-sec-filings/content/0001193125-26-212093/d116682dex991.htm'),
    'DD': dict(factor=3., ex_date='2026-06-24',
        url='https://www.investors.dupont.com/news-and-media/press-release-details/2026/DuPont-Announces-Reverse-Stock-Split-and-Reaffirms-2026-Financial-Guidance/default.aspx'),
    'MLI': dict(factor=.5, ex_date='2026-07-01',
        url='https://ir.muellerindustries.com/sec-filings/all-sec-filings/content/0000089439-26-000025/ex-99_16302026stocksplit.htm'),
    'SBS': dict(factor=.2, ex_date='2026-05-07',
        url='https://api.mziq.com/mzfilemanager/v2/d/9e47ee51-f833-4a23-af98-2bac9e54e0b3/6120c301-1988-3129-0a1b-47cf798497bf?origin=2',
        reserve='Issuer April27 planned ADR ex-date plus vendor cross-check; not independent daily execution certification')}
RESERVED = {'TOELY': dict(start='2026-07-13', reason='Unresolved scale/ADR basis; no inferred split date or price correction',
    url='https://www.tel.com/ir/stocks/info/', official_ordinary_split_date='2026-10-01',
    note='Ordinary share event does not prove TOELY ADR basis, or explain July13 discontinuity')}
RESERVED['DD'] = dict(start='2025-11-03', reason='Qnity distribution basis differs between vendor histories; no total-return/execution qualification',
    url='https://www.dupont.com/news/dupont-completes-separation-of-qnity-electronics.html',
    note='Pre-distribution windows wholly before this date are scale invariant. No new decisions from this date until basis qualified.')
FIELDS = ['open', 'high', 'low', 'close']
LOG = logging.getLogger(__name__)


def read(path):
    return holding.read(path)


def factors_against_sip(local, sip, factor, tolerance=.005):
    """Only allow 1 or the official split multiplier, corroborated on all OHLC."""
    merged = local.merge(sip[['symbol', 'date', *FIELDS]], on=['symbol', 'date'], suffixes=('', '_sip'), validate='one_to_one')
    ratios = np.column_stack([merged[f'{c}_sip']/merged[c] for c in FIELDS])
    same = np.isfinite(ratios).all(axis=1) & (np.abs(ratios-1) <= tolerance).all(axis=1)
    scaled = np.isfinite(ratios).all(axis=1) & (np.abs(ratios/factor-1) <= tolerance).all(axis=1)
    merged['normalization_factor'] = np.where(same, 1., np.where(scaled, factor, np.nan))
    merged['corroborated'] = same | scaled
    return merged


def normalize_rows(frame, factors):
    result = frame.copy()
    if not np.isfinite(factors).all() or (np.asarray(factors) <= 0).any(): raise ValueError('Unqualified factor')
    for c in [*FIELDS, 'adj_close', 'vwap']:
        if c in result: result[c] = result[c].astype(float)*factors
    result['volume'] = result.volume.astype(float)/factors
    return result


def fetch(root):
    root.mkdir(parents=True, exist_ok=True)
    from common.verified_http import verified_session
    from service.alpaca.clientAlpaca import _build_headers
    # One symbol at a time: isolate delisted/unsupported symbols; max 22 requests.
    with verified_session() as session:
        for symbol in FLAGGED:
            if symbol == 'TOELY': continue  # already unsupported in frozen SIP audit
            for adjustment in ('split', 'raw'):
                path = root/f'{symbol}-{adjustment}.json'
                if path.exists(): continue
                params = dict(symbols=symbol, timeframe='1Day', feed='sip', adjustment=adjustment, asof='-',
                    start='2023-01-01T00:00:00Z', end='2026-09-30T23:59:59Z', limit=10000, sort='asc')
                response = session.get('https://data.alpaca.markets/v2/stocks/bars', headers=_build_headers('default'), params=params, timeout=(10, 45))
                if response.status_code != 200:
                    # Do not archive headers/credentials or pretend errors mean no data.
                    atomic_json(path, dict(status='HTTP_ERROR', http_status=response.status_code, symbol=symbol, adjustment=adjustment))
                    raise RuntimeError(f'SIP cross-check HTTP {response.status_code} {symbol}/{adjustment}')
                payload = response.json()
                if payload.get('next_page_token'): raise ValueError('Unexpected truncation; bounded cross-check refuses pagination')
                atomic_json(path, dict(status='COMPLETED', observed_at_utc=datetime.now(timezone.utc).isoformat(),
                    params=params, bars=payload.get('bars', {}), no_next_page=True))
                LOG.info('SIP evidence %s/%s archived', symbol, adjustment)


def qualify(root, evidence):
    if (root/'report.json').exists(): raise ValueError('Immutable completed price audit exists')
    root.mkdir(parents=True, exist_ok=True)
    from scripts.research.us_sip_daily_universe_audit import provider_frame
    from modelFactory.oracle.build_labels import nyse_sessions
    sources = {str(p): digest(p) for p in [Path(__file__), PRICE, SIP, holding.FULL/'protocol.json', holding.TOP/'protocol.json']}
    parts = []
    for symbol in FLAGGED:
        if symbol == 'TOELY': continue
        f = evidence/f'{symbol}-split.json'; item = read(f)
        if item['status'] != 'COMPLETED' or not item['no_next_page']: raise ValueError('Incomplete provider evidence')
        sources[str(f)] = digest(f); parts.append(provider_frame(item['bars']))
        raw = evidence/f'{symbol}-raw.json'; sources[str(raw)] = digest(raw)
    sip = pd.concat(parts, ignore_index=True)
    prices = pd.read_parquet(PRICE); prices.date = pd.to_datetime(prices.date)
    # Compare the declared study window, not the seven October tail bars from
    # an older broader archive that this bounded SIP request does not cover.
    prices = prices[prices.date.le('2026-09-30')].copy()
    corrected = prices.copy(); changes = []; coverage = []; feature_reserves = []
    for symbol, spec in SPLITS.items():
        sub = prices[prices.symbol.eq(symbol)].copy()
        joined = factors_against_sip(sub, sip[sip.symbol.eq(symbol)], spec['factor'])
        # DD's old EODHD basis also adjusts the Qnity distribution; SIP "split"
        # does not. Uniform x3 rescaling of the legacy block preserves its
        # returns; it is NOT independent absolute-price corroboration. Reserve
        # crossing/after-distribution outcomes and features, not infer x7.17.
        legacy_basis = joined.date.lt(RESERVED['DD']['start']) if symbol == 'DD' else pd.Series(False, index=joined.index)
        joined.loc[legacy_basis, 'normalization_factor'] = spec['factor']
        eligible = joined.corroborated | legacy_basis
        if len(joined) != len(sub) or not eligible.all():
            bad = joined[~eligible]; bad.to_csv(root/f'{symbol}-unqualified.csv', index=False)
            atomic_json(root/'progress.json', dict(status='BLOCKED_PRICE_QUALIFICATION', symbol=symbol, missing=len(sub)-len(joined), unqualified=len(bad)))
            raise ValueError(f'Unqualified split overlay {symbol}: missing={len(sub)-len(joined)}, unqualified={len(bad)}')
        joined = joined.set_index('date').reindex(sub.date)
        factors = joined.normalization_factor.to_numpy()
        new = normalize_rows(sub, factors); corrected.loc[sub.index, new.columns] = new.to_numpy()
        changed = ~np.isclose(factors, 1.)
        # Guard cached features from the first observed change of basis, not
        # from the much earlier uniform scaling (which preserves price ratios).
        original_factor_state = pd.Series(factors, index=sub.date)
        switches = original_factor_state.ne(original_factor_state.shift())
        switches.iloc[0] = False
        first_switch = original_factor_state.index[switches][0] if switches.any() else None
        if first_switch is not None: feature_reserves.append(dict(symbol=symbol, start=str(first_switch.date()),
            reason='Cached features may include mixed adjustment history; excluded from future scoring until rebuilt', scope='FEATURES_ONLY'))
        changes.extend(dict(symbol=symbol, date=str(d.date()), factor=float(v),
            reason='LEGACY_UNIFORM_RESCALING_NOT_LEVEL_CERTIFIED' if symbol == 'DD' and d < pd.Timestamp(RESERVED['DD']['start'])
            else 'OFFICIAL_SPLIT_PLUS_SIP_OHLC_CORROBORATION')
            for d, v in zip(sub.loc[changed, 'date'], factors[changed]))
        coverage.append(dict(symbol=symbol, observed=len(sub), corroborated=int(joined.corroborated.sum()),
            legacy_uniform_rescaling_not_level_corroborated=int(legacy_basis.sum()), changed=int(changed.sum()),
            first_basis_switch=None if first_switch is None else str(first_switch.date()), official_event=spec))
    changes = pd.DataFrame(changes); changes.to_csv(root/'normalization-ledger.csv', index=False)
    corrected.to_parquet(root/'research-prices.parquet', index=False)
    # Other extreme movers: compare, do not remove them for having large returns.
    reviews = []
    for symbol in FLAGGED:
        sub = prices[prices.symbol.eq(symbol)].sort_values('date')
        shocks = sub[sub.close.pct_change().abs().gt(.5)]
        for row in shocks.itertuples():
            match = sip[sip.symbol.eq(symbol) & sip.date.eq(row.date)]
            previous_local = sub[sub.date.lt(row.date)].iloc[-1]
            previous_sip = sip[sip.symbol.eq(symbol) & sip.date.eq(previous_local.date)]
            scale = SPLITS[symbol]['factor'] if symbol in SPLITS else 1.
            coherent = not match.empty and not previous_sip.empty and abs(float(match.close.iloc[0]/previous_sip.close.iloc[0])/(row.close/previous_local.close)-1) <= .01
            reviews.append(dict(symbol=symbol, date=str(row.date.date()), old_close=row.close,
                raw_return=float(row.close/previous_local.close-1),
                status='OFFICIAL_SPLIT_SCALE_MIX_CORRECTED_RESEARCH' if symbol in SPLITS else
                    'CROSS_PROVIDER_SHOCK_RETAINED' if coherent else 'UNRESOLVED_REVIEW',
                inferred_split_factor=None if scale == 1 else scale))
    pd.DataFrame(reviews).to_csv(root/'shock-review.csv', index=False)
    atomic_json(root/'quality-reserves.json', dict(feature_reserves=feature_reserves, price_reserves=RESERVED,
        note='Reservations are data quality, not filters optimized on gains or future direction. No universe file deletion.'))
    # Frozen model/entry/membership sensitivity, exits recalculated only for four corrected symbols.
    days = nyse_sessions('2023-01-01', '2026-10-09'); outcomes = []; new_files = []
    groups = {s: g.set_index('date').reindex(days) for s, g in corrected[corrected.symbol.isin(SPLITS)].groupby('symbol')}
    for profile, protection in holding.previous.PROFILES.items():
        for scope, source in [('FULL_TRADABLE', holding.FULL), ('ORACLE_TOP20PCT', holding.TOP)]:
            f = pd.read_parquet(source/profile/'evaluations.parquet'); sources[str(source/profile/'evaluations.parquet')] = digest(source/profile/'evaluations.parquet')
            old = f.copy(); f['price_qualified'] = True
            for (symbol, side), group in f[f.symbol.isin(SPLITS)].groupby(['symbol', 'side'], observed=True):
                positions = days.get_indexer(group.date)
                new = holding.paths(groups[symbol], positions, side, horizon=20, **protection)
                for field, values in new.items():
                    if field in f: f.loc[group.index, field] = values
            f = holding.gate.attach_costs(f)
            for symbol, spec in RESERVED.items():
                affected = f.symbol.eq(symbol) & f.last_path_date.ge(pd.Timestamp(spec['start']))
                f.loc[affected, 'price_qualified'] = False
            for year, part in f.groupby('year'):
                before = old[old.year.eq(year)]
                for arm in holding.gate.ARMS:
                    a = holding.gate.chosen(before, arm); b = holding.gate.chosen(part, arm); qualified = b[b.price_qualified]
                    outcomes.append(dict(profile=profile, scope=scope, year=int(year), arm=arm, n_before=len(a), n_qualified=len(qualified),
                        reserved=len(b)-len(qualified), mean_net_before=float(a.net_outcome.mean()), mean_net_after=float(qualified.net_outcome.mean()),
                        corrected_rows=int(b.symbol.isin(SPLITS).sum()), changed_chosen_side=False,
                        note='Sensitivity only: original model features and historical memberships not refitted; not corrected model performance'))
            path = root/f'{profile}-{scope}-sensitivity.parquet'; f.to_parquet(path, index=False); new_files.append(path.name)
    pd.DataFrame(outcomes).to_csv(root/'frozen-sensitivity.csv', index=False)
    new_files += ['research-prices.parquet', 'normalization-ledger.csv', 'shock-review.csv', 'quality-reserves.json', 'frozen-sensitivity.csv']
    verify_hashes(Path('.'), sources)
    report = dict(status='RESEARCH_NORMALIZATION_SUPPORTED_NOT_INDEPENDENT_DAILY_CERTIFICATION', sources=sources,
        corrections=coverage, changed_rows=len(changes), reviews=reviews, frozen_sensitivity=outcomes,
        price_reserves=RESERVED, feature_reserves=feature_reserves,
        files={n: digest(root/n) for n in new_files}, training=False, sql_writes=False, production_changed=False,
        next='A common causal eligibility guard must exclude reserved cached features, without removing symbols or using future labels at J')
    atomic_json(root/'report.json', report); atomic_json(root/'progress.json', dict(status='COMPLETED_RESEARCH_ONLY', phase='DONE'))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['fetch', 'qualify'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args(); logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if args.phase == 'fetch': fetch(args.output)
    else: qualify(args.output, args.evidence)
