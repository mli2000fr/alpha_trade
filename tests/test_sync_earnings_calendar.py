from __future__ import annotations

import json
from datetime import date

from dataIntegrityEngine import sync_earnings_calendar


def _context(
    *,
    from_date: date,
    to_date: date,
    limit: int | None = None,
    symbol_source: str = "active-tradable",
    provider: str = "finnhub",
) -> dict[str, object]:
    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "limit": limit,
        "symbol_source": symbol_source,
        "provider": provider,
    }


def test_sync_earnings_calendar_processes_committed_batches_and_clears_bookmark(tmp_path, monkeypatch) -> None:
    symbols = [f"SYM{i:03d}" for i in range(1, 61)]
    bookmark_path = tmp_path / "sync_earnings_calendar_bookmark.json"
    upsert_sizes: list[int] = []

    monkeypatch.setattr(sync_earnings_calendar, "list_symbols_for_source", lambda symbol_source=None, limit=None: symbols)
    monkeypatch.setattr(
        sync_earnings_calendar,
        "fetch_earnings_calendar",
        lambda symbol, **kwargs: [{"symbol": symbol, "date": "2026-05-01", "epsEstimate": 1.0}],
    )
    monkeypatch.setattr(sync_earnings_calendar.time, "sleep", lambda seconds: None)

    def _fake_upsert(rows: list[dict[str, object]]) -> int:
        upsert_sizes.append(len(rows))
        return len(rows)

    monkeypatch.setattr(sync_earnings_calendar, "upsert_earnings_calendar", _fake_upsert)

    summary = sync_earnings_calendar.sync_earnings_calendar(
        from_date=date(2026, 4, 1),
        to_date=date(2026, 4, 30),
        sleep_seconds=0.0,
        batch_size=25,
        bookmark_path=bookmark_path,
    )

    assert upsert_sizes == [25, 25, 10]
    assert summary["symbols"] == 60
    assert summary["symbols_pending"] == 60
    assert summary["symbols_skipped_resume"] == 0
    assert summary["completed_symbols"] == 60
    assert summary["failed_symbols"] == 0
    assert summary["symbols_remaining"] == 0
    assert summary["rows_upserted"] == 60
    assert summary["batches_processed"] == 3
    assert not bookmark_path.exists()


def test_sync_earnings_calendar_resume_skips_completed_symbols(tmp_path, monkeypatch) -> None:
    all_symbols = ["AAPL", "MSFT", "NVDA", "TSLA"]
    bookmark_path = tmp_path / "sync_earnings_calendar_bookmark.json"
    from_date = date(2026, 4, 1)
    to_date = date(2026, 4, 30)
    bookmark_path.write_text(
        json.dumps(
            {
                "completed_symbols": ["AAPL", "MSFT"],
                "started_at": "2026-04-30T10:00:00",
                "last_updated_at": "2026-04-30T10:05:00",
                "context": _context(from_date=from_date, to_date=to_date),
            }
        ),
        encoding="utf-8",
    )

    fetched_symbols: list[str] = []
    monkeypatch.setattr(sync_earnings_calendar, "list_symbols_for_source", lambda symbol_source=None, limit=None: all_symbols)
    monkeypatch.setattr(sync_earnings_calendar.time, "sleep", lambda seconds: None)

    def _fake_fetch(symbol: str, **kwargs) -> list[dict[str, object]]:
        fetched_symbols.append(symbol)
        return [{"symbol": symbol, "date": "2026-05-01", "epsEstimate": 1.0}]

    monkeypatch.setattr(sync_earnings_calendar, "fetch_earnings_calendar", _fake_fetch)
    monkeypatch.setattr(sync_earnings_calendar, "upsert_earnings_calendar", lambda rows: len(rows))

    summary = sync_earnings_calendar.sync_earnings_calendar(
        from_date=from_date,
        to_date=to_date,
        sleep_seconds=0.0,
        batch_size=25,
        resume=True,
        bookmark_path=bookmark_path,
    )

    assert fetched_symbols == ["NVDA", "TSLA"]
    assert summary["symbols"] == 4
    assert summary["symbols_pending"] == 2
    assert summary["symbols_skipped_resume"] == 2
    assert summary["completed_symbols"] == 2
    assert summary["failed_symbols"] == 0
    assert summary["rows_upserted"] == 2
    assert not bookmark_path.exists()


