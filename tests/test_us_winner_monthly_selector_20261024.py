from dataclasses import replace
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_winner_monthly_selector_20261024 as study
from backtesting.simulator import BacktestEngine, BacktestConfig
from backtesting.trading_constraints import TradingConstraintConfig
from execution_engine.config import ExecutionConfig
from execution_engine.models import ExecutionTarget
from common.winner_pyramiding import WinnerPyramidingConfig
from risk_management.config import RiskConfig


def curves():
    dates = pd.bdate_range('2019-01-01', '2024-12-31')
    return {name: pd.Series(4000.*(1.+(i+1)*.0001)**np.arange(len(dates)), index=dates)
            for i, name in enumerate(study.CATALOG)}


@pytest.mark.parametrize('window', [30, 50])
def test_selection_uses_exactly_window_returns_and_never_future(window):
    data = curves(); cutoff = pd.Timestamp('2020-01-31')
    got = study.choose_profile(data, cutoff, window)
    expected = next(reversed(study.CATALOG))
    assert got['profile'] == expected
    idx = data[expected].index.get_loc(cutoff)
    assert got['window_start'] == str(data[expected].index[idx-window].date())
    for series in data.values():
        series.loc[series.index > cutoff] = .01
    assert study.choose_profile(data, cutoff, window) == got


def test_tie_retains_previous_and_missing_history_is_not_zero():
    dates = pd.bdate_range('2019-01-01', periods=70)
    data = {name: pd.Series(4000., index=dates) for name in study.CATALOG}
    previous = study.PROFILES[1]['name']
    assert study.choose_profile(data, dates[-1], 50, previous)['profile'] == previous
    with pytest.raises(ValueError, match='Insufficient'):
        study.choose_profile(data, dates[20], 50)
    data[previous] = data[previous].iloc[:-1]
    with pytest.raises(ValueError, match='calendars differ'):
        study.choose_profile(data, dates[-1], 30)


def test_monthly_cutoff_is_prior_session_close_and_2020_2024_only():
    decisions = study.monthly_decisions(curves(), 50)
    assert len(decisions) == 60
    assert decisions['2020-01']['cutoff'] == '2019-12-31'
    assert decisions['2020-01']['first_session'] == '2020-01-02'
    assert decisions['2020-02']['cutoff'] == '2020-01-31'
    assert decisions['2020-02']['first_session'] == '2020-02-03'
    assert all(pd.Timestamp(r['available_at']) < pd.Timestamp(r['effective_open']) for r in decisions.values())


def test_profile_configuration_keeps_requested_risk_capital_and_fees():
    p = study.capacity.read_json(study.capacity.ROOT/'protocol.json')
    cfg = study.configuration(p, date(2020, 1, 2))
    assert cfg.initial_equity == 4000.
    assert cfg.start_date == date(2020, 1, 2) and cfg.end_date == date(2024, 12, 31)
    assert cfg.risk_config.max_positions == cfg.risk_config.max_long_positions == 20
    assert cfg.risk_config.max_gross_exposure == 1.
    assert cfg.risk_config.concentration_max_trades_per_symbol == 10
    assert cfg.cost_round_trip_bps == 16.
    assert cfg.exec_config.winner_pyramiding.initial_position_fraction == 1.
    assert len(study.PROFILES) == 6


def test_target_resize_never_expands_original_signal_weight_cap():
    target = ExecutionTarget('r', date(2020, 1, 2), 'A', 50, 10., .125, 'S', 1., 'test', None,
                             risk_budget_dollars=50., side='long')
    config = ExecutionConfig(winner_pyramiding=WinnerPyramidingConfig(enabled=True, initial_position_fraction=1.))
    for name in study.CATALOG:
        policy = study.profile_policy(config, name)
        new = study.resize_target(target, config, policy)
        assert 0 <= new.target_shares <= 50 and new.target_weight <= target.target_weight
        assert new.risk_budget_dollars == target.risk_budget_dollars


