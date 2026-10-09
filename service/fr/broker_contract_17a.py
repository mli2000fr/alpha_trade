"""Offline FR intent harness; deliberately not an ExecutionBrokerPort or broker route."""
from dataclasses import dataclass
from decimal import Decimal
from threading import RLock
import re


def valid_isin(value: str) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]', value):
        return False
    digits = ''.join(str(ord(c) - 55) if c.isalpha() else c for c in value)
    total = 0
    for i, char in enumerate(reversed(digits)):
        number = int(char) * (2 if i % 2 else 1)
        total += number // 10 + number % 10
    return total % 10 == 0


@dataclass(frozen=True)
class FrenchTestIntent:
    intent_id: str
    instrument_id: int
    isin: str
    mic: str
    quantity: int
    reference_price_eur: Decimal
    market_code: str = 'FR_EQ'
    database_alias: str = 'fr_primary'
    currency: str = 'EUR'
    account_id: str = 'fr_simulated'
    side: str = 'buy'

    def validate(self):
        if (self.market_code, self.database_alias, self.currency, self.mic, self.account_id) != (
                'FR_EQ', 'fr_primary', 'EUR', 'XPAR', 'fr_simulated'):
            raise ValueError('Contexte FR simulé exclusivement : aucune route US/CN/PAPER/live')
        if not self.intent_id or not isinstance(self.intent_id, str):
            raise ValueError('Identifiant intention explicite requis')
        if type(self.instrument_id) is not int or self.instrument_id <= 0 or not valid_isin(self.isin):
            raise ValueError('Identité instrument/ISIN invalide')
        if self.side != 'buy':
            raise ValueError('Entrées LONG seulement ; aucune simulation de short')
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError('Quantité entière positive requise')
        if (not isinstance(self.reference_price_eur, Decimal)
                or not self.reference_price_eur.is_finite() or self.reference_price_eur <= 0):
            raise ValueError('Prix de référence EUR fini positif requis')


class FrenchIntentHarness:
    """Accept/cancel only; no fills, cash mutation, SQL, clock, network or credentials."""
    simulated = True
    market_code = 'FR_EQ'

    def __init__(self, *, max_intent_notional_eur: Decimal):
        if (not isinstance(max_intent_notional_eur, Decimal)
                or not max_intent_notional_eur.is_finite() or max_intent_notional_eur <= 0):
            raise ValueError('Limite de notionnel de test positive requise')
        self._limit = max_intent_notional_eur
        self._lock = RLock()
        self._intents = {}
        self._killed = False

    def accept(self, intent: FrenchTestIntent):
        intent.validate()
        with self._lock:
            if self._killed:
                raise ValueError('Kill switch actif')
            if intent.intent_id in self._intents:
                raise ValueError('Intention déjà soumise ; pas de second ordre implicite')
            if intent.quantity * intent.reference_price_eur > self._limit:
                raise ValueError('Limite de notionnel dépassée')
            self._intents[intent.intent_id] = (intent, 'ACCEPTED_SIMULATED')
            return self.status(intent.intent_id)

    def status(self, intent_id):
        with self._lock:
            intent, state = self._intents[intent_id]
            return {'intent_id': intent.intent_id, 'status': state, 'filled_quantity': 0,
                    'simulated': True, 'orders_allowed': False}

    def cancel(self, intent_id):
        with self._lock:
            intent, _ = self._intents[intent_id]
            self._intents[intent_id] = (intent, 'CANCELED_SIMULATED')
            return self.status(intent_id)

    def kill(self):
        with self._lock:
            self._killed = True
            for key in self._intents:
                self.cancel(key)


def readiness():
    return {'market_code': 'FR_EQ', 'database_alias': 'fr_primary',
            'status': 'PREPARATION_ONLY', 'paper_allowed': False, 'live_allowed': False,
            'sql_writes': False, 'blockers': ['BLOCKED_BROKER', 'BLOCKED_SHADOW_DATA'],
            'harness_is_broker_adapter': False}
