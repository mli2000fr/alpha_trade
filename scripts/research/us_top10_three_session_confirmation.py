"""Frozen H10 Oracle TOP10, close confirmation J-1/J/J+1, entry J+2.

Offline research only. No fitting, SQL, provider/LLM calls, production or orders.
TP10/SL5, ten sessions including entry; no trailing. Unknown futures stay missing.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import logging

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research import us_h10_h20_frozen_comparison as prior
from scripts.research import us_oracle_holding_horizons as execution
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

SOURCE = Path('artifacts/research/us_h10_h20_frozen_comparison/20261019-v1')
QUALITY = prior.QUALITY
LOG = logging.getLogger(__name__)
ARMS = ['ALL_TOP10_LONG', 'ALL_TOP10_SHORT', 'CONFIRMED_LONG', 'CONFIRMED_SHORT',
        'CONFIRMED_DIRECTION', 'CONFIRMED_PAIRS_ALL_LONG', 'CONFIRMED_PAIRS_ALL_SHORT']


def directions(close, positions):
    """Exactly two strict increases/decreases between three closes, not three returns."""
    positions = np.asarray(positions, dtype=int)
    if (positions < 1).any() or (positions+1 >= len(close)).any(): raise ValueError('Missing confirmation history')
    values = np.asarray(close, dtype=float)[positions[:, None]+np.array([-1, 0, 1])]
    valid = np.isfinite(values).all(axis=1) & (values > 0).all(axis=1)
    up = valid & (np.diff(values, axis=1) > 0).all(axis=1)
    down = valid & (np.diff(values, axis=1) < 0).all(axis=1)
    return np.where(up, 'LONG', np.where(down, 'SHORT', 'NONE'))


def qualify(raw, days, positions, *, identity_events=(), price_reserve=None):
    """Validate J-1 through J+11, without deleting candidates from J's ranking."""
    positions = np.asarray(positions, dtype=int)
    if raw.duplicated('date').any(): raise ValueError('Duplicate symbol/date price')
    if (positions < 1).any() or (positions+11 >= len(days)).any(): raise ValueError('Incomplete calendar')
    grid = raw.set_index('date').reindex(days)
    columns = ['open', 'high', 'low', 'close', 'adj_close', 'volume', 'is_filled']
    values = grid[columns].apply(pd.to_numeric, errors='coerce')
    adjusted = values.adj_close.where(values.adj_close.notna(), values.close)
    factor = adjusted/values.close
    good = (np.isfinite(values[['open', 'high', 'low', 'close']]).all(axis=1)
        & values[['open', 'high', 'low', 'close']].gt(0).all(axis=1)
        & values.high.ge(values[['open', 'close', 'low']].max(axis=1))
        & values.low.le(values[['open', 'close', 'high']].min(axis=1))
        & np.isfinite(factor) & factor.gt(0) & values.volume.gt(0) & values.is_filled.eq(0))
    indexes = positions[:, None]+np.arange(-1, 12)
    reason = np.full(len(positions), '', dtype=object)
    def reject(mask, message): reason[(reason == '') & mask] = message
    reject(~good.to_numpy()[indexes].all(axis=1), 'INVALID_OR_MISSING_CONFIRMATION_OR_PATH')
    for field in ('instrument_id', 'data_source', 'data_adjustment'):
        codes = pd.factorize(grid[field])[0][indexes]
        known = codes[:, 0] >= 0
        if field != 'instrument_id':
            known &= ~grid[field].iloc[positions-1].astype(str).str.upper().isin(['UNKNOWN', '']).to_numpy()
        reject(~((codes == codes[:, :1]).all(axis=1) & known), 'UNKNOWN_OR_CHANGED_'+field.upper())
    with np.errstate(divide='ignore', invalid='ignore'):
        closes = adjusted.to_numpy(float)[indexes]
        ratios = closes[:, 1:]/closes[:, :-1]
    reject(((ratios >= 20) | (ratios <= .05)).any(axis=1), 'UNEXPLAINED_20X_PRICE_BREAK')
    for event in identity_events:
        reject((days[positions-1] <= pd.Timestamp(event['last_predecessor_date']))
            & (days[positions+11] >= pd.Timestamp(event['first_successor_date'])), 'KNOWN_IDENTITY_BREAK')
    if price_reserve:
        reject(days[positions+11] >= pd.Timestamp(price_reserve['start']), 'UNRESOLVED_PRICE_OR_DISTRIBUTION_BASIS')
    executable = grid.copy()
    for column in ('open', 'high', 'low', 'close'): executable[column] = values[column]*factor
    return executable, directions(adjusted.to_numpy(float), positions), reason


