"""Mixed native LONG / isolated SHORT integration and capital parity."""
from dataclasses import replace
from datetime import date,datetime,UTC
from types import SimpleNamespace

import pandas as pd
import pytest

from backtesting.simulator import BacktestEngine
from backtesting.winner_intraday import MemoryCampaignStore
from backtesting.winner_short import reapprove_short
from backtesting.winner_short_broker import ShortReplayBroker
from backtesting.winner_short_ports import stage,ReplayCoordinator,close_campaign
from common.market_calendar import get_market_calendar
from execution_engine.models import ExecutionTarget
from execution_engine.winner_risk import reapprove_campaign
from execution_engine.winner_runtime import WinnerCampaignRuntime
from risk_management.circuit_breaker import CircuitBreaker
from tests.test_winner_intraday import fixture

pytestmark=pytest.mark.usefixtures('isolated_winner_config')


def mixed(*,reverse=False,leverage=1.,only_long=False,dispatcher=True):
    cfg,_,_=fixture(symbols=('AAA','BBB'),leverage=leverage,confirmation_bars=0,initial_position_fraction=1.)
    risk=replace(cfg.risk_config,short_selling_enabled=True,correlation_check_enabled=False)
    book=ShortReplayBroker(BacktestEngine(cfg),fee=.0008,borrow_fee_annual=.003)
    store=MemoryCampaignStore();now=datetime(2026,10,19,13,30,tzinfo=UTC)
    book.now=now;book.marks={'AAA':100.,'BBB':100.}
    sides=[('AAA','long' if only_long else 'short'),('BBB','long')]
    if reverse:sides.reverse()
    targets=[ExecutionTarget('risk-'+s,date(2026,10,16),s,30,100.,.75,'Sector'+s,1.,'fixture',None,
        risk_budget_dollars=400.,side=side) for s,side in sides]
    stage(targets,store,cfg.exec_config,now=now,calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False))
    repo=SimpleNamespace(acquire_execution_lock=lambda **kw:True,release_execution_lock=lambda **kw:None)
    breaker=CircuitBreaker(risk)
    def market(state,stamp):
        return dict(bars=[],bid=book.marks[state['symbol']],ask=book.marks[state['symbol']],feed='sip',quote_time=stamp)
    decisions=[]
    def recheck(state,version,quantity,snapshot,stamp,kind):
        current=replace(risk,account_equity=book.equity())
        context=dict(account_id='default',broker_mode='paper',captured_at=stamp,equity=book.equity(),risk_config=current,
            available_buying_power=book.capacity(),positions=[dict(p,quantity=p['qty']) for p in book.positions()],
            pending_entries=book.pending_entries(),sector_map={'AAA':'SectorAAA','BBB':'SectorBBB'},
            circuit_breaker=breaker,allocation_scale=1.,volatility_allocation_scale=1.,cost_reserve_pct=.0008,
            max_spread_bps=50.,return_matrix=pd.DataFrame(),adv_usd=1e9,entry_data_qualified=True,
            regime_qualified=True,concentration_qualified=True,concentration_allowed=True,corporate_actions_qualified=True,
            breaker_qualified=True,entries_allowed=True,replay_observed_price=book.marks[state['symbol']])
        function=reapprove_short if state.get('side')=='short' else reapprove_campaign
        result=function(state,version,quantity,snapshot,stamp,kind,context=context)
        decisions.append((state['symbol'],result));return result
    if dispatcher:result=ReplayCoordinator(store,repo,book,cfg.exec_config,market=market,risk=recheck,now=now).run(store.rows())
    else:result=WinnerCampaignRuntime(store,repo,book,cfg.exec_config,market=market,risk=recheck,now=now).run(store.rows())
    assert result['winner_failures']==0
    return book,store,cfg,decisions


@pytest.mark.parametrize('reverse',[False,True])
def test_mixed_native_risk_preserves_ranking_and_shares_single_capital(reverse):
    book,store,cfg,decisions=mixed(reverse=reverse)
    entries=[e for e in book.events if e['event'] in ('BUY_FILL','SHORT_FILL')]
    assert [e['symbol'] for e in entries]==(['BBB','AAA'] if reverse else ['AAA','BBB'])
    assert sum(e['quantity'] for e in entries)==39
    assert {p['side'] for p in book.positions()}=={'long','short'}
    assert book.gross()<=book.equity() and book.equity()<4000
    assert len(decisions)==2
    assert all(l['stop']>l['entry'] for r in store.rows() if r['state'].get('side')=='short' for l in r['state']['lots'])


def test_mixed_two_x_respects_native_capacity_and_restricted_short_proceeds():
    book,_,_,_=mixed(leverage=2)
    assert 4000<book.gross()<8000
    assert book.gross()<=2*book.equity()
    assert book.financing_balance()<book.cash


def test_long_dispatch_parity_is_exact_events_orders_cash_and_trades():
    native=mixed(only_long=True,dispatcher=False)
    routed=mixed(only_long=True,dispatcher=True)
    for attr in ('events','orders','lots','cash','trades'):
        assert getattr(native[0],attr)==getattr(routed[0],attr)
    assert native[1].records==routed[1].records
    assert native[3]==routed[3]


def test_global_short_cover_uses_remaining_lots_and_preserves_long_position():
    book,store,cfg,_=mixed()
    row=next(r for r in store.rows() if r['state'].get('side')=='short')
    qty=book.positions()[0]['qty'];book.marks['AAA']=110.
    cover=close_campaign(row,store,book,cfg.exec_config,book.now,1)
    assert cover==qty and len(book.positions())==1 and book.positions()[0]['side']=='long'
    assert book.trades[0]['pnl']<0 and book.trades[0]['exit_reason']=='GLOBAL_DRAWDOWN'
    assert book.equity()==pytest.approx(4000-sum(e.get('costs',0) for e in book.events)-qty*10)
