"""Tests Sprint S27 — service notifications email IHM."""
from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest

from ihm.services import notifications as notif_mod
from ihm.services import notifications_preferences as np_mod
from ihm.services.notifications import (
    SmtpConfig,
    build_workflow_email,
    collect_failed_step_context,
    notify_run_finished,
    send_email,
)
from ihm.services.notifications_preferences import NotificationPreferences


@pytest.fixture(autouse=True)
def _isolate_preferences(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "notifications.json"
    monkeypatch.setattr(np_mod, "PREFERENCES_DIR", tmp_path)
    monkeypatch.setattr(np_mod, "NOTIFICATIONS_PREFERENCES_PATH", target)


def _make_step_record(tmp_path: Path, *, status: str = "completed", run_id: str = "step-1") -> dict[str, Any]:
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    combined = run_dir / "combined.log"
    stderr = run_dir / "stderr.log"
    combined.write_text("line A\nline B\nfatal error: boom\n", encoding="utf-8")
    stderr.write_text("Traceback ...\nValueError: boom\n", encoding="utf-8")
    return {
        "run_id": run_id,
        "step_key": "scoring",
        "step_label": "10. Scoring",
        "status": status,
        "run_kind": "step",
        "parent_run_id": None,
        "account_id": "default",
        "executed_at": "2026-05-07T10:00:00",
        "actual_started_at": "2026-05-07T10:00:00",
        "finished_at": "2026-05-07T10:01:00",
        "duration_seconds": 60.0,
        "returncode": 0 if status == "completed" else 1,
        "combined_path": str(combined),
        "stderr_path": str(stderr),
        "stdout_path": str(combined),
    }


def test_build_workflow_email_failed_includes_log_excerpt(tmp_path: Path) -> None:
    record = _make_step_record(tmp_path, status="failed")
    msg = build_workflow_email(
        record,
        recipients=["a@b.com", "c@d.fr"],
        sender="bot@alpha.io",
        failed_child=record,
        log_excerpt="Traceback ...\nValueError: boom\n",
    )
    assert isinstance(msg, EmailMessage)
    assert "FAILED" in msg["Subject"]
    assert msg["To"] == "a@b.com, c@d.fr"
    body_part = msg.get_body(("plain",))
    body = body_part.get_content() if body_part is not None else ""
    assert "ValueError: boom" in body
    assert "Étape fautive" in body
    # Une pièce jointe au moins (combined.log).
    attachments = list(msg.iter_attachments())
    assert attachments, "log doit être attaché"


def test_build_workflow_email_completed_no_failed_block(tmp_path: Path) -> None:
    record = _make_step_record(tmp_path, status="completed")
    msg = build_workflow_email(
        record,
        recipients=["a@b.com"],
        sender="bot@alpha.io",
        failed_child=None,
        log_excerpt="",
    )
    assert "COMPLETED" in msg["Subject"]
    body_part = msg.get_body(("plain",))
    body = body_part.get_content() if body_part is not None else ""
    assert "Étape fautive" not in body


def test_collect_failed_step_context_for_workflow(monkeypatch, tmp_path: Path) -> None:
    workflow_dir = tmp_path / "wf-1"
    workflow_dir.mkdir()
    (workflow_dir / "combined.log").write_text("workflow log\n", encoding="utf-8")

    child_failed = _make_step_record(tmp_path, status="failed", run_id="child-2")
    child_ok = _make_step_record(tmp_path, status="completed", run_id="child-1")

    workflow_record = {
        "run_id": "wf-1",
        "status": "failed",
        "run_kind": "workflow",
        "workflow_child_run_ids": [child_ok["run_id"], child_failed["run_id"]],
        "workflow_current_child_run_id": child_failed["run_id"],
        "combined_path": str(workflow_dir / "combined.log"),
    }

    def fake_get(run_id: str) -> dict[str, Any] | None:
        return {"child-1": child_ok, "child-2": child_failed}.get(run_id)

    monkeypatch.setattr(
        "ihm.services.process_registry.get_pipeline_run_record",
        fake_get,
        raising=False,
    )

    failed, tail = collect_failed_step_context(workflow_record)
    assert failed is not None
    assert failed["run_id"] == "child-2"
    assert "ValueError" in tail


def test_collect_failed_step_context_workflow_completed_returns_empty(tmp_path: Path) -> None:
    workflow_record = {
        "run_id": "wf-ok",
        "status": "completed",
        "run_kind": "workflow",
        "workflow_child_run_ids": [],
        "combined_path": "",
    }
    failed, tail = collect_failed_step_context(workflow_record)
    assert failed is None and tail == ""


def test_send_email_uses_smtp_starttls(monkeypatch) -> None:
    sent: dict[str, Any] = {}

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int = 30) -> None:
            sent["host"] = host
            sent["port"] = port
            sent["tls"] = False

        def __enter__(self) -> "FakeSMTP":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def ehlo(self) -> None:
            sent.setdefault("ehlo", 0)
            sent["ehlo"] += 1

        def starttls(self, context: Any = None) -> None:
            sent["tls"] = True

        def login(self, user: str, pwd: str) -> None:
            sent["login"] = (user, pwd)

        def send_message(self, msg: EmailMessage) -> None:
            sent["msg_subject"] = msg["Subject"]

    monkeypatch.setattr(notif_mod.smtplib, "SMTP", FakeSMTP)

    msg = EmailMessage()
    msg["Subject"] = "hello"
    msg["From"] = "f@x.io"
    msg["To"] = "t@x.io"
    msg.set_content("body")

    cfg = SmtpConfig(host="smtp.x.io", port=587, username="u", password="p", sender="f@x.io", use_tls=True)
    assert send_email(msg, cfg) is True
    assert sent["tls"] is True
    assert sent["login"] == ("u", "p")
    assert sent["msg_subject"] == "hello"


