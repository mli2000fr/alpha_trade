from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from risk_management import cli
from risk_management.enums import Decision
from risk_management.models import AccountRiskSnapshot, PortfolioEntry
from service.market.models import MarketRegimeSnapshot


class _BaseFakeRepo:
    def load_equity_history(self, account_id, trade_date, lookback_days=25):
        return []


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

    class _FakeRepo(_BaseFakeRepo):
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
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
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


def test_cli_main_live_short_path_tags_candidates_before_builder(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeRepo(_BaseFakeRepo):
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
            from risk_management.models import SelectionScore

            return [
                SelectionScore("AAPL", "Tech", 0.15),
                SelectionScore("MSFT", "Tech", 0.20),
            ]

        def load_prices_asof(self, symbols, trade_date, atr_window=20):
            from risk_management.models import PriceInfo

            return {
                symbol: PriceInfo(
                    symbol=symbol,
                    last_close=100.0,
                    atr_20=5.0,
                    price_asof_date=trade_date,
                    atr_asof_date=trade_date,
                )
                for symbol in symbols
            }

        def load_predictions_asof(self, symbols, trade_date):
            return {}

        def load_win_rates_asof(self, symbols, trade_date):
            return {}

        def load_equity_history(self, account_id, trade_date, lookback_days=25):
            return []

        def load_return_matrix_asof(self, symbols, trade_date, lookback_days):
            return pd.DataFrame({symbol: [0.01, -0.01, 0.02] for symbol in symbols})

    class _FakeBuilder:
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
            self.progress_callback = None

        def build(self, candidates, prices, predictions, win_rates, return_matrix):
            captured["candidate_sides"] = {candidate.symbol: candidate.side for candidate in candidates}
            return [
                PortfolioEntry(
                    symbol=candidate.symbol,
                    sector=candidate.sector,
                    entry_price=prices[candidate.symbol].last_close,
                    score_used=candidate.score_used,
                    score_source=candidate.score_source,
                    atr_20=prices[candidate.symbol].atr_20,
                    proposed_shares=10,
                    approved_shares=10,
                    target_notional=1_000.0,
                    target_weight=0.01,
                    decision=Decision.ACCEPTED,
                    decision_reason="OK",
                    conviction_score=candidate.score_used,
                    side=candidate.side,
                )
                for candidate in candidates
            ]

    import risk_management.regime_apply as regime_apply

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "RiskRepository", lambda: _FakeRepo())
    monkeypatch.setattr(cli, "PortfolioBuilder", _FakeBuilder)
    monkeypatch.setattr(cli, "persist_market_macro_snapshot_daily", lambda **kwargs: None)
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
            risk_multiplier=0.8,
            allow_new_entries=True,
            allowed_long_entries=False,
            allowed_short_entries=True,
            reasons=(),
        ),
    )
    monkeypatch.setattr(
        regime_apply,
        "apply_structural_market_guards",
        lambda config, market_regimes_config=None, equity=None: replace(
            config,
            short_selling_enabled=True,
        ),
    )

    cli.main(["--trade-date", "2026-05-01", "--dry-run"])

    assert captured["candidate_sides"] == {"AAPL": "sell", "MSFT": "sell"}
    assert captured["summary"]["regime_snapshot_applied"] is True
    assert captured["summary"]["regime_mode"] == "capital_preservation"


def test_cli_main_treats_default_account_as_implicit_and_falls_back(monkeypatch) -> None:
    """L'IHM transmet toujours `--account default` ; sans snapshot on doit fallback."""
    captured: dict[str, object] = {}

    class _FakeRepo(_BaseFakeRepo):
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
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
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

    # `default` doit Ãªtre traitÃ© comme un compte implicite -> requested_account_id None cÃ´tÃ© repo.
    assert captured["requested_account_id"] is None
    assert captured["config"].account_equity == pytest.approx(100_000.0)
    assert captured["summary"]["effective_equity"] == pytest.approx(100_000.0)
    assert captured["summary"]["account_snapshot_trade_date"] is None


def test_cli_main_explicit_account_falls_back_when_no_snapshot(monkeypatch) -> None:
    """Switch sur un compte explicite (test1) sans snapshot doit fallback, pas crasher."""
    captured: dict[str, object] = {}

    class _FakeRepo(_BaseFakeRepo):
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
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
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

    # Doit s'exÃ©cuter sans lever RuntimeError, en fallback sur --account-equity.
    cli.main([
        "--trade-date", "2026-05-01",
        "--account", "test1",
        "--account-equity", "50000",
    ])

    # `test1` reste un compte explicite (non remappÃ© en None comme `default`).
    assert captured["requested_account_id"] == "test1"
    # Fallback sur --account-equity=50000.
    assert captured["config"].account_equity == pytest.approx(50_000.0)
    assert captured["summary"]["effective_equity"] == pytest.approx(50_000.0)
    assert captured["summary"]["account_snapshot_trade_date"] is None


