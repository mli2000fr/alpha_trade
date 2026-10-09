"""Synthetic FR order journal. No network, credentials, SQL or broker route.

Sequence numbers belong to the local evidence recorder, not Trading212.
This in-memory harness cannot provide durable production idempotency.
"""
from dataclasses import dataclass, replace
from decimal import Decimal
from threading import RLock

from service.fr.broker_contract_17a import FrenchTestIntent

ACTIVE = {'LOCAL', 'UNCONFIRMED', 'CONFIRMED', 'NEW', 'PARTIALLY_FILLED',
          'CANCELLING', 'REPLACING'}
TERMINAL = {'FILLED', 'CANCELLED', 'REJECTED', 'REPLACED'}


@dataclass(frozen=True)
class OrderEvidence:
    intent_id: str
    requested: Decimal
    status: str = 'REGISTERED_SYNTHETIC'
    filled: Decimal = Decimal('0')
    broker_id: str | None = None
    sequence: int = -1
    dispatch_attempted: bool = False
    cancel_requested: bool = False
    quarantined: bool = False


class SyntheticOrderJournal:
    """Failure-closed state tests, deliberately not ExecutionBrokerPort."""
    simulated = True
    orders_allowed = False

    def __init__(self, max_intent_notional_eur: Decimal):
        if (not isinstance(max_intent_notional_eur, Decimal)
                or not max_intent_notional_eur.is_finite() or max_intent_notional_eur <= 0):
            raise ValueError('Invalid synthetic notional limit')
        self._limit = max_intent_notional_eur
        self._orders = {}
        self._broker_owners = {}
        self._lock = RLock()
        self._killed = False

    def register(self, intent: FrenchTestIntent):
        intent.validate()
        with self._lock:
            if self._killed or intent.intent_id in self._orders:
                raise ValueError('Killed journal or duplicate intention')
            if intent.quantity * intent.reference_price_eur > self._limit:
                raise ValueError('Synthetic per-intent notional limit exceeded')
            self._orders[intent.intent_id] = OrderEvidence(intent.intent_id, Decimal(intent.quantity))
            return self.snapshot(intent.intent_id)

    def begin_dispatch(self, intent_id):
        """Record a synthetic attempt only. This function NEVER sends an order."""
        with self._lock:
            order = self._orders[intent_id]
            if self._killed or order.dispatch_attempted or order.quarantined or order.cancel_requested:
                raise ValueError('Dispatch prohibited; no automatic resend')
            self._orders[intent_id] = replace(order, dispatch_attempted=True,
                                             status='SUBMISSION_PENDING_SYNTHETIC')
            return self.snapshot(intent_id)

    def submission_timeout(self, intent_id):
        with self._lock:
            order = self._orders[intent_id]
            if order.status != 'SUBMISSION_PENDING_SYNTHETIC':
                raise ValueError('No pending synthetic submission')
            self._orders[intent_id] = replace(order, status='UNKNOWN_SUBMISSION')
            return self.snapshot(intent_id)

    def observe(self, intent_id, *, broker_id, status, filled: Decimal, sequence: int):
        """Replay already-correlated synthetic receipts; do not infer ownership."""
        with self._lock:
            order = self._orders[intent_id]
            try:
                if order.quarantined or not order.dispatch_attempted:
                    raise ValueError('Unsubmitted or quarantined intention')
                if type(sequence) is not int or sequence < 0:
                    raise ValueError('Invalid local receipt sequence')
                if status not in ACTIVE | TERMINAL:
                    raise ValueError('Unknown broker status')
                if not isinstance(broker_id, str) or not broker_id:
                    raise ValueError('Explicit correlated broker identity required')
                if order.broker_id is not None and order.broker_id != broker_id:
                    raise ValueError('Broker identity changed')
                if self._broker_owners.get(broker_id, intent_id) != intent_id:
                    raise ValueError('Broker identity already bound to another intention')
                if (not isinstance(filled, Decimal) or not filled.is_finite()
                        or not Decimal('0') <= filled <= order.requested):
                    raise ValueError('Invalid cumulative filled quantity')
                if sequence <= order.sequence:
                    if (sequence == order.sequence and status == order.status
                            and filled == order.filled and broker_id == order.broker_id):
                        return self.snapshot(intent_id)  # Exact duplicate receipt.
                    raise ValueError('Stale or conflicting receipt; manual review required')
                if filled < order.filled:
                    raise ValueError('Cumulative fill regression')
                if status == 'FILLED' and filled != order.requested:
                    raise ValueError('FILLED does not match requested quantity')
                if status == 'PARTIALLY_FILLED' and not Decimal('0') < filled < order.requested:
                    raise ValueError('Invalid partial fill')
                if status == 'REJECTED' and filled != 0:
                    raise ValueError('Rejected order with fills')
                if status in {'LOCAL', 'UNCONFIRMED', 'CONFIRMED', 'NEW'} and filled != 0:
                    raise ValueError('Non-fill status with filled quantity')
                if order.status in TERMINAL and (status != order.status or filled != order.filled):
                    raise ValueError('Terminal state changed; reconcile manually')
            except ValueError:
                self._orders[intent_id] = replace(order, quarantined=True)
                raise
            self._broker_owners[broker_id] = intent_id
            self._orders[intent_id] = replace(order, broker_id=broker_id, status=status,
                                              filled=filled, sequence=sequence)
            return self.snapshot(intent_id)

    def request_cancel(self, intent_id):
        """Local flag only, not an external cancellation or confirmation."""
        with self._lock:
            order = self._orders[intent_id]
            if order.status in TERMINAL:
                return self.snapshot(intent_id)
            self._orders[intent_id] = replace(order, cancel_requested=True)
            return self.snapshot(intent_id)

    def kill(self):
        with self._lock:
            self._killed = True
            for intent_id in self._orders:
                self.request_cancel(intent_id)
            # Filled/unknown positions are NOT closed magically by a kill switch.
            return [self.snapshot(intent_id) for intent_id in self._orders]

    def snapshot(self, intent_id):
        with self._lock:
            order = self._orders[intent_id]
            return {
                'intent_id': order.intent_id, 'status': order.status,
                'requested_quantity': str(order.requested), 'filled_quantity': str(order.filled),
                'remaining_quantity': str(order.requested - order.filled),
                'broker_id': order.broker_id, 'receipt_sequence': order.sequence,
                'cancel_requested': order.cancel_requested, 'quarantined': order.quarantined,
                'dispatch_attempted_synthetic': order.dispatch_attempted,
                'orders_allowed': False, 'simulated': True,
                'native_oco_qualified': False, 'durable_idempotency_qualified': False,
            }
