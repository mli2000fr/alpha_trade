import pandas as pd
from scripts.research.us_predictable_symbols_review_20261104 import check_2026, summarize


def test_holdout_check_uses_fixed_nonoverlap_phase_and_never_2025():
    a=pd.DataFrame(dict(year=[2025,2026,2026,2026,2026],session_index=[0,0,1,10,11],
        label=[0.,0.,1.,1.,0.],probability=[1.,.1,.1,.9,.9],long_threshold=.6))
    result=check_2026(a,'winner_h10')
    assert result['observations']==2 and result['auc']==1.
    assert result['long_precision']==1. and result['long_lift']==.5


def test_missing_class_never_gets_a_fabricated_auc():
    a=pd.DataFrame(dict(year=[2026,2026],session_index=[0,20],label=[1.,1.],
        probability=[.7,.8],long_threshold=.6))
    result=check_2026(a,'parcours_h20')
    assert result['auc'] is None and result['observations']==2
    s=summarize(pd.DataFrame([result]))
    assert s['with_auc']==0 and s['median_auc'] is None
