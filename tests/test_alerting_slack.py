"""Tests unitaires pour T5.2 — Slack alerting.

Vérifie que :
1. Le SlackNotifier envoie correctement les messages
2. Le circuit breaker s'intègre avec Slack pour les alertes
3. Les canaux d'alerting fonctionnent ensemble (email + Slack)
"""
from unittest.mock import MagicMock, patch

import pytest

from service.alerting import SlackNotifier, LogNotifier


class TestSlackNotifier:
    """Tests du SlackNotifier existant."""

    def test_slack_notifier_send_success(self):
        """Envoie un message Slack avec succès."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            notifier = SlackNotifier(webhook_url="https://hooks.slack.com/services/TEST")
            notifier.send(
                "Test Alert",
                "This is a test message",
                severity="warning"
            )

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "https://hooks.slack.com/services/TEST" in str(call_args)

    def test_slack_notifier_fallback_on_error(self):
        """Fallback sur LogNotifier en cas d'erreur."""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")

            fallback = LogNotifier()
            notifier = SlackNotifier(
                webhook_url="https://hooks.slack.com/services/TEST",
                fallback=fallback
            )

            # Should not raise
            notifier.send("Error Test", "This should fallback to log", severity="critical")

            mock_post.assert_called_once()

    def test_slack_notifier_severity_emoji(self):
        """Vérifie que les emojis de sévérité sont correctes."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            notifier = SlackNotifier(webhook_url="https://hooks.slack.com/services/TEST")

            # Test info
            notifier.send("Info", "Info message", severity="info")
            call_json = mock_post.call_args_list[0][1]["json"]
            assert ":information_source:" in call_json["text"]

            # Test critical
            notifier.send("Critical", "Critical message", severity="critical")
            call_json = mock_post.call_args_list[1][1]["json"]
            assert ":rotating_light:" in call_json["text"]


class TestCircuitBreakerSlackIntegration:
    """Tests d'intégration circuit breaker + Slack."""

    @patch("ihm.services.email_notifier.send_notification")
    def test_circuit_breaker_sends_to_slack(self, mock_email):
        """Vérifie la délégation au routeur multi-canaux courant."""
        from risk_management.circuit_breaker import _try_send_alert

        payload = {
            "trigger": "drawdown",
            "drawdown_pct": 12.5,
            "threshold_pct": 10.0,
            "portfolio_high_watermark": 100000.0,
            "portfolio_current_value": 87500.0,
        }

        # L'import de send_system_alert est local à la fonction : le patch du
        # symbole source est donc le contrat stable à vérifier.
        with patch("service.alerting.send_system_alert") as routed_alert:
            _try_send_alert("circuit_breaker_fired", payload)
            mock_email.assert_called_once()
            routed_alert.assert_called_once_with(
                event="CIRCUIT_BREAKER_FIRED", payload=payload, severity="critical"
            )


class TestAlertingBroadcast:
    """Tests du broadcast multi-canaux (Slack + SMTP)."""

    def test_build_notifiers_from_env_can_stack_channels(self) -> None:
        from service.alerting import build_notifiers_from_env

        env = {
            "ALPHA_TRADE_SLACK_WEBHOOK": "https://hooks.slack.com/services/TEST",
            "ALPHA_TRADE_SMTP_HOST": "smtp.example.com",
            "ALPHA_TRADE_SMTP_PORT": "587",
            "ALPHA_TRADE_SMTP_FROM": "alpha@example.com",
            "ALPHA_TRADE_SMTP_TO": "ops@example.com",
        }
        channels = build_notifiers_from_env(env=env)
        assert len(channels) == 2

    @patch("service.alerting.build_notifiers_from_env")
    def test_send_system_alert_dispatches_all_channels(self, mock_build) -> None:
        from service.alerting import send_system_alert

        a = MagicMock()
        b = MagicMock()
        mock_build.return_value = (a, b)

        send_system_alert("TEST_EVENT", {"k": 1}, severity="critical")

        a.send.assert_called_once()
        b.send.assert_called_once()


class TestSlackNotificationFromEnvironment:
    """Tests de configuration du webhook depuis l'environnement."""

    def test_slack_notifier_from_env(self, monkeypatch):
        """Crée un SlackNotifier depuis variables d'environnement."""
        test_webhook = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX"
        monkeypatch.setenv("ALPHA_TRADE_SLACK_WEBHOOK", test_webhook)

        # Import après configuration env
        from service.alerting import build_notifier_from_env

        notifier = build_notifier_from_env()

        # Devrait avoir créé un SlackNotifier
        assert isinstance(notifier, SlackNotifier)
        assert notifier.webhook_url == test_webhook


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



