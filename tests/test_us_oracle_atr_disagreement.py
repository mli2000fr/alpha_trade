import numpy as np
import pandas as pd

from scripts.research.us_oracle_atr_disagreement import classify, matched


def test_groups_partition_and_labels_do_not_affect_gates():
    frame=pd.DataFrame({'date':pd.Timestamp('2025-01-02'),'symbol':[str(i) for i in range(100)],
                        'proba_extreme':np.arange(100),'atr20_pct':np.roll(np.arange(100),10),
                        'rolling_volatility_60':np.arange(100),'oracle_decile':1})
    first,excluded=classify(frame)
    assert excluded==0
    assert set(first.cohort)=={'BOTH','ATR_ONLY','ORACLE_ONLY','NEITHER'}
    assert first.cohort.value_counts().sum()==100
    frame.oracle_decile=10
    second,_=classify(frame)
    assert first.cohort.tolist()==second.cohort.tolist()


def test_matching_support_and_expected_contrast():
    frame=pd.DataFrame({'date':[pd.Timestamp('2025-01-02')]*10,'atr_bin':10,'vol_bin':3,
                        'cohort':['BOTH']*5+['ATR_ONLY']*5,'target_quality_valid':1,
                        'oracle_decile':[10]*5+[5]*5,'oracle_extreme10':[1]*5+[0]*5,
                        'future_return':[.2]*5+[.01]*5,'extreme_gate':[True]*5+[False]*5})
    result=matched(frame)
    row=result[result.comparison.eq('WITHIN_ATR_TOP20')].iloc[0]
    assert row.extreme==1
    assert abs(row.future_return-.19)<1e-10
    assert row.supported_rows==10
    assert matched(frame.iloc[:-1]).empty
