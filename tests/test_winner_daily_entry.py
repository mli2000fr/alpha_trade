"""Daily-open admission, portfolio constraints and intraday protection lifecycle."""
from dataclasses import replace
from datetime import UTC,date,datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from backtesting.simulator import BacktestEngine
from backtesting.winner_intraday import MemoryCampaignStore,ReplayBroker
from backtesting.winner_daily_entry import enter_daily_candidates,approve_daily_open
from common.market_calendar import get_market_calendar
from risk_management.circuit_breaker import CircuitBreaker
from tests.test_winner_intraday import fixture

pytestmark=pytest.mark.usefixtures('isolated_winner_config')


def port(*,symbols=('AAA',),daily_price=99.5,raw_price=100.,permitted=True,risk_changes=None):
    cfg,args,_=fixture(symbols=symbols,confirmation_bars=2,initial_position_fraction=1.)
    risk=replace(cfg.risk_config,correlation_check_enabled=False,**(risk_changes or {}))
    book=ReplayBroker(BacktestEngine(cfg),fee=.0008);store=MemoryCampaignStore()
    opening=datetime(2026,10,19,13,30,tzinfo=UTC);book.now=opening;book.marks={s:raw_price for s in symbols}
    repo=SimpleNamespace(acquire_execution_lock=lambda **kw:True,release_execution_lock=lambda **kw:None)
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    sectors={s:'Sector'+s for s in symbols};audits=[];gaps=set();decisions=[]
    breaker=CircuitBreaker(risk)
    def recheck(state,version,quantity,snapshot,now,kind):
        assert kind=='DAILY_ENTRY'
        ctx=dict(account_id='default',broker_mode='paper',captured_at=now,equity=book.equity(),
            risk_config=replace(risk,account_equity=book.equity()),available_buying_power=book.capacity(),
            positions=[dict(p,quantity=p['qty']) for p in book.positions()],pending_entries=book.pending_entries(),
            sector_map=sectors,circuit_breaker=breaker,allocation_scale=1.,volatility_allocation_scale=1.,
            cost_reserve_pct=.0008,return_matrix=pd.DataFrame(),adv_usd=1e9,entry_data_qualified=True,
            regime_qualified=True,concentration_qualified=True,concentration_allowed=permitted,
            corporate_actions_qualified=True,breaker_qualified=True,entries_allowed=True)
        result=approve_daily_open(state,version,quantity,snapshot,now,context=ctx)
        decisions.append(result);return result
    kwargs=dict(signal_day=date(2026,10,16),day=date(2026,10,19),opening=opening,
        open_df=pd.DataFrame({s:[daily_price] for s in symbols},index=pd.to_datetime(['2026-10-19'])),
        book=book,store=store,repo=repo,
        execution=cfg.exec_config,risk_config=risk,recheck=recheck,calendar=cal,coverage=gaps,audit=audits,sector_map=sectors)
    rows=pd.DataFrame([dict(symbol=s,rank=i+1) for i,s in enumerate(symbols)])
    enter_daily_candidates(rows,**kwargs)
    return book,store,decisions,gaps,audits,rows,kwargs


def test_fill_uses_daily_open_at_official_open_not_raw_5m_price_or_confirmation():
    book,store,decisions,*_=port()
    fill=next(e for e in book.events if e['event']=='BUY_FILL')
    assert fill['time']==pd.Timestamp('2026-10-19T13:30Z') and fill['price']==99.5
    assert fill['execution_proxy']=='DAILY_SESSION_OPEN'
    assert decisions[0]['price_source']=='CANONICAL_DAILY_OPEN'
    state=next(iter(store.records.values()))['state'];lot=state['lots'][0]
    assert state['daily_entry_mode'] and state['initial_attempted']
    assert lot['entry']==99.5 and lot['stop_order_id']
    # The prior session's 5m tape was never requested by this port.
    assert book.marks['AAA']==100.


