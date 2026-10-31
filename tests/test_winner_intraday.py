"""Offline end-to-end replay through the actual campaign runtime and risk checker."""
from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.usefixtures('isolated_winner_config')

from backtesting.simulator import BacktestConfig, BacktestEngine
from backtesting.trading_constraints import TradingConstraintConfig
from common.market_calendar import get_market_calendar
from common.winner_pyramiding import WinnerPyramidingConfig
from execution_engine.config import ExecutionConfig, LeverageConfig
from risk_management.config import RiskConfig


def fixture(*, last=date(2026, 10, 20), leverage=1., symbols=('AAA',), **policy):
    first = date(2026, 10, 19)
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    sessions = [s for s in cal.sessions(first-timedelta(days=7), last) if s.is_open]
    history = pd.bdate_range('2025-01-01', last)
    daily = pd.DataFrame({s: 100.+np.sin(np.arange(len(history))*(i+1)) for i, s in enumerate(symbols)}, index=history)
    raw = {}
    for session in sessions:
        for s in symbols:
            stamps = pd.date_range(session.open_at_utc, session.close_at_utc, freq='5min', inclusive='left')
            values = np.full(len(stamps), 100.)
            if session.session_date >= first:
                values[1:] = 102.  # cross + two completed closes -> buy at 09:45 only
            raw[session.session_date, s] = pd.DataFrame(dict(symbol=s, timestamp=stamps,
                open=values, close=values, high=values+.1, low=values-.1, volume=100000.))
    def source(day, names):
        frames = [raw[day, s] for s in names if (day, s) in raw]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    prior = max(s.session_date for s in sessions if s.session_date < first)
    signals = pd.DataFrame([dict(trade_date=prior, symbol=s, selected=True, rank=i+1) for i, s in enumerate(symbols)])
    wp = WinnerPyramidingConfig(enabled=True, trailing_stop_pct=None, **policy)
    exec_cfg = ExecutionConfig(winner_pyramiding=wp, account_type='margin',
        simulated_margin_buying_power_multiplier=leverage,
        leverage=LeverageConfig(enabled=leverage > 1, mode='regt_swing' if leverage > 1 else 'disabled',
            max_leverage=leverage, dry_run_simulated_leverage=leverage))
    risk = RiskConfig(account_equity=4000., risk_per_trade_pct=.1, max_position_weight=.9,
        max_sector_weight=1., max_gross_exposure=leverage, max_positions=10,
        min_position_notional=10., correlation_threshold=1., policy='b0',
        max_daily_loss_pct=.5, max_portfolio_drawdown_pct=.5)
    cfg = BacktestConfig(start_date=first, end_date=last, initial_equity=4000.,
        exec_config=exec_cfg, risk_config=risk, use_canonical_costs=True,
        margin_interest_rate_annual=.08, trading_constraints=TradingConstraintConfig())
    args = dict(open_df=daily, close=daily, high=daily+1, low=daily-1,
        volume=daily*100000., signals_df=signals, sector_map={s: 'Sector'+str(i) for i, s in enumerate(symbols)},
        intraday_source=source, winner_research_assumptions=True, winner_corporate_actions=[])
    return cfg, args, raw


def test_actual_runtime_risk_cash_and_costs_are_connected():
    cfg, args, _ = fixture()
    result = BacktestEngine(cfg).run(**args)
    meta = result.tracker_snapshot['winner_replay']
    assert meta['status'] == 'COMPLETED_EXPLORATORY'
    assert len(meta['open_positions']) == 1
    assert meta['costs'] > 0 and result.final_value() < 4000
    marks = result.intraday_equity_curve
    assert marks.gross.max() <= 4000
    first_exposure = marks.loc[marks.gross.gt(0)].iloc[0]
    assert first_exposure.timestamp.hour == 13 and first_exposure.timestamp.minute == 50
    assert not result.drawdown_breaker_df.empty


def test_missing_archived_factors_blocks_entries_and_marks_incomplete():
    cfg, args, _ = fixture()
    cfg.risk_config = replace(cfg.risk_config, enable_factor_model=True)
    def unavailable(*a):
        raise ValueError('No causal factor observations')
    result = BacktestEngine(cfg).run(**args, winner_factor_source=unavailable)
    meta = result.tracker_snapshot['winner_replay']
    assert meta['status'] == 'INCOMPLETE_COVERAGE'
    assert any('FACTOR_CONTEXT_UNAVAILABLE' in str(gap) for gap in meta['coverage_gaps'])
    assert not result.trade_events_df.event.eq('BUY_FILL').any()


