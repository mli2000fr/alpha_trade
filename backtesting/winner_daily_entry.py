"""Replay-only initial entries at the next official session's DAILY open.

No quotes are fabricated, no live broker is called. Intraday coverage never
filters admission: incomplete/incompatible protection sessions use daily OHLC.
A refused entry is not retried later in that session or on a later day.
"""
from dataclasses import asdict,replace
import math

import pandas as pd

from common.winner_pyramiding import WinnerPyramidingConfig,aware,regular_bounds
from execution_engine.models import ExecutionTarget
from execution_engine.winner_broker import make_intent
from execution_engine.winner_plans import plan_from_target
from execution_engine.winner_runtime import WinnerCampaignRuntime
from risk_management.constraints import PortfolioState
from risk_management.risk_checker import RiskCheckerImpl


def approve_daily_open(state,version,proposed,snapshot,now,*,context):
    """Native portfolio sizing/limits on an opening print, never a quote token."""
    now=aware(now);price=float(snapshot['daily_open']);cfg=context['risk_config']
    if (snapshot.get('price_source')!='CANONICAL_DAILY_OPEN' or aware(snapshot['opening_at'])!=now
        or context['account_id']!=state['account_id'] or context['broker_mode']!=state['broker_mode']
        or not 0<=(now-aware(context['captured_at'])).total_seconds()<=60
        or not math.isfinite(price) or price<=0):raise ValueError('Daily-open replay evidence/account unqualified')
    for key in ('entry_data_qualified','regime_qualified','concentration_qualified','concentration_allowed',
                'corporate_actions_qualified','breaker_qualified','entries_allowed'):
        if context.get(key) is not True:raise ValueError('Daily-open native risk rejected: '+key)
    breaker=context['circuit_breaker']
    if breaker is None or breaker.is_active():raise ValueError('Native breaker blocks daily-open entry')
    if abs(context['equity']-cfg.account_equity)>.005:raise ValueError('Daily-open equity mismatch')
    for key in ('equity','available_buying_power','cost_reserve_pct','allocation_scale','volatility_allocation_scale'):
        if not math.isfinite(float(context[key])):raise ValueError('Non-finite daily-open risk context: '+key)
    if context['cost_reserve_pct']<0 or not 0<=context['volatility_allocation_scale']<=1 or not 0<=context['allocation_scale']<=1:
        raise ValueError('Invalid daily-open cost/allocation bounds')
    if cfg.enforce_net_exposure or (cfg.correlation_check_enabled and cfg.max_long_short_correlation is not None):
        raise ValueError('Daily-open adapter does not qualify cross-leg overlays')
    portfolio=PortfolioState();sectors=context['sector_map'];symbol=state['symbol'];sides={}
    if not sectors.get(symbol) or sectors[symbol].lower()=='unknown':raise ValueError('Daily-open sector missing')
    for position in context['positions']:
        held=position['symbol'];quantity=float(position['quantity']);mark=float(position['mark'])
        if held==symbol:raise ValueError('Already held; no duplicate daily-open entry')
        if not sectors.get(held) or not all(math.isfinite(x) and x>0 for x in (quantity,mark)):
            raise ValueError('Daily-open held position unqualified')
        portfolio.add_position(notional=quantity*mark,sector=sectors[held],side=position['side'],symbol=held)
        sides[held]=position['side']
    for pending in context['pending_entries']:
        held=pending['symbol'];notional=float(pending['notional'])
        if held==symbol or not sectors.get(held) or not math.isfinite(notional) or notional<=0:
            raise ValueError('Conflicting/unqualified pending daily-open entry')
        portfolio.add_position(notional=notional,sector=sectors[held],side=pending['side'],symbol=held)
        sides[held]=pending['side']
    returns=context['return_matrix']
    corr=returns.corr(min_periods=cfg.correlation_min_overlap) if cfg.correlation_check_enabled and not returns.empty else pd.DataFrame()
    for held,side in (sides.items() if cfg.correlation_check_enabled else ()):
        if symbol not in corr or held not in corr or pd.isna(corr.loc[symbol,held]):raise ValueError('Daily-open correlation history missing')
        signed=float(corr.loc[symbol,held])*(-1 if side in ('short','sell') else 1)
        if signed>cfg.correlation_threshold:raise ValueError('Native correlation cap blocks daily-open entry')
    checker=RiskCheckerImpl(cfg.with_overrides(sector_corr_map=corr.to_dict()),state=portfolio,
        circuit_breaker=breaker,sector_map=sectors)
    policy=WinnerPyramidingConfig(**state['policy']);fee=max(policy.fee,float(context['cost_reserve_pct']))
    scale=float(context['allocation_scale'])*float(context['volatility_allocation_scale'])
    if not math.isfinite(scale) or not 0<=scale<=1:raise ValueError('Invalid daily-open allocation scale')
    budget=min(state['risk_budget'],cfg.account_equity*cfg.risk_per_trade_pct*cfg.risk_multiplier*scale)
    full=min(state['full_quantity'],math.floor(budget/(price*(policy.stop_loss_pct+2.05*fee))))
    quantity=min(math.floor(proposed),math.floor(full*policy.initial_position_fraction),
        math.floor(max(context['available_buying_power'],0)/(price*(1+fee))),
        math.floor(cfg.account_equity*cfg.max_position_weight/price))
    if quantity>0:quantity=math.floor(checker.check_position_size(symbol,quantity,price,side='buy',
        adv_usd=context.get('adv_usd'),selection_rank=state['target'].get('selection_rank')))
    reasons=[]
    if quantity>0 and cfg.enable_factor_model:
        from risk_management.live_factor_context import factor_violations
        factor=context.get('factor_context') or {}
        available=factor.get('input_available_at') if factor.get('evidence_kind')=='RECONSTRUCTED_HISTORICAL_INPUTS' else factor.get('observed_at')
        if (context.get('factor_qualified') is not True or not factor or
            factor.get('asof_date')!=context.get('factor_asof_date') or available is None or aware(available)>now
            or factor['covariance'].estimation_date!=context['factor_asof_date']
            or not 0<=(now-aware(factor['captured_at'])).total_seconds()<=60):
            raise ValueError('Daily-open factor context unavailable/future/stale')
        weights={}
        for position in context['positions']:
            sign=-1 if position['side'] in ('short','sell') else 1
            weights[position['symbol']]=weights.get(position['symbol'],0)+sign*position['quantity']*position['mark']/cfg.account_equity
        for pending in context['pending_entries']:
            sign=-1 if pending['side'] in ('short','sell') else 1
            weights[pending['symbol']]=weights.get(pending['symbol'],0)+sign*pending['notional']/cfg.account_equity
        weights[symbol]=quantity*price/cfg.account_equity
        reasons=factor_violations(factor,weights,cfg,candidate=symbol,other_sides=sides)
        if reasons:quantity=0
    return dict(producer='native_daily_open_replay_risk',price_source='CANONICAL_DAILY_OPEN',
        max_quantity=quantity,entry_price=price,state_version=version,available_at=now.isoformat(),
        config_hash=cfg.fingerprint,reason='; '.join(reasons) or (checker.get_last_decision_reason() if quantity else 'DAILY_OPEN_BUDGET_OR_CAPACITY'))


