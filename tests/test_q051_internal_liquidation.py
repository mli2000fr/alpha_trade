from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from scripts.research.us_q051_internal_liquidation_policy_20261118 import ProtectedEntries,InternalLiquidation,prior_state


def states(active=False,transition=''):
    return pd.DataFrame(dict(active=active,transition=transition),index=pd.bdate_range('2026-10-01','2026-10-23'))


def test_dynamic_protection_is_inactive_passthrough_and_uses_previous_close():
    close=pd.DataFrame({'SPY':range(100,350)},index=pd.bdate_range('2025-11-01',periods=250))
    s=states();p=ProtectedEntries(s,close);native=lambda *a,**kw:dict(max_quantity=17,reason='native')
    opening=pd.Timestamp('2026-10-19T13:30Z');snapshot={'opening_at':opening}
    result=p.wrap(native)({'symbol':'AAA'},0,20,snapshot,opening,context={})
    assert result==dict(max_quantity=17,reason='native') and not p.budget.receipts
    s.loc[pd.Timestamp('2026-10-19'),'active']=True
    assert not prior_state(s,date(2026,10,19))[1].active
    rows=pd.DataFrame({'symbol':['AAA','BBB']})
    assert p.select(date(2026,10,16),rows,opening)['selected']==['AAA','BBB']


def test_protected_gate_uses_spy_history_only_during_active_state():
    days=pd.bdate_range('2025-01-01','2026-10-20');close=pd.DataFrame({'SPY':100.},index=days)
    close.loc['2026-10-16','SPY']=80.;s=states(True);p=ProtectedEntries(s,close)
    rows=pd.DataFrame({'symbol':['AAA']});opening=pd.Timestamp('2026-10-19T13:30Z')
    assert p.select(date(2026,10,16),rows,opening)['selected']==[]
    close.loc['2026-10-19','SPY']=1e6
    assert p.select(date(2026,10,16),rows,opening)['selected']==[]
    s.loc[pd.Timestamp('2026-10-16'),'active']=False
    assert p.select(date(2026,10,16),rows,opening)['selected']==['AAA']
    with pytest.raises(ValueError,match='same-session'):
        p.select(date(2026,10,19),rows,opening)


@pytest.mark.usefixtures('isolated_winner_config')
@pytest.mark.parametrize('gap',[False,True])
def test_total_exit_next_open_native_cash_fees_and_standing_stop_priority(gap):
    from tests.test_winner_daily_entry import daily_fixture
    from backtesting.simulator import BacktestEngine
    from backtesting import winner_global_liquidation as native
    cfg,args,raw=daily_fixture(confirmation_bars=0,stop_loss_pct=.05)
    s=states();s.loc[pd.Timestamp('2026-10-19'),['active','transition']]=[True,'ON']
    liquidator=InternalLiquidation(s)
    if gap:
        raw[date(2026,10,20),'AAA'].loc[0,['open','high','low','close']]=[90.,91.,89.,90.]
        args['open_df']=args['open_df'].copy();args['low']=args['low'].copy()
        args['open_df'].loc[pd.Timestamp('2026-10-20'),'AAA']=90.
        args['low'].loc[pd.Timestamp('2026-10-20'),'AAA']=89.
    with patch.object(native,'GlobalLiquidation',lambda *args:liquidator):result=BacktestEngine(cfg).run(**args)
    trades=result.closed_trades_df
    assert len(trades)==1 and trades.iloc[0].exit_date==pd.Timestamp('2026-10-20T13:30Z')
    assert trades.iloc[0].exit_reason==('STOP_GAP' if gap else 'INTERNAL_PROTECTION')
    assert trades.iloc[0].entry_fees>0 and trades.iloc[0].exit_fees>0
    assert not result.tracker_snapshot['winner_replay']['open_positions']
    assert len(liquidator.events)==1 and liquidator.pending is None
    assert liquidator.events[0]['signal_date']=='2026-10-19'
    assert result.tracker_snapshot['winner_replay']['costs']>0
    assert result.equity_curve.iloc[-1]==pytest.approx(4000+trades.pnl.sum())


@pytest.mark.usefixtures('isolated_winner_config')
def test_no_trigger_reproduces_native_reference_exactly():
    from tests.test_winner_daily_entry import daily_fixture
    from backtesting.simulator import BacktestEngine
    from backtesting import winner_global_liquidation as native
    cfg,args,_=daily_fixture(confirmation_bars=0,stop_loss_pct=.05)
    args['close']=args['close'].copy();args['close']['SPY']=100.
    before=BacktestEngine(cfg).run(**args);liquidator=InternalLiquidation(states())
    policy=ProtectedEntries(states(),args['close'])
    with patch.object(native,'GlobalLiquidation',lambda *args:liquidator):
        after=BacktestEngine(cfg).run(**args,winner_entry_risk_policy=policy,winner_selection_source=policy.select)
    pd.testing.assert_series_equal(before.equity_curve,after.equity_curve)
    pd.testing.assert_frame_equal(before.trade_events_df,after.trade_events_df)
    pd.testing.assert_frame_equal(before.intraday_equity_curve,after.intraday_equity_curve)


def test_active_budget_wraps_native_vol20_and_off_restores_unmodified_size():
    close=pd.DataFrame({'SPY':100.},index=pd.bdate_range('2025-01-01','2026-10-20'))
    s=states(True);p=ProtectedEntries(s,close);called=[]
    def budget_wrap(native):
        def approve(*args,**kwargs):called.append(True);return dict(max_quantity=3)
        return approve
    p.budget.wrap=budget_wrap;native=lambda *a,**kw:dict(max_quantity=10)
    approve=p.wrap(native);opening=pd.Timestamp('2026-10-19T13:30Z')
    assert approve({},0,10,{'opening_at':opening},opening,context={})['max_quantity']==3
    s.loc[pd.Timestamp('2026-10-16'),'active']=False
    assert approve({},0,10,{'opening_at':opening},opening,context={})['max_quantity']==10
    assert len(called)==1 and p.budget.target==.2 and p.budget.lookback==60
