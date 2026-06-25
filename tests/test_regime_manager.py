"""Tests unitaires pour ``service/market/regime_manager.py`` — nouveaux indicateurs."""
from __future__ import annotations

from datetime import date

import pytest

from service.market.config import (
    MarketRegimesConfig,
    MoveConfig,
    RvxConfig,
    Vix3mConfig,
    VxnConfig,
    parse_market_regimes,
)
from service.market.regime_manager import build_snapshot


# ──────────────────────────────────────────────────────────────────────────────
# Provider minimal pour injection de valeurs
# ──────────────────────────────────────────────────────────────────────────────


class _FakeMacroProvider:
    """Fournit des valeurs macro contrôlées pour les tests de régime."""

    def __init__(
        self,
        *,
        vix: float | None = None,
        vix_short: float | None = None,
        vxn: float | None = None,
        vix3m: float | None = None,
        move: float | None = None,
        rvx: float | None = None,
        yield_10y_5d_pct: float | None = None,
    ) -> None:
        self._vix = vix
        self._vix_short = vix_short
        self._vxn = vxn
        self._vix3m = vix3m
        self._move = move
        self._rvx = rvx
        self._yield_10y_5d_pct = yield_10y_5d_pct

    def get_vix_close(self, _trade_date: date) -> float | None:
        return self._vix

    def get_vix_short_term_close(self, _trade_date: date) -> float | None:
        return self._vix_short

    def get_vxn_close(self, _trade_date: date) -> float | None:
        return self._vxn

    def get_vix3m_close(self, _trade_date: date) -> float | None:
        return self._vix3m

    def get_move_close(self, _trade_date: date) -> float | None:
        return self._move

    def get_rvx_close(self, _trade_date: date) -> float | None:
        return self._rvx

    def get_us10y_history(self, _trade_date: date, lookback_days: int) -> list[float] | None:
        if self._yield_10y_5d_pct is not None:
            return [4.0] * lookback_days
        return None


def _make_config(**overrides: object) -> MarketRegimesConfig:
    """Construit une config minimale avec les nouveaux indicateurs activés."""
    base: dict[str, object] = {
        "enabled": True,
        "vix": {"enabled": False},
        "vxn": {"enabled": False},
        "vix3m": {"enabled": False},
        "move": {"enabled": False},
        "rvx": {"enabled": False},
        "yields": {"enabled": False},
        "sentiment_circuit_breaker": {"enabled": False},
    }
    base.update(overrides)
    return parse_market_regimes(base)


# ──────────────────────────────────────────────────────────────────────────────
# VXN — régime capital_preservation quand VXN dépasse le seuil
# ──────────────────────────────────────────────────────────────────────────────


def test_regime_vxn_high_escalates_to_capital_preservation():
    """VXN=25.0 avec high_threshold=23.0 → mode >= capital_preservation."""
    provider = _FakeMacroProvider(vxn=25.0)
    config = _make_config(
        vxn={"enabled": True, "high_threshold": 23.0, "symbol": "VXN.INDX"},
    )
    snap = build_snapshot(
        date(2025, 6, 25),
        config=config,
        macro_provider=provider,
        use_cache=False,
    )
    payload = snap.to_dict()
    assert payload["mode"] in {"capital_preservation", "close_only", "cash_only"}
    assert payload["macro"]["vxn"] == pytest.approx(25.0)
    assert any("vxn_high" in r for r in payload.get("reasons", []))


def test_regime_vxn_normal_below_threshold():
    """VXN=18.0 avec high_threshold=23.0 → mode normal."""
    provider = _FakeMacroProvider(vxn=18.0)
    config = _make_config(
        vxn={"enabled": True, "high_threshold": 23.0, "symbol": "VXN.INDX"},
    )
    snap = build_snapshot(
        date(2025, 6, 25),
        config=config,
        macro_provider=provider,
        use_cache=False,
    )
    payload = snap.to_dict()
    assert payload["mode"] == "normal"
    assert payload["macro"]["vxn"] == pytest.approx(18.0)


def test_regime_vxn_disabled_no_effect():
    """VXN désactivé → VXN élevé n'affecte pas le mode."""
    provider = _FakeMacroProvider(vxn=30.0)
    config = _make_config()  # vxn.enabled = False par défaut
    snap = build_snapshot(
        date(2025, 6, 25),
        config=config,
        macro_provider=provider,
        use_cache=False,
    )
    payload = snap.to_dict()
    assert payload["mode"] == "normal"
    # vxn ne devrait pas apparaître dans macro quand désactivé
    assert payload["macro"].get("vxn") is None


# ──────────────────────────────────────────────────────────────────────────────
# Term structure — backwardation
# ──────────────────────────────────────────────────────────────────────────────


def test_regime_vix_backwardation_escalates():
    """VIX=28, VIX3M=25 → backwardation → capital_preservation."""
    provider = _FakeMacroProvider(vix=28.0, vix3m=25.0)
    config = _make_config(
        vix={"enabled": True, "high_threshold": 30.0, "symbol": "VIX.INDX"},
        vix3m={"enabled": True, "backwardation_threshold": 1.0, "symbol": "VIX3M.INDX"},
    )
    snap = build_snapshot(
        date(2025, 6, 25),
        config=config,
        macro_provider=provider,
        use_cache=False,
    )
    payload = snap.to_dict()
    assert payload["mode"] in {"capital_preservation", "close_only", "cash_only"}
    assert payload["macro"]["vix3m"] == pytest.approx(25.0)
    assert payload["macro"]["vix_backwardation"] is True
    assert any("vix_backwardation" in r for r in payload.get("reasons", []))


