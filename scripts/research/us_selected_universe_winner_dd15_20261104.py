"""Matched 2x2 confirmation/DD15 experiment on frozen dedicated Oracle TOP5.

Pure local five-minute financial replay using native Winner confirmation and
native CampaignRiskState/B4 + GlobalLiquidation decisions. No broker or SQL.
Only next-session opportunities are tested; no reinforcement or stale plans.
"""
from __future__ import annotations
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import argparse
import json
import logging
import math
import time
from functools import lru_cache

import numpy as np
import pandas as pd

from common.market_calendar import get_market_calendar
from common.winner_pyramiding import (load_winner_pyramiding_config, confirmed_breakout,
    resolve_bar_exit, regular_bounds)
from common.winner_delayed import delayed_snapshot, delayed_price_limit
from common.winner_risk_state import CampaignRiskState, GUARD_FIELDS
from backtesting.winner_global_liquidation import GlobalLiquidation
from backtesting.regime_trailing import compute_regime
from risk_management.config import load_risk_config
from common.daily_bar_sources import select_daily_bars
from scripts.research.us_selected_universe_oracle_20261104 import (
    BASE, OUT as PRIOR, POLICY, END, CASES, digest, save, prepare_prices,
    summarize_portfolio, nyse_sessions)
from scripts.research.us_selected_universe_intraday_inputs_20261104 import OUT

LOG=logging.getLogger(__name__)
ARMS={'BASE':(False,False),'WINNER':(True,False),'DD15':(False,True),'WINNER_DD15':(True,True)}
FIELDS=['open','high','low','close','volume']


