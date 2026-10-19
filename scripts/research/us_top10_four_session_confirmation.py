"""Frozen H10 TOP10: four closes J-1..J+2, entry J+3, TP10/SL5.

Offline research only, preserving the sealed three-close experiment unchanged.
Ten holding sessions including entry; no new fitting, SQL, API or orders.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import logging

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research import us_top10_three_session_confirmation as previous
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

SOURCE = previous.SOURCE
QUALITY = previous.QUALITY
THREE = Path('artifacts/research/us_top10_three_session_confirmation/20261019-v1')
LOG = logging.getLogger(__name__)


def directions(close, positions):
    """Three strict same-direction changes between four closes, no endpoint shortcut."""
    pos = np.asarray(positions, dtype=int)
    if (pos < 1).any() or (pos+2 >= len(close)).any(): raise ValueError('Missing four-close history')
    values = np.asarray(close, dtype=float)[pos[:, None]+np.arange(-1, 3)]
    valid = np.isfinite(values).all(axis=1) & (values > 0).all(axis=1)
    changes = np.diff(values, axis=1)
    return np.where(valid & (changes > 0).all(axis=1), 'LONG',
        np.where(valid & (changes < 0).all(axis=1), 'SHORT', 'NONE'))


def qualify(raw, days, positions, *, identity_events=(), price_reserve=None):
    """Union of two sealed windows covers every bar from J-1 through J+12."""
    pos = np.asarray(positions, dtype=int)
    _, _, first = previous.qualify(raw, days, pos, identity_events=identity_events, price_reserve=price_reserve)
    grid, _, second = previous.qualify(raw, days, pos+1, identity_events=identity_events, price_reserve=price_reserve)
    reasons = np.where(first != '', first, second)
    # Explicit full-window event guard, even for a long predecessor/successor gap.
    for event in identity_events:
        cross = ((days[pos-1] <= pd.Timestamp(event['last_predecessor_date']))
            & (days[pos+12] >= pd.Timestamp(event['first_successor_date'])))
        reasons[(reasons == '') & cross] = 'KNOWN_IDENTITY_BREAK'
    return grid, directions(grid.close.to_numpy(float), pos), reasons


def trades_for(grid, positions, side):
    return previous.execution.paths(grid, np.asarray(positions)+2, side, horizon=10, tp=.10, sl=.05)


def prepare(root):
    if (root/'protocol.json').exists():
        p = previous.prior.read(root/'protocol.json'); verify_hashes(Path('.'), p['sources']); return p
    old = previous.prior.read(SOURCE/'protocol.json')
    audit = previous.prior.read(SOURCE/'final-audit.json')
    if audit['status'] != 'PASS_EXPLORATORY_ONLY' or audit['protocol_sha256'] != digest(SOURCE/'protocol.json'):
        raise ValueError('Unqualified H10 score source')
    verify_hashes(Path('.'), old['sources'])
    three = previous.prior.read(THREE/'protocol.json'); verify_hashes(Path('.'), three['sources'])
    three_audit = previous.prior.read(THREE/'final-audit.json')
    if three_audit['report_sha256'] != digest(THREE/'report.json'): raise ValueError('Changed three-close reference')
    quality = previous.prior.read(QUALITY/'report.json'); verify_hashes(QUALITY, quality['files'])
    sources = [Path(__file__), Path('tests/test_us_top10_four_session_confirmation.py'), Path(previous.__file__),
        Path(previous.execution.__file__), Path(previous.execution.gate.__file__), Path(previous.execution.base.__file__),
        SOURCE/'protocol.json', SOURCE/'final-audit.json', QUALITY/'report.json', QUALITY/'research-prices.parquet',
        QUALITY/'quality-reserves.json', THREE/'protocol.json', THREE/'report.json', THREE/'final-audit.json']
    for year in old['folds']:
        done = previous.prior.read(SOURCE/f'{year}-done.json'); verify_hashes(SOURCE, done['files'])
        sources += [SOURCE/f'{year}-done.json', SOURCE/f'{year}-H10-scores.parquet']
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), sources={str(f): digest(f) for f in sources},
        years=[2024,2025,2026], model='Same frozen annual research Oracle amplitude H10 scores as three-close study',
        rank='Original TOP10 at J; no re-ranking later or replacement for failed/missing confirmation',
        rule='LONG iff adjusted closes J-1<J<J+1<J+2; SHORT iff strictly decreasing; otherwise abstain',
        entry='J+3 open after J+2 close; ten holding sessions including entry, timeout J+12 close',
        tp=.10, sl=.05, holding_sessions=10, trailing=False, observation_end='2026-09-30', last_signal='2026-09-01',
        prices=str(QUALITY/'research-prices.parquet'), price_reserves=old['price_reserves'], identity_events=old['identity_events'],
        costs_per_leg=previous.execution.gate.COST_PER_LEG, short_borrow_annual=previous.execution.gate.BORROW_ANNUAL,
        gaps='Adverse open beyond SL not clipped; TP at limit without favourable improvement',
        collision='Stop first unless open resolves first barrier', controls=previous.ARMS,
        baseline='Same TOP10, entry J+3, TP10/SL5, no confirmation',
        three_close_comparison='Descriptive only: different confirmation and entry timing; no isolated causal attribution',
        independence='Earliest-first per symbol/side; next entry strictly after full holding window, no portfolio constraints',
        sql=False, new_fit=False, api_calls=0, orders=False, production_changes=False, portfolio_pnl=False,
        reserves=three['reserves'])
    root.mkdir(parents=True, exist_ok=False); (root/'parts').mkdir()
    atomic_json(root/'protocol.json',p); return p


def build(root):
    p = previous.prior.read(root/'protocol.json'); verify_hashes(Path('.'),p['sources'])
    if (root/'data-ready.json').exists(): verify_hashes(root,previous.prior.read(root/'data-ready.json')['files']); return
    selected = pd.concat([pd.read_parquet(SOURCE/f'{year}-H10-scores.parquet') for year in p['years']],ignore_index=True)
    selected = selected[selected['rank'].le(10)].copy()
    assert not selected.duplicated(['date','symbol']).any() and selected.groupby('date').size().eq(10).all()
    selected.to_parquet(root/'selected-at-j.parquet',index=False)
    days = nyse_sessions('2023-01-01','2026-10-09')
    prices = pd.read_parquet(p['prices'],filters=[('symbol','in',selected.symbol.unique().tolist())])
    groups = {str(s):g for s,g in prices.groupby('symbol',observed=True)}
    symbols = sorted(selected.symbol.unique()); files={'selected-at-j.parquet':digest(root/'selected-at-j.parquet')}; diagnostics=[]
    for chunk,start in enumerate(range(0,len(symbols),50)):
        folder=root/'parts'/f'{chunk:04}'; folder.mkdir(exist_ok=True); marker=folder/'done.json'
        if marker.exists():
            done=previous.prior.read(marker); verify_hashes(root,done['files']); files.update(done['files']); diagnostics.extend(done['diagnostics']); continue
        pieces=[]; records=[]
        for symbol in symbols[start:start+50]:
            s=selected[selected.symbol.eq(symbol)].sort_values('date').copy(); pos=days.get_indexer(s.date)
            if (pos<1).any() or symbol not in groups: raise ValueError(f'Missing calendar/price source {symbol}')
            grid,direction,reasons=qualify(groups[symbol],days,pos,
                identity_events=p['identity_events'].get(symbol,[]),price_reserve=p['price_reserves'].get(symbol))
            s['direction']=direction; s['quality_reason']=reasons
            records.extend(s[['date','symbol','rank','year','direction','quality_reason']].to_dict('records'))
            valid=reasons==''; q=s[valid]; indexes=pos[valid]
            if len(q):
                for side in ('LONG','SHORT'):
                    result=trades_for(grid,indexes,side)
                    pieces.append(pd.DataFrame(dict(date=q.date.to_numpy(),symbol=symbol,year=q.year.to_numpy(),
                        rank=q['rank'].to_numpy(),direction=q.direction.to_numpy(),side=side,
                        confirmation_date=days[indexes+2],entry_date=days[indexes+3],last_path_date=days[indexes+12],**result)))
        if not pieces: raise ValueError('Empty chunk')
        out=folder/'trades.parquet'; pd.concat(pieces,ignore_index=True).to_parquet(out,index=False)
        done=dict(files={str(out.relative_to(root)):digest(out)},diagnostics=records)
        atomic_json(marker,done); files.update(done['files']); diagnostics.extend(records)
        atomic_json(root/'progress.json',dict(status='RUNNING',phase='FOUR_CLOSE_CONFIRMATION',completed=min(start+50,len(symbols)),total=len(symbols)))
        LOG.info('Four-close confirmation %d/%d symbols',min(start+50,len(symbols)),len(symbols))
    pd.DataFrame(diagnostics).to_parquet(root/'qualification.parquet',index=False)
    files['qualification.parquet']=digest(root/'qualification.parquet')
    verify_hashes(Path('.'),p['sources']); atomic_json(root/'data-ready.json',dict(files=files,selected=len(selected)))


def summarize(root):
    # Summary/cost/episode conventions are identical to the sealed prior study.
    previous.summarize(root)
    old=previous.prior.read(THREE/'report.json'); new=previous.prior.read(root/'report.json')
    rows=[]
    for r in new['results']:
        ref=next(x for x in old['results'] if (x['year'],x['arm'])==(r['year'],r['arm']))
        rows.append(dict(year=r['year'],arm=r['arm'],three_close_n=ref['n'],four_close_n=r['n'],
            three_close_mean=ref.get('mean_net'),four_close_mean=r.get('mean_net'),
            reserve='Descriptive: entry J+2 versus J+3 and changed confirmation, not pure extra-close effect'))
    atomic_json(root/'three-vs-four-closes.json',dict(comparisons=rows,source_report_sha256=digest(THREE/'report.json')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','build','summarize','all'],default='all')
    args=parser.parse_args(); logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    for name,function in [('prepare',prepare),('build',build),('summarize',summarize)]:
        if args.phase in ('all',name): function(args.output)
