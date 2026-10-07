"""Sprint 18-A : US inchangé, CN bloqué avant tout accès broker."""

from __future__ import annotations

from dataclasses import replace

import pytest

from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.broker_doubles_18d import MockBrokerAdapter
from execution_engine.broker_router import BrokerRouteError, BrokerRouter, build_alpaca_broker
from execution_engine.config import ExecutionConfig


def test_us_route_preserves_broker_instance() -> None:
    calls = []
    config = ExecutionConfig(broker_mode="paper")
    broker = BrokerAdapter(object(), config)
    router = BrokerRouter(us_factory=lambda cfg: (calls.append(cfg), broker)[1])

    assert router.resolve(config) is broker
    assert calls == [config]


def test_simulated_adapter_cannot_be_routed_to_paper_or_live() -> None:
    for mode in ("paper", "live"):
        router = BrokerRouter(us_factory=lambda _cfg: MockBrokerAdapter())
        with pytest.raises(BrokerRouteError, match="incompatible"):
            router.resolve(ExecutionConfig(broker_mode=mode))


@pytest.mark.parametrize("market", ["CN_A", "CN_BJ", "", "FR_EQ"])
def test_foreign_market_is_rejected_before_factory(market: str) -> None:
    calls = []
    router = BrokerRouter(us_factory=lambda cfg: calls.append(cfg))

    with pytest.raises(BrokerRouteError, match="Aucun broker"):
        router.resolve(replace(ExecutionConfig(), market_code=market))
    assert calls == []


def test_unknown_mode_and_incompatible_factory_fail_closed() -> None:
    calls = []
    router = BrokerRouter(us_factory=lambda cfg: calls.append(cfg))
    # ExecutionConfig refuse déjà le mode inconnu, avant le routeur.
    with pytest.raises(ValueError, match="broker_mode"):
        ExecutionConfig(broker_mode="simulation")
    assert calls == []
    with pytest.raises(BrokerRouteError, match="incompatible"):
        router.resolve(ExecutionConfig())


def test_alpaca_adapter_refuses_cn_even_with_injected_client() -> None:
    class NeverCalledClient:
        def submit_order(self, payload):
            raise AssertionError("Alpaca appelé")

    with pytest.raises(ValueError, match="US_EQ"):
        BrokerAdapter(NeverCalledClient(), ExecutionConfig(market_code="CN_A"))


def test_alpaca_factory_refuses_cn_before_importing_client() -> None:
    with pytest.raises(BrokerRouteError, match="non US_EQ"):
        build_alpaca_broker(ExecutionConfig(market_code="CN_A"))
