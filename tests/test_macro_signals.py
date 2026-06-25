"""Tests unitaires pour ``service/market/macro_signals.py`` — VXN, VIX term structure."""
from __future__ import annotations

from datetime import date

import pytest

from service.market.macro_signals import (
    VixTermStructure,
    evaluate_vxn,
    evaluate_vix_term_structure,
)


# ──────────────────────────────────────────────────────────────────────────────
# Mocks compacts — provider minimal
# ──────────────────────────────────────────────────────────────────────────────


class _FakeMacroProvider:
    """Provider minimal avec valeurs injectées pour tests unitaires."""

    def __init__(
        self,
        *,
        vix: float | None = None,
        vix_short: float | None = None,
        vxn: float | None = None,
        vix3m: float | None = None,
        move: float | None = None,
        rvx: float | None = None,
    ) -> None:
        self._vix = vix
        self._vix_short = vix_short
        self._vxn = vxn
        self._vix3m = vix3m
        self._move = move
        self._rvx = rvx

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

    def get_us10y_history(self, _trade_date: date, _lookback_days: int) -> list[float] | None:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# evaluate_vxn()
# ──────────────────────────────────────────────────────────────────────────────


def test_evaluate_vxn_returns_none_when_provider_is_none():
    value, is_high, dq = evaluate_vxn(None, date(2025, 6, 25), high_threshold=23.0)
    assert value is None
    assert is_high is False
    assert isinstance(dq, dict)


def test_evaluate_vxn_returns_value_when_provider_has_data():
    provider = _FakeMacroProvider(vxn=18.5)
    value, is_high, dq = evaluate_vxn(provider, date(2025, 6, 25), high_threshold=23.0)
    assert value == pytest.approx(18.5)
    assert is_high is False
    assert "vxn_source" in dq


def test_evaluate_vxn_high_when_above_threshold():
    provider = _FakeMacroProvider(vxn=25.0)
    value, is_high, dq = evaluate_vxn(provider, date(2025, 6, 25), high_threshold=23.0)
    assert value == pytest.approx(25.0)
    assert is_high is True


def test_evaluate_vxn_not_high_when_equal_to_threshold():
    provider = _FakeMacroProvider(vxn=23.0)
    value, is_high, _ = evaluate_vxn(provider, date(2025, 6, 25), high_threshold=23.0)
    assert value == pytest.approx(23.0)
    assert is_high is False  # strictement supérieur


# ──────────────────────────────────────────────────────────────────────────────
# evaluate_vix_term_structure()
# ──────────────────────────────────────────────────────────────────────────────


def test_term_structure_returns_empty_when_provider_none():
    ts = evaluate_vix_term_structure(None, date(2025, 6, 25))
    assert ts.vix_value is None
    assert ts.vix3m_value is None
    assert ts.ratio is None
    assert ts.backwardation is False


def test_term_structure_contango():
    """VIX=20, VIX3M=25 → ratio=0.8 → contango (normal)."""
    provider = _FakeMacroProvider(vix=20.0, vix3m=25.0)
    ts = evaluate_vix_term_structure(provider, date(2025, 6, 25))
    assert ts.vix_value == pytest.approx(20.0)
    assert ts.vix3m_value == pytest.approx(25.0)
    assert ts.ratio == pytest.approx(0.8)
    assert ts.backwardation is False


def test_term_structure_backwardation():
    """VIX=28, VIX3M=25 → ratio=1.12 → backwardation (panique court terme)."""
    provider = _FakeMacroProvider(vix=28.0, vix3m=25.0)
    ts = evaluate_vix_term_structure(provider, date(2025, 6, 25))
    assert ts.vix_value == pytest.approx(28.0)
    assert ts.vix3m_value == pytest.approx(25.0)
    assert ts.ratio == pytest.approx(1.12)
    assert ts.backwardation is True


def test_term_structure_missing_vix3m():
    """Valeur VIX3M manquante → pas de backwardation."""
    provider = _FakeMacroProvider(vix=30.0, vix3m=None)
    ts = evaluate_vix_term_structure(provider, date(2025, 6, 25))
    assert ts.vix_value == pytest.approx(30.0)
    assert ts.vix3m_value is None
    assert ts.ratio is None
    assert ts.backwardation is False


def test_term_structure_missing_vix():
    """Valeur VIX manquante → pas de ratio."""
    provider = _FakeMacroProvider(vix=None, vix3m=20.0)
    ts = evaluate_vix_term_structure(provider, date(2025, 6, 25))
    assert ts.vix_value is None
    assert ts.vix3m_value == pytest.approx(20.0)
    assert ts.ratio is None
    assert ts.backwardation is False


def test_term_structure_custom_threshold():
    """Avec backwardation_threshold=0.95, ratio=0.98 → backwardation."""
    provider = _FakeMacroProvider(vix=19.0, vix3m=19.4)
    ts = evaluate_vix_term_structure(provider, date(2025, 6, 25), backwardation_threshold=0.95)
    assert ts.ratio == pytest.approx(19.0 / 19.4)  # ≈0.979
    assert ts.backwardation is True  # ratio > 0.95


def test_term_structure_vix3m_zero():
    """VIX3M=0 ne doit pas provoquer de division par zéro."""
    provider = _FakeMacroProvider(vix=20.0, vix3m=0.0)
    ts = evaluate_vix_term_structure(provider, date(2025, 6, 25))
    assert ts.vix_value == pytest.approx(20.0)
    assert ts.vix3m_value == pytest.approx(0.0)
    assert ts.ratio is None  # pas de division par 0
    assert ts.backwardation is False


# ──────────────────────────────────────────────────────────────────────────────
# VixTermStructure dataclass
# ──────────────────────────────────────────────────────────────────────────────


def test_vix_term_structure_defaults():
    ts = VixTermStructure()
    assert ts.vix_value is None
    assert ts.vix3m_value is None
    assert ts.ratio is None
    assert ts.backwardation is False
    assert ts.data_quality == {}


def test_vix_term_structure_immutable():
    ts = VixTermStructure(vix_value=20.0, vix3m_value=25.0, ratio=0.8, backwardation=False)
    with pytest.raises(Exception):
        ts.ratio = 1.5  # type: ignore[misc]
