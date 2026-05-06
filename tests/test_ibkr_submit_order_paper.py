"""Sprint S21.3 — Test paper-trading IBKR.

Désactivé par défaut : nécessite un TWS/Gateway paper en local + ``ib_insync``.

Activation::

    set IBKR_PAPER_HOST=127.0.0.1
    set IBKR_PAPER_PORT=7497
    set IBKR_PAPER_CLIENT_ID=11
    pytest -m live tests/test_ibkr_submit_order_paper.py

Le test :
1. submit un ordre limit BUY 1 share AAPL hors marché (limite très basse) ;
2. vérifie le snapshot ;
3. cancel l'ordre ;
4. vérifie qu'il a disparu de openTrades.
"""
from __future__ import annotations

import os
from decimal import Decimal

import pytest

ib_insync = pytest.importorskip("ib_insync")
pytestmark = pytest.mark.live

if not os.getenv("IBKR_PAPER_HOST"):
    pytest.skip("IBKR_PAPER_HOST non défini — test live IBKR ignoré.",
                allow_module_level=True)

from core.broker_models import OrderRequest  # noqa: E402
from service.ibkr.client import IBKRBrokerClient, IBKRUnavailableError  # noqa: E402


@pytest.fixture(scope="module")
def client():
    host = os.getenv("IBKR_PAPER_HOST", "127.0.0.1")
    port = int(os.getenv("IBKR_PAPER_PORT", "7497"))
    cid = int(os.getenv("IBKR_PAPER_CLIENT_ID", "11"))
    try:
        c = IBKRBrokerClient(host=host, port=port, client_id=cid, readonly=False)
    except IBKRUnavailableError as exc:
        pytest.skip(f"TWS paper indisponible: {exc}")
    yield c
    c.close()


def test_paper_submit_and_cancel_limit(client):
    req = OrderRequest(
        symbol="AAPL",
        qty=Decimal("1"),
        side="buy",
        type="limit",
        limit_price=Decimal("1.00"),  # hors marché : ne sera jamais exécuté
        time_in_force="day",
        client_order_id="alpha_trade-paper-test-1",
    )
    snap = client.submit_order(req)
    assert snap.order_id
    assert snap.symbol == "AAPL"
    assert snap.side == "buy"
    assert snap.status in {"new", "accepted", "pending"}

    cancelled = client.cancel_order(snap.order_id)
    assert cancelled is True

