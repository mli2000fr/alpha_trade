"""P-PATH-0: frozen univariate audit of dominant H20 excursions. No training.

Read-only SQL is used solely to archive complete price paths for the full scored
daily universe. All rankings and statistics are then computed offline. No label,
model, batch, order or serving table is changed.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from scipy.stats import rankdata

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_oracle_amplitude_rerank import HISTORY, EXTERNAL, checked, pool, read

LOG = logging.getLogger(__name__)
TASKS = ('D1_VS_D10', 'D10_VS_REST', 'D1_VS_REST', 'SIGN')
TARGETS = ('terminal', 'path', 'close_path')
DISCOVERY_CUTOFF = pd.Timestamp('2023-01-03')
MIN_DAILY_COVERAGE = .95
TIE_TOLERANCE = 1e-12


def dominant(up, down):
    """Both arguments are nonnegative fractions, not prices or percentage points."""
    up, down = np.asarray(up, float), np.asarray(down, float)
    valid = np.isfinite(up) & np.isfinite(down) & (up >= 0) & (down >= 0)
    tie = valid & np.isclose(up, down, rtol=0., atol=TIE_TOLERANCE)
    signed = np.where(up > down, up, -down)
    return np.where(valid & ~tie, signed, np.nan)


def evaluate_paths(selected, bars, sessions, registry):
    """Vectorized equivalent of the prior price-path qualification contract."""
    from modelFactory.oracle.security_continuity import path_crosses_known_discontinuity
    selected = selected.copy().reset_index(drop=True)
    bars = bars.copy()
    bars['date'] = pd.to_datetime(bars.date)
    if bars.duplicated('date').any():
        raise ValueError('Duplicate symbol price dates')
    grid = bars.set_index('date').reindex(sessions)
    raw = grid[['open', 'high', 'low', 'close', 'adj_close', 'volume', 'is_filled']].apply(
        pd.to_numeric, errors='coerce')
    adjusted = raw.adj_close.where(raw.adj_close.notna(), raw.close)
    factor = adjusted / raw.close
    close = adjusted.to_numpy(float)
    high, low = (raw.high * factor).to_numpy(float), (raw.low * factor).to_numpy(float)
    good = (np.isfinite(raw[['open', 'high', 'low', 'close']]).all(axis=1)
            & raw[['open', 'high', 'low', 'close']].gt(0).all(axis=1)
            & raw.high.ge(raw[['open', 'close', 'low']].max(axis=1))
            & raw.low.le(raw[['open', 'close', 'high']].min(axis=1))
            & np.isfinite(factor) & factor.gt(0)
            & raw.is_filled.eq(0) & raw.volume.gt(0)).to_numpy()
    pos = sessions.get_indexer(pd.to_datetime(selected.date))
    inside = (pos >= 0) & (pos + 21 < len(sessions))
    index = np.clip(pos, 0, len(sessions) - 22)
    flags = [[] for _ in range(len(selected))]
    def flag(mask, reason):
        for i in np.flatnonzero(mask):
            flags[i].append(reason)
    flag(~inside, 'OUTSIDE_CALENDAR')
    flag(~sliding_window_view(good, 21).all(axis=1)[index],
         'MISSING_FILLED_ZERO_VOLUME_OR_INVALID_OHLC')
    for column, reason in [('data_source', 'SOURCE_CHANGE_OR_UNKNOWN'),
                           ('data_adjustment', 'ADJUSTMENT_CHANGE_OR_UNKNOWN'),
                           ('instrument_id', 'IDENTITY_CHANGE_OR_UNKNOWN')]:
        values = grid[column]
        codes = pd.factorize(values)[0]
        windows = sliding_window_view(codes, 21)
        stable = ((windows == windows[:, :1]).all(axis=1) & (windows[:, 0] >= 0))
        if column != 'instrument_id':
            stable &= ~values.iloc[:len(stable)].isin(['UNKNOWN', '']).to_numpy()
        flag(~stable[index], reason)
    close_windows = sliding_window_view(close, 21)[index]
    with np.errstate(divide='ignore', invalid='ignore'):
        ratios = close_windows[:, 1:] / close_windows[:, :-1]
        terminal = close_windows[:, -1] / close_windows[:, 0] - 1
        up = np.maximum(0., sliding_window_view(high, 21)[index, 1:].max(axis=1) / close_windows[:, 0] - 1)
        down = np.maximum(0., 1 - sliding_window_view(low, 21)[index, 1:].min(axis=1) / close_windows[:, 0])
        cup = np.maximum(0., close_windows[:, 1:].max(axis=1) / close_windows[:, 0] - 1)
        cdown = np.maximum(0., 1 - close_windows[:, 1:].min(axis=1) / close_windows[:, 0])
        ranges = sliding_window_view(high / low, 21)[index]
    flag(((ratios >= 20) | (ratios <= .05)).any(axis=1), 'UNEXPLAINED_20X_PRICE_BREAK')
    flag(~selected.target_quality_valid.eq(1).to_numpy()
         | ~np.isfinite(selected.future_return.to_numpy(float)), 'UNQUALIFIED_ARCHIVED_LABEL')
    exits = sessions[index + 20]
    available = sessions[index + 21]
    flag((pd.to_datetime(selected.oracle_available_date).to_numpy() != available.to_numpy()) | ~inside,
         'LABEL_CALENDAR_MISMATCH')
    flag(~np.isclose(terminal, selected.future_return.to_numpy(float), rtol=1e-7, atol=1e-8),
         'ARCHIVED_RETURN_VS_CURRENT_BARS_MISMATCH')
    for i, row in selected[selected.symbol.isin(registry)].iterrows():
        if inside[i] and path_crosses_known_discontinuity(
                row.symbol, row.date, exits[i], registry):
            flags[i].append('KNOWN_IDENTITY_BREAK')
    valid = np.asarray([not value for value in flags])
    selected['path_qualified'] = valid
    selected['path_flags'] = ['|'.join(value) for value in flags]
    selected['exit_date'] = exits
    selected['available_date'] = available
    for name, values in [('up_excursion', up), ('down_excursion', down),
                         ('terminal_value', terminal), ('path_value', dominant(up, down)),
                         ('close_path_value', dominant(cup, cdown))]:
        selected[name] = np.where(valid, values, np.nan)
    selected['dominant_tie'] = valid & ~np.isfinite(dominant(up, down))
    selected['close_dominant_tie'] = valid & ~np.isfinite(dominant(cup, cdown))
    selected['intraday_range_review'] = (ranges >= 1.5).any(axis=1)
    selected['large_close_jump_review'] = (np.abs(ratios - 1) >= .5).any(axis=1)
    return selected


def classify_days(paths):
    """Use the full daily scored universe, not the selected Oracle/ATR pool.

    All three targets have the SAME qualified, unambiguous denominator. Rank ties
    share their maximum rank, exactly as in the existing Oracle label convention.
    Missing/tied paths remain in the output and coverage; they are never replaced.
    """
    result = paths.copy()
    valid = result.path_qualified & result.path_value.notna() & result.close_path_value.notna()
    result['paired_qualified'] = valid
    for target in TARGETS:
        value = result[f'{target}_value'].where(valid)
        fraction = value.groupby(result.date).rank(method='max', pct=True)
        result[f'{target}_decile'] = np.ceil(fraction * 10).clip(1, 10)
    result['daily_coverage'] = valid.groupby(result.date).transform('mean')
    result['daily_count'] = result.date.map(result.groupby('date').size())
    result['audit_eligible'] = valid & result.daily_coverage.ge(MIN_DAILY_COVERAGE) & result.daily_count.ge(20)
    return result


def auc_matrix(labels, values):
    """Tie-corrected Mann-Whitney AUC for many finite columns simultaneously."""
    y, x = np.asarray(labels, int), np.asarray(values, float)
    if x.ndim != 2 or len(y) != len(x) or not np.isin(y, [0, 1]).all():
        raise ValueError('Invalid AUC inputs')
    if not np.isfinite(x).all():
        raise ValueError('Nonfinite inputs; no test-period imputation')
    positive, negative = int(y.sum()), int((y == 0).sum())
    if min(positive, negative) < 5:
        return np.full(x.shape[1], np.nan)
    ranks = rankdata(x, axis=0, method='average')
    return (ranks[y == 1].sum(axis=0) - positive * (positive + 1) / 2) / (positive * negative)


def task_labels(frame, target, task):
    decile = frame[f'{target}_decile'].to_numpy()
    if task == 'D1_VS_D10':
        keep = np.isin(decile, [1, 10])
        return keep, (decile[keep] == 10).astype(int)
    if task in ('D10_VS_REST', 'D1_VS_REST'):
        return np.ones(len(frame), bool), (decile == (10 if task == 'D10_VS_REST' else 1)).astype(int)
    if task == 'SIGN':
        values = frame[f'{target}_value'].to_numpy()
        keep = values != 0
        return keep, (values[keep] > 0).astype(int)
    raise ValueError('Unknown task')


def frozen_orientation(daily):
    discovery = daily[(daily.date < DISCOVERY_CUTOFF) & (daily.available_date < DISCOVERY_CUTOFF)]
    means = discovery.groupby(['target', 'task', 'feature']).raw_auc.mean()
    return (means.ge(.5).astype(int) * 2 - 1).rename('orientation').reset_index()


def block_ci(values, seed=42, repeats=500):
    values = np.asarray(values, float)
    values = values[np.isfinite(values)]
    if not len(values):
        return [None, None]
    block = min(20, len(values))
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, len(values) - block + 1, size=(repeats, int(np.ceil(len(values) / block))))
    indices = (starts[:, :, None] + np.arange(block)).reshape(repeats, -1)[:, :len(values)]
    return np.quantile(values[indices].mean(axis=1), [.025, .975]).tolist()


def load_predictions():
    protocol = read(HISTORY / 'protocol.json')
    pieces = []
    fingerprints = []
    for fold in protocol['expected_fold_starts']:
        directory = HISTORY / 'corrected' / fold
        path = directory / 'predictions.parquet'
        sha = read(directory / 'done.json')[path.name]
        checked(path, sha)
        pieces.append(pd.read_parquet(path))
        fingerprints.append(dict(path=str(path), sha256=sha))
    historical = pd.concat(pieces, ignore_index=True)
    external_path = EXTERNAL / 'corrected-predictions.parquet'
    if 'COMPLETED' not in read(EXTERNAL / 'report.json')['status']:
        raise ValueError('External archive is incomplete')
    fingerprints.append(dict(path=str(external_path), sha256=digest(external_path)))
    external = pd.read_parquet(external_path)
    all_parts = []
    for source, root, frame in [('historical_oof', HISTORY, historical), ('external_frozen', EXTERNAL, external)]:
        frame = frame[frame.date.ge(pd.Timestamp('2020-01-01'))].copy()
        checked(root / 'labels.parquet', read(root / 'labels.json')['sha256'])
        labels = pd.read_parquet(root / 'labels.parquet', columns=['date', 'symbol', 'target_quality_valid',
                                                                  'oracle_available_date'])
        frame = frame.merge(labels, on=['date', 'symbol'], how='left', validate='one_to_one')
        selected = pool(frame).sort_values(['date', 'score', 'symbol'], ascending=[True, False, True])
        selected['oracle_pool_rank'] = selected.groupby('date').cumcount() + 1
        selected = selected[['date', 'symbol', 'oracle_pool_rank']]
        frame = frame.merge(selected, on=['date', 'symbol'], how='left', validate='one_to_one')
        frame['in_pool'] = frame.oracle_pool_rank.notna()
        frame['source'] = source
        all_parts.append(frame)
    result = pd.concat(all_parts, ignore_index=True).sort_values(['date', 'symbol']).reset_index(drop=True)
    if result.duplicated(['date', 'symbol']).any() or not np.isfinite(result[['score', 'atr20_pct']]).all().all():
        raise ValueError('Duplicate or nonfinite score/ATR archive')
    return result, fingerprints


def archive_paths(selected, output):
    from sqlalchemy import bindparam, event, text
    from database.connection import get_sqlalchemy_engine
    from modelFactory.oracle.build_labels import nyse_sessions
    from modelFactory.oracle.security_continuity import load_security_discontinuities
    sessions = nyse_sessions(selected.date.min().date(), (selected.date.max() + pd.Timedelta(days=90)).date())
    end = sessions[sessions.get_indexer([selected.date.max()])[0] + 20]
    registry = load_security_discontinuities()
    groups = {symbol: frame for symbol, frame in selected.groupby('symbol')}
    symbols = sorted(groups)
    total = int(np.ceil(len(symbols) / 25))
    engine = None
    query = text('''SELECT symbol,`date`,CAST(`open` AS DOUBLE) AS `open`,CAST(high AS DOUBLE) AS high,
        CAST(low AS DOUBLE) AS low,CAST(`close` AS DOUBLE) AS `close`,CAST(adj_close AS DOUBLE) AS adj_close,
        volume,is_filled,instrument_id,data_source,data_adjustment FROM stock_bars_daily
        WHERE symbol IN :symbols AND `date` BETWEEN :start AND :end ORDER BY symbol,`date`''').bindparams(
            bindparam('symbols', expanding=True))
    parts = []
    try:
        for chunk in range(total):
            names = symbols[chunk * 25:(chunk + 1) * 25]
            directory = output / f'prices-{chunk:03d}'
            directory.mkdir(exist_ok=True)
            atomic_json(output / 'progress.json', dict(status='RUNNING', phase='qualify_full_universe_paths',
                completed=chunk, total=total, symbols_done=chunk * 25, symbols_total=len(symbols)))
            marker = directory / 'done.json'
            if marker.exists():
                for filename, sha in read(marker).items():
                    checked(directory / filename, sha)
            else:
                if engine is None:
                    engine = get_sqlalchemy_engine(db_name='alpha_trade')
                    if engine.url.database != 'alpha_trade':
                        raise ValueError('US database required')
                    event.listen(engine, 'begin', lambda conn: conn.exec_driver_sql('SET TRANSACTION READ ONLY'))
                with engine.connect() as conn:
                    bars = pd.read_sql(query, conn, params=dict(symbols=names, start=selected.date.min().date(), end=end.date()))
                bars.to_parquet(directory / 'bars.parquet', index=False)
                price_groups = {symbol: frame for symbol, frame in bars.groupby('symbol')}
                paths = pd.concat([evaluate_paths(groups[name], price_groups.get(name, bars.iloc[:0]), sessions, registry)
                                   for name in names], ignore_index=True)
                paths.to_parquet(directory / 'paths.parquet', index=False)
                atomic_json(marker, {name: digest(directory / name) for name in ['bars.parquet', 'paths.parquet']})
            part = pd.read_parquet(directory / 'paths.parquet')
            parts.append(part)
            LOG.info('Full-universe paths %d/%d: %d rows, %d qualified', chunk + 1, total, len(part), part.path_qualified.sum())
    finally:
        if engine is not None:
            engine.dispose()
    return pd.concat(parts, ignore_index=True)


def load_features(selected, output, features):
    history_protocol = read(HISTORY / 'protocol.json')
    parts = []
    keys = selected[['date', 'symbol']]
    for source, root, pattern in [('historical_oof', Path(history_protocol['after']), 'features-*.parquet'),
                                   ('external_frozen', EXTERNAL, 'corrected-features-*.parquet')]:
        files = sorted(root.glob(pattern))
        for i, path in enumerate(files):
            if source == 'historical_oof':
                sha = read(path.with_suffix('.json'))['sha256']
            else:
                marker = root / path.name.replace('corrected-features-', 'features-').replace('.parquet', '.json')
                sha = read(marker)[path.name]
            checked(path, sha)
            atomic_json(output / 'progress.json', dict(status='RUNNING', phase='read_frozen_features',
                source=source, completed=i, total=len(files)))
            frame = pd.read_parquet(path, columns=['date', 'symbol', *features])
            parts.append(keys.merge(frame, on=['date', 'symbol'], how='inner', validate='one_to_one'))
            LOG.info('Features %s %d/%d', source, i + 1, len(files))
    data = pd.concat(parts, ignore_index=True)
    if data.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicated feature records')
    data = selected.merge(data, on=['date', 'symbol'], how='left', validate='one_to_one', indicator=True,
                          suffixes=('', '_feature'))
    if not data._merge.eq('both').all():
        raise ValueError('Missing frozen feature records')
    if 'atr20_pct_feature' in data:
        if not np.allclose(data.atr20_pct, data.atr20_pct_feature, rtol=0., atol=1e-14):
            raise ValueError('Frozen ATR differs between features and scores')
        data = data.drop(columns='atr20_pct_feature')
    if not np.isfinite(data[features + ['score']].to_numpy(float)).all():
        raise ValueError('Nonfinite archived features')
    return data.drop(columns='_merge')


def daily_statistics(data, features, output):
    parts = []
    for year, annual in data.groupby(data.date.dt.year):
        destination = output / f'daily-auc-{year}.parquet'
        marker = output / f'daily-auc-{year}.json'
        if marker.exists():
            checked(destination, read(marker)['sha256'])
            parts.append(pd.read_parquet(destination))
            continue
        rows = []
        for i, (day, frame) in enumerate(annual.groupby('date')):
            if i % 20 == 0:
                atomic_json(output / 'progress.json', dict(status='RUNNING', phase='daily_separability',
                    year=int(year), completed=i, total=annual.date.nunique()))
            matrix = frame[features].to_numpy(float)
            for target in TARGETS:
                for task in TASKS:
                    keep, labels = task_labels(frame, target, task)
                    aucs = auc_matrix(labels, matrix[keep])
                    rows.append(pd.DataFrame(dict(date=day, available_date=frame.available_date.max(),
                        target=target, task=task, feature=features, raw_auc=aucs,
                        observations=int(keep.sum()), positives=int(labels.sum()),
                        negatives=int((labels == 0).sum()))))
        daily = pd.concat(rows, ignore_index=True)
        daily.to_parquet(destination, index=False)
        atomic_json(marker, dict(sha256=digest(destination)))
        parts.append(daily)
        LOG.info('Univariate feature audit %d complete: %d days', year, annual.date.nunique())
    return pd.concat(parts, ignore_index=True)


def annual_summary(daily, orientation):
    daily = daily.merge(orientation, on=['target', 'task', 'feature'], validate='many_to_one')
    daily['auc'] = np.where(daily.orientation == 1, daily.raw_auc, 1 - daily.raw_auc)
    daily['year'] = daily.date.dt.year
    rows = []
    for (year, target, task, feature), frame in daily.groupby(['year', 'target', 'task', 'feature']):
        frame = frame.sort_values('date')
        valid = frame.dropna(subset=['auc'])
        if valid.empty:
            continue
        low, high = block_ci(valid.auc)
        rows.append(dict(year=int(year), target=target, task=task, feature=feature,
            orientation=int(frame.orientation.iloc[0]), days=len(valid),
            mean_daily_auc=float(valid.auc.mean()), mean_raw_daily_auc=float(valid.raw_auc.mean()),
            fraction_days_above_chance=float(valid.auc.gt(.5).astype(float).mean()),
            ci_low=low, ci_high=high,
            nonoverlap21_auc=float(valid.auc.iloc[::21].mean()), nonoverlap21_dates=len(valid.iloc[::21]),
            mean_observations=float(valid.observations.mean())))
    return pd.DataFrame(rows), daily


def label_summary(full):
    rows = []
    for scope, mask in [('FULL_SCORED_UNIVERSE', np.ones(len(full), bool)),
                         ('ORACLE_ATR_POOL', full.in_pool), ('ORACLE_TOP10_IN_POOL', full.oracle_pool_rank.le(10))]:
        for year, group in full.loc[mask].groupby(full.loc[mask].date.dt.year):
            good = group[group.audit_eligible]
            rows.append(dict(scope=scope, year=int(year), selected=len(group), evaluated=len(good),
                coverage=len(good) / len(group), dates=group.date.nunique(), usable_dates=good.date.nunique(),
                sign_changed=float((np.sign(good.path_value) != np.sign(good.terminal_value)).astype(float).mean()),
                decile_changed=float(good.path_decile.ne(good.terminal_decile).astype(float).mean()),
                old_d1_retained=float(good.loc[good.terminal_decile.eq(1), 'path_decile'].eq(1).astype(float).mean()),
                old_d10_retained=float(good.loc[good.terminal_decile.eq(10), 'path_decile'].eq(10).astype(float).mean()),
                path_d1_rate=float(good.path_decile.eq(1).astype(float).mean()),
                path_d10_rate=float(good.path_decile.eq(10).astype(float).mean()),
                path_positive_rate=float(good.path_value.gt(0).astype(float).mean()),
                path_vs_close_sign_changed=float((np.sign(good.path_value) != np.sign(good.close_path_value)).astype(float).mean()),
                archived_terminal_decile_changed=float(good.oracle_decile.ne(good.terminal_decile).astype(float).mean()),
                range_review=int(good.intraday_range_review.sum())))
    return pd.DataFrame(rows)


def screen_leads(annual, daily, features):
    """Descriptive screening, not significance or authorization to trade."""
    discovery = daily[(daily.date < DISCOVERY_CUTOFF) & (daily.available_date < DISCOVERY_CUTOFF)
                      & daily.target.eq('path') & daily.task.eq('D1_VS_D10')]
    scores = discovery.groupby('feature').auc.mean().sort_values(ascending=False)
    # Non-PIT selector data and aliases cannot create a selected research lead.
    top = [feature for feature in scores.index if feature in features
           and feature not in ('selector_short_score', 'is_filled')][:10]
    results = []
    for feature in top:
        records = annual[(annual.target == 'path') & (annual.task == 'D1_VS_D10') & (annual.feature == feature)]
        confirmations = records[records.year.isin([2023, 2024, 2025, 2026])]
        enough = set(confirmations.year) == {2023, 2024, 2025, 2026}
        passed = enough and bool((confirmations.mean_daily_auc.ge(.53)
            & confirmations.ci_low.gt(.5) & confirmations.days.ge(60)).all())
        results.append(dict(feature=feature, discovery_auc=float(scores[feature]),
            screen_pass=passed, confirmation=confirmations.to_dict('records')))
    return results


def run(args):
    from modelFactory.oracle.security_continuity import DEFAULT_REGISTRY_PATH
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    predictions, prediction_hashes = load_predictions()
    original_features = read(HISTORY / 'protocol.json')['features']
    features = [name for name in original_features if not name.endswith('_xs_rank')]
    aliases = {name: name[:-len('_xs_rank')] for name in original_features if name.endswith('_xs_rank')}
    if any(raw not in features for raw in aliases.values()):
        raise ValueError('Unresolved cross-sectional alias')
    protocol = dict(experiment='P-PATH-0', code_sha256=digest(__file__),
        input_protocol_hashes=[digest(root / 'protocol.json') for root in (HISTORY, EXTERNAL)],
        prediction_hashes=prediction_hashes, registry_sha256=digest(DEFAULT_REGISTRY_PATH),
        universe='Frozen cleaned tradable universe from corrected archives; full scored universe each date',
        universe_sha256=read(HISTORY / 'protocol.json')['universe_sha256'],
        anchor='adjusted signal-day close; high/low adjusted with adj_close/close',
        horizon='Exactly J+1..J+20 NYSE sessions; J and J+21 excluded',
        target='max(upward excursion, absolute downward excursion), signed by dominant side',
        tie='Absolute difference <=1e-12 excluded as ambiguous',
        label_denominator='Same qualified unambiguous FULL daily scored universe for all targets; rank(max,pct), ceil*10',
        minimum_daily_coverage=MIN_DAILY_COVERAGE, minimum_daily_universe=20,
        signal_start=str(predictions.date.min()), signal_end=str(predictions.date.max()),
        selection='Oracle TOP20 intersect ATR TOP20 before any future qualification; no replacements',
        tasks=TASKS, targets=TARGETS, features=features + ['score'], xs_aliases=aliases,
        aliases_contract='Daily AUC is invariant to monotonic cross-sectional rank; aliases copy raw AUC, no additional information',
        discovery='2020-2022, only labels available strictly before 2023-01-03; one fixed orientation per feature/target/task',
        confirmation='2023, 2024 through July 9, 2025, 2026 through September 3; 2026 not virgin',
        metric='Mean within-date AUC, equal weight dates, minimum 5 observations per class',
        intervals='Descriptive moving-block 20-session bootstrap, 500 repeats, seed42; NOT multiplicity-adjusted significance',
        nonoverlap_sensitivity='Every 21st eligible signal date per year, descriptive only',
        range_sensitivity='Exclude high/low>=1.5 paths; rebuild labels on same revised full paired denominator',
        screen='Ten distinct raw features chosen ONLY by discovery D1/D10 path AUC; AUC>=.53 and CI_low>.50 in each 2023/24/25/26, >=60 dates',
        feature_provenance='Archived causal rolling price/volume/benchmark features; selector_short_score retained for diagnosis but not qualified PIT',
        excluded_families=['News/sentiment, VIX/VXN/VIX3M/MOVE, fundamentals/consensus absent from frozen archives; not assumed tested'],
        training=False, sql_writes=False, pnl=False, serving_modified=False,
        limitations=['Current universe and revised/adjusted prices not fully PIT certified; survivorship',
            'Historical OOF ends 2024-07-09; no fabricated late-2024 scores',
            'Conditional pool audit, not study of all possible information',
            'Dominant future excursion is not executable profit or a known exit time',
            'Multiple features/related labels and overlapping horizons: exploratory screen, no promotion',
            'Direction-only sign ignores loss timing and simultaneous long/short barriers',
            'Availability dates apply to outcomes; adjusted source vintages not independently certified'])
    if (output / 'protocol.json').exists() and read(output / 'protocol.json') != read_json_compatible(protocol):
        raise ValueError('Resume protocol mismatch; use a new output directory')
    atomic_json(output / 'protocol.json', protocol)
    predictions.to_parquet(output / 'frozen_predictions.parquet', index=False)
    full = classify_days(archive_paths(predictions, output))
    full.to_parquet(output / 'full_universe_labels.parquet', index=False)
    annual_labels = label_summary(full)
    annual_labels.to_parquet(output / 'label_comparison_annual.parquet', index=False)
    keys = full[full.in_pool & full.audit_eligible].copy()
    feature_data = load_features(keys, output, features)
    feature_data.to_parquet(output / 'audit_inputs.parquet', index=False)
    daily = daily_statistics(feature_data, features + ['score'], output)
    orientation = frozen_orientation(daily)
    annual, oriented_daily = annual_summary(daily, orientation)
    orientation.to_parquet(output / 'frozen_orientation.parquet', index=False)
    # XS ranks are redundant for single-feature daily AUC: exact monotone aliases.
    alias_rows = [annual[annual.feature.eq(raw)].assign(feature=alias, alias_of=raw)
                  for alias, raw in aliases.items()]
    annual['alias_of'] = None
    all_annual = pd.concat([annual, *alias_rows], ignore_index=True)
    all_annual.to_parquet(output / 'feature_auc_annual.parquet', index=False)
    oriented_daily.to_parquet(output / 'feature_auc_daily.parquet', index=False)
    leads = screen_leads(annual, oriented_daily, features + ['score'])
    transitions = full[full.audit_eligible & full.in_pool].groupby(
        [full.date.dt.year, 'terminal_decile', 'path_decile']).size().rename('observations').reset_index()
    transitions.to_parquet(output / 'decile_transitions.parquet', index=False)
    # Range sensitivity relabels the full universe, never just the selected pool.
    filtered = full.copy()
    filtered['path_qualified'] &= ~filtered.intraday_range_review
    sensitivity_labels = classify_days(filtered)
    sensitivity_input = sensitivity_labels[sensitivity_labels.in_pool & sensitivity_labels.audit_eligible].copy()
    observed_features = feature_data[['date', 'symbol', *features, 'score']]
    sensitivity_input = sensitivity_input.drop(columns=['score', 'atr20_pct']).merge(
        observed_features, on=['date', 'symbol'], how='inner', validate='one_to_one')
    sensitivity_output = output / 'range_sensitivity'
    sensitivity_output.mkdir(exist_ok=True)
    sensitivity_daily = daily_statistics(sensitivity_input, features + ['score'], sensitivity_output)
    sensitivity_annual, _ = annual_summary(sensitivity_daily, orientation)
    sensitivity_annual.to_parquet(output / 'feature_auc_range_sensitivity.parquet', index=False)
    label_summary(sensitivity_labels).to_parquet(output / 'label_comparison_range_sensitivity.parquet', index=False)
    reason_counts = full.loc[~full.path_qualified, 'path_flags'].str.split('|').explode().value_counts().to_dict()
    manifest = {path.name: digest(path) for path in output.glob('*.parquet')}
    atomic_json(output / 'outputs.json', manifest)
    report = dict(status='COMPLETED_READ_ONLY_DOMINANT_PATH_AUDIT', experiment='P-PATH-0',
        rows=len(full), symbols=int(full.symbol.nunique()), signal_dates=int(full.date.nunique()),
        qualified_paths=int(full.path_qualified.sum()), paired_qualified=int(full.paired_qualified.sum()),
        dominant_ties=int(full.dominant_tie.sum()), close_dominant_ties=int(full.close_dominant_tie.sum()),
        reserved_reasons=reason_counts, feature_count=len(features) + 1 + len(aliases),
        unique_numeric_features=len(features) + 1, monotone_aliases=len(aliases),
        pool_rows=len(feature_data), pool_dates=int(feature_data.date.nunique()),
        label_comparison=annual_labels.to_dict('records'), discovery_selected_leads=leads,
        verdict='POSSIBLE_UNIVARIATE_LEAD_REQUIRES_NEW_CONFIRMATION' if any(x['screen_pass'] for x in leads)
                else 'NO_STABLE_UNIVARIATE_DOMINANT_PATH_SEPARATION',
        training=False, sql_writes=False, pnl=False, limitations=protocol['limitations'])
    atomic_json(output / 'report.json', report)
    atomic_json(output / 'progress.json', dict(status='COMPLETED', phase='report',
        rows=len(full), pool_rows=len(feature_data), verdict=report['verdict']))
    LOG.info('P-PATH-0 complete %s verdict=%s', output, report['verdict'])


def read_json_compatible(value):
    import json
    return json.loads(json.dumps(value, default=str))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        run(args)
    except Exception as exc:
        if args.output.is_dir():
            atomic_json(args.output / 'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)))
        raise


if __name__ == '__main__':
    main()
