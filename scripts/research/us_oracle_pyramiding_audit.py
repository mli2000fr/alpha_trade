"""Separate offline reconstruction of frozen inputs, stops, sizing and cash ledger."""
from __future__ import annotations

import argparse
from collections import defaultdict
import math
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_pyramiding import READ, ARMS


def near(a, b, label='value'):
    if not np.isclose(float(a), float(b), rtol=1e-10, atol=1e-7):
        raise AssertionError(f'{label}: {a} != {b}')


def independent_exit(path, start):
    """Vector prior peaks, unlike the incremental state machine being audited."""
    a = path.iloc[start:][['open', 'high', 'low', 'close']].to_numpy(float)
    entry = a[0, 0]
    prior_peaks = np.maximum.accumulate(np.r_[entry, a[:-1, 1]])
    stops = np.maximum(entry*.95, prior_peaks*.85)
    gaps = a[:, 0] <= stops+np.abs(stops)*1e-12
    touched = a[:, 2] <= stops+np.abs(stops)*1e-12
    touched[-1] = True
    i = int(np.flatnonzero(touched | gaps)[0])
    reason = 'GAP_STOP' if gaps[i] else 'EXPIRY' if i == len(a)-1 else 'STOP'
    price = float(a[i, 0] if reason != 'STOP' else stops[i])
    return start+i, price, reason, stops


def audit_candidates(root, bars, candidates):
    parent = Path(READ(root/'protocol.json')['parent'])
    snapshots = READ(parent/'snapshot-ready.json')['files']
    verify_hashes(parent, snapshots)
    raw = pd.concat([pd.read_parquet(parent/n) for n in snapshots], ignore_index=True)
    groups = {(s, d): g.sort_values('bar_timestamp') for (s, d), g in raw.groupby(['symbol', 'trade_date'])}
    days = pd.DatetimeIndex(pd.read_parquet(parent/'sessions.parquet').date)
    coverage = pd.read_parquet(parent/'coverage.parquet')
    if set(candidates.pair_id) != set(coverage.loc[coverage.status.eq('OK'), 'pair_id']):
        raise AssertionError('Changed common cohort')
    for r in candidates.itertuples():
        path = bars[bars.pair_id.eq(r.pair_id)].sort_values('bar_index')
        j = days.get_loc(r.date)
        frames = [groups[r.symbol, day] for day in days[j:j+21]]
        expected = None
        offset = 0
        for prev, today in zip(frames[:-1], frames[1:]):
            c = today.close.to_numpy(float)
            h = float(prev.high.max())
            before = np.r_[float(prev.close.iloc[-1]), c[:-3]]
            hit = (c[:-2] > h) & (c[1:-1] > h) & (before <= h)
            indices = np.flatnonzero(hit)
            if len(indices) and expected is None:
                expected = offset+int(indices[0])+2
            offset += len(today)
        if expected == len(path)-1:
            expected = None
        if int(r.entry_index) != (-1 if expected is None else expected):
            raise AssertionError(f'First LONG signal mismatch: {r.pair_id}')
        # Rebuild ALL bars independently from sealed raw parts, not only returns.
        original = pd.concat(frames[1:], ignore_index=True)
        np.testing.assert_allclose(path[['open', 'high', 'low', 'close']], original[['open', 'high', 'low', 'close']], rtol=0, atol=0)
        if list(path.bar_timestamp) != list(original.bar_timestamp):
            raise AssertionError('Bar timestamps changed')
        if list(path.bar_end_timestamp) != list(original.bar_end_timestamp):
            raise AssertionError('Bar end timestamps changed')
        if list(path.session_offset) != [s for s, frame in enumerate(frames[1:], 1) for _ in range(len(frame))]:
            raise AssertionError('Session offsets changed')
        if r.expiry != path.bar_timestamp.iloc[-1]:
            raise AssertionError('Expiry changed')
        if expected is not None and r.entry_time != path.bar_timestamp.iloc[expected]:
            raise AssertionError('Entry timestamp changed')


