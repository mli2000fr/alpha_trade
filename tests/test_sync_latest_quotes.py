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
from dataIntegrityEngine.sync_latest_quotes import (
    _fetch_near_close_quote_for_session,
    _iter_monthly_blocks,
    _market_date_from_timestamp,
    _parse_alpaca_timestamp,
    estimate_sync_latest_quotes_cost,
)


@pytest.fixture(autouse=True)
def _stub_symbol_has_any_quotes(monkeypatch):
    """Quick-check IEX : toujours True pour que les tests historiques passent."""
    monkeypatch.setattr(
        sync_latest_quotes,
        "_symbol_has_any_quotes_in_window",
        lambda symbol, from_date, to_date, *, session, account_id=None: True,
    )


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


def test_iter_monthly_blocks_splits_partial_month_boundaries() -> None:
    assert _iter_monthly_blocks(date(2026, 4, 29), date(2026, 6, 2)) == [
        (date(2026, 4, 29), date(2026, 4, 30)),
        (date(2026, 5, 1), date(2026, 5, 31)),
        (date(2026, 6, 1), date(2026, 6, 2)),
    ]


def test_estimate_sync_latest_quotes_cost_flags_large_historical_runs() -> None:
    estimate = estimate_sync_latest_quotes_cost(
        symbol_count=300,
        batch_size=50,
        from_date=date(2026, 1, 2),
        to_date=date(2026, 3, 31),
    )

    assert estimate["mode"] == "historical"
    assert int(estimate["trading_days"]) > 0
    assert int(estimate["hourly_windows"]) == 8
    assert int(estimate["estimated_api_calls"]) >= 300
    assert estimate["warning_required"] is True
    assert estimate["severity"] == "high"


def test_sync_latest_quotes_derives_quote_date_from_alpaca_timestamp(monkeypatch):
    captured_rows: list[dict[str, object]] = []

    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda symbol_source=None, limit=None: ["AAPL"])
    monkeypatch.setattr(
        sync_latest_quotes,
        "fetch_latest_quotes",
        lambda symbols, session=None, account_id=None: {
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
            "missing_ranges": [(from_date, to_date)],
        },
    )
    # Simule _fetch_near_close_quote_for_session : renvoie une quote différente par jour
    _call_count = {"count": 0}

    def _stub_fetch_near_close(symbol, session_date, *, session, account_id=None):
        _call_count["count"] += 1
        if _call_count["count"] == 1:
            return {"bp": 100.0, "ap": 100.5, "bs": 21, "as": 22, "t": "2026-04-29T20:00:00Z"}, 1, None
        else:
            return {"bp": 101.0, "ap": 101.4, "bs": 31, "as": 32, "t": "2026-04-30T19:30:00Z"}, 1, None

    monkeypatch.setattr(sync_latest_quotes, "_fetch_near_close_quote_for_session", _stub_fetch_near_close)
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
        lambda symbols, session=None, account_id=None: {"AAPL": {"bp": 100.0, "ap": 100.4, "bs": 1, "as": 2, "t": "2026-04-29T20:00:00Z"}},
    )
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: len(rows))

    summary = sync_latest_quotes.sync_latest_quotes(limit=7, batch_size=10, symbol_source="stock_scores_history")

    assert summary == {"symbols": 1, "rows_upserted": 1}
    assert captured_sources == [("stock-scores-history", 7)]


