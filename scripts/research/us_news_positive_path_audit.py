"""Frozen positive-news path association, offline; no SQL, APIs, fit or PnL."""
import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from common.universe_files import load_universe_file_symbols
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.security_continuity import (
    DEFAULT_REGISTRY_PATH, load_security_discontinuities,
)
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

NEWS = Path('artifacts/research/us_news_same_day/audit-202510-20261011-v1')
PRICES = Path('artifacts/research/us_oracle_tp20_sl10_new/20261012-v6/prices.parquet')
UNIVERSE = Path('config/univers/univers_filtred_tradable.txt')
LOG = logging.getLogger(__name__)
LEVELS = (0, 5, 10, 20)
VIEWS = (1, 2, 3, 'lag_1', 'lag_2')


def aggregate_news(news, calendar):
    """No maximum-score shortcut: every successfully scored article must pass."""
    news = news.copy()
    published = pd.to_datetime(news.published_at_utc, utc=True)
    news['date'] = published.dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    # Keep date-only ambiguity visible; never synthesize an availability time.
    news['ambiguous_hour'] = published.dt.hour.eq(0) & published.dt.minute.eq(0) & published.dt.second.eq(0)
    news['positive_score'] = pd.to_numeric(news.positive_score, errors='coerce')
    news['pass_score'] = news.positive_score.between(0, 1) & news.positive_score.gt(.9)
    news['available_at'] = pd.to_datetime(news.available_at, utc=True)
    news['has_availability'] = news.available_at.notna()
    groups = news.groupby(['date', 'symbol'], as_index=False).agg(
        articles=('article_id', 'size'), strong=('pass_score', 'all'),
        last_available=('available_at', 'max'), known_available=('has_availability', 'all'),
        ambiguous_hour=('ambiguous_hour', 'any'))
    result = []
    for symbol, part in groups.groupby('symbol'):
        frame = part.set_index('date').reindex(calendar)
        frame['symbol'] = symbol
        articles = frame.articles.fillna(0)
        available = pd.to_datetime(frame.last_available, utc=True)
        ns = available.astype('int64').where(available.notna(), np.nan)
        for days in (1, 2, 3):
            frame[f'news_days_{days}'] = articles.gt(0).astype(int).rolling(days).sum().eq(days)
            frame[f'strong_{days}'] = frame.strong.eq(True).astype(int).rolling(days).sum().eq(days)
            frame[f'known_{days}'] = frame.known_available.eq(True).astype(int).rolling(days).sum().eq(days)
            frame[f'ambiguous_{days}'] = frame.ambiguous_hour.eq(True).astype(int).rolling(days).sum().gt(0)
            frame[f'last_available_{days}'] = pd.to_datetime(ns.rolling(days).max(), utc=True)
        # Separate lag-only tests: do not require news on J for a J-1/J-2 signal.
        for lag in (1, 2):
            key = f'lag_{lag}'
            frame[f'news_days_{key}'] = articles.gt(0).shift(lag, fill_value=False)
            frame[f'strong_{key}'] = frame.strong.eq(True).shift(lag, fill_value=False)
            frame[f'known_{key}'] = frame.known_available.eq(True).shift(lag, fill_value=False)
            frame[f'ambiguous_{key}'] = frame.ambiguous_hour.eq(True).shift(lag, fill_value=False)
            frame[f'last_available_{key}'] = available.shift(lag)
        result.append(frame.drop(columns=['articles', 'strong', 'last_available',
                                         'known_available', 'ambiguous_hour']).reset_index(names='date'))
    return pd.concat(result, ignore_index=True), dict(
        article_symbol_rows=len(news), non_session_rows=int((~news.date.isin(calendar)).sum()),
        ambiguous_publication_hour_rows=int(news.ambiguous_hour.sum()))


