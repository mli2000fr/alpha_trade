from __future__ import annotations

from dataIntegrityEngine import import_alpaca_bar, import_eodhd_bar
from dataIntegrityEngine.bar_importer_common import normalize_symbols, resolve_bars_provider


def test_normalize_symbols_is_shared_and_deterministic() -> None:
    assert normalize_symbols([" aapl ", "AAPL", "msft", ""]) == ["AAPL", "MSFT"]


def test_resolve_bars_provider_shared_rules() -> None:
    cfg = {"market_data": {"bars_provider": "EODHD"}}

    assert resolve_bars_provider(cfg) == "eodhd"
    assert import_eodhd_bar.resolve_bars_provider(cfg) == "eodhd"


def test_import_alpaca_provider_resolution_delegates_to_shared_helper(monkeypatch) -> None:
    monkeypatch.setattr("common.config_loader.load_config", lambda: {"market_data": {"bars_provider": "alpaca"}})

    assert import_alpaca_bar._resolve_bars_provider() == resolve_bars_provider({"market_data": {"bars_provider": "alpaca"}})


def test_import_alpaca_symbol_normalization_delegates_to_shared_helper() -> None:
    assert import_alpaca_bar._normalize_target_symbols([" aapl ", "MSFT", "aapl"]) == ["AAPL", "MSFT"]

