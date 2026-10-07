import pandas as pd
import pytest

from scripts.research.us_top10_early_weakness_audit import early_paths, summarize_paths


def fixture():
    days = pd.bdate_range('2023-01-02', periods=25)
    bars = pd.DataFrame([dict(date=d,symbol=s,open=100.,high=102.,low=99.,
        close=101.,volume=1000,is_filled=0,instrument_id=i)
        for i,s in enumerate(['SPY','X']) for d in days])
    scores = pd.DataFrame([dict(date=days[0],symbol='X',proba_extreme=.8,ORACLE_TOP10=True)])
    return days,bars,scores


def test_next_open_and_entry_plus_twenty_no_future_rank():
    days,bars,scores = fixture()
    row = early_paths(scores,bars).iloc[0]
    assert row.entry_date == days[1]
    assert row.entry_plus20_date == days[21]
    assert row.return_j1 == pytest.approx(.01)
    assert row.relative_spy_j5 == pytest.approx(0)
    assert row.hold_return == pytest.approx(.01)
    assert summarize_paths(early_paths(scores,bars))[0]['count'] == 1


def test_zero_volume_does_not_silently_certify_path():
    days,bars,scores = fixture()
    bars.loc[bars.symbol.eq('X') & bars.date.eq(days[5]),'volume'] = 0
    result = early_paths(scores,bars)
    assert result.path_status.iloc[0] == 'UNQUALIFIED_PRICE_PATH'
    assert summarize_paths(result) == []


def test_missing_future_is_not_zero_return():
    days,bars,scores = fixture()
    scores['date'] = days[-1]
    result = early_paths(scores,bars)
    assert result.path_status.iloc[0] == 'INCOMPLETE_CALENDAR'


def test_hold_winner_can_touch_stop_before_recovery():
    days,bars,scores = fixture()
    bars.loc[bars.symbol.eq('X') & bars.date.eq(days[2]),'low'] = 90
    result = early_paths(scores,bars)
    assert result.touched_initial_sl7.iloc[0]
    assert result.hold_return.iloc[0] > 0