def price_paths(frame, calendar, registry=()):
    """H0..H20 = 21 sessions from J open; H1..H20 = 20 from next open."""
    frame = frame.set_index('date').reindex(calendar)
    n = len(frame)
    prices = frame[['open', 'high', 'low', 'close', 'volume']].apply(pd.to_numeric, errors='coerce')
    o, h, l, c, v = [prices[x].to_numpy(float) for x in prices]
    ids = frame.instrument_id.astype('string')
    good = (np.isfinite(prices).all(axis=1).to_numpy() & (o > 0) & (l > 0) & (v > 0)
            & (h >= np.maximum(o, c)) & (l <= np.minimum(o, c)) & (h >= l)
            & frame.is_filled.eq(0).fillna(False).to_numpy(bool)
            & frame.data_adjustment.eq('split').fillna(False).to_numpy(bool)
            & ids.notna().to_numpy())
    # Covariates strictly before J: do not match on the response to J news.
    prior_close = pd.Series(c).where(good)
    returns = prior_close.pct_change(fill_method=None)
    output = pd.DataFrame({'date': calendar,
        'prior_vol60': returns.rolling(60, min_periods=60).std().shift(1).to_numpy(),
        'prior_momentum20': (prior_close / prior_close.shift(20)-1).shift(1).to_numpy()})
    for name, offset, length in (('h0_h20', 0, 21), ('h1_h20', 1, 20)):
        maximum, minimum, terminal = [np.full(n, np.nan) for _ in range(3)]
        qualified = np.zeros(n, dtype=bool)
        mature = np.arange(n)+20 < n
        count = max(0, n-20)
        if count:
            slide = np.lib.stride_tricks.sliding_window_view
            codes = pd.factorize(ids)[0]
            identity = slide(codes[offset:], length)
            valid = slide(good[offset:], length).all(axis=1) & (identity == identity[:, :1]).all(axis=1)
            for event in registry:
                valid &= ~((calendar[offset:offset+count] <= event.last_predecessor_date)
                           & (calendar[20:20+count] >= event.first_successor_date))
            anchors = o[offset:offset+count]
            with np.errstate(divide='ignore', invalid='ignore'):
                up = (slide(h[offset:], length).max(axis=1)/anchors-1)*100
                down = (slide(l[offset:], length).min(axis=1)/anchors-1)*100
                close = (c[20:20+count]/anchors-1)*100
            maximum[:count] = np.where(valid, up, np.nan)
            minimum[:count] = np.where(valid, down, np.nan)
            terminal[:count] = np.where(valid, close, np.nan)
            qualified[:count] = valid
        output[f'{name}_qualified'] = qualified
        output[f'{name}_mature'] = mature
        output[f'{name}_max_up_pct'] = maximum
        output[f'{name}_min_down_pct'] = minimum
        output[f'{name}_terminal_pct'] = terminal
    return output


def metrics(frame, prefix):
    values = frame[f'{prefix}_max_up_pct'].dropna()
    terminal = frame.loc[values.index, f'{prefix}_terminal_pct']
    return dict(n=len(values), symbols=int(frame.loc[values.index, 'symbol'].nunique()),
        dates=int(frame.loc[values.index, 'date'].nunique()),
        mean_max_up_pct=float(values.mean()) if len(values) else None,
        median_max_up_pct=float(values.median()) if len(values) else None,
        median_max_down_pct=float(frame.loc[values.index, f'{prefix}_min_down_pct'].median()) if len(values) else None,
        terminal_positive_pct=float(terminal.gt(0).mean()*100) if len(values) else None,
        up20_but_terminal_nonpositive_pct=float((values.ge(20)&terminal.le(0)).mean()*100) if len(values) else None,
        reached_pct={str(level):float((values.gt(0) if level == 0 else values.ge(level)).mean()*100)
                     if len(values) else None for level in LEVELS})


