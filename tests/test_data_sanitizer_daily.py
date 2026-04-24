from datetime import date, datetime
from typing import cast

import polars as pl
import pytest
import pytz
from sqlalchemy.engine import Connection

from dataIntegrityEngine import data_sanitizer_daily
from dataIntegrityEngine.data_sanitizer_daily import DataQualityError, DataSanitizer


@pytest.fixture
def sanitizer() -> DataSanitizer:
    instance = DataSanitizer.__new__(DataSanitizer)
    instance.tz_ny = pytz.timezone("America/New_York")
    instance._spy_calendar_cache = None
    instance._tables_reflected = True
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


def test_sanitize_and_align_rejects_too_many_consecutive_fills(sanitizer: DataSanitizer) -> None:
    raw_df = pl.DataFrame(
        {
            "date": [date(2024, 1, 2), date(2024, 1, 9)],
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.0, 101.0],
            "volume": [1_000, 1_100],
            "adj_close": [100.0, 101.0],
            "vwap": [100.0, 101.0],
            "is_filled": [False, False],
        }
    )
    calendar_df = pl.DataFrame(
        {
            "date": [
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 4),
                date(2024, 1, 5),
                date(2024, 1, 8),
                date(2024, 1, 9),
            ]
        }
    )

    with pytest.raises(DataQualityError, match="fill streak"):
        sanitizer.sanitize_and_align(raw_df, calendar_df, prev_close=99.0)


def test_sanitize_and_align_sets_daily_return_to_null_when_prev_close_is_zero(sanitizer: DataSanitizer) -> None:
    raw_df = pl.DataFrame(
        {
            "date": [date(2024, 1, 2)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [1_000],
            "adj_close": [100.0],
            "vwap": [100.0],
            "is_filled": [False],
        }
    )
    calendar_df = pl.DataFrame({"date": [date(2024, 1, 2)]})

    aligned_df, _ = sanitizer.sanitize_and_align(raw_df, calendar_df, prev_close=0.0)

    assert aligned_df["daily_return"][0] is None


def test_sanitize_and_align_raises_clear_error_when_spy_calendar_is_empty(sanitizer: DataSanitizer) -> None:
    raw_df = pl.DataFrame(
        {
            "date": [date(2024, 1, 2)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [1_000],
            "adj_close": [100.0],
            "vwap": [100.0],
            "is_filled": [False],
        }
    )
    empty_calendar = pl.DataFrame({"date": pl.Series("date", [], dtype=pl.Date)})

    with pytest.raises(RuntimeError, match="Calendrier SPY introuvable"):
        sanitizer.sanitize_and_align(raw_df, empty_calendar, prev_close=None)


def test_ensure_spy_1d_available_imports_spy_when_missing(monkeypatch, sanitizer: DataSanitizer) -> None:
    sanitizer.stock_bars = object()
    fake_conn = _ContextConnection("stale")
    verification_conn = _ContextConnection("fresh")
    sanitizer.engine = _FakeEngine(verification_conn)
    calls: list[str] = []

    monkeypatch.setattr(
        data_sanitizer_daily,
        "get_stock_bars",
        lambda conn, stock_bars, symbol, timeframe, start: calls.append(
            f"read:{getattr(conn, 'label', 'unknown')}:{symbol}:{timeframe}"
        ) or (
            [] if getattr(conn, 'label', None) == "stale" else
            [{"t": datetime(2024, 1, 2, 0, 0, 0), "o": 0.0, "h": 0.0, "l": 0.0, "c": 0.0, "v": 0}]
        ),
    )
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.import_alpaca_bars",
        lambda time_frame, symbols=None: calls.append(f"import:{time_frame.db_value}:{','.join(symbols or [])}"),
    )

    sanitizer._ensure_spy_1d_available(cast(Connection, fake_conn))

    assert calls == [
        "read:stale:SPY:1D",
        "import:1D:SPY",
        "read:fresh:SPY:1D",
    ]


def test_ensure_spy_1d_available_raises_when_import_does_not_fill_spy(monkeypatch, sanitizer: DataSanitizer) -> None:
    sanitizer.stock_bars = object()
    fake_conn = _ContextConnection("stale")
    sanitizer.engine = _FakeEngine(_ContextConnection("fresh"))

    monkeypatch.setattr(data_sanitizer_daily, "get_stock_bars", lambda conn, stock_bars, symbol, timeframe, start: [])
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.import_alpaca_bars",
        lambda time_frame, symbols=None: None,
    )

    with pytest.raises(RuntimeError, match="Import automatique de SPY échoué"):
        sanitizer._ensure_spy_1d_available(cast(Connection, fake_conn))


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