def trades_for(grid, positions, side):
    # paths enters one session after its decision index. Shift by one to enter J+2.
    return execution.paths(grid, np.asarray(positions)+1, side, horizon=10, tp=.10, sl=.05)


def select_arm(frame, arm):
    if arm.startswith('ALL_TOP10_'): return frame[frame.side.eq(arm.removeprefix('ALL_TOP10_'))]
    if arm == 'CONFIRMED_LONG': return frame[frame.direction.eq('LONG') & frame.side.eq('LONG')]
    if arm == 'CONFIRMED_SHORT': return frame[frame.direction.eq('SHORT') & frame.side.eq('SHORT')]
    if arm == 'CONFIRMED_DIRECTION': return frame[frame.direction.eq(frame.side)]
    if arm.startswith('CONFIRMED_PAIRS_ALL_'):
        return frame[frame.direction.ne('NONE') & frame.side.eq(arm.removeprefix('CONFIRMED_PAIRS_ALL_'))]
    raise ValueError(arm)


def prepare(root):
    if (root/'protocol.json').exists():
        p = prior.read(root/'protocol.json'); verify_hashes(Path('.'), p['sources']); return p
    old = prior.read(SOURCE/'protocol.json'); audit = prior.read(SOURCE/'final-audit.json')
    if audit['status'] != 'PASS_EXPLORATORY_ONLY' or audit['protocol_sha256'] != digest(SOURCE/'protocol.json'):
        raise ValueError('Parent comparison is not qualified')
    verify_hashes(Path('.'), old['sources'])
    quality = prior.read(QUALITY/'report.json'); verify_hashes(QUALITY, quality['files'])
    sources = [Path(__file__), Path('tests/test_us_top10_three_session_confirmation.py'),
        Path(execution.__file__), Path(execution.gate.__file__), Path(execution.base.__file__),
        SOURCE/'protocol.json', SOURCE/'final-audit.json', QUALITY/'report.json',
        QUALITY/'research-prices.parquet', QUALITY/'quality-reserves.json']
    for year in old['folds']:
        done = prior.read(SOURCE/f'{year}-done.json'); verify_hashes(SOURCE, done['files'])
        sources += [SOURCE/f'{year}-done.json', SOURCE/f'{year}-H10-scores.parquet']
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), sources={str(p): digest(p) for p in sources},
        years=[2024, 2025, 2026], model='Frozen new research H10 amplitude models, one chronological fold per year',
        rank='Top 10 by original score at J; never re-rank at J+1 or replace missing/failed confirmations',
        rule='LONG iff adjusted close(J-1)<close(J)<close(J+1); SHORT iff strictly decreasing; otherwise abstain',
        entry='J+2 open, only after J+1 close; ten sessions including entry, timeout J+11 close',
        tp=.10, sl=.05, holding_sessions=10, trailing=False,
        observation_end='2026-09-30', last_signal='2026-09-01', prices=str(QUALITY/'research-prices.parquet'),
        price_reserves=old['price_reserves'], identity_events=old['identity_events'],
        costs_per_leg=execution.gate.COST_PER_LEG, short_borrow_annual=execution.gate.BORROW_ANNUAL,
        gaps='Adverse stop gap at open, not capped to 5%; TP gap at limit',
        collision='SL first unless open establishes first barrier',
        controls=ARMS, baseline='Same original TOP10, same delayed entry and same TP/SL, no direction confirmation',
        independence='Earliest-first per symbol/side; next entry after previous full ten-session window, not after early TP',
        sql=False, new_fit=False, api_calls=0, production_changes=False, orders=False, portfolio_pnl=False,
        reserves=['Current survivor universe; previously explored years and hypotheses, not virgin holdout',
            'Research normalized adjusted prices, not independent daily execution certification or all features PIT',
            'Full path quality exclusion reported after frozen selection, never replaced or assigned zero return',
            'Per-occasion results, no capital constraints, leverage, locates or portfolio drawdown inference'])
    root.mkdir(parents=True, exist_ok=False); (root/'parts').mkdir()
    atomic_json(root/'protocol.json', p); return p


