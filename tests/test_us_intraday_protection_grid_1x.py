from dataclasses import asdict

import pandas as pd
import pytest

from backtesting.research_intraday_native import IntradayNativeLedger
from risk_management.models import PriceInfo
from scripts.research import us_intraday_protection_grid as two
from scripts.research.us_intraday_protection_grid_1x import OneXGridLedger,risk_config,execution_config,prepare,TWO_X


def calendar():
    return pd.DataFrame([dict(date=pd.Timestamp('2025-01-02'),market_open=pd.Timestamp('2025-01-02 14:30Z'),
        market_close=pd.Timestamp('2025-01-02 14:45Z'))])


def entry(l,s,side='buy'):
    l.entry_context=dict(pair_id=1,oracle_date=l.day,rank=1,expiry=pd.Timestamp('2025-01-02 14:40Z'))
    return l.enter(s,side,PriceInfo(s,100.,2.,price_asof_date=l.day.date(),atr_asof_date=pd.Timestamp('2025-01-01').date(),adv_usd=1e8),
        sector='RESEARCH_NO_SECTOR_CAP',signal_time=l.now,quantity_fraction=.5)


def test_only_gross_limit_changes_in_risk():
    a,b=asdict(two.risk_config()),asdict(risk_config())
    assert {k for k in a if a[k]!=b[k]}=={'max_gross_exposure'}
    assert b['max_gross_exposure']==1
    assert b['max_position_weight']==.5 and b['risk_per_trade_pct']==.04


def test_execution_disabled_not_cash_account_short():
    e=execution_config()
    assert e.account_type=='margin' and e.leverage.enabled is False
    assert e.leverage.max_leverage==1 and e.simulated_margin_buying_power_multiplier==1


@pytest.mark.parametrize('side',['buy','sell'])
def test_true_one_x_budget_preserves_first_target(side):
    l=OneXGridLedger(calendar(),sl=.07,trailing=.15)
    l.begin_bar(pd.Timestamp('2025-01-02 14:30Z'),{'ABC':100.})
    assert l.buying_power()==4000
    assert entry(l,'ABC',side)
    assert l.state.positions['ABC'].quantity==10  # same first target as2x, NOT automatically half again
    assert l.buying_power()==pytest.approx(l.equity()-1000)
    assert l.equity()==pytest.approx(IntradayNativeLedger.equity(l))
    assert l.audit[-1]['max_entry_leverage']==1


@pytest.mark.parametrize('side',['buy','sell'])
def test_eight_orders_cannot_borrow_capital(side):
    l=OneXGridLedger(calendar(),sl=.05,trailing=None)
    symbols=[f'A{i}' for i in range(8)]
    l.begin_bar(pd.Timestamp('2025-01-02 14:30Z'),{s:100. for s in symbols})
    for s in symbols:
        entry(l,s,side)
        assert l.gross()<=l.equity()+1e-8
    assert l.state.settled_cash>=0
    assert l.gross()<4000


def test_no_margin_interest_for_funded_long():
    l=OneXGridLedger(calendar(),sl=.05,trailing=None)
    l.begin_bar(pd.Timestamp('2025-01-02 14:30Z'),{'ABC':100.})
    entry(l,'ABC')
    for i in range(3):
        if i:l.begin_bar(pd.Timestamp('2025-01-02 14:30Z')+pd.Timedelta(minutes=5*i),{'ABC':100.})
        l.observe_bar({'ABC':[100.,100.,100.,100.]})
    l.finish_day()
    assert l.interest==0


def test_stops_targets_costs_unchanged():
    a=two.GridLedger(calendar(),sl=.07,trailing=.15,tp=.2)
    b=OneXGridLedger(calendar(),sl=.07,trailing=.15,tp=.2)
    for l in (a,b):
        l.begin_bar(pd.Timestamp('2025-01-02 14:30Z'),{'ABC':100.})
        entry(l,'ABC')
        l.observe_bar({'ABC':[100.,125.,90.,100.]})
    assert a.state.closed_trades[0]['pnl']==b.state.closed_trades[0]['pnl']
    assert a.state.closed_trades[0]['exit_price']==b.state.closed_trades[0]['exit_price']==93


def test_cannot_overwrite_two_x_run():
    with pytest.raises(ValueError,match='Never overwrite'):prepare(TWO_X)
