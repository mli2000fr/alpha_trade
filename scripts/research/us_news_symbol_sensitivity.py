"""Offline symbol/tone sensitivity audit; optional bounded read-only metadata export.

No provider, LLM, training, SQL mutation or economic backtest.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from common.market_calendar import get_market_calendar
from modelFactory.oracle.security_continuity import (
    DEFAULT_REGISTRY_PATH, load_security_discontinuities,
)

SOURCE = Path('artifacts/research/us_news_same_day/audit-202510-20261011-v1')
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
PROTOCOL = Path('doc/ml/news_sensibilite_par_titre_protocole_20261022.md')
DEFAULT_OUTPUT = Path('artifacts/research/us_news_symbol_sensitivity/20261022-v1')
HORIZONS = (1, 5, 10, 20)
GATES = {1: (30, 10, 6), 5: (20, 8, 6), 10: (12, 4, 5), 20: (8, 3, 4)}
TONES = ('positive_only', 'negative_only')
PATTERNS = {
    'EARNINGS_GUIDANCE_SCREEN': r'\b(earnings|quarterly results|financial results|guidance|profit forecast)\b',
    'ANALYST_ACTION_SCREEN': r'\b(upgrade[sd]?|downgrade[sd]?|price target|analyst rating|initiates coverage)\b',
    'FINANCING_SCREEN': r'\b(public offering|share offering|stock offering|private placement|convertible notes|equity offering)\b',
    'MERGER_SCREEN': r'\b(merger|acquisition|acquire[sd]?|takeover|buyout)\b',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False,
                  default=lambda x: x.item() if isinstance(x, np.generic) else str(x))


def screen(headline):
    hits = [name for name, regex in PATTERNS.items() if re.search(regex, str(headline or ''), re.I)]
    return hits[0] if len(hits) == 1 else 'MULTIPLE_SCREEN' if hits else 'OTHER_UNCLASSIFIED'


def prepare(output):
    if output.exists():
        raise FileExistsError('New immutable experiment directory required')
    paths = sorted(SOURCE.glob('news-*.parquet')) + [SOURCE/'bars.parquet', UNIVERSE,
                                                    DEFAULT_REGISTRY_PATH, PROTOCOL, Path(__file__)]
    output.mkdir(parents=True)
    save(output/'protocol.json', dict(version='NEWS_SYMBOL_SENSITIVITY_V1',
        created_at_utc=datetime.now(timezone.utc).isoformat(), primary_horizon=5,
        train_year=2025, test_year=2026, publication_end_exclusive='2026-10-01',
        source_hashes={str(p): digest(p) for p in paths},
        sql_writes=False, provider_calls=0, llm_calls=0, training=False, economic_backtest=False,
        prospective_validation=False, gates=GATES))


def check(output):
    protocol = json.loads((output/'protocol.json').read_text(encoding='utf-8'))
    for name, expected in protocol['source_hashes'].items():
        if digest(name) != expected:
            raise ValueError(f'Frozen input changed: {name}')
    return protocol


def metadata(output):
    """Read existing local tables only; texts are retrospective routing, not evidence."""
    check(output)
    target = output/'metadata'
    if target.exists():
        raise FileExistsError('Metadata already exported; no overwrite')
    target.mkdir()
    from sqlalchemy import text
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()
    counts = {}
    try:
        with engine.connect() as conn:
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            sectors = pd.read_sql(text('SELECT symbol,sector,company_name,last_updated FROM stock_metadata'), conn)
            sectors.to_parquet(target/'sectors-current.parquet', index=False)
            for month in pd.date_range('2025-01-01', '2026-09-01', freq='MS'):
                end = month + pd.offsets.MonthBegin(1)
                frame = pd.read_sql(text('''SELECT article_id,headline,dedupe_hash,published_at_utc,
                    ingestion_source,created_at,updated_at FROM news_raw
                    FORCE INDEX(idx_news_raw_published_utc)
                    WHERE published_at_utc>=:start AND published_at_utc<:end
                    ORDER BY published_at_utc,article_id LIMIT 100001'''), conn,
                    params=dict(start=month.to_pydatetime(), end=end.to_pydatetime()))
                if len(frame) > 100000:
                    raise ValueError('Metadata truncated; partition before continuing')
                frame.to_parquet(target/f'headlines-{month:%Y-%m}.parquet', index=False)
                counts[f'{month:%Y-%m}'] = len(frame)
                print('metadata', month.strftime('%Y-%m'), len(frame), flush=True)
            conn.rollback()
    finally:
        engine.dispose()
    save(target/'manifest.json', dict(counts=counts, snapshot_utc=datetime.now(timezone.utc).isoformat(),
        qualified_event_types=False, sectors_pit=False,
        files={p.name: digest(p) for p in target.glob('*.parquet')}))


def schedule_frame():
    calendar = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    sessions = [s for s in calendar.sessions(date(2024, 12, 27), date(2026, 11, 15)) if s.is_open]
    return pd.DataFrame(dict(day=pd.to_datetime([s.session_date for s in sessions]),
        open_at=pd.to_datetime([s.open_at_utc for s in sessions], utc=True),
        close_at=pd.to_datetime([s.close_at_utc for s in sessions], utc=True)))


def make_events(news, schedule, headlines=None):
    n = news.copy()
    n['published'] = pd.to_datetime(n.published_at_utc, utc=True)
    n['available'] = pd.to_datetime(n.available_at, utc=True)
    n = n[n.published.ge('2025-01-01') & n.published.lt('2026-10-01')].copy()
    for col in ('positive_score', 'negative_score'):
        n[col] = pd.to_numeric(n[col], errors='coerce')
    invalid = ~n.positive_score.between(0, 1) | ~n.negative_score.between(0, 1) | n.published.isna()
    ambiguous = n.published.eq(n.published.dt.normalize())
    stats = dict(input_rows=len(n), invalid_scores_or_time=int(invalid.sum()),
                 ambiguous_midnight=int((ambiguous & ~invalid).sum()))
    n = n[~invalid & ~ambiguous].sort_values(['published', 'article_id', 'symbol']).copy()
    # Missing hash is NOT a shared content hash.
    n['content_key'] = n.dedupe_hash.fillna('').astype(str)
    missing = n.content_key.str.strip().eq('')
    n.loc[missing, 'content_key'] = 'article:' + n.loc[missing, 'article_id'].astype(str)
    before = len(n)
    n = n.drop_duplicates(['symbol', 'content_key'], keep='first').copy()
    stats['duplicate_symbol_contents'] = before - len(n)
    n['family'] = 'MISSING_ARCHIVED_TEXT'
    if headlines is not None:
        head = headlines.drop_duplicates('article_id').copy()
        head['family_current'] = head.headline.map(screen)
        n = n.merge(head[['article_id', 'dedupe_hash', 'family_current']], on='article_id',
                    how='left', suffixes=('', '_current'), validate='many_to_one')
        same = n.dedupe_hash.notna() & n.dedupe_hash.eq(n.dedupe_hash_current)
        n.loc[same, 'family'] = n.loc[same, 'family_current']
        stats['headline_hash_matched_rows'] = int(same.sum())
    # Search exact official opens, not fixed UTC/Paris times; leave five minutes.
    times = schedule.open_at.astype('int64').to_numpy()
    ready = n.published.astype('int64').to_numpy() + 5*60*10**9
    index = np.searchsorted(times, ready, side='right')
    good = index < len(schedule)
    n = n.loc[good].copy()
    n['entry_idx'] = index[good]
    n['positive'] = n.positive_score.gt(.9)
    n['negative'] = n.negative_score.gt(.9)
    n['unknown_availability'] = n.available.isna()
    rows = n.groupby(['symbol', 'entry_idx'], as_index=False).agg(
        positive=('positive', 'any'), negative=('negative', 'any'),
        articles=('article_id', 'size'), first_publication=('published', 'min'),
        last_publication=('published', 'max'), last_available=('available', 'max'),
        unknown_availability=('unknown_availability', 'any'),
        family=('family', lambda s: s.iloc[0] if s.nunique() == 1 else 'MULTIPLE_SCREEN'))
    rows['tone'] = np.select([rows.positive & rows.negative, rows.positive, rows.negative],
        ['mixed', 'positive_only', 'negative_only'], default='no_strong_score')
    rows['sign'] = rows.tone.map({'positive_only': 1, 'negative_only': -1}).fillna(0).astype(int)
    rows['entry_date'] = schedule.day.iloc[rows.entry_idx.to_numpy()].to_numpy()
    rows['entry_time'] = pd.to_datetime(schedule.open_at.iloc[rows.entry_idx.to_numpy()].to_numpy(), utc=True)
    rows['availability_proxy_before_entry'] = (~rows.unknown_availability &
        rows.last_available.lt(rows.entry_time) & rows.last_publication.lt(rows.entry_time-pd.Timedelta(minutes=5)))
    rows['year'] = rows.entry_date.dt.year
    stats.update(timed_deduped_rows=len(n), event_groups=len(rows),
                 covered_symbols=int(rows.symbol.nunique()),
                 availability_proxy_before_entry=int(rows.availability_proxy_before_entry.sum()))
    return rows, stats


def price_panels(bars, schedule):
    b = bars.copy()
    b['day'] = pd.to_datetime(b.date)
    if b.duplicated(['symbol', 'day']).any():
        raise ValueError('Duplicate daily prices; no arbitrary provider selection')
    for col in ('open', 'high', 'low', 'close', 'volume'):
        b[col] = pd.to_numeric(b[col], errors='coerce')
    valid = (b.is_filled.eq(0) & b.data_adjustment.eq('split') &
        np.isfinite(b[['open', 'high', 'low', 'close', 'volume']]).all(axis=1) &
        b[['open', 'high', 'low', 'close', 'volume']].gt(0).all(axis=1) &
        b.high.ge(b[['open', 'close', 'low']].max(axis=1)) &
        b.low.le(b[['open', 'close', 'high']].min(axis=1)))
    b.loc[~valid, ['open', 'close']] = np.nan
    panels = {col: b.pivot(index='day', columns='symbol', values=col).reindex(schedule.day)
              for col in ('open', 'close')}
    return panels, dict(rows=len(b), invalid=int((~valid).sum()), symbols=int(b.symbol.nunique()))


def outcomes(events, panels, schedule, sectors, horizon, registry):
    result = events.copy()
    result['exit_idx'] = result.entry_idx + horizon - 1
    result['exit_date'] = result.exit_idx.map(schedule.day.to_dict())
    idx = result.entry_idx.to_numpy(dtype=int)
    end = result.exit_idx.to_numpy(dtype=int)
    columns = panels['open'].columns
    loc = columns.get_indexer(result.symbol)
    ok = (loc >= 0) & (end < len(schedule))
    safe_col = np.maximum(loc, 0)
    safe_end = np.minimum(end, len(schedule)-1)
    opens, closes = panels['open'].to_numpy(), panels['close'].to_numpy()
    entry = opens[idx, safe_col]
    terminal = closes[safe_end, safe_col]
    for offset in range(horizon):
        step = np.minimum(idx+offset, len(schedule)-1)
        ok &= np.isfinite(opens[step, safe_col]) & np.isfinite(closes[step, safe_col])
    identity = np.zeros(len(result), dtype=bool)
    for symbol, breaks in registry.items():
        mask = result.symbol.eq(symbol)
        for event in breaks:
            identity |= (mask & result.entry_date.le(event.last_predecessor_date) &
                         result.exit_date.ge(event.first_successor_date)).to_numpy()
    ok &= ~identity
    result['qualified_path'] = ok
    result['identity_break'] = identity
    result['return_pct'] = np.where(ok, (terminal/entry-1)*100, np.nan)
    spy_open = panels['open']['SPY'].to_numpy()
    spy_close = panels['close']['SPY'].to_numpy()
    spy_valid = np.ones(len(result), dtype=bool)
    for offset in range(horizon):
        step = np.minimum(idx+offset, len(schedule)-1)
        spy_valid &= np.isfinite(spy_open[step]) & np.isfinite(spy_close[step])
    spy = np.where(spy_valid, (spy_close[safe_end]/spy_open[idx]-1)*100, np.nan)
    result['excess_spy_pct'] = result.return_pct - spy
    result['signed_return_pct'] = result.sign * result.return_pct
    result['signed_excess_spy_pct'] = result.sign * result.excess_spy_pct
    result['signed_after_assumed_16bps_pct'] = result.signed_return_pct - .16
    # Full past-to-decision bridge is descriptive; not a true pre-publication return.
    pub = result.first_publication.astype('int64').to_numpy()
    prior = np.searchsorted(schedule.close_at.astype('int64').to_numpy(), pub, side='left')-1
    previous = closes[np.maximum(prior, 0), safe_col]
    result['bridge_to_entry_pct'] = np.where((prior >= 0) & (loc >= 0), (entry/previous-1)*100, np.nan)
    result['sector_current'] = result.symbol.map(sectors)
    # Same entry/exit and adjustment basis, leave-one-out sector universe.
    sector_excess = np.full(len(result), np.nan)
    sector_array = np.array([sectors.get(s, '') for s in columns])
    all_valid = np.isfinite(opens) & np.isfinite(closes)
    for (start, finish, sector), group in result.dropna(subset=['sector_current']).groupby(
            ['entry_idx', 'exit_idx', 'sector_current'], sort=False):
        if finish >= len(schedule) or not sector:
            continue
        good = (sector_array == sector) & all_valid[start:finish+1].all(axis=0)
        members = np.flatnonzero(good)
        if len(members) < 6:
            continue
        values = (closes[finish, members]/opens[start, members]-1)*100
        total = values.sum()
        for row in group.itertuples():
            column = columns.get_loc(row.symbol)
            own = (closes[finish, column]/opens[start, column]-1)*100
            present = bool(good[column])
            n = len(members)-int(present)
            if n >= 5 and row.qualified_path:
                sector_excess[row.Index] = row.sign*(row.return_pct-(total-(own if present else 0))/n)
    result['signed_excess_sector_nonpit_pct'] = sector_excess
    return result


def spaced(frame):
    """Reserve all tones/missing outcomes before examining any future return."""
    keep = []
    last = {}
    for row in frame.sort_values(['entry_idx', 'symbol']).itertuples():
        if row.entry_idx > last.get(row.symbol, -1):
            keep.append(row.Index)
            last[row.symbol] = row.exit_idx
    return frame.loc[keep].copy()


def wilson(wins, n):
    if n <= 0:
        return 0.
    z = 1.6448536269514722
    p = wins/n
    return (p+z*z/(2*n)-z*np.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)


def bh(pvalues):
    p = np.asarray(pvalues, dtype=float)
    if not len(p):
        return p
    order = np.argsort(p, kind='stable')
    q = np.minimum.accumulate((p[order]*len(p)/np.arange(1, len(p)+1))[::-1])[::-1]
    result = np.empty(len(p))
    result[order] = np.minimum(q, 1.)
    return result


def memberships(episodes, horizon):
    # End-of-label strictly before first 2026 decision. No 2026 data read in selection.
    train = episodes[(episodes.year == 2025) & episodes.exit_date.lt('2026-01-01') &
                     episodes.tone.isin(TONES) & episodes.signed_excess_spy_pct.notna()].copy()
    baselines = {tone: (float(g.signed_excess_spy_pct.gt(0).mean()),
                       float(g.signed_after_assumed_16bps_pct.mean())) for tone, g in train.groupby('tone')}
    rows = []
    total_min, half_min, months_min = GATES[horizon]
    # Include every observed training symbol/tone, even underpowered ones, in BH denominator.
    for (symbol, tone), g in train.groupby(['symbol', 'tone']):
        n = len(g)
        wins = int(g.signed_excess_spy_pct.gt(0).sum())
        base_hit, base_net = baselines[tone]
        h1 = g[g.entry_date.dt.month <= 6]
        h2 = g[g.entry_date.dt.month > 6]
        enough = n >= total_min and min(len(h1), len(h2)) >= half_min and g.entry_date.dt.month.nunique() >= months_min
        stable = all(len(p) and p.signed_after_assumed_16bps_pct.mean() > 0 and
                     p.signed_excess_spy_pct.mean() > 0 for p in (h1, h2))
        lower = wilson(wins, n)
        hit = lower > max(.5, base_hit)
        net = g.signed_after_assumed_16bps_pct.mean() > max(0., base_net)
        rows.append(dict(symbol=symbol, tone=tone, horizon=horizon, n_train=n, h1=len(h1), h2=len(h2),
            train_months=int(g.entry_date.dt.month.nunique()), train_aligned_pct=100*wins/n,
            wilson90_lower_pct=100*lower, global_train_aligned_pct=100*base_hit,
            train_net_proxy_mean_pct=float(g.signed_after_assumed_16bps_pct.mean()),
            train_excess_spy_mean_pct=float(g.signed_excess_spy_pct.mean()),
            enough_history=bool(enough), stable_halves=bool(stable),
            selected_pre_bh=bool(enough and stable and hit and net),
            p_value=float(binomtest(wins, n, p=max(.5, base_hit), alternative='greater').pvalue),
            max_training_exit=g.exit_date.max()))
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result['q_bh'] = bh(result.p_value)
    result['selected_bh'] = result.selected_pre_bh & result.q_bh.le(.05)
    return result


def metrics(frame):
    f = frame[frame.signed_excess_spy_pct.notna() & frame.tone.isin(TONES)]
    if f.empty:
        return dict(n=0, symbols=0, months=0)
    monthly = f.groupby(f.entry_date.dt.strftime('%Y-%m')).signed_after_assumed_16bps_pct.mean()
    return dict(n=len(f), symbols=int(f.symbol.nunique()), months=len(monthly),
        aligned_excess_spy_pct=float(f.signed_excess_spy_pct.gt(0).mean()*100),
        aligned_raw_pct=float(f.signed_return_pct.gt(0).mean()*100),
        signed_return_mean_pct=float(f.signed_return_pct.mean()),
        signed_after_assumed_16bps_mean_pct=float(f.signed_after_assumed_16bps_pct.mean()),
        signed_excess_spy_mean_pct=float(f.signed_excess_spy_pct.mean()),
        signed_excess_sector_nonpit_mean_pct=(float(f.signed_excess_sector_nonpit_pct.mean())
            if f.signed_excess_sector_nonpit_pct.notna().any() else None),
        sector_comparison_n=int(f.signed_excess_sector_nonpit_pct.notna().sum()),
        bridge_to_entry_mean_pct=float(f.bridge_to_entry_pct.mean()) if f.bridge_to_entry_pct.notna().any() else None,
        availability_proxy_before_entry=int(f.availability_proxy_before_entry.sum()),
        largest_symbol_share_pct=float(f.symbol.value_counts(normalize=True).iloc[0]*100),
        positive_net_proxy_months=int(monthly.gt(0).sum()))


def evaluate(episodes, members):
    test = episodes[(episodes.year == 2026) & episodes.tone.isin(TONES)].copy()
    result = dict(all_2026=metrics(test))
    comparisons = []
    per_symbol = []
    for flag in ('selected_pre_bh', 'selected_bh'):
        chosen = members[members[flag]][['symbol', 'tone']]
        selected = test.merge(chosen, on=['symbol', 'tone'], how='inner', validate='many_to_one')
        result[flag] = metrics(selected)
        selected_keys = set(map(tuple, chosen.to_numpy()))
        for (symbol, tone), g in selected.groupby(['symbol', 'tone']):
            stat = metrics(g)
            valid = stat['n'] >= 10 and stat['months'] >= 4
            passed = (valid and stat['aligned_excess_spy_pct'] > 50 and
                stat['signed_after_assumed_16bps_mean_pct'] > 0 and stat['signed_excess_spy_mean_pct'] > 0)
            per_symbol.append(dict(selection=flag, symbol=symbol, tone=tone, **stat,
                enough_test_history=valid, retrospective_confirmation=passed))
        eligible = test[test.signed_excess_spy_pct.notna()].copy()
        eligible['is_selected'] = [(s, t) in selected_keys for s, t in zip(eligible.symbol, eligible.tone)]
        # Same-tone/same-entry-date controls; no comparison to unrelated dates.
        for (day, tone), group in eligible.groupby(['entry_date', 'tone']):
            treated = group[group.is_selected]
            controls = group[~group.is_selected]
            if len(treated) and len(controls) >= 5:
                comparisons.append(dict(selection=flag, entry_date=day, tone=tone,
                    selected_n=len(treated), controls_n=len(controls),
                    delta_net_proxy_pct=float(treated.signed_after_assumed_16bps_pct.mean()-
                                               controls.signed_after_assumed_16bps_pct.mean())))
    return result, pd.DataFrame(per_symbol), pd.DataFrame(comparisons)


def run(output):
    check(output)
    if (output/'report.json').exists():
        raise FileExistsError('Report exists; no rerun into immutable result')
    meta = output/'metadata'
    if not (meta/'manifest.json').exists():
        raise ValueError('Complete metadata snapshot required (or a new explicitly amended protocol)')
    manifest = json.loads((meta/'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['files'].items():
        if digest(meta/name) != expected:
            raise ValueError('Metadata hash mismatch')
    news = pd.concat([pd.read_parquet(p) for p in sorted(SOURCE.glob('news-*.parquet'))], ignore_index=True)
    symbols = set(re.split(r'[,;\s]+', UNIVERSE.read_text(encoding='utf-8-sig').strip()))
    news = news[news.symbol.isin(symbols)].copy()
    headlines = pd.concat([pd.read_parquet(p) for p in sorted(meta.glob('headlines-*.parquet'))], ignore_index=True)
    sectors_frame = pd.read_parquet(meta/'sectors-current.parquet').drop_duplicates('symbol')
    sectors = sectors_frame.set_index('symbol').sector.fillna('').to_dict()
    schedule = schedule_frame()
    events, news_quality = make_events(news, schedule, headlines)
    bars = pd.read_parquet(SOURCE/'bars.parquet')
    panels, price_quality = price_panels(bars, schedule)
    events = events.reset_index(drop=True)
    events.to_parquet(output/'news-events.parquet', index=False)
    registry = load_security_discontinuities()
    report = dict(status='COMPLETED_RETROSPECTIVE_NO_PRODUCTION_UNIVERSE',
        current_universe=len(symbols), current_symbols_without_news=sorted(symbols-set(events.symbol)),
        current_symbols_without_archived_bars=sorted(symbols-set(bars.symbol)),
        news_quality=news_quality, prices=price_quality, horizons={},
        event_types_validated=False, metadata_sector_pit=False,
        availability_immutable=False, economic_backtest=False,
        limitation='Post-publication daily reaction, not proven post-receipt/scoring profit; historical years already explored')
    for horizon in HORIZONS:
        panel = outcomes(events, panels, schedule, sectors, horizon, registry)
        panel.to_parquet(output/f'events-H{horizon}.parquet', index=False)
        episodes = spaced(panel)
        members = memberships(episodes, horizon)
        members.to_csv(output/f'train-memberships-H{horizon}.csv', index=False)
        summary, symbol_result, comparisons = evaluate(episodes, members)
        symbol_result.to_csv(output/f'test-symbols-H{horizon}.csv', index=False)
        comparisons.to_csv(output/f'test-matched-dates-H{horizon}.csv', index=False)
        if not comparisons.empty:
            summary['matched_date_comparisons'] = {
                selection: dict(dates=int(g.entry_date.nunique()),
                    equal_date_delta_pct=float(g.groupby('entry_date').delta_net_proxy_pct.mean().mean()),
                    positive_months=int(g.groupby(g.entry_date.dt.strftime('%Y-%m')).delta_net_proxy_pct.mean().gt(0).sum()))
                for selection, g in comparisons.groupby('selection')}
        summary.update(all_event_groups=len(panel), path_qualified=int(panel.qualified_path.sum()),
            nonoverlap_events=len(episodes), training_cells=len(members),
            enough_training_cells=int(members.enough_history.sum()),
            selected_pre_bh_cells=int(members.selected_pre_bh.sum()), selected_bh_cells=int(members.selected_bh.sum()),
            unknown_test_paths=int(((episodes.year == 2026) & episodes.return_pct.isna()).sum()),
            families_routing_only={name: metrics(g) for name, g in episodes[episodes.year == 2026].groupby('family')})
        report['horizons'][str(horizon)] = summary
        print('H', horizon, 'training cells', len(members), 'selected', summary['selected_pre_bh_cells'],
              'BH', summary['selected_bh_cells'], flush=True)
    report['output_hashes'] = {p.name: digest(p) for p in output.iterdir()
                              if p.is_file() and p.name not in {'protocol.json', 'report.json'}}
    save(output/'report.json', report)
    print(report['status'], output, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('prepare', 'metadata', 'run'), required=True)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    {'prepare': prepare, 'metadata': metadata, 'run': run}[args.phase](args.output_dir)


if __name__ == '__main__':
    main()
