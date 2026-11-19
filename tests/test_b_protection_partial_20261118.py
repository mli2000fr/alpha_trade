from datetime import date
from unittest.mock import patch
import pandas as pd
import pytest

from scripts.research.us_b_protection_partial_policy_20261118 import (
    recovery_states,CorePilotEntries,PilotLiquidation)


def state_frame(phase='NORMAL',transition=''):
    return pd.DataFrame(dict(phase=phase,active=phase!='NORMAL',transition=transition),
        index=pd.bdate_range('2025-01-01','2026-11-05'))


def test_recovery_requires_two_positive_returns_then_five_stable_closes_and_is_prefix_causal():
    index=pd.bdate_range('2025-01-01',periods=40)
    observer=pd.DataFrame(dict(active=False,transition=''),index=index)
    observer.loc[index[12]:,'active']=True;observer.loc[index[12],'transition']='ON'
    shadow=pd.Series([100.]*14+[101.+i for i in range(26)],index=index)
    result=recovery_states(observer,shadow,'PROGRESSIVE')
    assert result.loc[index[12],'phase']=='PROTECTED'
    assert result.loc[index[15],'phase']=='PROBE'
    assert result.loc[index[20],'phase']=='NORMAL'
    assert result.transition.eq('ON').sum()==1
    pd.testing.assert_frame_equal(result.iloc[:23],recovery_states(observer.iloc[:23],shadow.iloc[:23],'PROGRESSIVE'))
    old=recovery_states(observer,shadow,'OLD')
    assert old.active.equals(observer.active)


def test_half_protection_keeps_core_when_spy_rejects_and_probe_never_increases_native_size():
    close=pd.DataFrame({'SPY':100.},index=pd.bdate_range('2025-01-01','2026-11-05'))
    close.loc['2026-10-16','SPY']=70.
    states=state_frame('PROTECTED');p=CorePilotEntries(states,close,.5)
    native=lambda state,version,quantity,*a,**kw:dict(max_quantity=min(quantity,11),reason='native')
    opening=pd.Timestamp('2026-10-19T13:30Z');snapshot={'opening_at':opening}
    state={'symbol':'AAA','campaign_id':'campaign'}
    result=p.wrap(native)(state,0,20,snapshot,opening,context={})
    assert result['max_quantity']==6 and p.allocations['AAA']['core_quantity']==6
    states.loc[pd.Timestamp('2026-10-16'),'phase']='PROBE'
    assert p.wrap(native)(state,0,20,snapshot,opening,context={})['max_quantity']==8
    assert p.select(date(2026,10,16),pd.DataFrame({'symbol':['AAA']}),opening)['selected']==['AAA']


@pytest.mark.usefixtures('isolated_winner_config')
@pytest.mark.parametrize('later_stop',[False,True])
def test_partial_liquidation_rearms_retained_shares_and_preserves_open11(later_stop):
    from tests.test_winner_daily_entry import daily_fixture
    from backtesting.simulator import BacktestEngine
    from backtesting import winner_global_liquidation as native
    cfg,args,raw=daily_fixture(last=date(2026,11,4),confirmation_bars=0,stop_loss_pct=.05,horizon_sessions=10)
    args['close']=args['close'].copy();args['close']['SPY']=100.
    states=state_frame();states.loc[pd.Timestamp('2026-10-19'):,'phase']='PROTECTED'
    states.loc[pd.Timestamp('2026-10-19'):,'active']=True
    states.loc[pd.Timestamp('2026-10-19'),'transition']='ON'
    p=CorePilotEntries(states,args['close'],.5);p.full.gate=lambda day,rows,cutoff:dict(selected=[],incomplete=False)
    liquidation=PilotLiquidation(states,p)
    if later_stop:
        raw[date(2026,10,21),'AAA'].loc[0,['open','high','low','close']]=[90.,91.,89.,90.]
        for name,value in [('open_df',90.),('low',89.),('high',103.),('close',102.)]:
            args[name]=args[name].copy();args[name].loc[pd.Timestamp('2026-10-21'),'AAA']=value
    with patch.object(native,'GlobalLiquidation',lambda *a:liquidation):
        result=BacktestEngine(cfg).run(**args,winner_entry_risk_policy=p,winner_selection_source=p.select)
    trades=result.closed_trades_df
    assert len(trades)==2
    reduction=trades[trades.exit_reason.eq('PILOT_PROTECTION')].iloc[0]
    remaining=trades[~trades.exit_reason.eq('PILOT_PROTECTION')].iloc[0]
    assert reduction.exit_date==pd.Timestamp('2026-10-20T13:30Z')
    assert reduction.quantity<=remaining.quantity<=reduction.quantity+1
    if later_stop:assert remaining.exit_reason=='STOP_GAP'
    else:
        assert remaining.exit_reason=='HORIZON_OPEN'
        assert remaining.exit_date==pd.Timestamp('2026-11-02T14:30Z')
    assert not result.tracker_snapshot['winner_replay']['open_positions']
    assert result.equity_curve.iloc[-1]==pytest.approx(4000+trades.pnl.sum())


@pytest.mark.usefixtures('isolated_winner_config')
def test_no_protection_reproduces_native_exactly():
    from tests.test_winner_daily_entry import daily_fixture
    from backtesting.simulator import BacktestEngine
    from backtesting import winner_global_liquidation as native
    cfg,args,_=daily_fixture(confirmation_bars=0,stop_loss_pct=.05)
    args['close']=args['close'].copy();args['close']['SPY']=100.
    before=BacktestEngine(cfg).run(**args)
    states=state_frame();p=CorePilotEntries(states,args['close'],.5);liquidation=PilotLiquidation(states,p)
    with patch.object(native,'GlobalLiquidation',lambda *a:liquidation):
        after=BacktestEngine(cfg).run(**args,winner_entry_risk_policy=p,winner_selection_source=p.select)
    pd.testing.assert_series_equal(before.equity_curve,after.equity_curve)
    pd.testing.assert_frame_equal(before.closed_trades_df,after.closed_trades_df)


@pytest.mark.usefixtures('isolated_winner_config')
def test_partial_liquidation_does_not_resell_position_stopped_at_the_same_open():
    from tests.test_winner_daily_entry import daily_fixture
    from backtesting.simulator import BacktestEngine
    from backtesting import winner_global_liquidation as native
    cfg,args,raw=daily_fixture(confirmation_bars=0,stop_loss_pct=.05,horizon_sessions=10)
    args['close']=args['close'].copy();args['close']['SPY']=100.
    states=state_frame();states.loc[pd.Timestamp('2026-10-19'):,'phase']='PROTECTED'
    states.loc[pd.Timestamp('2026-10-19'):,'active']=True
    states.loc[pd.Timestamp('2026-10-19'),'transition']='ON'
    raw[date(2026,10,20),'AAA'].loc[0,['open','high','low','close']]=[90.,91.,89.,90.]
    for name,value in [('open_df',90.),('low',89.),('high',103.),('close',102.)]:
        args[name]=args[name].copy();args[name].loc[pd.Timestamp('2026-10-20'),'AAA']=value
    p=CorePilotEntries(states,args['close'],.5);guard=PilotLiquidation(states,p)
    with patch.object(native,'GlobalLiquidation',lambda *a:guard):
        result=BacktestEngine(cfg).run(**args,winner_entry_risk_policy=p,winner_selection_source=p.select)
    assert len(result.closed_trades_df)==1
    assert result.closed_trades_df.iloc[0].exit_reason=='STOP_GAP'
    assert guard.events[0]['quantities'].get('AAA',0)==0
    assert not result.tracker_snapshot['winner_replay']['open_positions']
