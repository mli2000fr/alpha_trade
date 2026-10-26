from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.usefixtures('isolated_winner_config')

from common.winner_risk_state import CampaignRiskState
from execution_engine.winner_live_risk import NativeWinnerRisk
from execution_engine.winner_risk import reapprove_campaign
from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.config import RiskConfig
from test_winner_runtime import setup, market, NOW


def context(cfg=None):
    cfg = cfg or RiskConfig(account_equity=4000., risk_per_trade_pct=.03,
        max_position_weight=.5, min_position_notional=10., correlation_min_overlap=20)
    return dict(account_id='default', broker_mode='paper', captured_at=NOW,
        equity=4000., entry_data_qualified=True, regime_qualified=True,
        concentration_qualified=True, corporate_actions_qualified=True, concentration_allowed=True,
        entries_allowed=True, max_spread_bps=50., risk_config=cfg,
        breaker_qualified=True, circuit_breaker=CircuitBreaker(cfg, PnLSnapshot(4000, 4000, 0)),
        allocation_scale=1., positions=[], pending_entries=[], sector_map={'TEST': 'Technology'},
        return_matrix=pd.DataFrame({'TEST': np.sin(np.arange(60))}), available_buying_power=4000.,
        cost_reserve_pct=.0025, volatility_allocation_scale=1., adv_usd=10000000.)


def data():
    cfg, store, _, _ = setup()
    state = store.rows()[0]['state']
    snap = market(state, NOW) | dict(feed='sip', quote_time=NOW)
    return state, snap


def test_native_reapproval_and_live_factory_are_actually_connected():
    state, snap = data()
    ctx = context()
    native = NativeWinnerRisk(None, None, None, context_provider=lambda *a: ctx, clock=lambda: NOW)
    result = native(state, 0, 10, snap, NOW, 'ENTRY')
    assert result['producer'] == 'native_intraday_risk' and result['max_quantity'] == 10
    assert result['config_hash'] and result['portfolio_hash'] and result['limit_price'] == 101.


@pytest.mark.parametrize('changes', [dict(broker_mode='live'), dict(entry_data_qualified=False),
    dict(regime_qualified=False), dict(concentration_allowed=False), dict(corporate_actions_qualified=False),
    dict(breaker_qualified=False), dict(entries_allowed=False), dict(available_buying_power=-1.),
    dict(captured_at=NOW-timedelta(seconds=61))])
def test_native_rejections_never_produce_positive_approval(changes):
    state, snap = data()
    ctx = context() | changes
    try:
        result = reapprove_campaign(state, 0, 10, snap, NOW, 'ENTRY', context=ctx)
    except ValueError:
        return
    assert result['max_quantity'] == 0


def test_realtime_sip_staleness_and_spread_caps():
    state, snap = data()
    for change in [dict(feed='iex'), dict(quote_time=NOW-timedelta(seconds=61)),
            dict(quote_time=NOW+timedelta(seconds=1)), dict(bid=90.)]:
        with pytest.raises(ValueError):
            reapprove_campaign(state, 0, 10, snap | change, NOW, 'ENTRY', context=context())


def test_risk_budget_half_fraction_and_real_capital_are_reapplied():
    state, snap = data()
    ctx = context(RiskConfig(account_equity=4000., risk_per_trade_pct=.01,
        max_position_weight=.5, min_position_notional=10.))
    result = reapprove_campaign(state, 0, 10, snap, NOW, 'ENTRY', context=ctx)
    assert 0 < result['max_quantity'] < 10
    limited = reapprove_campaign(state, 0, 10, snap, NOW, 'ENTRY', context=context() | {'available_buying_power': 101.})
    assert limited['max_quantity'] == 0  # Includes cost reserve; one share would overspend.


