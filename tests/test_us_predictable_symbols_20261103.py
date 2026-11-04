import numpy as np
import pandas as pd

from scripts.research.us_predictable_symbols_20261103 import path_labels, winner_labels, split, reliability
from scripts.research.us_winner_per_symbol_long_20261103 import long_labels


def bars(n=80):
    days=pd.bdate_range('2020-01-01',periods=n)
    close=100*np.exp(np.cumsum(np.random.default_rng(1).normal(.001,.02,n)))
    a=pd.DataFrame(dict(date=days,open=close,high=close*1.02,low=close*.98,close=close,
        adj_close=close,volume=1000.,is_filled=0,instrument_id=1,data_source='alpaca_sip'))
    return a,days


def test_vectorized_sl_gaps_fees_and_expiry_match_existing_reference():
    a,days=bars()
    a.loc[8,['open','high','low','close','adj_close']]*=.7
    expected=long_labels(a,days,horizon=10,stop=.05,fee=.0008)
    actual=winner_labels(a,days,fee=.0008)
    pd.testing.assert_frame_equal(actual.reset_index(drop=True),expected.reset_index(drop=True),check_like=True)


def test_missing_or_unidentified_held_bars_are_unknown_not_losses_or_wins():
    a,days=bars()
    a.loc[5,'instrument_id']=np.nan
    assert days[0] not in set(winner_labels(a,days,fee=.0008).date)
    assert days[0] not in set(path_labels(a,days).date)
    assert days[6] in set(path_labels(a,days).date)


def test_path_keeps_both_peaks_and_does_not_conflate_order_with_direction():
    a,days=bars(45)
    a[['open','high','low','close','adj_close']]=100.
    a.loc[4,'high']=122.
    a.loc[9,'low']=69.
    row=path_labels(a,days).iloc[0]
    assert np.isclose(row.max_up_pct,22) and np.isclose(row.max_down_pct,-31)
    assert row.label==0 and row.first_peak=='UP'
    assert row.up_peak_session==4 and row.down_peak_session==9


def test_daily_same_session_order_remains_unknown():
    a,days=bars(45)
    a[['open','high','low','close','adj_close']]=100.
    a.loc[3,'high']=130.;a.loc[3,'low']=70.
    row=path_labels(a,days).iloc[0]
    assert pd.isna(row.label) and row.first_peak=='SAME_SESSION_ORDER_UNKNOWN'


def test_fit_calibration_and_test_are_purged_by_label_maturity():
    panel=pd.DataFrame(dict(date=pd.to_datetime(['2020-12-20','2021-12-20','2022-01-05','2022-12-20','2023-01-05']),
        label_available_date=pd.to_datetime(['2021-01-10','2022-01-10','2022-02-01','2023-01-10','2023-02-01']),label=1.))
    fit,cal,test=split(panel,2023)
    assert fit.date.tolist()==[pd.Timestamp('2020-12-20')]
    assert cal.date.tolist()==[pd.Timestamp('2022-01-05')]
    assert test.date.tolist()==[pd.Timestamp('2023-01-05')]


def test_2026_never_changes_the_historical_reliability_rank():
    dates=pd.bdate_range('2023-01-01','2026-01-31')
    y=(np.arange(len(dates))%3==0).astype(float)
    f=pd.DataFrame(dict(date=dates,year=dates.year,label=y,probability=.2+.6*y,
        long_threshold=.6,baseline_probability=.33,session_index=np.arange(len(dates))))
    a=reliability(f,'winner_h10')
    f.loc[f.year.eq(2026),'label']=1-f.loc[f.year.eq(2026),'label']
    b=reliability(f,'winner_h10')
    for key in ['qualified_history','long_lift_conservative_bound','worst_annual_auc','n_independent']:
        assert a[key]==b[key]
    assert a['check_2026']!=b['check_2026']