def test_ranked_entries_share_cash_and_preserve_native_position_cap():
    book,_,_,_,_,_,_=port(symbols=('AAA','BBB'),risk_changes={'max_positions':1,'max_long_positions':1})
    assert [e['symbol'] for e in book.events if e['event']=='BUY_FILL']==['AAA']
    assert book.gross()<4000 and book.cash>0


@pytest.mark.parametrize('price',[float('nan'),-1.])
def test_missing_daily_open_is_not_fabricated(price):
    book,_,_,gaps,*_=port(daily_price=price)
    assert not book.positions() and gaps


def test_native_concentration_veto_and_duplicate_holding_are_kept():
    book,_,_,_,audit,*_=port(permitted=False)
    assert not book.positions() and any('concentration_allowed' in r['reason'] for r in audit)
    book,store,_,_,audit,rows,kwargs=port()
    enter_daily_candidates(rows,**kwargs)
    assert len(book.lots)==1 and any('ALREADY_HELD' in r['reason'] for r in audit)


def test_no_later_day_or_later_5m_retry_and_intraday_stop_remains_real():
    book,_,_,_,_,rows,kwargs=port()
    with pytest.raises(ValueError,match='J\+1'):
        enter_daily_candidates(rows,**dict(kwargs,day=date(2026,10,20)))
    with pytest.raises(ValueError,match='official|Official'):
        enter_daily_candidates(rows,**dict(kwargs,opening=datetime(2026,10,19,13,35,tzinfo=UTC)))
    book.now=datetime(2026,10,19,13,35,tzinfo=UTC)
    book.resolve({'AAA':dict(open=90.,high=91.,low=89.)},opening=True)
    assert book.trades[0]['exit_reason']=='STOP_GAP' and book.trades[0]['pnl']<0


def daily_fixture(**policy):
    cfg,args,raw=fixture(initial_position_fraction=1.,**policy)
    cfg.winner_daily_entry_enabled=True
    # Independent daily open, deliberately different from the raw first print.
    args['open_df']=args['open_df'].copy()
    args['open_df'].loc[pd.Timestamp(cfg.start_date),'AAA']=99.5
    prior=args['signals_df'].iloc[0].trade_date
    del raw[prior,'AAA']
    return cfg,args,raw


@pytest.mark.parametrize('delay',[0,930])
def test_full_replay_daily_open_bypasses_confirmation_and_prior_5m_requirement(delay):
    cfg,args,_=daily_fixture(confirmation_bars=2,market_data_delay_seconds=delay)
    result=BacktestEngine(cfg).run(**args)
    buys=result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]
    assert len(buys)==1 and buys.iloc[0].time==pd.Timestamp('2026-10-19T13:30Z')
    assert buys.iloc[0].price==99.5 and buys.iloc[0].execution_proxy=='DAILY_SESSION_OPEN'
    meta=result.tracker_snapshot['winner_replay']
    assert meta['status']=='COMPLETED_EXPLORATORY' and meta['costs']>0
    assert meta['initial_entry']['mode']=='DAILY_OPEN_J_PLUS_1'


def test_daily_native_factor_veto_is_not_bypassed():
    cfg,args,_=daily_fixture(confirmation_bars=2)
    cfg.risk_config=replace(cfg.risk_config,enable_factor_model=True)
    def missing(*unused):raise ValueError('No causal factors')
    result=BacktestEngine(cfg).run(**args,winner_factor_source=missing)
    assert not result.trade_events_df.event.eq('BUY_FILL').any()
    assert result.tracker_snapshot['winner_replay']['status']=='INCOMPLETE_COVERAGE'