def test_replay_archived_context_reaches_real_factor_guard(monkeypatch):
    from types import SimpleNamespace
    cfg, args, _ = fixture()
    cfg.risk_config = replace(cfg.risk_config, enable_factor_model=True)
    checks=[]
    def context(day, required, now, risk):
        assert required=={'AAA'}
        return dict(qualified=True, asof_date=day, captured_at=now, observed_at=now,
            exposures={'AAA': SimpleNamespace(market_beta=10.)},
            covariance=SimpleNamespace(estimation_date=day))
    def reject(context, weights, risk, **kwargs):
        checks.append((context,weights,kwargs))
        return ['beta cap']
    monkeypatch.setattr('risk_management.live_factor_context.factor_violations',reject)
    result=BacktestEngine(cfg).run(**args,winner_factor_source=context)
    assert checks and checks[0][2]['candidate']=='AAA'
    assert not result.trade_events_df.event.eq('BUY_FILL').any()


def test_zero_market_entry_fills_first_open_without_confirmation_and_still_exits_open21():
    cfg, args, _ = fixture(last=date(2026, 11, 18), confirmation_bars=0)
    result = BacktestEngine(cfg).run(**args)
    buys = result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]
    assert buys.iloc[0].time == pd.Timestamp('2026-10-19T13:30:00Z')
    trade = result.closed_trades_df.iloc[0]
    assert trade.entry_price == 100. and trade.exit_reason == 'HORIZON_OPEN'
    assert trade.exit_date == pd.Timestamp('2026-11-16T14:30:00Z')
    assert result.tracker_snapshot['winner_replay']['costs'] > 0
    assert 'observed 5m opens only' in result.tracker_snapshot['winner_replay']['standard_entry_assumptions']


def test_zero_resting_day_limit_cannot_fill_from_a_future_low_and_expires():
    cfg, args, raw = fixture(confirmation_bars=0)
    cfg.exec_config = replace(cfg.exec_config, entry_order_type='limit', limit_price_buffer_bps=-100)
    for day in (cfg.start_date, cfg.end_date):
        raw[(day, 'AAA')].loc[:, 'low'] = 95.  # Opens stay >99; don't infer intrabar fill.
    result = BacktestEngine(cfg).run(**args)
    assert not result.trade_events_df.event.eq('BUY_FILL').any()
    assert result.tracker_snapshot['winner_replay']['gross'] == 0


def test_zero_day_limit_waits_for_a_qualified_later_open_instead_of_becoming_ioc():
    cfg, args, raw = fixture(confirmation_bars=0)
    cfg.exec_config = replace(cfg.exec_config, entry_order_type='limit', limit_price_buffer_bps=-100)
    raw[(cfg.start_date, 'AAA')].loc[2, ['open', 'close', 'high', 'low']] = [98., 98., 98.1, 97.9]
    result = BacktestEngine(cfg).run(**args)
    buys = result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]
    assert buys.iloc[0].time == pd.Timestamp('2026-10-19T13:40:00Z')
    assert buys.iloc[0].price == 98.


def test_shared_capital_and_explicit_two_x_not_fake_independent_deposits():
    cfg, args, _ = fixture(symbols=('AAA', 'BBB', 'CCC'), initial_position_fraction=1.)
    one = BacktestEngine(cfg).run(**args)
    assert one.intraday_equity_curve.gross.max() <= 4000
    cfg2, args2, _ = fixture(symbols=('AAA', 'BBB', 'CCC'), leverage=2., initial_position_fraction=1.)
    two = BacktestEngine(cfg2).run(**args2)
    assert two.intraday_equity_curve.gross.max() > 4000
    assert two.intraday_equity_curve.gross.max() <= 8000
    assert two.tracker_snapshot['winner_replay']['margin_interest'] > 0


