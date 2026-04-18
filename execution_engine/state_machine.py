"""Order lifecycle state machine."""
from __future__ import annotations

from execution_engine.models import OrderStatus

# Transitions autorisées : {old_status: {new_status, ...}}
_TRANSITIONS: dict[str, frozenset[str]] = {
    OrderStatus.NEW: frozenset({OrderStatus.SUBMITTED}),
    OrderStatus.SUBMITTED: frozenset({
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
        OrderStatus.FAILED,
        OrderStatus.EXPIRED,
    }),
    OrderStatus.PARTIALLY_FILLED: frozenset({
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.FAILED,
    }),
}

# Mapping statuts Alpaca → statuts internes
_ALPACA_MAP: dict[str, str] = {
    "new": OrderStatus.NEW,
    "accepted": OrderStatus.SUBMITTED,
    "pending_new": OrderStatus.SUBMITTED,
    "partially_filled": OrderStatus.PARTIALLY_FILLED,
    "filled": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELED,
    "expired": OrderStatus.EXPIRED,
    "rejected": OrderStatus.REJECTED,
    "pending_cancel": OrderStatus.SUBMITTED,
    "pending_replace": OrderStatus.SUBMITTED,
}


def is_terminal(status: str) -> bool:
    return status in OrderStatus.TERMINAL


def can_transition(old: str, new: str) -> bool:
    if is_terminal(old):
        return False
    allowed = _TRANSITIONS.get(old)
    if allowed is None:
        return False
    return new in allowed


def require_transition(old: str, new: str) -> None:
    if not can_transition(old, new):
        raise ValueError(f"Transition illégale : {old} → {new}")


def map_alpaca_status(alpaca_status: str) -> str:
    return _ALPACA_MAP.get(alpaca_status.lower(), OrderStatus.FAILED)

