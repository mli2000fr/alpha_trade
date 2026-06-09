"""Tests unitaires pour `common.quantity_utils`."""
from __future__ import annotations

import pytest

from common.quantity_utils import (
    QUANTITY_EPSILON,
    format_share_quantity,
    is_effectively_integer_quantity,
    normalize_share_quantity,
)


def test_normalize_share_quantity_truncates_to_nine_decimals() -> None:
    assert normalize_share_quantity(0.3333333339) == pytest.approx(0.333333333)


def test_normalize_share_quantity_clamps_tiny_noise_to_zero() -> None:
    assert normalize_share_quantity(QUANTITY_EPSILON / 10) == 0.0


def test_is_effectively_integer_quantity_detects_quasi_integer_after_normalization() -> None:
    assert is_effectively_integer_quantity(1.0000000004) is True
    assert is_effectively_integer_quantity(1.25) is False


def test_format_share_quantity_preserves_integer_and_fractional_rendering() -> None:
    assert format_share_quantity(1.0) == "1"
    assert format_share_quantity(1.2500000001) == "1.25"
    assert format_share_quantity(0.3333333339) == "0.333333333"

