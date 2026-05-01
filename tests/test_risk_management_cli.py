from __future__ import annotations

import subprocess
import sys

import pandas as pd
import pytest

from risk_management import cli

def test_cli_importable():
    assert hasattr(cli, "__doc__")


def test_cli_module_executes_main_with_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "risk_management.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Module de gestion de risque Alpha Trade" in result.stdout


def test_cli_main_falls_back_to_account_equity_without_account_snapshot(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeRepo:
        def load_account_risk_snapshot(self, account_id, trade_date):
            return None

        def load_account_equity_breakdown(self, account_id, trade_date):
            return {
                "account_id": account_id or "default",
                "trade_date": trade_date.isoformat(),
                "cash": None,
                "settled_cash": None,
                "long_positions_value": None,
                "short_positions_value": None,
                "dividends_ledger": None,
                "total": None,
                "source": "missing",
                "snapshot_at": None,
            }

        def load_candidates_asof(self, trade_date):
            return []

        def load_prices_asof(self, symbols, trade_date, atr_window=20):
            return {}

        def load_predictions_asof(self, symbols, trade_date):
            return {}

        def load_win_rates_asof(self, symbols, trade_date):
            return {}

        def load_return_matrix_asof(self, symbols, trade_date, lookback_days):
            return pd.DataFrame()

    class _FakeBuilder:
        def __init__(self, config, pnl):
            captured["config"] = config
            captured["pnl"] = pnl

        def build(self, candidates, prices, predictions, win_rates, return_matrix):
            return []

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "RiskRepository", lambda: _FakeRepo())
    monkeypatch.setattr(cli, "PortfolioBuilder", _FakeBuilder)
    monkeypatch.setattr(cli, "_print_summary", lambda entries, run_id, trade_date: None)
    monkeypatch.setattr(cli, "persist_decisions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_portfolio_targets", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_run_business_summary", lambda **kwargs: captured.setdefault("summary", kwargs["summary"]))
    monkeypatch.setattr(cli, "emit_run_summary", lambda summary: None)

    cli.main(["--trade-date", "2026-05-01"])

    assert captured["config"].account_equity == pytest.approx(100_000.0)
    assert captured["pnl"].portfolio_high_watermark == pytest.approx(100_000.0)
    assert captured["pnl"].portfolio_current_value == pytest.approx(100_000.0)
    assert captured["summary"]["effective_equity"] == pytest.approx(100_000.0)
    assert captured["summary"]["account_snapshot_trade_date"] is None


def test_cli_main_treats_default_account_as_implicit_and_falls_back(monkeypatch) -> None:
    """L'IHM transmet toujours `--account default` ; sans snapshot on doit fallback."""
    captured: dict[str, object] = {}

    class _FakeRepo:
        def load_account_risk_snapshot(self, account_id, trade_date):
            captured["requested_account_id"] = account_id
            return None

        def load_account_equity_breakdown(self, account_id, trade_date):
            return {
                "account_id": account_id or "default",
                "trade_date": trade_date.isoformat(),
                "cash": None,
                "settled_cash": None,
                "long_positions_value": None,
                "short_positions_value": None,
                "dividends_ledger": None,
                "total": None,
                "source": "missing",
                "snapshot_at": None,
            }

        def load_candidates_asof(self, trade_date):
            return []

        def load_prices_asof(self, symbols, trade_date, atr_window=20):
            return {}

        def load_predictions_asof(self, symbols, trade_date):
            return {}

        def load_win_rates_asof(self, symbols, trade_date):
            return {}

        def load_return_matrix_asof(self, symbols, trade_date, lookback_days):
            return pd.DataFrame()

    class _FakeBuilder:
        def __init__(self, config, pnl):
            captured["config"] = config
            captured["pnl"] = pnl

        def build(self, candidates, prices, predictions, win_rates, return_matrix):
            return []

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "RiskRepository", lambda: _FakeRepo())
    monkeypatch.setattr(cli, "PortfolioBuilder", _FakeBuilder)
    monkeypatch.setattr(cli, "_print_summary", lambda entries, run_id, trade_date: None)
    monkeypatch.setattr(cli, "persist_decisions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_portfolio_targets", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_run_business_summary", lambda **kwargs: captured.setdefault("summary", kwargs["summary"]))
    monkeypatch.setattr(cli, "emit_run_summary", lambda summary: None)

    cli.main(["--trade-date", "2026-05-01", "--account", "default"])

    # `default` doit être traité comme un compte implicite -> requested_account_id None côté repo.
    assert captured["requested_account_id"] is None
    assert captured["config"].account_equity == pytest.approx(100_000.0)
    assert captured["summary"]["effective_equity"] == pytest.approx(100_000.0)
    assert captured["summary"]["account_snapshot_trade_date"] is None


def test_cli_main_explicit_account_falls_back_when_no_snapshot(monkeypatch) -> None:
    """Switch sur un compte explicite (test1) sans snapshot doit fallback, pas crasher."""
    captured: dict[str, object] = {}

    class _FakeRepo:
        def load_account_risk_snapshot(self, account_id, trade_date):
            captured["requested_account_id"] = account_id
            return None

        def load_account_equity_breakdown(self, account_id, trade_date):
            return {
                "account_id": account_id or "default",
                "trade_date": trade_date.isoformat(),
                "cash": None,
                "settled_cash": None,
                "long_positions_value": None,
                "short_positions_value": None,
                "dividends_ledger": None,
                "total": None,
                "source": "missing",
                "snapshot_at": None,
            }

        def load_candidates_asof(self, trade_date):
            return []

        def load_prices_asof(self, symbols, trade_date, atr_window=20):
            return {}

        def load_predictions_asof(self, symbols, trade_date):
            return {}

        def load_win_rates_asof(self, symbols, trade_date):
            return {}

        def load_return_matrix_asof(self, symbols, trade_date, lookback_days):
            return pd.DataFrame()

    class _FakeBuilder:
        def __init__(self, config, pnl):
            captured["config"] = config
            captured["pnl"] = pnl

        def build(self, candidates, prices, predictions, win_rates, return_matrix):
            return []

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "RiskRepository", lambda: _FakeRepo())
    monkeypatch.setattr(cli, "PortfolioBuilder", _FakeBuilder)
    monkeypatch.setattr(cli, "_print_summary", lambda entries, run_id, trade_date: None)
    monkeypatch.setattr(cli, "persist_decisions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_portfolio_targets", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_run_business_summary", lambda **kwargs: captured.setdefault("summary", kwargs["summary"]))
    monkeypatch.setattr(cli, "emit_run_summary", lambda summary: None)

    # Doit s'exécuter sans lever RuntimeError, en fallback sur --account-equity.
    cli.main([
        "--trade-date", "2026-05-01",
        "--account", "test1",
        "--account-equity", "50000",
    ])

    # `test1` reste un compte explicite (non remappé en None comme `default`).
    assert captured["requested_account_id"] == "test1"
    # Fallback sur --account-equity=50000.
    assert captured["config"].account_equity == pytest.approx(50_000.0)
    assert captured["summary"]["effective_equity"] == pytest.approx(50_000.0)
    assert captured["summary"]["account_snapshot_trade_date"] is None

