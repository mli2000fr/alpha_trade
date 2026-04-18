"""Tests for execution_engine.state_machine."""
from __future__ import annotations

import pytest
from execution_engine.models import OrderStatus
from execution_engine.state_machine import can_transition, is_terminal, map_alpaca_status, require_transition


class TestStateMachine:
    def test_valid_transitions(self) -> None:
        assert can_transition(OrderStatus.NEW, OrderStatus.SUBMITTED)
        assert can_transition(OrderStatus.SUBMITTED, OrderStatus.FILLED)
        assert can_transition(OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED)
        assert can_transition(OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED)

    def test_invalid_transitions(self) -> None:
        assert not can_transition(OrderStatus.NEW, OrderStatus.FILLED)
        assert not can_transition(OrderStatus.FILLED, OrderStatus.CANCELED)

    def test_require_raises(self) -> None:
        with pytest.raises(ValueError):
            require_transition(OrderStatus.FILLED, OrderStatus.NEW)

    def test_terminal_states(self) -> None:
        assert is_terminal(OrderStatus.FILLED)
        assert is_terminal(OrderStatus.CANCELED)
        assert is_terminal(OrderStatus.REJECTED)
        assert is_terminal(OrderStatus.FAILED)
        assert is_terminal(OrderStatus.EXPIRED)
        assert not is_terminal(OrderStatus.SUBMITTED)

    def test_map_alpaca_status_filled(self) -> None:
        assert map_alpaca_status("filled") == OrderStatus.FILLED

    def test_map_alpaca_status_partial(self) -> None:
        assert map_alpaca_status("partially_filled") == OrderStatus.PARTIALLY_FILLED

    def test_map_alpaca_status_unknown(self) -> None:
        assert map_alpaca_status("bizarre_status") == OrderStatus.FAILED
