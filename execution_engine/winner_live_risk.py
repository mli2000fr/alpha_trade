"""Live campaign risk context, captured under the canonical account lock.

No prediction, training or order submission. SQL writes are limited to the
account-scoped breaker state, and only when a campaign actually requests entry.
The historical equity seed is reported account observations, not a reconstructed
continuous NAV or an invented high-watermark.
"""
from datetime import UTC, datetime, timedelta
from dataclasses import replace
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import math

import pandas as pd
from sqlalchemy import bindparam, text

from common.market_calendar import get_market_calendar
from common.winner_pyramiding import aware
from common.winner_risk_state import CampaignRiskState
from execution_engine.account_state import build_account_constraint_state
from execution_engine.winner_campaign_store import WinnerCampaignStore
from execution_engine.winner_risk import reapprove_campaign
from risk_management.config import load_risk_config
from risk_management.db_io import RiskRepository
from risk_management.liquidity import LiquidityGate


class NativeWinnerRisk:
    def __init__(self, repo, broker, config, *, context_provider=None, clock=None):
        self.repo, self.broker, self.config = repo, broker, config
        self.context_provider = context_provider or self.capture
        self.clock = clock or (lambda: datetime.now(UTC))

    def __call__(self, state, version, quantity, snapshot, now, kind):
        context = self.context_provider(state, snapshot, now, kind)
        decision_time = aware(self.clock())
        return reapprove_campaign(state, version, quantity, snapshot, decision_time, kind, context=context)

    def capture(self, state, snapshot, now, kind):
        from common.config_loader import load_config
        from corporate_actions.db_io import CorporateActionRepository
        from risk_management.cli import _resolve_market_regime_snapshot, _evaluate_regime_transition
        from risk_management.regime_apply import apply_snapshot, apply_structural_market_guards, apply_transition
        from risk_management.live_pipeline_guards import evaluate_vol_target
        from service.market.new_entry_data_guard import check_new_entry_data
        from service.market import parse_market_regimes
        now = aware(now)
        if (state['account_id'] != self.config.resolved_account_id
                or state['broker_mode'] != self.config.broker_mode or self.config.market_code != 'US_EQ'):
            raise ValueError('Campaign risk routing mismatch')
        # Fail before querying portfolio state if no fresh SIP quote is usable.
        if snapshot.get('feed') != 'sip' or snapshot.get('quote_error') or snapshot.get('ask') is None:
            raise ValueError('SIP realtime unavailable; no fallback')
        if not 0 <= (now-aware(snapshot['quote_time'])).total_seconds() <= state['policy']['max_quote_age_seconds']:
            raise ValueError('SIP quote stale/future')
        engine, account, mode = self.repo.engine, state['account_id'], state['broker_mode']
        if engine.dialect.name != 'mysql' or engine.url.database != 'alpha_trade':
            raise ValueError('Actual campaign risk collector requires US alpha_trade')
        cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
        today = now.astimezone(ZoneInfo('America/New_York')).date()
        sessions = [s for s in cal.sessions(today-timedelta(days=14), today) if s.is_open]
        current = next((s for s in sessions if s.session_date == today), None)
        if current is None or not current.open_at_utc <= now < current.close_at_utc:
            raise ValueError('Fresh entry reapproval requires regular US trading hours')
        prior = [s for s in sessions if s.close_at_utc < now][-1].session_date
        rejected = check_new_entry_data(engine, [state['symbol']], prior, now=now)
        if rejected:
            raise ValueError(str(rejected))
        raw_account = self.broker.get_account_snapshot()
        if any(raw_account.get(k) is True for k in ('trading_blocked', 'account_blocked', 'trade_suspended_by_user')):
            raise ValueError('Broker account blocks trading')
        # The watcher's generic defaults are cash/no-leverage. Preserve the
        # step12 account policy instead, bounded by today's global permission.
        # A later YAML change can lower, never enlarge, an admitted leverage cap.
        account_cfg = account_config_for_campaign(self.config, state)
        capacity = build_account_constraint_state(account_cfg,
            SimpleNamespace(get_account_snapshot=lambda: raw_account))
        cfg = load_risk_config(equity=capacity.equity)
        risk_repo = RiskRepository(engine)
        raw_config = load_config()
        regime_config = parse_market_regimes(raw_config.get('market_regimes'))
        cfg = apply_structural_market_guards(cfg, market_regimes_config=regime_config, equity=capacity.equity)
        regime = _resolve_market_regime_snapshot(prior, capacity.equity, risk_repo)
        regime_enabled = regime_config.enabled
        if regime_enabled:
            if (regime is None or regime.trade_date != prior
                    or not 0 <= (aware(self.clock())-aware(regime.as_of)).total_seconds() <= 300
                    or regime.data_quality.get('macro') not in (None, 'ok')):
                raise ValueError('Native market regime date/freshness/mandatory macro unqualified')
        cfg = apply_snapshot(cfg, regime)
        cfg = apply_transition(cfg, _evaluate_regime_transition(regime))
        cfg = cfg.with_overrides(max_gross_exposure=min(cfg.max_gross_exposure,
            capacity.effective_leverage if capacity.leverage_active else 1.))
        orders = self.broker.list_recent_orders(status='open', limit=500)
        if len(orders) >= 500:
            raise ValueError('Open-order snapshot may be truncated')
        raw_positions = self.broker.get_all_positions()
        positions = [dict(symbol=p['symbol'], side=p['side'], quantity=abs(float(p['qty'])),
            mark=float(p['current_price'])) for p in raw_positions]
        if len({p['symbol'] for p in positions}) != len(positions):
            raise ValueError('Duplicate broker positions')
        longs = {p['symbol'] for p in positions if p['side'] == 'long'}
        pending = []
        for order in orders:
            # Standing long exits consume shares, not additional gross capital.
            if order.get('side') == 'sell' and order['symbol'] in longs:
                continue
            remaining = float(order['qty'])-float(order.get('filled_qty') or 0)
            if remaining <= 0:
                continue
            price = order.get('limit_price') or order.get('stop_price')
            if price is None:
                raise ValueError('Pending market order has no qualified capital reservation')
            pending.append(dict(symbol=order['symbol'], side=order['side'], notional=remaining*float(price)))
        symbols = sorted({state['symbol']} | {p['symbol'] for p in positions} | {o['symbol'] for o in pending})
        statement = text('SELECT symbol, sector FROM stock_metadata WHERE symbol IN :symbols').bindparams(
            bindparam('symbols', expanding=True))
        with engine.connect() as conn:
            sector_map = {r.symbol: r.sector for r in conn.execute(statement, {'symbols': symbols})}
            # Every candidate is also checked against the broker's current asset
            # status, rather than treating an old model universe as tradability.
            history = conn.execute(text('SELECT equity, created_at FROM broker_account_snapshots '
                'WHERE account_id=:account AND broker_mode=:mode AND equity>0 '
                "AND snapshot_kind='preflight' AND created_at<=:now ORDER BY created_at"),
                {'account': account, 'mode': mode, 'now': now}).mappings().all()
            fills = conn.execute(text('SELECT f.symbol, r.request_id, r.side, r.intent_role, f.filled_qty, '
                'f.avg_fill_price, f.fill_timestamp FROM execution_broker_fills f '
                'JOIN execution_order_requests r ON f.request_id=r.request_id '
                'JOIN execution_runs e ON r.exec_run_id=e.exec_run_id '
                'WHERE f.account_id=:account AND e.broker_mode=:mode AND f.symbol=:symbol '
                'AND f.fill_timestamp<=:now ORDER BY f.fill_timestamp, f.fill_id'),
                {'account': account, 'mode': mode, 'symbol': state['symbol'], 'now': now}).mappings().all()
        asset = self.broker._client.get_asset(state['symbol'])
        if asset.get('tradable') is not True or asset.get('status') != 'active':
            raise ValueError('Broker asset is not active/tradable')
        available = capacity.buying_power_available
        if account_cfg.account_type == 'margin' and asset.get('marginable') is not True:
            cash_capacity = float(raw_account.get('non_marginable_buying_power') or 0)
            if not math.isfinite(cash_capacity) or cash_capacity < 0:
                raise ValueError('Candidate non-marginable cash capacity unavailable')
            available = min(available, cash_capacity)
        prices = risk_repo.load_prices_asof([state['symbol']], prior)
        if state['symbol'] not in prices:
            raise ValueError('Prior-session native price/ATR/ADV unavailable')
        returns = risk_repo.load_return_matrix_asof(sorted(set(symbols+['SPY'])), prior,
            max(252, cfg.correlation_lookback_days, cfg.vol_target_lookback_days))
        vol_scale = 1.
        if cfg.target_annual_vol:
            decision = evaluate_vol_target(returns.get('SPY', pd.Series(dtype=float)),
                target_annual_vol=cfg.target_annual_vol, lookback_days=cfg.vol_target_lookback_days,
                benchmark_symbol='SPY')
            if not decision.applied:
                raise ValueError('Native volatility target unqualified: '+decision.reason)
            vol_scale = min(1., float(decision.scaler))
        # SPY price history (not returns) qualifies the native SMA50/200 regime.
        with engine.connect() as conn:
            spy_rows = conn.execute(text("SELECT date, close FROM stock_bars_daily WHERE symbol='SPY' "
                'AND date<=:prior ORDER BY date'), {'prior': prior}).all()
        if len({r[0] for r in spy_rows}) != len(spy_rows):
            raise ValueError('SPY daily source ambiguous')
        from backtesting.regime_trailing import compute_regime
        spy = pd.Series([float(r[1]) for r in spy_rows], index=pd.to_datetime([r[0] for r in spy_rows]))
        regimes = {pd.Timestamp(k).date(): v for k, v in compute_regime(spy).dropna().items()}
        observations = {}
        for row in history:
            stamp = row['created_at']
            stamp = stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else aware(stamp)
            local_day = stamp.astimezone(ZoneInfo('America/New_York')).date()
            candidates = [s for s in cal.sessions(local_day-timedelta(days=7), local_day) if s.is_open and s.close_at_utc <= stamp]
            if candidates:
                observed_day = candidates[-1].session_date
                if observed_day <= prior:
                    observations[observed_day] = max(observations.get(observed_day, 0.), float(row['equity']))
        store = WinnerCampaignStore(engine)
        saved, guard_version = store.get_guard(account, mode)
        if not observations and not saved:
            raise ValueError('No account/mode-specific observed equity seed; high-watermark not invented')
        controller = CampaignRiskState(cfg, saved=saved, observations=observations.items(), regimes=regimes)
        last_equity = float(raw_account.get('last_equity') or 0)
        if not math.isfinite(last_equity) or last_equity <= 0:
            raise ValueError('Broker previous equity required for daily PnL')
        evaluated = controller.evaluate(today, capacity.equity, regimes.get(prior),
            daily_pnl=capacity.equity-last_equity)
        store.save_guard(account, mode, controller.data, guard_version)
        pending_ca = CorporateActionRepository(engine).load_pending_events(as_of=today)
        concentration = concentration_allowed(fills, cfg, state['symbol'], today, kind)
        allowed = not self.config.blocks_new_entries
        if regime is not None:
            allowed = allowed and not regime.blocks_entry_for(state['symbol'], sector_map.get(state['symbol'], ''), side='buy')[0]
        return dict(account_id=account, broker_mode=mode, captured_at=self.clock(), equity=capacity.equity,
            available_buying_power=available, positions=positions, pending_entries=pending,
            sector_map=sector_map, risk_config=cfg, circuit_breaker=evaluated['circuit_breaker'],
            breaker_qualified=True, allocation_scale=evaluated['allocation_scale'], return_matrix=returns[symbols].tail(cfg.correlation_lookback_days),
            adv_usd=prices[state['symbol']].adv_usd, cost_reserve_pct=state['policy']['cost_reserve_bps_per_leg']/10000,
            max_spread_bps=LiquidityGate().max_spread_bps, volatility_allocation_scale=vol_scale,
            entry_data_qualified=True, regime_qualified=not regime_enabled or regime is not None,
            concentration_qualified=True, concentration_allowed=concentration,
            corporate_actions_qualified=not any(e.symbol == state['symbol'] for e in pending_ca),
            entries_allowed=allowed, factor_qualified=not cfg.enable_factor_model)


