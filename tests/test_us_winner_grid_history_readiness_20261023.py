import pytest
import pandas as pd
from scripts.research.us_winner_grid_history_readiness_20261023 import causal_fold,year_counts


def test_same_day_model_availability_is_not_causal():
    m=dict(test_start='2017-06-02',train_available_max='2016-11-29',val_available_max='2017-06-01')
    assert causal_fold(m)
    assert not causal_fold(dict(m,val_available_max='2017-06-02'))
    assert not causal_fold(dict(m,train_available_max='2018-01-01'))


def test_empty_2016_is_not_invented_by_annual_summary():
    rows=year_counts(pd.to_datetime(['2017-06-02','2017-06-02','2018-01-02']))
    assert [x['year'] for x in rows]==[2017,2018]
    assert rows[0]['first']=='2017-06-02' and rows[0]['score_rows']==2 and rows[0]['dates']==1
