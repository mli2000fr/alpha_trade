"""Optional automatic exclusions are explicit post-hoc screens; strict is default."""
from datetime import date,timedelta
import logging

import pandas as pd
import pytest
from sqlalchemy import create_engine,event

from backtesting.winner_missing_intraday import required_windows,classify_missing,screen_missing_intraday,log_missing_summary
from common.winner_pyramiding import WinnerPyramidingConfig,regular_bounds

pytestmark=pytest.mark.usefixtures('isolated_winner_config')


def test_default_and_command_parser_only_enable_on_explicit_option():
    from tests.test_winner_backtest_wiring import options
    from ihm.services.backtesting_runner import build_backtesting_command
    from backtesting.winner_campaign_replay import build_parser
    ordinary=build_backtesting_command('run',options())
    assert '--ignore-missing-intraday' not in ordinary
    assert build_parser().parse_args(ordinary[4:]).ignore_missing_intraday is False
    explicit=build_backtesting_command('run',options(winner_ignore_missing_intraday=True))
    assert build_parser().parse_args(explicit[4:]).ignore_missing_intraday is True


def test_scope_starts_at_signals_not_at_unrelated_prelisting_dates_and_counts_early_close():
    selected=pd.DataFrame([dict(symbol='IPO',trade_date='2026-11-27',selected=True,rank=1)])
    wp=WinnerPyramidingConfig(horizon_sessions=1,entry_valid_sessions=1)
    windows=required_windows(selected,date(2026,12,10),wp)
    assert windows=={'IPO':[(date(2026,11,27),date(2026,12,1))]}
    first,closing=regular_bounds(date(2026,11,27))
    gaps=classify_missing({'IPO':[(date(2026,11,27),date(2026,11,27))]},[
        dict(symbol='IPO',trade_date='2026-11-27',bars=42,first_bar=first,last_bar=closing-timedelta(minutes=5))])
    assert gaps==[]
    assert required_windows(selected.iloc[:0],date(2026,12,10),wp)=={}


def fixture_database():
    from tests.test_winner_intraday import fixture
    cfg,args,raw=fixture(symbols=('AAA','BBB'))
    missing=pd.Timestamp('2026-10-20T14:00Z')
    frame=raw[(cfg.end_date,'AAA')]
    raw[(cfg.end_date,'AAA')]=frame.loc[~frame.timestamp.eq(missing)]
    rows=[]
    for (day,symbol),frame in raw.items():
        for row in frame.to_dict('records'):
            stamp=row.pop('timestamp').to_pydatetime().replace(tzinfo=None)
            rows.append(dict(row,symbol=symbol,trade_date=day,bar_timestamp=stamp,
                bar_end_timestamp=stamp+timedelta(minutes=5),interval_code='5m',data_source='alpaca_sip',
                provider='alpaca',market_code='US_EQ',session_tag='regular',data_adjustment='raw',
                is_filled=0,payload_hash='qualified'))
    sql=create_engine('sqlite://')
    pd.DataFrame(rows).to_sql('stock_bars_intraday',sql,index=False)
    return sql,cfg,args


def test_audit_is_read_only_and_lists_the_exact_ticker_session_gap(caplog):
    sql,cfg,args=fixture_database()
    statements=[]
    event.listen(sql,'before_cursor_execute',lambda c,cursor,s,*a:statements.append(s))
    with sql.connect() as conn:
        report=screen_missing_intraday(conn,args['signals_df'],cfg.end_date,cfg.exec_config.winner_pyramiding)
    assert report['excluded_symbols']==['AAA']
    assert report['missing_sessions']==1
    assert report['gaps'][0]['date']=='2026-10-20'
    assert report['gaps'][0]['qualified_bars']==77 and report['gaps'][0]['missing_bars']==1
    assert report['uses_future_data_availability'] is True and report['live_compatible'] is False
    assert all(s.lstrip().startswith('SELECT') for s in statements)
    with caplog.at_level(logging.WARNING):log_missing_summary(report)
    assert 'AAA' in caplog.text and '2026-10-20' in caplog.text


def test_default_replay_still_fails_but_screened_replay_keeps_other_positions():
    from backtesting.simulator import BacktestEngine
    from backtesting.winner_exclusions import apply_exclusions
    sql,cfg,args=fixture_database()
    with pytest.raises(ValueError,match='Missing held-position'):
        BacktestEngine(cfg).run(**args)
    with sql.connect() as conn:
        report=screen_missing_intraday(conn,args['signals_df'],cfg.end_date,cfg.exec_config.winner_pyramiding)
    args['signals_df'],excluded=apply_exclusions(args['signals_df'],report['excluded_symbols'])
    result=BacktestEngine(cfg).run(**args)
    buys=result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]
    assert buys.symbol.tolist()==['BBB'] and excluded.symbol.tolist()==['AAA']


def test_complete_data_do_not_exclude_any_symbol_and_unknown_dates_are_reported():
    first,closing=regular_bounds(date(2026,10,19))
    windows={'AAA':[(date(2026,10,19),date(2026,10,19))]}
    complete=dict(symbol='AAA',trade_date='2026-10-19',bars=78,first_bar=first,last_bar=closing-timedelta(minutes=5))
    assert classify_missing(windows,[complete])==[]
    assert classify_missing(windows,[])[0]['missing_bars']==78
    with pytest.raises(ValueError,match='Duplicate'):
        classify_missing(windows,[complete,complete])
