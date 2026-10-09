from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
import pytest
from service.fr.broker_contract_17a import FrenchTestIntent, FrenchIntentHarness, readiness
from execution_engine.broker_router import BrokerRouter, BrokerRouteError, ExecutionBrokerPort
from execution_engine.config import ExecutionConfig


def intent():
    return FrenchTestIntent('fr-test-1', 1, 'NL0000235190', 'XPAR', 2, Decimal('100'))


def harness():
    return FrenchIntentHarness(max_intent_notional_eur=Decimal('400'))


def test_local_accept_cancel_no_fill_or_release():
    h = harness()
    assert h.accept(intent())['status'] == 'ACCEPTED_SIMULATED'
    assert h.cancel(intent().intent_id)['status'] == 'CANCELED_SIMULATED'
    assert h.status(intent().intent_id)['filled_quantity'] == 0
    assert not readiness()['paper_allowed'] and not readiness()['live_allowed']
    assert not isinstance(h, ExecutionBrokerPort)


@pytest.mark.parametrize('changes', [
    {'market_code': 'US_EQ'}, {'market_code': 'CN_A'}, {'database_alias': 'us_primary'},
    {'currency': 'USD'}, {'mic': 'XNAS'}, {'account_id': 'default'},
    {'isin': 'NL0000235191'}, {'instrument_id': True}, {'side': 'sell'},
    {'quantity': 1.5}, {'quantity': True}, {'quantity': 0},
    {'reference_price_eur': Decimal('NaN')}, {'reference_price_eur': Decimal('-1')},
    {'reference_price_eur': 100.0}, {'intent_id': ''},
])
def test_invalid_intentions_rejected(changes):
    with pytest.raises(ValueError):
        harness().accept(replace(intent(), **changes))


def test_notional_duplicate_and_kill_switch():
    h = harness()
    with pytest.raises(ValueError, match='notionnel'):
        h.accept(replace(intent(), quantity=5))
    h.accept(intent())
    with pytest.raises(ValueError, match='déjà'):
        h.accept(intent())
    h.kill()
    assert h.status(intent().intent_id)['status'] == 'CANCELED_SIMULATED'
    with pytest.raises(ValueError, match='Kill'):
        h.accept(replace(intent(), intent_id='new'))


def test_concurrent_duplicate_accepted_once():
    h = harness()
    def submit(_):
        try:
            h.accept(intent())
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(submit, range(8))) == 1


@pytest.mark.parametrize('market', ['FR_EQ', 'CN_A', 'CN_BJ'])
def test_router_never_calls_us_factory_for_foreign_market(market):
    calls = []
    router = BrokerRouter(us_factory=lambda cfg: calls.append(cfg))
    with pytest.raises(BrokerRouteError):
        router.resolve(replace(ExecutionConfig(), market_code=market))
    assert calls == []
