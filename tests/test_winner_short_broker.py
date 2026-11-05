"""Independent short accounting qualification, before wiring the replay."""
from dataclasses import asdict
from datetime import UTC,datetime

import pytest

from backtesting.simulator import BacktestEngine
from backtesting.winner_intraday import ReplayBroker
from backtesting.winner_short_broker import ShortReplayBroker
from common.winner_pyramiding import WinnerPyramidingConfig
from execution_engine.models import IntentRole
from execution_engine.winner_broker import make_intent
from tests.test_winner_intraday import fixture

pytestmark=pytest.mark.usefixtures('isolated_winner_config')


def setup(*,fee=.0008,borrow=.0252):
    cfg,_,_=fixture()
    book=ShortReplayBroker(BacktestEngine(cfg),fee=fee,borrow_fee_annual=borrow)
    book.now=datetime(2026,10,19,14,0,tzinfo=UTC);book.marks={'A':100.,'B':100.}
    state=dict(campaign_id='ws-test',side='short',symbol='A',risk_run_id='risk',exec_run_id='replay',
        broker_mode='paper',policy=asdict(WinnerPyramidingConfig(enabled=True)),lots=[],operations=[])
    return book,state


def enter(book,state,quantity=10,price=100.):
    intent=make_intent(state,'short-entry',quantity=quantity,side='sell',price=price,order_type='limit',tif='ioc')
    book.short_reservations[intent.intent_id]=price
    book.submit(state,intent)
    return intent


def cover(book,state,quantity,reason='TEST'):
    intent=make_intent(state,'cover-'+str(len(book.trades)),quantity=quantity,side='buy',role=IntentRole.EXIT,order_type='market')
    state['operations'].append(dict(key=intent.intent_id,exit_reason=reason))
    book.submit(state,intent)


def test_short_proceeds_are_liability_not_profit_and_cover_reconciles_costs():
    book,state=setup();enter(book,state)
    assert book.cash==pytest.approx(4999.1)
    assert book.equity()==pytest.approx(3999.1)
    assert book.gross()==1000 and book.positions()[0]['side']=='short'
    assert book.borrow_fees==pytest.approx(.1)
    book.marks['A']=90.;cover(book,state,10)
    assert book.trades[0]['pnl']==pytest.approx(100-.8-.72-.1)
    assert book.cash==book.equity()==pytest.approx(4098.38)
    assert book.gross()==0 and not book.positions()


def test_partial_cover_prorates_entry_cost_borrow_and_remaining_liability():
    book,state=setup();enter(book,state)
    book.marks['A']=90.;cover(book,state,4)
    assert book.positions()[0]['qty']==6
    cover(book,state,6)
    assert sum(t['pnl'] for t in book.trades)==pytest.approx(book.equity()-4000)
    assert sum(t['borrow_fees'] for t in book.trades)==pytest.approx(.1)


def test_shared_long_short_cash_and_gross_do_not_create_extra_capacity():
    book,state=setup(borrow=0)
    long=dict(state,side='long',symbol='B',campaign_id='long')
    intent=make_intent(long,'long-entry',quantity=20,price=100.,order_type='limit',tif='ioc')
    book.submit(long,intent)
    enter(book,state,quantity=30)
    assert book.orders[next(k for k,r in book.orders.items() if r.get('short_entry'))]['status']=='canceled'
    assert book.gross()==2000
    assert len(book.positions())==1 and book.positions()[0]['side']=='long'


def test_unfavorable_short_gap_or_over_reservation_cancels_entry():
    book,state=setup();book.marks['A']=102.
    intent=enter(book,state,price=100.)
    assert book.orders[intent.intent_id]['status']=='canceled'
    assert not book.positions() and book.borrow_fees==0
    book,state=setup();book.marks['A']=99.
    enter(book,state,price=100.)
    assert not book.positions()  # Sell limit is a minimum, not a buy ceiling.


def test_short_stop_tp_collision_adverse_first_and_gap_unlimited_loss():
    book,state=setup(borrow=0);parent=enter(book,state)
    stop=make_intent(state,'stop',quantity=10,side='buy',role=IntentRole.INITIAL_STOP,order_type='stop',stop=105.)
    tp=make_intent(state,'tp',quantity=10,side='buy',role=IntentRole.TAKE_PROFIT,order_type='limit',price=80.)
    book.protect(state,{},parent,tp_intent=tp,stop_intent=stop)
    book.resolve({'A':dict(open=100.,high=110.,low=70.)},opening=False)
    assert book.trades[0]['exit_price']==105 and book.trades[0]['exit_reason']=='STOP'
    assert book.orders[tp.intent_id]['status']=='canceled'
    book,state=setup(borrow=0);parent=enter(book,state)
    stop=make_intent(state,'stop',quantity=10,side='buy',role=IntentRole.INITIAL_STOP,order_type='stop',stop=105.)
    book.protect(state,{},parent,tp_intent=None,stop_intent=stop)
    book.resolve({'A':dict(open=250.,high=251.,low=249.)},opening=True)
    assert book.trades[0]['exit_price']==250 and book.trades[0]['pnl'] < -1500


def test_short_dividend_is_expense_and_borrow_charged_once_each_session():
    book,state=setup();enter(book,state)
    day=book.now.date();book.charge_borrow(day)
    assert book.borrow_fees==pytest.approx(.1)
    book.corporate_action(dict(symbol='A',ca_type='cash_dividend',ex_date=day,
        payable_date='2026-10-20',amount_per_share=1.,currency='USD'),day)
    assert book.equity()==pytest.approx(3989.1)
    book.settle(datetime(2026,10,20).date())
    assert not book.claims and book.cash==pytest.approx(4989.1)
    book.marks['A']=100.;cover(book,state,10)
    assert book.trades[0]['dividends']==-10
    assert book.equity()-4000==pytest.approx(book.trades[0]['pnl'])


def test_long_book_unchanged_when_short_adapter_delegates_long_events():
    cfg,_,_=fixture();engine=BacktestEngine(cfg)
    books=[ReplayBroker(engine,fee=.0008),ShortReplayBroker(engine,fee=.0008,borrow_fee_annual=0)]
    for book in books:
        book.now=datetime(2026,10,19,14,0,tzinfo=UTC);book.marks={'A':100.}
        state=dict(campaign_id='long',side='long',symbol='A',risk_run_id='risk',exec_run_id='replay',
            broker_mode='paper',policy=asdict(WinnerPyramidingConfig(enabled=True)),lots=[],operations=[])
        parent=make_intent(state,'long-entry',quantity=10,price=100.,order_type='limit',tif='ioc')
        book.submit(state,parent)
        stop=make_intent(state,'stop',quantity=10,side='sell',role=IntentRole.INITIAL_STOP,order_type='stop',stop=95.)
        book.protect(state,{},parent,tp_intent=None,stop_intent=stop)
        book.resolve({'A':dict(open=100.,high=102.,low=94.)},opening=False)
    assert books[0].trades==books[1].trades
    assert books[0].events==books[1].events
    assert books[0].equity()==books[1].equity()
