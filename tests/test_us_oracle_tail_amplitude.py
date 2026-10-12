import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_tail_amplitude import tail_target,tail_score,select,paired_summary
from scripts.research.us_oracle_amplitude_rerank import metrics,pool
from tests.test_us_oracle_amplitude_rerank import sample


def test_threshold_inclusive_and_symmetric():
    assert tail_target([-.2,.2,-.199,.199,0,.5]).tolist()==[True,True,False,False,False,True]
    with pytest.raises(ValueError):
        tail_target([np.nan])


def test_tail_contribution_not_direction_or_full_mean():
    np.testing.assert_allclose(tail_score([.5,.9,0],[.4,.1,2]),[.2,.18,0])
    with pytest.raises(ValueError):
        tail_score([1.1],[.3])
    with pytest.raises(ValueError):
        tail_score([.5],[np.nan])


def test_select_never_uses_future_or_replaces_missing():
    frame=pool(sample())
    frame['tail_score']=frame.score
    chosen=select(frame)
    frame['future_return']=np.nan
    unknown=select(frame)
    pd.testing.assert_frame_equal(chosen[['symbol','policy','top_n']],unknown[['symbol','policy','top_n']])
    assert metrics(unknown).full.eq(False).all()


def test_reject_unpaired_policies():
    frame=pool(sample())
    frame['tail_score']=frame.score
    daily=metrics(select(frame))
    daily['source'],daily['year'],daily['block']='historical_oof',2020,'block'
    with pytest.raises(ValueError,match='Unpaired'):
        paired_summary(daily[daily.policy.ne('ATR')])


def test_no_go_when_identical_scores():
    frame=pool(sample())
    frame['tail_score']=frame.score
    daily=metrics(select(frame))
    parts=[]
    for source,year in [('historical_oof',2020),('external_frozen',2025),('external_frozen',2026)]:
        part=daily.copy()
        part['date']=pd.to_datetime(f'{year}-01-01')
        part['source'],part['year'],part['block']=source,year,str(year)
        parts.append(part)
    _,_,report=paired_summary(pd.concat(parts,ignore_index=True))
    assert set(report['verdicts'].values())=={'NO_GO_STABLE_TAIL_RERANK'}
