import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle.build_labels import compute_cross_sectional_ranks
from scripts.research.us_directional_hierarchy_diagnostic import (
    ARMS, CONFIG, causal_training, daily_metrics, freeze_candidates, gate,
    group_corrections, holm_adjust, target, terminal_deciles,
    trajectory_features, transform_train_test,
)


@pytest.fixture
def cfg():
    return json.loads(CONFIG.read_text())


def test_frozen_config_not_a_window_search(cfg):
    assert cfg['trajectory_sessions'] == [5, 10]
    assert cfg['primary_pool'] == 'ORACLE_TOP20_PERCENT'
    assert cfg['validation_year'] == 2022
    assert not cfg['automatic_promotion']
    assert not cfg['database_access']


def test_trajectory_is_session_aligned_and_no_cross_symbol_leakage():
    calendar = pd.bdate_range('2020-01-01', periods=12)
    frame = pd.DataFrame({'date': list(calendar)*2, 'symbol': ['A']*12+['B']*12,
                          'x': list(range(12))+list(range(100, 112))})
    result = trajectory_features(frame, calendar, ['x'], [5, 10])
    assert result.loc[result.date.ge(calendar[5]), 'x_delta_5'].eq(5).all()
    assert result.loc[result.date.lt(calendar[5]), 'x_delta_5'].isna().all()
    assert result.loc[result.date.ge(calendar[10]), 'x_delta_10'].eq(10).all()


def test_gap_in_trajectory_not_forward_filled():
    calendar = pd.bdate_range('2020-01-01', periods=12)
    frame = pd.DataFrame({'date': calendar.delete(3), 'symbol': 'A', 'x': np.arange(11)})
    result = trajectory_features(frame, calendar, ['x'], [5])
    assert result.loc[result.date.eq(calendar[6]), 'x_delta_5'].isna().all()
    assert result.loc[result.date.eq(calendar[10]), 'x_delta_5'].iloc[0] == 5


def test_change_future_feature_cannot_change_earlier_trajectory():
    calendar = pd.bdate_range('2020-01-01', periods=20)
    frame = pd.DataFrame({'date': calendar, 'symbol': 'A', 'x': np.arange(20.)})
    first = trajectory_features(frame, calendar, ['x'], [5, 10])
    frame.loc[15:, 'x'] = 1e9
    second = trajectory_features(frame, calendar, ['x'], [5, 10])
    pd.testing.assert_frame_equal(first.iloc[:15], second.iloc[:15])


def test_freeze_uses_full_observable_population_not_future_quality():
    frame = pd.DataFrame({'date': pd.Timestamp('2020-01-01'), 'symbol': [f'S{i:03}' for i in range(100)],
                          'score_lightgbm': np.arange(100)/100, 'fold_start': '2019-01-01',
                          'future_valid': [True]*99+[False]})
    result = freeze_candidates(frame)
    assert len(result) == 50
    assert result.oracle_top20.sum() == 21  # inclusive canonical >= .8
    assert result.iloc[0].symbol == 'S099'
    assert 'future_valid' not in result
    assert result.iloc[0].oracle_rank == 1


def test_score_ties_deterministic_duplicate_keys_rejected():
    frame = pd.DataFrame({'date': pd.Timestamp('2020-01-01'), 'symbol': ['B', 'A'],
                          'score_lightgbm': .5, 'fold_start': '2019-01-01'})
    assert freeze_candidates(frame).symbol.tolist() == ['A', 'B']
    with pytest.raises(ValueError):
        freeze_candidates(pd.concat([frame, frame]))


def labels_frame():
    return pd.DataFrame({'date': pd.Timestamp('2020-01-01'), 'symbol': [f'S{i}' for i in range(20)],
                         'feature_eligible': True, 'path_qualified': True,
                         'terminal_return': np.arange(20.)/100-.1,
                         'oracle_available_date': pd.Timestamp('2020-02-03')})


def test_terminal_deciles_match_canonical_global_builder(cfg):
    frame = labels_frame()
    result = terminal_deciles(frame, cfg)
    expected = compute_cross_sectional_ranks(frame.terminal_return).oracle_decile
    assert result.oracle_decile.tolist() == expected.tolist()
    assert result.oracle_decile.iloc[0] == 1
    assert result.oracle_decile.iloc[-1] == 10


def test_low_coverage_disables_date_without_fabricating_negatives(cfg):
    frame = labels_frame()
    frame.loc[:2, 'path_qualified'] = False
    result = terminal_deciles(frame, cfg)
    assert result.oracle_decile.isna().all()
    assert result.label_coverage.eq(.85).all()


def test_immature_and_constant_returns_not_ranked(cfg):
    frame = labels_frame()
    frame['terminal_return'] = 0.
    assert terminal_deciles(frame, cfg).oracle_decile.isna().all()
    frame = labels_frame()
    frame['oracle_available_date'] = '2027-01-01'
    assert terminal_deciles(frame, cfg).oracle_decile.isna().all()


