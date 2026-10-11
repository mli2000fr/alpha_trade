import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_amplitude_rerank import (
    INPUTS, eligible_training, metrics, pool, relevance, selections,
)


def sample():
    return pd.DataFrame(dict(date=pd.to_datetime(['2020-01-01']*100),
        symbol=[f'S{i:03}' for i in range(100)], score=np.arange(100),
        atr20_pct=np.arange(100), future_return=np.linspace(-1, 1, 100),
        oracle_extreme10=[1]*100, target_quality_valid=[1]*100,
        oracle_available_date=pd.to_datetime(['2020-02-01']*100)))


def test_selection_is_independent_of_future():
    frame = sample()
    expected = pool(frame).symbol.tolist()
    frame['future_return'] = np.nan
    frame['oracle_extreme10'] = np.nan
    assert pool(frame).symbol.tolist() == expected
    assert len(expected) == 20


def test_purge_strictly_before_cutoff():
    frame = sample()
    assert eligible_training(frame, pd.Timestamp('2020-02-01')).empty
    assert len(eligible_training(frame, pd.Timestamp('2020-02-02'))) == 100
    frame['target_quality_valid'] = 0
    assert eligible_training(frame, pd.Timestamp('2020-02-02')).empty


def test_target_sign_symmetric_and_no_outcomes_in_inputs():
    frame = sample()
    original = relevance(frame)
    frame['future_return'] *= -1
    pd.testing.assert_series_equal(original, relevance(frame))
    assert not {'future_return', 'oracle_decile', 'oracle_extreme10',
                'oracle_available_date', 'target_quality_valid'} & set(INPUTS)


def test_missing_selected_result_does_not_replace_symbol():
    frame = pool(sample())
    frame['amplitude_score'] = frame.score
    frame.loc[frame.symbol.eq('S099'), 'future_return'] = np.nan
    selected = selections(frame)
    for _, rows in selected.groupby(['policy', 'top_n']):
        assert 'S099' in set(rows.symbol)
    daily = metrics(selected)
    assert daily.missing.eq(1).all()
    assert not daily.full.any()
    assert daily.precision.isna().all()


def test_ties_are_deterministic():
    frame = sample()
    frame['score'], frame['atr20_pct'] = 1., 1.
    assert pool(frame.sample(frac=1, random_state=7)).symbol.tolist() == pool(frame).symbol.tolist()


def test_duplicate_keys_rejected():
    frame = sample()
    with pytest.raises(ValueError, match='Duplicate'):
        pool(pd.concat([frame, frame.iloc[:1]]))
