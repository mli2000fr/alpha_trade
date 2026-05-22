from __future__ import annotations

from ihm.pages import settings
from ihm.services.notifications import SmtpConfig


def test_smtp_missing_banner_message_is_returned_when_not_configured() -> None:
    smtp_cfg = SmtpConfig(
        host="",
        port=587,
        username=None,
        password=None,
        sender="",
        use_tls=True,
        use_ssl=False,
    )

    message = settings._build_smtp_not_configured_warning_message(smtp_cfg)

    assert message is not None
    assert "SMTP non configuré" in message
    assert "aucune notification email ne sera envoyée" in message


def test_smtp_missing_banner_message_is_none_when_configured() -> None:
    smtp_cfg = SmtpConfig(
        host="smtp.example.com",
        port=587,
        username="user",
        password="secret",
        sender="ops@example.com",
        use_tls=True,
        use_ssl=False,
    )

    assert settings._build_smtp_not_configured_warning_message(smtp_cfg) is None

