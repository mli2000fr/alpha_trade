"""Sprint S3 / A-010 — télémétrie sizing rejets dans run_summary.

Vérifie que :
- ``PositionSizer.compute`` retourne ``method='rejected_atr_missing'``
  quand ATR indisponible.
- ``PositionSizer.compute`` retourne ``method='rejected_notional'``
  quand le notional minimum n'est pas atteint.
- ``PositionSizer.compute`` retourne ``method='atr'`` (succès) quand tout est OK.
- ``run_risk.main`` agrège ces compteurs dans le ``run_summary`` final
  sous les clés ``rejected_for_atr_missing`` / ``rejected_for_notional``
  / ``sizing_method_counts``.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk_management import cli as risk_cli
from risk_management.config import RiskConfig
from risk_management.models import (
    AccountRiskSnapshot,
    CandidateScore,
    PriceInfo,
)
from risk_management.position_sizer import PositionSizer


def test_sizing_method_rejected_atr_missing():
    cfg = RiskConfig(account_equity=10_000.0, min_position_notional=100.0)
    sizer = PositionSizer(cfg)
    result = sizer.compute(PriceInfo(symbol="X", last_close=50.0, atr_20=None))
    assert result.method == "rejected_atr_missing"
    assert result.proposed_shares == 0


def test_sizing_method_rejected_notional():
    """ATR énorme + notional minimum élevé -> shares insuffisantes pour atteindre min_notional."""
    cfg = RiskConfig(account_equity=1_000.0, risk_per_trade_pct=0.01, min_position_notional=500.0)
    sizer = PositionSizer(cfg)
    # risk_budget = 10$, atr=5 => risk_per_share = 10$ => shares = 1 => notional = 50$ < 500$
    result = sizer.compute(PriceInfo(symbol="X", last_close=50.0, atr_20=5.0))
    assert result.method == "rejected_notional"
    assert result.proposed_shares == 0


def test_sizing_method_rejected_invalid_price():
    cfg = RiskConfig(account_equity=10_000.0)
    sizer = PositionSizer(cfg)
    result = sizer.compute(PriceInfo(symbol="X", last_close=0.0, atr_20=1.0))
    assert result.method == "rejected_invalid_price"


def test_sizing_method_atr_success():
    cfg = RiskConfig(account_equity=100_000.0, risk_per_trade_pct=0.01, min_position_notional=100.0)
    sizer = PositionSizer(cfg)
    result = sizer.compute(PriceInfo(symbol="X", last_close=50.0, atr_20=1.0))
    assert result.method == "atr"
    assert result.proposed_shares > 0


# ---------------------------------------------------------------------------
# Intégration CLI : agrégation dans run_summary
# ---------------------------------------------------------------------------


_captured: list[dict] = []


@pytest.fixture(autouse=True)
def _reset():
    _captured.clear()
    yield
    _captured.clear()


@pytest.fixture()
def stub_repo_with_rejects(monkeypatch):
    """Repo qui livre 8 candidats dont 4 sans ATR, 4 avec notional insuffisant."""

    candidates = [
        CandidateScore(symbol=f"S{i}", sector="Tech", score_used=0.9, score_source="x")
        for i in range(8)
    ]
    # 4 premiers : ATR None  → rejected_atr_missing
    # 4 derniers : ATR énorme + petit equity + min_notional élevé → rejected_notional
    prices = {}
    for i in range(8):
        atr = None if i < 4 else 5.0
        prices[f"S{i}"] = PriceInfo(symbol=f"S{i}", last_close=50.0, atr_20=atr)

    class _Repo:
        def load_account_risk_snapshot(self, *_): return None
        def load_account_equity_breakdown(self, *_): return {}
        def load_candidates_asof(self, td): return candidates
        def load_prices_asof(self, syms, td, atr_window=20): return prices
        def load_predictions_asof(self, *_): return {}
        def load_win_rates_asof(self, *_): return {}
        def load_return_matrix_asof(self, *_): return pd.DataFrame()

    monkeypatch.setattr(risk_cli, "RiskRepository", lambda: _Repo())
    monkeypatch.setattr(risk_cli, "configure_root_logging", lambda **_: None)
    monkeypatch.setattr(risk_cli, "persist_run_business_summary", lambda **kw: None)
    monkeypatch.setattr(risk_cli, "emit_run_summary", lambda payload: _captured.append(payload))


def test_run_summary_contains_rejection_telemetry(stub_repo_with_rejects):
    risk_cli.main([
        "--trade-date", "2026-05-06",
        "--account-equity", "1000",
        "--risk-per-trade-pct", "0.01",
        "--min-position-notional", "500",
        "--dry-run",
    ])
    assert _captured
    final = _captured[-1]
    # Clés présentes (même si valeurs == 0).
    for key in (
        "rejected_for_atr_missing",
        "rejected_for_notional",
        "rejected_for_zero_shares",
        "rejected_for_invalid_price",
        "sizing_method_counts",
    ):
        assert key in final, f"clé manquante : {key}"
    assert final["rejected_for_atr_missing"] >= 4
    assert final["rejected_for_notional"] >= 4
    assert isinstance(final["sizing_method_counts"], dict)
    assert sum(final["sizing_method_counts"].values()) == final["targeted_symbols"]

