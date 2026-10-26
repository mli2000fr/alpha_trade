from copy import deepcopy
from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from scripts.research.us_winner_start_state_audit_20261025 import (
    ObservationHooks, broker_snapshot, independent_cash, reset_guard_only, stable_hash,
)


def test_cash_uses_explicit_deposit_not_fixed_4000():
    events = pd.DataFrame([
        dict(event='BUY_FILL',symbol='A',quantity=10.,price=20.,costs=.16),
        dict(event='SELL_FILL',symbol='A',quantity=10.,price=21.,costs=.168),
        dict(event='FINANCING',symbol=None,quantity=None,price=None,costs=.05),
    ])
    first, fees, held = independent_cash(events,4000.)
    other, other_fees, other_held = independent_cash(events,7980.1667511581745)
    assert first == pytest.approx(4009.622)
    assert other-first == pytest.approx(3980.1667511581745)
    assert fees == other_fees == pytest.approx(.328)
    assert held == other_held == {}


def test_cash_does_not_tolerate_repeated_buy_or_oversell():
    repeated = pd.DataFrame([dict(event='BUY_FILL',symbol='A',quantity=1.,price=10.,costs=.008)]*2)
    with pytest.raises(ValueError,match='Repeated'):
        independent_cash(repeated,4000.)
    oversell = repeated.iloc[:1].copy()
    oversell.loc[0,'event'] = 'SELL_FILL'
    with pytest.raises(ValueError,match='Oversell'):
        independent_cash(oversell,4000.)


def test_guard_reset_uses_observed_equity_and_no_fictitious_old_peak():
    from common.winner_risk_state import CampaignRiskState
    from risk_management.config import RiskConfig
    cfg = RiskConfig(account_equity=4000.,policy='b4',max_portfolio_drawdown_pct=.15)
    guard = CampaignRiskState(cfg,observations=[(date(2019,12,30),10000.)],regimes={date(2019,12,30):'SLIDE'})
    guard.evaluate(date(2019,12,31),7980.,'SLIDE',daily_pnl=-2020.)
    assert guard.data['tripped']
    previous = deepcopy(guard.data)
    reset_guard_only(guard,date(2019,12,31),7980.,'SLIDE',CampaignRiskState)
    assert guard.data['peaks'] == {'2019-12-31':7980.}
    assert not guard.data['tripped']
    assert previous['peaks']['2019-12-30'] == 10000.
    assert guard.cfg == cfg


def test_observation_hooks_do_not_change_native_fills_or_cash_and_restore_classes():
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    from tests.test_us_winner_monthly_selector_20261024 import replay_fixture
    from backtesting.simulator import BacktestEngine
    native = repair.study.native
    originals = native.ReplayBroker,native.MemoryCampaignStore,native.CampaignRiskState,native.reapprove_campaign
    results = []
    hooks = ObservationHooks(native)
    for observe in [False,True]:
        cfg,kwargs = replay_fixture()
        with repair.study.capacity.corrected_runtime(),repair.campaign_adapter(cfg.exec_config,lambda _d:repair.study.REFERENCE):
            if observe:
                with hooks.installed():
                    result = BacktestEngine(cfg).run(**kwargs)
            else:
                result = BacktestEngine(cfg).run(**kwargs)
        results.append(result)
    pd.testing.assert_series_equal(results[0].equity_curve,results[1].equity_curve)
    pd.testing.assert_frame_equal(results[0].intraday_equity_curve,results[1].intraday_equity_curve)
    for result in results:
        assert result.trade_events_df.event.eq('BUY_FILL').sum() == 1
    columns = ['time','event','quantity','price','costs']
    pd.testing.assert_frame_equal(results[0].trade_events_df[columns],results[1].trade_events_df[columns])
    assert originals == (native.ReplayBroker,native.MemoryCampaignStore,native.CampaignRiskState,native.reapprove_campaign)
    assert hooks.risk_rows and hooks.guard_days
    assert 'constraint_reason' in hooks.risk_rows[0]
    assert hooks.checkpoint(date(2020,11,3))['guard_reset'] is False


def test_checkpoint_reset_preserves_all_broker_and_campaign_state():
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    from tests.test_us_winner_monthly_selector_20261024 import replay_fixture
    from backtesting.simulator import BacktestEngine
    cfg,kwargs = replay_fixture()
    hooks = ObservationHooks(repair.study.native)
    with repair.study.capacity.corrected_runtime(),repair.campaign_adapter(cfg.exec_config,lambda _d:repair.study.REFERENCE),hooks.installed():
        BacktestEngine(cfg).run(**kwargs)
        before = stable_hash(broker_snapshot(hooks.book,hooks.store))
        receipt = hooks.checkpoint(date(2020,11,3),reset=True)
        after = stable_hash(broker_snapshot(hooks.book,hooks.store))
    assert before == after == receipt['unchanged_account_hash']
    assert receipt['guard_after']['peaks'] == {'2020-11-03':receipt['account']['equity']}
    assert receipt['guard_reset'] is True


def test_annual_return_is_chained_without_annual_reset():
    from types import SimpleNamespace
    from scripts.research.us_winner_start_state_audit_20261025 import annual_rows
    result = SimpleNamespace(equity_curve=pd.Series([8000.,12000.],index=pd.to_datetime(['2019-12-31','2020-12-31'])),
        intraday_equity_curve=pd.DataFrame(dict(timestamp=pd.to_datetime(['2019-12-31T20:00Z','2020-12-31T20:00Z']),
            equity=[8000.,12000.],gross=[4000.,6000.])))
    rows = annual_rows(result,4000.)
    assert rows[0]['return_pct'] == 100.
    assert rows[1]['starting_equity'] == 8000.
    assert rows[1]['return_pct'] == 50.