class Tape:
    def __init__(self):
        folder=OUT/'inputs'
        manifest=json.loads((folder/'manifest.json').read_text())
        recovery=json.loads((OUT/'recovery/report.json').read_text())
        assert recovery['status']=='COMPLETED'
        assert all(digest(folder/f)==h for f,h in manifest['files'].items())
        assert all(digest(p)==h for p,h in manifest['source_hashes'].items())
        self.calendar=nyse_sessions(pd.Timestamp('2016-01-01').date(),END.date())
        self.days=self.calendar[self.calendar>='2024-01-01']
        self.symbols=manifest['symbols']
        self.smap={s:i for i,s in enumerate(self.symbols)}
        self.dmap={d:i for i,d in enumerate(self.days)}
        self.global_index=np.array([self.calendar.get_loc(d) for d in self.days])
        sessions=get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions(
            self.days[0].date(),END.date())
        sessions=[s for s in sessions if s.is_open]
        assert [s.session_date for s in sessions]==[d.date() for d in self.days]
        self.opens=[s.open_at_utc for s in sessions]
        self.counts=np.array([int((s.close_at_utc-s.open_at_utc).total_seconds()/300) for s in sessions])
        self.values=np.full((len(self.days),78,len(self.symbols),5),np.nan)
        packets=[folder/f for f in manifest['files'] if f.endswith('.parquet') and f!='spy-daily.parquet']
        for r in recovery['cases']:
            path=OUT/'recovery'/r['symbol']/'regular.parquet'
            assert r['status']=='COMPLETED' and digest(path)==r['file_sha256']
            packets.append(path)
        tail=json.loads((OUT/'tail-recovery/report.json').read_text())
        assert tail['status']=='COMPLETED'
        for r in tail['cases']:
            path=OUT/'tail-recovery'/r['file']
            assert digest(path)==r['file_sha256']
            packets.append(path)
        for path in packets:
            frame=pd.read_parquet(path)
            if frame.empty:continue
            frame['trade_date']=pd.to_datetime(frame.trade_date)
            frame['timestamp']=pd.to_datetime(frame.timestamp,utc=True)
            assert set(frame.symbol)<=set(self.symbols)
            assert frame.trade_date.between(self.days[0],END).all()
            assert not frame.duplicated(['symbol','timestamp']).any()
            for day,g in frame.groupby('trade_date'):
                if day not in self.dmap:continue
                di=self.dmap[day]
                offsets=(g.timestamp-pd.Timestamp(self.opens[di])).dt.total_seconds().to_numpy()/300
                keep=(offsets>=0)&(offsets<self.counts[di])&(offsets==np.floor(offsets))
                g=g.loc[keep];offsets=offsets[keep].astype(int)
                si=g.symbol.map(self.smap).to_numpy(int)
                assert np.isnan(self.values[di,offsets,si]).all()
                data=g[FIELDS].apply(pd.to_numeric,errors='coerce').to_numpy(float)
                good=np.isfinite(data).all(axis=1)&(data>0).all(axis=1)
                good&=(data[:,1]>=np.maximum(data[:,0],data[:,3]))&(data[:,2]<=np.minimum(data[:,0],data[:,3]))
                good&=data[:,1]>=data[:,2]
                self.values[di,offsets[good],si[good]]=data[good]
        self.complete=np.zeros((len(self.days),len(self.symbols)),dtype=bool)
        coverage=[]
        for di,day in enumerate(self.days):
            valid=np.isfinite(self.values[di,:self.counts[di]]).all(axis=2)
            self.complete[di]=valid.all(axis=0)
            for si,symbol in enumerate(self.symbols):
                coverage.append(dict(symbol=symbol,date=day,expected=int(self.counts[di]),
                    qualified_bars=int(valid[:,si].sum()),complete=bool(self.complete[di,si])))
        pd.DataFrame(coverage).to_csv(OUT/'intraday-qualified-coverage.csv',index=False)
        spy=pd.read_parquet(folder/'spy-daily.parquet').set_index('date').close
        self.regimes=compute_regime(spy).dropna()
        split_folder=OUT/'split-qualification'
        split_meta=json.loads((split_folder/'report.json').read_text())
        assert split_meta['status']=='COMPLETED'
        assert all(digest(split_folder/f)==h for f,h in split_meta['files'].items())
        transitions=pd.read_csv(split_folder/'transitions.csv',parse_dates=['date'])
        self.split_dates={s:g.date.tolist() for s,g in transitions.groupby('symbol')}
        self.risk=load_risk_config(equity=4000.,cli_overrides={'account_equity':4000.})
        assert self.risk.policy=='b4' and abs(self.risk.max_portfolio_drawdown_pct-.15)<1e-12
        self.native_policy=load_winner_pyramiding_config()
        assert self.native_policy.confirmation_bars==2
        self.top={};self.daily={};self.quality={}
        for case,(horizon,_) in CASES.items():
            top=pd.read_csv(PRIOR/case/'daily-top5.csv',parse_dates=['date'])
            self.top[case]={d:g.sort_values('oracle_rank').to_dict('records') for d,g in top.groupby('date')}
            universe=json.loads((PRIOR/'report.json').read_text())['cases'][case]['universe']
            raw={s:select_daily_bars(pd.read_parquet(BASE/'symbols'/s/'source-bars.parquet')) for s in universe}
            self.daily[case]=prepare_prices(raw,self.calendar)
            gates=[]
            for di,day in enumerate(self.days):
                gi=self.global_index[di]
                for row in self.top[case].get(self.calendar[gi-1],[]):
                    symbol=row['symbol'];si=self.smap[symbol]
                    price,good,identity,source=self.daily[case][symbol]
                    last=min(gi+horizon,len(self.calendar)-1)
                    reasons=[]
                    if not good[gi:last+1].all():reasons.append('DAILY_OHLCV_MISSING')
                    if len(set(identity[gi:last+1]))!=1:reasons.append('DAILY_IDENTITY_CHANGE')
                    if len(set(source[gi:last+1]))!=1:reasons.append('DAILY_PROVIDER_CHANGE')
                    if any(day<=d<=self.calendar[last] for d in self.split_dates.get(symbol,())):
                        reasons.append('PROVIDER_SPLIT_BASIS_CHANGE')
                    if di<1 or not self.complete[max(0,di-1):min(di+horizon+1,len(self.days)),si].all():
                        reasons.append('INTRADAY_WINDOW_INCOMPLETE')
                    ok=not reasons
                    self.quality[case,di,symbol]=ok
                    gates.append(dict(entry_date=day,signal_date=self.calendar[gi-1],symbol=symbol,
                        eligible=ok,reason=';'.join(reasons),rank=row['oracle_rank']))
            pd.DataFrame(gates).to_csv(OUT/f'{case}-matched-entry-quality.csv',index=False)


class Book:
    def __init__(self):
        self.holdings={};self.marks={};self.events=[]
    def positions(self):
        return [dict(symbol=s,side='long',qty=p['quantity']) for s,p in self.holdings.items()]
    @property
    def lots(self):
        return {s:dict(symbol=s,remaining=p['quantity'],entry=p['price']) for s,p in self.holdings.items()}


