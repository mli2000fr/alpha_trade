"""Offline, shared-cash LONG H20 research. No database, API, broker or training.

This deliberately is NOT native PAPER execution parity. Immutable parent cohort;
full/half/half-plus-one winning add, integer shares, causal five-minute events.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_campaign import make_path, fresh_signals
from scripts.research.us_top10_intraday_breakout import qualify_day

PARENT = Path('artifacts/research/us_oracle_campaign/20261020-v1')
ARMS = ('FULL_BASE', 'HALF_CONTROL', 'HALF_ADD_ONE')
READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
LOG = logging.getLogger(__name__)
EPS = 1e-8


def prepare(root):
    if (root/'prepared.json').exists():
        verify_hashes(Path('.'), READ(root/'protocol.json')['sources'])
        verify_hashes(root, READ(root/'prepared.json')['files'])
        return
    if root.exists() and any(root.iterdir()):
        raise ValueError('Fresh output required; preparation is not silently restarted')
    parent_protocol = READ(PARENT/'protocol.json')
    verify_hashes(Path('.'), parent_protocol['sources'])
    verify_hashes(PARENT, READ(PARENT/'prepared.json')['files'])
    verify_hashes(PARENT, READ(PARENT/'report.json')['files'])
    snap = READ(PARENT/'snapshot-ready.json')
    verify_hashes(PARENT, snap['files'])
    if READ(PARENT/'final-audit.json')['status'] != 'PASS_EXPLORATORY_CAMPAIGN_AUDIT':
        raise ValueError('Unqualified parent')
    sources = [Path(__file__), Path('scripts/research/us_oracle_pyramiding_audit.py'),
        Path('tests/test_us_oracle_pyramiding.py'), Path('scripts/research/us_oracle_campaign.py'),
        Path('scripts/research/us_top10_intraday_breakout.py'),
        Path('scripts/research/us_concentrated_historical_tapes.py')]
    sources += [PARENT/n for n in ['protocol.json', 'prepared.json', 'snapshot-ready.json',
        'report.json', 'final-audit.json', 'selected.parquet', 'sessions.parquet', 'coverage.parquet']]
    protocol = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(p): digest(p) for p in sources}, parent=str(PARENT), arms=list(ARMS),
        hypothesis='One addition to an observed winner may outperform a full initial entry; no presumed benefit.',
        selection='Audited parent: frozen research CatBoost PATH_H20 OOS TOP10, admission before quality, common complete21-session SIP cohort. No replacement, rerank or use of old outcomes for signals. NOT production LightGBM.',
        sample='2024 has no qualified intraday campaigns and is NOT simulated as zero return. 2025/26 already examined: exploratory, survivor and full-path-quality selection biases.',
        initial_equity=4000., start='2025-01-01', end='2026-09-30', leverage=1., max_positions=8,
        max_position_weight=.25, campaign_risk=.02, sl=.05, trailing=.15, add_trigger=.05,
        costs_per_leg=[.0008, .0025], whole_shares=True,
        entry='First fresh LONG breakout of each qualified parent campaign: two completed5m closes above prior FULL-session high, earlier close at/inside. Execute next contiguous same-session open before expiry. First attempt only, even when rejected. No future-return filter.',
        full_quantity='At initial open: floor(min(2%equity/(price*(SL+2.05*cost)),25%equity/price,cash/(price*(1+cost)))). Freeze target and 2%equity risk budget. No leverage, at most8 held symbols. Half arms use floor(full_quantity/2). No minimum notional; integer0 rejects.',
        add='HALF_ADD_ONE: two consecutive completed same-session closes >=initial entry*1.05 while original lot alive; next contiguous open before expiry. One queued attempt only, also consumed on refusal. At add open require original still alive and price>=threshold. Quantity<=frozen full target minus original quantity, remaining cash/25%current-equity cap and remaining frozen risk. No averaging down.',
        risk='Addition risk budget does NOT grow with equity or gains. Used risk: prior realized lot losses + sum(qty*(max(entry-knownStop,0)+cost*(entry+knownStop))) over active lots. New qty reserve=price*(.05+2.05*cost). No profit recycling. This is planned risk, not a guaranteed loss bound on gaps.',
        protection='Each lot has independent initialSL5%, trailing15% of prior completed-bar high. No breakeven modification, no TP, common campaign expiry at OPEN of last5m bar of J+20. Waiting and addition do not reset horizon. Gap through known stop at actual open; intrabar stop conservatively recorded at bar END (interval censored). Current high cannot tighten same-bar stop.',
        ordering='All held gap/expiry sells at current opens; then original orders before adds, sorted by signal date/rank/symbol/id; then intrabar stops; update remaining stops after bars complete; queue additions; close marks. Intrabar sale proceeds cannot finance an earlier same-bar open. Opening sizing values held names using only simultaneous current opens.',
        ledger='One continuous USD cash account, cash>=0, buys debit notional+cost, sells credit notional-cost, equity=cash+held close value.25%position cap only on fills, drift allowed. Annual equity2026 begins at final2025 mark incl carried positions, NOT reset4000. Campaign win/loss by final-exit year, not per lot.',
        stress='25bps is a FULL re-simulation of sizing, cash and decisions, not an adjustment of the base fills. Costs hypothetical total per-leg friction, NOT verified NBBO/commissions. No extra fixed commission.',
        controls='FULL_BASE vs HALF_ADD_ONE same frozen planned-risk ceiling at each initial decision, not necessarily same spent risk. HALF_CONTROL isolates reduced sizing but capital feedback means later initial fills need not match across accounts.',
        restrictions='No native portfolio risk engine, sector/correlation/regime/circuitbreaker limits, dividends/taxes/corporate-action cashflows, margin, quotes/halts/depth/fills proof. Research shared-cash simulation, NOT full PAPER/live parity. Parent price-basis audit is internal consistency, not an independent price vendor proof.',
        validation='Separate stop/quantity/cash/equity reconstruction + unit tests, same assistant not independent human. No untouched holdout or statistical promotion; no selecting best arm byyear.',
        sql_writes=False, provider_calls=False, llm_calls=False, training=False, orders=False,
        production_changes=False)
    root.mkdir(parents=True)
    atomic_json(root/'protocol.json', protocol)  # Before any results or portfolio replay.
    schedule = pd.read_parquet(PARENT/'sessions.parquet')
    days = pd.DatetimeIndex(schedule.date)
    cov = pd.read_parquet(PARENT/'coverage.parquet')
    cohort = cov[cov.status.eq('OK')].copy()
    raw = pd.concat([pd.read_parquet(PARENT/n) for n in snap['files']], ignore_index=True)
    groups = dict(tuple(raw.groupby(['symbol', 'trade_date'], sort=False)))
    del raw
    sched = schedule.set_index('date')
    rows, candidates = [], []
    for r in cohort.itertuples():
        i = days.get_loc(r.date)
        frames = []
        for day in days[i:i+21]:
            q, why = qualify_day(groups.get((r.symbol, day)), *sched.loc[day, ['market_open', 'market_close']])
            if q is None:
                raise ValueError(f'Changed parent qualification: {r.pair_id}/{day}/{why}')
            frames.append(q)
        path = make_path(frames)
        events = [(idx, side) for idx, side in fresh_signals(path) if side == 1 and idx < len(path)-1]
        candidate = dict(pair_id=int(r.pair_id), symbol=r.symbol, date=r.date, rank=int(r.rank),
            year=int(r.year), expiry=path.bar_timestamp.iloc[-1],
            entry_index=events[0][0] if events else -1,
            entry_time=path.bar_timestamp.iloc[events[0][0]] if events else pd.NaT)
        candidates.append(candidate)
        path['pair_id'] = int(r.pair_id)
        path['bar_index'] = np.arange(len(path))
        rows.append(path[['pair_id', 'bar_index', 'bar_timestamp', 'bar_end_timestamp',
            'session_offset', 'open', 'high', 'low', 'close']])
    pd.concat(rows, ignore_index=True).to_parquet(root/'bars.parquet', index=False)
    pd.DataFrame(candidates).to_parquet(root/'candidates.parquet', index=False)
    calendar = schedule[schedule.date.between(protocol['start'], protocol['end'])]
    calendar.to_parquet(root/'calendar.parquet', index=False)
    cov.to_parquet(root/'coverage.parquet', index=False)
    atomic_json(root/'prepared.json', dict(qualified=len(cohort),
        signals=sum(c['entry_index'] >= 0 for c in candidates),
        files={n: digest(root/n) for n in ['bars.parquet', 'candidates.parquet', 'calendar.parquet', 'coverage.parquet']}))
    LOG.info('Prepared %d qualified campaigns, %d LONG signals', len(cohort), sum(c['entry_index'] >= 0 for c in candidates))


@dataclass(frozen=True)
class Bar:
    pair_id: int
    bar_index: int
    bar_timestamp: pd.Timestamp
    bar_end_timestamp: pd.Timestamp
    session_offset: int
    open: float
    high: float
    low: float
    close: float


def tapes(bars, candidates, calendar):
    bytime = defaultdict(dict)
    bypair = defaultdict(list)
    for r in bars.itertuples(index=False):
        b = Bar(**r._asdict())
        bytime[b.bar_timestamp][b.pair_id] = b
        bypair[b.pair_id].append(b)
    starts = defaultdict(list)
    meta = {int(r.pair_id): r._asdict() for r in candidates.itertuples(index=False)}
    for r in meta.values():
        if r['entry_index'] >= 0:
            starts[r['entry_time']].append(r['pair_id'])
    timeline = []
    for r in calendar.itertuples():
        timeline.extend(pd.date_range(r.market_open, r.market_close, freq='5min', inclusive='left'))
    for path in bypair.values():
        path.sort(key=lambda b: b.bar_index)
        if [b.bar_index for b in path] != list(range(len(path))):
            raise ValueError('Non contiguous campaign index')
    return dict(bytime=bytime, bypair=bypair, starts=starts, meta=meta, timeline=timeline)


def planned_full_quantity(equity, cash, price, cost):
    return max(0, int(np.floor(min(.02*equity/(price*(.05+2.05*cost)),
        .25*equity/price, cash/(price*(1+cost))) + 1e-12)))


def annual_summary(marks, lots, orders, fills):
    summaries = []
    start = 4000.
    for year, g in marks.groupby('year', sort=True):
        end = float(g.equity.iloc[-1])
        levels = np.r_[start, g.equity.to_numpy(float)]
        dd = levels/np.maximum.accumulate(levels)-1
        exits = lots[pd.to_datetime(lots.exit_time, utc=True).dt.year.eq(year)] if len(lots) else lots
        campaigns = exits.groupby('pair_id').agg(net=('net', 'sum')) if len(exits) else pd.DataFrame(columns=['net'])
        # Here every campaign expires within20sessions. For campaigns crossing
        # Dec31, avoid counting a partial campaign when only one lot has exited.
        if len(exits):
            complete = lots.groupby('pair_id').exit_time.max()
            ids = complete[pd.to_datetime(complete, utc=True).dt.year.eq(year)].index
            campaigns = lots[lots.pair_id.isin(ids)].groupby('pair_id').agg(net=('net', 'sum'))
        fy = fills[pd.to_datetime(fills.bar_time, utc=True).dt.year.eq(year)] if len(fills) else fills
        oy = orders[pd.to_datetime(orders.time, utc=True).dt.year.eq(year)] if len(orders) else orders
        n = len(campaigns)
        summaries.append(dict(year=int(year), start_equity=start, final_equity=end, net=end-start,
            return_pct=100*(end/start-1), max_drawdown_pct=100*float(dd.min()),
            winning_campaigns=int(campaigns.net.gt(EPS).sum()), losing_campaigns=int(campaigns.net.lt(-EPS).sum()),
            flat_campaigns=int(campaigns.net.abs().le(EPS).sum()), completed_campaigns=n,
            campaign_win_pct=100*float(campaigns.net.gt(EPS).mean()) if n else None,
            closed_campaign_gains=float(campaigns.net.clip(lower=0).sum()),
            closed_campaign_losses=float(campaigns.net.clip(upper=0).sum()),
            fees=float(fy.fee.sum()) if len(fy) else 0.,
            initial_buys=int((fy.side.eq('BUY') & fy.leg.eq('INITIAL')).sum()) if len(fy) else 0,
            add_buys=int((fy.side.eq('BUY') & fy.leg.eq('ADD')).sum()) if len(fy) else 0,
            order_rejections=int(oy.status.ne('FILLED').sum()) if len(oy) else 0,
            mean_invested_pct=100*float((g.gross/g.equity).mean()),
            max_invested_pct=100*float((g.gross/g.equity).max()),
            mean_positions=float(g.positions.mean()), max_positions=int(g.positions.max()),
            min_cash=float(g.cash.min()),
            note='Campaign realized gains/losses by final exit year; annual PnL includes carried/unrealized changes.'))
        start = end
    return summaries


def simulate(tape, arm, cost):
    if arm not in ARMS or cost not in (.0008, .0025):
        raise ValueError('Unfrozen arm/cost')
    cash = 4000.
    active, campaigns, pending = {}, {}, defaultdict(list)
    fills, orders, closed, marks = [], [], [], []
    seq = 0

    def held_equity(prices):
        return cash + sum(lot['quantity']*prices[lot['pair_id']] for lot in active.values())

    def order(pid, ts, kind, status, **details):
        orders.append(dict(order_id=len(orders), pair_id=pid, symbol=tape['meta'][pid]['symbol'],
            time=ts, kind=kind, status=status, **details))

    def transact(lot, bar, side, price, reason, phase):
        nonlocal cash, seq
        quantity = lot['quantity']
        fee = quantity*price*cost
        cash += (quantity*price-fee) if side == 'SELL' else -(quantity*price+fee)
        ts = bar.bar_end_timestamp if phase == 'INTRABAR' else bar.bar_timestamp
        fills.append(dict(sequence=seq, lot_id=lot['lot_id'], pair_id=lot['pair_id'],
            symbol=tape['meta'][lot['pair_id']]['symbol'], leg=lot['leg'], side=side,
            time=ts, bar_time=bar.bar_timestamp, bar_index=bar.bar_index, price=price,
            quantity=quantity, fee=fee, reason=reason, phase=phase, cash_after=cash))
        seq += 1
        if side == 'SELL':
            net = quantity*(price-lot['entry_price'])-lot['entry_fee']-fee
            closed.append(dict(**lot, exit_price=price, exit_time=ts, exit_bar_index=bar.bar_index,
                exit_reason=reason, exit_fee=fee, net=net,
                gross=quantity*(price-lot['entry_price'])))
            campaigns[lot['pair_id']]['realized_losses'] += max(0., -net)
            del active[lot['lot_id']]
        if cash < -EPS:
            raise AssertionError('Negative cash')

    for ts in tape['timeline']:
        bars = tape['bytime'].get(ts, {})
        pids = {v['pair_id'] for v in active.values()}
        if not pids.issubset(bars):
            raise ValueError(f'Missing held bars at {ts}: {pids-set(bars)}')
        opens = {pid: b.open for pid, b in bars.items()}
        # All current opens, never current highs/closes, are available for sizing.
        for lot in list(active.values()):
            b = bars[lot['pair_id']]
            if b.open <= lot['stop']+abs(lot['stop'])*1e-12:
                transact(lot, b, 'SELL', b.open, 'GAP_STOP', 'OPEN')
            elif ts == tape['meta'][lot['pair_id']]['expiry']:
                transact(lot, b, 'SELL', b.open, 'EXPIRY', 'OPEN')

        def priority(pid):
            m = tape['meta'][pid]
            return (m['date'], m['rank'], m['symbol'], pid)

        for pid in sorted(tape['starts'].get(ts, []), key=priority):
            b = bars[pid]
            m = tape['meta'][pid]
            eq = held_equity(opens)
            if pid in campaigns:
                raise AssertionError('Duplicate initial attempt')
            campaigns[pid] = dict(budget=.02*eq, realized_losses=0., add_attempted=False,
                initial_quantity=0, full_quantity=0, entry_price=b.open, entry_index=b.bar_index)
            c = campaigns[pid]
            held = {v['pair_id'] for v in active.values()}
            symbols = {tape['meta'][x]['symbol'] for x in held}
            full = planned_full_quantity(eq, cash, b.open, cost)
            qty = full if arm == 'FULL_BASE' else full//2
            c.update(full_quantity=full, initial_quantity=qty)
            why = ('DUPLICATE_HELD_SYMBOL' if m['symbol'] in symbols else
                'MAX_POSITIONS' if len(held) >= 8 else 'ZERO_WHOLE_SHARES' if qty <= 0 else None)
            if why:
                order(pid, ts, 'INITIAL', why, equity_before=eq, cash_before=cash,
                    full_quantity=full, quantity=0, budget=c['budget'])
                continue
            lot = dict(lot_id=f'{pid}-0', pair_id=pid, leg='INITIAL', quantity=qty,
                entry_time=ts, entry_bar_index=b.bar_index, entry_price=b.open,
                entry_fee=qty*b.open*cost, stop=b.open*.95, peak=b.open,
                budget=c['budget'], full_quantity=full)
            order(pid, ts, 'INITIAL', 'FILLED', equity_before=eq, cash_before=cash,
                full_quantity=full, quantity=qty, budget=c['budget'])
            active[lot['lot_id']] = lot
            transact(lot, b, 'BUY', b.open, 'FIRST_LONG_BREAKOUT', 'OPEN')

        for pid in sorted(pending.pop(ts, []), key=priority):
            c = campaigns[pid]
            original = active.get(f'{pid}-0')
            b = bars[pid]
            eq = held_equity(opens)
            if original is None or b.open+EPS < c['entry_price']*1.05:
                order(pid, ts, 'ADD', 'CANCEL_ORIGINAL_EXITED' if original is None else 'CANCEL_GAP_BELOW_TRIGGER',
                    quantity=0, budget=c['budget'], equity_before=eq, cash_before=cash)
                continue
            lots = [v for v in active.values() if v['pair_id'] == pid]
            used = c['realized_losses'] + sum(v['quantity']*(max(v['entry_price']-v['stop'], 0.)
                +cost*(v['entry_price']+v['stop'])) for v in lots)
            notional = sum(v['quantity']*b.open for v in lots)
            remaining = max(0., c['budget']-used)
            qty = max(0, int(np.floor(min(c['full_quantity']-c['initial_quantity'],
                cash/(b.open*(1+cost)), max(0., .25*eq-notional)/b.open,
                remaining/(b.open*(.05+2.05*cost)))+1e-12)))
            if qty <= 0:
                order(pid, ts, 'ADD', 'CASH_POSITION_OR_RISK_CAP', quantity=0,
                    budget=c['budget'], used_risk=used, equity_before=eq, cash_before=cash)
                continue
            lot = dict(lot_id=f'{pid}-1', pair_id=pid, leg='ADD', quantity=qty,
                entry_time=ts, entry_bar_index=b.bar_index, entry_price=b.open,
                entry_fee=qty*b.open*cost, stop=b.open*.95, peak=b.open,
                budget=c['budget'], full_quantity=c['full_quantity'])
            order(pid, ts, 'ADD', 'FILLED', quantity=qty, full_quantity=c['full_quantity'],
                budget=c['budget'], used_risk=used, equity_before=eq, cash_before=cash)
            active[lot['lot_id']] = lot
            transact(lot, b, 'BUY', b.open, 'TWO_CLOSES_PLUS_5PCT', 'OPEN')

        # Sales inside this bar happen AFTER all opening orders, never fund them.
        for lot in list(active.values()):
            b = bars[lot['pair_id']]
            if b.low <= lot['stop']+abs(lot['stop'])*1e-12:
                transact(lot, b, 'SELL', lot['stop'], 'STOP', 'INTRABAR')
            else:
                lot['peak'] = max(lot['peak'], b.high)
                lot['stop'] = max(lot['entry_price']*.95, lot['peak']*.85)

        if arm == 'HALF_ADD_ONE':
            for pid in sorted({v['pair_id'] for v in active.values()}):
                c = campaigns[pid]
                if c['add_attempted'] or f'{pid}-0' not in active:
                    continue
                b = bars[pid]
                path = tape['bypair'][pid]
                k = b.bar_index
                # Both closes completed after purchase, no overnight pairing.
                if k <= c['entry_index'] or k+1 >= len(path)-1:
                    continue
                prev, nxt = path[k-1], path[k+1]
                if (prev.session_offset == b.session_offset == nxt.session_offset
                    and prev.bar_end_timestamp == b.bar_timestamp
                    and b.bar_end_timestamp == nxt.bar_timestamp
                    and min(prev.close, b.close)+EPS >= c['entry_price']*1.05):
                    c['add_attempted'] = True
                    pending[nxt.bar_timestamp].append(pid)

        gross = sum(v['quantity']*bars[v['pair_id']].close for v in active.values())
        eq = cash+gross
        if cash < -EPS or gross > eq+EPS or len({v['pair_id'] for v in active.values()}) > 8:
            raise AssertionError('Capital/exposure invariant failed')
        marks.append(dict(time=ts+pd.Timedelta(minutes=5), year=ts.year, cash=cash, gross=gross,
            equity=eq, positions=len({v['pair_id'] for v in active.values()}), lots=len(active)))
    if active or pending:
        raise ValueError('Incomplete portfolio lifecycle')
    return {key: pd.DataFrame(value) for key, value in
        [('marks', marks), ('lots', closed), ('orders', orders), ('fills', fills)]}


def replay(root):
    prepare(root)
    if (root/'report.json').exists():
        raise ValueError('Immutable completed result; use another output directory')
    tape = tapes(pd.read_parquet(root/'bars.parquet'), pd.read_parquet(root/'candidates.parquet'),
        pd.read_parquet(root/'calendar.parquet'))
    summaries, files = [], {}
    for cost in [.0008, .0025]:
        for arm in ARMS:
            label = f'{arm}-{int(round(cost*10000))}bps'
            out = root/label
            out.mkdir(exist_ok=False)
            result = simulate(tape, arm, cost)
            for name, frame in result.items():
                dest = out/f'{name}.parquet'
                frame.to_parquet(dest, index=False)
                files[str(dest.relative_to(root))] = digest(dest)
            annual = annual_summary(**{k: result[k] for k in ['marks', 'lots', 'orders', 'fills']})
            summaries.extend([dict(arm=arm, cost_bps=int(round(cost*10000)), **v) for v in annual])
            LOG.info('%s final=%.2f lots=%d adds=%d', label, result['marks'].equity.iloc[-1],
                len(result['lots']), sum(result['lots'].leg.eq('ADD')) if len(result['lots']) else 0)
            atomic_json(root/'progress.json', dict(status='REPLAYING', completed=len(summaries)//2, total=6, current=label))
    pd.DataFrame(summaries).to_csv(root/'annual-summary.csv', index=False)
    files['annual-summary.csv'] = digest(root/'annual-summary.csv')
    atomic_json(root/'report.json', dict(status='COMPLETED_PENDING_AUDIT', summaries=summaries, files=files,
        verdict='NO_PROMOTION_PENDING_AUDIT', note='Shared cash research, NOT native PAPER parity. No virgin holdout.'))
    atomic_json(root/'progress.json', dict(status='COMPLETED_PENDING_AUDIT', completed=6, total=6))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=['prepare', 'replay'], required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    {'prepare': prepare, 'replay': replay}[args.phase](args.output)


if __name__ == '__main__':
    main()
