import pandas as pd
import pytest
from scripts.research import us_cash_merger_economic_pilot as s


def fixture():
    bars=pd.DataFrame([dict(symbol='X',date=pd.Timestamp(d),o=o,c=c) for d,o,c in [('2024-01-26',10.,10.),('2024-01-29',10.,11.)]])
    events=[dict(symbol='X',sec_legal_closing='2024-01-30',provider_payable_date='2024-02-01',cash_per_share_usd=11.)]
    config=dict(start='2024-01-26',end='2024-02-01',initial_capital_usd=4000.,slot_weight=.2,commission_per_buy_usd=1.,cash_action_fee_usd=0.)
    scenario=dict(name='TEST',cash_yield=0.,entry_bps=10,payment_delay_sessions=0)
    return bars,events,config,scenario


def test_single_economic_payment_and_commission_friction_no_exit_spread():
    b,e,c,p=fixture();d,t,f,r=s.simulate(b,e,c,p)
    assert len(t)==1 and r['proxy_cash_payments']==1
    assert t.quantity.iloc[0]==pytest.approx((800-1)/1.001/10)
    assert r['portfolio_profit_usd']==pytest.approx(t.net_trade_profit_usd.iloc[0])
    assert r['total_entry_costs_usd']>1
    assert r['winning_trades']==1 and r['losing_trades']==0
    assert (d.cash>=0).all() and (d.market_value<=d.equity).all()


def test_receivable_not_immediate_cash_weekend_mark_not_fill():
    b,e,c,p=fixture();d,_,_,_=s.simulate(b,e,c,p)
    x=d.set_index('date')
    assert x.loc['2024-01-30','market_value']==0 and x.loc['2024-01-30','receivable']>0
    assert x.loc['2024-01-30','cash']==pytest.approx(3200)
    assert x.loc['2024-01-27','market_value']==x.loc['2024-01-26','market_value']


def test_credit_delay_after_horizon_remains_receivable_not_fictitious_sale():
    b,e,c,p=fixture();p['payment_delay_sessions']=5
    d,t,f,r=s.simulate(b,e,c,p)
    assert r['proxy_cash_payments']==0 and r['final_receivables_usd']>0
    assert d.cash.iloc[-1]==pytest.approx(3200)


def test_missing_payment_or_missing_session_blocks_not_drops():
    b,e,c,p=fixture();e[0]['provider_payable_date']=None
    with pytest.raises(ValueError,match='Missing provider'):s.simulate(b,e,c,p)
    b,e,c,p=fixture()
    with pytest.raises(ValueError,match='Missing held'):s.simulate(b.iloc[:1],e,c,p)


def test_duplicate_economic_event_rejected_even_if_provider_ids_differ():
    b,e,c,p=fixture()
    with pytest.raises(ValueError,match='One economic'):s.simulate(b,e+e,c,p)


def test_fees_can_make_completed_deal_losing_no_success_equals_win():
    b,e,c,p=fixture();e[0]['cash_per_share_usd']=10.
    d,t,f,r=s.simulate(b,e,c,p)
    assert r['winning_trades']==0 and r['losing_trades']==1 and r['portfolio_profit_usd']<0


def test_cash_interest_same_reference_no_fake_outperformance():
    b,e,c,p=fixture();p['cash_yield']=.04
    d,t,f,r=s.simulate(b,e,c,p)
    expected=4000*(1.04**(len(d)/365))
    assert r['cash_benchmark_final_usd']==pytest.approx(expected)
    assert r['portfolio_profit_usd']==pytest.approx(r['sum_net_trade_profit_usd']+r['cash_interest_usd'])


def test_shift_uses_nyse_sessions_not_two_calendar_days():
    assert s.payment_day('2024-03-28',2)==pd.Timestamp('2024-04-02') # Good Friday/weekend excluded
    with pytest.raises(ValueError):s.payment_day(None,2)


def test_seven_prespecified_sensitivities_not_retuned():
    assert len(s.SCENARIOS)==7 and s.SCENARIOS[0]['name']=='PRIMARY'
    assert s.SCENARIOS[0]['cash_yield']==.04 and s.SCENARIOS[0]['entry_bps']==10
