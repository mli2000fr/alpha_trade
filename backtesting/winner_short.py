"""SHORT campaign adapter restricted to the in-memory Winner replay.

No SQL, provider, broker bridge or production campaign mutation. Historical
borrow availability is an explicit research assumption; fees are charged, but
locates, recalls and historical bid/ask are not certified by five-minute bars.
"""
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal,ROUND_CEILING
import hashlib
import math
from zoneinfo import ZoneInfo

import pandas as pd

from common.winner_pyramiding import (WinnerPyramidingConfig,aware,due_open,
    fresh_completed_bars,initial_quantities,regular_bounds)
from execution_engine.models import IntentRole
from execution_engine.winner_broker import make_intent
from risk_management.constraints import PortfolioState
from risk_management.risk_checker import RiskCheckerImpl


def is_short(state):return state.get('side')=='short'


def short_plan(target,config,*,now,calendar):
    if str(target.side).lower() not in ('short','sell') or config.account_type!='margin':
        raise ValueError('SHORT replay requires a SHORT target and margin account')
    policy=config.winner_pyramiding
    if not policy.enabled or config.market_code!='US_EQ':raise ValueError('Enabled US Winner replay required')
    full,initial=initial_quantities(target.target_shares,target.entry_price,target.risk_budget_dollars,policy)
    if initial<1:raise ValueError('SHORT campaign budget insufficient')
    sessions=[s for s in calendar.sessions(target.trade_date,target.trade_date+timedelta(days=policy.entry_valid_sessions*3+40)) if s.is_open]
    if not sessions or sessions[0].session_date!=target.trade_date or len(sessions)<=policy.entry_valid_sessions:
        raise ValueError('Official SHORT campaign calendar incomplete')
    if aware(now)>=aware(sessions[policy.entry_valid_sessions].close_at_utc):raise ValueError('Expired SHORT plan')
    key='ws-'+hashlib.sha256('|'.join((config.resolved_account_id,target.risk_run_id,target.symbol)).encode()).hexdigest()[:40]
    return dict(campaign_id=key,symbol=target.symbol,side='short',policy=asdict(policy),
        full_quantity=full,initial_quantity=initial,risk_budget=float(target.risk_budget_dollars),
        realized_losses=0.,added_quantity=0,add_attempted=False,first_fill_at=None,due_open=None,lots=[],
        status='PENDING',exec_run_id='winner-replay',signal_date=target.trade_date.isoformat(),
        account_policy=dict(account_type=config.account_type,leverage=asdict(config.leverage)),
        created_at=aware(now).isoformat(),earliest_entry_open=aware(sessions[1].open_at_utc).isoformat(),
        entry_expires_at=aware(sessions[policy.entry_valid_sessions].close_at_utc).isoformat(),
        target=asdict(target),parents={},operations=[],admission='SHORT_REPLAY_RISK_RECHECK_REQUIRED',
        entry_policy=dict(order_type=config.entry_order_type,limit_price_buffer_bps=config.limit_price_buffer_bps,
            max_entry_gap_pct=config.max_entry_gap_pct,submission_window=config.submission_window))


def short_exit(levels,bar):
    op,hi,lo=(float(bar[k]) for k in ('open','high','low'))
    if not all(math.isfinite(x) and x>0 for x in (op,hi,lo)) or not lo<=op<=hi:
        raise ValueError('Invalid SHORT OHLC')
    if op>=levels['stop']:return op,'STOP_GAP','OPEN'
    if levels.get('tp') is not None and op<=levels['tp']:return levels['tp'],'TP_GAP_CAPPED','OPEN'
    if hi>=levels['stop']:return levels['stop'],'STOP','INTRABAR'
    if levels.get('tp') is not None and lo<=levels['tp']:return levels['tp'],'TP','INTRABAR'
    return None


