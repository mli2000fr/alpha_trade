from __future__ import annotations

from types import SimpleNamespace

from ihm.pages.batches import (
    _batch_title,
    _last_run_failed,
    _windows_last_run_failed,
)
from scripts import send_batch_email as notifier


def _args(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "status": "ERROR",
        "requested": None,
        "received": None,
        "persisted": None,
        "failed": None,
        "alerts": None,
        "error_message": "",
        "warning": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_notification_metrics_are_read_from_normalized_summary() -> None:
    log = (
        '::alpha_trade_run_summary::{"requested":100,"received":90,'
        '"persisted":80,"failed":10,"warnings":["quota"],'
        '"error_message":"HTTP 429"}'
    )
    assert notifier._build_metrics(_args(), log) == {
        "requested": 100,
        "received": 90,
        "persisted": 80,
        "failed": 10,
        "alerts": 1,
        "error_message": "HTTP 429",
    }


def test_notification_keeps_summary_after_verbose_log_truncation(tmp_path) -> None:
    log = tmp_path / "verbose_run.log"
    summary = (
        '::alpha_trade_run_summary::{"requested":1798,"received":1660,'
        '"persisted":1660,"failed":0,"warnings":[]}'
    )
    log.write_text("\n".join(["stderr " + "x" * 100] * 500 + [summary]), encoding="utf-8")
    visible = notifier._read_run_log(str(log), max_lines=300, max_chars=20000)
    metrics = notifier._build_metrics(_args(status="OK"), visible)
    assert metrics["requested"] == 1798
    assert metrics["received"] == 1660
    assert metrics["persisted"] == 1660
    assert metrics["failed"] == 0


def test_failed_notification_never_reports_zero_failures() -> None:
    metrics = notifier._build_metrics(
        _args(), "RuntimeError: source indisponible",
    )
    assert metrics["failed"] == 1
    assert metrics["error_message"] == "RuntimeError: source indisponible"


def test_telegram_is_attempted_even_when_email_raises(monkeypatch, tmp_path) -> None:
    log = tmp_path / "run.log"
    log.write_text("ValueError: test failure", encoding="utf-8")
    monkeypatch.setattr(
        "ihm.services.email_notifier.send_notification",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("smtp down")),
    )
    calls: list[object] = []
    monkeypatch.setattr(notifier, "_send_telegram_status", lambda args: calls.append(args) or True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "send_batch_email.py", "--event", "test_batch", "--status", "ERROR",
            "--exit-code", "1", "--log-file", str(log),
        ],
    )
    assert notifier.main() == 0
    assert len(calls) == 1
    assert calls[0].metrics["failed"] == 1


def test_failed_batch_title_is_red_and_bold() -> None:
    row = {"status": "FAILED"}
    assert _last_run_failed(row)
    title = _batch_title(["🔴 P0", "🟢 Installé"], "daily_bars_sync", row)
    assert title.startswith(":red[**")
    assert title.endswith("**]")
    assert "daily_bars_sync" in title


def test_successful_batch_title_keeps_normal_style() -> None:
    title = _batch_title(["🔴 P0"], "daily_bars_sync", {"status": "COMPLETED"})
    assert title == "🔴 P0 — daily_bars_sync"


def test_metrics_aggregate_multiple_provider_summaries() -> None:
    log = "\n".join(
        [
            '::alpha_trade_run_summary::{"requested":100,"received":90,"persisted":80,"failed":10}',
            '::alpha_trade_run_summary::{"requested":100,"received":95,"persisted":85,"failed":5}',
        ]
    )
    metrics = notifier._build_metrics(_args(status="OK"), log)
    assert metrics["requested"] == 200
    assert metrics["received"] == 185
    assert metrics["persisted"] == 165
    assert metrics["failed"] == 15


def test_analyst_summary_sums_persisted_rows_and_alerts() -> None:
    log = (
        '::alpha_trade_run_summary::{"requested_symbols":10,"successful_symbols":8,'
        '"failed_symbols":2,"estimates_rows_inserted":4,"eps_trend_rows_inserted":3,'
        '"targets_rows_inserted":2,"rate_limit_count":1,"parse_error_count":2}'
    )
    metrics = notifier._build_metrics(_args(status="OK"), log)
    assert metrics["persisted"] == 9
    assert metrics["alerts"] == 3


def test_telegram_contains_counts_and_failure_message(monkeypatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr("service.telegram.is_telegram_configured", lambda: True)
    monkeypatch.setattr(
        "service.telegram.send_telegram_message",
        lambda message: sent.append(message) or True,
    )
    args = SimpleNamespace(
        status="ERROR",
        event="daily_bars_sync",
        duration="2m",
        exit_code=1,
        warning=[],
        passage="secours",
        metrics={
            "requested": 100,
            "received": 80,
            "persisted": 75,
            "failed": 20,
            "alerts": 3,
            "error_message": "HTTP 503",
        },
    )
    assert notifier._send_telegram_status(args)
    assert len(sent) == 1
    assert "Demandés 100 · reçus 80 · persistés 75 · échecs 20 · alertes 3" in sent[0]
    assert "Erreur : HTTP 503" in sent[0]
    assert "Passage : second passage (secours conditionnel)" in sent[0]


def test_error_email_event_and_payload_identify_primary_passage(monkeypatch, tmp_path) -> None:
    log = tmp_path / "run.log"
    log.write_text("RuntimeError: test failure", encoding="utf-8")
    sent: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "ihm.services.email_notifier.send_notification",
        lambda event, payload: sent.append((event, payload)) or True,
    )
    monkeypatch.setattr(notifier, "_send_telegram_status", lambda _args: True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "send_batch_email.py", "--event", "snapshot", "--status", "ERROR",
            "--exit-code", "1", "--log-file", str(log), "--passage", "principal",
        ],
    )
    assert notifier.main() == 0
    assert sent[0][0] == "snapshot_premier_passage_error"
    assert sent[0][1]["passage"] == "principal"
    assert sent[0][1]["passage_label"] == "premier passage (principal)"


def test_windows_failure_marks_legacy_batch_title_red() -> None:
    task = {
        "state": "Ready",
        "last_run_time": "2026-09-13T11:00:00+02:00",
        "last_result": 1,
    }
    assert _windows_last_run_failed(task)
    title = _batch_title(["🔴 P0"], "market_cap_sync", None, task)
    assert title.startswith(":red[**")


def test_running_windows_task_does_not_reuse_previous_failure() -> None:
    task = {"state": "Running", "last_run_time": "2026-09-13T11:00:00+02:00", "last_result": 1}
    assert not _windows_last_run_failed(task)