def build(root):
    p = prior.read(root/'protocol.json'); verify_hashes(Path('.'), p['sources'])
    if (root/'data-ready.json').exists(): verify_hashes(root, prior.read(root/'data-ready.json')['files']); return
    selected = pd.concat([pd.read_parquet(SOURCE/f'{year}-H10-scores.parquet') for year in p['years']], ignore_index=True)
    selected = selected[selected['rank'].le(10)].copy()
    assert not selected.duplicated(['date', 'symbol']).any()
    assert selected.groupby('date').size().eq(10).all()
    selected.to_parquet(root/'selected-at-j.parquet', index=False)
    days = nyse_sessions('2023-01-01', '2026-10-09')
    prices = pd.read_parquet(p['prices'], filters=[('symbol', 'in', selected.symbol.unique().tolist())])
    groups = {str(s): g for s, g in prices.groupby('symbol', observed=True)}
    symbols = sorted(selected.symbol.unique()); files = {'selected-at-j.parquet': digest(root/'selected-at-j.parquet')}
    all_diagnostics = []
    for chunk, start in enumerate(range(0, len(symbols), 50)):
        folder = root/'parts'/f'{chunk:04}'; folder.mkdir(exist_ok=True); marker = folder/'done.json'
        if marker.exists():
            done = prior.read(marker); verify_hashes(root, done['files']); files.update(done['files']); all_diagnostics.extend(done['diagnostics']); continue
        pieces = []; diagnostics = []
        for symbol in symbols[start:start+50]:
            s = selected[selected.symbol.eq(symbol)].sort_values('date').copy()
            pos = days.get_indexer(s.date)
            if (pos < 1).any(): raise ValueError('Non-session or insufficient past')
            if symbol not in groups: raise ValueError(f'No price archive at all: {symbol}')
            grid, direction, reason = qualify(groups[symbol], days, pos,
                identity_events=p['identity_events'].get(symbol, []), price_reserve=p['price_reserves'].get(symbol))
            s['direction'] = direction; s['quality_reason'] = reason
            diagnostics.extend(s[['date', 'symbol', 'rank', 'year', 'direction', 'quality_reason']].to_dict('records'))
            keep = reason == ''; q = s[keep]; indexes = pos[keep]
            if len(q):
                for side in ('LONG', 'SHORT'):
                    result = trades_for(grid, indexes, side)
                    pieces.append(pd.DataFrame(dict(date=q.date.to_numpy(), symbol=symbol, year=q.year.to_numpy(),
                        rank=q['rank'].to_numpy(), direction=q.direction.to_numpy(), side=side,
                        entry_date=days[indexes+2], confirmation_date=days[indexes+1],
                        last_path_date=days[indexes+11], **result)))
        if not pieces: raise ValueError('Empty chunk')
        out = folder/'trades.parquet'; pd.concat(pieces, ignore_index=True).to_parquet(out, index=False)
        done = dict(files={str(out.relative_to(root)): digest(out)}, diagnostics=diagnostics)
        atomic_json(marker, done); files.update(done['files']); all_diagnostics.extend(diagnostics)
        atomic_json(root/'progress.json', dict(status='RUNNING', phase='DELAYED_ENTRY', completed=min(start+50,len(symbols)), total=len(symbols)))
        LOG.info('TOP10 confirmation: %d/%d distinct symbols', min(start+50,len(symbols)),len(symbols))
    d = pd.DataFrame(all_diagnostics); d.to_parquet(root/'qualification.parquet', index=False)
    files['qualification.parquet'] = digest(root/'qualification.parquet')
    verify_hashes(Path('.'), p['sources']); atomic_json(root/'data-ready.json', dict(files=files, selected=len(selected)))