def test_regime_vix_contango_no_escalation():
    """VIX=20, VIX3M=25 → contango → mode normal (si VIX < seuil)."""
    provider = _FakeMacroProvider(vix=20.0, vix3m=25.0)
    config = _make_config(
        vix={"enabled": True, "high_threshold": 30.0, "symbol": "VIX.INDX"},
        vix3m={"enabled": True, "backwardation_threshold": 1.0, "symbol": "VIX3M.INDX"},
    )
    snap = build_snapshot(
        date(2025, 6, 25),
        config=config,
        macro_provider=provider,
        use_cache=False,
    )
    payload = snap.to_dict()
    assert payload["mode"] == "normal"
    assert payload["macro"]["vix_backwardation"] is False


# ──────────────────────────────────────────────────────────────────────────────
# MOVE (bond volatility)
# ──────────────────────────────────────────────────────────────────────────────


def test_regime_move_high_escalates():
    """MOVE=130, high_threshold=120 → capital_preservation."""
    provider = _FakeMacroProvider(move=130.0)
    config = _make_config(
        move={"enabled": True, "high_threshold": 120.0, "symbol": "MOVE.INDX"},
    )
    snap = build_snapshot(
        date(2025, 6, 25),
        config=config,
        macro_provider=provider,
        use_cache=False,
    )
    payload = snap.to_dict()
    assert payload["mode"] in {"capital_preservation", "close_only", "cash_only"}
    assert payload["macro"]["move"] == pytest.approx(130.0)
    assert any("move_high" in r for r in payload.get("reasons", []))


def test_regime_move_normal_below_threshold():
    """MOVE=100, high_threshold=120 → normal."""
    provider = _FakeMacroProvider(move=100.0)
    config = _make_config(
        move={"enabled": True, "high_threshold": 120.0, "symbol": "MOVE.INDX"},
    )
    snap = build_snapshot(
        date(2025, 6, 25),
        config=config,
        macro_provider=provider,
        use_cache=False,
    )
    payload = snap.to_dict()
    assert payload["mode"] == "normal"


# ──────────────────────────────────────────────────────────────────────────────
# RVX (Small Caps volatility)
# ──────────────────────────────────────────────────────────────────────────────


def test_regime_rvx_high_escalates():
    """RVX=32, high_threshold=30 → capital_preservation."""
    provider = _FakeMacroProvider(rvx=32.0)
    config = _make_config(
        rvx={"enabled": True, "high_threshold": 30.0, "symbol": "RVX.INDX"},
    )
    snap = build_snapshot(
        date(2025, 6, 25),
        config=config,
        macro_provider=provider,
        use_cache=False,
    )
    payload = snap.to_dict()
    assert payload["mode"] in {"capital_preservation", "close_only", "cash_only"}
    assert payload["macro"]["rvx"] == pytest.approx(32.0)
    assert any("rvx_high" in r for r in payload.get("reasons", []))


def test_regime_rvx_normal_below_threshold():
    """RVX=25, high_threshold=30 → normal."""
    provider = _FakeMacroProvider(rvx=25.0)
    config = _make_config(
        rvx={"enabled": True, "high_threshold": 30.0, "symbol": "RVX.INDX"},
    )
    snap = build_snapshot(
        date(2025, 6, 25),
        config=config,
        macro_provider=provider,
        use_cache=False,
    )
    payload = snap.to_dict()
    assert payload["mode"] == "normal"


# ──────────────────────────────────────────────────────────────────────────────
# Combinaison multi-indicateurs
# ──────────────────────────────────────────────────────────────────────────────


def test_regime_multiple_indicators_escalate_once():
    """VXN=25, MOVE=130, RVX=32 → escalation unique capital_preservation."""
    provider = _FakeMacroProvider(vxn=25.0, move=130.0, rvx=32.0)
    config = _make_config(
        vxn={"enabled": True, "high_threshold": 23.0, "symbol": "VXN.INDX"},
        move={"enabled": True, "high_threshold": 120.0, "symbol": "MOVE.INDX"},
        rvx={"enabled": True, "high_threshold": 30.0, "symbol": "RVX.INDX"},
    )
    snap = build_snapshot(
        date(2025, 6, 25),
        config=config,
        macro_provider=provider,
        use_cache=False,
    )
    payload = snap.to_dict()
    # Doit être au moins capital_preservation (pas nécessairement close_only)
    assert payload["mode"] in {"capital_preservation", "close_only", "cash_only"}
    # Plusieurs raisons doivent être présentes
    reasons = payload.get("reasons", [])
    assert len([r for r in reasons if "vxn_high" in r]) >= 1
    assert len([r for r in reasons if "move_high" in r]) >= 1
    assert len([r for r in reasons if "rvx_high" in r]) >= 1
