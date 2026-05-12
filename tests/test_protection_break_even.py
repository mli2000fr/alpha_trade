"""Tests des helpers break-even / EOD (Axe F)."""
from __future__ import annotations

from datetime import datetime

from execution_engine.config import TrailingStopConfig
from execution_engine.protection_break_even import (
    compute_break_even_stop_price,
    is_eod_review_window,
    should_promote_to_break_even,
)


def _cfg(**kw):
    base = dict(enabled=True, mode="dynamic_atr", break_even_after_atr_multiple=2.0,
                eod_check_time_est="15:50")
    base.update(kw)
    return TrailingStopConfig(**base)


def test_break_even_triggers_above_threshold():
    assert should_promote_to_break_even(
        avg_fill_price=100, current_price=105, atr_value=2.0, shares=10, cfg=_cfg(),
    )


def test_break_even_does_not_trigger_below_threshold():
    assert not should_promote_to_break_even(
        avg_fill_price=100, current_price=103, atr_value=2.0, shares=10, cfg=_cfg(),
    )


def test_break_even_disabled_when_config_off():
    assert not should_promote_to_break_even(
        avg_fill_price=100, current_price=200, atr_value=2.0, shares=10, cfg=_cfg(enabled=False),
    )


def test_break_even_no_atr_returns_false():
    assert not should_promote_to_break_even(
        avg_fill_price=100, current_price=200, atr_value=None, shares=10, cfg=_cfg(),
    )


def test_break_even_stop_price_equals_entry():
    assert compute_break_even_stop_price(100.123) == 100.12


def test_eod_review_window_after_time():
    assert is_eod_review_window(now_eastern=datetime(2025, 5, 1, 16, 0), cfg=_cfg())


def test_eod_review_window_before_time():
    assert not is_eod_review_window(now_eastern=datetime(2025, 5, 1, 14, 0), cfg=_cfg())


def test_eod_review_window_disabled():
    assert not is_eod_review_window(
        now_eastern=datetime(2025, 5, 1, 16, 0), cfg=_cfg(enabled=False),
    )

