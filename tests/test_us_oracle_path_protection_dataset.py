import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_path_protection_dataset as dataset


def bars(n=350):
    rng = np.random.default_rng(731)
    d = pd.bdate_range('2018-01-01', periods=n)
    close = 100*np.exp(np.cumsum(rng.normal(.0003, .01, n)))
    return pd.DataFrame(dict(date=d, symbol='ABC', open=close*.999,
        high=close*1.02, low=close*.98, close=close, adj_close=close,
        volume=1000+rng.integers(0, 1000, n), is_filled=0, instrument_id=1))


def benchmark(b):
    return pd.Series(np.linspace(100, 130, len(b)), index=b.date)


def test_j_only_prefix_invariance_all_authorized_features():
    b = bars(); spy = benchmark(b)
    full = dataset.decision_features(b, spy)
    short = dataset.decision_features(b.iloc[:280], spy.iloc[:280])
    pd.testing.assert_series_equal(full.iloc[279], short.iloc[-1], check_exact=True)
    future = b.copy(); future.loc[280:, ['open', 'high', 'low', 'close', 'adj_close']] *= 100
    pd.testing.assert_series_equal(full.iloc[279], dataset.decision_features(future, spy).iloc[279], check_exact=True)


def test_feature_allowlist_excludes_future_or_reserved_inputs():
    assert len(dataset.FEATURES) == 24
    assert len(set(dataset.FEATURES)) == 24
    assert not any(c in dataset.FEATURES for c in ['entry_price', 'label_available', 'symbol', 'date',
                                                  'score', 'selector_short_score', 'vix', 'future_return'])


def test_label_availability_purge_not_decision_only():
    assert dataset.assign_split('2021-12-01', '2022-01-01') == 'PURGED_FIT_BOUNDARY'
    assert dataset.assign_split('2021-10-01', '2021-12-31') == 'FIT_2018_2021'
    assert dataset.assign_split('2022-12-01', '2023-01-01') == 'PURGED_VALIDATION_BOUNDARY'
    assert dataset.assign_split('2022-10-01', '2022-12-30') == 'VALIDATION_2022'
    assert dataset.assign_split('2023-07-07', '2023-09-29') == 'CONTROL_2023'
    assert dataset.assign_split('2023-07-07', pd.NaT) == 'UNAVAILABLE_LABEL'


def test_ordinal_selection_ties_deterministic_before_future_labels():
    frame = pd.DataFrame(dict(date=pd.Timestamp('2019-01-02'), symbol=list('GFEDCBA'), score=.5))
    frame['bad_future'] = [False, False, False, False, False, False, True]
    selected = dataset.freeze_top5(frame)
    assert selected.symbol.tolist() == list('ABCDE')
    assert selected.oracle_rank.tolist() == [1, 2, 3, 4, 5]


@pytest.mark.parametrize('known', ['2018-07-05', '2019-01-01', None])
def test_reject_fold_that_sees_scoring_period(known):
    done = dict(metrics=dict(test_start='2018-07-05', test_end='2019-01-03',
                             train_available_max='2018-01-01', val_available_max=known))
    with pytest.raises(ValueError):
        dataset.fold_is_causal(done)


def test_accept_causal_fold():
    done = dict(metrics=dict(test_start='2018-07-05', test_end='2019-01-03',
                             train_available_max='2018-01-01', val_available_max='2018-07-03'))
    assert dataset.fold_is_causal(done)[0] == pd.Timestamp('2018-07-05')


def test_j_quality_requires_consecutive_history_and_stable_id():
    b = bars(); spy = benchmark(b); days = pd.DatetimeIndex(b.date)
    frame = b.set_index('date')
    q = dataset.j_history_quality(frame, spy, days)
    assert not q.iloc[:200].any()
    assert q.iloc[200:].all()
    changed = frame.copy(); changed.iloc[290, changed.columns.get_loc('instrument_id')] = 2
    assert not dataset.j_history_quality(changed, spy, days).iloc[300]
    filled = frame.copy(); filled.iloc[290, filled.columns.get_loc('is_filled')] = 1
    assert not dataset.j_history_quality(filled, spy, days).iloc[300]


def test_known_future_bar_cannot_change_j_quality():
    b = bars(); spy = benchmark(b); days = pd.DatetimeIndex(b.date)
    original = dataset.j_history_quality(b.set_index('date'), spy, days)
    b.loc[300:, 'volume'] = 0
    changed = dataset.j_history_quality(b.set_index('date'), spy, days)
    pd.testing.assert_series_equal(original.iloc[:300], changed.iloc[:300], check_exact=True)


def test_market_relative_feature_formula():
    b = bars(); spy = benchmark(b)
    f = dataset.decision_features(b, spy)
    expected = b.close.iloc[-1]/b.close.iloc[-21]-spy.iloc[-1]/spy.iloc[-21]
    assert f.relative_strength_20.iloc[-1] == pytest.approx(expected)


def test_annual_model_mapping_exact():
    assert dataset.ANNUAL_MODELS == {
        2024: 'model-factory-20261014113215-437ed1',
        2025: 'model-factory-20261014113226-102eca',
        2026: 'model-factory-20261014113232-bc35a7',
    }
