"""Tests unitaires pour le service Telegram (``service/telegram.py``).

Vérifie que :
1. L'envoi construit l'URL ``/bot<token>/sendMessage`` et le payload attendu.
2. Le token est bien lu depuis l'env ``TOKEN_TELEGRAM_BOT``.
3. Le chat_id est lu depuis l'env ``TELEGRAM_CHAT_ID`` en l'absence d'argument.
4. Une config manquante (token ou chat_id) lève ``TelegramConfigError``.
5. Une erreur réseau renvoie ``False`` sans lever (best-effort).
6. Les messages > 4096 caractères sont tronqués.
"""
from unittest.mock import MagicMock, patch

import pytest

from service.telegram import (
    API_BASE_URL,
    CHAT_ID_ENV,
    MAX_TEXT_LENGTH,
    TOKEN_ENV,
    TelegramClient,
    TelegramConfigError,
    send_telegram_message,
)


class TestTelegramClientSend:
    def test_send_success_builds_url_and_payload(self):
        """URL `/bot<token>/sendMessage` + payload chat_id/text/parse_mode."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            client = TelegramClient(bot_token="123:ABC", default_chat_id="-10042")
            ok = client.send("Hello", parse_mode="Markdown")

            assert ok is True
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0] == f"{API_BASE_URL}/bot123:ABC/sendMessage"
            assert kwargs["json"]["chat_id"] == "-10042"
            assert kwargs["json"]["text"] == "Hello"
            assert kwargs["json"]["parse_mode"] == "Markdown"

    def test_send_explicit_chat_id_overrides_default(self):
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            client = TelegramClient(bot_token="tok", default_chat_id="-10042")
            client.send("Hi", chat_id="-20000")

            _, kwargs = mock_post.call_args
            assert kwargs["json"]["chat_id"] == "-20000"

    def test_send_http_error_returns_false(self):
        """HTTP >= 300 → retourne False (et ne lève pas par défaut)."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = '{"ok":false}'
            mock_post.return_value = mock_response

            client = TelegramClient(bot_token="tok", default_chat_id="-10042")
            assert client.send("Hello") is False

    def test_send_network_error_returns_false(self):
        """Erreur réseau → False sans lever (best-effort)."""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")

            client = TelegramClient(bot_token="tok", default_chat_id="-10042")
            assert client.send("Hello") is False

    def test_send_network_error_raises_when_requested(self):
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")

            client = TelegramClient(bot_token="tok", default_chat_id="-10042")
            with pytest.raises(Exception, match="Network error"):
                client.send("Hello", raise_on_error=True)

    def test_send_truncates_long_text(self):
        long_text = "a" * (MAX_TEXT_LENGTH + 100)
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            client = TelegramClient(bot_token="tok", default_chat_id="-10042")
            client.send(long_text)

            _, kwargs = mock_post.call_args
            assert len(kwargs["json"]["text"]) <= MAX_TEXT_LENGTH


class TestEnvResolution:
    def test_token_read_from_env(self, monkeypatch):
        """Le token est lu depuis TOKEN_TELEGRAM_BOT pour l'envoi one-shot."""
        monkeypatch.setenv(TOKEN_ENV, "envtoken:XYZ")
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            ok = send_telegram_message("Hi", chat_id="-10042")
            assert ok is True
            args, _ = mock_post.call_args
            assert args[0] == f"{API_BASE_URL}/botenvtoken:XYZ/sendMessage"

    def test_chat_id_read_from_env(self, monkeypatch):
        """Le chat_id est lu depuis TELEGRAM_CHAT_ID quand absent de l'appel."""
        monkeypatch.setenv(TOKEN_ENV, "tok")
        monkeypatch.setenv(CHAT_ID_ENV, "-999")
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            ok = send_telegram_message("Hi")
            assert ok is True
            _, kwargs = mock_post.call_args
            assert kwargs["json"]["chat_id"] == "-999"

    def test_is_configured(self, monkeypatch):
        monkeypatch.delenv(TOKEN_ENV, raising=False)
        from service.telegram import is_telegram_configured

        assert is_telegram_configured() is False
        monkeypatch.setenv(TOKEN_ENV, "tok")
        assert is_telegram_configured() is True


class TestConfigErrors:
    def test_missing_token_raises(self, monkeypatch):
        """Aucun token (ni env ni argument) → TelegramConfigError."""
        monkeypatch.delenv(TOKEN_ENV, raising=False)
        with pytest.raises(TelegramConfigError):
            send_telegram_message("Hi", chat_id="-10042")

    def test_missing_chat_id_raises(self, monkeypatch):
        """Aucun chat_id (ni argument ni env) → TelegramConfigError."""
        monkeypatch.setenv(TOKEN_ENV, "tok")
        monkeypatch.delenv(CHAT_ID_ENV, raising=False)
        with pytest.raises(TelegramConfigError):
            send_telegram_message("Hi")
