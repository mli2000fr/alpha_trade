from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from scripts.research.us_q051_spy_switch_policy_20261117 import switch_states,SwitchedRegime,SwitchedBudget


def tape():
    return pd.Series([100.]*250+[90.,85.]+[110.]*5,index=pd.bdate_range('2023-01-02',periods=257))


def test_asymmetric_confirmations_and_state_memory():
    s=tape();a=switch_states(s,20)
    assert not a.iloc[250].active and a.iloc[251].transition=='ON'
    assert a.iloc[252:256].active.all() and a.iloc[256].transition=='OFF'
    assert not a.iloc[256].active
    b=switch_states(pd.concat([s.iloc[:252],pd.Series([85.]*10,index=pd.bdate_range(s.index[251]+pd.Timedelta(days=1),periods=10))]),20)
    assert b.iloc[-1].active # no signal callback needed for these days


def test_future_prices_cannot_change_any_previous_state():
    s=tape().rename_axis('date');original=switch_states(s,20);other=s.copy();other.iloc[253:]=1e6
    changed=switch_states(other,20)
    pd.testing.assert_frame_equal(original.iloc[:253],changed.iloc[:253])
    pd.testing.assert_frame_equal(original.iloc[:253],switch_states(s.iloc[:253],20))


def test_gate_is_inactive_until_confirmed_then_uses_original_sma200():
    s=tape();a=switch_states(s,20);gate=SwitchedRegime(s.to_frame('SPY'),a)
    rows=pd.DataFrame({'symbol':['AAA','BBB']})
    def apply(i):return gate(s.index[i],rows,s.index[i].tz_localize('UTC')+pd.Timedelta(days=1,hours=14))
    assert apply(250)['selected']==['AAA','BBB']
    assert apply(251)['selected']==[]
    assert apply(252)['selected']==['AAA','BBB'] # still protected, but SPY200 permits
    assert gate.receipts[-1]['protection_active']
    with pytest.raises(ValueError,match='precede'):gate(s.index[251],rows,s.index[251].tz_localize('UTC'))


def test_inactive_budget_is_exact_native_passthrough_active_uses_same_budget():
    s=tape();a=switch_states(s,20);budget=SwitchedBudget(s.to_frame('SPY'),a)
    native=Mock(return_value={'max_quantity':10,'reason':'native'});reduced={'max_quantity':4}
    def wrapped(original):
        assert original is native
        def protected(*args,**kwargs):
            budget.defensive.receipts.append({'status':'QUALIFIED'});return reduced
        return protected
    budget.defensive.wrap=wrapped;approve=budget.wrap(native)
    def apply(i):
        opening=(s.index[i]+pd.offsets.BDay()).tz_localize('America/New_York')+pd.Timedelta(hours=9,minutes=30)
        return approve({'symbol':'AAA'},0,10,{'opening_at':opening},opening,context={})
    assert apply(250) is native.return_value and native.call_count==1
    assert apply(251) is reduced and native.call_count==1
    assert not budget.receipts[0]['protection_active'] and budget.receipts[1]['budget_called']
    assert budget.defensive.target==.20 and budget.defensive.lookback==60


@pytest.mark.parametrize('kwargs',[{'window':0},{'window':20,'on_sessions':0},{'window':20,'entry_buffer':.02,'exit_buffer':.01}])
def test_invalid_switch_contract_fails_closed(kwargs):
    with pytest.raises(ValueError):switch_states(tape(),**kwargs)


@pytest.mark.usefixtures('isolated_winner_config')
def test_native_replay_inactive_switch_preserves_fills_and_equity():
    from tests.test_winner_daily_entry import daily_fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,_=daily_fixture(confirmation_bars=0)
    baseline=BacktestEngine(cfg).run(**args)
    dates=pd.bdate_range('2024-01-01','2026-10-30');s=pd.Series(100.,index=dates)
    close=s.to_frame('SPY');states=switch_states(s,50)
    switched=BacktestEngine(cfg).run(**args,winner_selection_source=SwitchedRegime(close,states),
        winner_entry_risk_policy=SwitchedBudget(close,states))
    pd.testing.assert_series_equal(baseline.equity_curve,switched.equity_curve)
    pd.testing.assert_frame_equal(baseline.trade_events_df,switched.trade_events_df)
