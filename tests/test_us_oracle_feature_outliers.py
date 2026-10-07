import numpy as np
import pandas as pd
from scripts.research.us_oracle_feature_outliers import diagnose_segment


def bars(close,adjusted,ids):
    return pd.DataFrame(dict(date=pd.date_range('2024-01-01',periods=len(close)),
        symbol=['X']*len(close),open=close,high=close,low=close,close=close,
        adj_close=adjusted,volume=[100]*len(close),vwap=close,
        is_filled=[0]*len(close),instrument_id=ids))


def test_adjusted_returns_not_raw_split_jump():
    result=diagnose_segment(bars([100.,50.],[50.,50.],[1,1]))
    assert result.daily_return_recomputed.iloc[1]==0
    assert result.overnight_gap_recomputed.iloc[1]==0
    assert result.raw_return.iloc[1]==-.5


def test_bad_adjusted_tiny_value_reproduced_not_silently_cleaned():
    result=diagnose_segment(bars([10.,10.],[.0001,4.55],[1,2]))
    assert np.isclose(result.daily_return_recomputed.iloc[1],45499)
    assert result.instrument_changed.iloc[1]
    assert result.previous_adj_close.iloc[1]==.0001
