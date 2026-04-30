"""Phase 5.3.a — Tests `compute_idempotency_key` (scope account_id).

Réf. ``prompt/refactor/plan_phase5.md`` § 5.3.a (lignes 127-132).
"""
from __future__ import annotations

from datetime import date

import pytest

from corporate_actions.models import CaType, CorporateActionEvent


@pytest.fixture()
def dividend_event() -> CorporateActionEvent:
    return CorporateActionEvent(
        provider="alpaca",
        provider_event_id="div-1",
        symbol="AAPL",
        ca_type=CaType.CASH_DIVIDEND,
        amount_per_share=0.24,
        ex_date=date(2026, 4, 15),
    )


@pytest.fixture()
def split_event() -> CorporateActionEvent:
    return CorporateActionEvent(
        provider="alpaca",
        provider_event_id="split-1",
        symbol="NVDA",
        ca_type=CaType.SPLIT,
        split_from=1,
        split_to=10,
        ex_date=date(2026, 6, 10),
    )


def test_idempotency_key_includes_account_id(dividend_event: CorporateActionEvent) -> None:
    """Deux account_id distincts → deux clés distinctes."""
    key_a = dividend_event.compute_idempotency_key("live1")
    key_b = dividend_event.compute_idempotency_key("live2")
    assert key_a != key_b
    assert len(key_a) == 32
    assert len(key_b) == 32


def test_two_accounts_distinct_keys_split(split_event: CorporateActionEvent) -> None:
    assert split_event.compute_idempotency_key("paper") != split_event.compute_idempotency_key("live1")


def test_legacy_property_equivalent_to_account_id_none(dividend_event: CorporateActionEvent) -> None:
    """``account_id=None`` → préserve la clé legacy (rétrocompat)."""
    assert dividend_event.compute_idempotency_key(None) == dividend_event.idempotency_key


def test_same_account_same_key_is_deterministic(dividend_event: CorporateActionEvent) -> None:
    """Deux appels avec même account_id → même clé (déterministe)."""
    k1 = dividend_event.compute_idempotency_key("live1")
    k2 = dividend_event.compute_idempotency_key("live1")
    assert k1 == k2


def test_split_keys_differ_from_dividend_keys(
    dividend_event: CorporateActionEvent,
    split_event: CorporateActionEvent,
) -> None:
    """Garantit que la formule scopée n'introduit pas de collisions trivialement
    cross-types."""
    assert dividend_event.compute_idempotency_key("live1") != split_event.compute_idempotency_key("live1")

