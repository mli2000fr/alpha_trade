from datetime import date, datetime
from typing import cast

import polars as pl
import pytest
import pytz
from sqlalchemy.engine import Connection

from dataIntegrityEngine import data_sanitizer_daily
from dataIntegrityEngine.data_sanitizer_daily import DataSanitizer


@pytest.fixture
def sanitizer() -> DataSanitizer:
    instance = DataSanitizer.__new__(DataSanitizer)
    instance.tz_ny = pytz.timezone("America/New_York")
    instance._spy_calendar_cache = None
    return instance


def test_to_ny_date_handles_utc_conversion(sanitizer: DataSanitizer) -> None:
    assert sanitizer._to_ny_date("2024-01-02T01:00:00Z") == date(2024, 1, 1)


def test_to_ny_date_handles_naive_new_york_db_timestamp(sanitizer: DataSanitizer) -> None:
    assert sanitizer._to_ny_date(datetime(2024, 1, 2, 0, 0, 0)) == date(2024, 1, 2)


def test_fetch_symbol_bars_1d_reads_from_stock_bars(monkeypatch, sanitizer: DataSanitizer) -> None:
    calls: list[tuple[object, object, str, str, date | None]] = []
    sanitizer.stock_bars = object()

    monkeypatch.setattr(
        data_sanitizer_daily,
        "get_stock_bars",
        lambda conn, stock_bars, symbol, timeframe, start: calls.append((conn, stock_bars, symbol, timeframe, start)) or [
            {
                "t": datetime(2024, 1, 2, 0, 0, 0),
                "o": 100.0,
                "h": 101.0,
                "l": 99.0,
                "c": 100.5,
                "v": 1_500,
                "vw": 100.25,
            }
        ],
    )

    conn = cast(Connection, object())
    df = sanitizer.fetch_symbol_bars_1d(conn, "AAPL", date(2024, 1, 2))

    assert calls == [(conn, sanitizer.stock_bars, "AAPL", "1D", date(2024, 1, 2))]
    assert df["date"].to_list() == [date(2024, 1, 2)]
    assert df["close"].to_list() == [100.5]
    assert df["is_filled"].to_list() == [False]


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


def test_format_exception_message_includes_exception_type_and_message(sanitizer: DataSanitizer) -> None:
    message = sanitizer._format_exception_message(ValueError("boom"))

    assert message == "ValueError: boom"


def test_format_exception_message_falls_back_to_exception_type_when_empty(sanitizer: DataSanitizer) -> None:
    message = sanitizer._format_exception_message(RuntimeError())

    assert message == "RuntimeError"


def test_log_failed_audit_summary_logs_failed_rows(monkeypatch, caplog, sanitizer: DataSanitizer) -> None:
    sanitizer.cleaning_audit_log = object()
    fake_conn = cast(Connection, object())

    monkeypatch.setattr(
        data_sanitizer_daily,
        "get_failed_audits",
        lambda conn, table, limit=20: [
            {
                "symbol": "AAPL",
                "updated_at": datetime(2024, 1, 3, 10, 0, 0),
                "last_sync_date": date(2024, 1, 3),
                "error_msg": "ValueError: boom",
            }
        ],
    )

    with caplog.at_level("INFO", logger="dataIntegrityEngine.data_sanitizer_daily"):
        sanitizer._log_failed_audit_summary(fake_conn, limit=5)

    assert any("Audits en échec détectés dans cleaning_audit_log" in message for message in caplog.messages)
    assert any("Audit failed summary | symbol=AAPL" in message for message in caplog.messages)


