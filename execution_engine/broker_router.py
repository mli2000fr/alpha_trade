"""Routage explicite des brokers du moteur d'exécution (Sprint 18-A).

Le routeur ne déduit jamais le marché du symbole. CN_A n'a pas de broker
paper/live : sa recherche et son futur shadow restent hors de ce chemin.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from execution_engine.config import ExecutionConfig
from execution_engine.models import BrokerOrder, CancelResult, OrderIntent


class BrokerRouteError(RuntimeError):
    """Aucune route d'exécution sûre n'existe pour ce marché/mode."""


@runtime_checkable
class ExecutionBrokerPort(Protocol):
    """Contrat complet réellement consommé par l'OMS, le watcher et la CLI."""

    market_code: str

    def submit_intent(self, intent: OrderIntent) -> BrokerOrder: ...

    def poll_order_status(self, broker_order_id: str, intent_id: str = "") -> BrokerOrder: ...

    def cancel_broker_order(self, broker_order_id: str) -> bool: ...

    def submit_market_order(self, *, symbol: str, qty: float, side: str,
                            intent_id: str) -> BrokerOrder: ...

    def submit_oco_protection(self, parent_intent: OrderIntent,
                              tp_intent: OrderIntent, stop_intent: OrderIntent
                              ) -> tuple[BrokerOrder, BrokerOrder]: ...

    def replace_stop_order(self, existing_broker_order_id: str,
                           new_stop_intent: OrderIntent) -> BrokerOrder: ...

    def get_position(self, symbol: str) -> dict[str, Any] | None: ...

    def get_all_positions(self) -> list[dict[str, Any]]: ...

    def get_account_snapshot(self) -> dict[str, Any]: ...

    def get_account_equity(self) -> float: ...

    def get_latest_market_price(self, symbol: str) -> float | None: ...

    def is_market_open(self) -> bool: ...

    def cancel_all_open_orders(self, *, dry_run: bool = False) -> list[CancelResult]: ...

    def list_recent_orders(self, *, status: str = "all", limit: int = 500,
                           symbols: list[str] | None = None) -> list[dict[str, Any]]: ...

    def broker_order_from_api(self, payload: dict[str, Any], *,
                              intent_id: str = "") -> BrokerOrder: ...


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
        if (not isinstance(broker, ExecutionBrokerPort)
                or broker.market_code != "US_EQ"
                or getattr(broker, "simulated", False)):
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
