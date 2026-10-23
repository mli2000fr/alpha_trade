"""Offline, unfitted TOP10 path-trend ranking audit; no SQL/network/serving."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.security_continuity import (
    DEFAULT_REGISTRY_PATH, load_security_discontinuities,
    path_crosses_known_discontinuity, split_frame_on_discontinuities,
)
from scripts.research.us_oracle_path_protection_dataset import (
    STOCK, MARKET, decision_features, j_history_quality,
)

LOG = logging.getLogger(__name__)
ROOT = Path('artifacts/research/us_oracle_path_trend_ranking/20261022-v1')
DOC = Path('doc/ml/oracle_tri_tendance_parcours_protocole_20261022.md')
PARENT = Path('artifacts/research/us_oracle_path_profit_filter/20261015-protocol-v1')
DATASET = Path('artifacts/research/us_oracle_path_profit_filter/20261015-tp15-sl7-dataset-v2')
RECENT = Path('artifacts/research/us_news_gpt_long_comparison/20261015-v1')
HISTORY = Path('artifacts/research/oracle_path_comparison/20261013-v1/models/oracle-path-comparison/oracle_path')
BENCHMARK = Path('artifacts/research/us_oracle_path_protection_dataset/20261014-v1/benchmark-history.parquet')
FEATURES = [*STOCK, *MARKET, 'score', 'oracle_rank']
PRIMARY = [*STOCK, 'relative_strength_20', 'relative_strength_60']
PERIODS = ['DISCOVERY', 'VALIDATION', 'CONTROL_2023', 'CHECK_2024', 'CHECK_2025', 'CHECK_2026']
AS_OF = pd.Timestamp('2026-10-09')
RULES = dict(discovery_ic=.05, validation_ic=.03, maxT_alpha=.05,
             discovery_dates=100, validation_dates=30, confirmation_dates=30,
             block=63, min_block_dates=20, min_blocks=8, replications=999, seed=20261022)
PRICE_COLS = ['date', 'symbol', 'open', 'high', 'low', 'close', 'adj_close',
              'volume', 'instrument_id', 'is_filled', 'data_source', 'data_adjustment']
METRICS = ['area_pct', 'persistence_pct', 'adverse_before_peak_close_pct',
           'peak_close_pct', 'peak_session', 'terminal_pct',
           'mfe_intraday_pct', 'mae_intraday_pct',
           'adverse_before_high_day_lower_pct', 'adverse_before_high_day_upper_pct']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False,
                  default=lambda v: v.item() if isinstance(v, np.generic) else str(v))


def verify(items):
    for name, expected in items.items():
        if digest(name) != expected:
            raise ValueError(f'Immutable source changed: {name}')


def freeze(output):
    if output.exists():
        raise FileExistsError('Fresh immutable output directory required')
    parent = read(PARENT/'manifest.json')
    old = read(DATASET/'protocol.json')
    audit = read(DATASET/'completion-audit.json')
    if audit['status'] != 'AUDITED_NATIVE_TP15_SL7_DATASET':
        raise ValueError('Historical feature audit absent')
    sources = {}

    def bind(path, expected=None):
        actual = digest(path)
        if expected and actual != expected:
            raise ValueError(f'Input hash mismatch: {path}')
        sources[str(path)] = actual

    for path in [Path(__file__), DOC, Path('tests/test_us_oracle_path_trend_ranking_20261022.py'),
                 PARENT/'manifest.json', PARENT/'report.json', DATASET/'protocol.json',
                 DATASET/'completion-audit.json', RECENT/'ready.json', RECENT/'audit.json',
                 DEFAULT_REGISTRY_PATH,
                 Path('modelFactory/oracle/security_continuity.py'),
                 Path('modelFactory/oracle/build_labels.py'), Path('modelFactory/features.py'),
                 Path('scripts/research/us_oracle_path_protection_dataset.py')]:
        bind(path)
    bind(DATASET/'report.json', audit['source_report_sha256'])
    bind(DATASET/'dataset.parquet', audit['source_dataset_sha256'])
    bind(PARENT/'historical-top20.parquet', read(PARENT/'report.json')['files']['historical-top20.parquet'])
    bind(BENCHMARK, old['sources'][str(BENCHMARK)])
    recent = read(RECENT/'ready.json')
    bind(RECENT/'candidates.parquet', recent['files']['candidates.parquet'])
    price_path = Path(recent['prices'])
    expected = next(v for k, v in recent['sources'].items() if Path(k) == price_path)
    bind(price_path, expected)
    folds = []
    for folder in sorted((HISTORY/'folds').iterdir()):
        path = folder/'done.json'
        bind(path, parent['sources'][str(path)])
        m = read(path)['metrics']
        if any(pd.Timestamp(m[k]) >= pd.Timestamp(m['test_start'])
               for k in ('train_available_max', 'val_available_max')):
            raise ValueError('Noncausal Oracle OOF fold')
        folds.append(dict(name=folder.name, test_start=m['test_start'], test_end=m['test_end'],
                          train_available_max=m['train_available_max'], val_available_max=m['val_available_max']))
    for item in parent['price_chunks']:
        bind(item['path'], item['verified_sha256'])
    # Annual scores are reused, not regenerated using current production weights.
    contracts_path = Path('artifacts/research/us_oracle_path_protection_dataset/20261014-v1/protocol.json')
    bind(contracts_path, parent['sources'][str(contracts_path)])
    contracts = read(contracts_path)['annual_test_models']
    for year, c in contracts.items():
        if any(pd.Timestamp(c[k]) >= pd.Timestamp(f'{year}-01-01')
               for k in ('train_available_max', 'val_available_max')):
            raise ValueError('Noncausal annual Oracle metadata')
    output.mkdir(parents=True)
    value = dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
                 features=FEATURES, primary_family=PRIMARY, rules=RULES, folds=folds,
                 annual_contracts=contracts, recent_prices=str(price_path),
                 historical_price_chunks=parent['price_chunks'], as_of=str(AS_OF.date()),
                 horizon=20, target='mean signed close return from J1 open; no TP/SL',
                 label_availability='NYSE J21', main_side='LONG', short_mirror_only=True,
                 training=False, sql_reads=0, sql_writes=False, API_calls=0,
                 portfolio_backtest=False, orders=False, production_changed=False,
                 current_survivor_universe=True, strict_PIT_certified=False)
    save(output/'protocol.json', value)
    return value


def period_for(day, available):
    day, available = pd.Timestamp(day), pd.Timestamp(available)
    if pd.isna(available):
        return 'IMMATURE'
    if day.year <= 2021:
        return 'DISCOVERY' if available < pd.Timestamp('2022-01-01') else 'PURGED_DISCOVERY'
    if day.year == 2022:
        return 'VALIDATION' if available < pd.Timestamp('2023-01-01') else 'PURGED_VALIDATION'
    return 'CONTROL_2023' if day.year == 2023 else f'CHECK_{day.year}'


def path_metrics(window):
    """Twenty daily OHLC: close chronology exact; high/low chronology bounded."""
    a = np.asarray(window, dtype=float)
    if a.shape != (20, 4) or not np.isfinite(a).all() or (a <= 0).any():
        raise ValueError('Require twenty positive finite OHLC bars')
    o, h, l, c = a.T
    if (h < np.maximum(o, c)).any() or (l > np.minimum(o, c)).any() or (h < l).any():
        raise ValueError('Inconsistent OHLC')
    entry = o[0]
    returns = (c/entry-1)*100
    result = {}
    for side, sign in [('long', 1), ('short', -1)]:
        r = np.r_[0., sign*returns]
        peak = int(np.argmax(r))  # earliest tie; reference entry included
        favourable = (h/entry-1)*100 if sign == 1 else (1-l/entry)*100
        adverse = (1-l/entry)*100 if sign == 1 else (h/entry-1)*100
        imax = int(np.argmax(np.r_[0., favourable]))-1
        before = adverse[:imax] if imax >= 0 else []
        through = adverse[:imax+1] if imax >= 0 else []
        out = dict(area_pct=float(sign*returns.mean()),
                   persistence_pct=float(100*np.mean(sign*returns > 0)),
                   adverse_before_peak_close_pct=float(max(0., -r[:peak+1].min())),
                   peak_close_pct=float(r[peak]), peak_session=peak,
                   terminal_pct=float(sign*returns[-1]),
                   mfe_intraday_pct=float(max(0., np.max(favourable))),
                   mae_intraday_pct=float(max(0., np.max(adverse))),
                   adverse_before_high_day_lower_pct=float(max([0., *before])),
                   adverse_before_high_day_upper_pct=float(max([0., *through])))
        result.update({f'{side}_{k}': v for k, v in out.items()})
    return result


def qualify_path(grid, j, days, symbol, registry):
    if j < 0 or j+21 >= len(days) or days[j+21] > AS_OF:
        return 'IMMATURE_J21'
    path = grid.iloc[j:j+21]
    num = path[['open', 'high', 'low', 'close', 'volume']].apply(pd.to_numeric, errors='coerce')
    if len(path) != 21 or not np.isfinite(num).all().all() or not num.gt(0).all().all():
        return 'MISSING_OR_NONPOSITIVE_PATH'
    if not path.is_filled.eq(0).all():
        return 'FILLED_PATH'
    if (num.high < num[['open', 'close']].max(axis=1)).any() or (num.low > num[['open', 'close']].min(axis=1)).any() or (num.high < num.low).any():
        return 'INCONSISTENT_OHLC'
    for col in ['instrument_id', 'data_source', 'data_adjustment']:
        s = path[col].astype('string').str.strip()
        if s.isna().any() or s.str.upper().isin(['', 'UNKNOWN']).any() or s.nunique() != 1:
            return 'UNKNOWN_OR_CHANGED_'+col.upper()
    if not path.data_adjustment.eq('split').all():
        return 'NOT_SPLIT_BASIS'
    if not pd.to_numeric(path.instrument_id, errors='coerce').gt(0).all():
        return 'INVALID_IDENTITY'
    ratio = num.close/num.close.shift()
    if ratio.ge(20).any() or ratio.le(.05).any():
        return 'UNEXPLAINED_20X_BREAK'
    if path_crosses_known_discontinuity(symbol, days[j], days[j+20], registry):
        return 'KNOWN_IDENTITY_BREAK'
    return ''


def recent_inputs(pool, prices, days, registry):
    spy = prices.loc[prices.symbol.eq('SPY')].sort_values('date').set_index('date').adj_close
    if not spy.index.is_unique:
        raise ValueError('Duplicate benchmark')
    parts, probes = [], []
    for symbol, group in pool.groupby('symbol', sort=True):
        raw = prices.loc[prices.symbol.eq(symbol)].sort_values('date').copy()
        if raw.empty:
            empty = group.copy()
            for f in STOCK+MARKET:
                empty[f] = np.nan
            empty['J_qualified'] = False
            parts.append(empty)
            continue
        frames, qualities, segments = [], [], list(split_frame_on_discontinuities(raw, symbol, registry))
        for s in segments:
            frames.append(decision_features(s, spy))
            grid = s.set_index('date').reindex(days[(days >= s.date.min()) & (days <= s.date.max())])
            qualities.append(j_history_quality(grid, spy, days))
        f, q = pd.concat(frames), pd.concat(qualities)
        if not f.index.is_unique or not q.index.is_unique:
            raise ValueError('Duplicate feature dates')
        joined = group.merge(f[STOCK+MARKET], left_on='date', right_index=True, how='left', validate='one_to_one')
        joined['J_qualified'] = joined.date.map(q).fillna(False).astype(bool) & np.isfinite(joined[STOCK+MARKET]).all(axis=1)
        for day in sorted(set(group.date.iloc[[0, len(group)//2, -1]])):
            segment = next((s for s in segments if s.date.min() <= day <= s.date.max()), None)
            if segment is None:
                continue
            prefix = decision_features(segment[segment.date.le(day)], spy.loc[:day])
            pd.testing.assert_series_equal(f.loc[day], prefix.loc[day], check_exact=True)
            probes.append(dict(symbol=symbol, date=str(day.date()), prefix_exact=True))
        parts.append(joined)
    return pd.concat(parts, ignore_index=True), probes


def freeze_recent(p):
    names = ['date', 'symbol', 'score', 'oracle_rank', 'fold_start', 'batch_id', 'model_available_date']
    a = pd.read_parquet(RECENT/'candidates.parquet', columns=names)
    a = a.loc[a.oracle_rank.le(10)].copy()
    validate_top10(a)
    for year, c in p['annual_contracts'].items():
        g = a[a.date.dt.year.eq(int(year))]
        if not g.batch_id.eq(c['batch_id']).all() or not pd.to_datetime(g.model_available_date).lt(g.date).all():
            raise ValueError('Wrong/noncausal annual Oracle')
    return a[['date', 'symbol', 'score', 'oracle_rank', 'fold_start']]


def validate_top10(a):
    if a.duplicated(['date', 'symbol']).any() or a[['date', 'symbol', 'score', 'oracle_rank']].isna().any().any():
        raise ValueError('Missing/duplicate candidate key')
    if not np.isfinite(a.score).all() or not a.groupby('date').oracle_rank.apply(lambda r: sorted(r)==list(range(1, 11))).all():
        raise ValueError('Incomplete original TOP10')
    order = a.sort_values(['date', 'score', 'symbol'], ascending=[True, False, True])
    if not np.array_equal(order.oracle_rank.to_numpy(), order.groupby('date').cumcount().to_numpy()+1):
        raise ValueError('Oracle order differs from observable score')


def build_dataset(output, p):
    cols = ['date', 'symbol', 'score', 'oracle_rank', 'fold_start', *STOCK, *MARKET, 'J_qualified']
    historical = pd.read_parquet(DATASET/'dataset.parquet', columns=cols)
    historical = historical.loc[historical.oracle_rank.le(10)].copy()
    parent = pd.read_parquet(PARENT/'historical-top20.parquet')
    parent = parent.loc[parent.oracle_rank.le(10), ['date', 'symbol', 'score', 'oracle_rank', 'fold_start']]
    keys = ['date', 'symbol']
    pd.testing.assert_frame_equal(historical[parent.columns].sort_values(keys).reset_index(drop=True),
                                  parent.sort_values(keys).reset_index(drop=True), check_dtype=False)
    validate_top10(historical)
    recent = freeze_recent(p)
    registry = load_security_discontinuities()
    days = nyse_sessions('2016-01-01', AS_OF.date())
    recent_prices = pd.read_parquet(p['recent_prices'], columns=PRICE_COLS)
    if recent_prices.duplicated(keys).any():
        raise ValueError('Ambiguous recent price')
    recent, probes = recent_inputs(recent, recent_prices, days, registry)
    pool = pd.concat([historical, recent], ignore_index=True)
    validate_top10(pool)
    pool.to_parquet(output/'observable-top10.parquet', index=False)
    save(output/'prefix-checks.json', probes)
    wanted = set(historical.symbol)
    parts = [pd.read_parquet(item['path'], columns=PRICE_COLS, filters=[('symbol', 'in', list(wanted))])
             for item in p['historical_price_chunks']]
    historical_prices = pd.concat(parts, ignore_index=True)
    if historical_prices.duplicated(keys).any():
        raise ValueError('Ambiguous historical price')
    records = []
    for source, candidates, prices in [('historical', historical, historical_prices), ('recent', recent, recent_prices)]:
        for number, (symbol, g) in enumerate(candidates.groupby('symbol', sort=True)):
            raw = prices[prices.symbol.eq(symbol)].sort_values('date')
            grid = raw.set_index('date').reindex(days)
            for row in g.itertuples(index=False):
                j = days.get_indexer([row.date])[0]
                available = days[j+21] if 0 <= j and j+21 < len(days) else pd.NaT
                reason = 'J_HISTORY_OR_FEATURES_UNQUALIFIED' if not row.J_qualified else qualify_path(grid, j, days, symbol, registry)
                record = dict(date=row.date, symbol=symbol, source=source, label_available=available,
                              period=period_for(row.date, available), path_reason=reason,
                              nonoverlap=(j-days.get_indexer([pd.Timestamp('2018-07-05')])[0]) % 21 == 0)
                if not reason:
                    record.update(path_metrics(grid[['open', 'high', 'low', 'close']].iloc[j+1:j+21].to_numpy(float)))
                records.append(record)
            if number % 50 == 0:
                LOG.info('%s paths: %s symbols', source, number+1)
    targets = pd.DataFrame(records)
    result = pool.merge(targets, on=keys, validate='one_to_one')
    result['individual_known'] = result.path_reason.eq('') & np.isfinite(result[FEATURES]).all(axis=1)
    result['complete_date'] = result.groupby('date').individual_known.transform('all')
    result.to_parquet(output/'dataset.parquet', index=False)
    return result


def daily_ic(frame, columns):
    x = frame[columns].groupby(frame.date).rank(method='average')
    y = frame.groupby('date').long_area_pct.rank(method='average')
    xc = x-x.groupby(frame.date).transform('mean')
    yc = y-y.groupby(frame.date).transform('mean')
    numerator = xc.mul(yc, axis=0).groupby(frame.date).sum()
    den = np.sqrt(xc.pow(2).groupby(frame.date).sum().mul(yc.pow(2).groupby(frame.date).sum(), axis=0))
    return numerator.div(den.where(den.gt(0)))


def maxT(daily, calendar):
    idx = pd.Series(np.arange(len(calendar)), index=calendar)
    blocks = (idx.reindex(daily.index)//RULES['block']).astype(int)
    means = daily.groupby(blocks.to_numpy()).mean().where(
        daily.groupby(blocks.to_numpy()).count().ge(RULES['min_block_dates']))
    matrix = means.to_numpy(float)
    n = np.isfinite(matrix).sum(axis=0)
    def stat(a):
        with np.errstate(invalid='ignore', divide='ignore'):
            return np.abs(np.nanmean(a, axis=0)/(np.maximum(np.nanstd(a, axis=0, ddof=1), 1e-12)/np.sqrt(n)))
    obs = stat(matrix)
    eligible = n >= RULES['min_blocks']
    rng = np.random.default_rng(RULES['seed'])
    null = []
    for _ in range(RULES['replications']):
        s = stat(matrix*rng.choice([-1., 1.], size=(len(matrix), 1)))
        null.append(float(np.nanmax(s[eligible])) if eligible.any() else 0.)
    return {c: dict(blocks=int(n[i]), p_maxT=float((1+np.sum(np.array(null)>=obs[i]))/(1+len(null)))
                    if eligible[i] and np.isfinite(obs[i]) else None) for i, c in enumerate(daily.columns)}


def select(frame, feature, orientation, count, side='long'):
    a = frame[['date', 'symbol', feature]].copy()
    a['priority'] = a[feature]*orientation*(1 if side == 'long' else -1)
    a = a.sort_values(['date', 'priority', 'symbol'], ascending=[True, False, True])
    return a.groupby('date', sort=False).head(count)[['date', 'symbol']]


def bootstrap_mean(series):
    a = np.asarray(series, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) < 2*RULES['block']:
        return None
    rng = np.random.default_rng(RULES['seed'])
    b = RULES['block']
    starts = rng.integers(0, len(a)-b+1, size=(RULES['replications'], int(np.ceil(len(a)/b))))
    indices = (starts[..., None]+np.arange(b)).reshape(RULES['replications'], -1)[:, :len(a)]
    return [float(x) for x in np.quantile(a[indices].mean(axis=1), [.025, .975])]


def policy_statistics(frame, feature, orientation, count, side='long'):
    keys = select(frame, feature, orientation, count, side)
    chosen = keys.merge(frame, on=['date', 'symbol'], validate='one_to_one')
    baseline = frame.loc[frame.oracle_rank.le(count)]
    columns = [side+'_'+m for m in METRICS]
    d = chosen.groupby('date')[columns].mean()
    b = baseline.groupby('date')[columns].mean()
    uniform = frame.groupby('date')[columns].mean()
    future_key = select(frame, side+'_area_pct', 1, count)  # hindsight upper bound only
    ceiling = future_key.merge(frame, on=['date', 'symbol']).groupby('date')[side+'_area_pct'].mean()
    result = dict(rows=len(chosen), dates=len(d), symbols=int(chosen.symbol.nunique()),
                  max_symbol_share=float(chosen.symbol.value_counts(normalize=True).max()) if len(chosen) else None,
                  metrics={}, no_portfolio_returns=True)
    for m, c in zip(METRICS, columns):
        delta = d[c]-b[c]
        result['metrics'][m] = dict(selected=float(d[c].mean()) if len(d) else None,
            oracle=float(b[c].mean()) if len(b) else None, uniform=float(uniform[c].mean()) if len(uniform) else None,
            delta_oracle=float(delta.mean()) if len(delta) else None,
            delta_oracle_ci63=bootstrap_mean(delta),
            nonoverlap_delta=float(delta.loc[chosen.groupby('date').nonoverlap.first()].mean())
                if len(delta) and chosen.nonoverlap.any() else None)
    result['hindsight_area_ceiling_not_strategy'] = float(ceiling.mean()) if len(ceiling) else None
    result['nonoverlap_dates'] = int(chosen.groupby('date').nonoverlap.first().sum())
    return result


def period_gate(stats, minimum_dates):
    for k in ('3', '5'):
        s = stats[k]
        if s['dates'] < minimum_dates:
            return False
        m = s['metrics']
        if not (m['area_pct']['delta_oracle'] > 0 and m['persistence_pct']['delta_oracle'] >= 0
                and m['adverse_before_peak_close_pct']['delta_oracle'] <= 0):
            return False
    return True


def analyse(frame):
    known = frame.loc[frame.complete_date & frame.period.isin(PERIODS)].copy()
    coverage = []
    for period, g in frame.groupby('period', sort=True):
        coverage.append(dict(period=period, original_rows=len(g), original_dates=int(g.date.nunique()),
            J_qualified=int(g.J_qualified.sum()), individual_paths=int(g.individual_known.sum()),
            complete_rows=int(g.complete_date.sum()), complete_dates=int(g.loc[g.complete_date, 'date'].nunique()),
            path_reasons=g.path_reason.value_counts().to_dict()))
    discovery = known.loc[known.period.eq('DISCOVERY')]
    ics = daily_ic(known, FEATURES)
    periods = known.groupby('date').period.first()
    di = ics.loc[periods.eq('DISCOVERY')]
    calendar = nyse_sessions('2018-07-05', '2021-12-31')
    multiple = maxT(di[PRIMARY], calendar)
    records = []
    selection = []
    for feature in FEATURES:
        orientation = 1 if di[feature].mean() >= 0 else -1
        p = multiple.get(feature, dict(blocks=0, p_maxT=None))
        stats = {}
        for period in PERIODS:
            g = known[known.period.eq(period)]
            ic = ics.loc[periods.eq(period), feature].dropna()*orientation
            stats[period] = dict(dates_ic=len(ic), ic=float(ic.mean()) if len(ic) else None,
                policies={str(n): policy_statistics(g, feature, orientation, n) for n in (3, 5)})
        d, v = stats['DISCOVERY'], stats['VALIDATION']
        candidate = bool(feature in PRIMARY and p['p_maxT'] is not None and p['p_maxT']<=RULES['maxT_alpha']
            and d['ic'] is not None and d['ic']>=RULES['discovery_ic'] and d['dates_ic']>=RULES['discovery_dates']
            and v['ic'] is not None and v['ic']>=RULES['validation_ic'] and v['dates_ic']>=RULES['validation_dates']
            and period_gate(v['policies'], RULES['validation_dates']))
        # No external metric enters the preceding selection decision.
        stable = candidate and all(stats[t]['ic'] is not None and stats[t]['ic']>0
            and period_gate(stats[t]['policies'], RULES['confirmation_dates']) for t in PERIODS[2:])
        rec = dict(feature=feature, orientation_frozen_discovery=orientation, **p,
                   selected_before_confirmation=candidate, stable=bool(stable), periods=stats)
        records.append(rec)
        if candidate:
            selection.append(feature)
        LOG.info('Statistics %s: pre-confirmation=%s, stable=%s', feature, candidate, stable)
    best = sorted((r for r in records if r['feature'] in PRIMARY),
                  key=lambda r: r['periods']['DISCOVERY']['ic'] if r['periods']['DISCOVERY']['ic'] is not None else -np.inf,
                  reverse=True)[0]
    # Opposite ranking is a frozen mirror, not a new search for a winning side.
    mirror = {period: {str(n): policy_statistics(known[known.period.eq(period)], best['feature'],
               best['orientation_frozen_discovery'], n, 'short') for n in (3, 5)} for period in PERIODS}
    return dict(status='COMPLETED_EXPLORATORY',
        verdict='ASSOCIATION_ONLY_REQUIRES_NEW_VALIDATION' if any(r['stable'] for r in records)
                else 'NO_STABLE_UNIVARIATE_PATH_TREND_RANKING',
        coverage=coverage, features=records, selected_before_confirmation=selection,
        stable_features=[r['feature'] for r in records if r['stable']],
        best_discovery_diagnostic_only=best['feature'], short_mirror_diagnostic_only=mirror,
        comparison='3 and 5 within frozen TOP10; all ten complete on common dates',
        path_area_is_not_trade_return=True, model_fits=0, portfolio_runs=0, API_calls=0,
        sql_reads=0, sql_writes=False, orders=False, production_changed=False,
        limitations=['18 J-only price/relative-strength probes, not all173 upstream features',
          'split-only legacy EODHD caches, not SIP replacement or independent price certification',
          'mean path level need not be monotonic, stop-compatible, or achievable as exit profit',
          'daily bars cannot order same-day extrema; interval bounds only',
          'complete-future-window evaluation can bias coverage; original membership and exclusions preserved',
          'current survivor universe and historical provider vintages not certified PIT',
          '2024-2026 already examined, not untouched holdout',
          'maxT and bootstrap dependence diagnostics do not account for all historical research attempts',
          'no training; failed univariate gate is not proof multivariate models are impossible'])


def run(output):
    p = freeze(output)
    frame = build_dataset(output, p)
    report = analyse(frame)
    verify(p['sources'])
    report['files'] = {x.name: digest(x) for x in output.iterdir() if x.is_file()}
    report['source_hashes_verified_after_calculation'] = True
    save(output/'report.json', report)
    save(output/'progress.json', dict(status=report['status'], verdict=report['verdict']))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbidden(*args, **kwargs):
        raise RuntimeError('Network forbidden in offline path trend audit')
    requests.Session.request = forbidden
    result = run(args.output)
    print(json.dumps({k: result[k] for k in ('status', 'verdict', 'selected_before_confirmation', 'stable_features')}))
