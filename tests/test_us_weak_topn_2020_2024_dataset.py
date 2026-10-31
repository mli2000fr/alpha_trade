import numpy as np
import pandas as pd
import pytest

from scripts.research.us_weak_topn_2020_2024_dataset import (
    freeze_top,validate_top,causal_spec,missing_sessions,normalize_prices,
)


def test_top_membership_ignores_future_labels_and_ties_are_deterministic():
    frame=pd.DataFrame(dict(date=['2023-07-10']*3,symbol=['C','B','A'],score_lightgbm=[.8,.9,.9],future=[100,0,-100]))
    top=freeze_top(frame,2)
    assert list(top.symbol)==['A','B'] and list(top.oracle_rank)==[1,2]
    assert 'future' not in top


def test_missing_first_candidate_is_not_replaced_by_lower_rank():
    frame=pd.DataFrame(dict(date=['2023-07-10']*3,symbol=['A','B','C'],score_lightgbm=[.9,.8,.7]))
    top=freeze_top(frame,2)
    with pytest.raises(ValueError,match='complete TOP'):
        validate_top(top.loc[top.symbol.ne('A')],2)


@pytest.mark.parametrize('value',[np.nan,np.inf,1.1,-.1])
def test_invalid_scores_never_enter_top(value):
    frame=pd.DataFrame(dict(date=['2023-07-10'],symbol=['A'],score_lightgbm=[value]))
    with pytest.raises(ValueError):freeze_top(frame,1)


def test_gap_is_based_on_official_calendar_not_calendar_days():
    frame=pd.DataFrame(dict(date=pd.to_datetime(['2023-07-07','2023-07-11'])))
    calendar=pd.to_datetime(['2023-07-07','2023-07-10','2023-07-11'])
    assert list(missing_sessions(frame,calendar,2023))==[pd.Timestamp('2023-07-10')]


def test_frozen_extension_accepts_only_causal_training_and_validation():
    done=dict(metrics=dict(test_start='2023-01-05',test_end='2023-07-07',
        train_available_max='2022-07-06',val_available_max='2023-01-04'))
    assert causal_spec('2023-01-05',done,'2023-07-10')['original_test_end']=='2023-07-07'
    bad=dict(metrics={**done['metrics'],'val_available_max':'2023-07-10'})
    with pytest.raises(ValueError):causal_spec('2023-01-05',bad,'2023-07-10')
    with pytest.raises(ValueError):causal_spec('2023-01-05',done,'2022-12-30')


def test_adjustment_is_applied_once_and_lineage_is_retained():
    raw=pd.DataFrame(dict(date=['2023-07-10'],symbol=['A'],open=[20.],high=[22.],low=[18.],close=[20.],
        adj_close=[10.],volume=[100],instrument_id=['42'],data_source=['SIP'],data_adjustment=['raw']))
    result=normalize_prices(raw)
    assert result.open.iloc[0]==10 and result.close.iloc[0]==10 and result.adj_close.iloc[0]==10
    again=normalize_prices(result)
    assert again.close.iloc[0]==10 and result.instrument_id.iloc[0]=='42'


def test_duplicate_prices_are_never_silently_deduplicated():
    raw=pd.DataFrame(dict(date=['2023-07-10']*2,symbol=['A']*2))
    with pytest.raises(ValueError):normalize_prices(raw)
