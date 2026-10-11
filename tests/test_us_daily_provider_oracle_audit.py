import numpy as np
import pandas as pd
from scripts.research.us_daily_provider_oracle_audit import frame,model_frame,price_comparison,score_comparison


def test_split_units_and_utc_daily_date():
    splits=[dict(date='2025-01-03',split='2/1')]
    e=frame([dict(date='2025-01-02',open=100,high=104,low=98,close=102,volume=2000)],'ABC','eodhd',splits)
    a=frame([dict(t='2025-01-02T05:00:00Z',o=100,h=104,l=98,c=102,v=1000,vw=101)],'ABC','iex',splits)
    assert a.date.iloc[0]==pd.Timestamp('2025-01-02')
    assert model_frame(e).close.iloc[0]==51
    assert model_frame(e).volume.iloc[0]==model_frame(a).volume.iloc[0]==2000


def test_price_comparison_excludes_unmatched_dates():
    rows=[dict(date='2025-01-02',open=100,high=100,low=100,close=100,volume=100)]
    e=frame(rows,'ABC','eodhd',[])
    a=e.copy();a['close']=101
    metrics,_=price_comparison(e,a)
    assert np.isclose(metrics['close_absolute_bps']['median'],100)
    assert metrics['matched_days']==1


def test_score_ranking_and_probability_changes():
    base=pd.DataFrame(dict(date=[pd.Timestamp('2025-01-02')]*5,symbol=list('ABCDE'),score=[.9,.8,.7,.6,.5]))
    other=base.copy();other['score']=[.8,.9,.7,.6,.5]
    result=score_comparison(base,other)
    assert result['mean_top20_overlap']==0
    assert np.isclose(result['absolute_probability_change']['maximum'],.1)


def test_duplicate_provider_dates_rejected():
    import pytest
    row=dict(date='2025-01-02',open=100,high=100,low=100,close=100,volume=100)
    with pytest.raises(ValueError,match='Duplicate'):
        frame([row,row],'ABC','eodhd',[])
