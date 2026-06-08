from __future__ import annotations

from types import SimpleNamespace

import ihm.services.account_defaults as account_defaults


def test_get_pipeline_execution_defaults_infers_cash_account(monkeypatch) -> None:
	class DummyRegistry:
		def resolve(self, account_id: str) -> SimpleNamespace:
			assert account_id == "cash1"
			return SimpleNamespace(mode="paper")

	class DummyAccountRegistry:
		@staticmethod
		def get() -> DummyRegistry:
			return DummyRegistry()

	class DummyClient:
		def __init__(self, broker_mode: str, account_id: str | None = None) -> None:
			assert broker_mode == "paper"
			assert account_id == "cash1"

		def get_account(self) -> dict[str, object]:
			return {
				"equity": "12500",
				"multiplier": "1",
			}

	monkeypatch.setattr(account_defaults, "AccountRegistry", DummyAccountRegistry)
	monkeypatch.setattr(account_defaults, "AlpacaTradingClient", DummyClient)

	defaults = account_defaults.get_pipeline_execution_defaults("cash1")

	assert defaults is not None
	assert defaults.account_type == "cash"
	assert defaults.swing_only is None
	assert defaults.equity == 12_500.0


def test_get_pipeline_execution_defaults_infers_margin_account(monkeypatch) -> None:
	class DummyRegistry:
		def resolve(self, account_id: str) -> SimpleNamespace:
			assert account_id == "margin1"
			return SimpleNamespace(mode="live")

	class DummyAccountRegistry:
		@staticmethod
		def get() -> DummyRegistry:
			return DummyRegistry()

	class DummyClient:
		def __init__(self, broker_mode: str, account_id: str | None = None) -> None:
			assert broker_mode == "live"
			assert account_id == "margin1"

		def get_account(self) -> dict[str, object]:
			return {
				"portfolio_value": "24000",
				"multiplier": "2",
			}

	monkeypatch.setattr(account_defaults, "AccountRegistry", DummyAccountRegistry)
	monkeypatch.setattr(account_defaults, "AlpacaTradingClient", DummyClient)

	defaults = account_defaults.get_pipeline_execution_defaults("margin1")

	assert defaults is not None
	assert defaults.account_type == "margin"
	assert defaults.swing_only is None
	assert defaults.equity == 24_000.0


def test_get_pipeline_execution_defaults_returns_account_type_for_large_margin(monkeypatch) -> None:
	class DummyRegistry:
		def resolve(self, account_id: str) -> SimpleNamespace:
			assert account_id == "margin2"
			return SimpleNamespace(mode="paper")

	class DummyAccountRegistry:
		@staticmethod
		def get() -> DummyRegistry:
			return DummyRegistry()

	class DummyClient:
		def __init__(self, broker_mode: str, account_id: str | None = None) -> None:
			assert broker_mode == "paper"
			assert account_id == "margin2"

		def get_account(self) -> dict[str, object]:
			return {
				"equity": "50000",
				"multiplier": "2",
			}

	monkeypatch.setattr(account_defaults, "AccountRegistry", DummyAccountRegistry)
	monkeypatch.setattr(account_defaults, "AlpacaTradingClient", DummyClient)

	defaults = account_defaults.get_pipeline_execution_defaults("margin2")

	assert defaults is not None
	assert defaults.account_type == "margin"
	assert defaults.swing_only is None
	assert defaults.equity == 50_000.0