def summarize(root):
    p = prior.read(root/'protocol.json'); verify_hashes(Path('.'), p['sources'])
    ready = prior.read(root/'data-ready.json'); verify_hashes(root, ready['files'])
    raw = pd.concat([pd.read_parquet(root/n) for n in ready['files'] if n.endswith('trades.parquet')], ignore_index=True)
    f = execution.gate.attach_costs(raw); f.to_parquet(root/'evaluations.parquet', index=False)
    d = pd.read_parquet(root/'qualification.parquet'); rows = []; coverage = []
    days = nyse_sessions('2024-01-01', '2026-10-09')
    for year, annual in f.groupby('year'):
        source = d[d.year.eq(year)]
        coverage.append(dict(year=int(year), selected=len(source), qualified=int(source.quality_reason.eq('').sum()),
            directions=source.direction.value_counts().to_dict(), reasons=source.quality_reason.value_counts().to_dict()))
        for arm in ARMS:
            s = select_arm(annual, arm)
            if s.empty: rows.append(dict(year=int(year), arm=arm, n=0)); continue
            nonoverlap = execution.base.independent_fast(s)
            gains = s.net_outcome[s.net_outcome.gt(0)]; losses = s.net_outcome[s.net_outcome.le(0)]
            row = dict(year=int(year), arm=arm, n=len(s), selection_rate=len(s)/(len(annual)//2),
                mean_net=float(s.net_outcome.mean()), median_net=float(s.net_outcome.median()),
                win_rate=float(s.net_outcome.gt(0).mean()), tp_rate=float(s.tp_first.mean()), sl_rate=float(s.sl_first.mean()),
                timeout_rate=float(s.outcome.eq('TIMEOUT').mean()), mean_win=float(gains.mean()) if len(gains) else None,
                mean_loss=float(losses.mean()) if len(losses) else None, worst=float(s.net_outcome.min()),
                profit_factor=float(gains.sum()/-losses.sum()) if len(losses) and losses.sum()<0 else None,
                independent_n=len(nonoverlap), independent_mean_net=float(nonoverlap.net_outcome.mean()),
                independent_win_rate=float(nonoverlap.net_outcome.gt(0).mean()),
                gap_stop_rate=float(s.gap_stop.mean()), ambiguity_rate=float(s.ambiguity.mean()))
            if arm in ('CONFIRMED_LONG', 'CONFIRMED_SHORT'):
                side=arm.removeprefix('CONFIRMED_'); baseline=annual[annual.side.eq(side)].groupby('date').net_outcome.mean()
                delta=s.groupby('date').net_outcome.mean()-baseline
                row['daily_gain_vs_unfiltered_same_side']=execution.gate.block_interval(delta,days)
            if arm=='CONFIRMED_DIRECTION':
                row['daily_gain_vs_blind_same_pairs']={}
                for side in ('LONG','SHORT'):
                    blind=select_arm(annual,'CONFIRMED_PAIRS_ALL_'+side)
                    row['daily_gain_vs_blind_same_pairs'][side]=execution.gate.block_interval(
                        s.groupby('date').net_outcome.mean()-blind.groupby('date').net_outcome.mean(),days)
            rows.append(row)
    pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,dict)} for r in rows]).to_csv(root/'comparison.csv',index=False)
    files={n:digest(root/n) for n in ('evaluations.parquet','comparison.csv')}
    atomic_json(root/'report.json',dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',protocol_sha256=digest(root/'protocol.json'),
        results=rows,coverage=coverage,files=files,claim='Confirmation observed before delayed entry; per-occasion hypothetical results, not annual capital returns'))
    verify_hashes(Path('.'),p['sources'])
    atomic_json(root/'progress.json',dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',phase='DONE'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--phase',choices=['prepare','build','summarize','all'],default='all')
    args=parser.parse_args(); logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    for name, function in [('prepare',prepare),('build',build),('summarize',summarize)]:
        if args.phase in ('all',name): function(args.output)
