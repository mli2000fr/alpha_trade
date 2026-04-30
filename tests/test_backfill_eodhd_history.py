"""T-EOD-5 - backfill_eodhd_history (plan §6 Phase 5 + §7.1)."""
from __future__ import annotations

import json
import time
from datetime import date
from typing import Any

import pytest

from dataIntegrityEngine import backfill_eodhd_history as bf
from dataIntegrityEngine import import_eodhd_bar
from service.eodhd import accounts as eodhd_accounts
from service.eodhd import quota as eodhd_quota


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[Any] = []
        self.committed = 0
        self.rolled_back = 0

    def execute(self, stmt) -> Any:
        self.executed.append(stmt)
        class _R:
            rowcount = 0
        return _R()

    def commit(self) -> None: self.committed += 1
    def rollback(self) -> None: self.rolled_back += 1
    def close(self) -> None: ...


def _make_eod_history(symbol: str, n_days: int = 30) -> list[dict]:
    return [
        {
            "date": f"2025-04-{(d % 28) + 1:02d}",
            "open": 100.0 + d * 0.5,
            "high": 101.0 + d * 0.5,
            "low": 99.0 + d * 0.5,
            "close": 100.5 + d * 0.5,
            "adjusted_close": 100.5 + d * 0.5,
            "volume": 1_000_000 + d * 1000,
        }
        for d in range(1, n_days + 1)
    ]


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("EODHD_API_TOKEN", "TEST")
    eodhd_accounts.EodhdAccountRegistry.reset()
    eodhd_quota.reset_default_tracker()
    tracker = eodhd_quota.EodhdQuotaTracker(cache_dir=tmp_path)
    monkeypatch.setattr(eodhd_quota, "_DEFAULT_TRACKER", tracker, raising=False)

    monkeypatch.setattr(
        import_eodhd_bar, "_get_active_tradable_symbols",
        lambda session: ["AAPL", "NVDA", "MSFT"],
    )
    # backfill_eodhd_history importe directement la fonction -> patch aussi le binding local
    monkeypatch.setattr(
        bf, "_get_active_tradable_symbols",
        lambda session: ["AAPL", "NVDA", "MSFT"],
    )

    from sqlalchemy import Column, MetaData, Table
    from sqlalchemy.types import BigInteger, Date, DateTime, Integer, Numeric, String
    md = MetaData()
    sm = Table("stock_metadata", md, Column("symbol", String(20), primary_key=True))
    sb = Table(
        "stock_bars", md,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("symbol", String(20)), Column("timeframe", String(5)),
        Column("timestamp", DateTime),
        Column("open_price", Numeric(20, 8)), Column("high_price", Numeric(20, 8)),
        Column("low_price", Numeric(20, 8)), Column("close_price", Numeric(20, 8)),
        Column("volume", BigInteger), Column("trade_count", BigInteger),
        Column("vwa_price", Numeric(20, 8)),
        Column("data_adjustment", String(16)), Column("data_source", String(16)),
    )
    sbd = Table(
        "stock_bars_daily", md,
        Column("symbol", String(20), primary_key=True),
        Column("date", Date, primary_key=True),
        Column("open", Numeric(20, 8)), Column("high", Numeric(20, 8)),
        Column("low", Numeric(20, 8)), Column("close", Numeric(20, 8)),
        Column("volume", BigInteger), Column("adj_close", Numeric(20, 8)),
        Column("vwap", Numeric(20, 8)), Column("daily_return", Numeric(10, 6)),
        Column("is_filled", Integer),
        Column("data_adjustment", String(16)), Column("data_source", String(16)),
    )
    monkeypatch.setattr(import_eodhd_bar, "_get_tables", lambda: (sm, sb, sbd))

    yield {"tracker": tracker, "tmp_path": tmp_path}
    eodhd_accounts.EodhdAccountRegistry.reset()
    eodhd_quota.reset_default_tracker()


def test_bookmark_load_save_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    state = bf.load_bookmark(path)
    assert state["completed_symbols"] == []

    state["completed_symbols"].extend(["AAPL", "NVDA"])
    state["last_run_id"] = "abc"
    bf.save_bookmark(path, state)

    reloaded = bf.load_bookmark(path)
    assert reloaded["completed_symbols"] == ["AAPL", "NVDA"]
    assert reloaded["last_run_id"] == "abc"


