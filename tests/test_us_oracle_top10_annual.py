import pandas as pd
import pytest

from scripts.research.us_oracle_top10_annual import check_coverage, select_scores, yearly_windows


def predictions():
    return pd.DataFrame(dict(date=[pd.Timestamp('2024-07-10')]*12,
        symbol=[f'S{i:02}' for i in range(12)], score=[.5]*12,
        fold_start=['2024-01-08']*12, future_return=list(range(12))))


def test_top10_uses_score_not_future_and_strips_labels():
    data = predictions()
    expected = select_scores(data)
    data['future_return'] *= -100
    pd.testing.assert_frame_equal(expected, select_scores(data))
    assert expected.symbol.tolist() == [f'S{i:02}' for i in range(10)]
    assert 'future_return' not in expected
    assert expected.oracle_rank.tolist() == list(range(1, 11))


def test_future_model_rejected():
    data = predictions()
    data['fold_start'] = '2025-01-01'
    with pytest.raises(ValueError, match='chronology'):
        select_scores(data)


def test_duplicate_predictions_rejected():
    data = predictions()
    with pytest.raises(ValueError, match='Duplicate'):
        select_scores(pd.concat([data, data.iloc[:1]]))


def test_missing_calendar_day_never_implies_cash_day():
    data = select_scores(predictions())
    with pytest.raises(ValueError, match='2024-07-11'):
        check_coverage(data, pd.date_range('2024-07-10', periods=2), '2024-07-10', '2024-07-11')
    assert len(check_coverage(data, pd.date_range('2024-07-10', periods=1), '2024-07-10', '2024-07-10')) == 1


def test_annual_windows_and_partial_2026():
    windows = yearly_windows('2020-01-01', '2026-09-03')
    assert len(windows) == 7
    assert windows[4] == (2024, pd.Timestamp('2024-01-01'), pd.Timestamp('2024-12-31'))
    assert windows[-1][2] == pd.Timestamp('2026-09-03')
    with pytest.raises(ValueError):
        yearly_windows('2026-01-01', '2020-01-01')


def test_nonfinite_score_and_small_pool_rejected():
    data = predictions()
    data.loc[0, 'score'] = float('nan')
    with pytest.raises(ValueError):
        select_scores(data)
    with pytest.raises(ValueError, match='Fewer'):
        select_scores(predictions().iloc[:9])
