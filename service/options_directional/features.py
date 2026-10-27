"""Observable-only production copy of the frozen equal-mix feature definition.

Indicative OI is not OPRA OI, and unsigned CALL/PUT activity is not order intent.
No labels, future prices, fitting or historical backfill are read here.
"""
import math
import numpy as np
import pandas as pd
from common.options_directional_contract import DTE_MIN, DTE_MAX, DTE_TARGET, ATM_MAX_DISTANCE


def _rows(frame, day, cutoff, *, volume=False):
    frame = frame.copy()
    if frame.empty:
        return frame
    for name in ('observed_at', 'available_at'):
        frame[name] = pd.to_datetime(frame[name], utc=True, errors='coerce')
    # Both timestamps must exist; max(skipna=True) alone would accept a missing receipt.
    frame = frame[frame[['observed_at', 'available_at']].notna().all(axis=1)].copy()
    frame = frame[frame.payload_hash.notna() & frame.contract_symbol.notna()].copy()
    frame['received_at'] = frame[['observed_at', 'available_at']].max(axis=1)
    frame = frame[frame.received_at.le(cutoff)].copy()
    if 'provider_timestamp' in frame:
        provider_time = pd.to_datetime(frame.provider_timestamp, utc=True, errors='coerce')
        frame = frame[provider_time.isna() | provider_time.le(cutoff)].copy()
    frame['day'] = frame.received_at.dt.tz_convert('America/New_York').dt.date
    frame = frame[frame.day.eq(day)].copy()
    if volume:
        bar = pd.to_datetime(frame.bar_timestamp, utc=True, errors='coerce')
        frame = frame[bar.le(cutoff) & bar.dt.tz_convert('America/New_York').dt.date.eq(day)].copy()
    frame['expiration_date'] = pd.to_datetime(frame.expiration_date, errors='coerce')
    frame['option_type'] = frame.option_type.str.upper().replace({'C': 'CALL', 'P': 'PUT'})
    root = frame.contract_symbol.str.replace(r'\d{6}[CP]\d{8}$', '', regex=True)
    frame = frame[root.eq(frame.symbol.str.replace('.', '', regex=False))].copy()
    frame['dte'] = (frame.expiration_date - pd.Timestamp(day)).dt.days
    return frame[frame.dte.between(DTE_MIN, DTE_MAX)].copy()


def _latest(frame, keys, values):
    if frame.empty:
        return frame
    frame = frame[frame.received_at.eq(frame.groupby(keys).received_at.transform('max'))].copy()
    conflicts = frame.groupby(keys)[values].transform(lambda s: s.nunique(dropna=False)).gt(1).any(axis=1)
    return frame[~conflicts].drop_duplicates(keys).copy()