def price_terms(state,snapshot,now):
    """Sell floor plus separate maximum notional/risk price for the IOC proxy."""
    p=WinnerPyramidingConfig(**state['policy'])
    standard=p.confirmation_bars==0 and not state['lots']
    reference=float(state['target']['entry_price'])
    if p.market_data_delay_seconds and not standard:
        # Qualify the receipt through the existing LONG evidence validator,
        # using only its receipt checks; derive SHORT bounds independently.
        from common.winner_delayed import delayed_price_limit
        delayed_price_limit(state,snapshot,now)
        price=float(snapshot['delayed_reference_price'])
        floor=price*(1-p.delayed_entry_limit_buffer_pct)
        risk_price=price*(1+p.delayed_entry_limit_buffer_pct)
        order_type='limit'
    else:
        price=float(snapshot.get('bid') or reference)
        floor=price;risk_price=price
        order_type='limit'
        if standard:
            terms=state['entry_policy'];order_type=terms['order_type']
            if order_type=='limit':floor=reference*(1-float(terms['limit_price_buffer_bps'])/10000)
            if snapshot.get('standard_entry_quote_check_enabled') is False:
                gap=float(terms['max_entry_gap_pct'])
                bound=reference*(1-gap if gap else 1-float(terms['limit_price_buffer_bps'])/10000)
                floor=max(floor,bound) if order_type=='limit' else bound
                order_type='limit'
    gap=float(state['entry_policy']['max_entry_gap_pct'])
    if gap and not state['lots']:
        floor=max(floor,reference*(1-gap))
    if not all(math.isfinite(x) and x>0 for x in (floor,risk_price)):raise ValueError('Invalid SHORT entry bounds')
    tick=Decimal('.01') if floor>=1 else Decimal('.0001')
    floor=float(Decimal(str(floor)).quantize(tick,rounding=ROUND_CEILING))
    return order_type,None if order_type=='market' else floor,risk_price


