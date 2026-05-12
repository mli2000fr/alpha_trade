"""Tests du pré-flight market regime (Axe C)."""
from __future__ import annotations

from execution_engine.market_regime_preflight import (
    derive_entry_mode,
    render_text_summary,
)


def _snap(**overrides):
    base = {
        "trade_date": "2025-05-01",
        "mode": "normal",
        "risk_multiplier": 1.0,
        "effective_max_positions": 10,
        "enforced_min_notional": 155,
        "allowed_slots": 12,
        "allow_new_entries": True,
        "active_patterns": [],
        "blocked_sectors": [],
        "earnings_shielded_symbols": {},
        "buyback_blackout_symbols": {},
        "macro": {},
        "reasons": [],
    }
    base.update(overrides)
    return base


def test_render_text_summary_contains_key_fields():
    text = render_text_summary(_snap())
    assert "Market-Aware Regime Pre-flight" in text
    assert "trade_date" in text
    assert "mode" in text
    assert "allowed_slots" in text


def test_derive_entry_mode_normal():
    assert derive_entry_mode(_snap()) == "normal"


def test_derive_entry_mode_close_only_from_mode():
    assert derive_entry_mode(_snap(mode="close_only")) == "close_only"


def test_derive_entry_mode_close_only_from_allow_new_entries_false():
    assert derive_entry_mode(_snap(allow_new_entries=False)) == "close_only"


def test_derive_entry_mode_capital_preservation_passthrough():
    assert derive_entry_mode(_snap(mode="capital_preservation")) == "capital_preservation"

