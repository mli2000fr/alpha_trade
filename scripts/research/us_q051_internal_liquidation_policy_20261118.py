"""Research-only ON -> native full exit, then conditional vol20 / SPY200.

No production patch persists. Official opens execute exits after standing stops;
the immutable previous-close state controls only the protected entry budget.
"""
import pandas as pd

from backtesting.winner_portfolio_budget import replay_protections
from scripts.research.us_q051_internal_protection_policy_20261117 import internal_states


def prior_state(states,day):
    prior=states.index[states.index<pd.Timestamp(day)]
    if not len(prior):raise ValueError('No causal previous-close internal protection state')
    signal=prior[-1]
    return signal,states.loc[signal]


class ProtectedEntries:
    def __init__(self,states,close):
        self.states=states;self.receipts=[]
        self.budget,self.gate=replay_protections(close,daily_entry=True,target=.20,lookback=60,
            regime=True,sma_window=200,bear_threshold=-.02)

    def select(self,signal_day,rows,cutoff):
        signal=pd.Timestamp(signal_day)
        if signal not in self.states.index:raise ValueError('Missing signal protection state')
        if pd.Timestamp(cutoff).tz_convert('America/New_York').date()<=signal.date():
            raise ValueError('Previous-close state cannot affect same-session entries')
        active=bool(self.states.loc[signal,'active'])
        selected=self.gate(signal_day,rows,cutoff) if active else dict(selected=rows.symbol.tolist(),incomplete=False)
        self.receipts.append(dict(signal_date=str(signal.date()),active=active,
            candidates=len(rows),selected=len(selected['selected'])))
        return selected

    def wrap(self,native):
        protected=self.budget.wrap(native)
        def approve(state,version,quantity,snapshot,now,*,context):
            day=pd.Timestamp(snapshot['opening_at']).tz_convert('America/New_York').date()
            _,row=prior_state(self.states,day)
            return (protected if bool(row.active) else native)(state,version,quantity,snapshot,now,context=context)
        return approve


def close_campaign(record,store,repo,book,exec_config,stamp,event_id):
    """Native EXIT journal/broker lifecycle with an explicit research exit reason.

    Mirrors winner_global_liquidation.close_campaign; no cash/PnL shortcut and
    no backdated mark. Only reason, operation key and timing metadata differ.
    """
    from execution_engine.models import IntentRole
    from execution_engine.winner_broker import make_intent
    from execution_engine.winner_runtime import WinnerCampaignRuntime,TERMINAL
    rt=WinnerCampaignRuntime(store,repo,book,exec_config,market=lambda *_:{},risk=lambda *_:{},now=stamp)
    row=store.get(record['state']['campaign_id']);rt.state,rt.version=row['state'],row['version']
    rt.reconcile()
    if rt.pending():raise ValueError('Internal liquidation requires resolved pending operations')
    rt.reconcile_lots()
    for lot in rt.state['lots']:
        if not lot['remaining']:continue
        for field in ('stop_order_id','tp_order_id'):
            if lot.get(field):
                raw=book.cancel(lot[field]);rt.apply_lot_sale(lot,raw);rt.save()
                if raw['status'] not in TERMINAL:raise ValueError('Protection cancellation unconfirmed')
    quantity=sum(l['remaining'] for l in rt.state['lots'])
    if quantity:
        position=next((p for p in book.positions() if p['symbol']==rt.state['symbol']),None)
        if position is None or position['side']!='long' or position['qty']!=quantity:
            raise ValueError('Internal liquidation lot/broker mismatch')
        intent=make_intent(rt.state,rt.state['campaign_id']+'-internal-on-'+str(event_id),
            quantity=quantity,side='sell',role=IntentRole.EXIT,order_type='market',price=book.marks[rt.state['symbol']])
        operation=rt.reserve('EXIT',intent,booked_quantity=0,execution_timing='INTERNAL_PROTECTION_NEXT_OPEN',
            exit_reason='INTERNAL_PROTECTION',internal_protection_event_id=event_id)
        order=book.submit(rt.state,intent);operation.update(status='SUBMITTED',broker_id=order.broker_order_id)
        rt.save();rt.reconcile()
    if any(l['remaining'] for l in rt.state['lots']):raise ValueError('Incomplete internal liquidation')
    rt.state['status']='CLOSED';rt.save()
    return quantity


class InternalLiquidation:
    """Implements the replay's basket-exit port, without a DD/B4 controller."""
    enabled=False
    halted=False
    cycle_stopped=False
    cycle=1

    def __init__(self,states):
        if states.index.has_duplicates or not states.index.is_monotonic_increasing:raise ValueError('Ambiguous state dates')
        self.states=states;self.pending=None;self.events=[];self.counter=0;self.last_open=None

    @property
    def blocks_entries(self):return self.pending is not None

    def resume(self,stamp,book):
        from common.winner_pyramiding import regular_bounds
        day=pd.Timestamp(stamp).tz_convert('America/New_York').date()
        if stamp!=regular_bounds(day)[0]:raise ValueError('Internal liquidation requires an official open')
        if self.last_open==stamp:raise ValueError('Duplicate opening callback')
        self.last_open=stamp
        if self.pending is not None:raise ValueError('Unresolved previous liquidation')
        signal,row=prior_state(self.states,day)
        if row.transition=='ON':
            self.counter+=1
            self.pending=dict(event_id=self.counter,signal_date=str(signal.date()),detected_at=stamp.isoformat(),
                symbols=sorted(p['symbol'] for p in book.positions()),equity_before=book.equity())
        return False  # Never reset native risk/peaks on an internal transition.

    def observe(self,*args):pass

    def execute(self,stamp,store,repo,book,exec_cfg):
        if self.pending is None:return
        event=self.pending
        if stamp!=pd.Timestamp(event['detected_at']).to_pydatetime():raise ValueError('Exit must execute at the next official opening')
        records={r['state']['symbol']:r for r in store.rows() if any(l['remaining'] for l in r['state']['lots'])}
        quantities={}
        for symbol in event['symbols']:
            # Standing SL / open11 can already have sold at this same opening.
            if symbol in records:quantities[symbol]=close_campaign(records[symbol],store,repo,book,exec_cfg,stamp,event['event_id'])
        if book.positions():raise ValueError('Internal ON liquidation left held positions')
        event.update(executed_at=stamp.isoformat(),quantities=quantities,equity_after=book.equity())
        self.events.append(event);self.pending=None
        book.events.append(dict(time=stamp,event='INTERNAL_PROTECTION_LIQUIDATION',**event))

    def summary(self):
        return dict(enabled=False,internal_protection=True,events=self.events,pending=self.pending,
            execution='PREVIOUS_CLOSE_ON_NEXT_OFFICIAL_OPEN_STANDING_STOPS_FIRST')
