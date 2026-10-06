"""CN batch notification contracts without SMTP or Telegram traffic."""

import json
import sys

from scripts import send_batch_email


def test_cn_failure_notification_includes_counts_error_and_passage(monkeypatch, tmp_path):
    log = tmp_path / "run.txt"
    log.write_text("::alpha_trade_run_summary::" + json.dumps({
        "batch": "cn_oracle_prospective_daily", "status": "FAILED",
        "requested": 209, "received": 180, "persisted": 0,
        "failed": 1, "warning_count": 2,
        "error_message": "CN daily source collection is incomplete",
    }) + "\n", encoding="utf-8")
    emails = []
    messages = []
    monkeypatch.setattr("ihm.services.email_notifier.send_notification",
                        lambda **kwargs: emails.append(kwargs) or True)
    monkeypatch.setattr("service.telegram.is_telegram_configured", lambda: True)
    monkeypatch.setattr("service.telegram.send_telegram_message",
                        lambda message: messages.append(message) or True)
    monkeypatch.setattr(sys, "argv", ["send_batch_email.py", "--event",
                        "cn_oracle_prospective_daily", "--status", "ERROR",
                        "--exit-code", "1", "--log-file", str(log),
                        "--passage", "principal"])
    assert send_batch_email.main() == 0
    assert emails[0]["event"] == "cn_oracle_prospective_daily_premier_passage_error"
    assert emails[0]["payload"]["requested"] == 209
    assert emails[0]["payload"]["failed"] == 1
    assert "premier passage" in messages[0]
    assert "Demandés 209 · reçus 180 · persistés 0 · échecs 1 · alertes 2" in messages[0]
    assert "CN daily source collection is incomplete" in messages[0]
