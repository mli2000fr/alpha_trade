from dataclasses import replace
import numpy as np
import pandas as pd
import pytest

from backtesting.research_intraday_native import IntradayNativeLedger
from risk_management.models import PriceInfo
from scripts.research.us_intraday_protection_grid import GridLedger,cases,case_key,metrics
from scripts.research.us_intraday_protection_grid_audit import scalar_exit


def calendar():
    return pd.DataFrame([dict(date=pd.Timestamp(d),market_open=pd.Timestamp(d+' 14:30Z'),
        market_close=pd.Timestamp(d+' 14:45Z')) for d in ['2025-01-02','2025-01-03','2025-01-06']])


def enter(l,side='buy',symbol='ABC'):
    l.entry_context=dict(pair_id=1,oracle_date=l.day,rank=1,expiry=pd.Timestamp('2025-01-06 14:40Z'))
    return l.enter(symbol,side,PriceInfo(symbol,100.,2.,price_asof_date=l.day.date(),
        atr_asof_date=pd.Timestamp('2025-01-01').date(),adv_usd=1e8),
        sector='RESEARCH_NO_SECTOR_CAP',signal_time=l.now,quantity_fraction=.5)


def start(l,price=100.):
    l.bar_number=0
    l.begin_bar(pd.Timestamp('2025-01-02 14:30Z'),{'ABC':price})


def test_grid_complete_unique_and_symmetric():
    cs=cases()
    assert len(cs)==576 and len({case_key(c) for c in cs})==576
    for y in (2025,2026):
        for side in ('buy','sell'):assert sum(c['year']==y and c['side']==side for c in cs)==144


@pytest.mark.parametrize('side',['buy','sell'])
def test_leverage_is_real_buying_power_not_double_pnl(side):
    l=GridLedger(calendar(),sl=.05,trailing=None)
    start(l)
    assert l.engine._resolve_margin_buying_power_multiplier(4000)==2
    assert l.buying_power()==8000
    assert enter(l,side)
    assert l.state.positions['ABC'].quantity==10
    assert l.gross()==1000
    assert l.buying_power()==pytest.approx(2*l.equity()-1000)
    assert l.equity()==pytest.approx(3999.2)
    assert l.equity()==pytest.approx(IntradayNativeLedger.equity(l))
    assert l.gross()==pytest.approx(IntradayNativeLedger.gross(l))


def test_leverage_reaches_over_one_and_stays_within_two_at_entry():
    l=GridLedger(calendar(),sl=.05,trailing=None)
    symbols=[f'A{i}' for i in range(8)]
    l.begin_bar(pd.Timestamp('2025-01-02 14:30Z'),{s:100. for s in symbols})
    for s in symbols:enter(l,symbol=s)
    assert 1<l.gross()/l.equity()<=2
    assert l.state.settled_cash<0


def test_no_leverage_below_minimum_equity():
    l=GridLedger(calendar(),sl=.05,trailing=None)
    l.state.settled_cash=1900
    start(l)
    assert l.buying_power()==1900
    assert not enter(l,'sell')


@pytest.mark.parametrize('side,op,target',[('buy',130.,120.),('sell',70.,80.)])
def test_expiry_favourable_gap_capped_at_standing_tp(side,op,target):
    l=GridLedger(calendar(),sl=.05,trailing=None,tp=.2)
    start(l);assert enter(l,side)
    l.observe_bar({'ABC':[100,100,100,100]})
    l.bar_number=1
    l.begin_bar(pd.Timestamp('2025-01-02 14:35Z'),{'ABC':op},expiry_symbols={'ABC'})
    l.resolve_open()
    assert l.state.closed_trades[-1]['exit_price']==target
    assert l.state.closed_trades[-1]['exit_reason']=='TP_GAP_LIMIT'


