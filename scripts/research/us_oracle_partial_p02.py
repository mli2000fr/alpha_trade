"""P02: existing two-close Winner entry plus ONE half exit at +10%, offline.

Frozen local cohort, native sizing/cash/B4 with explicit research-only partial
adapter. No SQL, provider, training, broker or production config mutation.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import math

import numpy as np
import pandas as pd

from common.config_loader import load_config
from common.trading_costs import TradingCostModel
from common.winner_pyramiding import WinnerPyramidingConfig
from risk_management.models import PriceInfo
from scripts.research import us_oracle_compression_p01 as parent
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

READ = parent.READ
REFERENCE = parent.OUTPUT
OUTPUT = Path('artifacts/research/us_oracle_partial_p02/20261022-v1')
ARMS = ('WINNER', 'P02')
FEES = (8,25)
RULE = dict(partial_trigger_pct=.10, partial_fraction=.5, stop_pct=.07, trailing_pct=.15,
            horizon_sessions=20, initial_position_fraction=.5, confirmation_bars=2)


def partial_quantity(initial_quantity):
    return math.floor(initial_quantity*RULE['partial_fraction']) if initial_quantity >= 2 else 0


def validate_config(raw):
    policy = WinnerPyramidingConfig(**raw)
    wanted = dict(initial_position_fraction=.5, reinforcement_enabled=False, confirmation_bars=2,
        stop_loss_pct=.07, take_profit_pct=None, trailing_stop_pct=.15, horizon_sessions=20, entry_valid_sessions=20)
    if any(getattr(policy,k)!=v for k,v in wanted.items()):
        raise ValueError('Current Winner policy differs from predeclared P02 reference')
    return policy


class PartialLedger(parent.CentLedger):
    """Partial lots book through native cash/fee exit, preserving the remainder.

    Entry flow/cost prorated, no second entry and no doubled fee basis. A
    fragment does NOT close the original campaign or update its loss streak.
    At final exit the tracker receives aggregate campaign PnL exactly once.
    """
    def __init__(self, *args, partial_enabled=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.partial_enabled = partial_enabled
        self.books = {}
        self.partial_events = []

    def enter(self, symbol, side, price_info, **kwargs):
        if self.phase!='OPEN': raise ValueError('Entry requires OPEN phase; no intrabar proceeds retroactively')
        opened = super().enter(symbol, side, price_info, **kwargs)
        if opened and self.partial_enabled:
            p = self.state.positions[symbol]
            self.books[symbol] = dict(initial_qty=int(p.quantity), realized=0., done=False,
                target=round(p.entry_price*(1+RULE['partial_trigger_pct']),2))
        return opened

    def close(self, symbol, price, reason, *, phase='OPEN'):
        if not self.partial_enabled:
            return super().close(symbol,price,reason,phase=phase)
        tracker = deepcopy(self.engine._concentration_loss_tracker)
        book = self.books[symbol]
        t = super().close(symbol,price,reason,phase=phase)
        # Native final-fragment PnL alone must not classify a profitable complete
        # campaign as a loss after its earlier profit-taking leg.
        self.engine._concentration_loss_tracker = tracker
        tracker.record(symbol, book['realized']+t['pnl'], self.day.date(), side='buy')
        t.update(leg_role='FINAL', initial_quantity=book['initial_qty'], remaining_quantity=0)
        del self.books[symbol]
        return t

    def close_partial(self, symbol, price, *, phase):
        book = self.books[symbol]
        if book['done']: return False
        q = partial_quantity(book['initial_qty'])
        if q == 0:
            book['done'] = True
            self.partial_events.append(dict(time=self.now,symbol=symbol,status='ONE_SHARE_NO_PARTIAL'))
            return False
        original = deepcopy(self.state.positions[symbol])
        if not 0 < q < original.quantity: raise ValueError('Partial must preserve a positive remainder')
        meta = dict(self.live_meta[symbol]); fraction = q/original.quantity
        fragment = replace(original, quantity=q, entry_cost=original.entry_cost*fraction,
                           entry_cash_flow=original.entry_cash_flow*fraction)
        tracker = deepcopy(self.engine._concentration_loss_tracker)
        self.state.positions[symbol] = fragment
        # Deliberately bypass this subclass's FINAL method. Native fee/cash exit
        # is retained; synthetic fragment is replaced by the actual remainder.
        t = super().close(symbol,price,'PARTIAL_TP10',phase=phase)
        remaining = replace(original, quantity=original.quantity-q,
            entry_cost=original.entry_cost-fragment.entry_cost,
            entry_cash_flow=original.entry_cash_flow-fragment.entry_cash_flow)
        self.state.positions[symbol] = remaining
        self.live_meta[symbol] = meta
        self.engine._concentration_loss_tracker = tracker
        book['realized'] += t['pnl']; book['done'] = True
        t.update(leg_role='PARTIAL', initial_quantity=book['initial_qty'], remaining_quantity=int(remaining.quantity))
        self.partial_events.append(dict(time=t['exit_timestamp'],symbol=symbol,status='PARTIAL_FILLED',
            quantity=q,remaining_quantity=int(remaining.quantity),price=price,phase=phase,
            due_open=meta['expiry'],peak_preserved=remaining.peak_high))
        return True

    def resolve_open(self, *, expiry_symbols=None):
        if not self.partial_enabled: return super().resolve_open(expiry_symbols=expiry_symbols)
        self._healthy()
        if self.phase!='OPEN': raise ValueError('Opening guards require OPEN phase')
        due = self.expiry_symbols if expiry_symbols is None else expiry_symbols
        for s,p in list(self.state.positions.items()):
            op = self.prices[s]
            if op <= self.known_stop(s):
                self.close(s,op,'GAP_STOP')
                continue
            book = self.books[s]
            if not book['done'] and op >= book['target']:
                self.close_partial(s,book['target'],phase='OPEN')
            if s in due: self.close(s,op,'EXPIRY')

    def observe_bar(self, bars, *, expiry_symbols=()):
        if not self.partial_enabled: return super().observe_bar(bars,expiry_symbols=expiry_symbols)
        self._healthy()
        if self.phase!='OPEN' or set(self.state.positions)-set(bars): raise ValueError('Unqualified bar phase/coverage')
        for s,a in bars.items():
            if (len(a)!=4 or not all(math.isfinite(x) and x>0 for x in a)
                    or a[1]<max(a) or a[2]>min(a) or a[0]!=self.prices[s]):
                raise ValueError('Invalid observed OHLC')
        self.resolve_open(expiry_symbols=self.expiry_symbols|set(expiry_symbols))
        for s,p in list(self.state.positions.items()):
            op,hi,lo,cl = bars[s]
            # Without tick ordering, the adverse standing stop wins a collision
            # against the partial target. Never invent TP first from a high.
            if lo <= self.known_stop(s):
                self.close(s,self.known_stop(s),'initial_stop',phase='INTRABAR')
                continue
            book = self.books[s]
            if not book['done'] and hi >= book['target']:
                self.close_partial(s,book['target'],phase='INTRABAR')
            if s in self.state.positions:
                p = self.state.positions[s]
                p.peak_high,p.trough_low = max(p.peak_high,hi),min(p.trough_low,lo)
        self.prices = {s:float(a[3]) for s,a in bars.items()}
        self.phase = 'INTRABAR'; self.last_bar_end = self.now+pd.Timedelta(minutes=5)
        return self.equity()


def scalar_legs(path, entry, expiry, quantity, partial, mandatory=None):
    """Separate chronological share-lot arithmetic, also used by the audit.

    No native/shared exit function. Retains remaining shares for annual MTM.
    """
    price = float(path.open.iloc[entry]); peak = price; remaining = quantity
    target = round(price*(1+.10),2); qhalf = quantity//2; done = not partial or qhalf==0
    exits = []
    for i,r in enumerate(path.iloc[entry:].itertuples(),entry):
        stop = max(round(price*(1-.07),2),round(peak*(1-.15),2))
        if r.open<=stop:
            exits.append(dict(index=i,quantity=remaining,price=float(r.open),phase='OPEN',role='FINAL'));remaining=0;break
        if not done and r.open>=target:
            exits.append(dict(index=i,quantity=qhalf,price=target,phase='OPEN',role='PARTIAL'));remaining-=qhalf;done=True
        if (mandatory is not None and r.bar_timestamp==mandatory) or r.bar_timestamp>=expiry:
            exits.append(dict(index=i,quantity=remaining,price=float(r.open),phase='OPEN',role='FINAL'));remaining=0;break
        if r.low<=stop:
            exits.append(dict(index=i,quantity=remaining,price=stop,phase='INTRABAR',role='FINAL'));remaining=0;break
        if not done and r.high>=target:
            exits.append(dict(index=i,quantity=qhalf,price=target,phase='INTRABAR',role='PARTIAL'));remaining-=qhalf;done=True
        peak=max(peak,r.high)
    return exits, remaining


def prepare(root):
    root=Path(root)
    if root.exists(): raise ValueError('Fresh immutable output required')
    report=READ(REFERENCE/'report.json');verify_hashes(REFERENCE,report['files'])
    review=READ(REFERENCE/'final-audit.json')
    if review['status']!='PASS_P01_SEPARATE_ARITHMETIC_AND_PORTFOLIO_AUDITS' or review['primary_report_sha256']!=digest(REFERENCE/'report.json'):
        raise ValueError('Validated frozen Winner reference required')
    config=load_config()['winner_pyramiding'];validate_config(config)
    source_paths=[Path(__file__),Path('scripts/research/us_oracle_partial_p02_audit.py'),
        Path('tests/test_us_oracle_partial_p02.py'),Path('doc/ml/oracle_partial_p02_20261022.md'),
        Path('risk_management/concentration.py'),
        Path('config.yaml'),REFERENCE/'report.json',REFERENCE/'final-audit.json']
    sources=dict(READ(REFERENCE/'protocol.json')['sources'])
    sources.update({str(p):digest(p) for p in source_paths})
    root.mkdir(parents=True)
    atomic_json(root/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources=sources,reference=str(REFERENCE),rule=RULE,arms=ARMS,fees_bps_per_leg=FEES,
        configured_winner=config,production_enabled_unchanged=config['enabled'],
        entry='Exact WINNER signals from verified P01v2; no P01 compression gate. Two consecutive completed regular5m '
            'closes above previous raw-session high, fresh cross, next contiguous open. Not simply two rising closes or fixed5min wait.',
        partial='Standing one-off target at round(actualentry*1.10,2). Sell floor(initial_shares/2), keep rest. '
            'One share => no partial. No BE stop, no loosening, no add/reentry/horizon reset. '
            'Gap favourable receives limit only, stop gap first, intrabar stop/TP collision: stop first on all remaining shares. '
            'Intrabar proceeds not available at preceding samebar open. Sell costs paid per filled notional.',
        accounting='Native exit cash/fee logic on prorated entry flow/cost. Restore remainder original peak/entry/expiry. '
            'Loss streak recorded once on total campaign PnL at final exit, never per fragment. '
            'B4 sees actual remaining shares, realized cash and unrealized mark. Compare campaigns not sell-leg win rates.',
        unchanged='Annual4000USD,1x gross admission cap, HALF target, SL7/TR15/no fullTP,20holding sessions thenOPEN21, '
            'same native sizing/constraints/B4DD15 and fixed prior-SPY regime. Fee8and25bps/leg. '
            'Baseline must exactly reproduce all4sealed Winner tapes and metrics before conclusions.',
        evaluation='Only50%@+10%, no optimization or combined filter. Per-entry unit paths, conservative nonoverlapOracleJ40, '
            'portfolio cash/reinvestment actual quantity changes. 2025/2026 already seen, not pristine holdout. '
            'No success claim from higher winner fraction alone.',
        criteria=dict(min_nonoverlap_per_year=30,min_partial_touches_per_year=10,
            positive_net_portfolio_increment_both_years_both_fees=True,
            dd_not_worse_both_years_normal_fees=True,
            positive_unit_increment_both_years_stress=True,monthly_cluster_lower95_gt_zero=True,
            minimum_months=6,draws=2000,seed=731),
        limitations=READ(REFERENCE/'protocol.json')['limitations']+[
            'Same200common campaigns/69symbols after inherited P01coverage exclusions, not whole dailyTOP10.',
            'Research partial adapter, no claim full production partial-order/broker parity.',
            'Annual resets/MTM of open positions, not one continuous multi-year account.',
            'Friction per notional, no historical order minimum commissions or queue/fill quotes.'],
        training=False,sql_writes=False,provider_calls=False,broker_calls=False,production_changes=False,full_live_parity=False))
    atomic_json(root/'progress.json',dict(status='PREPARED',completed=0,total=8))


def make_tape(groups,schedule,signals,year):
    calendar=schedule[schedule.date.dt.year.eq(year)&schedule.date.le(parent.END)].copy()
    pertime=defaultdict(dict);by_symbol={}
    for (s,d),g in groups.items():
        if d.year!=year or d>parent.END: continue
        by_symbol.setdefault(s,[]).append(g)
        for r in g.itertuples(): pertime[r.bar_timestamp][s]=(r.open,r.high,r.low,r.close)
    timeline=[(t,r.date,t==r.market_close-pd.Timedelta(minutes=5)) for r in calendar.itertuples()
        for t in pd.date_range(r.market_open,r.market_close-pd.Timedelta(minutes=5),freq='5min')]
    symbols={s:pd.concat(frames).sort_values('bar_timestamp').reset_index(drop=True) for s,frames in by_symbol.items()}
    eligible=signals[signals.year.eq(year)].sort_values(['timestamp','rank','symbol','pair_id'])
    return dict(calendar=calendar,timeline=timeline,bars=[pertime[t] for t,_,_ in timeline],
        candidates=eligible,paths={int(r.pair_id):symbols[r.symbol] for r in eligible.itertuples()})


def campaigns_from_legs(trades,opened):
    active={int(r['pair_id']) for r in opened};rows=[]
    if trades.empty: return pd.DataFrame(columns=['pnl','net_return_pct','holding_sessions','holding_calendar_days'])
    for pid,g in trades.groupby('pair_id',sort=False):
        if int(pid) in active: continue
        last=g.sort_values(['exit_timestamp','exit_bar']).iloc[-1].to_dict()
        q=int(g.quantity.sum());p=float(g.entry_price.iloc[0]);pnl=float(g.pnl.sum())
        last.update(quantity=q,qty=q,pnl=pnl,net_return_pct=100*pnl/(q*p),
            exit_price=float((g.quantity*g.exit_price).sum()/q),exit_legs=len(g),
            partial_exits=int(g.exit_reason.eq('PARTIAL_TP10').sum()))
        rows.append(last)
    return pd.DataFrame(rows)


def run_case(root,arm,year,fee,tape):
    out=root/f'{arm}-fee{fee}'/'cases'/str(year);out.mkdir(parents=True)
    parent.risk.PROFILE=READ(parent.REFERENCE/'production-risk.json')
    parent.risk.REGIMES={r.date:dict(source_date=r.source_date,regime=None if pd.isna(r.regime) else str(r.regime))
        for r in pd.read_parquet(parent.REFERENCE/'risk-regimes.parquet').itertuples()}
    parent.risk.ACTIVE_OUTPUT=out
    costs=replace(TradingCostModel(),slippage_bps=fee-6.)
    if not np.isclose(costs.per_leg_cost_pct,fee/10000): raise ValueError('Fee mismatch')
    ledger=PartialLedger(tape['calendar'],sl=.07,trailing=.15,tp=None,costs=costs,partial_enabled=arm=='P02')
    ctx={(r.symbol,r.date):r for r in pd.read_parquet(parent.REFERENCE/'prior-context.parquet').itertuples()}
    entries=defaultdict(list)
    for r in tape['candidates'].itertuples(): entries[r.timestamp].append(r)
    marks=[];blocked_day=None
    for i,((ts,day,last),bars) in enumerate(zip(tape['timeline'],tape['bars'])):
        ledger.bar_number=i
        due={s for s,m in ledger.live_meta.items() if ts>=m['expiry']}
        ledger.begin_bar(ts,{s:a[0] for s,a in bars.items()},expiry_symbols=due)
        if ledger.maintenance_pending and ts==ledger.calendar.at[day,'market_open']:
            for s in list(ledger.state.positions): ledger.close(s,ledger.prices[s],'MAINTENANCE_NEXT_OPEN')
            ledger.maintenance_pending=False;blocked_day=day
        ledger.resolve_open()
        for r in entries.get(ts,[]):
            c=ctx.get((r.symbol,day))
            if blocked_day==day or c is None or not np.isfinite([c.atr,c.adv]).all():
                ledger.audit.append(dict(time=ts,symbol=r.symbol,status='BLOCKED',reasons=['MAINTENANCE_OR_PRIOR_CONTEXT']));continue
            info=PriceInfo(r.symbol,float(r.signal_close),float(c.atr),price_asof_date=day.date(),
                atr_asof_date=c.atr_date.date(),adv_usd=float(c.adv))
            ledger.entry_context=dict(pair_id=int(r.pair_id),oracle_date=r.oracle_date,rank=int(r.rank),expiry=r.due_open)
            ledger.enter(r.symbol,'buy',info,sector='RESEARCH_NO_SECTOR_CAP',signal_time=ts,quantity_fraction=.5,selection_rank=int(r.rank))
        eq=ledger.observe_bar(bars)
        if last: eq=ledger.finish_day()
        marks.append(dict(time=ts+pd.Timedelta(minutes=5),equity=eq,gross=ledger.gross(),
            cash=ledger.state.settled_cash,unsettled=ledger.state.unsettled_cash,interest=ledger.interest))
    trades=pd.DataFrame(ledger.state.closed_trades)
    if trades.empty: trades=pd.DataFrame(columns=['symbol','pnl','net_return_pct','holding_sessions','holding_calendar_days'])
    opened=[dict(symbol=s,side='buy',qty=p.quantity,entry_price=p.entry_price,mark=ledger.prices[s],
        borrow_accrued_usd=0.,unrealized_pnl_usd=p.quantity*(ledger.prices[s]-p.entry_price)-p.quantity*p.entry_price*costs.per_leg_cost_pct,
        **ledger.live_meta[s]) for s,p in ledger.state.positions.items()]
    m=pd.DataFrame(marks)
    if not np.isclose(4000+trades.pnl.sum()+sum(r['unrealized_pnl_usd'] for r in opened)-ledger.interest,m.equity.iloc[-1],atol=1e-6):
        raise ValueError('Cash/remaining-basis identity failed')
    complete=campaigns_from_legs(trades,opened)
    for name,frame in [('trades.parquet',trades),('marks.parquet',m),('campaign-trades.parquet',complete)]: frame.to_parquet(out/name,index=False)
    atomic_json(out/'open-positions.json',opened);atomic_json(out/'decisions.json',ledger.audit)
    atomic_json(out/'maintenance.json',ledger.margin_log);atomic_json(out/'partial-events.json',ledger.partial_events)
    if arm=='WINNER':
        old=REFERENCE/f'WINNER-fee{fee}'/'cases'/str(year)
        for name in ['trades.parquet','marks.parquet','decisions.json','maintenance.json','production-risk-events.json']:
            if digest(out/name)!=digest(old/name): raise ValueError('Baseline transaction reproduction failed: '+name)
    from scripts.research.us_oracle_partial_p02_audit import audit_case
    audit=audit_case(out,tape,fee,arm=='P02')
    result=dict(arm=arm,year=year,fee_bps=fee,**parent.risk.base.metrics(m,complete,opened),
        closed_exit_legs=len(trades),partial_exits=int(trades.exit_reason.eq('PARTIAL_TP10').sum()) if len(trades) else 0,
        financing_usd=ledger.interest,audit=audit,baseline_exact_reproduction=arm=='WINNER',full_live_parity=False)
    atomic_json(out/'done.json',result)
    return result


def unit_results(root,signals,groups,schedule):
    days=pd.DatetimeIndex(schedule.date);sch=schedule.set_index('date');rows=[]
    for r in signals.itertuples():
        i=days.get_loc(r.date)
        frame=pd.concat([groups[r.symbol,d] for d in days[i:i+21]],ignore_index=True)
        frame=frame[frame.bar_timestamp.between(r.timestamp,r.due_open)].reset_index(drop=True)
        row=dict(pair_id=int(r.pair_id),symbol=r.symbol,rank=int(r.rank),year=r.oracle_date.year,
            oracle_date=r.oracle_date,entry_time=r.timestamp,
            label_available=sch.loc[days[days.get_loc(r.oracle_date)+40],'market_open'])
        for arm in ARMS:
            exits,remaining=scalar_legs(frame,0,r.due_open,2,arm=='P02')
            if remaining: raise ValueError('Unit common path must be mature')
            for fee in FEES:
                row[f'{arm}_{fee}']=100*sum(e['quantity']*((e['price']-r.price)-(fee/10000)*(e['price']+r.price)) for e in exits)/(2*r.price)
            if arm=='P02': row['partial_touch']=any(e['role']=='PARTIAL' for e in exits)
        rows.append(row)
    result=pd.DataFrame(rows);result.to_parquet(root/'unit-results.parquet',index=False)
    nonoverlap=parent.history.spaced(result);nonoverlap.to_parquet(root/'nonoverlap.parquet',index=False)
    checks=[]
    for year,g in nonoverlap.groupby('year'):
        ci=parent.history.monthly_interval(g.oracle_date.dt.tz_localize('UTC'),g.P02_8-g.WINNER_8)
        checks.append(dict(year=int(year),n=len(g),partial_touches=int(g.partial_touch.sum()),
            increment_pp=float((g.P02_8-g.WINNER_8).mean()),stress_increment_pp=float((g.P02_25-g.WINNER_25).mean()),ci=ci))
    return checks


def analyze(root):
    root=Path(root)
    if (root/'report.json').exists(): raise ValueError('Already sealed')
    protocol=READ(root/'protocol.json');verify_hashes(Path('.'),protocol['sources'])
    verify_hashes(REFERENCE,READ(REFERENCE/'report.json')['files'])
    groups,_,schedule=parent.load_groups()
    signals=pd.read_parquet(REFERENCE/'signals.parquet');signals=signals[signals.arm.eq('WINNER')].copy()
    signals.to_parquet(root/'signals.parquet',index=False)
    checks=unit_results(root,signals,groups,schedule);reports=[]
    tapes={y:make_tape(groups,schedule,signals,y) for y in (2025,2026)}
    for fee in FEES:
        for year in (2025,2026):
            for arm in ARMS:
                atomic_json(root/'progress.json',dict(status='RUNNING',completed=len(reports),total=8,year=year,arm=arm,fee_bps=fee))
                r=run_case(root,arm,year,fee,tapes[year]);reports.append(r)
                print(f'{year} {arm} fee{fee}: {r["return_pct"]:.3f}% DD{r["max_drawdown_pct"]:.3f} campaigns{r["trades"]} partials{r["partial_exits"]}',flush=True)
    comparisons=[]
    for fee in FEES:
        for year in (2025,2026):
            b=next(r for r in reports if r['arm']=='WINNER' and r['year']==year and r['fee_bps']==fee)
            p=next(r for r in reports if r['arm']=='P02' and r['year']==year and r['fee_bps']==fee)
            comparisons.append(dict(year=year,fee_bps=fee,return_increment_pp=p['return_pct']-b['return_pct'],
                dd_increment_pp=p['max_drawdown_pct']-b['max_drawdown_pct']))
    sufficient=all(any(c['year']==y and c['n']>=30 and c['partial_touches']>=10 for c in checks) for y in (2025,2026))
    passes=sufficient and all(r['return_increment_pp']>0 for r in comparisons) and all(
        r['dd_increment_pp']<=0 for r in comparisons if r['fee_bps']==8) and all(
        c['stress_increment_pp']>0 and c['ci']['months']>=6 and c['ci']['lower95']>0 for c in checks)
    pd.DataFrame([{k:v for k,v in r.items() if k!='audit'} for r in reports]).to_csv(root/'annual-summary.csv',index=False)
    verify_hashes(Path('.'),protocol['sources']);verify_hashes(REFERENCE,READ(REFERENCE/'report.json')['files'])
    result=dict(status='EXPLORATORY_P02_WORTH_CONFIRMATION' if passes else 'INSUFFICIENT_P02_SAMPLE' if not sufficient else 'NO_GO_P02_NOT_CONFIRMED',
        campaigns=len(signals),symbols=int(signals.symbol.nunique()),results=reports,comparisons=comparisons,
        unit_checks=checks,production_promoted=False,sql_writes=False,provider_calls=False,
        files={str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file() and p.name not in ['run.lock','progress.json','report.json']})
    atomic_json(root/'report.json',result);atomic_json(root/'progress.json',dict(status=result['status'],completed=8,total=8,failed=0))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=OUTPUT)
    p.add_argument('--phase',choices=['prepare','analyze','run'],default='run');a=p.parse_args()
    from scripts.research.oracle_path_confirmation import exclusive_run
    try:
        if a.phase in ('prepare','run'): prepare(a.output_dir)
        if a.phase in ('analyze','run'):
            with exclusive_run(a.output_dir): analyze(a.output_dir)
    except Exception as exc:
        if (a.output_dir/'protocol.json').exists() and not (a.output_dir/'report.json').exists():
            atomic_json(a.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__': main()
