"""Tests du gate quotidien de parité risk layers (régime, allocation B4, état breaker, protections)."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtesting.parity import compare_risk_layers

IDENTICAL_LIVE = {
    "regime": "SLIDE", "trailing_policy": "c2",
    "allocation_scale": 0.10, "breaker_tripped": True,
    "episode_peak": 4200.0, "episode_trough": 3300.0,
    "episode_alloc": 0.10, "rearm_date": "2025-05-06", "force_close": False,
    "protections": {"AAPL": {"tp": 0.07, "sl": 0.025, "trailing": 0.07}},
}
IDENTICAL_REPLAY = {
    "regime": "SLIDE", "trailing_policy": "c2",
    "allocation_scale": 0.10, "breaker_tripped": True,
    "episode_peak": 4200.0, "episode_trough": 3300.0,
    "episode_alloc": 0.10, "rearm_date": "2025-05-06", "force_close": False,
    "protections": {"AAPL": {"tp": 0.07, "sl": 0.025, "trailing": 0.07}},
}


def test_identical_contexts_zero_divergence():
    assert compare_risk_layers(IDENTICAL_LIVE, IDENTICAL_REPLAY) == []


def test_float_tiny_tolerance_ok():
    ctx = dict(IDENTICAL_REPLAY, allocation_scale=0.1000001)
    assert compare_risk_layers(IDENTICAL_LIVE, ctx) == []


def test_float_beyond_tolerance_diverges():
    ctx = dict(IDENTICAL_REPLAY, allocation_scale=0.11)
    divs = compare_risk_layers(IDENTICAL_LIVE, ctx)
    assert any(d["layer"] == "allocation_scale" for d in divs)


def test_regime_discrete_strict():
    ctx = dict(IDENTICAL_REPLAY, regime="REBOUND")
    divs = compare_risk_layers(IDENTICAL_LIVE, ctx)
    assert any(d["layer"] == "regime" and d["live"] == "SLIDE" and d["replay"] == "REBOUND" for d in divs)


def test_breaker_tripped_strict():
    ctx = dict(IDENTICAL_REPLAY, breaker_tripped=False)
    divs = compare_risk_layers(IDENTICAL_LIVE, ctx)
    assert any(d["layer"] == "breaker_tripped" for d in divs)


def test_rearm_date_strict():
    ctx = dict(IDENTICAL_REPLAY, rearm_date="2025-06-01")
    divs = compare_risk_layers(IDENTICAL_LIVE, ctx)
    assert any(d["layer"] == "rearm_date" for d in divs)


def test_episode_state_diverges():
    ctx = dict(IDENTICAL_REPLAY, episode_trough=3400.0)
    divs = compare_risk_layers(IDENTICAL_LIVE, ctx)
    assert any(d["layer"] == "episode_trough" for d in divs)


def test_protection_diverges():
    ctx = {
        "regime": "SLIDE", "trailing_policy": "c2", "allocation_scale": 0.10,
        "breaker_tripped": True, "episode_peak": 4200.0, "episode_trough": 3300.0,
        "episode_alloc": 0.10, "rearm_date": "2025-05-06", "force_close": False,
        "protections": {"AAPL": {"tp": 0.07, "sl": 0.02, "trailing": 0.07}},
    }
    divs = compare_risk_layers(IDENTICAL_LIVE, ctx)
    assert any(d["layer"] == "protection.AAPL.sl" for d in divs)


def test_missing_protection_symbole_diverges():
    ctx = dict(IDENTICAL_REPLAY, protections={})
    divs = compare_risk_layers(IDENTICAL_LIVE, ctx)
    assert any(d["layer"] == "protection.AAPL.tp" for d in divs)