def enter_daily_candidates(rows,*,signal_day,day,opening,open_df,book,store,repo,
        execution,risk_config,recheck,calendar,coverage,audit,sector_map):
    """One attempt per ranked candidate, strictly on J's next official session."""
    if calendar.next_session(signal_day)!=day:raise ValueError('Daily entry must be on signal J+1')
    if aware(opening)!=regular_bounds(day)[0]:raise ValueError('Official daily opening required')
    from backtesting.winner_intraday import ReplayBroker
    if not isinstance(book,ReplayBroker):raise ValueError('Daily entry is restricted to the in-memory replay book')
    for row in rows.sort_values('rank' if 'rank' in rows else 'symbol').to_dict('records'):
        symbol=row['symbol']
        if any(r['state']['symbol']==symbol for r in store.rows()):
            audit.append(dict(time=opening,symbol=symbol,reason='DAILY_OPEN_ALREADY_HELD_OR_ACTIVE'));continue
        if symbol not in open_df or pd.Timestamp(day) not in open_df.index:
            coverage.add((str(day),symbol,'DAILY_OPEN_MISSING'));continue
        price=float(open_df.loc[pd.Timestamp(day),symbol])
        if not math.isfinite(price) or price<=0:
            coverage.add((str(day),symbol,'DAILY_OPEN_MISSING'));continue
        current=replace(risk_config,account_equity=book.equity())
        policy=execution.winner_pyramiding
        budget=current.account_equity*current.risk_per_trade_pct*current.risk_multiplier
        full=min(math.floor(budget/(price*(policy.stop_loss_pct+2.05*max(policy.fee,book.fee)))),
            math.floor(current.account_equity*current.max_position_weight/price))
        if full<1 or math.floor(full*policy.initial_position_fraction)*price<current.effective_min_notional:
            audit.append(dict(time=opening,symbol=symbol,reason='DAILY_OPEN_BUDGET_TOO_SMALL'));continue
        sector=sector_map.get(symbol)
        target=ExecutionTarget('replay-'+str(signal_day),signal_day,symbol,full,price,
            full*price/current.account_equity,sector,1.,'daily_open_replay_budget',None,
            selection_rank=int(row.get('rank') or 1),risk_budget_dollars=budget,side='long')
        state=plan_from_target(target,execution,'winner-replay',now=opening,calendar=calendar)
        state.update(account_id=execution.resolved_account_id,broker_mode=execution.broker_mode,
            risk_run_id=target.risk_run_id,admission='DAILY_OPEN_REPLAY_ONLY',daily_entry_mode=True)
        snapshot=dict(price_source='CANONICAL_DAILY_OPEN',daily_open=price,opening_at=opening.isoformat())
        try:approved=recheck(state,0,state['initial_quantity'],snapshot,opening,'DAILY_ENTRY')
        except ValueError as exc:
            audit.append(dict(time=opening,symbol=symbol,reason='DAILY_OPEN_RISK_REJECTED: '+str(exc)));continue
        quantity=min(state['initial_quantity'],int(approved['max_quantity']))
        if quantity<1:
            audit.append(dict(time=opening,symbol=symbol,reason='DAILY_OPEN_RISK_REJECTED: '+approved.get('reason','')));continue
        if not store.create(state,execution.resolved_account_id,execution.broker_mode,target.risk_run_id):continue
        stored=store.get(state['campaign_id']);state,version=stored['state'],stored['version']
        intent=make_intent(state,state['campaign_id']+'-daily-open',quantity=quantity,
            order_type='market',price=price,tif='ioc')
        state['initial_attempted']=True
        state['operations'].append(dict(key=intent.intent_id,action='ENTRY',status='SUBMITTED',
            reserved_at=opening.isoformat(),approval=approved,intent=asdict(intent)))
        state['parents'][intent.intent_id]=dict(action='ENTRY',booked_quantity=0,booked_notional=0.)
        store.save(state,version)
        previous=book.marks.get(symbol);book.marks[symbol]=price
        order=book.submit(state,intent)
        raw=book.get(order.broker_order_id)
        for event in reversed(book.events):
            if event.get('event')=='BUY_FILL' and event.get('symbol')==symbol and event.get('time')==opening:
                event.update(execution_proxy='DAILY_SESSION_OPEN',price_source='CANONICAL_DAILY_OPEN',signal_date=str(signal_day));break
        if raw['status']!='filled':
            stored=store.get(state['campaign_id']);stored['state']['status']='CANCELED'
            store.save(stored['state'],stored['version'])
            audit.append(dict(time=opening,symbol=symbol,reason='DAILY_OPEN_CAPACITY_REJECTED_NO_RETRY'))
        else:
            synchronized=WinnerCampaignRuntime(store,repo,book,execution,market=lambda *_:{},risk=lambda *_:{},
                now=opening,lifecycle_only=True).run([store.get(state['campaign_id'])])
            if synchronized['winner_failures']:raise ValueError('Daily-open protection reconciliation failed: '+str(synchronized))
        if previous is not None:book.marks[symbol]=previous
