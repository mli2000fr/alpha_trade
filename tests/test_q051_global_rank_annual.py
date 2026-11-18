import numpy as np
import pandas as pd
from scripts.research.us_q051_global_rank_h10_20261115 import exact_session_targets,chronological_split,label_deciles


def test_exact_horizon_does_not_shift_over_missing_session():
    days=pd.bdate_range('2020-01-01',periods=25)
    f=pd.DataFrame(dict(date=days,symbol='A',close=np.arange(25)+100.,rolling_volatility_20=.02))
    f=f[f.date.ne(days[10])]
    out=exact_session_targets(f,days).set_index('date')
    assert pd.isna(out.loc[days[0],'scaled_return'])
    assert out.loc[days[1],'label_available_date']==days[11]
    assert np.isclose(out.loc[days[1],'raw_return'],111/101-1)


def test_target_rejects_security_identity_crossing():
    from modelFactory.oracle.security_continuity import SecurityDiscontinuity
    days=pd.bdate_range('2020-01-01',periods=25)
    f=pd.DataFrame(dict(date=days,symbol='A',close=100.,rolling_volatility_20=.02))
    event=SecurityDiscontinuity('A',days[5],days[6],'new company')
    out=exact_session_targets(f,days,breaks={'A':(event,)})
    assert out.loc[out.date.eq(days[0]),'scaled_return'].isna().all()
    assert out.loc[out.date.eq(days[6]),'scaled_return'].notna().all()


def test_validation_is_purged_and_model_precedes_first_signal():
    days=pd.bdate_range('2018-01-01',periods=600)
    f=pd.DataFrame(dict(date=days[:-10],label_available_date=days[10:]))
    fit,val,cutoff=chronological_split(f,days[-1],days)
    assert cutoff<days[-1]
    assert fit.label_available_date.max()<val.date.min()
    assert val.label_available_date.max()<=cutoff
    assert val.date.nunique()==126
    assert not set(fit.date)&set(val.date)


def test_cross_section_deciles_do_not_depend_on_other_dates():
    f=pd.DataFrame(dict(date=np.repeat(pd.to_datetime(['2020-01-01','2020-01-02']),100),scaled_return=np.tile(np.arange(100),2)))
    a=label_deciles(f)
    f.loc[f.date.eq(pd.Timestamp('2020-01-02')),'scaled_return']*=-100
    b=label_deciles(f)
    assert a.label.between(0,9).all()
    pd.testing.assert_series_equal(a.loc[:99,'label'],b.loc[:99,'label'])
