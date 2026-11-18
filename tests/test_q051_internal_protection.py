from unittest.mock import Mock

import pandas as pd
import pytest

from scripts.research.us_q051_internal_protection_policy_20261117 import internal_states,HalfNewEntry
from scripts.research.us_q051_winrate_recovery_audit_20261117 import rate_switch


def rates():
    days=pd.bdate_range('2023-01-02',periods=40)
    return pd.DataFrame({'qualified':True,'recent_rate':[.4]*3+[.49]*5+[.2]*32,'reference_rate':.5},index=days)


def test_rate_rule_matches_archived_switch_and_is_prefix_causal():
    r=rates();e=pd.Series(100.,index=r.index)
    a=internal_states(r,e,'RATE');old=rate_switch(r)
    pd.testing.assert_series_equal(a.active,old.active,check_names=False,check_index_type=False)
    assert a.iloc[2].transition=='ON' and a.iloc[7].transition=='OFF'
    b=internal_states(r.iloc[:25],e.iloc[:25],'RATE')
    pd.testing.assert_frame_equal(a.iloc[:25],b)


def test_shadow_return_waits_twenty_closes_and_five_confirmations():
    r=rates();r.recent_rate=.2;e=pd.Series([100.]*20+[110.]*20,index=r.index)
    a=internal_states(r,e,'SHADOW')
    assert a.iloc[2].transition=='ON' and a.iloc[23].active and a.iloc[24].transition=='OFF'
    # Rate coverage can be missing in protection: independently observed shadow
    # returns still permit recovery. Missing rate evidence cannot initiate ON.
    r.loc[r.index[20:],'qualified']=False
    b=internal_states(r,e,'SHADOW');assert b.iloc[24].transition=='OFF'
    unknown=r.copy();unknown.qualified=False
    assert not internal_states(unknown,e,'SHADOW').active.any()


def test_unknown_rate_preserves_active_state_and_resets_confirmations():
    r=rates();r.loc[r.index[5],'qualified']=False;e=pd.Series(100.,index=r.index)
    a=internal_states(r,e,'RATE')
    assert a.iloc[7].active and a.iloc[5].active


def test_rate_recovery_decisions_do_not_depend_on_shadow_account_choice():
    r=rates();flat=pd.Series(100.,index=r.index);rising=pd.Series(range(100,140),index=r.index,dtype=float)
    a=internal_states(r,flat,'RATE');b=internal_states(r,rising,'RATE')
    pd.testing.assert_frame_equal(a.drop(columns='shadow_ret20'),b.drop(columns='shadow_ret20'))


def test_half_uses_previous_close_and_rechecks_native_integer_limits():
    r=rates();states=internal_states(r,pd.Series(100.,index=r.index),'RATE');p=HalfNewEntry(states)
    native=Mock(side_effect=lambda state,ver,qty,snap,now,context:dict(max_quantity=min(qty,11)))
    approve=p.wrap(native)
    opening=(r.index[2]+pd.offsets.BDay()).tz_localize('America/New_York')+pd.Timedelta(hours=9,minutes=30)
    result=approve({'symbol':'AAA'},0,50,{'opening_at':opening},opening,context={})
    assert result['max_quantity']==5 and native.call_args_list[-1].args[2]==5
    assert p.receipts[-1]['native_quantity']==11
    # The OFF close cannot change an order from that same day's opening.
    off_open=r.index[7].tz_localize('America/New_York')+pd.Timedelta(hours=9,minutes=30)
    assert approve({'symbol':'AAA'},0,50,{'opening_at':off_open},off_open,context={})['max_quantity']==5


def test_inactive_is_exact_passthrough_and_active_cannot_override_veto():
    r=rates();states=internal_states(r,pd.Series(100.,index=r.index),'RATE');p=HalfNewEntry(states)
    original={'max_quantity':0,'reason':'native veto'};native=Mock(return_value=original);approve=p.wrap(native)
    opening=r.index[1].tz_localize('America/New_York')+pd.Timedelta(hours=9,minutes=30)
    assert approve({'symbol':'AAA'},0,50,{'opening_at':opening},opening,context={}) is original
    assert native.call_count==1
    opening=r.index[3].tz_localize('America/New_York')+pd.Timedelta(hours=9,minutes=30)
    assert approve({'symbol':'AAA'},0,50,{'opening_at':opening},opening,context={})['max_quantity']==0


@pytest.mark.usefixtures('isolated_winner_config')
def test_native_replay_half_is_applied_once_and_sl_terms_stay_identical():
    from tests.test_winner_daily_entry import daily_fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,raw=daily_fixture(confirmation_bars=0,stop_loss_pct=.05)
    raw[cfg.start_date,'AAA'].loc[0,'low']=90.
    original=BacktestEngine(cfg).run(**args)
    dates=pd.bdate_range('2024-01-01','2026-10-30')
    states=pd.DataFrame({'active':True,'qualified':True},index=dates)
    p=HalfNewEntry(states);half=BacktestEngine(cfg).run(**args,winner_entry_risk_policy=p)
    a=original.closed_trades_df.iloc[0];b=half.closed_trades_df.iloc[0]
    assert b.quantity==a.quantity//2 and b.entry_price==a.entry_price and b.exit_price==a.exit_price
    assert b.exit_reason==a.exit_reason and b.exit_date==a.exit_date
    assert len(p.receipts)==1
    states.active=False
    same=BacktestEngine(cfg).run(**args,winner_entry_risk_policy=HalfNewEntry(states))
    pd.testing.assert_series_equal(original.equity_curve,same.equity_curve)
    pd.testing.assert_frame_equal(original.trade_events_df,same.trade_events_df)
