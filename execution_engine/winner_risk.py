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
    from service.market.live_quotes import validate_campaign_quote
    from execution_engine.winner_standard_entry import standard_initial, standard_risk_price
    quote_required = context.get('standard_entry_quote_check_enabled', True)
    if type(quote_required) is not bool:
        raise ValueError('Quote check policy must be boolean')
    if quote_required:
        validate_campaign_quote(snapshot, now=now, max_age_seconds=policy.max_quote_age_seconds)
        bid, ask = float(snapshot['bid']), float(snapshot['ask'])
        if (not all(math.isfinite(x) and x > 0 for x in (bid, ask)) or bid > ask
                or not 0 <= (now-aware(snapshot['quote_time'])).total_seconds() <= policy.max_quote_age_seconds):
            raise ValueError('SIP quote invalid, future or stale')
        spread = 10000*(ask-bid)/((bid+ask)/2)
        if spread > context['max_spread_bps']:
            raise ValueError('Native maximum spread exceeded')
        price = entry_limit(ask)
    else:
        if kind != 'ENTRY' or not standard_initial(state) or policy.standard_entry_quote_check_enabled:
            raise ValueError('No-quote mode only permits standard initial entries')
        reference = float(context['reference_price'])
        if (context.get('reference_price_asof') != snapshot['prior_session']
                or not math.isfinite(reference) or reference <= 0):
            raise ValueError('Qualified prior-session reference required; no invented real-time price')
        price = entry_limit(max(reference, float(state['target']['entry_price'])))
    if kind == 'ENTRY' and standard_initial(state):
        price = standard_risk_price(state, price, quote_check_enabled=quote_required)
    from execution_engine.winner_standard_entry import standard_order_terms
    effective_type, effective_limit = (standard_order_terms(state, quote_check_enabled=quote_required)
        if kind == 'ENTRY' and standard_initial(state) else ('limit', price))
    cfg = context['risk_config']
    if cfg.enforce_net_exposure or cfg.max_long_short_correlation is not None:
        raise ValueError('Campaign adapter does not qualify market-neutral / cross-leg overlays')
    if abs(float(context['equity'])-cfg.account_equity) > .005:
        raise ValueError('Native risk equity differs from captured account')
    if cfg.enable_factor_model and context.get('factor_qualified') is not True:
        raise ValueError('Factor model enabled but fresh exposures are unqualified')
    if cfg.enable_factor_model:
        factor_context = context.get('factor_context')
        if (not factor_context or factor_context.get('asof_date') != context.get('factor_asof_date')
                or factor_context['covariance'].estimation_date != context.get('factor_asof_date')
                or aware(factor_context['observed_at']) > now
                or not 0 <= (now-aware(factor_context['captured_at'])).total_seconds() <= 60):
            raise ValueError('Native factor context absent, future, stale or wrong-session')
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
    factor_rejections = []
    factor_beta_exposure = None
    if quantity > 0 and cfg.enable_factor_model:
        from risk_management.live_factor_context import factor_violations
        weights = {}
        for position in positions:
            sign = -1 if position['side'] in ('short','sell') else 1
            weights[position['symbol']] = weights.get(position['symbol'],0.)+sign*float(position['quantity'])*float(position['mark'])/cfg.account_equity
        for pending in context['pending_entries']:
            sign = -1 if pending['side'] in ('short','sell') else 1
            weights[pending['symbol']] = weights.get(pending['symbol'],0.)+sign*pending['notional']/cfg.account_equity
        weights[symbol] = weights.get(symbol,0.)+quantity*price/cfg.account_equity
        from risk_management.factor_model import portfolio_beta_exposure
        factor_beta_exposure = portfolio_beta_exposure(weights,context['factor_context']['exposures'],
            basis=cfg.beta_exposure_basis)
        factor_rejections = factor_violations(context['factor_context'],weights,cfg,candidate=symbol,
            other_sides=side_by_symbol)
        if factor_rejections:
            quantity = 0
    fingerprint = hashlib.sha256(json.dumps({k: context[k] for k in
        ('account_id', 'broker_mode', 'captured_at', 'equity', 'positions', 'pending_entries')},
        sort_keys=True, default=str).encode()).hexdigest()
    return dict(producer='native_intraday_risk', campaign_id=state['campaign_id'],
        account_id=state['account_id'], broker_mode=state['broker_mode'], state_version=version,
        side='buy', entry_data_qualified=True, realtime_sip_qualified=quote_required, regime_qualified=True,
        standard_entry_quote_check_enabled=quote_required,
        price_basis='realtime_quote' if quote_required else 'bounded_standard_limit',
        order_type=effective_type, order_limit_price=effective_limit,
        realtime_gap_checked=(quote_required and kind == 'ENTRY' and standard_initial(state)
            and float(state['entry_policy']['max_entry_gap_pct']) > 0),
        reference_price_asof=str(context.get('reference_price_asof')) if not quote_required else None,
        factor_model_checked=cfg.enable_factor_model,
        factor_beta_basis=cfg.beta_exposure_basis if cfg.enable_factor_model else None,
        factor_beta_exposure=factor_beta_exposure,
        factor_beta_limit=cfg.max_portfolio_beta if cfg.enable_factor_model else None,
        factor_snapshot_hash=context['factor_context']['snapshot_hash'] if cfg.enable_factor_model else None,
        factor_rejections=factor_rejections,
        qualified=True, max_quantity=quantity, limit_price=price, config_hash=cfg.fingerprint,
        portfolio_hash=fingerprint, available_at=now.isoformat(),
        valid_until=(now+timedelta(seconds=min(30, policy.max_quote_age_seconds))).isoformat(),
        reason=('FACTOR_RISK_REJECTED: '+'; '.join(factor_rejections) if factor_rejections
            else (checker.get_last_decision_reason() if quantity else 'CAMPAIGN_RISK_OR_CAPACITY_EXHAUSTED')))