def test_daily_initial_stop_is_active_in_the_first_candle():
    cfg,args,raw=daily_fixture(confirmation_bars=2,stop_loss_pct=.05)
    raw[cfg.start_date,'AAA'].loc[0,'low']=90.
    result=BacktestEngine(cfg).run(**args)
    trade=result.closed_trades_df.iloc[0]
    assert trade.entry_price==99.5 and trade.exit_price==94.52 and trade.exit_reason=='STOP'
    assert len(result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')])==1


def test_daily_failed_open_does_not_retry_later_and_horizon_uses_real_fill_date():
    cfg,args,_=daily_fixture(confirmation_bars=2,horizon_sessions=1)
    cfg.exec_config=replace(cfg.exec_config,entry_order_type='limit',limit_price_buffer_bps=-100)
    result=BacktestEngine(cfg).run(**args)
    trade=result.closed_trades_df.iloc[0]
    assert trade.exit_date==pd.Timestamp('2026-10-20T13:30Z') and trade.exit_reason=='HORIZON_OPEN'
    cfg,args,_=daily_fixture(confirmation_bars=2)
    args['open_df'].loc[pd.Timestamp(cfg.start_date),'AAA']=float('nan')
    result=BacktestEngine(cfg).run(**args)
    assert not result.trade_events_df.event.eq('BUY_FILL').any()


def test_daily_flag_round_trip_and_legacy_default():
    from tests.test_winner_backtest_wiring import options
    from ihm.services.backtesting_runner import build_backtesting_command
    from backtesting.winner_campaign_replay import build_parser
    for active in (True,False):
        args=build_parser().parse_args(build_backtesting_command('run',options(winner_daily_entry_enabled=active))[4:])
        assert args.daily_entry is active
    assert build_parser().parse_args(build_backtesting_command('run',options())[4:]).daily_entry is False


def test_daily_coverage_gate_needs_entry_and_holding_but_not_prior_intraday(tmp_path):
    from backtesting.winner_missing_intraday import required_windows
    from backtesting.winner_intraday_recovery import RecoveringIntradaySource
    cfg,args,_=daily_fixture(horizon_sessions=1)
    prior=args['signals_df'].iloc[0].trade_date
    assert required_windows(args['signals_df'],cfg.end_date,cfg.exec_config.winner_pyramiding,
        daily_entry=True)['AAA']==[(cfg.start_date,cfg.end_date)]
    source=RecoveringIntradaySource(lambda *_:pd.DataFrame(),cfg.end_date,cfg.exec_config.winner_pyramiding,
        daily_entry=True,cache_dir=tmp_path)
    source.remaining={('AAA',prior):{}}
    assert source.entry_allowed('AAA',cfg.start_date)
    source._remaining_dates=None;source._entry_cache={};source.remaining={('AAA',cfg.end_date):{}}
    assert source.entry_allowed('AAA',cfg.start_date)  # Even future held-session gaps must never select entries.


@pytest.mark.parametrize('leverage',[1.,2.])
def test_daily_shared_portfolio_capacity_and_costs_not_independent_deposits(leverage):
    cfg,args,_=fixture(symbols=('AAA','BBB','CCC'),leverage=leverage,confirmation_bars=2,
        initial_position_fraction=1.)
    cfg.winner_daily_entry_enabled=True
    args['open_df']=args['open_df']*0+100.
    result=BacktestEngine(cfg).run(**args)
    marks=result.intraday_equity_curve
    assert marks.gross.iloc[0]<=4000*leverage
    assert result.tracker_snapshot['winner_replay']['costs']>0
    if leverage==2.:
        assert marks.gross.iloc[0]>4000 and result.tracker_snapshot['winner_replay']['margin_interest']>0


@pytest.mark.parametrize('delay',[0,930])
def test_daily_initial_entry_keeps_optional_winner_add_confirmation(delay):
    cfg,args,_=fixture(confirmation_bars=2,initial_position_fraction=.5,
        reinforcement_enabled=True,reinforcement_trigger_pct=.01,market_data_delay_seconds=delay)
    cfg.winner_daily_entry_enabled=True
    args['open_df']=args['open_df']*0+100.
    result=BacktestEngine(cfg).run(**args)
    buys=result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]
    assert len(buys)==2 and buys.iloc[0].time==pd.Timestamp('2026-10-19T13:30Z')
    assert buys.iloc[1].time>pd.Timestamp('2026-10-19T13:40Z')
