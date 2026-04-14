from datetime import date

import polars as pl
import pytest
import pytz

from dataIntegrityEngine.data_sanitizer_daily import DataSanitizer


@pytest.fixture
def sanitizer() -> DataSanitizer:
    instance = DataSanitizer.__new__(DataSanitizer)
    instance.tz_ny = pytz.timezone("America/New_York")
    instance._spy_calendar_cache = None
    return instance


def test_to_ny_date_handles_utc_conversion(sanitizer: DataSanitizer) -> None:
    assert sanitizer._to_ny_date("2024-01-02T01:00:00Z") == date(2024, 1, 1)


def test_sanitize_and_align_forward_fills_missing_days(sanitizer: DataSanitizer) -> None:
    raw_df = pl.DataFrame(
        {
            "date": [date(2024, 1, 2), date(2024, 1, 4)],
            "open": [100.0, 105.0],
            "high": [101.0, 106.0],
            "low": [99.0, 104.0],
            "close": [100.0, 105.0],
            "volume": [1_000, 2_000],
            "adj_close": [100.0, 105.0],
            "vwap": [100.0, 105.0],
            "is_filled": [False, False],
        }
    )
    calendar_df = pl.DataFrame({"date": [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]})

    aligned_df, filled_count = sanitizer.sanitize_and_align(raw_df, calendar_df, prev_close=98.0)
    filled_row = aligned_df.filter(pl.col("date") == date(2024, 1, 3))

    assert filled_count == 1
    assert filled_row["is_filled"][0] is True
    assert filled_row["volume"][0] == 0
    assert filled_row["close"][0] == 100.0
    assert "daily_return" in aligned_df.columns


def test_detect_anomalies_returns_boolean_flags_without_nulls(sanitizer: DataSanitizer) -> None:
    df = pl.DataFrame(
        {
            "date": [date(2024, 1, day) for day in range(1, 9)],
            "daily_return": [0.01, 0.011, 0.009, 0.012, 0.013, 0.011, 0.0105, 0.35],
        }
    )

    anomaly_df, anomaly_count = sanitizer.detect_anomalies(df)

    assert anomaly_df["is_anomaly"].dtype == pl.Boolean
    assert anomaly_df["is_anomaly"].null_count() == 0
    assert anomaly_count >= 0


def test_run_pipeline_rejects_invalid_commit_every(sanitizer: DataSanitizer) -> None:
    with pytest.raises(ValueError):
        sanitizer.run_pipeline(commit_every=0)

