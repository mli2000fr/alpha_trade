import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_numeric_top10 import (
    POLICIES, daily_metrics, paired_deltas, select_top10, validate_predictions,
)


def predictions(n=100):
    return pd.DataFrame({
        'date': [pd.Timestamp('2025-01-02')] * n,
        'symbol': [f'S{i:03d}' for i in range(n)],
        'score': np.arange(n, 0, -1, dtype=float),
        'atr20_pct': np.arange(n, 0, -1, dtype=float) / 100,
        'fold_start': ['2024-01-08'] * n,
        'oracle_extreme10': [1] * n,
        'oracle_decile': [10] * n,
        'future_return': np.linspace(-.5, .5, n),
    })


def symbols(selected, policy):
    return selected.loc[selected.policy.eq(policy), 'symbol'].tolist()


def test_ten_titles_not_ten_percent_and_no_future_sort():
    frame = predictions(200)
    selected = select_top10(frame)
    assert selected.groupby('policy').size().to_dict() == dict.fromkeys(POLICIES, 10)
    assert symbols(selected, POLICIES[0]) == [f'S{i:03d}' for i in range(10)]
    assert selected.loc[selected.policy.eq(POLICIES[0]), 'future_return'].lt(0).all()


def test_future_outcomes_cannot_change_selection():
    frame = predictions()
    original = select_top10(frame)[['date', 'symbol', 'policy', 'selection_rank']]
    frame['future_return'] = np.nan
    frame['oracle_decile'] = 1
    frame['oracle_extreme10'] = 0
    pd.testing.assert_frame_equal(original, select_top10(frame)[original.columns])


def test_missing_outcome_is_not_replaced_by_next_symbol():
    frame = predictions()
    frame.loc[0, 'future_return'] = np.nan
    selected = select_top10(frame)
    assert symbols(selected, POLICIES[0])[0] == 'S000'
    daily = daily_metrics(selected).set_index('policy')
    assert daily.loc[POLICIES[0], 'evaluated'] == 9
    assert daily.loc[POLICIES[0], 'missing'] == 1


def test_intersection_uses_full_top20_then_oracle_score():
    frame = predictions()
    # The first five Oracle titles fail the ATR gate; the next 15 pass it.
    frame.loc[:4, 'atr20_pct'] = .001
    frame.loc[5:19, 'atr20_pct'] = 10
    selected = select_top10(frame)
    assert symbols(selected, POLICIES[1]) == [f'S{i:03d}' for i in range(5, 15)]
    intersect = selected[selected.policy.eq(POLICIES[1])]
    assert intersect.oracle_rank.tolist() == list(range(6, 16))
    assert intersect.selection_rank.tolist() == list(range(1, 11))


def test_atr_baseline_does_not_depend_on_oracle_score():
    frame = predictions()
    first = symbols(select_top10(frame), POLICIES[2])
    frame['score'] = frame.score.iloc[::-1].to_numpy()
    assert symbols(select_top10(frame), POLICIES[2]) == first


def test_ties_are_deterministic():
    frame = predictions()
    frame['score'] = 1.
    frame['atr20_pct'] = 1.
    shuffled = select_top10(frame.sample(frac=1, random_state=42))
    for policy in POLICIES:
        assert symbols(shuffled, policy) == [f'S{i:03d}' for i in range(10)]


@pytest.mark.parametrize('column', ['score', 'atr20_pct'])
def test_invalid_observables_rejected(column):
    frame = predictions()
    frame.loc[0, column] = np.inf
    with pytest.raises(ValueError, match='Nonfinite'):
        validate_predictions(frame)


def test_duplicate_keys_rejected():
    frame = predictions()
    with pytest.raises(ValueError, match='Duplicate'):
        validate_predictions(pd.concat([frame, frame.iloc[:1]]))


def test_rate_boundaries_and_negative_returns():
    frame = predictions()
    frame.loc[:9, 'future_return'] = [.5, -.5, .2, -.2, 0, .1, -.1, .01, -.01, 0]
    daily = daily_metrics(select_top10(frame)).set_index('policy')
    row = daily.loc[POLICIES[0]]
    assert row.positive_rate == .4
    assert row.negative_rate == .4
    assert row.abs_ge20_rate == .4
    assert row.abs_ge50_rate == .2
    assert row.gain_ge50_rate == .1
    assert row.loss_ge50_rate == .1


def test_identical_predictions_have_zero_paired_deltas():
    daily = daily_metrics(select_top10(predictions()))
    result = paired_deltas(daily, daily)
    assert len(result) == 18
    assert all(row['delta_times100'] == 0 for row in result)
    assert all(row['descriptive_block20_ci_times100'] == [0, 0] for row in result)


def test_unpaired_dates_rejected():
    daily = daily_metrics(select_top10(predictions()))
    other = daily.copy()
    other['date'] += pd.Timedelta(days=1)
    with pytest.raises(ValueError, match='Unpaired'):
        paired_deltas(daily, other)
