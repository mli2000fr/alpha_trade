from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest

from service.fr.provider_exploratory_engine_13b import ReplayBlocked, replay_assumed, resolve_assumed_liability
from service.fr.provider_exploratory_metrics_13b import ledger_metrics
from service.fr.portfolio_replay_12b import replay as strict_replay, ReplayBlocked as StrictBlocked
from tests.test_fr_portfolio_replay_12b import fixture


def assumed_fixture(tmp_path):
    tape,costs,tax=fixture(tmp_path)
    tape['evidence_state']='EXPLORATORY_PROVIDER_ASSUMED'
    for coverage in tape['corporate_action_coverage'].values():
        coverage['supplier_assumption_accepted']=coverage.pop('verified')
    for bars in tape['bars'].values():
        for bar in bars.values():
            bar['supplier_assumption_accepted']=bar.pop('economic_verified')
    return tape,costs,tax


def test_explicit_profile_and_no_strict_promotion(tmp_path):
    tape,costs,tax=assumed_fixture(tmp_path)
    with pytest.raises(StrictBlocked):
        strict_replay(tape,costs,tax)
    tape.pop('evidence_state')
    with pytest.raises(ValueError,match='Explicit exploratory'):
        replay_assumed(tape,costs,{'known_positive':{},'unknown_liable':False})


@pytest.mark.parametrize('unknown',[True,False])
def test_reconciliation_metrics_and_tax_scenarios(tmp_path,unknown):
    tape,costs,_=assumed_fixture(tmp_path)
    result=replay_assumed(tape,costs,{'known_positive':{},'unknown_liable':unknown})
    assert result['economic_go_allowed'] is False
    assert result['costs']['taxes']>0 if unknown else result['costs']['taxes']==0
    assert result['gross_pnl']==90
    assert result['net_pnl']==result['final_equity']-result['initial_equity']
    metrics=ledger_metrics(result,data_kind='EXPLORATORY_PROVIDER_ASSUMED')
    assert metrics['not_production_evidence'] and metrics['closed_trades']==1
    with pytest.raises(ValueError):
        ledger_metrics(result,data_kind='QUALIFIED_RESEARCH')


def test_known_positive_never_exempt_and_tax_not_stressed(tmp_path):
    assert resolve_assumed_liability({'known_positive':{'A.PA/2025':True},'unknown_liable':False},'A.PA',date(2025,1,1))
    tape,costs,_=assumed_fixture(tmp_path)
    scenario={'known_positive':{'A.PA/2025':True},'unknown_liable':False}
    nominal=replay_assumed(tape,costs,scenario)
    stress=replay_assumed(tape,costs,scenario,stress_multiplier=Decimal(2))
    assert stress['costs']['commission']==nominal['costs']['commission']*2
    # Same quantity, tax base reflects execution-price impact, not x2 tax rate.
    assert stress['costs']['taxes']<nominal['costs']['taxes']*2


def test_missing_held_price_blocks_no_future_exclusion(tmp_path):
    tape,costs,_=assumed_fixture(tmp_path)
    del tape['bars'][tape['sessions'][1]]['A']
    with pytest.raises(ReplayBlocked) as caught:
        replay_assumed(tape,costs,{'known_positive':{},'unknown_liable':False})
    assert caught.value.ledger['orders'][0]['side']=='BUY'
    with pytest.raises(ValueError):
        ledger_metrics({'status':'BLOCKED_EXPLORATORY_CELL'},data_kind='EXPLORATORY_PROVIDER_ASSUMED')


def test_incomplete_dividend_blocks_only_if_held(tmp_path):
    tape,costs,_=assumed_fixture(tmp_path)
    tape['events']=[{'id':'bad','uid':'A','session':tape['sessions'][1],
        'kind':'UNSUPPORTED_DIVIDEND_FIELDS','supplier_assumption_accepted':True,'evidence':'provider',
        'problems':['PAYMENT_DATE_MISSING']}]
    with pytest.raises(ReplayBlocked,match='bad'):
        replay_assumed(tape,costs,{'known_positive':{},'unknown_liable':False})
    tape['candidates']=[]
    assert replay_assumed(tape,costs,{'known_positive':{},'unknown_liable':False})['net_pnl']==0


def test_reserved_confirmation_and_lookahead_block(tmp_path):
    tape,costs,_=assumed_fixture(tmp_path)
    scenario={'known_positive':{},'unknown_liable':False}
    future=deepcopy(tape)
    future['sessions'].append('2026-01-02')
    with pytest.raises(ValueError,match='réservée'):
        replay_assumed(future,costs,scenario)
    tape['candidates'][0]['available_at']='2025-03-28T08:00:00+00:00'
    with pytest.raises(ValueError,match='non disponible'):
        replay_assumed(tape,costs,scenario)