def audit_arm(root, label, bars, candidates, calendar):
    cost = int(label.rsplit('-', 1)[1].replace('bps', ''))/10000
    arm = label.rsplit('-', 1)[0]
    out = root/label
    marks, lots, orders, fills = [pd.read_parquet(out/f'{n}.parquet') for n in ['marks', 'lots', 'orders', 'fills']]
    paths = {int(pid): g.sort_values('bar_index').reset_index(drop=True) for pid, g in bars.groupby('pair_id')}
    meta = candidates.set_index('pair_id').to_dict('index')
    bytime = {ts: g.set_index('pair_id') for ts, g in bars.groupby('bar_timestamp')}
    byfill = {ts: g.sort_values('sequence') for ts, g in fills.groupby('bar_time')}
    byorder = {ts: g.sort_values('order_id') for ts, g in orders.groupby('time')}
    lotmeta = lots.set_index('lot_id').to_dict('index')
    stop_arrays = {}
    for r in lots.itertuples():
        path = paths[r.pair_id]
        i, price, reason, stops = independent_exit(path, r.entry_bar_index)
        if i != r.exit_bar_index or reason != r.exit_reason:
            raise AssertionError(f'Stop lifecycle mismatch: {r.lot_id}')
        near(price, r.exit_price, 'exit price')
        b = path.iloc[i]
        expected_time = b.bar_end_timestamp if reason == 'STOP' else b.bar_timestamp
        if r.exit_time != expected_time:
            raise AssertionError('Exit timestamp/interval convention')
        near(r.entry_fee, cost*r.entry_price*r.quantity)
        near(r.exit_fee, cost*r.exit_price*r.quantity)
        near(r.net, r.quantity*(price-r.entry_price)-r.entry_fee-r.exit_fee)
        stop_arrays[r.lot_id] = stops
    if orders[orders.kind.eq('INITIAL')].pair_id.duplicated().any():
        raise AssertionError('Repeated initial attempt')
    if orders[orders.kind.eq('ADD')].pair_id.duplicated().any():
        raise AssertionError('Repeated add attempt')
    if set(orders.loc[orders.kind.eq('INITIAL'), 'pair_id']) != set(candidates.loc[candidates.entry_index.ge(0), 'pair_id']):
        raise AssertionError('Missing/replaced initial candidate')
    if arm != 'HALF_ADD_ONE' and (orders.kind.eq('ADD').any() or lots.leg.eq('ADD').any()):
        raise AssertionError('Add in control')
    # First valid two-close opportunity, including refused/cancelled add orders.
    for initial in lots[lots.leg.eq('INITIAL')].itertuples():
        if arm != 'HALF_ADD_ONE':
            continue
        path = paths[initial.pair_id]
        expected = None
        for k in range(initial.entry_bar_index+1, min(initial.exit_bar_index, len(path)-2)):
            prev, now, nxt = path.iloc[k-1], path.iloc[k], path.iloc[k+1]
            if (prev.session_offset == now.session_offset == nxt.session_offset
                and min(prev.close, now.close)+1e-8 >= initial.entry_price*1.05):
                expected = nxt.bar_timestamp
                break
        actual = orders[(orders.pair_id.eq(initial.pair_id)) & orders.kind.eq('ADD')]
        if expected is None and len(actual) or expected is not None and (len(actual) != 1 or actual.time.iloc[0] != expected):
            raise AssertionError(f'Add confirmation timing {initial.pair_id}')
    cash = 4000.
    inventory, campaign_info, losses = {}, {}, defaultdict(float)
    reconstructed = []
    seen = []
    for mark in marks.itertuples():
        ts = mark.time-pd.Timedelta(minutes=5)
        frame = bytime.get(ts)
        fs = byfill.get(ts, fills.iloc[:0])
        os = byorder.get(ts, orders.iloc[:0])

        def apply_fill(f):
            nonlocal cash
            seen.append(int(f.sequence))
            if f.quantity <= 0 or f.quantity != math.floor(f.quantity):
                raise AssertionError('Noninteger/nonpositive quantity')
            near(f.fee, f.quantity*f.price*cost)
            if f.side == 'BUY':
                if f.lot_id in inventory:
                    raise AssertionError('Duplicate buy')
                inventory[f.lot_id] = lotmeta[f.lot_id]
                near(f.price, lotmeta[f.lot_id]['entry_price'])
                near(f.quantity, lotmeta[f.lot_id]['quantity'])
                cash -= f.quantity*f.price+f.fee
            else:
                lot = inventory.pop(f.lot_id)
                near(f.quantity, lot['quantity'])
                near(f.price, lot['exit_price'])
                cash += f.quantity*f.price-f.fee
                losses[f.pair_id] += max(0., -lot['net'])
            near(cash, f.cash_after, 'cash after fill')
            if cash < -1e-7:
                raise AssertionError('Negative cash')

        for f in fs[(fs.phase.eq('OPEN')) & fs.side.eq('SELL')].itertuples():
            apply_fill(f)
        buys = fs[fs.side.eq('BUY')]
        for o in os.itertuples():
            eq = cash+sum(v['quantity']*float(frame.loc[v['pair_id'], 'open']) for v in inventory.values())
            near(o.equity_before, eq, 'sizing equity')
            near(o.cash_before, cash, 'sizing cash')
            pid = o.pair_id
            price = float(frame.loc[pid, 'open'])
            if o.kind == 'INITIAL':
                m = meta[pid]
                if ts != m['entry_time']:
                    raise AssertionError('Initial entry not next-bar first signal')
                budget = .02*eq
                full = max(0, math.floor(min(budget/(price*(.05+2.05*cost)),
                    .25*eq/price, cash/(price*(1+cost)))+1e-12))
                qty = full if arm == 'FULL_BASE' else full//2
                held = {v['pair_id'] for v in inventory.values()}
                symbols = {meta[x]['symbol'] for x in held}
                why = ('DUPLICATE_HELD_SYMBOL' if m['symbol'] in symbols else
                    'MAX_POSITIONS' if len(held) >= 8 else 'ZERO_WHOLE_SHARES' if qty <= 0 else 'FILLED')
                campaign_info[pid] = dict(full=full, initial_qty=qty, budget=budget, entry=price)
                near(o.full_quantity, full)
                near(o.budget, budget)
            else:
                c = campaign_info[pid]
                original = inventory.get(f'{pid}-0')
                if original is None or price+1e-8 < c['entry']*1.05:
                    why = 'CANCEL_ORIGINAL_EXITED' if original is None else 'CANCEL_GAP_BELOW_TRIGGER'
                    qty = 0
                else:
                    used = losses[pid]
                    notional = 0.
                    for lid, lot in inventory.items():
                        if lot['pair_id'] != pid:
                            continue
                        k = int(frame.loc[pid, 'bar_index'])
                        stop = stop_arrays[lid][k-lot['entry_bar_index']]
                        used += lot['quantity']*(max(lot['entry_price']-stop, 0.)+cost*(lot['entry_price']+stop))
                        notional += lot['quantity']*price
                    qty = max(0, math.floor(min(c['full']-c['initial_qty'], cash/(price*(1+cost)),
                        max(0., .25*eq-notional)/price,
                        max(0., c['budget']-used)/(price*(.05+2.05*cost)))+1e-12))
                    why = 'FILLED' if qty > 0 else 'CASH_POSITION_OR_RISK_CAP'
                    near(o.used_risk, used)
                near(o.budget, c['budget'])
            if o.status != why:
                raise AssertionError(f'Unexpected order status {o.order_id}: {o.status}/{why}')
            near(o.quantity, qty if why == 'FILLED' else 0)
            match = buys[(buys.pair_id.eq(pid)) & buys.leg.eq(o.kind)]
            if why == 'FILLED':
                if len(match) != 1:
                    raise AssertionError('Missing/excess buy')
                f = next(match.itertuples())
                near(f.quantity, qty)
                near(f.price, price)
                apply_fill(f)
                held = {v['pair_id'] for v in inventory.values()}
                if len(held) > 8:
                    raise AssertionError('Position count')
                position_value = sum(v['quantity']*price for v in inventory.values() if v['pair_id'] == pid)
                if position_value > .25*eq+1e-7:
                    raise AssertionError('Entry position cap')
            elif len(match):
                raise AssertionError('Rejected order was filled')
        for f in fs[fs.phase.eq('INTRABAR')].itertuples():
            apply_fill(f)
        gross = sum(v['quantity']*float(frame.loc[v['pair_id'], 'close']) for v in inventory.values())
        near(mark.cash, cash, 'mark cash')
        near(mark.gross, gross, 'mark gross')
        near(mark.equity, cash+gross, 'mark equity')
        near(mark.positions, len({v['pair_id'] for v in inventory.values()}))
        near(mark.lots, len(inventory))
        reconstructed.append(cash+gross)
    if inventory or seen != list(range(len(fills))):
        raise AssertionError('Incomplete/unordered lifecycle')
    near(cash-4000, lots.net.sum(), 'final profit conservation')
    expected_times = []
    for r in calendar.itertuples():
        expected_times.extend(pd.date_range(r.market_open, r.market_close, freq='5min', inclusive='left')+pd.Timedelta(minutes=5))
    if list(marks.time) != expected_times:
        raise AssertionError('Missing calendar marks')
    report_rows = [r for r in READ(root/'report.json')['summaries'] if r['arm'] == arm and r['cost_bps'] == round(cost*10000)]
    start = 4000.
    for r in report_rows:
        values = marks.loc[marks.year.eq(r['year']), 'equity'].to_numpy()
        near(r['start_equity'], start)
        near(r['final_equity'], values[-1])
        near(r['return_pct'], 100*(values[-1]/start-1))
        levels = np.r_[start, values]
        near(r['max_drawdown_pct'], 100*(levels/np.maximum.accumulate(levels)-1).min())
        start = float(values[-1])
    levels = np.r_[4000., reconstructed]
    return dict(label=label, fills=len(fills), lots=len(lots), orders=len(orders), marks=len(marks),
        final_equity=cash, net=cash-4000., max_drawdown_pct=100*float((levels/np.maximum.accumulate(levels)-1).min()),
        adds=int(lots.leg.eq('ADD').sum()), status='PASS_RECONSTRUCTED')


def audit(root):
    if (root/'final-audit.json').exists():
        raise ValueError('Immutable audit')
    verify_hashes(Path('.'), READ(root/'protocol.json')['sources'])
    verify_hashes(root, READ(root/'prepared.json')['files'])
    verify_hashes(root, READ(root/'report.json')['files'])
    bars, candidates, calendar = [pd.read_parquet(root/n) for n in ['bars.parquet', 'candidates.parquet', 'calendar.parquet']]
    audit_candidates(root, bars, candidates)
    results = [audit_arm(root, f'{arm}-{bps}bps', bars, candidates, calendar) for bps in [8, 25] for arm in ARMS]
    verdict = 'EXPLORATORY_ONLY_NO_PROMOTION'
    atomic_json(root/'final-audit.json', dict(status='PASS_SHARED_CASH_RESEARCH_AUDIT',
        report_sha256=digest(root/'report.json'), qualified=len(candidates), results=results,
        verdict=verdict, note='Same assistant separate reconstruction, not independent human or native PAPER parity.'))
    print(READ(root/'final-audit.json'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    audit(p.parse_args().output)