def test_three_tasks_distinguish_theoretical_and_full_pool():
    frame = pd.DataFrame({'oracle_decile': [1, 5, 10, np.nan]})
    assert target(frame, 'D1_VS_D10').isna().tolist() == [False, True, False, True]
    assert target(frame, 'D10_VS_REST').iloc[:3].tolist() == [0, 0, 1]
    assert target(frame, 'D1_VS_REST').iloc[:3].tolist() == [1, 0, 0]
    with pytest.raises(ValueError):
        target(frame, 'OTHER')


def test_training_label_must_be_available_strictly_before_test():
    frame = pd.DataFrame({'date': pd.to_datetime(['2021-12-01']*3),
                          'oracle_available_date': pd.to_datetime(['2021-12-31', '2022-01-01', None])})
    assert len(causal_training(frame, '2022-01-01')) == 1


def test_scaling_never_uses_test_values(cfg):
    train = pd.DataFrame({'x': [1., 2., np.nan, 4.]})
    test = pd.DataFrame({'x': [1e9]})
    a, _ = transform_train_test(train, test, ['x'], cfg)
    a2, _ = transform_train_test(train, test*-1, ['x'], cfg)
    np.testing.assert_array_equal(a, a2)


def test_unknown_or_sparse_groups_use_reference(cfg):
    train = pd.DataFrame({'date': pd.bdate_range('2020-01-01', periods=4),
                           'symbol': 'A', 'sector': 'UNKNOWN', '_target': [0, 1, 0, 1]})
    test = pd.DataFrame({'date': [pd.Timestamp('2021-01-01')], 'symbol': ['NEW'], 'sector': ['UNKNOWN']})
    a, b, seen_sector, seen_symbol, evidence = group_corrections(
        train, test, np.zeros((4, 1)), np.zeros((1, 1)), np.full(4, .5), np.array([.6]), cfg)
    assert a[0] == b[0] == .6
    assert not seen_sector.any() and not seen_symbol.any() and not evidence


def test_partial_pooling_learns_group_response_but_shrinks(cfg):
    cfg = {**cfg, 'min_sector_dates': 2, 'min_symbol_dates': 2, 'min_group_each_class': 1,
           'sector_prior_sessions': 10, 'symbol_prior_sessions': 10}
    days = pd.bdate_range('2020-01-01', periods=10)
    train = pd.DataFrame({'date': np.repeat(days, 4), 'symbol': ['A', 'B', 'C', 'D']*10,
                           'sector': ['UP', 'UP', 'DOWN', 'DOWN']*10,
                           '_target': [1, 1, 0, 0]*10})
    # Each group needs both classes: insert occasional counterexamples.
    train.loc[[0, 1, 6, 7], '_target'] = [0, 0, 1, 1]
    test = train.iloc[:4].copy()
    a, b, seen, _, evidence = group_corrections(train, test, np.zeros((40, 1)), np.zeros((4, 1)),
                                               np.full(40, .5), np.full(4, .5), cfg)
    assert a[0] > .5 > a[2]
    assert np.abs(a-.5).max() <= cfg['max_probability_correction']
    assert seen.all() and len(evidence) >= 2
    assert np.isfinite(b).all()


def test_daily_selection_precedes_missing_label_and_tail_filtering():
    frame = pd.DataFrame({'date': pd.Timestamp('2020-01-01'), 'symbol': ['A', 'B', 'C', 'D', 'E'],
                          'oracle_decile': [np.nan, 10., 1., 10., 1.]})
    for arm in ARMS:
        frame[arm] = [.9, .8, .7, .6, .5]
    daily = daily_metrics(frame, 'D1_VS_D10')
    assert daily.selected_label_coverage.eq(0).all()
    assert daily.selected_d10.isna().all()  # missing top A is never replaced by B


def test_daily_auc_not_confounded_by_market_date():
    frame = pd.DataFrame({'date': pd.to_datetime(['2020-01-01']*4+['2020-01-02']*4),
                          'symbol': list('ABCD')*2, 'oracle_decile': [1, 1, 10, 10]*2})
    for arm in ARMS:
        frame[arm] = [.9]*4+[.1]*4
    daily = daily_metrics(frame, 'D1_VS_D10')
    assert daily.auc.eq(.5).all()


def test_holm_is_monotonic_and_retains_unknown():
    p = holm_adjust({'a': .01, 'b': .03, 'c': .9, 'd': None})
    assert p == {'a': .03, 'b': .06, 'c': .9, 'd': None}


def test_gate_rejects_attractive_external_if_validation_fails(cfg):
    validation = dict(auc=.54, auc_delta=.02, brier_gain=.01, dates=200, corrected_fraction=.9)
    confirmation = [dict(auc_delta=.01, brier_gain=.01, dates=100)]*4
    assert gate(validation, confirmation, .01, cfg)
    assert not gate({**validation, 'auc_delta': -.01}, confirmation, .01, cfg)
    assert not gate(validation, confirmation, .2, cfg)
    assert not gate(validation, confirmation[:2], .01, cfg)


def test_script_has_no_sql_provider_or_order_path():
    source = Path('scripts/research/us_directional_hierarchy_diagnostic.py').read_text()
    assert 'get_sqlalchemy_engine' not in source
    assert 'requests.' not in source
    assert 'subprocess.' not in source