def test_missing_held_bar_aborts_instead_of_inventing_a_price():
    cfg, args, raw = fixture()
    key = (cfg.end_date, 'AAA')
    raw[key] = raw[key].iloc[1:]
    with pytest.raises(ValueError, match='Missing held-position'):
        BacktestEngine(cfg).run(**args)


def test_future_same_day_gap_is_not_a_lookahead_filter_on_initial_selection():
    cfg, args, raw = fixture()
    key = (cfg.start_date, 'AAA')
    raw[key] = raw[key].drop(index=20)  # Entry is qualified long BEFORE the hole.
    with pytest.raises(ValueError, match='Missing held-position'):
        BacktestEngine(cfg).run(**args)  # Cannot skip the entry using future coverage.


def test_candidate_missing_history_is_reported_incomplete_not_success():
    cfg, args, raw = fixture()
    raw[(date(2026, 10, 16), 'AAA')] = raw[(date(2026, 10, 16), 'AAA')].iloc[1:]
    result = BacktestEngine(cfg).run(**args)
    assert result.tracker_snapshot['winner_replay']['status'] == 'INCOMPLETE_COVERAGE'
    assert result.intraday_equity_curve.gross.max() == 0


def test_holding_session_twenty_is_followed_by_session_twenty_one_open_exit():
    cfg, args, _ = fixture(last=date(2026, 11, 18))
    result = BacktestEngine(cfg).run(**args)
    trades = result.closed_trades_df
    assert len(trades) == 1 and trades.iloc[0].exit_reason == 'HORIZON_OPEN'
    assert trades.iloc[0].entry_date.date() == date(2026, 10, 19)
    assert trades.iloc[0].exit_date == pd.Timestamp('2026-11-16 14:30:00Z')
    assert result.tracker_snapshot['winner_replay']['gross'] == 0


def test_no_short_conversion_and_no_daily_fallback():
    cfg, args, _ = fixture()
    args['signals_df']['side'] = 'short'
    with pytest.raises(ValueError, match='LONG-only'):
        BacktestEngine(cfg).run(**args)
    args['signals_df']['side'] = 'long'
    args['intraday_source'] = None
    with pytest.raises(ValueError, match='explicit intraday'):
        BacktestEngine(cfg).run(**args)
    args['winner_research_assumptions'] = False
    with pytest.raises(ValueError, match='research_assumptions'):
        BacktestEngine(cfg).run(**args)


def test_known_corporate_action_does_not_become_fake_pnl():
    cfg, args, _ = fixture()
    args['winner_corporate_actions'] = [dict(symbol='AAA', ex_date=cfg.end_date, ca_type='split')]
    with pytest.raises(ValueError, match='Corporate action'):
        BacktestEngine(cfg).run(**args)


def test_native_drawdown_breaker_blocks_later_entry_after_actual_stop_loss():
    cfg, args, raw = fixture(symbols=('AAA', 'BBB'))
    cfg.risk_config = replace(cfg.risk_config, max_portfolio_drawdown_pct=.04)
    first = raw[(cfg.start_date, 'AAA')]
    first.loc[4, ['open', 'close', 'high', 'low']] = [90., 90., 90.1, 89.9]
    second = raw[(cfg.start_date, 'BBB')]
    second.loc[:9, ['open', 'close', 'high', 'low']] = [100., 100., 100.1, 99.9]
    result = BacktestEngine(cfg).run(**args)
    filled = result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]
    assert filled.symbol.tolist() == ['AAA']
    assert result.closed_trades_df.iloc[0].pnl < 0
    assert result.drawdown_breaker_df.active.any()


def test_optional_winning_add_uses_remaining_budget_and_shared_cash():
    cfg, args, raw = fixture(reinforcement_enabled=True)
    frame = raw[(cfg.start_date, 'AAA')]
    frame.loc[10:, ['open', 'close', 'high', 'low']] = [109., 109., 109.1, 108.9]
    result = BacktestEngine(cfg).run(**args)
    buys = result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]
    assert len(buys) == 2
    assert buys.iloc[1].price > buys.iloc[0].price*1.05
    assert result.intraday_equity_curve.gross.max() <= 4000


