"""Offline SHORT portfolios on the frozen August GPT/TOP20 cohort.

Native RiskChecker/Constraints/B4 are reused; Winner's LONG-only coordinator
is NOT relabelled as a SHORT implementation. Independent causal entry/exit
and collateral accounting, audited against scalar paths. No SQL/network/orders.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import logging
import math
import os
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from scripts.research import us_gpt_veto_direct_open_august_2026 as previous
from common.winner_risk_state import CampaignRiskState
from risk_management.concentration import SymbolTradeTracker, ConsecutiveLossTracker
from risk_management.constraints import PortfolioState
from risk_management.risk_checker import RiskCheckerImpl
from backtesting.regime_trailing import compute_regime

base, grid, original = previous.base, previous.grid, previous.original
PARENT = previous.ROOT
ROOT = PARENT.parent/'20261025-short-v1'
FEE, BORROW = .0008, .003
DOC = Path('doc/ml/gpt_short_aout_2026.md')
TEST = Path('tests/test_us_gpt_short_august_2026.py')


def veto_mask(cohort, low):
    if low not in (None, 6, 7):
        raise ValueError('Only announced inclusive exclusions 7..9 or 6..9')
    return pd.Series(False, index=cohort.index) if low is None else (
        cohort.gpt_status.eq('VALID') & cohort.gpt_score.between(low, 9)).fillna(False)


def confirmation(closes, level, side):
    if len(closes) != 3 or not np.isfinite(closes).all() or level <= 0:
        return False
    a,b,c = closes
    return bool(a >= level and b < level and c < level) if side == 'sell' else bool(a <= level and b > level and c > level)


def stop_exit(bar, stop, side, due=False):
    """Only this bar open is known before entries; intrabar hit at bar end."""
    op, hi, lo = map(float, (bar.open, bar.high, bar.low))
    if op >= stop if side == 'sell' else op <= stop:
        return op, 'STOP_GAP', 'OPEN'
    if due:
        return op, 'HORIZON_OPEN', 'OPEN'
    if hi >= stop if side == 'sell' else lo <= stop:
        return stop, 'STOP', 'INTRABAR'
    return None


def net_trade(entry, exit, qty, side, holding_sessions):
    direction = -1 if side == 'sell' else 1
    fees = qty*(entry+exit)*FEE
    loan = qty*entry*BORROW*holding_sessions/252 if side == 'sell' else 0.
    return direction*qty*(exit-entry)-fees-loan, fees, loan


def prepare(root):
    old = base.read(PARENT/'report.json')
    if old['status'] != 'COMPLETED_AUDITED_EXPLORATORY':
        raise ValueError('Audited direct LONG comparison required')
    parent = base.read(PARENT/'protocol.json'); base.verify(parent['sources'])
    manifest = base.read(PARENT/'inputs/snapshot.json')
    sources = {str(PARENT/'inputs'/n):h for n,h in manifest['files'].items()}
    names = [Path(__file__), DOC, TEST, PARENT/'protocol.json', PARENT/'report.json',
        PARENT/'common-cohort.parquet', PARENT/'frozen-signals.parquet',
        Path('common/winner_risk_state.py'), Path('risk_management/risk_checker.py'),
        Path('risk_management/constraints.py'), Path('risk_management/concentration.py'),
        Path('risk_management/circuit_breaker.py'), Path('backtesting/regime_trailing.py'),
        Path('backtesting/adaptive_breaker.py')]
    sources.update({str(n):base.digest(n) for n in names}); base.verify(sources)
    root.mkdir(parents=True,exist_ok=False)
    shutil.copytree(PARENT/'inputs',root/'inputs')
    shutil.copy2(PARENT/'frozen-signals.parquet',root/'frozen-signals.parquet')
    protocol = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        reference_config=parent['reference_config'],signal_period='2026-08-03..2026-08-31',
        replay_period='2026-08-03..2026-09-30',initial_equity=4000.,fraction=.5,SL=.07,TP=None,trailing=None,
        holding_sessions=20,exit='Open21, stop gaps first',entry_valid_sessions=20,
        arms='6 SHORT: direct/confirmed x none/veto7..9/veto6..9; 2 LONG parity diagnostics',
        score10='Retained by exact user request; count explicitly, no silent extension to10',
        invalid_scores='Retained without veto, same comparator policy',
        short_confirmation='Fresh downward cross of prior regular low, then two completed5m closes below; next bar open',
        native_risk='Original frozen RiskChecker/Constraints/B4, sector/correlation/concentration; same HALF budget formula',
        short_max_positions=parent['reference_config']['risk']['max_short_positions'],
        collateral='Net liquidation collateral + unrealized PnL; sale proceeds segregated, never reusable buying power',
        assumed_borrow_annual=BORROW,borrow_basis='Entry notional/252 per holding session, including exit; no actual locate evidence',
        maintenance='Assumed SHORT tier: max(2.5,price) if price<5 else max(5,.3*price); next-open liquidation on breach',
        implementation='New research side-aware adapter, NOT native Winner SHORT/live support',
        fee_per_leg=FEE,effective_gross_cap=1.,historical_gpt_non_PIT=True,future_coverage_selection_bias=True,
        full_live_parity=False,independent_holdout=False,gpt_calls=0,provider_calls=0,SQL_reads=0,
        SQL_writes=False,broker_orders=False,production_changed=False)
    base.save_new(root/'protocol.json',protocol)
    grid.atomic_json(root/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=8))
    return protocol


class Replay:
    def __init__(self, cohort, groups, pivots, sectors, sessions, risk, *, side, confirmed):
        self.cohort,self.groups,self.pivots,self.sectors = cohort,groups,pivots,sectors
        self.sessions,self.days = sessions,[s.session_date for s in sessions]
        self.idx = {d:i for i,d in enumerate(self.days)}
        self.risk,self.side,self.confirmed = risk,side,confirmed
        self.plans,self.positions,self.marks = {},{},{}
        self.cash,self.fees,self.loan = 4000.,0.,0.
        self.trades,self.events,self.curve,self.breakers,self.refusals = [],[],[],[],[]
        self.all_entries = []
        self.tracker = SymbolTradeTracker(risk.concentration_max_trades_per_symbol,risk.concentration_window_calendar_days)
        self.losses = ConsecutiveLossTracker(risk.concentration_max_consecutive_losses,risk.concentration_blacklist_duration_days)
        self.returns = pivots['close'].pct_change(fill_method=None)
        self.regimes = {pd.Timestamp(k).date():str(v) for k,v in compute_regime(pivots['close']['SPY']).dropna().items()}
        seed = max(d for d in self.days if d < original.START)
        self.guard = CampaignRiskState(risk,observations=[(seed,4000.)],regimes=self.regimes)
        self.previous_close,self.maintenance_pending = 4000.,False

    def equity(self):
        direction = -1 if self.side == 'sell' else 1
        return self.cash+sum(direction*p['quantity']*(self.marks[s]-p['entry_price']) for s,p in self.positions.items())

    def gross(self):
        return sum(p['quantity']*self.marks[s] for s,p in self.positions.items())

    def admit(self, day):
        rows = self.cohort[self.cohort.selected & self.cohort.date.eq(pd.Timestamp(day))].sort_values('oracle_rank')
        eq = self.equity()
        for row in rows.itertuples():
            s = row.symbol
            if s in self.plans or s in self.positions:
                continue
            price = float(self.groups[s,day].close.iloc[-1])
            budget = eq*self.risk.risk_per_trade_pct*self.risk.risk_multiplier
            full = min(math.floor(budget/(price*(.07+2.05*.0025))),math.floor(eq*self.risk.max_position_weight/price))
            initial = full//2
            if initial < 1 or full*.5*price < self.risk.effective_min_notional:
                continue
            self.plans[s] = dict(symbol=s,signal_date=day,signal_index=self.idx[day],rank=int(row.oracle_rank),
                budget=budget,full=full,initial=initial)

    def approve(self, plan, price, day, stamp, evaluated, correlations, daily_days):
        s,eq = plan['symbol'],self.equity()
        if self.side == 'sell' and (not self.risk.short_selling_enabled or eq < 2000):
            return 0,'SHORT_POLICY_OR_MIN_EQUITY'
        if not self.tracker.allow_entry(s,day,side=self.side) or self.losses.is_blacklisted(s,day,side=self.side):
            return 0,'CONCENTRATION'
        if len(daily_days) != 61:
            return 0,'INSUFFICIENT_DAILY_SESSIONS'
        for frame in self.pivots.values():
            if s not in frame:
                return 0,'MISSING_DAILY_SYMBOL'
            v = frame[s].reindex(daily_days)
            if not (v.notna() & np.isfinite(v) & v.gt(0)).all():
                return 0,'UNQUALIFIED_DAILY_DATA'
        ps = PortfolioState()
        for held,p in self.positions.items():
            ps.add_position(notional=p['quantity']*self.marks[held],sector=self.sectors[held],side=self.side,symbol=held)
            if s not in correlations or held not in correlations or pd.isna(correlations.loc[s,held]):
                return 0,'INSUFFICIENT_CORRELATION'
            # Both held and proposed directions agree => signed exposure corr equals raw corr.
            if correlations.loc[s,held] > self.risk.correlation_threshold:
                return 0,'CORRELATION_CAP'
        cfg = replace(self.risk,account_equity=eq,sector_corr_map=correlations.to_dict(),max_gross_exposure=1.)
        fee = .0025
        budget = min(plan['budget'],eq*cfg.risk_per_trade_pct*cfg.risk_multiplier*evaluated['allocation_scale'])
        full = min(plan['full'],math.floor(budget/(price*(.07+2.05*fee))))
        proposed = min(plan['initial'],full//2,math.floor(budget/(price*(.07+2.05*fee))),
            math.floor(max(eq-self.gross(),0)/(price*(1+fee))),math.floor(eq*cfg.max_position_weight/price))
        if proposed <= 0:
            return 0,'CAMPAIGN_RISK_OR_CAPACITY'
        prior = pd.Timestamp(self.days[self.idx[day]-1])
        hist = self.pivots['close'].loc[:prior,s].tail(20)
        adv = float((hist*self.pivots['volume'].loc[hist.index,s]).mean())
        checker = RiskCheckerImpl(cfg,state=ps,circuit_breaker=evaluated['circuit_breaker'],sector_map=self.sectors)
        q = math.floor(checker.check_position_size(s,proposed,price,side=self.side,adv_usd=adv,selection_rank=plan['rank']))
        return q,checker.get_last_decision_reason()

    def open(self, plan, bar, day, stamp, quantity):
        s,price = plan['symbol'],float(bar.open)
        entry_fee = quantity*price*FEE
        self.cash -= entry_fee; self.fees += entry_fee
        self.positions[s] = dict(symbol=s,quantity=quantity,entry_price=price,entry_date=stamp,entry_day=day,
            signal_date=plan['signal_date'],rank=plan['rank'],due_index=self.idx[day]+20,
            stop=round(price*(1.07 if self.side=='sell' else .93),2),entry_fees=entry_fee,accrued_borrow=0.)
        event = dict(time=stamp,event='SELL_SHORT' if self.side=='sell' else 'BUY',symbol=s,price=price,
            quantity=quantity,fee=entry_fee,signal_date=plan['signal_date'],rank=plan['rank'])
        self.events.append(event); self.all_entries.append(dict(self.positions[s]))
        self.tracker.record(s,day,side=self.side)
        del self.plans[s]

    def close(self, s, price, stamp, day, reason):
        p = self.positions.pop(s)
        count = self.idx[day]-self.idx[p['entry_day']]+1
        net,fees,loan = net_trade(p['entry_price'],price,p['quantity'],self.side,count)
        exit_fee = p['quantity']*price*FEE
        incremental_loan = loan-p['accrued_borrow']
        self.cash += (-1 if self.side=='sell' else 1)*p['quantity']*(price-p['entry_price'])-exit_fee-incremental_loan
        self.loan += incremental_loan;self.fees += exit_fee
        trade = dict(p,exit_price=price,exit_date=stamp,exit_reason=reason,pnl=net,
            exit_fees=exit_fee,borrow_cost=loan,holding_sessions=count,side=self.side)
        self.trades.append(trade)
        self.losses.record(s,net,day,side=self.side)
        self.events.append(dict(time=stamp,event='BUY_TO_COVER' if self.side=='sell' else 'SELL',symbol=s,
            price=price,quantity=p['quantity'],fee=exit_fee,borrow=incremental_loan,pnl=net,reason=reason))

    def run(self, progress=None):
        days = [s for s in self.sessions if original.START <= s.session_date <= original.END]
        self.admit(self.days[self.idx[days[0].session_date]-1])
        for n,session in enumerate(days):
            day,i = session.session_date,self.idx[session.session_date]
            prior = self.days[i-1]
            daily_days = [pd.Timestamp(d) for d in self.days[max(0,i-61):i]]
            hist = self.returns.loc[:pd.Timestamp(prior)].tail(self.risk.correlation_lookback_days)
            correlations = hist.corr(min_periods=self.risk.correlation_min_overlap)
            for s in list(self.plans):
                if i > self.plans[s]['signal_index']+20:
                    del self.plans[s]
            symbols = set(self.plans)|set(self.positions)
            arrays = {}
            for s in symbols:
                if (s,day) not in self.groups:
                    raise ValueError('Missing common-cohort session '+str((s,day)))
                arrays[s] = list(self.groups[s,day].itertuples())
            for offset,stamp in enumerate(pd.date_range(session.open_at_utc,session.close_at_utc,freq='5min',inclusive='left')):
                bars = {s:a[offset] for s,a in arrays.items()}
                self.marks.update({s:float(b.open) for s,b in bars.items()})
                for s,p in list(self.positions.items()):
                    got = stop_exit(bars[s],p['stop'],self.side,due=i>=p['due_index'])
                    if got and got[2]=='OPEN':
                        self.close(s,got[0],stamp,day,got[1])
                if offset == 0 and self.maintenance_pending:
                    for s in list(self.positions):
                        self.close(s,float(bars[s].open),stamp,day,'ASSUMED_MAINTENANCE')
                    self.maintenance_pending=False
                eq = self.equity()
                if eq <= 0:
                    raise ValueError('Insolvent research account')
                evaluated = self.guard.evaluate(day,eq,self.regimes.get(prior),daily_pnl=eq-self.previous_close)
                self.breakers.append(dict(time=stamp,equity=eq,allocation=evaluated['allocation_scale'],peak=evaluated['reference_peak']))
                for s,plan in list(self.plans.items()):
                    if s in self.positions or not 1 <= i-plan['signal_index'] <= 20:
                        continue
                    if self.confirmed:
                        old = self.groups[s,prior]
                        level = float(old.low.min() if self.side=='sell' else old.high.max())
                        ready = offset>=3 and confirmation([float(bars_.close) for bars_ in arrays[s][offset-3:offset]],level,self.side)
                    else:
                        ready = offset==0 and i==plan['signal_index']+1
                    if ready:
                        q,reason = self.approve(plan,float(bars[s].open),day,stamp,evaluated,correlations,daily_days)
                        if q>0:
                            self.open(plan,bars[s],day,stamp,q)
                        else:
                            self.refusals.append(dict(time=stamp,symbol=s,reason=reason))
                    if not self.confirmed and s in self.plans and i>=plan['signal_index']+1:
                        del self.plans[s]
                for s,p in list(self.positions.items()):
                    got = stop_exit(bars[s],p['stop'],self.side)
                    if got and got[2]=='INTRABAR':
                        self.close(s,got[0],stamp+pd.Timedelta(minutes=5),day,got[1])
                self.marks.update({s:float(b.close) for s,b in bars.items()})
                self.curve.append(dict(timestamp=stamp+pd.Timedelta(minutes=5),equity=self.equity(),gross=self.gross()))
            if self.side=='sell':
                for p in self.positions.values():
                    total = p['quantity']*p['entry_price']*BORROW*(i-self.idx[p['entry_day']]+1)/252
                    debit = total-p['accrued_borrow'];p['accrued_borrow']=total
                    self.cash -= debit;self.loan += debit
                    self.events.append(dict(time=session.close_at_utc,event='BORROW_ACCRUAL',symbol=p['symbol'],borrow=debit))
            self.curve[-1].update(equity=self.equity())
            self.previous_close = self.equity()
            required = sum(p['quantity']*(max(2.5,self.marks[s]) if self.marks[s]<5 else max(5.,.3*self.marks[s]))
                for s,p in self.positions.items()) if self.side=='sell' else 0.
            self.maintenance_pending = self.equity()<required
            self.admit(day)
            if progress: progress(n+1,len(days),str(day))
        return self


def audit(replay, raw):
    """Independent chronological scalar exit, entry signal, cash and loan checks."""
    for p in replay.all_entries:
        path = raw[p['symbol']]
        stamp = pd.Timestamp(p['entry_date']); day = p['entry_day']; i=replay.idx[day]
        g = path[path.trade_date.eq(pd.Timestamp(day))].reset_index(drop=True)
        matches = np.flatnonzero(g.bar_timestamp.eq(stamp))
        if len(matches)!=1: raise ValueError('Entry bar absent')
        k=int(matches[0]);grid.near(p['entry_price'],g.iloc[k].open)
        if replay.confirmed:
            prev = raw[p['symbol']];prev=prev[prev.trade_date.eq(pd.Timestamp(replay.days[i-1]))]
            level=float(prev.low.min() if replay.side=='sell' else prev.high.max())
            if k<3 or not confirmation(g.close.iloc[k-3:k].to_numpy(),level,replay.side):
                raise ValueError('Noncausal confirmation')
        elif i != replay.idx[p['signal_date']]+1 or k!=0:
            raise ValueError('Direct entry is not exact J+1 open')
    for t in replay.trades:
        path=raw[t['symbol']]; due=pd.Timestamp(replay.sessions[t['due_index']].open_at_utc)
        found=None
        for b in path[path.bar_timestamp.ge(t['entry_date'])].itertuples():
            # Separate scalar implementation, not stop_exit().
            opening_hit = b.open >= t['stop'] if replay.side=='sell' else b.open <= t['stop']
            touched = b.high >= t['stop'] if replay.side=='sell' else b.low <= t['stop']
            if opening_hit: found=(b.bar_timestamp,float(b.open),'STOP_GAP');break
            if b.bar_timestamp>=due: found=(b.bar_timestamp,float(b.open),'HORIZON_OPEN');break
            if touched: found=(b.bar_end_timestamp,t['stop'],'STOP');break
        if t['exit_reason']=='ASSUMED_MAINTENANCE':
            if pd.Timestamp(t['exit_date']).time()!=pd.Timestamp(replay.sessions[replay.idx[pd.Timestamp(t['exit_date']).tz_convert('America/New_York').date()]].open_at_utc).time():
                raise ValueError('Maintenance must execute at open')
        elif found is None or (found[0],found[2])!=(t['exit_date'],t['exit_reason']):
            raise ValueError('Scalar SHORT lifecycle differs '+str((t['symbol'],found)))
        else: grid.near(found[1],t['exit_price'])
        expected,fees,borrow=net_trade(t['entry_price'],t['exit_price'],t['quantity'],replay.side,t['holding_sessions'])
        grid.near(expected,t['pnl']);grid.near(borrow,t['borrow_cost']);grid.near(fees,t['entry_fees']+t['exit_fees'])
    closed=sum(t['pnl'] for t in replay.trades)
    open_cost=sum(p['entry_fees']+p['accrued_borrow'] for p in replay.positions.values())
    grid.near(replay.cash,4000.+closed-open_cost)
    grid.near(replay.loan,sum(t['borrow_cost'] for t in replay.trades)+sum(p['accrued_borrow'] for p in replay.positions.values()))
    return dict(status='PASS_SCALAR_ENTRIES_EXITS_COLLATERAL_LOAN',entries=len(replay.all_entries),exits=len(replay.trades))


def summary(r,arm,checks,cohort,low):
    curve=pd.DataFrame(r.curve);values=np.r_[4000.,curve.equity.to_numpy()]
    wins=[t['pnl'] for t in r.trades if t['pnl']>0];losses=[t['pnl'] for t in r.trades if t['pnl']<0]
    return dict(arm=arm,status='COMPLETED_AUDITED_EXPLORATORY',side=r.side,confirmation=r.confirmed,veto_low=low,
        final_equity=r.equity(),return_pct=100*(r.equity()/4000.-1),max_drawdown_pct=100*float(np.min(values/np.maximum.accumulate(values)-1)),
        entries=len(r.all_entries),closed_trades=len(r.trades),winners=len(wins),losers=len(losses),
        win_pct=100*len(wins)/len(r.trades) if r.trades else None,
        gross_winning_pnl=sum(wins),gross_losing_pnl=sum(losses),net_closed_pnl=sum(wins)+sum(losses),
        average_winning_pnl=float(np.mean(wins)) if wins else None,average_losing_pnl=float(np.mean(losses)) if losses else None,
        costs=r.fees,borrow_cost=r.loan,average_gross_capital=float(curve.gross.mean()),
        open_positions=[dict(p,mark=r.marks[s]) for s,p in r.positions.items()],eligible_signals=int(cohort.selected.sum()),
        audit=checks,full_live_parity=False)


def run(root):
    protocol=prepare(root)
    with previous.prior.previous.run_lock(root):
        cohort,groups,raw,actions,sectors,pivots,sessions=original.load_inputs(root)
        pd.testing.assert_frame_equal(cohort,pd.read_parquet(PARENT/'common-cohort.parquet'))
        # Calendar must include actual61-session warmup, not fabricated old bars.
        sessions=[s for s in grid.calendar().sessions(pd.Timestamp('2025-01-01').date(),pd.Timestamp('2026-11-30').date()) if s.is_open]
        cfg=base.engine_config(protocol['reference_config'],2026)
        reports=[]
        cases=[('sell',confirmed,low) for confirmed in [False,True] for low in [None,7,6]]
        cases += [('buy',False,None),('buy',True,None)]
        for side,confirmed,low in cases:
            arm=f"{'SHORT' if side=='sell' else 'LONG_CONTROL'}_{'CONFIRMED' if confirmed else 'DIRECT'}_"+(f'VETO_{low}_9' if low else 'NO_VETO')
            folder=root/arm;folder.mkdir()
            selected=cohort.copy();selected['selected']=cohort.selected & ~veto_mask(cohort,low)
            def progress(done,total,day):
                grid.atomic_json(root/'progress.json',dict(status='RUNNING',arm=arm,completed_runs=len(reports),total_runs=8,
                    completed_sessions=done,total_sessions=total,last_date=day,updated_at_utc=datetime.now(timezone.utc).isoformat()))
            replay=Replay(selected,groups,pivots,sectors,sessions,cfg.risk_config,side=side,confirmed=confirmed).run(progress)
            checks=audit(replay,raw);report=summary(replay,arm,checks,selected,low)
            for name,rows in [('trades',replay.trades),('events',replay.events),('equity-5m',replay.curve),
                    ('breaker',replay.breakers),('refusals',replay.refusals)]:
                pd.DataFrame(rows).to_parquet(folder/(name+'.parquet'),index=False)
            report['files']={p.name:base.digest(p) for p in folder.iterdir() if p.is_file()}
            base.save_new(folder/'report.json',report);reports.append(report)
        diagnostic={}
        for confirmed,name in [(False,'DIRECT_ONLY'),(True,'WINNER_ONLY')]:
            source=(PARENT/name if not confirmed else original.ROOT/name)
            old=base.read(source/'report.json')
            new=next(r for r in reports if r['side']=='buy' and r['confirmation']==confirmed)
            diagnostic[name]=dict(archived_equity=old['final_equity'],adapter_equity=new['final_equity'],
                delta_usd=new['final_equity']-old['final_equity'],archived_closed=old['closed_lot_trades'],adapter_closed=new['closed_trades'])
        paths=pd.read_parquet(original.GPT/'results.parquet')
        qualified=paths[paths.path_status.eq('QUALIFIED_COMPLETE_5M')]
        bias=dict(qualified_pairs=len(qualified),unique_symbols=int(qualified.symbol.nunique()),
            dominant_counts=qualified.dominant_direction.value_counts().to_dict(),
            h20_close_positive=int(qualified.h20_close_return_pct.gt(0).sum()),h20_close_negative=int(qualified.h20_close_return_pct.lt(0).sum()))
        base.verify(protocol['sources'])
        base.save_new(root/'report.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',cases=reports,long_adapter_diagnostic=diagnostic,
            universe_direction_diagnostic=bias,eligible_score_counts=cohort[cohort.selected].groupby(['gpt_status','gpt_score'],dropna=False).size().to_string(),
            score10_eligible=int((cohort.selected & cohort.gpt_status.eq('VALID') & cohort.gpt_score.eq(10)).sum()),
            historical_gpt_non_PIT=True,future_coverage_selection_bias=True,full_live_parity=False,
            gpt_calls=0,provider_calls=0,SQL_writes=False,broker_orders=False,sources=protocol['sources']))
        grid.atomic_json(root/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',completed_runs=8,total_runs=8))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT)
    args=parser.parse_args();logging.basicConfig(level=logging.ERROR,force=True);os.environ['SSLKEYLOGFILE']=''
    if os.name=='nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No network in local SHORT replay'))
    try:run(args.output)
    except BaseException as exc:
        if args.output.exists():
            grid.atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':main()