def matched_comparison(frame, signal, prefix, calendar):
    """Matched non-strong news controls; equal-date/block uncertainty is descriptive."""
    eligible = frame[f'{prefix}_qualified'] & frame[f'news_days_{signal}']
    good = frame.loc[eligible].copy()
    strong = good[f'strong_{signal}']
    rows = []
    keys = ['date', 'vol_bin', 'momentum_bin']
    controls = good.loc[~strong].dropna(subset=keys)
    treatments = good.loc[strong].dropna(subset=keys)
    control = controls.assign(hit20=controls[f'{prefix}_max_up_pct'].ge(20).astype(float)).groupby(keys).agg(
        control_n=('hit20','size'), control_hit20=('hit20','mean'))
    joined = treatments.join(control, on=keys)
    joined = joined[joined.control_n.ge(5)].copy()
    if len(joined):
        joined['hit20'] = joined[f'{prefix}_max_up_pct'].ge(20).astype(float)
        joined['delta_pp'] = (joined.hit20-joined.control_hit20)*100
        daily = joined.groupby('date').delta_pp.mean()
        order = pd.Series(np.arange(len(calendar)), index=calendar)
        block = daily.groupby(order.reindex(daily.index).to_numpy()//21).mean()
        interval = None
        if len(block) >= 8:
            rng = np.random.default_rng(20261014)
            draws = rng.choice(block.to_numpy(), (999, len(block)), replace=True).mean(axis=1)
            interval = [float(x) for x in np.quantile(draws, [.025,.975])]
        rows = dict(matched_n=len(joined), total_strong_qualified=len(treatments),
            matched_dates=len(daily), blocks=len(block),
            treatment_hit20_pct=float(joined.hit20.mean()*100),
            control_hit20_pct=float(joined.control_hit20.mean()*100),
            equal_day_delta_pp=float(daily.mean()), equal_block_delta_pp=float(block.mean()),
            descriptive_block_ci95_pp=interval)
    return rows or dict(matched_n=0, total_strong_qualified=len(treatments))


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output/'protocol.json').exists():
        raise ValueError('Use a new output directory; immutable protocol')
    calendar = pd.DatetimeIndex(nyse_sessions(pd.Timestamp('2023-01-03'), pd.Timestamp('2026-10-09')))
    symbols = load_universe_file_symbols('universe-file:univers_filtred_tradable.txt')
    source_report = json.loads((NEWS/'report.json').read_text(encoding='utf-8'))
    files = sorted(NEWS.glob('news-*.parquet'))
    hashes = {str(p):digest(p) for p in [*files, PRICES, UNIVERSE, DEFAULT_REGISTRY_PATH, Path(__file__)]}
    for p in files:
        if hashes[str(p)] != source_report['source_files'][p.name]:
            raise ValueError(f'News archive hash mismatch: {p}')
    source_symbols = set(load_universe_file_symbols('universe-file:config/univers_batch/univers_filtred_tradable.txt'))
    if set(symbols) != source_symbols or digest(Path('config/univers_batch/univers_filtred_tradable.txt')) != source_report['protocol']['universe_sha256']:
        raise ValueError('News cache universe coverage not proven')
    protocol = dict(universe=str(UNIVERSE), symbols=len(symbols), threshold=.9,
        rule='All successfully scored articles >0.9 on every required NYSE session; >=1 article per session',
        windows={'1':'J','2':'J-1/J','3':'J-2/J'}, lags='NYSE sessions, not calendar days',
        separate_lags={'lag_1':'J-1 alone; no news requirement on J', 'lag_2':'J-2 alone; no news requirement on J'},
        years=[2025,2026], h0='J open -> highs/lows J through J+20 inclusive (21 sessions)',
        h1='J+1 open -> highs/lows J+1 through J+20 (20 sessions)',
        outcomes=list(LEVELS), strict_availability='All current updated_at values before J+1 open; diagnostic, not immutable PIT proof',
        match='J-1 vol60 quintile x momentum20 quintile x date, >=5 non-strong news controls',
        sources=hashes, sql_writes=False, sql_reads=False, api_calls=0, fit=False, pnl=False,
        caveats=['Current universe survivorship; only scored articles, not all published news',
            'Daily H0 high may precede publication; current scores/updates not historical immutable PIT',
            'Excursion is not achievable profit, not TP before SL; overlapping paths and no holdout',
            'Matching not causal; sparse J-1/J-2 cohorts may be inconclusive'])
    atomic_json(output/'protocol.json', protocol)
    news = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    news = news[news.symbol.isin(symbols)].sort_values('available_at').drop_duplicates(['symbol','dedupe_hash','published_at_utc'])
    aggregated, counts = aggregate_news(news, calendar)
    prices = pd.read_parquet(PRICES)
    prices.date = pd.to_datetime(prices.date)
    if prices.duplicated(['symbol','date']).any():
        raise ValueError('Duplicate bar keys')
    registry = load_security_discontinuities()
    parts = []
    for index, (symbol, frame) in enumerate(prices[prices.symbol.isin(symbols)].groupby('symbol')):
        paths = price_paths(frame, calendar, registry.get(symbol, ()))
        paths['symbol'] = symbol
        parts.append(paths[paths.date.between('2025-01-01','2026-10-09')])
        if index % 100 == 0:
            atomic_json(output/'progress.json', dict(status='RUNNING', completed_symbols=index, total_symbols=len(symbols)))
            LOG.info('Price paths %s/%s', index, len(symbols))
    panel = pd.concat(parts, ignore_index=True).merge(aggregated, on=['date','symbol'], how='left', validate='one_to_one')
    # J-only cross-sectional bins computed without any future-path filtering.
    for source, target in [('prior_vol60','vol_bin'),('prior_momentum20','momentum_bin')]:
        ranks = panel.groupby('date')[source].rank(pct=True)
        panel[target] = np.ceil(ranks*5).clip(1,5)
    from common.market_calendar import get_market_calendar
    sessions = get_market_calendar('US_EQ', allow_us_weekday_fallback=False).sessions(
        calendar.min().date(), pd.Timestamp('2026-10-12').date())
    opens = pd.Series({pd.Timestamp(s.session_date):pd.Timestamp(s.open_at_utc) for s in sessions if s.is_open}).sort_index()
    next_open = opens.shift(-1)
    for days in VIEWS:
        for column in (f'news_days_{days}',f'strong_{days}',f'known_{days}',f'ambiguous_{days}'):
            panel[column] = panel[column].eq(True)
        panel[f'available_{days}'] = (panel[f'known_{days}'] & ~panel[f'ambiguous_{days}'] &
            pd.to_datetime(panel[f'last_available_{days}'],utc=True).lt(pd.to_datetime(panel.date.map(next_open),utc=True)))
    panel.to_parquet(output/'observations.parquet', index=False)
    report = dict(protocol=protocol, news=counts, years={}, monthly={})
    for year, part in panel.groupby(panel.date.dt.year):
        report['years'][str(year)] = {}
        for prefix in ('h0_h20','h1_h20'):
            item = {'full_universe':metrics(part,prefix), 'windows':{}}
            for days in VIEWS:
                strong = part[part[f'strong_{days}']]
                item['windows'][str(days)] = dict(selected=len(strong),
                    immature=int((~strong[f'{prefix}_mature']).sum()),
                    mature_unqualified=int((strong[f'{prefix}_mature'] & ~strong[f'{prefix}_qualified']).sum()),
                    strong=metrics(strong,prefix),
                    news_control=metrics(part[part[f'news_days_{days}'] & ~part[f'strong_{days}']],prefix),
                    availability_diagnostic=metrics(strong[strong[f'available_{days}']],prefix),
                    matched=matched_comparison(part,days,prefix,calendar))
            report['years'][str(year)][prefix] = item
    for month, part in panel.groupby(panel.date.dt.strftime('%Y-%m')):
        report['monthly'][month] = {str(days):metrics(part[part[f'strong_{days}']], 'h1_h20') for days in VIEWS}
    for p, expected in hashes.items():
        if digest(Path(p)) != expected:
            raise RuntimeError(f'Source changed during audit: {p}')
    report['status'] = 'COMPLETED_RETROSPECTIVE_ASSOCIATION_NOT_PREDICTIVE_VALIDATION'
    atomic_json(output/'report.json', report)
    atomic_json(output/'progress.json', dict(status='COMPLETED', report=str(output/'report.json')))
    LOG.info('Completed %s', output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        run(args.output)
    except Exception as exc:
        atomic_json(Path(args.output)/'progress.json', dict(status='FAILED', error=str(exc)))
        raise