def test_score_ranking_is_not_realized_return_and_noncausal_model_is_refused():
    from backtesting.winner_campaign_replay import validate_scores
    rows = pd.DataFrame([dict(trade_date=date(2026, 10, 16), symbol=s, proba_extreme=p,
        fold_start='2026-01-01', lineage_fold_start='2026-01-01', model_available_date='2025-12-31',
        target_name='oracle_path_extreme20', target_horizon=20, model_sha256='model',
        feature_profile_sha256='profile') for s, p in [('ZZZ', .8), ('AAA', .8), ('TOP', .9)]])
    kwargs = dict(profile_hash='profile', folds={'2026-01-01': {'model_sha256': 'model',
        'metrics': dict(train_available_max='2025-12-30',val_available_max='2025-12-31')}},
        expected_days=[date(2026, 10, 16)], top_n=2)
    assert validate_scores(rows, **kwargs).symbol.tolist() == ['TOP', 'AAA']
    rows.loc[0, 'model_available_date'] = '2026-10-16'
    with pytest.raises(ValueError, match='non-causal'):
        validate_scores(rows, **kwargs)  # validate all rows before truncating TOP-N


def test_cash_dividend_is_receivable_then_cash_not_fake_price_profit():
    cfg, args, _ = fixture()
    args['winner_corporate_actions'] = [dict(symbol='AAA', ex_date=cfg.end_date,
        ca_type='cash_dividend', payable_date=cfg.end_date+timedelta(days=1), amount_per_share=1., currency='USD')]
    result = BacktestEngine(cfg).run(**args)
    meta = result.tracker_snapshot['winner_replay']
    assert meta['dividends_accrued'] == meta['dividends_receivable'] > 0
    assert result.final_value() == pytest.approx(4000-meta['costs']+meta['dividends_receivable'])


def test_metrics_and_sql_source_are_read_only_and_keep_provider_scope():
    from backtesting.winner_campaign_replay import SqlIntradaySource, metrics
    from sqlalchemy import create_engine, event, text
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE stock_bars_intraday (symbol TEXT, bar_timestamp TEXT, bar_end_timestamp TEXT, '
            'trade_date TEXT, interval_code TEXT, data_source TEXT, provider TEXT, market_code TEXT, '
            'session_tag TEXT, data_adjustment TEXT, is_filled INT, open REAL, high REAL, low REAL, close REAL, volume REAL, payload_hash TEXT)'))
        conn.execute(text("INSERT INTO stock_bars_intraday VALUES ('AAA','2026-10-19 13:30:00','2026-10-19 13:35:00',"
            "'2026-10-19','5m','alpaca_iex','alpaca','US_EQ','regular','raw',0,100,101,99,100,1000,'hash')"))
    statements = []
    event.listen(engine, 'before_cursor_execute', lambda conn, cursor, statement, *a: statements.append(statement))
    with engine.connect() as conn:
        assert SqlIntradaySource(conn)(date(2026, 10, 19), ['AAA']).empty
    assert all(s.lstrip().upper().startswith('SELECT ') for s in statements)
    cfg, args, _ = fixture()
    report = metrics(BacktestEngine(cfg).run(**args), 4000.)
    assert report['costs'] > 0 and report['full_live_parity'] is False
    assert report['average_gross_capital'] > 0