def reapprove_short(state,version,proposed,snapshot,now,kind,*,context):
    """Native risk/constraints with signed exposure, on explicit replay evidence."""
    if not is_short(state) or kind not in ('ENTRY','ADD'):raise ValueError('Invalid SHORT reapproval')
    cfg=context['risk_config'];p=WinnerPyramidingConfig(**state['policy'])
    if not cfg.short_selling_enabled:raise ValueError('SHORT disabled in replay risk')
    if cfg.enforce_net_exposure or (cfg.correlation_check_enabled and cfg.max_long_short_correlation is not None):
        raise ValueError('SHORT replay does not qualify market-neutral / cross-leg overlays')
    if (context['account_id']!=state['account_id'] or context['broker_mode']!=state['broker_mode'] or
        not 0<=(aware(now)-aware(context['captured_at'])).total_seconds()<=60):raise ValueError('Stale/mismatched SHORT context')
    for key in ('entry_data_qualified','regime_qualified','concentration_qualified','concentration_allowed',
                'corporate_actions_qualified','breaker_qualified','entries_allowed'):
        if context.get(key) is not True:raise ValueError('SHORT risk context unqualified: '+key)
    if context['circuit_breaker'].is_active():raise ValueError('Native circuit breaker blocks SHORT entry')
    if abs(context['equity']-cfg.account_equity)>.005:raise ValueError('SHORT equity differs from native risk')
    order_type,limit,price=price_terms(state,snapshot,now)
    # Only an already observed price can increase the reservation. This does
    # not change the delayed signal or claim a contemporaneous historical quote.
    price=max(price,float(context['replay_observed_price']))
    positions=context['positions'];sector_map=context['sector_map'];symbol=state['symbol']
    sector=sector_map.get(symbol)
    if not sector or sector.lower()=='unknown':raise ValueError('SHORT current sector unavailable')
    portfolio=PortfolioState();own=0.;own_quantity=0.;other_sides={}
    for position in positions:
        held=position['symbol'];qty=float(position['quantity']);mark=float(position['mark'])
        if not sector_map.get(held) or not all(math.isfinite(v) and v>0 for v in (qty,mark)):
            raise ValueError('Unqualified SHORT portfolio holding')
        portfolio.add_position(notional=qty*mark,sector=sector_map[held],side=position['side'],symbol=held)
        other_sides[held]=position['side']
        if held==symbol:
            if position['side']!='short':raise ValueError('Opposite-side holding blocks SHORT')
            own=qty*mark;own_quantity=qty
    if kind=='ENTRY' and own_quantity:raise ValueError('Cannot average an existing SHORT')
    if kind=='ADD' and own_quantity!=sum(l['remaining'] for l in state['lots']):raise ValueError('SHORT lots mismatch')
    for pending in context['pending_entries']:
        if pending['symbol']==symbol:raise ValueError('Pending order conflicts with SHORT')
        portfolio.add_position(notional=pending['notional'],sector=sector_map[pending['symbol']],
            side=pending['side'],symbol=pending['symbol'])
        other_sides[pending['symbol']]=pending['side']
    returns=context['return_matrix']
    corr=returns.corr(min_periods=cfg.correlation_min_overlap) if cfg.correlation_check_enabled and not returns.empty else pd.DataFrame()
    for held,side in (other_sides.items() if cfg.correlation_check_enabled else ()):
        if held==symbol:continue
        if symbol not in corr or held not in corr or pd.isna(corr.loc[symbol,held]):raise ValueError('SHORT correlation history insufficient')
        signed=float(corr.loc[symbol,held])*(1 if side in ('short','sell') else -1)
        if signed>cfg.correlation_threshold:raise ValueError('Native correlation cap blocks SHORT')
    if kind=='ADD':
        portfolio.position_count-=1;portfolio.short_count-=1
        portfolio.sector_ticker_count[sector]-=1;portfolio.sector_symbols[sector].remove(symbol)
    checker=RiskCheckerImpl(cfg.with_overrides(sector_corr_map=corr.to_dict()),state=portfolio,
        circuit_breaker=context['circuit_breaker'],sector_map=sector_map)
    fee=max(p.fee,context['cost_reserve_pct'])
    scale=float(context['allocation_scale'])*float(context['volatility_allocation_scale'])
    if not math.isfinite(scale) or not 0<=scale<=1:raise ValueError('Invalid SHORT allocation scale')
    budget=min(state['risk_budget'],cfg.account_equity*cfg.risk_per_trade_pct*cfg.risk_multiplier*scale)
    known=state['realized_losses']+sum(l['remaining']*(max(l['stop']-l['entry'],0)+fee*(l['entry']+l['stop'])) for l in state['lots'])
    # Stops above the entry have a slightly greater closing notional.
    unit=price*(p.stop_loss_pct+(2+p.stop_loss_pct)*fee)
    quantity=min(math.floor(proposed),math.floor(max(budget-known,0)/unit),
        math.floor(max(context['available_buying_power'],0)/(price*(1+fee))),
        math.floor(max(cfg.account_equity*cfg.max_position_weight-own,0)/price))
    if kind=='ENTRY':quantity=min(quantity,math.floor(min(state['full_quantity'],math.floor(budget/unit))*p.initial_position_fraction))
    if quantity>0:quantity=math.floor(checker.check_position_size(symbol,quantity,price,side='sell',
        adv_usd=context.get('adv_usd'),selection_rank=state['target'].get('selection_rank')))
    reasons=[]
    if quantity>0 and cfg.enable_factor_model:
        from risk_management.live_factor_context import factor_violations
        factors=context.get('factor_context')
        if context.get('factor_qualified') is not True or not factors or factors['asof_date']!=context.get('factor_asof_date'):
            raise ValueError('SHORT factor context unavailable')
        available=factors.get('input_available_at') if factors.get('evidence_kind')=='RECONSTRUCTED_HISTORICAL_INPUTS' else factors.get('observed_at')
        if available is None or aware(available)>aware(now) or factors['covariance'].estimation_date!=context['factor_asof_date']:
            raise ValueError('SHORT factor context future/wrong session')
        weights={}
        for position in positions:
            sign=-1 if position['side'] in ('short','sell') else 1
            weights[position['symbol']]=weights.get(position['symbol'],0)+sign*position['quantity']*position['mark']/cfg.account_equity
        for pending in context['pending_entries']:
            sign=-1 if pending['side'] in ('short','sell') else 1
            weights[pending['symbol']]=weights.get(pending['symbol'],0)+sign*pending['notional']/cfg.account_equity
        weights[symbol]=weights.get(symbol,0)-quantity*price/cfg.account_equity
        reasons=factor_violations(factors,weights,cfg,candidate=symbol,other_sides=other_sides)
        if reasons:quantity=0
    return dict(max_quantity=quantity,limit_price=limit,risk_price=price,order_type=order_type,
        reason='; '.join(reasons) or checker.get_last_decision_reason(),
        producer='native_short_replay_risk',state_version=version,side='sell',
        config_hash=cfg.fingerprint,available_at=aware(now).isoformat(),
        borrow_policy='ASSUMED_AVAILABLE_WITH_EXPLICIT_SIMULATED_FEE_NOT_HISTORICALLY_CERTIFIED')


