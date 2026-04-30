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
        lambda: type("_Parser", (), {"parse_args": lambda self: argparse.Namespace(limit=12, batch_size=34)})(),
    )
    monkeypatch.setattr(
        sync_latest_quotes,
        "sync_latest_quotes",
        lambda limit, batch_size: {"symbols": int(limit or 0), "rows_upserted": int(batch_size)},
    )

    sync_latest_quotes.main()

    payload = _payload_from_stdout(capsys.readouterr().out.strip(), sync_latest_quotes.RUN_SUMMARY_PREFIX)
    assert payload["requested_limit"] == 12
    assert payload["batch_size"] == 34
    assert payload["symbols"] == 12
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
                    limit=22,
                    sleep_seconds=1.4,
                    log_every=7,
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
    assert payload["requested_limit"] == 22
    assert payload["sleep_seconds"] == 1.4
    assert payload["log_every"] == 7
    assert payload["rows_upserted"] == 18


def test_sync_earnings_calendar_emits_operator_visible_logs(monkeypatch, caplog) -> None:
    monkeypatch.setattr(sync_earnings_calendar, "list_active_tradable_symbols", lambda limit=None: ["AAPL", "MSFT"])
    monkeypatch.setattr(
        sync_earnings_calendar,
        "fetch_multiple_symbols_earnings_calendar",
        lambda symbols, **kwargs: [
            {"symbol": "AAPL", "date": "2026-05-01", "epsEstimate": 1.23},
            {"symbol": "MSFT", "earningsDate": "2026-05-02", "epsActual": 2.34},
        ],
    )
    monkeypatch.setattr(sync_earnings_calendar, "upsert_earnings_calendar", lambda rows: len(rows))

    with caplog.at_level(logging.INFO):
        summary = sync_earnings_calendar.sync_earnings_calendar(
            from_date=date(2026, 4, 1),
            to_date=date(2026, 4, 30),
            limit=2,
            sleep_seconds=0.0,
            log_every=1,
        )

    assert summary == {"symbols": 2, "rows_upserted": 2}
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "Sync earnings calendar start" in messages
    assert "Sync earnings calendar fetched" in messages
    assert "Sync earnings calendar normalized" in messages


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
            {"parse_args": lambda self: argparse.Namespace(limit=30, sleep_seconds=1.2, log_every=9, refresh_stale_days=0)},
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
    assert payload["sleep_seconds"] == 1.2
    assert payload["log_every"] == 9
    assert payload["updated"] == 12
    assert payload["failed"] == 3

