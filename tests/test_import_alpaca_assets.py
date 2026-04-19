import pytest
from unittest.mock import patch

from dataIntegrityEngine import import_alpaca_assets


def test_main_calls_fetch_and_insert(monkeypatch):
    calls = []
    monkeypatch.setattr(import_alpaca_assets, "fetch_alpaca_assets", lambda: calls.append("fetch") or ["AAPL", "MSFT"])
    monkeypatch.setattr(import_alpaca_assets, "insert_assets_to_db", lambda assets: calls.append(("insert", assets)))
    import_alpaca_assets.main()
    assert calls == ["fetch", ("insert", ["AAPL", "MSFT"])]

