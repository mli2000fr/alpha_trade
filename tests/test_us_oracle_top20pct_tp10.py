import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_top20pct_tp10 as s


def scores(n=1790):
    return pd.DataFrame({'date': pd.Timestamp('2025-01-02'),
        'symbol': [f'S{i:04}' for i in range(n)], 'score': np.linspace(1, 0, n)})


def test_top20_percent_not_top20_stocks_or_top10():
    selected = s.top_fraction(scores())
    assert len(selected) == 358
    assert selected.oracle_rank.tolist() == list(range(1, 359))
    assert selected.scored_count.eq(1790).all()


def test_ceiling_and_separate_daily_denominators():
    first = scores(11)
    second = scores(26).assign(date=pd.Timestamp('2025-01-03'))
    selected = s.top_fraction(pd.concat([first, second]))
    assert selected.groupby('date').size().tolist() == [3, 6]


def test_ties_alphabetical_and_input_order_independent():
    f = scores(10).assign(score=.5)
    selected = s.top_fraction(f.sample(frac=1, random_state=18))
    assert selected.symbol.tolist() == ['S0000', 'S0001']


@pytest.mark.parametrize('bad', [np.nan, np.inf, -.01, 1.01])
def test_invalid_score_refused(bad):
    f = scores(10); f.loc[0, 'score'] = bad
    with pytest.raises(ValueError): s.top_fraction(f)


@pytest.mark.parametrize('fraction', [0, -.1, 1.1])
def test_invalid_fraction_refused(fraction):
    with pytest.raises(ValueError): s.top_fraction(scores(), fraction)


def test_duplicate_scores_refused():
    f = scores(10)
    with pytest.raises(ValueError): s.top_fraction(pd.concat([f, f.iloc[:1]]))


def test_future_path_missing_never_promotes_next_rank():
    original = scores(10)
    selection = s.top_fraction(original)
    # Highest score lacks a qualified future; rank 3 must not replace it.
    frame = original.iloc[1:].drop(columns='score').assign(side='LONG', path_return=.5)
    selected = s.restrict_paths(frame, selection)
    assert selected.symbol.tolist() == ['S0001']
    assert selected.oracle_rank.tolist() == [2]
    changed = frame.assign(path_return=-.9)
    assert s.restrict_paths(changed, selection).symbol.tolist() == selected.symbol.tolist()


def test_both_sides_identical_frozen_membership():
    original = scores(10)
    f = pd.concat([original.assign(side=side) for side in ('LONG', 'SHORT')])
    result = s.restrict_paths(f, s.top_fraction(original))
    assert len(result) == 4
    assert result.groupby('side').symbol.apply(list).tolist() == [['S0000', 'S0001']] * 2


def test_duplicate_path_or_frozen_membership_refused():
    original = scores(10); selected = s.top_fraction(original)
    f = pd.concat([original.assign(side='LONG')] * 2)
    with pytest.raises(ValueError): s.restrict_paths(f, selected)
    with pytest.raises(ValueError): s.restrict_paths(original.assign(side='LONG'), pd.concat([selected] * 2))


def stored_score():
    model = dict(universe=['A'], fold='2023-12-05', model_sha256='weight-hash',
        profile_sha256='profile-hash', available_date='2023-12-04')
    frame = pd.DataFrame([dict(date=pd.Timestamp('2024-01-02'), symbol='A', score=.8,
        fold_start=model['fold'], lineage_fold=model['fold'], model_sha256=model['model_sha256'],
        feature_profile_sha256=model['profile_sha256'], model_available_date=model['available_date'],
        target_name='oracle_path_extreme20', target_horizon=20, future_return=None, oracle_extreme10=None)])
    return frame, model


def test_stored_score_lineage_qualified():
    from scripts.research.us_news_gpt_top20_history import validate_scores
    frame, model = stored_score()
    validate_scores(frame, model)


@pytest.mark.parametrize('field,value', [('model_sha256', 'other-model'),
    ('model_available_date', '2024-01-02'), ('future_return', .2), ('target_horizon', 10)])
def test_wrong_or_future_or_labelled_stored_score_refused(field, value):
    from scripts.research.us_news_gpt_top20_history import validate_scores
    frame, model = stored_score(); frame[field] = value
    with pytest.raises(ValueError): validate_scores(frame, model)


def test_category_dictionary_does_not_change_key_equality():
    left = pd.DataFrame({'symbol': pd.Categorical(['A'], categories=['A', 'B'])})
    right = pd.DataFrame({'symbol': pd.Categorical(['A'], categories=['A'])})
    pd.testing.assert_frame_equal(left, right, check_dtype=False, check_categorical=False)
    right['symbol'] = 'B'
    with pytest.raises(AssertionError):
        pd.testing.assert_frame_equal(left, right, check_dtype=False, check_categorical=False)
