from datetime import date
import os
import sys

import polars as pl
import pytz

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dataIntegrityEngine.data_sanitizer_daily import DataSanitizer


def _build_sanitizer_without_db() -> DataSanitizer:
    sanitizer = DataSanitizer.__new__(DataSanitizer)
    sanitizer.tz_ny = pytz.timezone("America/New_York")
    sanitizer._spy_calendar_cache = None
    return sanitizer


def main() -> None:
    sanitizer = _build_sanitizer_without_db()

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
    anomaly_df, anomaly_count = sanitizer.detect_anomalies(aligned_df)

    print(aligned_df)
    print(anomaly_df.select(["date", "daily_return", "is_anomaly"]))

    assert filled_count == 1, "Une journée manquante doit être forward-fillée"
    assert aligned_df.filter(pl.col("date") == date(2024, 1, 3))["is_filled"][0] is True
    assert aligned_df.filter(pl.col("date") == date(2024, 1, 3))["volume"][0] == 0
    assert aligned_df.filter(pl.col("date") == date(2024, 1, 3))["close"][0] == 100.0
    assert anomaly_count >= 0


if __name__ == "__main__":
    main()

