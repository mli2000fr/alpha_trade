"""Tests du helper de parsing du timestamp Alpaca pour `stock_quote_snapshots`.

Régression du bug MySQL 1292 (« Incorrect datetime value ») rencontré le
2026-04-30 : le format RFC 3339 d'Alpaca (`...Z`, fraction nanoseconde) est
désormais converti en `datetime` Python timezone-naïf UTC tronqué aux
microsecondes — compatible MySQL `DATETIME(6)`.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from dataIntegrityEngine import sync_latest_quotes
from dataIntegrityEngine.sync_latest_quotes import _market_date_from_timestamp, _parse_alpaca_timestamp


class TestParseAlpacaTimestamp:
    def test_alpaca_rfc3339_nanoseconds_z_suffix(self):
        out = _parse_alpaca_timestamp("2026-04-29T19:59:49.779850529Z")
        assert out == datetime(2026, 4, 29, 19, 59, 49, 779850)
        assert out.tzinfo is None  # MySQL DATETIME(6) — pas de tzinfo.

    def test_microseconds_preserved_intact(self):
        out = _parse_alpaca_timestamp("2026-04-29T20:00:00.123456Z")
        assert out == datetime(2026, 4, 29, 20, 0, 0, 123456)

    def test_no_fraction(self):
        out = _parse_alpaca_timestamp("2026-04-29T20:00:00Z")
        assert out == datetime(2026, 4, 29, 20, 0, 0)

    def test_offset_other_than_zero_normalised_to_utc(self):
        out = _parse_alpaca_timestamp("2026-04-29T22:00:00+02:00")
        assert out == datetime(2026, 4, 29, 20, 0, 0)
        assert out.tzinfo is None

    def test_aware_datetime_input(self):
        aware = datetime(2026, 4, 29, 22, 0, 0, tzinfo=timezone.utc)
        out = _parse_alpaca_timestamp(aware)
        assert out == datetime(2026, 4, 29, 22, 0, 0)
        assert out.tzinfo is None

    def test_naive_datetime_input_passthrough(self):
        naive = datetime(2026, 4, 29, 22, 0, 0)
        assert _parse_alpaca_timestamp(naive) == naive

    @pytest.mark.parametrize("value", [None, ""])
    def test_none_or_empty_returns_none(self, value):
        assert _parse_alpaca_timestamp(value) is None

    def test_invalid_string_returns_none_and_logs(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            assert _parse_alpaca_timestamp("not-a-date") is None
        assert any("quote_timestamp invalide" in rec.message for rec in caplog.records)


class TestMarketDateFromTimestamp:
    def test_uses_market_date_new_york_from_utc_timestamp(self):
        quote_timestamp = datetime(2026, 4, 29, 20, 0, 0)
        assert _market_date_from_timestamp(quote_timestamp) == datetime(2026, 4, 29, 16, 0, 0).date()

    def test_midnight_utc_can_still_belong_to_previous_market_day(self):
        quote_timestamp = datetime(2026, 4, 30, 0, 30, 0)
        assert _market_date_from_timestamp(quote_timestamp) == datetime(2026, 4, 29, 20, 30, 0).date()


def test_sync_latest_quotes_derives_quote_date_from_alpaca_timestamp(monkeypatch):
    captured_rows: list[dict[str, object]] = []

    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda symbol_source=None, limit=None: ["AAPL"])
    monkeypatch.setattr(
        sync_latest_quotes,
        "fetch_latest_quotes",
        lambda symbols, session=None: {
            "AAPL": {
                "bp": 100.0,
                "ap": 100.5,
                "bs": 10,
                "as": 12,
                "t": "2026-04-29T20:00:00Z",
            }
        },
    )
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: captured_rows.extend(rows) or len(rows))

    summary = sync_latest_quotes.sync_latest_quotes(limit=1, batch_size=1)

    assert summary == {"symbols": 1, "rows_upserted": 1}
    assert len(captured_rows) == 1
    assert captured_rows[0]["quote_timestamp"] == datetime(2026, 4, 29, 20, 0, 0)
    assert captured_rows[0]["quote_date"] == datetime(2026, 4, 29, 16, 0, 0).date()


def test_sync_latest_quotes_historical_keeps_latest_quote_per_market_day(monkeypatch):
    captured_rows: list[dict[str, object]] = []

    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda symbol_source=None, limit=None: ["AAPL"])
    monkeypatch.setattr(
        sync_latest_quotes,
        "get_quote_snapshot_resume_state",
        lambda symbol, from_date, to_date, expected_dates=None: {
            "symbol": symbol,
            "has_expected_days": True,
            "is_complete": False,
            "expected_days": 2,
            "stored_days": 0,
            "missing_days": 2,
            "first_missing_date": from_date,
        },
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "fetch_historical_quotes",
        lambda symbol, **kwargs: [
            {"bp": 99.8, "ap": 100.2, "bs": 11, "as": 12, "t": "2026-04-29T14:00:00Z"},
            {"bp": 100.0, "ap": 100.5, "bs": 21, "as": 22, "t": "2026-04-29T20:00:00Z"},
            {"bp": 101.0, "ap": 101.4, "bs": 31, "as": 32, "t": "2026-04-30T19:30:00Z"},
        ],
    )
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: captured_rows.extend(rows) or len(rows))

    summary = sync_latest_quotes.sync_latest_quotes(
        limit=1,
        batch_size=50,
        from_date=date(2026, 4, 29),
        to_date=date(2026, 4, 30),
    )

    assert summary == {"symbols": 1, "rows_upserted": 2}
    assert [row["quote_date"] for row in captured_rows] == [date(2026, 4, 29), date(2026, 4, 30)]
    assert captured_rows[0]["quote_timestamp"] == datetime(2026, 4, 29, 20, 0, 0)
    assert captured_rows[1]["quote_timestamp"] == datetime(2026, 4, 30, 19, 30, 0)


def test_sync_latest_quotes_rejects_inverted_historical_period() -> None:
    with pytest.raises(ValueError, match="from_date"):
        sync_latest_quotes.sync_latest_quotes(
            from_date=date(2026, 5, 2),
            to_date=date(2026, 5, 1),
        )


def test_sync_latest_quotes_resolves_requested_symbol_source(monkeypatch) -> None:
    captured_sources: list[tuple[object, object]] = []

    monkeypatch.setattr(
        sync_latest_quotes,
        "list_symbols_for_source",
        lambda symbol_source=None, limit=None: captured_sources.append((symbol_source, limit)) or ["AAPL"],
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "fetch_latest_quotes",
        lambda symbols, session=None: {"AAPL": {"bp": 100.0, "ap": 100.4, "bs": 1, "as": 2, "t": "2026-04-29T20:00:00Z"}},
    )
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: len(rows))

    summary = sync_latest_quotes.sync_latest_quotes(limit=7, batch_size=10, symbol_source="stock_scores_history")

    assert summary == {"symbols": 1, "rows_upserted": 1}
    assert captured_sources == [("stock-scores-history", 7)]


def test_sync_latest_quotes_emits_historical_progress_logs(monkeypatch, caplog) -> None:
    import logging

    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda symbol_source=None, limit=None: ["AAPL", "MSFT"])
    monkeypatch.setattr(
        sync_latest_quotes,
        "get_quote_snapshot_resume_state",
        lambda symbol, from_date, to_date, expected_dates=None: {
            "symbol": symbol,
            "has_expected_days": True,
            "is_complete": False,
            "expected_days": 2,
            "stored_days": 0,
            "missing_days": 2,
            "first_missing_date": from_date,
        },
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "fetch_historical_quotes",
        lambda symbol, **kwargs: [
            {"bp": 100.0, "ap": 100.5, "bs": 10, "as": 12, "t": "2026-04-29T20:00:00Z"},
            {"bp": 101.0, "ap": 101.3, "bs": 8, "as": 9, "t": "2026-04-30T20:00:00Z"},
        ],
    )
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: len(rows))

    with caplog.at_level(logging.INFO):
        summary = sync_latest_quotes.sync_latest_quotes(
            from_date=date(2026, 4, 29),
            to_date=date(2026, 4, 30),
            symbol_source="stock_scores_all",
        )

    assert summary == {"symbols": 2, "rows_upserted": 4}
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "Sync latest quotes start | mode=historical symbol_source=stock-scores-all symbols=2" in messages
    assert "stage=fetch_start" in messages
    assert "progress=1/2" in messages
    assert "quotes_fetched=2" in messages
    assert "Sync latest quotes completed | mode=historical symbol_source=stock-scores-all symbols=2 rows_upserted=4" in messages


def test_sync_latest_quotes_historical_skips_symbol_when_period_already_covered(monkeypatch) -> None:
    fetch_calls: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda symbol_source=None, limit=None: ["AAPL"])
    monkeypatch.setattr(
        sync_latest_quotes,
        "get_quote_snapshot_resume_state",
        lambda symbol, from_date, to_date, expected_dates=None: {
            "symbol": symbol,
            "has_expected_days": True,
            "is_complete": True,
            "expected_days": 22,
            "stored_days": 22,
            "missing_days": 0,
            "first_missing_date": None,
        },
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "fetch_historical_quotes",
        lambda symbol, **kwargs: fetch_calls.append((symbol, kwargs)) or [],
    )
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: len(rows))

    summary = sync_latest_quotes.sync_latest_quotes(
        limit=1,
        from_date=date(2026, 4, 21),
        to_date=date(2026, 5, 21),
    )

    assert summary == {"symbols": 1, "rows_upserted": 0}
    assert fetch_calls == []


def test_sync_latest_quotes_historical_resumes_from_first_missing_date(monkeypatch) -> None:
    fetch_calls: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda symbol_source=None, limit=None: ["AAPL"])
    monkeypatch.setattr(
        sync_latest_quotes,
        "get_quote_snapshot_resume_state",
        lambda symbol, from_date, to_date, expected_dates=None: {
            "symbol": symbol,
            "has_expected_days": True,
            "is_complete": False,
            "expected_days": 22,
            "stored_days": 10,
            "missing_days": 12,
            "first_missing_date": date(2026, 5, 5),
        },
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "fetch_historical_quotes",
        lambda symbol, **kwargs: fetch_calls.append((symbol, kwargs)) or [
            {"bp": 100.0, "ap": 100.5, "bs": 10, "as": 12, "t": "2026-05-05T20:00:00Z"},
        ],
    )
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: len(rows))

    summary = sync_latest_quotes.sync_latest_quotes(
        limit=1,
        from_date=date(2026, 4, 21),
        to_date=date(2026, 5, 21),
    )

    assert summary == {"symbols": 1, "rows_upserted": 1}
    assert fetch_calls[0][0] == "AAPL"
    assert fetch_calls[0][1]["start"] == "2026-05-05"
    assert fetch_calls[0][1]["end"] == "2026-05-21"


def test_sync_latest_quotes_emits_latest_batch_progress_logs(monkeypatch, caplog) -> None:
    import logging

    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda symbol_source=None, limit=None: ["AAPL", "MSFT", "NVDA"])
    monkeypatch.setattr(
        sync_latest_quotes,
        "fetch_latest_quotes",
        lambda symbols, session=None: {
            symbol: {"bp": 100.0, "ap": 100.5, "bs": 10, "as": 12, "t": "2026-04-29T20:00:00Z"}
            for symbol in symbols
        },
    )
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: len(rows))

    with caplog.at_level(logging.INFO):
        summary = sync_latest_quotes.sync_latest_quotes(batch_size=2, symbol_source="candidates")

    assert summary == {"symbols": 3, "rows_upserted": 3}
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "Sync latest quotes start | mode=latest symbol_source=candidates symbols=3" in messages
    assert "batch=1/2" in messages
    assert "rows_in_batch=2" in messages
    assert "Sync latest quotes completed | mode=latest symbol_source=candidates symbols=3 rows_upserted=3" in messages