def test_sync_latest_quotes_passes_start_symbol_when_requested(monkeypatch) -> None:
    captured_sources: list[tuple[object, object, object]] = []

    monkeypatch.setattr(
        sync_latest_quotes,
        "list_symbols_for_source",
        lambda symbol_source=None, limit=None, start_symbol=None: captured_sources.append((symbol_source, limit, start_symbol)) or ["AAG"],
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "fetch_latest_quotes",
        lambda symbols, session=None, account_id=None: {"AAG": {"bp": 100.0, "ap": 100.4, "bs": 1, "as": 2, "t": "2026-04-29T20:00:00Z"}},
    )
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: len(rows))

    summary = sync_latest_quotes.sync_latest_quotes(
        limit=7,
        batch_size=10,
        symbol_source="stock_scores_history",
        start_symbol=" aag ",
    )

    assert summary == {"symbols": 1, "rows_upserted": 1}
    assert captured_sources == [("stock-scores-history", 7, "AAG")]


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
            "missing_ranges": [(from_date, to_date)],
        },
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "_fetch_near_close_quote_for_session",
        lambda symbol, session_date, *, session, account_id=None: (
            {"bp": 100.0, "ap": 100.5, "bs": 10, "as": 12, "t": "2026-04-29T20:00:00Z"}
            if session_date == date(2026, 4, 29)
            else {"bp": 101.0, "ap": 101.3, "bs": 8, "as": 9, "t": "2026-04-30T20:00:00Z"},
            1,
            None,
        ),
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
    assert "stage=fetch_range" in messages
    assert "progress=1/2" in messages
    assert "stage=symbol_summary" in messages
    assert "missing_ranges=1" in messages
    assert "missing_days=2" in messages
    assert "fetched_ranges=1" in messages
    assert "skipped_existing=False" in messages
    assert "stage=day_progress" in messages
    assert "api_calls=" in messages
    assert "days_fetched=" in messages
    assert "ranges_fetched=" in messages
    assert "Sync latest quotes completed | mode=historical symbol_source=stock-scores-all symbols=2 rows_upserted=4" in messages


def test_sync_latest_quotes_historical_skips_symbol_when_period_already_covered(monkeypatch, caplog) -> None:
    import logging

    fetch_calls: list[tuple[str, date]] = []

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
            "missing_ranges": [],
        },
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "_fetch_near_close_quote_for_session",
        lambda symbol, session_date, *, session, account_id=None: fetch_calls.append((symbol, session_date)) or (None, None, None),
    )
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: len(rows))

    with caplog.at_level(logging.INFO):
        summary = sync_latest_quotes.sync_latest_quotes(
            limit=1,
            from_date=date(2026, 4, 21),
            to_date=date(2026, 5, 21),
        )

    assert summary == {"symbols": 1, "rows_upserted": 0}
    assert fetch_calls == []
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "stage=symbol_summary" in messages
    assert "missing_ranges=0" in messages
    assert "missing_days=0" in messages
    assert "fetched_ranges=0" in messages
    assert "skipped_existing=True" in messages


def test_sync_latest_quotes_historical_resumes_from_first_missing_date(monkeypatch) -> None:
    fetch_calls: list[tuple[str, date]] = []

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
            "missing_ranges": [(date(2026, 5, 5), date(2026, 5, 5))],
        },
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "_fetch_near_close_quote_for_session",
        lambda symbol, session_date, *, session, account_id=None: fetch_calls.append((symbol, session_date))
        or ({"bp": 100.0, "ap": 100.5, "bs": 10, "as": 12, "t": "2026-05-05T20:00:00Z"}, 1, None),
    )
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: len(rows))

    summary = sync_latest_quotes.sync_latest_quotes(
        limit=1,
        from_date=date(2026, 4, 21),
        to_date=date(2026, 5, 21),
    )

    assert summary == {"symbols": 1, "rows_upserted": 1}
    assert len(fetch_calls) == 1
    assert fetch_calls[0][0] == "AAPL"
    assert fetch_calls[0][1] == date(2026, 5, 5)


def test_sync_latest_quotes_historical_fetches_only_missing_ranges(monkeypatch) -> None:
    fetch_calls: list[tuple[str, date]] = []

    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda symbol_source=None, limit=None: ["AAPL"])
    monkeypatch.setattr(
        sync_latest_quotes,
        "get_quote_snapshot_resume_state",
        lambda symbol, from_date, to_date, expected_dates=None: {
            "symbol": symbol,
            "has_expected_days": True,
            "is_complete": False,
            "expected_days": 10,
            "stored_days": 7,
            "missing_days": 3,
            "first_missing_date": date(2026, 5, 5),
            "missing_ranges": [
                (date(2026, 5, 5), date(2026, 5, 6)),
                (date(2026, 5, 20), date(2026, 5, 20)),
            ],
        },
    )

    def _stub_fetch(symbol, session_date, *, session, account_id=None):
        fetch_calls.append((symbol, session_date))
        ts = session_date.isoformat() + "T20:00:00Z"
        return {"bp": 100.0, "ap": 100.5, "bs": 10, "as": 12, "t": ts}, 1, None

    monkeypatch.setattr(sync_latest_quotes, "_fetch_near_close_quote_for_session", _stub_fetch)
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: len(rows))

    summary = sync_latest_quotes.sync_latest_quotes(
        limit=1,
        from_date=date(2026, 5, 1),
        to_date=date(2026, 5, 21),
    )

    assert summary == {"symbols": 1, "rows_upserted": 3}
    assert len(fetch_calls) == 3
    assert fetch_calls[0] == ("AAPL", date(2026, 5, 5))
    assert fetch_calls[1] == ("AAPL", date(2026, 5, 6))
    assert fetch_calls[2] == ("AAPL", date(2026, 5, 20))


