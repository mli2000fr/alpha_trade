"""Daily-open entries survive missing 5m history without fake intraday evidence."""
from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from backtesting.simulator import BacktestEngine
from tests.test_winner_intraday import fixture

pytestmark=pytest.mark.usefixtures('isolated_winner_config')


def setup(*,symbols=('AAA',),**policy):
    cfg,args,raw=fixture(symbols=symbols,initial_position_fraction=policy.pop('initial_position_fraction',1.),**policy)
    cfg.winner_daily_entry_enabled=True
    cfg.winner_drawdown_controller_enabled=False
    for field,value in [('open_df',100.),('close',100.),('high',101.),('low',99.)]:
        args[field]=args[field]*0+value
    return cfg,args,raw


def set_day(args,day,*,symbol='AAA',op=100.,high=101.,low=99.,close=100.):
    for field,value in [('open_df',op),('high',high),('low',low),('close',close)]:
        args[field].loc[pd.Timestamp(day),symbol]=value


def buys(result):return result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]


def test_no_intraday_at_all_buys_j1_and_horizon_uses_daily_next_open():
    cfg,args,raw=setup(confirmation_bars=2,horizon_sessions=1)
    raw.clear()
    class Source:
        def __call__(self,day,symbols):return pd.DataFrame()
        def entry_allowed(self,*unused):raise AssertionError('Future availability must never filter a daily entry')
    args['intraday_source']=Source()
    result=BacktestEngine(cfg).run(**args)
    assert buys(result).iloc[0].time==pd.Timestamp('2026-10-19T13:30Z')
    assert buys(result).iloc[0].price==100.
    trade=result.closed_trades_df.iloc[0]
    assert trade.exit_date==pd.Timestamp('2026-10-20T13:30Z') and trade.exit_reason=='HORIZON_OPEN'
    assert result.tracker_snapshot['winner_replay']['costs']>0
    assert all('ENTRY_GATE' not in r['reason'] for r in result.tracker_snapshot['winner_replay']['coverage_gaps'])


def test_future_missing_held_bar_does_not_cancel_the_initial_daily_purchase():
    cfg,args,raw=setup(horizon_sessions=1)
    raw[cfg.end_date,'AAA']=raw[cfg.end_date,'AAA'].iloc[1:]
    result=BacktestEngine(cfg).run(**args)
    assert len(buys(result))==1
    assert result.closed_trades_df.iloc[0].exit_date==pd.Timestamp('2026-10-20T13:30Z')
    assert result.tracker_snapshot['winner_replay']['protection_resolution']['fallback_symbol_sessions']==1


def test_complete_intraday_is_preferred_to_inconsistent_daily_extrema():
    cfg,args,raw=setup()
    set_day(args,cfg.start_date,low=90.)
    result=BacktestEngine(cfg).run(**args)
    assert result.closed_trades_df.empty
    assert result.tracker_snapshot['winner_replay']['protection_resolution']['fallback_symbol_sessions']==0


def test_invalid_5m_candle_uses_daily_protection_without_cancelling_entry():
    cfg,args,raw=setup()
    raw[cfg.start_date,'AAA'].loc[2,'volume']=0.
    result=BacktestEngine(cfg).run(**args)
    assert len(buys(result))==1
    assert result.tracker_snapshot['winner_replay']['protection_resolution']['sessions'][0]['reason']=='INVALID_5M_OHLCV'


def test_ambiguous_sql_candles_fall_back_only_for_explicit_daily_mode():
    from sqlalchemy import create_engine
    from backtesting.winner_campaign_replay import SqlIntradaySource
    cfg,_,raw=setup()
    frame=raw[cfg.start_date,'AAA'].copy()
    frame=pd.concat([frame,frame.iloc[:1]],ignore_index=True)
    frame=frame.rename(columns={'timestamp':'bar_timestamp'})
    frame['bar_end_timestamp']=frame.bar_timestamp+pd.Timedelta(minutes=5)
    frame['bar_timestamp']=frame.bar_timestamp.dt.tz_localize(None)
    frame['bar_end_timestamp']=frame.bar_end_timestamp.dt.tz_localize(None)
    for key,value in dict(trade_date=str(cfg.start_date),interval_code='5m',data_source='alpaca_sip',
        provider='alpaca',market_code='US_EQ',session_tag='regular',data_adjustment='raw',is_filled=0,payload_hash='x').items():
        frame[key]=value
    engine=create_engine('sqlite://')
    frame.to_sql('stock_bars_intraday',engine,index=False)
    with engine.connect() as conn:
        assert SqlIntradaySource(conn,discard_unqualified=True,allow_daily_fallback=True)(cfg.start_date,['AAA']).empty
        with pytest.raises(ValueError,match='duplicate'):
            SqlIntradaySource(conn,discard_unqualified=True)(cfg.start_date,['AAA'])


@pytest.mark.parametrize('daily_low,expected,reason',[(90.,95.,'STOP'),(99.,110.,'TP')])
def test_daily_collision_sl_first_and_realized_proceeds_only_at_close(daily_low,expected,reason):
    cfg,args,raw=setup(stop_loss_pct=.05,take_profit_pct=.10)
    raw.clear();set_day(args,cfg.start_date,high=120.,low=daily_low,close=105.)
    result=BacktestEngine(cfg).run(**args)
    trade=result.closed_trades_df.iloc[0]
    assert trade.exit_price==expected and trade.exit_reason==reason
    assert trade.exit_date==pd.Timestamp('2026-10-19T20:00Z')
    sale=result.trade_events_df.loc[result.trade_events_df.event.eq('SELL_FILL')].iloc[0]
    assert sale.execution_proxy=='DAILY_OHLC_CLOSE_BOUND' and not sale.exact_intraday_time_known


