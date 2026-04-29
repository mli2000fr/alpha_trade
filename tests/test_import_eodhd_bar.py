"""Tests Phase 3 EODHD - import_eodhd_bar (T-EOD-4 plan §7.1).

Stratégie : on mocke ``fetch_eod_bulk`` / ``fetch_splits`` / ``fetch_eod`` et
on remplace la session DB par un FakeSession qui capture les statements SQL.

But des tests :
- bulk -> rows mappées vers les **2 tables**.
- mode dry-run = pas d'upsert.
- mode write = upsert appelé pour les 2 tables.
- provider != eodhd -> no-op.
- circuit-breaker / quota -> ne crashe pas, errors comptabilisé.
- run_summary contient les clés ``eodhd.*`` + ``cross_check_stooq.*``.
"""
from __future__ import annotations

from typing import Any

import pytest

from dataIntegrityEngine import import_eodhd_bar
from service.eodhd import accounts as eodhd_accounts
from service.eodhd import quota as eodhd_quota


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeSession:
    """Session SQLAlchemy minimaliste qui ne se connecte à rien."""

    def __init__(self) -> None:
        self.executed: list[Any] = []
        self.committed = 0
        self.rolled_back = 0
        self.closed = False

    def execute(self, stmt) -> Any:
        self.executed.append(stmt)
        class _R:
            rowcount = 0
        return _R()

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        self.rolled_back += 1

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def patched_env(monkeypatch, tmp_path):
    """Token + tracker isolé + tables mockées."""
    monkeypatch.setenv("EODHD_API_TOKEN", "TEST_TOKEN")
    eodhd_accounts.EodhdAccountRegistry.reset()
    eodhd_quota.reset_default_tracker()

    tracker = eodhd_quota.EodhdQuotaTracker(cache_dir=tmp_path)
    monkeypatch.setattr(eodhd_quota, "_DEFAULT_TRACKER", tracker, raising=False)

    # Mock _get_tables : dummies suffisants pour les statements SQLAlchemy
    from sqlalchemy import Column, MetaData, Table
    from sqlalchemy.types import BigInteger, Date, DateTime, Integer, Numeric, String
    md = MetaData()
    sm = Table("stock_metadata", md, Column("symbol", String(20), primary_key=True))
    sb = Table(
        "stock_bars", md,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("symbol", String(20)),
        Column("timeframe", String(5)),
        Column("timestamp", DateTime),
        Column("open_price", Numeric(20, 8)),
        Column("high_price", Numeric(20, 8)),
        Column("low_price", Numeric(20, 8)),
        Column("close_price", Numeric(20, 8)),
        Column("volume", BigInteger),
        Column("trade_count", BigInteger),
        Column("vwa_price", Numeric(20, 8)),
        Column("data_adjustment", String(16)),
        Column("data_source", String(16)),
    )
    sbd = Table(
        "stock_bars_daily", md,
        Column("symbol", String(20), primary_key=True),
        Column("date", Date, primary_key=True),
        Column("open", Numeric(20, 8)),
        Column("high", Numeric(20, 8)),
        Column("low", Numeric(20, 8)),
        Column("close", Numeric(20, 8)),
        Column("volume", BigInteger),
        Column("adj_close", Numeric(20, 8)),
        Column("vwap", Numeric(20, 8)),
        Column("daily_return", Numeric(10, 6)),
        Column("is_filled", Integer),
        Column("data_adjustment", String(16)),
        Column("data_source", String(16)),
    )
    monkeypatch.setattr(import_eodhd_bar, "_get_tables", lambda: (sm, sb, sbd))
    monkeypatch.setattr(import_eodhd_bar, "_get_active_tradable_symbols",
                        lambda session: ["AAPL", "NVDA", "BRK.B"])

    yield {"tracker": tracker, "tmp_path": tmp_path}
    eodhd_accounts.EodhdAccountRegistry.reset()
    eodhd_quota.reset_default_tracker()


