"""Routage explicite des brokers du moteur d'exécution (Sprint 18-A).

Le routeur ne déduit jamais le marché du symbole. CN_A n'a pas de broker
paper/live : sa recherche et son futur shadow restent hors de ce chemin.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from execution_engine.config import ExecutionConfig
from execution_engine.models import BrokerOrder, OrderIntent


class BrokerRouteError(RuntimeError):
    """Aucune route d'exécution sûre n'existe pour ce marché/mode."""


@runtime_checkable
class ExecutionBrokerPort(Protocol):
    """Contrat minimal consommé par le moteur pour soumettre et suivre un ordre."""

    market_code: str

    def submit_intent(self, intent: OrderIntent) -> BrokerOrder: ...

    def poll_order_status(self, broker_order_id: str, intent_id: str = "") -> BrokerOrder: ...

    def cancel_broker_order(self, broker_order_id: str) -> bool: ...


class BrokerRouter:
    """Route le moteur US sans exposer accidentellement Alpaca au marché CN."""

    def __init__(self, *, us_factory: Callable[[ExecutionConfig], ExecutionBrokerPort]) -> None:
        self._us_factory = us_factory

    @staticmethod
    def validate(config: ExecutionConfig) -> None:
        # Le contrôle précède impérativement l'appel de la factory : cette
        # dernière peut ouvrir une connexion broker ou lire des credentials.
        if config.market_code != "US_EQ":
            raise BrokerRouteError(
                f"Aucun broker d'ordres pour {config.market_code!r}; "
                "CN_A reste en recherche/shadow sans ordre broker."
            )
        if config.broker_mode not in {"paper", "live"}:
            raise BrokerRouteError(f"Mode broker inconnu : {config.broker_mode!r}")

    def resolve(self, config: ExecutionConfig) -> ExecutionBrokerPort:
        self.validate(config)
        broker = self._us_factory(config)
        if not isinstance(broker, ExecutionBrokerPort) or broker.market_code != "US_EQ":
            raise BrokerRouteError("Factory US incompatible avec le contrat d'exécution US_EQ")
        return broker


def build_alpaca_broker(config: ExecutionConfig) -> ExecutionBrokerPort:
    """Construit le broker historique US après validation du marché."""
    if config.market_code != "US_EQ":
        raise BrokerRouteError("Un client Alpaca ne peut pas être créé pour un marché non US_EQ")
    from execution_engine.broker_adapter import BrokerAdapter
    from service.alpaca.trading_client import AlpacaTradingClient

    client = AlpacaTradingClient(broker_mode=config.broker_mode, account_id=config.account_id)
    return BrokerAdapter(client, config)
