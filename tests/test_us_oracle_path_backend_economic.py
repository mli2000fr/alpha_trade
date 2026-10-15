import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_path_backend_economic import freeze_top5,BACKENDS,MODEL_NAMES


def test_two_archived_backends_and_fixed_model_file_names():
    assert BACKENDS==('lightgbm','catboost')
    assert MODEL_NAMES=={'lightgbm':'path_model.txt','catboost':'catboost_model.cbm'}


def test_top5_uses_full_pool_rank_and_symbol_tie_break_not_future_return():
    matrix=pd.DataFrame({'date':['2025-01-02']*7,'symbol':['G','F','E','D','C','B','A'],
        'future_return':[999,888,777,666,555,444,333]})
    scores=freeze_top5(matrix,[.1,.2,.3,.4,.8,.8,.8],year=2025,backend='catboost',fold='2024-12-05')
    assert list(scores.symbol)==['A','B','C','D','E']
    assert list(scores.oracle_rank)==[1,2,3,4,5]
    assert scores.proba_extreme.iloc[0]==pytest.approx(6/7)
    assert 'future_return' not in scores
    altered=matrix.copy();altered['future_return']=-altered.future_return
    pd.testing.assert_frame_equal(scores,freeze_top5(altered,[.1,.2,.3,.4,.8,.8,.8],
        year=2025,backend='catboost',fold='2024-12-05'))


def test_future_date_scores_do_not_change_today_selection():
    matrix=pd.DataFrame({'date':['2025-01-02']*6,'symbol':list('ABCDEF')})
    values=np.arange(6)/10
    initial=freeze_top5(matrix,values,year=2025,backend='lightgbm',fold='2024-12-05')
    both=pd.concat([matrix,matrix.assign(date='2025-01-03')],ignore_index=True)
    out=freeze_top5(both,np.r_[values,1-values],year=2025,backend='lightgbm',fold='2024-12-05')
    pd.testing.assert_frame_equal(initial,out[out.date.eq('2025-01-02')])


@pytest.mark.parametrize('values',[[.1,np.nan],[.1,np.inf],[.1,1.1],[-.01,.1],[.1]])
def test_invalid_probabilities_fail_closed(values):
    matrix=pd.DataFrame({'date':['2025-01-02']*2,'symbol':['A','B']})
    with pytest.raises(ValueError,match='Invalid'):
        freeze_top5(matrix,values,year=2025,backend='lightgbm',fold='2024-12-05')


def test_duplicate_candidate_key_rejected():
    matrix=pd.DataFrame({'date':['2025-01-02']*2,'symbol':['A','A']})
    with pytest.raises(ValueError,match='Duplicate'):
        freeze_top5(matrix,[.1,.2],year=2025,backend='lightgbm',fold='2024-12-05')
