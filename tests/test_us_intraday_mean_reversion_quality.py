import numpy as np
import pandas as pd
from scripts.research.us_intraday_mean_reversion_quality import price_check,causal_arrays,cap_forced_open_target
from tests.test_us_intraday_mean_reversion import bars


def test_constant_scale_allowed_but_bad_ohlc_reserved():
    assert price_check([100,110,90,105],[50,55,45,52.5])[0]=='OK'
    assert price_check([100,150,90,105],[50,55,45,52.5])[0]=='DAILY_OHLC_DISAGREEMENT'
    assert price_check([100,np.nan,90,105],[50,55,45,52.5])[0]=='MISSING_OR_INVALID_REFERENCE'


def test_independent_prefix_does_not_see_future():
    f=bars([[100,101,99,100]]*12);times=pd.DatetimeIndex(f.bar_timestamp)
    a=causal_arrays(f,times)
    f=f.iloc[:-1]
    b=causal_arrays(f,times)
    np.testing.assert_array_equal(a[3][:-1],b[3][:-1])
    np.testing.assert_array_equal(a[4][:-1],b[4][:-1])
    assert np.isnan(b[3][-1]) and not b[2][-1]


def test_favorable_target_gap_at_final_open_is_also_capped():
    f=pd.DataFrame(dict(side=['LONG','SHORT'],outcome=['TIME','TIME'],entry_price=[100.,100.],
        exit_price=[103.,97.],target=[102.,98.],commission=[.002,.002],borrow=[0.,.003/365]))
    g=cap_forced_open_target(f)
    assert g.final_open_target_corrected.all()
    assert g.outcome.eq('TP').all()
    np.testing.assert_allclose(g.gross,[.02,.02])
    np.testing.assert_allclose(g.exit_price,[102.,98.])