def test_sync_latest_quotes_historical_persists_once_per_symbol(monkeypatch, caplog) -> None:
    import logging

    upserted_batches: list[list[dict[str, object]]] = []

    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda symbol_source=None, limit=None: ["AAPL"])
    monkeypatch.setattr(
        sync_latest_quotes,
        "get_quote_snapshot_resume_state",
        lambda symbol, from_date, to_date, expected_dates=None: {
            "symbol": symbol,
            "has_expected_days": True,
            "is_complete": False,
            "expected_days": 3,
            "stored_days": 0,
            "missing_days": 3,
            "first_missing_date": from_date,
            "missing_ranges": [(from_date, to_date)],
        },
    )

    def _stub_fetch(symbol, session_date, *, session, account_id=None):
        ts = session_date.isoformat() + "T20:00:00Z"
        return {"bp": 100.0, "ap": 100.5, "bs": 10, "as": 12, "t": ts}, 1, None

    monkeypatch.setattr(sync_latest_quotes, "_fetch_near_close_quote_for_session", _stub_fetch)
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: upserted_batches.append(list(rows)) or len(rows))

    with caplog.at_level(logging.INFO):
        summary = sync_latest_quotes.sync_latest_quotes(
            limit=1,
            from_date=date(2026, 4, 29),
            to_date=date(2026, 5, 1),
        )

    assert summary == {"symbols": 1, "rows_upserted": 3}
    # Un seul batch d'upsert pour tout le symbole (plus de persistance par bloc mensuel)
    assert len(upserted_batches) == 1
    assert [row["quote_date"] for row in upserted_batches[0]] == [
        date(2026, 4, 29),
        date(2026, 4, 30),
        date(2026, 5, 1),
    ]
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "stage=day_progress" in messages
    assert "stage=symbol_summary" in messages
    assert "days_fetched=3" in messages


def test_sync_latest_quotes_historical_skips_days_without_any_quote(monkeypatch, caplog) -> None:
    import logging

    fetch_calls: list[tuple[str, date]] = []

    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda symbol_source=None, limit=None: ["AAA"])
    monkeypatch.setattr(
        sync_latest_quotes,
        "get_quote_snapshot_resume_state",
        lambda symbol, from_date, to_date, expected_dates=None: {
            "symbol": symbol,
            "has_expected_days": True,
            "is_complete": False,
            "expected_days": 3,
            "stored_days": 0,
            "missing_days": 3,
            "first_missing_date": from_date,
            "missing_ranges": [(from_date, to_date)],
        },
    )
    # _fetch_near_close_quote_for_session renvoie None (aucune quote trouvée après toutes les fenêtres)
    monkeypatch.setattr(
        sync_latest_quotes,
        "_fetch_near_close_quote_for_session",
        lambda symbol, session_date, *, session, account_id=None: fetch_calls.append((symbol, session_date)) or (None, None, None),
    )
    monkeypatch.setattr(sync_latest_quotes, "upsert_quote_snapshots", lambda rows: len(rows))

    with caplog.at_level(logging.INFO):
        summary = sync_latest_quotes.sync_latest_quotes(
            limit=1,
            from_date=date(2026, 4, 29),
            to_date=date(2026, 5, 1),
        )

    assert summary == {"symbols": 1, "rows_upserted": 0}
    # Les appels ont bien eu lieu (on a essayé chaque jour), mais aucune quote trouvée
    assert len(fetch_calls) == 3
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "stage=symbol_summary" in messages
    assert "fetched_ranges=1" in messages


def test_sync_latest_quotes_emits_latest_batch_progress_logs(monkeypatch, caplog) -> None:
    import logging

    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda symbol_source=None, limit=None: ["AAPL", "MSFT", "NVDA"])
    monkeypatch.setattr(
        sync_latest_quotes,
        "fetch_latest_quotes",
        lambda symbols, session=None, account_id=None: {
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