def test_add_is_same_slot_but_combined_notional_still_capped():
    from common.winner_pyramiding import add_fill
    state, snap = data()
    add_fill(state, parent_id='lot', quantity=10, price=100., filled_at=NOW)
    ctx = context()
    ctx['risk_config'] = replace(ctx['risk_config'], max_positions=1, max_position_weight=.3)
    ctx['positions'] = [dict(symbol='TEST', side='long', quantity=10, mark=107.)]
    result = reapprove_campaign(state, 0, 10, snap | {'ask': 107., 'bid': 106.9}, NOW, 'ADD', context=ctx)
    assert result['max_quantity'] == 1  # $1200 cap minus $1070 already held.


def test_breaker_persists_peak_and_only_advances_favorable_streak_once_a_day():
    cfg = RiskConfig(account_equity=4000., policy='b4', rolling_peak_window_days=252)
    ctl = CampaignRiskState(cfg, observations=[(date(2026, 10, 16), 5000.)],
        regimes={date(2026, 10, 16): 'BULL'})
    result = ctl.evaluate(date(2026, 10, 19), 4000., 'SLIDE', daily_pnl=-1000.)
    assert result['reference_peak'] == 5000. and result['allocation_scale'] < 1.
    saved = deepcopy(ctl.data)
    restarted = CampaignRiskState(cfg, saved=saved)
    restarted.evaluate(date(2026, 10, 19), 4050., 'BULL', daily_pnl=-950.)
    streak = restarted.data['episode']['favorable_streak']
    restarted.evaluate(date(2026, 10, 19), 4060., 'BULL', daily_pnl=-940.)
    assert restarted.data['episode']['favorable_streak'] == streak
    assert max(restarted.data['peaks'].values()) == 5000.
    with pytest.raises(ValueError, match='policy changed'):
        CampaignRiskState(replace(cfg, max_portfolio_drawdown_pct=.1), saved=saved)


def test_risk_state_cannot_invent_history_or_adaptive_regime():
    with pytest.raises(ValueError, match='real account equity observation'):
        CampaignRiskState(RiskConfig())
    with pytest.raises(ValueError, match='SPY regime'):
        CampaignRiskState(RiskConfig(policy='b4'), observations=[(date(2026, 10, 16), 4000.)])


def test_restart_recovers_observed_peak_during_downtime_without_favorable_days():
    cfg = RiskConfig(account_equity=4000., policy='b0')
    ctl = CampaignRiskState(cfg, observations=[(date(2026, 10, 16), 4000.)])
    saved = deepcopy(ctl.data)
    resumed = CampaignRiskState(cfg, saved=saved, observations=[(date(2026, 10, 19), 5000.)])
    assert resumed.data['normal_streak'] == ctl.data['normal_streak']
    observed = resumed.evaluate(date(2026, 10, 20), 4000., None, daily_pnl=0.)
    assert observed['reference_peak'] == 5000.


def test_watcher_defaults_cannot_change_frozen_account_type_or_grant_more_leverage():
    from dataclasses import asdict
    from execution_engine.config import ExecutionConfig, LeverageConfig
    from execution_engine.winner_live_risk import account_config_for_campaign
    admitted = LeverageConfig(enabled=True, mode='regt_swing', max_leverage=2., min_equity_usd=2000.)
    state = {'account_policy': dict(account_type='margin', leverage=asdict(admitted))}
    generic_watcher = ExecutionConfig(account_type='cash')
    actual = account_config_for_campaign(generic_watcher, state, admitted)
    assert actual.account_type == 'margin' and actual.leverage.max_leverage == 2.
    restricted = account_config_for_campaign(generic_watcher, state,
        replace(admitted, max_leverage=1.5, min_equity_usd=5000.))
    assert restricted.leverage.max_leverage == 1.5 and restricted.leverage.min_equity_usd == 5000.
    assert not account_config_for_campaign(generic_watcher, state,
        LeverageConfig()).leverage.enabled
    cash = {'account_policy': dict(account_type='cash', leverage=asdict(admitted))}
    assert account_config_for_campaign(generic_watcher, cash, admitted).account_type == 'cash'
