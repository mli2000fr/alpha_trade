"""Research-only core/piloted allocation and causal progressive recovery.

No production engine changes. One native account, integer shares, real fills,
unchanged SL/open11 on the core remaining after a piloted-portion reduction.
"""
import math
import pandas as pd

from scripts.research.us_q051_internal_liquidation_policy_20261118 import (
    ProtectedEntries, InternalLiquidation, prior_state, close_campaign)


def recovery_states(observer, shadow, mode):
    if mode not in ('OLD','PROGRESSIVE'):raise ValueError('Unknown recovery mode')
    if observer.index.has_duplicates or not observer.index.is_monotonic_increasing:
        raise ValueError('Ambiguous observer clock')
    ret10=(shadow/shadow.shift(10)-1).reindex(observer.index)
    equity=shadow.reindex(observer.index)
    phase='NORMAL';up=stable=0;anchor=None;rows=[]
    for day,row in observer.iterrows():
        transition='';previous=phase
        if mode=='OLD':
            phase='PROTECTED' if row.active else 'NORMAL';transition=row.transition
        elif row.transition=='ON':
            phase='PROTECTED';transition='ON';up=stable=0;anchor=None
        elif phase=='PROTECTED':
            up=up+1 if pd.notna(ret10.loc[day]) and ret10.loc[day]>0 else 0
            if up>=2:
                phase='PROBE';transition='PROBE';anchor=float(equity.loc[day]);stable=0
        elif phase=='PROBE':
            improving=(pd.notna(ret10.loc[day]) and ret10.loc[day]>0
                and pd.notna(equity.loc[day]) and equity.loc[day]>=anchor)
            stable=stable+1 if improving else 0
            if stable>=5:phase='NORMAL';transition='OFF';up=stable=0
        rows.append(dict(signal_date=day,phase=phase,previous_phase=previous,
            active=phase!='NORMAL',transition=transition,observer_active=bool(row.active),
            observer_transition=row.transition,shadow_return10=ret10.loc[day],
            positive_count=up,stable_count=stable,probe_anchor=anchor))
    return pd.DataFrame(rows).set_index('signal_date')


