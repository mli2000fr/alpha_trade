"""Frozen Feb/Mar 2024 options audit. SQL SELECT + existing RAW cache only.

Never calls Alpaca, modifies a batch, trains a model or writes production SQL.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import gzip
import hashlib
import json
import logging
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sqlalchemy import text
from common.market_calendar import get_market_calendar
from database.connection import get_sqlalchemy_engine
from service.alpaca.options_history_backfill import atomic_json, digest
from scripts.research.us_prospective_directional_collection_audit import query
from scripts.research.us_prospective_directional_check import directional_metrics

ROOT = Path('artifacts/research/alpaca_options_history/backfill-20240120-20261009-v1')
OUTPUT = Path('artifacts/research/alpaca_options_history/directional-feb-mar-2024-20261011-v1')
FEATURE = 'volume_call_minus_put_log'


def cached_spots(root, symbols):
    """Deterministic cache addresses; missing RAW is excluded, never downloaded."""
    rows, absent = [], []
    ny = ZoneInfo('America/New_York')
    for start, end in [(date(2024, 2, 1), date(2024, 2, 29)), (date(2024, 3, 1), date(2024, 3, 31))]:
        for offset in range(0, len(symbols), 100):
            params = {'symbols': ','.join(symbols[offset:offset+100]), 'timeframe': '1Day',
                'start': datetime.combine(start, datetime.min.time(), ny).isoformat(),
                'end': datetime.combine(end+timedelta(days=1), datetime.min.time(), ny).isoformat(),
                'adjustment': 'raw', 'feed': 'iex', 'limit': 10000, 'sort': 'asc'}
            for _ in range(100):
                path = root/'raw'/(digest({'url': 'https://data.alpaca.markets/v2/stocks/bars', 'params': params})+'.json.gz')
                if not path.exists():
                    absent.append({'month': start.strftime('%Y-%m'), 'chunk': offset//100, 'cache': path.name})
                    break
                with gzip.open(path, 'rt', encoding='utf-8') as stream:
                    raw = json.load(stream)
                for symbol, items in (raw['payload'].get('bars') or {}).items():
                    for bar in items:
                        day = pd.Timestamp(bar['t']).tz_convert(ny).tz_localize(None).normalize()
                        value = float(bar['c'])
                        if np.isfinite(value) and value > 0:
                            rows.append({'symbol': symbol, 'day': day, 'spot': value})
                token = raw['payload'].get('next_page_token')
                if not token:
                    break
                params = params | {'page_token': token}
            else:
                raise ValueError('Incomplete cached pagination')
    return pd.DataFrame(rows, columns=['symbol', 'day', 'spot']).drop_duplicates(['symbol', 'day']), absent


def paired_features(options, spots):
    options = options.copy()
    options['day'] = pd.to_datetime(options.bar_timestamp, utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    options['expiry'] = pd.to_datetime(options.expiration_date)
    options['volume'] = pd.to_numeric(options.volume, errors='coerce')
    options['strike'] = pd.to_numeric(options.strike, errors='coerce')
    options = options.merge(spots, on=['symbol', 'day'], validate='many_to_one')
    options['dte'] = (options.expiry-options.day).dt.days
    options['distance'] = (options.strike/options.spot-1).abs()
    options = options[options.dte.between(15, 25) & options.distance.le(.05)
                      & options.volume.ge(0) & np.isfinite(options.volume)]
    keys = ['symbol', 'day', 'expiry', 'strike']
    result = options[options.option_type.eq('CALL')].merge(options[options.option_type.eq('PUT')],
        on=keys, suffixes=('_call', '_put'), validate='one_to_one')
    result['tenor_distance'] = (result.dte_call-20).abs()
    result = result.sort_values(['symbol', 'day', 'tenor_distance', 'distance_call', 'expiry', 'strike'],
        kind='stable').drop_duplicates(['symbol', 'day'])
    result[FEATURE] = np.log1p(result.volume_call)-np.log1p(result.volume_put)
    return result


def metrics(frame):
    result = directional_metrics(frame, FEATURE)
    extreme = frame[frame.decile.isin([1, 10])]
    groups = {}
    for name, selected in [('call_dominant', extreme[extreme[FEATURE].gt(0)]),
                           ('put_dominant', extreme[extreme[FEATURE].lt(0)]),
                           ('equal_volume', extreme[extreme[FEATURE].eq(0)])]:
        groups[name] = {'count': len(selected), 'd10_pct': float(selected.decile.eq(10).mean()*100) if len(selected) else None}
    result['fixed_sign_extreme_groups'] = groups
    result['baseline_extreme_d10_pct'] = float(extreme.decile.eq(10).mean()*100) if len(extreme) else None
    by_symbol = []
    for symbol, part in extreme.groupby('symbol'):
        if len(part) >= 20 and part.decile.nunique() == 2 and part[FEATURE].nunique() > 1:
            by_symbol.append({'symbol': symbol, 'count': len(part),
                              'auc': float(roc_auc_score(part.decile.eq(10), part[FEATURE]))})
    result['within_symbol_diagnostic'] = by_symbol
    return result


def run():
    OUTPUT.mkdir(parents=True, exist_ok=False)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', handlers=[
        logging.StreamHandler(), logging.FileHandler(OUTPUT/'run.log', encoding='utf-8')])
    plan = json.loads((ROOT/'plan.json').read_text(encoding='utf-8'))
    symbols = plan['symbols']
    snapshot = datetime.now(timezone.utc).replace(tzinfo=None)
    protocol = {'start': '2024-02-01', 'end_inclusive': '2024-03-31', 'primary_horizon': 20,
        'secondary_horizons': [3, 5, 10], 'feature': FEATURE, 'orientation': 'higher -> D10',
        'selection': 'nearest 20 calendar DTE within 15..25; same strike/expiry; ATM <=5% from cached raw IEX spot',
        'entry': 'next US session open', 'exit': 'Hth session close, entry included',
        'labels': 'signed-return deciles in full price-qualified frozen current tradable universe, min coverage 90%',
        'universe_count': len(symbols), 'universe_sha256': plan['universe_sha256'], 'source_plan_sha256': digest(plan),
        'sql_snapshot_cutoff_utc': str(snapshot), 'sql_writes': False, 'api_calls': 0,
        'models_trained': False, 'threshold_tuning': False, 'portfolio_or_orders': False,
        'historical_available_at': 'actual retrieval in October 2026; next-open historical feature availability only assumed',
        'secondary_checks': 'per month, daily AUC, temporal halves, fixed H-spaced nonoverlapping entry cohort',
        'limitations': ['Not certified historical PIT; archived catalog is current, not a full historical chain',
            'Current universe survivorship bias; limited ATM pairs not full chain/signed buyer order flow',
            'UNVERIFIED_OPRA; no OI/IV/Greeks/NBBO included; IEX is strike-selection spot, not consolidated volume',
            'Overlapping returns and two months; no sector/size neutralization or economic validation',
            'Canonical split-adjusted stock returns, not total returns with corporate-action cash',
            'Not conditional on Oracle predicted TOP20; standalone D1/D10 diagnostic']}
    atomic_json(OUTPUT/'protocol.json', protocol)
    tasks = {}
    for month in ('2024-02', '2024-03'):
        records = [json.loads((ROOT/'tasks'/f'{month}_{s}.json').read_text(encoding='utf-8'))
                   if (ROOT/'tasks'/f'{month}_{s}.json').exists() else {'status': 'MISSING'} for s in symbols]
        tasks[month] = {status: sum(r['status'] == status for r in records) for status in ('COMPLETED', 'EMPTY', 'FAILED', 'MISSING')}
    logging.info('Frozen protocol; checkpoints %s', tasks)
    spots, absent = cached_spots(ROOT, symbols)
    logging.info('Cached historical raw IEX spots=%d; absent pages=%d', len(spots), len(absent))
    engine = get_sqlalchemy_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            options = pd.DataFrame(query(conn, '''SELECT id,underlying_symbol AS symbol,contract_symbol,
                expiration_date,strike,option_type,bar_timestamp,observed_at,available_at,volume,payload_hash
                FROM alpha_trade.stock_option_bars_delayed WHERE underlying_symbol IN :symbols
                AND provider='alpaca' AND feed='historical_default' AND timeframe='1Day'
                AND bar_timestamp >= '2024-02-01' AND bar_timestamp < '2024-04-01'
                AND observed_at<=:cutoff''', symbols, cutoff=snapshot))
            logging.info('SQL option bars=%d', len(options))
            prices = pd.DataFrame(query(conn, '''SELECT symbol,date,open,high,low,close,volume,is_filled,data_adjustment
                FROM alpha_trade.stock_bars_daily WHERE symbol IN :symbols
                AND date >= '2024-02-01' AND date <= '2024-05-15' ''', symbols))
            conn.rollback()
    finally:
        engine.dispose()
    identity = ['symbol', 'contract_symbol', 'bar_timestamp']
    conflicts = options.groupby(identity).payload_hash.nunique()
    conflicting = conflicts[conflicts.gt(1)].index
    excluded_versions = options.set_index(identity).index.isin(conflicting)
    option_quality = {'raw_rows': len(options), 'conflicting_contract_bars': len(conflicting),
                      'excluded_conflicting_rows': int(excluded_versions.sum())}
    options = options[~excluded_versions].sort_values(['observed_at', 'id']).drop_duplicates(identity)
    features = paired_features(options, spots)
    features.to_parquet(OUTPUT/'features.parquet', index=False)
    logging.info('Matched features=%d, symbols=%d', len(features), features.symbol.nunique())
    prices['date'] = pd.to_datetime(prices.date)
    for col in ['open', 'high', 'low', 'close', 'volume']:
        prices[col] = pd.to_numeric(prices[col], errors='coerce')
    prices['valid'] = (prices.is_filled.eq(0) & prices.data_adjustment.eq('split')
        & prices.open.gt(0) & prices.close.gt(0) & prices.volume.gt(0)
        & prices.high.ge(prices[['open', 'close']].max(axis=1))
        & prices.low.le(prices[['open', 'close']].min(axis=1)))
    opens, closes, valid = [prices.pivot(index='date', columns='symbol', values=c).reindex(columns=symbols)
                            for c in ('open', 'close', 'valid')]
    calendar = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    sessions = pd.DatetimeIndex(calendar.session_dates(date(2024, 2, 1), date(2024, 5, 15)))
    next_day = {day: sessions[sessions > day][0] for day in features.day.unique()}
    features['entry_date'] = features.day.map(next_day)
    result = {'status': 'COMPLETED_EXPLORATORY_NO_PROMOTION', 'protocol': protocol,
              'tasks': tasks, 'missing_raw_spot_pages': absent, 'option_quality': option_quality,
              'feature_count': len(features), 'feature_symbols': int(features.symbol.nunique()),
              'monthly_coverage': features.groupby(features.day.dt.strftime('%Y-%m')).agg(
                  pairs=('symbol', 'size'), symbols=('symbol', 'nunique'), days=('day', 'nunique')).reset_index().to_dict('records'),
              'horizons': {}}
    for h in (3, 5, 10, 20):
        targets, coverage = [], []
        for entry in sorted(features.entry_date.unique()):
            start = sessions.get_loc(entry)
            path = sessions[start:start+h]
            good = valid.reindex(path).eq(True).all(axis=0)
            returns = closes.reindex([path[-1]]).iloc[0]/opens.reindex([entry]).iloc[0]-1
            returns = returns[good & np.isfinite(returns)]
            coverage.append({'entry_date': str(pd.Timestamp(entry).date()), 'label_symbols': len(returns),
                             'qualified': len(path) == h and len(returns) >= .9*len(symbols)})
            if not coverage[-1]['qualified']:
                continue
            frame = returns.rename('future_return').reset_index().sort_values(['future_return', 'symbol'], kind='stable')
            frame['decile'] = (np.floor(np.arange(len(frame))*10/len(frame))+1).astype(int)
            frame['entry_date'] = entry
            targets.append(frame)
        if not targets:
            result['horizons'][str(h)] = {'status': 'NO_QUALIFIED_LABELS', 'coverage': coverage}
            continue
        joined = features.merge(pd.concat(targets), on=['entry_date', 'symbol'], validate='one_to_one')
        joined.to_parquet(OUTPUT/f'pairs_h{h}.parquet', index=False)
        block_days = sorted(features.entry_date.unique())[::h]  # Fixed phase, no best offset selection.
        result['horizons'][str(h)] = {'overall': metrics(joined), 'coverage': coverage,
            'monthly': {month: metrics(part) for month, part in joined.groupby(joined.day.dt.strftime('%Y-%m'))},
            'fixed_nonoverlapping_cohort': metrics(joined[joined.entry_date.isin(block_days)])}
        logging.info('H%d samples=%d extremes=%d pooled_auc=%s daily_auc=%s', h,
            result['horizons'][str(h)]['overall']['samples'], result['horizons'][str(h)]['overall']['extreme_samples'],
            result['horizons'][str(h)]['overall']['auc_pooled_exploratory'], result['horizons'][str(h)]['overall']['mean_daily_auc'])
    atomic_json(OUTPUT/'report.json', result)
    logging.info('Audit complete %s', OUTPUT)
    return result


if __name__ == '__main__':
    run()