class ShortReplayCoordinator:
    def __init__(self,store,book,config,*,market,risk,now,lifecycle_only=False):
        if not getattr(book,'is_winner_replay',False):raise ValueError('SHORT coordinator requires in-memory replay broker')
        self.store,self.book,self.config=store,book,config
        self.market,self.risk,self.now,self.lifecycle_only=market,risk,aware(now),lifecycle_only

    def save(self):self.version=self.store.save(self.state,self.version)

    def sync(self):
        s=self.state;p=WinnerPyramidingConfig(**s['policy'])
        for operation in s['operations']:
            raw=self.book.orders.get(operation['key'])
            if raw and raw['status'] in ('filled','canceled','expired','rejected'):operation['status']='DONE'
        for key,lot in self.book.lots.items():
            if lot['campaign_id']!=s['campaign_id']:continue
            local=next((l for l in s['lots'] if l['parent_id']==key),None)
            if local is None:
                if s['first_fill_at'] is None:
                    s['first_fill_at']=lot['entry_time'].isoformat()
                    due=due_open(lot['entry_time'],p)
                    s['due_open']=due.isoformat() if due else None
                local=dict(parent_id=key,parent_intent_id=key,quantity=lot['quantity'],remaining=lot['remaining'],
                    entry=lot['entry'],peak=lot['entry'],stop=round(lot['entry']*(1+p.stop_loss_pct),2),
                    tp=round(lot['entry']*(1-p.take_profit_pct),2) if p.take_profit_pct else None,
                    filled_at=lot['entry_time'].isoformat(),last_bar_end=None,stop_order_id=None,tp_order_id=None)
                s['lots'].append(local);s['status']='OPEN'
            local['remaining']=lot['remaining']
        s['realized_losses']=sum(max(-t['pnl'],0) for t in self.book.trades if t['campaign_id']==s['campaign_id'])
        if s['lots'] and not any(l['remaining'] for l in s['lots']):s['status']='CLOSED'
        self.save()

    def protect(self):
        for lot in self.state['lots']:
            if not lot['remaining'] or lot['stop_order_id']:continue
            parent=self.book.intents[lot['parent_id']]
            stop=make_intent(self.state,lot['parent_id']+'-sl',quantity=lot['remaining'],side='buy',
                role=IntentRole.INITIAL_STOP,order_type='stop',stop=lot['stop'],parent=parent.intent_id)
            tp=(make_intent(self.state,lot['parent_id']+'-tp',quantity=lot['remaining'],side='buy',
                role=IntentRole.TAKE_PROFIT,order_type='limit',price=lot['tp'],parent=parent.intent_id) if lot['tp'] else None)
            tp_order,stop_order=self.book.protect(self.state,lot,parent,tp_intent=tp,stop_intent=stop)
            lot['stop_order_id']=stop_order.broker_order_id
            lot['tp_order_id']=tp_order.broker_order_id if tp_order else None
        self.save()

    def close(self,reason,*,moo=False):
        self.sync()
        for lot in self.state['lots']:
            for key in ('stop_order_id','tp_order_id'):
                if lot.get(key):self.book.cancel(lot[key])
        qty=sum(l['remaining'] for l in self.state['lots'])
        if qty:
            intent=make_intent(self.state,self.state['campaign_id']+'-exit-'+str(len(self.state['operations'])),
                quantity=qty,side='buy',role=IntentRole.EXIT,order_type='market',tif='opg' if moo else None)
            self.state['operations'].append(dict(key=intent.intent_id,action='EXIT',exit_reason=reason,status='SUBMITTED'))
            self.book.submit(self.state,intent)
        self.sync()

    def tick(self):
        s=self.state;p=WinnerPyramidingConfig(**s['policy'])
        self.sync();self.protect()
        if s['status'] in ('CLOSED','CANCELED','EXPIRED'):return
        pending=[r for r in self.book.orders.values() if r.get('campaign_id')==s['campaign_id'] and r['status']=='new' and r.get('entry_order')]
        if pending:return
        if s['lots'] and s.get('due_open'):
            due=aware(s['due_open'])
            if self.now>=due:
                bounds=regular_bounds(self.now.astimezone(ZoneInfo('America/New_York')).date())
                if bounds and bounds[0]<=self.now<bounds[1]:self.close('HORIZON_LATE_MARKET')
                return
            if due-timedelta(minutes=10)<=self.now<due-timedelta(minutes=2):
                if not any(o['action']=='EXIT' for o in s['operations']):self.close('HORIZON_OPEN',moo=True)
                return
        if not s['lots'] and self.now>=aware(s['entry_expires_at']):s['status']='EXPIRED';self.save();return
        if self.lifecycle_only:return
        if s['lots'] and not p.trailing_stop_pct and not p.reinforcement_enabled:return
        if not s['lots'] and self.now<aware(s['earliest_entry_open']):return
        try:snapshot=self.market(s,self.now)
        except ValueError as exc:
            self.details.append(dict(symbol=s['symbol'],reason='SHORT_MARKET_DATA_UNQUALIFIED: '+str(exc)));return
        if s['lots'] and p.trailing_stop_pct:
            for lot in s['lots']:
                if not lot['remaining']:continue
                for bar in sorted(snapshot['bars'],key=lambda b:aware(b['timestamp'])):
                    start=aware(bar['timestamp']);end=start+timedelta(minutes=5)
                    if (start<aware(lot['filled_at']) or end>self.now-timedelta(seconds=p.market_data_delay_seconds)
                        or lot['last_bar_end'] and end<=aware(lot['last_bar_end'])):continue
                    lot['peak']=min(lot['peak'],float(bar['low']));lot['last_bar_end']=end.isoformat()
                level=min(lot['stop'],round(lot['peak']*(1+p.trailing_stop_pct),2))
                if level<lot['stop']:
                    intent=make_intent(s,lot['parent_id']+'-trail-'+str(level),quantity=lot['remaining'],side='buy',
                        role=IntentRole.INITIAL_STOP,order_type='stop',stop=level,parent=lot['parent_id'])
                    order=self.book.tighten(s,lot,intent);lot.update(stop=level,stop_order_id=order.broker_order_id)
            self.sync()
        if not self.config.winner_pyramiding.enabled or self.config.blocks_new_entries:return
        if s['lots']:
            if not p.reinforcement_enabled or p.initial_position_fraction==1 or s['add_attempted']:return
            if any(l['remaining']!=l['quantity'] for l in s['lots']):return
            initial=[l for l in s['lots'] if self.book.lots[l['parent_id']].get('entry_kind')!='ADD']
            entry=sum(l['quantity']*l['entry'] for l in initial)/sum(l['quantity'] for l in initial)
            tail=fresh_completed_bars(snapshot['bars'],p,now=self.now,count=max(1,p.confirmation_bars))
            if not tail or any(aware(b['timestamp'])<aware(s['first_fill_at']) or b['close']>entry*(1-p.reinforcement_trigger_pct) for b in tail):return
            proposed=s['full_quantity']-sum(l['quantity'] for l in s['lots']);kind='ADD'
        else:
            if s.get('initial_attempted'):return
            if p.confirmation_bars:
                tail=fresh_completed_bars(snapshot['bars'],p,now=self.now,count=p.confirmation_bars+1)
                level=snapshot.get('prior_session_low')
                if not tail or level is None or not(tail[0]['close']>=level and all(b['close']<level for b in tail[1:])):return
            else:
                from execution_engine.winner_standard_entry import standard_entry_window
                if not standard_entry_window(s,self.now):return
            proposed=s['initial_quantity'];kind='ENTRY'
        try:approved=self.risk(s,self.version,proposed,snapshot,self.now,kind)
        except ValueError as exc:
            self.details.append(dict(symbol=s['symbol'],reason='SHORT_NATIVE_RISK_REJECTED: '+str(exc)));return
        quantity=min(int(proposed),int(approved['max_quantity']))
        if quantity<1:
            self.details.append(dict(symbol=s['symbol'],reason=approved.get('reason','SHORT_RISK_REJECTED')));return
        key=s['campaign_id']+'-'+kind.lower()
        intent=make_intent(s,key,quantity=quantity,side='sell',role=IntentRole.ENTRY,
            order_type=approved['order_type'],price=approved['limit_price'],tif='day' if p.confirmation_bars==0 and kind=='ENTRY' else 'ioc')
        s['initial_attempted']=True
        if kind=='ADD':s['add_attempted']=True
        s['operations'].append(dict(key=intent.intent_id,action=kind,status='SUBMITTED',approval=approved))
        self.save()
        self.book.short_reservations[intent.intent_id]=approved['risk_price']
        self.book.submit(s,intent)
        self.sync();self.protect()

    def run(self,records):
        self.details=[]
        for record in records:
            row=self.store.get(record['state']['campaign_id'])
            self.state,self.version=row['state'],row['version']
            if not is_short(self.state):raise ValueError('SHORT coordinator received LONG campaign')
            # Only market/risk vetoes are caught at their decision boundary.
            # Accounting/protection exceptions abort the simulation.
            self.tick()
        return dict(winner_details=self.details,winner_failures=0)
