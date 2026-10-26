from datetime import date
import pandas as pd
import pytest
from scripts.research.us_oracle_path_trend_ranking_dates_20261022 import normalize_recent, freeze


def test_normalization_preserves_calendar_and_all_other_columns():
    a = pd.DataFrame({'fold_start': [date(2023, 12, 5), date(2024, 12, 4)],
                      'score': [.7, .8], 'symbol': ['A', 'B']})
    b = normalize_recent(a)
    assert b.fold_start.dt.date.tolist() == a.fold_start.tolist()
    pd.testing.assert_frame_equal(a.drop(columns='fold_start'), b.drop(columns='fold_start'))
    assert isinstance(a.fold_start.iloc[0], date)


def test_mixed_archives_now_concat_to_timestamp():
    historical = pd.DataFrame({'fold_start': [pd.Timestamp('2023-01-05')]})
    recent = normalize_recent(pd.DataFrame({'fold_start': [date(2023, 12, 5)]}))
    assert str(pd.concat([historical, recent]).fold_start.dtype) == 'datetime64[ns]'


def test_no_overwrite(tmp_path):
    with pytest.raises(FileExistsError):
        freeze(tmp_path)
