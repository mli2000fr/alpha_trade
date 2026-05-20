from __future__ import annotations

import subprocess
import sys
from datetime import date

import pandas as pd
import pytest

from risk_management import cli
from risk_management.models import AccountRiskSnapshot
from service.market.models import MarketRegimeSnapshot


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
        def __init__(self, config, pnl, circuit_breaker=None):
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
    assert captured["summary"]["equity_source"] == "cli_account_equity_fallback"
    assert captured["summary"]["equity_fallback_used"] is True
    assert captured["summary"]["snapshot_freshness_days"] is None
    assert captured["summary"]["preflight_data_quality"]["checks"]["equity_snapshot"]["status"] == "fallback"


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
        def __init__(self, config, pnl, circuit_breaker=None):
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
        def __init__(self, config, pnl, circuit_breaker=None):
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


def test_cli_main_accepts_min_position_notional_argument(monkeypatch) -> None:
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
        def __init__(self, config, pnl, circuit_breaker=None):
            captured["config"] = config

        def build(self, candidates, prices, predictions, win_rates, return_matrix):
            return []

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "RiskRepository", lambda: _FakeRepo())
    monkeypatch.setattr(cli, "PortfolioBuilder", _FakeBuilder)
    monkeypatch.setattr(cli, "_print_summary", lambda entries, run_id, trade_date: None)
    monkeypatch.setattr(cli, "persist_decisions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_portfolio_targets", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_run_business_summary", lambda **kwargs: None)
    monkeypatch.setattr(cli, "emit_run_summary", lambda summary: None)

    cli.main([
        "--trade-date", "2026-05-01",
        "--account-equity", "2000",
        "--min-position-notional", "150",
    ])

    assert captured["config"].min_position_notional == pytest.approx(150.0)


def test_cli_main_caps_stale_snapshot_with_lower_requested_equity(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeRepo:
        def load_account_risk_snapshot(self, account_id, trade_date):
            return AccountRiskSnapshot(
                account_id=account_id or "default",
                trade_date=date(2026, 4, 30),
                cash=80_000.0,
                equity=80_000.0,
                buying_power=80_000.0,
                high_watermark=80_000.0,
            )

        def load_account_equity_breakdown(self, account_id, trade_date):
            return {
                "account_id": account_id or "default",
                "trade_date": trade_date.isoformat(),
                "cash": 80_000.0,
                "settled_cash": 80_000.0,
                "long_positions_value": 0.0,
                "short_positions_value": 0.0,
                "dividends_ledger": 0.0,
                "total": 80_000.0,
                "source": "broker_account_snapshots",
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
        def __init__(self, config, pnl, circuit_breaker=None):
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

    cli.main([
        "--trade-date", "2026-05-01",
        "--account", "test1",
        "--account-equity", "2000",
    ])

    assert captured["config"].account_equity == pytest.approx(2_000.0)
    assert captured["summary"]["effective_equity"] == pytest.approx(2_000.0)
    assert captured["summary"]["account_snapshot_trade_date"] == "2026-04-30"
    assert captured["summary"]["equity_source"] == "broker_account_snapshots"
    assert captured["summary"]["equity_fallback_used"] is False
    assert captured["summary"]["snapshot_freshness_days"] == 1
    assert captured["summary"]["preflight_data_quality"]["checks"]["equity_snapshot"]["status"] == "stale"


def test_cli_main_emits_live_progress_payloads(monkeypatch) -> None:
    emitted_payloads: list[dict[str, object]] = []

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
        def __init__(self, config, pnl, circuit_breaker=None):
            self.progress_callback = None

        def build(self, candidates, prices, predictions, win_rates, return_matrix):
            if callable(self.progress_callback):
                self.progress_callback(
                    {
                        "progress_live": True,
                        "progress_current": 0,
                        "progress_total": 1,
                        "progress_phase": "build_portfolio",
                        "progress_label": "🛡️ Progression risk management — construction portefeuille",
                        "targeted_symbols": len(candidates),
                    }
                )
            return []

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "RiskRepository", lambda: _FakeRepo())
    monkeypatch.setattr(cli, "PortfolioBuilder", _FakeBuilder)
    monkeypatch.setattr(cli, "_print_summary", lambda entries, run_id, trade_date: None)
    monkeypatch.setattr(cli, "persist_decisions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_portfolio_targets", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_run_business_summary", lambda **kwargs: None)
    monkeypatch.setattr(cli, "emit_run_summary", lambda summary: emitted_payloads.append(dict(summary)))

    cli.main(["--trade-date", "2026-05-01", "--dry-run"])

    live_payloads = [payload for payload in emitted_payloads if payload.get("progress_live")]
    final_payload = next(payload for payload in reversed(emitted_payloads) if not payload.get("progress_live"))

    assert live_payloads
    assert any(payload.get("progress_phase") == "resolve_account" for payload in live_payloads)
    assert any(payload.get("progress_phase") == "load_candidates" for payload in live_payloads)
    assert any(payload.get("progress_phase") == "build_portfolio" for payload in live_payloads)
    assert any(payload.get("progress_phase") == "persist_results" for payload in live_payloads)
    assert final_payload["trade_date"] == "2026-05-01"


def test_cli_main_applies_market_regime_overrides_to_builder(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeRepo:
        def load_account_risk_snapshot(self, account_id, trade_date):
            return None

        def load_account_equity_breakdown(self, account_id, trade_date):
            return {}

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
        def __init__(self, config, pnl, circuit_breaker=None):
            captured["config"] = config
            self.progress_callback = None

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
    monkeypatch.setattr(
        cli,
        "_resolve_market_regime_snapshot",
        lambda trade_date, effective_equity, repo: MarketRegimeSnapshot(
            trade_date=trade_date,
            mode="capital_preservation",
            risk_multiplier=0.5,
            effective_max_positions=2,
            enforced_min_notional=155.0,
            max_tickers_per_sector=1,
        ),
    )

    cli.main(["--trade-date", "2026-05-01", "--dry-run"])

    assert captured["config"].risk_multiplier == pytest.approx(0.5)
    assert captured["config"].effective_max_positions == 2
    assert captured["config"].effective_min_notional == pytest.approx(155.0)
    assert captured["config"].max_tickers_per_sector == 1
    assert captured["summary"]["regime_snapshot_applied"] is True
    assert captured["summary"]["regime_mode"] == "capital_preservation"
    assert captured["summary"]["risk_controls_effective"]["risk_multiplier"] == pytest.approx(0.5)


def test_cli_main_blocks_new_entries_when_regime_disallows_them(monkeypatch) -> None:
    captured: dict[str, object] = {"build_called": False}

    class _FakeRepo:
        def load_account_risk_snapshot(self, account_id, trade_date):
            return None

        def load_account_equity_breakdown(self, account_id, trade_date):
            return {}

        def load_candidates_asof(self, trade_date):
            from risk_management.models import CandidateScore

            return [CandidateScore("AAPL", "Tech", 0.9), CandidateScore("MSFT", "Tech", 0.8)]

        def load_prices_asof(self, symbols, trade_date, atr_window=20):
            raise AssertionError("Les prix ne doivent pas être chargés si le régime bloque les entrées")

        def load_predictions_asof(self, symbols, trade_date):
            raise AssertionError("Les prédictions ne doivent pas être chargées si le régime bloque les entrées")

        def load_win_rates_asof(self, symbols, trade_date):
            raise AssertionError("Les win rates ne doivent pas être chargés si le régime bloque les entrées")

        def load_return_matrix_asof(self, symbols, trade_date, lookback_days):
            raise AssertionError("La matrice de rendements ne doit pas être chargée si le régime bloque les entrées")

    class _FakeBuilder:
        def __init__(self, config, pnl, circuit_breaker=None):
            captured["build_called"] = True
            self.progress_callback = None

        def build(self, candidates, prices, predictions, win_rates, return_matrix):
            captured["build_called"] = True
            return []

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "RiskRepository", lambda: _FakeRepo())
    monkeypatch.setattr(cli, "PortfolioBuilder", _FakeBuilder)
    monkeypatch.setattr(cli, "_print_summary", lambda entries, run_id, trade_date: None)
    monkeypatch.setattr(cli, "persist_decisions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_portfolio_targets", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_run_business_summary", lambda **kwargs: captured.setdefault("summary", kwargs["summary"]))
    monkeypatch.setattr(cli, "emit_run_summary", lambda summary: None)
    monkeypatch.setattr(
        cli,
        "_resolve_market_regime_snapshot",
        lambda trade_date, effective_equity, repo: MarketRegimeSnapshot(
            trade_date=trade_date,
            mode="close_only",
            allow_new_entries=False,
            reasons=("sentiment_critical",),
        ),
    )

    cli.main(["--trade-date", "2026-05-01", "--dry-run"])

    assert captured["build_called"] is False
    assert captured["summary"]["entries_blocked_by_regime"] == 2
    assert captured["summary"]["regime_allow_new_entries"] is False
    assert captured["summary"]["regime_mode"] == "close_only"
    assert captured["summary"]["preflight_data_quality"]["checks"]["atr_coverage"]["status"] == "skipped_by_regime"
    assert captured["summary"]["preflight_data_quality"]["checks"]["correlation_matrix"]["status"] == "skipped_by_regime"