def entry_terms(equity,cash,price,scale=1.):
    budget=min(equity*POLICY['max_position_weight'],
        equity*POLICY['risk_per_trade_pct']*scale/(POLICY['stop_loss_pct']+2*POLICY['fee_per_leg']))
    quantity=math.floor(min(budget,cash/(1+POLICY['fee_per_leg']))/price+1e-12)
    return quantity if quantity>0 and quantity*price>=POLICY['min_notional'] else 0


def confirmation_terms(tape,di,k,symbol,policy):
    """Native three-bar cross test, actual 930s clock and one next-open IOC."""
    si=tape.smap[symbol]
    offset=policy.market_data_delay_seconds%300
    now=tape.opens[di]+timedelta(seconds=300*k+offset)
    cutoff=now-timedelta(seconds=policy.market_data_delay_seconds)
    last=int((cutoff-tape.opens[di]).total_seconds()//300)-1
    first=last-policy.confirmation_bars
    if first<0 or di<1 or k+1>=tape.counts[di]:return None
    if not tape.complete[di-1,si]:return None
    evidence=[dict(timestamp=tape.opens[di]+timedelta(minutes=5*j),
        close=float(tape.values[di,j,si,3]),session_tag='regular') for j in range(first,last+1)]
    prior_high=float(tape.values[di-1,:tape.counts[di-1],si,1].max())
    if not confirmed_breakout(evidence,prior_high,policy,now=now):return None
    snapshot=delayed_snapshot(evidence,policy,now)
    state=dict(policy=asdict(policy),lots=[],entry_policy={'max_entry_gap_pct':0.})
    ceiling=delayed_price_limit(state,snapshot,now)
    return dict(decided_at=now,fill_k=k+1,ceiling=ceiling,reference=snapshot['delayed_reference_price'],
        evidence_last_end=snapshot['delayed_reference_end'],prior_high=prior_high)


def run_case(tape,case,period,arm):
    dest=OUT/'runs'/case/period/arm
    if (dest/'report.json').exists():
        previous=json.loads((dest/'report.json').read_text())
        assert previous['files'] and all(digest(dest/f)==h for f,h in previous['files'].items())
        return previous
    if dest.exists():raise FileExistsError('Partial research result requires review: '+str(dest))
    confirmation,dd=ARMS[arm]
    horizon=CASES[case][0]
    start=pd.Timestamp('2024-01-01' if period=='continuous' else f'{period}-01-01')
    end=END if period in ('2026','continuous') else pd.Timestamp(f'{period}-12-31')
    selected=np.flatnonzero((tape.days>=start)&(tape.days<=end))
    native=replace(tape.native_policy,enabled=True,initial_position_fraction=1.,reinforcement_enabled=False,
        stop_loss_pct=.05,take_profit_pct=None,trailing_stop_pct=None,horizon_sessions=horizon)
    book=Book();cash=4000.;cost=0.;trades=[];daily=[];marks=[];audit=[];orders=[]
    risk=replace(tape.risk,force_close_on_breaker=dd,force_close_pct=.5)
    initial_di=int(selected[0]);prior=tape.calendar[tape.global_index[initial_di]-1]
    @lru_cache(maxsize=None)
    def regime(d):
        history=tape.regimes.loc[:d]
        return str(history.iloc[-1]) if len(history) else None
    guard=CampaignRiskState(risk,observations=[(prior.date(),4000.)],regimes={prior.date():regime(prior)}) if dd else None
    liq=GlobalLiquidation(SimpleNamespace(initial_equity=4000.),risk,
        SimpleNamespace(force_close_on_breaker=dd,force_close_pct=.5))
    pending={};scale=1.;evaluated=None;last_daily=4000.
    last_observation=None

    def equity():
        return cash+sum(p['quantity']*book.marks[s] for s,p in book.holdings.items())

    def sell(symbol,price,stamp,reason,gi):
        nonlocal cash,cost
        p=book.holdings.pop(symbol)
        charge=p['quantity']*price*POLICY['fee_per_leg']
        cash+=p['quantity']*price-charge;cost+=charge
        trades.append(dict(symbol=symbol,signal_date=p['signal_date'],entry_date=p['entry_time'],
            exit_date=stamp,quantity=p['quantity'],entry_price=p['price'],exit_price=price,
            pnl=p['quantity']*price-charge-p['basis'],entry_cost=p['entry_cost'],exit_cost=charge,
            reason=reason,holding_sessions=gi-p['entry_i']+int(reason not in ('TIME_OPEN','SL_GAP','GLOBAL_DD15'))))

    def observe(stamp,day,prior_day):
        nonlocal scale,evaluated,pending,last_observation
        if not dd:return
        current=equity()
        key=(day.date(),current,regime(prior_day),last_daily)
        if key==last_observation:return
        last_observation=key
        evaluated=guard.evaluate(day.date(),current,regime(prior_day),daily_pnl=current-last_daily)
        scale=evaluated['allocation_scale']
        before=liq.counter
        liq.observe(stamp,equity(),book,evaluated)
        if liq.counter!=before:
            orders.extend(dict(symbol=s,status='CANCELED_BY_DD',time=stamp) for s in pending)
            pending={}

    for number,di0 in enumerate(selected):
        di=int(di0);day=tape.days[di];gi=int(tape.global_index[di]);prior_day=tape.calendar[gi-1]
        held_at_open=set(book.holdings)
        signals=tape.top[case].get(prior_day,[])
        candidates=[]
        for row in signals:
            symbol=row['symbol']
            if symbol in held_at_open:
                audit.append(dict(date=day,symbol=symbol,status='ALREADY_HELD'));continue
            if not tape.quality.get((case,di,symbol),False):
                audit.append(dict(date=day,symbol=symbol,status='MATCHED_DATA_GATE'));continue
            candidates.append(row)
        attempted=set();pending={}
        for k in range(int(tape.counts[di])):
            stamp=tape.opens[di]+timedelta(minutes=5*k)
            bars=tape.values[di,k]
            for s in book.holdings:
                op=bars[tape.smap[s],0]
                if not np.isfinite(op):raise ValueError(f'Missing held opening {s}/{stamp}')
                book.marks[s]=float(op)
            # Standing stop and scheduled MOO precede any global liquidation.
            for s in list(book.holdings):
                p=book.holdings[s];op=float(bars[tape.smap[s],0])
                if k==0 and gi-p['entry_i']>=horizon:sell(s,op,stamp,'TIME_OPEN',gi)
                elif op<=p['stop']:sell(s,op,stamp,'SL_GAP',gi)
            # Execute the event detected at the preceding completed observation.
            queued=liq.pending
            if queued is not None and pd.Timestamp(queued['detected_at'])<=pd.Timestamp(stamp):
                sold={}
                for s in queued['symbols']:
                    if s in book.holdings:
                        sold[s]=book.holdings[s]['quantity']
                        sell(s,float(bars[tape.smap[s],0]),stamp,'GLOBAL_DD15',gi)
                liq.events.append(dict(queued,executed_at=stamp.isoformat(),quantities=sold,equity_after=equity()))
                liq.pending=None
            observe(stamp,day,prior_day)
            # A new trip observed at this open cannot sell at the already known print.
            if liq.pending is None:
                for s,order in list(pending.items()):
                    if order['fill_k']!=k:continue
                    del pending[s]
                    price=float(bars[tape.smap[s],0])
                    if price>order['ceiling']:
                        orders.append(dict(order,symbol=s,status='IOC_PRICE_CAP_REJECTED',fill_time=stamp,opening=price));continue
                    q=min(order['quantity'],entry_terms(equity(),cash,price,scale))
                    if q<1:
                        orders.append(dict(order,symbol=s,status='FILL_CAPACITY_REJECTED',fill_time=stamp));continue
                    basis=q*price*(1+POLICY['fee_per_leg']);cash-=basis;cost+=q*price*POLICY['fee_per_leg']
                    book.holdings[s]=dict(entry_i=gi,entry_time=stamp,signal_date=prior_day,
                        price=price,quantity=q,stop=price*.95,basis=basis,entry_cost=q*price*POLICY['fee_per_leg'])
                    book.marks[s]=price
                    orders.append(dict(order,symbol=s,status='FILLED',fill_time=stamp,fill_price=price,filled_quantity=q))
                    audit.append(dict(date=day,symbol=s,status='BOUGHT',price=price,quantity=q))
            if not confirmation and k==0 and liq.pending is None:
                for row in candidates:
                    s=row['symbol']
                    if len(book.holdings)>=POLICY['max_positions']:break
                    price=float(bars[tape.smap[s],0])
                    q=entry_terms(equity(),cash,price,scale)
                    if q<1:
                        audit.append(dict(date=day,symbol=s,status='INSUFFICIENT_CASH_OR_SIZING'));continue
                    basis=q*price*(1+POLICY['fee_per_leg']);cash-=basis;cost+=q*price*POLICY['fee_per_leg']
                    book.holdings[s]=dict(entry_i=gi,entry_time=stamp,signal_date=prior_day,
                        price=price,quantity=q,stop=price*.95,basis=basis,entry_cost=q*price*POLICY['fee_per_leg'])
                    book.marks[s]=price
                    audit.append(dict(date=day,symbol=s,status='BOUGHT',price=price,quantity=q))
            if confirmation and liq.pending is None:
                for row in candidates:
                    s=row['symbol']
                    if s in attempted or s in book.holdings:continue
                    terms=confirmation_terms(tape,di,k,s,native)
                    if terms is None:continue
                    attempted.add(s)
                    reserved=sum(o['quantity']*o['ceiling']*(1+POLICY['fee_per_leg']) for o in pending.values())
                    q=entry_terms(equity(),max(0.,cash-reserved),terms['ceiling'],scale)
                    if q<1 or len(book.holdings)+len(pending)>=POLICY['max_positions']:
                        orders.append(dict(terms,symbol=s,status='CONFIRMED_NO_CAPACITY'));continue
                    pending[s]=dict(terms,quantity=q,signal_date=str(prior_day.date()))
            # Stop fills at the end bound; do not fund any buy at this bar's open.
            for s in list(book.holdings):
                p=book.holdings[s];values=bars[tape.smap[s]]
                if not np.isfinite(values).all():raise ValueError(f'Missing held intraday {s}/{stamp}')
                outcome=resolve_bar_exit({'stop':p['stop'],'tp':None},dict(zip(FIELDS,values)))
                if outcome is not None:
                    price,reason,phase=outcome
                    sell(s,price,stamp+timedelta(minutes=5),'SL',gi)
            for s in book.holdings:book.marks[s]=float(bars[tape.smap[s],3])
            close_stamp=stamp+timedelta(minutes=5)
            observe(close_stamp,day,prior_day)
            gross=sum(p['quantity']*book.marks[s] for s,p in book.holdings.items())
            eq=equity()
            assert cash>=-1e-7 and gross<=eq+1e-7 and eq>0
            marks.append(dict(timestamp=close_stamp,equity=eq,gross=gross,cash=cash,allocation_scale=scale))
        last_daily=equity()
        daily.append(dict(date=day,cash=cash,gross=gross,equity=last_daily,positions=len(book.holdings)))
        for row in candidates:
            if confirmation and row['symbol'] not in attempted:
                audit.append(dict(date=day,symbol=row['symbol'],status='NO_CONFIRMED_BREAKOUT'))
        if number%50==0:
            save(OUT/'progress.json',dict(status='RUNNING',phase='REPLAY_5M',case=case,period=period,arm=arm,
                completed=number+1,total=len(selected),date=str(day.date())))
    opened=[dict(symbol=s,quantity=p['quantity'],entry_date=p['entry_time'].isoformat(),
        entry_price=p['price'],mark=book.marks[s],stop=p['stop']) for s,p in book.holdings.items()]
    report=summarize_portfolio(daily,trades,4000.,opened,cost)
    curve=np.r_[4000.,[m['equity'] for m in marks]]
    report.update(max_drawdown_daily_close_pct=report['max_drawdown_pct'],
        max_drawdown_pct=float(100*(curve/np.maximum.accumulate(curve)-1).min()),
        average_gross_capital=float(np.mean([m['gross'] for m in marks])),
        maximum_gross_capital=float(max(m['gross'] for m in marks)),
        average_gross_equity_pct=float(np.mean([m['gross']/m['equity'] for m in marks])*100),
        case=case,period=period,arm=arm,horizon=horizon,confirmation=confirmation,dd15=dd,
        status='COMPLETED_MATCHED_COVERAGE_RETROSPECTIVE',full_universe_coverage=False,full_live_parity=False,
        buys=sum(r['status']=='BOUGHT' for r in audit),data_gate_rejections=sum(r['status']=='MATCHED_DATA_GATE' for r in audit),
        final_positions=len(opened),drawdown_basis='Five-minute completed closes; no invented intrabar extrema',
        liquidation=liq.summary(),no_forced_terminal_liquidation=True,
        start=str(tape.days[selected[0]].date()),end=str(tape.days[selected[-1]].date()))
    dest.mkdir(parents=True,exist_ok=False)
    pd.DataFrame(daily).to_csv(dest/'equity.csv',index=False)
    pd.DataFrame(marks).to_parquet(dest/'marks.parquet',index=False)
    pd.DataFrame(trades).to_csv(dest/'trades.csv',index=False)
    pd.DataFrame(audit).to_csv(dest/'entry-audit.csv',index=False)
    pd.DataFrame(orders).to_json(dest/'confirmation-orders.json',orient='records',date_format='iso',indent=2)
    report['files']={f:digest(dest/f) for f in ['equity.csv','marks.parquet','trades.csv','entry-audit.csv','confirmation-orders.json']}
    save(dest/'report.json',report)
    LOG.info('%s %s %s return=%.2f DD=%.2f trades=%s events=%s',case,period,arm,
        report['return_pct'],report['max_drawdown_pct'],report['closed_trades'],len(liq.events))
    return report


def main():
    if (OUT/'protocol.json').exists():
        frozen=json.loads((OUT/'protocol.json').read_text())
        assert all(digest(p)==h for p,h in frozen['sources'].items()),'Source changed: new protocol required'
        if (OUT/'report.json').exists():
            print('Completed experiment already exists; no rerun')
            return
    started=time.monotonic()
    tape=Tape()
    dependencies=[Path(__file__),Path('config.yaml'),Path('common/winner_pyramiding.py'),
        Path('common/winner_delayed.py'),Path('common/winner_risk_state.py'),Path('risk_management/circuit_breaker.py'),
        Path('backtesting/adaptive_breaker.py'),Path('backtesting/winner_global_liquidation.py'),
        PRIOR/'protocol.json',PRIOR/'report.json',OUT/'inputs/manifest.json',OUT/'recovery/report.json']
    dependencies.append(OUT/'split-qualification/report.json')
    dependencies.append(OUT/'tail-recovery/report.json')
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(p):digest(p) for p in dependencies},arms=ARMS,original_policy=POLICY,
        native_confirmation=asdict(tape.native_policy),dd15_guard={k:getattr(tape.risk,k) for k in GUARD_FIELDS},
        dd15_force_close_fraction=.5,dd15_state='Native CampaignRiskState/B4 and GlobalLiquidation observation decisions',
        execution='Research cash ledger; next observed open after known trigger, standing stops first',
        confirmation_scope='Native cross of previous session high + two closes; delay930s, one IOC ceiling1%; next session only',
        no_stale_twenty_session_entry_plans=True,no_reinforcement=True,keep_full_positions=True,
        horizons={'winner_h10':10,'parcours_h20':20},initial_equity=4000.,leverage=1.,
        annual_reset=True,additional_continuous=True,end=str(END.date()),same_oracle_scores=True,new_models=0,
        shared_data_gate='Same prospective-entry key mask for all4 arms; full 5m prior and future holding sessions, frozen daily provider/identity gate',
        future_data_gate_bias=True,universe_uses_2026_outcomes=True,independent_validation=False,
        split_qualification='Exclude windows crossing provider-declared split-basis transitions; never count a raw split as a return',
        full_live_parity=False,sql_writes=False,broker_calls=0,production_changed=False)
    if not (OUT/'protocol.json').exists():save(OUT/'protocol.json',protocol)
    results=[]
    for case in CASES:
        for period in ('2024','2025','2026','continuous'):
            for arm in ARMS:
                results.append(run_case(tape,case,period,arm))
                rows=[{k:v for k,v in r.items() if k not in ('liquidation','open_positions','files')} for r in results]
                pd.DataFrame(rows).to_csv(OUT/'comparison.csv',index=False)
    protocol=json.loads((OUT/'protocol.json').read_text())
    assert all(digest(p)==h for p,h in protocol['sources'].items())
    save(OUT/'report.json',dict(status='COMPLETED_MATCHED_COVERAGE_RETROSPECTIVE',runs=len(results),cases=results,
        elapsed_seconds=time.monotonic()-started,sql_writes=False,broker_calls=0,production_changed=False))
    save(OUT/'progress.json',dict(status='COMPLETED_MATCHED_COVERAGE_RETROSPECTIVE',completed=len(results),total=32))


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbidden_http(*args,**kwargs):
        raise RuntimeError('HTTP forbidden during the frozen financial replay')
    requests.Session.request=forbidden_http
    main()
