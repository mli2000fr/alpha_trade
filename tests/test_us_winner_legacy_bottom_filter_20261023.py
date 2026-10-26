import numpy as np
import pandas as pd
import pytest
from scripts.research import us_winner_legacy_bottom_filter_20261023 as s


def frame():
    return pd.DataFrame([dict(date=pd.Timestamp('2025-01-02'),symbol=f'S{i}',rank=i,
        vol_ratio_20_60=11-i,J_qualified=True) for i in range(1,11)])


def test_only_bottom_three_or_five_are_vetoed():
    a=s.frozen_filter(frame())
    assert a.loc[a.DROP_BOTTOM3_KEEP7,'rank'].tolist()==list(range(4,11))
    assert a.loc[a.DROP_BOTTOM5_KEEP5,'rank'].tolist()==list(range(6,11))
    assert a.WINNER_LEGACY_ONLY.all()


def test_one_unknown_means_passthrough_not_arbitrary_loser():
    a=frame();a.loc[0,'vol_ratio_20_60']=np.nan
    b=s.frozen_filter(a)
    assert b[list(s.ARMS)].all().all()
    assert not b.all_ten_known.any()


def test_future_outcome_never_enters_filter():
    a=frame();b=s.frozen_filter(a)
    a['future_return']=np.arange(10)*100;a['entry_index']=999
    pd.testing.assert_frame_equal(b,s.frozen_filter(a))


def test_frozen_tape_only_initial_attempts_change():
    a={'starts':{1:[4,5],2:[6]},'bytime':object(),'bypair':object(),'timeline':object(),'meta':object()}
    b=s.veto_tape(a,{5})
    assert b['starts']=={1:[5],2:[]}
    assert a['starts']=={1:[4,5],2:[6]}
    for k in ('bytime','bypair','timeline','meta'):assert b[k] is a[k]


def test_original_rank_ties_and_complete_top10():
    a=frame();a.vol_ratio_20_60=1
    b=s.frozen_filter(a)
    assert b.loc[b.DROP_BOTTOM3_KEEP7,'rank'].tolist()==list(range(1,8))
    with pytest.raises(ValueError):s.frozen_filter(a.iloc[:9])