class CorePilotEntries:
    """Native-approved quantity split within ONE order/account, never increased.

    Core shares use ceil(N/2); the piloted remainder floor(N/2) can be gated.
    The20% volatility entry budget applies to the piloted holdings relative to
    its equity allocation only. It is NOT a20% guarantee for the whole account.
    """
    def __init__(self,states,close,fraction):
        if fraction not in (.5,1.):raise ValueError('Pilot fraction must be .5 or1')
        self.states=states;self.fraction=fraction;self.receipts=[];self.allocations={}
        self.full=ProtectedEntries(states,close)

    def select(self,signal_day,rows,cutoff):
        row=self.states.loc[pd.Timestamp(signal_day)]
        if self.fraction==1 and row.phase=='PROTECTED':
            return self.full.select(signal_day,rows,cutoff)
        if pd.Timestamp(cutoff).tz_convert('America/New_York').date()<=pd.Timestamp(signal_day).date():
            raise ValueError('State cannot affect same-session entries')
        return dict(selected=rows.symbol.tolist(),incomplete=False)

    def _remember(self,state,quantity,core):
        self.allocations[state['symbol']]=dict(campaign_id=state['campaign_id'],
            initial_quantity=int(quantity),core_quantity=min(int(quantity),int(core)))

    def pilot_positions(self,positions):
        out=[]
        for position in positions:
            assigned=self.allocations.get(position['symbol'])
            if assigned is None:raise ValueError('Held campaign has no core/pilot allocation')
            quantity=int(position['quantity']);pilot=max(0,quantity-assigned['core_quantity'])
            if pilot:out.append(dict(position,quantity=pilot,qty=pilot))
        return out

    def wrap(self,native):
        full_protected=self.full.wrap(native)
        def approve(state,version,proposed,snapshot,now,*,context):
            day=pd.Timestamp(snapshot['opening_at']).tz_convert('America/New_York').date()
            signal,row=prior_state(self.states,day)
            # Preserve the original full-liquidation/old-recovery admission path.
            if self.fraction==1 and row.phase=='PROTECTED':
                result=full_protected(state,version,proposed,snapshot,now,context=context)
                self._remember(state,result['max_quantity'],0)
                return result
            original=native(state,version,proposed,snapshot,now,context=context)
            native_qty=int(original['max_quantity'])
            core=0 if self.fraction==1 else (native_qty+1)//2
            pilot=native_qty-core;reason='NORMAL'
            if row.phase=='PROBE':
                pilot=pilot//2;reason='HALF_PILOT_RECOVERY'
            elif row.phase=='PROTECTED':
                selected=self.full.gate(signal, pd.DataFrame({'symbol':[state['symbol']]}),now)
                if not selected['selected']:pilot=0;reason='PILOT_SPY_GATE'
                elif pilot:
                    from risk_management.portfolio_volatility import portfolio_limit
                    if context['pending_entries']:raise ValueError('Unexpected pending entry in daily core/pilot study')
                    prior=self.full.budget.returns.index[self.full.budget.returns.index<pd.Timestamp(day)][-1]
                    price=float(snapshot['entry_open'] if snapshot.get('price_source')=='OBSERVED_5M_OPEN' else snapshot['daily_open'])
                    decision=portfolio_limit(self.full.budget.returns,prior_day=prior,
                        positions=self.pilot_positions(context['positions']),pending=[],
                        symbol=state['symbol'],price=price,equity=context['equity']*self.fraction,
                        proposed=pilot,target=.20,lookback=60)
                    pilot=min(pilot,int(decision['quantity']));reason=decision['reason']
                    self.full.budget.receipts.append(dict(time=str(now),symbol=state['symbol'],**decision,
                        sleeve_fraction=self.fraction,core_quantity=core))
            limit=core+pilot
            result=native(state,version,min(proposed,limit),snapshot,now,context=context) if limit<native_qty else original
            final=int(result['max_quantity'])
            if final>limit or final>native_qty:raise ValueError('Protection increased native entry')
            self._remember(state,final,core)
            self.receipts.append(dict(time=str(now),signal_date=str(signal.date()),symbol=state['symbol'],
                campaign_id=state['campaign_id'],phase=row.phase,native_quantity=native_qty,
                core_quantity=min(core,final),pilot_quantity=max(0,final-core),final_quantity=final,
                quantity_limit=limit,reason=reason))
            return result
        return approve


