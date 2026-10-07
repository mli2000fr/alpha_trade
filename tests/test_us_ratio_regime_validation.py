import numpy as np
import pandas as pd

from scripts.research.us_ratio_regime_validation import prepare, training_mask, block_ci


def fixture():
    days=pd.bdate_range('2022-12-01',periods=40)
    raw=pd.DataFrame({'trade_date':days,'vix':np.arange(40)+15.,'vix3m':30.,
        'sentiment_score':.1,'regime_mode':'normal','d1_count':10,'d10_count':20,
        'unknown_count':0,'evaluated_count':100})
    maturity=pd.DataFrame({'trade_date':days,'label_mature_at':days+pd.Timedelta(days=30)})
    return raw,maturity


def test_lag_and_purge():
    raw,maturity=fixture()
    frame=prepare(raw,maturity)
    assert frame.loc[6,'vix_lag1']==raw.loc[5,'vix']
    assert frame.loc[6,'tail_share']==2/3
    mask=training_mask(frame,pd.Timestamp('2023-01-15'))
    assert frame.loc[mask,'label_mature_at'].lt('2023-01-15').all()
    assert frame.loc[mask,'trade_date'].lt('2023-01-15').all()


def test_unknown_labels_excluded_zero_d1_retained():
    raw,maturity=fixture()
    raw.loc[10,'unknown_count']=1
    raw.loc[11,'d1_count']=0
    frame=prepare(raw,maturity)
    assert not frame.loc[10,'eligible']
    assert frame.loc[11,'eligible']
    assert frame.loc[11,'tail_share']==1


def test_future_macro_cannot_change_past_features():
    raw,maturity=fixture()
    initial=prepare(raw,maturity)
    raw.loc[20:,'vix']=1000
    changed=prepare(raw,maturity)
    pd.testing.assert_frame_equal(initial.loc[:20],changed.loc[:20].assign(
        vix=initial.loc[:20,'vix'],term=initial.loc[:20,'term'],vix_change5=initial.loc[:20,'vix_change5']))


def test_bootstrap_deterministic():
    a=block_ci(np.arange(50)/100)
    assert a==block_ci(np.arange(50)/100)
    assert a[0]<=.245<=a[1]