def test_format_exception_message_prefers_dbapi_origin_message(sanitizer: DataSanitizer) -> None:
    exc = RuntimeError("verbose wrapper")
    exc.orig = ValueError("nan can not be used with MySQL")

    message = sanitizer._format_exception_message(exc)

    assert message == "RuntimeError: nan can not be used with MySQL"


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
            }
        ],
    )

    with caplog.at_level("INFO", logger="dataIntegrityEngine.data_sanitizer_daily"):
        sanitizer._log_failed_audit_summary(fake_conn, limit=5)

    # Compatibilité logs sans accents (Windows)
    assert any("Audits en echec detectes dans cleaning_audit_log" in message or "Audits en échec détectés dans cleaning_audit_log" in message for message in caplog.messages)
    assert any("Audit failed summary | symbol=AAPL" in message for message in caplog.messages)


class _FakeTransaction:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


class _ContextConnection:
    def __init__(self, label: str) -> None:
        self.label = label

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakePipelineConnection:
    def __init__(self) -> None:
        self.transactions: list[_FakeTransaction] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def begin(self) -> _FakeTransaction:
        tx = _FakeTransaction()
        self.transactions.append(tx)
        return tx


class _FakeEngine:
    def __init__(self, conn: object) -> None:
        self._conn = conn

    def connect(self):
        return self._conn


def test_run_pipeline_syncs_audit_to_stock_scores_after_upsert(monkeypatch, sanitizer: DataSanitizer) -> None:
    fake_conn = _FakePipelineConnection()
    sanitizer.engine = _FakeEngine(fake_conn)
    sanitizer.stock_metadata = object()
    sanitizer.cleaning_audit_log = object()
    sanitizer.stock_scores = object()

    upsert_calls: list[tuple[str, dict]] = []
    sync_calls: list[tuple[object, object, str, int | None, int | None, str]] = []

    monkeypatch.setattr(data_sanitizer_daily, "get_symbols", lambda conn, table: ["AAPL"])
    monkeypatch.setattr(sanitizer, "_ensure_spy_1d_available", lambda conn: None)
    monkeypatch.setattr(
        sanitizer,
        "_process_symbol",
        lambda conn, symbol: (True, {
            "last_sync": date(2024, 1, 5),
            "missing_days": 2,
            "anomaly_count": 4,
            "status": "success",
        }),
    )
    monkeypatch.setattr(
        data_sanitizer_daily,
        "upsert_audit",
        lambda conn, table, symbol, **payload: upsert_calls.append((symbol, payload)),
    )
    monkeypatch.setattr(
        data_sanitizer_daily,
        "sync_audit_to_stock_scores",
        lambda conn, table, symbol, missing_days, anomaly_count, sanitizer_status: sync_calls.append((conn, table, symbol, missing_days, anomaly_count, sanitizer_status)),
    )
    monkeypatch.setattr(sanitizer, "_log_failed_audit_summary", lambda conn: None)

    sanitizer.run_pipeline(commit_every=10)

    assert upsert_calls == [(
        "AAPL",
        {
            "last_sync": date(2024, 1, 5),
            "missing_days": 2,
            "anomaly_count": 4,
            "status": "success",
        },
    )]
    assert sync_calls == [(fake_conn, sanitizer.stock_scores, "AAPL", 2, 4, "success")]


