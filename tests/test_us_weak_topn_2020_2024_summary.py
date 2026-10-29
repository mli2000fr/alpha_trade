import pytest

from scripts.research.us_weak_topn_2020_2024_summary import weighted_auc


def test_daily_average_weights_informative_dates_not_number_of_years():
    rows=[dict(auc_daily_mean=.6,auc_daily_dates=100),dict(auc_daily_mean=.4,auc_daily_dates=200)]
    assert weighted_auc(rows)==pytest.approx(140/300)


def test_undefined_or_zero_support_auc_is_not_a_half_auc():
    rows=[dict(auc_daily_mean=None,auc_daily_dates=200),dict(auc_daily_mean=.9,auc_daily_dates=0)]
    assert weighted_auc(rows) is None
    assert weighted_auc(rows+[dict(auc_daily_mean=.53,auc_daily_dates=10)])==.53


def test_nonoverlap_uses_its_own_informative_support():
    rows=[dict(auc_daily_mean=.9,auc_daily_dates=100,auc_h_spaced_mean=.4,auc_h_spaced_dates=5),
          dict(auc_daily_mean=.1,auc_daily_dates=100,auc_h_spaced_mean=.6,auc_h_spaced_dates=15)]
    assert weighted_auc(rows,'auc_h_spaced_mean','auc_h_spaced_dates')==pytest.approx(.55)
