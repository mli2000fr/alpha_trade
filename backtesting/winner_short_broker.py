"""Isolated in-memory SHORT ledger. Not connected to any live broker.

LONG methods delegate to the existing replay broker. The shared cash ledger
marks SHORT stock liabilities negatively; sale proceeds do not create equity
or extra gross buying power. Tested independently before replay integration.
"""
from copy import deepcopy
from datetime import date
import math
from types import SimpleNamespace

from common.winner_pyramiding import aware,regular_bounds,resolve_bar_exit
from backtesting.winner_clock import at_observed_open,next_observed_open
from backtesting.winner_intraday import ReplayBroker
from backtesting.winner_short import is_short,short_exit


class ShortReplayBroker(ReplayBroker):
    is_winner_replay=True

    def __init__(self,engine,*,fee,borrow_fee_annual):
        super().__init__(engine,fee=fee)
        if type(borrow_fee_annual) not in (int,float) or not math.isfinite(borrow_fee_annual) or not 0<=borrow_fee_annual<=1:
            raise ValueError('SHORT annual borrow fee must be in [0,1]')
        if self.constraints.account_type!='margin':raise ValueError('SHORT replay requires margin account')
        self.borrow_fee_annual=float(borrow_fee_annual);self.borrow_fees=0.;self.short_reservations={}

    def equity(self):
        return (self.cash+sum(v for _,v in self.unsettled)+sum(c['amount'] for c in self.claims)+
            sum((-1 if l.get('side')=='short' else 1)*l['remaining']*self.marks[l['symbol']] for l in self.lots.values()))

    def positions(self):
        grouped={};sides={}
        for lot in self.lots.values():
            if not lot['remaining']:continue
            symbol=lot['symbol'];side=lot.get('side','long')
            if symbol in sides and sides[symbol]!=side:raise ValueError('Opposite-side lots share a symbol')
            sides[symbol]=side;grouped[symbol]=grouped.get(symbol,0)+lot['remaining']
        return [dict(symbol=s,side=sides[s],qty=q,quantity=q,mark=self.marks[s]) for s,q in grouped.items()]

    def financing_balance(self):
        # Conservative restriction: borrowed-stock sale proceeds cannot finance
        # another long position for free. Gross buying power remains native.
        return self.cash-sum(l['remaining']*l['entry'] for l in self.lots.values() if l.get('side')=='short')

    def pending_entries(self,exclude=None):
        return [dict(symbol=r['symbol'],side=r['side'],notional=float(r['qty'])*float(r.get('reserved_price') or r['limit_price']))
            for key,r in self.orders.items() if key!=exclude and r['status']=='new' and
            (r.get('short_entry') or r.get('side')=='buy' and not r.get('short_exit') and not r.get('parent')) and
            (r.get('time_in_force')=='day' or r.get('replay_next_open')) and
            (r.get('reserved_price') is not None or r.get('limit_price') is not None)]

    def submit(self,state,intent):
        if not is_short(state):return super().submit(state,intent)
        if intent.intent_id in self.orders:raise ValueError('Duplicate SHORT simulated order')
        self.intents[intent.intent_id]=intent
        entry=intent.intent_role=='entry'
        raw=dict(id=intent.intent_id,type=intent.order_type,status='new',filled_qty='0',filled_avg_price=None,
            client_order_id=intent.submission_key,qty=str(intent.qty),side=intent.side,symbol=intent.symbol,
            time_in_force=intent.time_in_force,stop_price=intent.stop_price,limit_price=intent.limit_price,
            campaign_id=state['campaign_id'],short_entry=entry,short_exit=not entry)
        self.orders[intent.intent_id]=raw
        if entry:
            if intent.side!='sell':raise ValueError('SHORT entry must sell')
            raw['reserved_price']=self.short_reservations[intent.intent_id]
            raw['entry_kind']='ADD' if state['lots'] else 'ENTRY'
            if not at_observed_open(self.now):
                from common.winner_delayed import delayed_entry
                if not delayed_entry(state,'ADD' if state['lots'] else 'ENTRY'):raise ValueError('Off-grid SHORT needs delayed contract')
                following=next_observed_open(self.now)
                raw.update(replay_next_open=following.isoformat() if following else None,
                    replay_decision_at=self.now.isoformat(),replay_ioc_proxy=True)
                if following is None:raw['status']='canceled'
                self.events.append(dict(time=self.now,symbol=intent.symbol,event='DELAYED_SHORT_DECISION',
                    execution_open=raw['replay_next_open'],quantity=intent.qty,limit_price=intent.limit_price))
            else:
                self.fill_short(intent,raw,self.marks[intent.symbol],state['campaign_id'])
                if raw['status']=='new' and intent.time_in_force!='day':raw['status']='canceled'
        elif intent.intent_role=='exit':
            if intent.side!='buy':raise ValueError('SHORT exit must buy to cover')
            if intent.time_in_force=='opg':raw['queued_moo']=True
            else:
                if not at_observed_open(self.now):raise ValueError('SHORT cover requires observed open')
                reason=next((o.get('exit_reason') for o in state['operations'] if o['key']==intent.intent_id),None)
                self.close(intent.symbol,intent.qty,self.marks[intent.symbol],intent.intent_id,reason or 'HORIZON_LATE_MARKET')
        else:raise ValueError('Unsupported SHORT replay order')
        return SimpleNamespace(broker_order_id=intent.intent_id)

    def fill_short(self,intent,raw,price,campaign_id):
        if (intent.limit_price is not None and price<intent.limit_price-1e-8
            or price>raw['reserved_price']+1e-8
            or intent.qty*price*(1+self.fee)>self.capacity(exclude=intent.intent_id)+1e-6):return
        if any(p['symbol']==intent.symbol and p['side']!='short' for p in self.positions()):raise ValueError('LONG holding conflicts with SHORT fill')
        self.cash+=intent.qty*price*(1-self.fee);self.fees+=intent.qty*price*self.fee
        self.lots[intent.intent_id]=dict(symbol=intent.symbol,side='short',quantity=intent.qty,remaining=intent.qty,
            entry=price,entry_time=self.now,entry_fee=intent.qty*price*self.fee,campaign_id=campaign_id,
            entry_kind=raw['entry_kind'],borrow_remaining=0.)
        self.charge_borrow(self.now.date(),only=intent.intent_id)
        self.events.append(dict(time=self.now,symbol=intent.symbol,event='SHORT_FILL',quantity=intent.qty,price=price,
            costs=intent.qty*price*self.fee,decision_time=raw.get('replay_decision_at',self.now.isoformat()),
            execution_proxy='NEXT_OBSERVED_5M_OPEN' if raw.get('replay_ioc_proxy') else 'OBSERVED_5M_OPEN'))
        self.filled(raw,intent.qty,price)

    def charge_borrow(self,day,only=None):
        for key,lot in self.lots.items():
            if (only is not None and key!=only or lot.get('side')!='short' or not lot['remaining']
                or lot.get('borrow_day')==day):continue
            charge=lot['remaining']*self.marks[lot['symbol']]*self.borrow_fee_annual/252
            self.cash-=charge;self.borrow_fees+=charge;lot['borrow_remaining']+=charge;lot['borrow_day']=day
            self.events.append(dict(time=self.now,symbol=lot['symbol'],event='SHORT_BORROW_FEE',costs=charge))

    def corporate_action(self,action,day):
        shorts=[l for l in self.lots.values() if l['symbol']==action['symbol'] and l['remaining'] and l.get('side')=='short']
        if not shorts:return super().corporate_action(action,day)
        payable=action.get('payable_date');amount=float(action.get('amount_per_share') or 0)
        if (action['ca_type'] not in ('cash_dividend','special_dividend') or not payable or str(payable)=='NaT'
            or not math.isfinite(amount) or amount<=0 or action.get('currency')!='USD' or date.fromisoformat(str(payable)[:10])<day):
            raise ValueError('SHORT corporate action unqualified')
        for lot in shorts:
            value=-lot['remaining']*amount
            self.claims.append(dict(amount=value,payable_date=date.fromisoformat(str(payable)[:10])))
            lot['dividends_remaining']=lot.get('dividends_remaining',0)+value;self.dividends+=value
        self.settle(day)

    def protect(self,state,lot,parent,*,tp_intent,stop_intent):
        if not is_short(state):return super().protect(state,lot,parent,tp_intent=tp_intent,stop_intent=stop_intent)
        for intent in (stop_intent,tp_intent):
            if intent:
                self.intents[intent.intent_id]=intent
                self.orders[intent.intent_id]=dict(id=intent.intent_id,status='new',type=intent.order_type,
                    side='buy',filled_qty='0',qty=str(intent.qty),stop_price=intent.stop_price,limit_price=intent.limit_price,
                    parent=parent.intent_id,peer=tp_intent.intent_id if intent==stop_intent and tp_intent else stop_intent.intent_id)
        return (SimpleNamespace(broker_order_id=tp_intent.intent_id) if tp_intent else None,SimpleNamespace(broker_order_id=stop_intent.intent_id))

    def tighten(self,state,lot,intent):
        if not is_short(state):return super().tighten(state,lot,intent)
        raw=self.orders[lot['stop_order_id']]
        if raw['status']!='new' or intent.stop_price>raw['stop_price']:raise ValueError('SHORT stop must only tighten')
        updated=deepcopy(raw);updated.update(id=intent.intent_id,stop_price=intent.stop_price)
        if not at_observed_open(self.now):
            following=next_observed_open(self.now)
            from zoneinfo import ZoneInfo
            updated.update(replay_old_stop=raw['stop_price'],replay_stop_from=(following or regular_bounds(
                self.now.astimezone(ZoneInfo('America/New_York')).date())[1]).isoformat())
        self.orders[intent.intent_id]=updated;self.intents[intent.intent_id]=intent;raw['status']='replaced'
        if updated.get('peer') in self.orders:self.orders[updated['peer']]['peer']=intent.intent_id
        if at_observed_open(self.now) and self.marks[intent.symbol]>=intent.stop_price:
            self.close(intent.symbol,intent.qty,self.marks[intent.symbol],intent.intent_id,'TIGHTENED_STOP_GAP',parent=updated['parent'])
        return SimpleNamespace(broker_order_id=intent.intent_id)

    def close(self,symbol,quantity,price,order_id,reason,*,parent=None):
        if not math.isfinite(price) or price<=0 or quantity<=0 or not float(quantity).is_integer():
            raise ValueError('Qualified whole SHORT cover quantity/price required')
        shorts=[l for l in self.lots.values() if l['symbol']==symbol and l['remaining'] and l.get('side')=='short']
        if not shorts:return super().close(symbol,quantity,price,order_id,reason,parent=parent)
        remaining=quantity
        for key,lot in self.lots.items():
            if lot['symbol']!=symbol or parent and parent!=key or not lot['remaining']:continue
            used=min(remaining,lot['remaining']);fee=used*price*self.fee
            entry_fee=lot['entry_fee']*used/lot['quantity']
            dividends=lot.get('dividends_remaining',0)*used/lot['remaining']
            borrow=lot['borrow_remaining']*used/lot['remaining']
            self.cash-=used*price+fee;self.fees+=fee
            lot['dividends_remaining']=lot.get('dividends_remaining',0)-dividends;lot['borrow_remaining']-=borrow
            pnl=used*(lot['entry']-price)-entry_fee-fee+dividends-borrow
            self.trades.append(dict(symbol=symbol,quantity=used,entry_date=lot['entry_time'],exit_date=self.now,
                entry_price=lot['entry'],exit_price=price,pnl=pnl,return_pct=pnl/(used*lot['entry']),
                holding_days=(self.now-lot['entry_time']).total_seconds()/86400,exit_reason=reason,
                is_day_trade=self.now.date()==lot['entry_time'].date(),side='sell',entry_fees=entry_fee,exit_fees=fee,
                dividends=dividends,borrow_fees=borrow,campaign_id=lot['campaign_id']))
            lot['remaining']-=used;remaining-=used
            if not remaining:break
        if remaining:raise ValueError('SHORT cover exceeds remaining quantity')
        raw=self.orders[order_id];self.filled(raw,quantity,price)
        self.events.append(dict(time=self.now,symbol=symbol,event='COVER_FILL',quantity=quantity,price=price,costs=quantity*price*self.fee))
        if raw.get('peer') in self.orders:self.orders[raw['peer']]['status']='canceled'

    def expire_day_entries(self):
        super().expire_day_entries()
        for raw in self.orders.values():
            if raw.get('short_entry') and raw['status']=='new' and (raw.get('time_in_force')=='day' or raw.get('replay_next_open')):raw['status']='expired'

    def resolve(self,bars,*,opening):
        # Same observation clock as the LONG broker. Each order is processed
        # once; no closing liability is mistaken for a new LONG purchase.
        for key,raw in list(self.orders.items()):
            if raw['status']!='new':continue
            intent=self.intents[key]
            entry=raw.get('short_entry') or (intent.side=='buy' and not raw.get('short_exit') and not raw.get('parent'))
            def fill(price):
                if raw.get('short_entry'):self.fill_short(intent,raw,price,intent.winner_campaign_id)
                else:self.fill_buy(intent,raw,price,intent.winner_campaign_id)
            if opening and raw.get('replay_next_open'):
                expected=aware(raw['replay_next_open'])
                if self.now<expected:continue
                if self.now==expected and intent.symbol in bars:fill(float(bars[intent.symbol]['open']))
                if raw['status']=='new':
                    raw['status']='canceled'
                    self.events.append(dict(time=self.now,symbol=intent.symbol,event='DELAYED_ENTRY_CANCELED',
                        reason='NEXT_OPEN_MISSING' if self.now!=expected or intent.symbol not in bars else 'LIMIT_OR_CAPACITY',decision_time=raw['replay_decision_at']))
                continue
            if intent.symbol not in bars:continue
            bar=bars[intent.symbol]
            if opening and entry and intent.time_in_force=='day':fill(float(bar['open']));continue
            if opening and raw.get('queued_moo'):
                self.close(intent.symbol,intent.qty,float(bar['open']),key,'HORIZON_OPEN');continue
            if not raw.get('parent') or raw['parent'] not in self.lots:continue
            lot=self.lots[raw['parent']]
            if not lot['remaining'] or raw['type']!='stop':continue
            peer=self.orders.get(raw.get('peer'),{});stop=raw['stop_price']
            if raw.get('replay_stop_from') and (self.now<aware(raw['replay_stop_from']) or not opening and self.now==aware(raw['replay_stop_from'])):stop=raw['replay_old_stop']
            levels=dict(stop=float(stop),tp=peer.get('limit_price'))
            outcome=short_exit(levels,bar) if lot.get('side')=='short' else resolve_bar_exit(levels,bar)
            if outcome is None or (outcome[2]=='OPEN')!=opening:continue
            price,reason,_=outcome;selected_id=raw['peer'] if reason.startswith('TP') else key
            self.close(intent.symbol,lot['remaining'],price,selected_id,reason,parent=raw['parent'])