def test_cli_main_accepts_min_position_notional_argument(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeRepo(_BaseFakeRepo):
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
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
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

    class _FakeRepo(_BaseFakeRepo):
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
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
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

    class _FakeRepo(_BaseFakeRepo):
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
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
            self.progress_callback = None

        def build(self, candidates, prices, predictions, win_rates, return_matrix):
            if callable(self.progress_callback):
                self.progress_callback(
                    {
                        "progress_live": True,
                        "progress_current": 0,
                        "progress_total": 1,
                        "progress_phase": "build_portfolio",
                        "progress_label": "ðŸ›¡ï¸ Progression risk management â€” construction portefeuille",
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

    class _FakeRepo(_BaseFakeRepo):
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
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
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


def test_cli_main_persists_market_macro_snapshot(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeRepo(_BaseFakeRepo):
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
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
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
        "persist_market_macro_snapshot_daily",
        lambda **kwargs: captured.setdefault("persist_macro_call", kwargs) or 1,
    )
    monkeypatch.setattr(
        cli,
        "_resolve_market_regime_snapshot",
        lambda trade_date, effective_equity, repo: MarketRegimeSnapshot(
            trade_date=trade_date,
            mode="normal",
            macro={"vix": 22.4, "vix_short": 14.15, "yield_10y": 4.50},
        ),
    )

    cli.main(["--trade-date", "2026-05-01", "--dry-run"])

    assert captured["persist_macro_call"] == {
        "trade_date": date(2026, 5, 1),
        "macro_payload": {"vix": 22.4, "vix_short": 14.15, "yield_10y": 4.50},
        "engine": None,
    }


def test_cli_main_blocks_new_entries_when_regime_disallows_them(monkeypatch) -> None:
    captured: dict[str, object] = {"build_called": False}

    class _FakeRepo(_BaseFakeRepo):
        def load_account_risk_snapshot(self, account_id, trade_date):
            return None

        def load_account_equity_breakdown(self, account_id, trade_date):
            return {}

        def load_candidates_asof(self, trade_date):
            from risk_management.models import SelectionScore

            return [SelectionScore("AAPL", "Tech", 0.9), SelectionScore("MSFT", "Tech", 0.8)]

        def load_prices_asof(self, symbols, trade_date, atr_window=20):
            raise AssertionError("Les prix ne doivent pas Ãªtre chargÃ©s si le rÃ©gime bloque les entrÃ©es")

        def load_predictions_asof(self, symbols, trade_date):
            raise AssertionError("Les prÃ©dictions ne doivent pas Ãªtre chargÃ©es si le rÃ©gime bloque les entrÃ©es")

        def load_win_rates_asof(self, symbols, trade_date):
            raise AssertionError("Les win rates ne doivent pas Ãªtre chargÃ©s si le rÃ©gime bloque les entrÃ©es")

        def load_return_matrix_asof(self, symbols, trade_date, lookback_days):
            raise AssertionError("La matrice de rendements ne doit pas Ãªtre chargÃ©e si le rÃ©gime bloque les entrÃ©es")

    class _FakeBuilder:
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
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


def test_cli_main_blocks_run_when_ml_coverage_is_below_threshold(monkeypatch) -> None:
    from risk_management.ml_gate import MlGateState

    class _FakeRepo(_BaseFakeRepo):
        def load_account_risk_snapshot(self, account_id, trade_date):
            return None

        def load_account_equity_breakdown(self, account_id, trade_date):
            return {}

        def load_candidates_asof(self, trade_date):
            from risk_management.models import SelectionScore

            return [SelectionScore("AAPL", "Tech", 0.9), SelectionScore("MSFT", "Tech", 0.8)]

        def load_predictions_asof(self, symbols, trade_date):
            return {"AAPL": object()}

        def load_prices_asof(self, symbols, trade_date, atr_window=20):
            raise AssertionError("Les prix ne doivent pas Ãªtre chargÃ©s si le gate ML bloque le run")

        def load_win_rates_asof(self, symbols, trade_date):
            raise AssertionError("Les win rates ne doivent pas Ãªtre chargÃ©s si le gate ML bloque le run")

        def load_return_matrix_asof(self, symbols, trade_date, lookback_days):
            return pd.DataFrame()

    class _FakeBuilder:
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
            raise AssertionError("Le builder ne doit pas Ãªtre instanciÃ© si le gate ML bloque le run")

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "RiskRepository", lambda: _FakeRepo())
    monkeypatch.setattr(cli, "PortfolioBuilder", _FakeBuilder)
    monkeypatch.setattr(cli, "_print_summary", lambda entries, run_id, trade_date: None)
    monkeypatch.setattr(cli, "persist_decisions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_portfolio_targets", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_run_business_summary", lambda **kwargs: None)
    monkeypatch.setattr(cli, "emit_run_summary", lambda summary: None)
    monkeypatch.setattr(cli, "_resolve_market_regime_snapshot", lambda trade_date, effective_equity, repo: None)

    import risk_management.ml_gate as ml_gate_module

    monkeypatch.setattr(
        ml_gate_module,
        "resolve_ml_gate_state",
        lambda engine: MlGateState(enabled=True, reason="enabled", action="allow"),
    )
    monkeypatch.setattr(ml_gate_module, "apply_ml_gate_to_risk_config", lambda config, gate_state: config)

    with pytest.raises(SystemExit, match="Couverture ML insuffisante"):
        cli.main([
            "--trade-date",
            "2026-05-01",
            "--dry-run",
            "--min-ml-coverage-ratio",
            "0.80",
        ])


def test_cli_main_applies_vol_targeting_and_exposes_summary(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeRepo(_BaseFakeRepo):
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
            if symbols == ["SPY"]:
                return pd.DataFrame({"SPY": ([0.02, -0.02] * 30)})
            return pd.DataFrame()

    class _FakeBuilder:
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
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
    monkeypatch.setattr(cli, "_resolve_market_regime_snapshot", lambda trade_date, effective_equity, repo: None)

    cli.main([
        "--trade-date",
        "2026-05-01",
        "--dry-run",
        "--target-annual-vol",
        "0.12",
        "--vol-target-lookback-days",
        "60",
    ])

    assert captured["config"].risk_multiplier < 1.0
    assert captured["config"].max_gross_exposure < 1.0
    assert captured["summary"]["vol_targeting"]["enabled"] is True
    assert captured["summary"]["vol_targeting"]["applied"] is True
    assert captured["summary"]["vol_targeting"]["target_annual_vol"] == pytest.approx(0.12)
    assert captured["summary"]["vol_targeting"]["lookback_days"] == 60


def test_cli_main_exposes_shadow_compare_and_postmortem_artifacts(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeRepo(_BaseFakeRepo):
        def load_account_risk_snapshot(self, account_id, trade_date):
            return None

        def load_account_equity_breakdown(self, account_id, trade_date):
            return {}

        def load_candidates_asof(self, trade_date):
            from risk_management.models import SelectionScore

            return [
                SelectionScore(
                    "AAPL",
                    "Tech",
                    0.9,
                    calibration_run_id="calib-1",
                    calibration_source="walk_forward",
                )
            ]

        def load_prices_asof(self, symbols, trade_date, atr_window=20):
            from risk_management.models import PriceInfo

            return {"AAPL": PriceInfo(symbol="AAPL", last_close=100.0, atr_20=5.0, price_asof_date=trade_date, atr_asof_date=trade_date)}

        def load_predictions_asof(self, symbols, trade_date):
            return {}

        def load_win_rates_asof(self, symbols, trade_date):
            return {}

        def load_return_matrix_asof(self, symbols, trade_date, lookback_days):
            return pd.DataFrame([[0.01]], columns=["AAPL"])

        def load_risk_decisions_for_date(self, trade_date, account_id=None):
            return pd.DataFrame(
                [
                    {
                        "run_id": "prev-risk-run",
                        "symbol": "AAPL",
                        "approved_shares": 8,
                        "entry_price": 95.0,
                        "conviction_score": 0.75,
                    }
                ]
            )

    class _FakeBuilder:
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
            self.progress_callback = None

        def build(self, candidates, prices, predictions, win_rates, return_matrix):
            return [
                PortfolioEntry(
                    symbol="AAPL",
                    sector="Tech",
                    entry_price=100.0,
                    score_used=0.9,
                    score_source="final_score_sentiment",
                    atr_20=5.0,
                    proposed_shares=10,
                    approved_shares=10,
                    target_notional=1_000.0,
                    target_weight=0.01,
                    decision=Decision.ACCEPTED,
                    decision_reason="OK",
                    conviction_score=0.8,
                    sizing_method="atr",
                    calibration_run_id="calib-1",
                    calibration_source="walk_forward",
                )
            ]

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "RiskRepository", lambda: _FakeRepo())
    monkeypatch.setattr(cli, "PortfolioBuilder", _FakeBuilder)
    monkeypatch.setattr(cli, "_print_summary", lambda entries, run_id, trade_date: None)
    monkeypatch.setattr(cli, "persist_decisions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_portfolio_targets", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_run_business_summary", lambda **kwargs: captured.setdefault("summary", kwargs["summary"]))
    monkeypatch.setattr(cli, "emit_run_summary", lambda summary: None)

    cli.main(["--trade-date", "2026-05-01", "--dry-run", "--enable-shadow-compare"])

    shadow_compare = captured["summary"]["shadow_compare"]
    assert shadow_compare["status"] == "compared"
    assert shadow_compare["reference_run_id"] == "prev-risk-run"
    assert shadow_compare["report"]["schema_version"] == 1
    assert captured["summary"]["conviction_weights_calibration"]["source"] == "walk_forward"
    assert captured["summary"]["conviction_weights_calibration"]["calibration_run_id"] == "calib-1"
    assert captured["summary"]["postmortem_artifacts"]["regime_summary"]["allow_new_entries"] is True
    assert captured["summary"]["postmortem_artifacts"]["sector_breakdown"][0]["sector"] == "Tech"


def test_cli_main_applies_empirical_risk_calibration_from_repository(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeRepo(_BaseFakeRepo):
        def load_account_risk_snapshot(self, account_id, trade_date):
            return None

        def load_account_equity_breakdown(self, account_id, trade_date):
            return {}

        def load_latest_empirical_risk_calibration(self, trade_date, run_id=None, market_regime_mode=None, horizon_days=None, lookback_months=None):
            captured["requested_market_regime_mode"] = market_regime_mode
            captured["requested_horizon_days"] = horizon_days
            captured["requested_lookback_months"] = lookback_months
            return {
                "run_id": "risk-cal-001",
                "metric_name": "sharpe",
                "metric_value": 1.42,
                "window_start": date(2025, 1, 1),
                "window_end": date(2026, 3, 31),
                "status": "selected",
                "segment_key": "regime=capital_preservation|horizon=5d|window=12m",
                "requested_segment_key": "regime=capital_preservation|horizon=5d|window=12m",
                "horizon_days": horizon_days,
                "lookback_months": lookback_months,
                "requested_horizon_days": horizon_days,
                "requested_lookback_months": lookback_months,
                "eligible_for_live": True,
                "market_regime_mode": "capital_preservation",
                "requested_market_regime_mode": market_regime_mode,
                "market_regime_fallback_used": False,
                "fallback_reason": "niveau=exact_segment; requested=regime=capital_preservation|horizon=5d|window=12m; resolved=regime=capital_preservation|horizon=5d|window=12m",
                "fallback_journal": [
                    {
                        "rank": 1,
                        "level": "exact_segment",
                        "eligible_candidates": 1,
                        "blocked_candidates": 0,
                        "outcome": "selected",
                        "selected": True,
                    }
                ],
                "fallback_policy_source": "config_yaml",
                "source": "weights_calibration_runs",
                "best_weights": {
                    "score_weight": 0.25,
                    "prediction_weight": 0.75,
                    "kelly_fraction_multiplier": 0.5,
                    "min_effective_probability": 0.55,
                    "assumed_payoff_ratio": 2.0,
                },
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
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
            captured["config"] = config
            self.progress_callback = None

        def build(self, candidates, prices, predictions, win_rates, return_matrix):
            return []

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "RiskRepository", lambda: _FakeRepo())
    monkeypatch.setattr(cli, "PortfolioBuilder", _FakeBuilder)
    monkeypatch.setattr(
        cli,
        "_resolve_market_regime_snapshot",
        lambda trade_date, effective_equity, repo: MarketRegimeSnapshot(
            trade_date=trade_date,
            mode="capital_preservation",
            risk_multiplier=1.0,
            allow_new_entries=True,
            reasons=(),
        ),
    )
    monkeypatch.setattr(cli, "_print_summary", lambda entries, run_id, trade_date: None)
    monkeypatch.setattr(cli, "persist_decisions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_portfolio_targets", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_run_business_summary", lambda **kwargs: captured.setdefault("summary", kwargs["summary"]))
    monkeypatch.setattr(cli, "emit_run_summary", lambda summary: None)

    cli.main(["--trade-date", "2026-05-01", "--dry-run", "--enable-kelly-sizing"])

    assert captured["config"].score_weight == pytest.approx(0.25)
    assert captured["config"].prediction_weight == pytest.approx(0.75)
    assert captured["config"].kelly_fraction_multiplier == pytest.approx(0.5)
    assert captured["config"].min_effective_probability == pytest.approx(0.55)
    assert captured["config"].assumed_payoff_ratio == pytest.approx(2.0)
    assert captured["requested_market_regime_mode"] == "capital_preservation"
    assert captured["requested_horizon_days"] == 5
    assert captured["requested_lookback_months"] == 12
    assert captured["summary"]["empirical_risk_calibration"]["run_id"] == "risk-cal-001"
    assert captured["summary"]["empirical_risk_calibration"]["market_regime_mode"] == "capital_preservation"
    assert captured["summary"]["conviction_weights_calibration"]["runtime_requested_segment_key"] == "regime=capital_preservation|horizon=5d|window=12m"
    assert captured["summary"]["conviction_weights_calibration"]["runtime_requested_horizon_days"] == 5
    assert captured["summary"]["conviction_weights_calibration"]["runtime_requested_lookback_months"] == 12
    assert captured["summary"]["conviction_weights_calibration"]["runtime_fallback_reason"].startswith("niveau=exact_segment")
    assert captured["summary"]["conviction_weights_calibration"]["runtime_fallback_policy_source"] == "config_yaml"
    assert captured["summary"]["conviction_weights_calibration"]["runtime_fallback_journal"][0]["level"] == "exact_segment"
    assert captured["summary"]["conviction_weights_calibration"]["runtime_applied"] is True
    assert captured["summary"]["conviction_weights_calibration"]["runtime_market_regime_mode"] == "capital_preservation"


def test_cli_main_does_not_apply_empirical_risk_calibration_when_blocked_by_governance(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeRepo(_BaseFakeRepo):
        def load_account_risk_snapshot(self, account_id, trade_date):
            return None

        def load_account_equity_breakdown(self, account_id, trade_date):
            return {}

        def load_latest_empirical_risk_calibration(self, trade_date, run_id=None, market_regime_mode=None, horizon_days=None, lookback_months=None):
            return {
                "run_id": "risk-cal-blocked",
                "status": "blocked_by_governance",
                "segment_key": "regime=capital_preservation|horizon=5d|window=12m",
                "horizon_days": horizon_days,
                "lookback_months": lookback_months,
                "eligible_for_live": False,
                "eligibility_reason": "insufficient_snapshot_days",
                "market_regime_mode": "capital_preservation",
                "requested_market_regime_mode": market_regime_mode,
                "fallback_level": "blocked_governance_exact_segment",
                "source": "weights_calibration_runs",
                "best_weights": {
                    "score_weight": 0.1,
                    "prediction_weight": 0.9,
                    "kelly_fraction_multiplier": 0.5,
                    "min_effective_probability": 0.55,
                    "assumed_payoff_ratio": 2.0,
                },
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
        def __init__(self, config, pnl, circuit_breaker=None, **kwargs):
            captured["config"] = config
            self.progress_callback = None

        def build(self, candidates, prices, predictions, win_rates, return_matrix):
            return []

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "RiskRepository", lambda: _FakeRepo())
    monkeypatch.setattr(cli, "PortfolioBuilder", _FakeBuilder)
    monkeypatch.setattr(
        cli,
        "_resolve_market_regime_snapshot",
        lambda trade_date, effective_equity, repo: MarketRegimeSnapshot(
            trade_date=trade_date,
            mode="capital_preservation",
            risk_multiplier=1.0,
            allow_new_entries=True,
            reasons=(),
        ),
    )
    monkeypatch.setattr(cli, "_print_summary", lambda entries, run_id, trade_date: None)
    monkeypatch.setattr(cli, "persist_decisions", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_portfolio_targets", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "persist_run_business_summary", lambda **kwargs: captured.setdefault("summary", kwargs["summary"]))
    monkeypatch.setattr(cli, "emit_run_summary", lambda summary: None)

    cli.main(["--trade-date", "2026-05-01", "--dry-run", "--enable-kelly-sizing"])

    assert captured["config"].score_weight == pytest.approx(0.4)
    assert captured["config"].prediction_weight == pytest.approx(0.6)
    assert captured["summary"]["empirical_risk_calibration"]["status"] == "blocked_by_governance"
    assert captured["summary"]["conviction_weights_calibration"]["runtime_applied"] is False
    assert captured["summary"]["conviction_weights_calibration"]["runtime_eligibility_reason"] == "insufficient_snapshot_days"