def test_sync_earnings_calendar_retains_bookmark_for_failed_symbols(tmp_path, monkeypatch) -> None:
    symbols = ["AAPL", "MSFT", "NVDA"]
    bookmark_path = tmp_path / "sync_earnings_calendar_bookmark.json"
    from_date = date(2026, 4, 1)
    to_date = date(2026, 4, 30)

    monkeypatch.setattr(sync_earnings_calendar, "list_symbols_for_source", lambda symbol_source=None, limit=None: symbols)
    monkeypatch.setattr(sync_earnings_calendar.time, "sleep", lambda seconds: None)

    def _fake_fetch(symbol: str, **kwargs) -> list[dict[str, object]]:
        if symbol == "MSFT":
            raise RuntimeError("finnhub timeout")
        return [{"symbol": symbol, "date": "2026-05-01", "epsEstimate": 1.0}]

    monkeypatch.setattr(sync_earnings_calendar, "fetch_earnings_calendar", _fake_fetch)
    monkeypatch.setattr(sync_earnings_calendar, "upsert_earnings_calendar", lambda rows: len(rows))

    summary = sync_earnings_calendar.sync_earnings_calendar(
        from_date=from_date,
        to_date=to_date,
        sleep_seconds=0.0,
        batch_size=25,
        resume=True,
        bookmark_path=bookmark_path,
    )

    assert summary["completed_symbols"] == 2
    assert summary["failed_symbols"] == 1
    assert summary["symbols_remaining"] == 1
    assert summary["rows_upserted"] == 2
    assert bookmark_path.exists()

    bookmark = json.loads(bookmark_path.read_text(encoding="utf-8"))
    assert bookmark["completed_symbols"] == ["AAPL", "NVDA"]
    assert bookmark["context"] == _context(from_date=from_date, to_date=to_date)


def test_sync_earnings_calendar_uses_requested_symbol_source_in_fetch_and_bookmark(tmp_path, monkeypatch) -> None:
    bookmark_path = tmp_path / "sync_earnings_calendar_bookmark.json"
    fetched_symbols: list[str] = []
    captured_sources: list[tuple[object, object]] = []

    monkeypatch.setattr(
        sync_earnings_calendar,
        "list_symbols_for_source",
        lambda symbol_source=None, limit=None: captured_sources.append((symbol_source, limit)) or ["AAPL", "MSFT"],
    )
    monkeypatch.setattr(sync_earnings_calendar.time, "sleep", lambda seconds: None)

    def _fake_fetch(symbol: str, **kwargs) -> list[dict[str, object]]:
        fetched_symbols.append(symbol)
        return [{"symbol": symbol, "date": "2026-05-01", "epsEstimate": 1.0}]

    monkeypatch.setattr(sync_earnings_calendar, "fetch_earnings_calendar", _fake_fetch)
    monkeypatch.setattr(sync_earnings_calendar, "upsert_earnings_calendar", lambda rows: len(rows))

    summary = sync_earnings_calendar.sync_earnings_calendar(
        from_date=date(2026, 4, 1),
        to_date=date(2026, 4, 30),
        limit=2,
        symbol_source="stock_scores",
        sleep_seconds=0.0,
        batch_size=25,
        bookmark_path=bookmark_path,
    )

    assert summary["symbols"] == 2
    assert fetched_symbols == ["AAPL", "MSFT"]
    assert captured_sources == [("stock-scores", 2)]
    assert not bookmark_path.exists()