def test_daily_gap_executes_at_open_not_at_a_guaranteed_stop_price():
    cfg,args,raw=setup(stop_loss_pct=.05)
    raw.clear();set_day(args,cfg.end_date,op=80.,high=90.,low=79.,close=85.)
    result=BacktestEngine(cfg).run(**args)
    trade=result.closed_trades_df.iloc[0]
    assert trade.exit_price==80. and trade.exit_reason=='STOP_GAP'
    assert trade.exit_date==pd.Timestamp('2026-10-20T13:30Z')


def test_incompatible_raw_prices_fall_back_instead_of_excluding_daily_entry():
    cfg,args,raw=setup()
    for field,delta in [('open_df',0.),('close',0.),('high',1.),('low',-1.)]:
        args[field]=args[field]*0+50.+delta
    result=BacktestEngine(cfg).run(**args)
    assert buys(result).iloc[0].price==50.
    meta=result.tracker_snapshot['winner_replay']
    assert meta['open_positions'][0]['mark']==50.
    assert {r['reason'] for r in meta['protection_resolution']['sessions']}=={'DAILY_RAW_PRICE_BASIS_MISMATCH'}


def test_daily_high_cannot_tighten_its_own_earlier_low_then_returns_to_real_intraday():
    cfg,args,raw=setup(stop_loss_pct=.05)
    cfg.exec_config=replace(cfg.exec_config,winner_pyramiding=replace(cfg.exec_config.winner_pyramiding,trailing_stop_pct=.15))
    del raw[cfg.start_date,'AAA']
    set_day(args,cfg.start_date,high=130.,low=99.,close=125.)
    set_day(args,cfg.end_date,op=108.,high=109.,low=107.,close=108.)
    g=raw[cfg.end_date,'AAA']
    g.loc[:,['open','high','low','close']]=[108.,108.1,107.9,108.]
    result=BacktestEngine(cfg).run(**args)
    trade=result.closed_trades_df.iloc[0]
    assert trade.exit_date==pd.Timestamp('2026-10-20T13:30Z') and trade.exit_price==108.
    updates=result.trade_events_df.loc[result.trade_events_df.event.eq('DAILY_TRAILING_UPDATE')]
    assert updates.iloc[0].time==pd.Timestamp('2026-10-19T20:00Z')
    assert updates.iloc[0].stop==110.5
    assert result.tracker_snapshot['winner_replay']['protection_resolution']['fallback_symbol_sessions']==1


def test_no_fake_confirmation_from_daily_high_for_reinforcement():
    cfg,args,raw=setup(initial_position_fraction=.5,reinforcement_enabled=True,
        reinforcement_trigger_pct=.01,confirmation_bars=2)
    del raw[cfg.start_date,'AAA']
    set_day(args,cfg.start_date,high=120.,low=99.,close=102.)
    result=BacktestEngine(cfg).run(**args)
    b=buys(result)
    assert len(b)==2 and b.iloc[1].time.date()==cfg.end_date
    assert b.iloc[1].time>pd.Timestamp('2026-10-20T13:40Z')


def test_missing_daily_and_intraday_for_held_fails_after_real_initial_entry(monkeypatch):
    from backtesting.winner_intraday import ReplayBroker
    filled=[];original=ReplayBroker.fill_buy
    def spy(self,*args,**kwargs):
        result=original(self,*args,**kwargs);filled.extend(self.positions());return result
    monkeypatch.setattr(ReplayBroker,'fill_buy',spy)
    cfg,args,raw=setup()
    raw.clear();args['low'].loc[pd.Timestamp(cfg.end_date),'AAA']=float('nan')
    with pytest.raises(ValueError,match='Missing/invalid daily protection OHLC'):
        BacktestEngine(cfg).run(**args)
    assert filled


def test_native_risk_and_cash_still_block_entries_without_5m():
    cfg,args,raw=setup(symbols=('AAA','BBB','CCC'))
    raw.clear();cfg.risk_config=replace(cfg.risk_config,max_positions=1,max_long_positions=1,
        correlation_check_enabled=False)
    result=BacktestEngine(cfg).run(**args)
    assert buys(result).symbol.tolist()==['AAA']
    assert result.intraday_equity_curve.gross.max()<=4000.


def test_dd_liquidation_never_sells_daily_fallback_at_a_stale_midday_price():
    cfg,args,raw=setup(symbols=('AAA','BBB'),stop_loss_pct=.05)
    cfg.winner_drawdown_controller_enabled=True
    cfg.risk_config=replace(cfg.risk_config,max_portfolio_drawdown_pct=.02,max_daily_loss_pct=.9,
        force_close_on_breaker=True,force_close_pct=1.,max_position_weight=.4,correlation_check_enabled=False)
    del raw[cfg.start_date,'AAA'];del raw[cfg.end_date,'AAA']
    raw[cfg.start_date,'BBB'].loc[2,'low']=90.
    set_day(args,cfg.end_date,op=98.,high=100.,low=97.,close=99.)
    result=BacktestEngine(cfg).run(**args)
    assert len(buys(result))==2,result.trade_events_df.to_dict('records')
    trades=result.closed_trades_df
    aaa=trades.loc[trades.symbol.eq('AAA')].iloc[0]
    assert aaa.exit_reason=='GLOBAL_DRAWDOWN' and aaa.exit_price==98.
    assert aaa.exit_date==pd.Timestamp('2026-10-20T13:30Z')
    assert result.tracker_snapshot['winner_replay']['global_liquidation']['events']
