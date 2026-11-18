import numpy as np
import pandas as pd

from scripts.research.us_q051_winrate_recovery_audit_20261117 import mature_rates,rate_switch,first_confirmed


def test_unknown_outcomes_are_neither_losses_nor_free_support():
    days=pd.bdate_range('2021-01-01',periods=180)
    a=pd.DataFrame({'available':np.repeat(days,10),'outcome':np.resize([1.,0.],1800)})
    r=mature_rates(a,days);assert r.iloc[-1].recent_rate==.5
    a.loc[a.available.ge(days[160]),'outcome']=np.nan
    missing=mature_rates(a,days)
    assert not missing.iloc[-1].qualified and pd.isna(missing.iloc[-1].recent_rate)
    prefix=mature_rates(a[a.available.le(days[150])],days[:151])
    pd.testing.assert_frame_equal(prefix,missing.iloc[:151])


def test_switch_freezes_reference_before_recovery_and_ignores_future():
    days=pd.bdate_range('2023-01-02',periods=12)
    r=pd.DataFrame({'qualified':True,'recent_rate':[.4]*3+[.47]*5+[.2]*4,
        'reference_rate':[.5]*3+[.2]*9},index=days)
    s=rate_switch(r)
    assert s.iloc[2].transition=='ON' and s.iloc[2].anchor==.5
    assert s.iloc[7].active # .47 does not reach frozen .50-.02
    r.loc[days[3:8],'recent_rate']=.49;s=rate_switch(r)
    assert s.iloc[7].transition=='OFF'
    pd.testing.assert_frame_equal(s.iloc[:8],rate_switch(r.iloc[:8]))


def test_recovery_confirmation_needs_five_known_consecutive_dates_after_on():
    days=pd.bdate_range('2024-01-02',periods=12)
    s=pd.Series([True]*3+[pd.NA]+[True]*8,index=days,dtype='boolean')
    assert first_confirmed(s,days[0])==days[8]
    assert pd.isna(first_confirmed(s,days[0],max_sessions=5))
