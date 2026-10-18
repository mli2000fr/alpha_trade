import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from catboost import CatBoostClassifier

from scripts.research.us_directional_hierarchy_diagnostic import transform_train_test
from scripts.research.us_top10_catboost_multiclass import (
    CAT, CONFIG, LINEAR, OLD, ORACLE, PROB_ARMS, RANK_ARMS,
    contrast, daily_auc, fixed_gate, ordered_probabilities, preprocess,
    primary_days, probability_metrics, ranking_metrics, selection_rows, three_classes,
)


@pytest.fixture
def cfg():
    return json.loads(CONFIG.read_text())


def sample(days=2):
    f = pd.DataFrame({'date': np.repeat(pd.bdate_range('2020-01-01', periods=days), 10),
                      'symbol': list('ABCDEFGHIJ')*days, 'oracle_rank': list(range(1, 11))*days,
                      'oracle_decile': [1., 10., 5., 1., 10., 5., 5., 5., 5., 5.]*days})
    for arm in RANK_ARMS[:-1]:
        f[arm] = np.tile(np.linspace(-.5, .5, 10), days)
    return f


def test_fixed_protocol_not_a_parameter_search(cfg):
    assert cfg['catboost']['depth'] == 3
    assert cfg['catboost']['iterations'] == 200
    assert cfg['catboost']['loss_function'] == 'MultiClass'
    assert not cfg['early_stopping'] and not cfg['hyperparameter_search']
    assert not cfg['sector_or_symbol_features'] and not cfg['catboost']['allow_writing_files']
    assert cfg['primary_selection_count'] == 3
    assert cfg['trajectory_sessions'] == [5, 10]


def test_three_classes_include_all_middle_deciles_keep_unknown():
    d = pd.Series([1., 2., 5., 9., 10., np.nan])
    result = three_classes(d)
    assert result.iloc[:5].tolist() == [0, 1, 1, 1, 2]
    assert pd.isna(result.iloc[-1])


@pytest.mark.parametrize('bad', [0, 11, 1.5, -1])
def test_invalid_global_decile_not_silently_relabelled(bad):
    with pytest.raises(ValueError):
        three_classes(pd.Series([1, bad, 10]))


def test_explicit_probability_class_order():
    result = ordered_probabilities([[.6, .1, .3]], [2, 0, 1])
    np.testing.assert_allclose(result, [[.1, .3, .6]])


@pytest.mark.parametrize('values,classes', [
    ([[.3, .3, .3]], [0, 1, 2]),
    ([[.3, .2, np.nan]], [0, 1, 2]),
    ([[.4, -.1, .7]], [0, 1, 2]),
    ([[.1, .2, .7]], [0, 0, 2]),
    ([[.3, .7]], [0, 2]),
    ([[.1, .2, .7]], [0, 1, 3]),
])
def test_invalid_probabilities_rejected_not_renormalized(values, classes):
    with pytest.raises(ValueError):
        ordered_probabilities(values, classes)


def test_contrast_penalizes_simultaneous_downside_tail():
    # First has higher P(D10), but also much more P(D1).
    p = np.array([[.35, .05, .6], [.05, .45, .5]])
    np.testing.assert_allclose(contrast(p), [.25, .45])


def test_preprocessing_matches_frozen_old_reference_and_no_test_leak(cfg):
    train = pd.DataFrame({'x': [1., 2., np.nan, 4.], 'z': [0., 1., 3., np.inf]})
    test = pd.DataFrame({'x': [1e9], 'z': [-1e9]})
    a, b, record = preprocess(train, test, ['x', 'z'], cfg)
    old_a, old_b = transform_train_test(train, test, ['x', 'z'], cfg)
    np.testing.assert_array_equal(a, old_a)
    np.testing.assert_array_equal(b, old_b)
    a2, _, record2 = preprocess(train, -test, ['x', 'z'], cfg)
    np.testing.assert_array_equal(a, a2)
    assert record == record2


def test_shortlist_frozen_before_unknown_outcomes_no_rank11():
    f = sample(1)
    f.loc[f.oracle_rank.ge(8), 'oracle_decile'] = [5., np.nan, 1.]
    rows = selection_rows(f, [3])
    cat = rows.loc[rows.arm.eq(CAT)].iloc[0]
    assert cat.selected_count == 3 and cat.known_count == 2
    assert cat.d1 == .5 and not cat.complete_ten_labels


