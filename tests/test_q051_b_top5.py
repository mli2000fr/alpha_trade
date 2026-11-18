import pandas as pd
import pytest
from scripts.research.us_q051_b_top5_20261117 import top_long_before_filter
from scripts.research.us_q051_b_early_sl_20261116 import meta_filter


def test_top5_uses_original_long_rank_not_compressed_execution_rank():
    # Rank1 was rejected by AUC upstream. Rank6 must not fill that TOP5 slot.
    f=pd.DataFrame(dict(trade_date=pd.Timestamp('2024-01-02'),symbol=list('ABCDE'),
        long_rank=[2.,3.,4.,5.,6.],rank=[1,2,3,4,5]))
    a=top_long_before_filter(f)
    assert a.symbol.tolist()==list('ABCD')
    assert a.long_rank.max()==5 and len(a)==4


def test_sl_gate_after_top5_has_no_replacement_from_rank6():
    f=pd.DataFrame(dict(trade_date=pd.Timestamp('2024-01-02'),symbol=list('ABCDEF'),
        long_rank=[1.,2.,3.,4.,5.,6.],rank=[1,2,3,4,5,6]))
    p=pd.DataFrame(dict(date=pd.Timestamp('2024-01-02'),symbol=list('ABCDEF'),SL10_risk=[.9,.1,.1,.1,.1,.1],
        SL10_threshold=.8,SL10_available='2023-12-20'))
    a=meta_filter(top_long_before_filter(f).rename(columns={'trade_date':'date'}),p,'SL10')
    assert a[a.selected].symbol.tolist()==list('BCDE')


def test_missing_original_rank_cannot_silently_use_execution_rank():
    f=pd.DataFrame(dict(trade_date=pd.Timestamp('2024-01-02'),symbol=['A'],rank=[1]))
    with pytest.raises(ValueError,match='pre-threshold'):top_long_before_filter(f)