def test_run_pipeline_syncs_failed_audit_to_stock_scores_on_exception(monkeypatch, sanitizer: DataSanitizer) -> None:
    fake_conn = _FakePipelineConnection()
    sanitizer.engine = _FakeEngine(fake_conn)
    sanitizer.stock_metadata = object()
    sanitizer.cleaning_audit_log = object()
    sanitizer.stock_scores = object()

    upsert_calls: list[tuple[str, dict]] = []
    sync_calls: list[tuple[object, object, str, int | None, int | None, str]] = []

    monkeypatch.setattr(data_sanitizer_daily, "get_symbols", lambda conn, table: ["AAPL"])
    monkeypatch.setattr(sanitizer, "_ensure_spy_1d_available", lambda conn: None)
    monkeypatch.setattr(
        sanitizer,
        "_process_symbol",
        lambda conn, symbol: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(data_sanitizer_daily, "get_last_sync_date", lambda conn, table, symbol: date(2024, 1, 3))
    monkeypatch.setattr(
        data_sanitizer_daily,
        "upsert_audit",
        lambda conn, table, symbol, **payload: upsert_calls.append((symbol, payload)),
    )
    monkeypatch.setattr(
        data_sanitizer_daily,
        "sync_audit_to_stock_scores",
        lambda conn, table, symbol, missing_days, anomaly_count, sanitizer_status: sync_calls.append((conn, table, symbol, missing_days, anomaly_count, sanitizer_status)),
    )
    monkeypatch.setattr(sanitizer, "_log_failed_audit_summary", lambda conn: None)

    sanitizer.run_pipeline(commit_every=10)

    assert upsert_calls == [(
        "AAPL",
        {
            "last_sync": date(2024, 1, 3),
            "missing_days": None,
            "anomaly_count": None,
            "status": "failed",
        },
    )]
    assert sync_calls == [(fake_conn, sanitizer.stock_scores, "AAPL", None, None, "failed")]


def test_process_symbol_rebuilds_with_gliding_lookback(monkeypatch, sanitizer: DataSanitizer) -> None:
    sanitizer.cleaning_audit_log = object()
    sanitizer.stock_bars = object()
    sanitizer.stock_bars_daily = object()
    sanitizer.stock_scores = object()
    conn = cast(Connection, object())
    fetch_calls: list[date | None] = []

    monkeypatch.setattr(data_sanitizer_daily, "get_last_sync_date", lambda current_conn, table, symbol: date(2024, 6, 1))
    monkeypatch.setattr(
        sanitizer,
        "fetch_symbol_bars_1d",
        lambda current_conn, symbol, start: fetch_calls.append(start) or pl.DataFrame(
            {
                "date": [date(2024, 1, 2), date(2024, 6, 3)],
                "open": [100.0, 101.0],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "close": [100.0, 101.0],
                "volume": [1_000, 1_100],
                "adj_close": [100.0, 101.0],
                "vwap": [100.0, 101.0],
                "is_filled": [False, False],
            }
        ),
    )
    monkeypatch.setattr(sanitizer, "load_spy_calendar", lambda current_conn, start, end: pl.DataFrame({"date": [date(2024, 1, 2), date(2024, 6, 3)]}))
    monkeypatch.setattr(data_sanitizer_daily, "get_prev_close_before", lambda current_conn, table, symbol, d: 99.0)
    monkeypatch.setattr(sanitizer, "sanitize_and_align", lambda df, calendar, prev_close: (df.with_columns(pl.lit(0.01).alias("daily_return")), 0))
    monkeypatch.setattr(sanitizer, "detect_anomalies", lambda df: (df, 0))
    monkeypatch.setattr(data_sanitizer_daily, "upsert_stock_bars_daily", lambda conn, table, symbol, df, data_adjustment=None: len(df))

    was_processed, payload = sanitizer._process_symbol(conn, "AAPL")

    assert was_processed is True
    assert fetch_calls == [date(2023, 4, 28)]
    assert payload["status"] == "success"