def test_prior_high_not_used_for_same_bar_trailing():
    l=GridLedger(calendar(),sl=.05,trailing=.1)
    start(l);assert enter(l)
    l.observe_bar({'ABC':[100.,120.,96.,110.]})
    assert 'ABC' in l.state.positions
    assert l.known_stop('ABC')==108


def test_stop_first_on_tp_sl_collision():
    l=GridLedger(calendar(),sl=.05,trailing=None,tp=.1)
    start(l);assert enter(l)
    l.observe_bar({'ABC':[100.,115.,90.,102.]})
    assert l.state.closed_trades[-1]['exit_price']==95


def test_financing_act360_weekend():
    l=GridLedger(calendar(),sl=.05,trailing=None)
    start(l)
    l.state.settled_cash=-1000
    for i in range(3):
        if i:l.begin_bar(pd.Timestamp('2025-01-02 14:30Z')+pd.Timedelta(minutes=5*i),{'ABC':100.})
        l.observe_bar({'ABC':[100.,100.,100.,100.]})
    l.finish_day()
    assert l.interest==pytest.approx(1000*.065/360)
    for i in range(3):
        l.begin_bar(pd.Timestamp('2025-01-03 14:30Z')+pd.Timedelta(minutes=5*i),{'ABC':100.})
        l.observe_bar({'ABC':[100.,100.,100.,100.]})
    debit=-l.state.settled_cash
    l.finish_day()
    assert l.margin_log[-1]['interest']==pytest.approx(debit*.065*3/360)


def test_entry_after_multiple_daily_sessions_has_native_calendar_alignment():
    l=GridLedger(calendar(),sl=.05,trailing=None)
    for d in ['2025-01-02','2025-01-03']:
        for i in range(3):
            l.begin_bar(pd.Timestamp(d+' 14:30Z')+pd.Timedelta(minutes=5*i),{'ABC':100.})
            l.observe_bar({'ABC':[100.,100.,100.,100.]})
        l.finish_day()
    l.begin_bar(pd.Timestamp('2025-01-06 14:30Z'),{'ABC':100.})
    assert enter(l)


def test_duration_and_net_pnl_metadata():
    l=GridLedger(calendar(),sl=.05,trailing=None)
    start(l);assert enter(l)
    t=l.close('ABC',110.,'TEST')
    assert t['holding_sessions']==1 and t['holding_calendar_days']==0
    assert t['net_return_pct']==pytest.approx(9.832)


def test_metrics_include_requested_allocation_and_holding_stats():
    marks=pd.DataFrame(dict(equity=[4000.,4400.,3960.],gross=[0.,6000.,4000.]))
    trades=pd.DataFrame(dict(pnl=[200.,-100.],net_return_pct=[20.,-10.],
        holding_sessions=[5,3],holding_calendar_days=[7.,4.]))
    m=metrics(marks,trades,[])
    assert m['max_drawdown_pct']==pytest.approx(10.)
    assert m['win_rate_pct']==50
    assert m['avg_winner_holding_sessions']==5 and m['avg_loser_holding_calendar_days']==4
    assert m['mean_capital_used_usd']==pytest.approx(10000/3)
    assert m['max_observed_leverage']==pytest.approx(6000/4400)


def test_scalar_target_limit_before_expiry():
    path=pd.DataFrame(dict(bar_timestamp=pd.to_datetime(['2025-01-02 14:30Z','2025-01-02 14:35Z']),
        open=[100.,130.],high=[101.,131.],low=[99.,129.],close=[100.,130.]))
    c=dict(side='buy',sl=.05,trailing=None,tp=.2)
    assert scalar_exit(path,0,path.bar_timestamp.iloc[-1],c)==(1,120.,'OPEN')


def test_annual_reset_and_hypotheses_are_explicit():
    a=GridLedger(calendar(),sl=.05,trailing=None)
    b=GridLedger(calendar(),sl=.05,trailing=None)
    a.state.settled_cash=5000
    assert b.equity()==4000
    assert a.engine.config.margin_interest_rate_annual==.065
    assert a.strict is False