def replay_fixture(pending_until_november=False):
    start, end = date(2020, 10, 30), date(2020, 11, 3)
    cal = study.capacity.grid.calendar()
    schedule = [s for s in cal.sessions(start-timedelta(days=10), end) if s.is_open]
    history = pd.bdate_range('2019-01-01', end)
    daily = pd.DataFrame({'AAA': 100.+np.sin(np.arange(len(history)))}, index=history)
    raw = {}
    for session in schedule:
        stamps = pd.date_range(session.open_at_utc, session.close_at_utc, freq='5min', inclusive='left')
        values = np.full(len(stamps), 100.)
        if session.session_date >= (date(2020, 11, 2) if pending_until_november else start):
            values[1:] = 102.
        raw[session.session_date] = pd.DataFrame(dict(symbol='AAA', timestamp=stamps,
            open=values, close=values, high=values+.1, low=values-.1, volume=100000.))
    def source(day, symbols):
        return raw[day].copy() if 'AAA' in symbols else pd.DataFrame()
    policy = WinnerPyramidingConfig(enabled=True, initial_position_fraction=1., reinforcement_enabled=False,
        stop_loss_pct=.03, trailing_stop_pct=None, take_profit_pct=None, horizon_sessions=20)
    execution = ExecutionConfig(winner_pyramiding=policy, account_type='margin')
    risk = RiskConfig(account_equity=4000., risk_per_trade_pct=.1, max_position_weight=.9,
        max_sector_weight=1., max_gross_exposure=1., max_positions=20, min_position_notional=10.,
        correlation_threshold=1., policy='b0', max_daily_loss_pct=.5, max_portfolio_drawdown_pct=.5)
    cfg = BacktestConfig(start_date=start, end_date=end, initial_equity=4000., exec_config=execution,
        risk_config=risk, use_canonical_costs=True, cost_round_trip_bps=16.,
        trading_constraints=TradingConstraintConfig(account_type='margin', swing_only=False))
    prior = max(s.session_date for s in schedule if s.session_date < start)
    kwargs = dict(open_df=daily, close=daily, high=daily+1, low=daily-1, volume=daily*100000.,
        signals_df=pd.DataFrame([dict(trade_date=prior, symbol='AAA', rank=1, selected=True)]),
        sector_map={'AAA': 'S'}, intraday_source=source,
        winner_research_assumptions=True, winner_corporate_actions=[])
    return cfg, kwargs


@pytest.mark.parametrize('pending', [False, True])
def test_real_native_runtime_preserves_held_policy_and_rearms_only_pending(pending):
    cfg, kwargs = replay_fixture(pending)
    select = lambda d: study.PROFILES[0]['name'] if d.month == 10 else study.PROFILES[1]['name']
    before_stage, before_runtime = study.native.stage_targets, study.native.WinnerCampaignRuntime
    with study.capacity.corrected_runtime(), study.campaign_adapter(cfg.exec_config, select) as metadata:
        result = BacktestEngine(cfg).run(**kwargs)
    assert study.native.stage_targets is before_stage and study.native.WinnerCampaignRuntime is before_runtime
    filled = [r for r in metadata.values() if r.get('first_fill_at')]
    assert len(filled) == 1
    assert filled[0]['profile'] == study.PROFILES[int(pending)]['name']
    assert filled[0]['policy']['trailing_stop_pct'] == (.15 if pending else None)
    assert result.tracker_snapshot['winner_replay']['status'] == 'COMPLETED_EXPLORATORY'
    if pending:
        assert len({r['entry_expires_at'] for r in metadata.values()}) == 1
        assert len(metadata) == 2


def test_funded_or_attempted_plans_cannot_be_rearmed():
    state = dict(lots=[], initial_attempted=False, operations=[], status='PENDING', entry_expires_at='2020-12-01T21:00:00+00:00')
    now = pd.Timestamp('2020-11-02T15:00Z')
    assert study.unfilled_rearm_allowed(state, now)
    for changes in [dict(lots=[dict(remaining=5)]), dict(initial_attempted=True), dict(operations=[dict(status='RESERVED')])]:
        assert not study.unfilled_rearm_allowed(dict(state, **changes), now)


def test_real_entry_uses_selected_horizon_not_outer_admission_h20():
    cfg, kwargs = replay_fixture()
    name = study.PROFILES[3]['name']
    with study.capacity.corrected_runtime(), study.campaign_adapter(cfg.exec_config, lambda _d: name) as metadata:
        BacktestEngine(cfg).run(**kwargs)
    filled = next(r for r in metadata.values() if r.get('first_fill_at'))
    day = pd.Timestamp(filled['first_fill_at']).tz_convert('America/New_York').date()
    days = [s for s in study.capacity.grid.calendar().sessions(day, day+timedelta(days=40)) if s.is_open]
    assert filled['policy']['horizon_sessions'] == 10
    assert pd.Timestamp(filled['due_open']) == pd.Timestamp(days[10].open_at_utc)


def test_sealed_top20_score_archive_is_complete_and_causal():
    scores, seed = study.inputs.ranked_scores()
    assert seed == date(2019, 6, 28)
    assert len(scores) == 27740 and scores.symbol.nunique() == 333
    assert scores.groupby('date').size().eq(20).all()
    assert (pd.to_datetime(scores.model_available_date) < scores.date).all()
