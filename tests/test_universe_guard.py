"""Tests unitaires — garde-fou breadth de l'univers ML live."""
from __future__ import annotations

import pytest

from modelFactory.universe_guard import (
    DEFAULT_MIN_UNIVERSE_PCT,
    compute_min_breadth,
    enforce_min_universe_breadth,
)


@pytest.mark.unit
def test_compute_min_breadth_75pct_of_400() -> None:
    assert compute_min_breadth(400, 75.0) == 300


@pytest.mark.unit
def test_compute_min_breadth_rounds_up() -> None:
    assert compute_min_breadth(393, 75.0) == 295


@pytest.mark.unit
def test_default_pct_is_75() -> None:
    assert DEFAULT_MIN_UNIVERSE_PCT == 75.0


@pytest.mark.unit
def test_enforce_passes_when_above_threshold() -> None:
    assert enforce_min_universe_breadth(400, minimum=300) is True


@pytest.mark.unit
def test_enforce_blocks_when_below_threshold() -> None:
    with pytest.raises(RuntimeError, match="Garde-fou breadth"):
        enforce_min_universe_breadth(50, trade_date=None, minimum=300, block=True)


@pytest.mark.unit
def test_enforce_warns_without_blocking_for_backfill() -> None:
    assert enforce_min_universe_breadth(50, minimum=300, block=False) is False
