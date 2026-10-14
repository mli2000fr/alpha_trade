import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_path_stop_recovery import bucket, recovery_path, nonoverlapping


def resolve(rows, exit_index=0):
    dates = pd.bdate_range('2024-01-02', periods=len(rows))
    return recovery_path(np.asarray(rows, float), dates, dates[exit_index], 100.)


def test_exit_day_high_is_never_a_post_stop_recovery():
    r = resolve([[100, 130, 94, 100], [100, 110, 97, 103]])
    assert not r['recovered_high20']


def test_touch_is_not_close_and_hit_day_low_order_is_unknown():
    r = resolve([[100, 101, 95, 97], [98, 122, 85, 115]])
    assert r['recovered_high20'] and not r['recovered_close20']
    assert r['min_before_target_excluding_hit_day_pct'] == pytest.approx(-5)
    assert r['min_before_target_including_hit_day_pct'] == pytest.approx(-15)
    assert r['target_day_low_before_high_unknown']
    assert r['sl10_target_collision']
    assert not r['recovered_high20_without_prior_sl10']


def test_recovery_after_sl10_is_not_saved_by_a_wider_stop():
    r = resolve([[100, 101, 95, 96], [95, 97, 89, 92], [92, 125, 91, 123]])
    assert r['recovered_high20'] and r['recovered_close20']
    assert not r['recovered_high20_without_prior_sl10']
    assert r['sessions_after_stop_to_target'] == 2


def test_recovery_without_prior_sl10_and_gap_down_priority():
    assert resolve([[100, 101, 95, 97], [98, 125, 94, 123]])['recovered_high20_without_prior_sl10']
    assert not resolve([[100, 101, 95, 97], [88, 125, 85, 123]])['recovered_high20_without_prior_sl10']


def test_target_gap_open_precedes_later_same_day_low():
    r = resolve([[100, 101, 95, 97], [121, 125, 85, 110]])
    assert r['recovered_high20_without_prior_sl10']
    assert not r['sl10_target_collision']


def test_no_future_session_is_reserved_not_false_recovery():
    with pytest.raises(ValueError, match='No subsequent'):
        resolve([[100, 101, 95, 97]])


def test_atr_bins_are_frozen_and_finite():
    assert [bucket(v) for v in [.99, 1, 1.99, 2]] == ['LT1_ATR', '1_TO_LT2_ATR', '1_TO_LT2_ATR', 'GE2_ATR']
    with pytest.raises(ValueError):
        bucket(np.nan)


def test_nonoverlap_depends_on_entry_window_not_recovery():
    days = pd.bdate_range('2024-01-02', periods=50)
    f = pd.DataFrame({'entry_date': days[[0, 5, 20]], 'symbol': ['A']*3, 'horizon': [20]*3,
                      'recovered_high20': [False, True, False]})
    assert nonoverlapping(f, days).index.tolist() == [0, 2]
    f.recovered_high20 = ~f.recovered_high20
    assert nonoverlapping(f, days).index.tolist() == [0, 2]
