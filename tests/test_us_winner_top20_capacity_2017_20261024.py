from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.research import us_winner_top20_capacity_2017_20261024 as study


def test_only_requested_configuration_changes():
    parent = study.read_json(study.PARENT/'protocol.json')
    before = study.grid.configuration(parent, 2017, study.PROFILE)
    after = study.configuration(parent)
    assert after.risk_config.max_positions == after.risk_config.max_long_positions == 20
    assert after.risk_config.concentration_max_trades_per_symbol == 10
    assert after.risk_config.concentration_window_calendar_days == 180
    assert after.exec_config.winner_pyramiding.initial_position_fraction == 1.
    assert not after.exec_config.winner_pyramiding.reinforcement_enabled
    assert after.risk_config.max_gross_exposure == 1.
    assert after.risk_config.concentration_max_consecutive_losses == before.risk_config.concentration_max_consecutive_losses == 3
    assert after.risk_config.concentration_blacklist_duration_days == before.risk_config.concentration_blacklist_duration_days == 90
    assert after.risk_config.risk_per_trade_pct == before.risk_config.risk_per_trade_pct
    assert after.risk_config.correlation_threshold == before.risk_config.correlation_threshold
    assert after.risk_config.max_sector_weight == before.risk_config.max_sector_weight
    assert after.cost_round_trip_bps == before.cost_round_trip_bps == 16.


def test_entry_coverage_needs_exit_day_and_clips_at_year_end():
    days = [date(2017, 7, 1)+timedelta(days=i) for i in range(45)]
    groups = {('A', day): object() for day in days[:21]}
    assert study.holding_window_available('A', days[0], groups, days)
    assert not study.holding_window_available('A', days[1], groups, days)
    del groups['A', days[20]]
    assert not study.holding_window_available('A', days[0], groups, days)
    assert study.holding_window_available('A', days[19], groups, days[:20])
    assert not study.holding_window_available('B', days[0], groups, days)


def test_relaxation_preserves_rank_and_corporate_action_reservation():
    days = [date(2017, 7, 1)+timedelta(days=i) for i in range(45)]
    signals = pd.DataFrame(dict(date=[pd.Timestamp(days[0])]*3, symbol=['A', 'B', 'C'], rank=[1, 2, 3]))
    groups = {('A', days[0]): object(), ('B', days[0]): object()}
    actions = pd.DataFrame(dict(symbol=['B'], ex_date=[pd.Timestamp(days[30])]))
    got = study.relaxed_signals(signals, groups, actions, {'A': 'S', 'B': 'S', 'C': 'S'}, days)
    assert got['rank'].tolist() == [1, 2, 3]
    assert got.selected.tolist() == [True, False, False]
    assert got.coverage_reason.tolist() == ['', 'CORPORATE_ACTION_LIFECYCLE_RESERVED', 'SIGNAL_SESSION_SIP_MISSING']


def test_entry_gate_is_process_local_and_never_approves_missing_holding_window(monkeypatch):
    days = [date(2017, 7, 1), date(2017, 7, 2)]
    now = datetime(2017, 7, 1, 15, tzinfo=timezone.utc)
    monkeypatch.setattr(study.native, 'reapprove_campaign', lambda *_a, **_k: {'ok': True})
    old = study.native.reapprove_campaign
    with study.entry_coverage_gate({}, days) as refused:
        with pytest.raises(ValueError, match='HOLDING_WINDOW'):
            study.native.reapprove_campaign({'symbol': 'A'}, 0, 1, {}, now, 'ENTRY', context={})
        assert refused == {('2017-07-01', 'A')}
    assert study.native.reapprove_campaign is old


def test_candidate_gap_must_not_hide_a_held_position():
    result = SimpleNamespace(closed_trades_df=pd.DataFrame([dict(symbol='A',
        entry_date=pd.Timestamp('2017-07-03T14:00Z'), exit_date=pd.Timestamp('2017-07-05T14:00Z'))]),
        trade_events_df=pd.DataFrame(columns=['event', 'symbol', 'time', 'quantity']),
        tracker_snapshot={'winner_replay': {'open_positions': []}})
    assert study.audit_held_coverage(result, [dict(date='2017-07-06', symbol='A')], date(2017, 12, 31))['status'].startswith('PASS')
    with pytest.raises(ValueError, match='held lifecycle'):
        study.audit_held_coverage(result, [dict(date='2017-07-04', symbol='A')], date(2017, 12, 31))


def test_reentry_does_not_turn_a_flat_interval_into_a_held_coverage_gap():
    events = pd.DataFrame([
        dict(event='BUY_FILL', symbol='A', quantity=5, time=pd.Timestamp('2017-07-03T14:00Z')),
        dict(event='SELL_FILL', symbol='A', quantity=5, time=pd.Timestamp('2017-07-05T14:00Z')),
        dict(event='BUY_FILL', symbol='A', quantity=3, time=pd.Timestamp('2017-07-10T14:00Z')),
    ])
    result = SimpleNamespace(closed_trades_df=pd.DataFrame([dict(symbol='A',
        entry_date=pd.Timestamp('2017-07-03T14:00Z'), exit_date=pd.Timestamp('2017-07-05T14:00Z'))]),
        trade_events_df=events, tracker_snapshot={'winner_replay': {'open_positions': [dict(symbol='A', qty=3)]}})
    assert study.audit_held_coverage(result, [dict(date='2017-07-07', symbol='A')], date(2017, 12, 31))['candidate_gap_count'] == 1
    with pytest.raises(ValueError, match='held lifecycle'):
        study.audit_held_coverage(result, [dict(date='2017-07-11', symbol='A')], date(2017, 12, 31))
