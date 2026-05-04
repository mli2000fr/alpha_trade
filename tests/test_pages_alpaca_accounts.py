from __future__ import annotations

from ihm.pages import alpaca_accounts


def test_pages_alpaca_accounts_importable() -> None:
    assert hasattr(alpaca_accounts, "__doc__")


def test_format_currency_handles_invalid_values() -> None:
    assert alpaca_accounts._format_currency("1234.5") == "$1,234.50"
    assert alpaca_accounts._format_currency(None) == "—"

