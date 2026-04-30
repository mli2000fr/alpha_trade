"""Tests du helper de parsing du timestamp Alpaca pour `stock_quote_snapshots`.

Régression du bug MySQL 1292 (« Incorrect datetime value ») rencontré le
2026-04-30 : le format RFC 3339 d'Alpaca (`...Z`, fraction nanoseconde) est
désormais converti en `datetime` Python timezone-naïf UTC tronqué aux
microsecondes — compatible MySQL `DATETIME(6)`.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from dataIntegrityEngine.sync_latest_quotes import _parse_alpaca_timestamp


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

