"""OCO Manager — annulation du sibling quand un enfant bracket est filled."""
from __future__ import annotations

import logging

from execution_engine.audit import make_event
from execution_engine.db_io import ExecutionRepository
from execution_engine.models import EventType, ExecutionEvent, OrderIntent, OrderStatus
from execution_engine.broker_adapter import BrokerAdapter

LOGGER = logging.getLogger(__name__)


class OcoManager:
    """Gère la logique OCO synthétique pour les synthetic brackets."""

    def __init__(self, broker: BrokerAdapter, repo: ExecutionRepository) -> None:
        self._broker = broker
        self._repo = repo

    def check_and_cancel_sibling(
        self,
        filled_intent: OrderIntent,
        exec_run_id: str,
    ) -> list[ExecutionEvent]:
        """Si un enfant est FILLED, annule l'autre enfant du même parent."""
        if filled_intent.parent_intent_id is None:
            return []

        open_siblings = self._repo.load_open_child_orders(filled_intent.parent_intent_id)
        events: list[ExecutionEvent] = []
        for sib in open_siblings:
            # Ne pas annuler l'ordre qui vient d'être filled
            if sib.intent_id == filled_intent.intent_id:
                continue
            if sib.status in OrderStatus.TERMINAL:
                continue
            LOGGER.info("OCO cancel: %s (sibling of filled %s)", sib.broker_order_id, filled_intent.intent_id)
            success = self._broker.cancel_broker_order(sib.broker_order_id)
            events.append(make_event(
                exec_run_id,
                EventType.OCO_CANCEL_TRIGGERED,
                f"OCO cancel {'ok' if success else 'failed'}: {sib.broker_order_id}",
                symbol=sib.symbol,
                broker_order_id=sib.broker_order_id,
                intent_id=sib.intent_id,
            ))
        return events