def test_primary_mask_never_changes_ranking_or_shortlist():
    f = sample(1)
    before = selection_rows(f, [3])
    f.loc[0, 'oracle_decile'] = np.nan
    after = selection_rows(f, [3])
    assert not primary_days(f).any()
    a, b = before.loc[before.arm.eq(CAT)].iloc[0], after.loc[after.arm.eq(CAT)].iloc[0]
    assert a.d1_count == b.d1_count and a.d10_count == b.d10_count
    assert a.selected_count == b.selected_count == 3


def test_all_ten_and_original_order_are_valid_references():
    f = sample()
    rows = selection_rows(f, [3, 5, 10])
    all_ten = rows.loc[rows.selection_count.eq(10)]
    assert all_ten.d1.eq(.2).all() and all_ten.d10.eq(.2).all()
    original = rows.loc[rows.selection_count.eq(3) & rows.arm.eq(ORACLE)]
    assert original.d1_count.eq(1).all() and original.d10_count.eq(1).all()


def test_rank_ties_break_using_original_oracle_order():
    f = sample(1)
    f[CAT] = 0.
    rows = selection_rows(f, [3])
    cat = rows.loc[rows.arm.eq(CAT)].iloc[0]
    oracle = rows.loc[rows.arm.eq(ORACLE)].iloc[0]
    assert cat.d1_count == oracle.d1_count and cat.d10_count == oracle.d10_count


@pytest.mark.parametrize('count', [0, 11, True, 3.5])
def test_illegal_selection_size_fails_closed(count):
    with pytest.raises(ValueError):
        selection_rows(sample(), [count])


def test_multiclass_brier_not_binary_and_unknowns_not_errors():
    f = sample(1)
    f.loc[0, 'oracle_decile'] = np.nan
    p = np.array([.2, .5, .3])
    for arm in PROB_ARMS:
        for i, label in enumerate(['d1', 'middle', 'd10']):
            f[f'{arm}_p_{label}'] = p[i]
    rows = probability_metrics(f)
    known = f.oracle_decile.dropna()
    expected = ((np.eye(3)[three_classes(known).to_numpy(int)]-p)**2).sum(axis=1).mean()
    assert np.allclose(rows.brier3, expected)
    assert rows.logloss3.notna().all()


def test_auc_date_weighting_and_sparse_dates():
    dates = pd.to_datetime(['2020-01-01']*4+['2020-01-02']*4)
    y = [0., 0., 1., 1., 0., 0., 1., np.nan]
    score = [.1, .1, .1, .1, .9, .9, .9, .9]
    result = daily_auc(y, score, dates)
    assert result.iloc[0] == .5 and pd.isna(result.iloc[1])


def test_ranking_metrics_do_not_drop_middle_candidates_before_selection():
    f = sample()
    result = ranking_metrics(f)
    assert set(result.arm) == set(RANK_ARMS)
    assert result.complete_ten_labels.all()
    assert result.auc_d10_rest.notna().all()


def test_fixed_gate_requires_gain_over_old_and_equivalent_multiclass(cfg):
    row = dict(auc_d10_rest=.56, auc_gain_vs_linear=.02, brier_gain_vs_linear=.01,
               d10_lift_vs_oracle=.05, d1_lift_vs_oracle=-.01, d10_lift_vs_old=.03,
               d10_lift_vs_linear=.02, auc_dates=100)
    assert fixed_gate(row, cfg)
    assert not fixed_gate({**row, 'd10_lift_vs_old': -.01}, cfg)
    assert not fixed_gate({**row, 'brier_gain_vs_linear': -.01}, cfg)
    assert not fixed_gate({**row, 'd1_lift_vs_oracle': .01}, cfg)


def test_small_real_catboost_three_classes_and_no_output_directory(tmp_path):
    x = np.random.default_rng(1).normal(size=(60, 3))
    y = np.tile([0, 1, 2], 20)
    model = CatBoostClassifier(iterations=3, depth=2, loss_function='MultiClass',
                               classes_count=3, thread_count=1, random_seed=1,
                               allow_writing_files=False, verbose=False, train_dir=str(tmp_path/'not_created'))
    model.fit(x, y)
    p = ordered_probabilities(model.predict_proba(x[:4]), model.classes_)
    assert p.shape == (4, 3) and model.tree_count_ == 3
    assert not (tmp_path/'not_created').exists()


def test_no_live_sql_or_provider_path():
    code = Path('scripts/research/us_top10_catboost_multiclass.py').read_text()
    for forbidden in ('get_sqlalchemy_engine', 'requests.', 'subprocess.', 'execute_approved'):
        assert forbidden not in code