def account_config_for_campaign(config, state, current=None):
    from execution_engine.config import LeverageConfig, load_leverage_config_from_yaml
    policy = state.get('account_policy')
    if not policy or policy.get('account_type') not in ('cash', 'margin'):
        raise ValueError('Frozen admission account policy required')
    frozen = LeverageConfig(**policy['leverage'])
    current = current or load_leverage_config_from_yaml()
    enabled = frozen.enabled and current.enabled and frozen.mode == current.mode == 'regt_swing'
    leverage = replace(current, enabled=enabled, mode='regt_swing' if enabled else 'disabled',
        max_leverage=min(frozen.max_leverage, current.max_leverage),
        min_equity_usd=max(frozen.min_equity_usd, current.min_equity_usd))
    return replace(config, dry_run=False, account_type=policy['account_type'], leverage=leverage)


def concentration_allowed(fills, cfg, symbol, today, kind):
    from risk_management.concentration import SymbolTradeTracker, ConsecutiveLossTracker
    trades = SymbolTradeTracker(cfg.concentration_max_trades_per_symbol, cfg.concentration_window_calendar_days)
    losses = ConsecutiveLossTracker(cfg.concentration_max_consecutive_losses, cfg.concentration_blacklist_duration_days)
    lots, entry_requests = [], set()
    for row in fills:
        stamp = row['fill_timestamp']
        stamp = stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else aware(stamp)
        day = stamp.astimezone(ZoneInfo('America/New_York')).date()
        quantity, price = float(row['filled_qty']), float(row['avg_fill_price'])
        if row['side'] == 'buy' and row['intent_role'] in ('entry', 'adopted_entry', 'rebalance_buy'):
            key = row.get('request_id') or ('unscoped', stamp.isoformat())
            if key not in entry_requests:
                trades.record(symbol, day, side='buy')
                entry_requests.add(key)
            lots.append([quantity, price, 0.])
        elif row['side'] == 'sell' and row['intent_role'] not in ('entry', 'adopted_entry'):
            remaining = quantity
            while remaining > 1e-9 and lots:
                lot = lots[0]
                used = min(lot[0], remaining)
                lot[0] -= used
                lot[2] += used*(price-lot[1])
                remaining -= used
                if lot[0] < 1e-9:
                    losses.record(symbol, lot[2], day, side='buy')
                    lots.pop(0)
    return (kind == 'ADD' or trades.allow_entry(symbol, today, side='buy')) and not losses.is_blacklisted(symbol, today, side='buy')
