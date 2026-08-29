from __future__ import annotations

import argparse
import json
import logging
from datetime import date

from dataIntegrityEngine import import_alpaca_assets, sync_earnings_calendar, sync_latest_quotes, update_sector
from service.finnhub import clientFinnhub


def _payload_from_stdout(stdout: str, prefix: str) -> dict[str, object]:
    assert stdout.startswith(prefix)
    return json.loads(stdout[len(prefix):])


def test_import_alpaca_assets_main_emits_structured_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(import_alpaca_assets, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        import_alpaca_assets,
        "fetch_alpaca_assets",
        lambda: [{"symbol": "AAPL", "id": "1"}, {"symbol": "MSFT", "id": "2"}],
    )
    monkeypatch.setattr(import_alpaca_assets, "insert_assets_to_db", lambda assets: len(list(assets)))

    import_alpaca_assets.main()

    payload = _payload_from_stdout(capsys.readouterr().out.strip(), import_alpaca_assets.RUN_SUMMARY_PREFIX)
    assert payload["assets_fetched"] == 2
    assert payload["rows_upserted"] == 2
    assert payload["run_id"]


def test_sync_latest_quotes_main_emits_structured_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sync_latest_quotes, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        sync_latest_quotes,
        "_build_arg_parser",
        lambda: type(
            "_Parser",
            (),
            {
                "parse_args": lambda self: argparse.Namespace(
                    from_date="2026-04-01",
                    to_date="2026-04-15",
                    symbol_source=None,
                    limit=12,
                    batch_size=34,
                )
            },
        )(),
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "sync_latest_quotes",
        lambda limit, batch_size, from_date=None, to_date=None, symbol_source=None: {"symbols": int(limit or 0), "rows_upserted": int(batch_size)},
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "build_quote_iex_vs_consolidated_bias_summary",
        lambda **kwargs: {
            "quote_iex_vs_consolidated_status": "ok",
            "quote_iex_vs_consolidated_bps": 42.5,
            "quote_iex_vs_consolidated_observations": 11,
        },
    )

    sync_latest_quotes.main()

    payload = _payload_from_stdout(capsys.readouterr().out.strip(), sync_latest_quotes.RUN_SUMMARY_PREFIX)
    assert payload["from_date"] == "2026-04-01"
    assert payload["to_date"] == "2026-04-15"
    assert payload["symbol_source"] == "active-tradable"
    assert payload["requested_limit"] == 12
    assert payload["batch_size"] == 34
    assert payload["symbols"] == 12
    assert payload["rows_upserted"] == 34
    assert payload["quote_iex_vs_consolidated_status"] == "ok"
    assert payload["quote_iex_vs_consolidated_bps"] == 42.5
    assert payload["quote_iex_vs_consolidated_observations"] == 11


