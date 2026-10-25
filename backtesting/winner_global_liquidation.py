"""Causal global drawdown exits for the LONG intraday campaign replay.

A completed close can request a sale, never fill it retroactively. Exits use
the next observed regular opening print, standing stops first, actual remaining
lots, ordinary broker cash/fees and the coordinator's durable EXIT journal.
"""
import math
from datetime import datetime
import pandas as pd

from execution_engine.models import IntentRole
from execution_engine.winner_broker import make_intent
from execution_engine.winner_runtime import WinnerCampaignRuntime, TERMINAL


def close_campaign(record,store,repo,book,exec_config,stamp,event_id):
    rt=WinnerCampaignRuntime(store,repo,book,exec_config,market=lambda *_:{},risk=lambda *_:{},now=stamp)
    row=store.get(record['state']['campaign_id'])
    rt.state,rt.version=row['state'],row['version']
    rt.reconcile()
    if rt.pending():
        raise ValueError('Global liquidation requires resolution of pending campaign operations')
    rt.reconcile_lots()
    for lot in rt.state['lots']:
        if not lot['remaining']:
            continue
        for field in ('stop_order_id','tp_order_id'):
            if lot.get(field):
                raw=book.cancel(lot[field]);rt.apply_lot_sale(lot,raw);rt.save()
                if raw['status'] not in TERMINAL:
                    raise ValueError('Global liquidation protection cancellation unconfirmed')
    quantity=sum(l['remaining'] for l in rt.state['lots'])
    if quantity:
        position=next((p for p in book.positions() if p['symbol']==rt.state['symbol']),None)
        if position is None or position['side']!='long' or position['qty']!=quantity:
            raise ValueError('Global liquidation lot/broker quantity mismatch')
        intent=make_intent(rt.state,rt.state['campaign_id']+'-global-dd-'+str(event_id),
            quantity=quantity,side='sell',role=IntentRole.EXIT,order_type='market',
            price=book.marks[rt.state['symbol']])
        operation=rt.reserve('EXIT',intent,booked_quantity=0,execution_timing='GLOBAL_DD_NEXT_OPEN',
            exit_reason='GLOBAL_DRAWDOWN',drawdown_event_id=event_id)
        order=book.submit(rt.state,intent)
        operation.update(status='SUBMITTED',broker_id=order.broker_order_id);rt.save()
        rt.reconcile()
    if any(l['remaining'] for l in rt.state['lots']):
        raise ValueError('Global liquidation not completely filled; no optimistic continuation')
    rt.state['status']='CLOSED';rt.save()
    return quantity