def test_send_email_returns_false_when_unconfigured() -> None:
    msg = EmailMessage()
    msg["Subject"] = "x"
    cfg = SmtpConfig(host="", port=0, username=None, password=None, sender="")
    assert send_email(msg, cfg) is False


def test_notify_run_finished_anti_doublon(monkeypatch, tmp_path: Path) -> None:
    record = _make_step_record(tmp_path, status="completed", run_id="r1")
    prefs = NotificationPreferences(recipients=["a@b.com"], enabled=True, notify_on=["completed"])
    cfg = SmtpConfig(host="smtp.x", port=25, username=None, password=None, sender="f@x.io", use_tls=False)

    sends: list[str] = []

    def fake_send(message: EmailMessage, smtp_config: SmtpConfig) -> bool:
        sends.append(str(message["Subject"]))
        return True

    monkeypatch.setattr(notif_mod, "send_email", fake_send)

    assert notify_run_finished(record, prefs=prefs, smtp_config=cfg) is True
    assert notify_run_finished(record, prefs=prefs, smtp_config=cfg) is False
    assert len(sends) == 1
    flag = Path(record["combined_path"]).parent / "notification_sent.flag"
    assert flag.exists()


def test_notify_run_finished_skips_subruns(monkeypatch, tmp_path: Path) -> None:
    record = _make_step_record(tmp_path, status="failed", run_id="child")
    record["parent_run_id"] = "wf-x"
    prefs = NotificationPreferences(recipients=["a@b.com"], enabled=True, notify_on=["failed"])
    cfg = SmtpConfig(host="smtp.x", port=25, username=None, password=None, sender="f@x.io")
    monkeypatch.setattr(notif_mod, "send_email", lambda *_a, **_k: True)
    assert notify_run_finished(record, prefs=prefs, smtp_config=cfg) is False


def test_notify_run_finished_respects_disabled(monkeypatch, tmp_path: Path) -> None:
    record = _make_step_record(tmp_path, status="failed", run_id="r2")
    prefs = NotificationPreferences(recipients=["a@b.com"], enabled=False, notify_on=["failed"])
    cfg = SmtpConfig(host="smtp.x", port=25, username=None, password=None, sender="f@x.io")
    monkeypatch.setattr(notif_mod, "send_email", lambda *_a, **_k: True)
    assert notify_run_finished(record, prefs=prefs, smtp_config=cfg) is False


def test_notify_run_finished_filters_status(monkeypatch, tmp_path: Path) -> None:
    record = _make_step_record(tmp_path, status="completed", run_id="r3")
    prefs = NotificationPreferences(recipients=["a@b.com"], enabled=True, notify_on=["failed"])
    cfg = SmtpConfig(host="smtp.x", port=25, username=None, password=None, sender="f@x.io")
    monkeypatch.setattr(notif_mod, "send_email", lambda *_a, **_k: True)
    assert notify_run_finished(record, prefs=prefs, smtp_config=cfg) is False


def test_notify_run_finished_skips_non_terminal(tmp_path: Path) -> None:
    record = _make_step_record(tmp_path, status="running", run_id="r4")
    assert notify_run_finished(record) is False


def test_notify_run_finished_does_not_raise_on_failure(monkeypatch, tmp_path: Path) -> None:
    record = _make_step_record(tmp_path, status="completed", run_id="r5")
    prefs = NotificationPreferences(recipients=["a@b.com"], enabled=True, notify_on=["completed"])
    cfg = SmtpConfig(host="smtp.x", port=25, username=None, password=None, sender="f@x.io")

    def boom(*_a: Any, **_k: Any) -> bool:
        raise RuntimeError("smtp down")

    monkeypatch.setattr(notif_mod, "send_email", boom)
    assert notify_run_finished(record, prefs=prefs, smtp_config=cfg) is False
    flag = Path(record["combined_path"]).parent / "notification_sent.flag"
    assert not flag.exists()  # pas de marqueur si échec → permet retry