@pytest.fixture
def fake_bulk_payload():
    return [
        {"code": "AAPL", "exchange_short_name": "US", "date": "2026-04-28",
         "open": 192.0, "high": 193.5, "low": 191.0, "close": 192.5,
         "adjusted_close": 192.5, "volume": 50_000_000},
        {"code": "NVDA", "exchange_short_name": "US", "date": "2026-04-28",
         "open": 165.0, "high": 167.0, "low": 164.0, "close": 165.5,
         "adjusted_close": 165.5, "volume": 200_000_000},
        # BRK-B pour tester le mapping inverse class-share
        {"code": "BRK-B", "exchange_short_name": "US", "date": "2026-04-28",
         "open": 410.0, "high": 412.0, "low": 408.0, "close": 411.0,
         "adjusted_close": 411.0, "volume": 4_000_000},
        # Hors univers : doit être ignoré
        {"code": "MSFT", "exchange_short_name": "US", "date": "2026-04-28",
         "open": 1, "high": 1, "low": 1, "close": 1, "adjusted_close": 1, "volume": 1},
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_resolve_bars_provider_default_alpaca():
    assert import_eodhd_bar.resolve_bars_provider({}) == "alpaca"
    assert import_eodhd_bar.resolve_bars_provider({"market_data": {"bars_provider": "EODHD"}}) == "eodhd"


def test_get_active_tradable_symbols_orders_by_symbol(monkeypatch):
    from sqlalchemy import Boolean, Column, MetaData, String, Table

    md = MetaData()
    sm = Table(
        "stock_metadata",
        md,
        Column("symbol", String(20), primary_key=True),
        Column("status", String(20)),
        Column("tradable", Boolean),
        Column("bars_available", Boolean),
        Column("asset_class", String(20)),
        Column("history_status", String(32)),
    )
    monkeypatch.setattr(import_eodhd_bar, "_get_tables", lambda: (sm, None, None))

    captured = {}

    class _Session:
        def execute(self, stmt):
            captured["sql"] = str(stmt)

            class _R:
                def all(self_inner):
                    return [("A",), ("AAPL",), ("AGHG",)]

            return _R()

    symbols = import_eodhd_bar._get_active_tradable_symbols(_Session())

    assert symbols == ["A", "AAPL", "AGHG"]
    assert "ORDER BY" in captured["sql"]


def test_dry_run_no_db_writes(monkeypatch, patched_env, fake_bulk_payload):
    monkeypatch.setattr(import_eodhd_bar, "fetch_eod_bulk",
                        lambda **kwargs: fake_bulk_payload)
    monkeypatch.setattr(import_eodhd_bar, "fetch_splits",
                        lambda symbol, **kwargs: [])

    session = _FakeSession()
    summary = import_eodhd_bar.run_eodhd_ingestion(
        dry_run=True,
        target_date="2026-04-28",
        symbols=None,
        enable_stooq_cross_check=False,
        config={},
        session=session,
        tracker=patched_env["tracker"],
    )

    assert summary["mode"] == "dry_run"
    assert summary["targeted_symbols"] == 3
    assert summary["bulk_size"] == 4
    assert summary["matched_in_bulk"] == 3  # AAPL, NVDA, BRK.B (MSFT ignoré)
    assert summary["rows_upserted_stock_bars"] == 0
    assert summary["rows_upserted_stock_bars_daily"] == 0
    # Une lecture d'ancre d'historique, mais aucune écriture SQL en dry-run.
    assert len(session.executed) == 1
    assert session.committed == 0
    # Clés run_summary plan §8.1
    assert "eodhd" in summary
    assert summary["eodhd"]["data_source"] == "eodhd_eod"
    assert summary["eodhd"]["bulk_size"] == 4


def test_write_mode_upserts_both_tables(monkeypatch, patched_env, fake_bulk_payload):
    monkeypatch.setattr(import_eodhd_bar, "fetch_eod_bulk",
                        lambda **kwargs: fake_bulk_payload)
    monkeypatch.setattr(import_eodhd_bar, "fetch_splits",
                        lambda symbol, **kwargs: [])

    session = _FakeSession()
    summary = import_eodhd_bar.run_eodhd_ingestion(
        dry_run=False,
        target_date="2026-04-28",
        symbols=None,
        enable_stooq_cross_check=False,
        config={},
        session=session,
        tracker=patched_env["tracker"],
    )

    assert summary["mode"] == "write"
    assert summary["rows_upserted_stock_bars_daily"] == 3
    assert summary["rows_upserted_stock_bars"] == 3
    # 1 select ancre + 2 statements d'upsert.
    assert len(session.executed) == 3
    assert session.committed >= 1


def test_missing_from_bulk_recovered_via_per_symbol(monkeypatch, patched_env):
    # Bulk vide -> tous les symboles univers manquants
    monkeypatch.setattr(import_eodhd_bar, "fetch_eod_bulk", lambda **kwargs: [])
    monkeypatch.setattr(import_eodhd_bar, "fetch_splits",
                        lambda symbol, **kwargs: [])

    def _fake_eod(symbol, **kwargs):
        return [{
            "date": "2026-04-28", "open": 1.0, "high": 1.0, "low": 1.0,
            "close": 1.0, "adjusted_close": 1.0, "volume": 100,
        }]
    monkeypatch.setattr(import_eodhd_bar, "fetch_eod", _fake_eod)

    session = _FakeSession()
    summary = import_eodhd_bar.run_eodhd_ingestion(
        dry_run=True,
        target_date="2026-04-28",
        per_symbol_limit=10,
        enable_stooq_cross_check=False,
        config={},
        session=session,
        tracker=patched_env["tracker"],
    )

    assert summary["missing_from_bulk"] == 3
    assert summary["per_symbol_recovered"] == 3


def test_existing_history_is_caught_up_until_target_date(monkeypatch, patched_env, fake_bulk_payload):
    monkeypatch.setattr(import_eodhd_bar, "fetch_eod_bulk", lambda **kwargs: fake_bulk_payload)
    monkeypatch.setattr(import_eodhd_bar, "fetch_splits", lambda symbol, **kwargs: [])
    monkeypatch.setattr(
        import_eodhd_bar,
        "_get_latest_bar_dates",
        lambda session, symbols: {"AAPL": import_eodhd_bar.date(2026, 4, 24)},
    )

    fetch_calls: list[tuple[str, str, str]] = []

    def _fake_eod(symbol, **kwargs):
        fetch_calls.append((symbol, kwargs["start"], kwargs["end"]))
        return [
            {
                "date": "2026-04-25",
                "open": 190.0,
                "high": 191.0,
                "low": 189.0,
                "close": 190.5,
                "adjusted_close": 190.5,
                "volume": 10,
            },
            {
                "date": "2026-04-27",
                "open": 191.0,
                "high": 192.0,
                "low": 190.0,
                "close": 191.5,
                "adjusted_close": 191.5,
                "volume": 11,
            },
        ]

    monkeypatch.setattr(import_eodhd_bar, "fetch_eod", _fake_eod)

    summary = import_eodhd_bar.run_eodhd_ingestion(
        dry_run=False,
        target_date="2026-04-28",
        enable_stooq_cross_check=False,
        config={},
        session=_FakeSession(),
        tracker=patched_env["tracker"],
    )

    assert fetch_calls == [("AAPL", "2026-04-25", "2026-04-27")]
    assert summary["symbols_with_existing_history"] == 1
    assert summary["catchup_symbols"] == 1
    assert summary["catchup_days_requested"] == 3
    # AAPL = 2 jours catch-up + 1 jour bulk cible ; NVDA et BRK.B = bulk cible.
    assert summary["rows_upserted_stock_bars_daily"] == 5
    assert summary["rows_upserted_stock_bars"] == 5


def test_bulk_unavailable_records_error_does_not_crash(monkeypatch, patched_env):
    from service.eodhd.clientEodhd import EodhdBarsFetchError

    def _boom(**kwargs):
        raise EodhdBarsFetchError("HTTP 423 simulated")
    monkeypatch.setattr(import_eodhd_bar, "fetch_eod_bulk", _boom)
    monkeypatch.setattr(import_eodhd_bar, "fetch_eod",
                        lambda symbol, **kwargs: [])

    session = _FakeSession()
    summary = import_eodhd_bar.run_eodhd_ingestion(
        dry_run=True,
        target_date="2026-04-28",
        enable_stooq_cross_check=False,
        config={},
        session=session,
        tracker=patched_env["tracker"],
    )

    assert summary["errors"] >= 1
    assert summary["bulk_size"] == 0
    assert summary["rows_upserted_stock_bars"] == 0


def test_circuit_open_during_splits_stops_run_cleanly(monkeypatch, patched_env, fake_bulk_payload):
    tracker = patched_env["tracker"]
    tracker.failure_threshold = 1
    monkeypatch.setattr(import_eodhd_bar, "fetch_eod_bulk", lambda **kwargs: fake_bulk_payload)

    calls: list[str] = []

    def _fake_cached_splits(symbol, **kwargs):
        calls.append(symbol)
        tracker.record_failure("splits", count_call=True, count_towards_circuit=True)
        return []

    monkeypatch.setattr(import_eodhd_bar, "_cached_fetch_splits", _fake_cached_splits)

    summary = import_eodhd_bar.run_eodhd_ingestion(
        dry_run=True,
        target_date="2026-04-28",
        enable_stooq_cross_check=False,
        config={},
        session=_FakeSession(),
        tracker=tracker,
    )

    assert calls == ["AAPL"]
    assert summary["stopped_reason"] in {"circuit_open_after_fetch", "circuit_open"}
    assert summary["eodhd"]["circuit_open"] is True
    assert summary["errors"] == 0


def test_preferred_series_symbol_is_skipped_before_per_symbol_fallback_and_marked_unavailable(monkeypatch, patched_env):
    monkeypatch.setattr(import_eodhd_bar, "fetch_eod_bulk", lambda **kwargs: [])
    monkeypatch.setattr(import_eodhd_bar, "_get_active_tradable_symbols", lambda session: ["ABR.PRD"])

    fetch_calls: list[str] = []
    bars_unavailable_calls: list[str] = []

    monkeypatch.setattr(
        import_eodhd_bar,
        "fetch_eod",
        lambda symbol, **kwargs: fetch_calls.append(symbol) or [],
    )
    monkeypatch.setattr(
        import_eodhd_bar,
        "update_bars_available_false",
        lambda symbol: bars_unavailable_calls.append(symbol),
    )

    summary = import_eodhd_bar.run_eodhd_ingestion(
        dry_run=False,
        target_date="2026-04-28",
        enable_stooq_cross_check=False,
        config={},
        session=_FakeSession(),
        tracker=patched_env["tracker"],
    )

    assert fetch_calls == []
    assert bars_unavailable_calls == ["ABR.PRD"]
    assert summary["unsupported_fallback_symbols"] == 1
    assert summary["metadata_marked_unavailable"] == 1


def test_explicit_symbols_skip_universe_query(monkeypatch, patched_env, fake_bulk_payload):
    monkeypatch.setattr(import_eodhd_bar, "fetch_eod_bulk",
                        lambda **kwargs: fake_bulk_payload)
    monkeypatch.setattr(import_eodhd_bar, "fetch_splits",
                        lambda symbol, **kwargs: [])

    # On ne devrait PAS appeler _get_active_tradable_symbols quand symbols est fourni
    def _should_not_be_called(session):
        raise AssertionError("ne doit pas être appelé quand symbols=[...]")
    monkeypatch.setattr(import_eodhd_bar, "_get_active_tradable_symbols",
                        _should_not_be_called)

    session = _FakeSession()
    summary = import_eodhd_bar.run_eodhd_ingestion(
        dry_run=True,
        target_date="2026-04-28",
        symbols=["AAPL"],
        enable_stooq_cross_check=False,
        config={},
        session=session,
        tracker=patched_env["tracker"],
    )

    assert summary["targeted_symbols"] == 1
    assert summary["matched_in_bulk"] == 1


def test_run_summary_keys_compliance_plan_section_8_1(
    monkeypatch, patched_env, fake_bulk_payload
):
    """Vérifie la présence des clés normalisées du plan §8.1."""
    monkeypatch.setattr(import_eodhd_bar, "fetch_eod_bulk",
                        lambda **kwargs: fake_bulk_payload)
    monkeypatch.setattr(import_eodhd_bar, "fetch_splits",
                        lambda symbol, **kwargs: [])

    summary = import_eodhd_bar.run_eodhd_ingestion(
        dry_run=True,
        target_date="2026-04-28",
        enable_stooq_cross_check=False,
        config={},
        session=_FakeSession(),
        tracker=patched_env["tracker"],
    )

    eodhd = summary["eodhd"]
    for key in (
        "calls_used", "calls_failed", "circuit_open",
        "bulk_size", "symbols_missing",
        "rows_upserted_stock_bars", "rows_upserted_stock_bars_daily",
    ):
        assert key in eodhd, f"clé eodhd.{key} manquante (plan §8.1)"

    cross = summary["cross_check_stooq"]
    assert "anomalies_count" in cross and "failed" in cross


def test_main_noop_when_provider_alpaca(monkeypatch, capsys):
    """``bars_provider=alpaca`` -> exit 0 et pas d'ingestion."""
    monkeypatch.setattr(import_eodhd_bar, "_load_config_safe",
                        lambda: {"market_data": {"bars_provider": "alpaca"}})
    # Garde-fou : si on entre dans le pipeline, fetch_eod_bulk lèvera
    monkeypatch.setattr(import_eodhd_bar, "fetch_eod_bulk",
                        lambda **kwargs: pytest.fail("ne doit pas être appelé"))
    # Évite l'init du logger fichier (pas de répertoire ./log/ en CI)
    monkeypatch.setattr(import_eodhd_bar, "configure_root_logging",
                        lambda **kwargs: None)

    rc = import_eodhd_bar.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha_trade_run_summary" in out
    assert '"mode": "noop"' in out or '"mode":"noop"' in out

