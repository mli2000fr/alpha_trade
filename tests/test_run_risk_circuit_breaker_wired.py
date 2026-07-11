"""Sprint S3 / A-007 — circuit_breaker branché sur PnL réel dans run_risk.

Vérifie que :
- ``run_risk.main`` construit toujours un ``PnLSnapshot`` non-vide
  (``portfolio_current_value`` non-None et > 0) — soit depuis
  ``account_risk_snapshot``, soit via fallback ``--account-equity``.
- Le ``CircuitBreaker`` instancié dans le summary expose des seuils
  cohérents (max_portfolio_drawdown_pct + max_daily_loss_pct).
- En cas de drawdown synthétique > seuil, le breaker s'active.
- Le ``run_summary`` final contient ``circuit_breaker_active`` et
  ``circuit_breaker_thresholds`` (Sprint S3 / A-011).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk_management import cli as risk_cli
from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.config import RiskConfig
from risk_management.models import AccountRiskSnapshot


@pytest.fixture()
def stub_repo(monkeypatch):
    """Stub RiskRepository pour éviter toute dépendance DB."""

    class _StubRepo:
        def __init__(self):
            self.snapshot_returned: AccountRiskSnapshot | None = None

        def load_account_risk_snapshot(self, account_id, trade_date):
            return self.snapshot_returned

        def load_account_equity_breakdown(self, account_id, trade_date):
            return {}

        def load_tradable_universe_asof(self, *_):
            return SimpleNamespace(symbols=(), data_quality_grade="full", universe_run_id="test-universe-run")

        def load_score_context_asof(self, *_):
            return []

        def load_equity_history(self, *_args, **_kwargs):
            return []

        def load_prices_asof(self, symbols, trade_date, atr_window=20):
            return {}

        def load_predictions_asof(self, symbols, trade_date):
            return {}

        def load_win_rates_asof(self, symbols, trade_date):
            return {}

        def load_return_matrix_asof(self, symbols, trade_date, lookback):
            return pd.DataFrame()

    instance = _StubRepo()
    monkeypatch.setattr(risk_cli, "RiskRepository", lambda: instance)
    monkeypatch.setattr(risk_cli, "configure_root_logging", lambda **_: None)
    monkeypatch.setattr(risk_cli, "persist_run_business_summary", lambda **kw: None)
    monkeypatch.setattr(risk_cli, "emit_run_summary", lambda payload: captured.append(payload))
    return instance


captured: list[dict] = []


@pytest.fixture(autouse=True)
def _reset_captured():
    captured.clear()
    yield
    captured.clear()


def test_circuit_breaker_receives_non_none_pnl_via_snapshot(stub_repo):
    """Quand un snapshot existe, PnLSnapshot doit refléter ses valeurs."""
    stub_repo.snapshot_returned = AccountRiskSnapshot(
        account_id="paper1",
        trade_date=date(2026, 5, 6),
        cash=2_000.0,
        equity=10_500.0,
        buying_power=4_000.0,
        high_watermark=11_000.0,
        daily_realized_pnl=-50.0,
        daily_unrealized_pnl=-25.0,
        daily_total_pnl=-75.0,
    )
    instances: list[CircuitBreaker] = []
    original = CircuitBreaker.__init__

    def _capturing_init(self, cfg, pnl=None):
        original(self, cfg, pnl)
        instances.append(self)

    with patch.object(CircuitBreaker, "__init__", _capturing_init):
        risk_cli.main([
            "--trade-date", "2026-05-06",
            "--account", "paper1",
            "--account-equity", "10000",
            "--dry-run",
        ])

    assert instances, "CircuitBreaker doit être instancié au moins une fois."
    cb = instances[-1]
    pnl = cb._pnl  # type: ignore[attr-defined]
    assert pnl.portfolio_current_value == pytest.approx(10_500.0)
    assert pnl.portfolio_high_watermark == pytest.approx(11_000.0)
    assert pnl.daily_pnl == pytest.approx(-75.0)


def test_circuit_breaker_receives_non_none_pnl_via_fallback(stub_repo):
    """Sans snapshot, le PnLSnapshot fallback doit être valorisé sur --account-equity."""
    stub_repo.snapshot_returned = None
    instances: list[CircuitBreaker] = []
    original = CircuitBreaker.__init__

    def _capturing_init(self, cfg, pnl=None):
        original(self, cfg, pnl)
        instances.append(self)

    with patch.object(CircuitBreaker, "__init__", _capturing_init):
        risk_cli.main([
            "--trade-date", "2026-05-06",
            "--account-equity", "25000",
            "--dry-run",
        ])

    assert instances
    cb = instances[-1]
    pnl = cb._pnl  # type: ignore[attr-defined]
    assert pnl.portfolio_current_value == pytest.approx(25_000.0)
    assert pnl.portfolio_high_watermark == pytest.approx(25_000.0)
    assert pnl.daily_pnl == pytest.approx(0.0)
    # Aucun déclenchement attendu sur fallback (pas de drawdown ni loss).
    assert not cb.is_active()


def test_circuit_breaker_triggers_on_drawdown_threshold():
    cfg = RiskConfig(account_equity=100_000.0, max_portfolio_drawdown_pct=0.10)
    pnl = PnLSnapshot(portfolio_high_watermark=100_000.0, portfolio_current_value=85_000.0)
    cb = CircuitBreaker(cfg, pnl)
    assert cb.is_active() is True


def test_circuit_breaker_triggers_on_daily_loss_threshold():
    cfg = RiskConfig(account_equity=10_000.0, max_daily_loss_pct=0.03)
    pnl = PnLSnapshot(daily_pnl=-500.0)  # -5 % > seuil 3 %
    cb = CircuitBreaker(cfg, pnl)
    assert cb.is_active() is True


def test_run_summary_exposes_circuit_breaker_thresholds(stub_repo):
    """A-011 : le summary doit exposer les seuils effectifs du CB."""
    stub_repo.snapshot_returned = None
    risk_cli.main([
        "--trade-date", "2026-05-06",
        "--account-equity", "5000",
        "--max-portfolio-drawdown-pct", "0.08",
        "--max-daily-loss-pct", "0.03",
        "--dry-run",
    ])
    assert captured, "Au moins un run_summary doit être émis."
    final = captured[-1]
    thresholds = final.get("circuit_breaker_thresholds")
    assert thresholds is not None
    assert thresholds["max_portfolio_drawdown_pct"] == pytest.approx(0.08)
    assert thresholds["max_daily_loss_pct"] == pytest.approx(0.03)
    assert "circuit_breaker_active" in final