def build_features(snapshots, volumes, spots, day, cutoff):
    """One matched ATM OI pair + nearest-tenor volume, exactly as the audit.

    Tenor 15..25 calendar days, target 20; OI strikes within 5% of close J.
    Volume and OI can have different nearest expiries, both recorded explicitly.
    """
    oi, flow = _rows(snapshots, day, cutoff), _rows(volumes, day, cutoff, volume=True)
    if oi.empty or flow.empty:
        return {}
    oi['strike'] = pd.to_numeric(oi.strike, errors='coerce')
    oi['open_interest'] = pd.to_numeric(oi.open_interest, errors='coerce')
    oi = _latest(oi, ['symbol', 'contract_symbol'],
                 ['open_interest', 'strike', 'expiration_date', 'option_type', 'payload_hash'])
    oi['spot'] = oi.symbol.map(spots)
    oi['distance'] = (oi.strike / oi.spot - 1).abs()
    oi = oi[oi.distance.le(ATM_MAX_DISTANCE) & oi.open_interest.ge(0) & np.isfinite(oi.open_interest)].copy()
    keys = ['symbol', 'expiration_date', 'strike']
    oi = oi[oi.option_type.eq('CALL')].merge(oi[oi.option_type.eq('PUT')], on=keys,
        suffixes=('_call', '_put'), validate='one_to_one')
    if oi.empty:
        return {}
    oi['tenor_distance'] = (oi.dte_call - DTE_TARGET).abs()
    oi = oi.sort_values(['symbol', 'tenor_distance', 'distance_call', 'expiration_date', 'strike'],
                        kind='stable').drop_duplicates('symbol')
    oi = oi[['symbol', 'expiration_date', 'open_interest_call', 'open_interest_put',
             'received_at_call', 'received_at_put']]
    flow['volume'] = pd.to_numeric(flow.volume, errors='coerce')
    flow = _latest(flow, ['symbol', 'contract_symbol', 'bar_timestamp'],
                   ['volume', 'payload_hash', 'option_type', 'expiration_date'])
    if flow.empty:
        return {}
    flow['bad'] = ~np.isfinite(flow.volume) | flow.volume.lt(0)
    flow = flow.groupby(['symbol', 'expiration_date', 'option_type'], as_index=False).agg(
        volume=('volume', 'sum'), bad=('bad', 'any'), received_at=('received_at', 'max'), dte=('dte', 'first'))
    flow = flow[~flow.bad].copy()
    flow = flow[flow.option_type.eq('CALL')].merge(flow[flow.option_type.eq('PUT')],
        on=['symbol', 'expiration_date'], suffixes=('_call', '_put'), validate='one_to_one')
    if flow.empty:
        return {}
    flow['tenor_distance'] = (flow.dte_call - DTE_TARGET).abs()
    flow = flow.sort_values(['symbol', 'tenor_distance', 'expiration_date'], kind='stable').drop_duplicates('symbol')
    paired = flow.merge(oi, on='symbol', suffixes=('_volume', '_oi'), validate='one_to_one')
    result = {}
    for r in paired.to_dict('records'):
        result[r['symbol']] = dict(
            volume_feature=math.log1p(r['volume_call']) - math.log1p(r['volume_put']),
            oi_feature=math.log1p(r['open_interest_call']) - math.log1p(r['open_interest_put']),
            volume_expiry=str(r['expiration_date_volume'].date()), oi_expiry=str(r['expiration_date_oi'].date()),
            available_at=str(max(r[k] for k in ('received_at_call_volume', 'received_at_put_volume',
                                               'received_at_call_oi', 'received_at_put_oi'))))
    return result


def select_top(oracle, features, config):
    """Fix TOP before missing-data handling. Rank only the doubly covered cohort."""
    if not oracle or len({r['symbol'] for r in oracle}) != len(oracle):
        raise ValueError('Classement Oracle vide ou dupliqué')
    if any(not math.isfinite(float(r['proba_extreme'])) or not 0 <= float(r['proba_extreme']) <= 1 for r in oracle):
        raise ValueError('Score Oracle invalide')
    top = sorted(oracle, key=lambda r: (-float(r['proba_extreme']), r['symbol']))[:config.oracle_top_n]
    covered = [r['symbol'] for r in top if r['symbol'] in features]
    ranks = {}
    upper_half = set()
    if len(covered) >= config.min_covered:
        frame = pd.DataFrame([dict(symbol=s, **features[s]) for s in covered]).set_index('symbol')
        if not np.isfinite(frame[['volume_feature', 'oi_feature']].to_numpy(float)).all():
            raise ValueError('Feature options invalide')
        for name in ('volume', 'oi'):
            frame[name+'_score'] = (frame[name+'_feature'].rank(method='average') - .5) / len(frame)
        frame['combined_score'] = .5 * frame.volume_score + .5 * frame.oi_score
        ranks = frame.to_dict('index')
        oracle_order = {r['symbol']: i for i, r in enumerate(top)}
        upper_half = set(sorted(covered, key=lambda s: (-ranks[s]['combined_score'], oracle_order[s]))[:len(covered)//2])
    rows = []
    for rank, r in enumerate(top, 1):
        feature = features.get(r['symbol'])
        score = ranks.get(r['symbol'], {}).get('combined_score')
        reason = ('MISSING_OR_STALE_OPTIONS' if feature is None else
                  'INSUFFICIENT_COVERED_COHORT' if score is None else
                  'SCORE_NOT_ABOVE_THRESHOLD' if score <= config.min_combined_score else
                  'OUTSIDE_UPPER_HALF' if r['symbol'] not in upper_half else 'SELECTED_LONG')
        rows.append(dict(symbol=r['symbol'], oracle_rank=rank, oracle_score=float(r['proba_extreme']),
                         **(ranks.get(r['symbol']) or feature or {}), selected=reason == 'SELECTED_LONG', reason=reason))
    return rows