def test_sync_latest_quotes_main_emits_failed_summary_when_sync_raises(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sync_latest_quotes, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(sync_latest_quotes, "record_quotes_audit_run", lambda **kwargs: None)
    monkeypatch.setattr(
        sync_latest_quotes,
        "_build_arg_parser",
        lambda: type(
            "_Parser",
            (),
            {
                "parse_args": lambda self: argparse.Namespace(
                    from_date="2026-04-01",
                    to_date="2026-04-15",
                    symbol_source="active-tradable",
                    limit=5,
                    batch_size=10,
                    start_symbol=" msft ",
                )
            },
        )(),
    )
    monkeypatch.setattr(sync_latest_quotes, "sync_latest_quotes", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    try:
        sync_latest_quotes.main()
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:  # pragma: no cover - garde défensive
        raise AssertionError("RuntimeError attendue")

    payload = _payload_from_stdout(capsys.readouterr().out.strip(), sync_latest_quotes.RUN_SUMMARY_PREFIX)
    assert payload["audit_status"] == "failed"
    assert payload["error_message"] == "RuntimeError('boom')"
    assert payload["symbol_source"] == "active-tradable"
    assert payload["start_symbol"] == "MSFT"
    assert payload["symbols"] == 0
    assert payload["rows_upserted"] == 0


def test_sync_latest_quotes_main_falls_back_to_unavailable_bias_summary_when_proxy_raises(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sync_latest_quotes, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(sync_latest_quotes, "record_quotes_audit_run", lambda **kwargs: None)
    monkeypatch.setattr(
        sync_latest_quotes,
        "_build_arg_parser",
        lambda: type(
            "_Parser",
            (),
            {
                "parse_args": lambda self: argparse.Namespace(
                    from_date="2026-04-01",
                    to_date="2026-04-15",
                    symbol_source="stock_scores_history",
                    limit=12,
                    batch_size=34,
                    start_symbol=None,
                )
            },
        )(),
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "sync_latest_quotes",
        lambda **kwargs: {"symbols": 12, "rows_upserted": 34},
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "build_quote_iex_vs_consolidated_bias_summary",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("bias helper down")),
    )

    sync_latest_quotes.main()

    payload = _payload_from_stdout(capsys.readouterr().out.strip(), sync_latest_quotes.RUN_SUMMARY_PREFIX)
    assert payload["audit_status"] == "success"
    assert payload["quote_iex_vs_consolidated_status"] == "unavailable"
    assert payload["quote_iex_vs_consolidated_window_mode"] == "historical"
    assert payload["quote_iex_vs_consolidated_window_start"] == "2026-04-01"
    assert payload["quote_iex_vs_consolidated_window_end"] == "2026-04-15"
    assert payload["quote_iex_vs_consolidated_symbol_scope"] == "stock-scores-history"
    assert payload["rows_upserted"] == 34


def test_sync_earnings_calendar_main_emits_structured_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sync_earnings_calendar, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        sync_earnings_calendar,
        "_build_arg_parser",
        lambda: type(
            "_Parser",
            (),
            {
                "parse_args": lambda self: argparse.Namespace(
                    from_date="2026-04-01",
                    to_date="2026-04-15",
                    symbol_source="active-tradable",
                    limit=22,
                    sleep_seconds=1.4,
                    log_every=7,
                    batch_size=50,
                    resume=True,
                    provider="finnhub",
                )
            },
        )(),
    )
    monkeypatch.setattr(
        sync_earnings_calendar,
        "sync_earnings_calendar",
        lambda **kwargs: {"symbols": 22, "rows_upserted": 18},
    )

    sync_earnings_calendar.main()

    payload = _payload_from_stdout(capsys.readouterr().out.strip(), sync_earnings_calendar.RUN_SUMMARY_PREFIX)
    assert payload["from_date"] == "2026-04-01"
    assert payload["to_date"] == "2026-04-15"
    assert payload["symbol_source"] == "active-tradable"
    assert payload["requested_limit"] == 22
    assert payload["sleep_seconds"] == 1.4
    assert payload["log_every"] == 7
    assert payload["batch_size"] == 50
    assert payload["resume"] is True
    assert payload["rows_upserted"] == 18


def test_sync_earnings_calendar_emits_operator_visible_logs(monkeypatch, caplog) -> None:
    monkeypatch.setattr(sync_earnings_calendar, "list_symbols_for_source", lambda symbol_source=None, limit=None: ["AAPL", "MSFT"])
    monkeypatch.setattr(
        sync_earnings_calendar,
        "fetch_earnings_calendar",
        lambda symbol, **kwargs: [{"symbol": symbol, "date": "2026-05-01", "epsEstimate": 1.23}],
    )
    monkeypatch.setattr(sync_earnings_calendar, "upsert_earnings_calendar", lambda rows: len(rows))
    monkeypatch.setattr(sync_earnings_calendar.time, "sleep", lambda seconds: None)

    with caplog.at_level(logging.INFO):
        summary = sync_earnings_calendar.sync_earnings_calendar(
            from_date=date(2026, 4, 1),
            to_date=date(2026, 4, 30),
            limit=2,
            sleep_seconds=0.0,
            log_every=1,
            batch_size=25,
        )

    assert summary["symbols"] == 2
    assert summary["rows_upserted"] == 2
    assert summary["batches_processed"] == 1
    assert summary["failed_symbols"] == 0
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "Sync earnings calendar start" in messages
    assert "Sync earnings calendar fetched" in messages
    assert "Sync earnings calendar normalized" in messages
    assert "Sync earnings calendar batch committed" in messages


def test_finnhub_earnings_batch_fetch_logs_progress(monkeypatch, caplog) -> None:
    def _fake_fetch(symbol: str, from_date: str, to_date: str, session=None) -> list[dict[str, object]]:
        return [{"symbol": symbol, "date": from_date, "to": to_date}]

    monkeypatch.setattr(clientFinnhub, "fetch_earnings_calendar", _fake_fetch)
    monkeypatch.setattr(clientFinnhub.time, "sleep", lambda seconds: None)

    with caplog.at_level(logging.INFO):
        rows = clientFinnhub.fetch_multiple_symbols_earnings_calendar(
            ["AAPL", "MSFT", "NVDA"],
            from_date="2026-04-01",
            to_date="2026-04-30",
            sleep_seconds=0.0,
            log_every=2,
        )

    assert [row["symbol"] for row in rows] == ["AAPL", "MSFT", "NVDA"]
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "processed=1/3" in messages
    assert "processed=2/3" in messages
    assert "processed=3/3" in messages


def test_update_sector_main_emits_structured_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(update_sector, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        update_sector,
        "_build_arg_parser",
        lambda: type(
            "_Parser",
            (),
            {
                "parse_args": lambda self: argparse.Namespace(
                    limit=30,
                    provider="yahoo_finance",
                    overwrite_existing=True,
                    sleep_seconds=1.2,
                    log_every=9,
                    refresh_stale_days=0,
                    symbols_file=None,
                    symbol_source="active-tradable",
                )
            },
        )(),
    )
    monkeypatch.setattr(
        update_sector,
        "update_missing_sectors",
        lambda **kwargs: {"total": 30, "updated": 12, "skipped": 15, "failed": 3},
    )

    update_sector.main()

    payload = _payload_from_stdout(capsys.readouterr().out.strip(), update_sector.RUN_SUMMARY_PREFIX)
    assert payload["requested_limit"] == 30
    assert payload["provider"] == "yahoo_finance"
    assert payload["overwrite_existing"] is True
    assert payload["sleep_seconds"] == 1.2
    assert payload["log_every"] == 9
    assert payload["updated"] == 12
    assert payload["failed"] == 3

