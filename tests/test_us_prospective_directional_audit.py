"""Tests of the descriptive audit; no database or provider access."""
import numpy as np
import pandas as pd
import pytest

from scripts.research.us_prospective_directional_check import directional_metrics, local_day


def fixture_frame():
    rows = []
    for day in pd.to_datetime(["2026-09-15", "2026-09-16"]):
        for i in range(20):
            decile = 1 if i < 10 else 10
            rows.append({"entry_date":day,"symbol":str(i),"future_return":-.1 if decile==1 else .1,
                         "decile":decile,"feature":float(decile==10)})
    return pd.DataFrame(rows)


def test_dates_are_new_york_days_not_utc_days():
    result=local_day(pd.Series(["2026-09-15 02:00:00", "2026-09-15 14:00:00"]))
    assert result.tolist()==list(pd.to_datetime(["2026-09-14","2026-09-15"]))


def test_perfect_separation_is_descriptive_not_promoted():
    result=directional_metrics(fixture_frame(),"feature")
    assert result["samples"]==40
    assert result["auc_pooled_exploratory"]==pytest.approx(1.)
    assert result["mean_daily_auc"]==pytest.approx(1.)
    assert [row["auc"] for row in result["chronological_halves"]]==[1.,1.]
    assert result["verdict"]=="INSUFFICIENT_PROSPECTIVE_HISTORY_NO_PROMOTION"


def test_absent_values_do_not_become_zero_or_a_signal():
    data=fixture_frame()
    data["feature"]=np.nan
    result=directional_metrics(data,"feature")
    assert result["samples"]==0
    assert result["auc_pooled_exploratory"] is None
    assert result["daily_auc"]==[]


def test_orientation_not_selected_after_observing_outcomes():
    data=fixture_frame()
    data["feature"]=-data.feature
    assert directional_metrics(data,"feature")["auc_pooled_exploratory"]==pytest.approx(0.)


def test_non_extremes_are_not_relabelled_inside_feature_cohort():
    data=fixture_frame()
    data.loc[:9,"decile"]=5
    result=directional_metrics(data,"feature")
    assert result["samples"]==40
    assert result["extreme_samples"]==30
    assert result["d1_count"]==10