def test_bookmark_corrupted_file_resets(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not-json{{{", encoding="utf-8")
    state = bf.load_bookmark(path)
    assert state["completed_symbols"] == []


def test_backfill_one_symbol_dry_run_no_writes(env, monkeypatch):
    monkeypatch.setattr(bf, "_cached_fetch_splits", lambda symbol, **kwargs: [])
    history = _make_eod_history("AAPL", 25)

    result = bf.backfill_one_symbol(
        symbol="AAPL", start="2025-01-01", end="2025-04-29",
        cache=None, tracker=env["tracker"], session=_FakeSession(),
        dry_run=True,
        fetch_eod_fn=lambda *a, **k: history,
    )
    assert result["raw_rows"] == 25
    assert result["rows_daily"] == 0
    assert result["rows_bars"] == 0
    assert result["would_upsert_daily"] == 25
    assert result["errors"] == 0


def test_backfill_one_symbol_write_mode_calls_upserts(env, monkeypatch):
    monkeypatch.setattr(bf, "_cached_fetch_splits", lambda symbol, **kwargs: [])
    history = _make_eod_history("NVDA", 10)
    session = _FakeSession()

    result = bf.backfill_one_symbol(
        symbol="NVDA", start="2025-01-01", end="2025-04-29",
        cache=None, tracker=env["tracker"], session=session,
        dry_run=False,
        fetch_eod_fn=lambda *a, **k: history,
    )
    assert result["rows_daily"] == 10
    assert result["rows_bars"] == 10
    assert result["errors"] == 0
    assert len(session.executed) == 2


def test_backfill_one_symbol_handles_real_eodhd_split_format(env, monkeypatch):
    """Format reel EODHD : '10.000000/1.000000' doit parser."""
    monkeypatch.setattr(
        bf, "_cached_fetch_splits",
        lambda symbol, **kwargs: [
            {"date": "2024-06-10", "split": "10.000000/1.000000"},
        ],
    )
    history = [{
        "date": "2024-06-07",
        "open": 1200.0, "high": 1210.0, "low": 1190.0,
        "close": 1205.0, "adjusted_close": 120.5, "volume": 30_000_000,
    }]
    result = bf.backfill_one_symbol(
        symbol="NVDA", start="2024-06-01", end="2024-06-08",
        cache=None, tracker=env["tracker"], session=_FakeSession(),
        dry_run=True,
        fetch_eod_fn=lambda *a, **k: history,
    )
    assert result["raw_rows"] == 1
    assert result["errors"] == 0
    assert result["would_upsert_daily"] == 1


def test_backfill_one_symbol_fetch_error_records_error(env, monkeypatch):
    from service.eodhd.clientEodhd import EodhdBarsFetchError

    def _boom(*a, **k):
        raise EodhdBarsFetchError("HTTP 500")

    monkeypatch.setattr(bf, "_cached_fetch_splits", lambda symbol, **kwargs: [])
    result = bf.backfill_one_symbol(
        symbol="AAPL", start="2025-01-01", end="2025-04-29",
        cache=None, tracker=env["tracker"], session=_FakeSession(),
        dry_run=True, fetch_eod_fn=_boom,
    )
    assert result["errors"] == 1
    assert result["raw_rows"] == 0


def test_run_backfill_processes_universe_and_writes_bookmark(env, monkeypatch, tmp_path):
    history = _make_eod_history("X", 5)
    monkeypatch.setattr(bf, "fetch_eod", lambda symbol, **kwargs: history)
    monkeypatch.setattr(bf, "_cached_fetch_splits", lambda symbol, **kwargs: [])

    bookmark_path = tmp_path / "bm.json"
    summary = bf.run_backfill(
        years=2, symbols=None, dry_run=True, resume=False,
        bookmark_path=bookmark_path, config={},
        session=_FakeSession(), tracker=env["tracker"],
    )
    assert summary["targeted_symbols"] == 3
    assert summary["symbols_processed"] == 3
    assert summary["raw_rows_total"] == 15
    assert summary["errors"] == 0
    assert summary["rows_upserted_stock_bars_daily"] == 0
    assert summary["would_upsert_stock_bars_daily"] == 15
    assert summary["would_upsert_stock_bars"] == 15

    bm = json.loads(bookmark_path.read_text(encoding="utf-8"))
    assert set(bm["completed_symbols"]) == {"AAPL", "NVDA", "MSFT"}


def test_run_backfill_resume_skips_completed_symbols(env, monkeypatch, tmp_path):
    monkeypatch.setattr(bf, "fetch_eod", lambda symbol, **kwargs: _make_eod_history(symbol, 3))
    monkeypatch.setattr(bf, "_cached_fetch_splits", lambda symbol, **kwargs: [])

    bookmark_path = tmp_path / "bm.json"
    bf.save_bookmark(bookmark_path, {
        "completed_symbols": ["AAPL", "NVDA"],
        "started_at": "2025-01-01T00:00:00",
        "last_run_id": "previous",
    })
    summary = bf.run_backfill(
        years=2, dry_run=True, resume=True,
        bookmark_path=bookmark_path, config={},
        session=_FakeSession(), tracker=env["tracker"],
    )
    assert summary["targeted_symbols"] == 3
    assert summary["symbols_skipped_resumed"] == 2
    assert summary["remaining_after_bookmark"] == 1
    assert summary["symbols_processed"] == 1


def test_run_backfill_write_mode_ignores_stale_bookmark_when_db_empty(env, monkeypatch, tmp_path):
    monkeypatch.setattr(bf, "fetch_eod", lambda symbol, **kwargs: _make_eod_history(symbol, 2))
    monkeypatch.setattr(bf, "_cached_fetch_splits", lambda symbol, **kwargs: [])
    monkeypatch.setattr(bf, "_get_latest_bar_dates", lambda session, symbols: {})

    bookmark_path = tmp_path / "bm.json"
    bf.save_bookmark(bookmark_path, {
        "completed_symbols": ["AAPL", "NVDA"],
        "started_at": "2025-01-01T00:00:00",
        "last_run_id": "previous",
    })
    summary = bf.run_backfill(
        years=2, dry_run=False, resume=True,
        bookmark_path=bookmark_path, config={},
        session=_FakeSession(), tracker=env["tracker"],
    )
    assert summary["targeted_symbols"] == 3
    assert summary["symbols_skipped_resumed"] == 0
    assert summary["symbols_processed"] == 3


def test_run_backfill_no_resume_reprocesses_all(env, monkeypatch, tmp_path):
    monkeypatch.setattr(bf, "fetch_eod", lambda symbol, **kwargs: _make_eod_history(symbol, 1))
    monkeypatch.setattr(bf, "_cached_fetch_splits", lambda symbol, **kwargs: [])

    bookmark_path = tmp_path / "bm.json"
    bf.save_bookmark(bookmark_path, {
        "completed_symbols": ["AAPL", "NVDA", "MSFT"],
        "started_at": None, "last_run_id": None,
    })
    summary = bf.run_backfill(
        years=2, dry_run=True, resume=False,
        bookmark_path=bookmark_path, config={},
        session=_FakeSession(), tracker=env["tracker"],
    )
    assert summary["symbols_processed"] == 3
    assert summary["symbols_skipped_resumed"] == 0


def test_run_backfill_write_mode_skips_symbols_already_fresh_in_db(env, monkeypatch, tmp_path):
    monkeypatch.setattr(bf, "fetch_eod", lambda symbol, **kwargs: _make_eod_history(symbol, 1))
    monkeypatch.setattr(bf, "_cached_fetch_splits", lambda symbol, **kwargs: [])
    monkeypatch.setattr(
        bf,
        "_get_latest_bar_dates",
        lambda session, symbols: {"AAPL": date(2026, 4, 28)},
    )

    summary = bf.run_backfill(
        years=2, dry_run=False, resume=False,
        bookmark_path=tmp_path / "bm.json", config={},
        session=_FakeSession(), tracker=env["tracker"],
        today=date(2026, 4, 29),
    )
    assert summary["targeted_symbols"] == 3
    assert summary["symbols_skipped_db_fresh"] == 1
    assert summary["db_fresh_cutoff"] == "2026-04-22"
    assert summary["symbols_processed"] == 2


def test_run_backfill_explicit_symbols_bypass_universe(env, monkeypatch, tmp_path):
    monkeypatch.setattr(bf, "fetch_eod", lambda symbol, **kwargs: _make_eod_history(symbol, 2))
    monkeypatch.setattr(bf, "_cached_fetch_splits", lambda symbol, **kwargs: [])
    monkeypatch.setattr(bf, "_get_latest_bar_dates", lambda session, symbols: {})

    def _should_not_be_called(session):
        raise AssertionError("ne doit pas etre appele quand symbols=[...]")
    monkeypatch.setattr(import_eodhd_bar, "_get_active_tradable_symbols", _should_not_be_called)
    monkeypatch.setattr(bf, "_get_active_tradable_symbols", _should_not_be_called)

    summary = bf.run_backfill(
        years=2, symbols=["TSLA", "META"], dry_run=True, resume=False,
        bookmark_path=tmp_path / "bm.json", config={},
        session=_FakeSession(), tracker=env["tracker"],
    )
    assert summary["targeted_symbols"] == 2
    assert summary["symbols_processed"] == 2


def test_run_backfill_circuit_breaker_stops_processing(env, monkeypatch, tmp_path):
    monkeypatch.setattr(bf, "fetch_eod", lambda symbol, **kwargs: _make_eod_history(symbol, 1))
    monkeypatch.setattr(bf, "_cached_fetch_splits", lambda symbol, **kwargs: [])

    tracker = env["tracker"]
    tracker.state.circuit_open_until_epoch = time.time() + 3600

    summary = bf.run_backfill(
        years=2, dry_run=True, resume=False,
        bookmark_path=tmp_path / "bm.json", config={},
        session=_FakeSession(), tracker=tracker,
    )
    assert summary["symbols_processed"] == 0
    assert summary["stopped_reason"] == "circuit_open"


def test_run_backfill_skips_preferred_series_before_fetch(env, monkeypatch, tmp_path):
    monkeypatch.setattr(bf, "fetch_eod", lambda symbol, **kwargs: pytest.fail("fetch_eod ne doit pas être appelé"))

    summary = bf.run_backfill(
        years=2,
        symbols=["ABR.PRD"],
        dry_run=True,
        resume=False,
        bookmark_path=tmp_path / "bm.json",
        config={},
        session=_FakeSession(),
        tracker=env["tracker"],
    )

    assert summary["targeted_symbols"] == 1
    assert summary["unsupported_fallback_symbols"] == 1
    assert summary["metadata_marked_unavailable"] == 0
    assert summary["symbols_processed"] == 0
    bm = json.loads((tmp_path / "bm.json").read_text(encoding="utf-8"))
    assert bm["completed_symbols"] == ["ABR.PRD"]


def test_run_backfill_marks_preferred_series_unavailable_in_write_mode(env, monkeypatch, tmp_path):
    monkeypatch.setattr(bf, "fetch_eod", lambda symbol, **kwargs: pytest.fail("fetch_eod ne doit pas être appelé"))
    update_calls: list[str] = []
    monkeypatch.setattr(bf, "update_bars_available_false", lambda symbol: update_calls.append(symbol))

    summary = bf.run_backfill(
        years=2,
        symbols=["ABR.PRD"],
        dry_run=False,
        resume=False,
        bookmark_path=tmp_path / "bm.json",
        config={},
        session=_FakeSession(),
        tracker=env["tracker"],
    )

    assert update_calls == ["ABR.PRD"]
    assert summary["unsupported_fallback_symbols"] == 1
    assert summary["metadata_marked_unavailable"] == 1


def test_run_backfill_window_is_years_long(env, monkeypatch, tmp_path):
    captured: dict[str, Any] = {}

    def _capture(symbol, *, start=None, end=None, **kwargs):
        captured["start"] = start
        captured["end"] = end
        return []

    monkeypatch.setattr(bf, "fetch_eod", _capture)
    monkeypatch.setattr(bf, "_cached_fetch_splits", lambda symbol, **kwargs: [])

    today = date(2026, 4, 29)
    bf.run_backfill(
        years=5, symbols=["AAPL"], dry_run=True, resume=False,
        bookmark_path=tmp_path / "bm.json", config={},
        session=_FakeSession(), tracker=env["tracker"],
        today=today,
    )
    assert captured["end"] == "2026-04-29"
    assert captured["start"] == "2021-04-29"