def test_cli_complete_readonly_run_exports_reports_without_api_or_prediction(tmp_path, monkeypatch):
    from argparse import Namespace
    from hashlib import sha256
    import json
    from sqlalchemy import create_engine, event
    from backtesting.winner_campaign_replay import run
    cfg, args, raw = fixture()
    engine = create_engine('sqlite://')
    daily = args['close'].copy()
    daily['SPY'] = daily.AAA
    daily = daily.stack().rename('close').reset_index()
    daily.columns = ['date', 'symbol', 'close']
    for field, delta in [('open', 0), ('high', 1), ('low', -1)]:
        daily[field] = daily.close+delta
    daily['date'] = daily.date.dt.date
    daily['volume'], daily['is_filled'], daily['data_adjustment'] = 1000000, 0, 'split'
    daily['data_source'] = 'alpaca_sip'
    daily.to_sql('stock_bars_daily', engine, index=False)
    frame = pd.concat(raw.values(), ignore_index=True).rename(columns={'timestamp': 'bar_timestamp'})
    frame['trade_date'] = frame.bar_timestamp.dt.date
    frame['bar_end_timestamp'] = frame.bar_timestamp+pd.Timedelta(minutes=5)
    frame['bar_timestamp'] = frame.bar_timestamp.dt.tz_localize(None)
    frame['bar_end_timestamp'] = frame.bar_end_timestamp.dt.tz_localize(None)
    for key, val in dict(interval_code='5m', data_source='alpaca_sip', provider='alpaca', market_code='US_EQ',
            session_tag='regular', data_adjustment='raw', is_filled=0, payload_hash='x'*64).items():
        frame[key] = val
    frame.to_sql('stock_bars_intraday', engine, index=False)
    pd.DataFrame([dict(symbol='AAA', sector='Technology')]).to_sql('stock_metadata', engine, index=False)
    pd.DataFrame(columns=['symbol', 'ca_type', 'ex_date', 'payable_date', 'amount_per_share', 'currency']).to_sql(
        'corporate_actions_events', engine, index=False)
    root = tmp_path/'model'
    root.mkdir()
    (root/'protocol.json').write_text('{}')
    (root/'feature_profile.json').write_text('{}')
    digest = sha256(b'{}').hexdigest()
    predictions = pd.DataFrame([dict(prediction_date=d, symbol='AAA', proba_extreme=.9,
        fold_start=date(2026, 1, 1), batch_id='model') for d in [date(2026, 10, 16), date(2026, 10, 19)]])
    predictions.to_sql('oracle_extreme_predictions', engine, index=False)
    lineage = predictions.drop(columns='proba_extreme').assign(model_available_date=date(2025, 12, 31),
        target_name='oracle_path_extreme20', target_horizon=20, model_sha256='m'*64,
        feature_profile_sha256=digest)
    lineage.to_sql('oracle_path_prediction_lineage', engine, index=False)
    monkeypatch.setattr('database.connection.get_sqlalchemy_engine', lambda **kw: engine)
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract',
        lambda *a: (root, {'horizon':20}, {}, {'2026-01-01': {'model_sha256': 'm'*64,
            'metrics':dict(train_available_max='2025-12-30',val_available_max='2025-12-31')}}))
    monkeypatch.setattr('common.universe_files.load_universe_file_symbols', lambda *a: ['AAA'])
    monkeypatch.setattr('risk_management.config.load_risk_config', lambda **kw: cfg.risk_config)
    def select_only(conn, cursor, sql, parameters, *unused):
        assert sql.lstrip().upper().startswith(('SELECT', 'SET TRANSACTION')), sql
        if sql.startswith('SET TRANSACTION'):
            return 'SELECT 1', ()
        if sql == 'SELECT DATABASE()':
            return "SELECT 'alpha_trade'", ()
        return sql, parameters
    event.listen(engine, 'before_cursor_execute', select_only, retval=True)
    options = Namespace(start_date=cfg.start_date, end_date=cfg.end_date, initial_equity=4000.,
        top_n=1, research_assumptions=True, output_dir=str(tmp_path/'replay'), artifacts_dir=str(root),
        oracle_batch_id='model', symbol_source='universe-file:fixture.txt', max_leverage=1.,
        account_type='margin', margin_interest_annual=.065,max_positions=12,
        risk_overrides_json='{"risk_per_trade_pct":0.02,"min_position_notional":20.0}',
        policy_overrides_json='{"stop_loss_pct":0.07,"horizon_sessions":10}')
    report = run(options)
    assert report['status'] == 'COMPLETED_EXPLORATORY' and report['costs'] > 0
    assert (tmp_path/'replay'/'annual-summary.csv').is_file()
    assert (tmp_path/'replay'/'equity_curve.csv').is_file()
    assert report['summary']['final_value'] == report['final_equity']
    assert report['run_metadata']['engine'] == 'winner_campaign_replay'
    assert report['params']['risk']['risk_per_trade_pct']==.02
    assert report['params']['risk']['min_position_notional']==20.
    assert report['params']['risk']['fixed_stop_pct']==.07
    assert report['params']['risk']['max_positions']==report['params']['risk']['max_long_positions']==12
    assert report['params']['winner_policy']['horizon_sessions']==10
    assert json.loads((tmp_path/'replay'/'progress.json').read_text())['completed'] == 2
    with pytest.raises(FileExistsError):
        run(options)  # Never overwrite a completed run.
