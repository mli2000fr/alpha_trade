import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_grid_robustness import (ANCHOR, AXES, neighbors, profile_key,
    read_grid, fixed_plan, specialize_cost_auditor, scenario_candidates, verify_baseline_exports)


def test_anchor_has_exactly_five_immediate_neighbors_and_off_is_explicit():
    assert {profile_key(c) for c in neighbors(ANCHOR)} == {
        'SL5-TR15-H20-TPOFF', 'SL7-TR10-H20-TPOFF', 'SL7-TR20-H20-TPOFF',
        'SL7-TR15-H15-TPOFF', 'SL7-TR15-H20-TP10'}
    assert ANCHOR['tp'] is None


def test_neighborhood_symmetric_and_changes_one_axis_one_level_only():
    from itertools import product
    profiles = [dict(zip(AXES, values)) for values in product(*AXES.values())]
    assert len(profiles) == 144
    for p in profiles:
        for n in neighbors(p):
            assert p in neighbors(n)
            changed = [k for k in AXES if p[k] != n[k]]
            assert len(changed) == 1
            key = changed[0]
            assert abs(AXES[key].index(p[key])-AXES[key].index(n[key])) == 1


def test_plan_bounded_and_no_future_training_or_production_tuning():
    plan, contributions = fixed_plan(read_grid())
    assert len(plan) == 86 and len(contributions) > 0
    assert sum(c['scenario'] == 'baseline' for c in plan) == 4
    assert sum(c['scenario'] == 'cost25' for c in plan) == 24
    assert sum(c['scenario'] == 'delay5m' for c in plan) == 24
    assert sum(c['scenario'] == 'cost25_delay5m' for c in plan) == 4
    assert sum(c['scenario'].startswith('without_top') for c in plan) == 16
    assert sum(c['scenario'].startswith('without_entry_') for c in plan) == 14
    assert all(c['fee_bps'] in [8., 25.] and c['delay_bars'] in [0, 1] for c in plan)


def test_auditor_specialization_does_not_change_historical_function_or_accept_unknown_shape():
    from scripts.research import us_intraday_protection_grid_risk_audit as old
    before = old.audit_case
    adapted = specialize_cost_auditor()
    assert old.audit_case is before and adapted is not before
    assert .0008 not in adapted.__code__.co_consts
    assert 'fee_pct' in adapted.__code__.co_consts
    with pytest.raises(ValueError, match='exactly three'):
        specialize_cost_auditor(test_auditor_specialization_does_not_change_historical_function_or_accept_unknown_shape)


def toy_tape():
    ts = pd.Timestamp('2026-01-05T15:00:00Z')
    c = pd.DataFrame([dict(pair_id=1, side='buy', symbol='A', decision_time=ts, signal_close=100.,
                           signal_bar_start=ts-pd.Timedelta(minutes=5), oracle_date=pd.Timestamp('2026-01-02'), rank=1)])
    path = pd.DataFrame(dict(bar_timestamp=[ts, ts+pd.Timedelta(minutes=5)]))
    return dict(candidates=c, paths={1: path}, expiry={(1, 20): ts+pd.Timedelta(days=10)})


def test_entry_delay_keeps_original_known_signal_and_uses_next_contiguous_bar():
    tape = toy_tape()
    c = dict(side='buy', horizon=20, delay_bars=1, excluded_symbols=[], excluded_quarter=None)
    frame, events = scenario_candidates(tape, c)
    assert len(frame) == 1 and events[0]['reason'] == 'KEEP'
    assert frame.decision_time.iloc[0] == tape['candidates'].decision_time.iloc[0]+pd.Timedelta(minutes=5)
    assert frame.signal_close.iloc[0] == 100.
    assert frame.signal_bar_start.iloc[0] == tape['candidates'].signal_bar_start.iloc[0]


def test_no_delayed_entry_rollover_or_missing_bar_fill():
    tape = toy_tape(); tape['paths'][1] = tape['paths'][1].iloc[:1]
    c = dict(side='buy', horizon=20, delay_bars=1, excluded_symbols=[], excluded_quarter=None)
    frame, events = scenario_candidates(tape, c)
    assert frame.empty and events[0]['reason'] == 'NO_CONTIGUOUS_SAME_SESSION_DELAY'


def test_ablation_filters_entries_not_the_price_archive():
    tape = toy_tape(); before = tape['paths'][1].copy()
    c = dict(side='buy', horizon=20, delay_bars=0, excluded_symbols=['A'], excluded_quarter=None)
    frame, events = scenario_candidates(tape, c)
    assert frame.empty and events[0]['reason'] == 'SYMBOL_HINDSIGHT_ABLATION'
    pd.testing.assert_frame_equal(before, tape['paths'][1])
    c.update(excluded_symbols=[], excluded_quarter=1)
    assert scenario_candidates(tape, c)[0].empty


def test_baseline_comparison_normalizes_json_dates_but_rejects_changed_economics(tmp_path):
    from scripts.research.us_concentrated_historical_tapes import atomic_json
    a, b = tmp_path/'a', tmp_path/'b'
    a.mkdir(); b.mkdir()
    frame = pd.DataFrame(dict(value=[1.], timestamp=[pd.Timestamp('2025-01-01T15:00:00Z')]))
    for root in [a, b]:
        for name in ['trades.parquet', 'marks.parquet']:
            frame.to_parquet(root/name, index=False)
        atomic_json(root/'open-positions.json', [dict(qty=1, mark=100., timestamp=frame.timestamp.iloc[0])])
    verify_baseline_exports(a, b)
    atomic_json(a/'open-positions.json', [dict(qty=1, mark=101., timestamp=frame.timestamp.iloc[0])])
    with pytest.raises(ValueError, match='open positions changed'):
        verify_baseline_exports(a, b)
