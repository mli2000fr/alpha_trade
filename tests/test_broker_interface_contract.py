"""Sprint S13.1 — Vérifie le contrat ``BrokerClient`` (Liskov substitution).

Toutes les implémentations enregistrées doivent répondre aux mêmes
méthodes avec la même sémantique.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from core.broker_models import OrderRequest
from core.interfaces import BrokerClient
from service.mock_broker import MockBroker


def _instances():
    """Construit la liste des implémentations testables localement."""
    out: list[BrokerClient] = [MockBroker(seed=1)]
    try:
        from service.ibkr import IBKRBrokerClient  # noqa: F401
        # IBKR nécessite TWS — on ne l'instancie pas en CI, juste son interface.
    except Exception:  # noqa: BLE001
        pass
    return out


@pytest.mark.parametrize("client", _instances(), ids=lambda c: c.name)
def test_broker_client_protocol(client):
    assert isinstance(client, BrokerClient)


@pytest.mark.parametrize("client", _instances(), ids=lambda c: c.name)
def test_get_account_returns_snapshot(client):
    snap = client.get_account()
    assert snap.account_id
    assert snap.equity >= 0


def test_mock_submit_then_position_visible():
    broker = MockBroker(seed=7)
    snap = broker.submit_order(OrderRequest(symbol="AAPL", qty=Decimal("10"), side="buy"))
    assert snap.status == "filled"
    positions = broker.get_positions()
    assert any(p.symbol == "AAPL" and p.qty == Decimal("10") for p in positions)

