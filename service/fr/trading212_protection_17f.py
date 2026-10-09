"""Pure synthetic protection audit. No dispatch, transport, SQL or broker route."""
from dataclasses import dataclass
from decimal import Decimal

from service.fr.trading212_reconciliation_17d import ACTIVE, TERMINAL


def quantity(value, name):
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(f'Invalid {name}')
    return value


@dataclass(frozen=True)
class ExitLeg:
    broker_id: str
    kind: str
    requested: Decimal
    filled: Decimal
    status: str
    cancel_requested: bool = False

    def validate(self):
        if not isinstance(self.broker_id, str) or not self.broker_id:
            raise ValueError('Explicit synthetic leg identity required')
        if self.kind not in {'STOP', 'LIMIT_TP', 'STOP_LIMIT'}:
            raise ValueError('Unknown exit kind')
        quantity(self.requested, 'requested')
        quantity(self.filled, 'filled')
        if self.requested <= 0 or self.filled > self.requested:
            raise ValueError('Invalid exit cumulative quantity')
        if self.status not in ACTIVE | TERMINAL | {'UNKNOWN_SUBMISSION'}:
            raise ValueError('Unknown exit status')
        if self.status == 'FILLED' and self.filled != self.requested:
            raise ValueError('FILLED mismatch')
        if self.status == 'PARTIALLY_FILLED' and not 0 < self.filled < self.requested:
            raise ValueError('Partial fill mismatch')
        if self.status in {'LOCAL', 'NEW', 'UNCONFIRMED', 'CONFIRMED', 'REJECTED'} and self.filled != 0:
            raise ValueError('Status contradicts fills')

    @property
    def potentially_executable(self):
        # Request/HTTP acceptance of cancellation does NOT remove exposure.
        return self.requested - self.filled if self.status not in TERMINAL else Decimal('0')


def audit_protection(*, entry_filled, position_quantity, legs,
                     position_reconciled, entry_terminal, context='fr_simulated'):
    """Inputs describe one position epoch, no prior holding or unrelated trades.

    position_reconciled is an explicit synthetic precondition, not proof of
    freshness derived from the broker. Duplicate cumulative snapshots are not
    additional fills. Actual native OCO semantics are deliberately unqualified.
    """
    if context != 'fr_simulated':
        raise ValueError('Synthetic FR context only')
    entry = quantity(entry_filled, 'entry fill')
    held = quantity(position_quantity, 'position')
    if type(position_reconciled) is not bool or type(entry_terminal) is not bool:
        raise ValueError('Explicit reconciliation flags required')
    identifiers = set()
    for leg in legs:
        if type(leg) is not ExitLeg:
            raise ValueError('Synthetic ExitLeg required')
        leg.validate()
        if leg.broker_id in identifiers:
            raise ValueError('Duplicate exit identity')
        identifiers.add(leg.broker_id)
    sold = sum((leg.filled for leg in legs), Decimal('0'))
    exposure = sum((leg.potentially_executable for leg in legs), Decimal('0'))
    reasons = []
    if sold > entry:
        reasons.append('OVERSOLD_SYNTHETIC_POSITION')
    if sold + held != entry:
        reasons.append('POSITION_FILL_MISMATCH')
    if not position_reconciled:
        reasons.append('POSITION_NOT_RECONCILED')
    if not entry_terminal:
        reasons.append('ENTRY_CAN_STILL_FILL')
    if any(leg.status == 'UNKNOWN_SUBMISSION' for leg in legs):
        reasons.append('UNKNOWN_EXIT_SUBMISSION')
    if any(leg.status in {'REPLACING', 'REPLACED'} for leg in legs):
        reasons.append('REPLACEMENT_CHAIN_NOT_QUALIFIED')
    if exposure > held:
        reasons.append('POTENTIAL_EXIT_QUANTITY_EXCEEDS_POSITION')
    active = [leg for leg in legs if leg.potentially_executable > 0]
    if len(active) > 1:
        reasons.append('INDEPENDENT_EXITS_NOT_ATOMIC_OCO')
    if any(leg.cancel_requested and leg.status not in TERMINAL for leg in legs):
        reasons.append('CANCELLATION_NOT_CONFIRMED')
    stop_coverage = sum((leg.potentially_executable for leg in active if leg.kind == 'STOP'), Decimal('0'))
    if held > 0 and stop_coverage < held:
        reasons.append('STOP_MARKET_COVERAGE_INCOMPLETE')
    if any(leg.kind == 'STOP_LIMIT' and leg.potentially_executable > 0 for leg in legs):
        reasons.append('STOP_LIMIT_EXECUTION_NOT_GUARANTEED')
    return {'status': 'BLOCKED_SYNTHETIC_REVIEW' if reasons else 'CONSISTENT_SYNTHETIC_ONLY',
            'reasons': reasons, 'held_quantity': str(held), 'exit_filled': str(sold),
            'potential_exit_quantity': str(exposure), 'stop_market_coverage': str(stop_coverage),
            'orders_allowed': False, 'native_oco_qualified': False,
            'broker_protection_qualified': False, 'stop_price_guaranteed': False}


def replacement_preflight(*, entry_filled, position_quantity, legs,
                          old_broker_id, position_reconciled, entry_terminal):
    """No replacement sent. Exposes the protection gap after confirmed cancel."""
    audit = audit_protection(entry_filled=entry_filled, position_quantity=position_quantity,
                             legs=legs, position_reconciled=position_reconciled,
                             entry_terminal=entry_terminal)
    old = [leg for leg in legs if leg.broker_id == old_broker_id]
    if len(old) != 1 or old[0].kind != 'STOP':
        raise ValueError('Explicit old stop required')
    reasons = [r for r in audit['reasons'] if r != 'STOP_MARKET_COVERAGE_INCOMPLETE']
    if old[0].status != 'CANCELLED':
        reasons.append('OLD_STOP_NOT_CONFIRMED_CANCELLED')
    if any(leg.potentially_executable > 0 for leg in legs):
        reasons.append('OTHER_EXIT_MAY_EXECUTE')
    if position_quantity <= 0:
        reasons.append('NO_RESIDUAL_LONG_POSITION')
    return {'status': 'BLOCKED_SYNTHETIC_REPLACEMENT' if reasons else 'SYNTHETIC_REPLACEMENT_PRECONDITIONS_ONLY',
            'reasons': reasons, 'replacement_quantity': str(position_quantity) if not reasons else None,
            'unprotected_gap': position_quantity > 0 and not any(
                leg.kind == 'STOP' and leg.potentially_executable > 0 for leg in legs),
            'atomic_replace_qualified': False, 'orders_allowed': False}


def readiness():
    return {'status': 'BLOCKED_BROKER_PROTECTION_PARITY', 'orders_allowed': False,
            'stop_endpoint_documented': True, 'sell_limit_endpoint_documented': True,
            'native_oco_qualified': False, 'atomic_replace_qualified': False,
            'reduce_only_qualified': False, 'demo_behavior_tested': False,
            'blockers': ['NO_QUALIFIED_NATIVE_OCO', 'NO_QUALIFIED_ATOMIC_REPLACE',
                         'NO_EXTERNAL_ORDER_TEST', 'SHADOW_DATA_NOT_RELEASED']}
