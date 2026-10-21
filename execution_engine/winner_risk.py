"""Native constraint reapproval for a previously approved LONG campaign.

The context provider must supply current broker capacity, canonical daily
data, a qualified persistent breaker and concentration state. Missing evidence
rejects the entry; the LLM's conclusion is never a substitute for that context.
"""
from datetime import timedelta
import hashlib
import json
import math

import pandas as pd

from common.winner_pyramiding import WinnerPyramidingConfig, aware, known_risk
from execution_engine.winner_broker import entry_limit
from risk_management.constraints import PortfolioState
from risk_management.risk_checker import RiskCheckerImpl


def reapprove_campaign(state, version, proposed, snapshot, now, kind, *, context):
    """Pure decision over an explicitly captured native risk context.

    Reuses RiskCheckerImpl / its ConstraintChecker / persistent CircuitBreaker.
    Adds campaign-specific combined-position and residual-risk caps. Context
    mutation is limited to native breaker evaluation, never broker/SQL writes.
    """
    now = aware(now)
    policy = WinnerPyramidingConfig(**state['policy'])
    if kind not in ('ENTRY', 'ADD') or context.get('account_id') != state['account_id'] or context.get('broker_mode') != state['broker_mode']:
        raise ValueError('Fresh risk account/mode does not match campaign')
    captured = aware(context['captured_at'])
    if not 0 <= (now-captured).total_seconds() <= 60:
        raise ValueError('Stale/future operational risk snapshot')
    if (context.get('entry_data_qualified') is not True or context.get('regime_qualified') is not True
            or context.get('concentration_qualified') is not True
            or context.get('corporate_actions_qualified') is not True):
        raise ValueError('Unqualified native entry data / regime / concentration / corporate actions')
    if context.get('entries_allowed') is not True:
        raise ValueError('Native regime blocks new LONG entries')
    if snapshot.get('feed') != 'sip' or snapshot.get('quote_error'):
        raise ValueError('Real-time SIP quote required')
    bid, ask = float(snapshot['bid']), float(snapshot['ask'])
    if (not all(math.isfinite(x) and x > 0 for x in (bid, ask)) or bid > ask
            or not 0 <= (now-aware(snapshot['quote_time'])).total_seconds() <= policy.max_quote_age_seconds):
        raise ValueError('SIP quote invalid, future or stale')
    spread = 10000*(ask-bid)/((bid+ask)/2)
    if spread > context['max_spread_bps']:
        raise ValueError('Native maximum spread exceeded')
    price = entry_limit(ask)
    cfg = context['risk_config']
    if cfg.enforce_net_exposure or cfg.max_long_short_correlation is not None:
        raise ValueError('Campaign adapter does not qualify market-neutral / cross-leg overlays')
    if abs(float(context['equity'])-cfg.account_equity) > .005:
        raise ValueError('Native risk equity differs from captured account')
    if cfg.enable_factor_model and context.get('factor_qualified') is not True:
        raise ValueError('Factor model enabled but fresh exposures are unqualified')
    if context.get('concentration_allowed') is not True:
        raise ValueError('Native concentration rule blocks this campaign')
    breaker = context['circuit_breaker']
    if breaker is None or context.get('breaker_qualified') is not True:
        raise ValueError('Persistent native breaker context missing; no reset to current equity')
    if breaker.is_active():
        raise ValueError('Native circuit breaker blocks entry')
    scale = float(context['allocation_scale'])
    if not math.isfinite(scale) or not 0 <= scale <= 1:
        raise ValueError('Native allocation scale unqualified')
    for key in ('equity', 'available_buying_power', 'max_spread_bps', 'cost_reserve_pct', 'volatility_allocation_scale'):
        if not math.isfinite(float(context[key])):
            raise ValueError('Non-finite native risk context: '+key)
    if (context['cost_reserve_pct'] < 0 or not 0 <= context['volatility_allocation_scale'] <= 1
            or context['max_spread_bps'] < 0):
        raise ValueError('Invalid native cost / volatility / spread bounds')
    portfolio = PortfolioState()
    symbol, sector_map = state['symbol'], context['sector_map']
    sector = sector_map.get(symbol)
    if not sector or sector.lower() == 'unknown':
        raise ValueError('Current sector metadata unavailable')
    own_notional, own_quantity = 0., 0.
    positions = context['positions']
    returns = context['return_matrix']
    correlations = returns.corr(min_periods=cfg.correlation_min_overlap) if not returns.empty else pd.DataFrame()
    side_by_symbol = {}
    for position in positions:
        held = position['symbol']
        quantity, mark = float(position['quantity']), float(position['mark'])
        if not math.isfinite(quantity) or not quantity > 0 or not math.isfinite(mark) or mark <= 0 or not sector_map.get(held):
            raise ValueError('Held-position quantity/mark/sector unqualified')
        portfolio.add_position(notional=quantity*mark, sector=sector_map[held],
            side=position['side'], symbol=held)
        side_by_symbol[held] = position['side']
        if held == symbol:
            if position['side'] not in ('buy', 'long'):
                raise ValueError('Cannot reinforce an opposite-side holding')
            own_quantity, own_notional = quantity, quantity*mark
    if kind == 'ENTRY' and own_quantity:
        raise ValueError('Initial campaign cannot average an existing position')
    if kind == 'ADD' and own_quantity != sum(l['remaining'] for l in state['lots']):
        raise ValueError('Campaign lots differ from actual broker holding')
    # Pending orders outside this campaign also consume gross/sector capacity.
    for pending in context['pending_entries']:
        if not math.isfinite(float(pending['notional'])) or pending['notional'] <= 0:
            raise ValueError('Pending-entry notional unavailable')
        if pending['symbol'] == symbol:
            raise ValueError('Another pending entry conflicts with campaign')
        if not sector_map.get(pending['symbol']):
            raise ValueError('Pending-entry sector unavailable')
        portfolio.add_position(notional=pending['notional'], sector=sector_map[pending['symbol']],
            side=pending['side'], symbol=pending['symbol'])
        side_by_symbol[pending['symbol']] = pending['side']
    for held, side in side_by_symbol.items():
        if held == symbol:
            continue
        if symbol not in correlations or held not in correlations or pd.isna(correlations.loc[symbol, held]):
            raise ValueError('Insufficient observed returns for held/pending correlation')
        signed = float(correlations.loc[symbol, held])*(-1 if side in ('short', 'sell') else 1)
        if signed > cfg.correlation_threshold:
            raise ValueError('Native correlation cap blocks candidate')
    # A reinforcement is one ticker, not an extra slot, but its notional remains
    # in gross/sector caps. Remove only that slot, never its existing exposure.
    if kind == 'ADD':
        portfolio.position_count -= 1
        portfolio.long_count -= 1
        portfolio.sector_ticker_count[sector] -= 1
        portfolio.sector_symbols[sector].remove(symbol)
    cfg = cfg.with_overrides(sector_corr_map=correlations.to_dict())
    checker = RiskCheckerImpl(cfg, state=portfolio, circuit_breaker=breaker, sector_map=sector_map)
    fee = max(policy.fee, float(context['cost_reserve_pct']))
    current_budget = min(state['risk_budget'], cfg.account_equity*cfg.risk_per_trade_pct*
        float(cfg.risk_multiplier)*scale*float(context['volatility_allocation_scale']))
    residual = max(current_budget-known_risk(state, fee), 0.)
    unit_risk = price*(policy.stop_loss_pct+2.05*fee)
    quantity = min(math.floor(proposed), math.floor(residual/unit_risk),
        math.floor(max(context['available_buying_power'], 0)/(price*(1+fee))),
        math.floor(max(cfg.account_equity*cfg.max_position_weight-own_notional, 0)/price))
    if kind == 'ENTRY':
        fresh_full = min(state['full_quantity'], math.floor(current_budget/unit_risk))
        quantity = min(quantity, math.floor(fresh_full*policy.initial_position_fraction))
    if quantity > 0:
        quantity = math.floor(checker.check_position_size(symbol, quantity, price, side='buy',
            adv_usd=context.get('adv_usd'), selection_rank=state['target'].get('selection_rank')))
    fingerprint = hashlib.sha256(json.dumps({k: context[k] for k in
        ('account_id', 'broker_mode', 'captured_at', 'equity', 'positions', 'pending_entries')},
        sort_keys=True, default=str).encode()).hexdigest()
    return dict(producer='native_intraday_risk', campaign_id=state['campaign_id'],
        account_id=state['account_id'], broker_mode=state['broker_mode'], state_version=version,
        side='buy', entry_data_qualified=True, realtime_sip_qualified=True, regime_qualified=True,
        qualified=True, max_quantity=quantity, limit_price=price, config_hash=cfg.fingerprint,
        portfolio_hash=fingerprint, available_at=now.isoformat(),
        valid_until=(now+timedelta(seconds=min(30, policy.max_quote_age_seconds))).isoformat(),
        reason=checker.get_last_decision_reason() if quantity else 'CAMPAIGN_RISK_OR_CAPACITY_EXHAUSTED')