def reduce_campaign(record,store,repo,book,exec_config,stamp,event_id,quantity):
    """Native sell accounting, retained stop and due date; research REDUCE journal.

    A reduction is not a terminal EXIT. Marking it as EXIT would incorrectly
    prevent the native open11 deadline from selling the retained shares.
    """
    from execution_engine.models import IntentRole
    from execution_engine.winner_broker import make_intent
    from execution_engine.winner_runtime import WinnerCampaignRuntime,TERMINAL
    rt=WinnerCampaignRuntime(store,repo,book,exec_config,market=lambda *_:{},risk=lambda *_:{},now=stamp)
    row=store.get(record['state']['campaign_id']);rt.state,rt.version=row['state'],row['version']
    rt.reconcile()
    if rt.pending():raise ValueError('Reduction requires resolved operations')
    rt.reconcile_lots();due=rt.state['due_open']
    held=sum(l['remaining'] for l in rt.state['lots'])
    if not 0<quantity<held:raise ValueError('Qualified partial quantity required')
    if len([l for l in rt.state['lots'] if l['remaining']])!=1:
        raise ValueError('Study requires one initial fill, no reinforcement or fragmented lots')
    for lot in rt.state['lots']:
        if not lot['remaining']:continue
        for field in ('stop_order_id','tp_order_id'):
            if lot.get(field):
                raw=book.cancel(lot[field]);rt.apply_lot_sale(lot,raw);rt.save()
                if raw['status'] not in TERMINAL:raise ValueError('Reduction cancellation unconfirmed')
    if sum(l['remaining'] for l in rt.state['lots'])!=held:raise ValueError('Unexpected cancel race in isolated replay')
    key=rt.state['campaign_id']+'-pilot-reduce-'+str(event_id)
    intent=make_intent(rt.state,key,quantity=quantity,side='sell',role=IntentRole.EXIT,
        order_type='market',price=book.marks[rt.state['symbol']])
    operation=rt.reserve('RESEARCH_REDUCE',intent,booked_quantity=0,exit_reason='PILOT_PROTECTION',
        execution_timing='PREVIOUS_CLOSE_NEXT_OPEN',event_id=event_id)
    submitted=book.submit(rt.state,intent);raw=book.get(submitted.broker_order_id)
    if raw['status']!='filled':raise ValueError('Isolated reduction failed; no optimistic continuation')
    rt.book_sell(operation,raw);operation.update(status='DONE',broker_id=submitted.broker_order_id);rt.save()
    for index,lot in enumerate(rt.state['lots']):
        if not lot['remaining']:continue
        stop=make_intent(rt.state,key+'-rearm-'+str(index),quantity=lot['remaining'],side='sell',
            role=IntentRole.INITIAL_STOP,order_type='stop',stop=lot['stop'],parent=lot['parent_intent_id'])
        repair=rt.reserve('REARM',stop,lot_index=index)
        parent=book.intents[lot['parent_intent_id']]
        _,order=book.protect(rt.state,lot,parent,tp_intent=None,stop_intent=stop)
        book.orders[stop.intent_id]['peer']=None
        repair.update(status='SUBMITTED',broker_id=order.broker_order_id);rt.save();rt.reconcile()
    rt.reconcile_lots()
    if rt.state['due_open']!=due or sum(l['remaining'] for l in rt.state['lots'])!=held-quantity:
        raise ValueError('Reduction changed horizon or remaining quantity')
    rt.save();return quantity


class PilotLiquidation(InternalLiquidation):
    def __init__(self,states,policy):
        super().__init__(states);self.policy=policy

    def execute(self,stamp,store,repo,book,exec_cfg):
        if self.policy.fraction==1:return super().execute(stamp,store,repo,book,exec_cfg)
        if self.pending is None:return
        event=self.pending
        if stamp!=pd.Timestamp(event['detected_at']).to_pydatetime():raise ValueError('Reduction is not at next official open')
        records={r['state']['symbol']:r for r in store.rows() if any(l['remaining'] for l in r['state']['lots'])}
        quantities={};retained={}
        for symbol in event['symbols']:
            if symbol not in records:continue  # Standing stop/open11 executes first.
            record=records[symbol];allocation=self.policy.allocations.get(symbol)
            if allocation is None or allocation['campaign_id']!=record['state']['campaign_id']:
                raise ValueError('Missing campaign core allocation')
            # The broker has already resolved standing stops at this open;
            # the campaign journal can still contain yesterday's quantity.
            # Use the actual remaining holding, never sell a stale lot twice.
            actual=next((p for p in book.positions() if p['symbol']==symbol),None)
            held=int(actual['qty']) if actual is not None else 0
            if not held:
                quantities[symbol]=0;retained[symbol]=0;continue
            core=min(held,allocation['core_quantity']);quantity=held-core
            quantities[symbol]=reduce_campaign(record,store,repo,book,exec_cfg,stamp,event['event_id'],quantity) if quantity else 0
            retained[symbol]=core
        event.update(executed_at=stamp.isoformat(),quantities=quantities,retained_core=retained,equity_after=book.equity())
        self.events.append(event);self.pending=None
        book.events.append(dict(time=stamp,event='PILOT_PROTECTION_REDUCTION',**event))
