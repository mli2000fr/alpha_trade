import numpy as np
import pandas as pd
import pytest
from scripts.research import multi_asset_trend_backtest as b


def fixture():
    days=pd.bdate_range('2020-01-01','2020-04-15')
    symbols=['A','B','C','D']; rows=[]
    for s in symbols:
        for i,d in enumerate(days):
            rows.append(dict(symbol=s,date=d,open=100+i,close=100+i))
    cfg=dict(symbols=symbols,lookbacks_sessions=[2,3,4],positive_votes_required=2,
        weight_per_active_asset=.25,start='2020-02-03',end='2020-04-15',initial_capital_usd=4000)
    events=pd.DataFrame(columns=['symbol','ex_date','pay_date','amount'])
    return pd.DataFrame(rows),events,cfg


def test_tr_signal_dividend_does_not_make_price_loss():
    c=pd.DataFrame({'A':[100.,90.,90.]},index=pd.date_range('2020-01-01',periods=3))
    d=pd.DataFrame([dict(symbol='A',ex_date=c.index[1],amount=10.)])
    assert b.total_return_signal(c,d).A.tolist()==[1.,1.,1.]


def test_first_next_open_prior_close_monthly_and_no_borrowing():
    p,e,c=fixture();d,o,_,de,a,s=b.simulate(p,e,c,'TREND_2_OF_3',10)
    assert o.fill_date.min()==pd.Timestamp('2020-02-03')
    assert de.decision_date.min()==pd.Timestamp('2020-01-31')
    assert set(de.fill_date.dt.day)=={2,3,1} # Feb3, Mar2, Apr1 (unchanged targets need no trade)
    assert d.cash.min()>=0
    assert np.allclose(d.equity,d.cash+d.market_value+d.receivable)
    assert s['costs_usd']==pytest.approx(o.notional.sum()*.001)
    assert a.iloc[0].initial_capital_usd==4000


def test_future_cannot_change_past_signal_or_quantities():
    p,e,c=fixture();_,o,_,de,_,_=b.simulate(p,e,c,'TREND_2_OF_3',10)
    p.loc[p.date>=pd.Timestamp('2020-03-10'),'close']*=3
    _,o2,_,de2,_,_=b.simulate(p,e,c,'TREND_2_OF_3',10)
    pd.testing.assert_frame_equal(de[de.fill_date<'2020-03-10'],de2[de2.fill_date<'2020-03-10'])
    pd.testing.assert_frame_equal(o[o.fill_date<'2020-03-10'],o2[o2.fill_date<'2020-03-10'])


def test_open_gap_cash_clip_not_lookahead_sizing():
    p,e,c=fixture();_,_,_,de,_,_=b.simulate(p,e,c,'TREND_2_OF_3',10)
    p.loc[p.date.eq(pd.Timestamp(c['start'])),'open']*=2
    d,o,_,de2,_,_=b.simulate(p,e,c,'TREND_2_OF_3',10)
    assert (o[o.fill_date.eq(pd.Timestamp(c['start']))].cash_clip_scale<.51).all()
    assert np.allclose(de2[de2.fill_date.eq(pd.Timestamp(c['start']))].target_quantity,
        de[de.fill_date.eq(pd.Timestamp(c['start']))].target_quantity)
    assert d.cash.min()>=0


def test_exdate_buyer_no_entitlement_payment_not_immediate_unpaid_final_nav():
    p,e,c=fixture()
    e=pd.DataFrame([dict(symbol='A',ex_date=pd.Timestamp(c['start']),pay_date=pd.Timestamp('2020-02-10'),amount=5.),
        dict(symbol='A',ex_date=pd.Timestamp('2020-02-04'),pay_date=pd.Timestamp('2020-02-10'),amount=5.),
        dict(symbol='A',ex_date=pd.Timestamp('2020-04-14'),pay_date=pd.Timestamp('2020-05-01'),amount=5.)])
    d,o,claims,_,_,s=b.simulate(p,e,c,'EQUAL_WEIGHT_BUY_AND_HOLD',0)
    assert len(claims)==2
    assert d[d.date.eq(pd.Timestamp('2020-02-04'))].dividends_paid.iloc[0]==0
    assert d[d.date.eq(pd.Timestamp('2020-02-04'))].receivable.iloc[0]>0
    assert d[d.date.eq(pd.Timestamp('2020-02-10'))].dividends_paid.iloc[0]>0
    assert s['final_receivables_usd']>0
    assert len(o)==4


def test_exdate_seller_keeps_claim_cash_received_only_at_payment():
    p,e,c=fixture()
    # All trends turn down BEFORE the March decision; A pays on exit day.
    p.loc[p.date>=pd.Timestamp('2020-02-20'),'close']=50.
    e=pd.DataFrame([dict(symbol='A',ex_date=pd.Timestamp('2020-03-02'),pay_date=pd.Timestamp('2020-03-06'),amount=2.)])
    d,o,claims,_,_,_=b.simulate(p,e,c,'TREND_2_OF_3',10)
    assert len(claims)==1 and claims.iloc[0].amount>0
    assert 'SELL' in o[o.fill_date.eq(pd.Timestamp('2020-03-02'))].side.tolist()
    assert d[d.date.eq(pd.Timestamp('2020-03-02'))].quantity_A.iloc[0]==pytest.approx(0.)
    assert d[d.date.eq(pd.Timestamp('2020-03-06'))].dividends_paid.iloc[0]==pytest.approx(claims.iloc[0].amount)


def test_insufficient_history_no_silent_cash_fallback():
    p,e,c=fixture();c['lookbacks_sessions']=[63,126,252]
    with pytest.raises(ValueError,match='warmup'):b.simulate(p,e,c,'TREND_2_OF_3',10)


def test_benchmarks_same_initial_cost_dividend_rules_not_free():
    p,e,c=fixture()
    for strategy in b.STRATEGIES:
        d,o,_,_,_,s=b.simulate(p,e,c,strategy,10)
        assert o.cost.sum()>0
        assert (o.cost/o.notional).to_numpy()==pytest.approx(np.full(len(o),.001))
        assert d.iloc[0].equity==pytest.approx(4000-o[o.fill_date.eq(d.date.iloc[0])].cost.sum())
        assert s['max_drawdown_pct']<0 # first fee counts against initial NAV


def test_drawdown_includes_starting_nav():
    assert b.drawdown([90,95],100)==pytest.approx(-10)


def test_annual_carry_nav_and_partial_year():
    p,e,c=fixture()
    dates=sorted(p.date.unique());mapping=dict(zip(dates,pd.bdate_range('2020-11-01',periods=len(dates))))
    p['date']=p.date.map(mapping)
    c.update(start='2020-12-03',end='2021-02-15')
    d,_,_,_,a,_=b.simulate(p,e,c,'EQUAL_WEIGHT_MONTHLY',10)
    assert a.year.tolist()==[2020,2021]
    assert a.iloc[1].initial_capital_usd==pytest.approx(d[d.date.dt.year.eq(2020)].equity.iloc[-1])
    assert a.iloc[1].partial_year