class GlobalLiquidation:
    def __init__(self,cfg,risk,exec_cfg):
        self.enabled=bool(exec_cfg.force_close_on_breaker or risk.force_close_on_breaker)
        self.fraction=float(exec_cfg.force_close_pct if exec_cfg.force_close_on_breaker else risk.force_close_pct)
        self.halt=bool(getattr(cfg,'winner_global_drawdown_halt',False))
        self.threshold=float(risk.max_portfolio_drawdown_pct)
        self.hard_threshold=getattr(cfg,'winner_hard_drawdown_pct',None)
        self.cycle_threshold=getattr(cfg,'winner_cycle_drawdown_pct',None)
        self.cooldown_months=getattr(cfg,'winner_drawdown_cooldown_months',0)
        if self.enabled and not 0<self.fraction<=1:
            raise ValueError('Qualified global liquidation fraction in (0,1] required')
        if self.halt and (not self.enabled or self.fraction!=1 or not 0<self.threshold<1):
            raise ValueError('Global drawdown halt requires enabled total liquidation and a valid threshold')
        if self.hard_threshold is not None and (not self.enabled or self.halt
                or type(self.hard_threshold) not in (float,int)
                or not math.isfinite(self.hard_threshold) or not self.threshold<self.hard_threshold<1):
            raise ValueError('Hard drawdown stop requires enabled partial mode and soft < hard < 1')
        if self.cycle_threshold is not None:
            if (self.hard_threshold is None or type(self.cycle_threshold) not in (float,int)
                    or not math.isfinite(self.cycle_threshold)
                    or not self.threshold<self.cycle_threshold<self.hard_threshold
                    or type(self.cooldown_months) is not int or self.cooldown_months<1):
                raise ValueError('Cycle stop requires soft < cycle < global hard and positive calendar months')
        elif self.cooldown_months:
            raise ValueError('Cooldown requires a qualified cycle threshold')
        self.peak=float(cfg.initial_equity)
        self.halted=False;self.pending=None;self.events=[];self.counter=0;self.min_drawdown=0.
        self.cycle_peak=self.peak;self.cycle=1;self.cycle_stopped=False
        self.paused_until=None;self.resumes=[]

    @property
    def blocks_entries(self):
        return self.halted or self.cycle_stopped

    def resume(self,stamp,book):
        """Caller invokes only at an official session open, before admitting signals."""
        if (self.halted or not self.cycle_stopped or self.pending is not None
                or self.paused_until is None or stamp<self.paused_until):
            return False
        if book.positions():
            raise ValueError('Cooldown cannot resume before complete liquidation')
        equity=book.equity()
        # Global high-watermark survives every cycle. A cash loss cannot bypass it.
        if equity<=self.peak*(1-self.hard_threshold):
            self.halted=True
            return False
        self.cycle+=1;self.cycle_peak=equity;self.cycle_stopped=False
        event=dict(cycle=self.cycle,resumed_at=stamp.isoformat(),equity=equity,
            global_peak=self.peak,previous_paused_until=self.paused_until.isoformat())
        self.resumes.append(event);self.paused_until=None
        book.events.append(dict(time=stamp,event='GLOBAL_DD_RESUME',cycle=self.cycle,equity=equity))
        return True

    def observe(self,stamp,equity,book,evaluated):
        if not self.enabled:
            return
        if not math.isfinite(equity) or equity<=0:
            raise ValueError('Global liquidation requires finite positive portfolio equity')
        self.peak=max(self.peak,equity)
        self.min_drawdown=min(self.min_drawdown,equity/self.peak-1)
        if self.halted:
            return
        hard_hit=self.hard_threshold is not None and equity<=self.peak*(1-self.hard_threshold)
        if not self.cycle_stopped:
            self.cycle_peak=max(self.cycle_peak,equity)
        cycle_hit=(self.cycle_threshold is not None and not self.cycle_stopped
            and equity<=self.cycle_peak*(1-self.cycle_threshold))
        if self.pending and not hard_hit:
            return
        if self.cycle_stopped and not hard_hit:
            return
        # Full halt uses the SAME historical high-watermark as reported global DD.
        # Partial mode instead mirrors the configured native B4 episode transition.
        hit=hard_hit or cycle_hit or ((equity<=self.peak*(1-self.threshold)) if self.halt else evaluated['circuit_breaker'].just_tripped())
        if not hit:
            return
        positions=book.positions()
        positions.sort(key=lambda p:(sum(l['remaining']*(book.marks[p['symbol']]-l['entry'])
            for l in book.lots.values() if l['symbol']==p['symbol']),p['symbol']))
        total=self.halt or hard_hit or cycle_hit
        count=len(positions) if total else min(len(positions),max(1,int(len(positions)*self.fraction+.5)))
        self.counter+=1
        superseded=self.pending['event_id'] if self.pending is not None else None
        self.pending=dict(event_id=self.counter,detected_at=stamp.isoformat(),equity_at_detection=equity,
            peak_at_detection=self.peak,drawdown_at_detection_pct=100*(equity/self.peak-1),
            native_reference_peak=evaluated['reference_peak'],symbols=[p['symbol'] for p in positions[:count]],
            force_close_pct=1. if total else self.fraction,
            threshold_pct=self.hard_threshold if hard_hit else self.cycle_threshold if cycle_hit else self.threshold,
            reference_peak_at_detection=self.cycle_peak if self.cycle_threshold is not None and not hard_hit else self.peak,
            cycle_peak_at_detection=self.cycle_peak,cycle=self.cycle,
            reason='HARD_DRAWDOWN' if hard_hit else 'CYCLE_DRAWDOWN' if cycle_hit else 'SOFT_DRAWDOWN',
            supersedes_event_id=superseded)
        self.halted=self.halt or hard_hit
        self.cycle_stopped=self.cycle_stopped or cycle_hit
        book.events.append(dict(time=stamp,event='GLOBAL_DD_TRIGGER',drawdown_event_id=self.counter,
            equity=equity,reference_peak=self.peak,threshold=self.pending['threshold_pct']))

    def execute(self,stamp,store,repo,book,exec_cfg):
        if self.pending is None:
            return
        event=self.pending
        if stamp<datetime.fromisoformat(event['detected_at']):
            raise ValueError('Global liquidation cannot execute before detection')
        records={r['state']['symbol']:r for r in store.rows() if any(l['remaining'] for l in r['state']['lots'])}
        quantities={}
        for symbol in event['symbols']:
            # Standing stop/MOO can fill first at this opening; never sell twice.
            if symbol in records:
                quantities[symbol]=close_campaign(records[symbol],store,repo,book,exec_cfg,stamp,event['event_id'])
        if self.blocks_entries and book.positions():
            raise ValueError('Total global liquidation left an open broker position')
        event.update(executed_at=stamp.isoformat(),quantities=quantities,equity_after=book.equity())
        self.events.append(event);self.pending=None
        if event['reason']=='CYCLE_DRAWDOWN':
            # Three calendar months from the NY liquidation date, not 90 days.
            # Reentry is on the first official opening on/after that local date.
            self.paused_until=(pd.Timestamp(stamp).tz_convert('America/New_York').normalize()
                +pd.DateOffset(months=self.cooldown_months)).to_pydatetime()
            event['paused_until']=self.paused_until.isoformat()
        if self.blocks_entries:
            for row in store.rows():
                if not row['state']['lots']:
                    state=row['state'];state['status']='CANCELED'
                    store.save(state,row['version'])

    def summary(self):
        return dict(enabled=self.enabled,threshold_pct=self.threshold,force_close_pct=self.fraction,
            hard_threshold_pct=self.hard_threshold,
            cycle_threshold_pct=self.cycle_threshold,cooldown_months=self.cooldown_months,
            cycle=self.cycle,cycle_peak=self.cycle_peak,cycle_stopped=self.cycle_stopped,
            paused_until=self.paused_until.isoformat() if self.paused_until is not None else None,
            resumes=self.resumes,
            historical_peak_halt=self.halt,halted=self.halted,peak=self.peak,
            max_observed_drawdown_pct=100*self.min_drawdown,events=self.events,
            pending=self.pending,rearm=('NONE_UNTIL_END_OF_RUN' if self.halt else
                'CYCLE_CALENDAR_COOLDOWN_WITH_PRESERVED_GLOBAL_HARD_STOP' if self.cycle_threshold is not None else
                'NATIVE_B4_SOFT_ONLY_HARD_STOP_UNTIL_END_OF_RUN' if self.hard_threshold is not None else 'NATIVE_B4'),
            execution='NEXT_OBSERVED_REGULAR_OPEN_AFTER_KNOWN_MARK_STANDING_STOPS_FIRST')
