"""Native risk for amplitude LONG: no fake edge/probability, no relaxed limits."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from tests.test_oracle_pure_portfolio_policy import DAY, setup
from risk_management.models import PriceInfo
from risk_management.oracle_path_contract import build_entries
from risk_management.selection_contract import MLRankedCandidate
from risk_management.cli import _wire_covariance_to_optimizer


def candidate(**changes):
    return replace(MLRankedCandidate('NEW', DAY, 'long', p_side=.9, side_rank=1,
        model_run_id='oracle', universe_run_id='universe',
        lineage={'score_semantics':'amplitude_rank_not_directional_probability'}), **changes)


def build(builder, c=None, prices=None):
    return build_entries(builder,[c or candidate()], prices if prices is not None else {
        'NEW':PriceInfo('NEW',100.,2.,DAY,DAY,1000000.)}, {'NEW':'Tech'},DAY,pd.DataFrame())


def test_rank_is_preserved_without_probabilities_or_kelly():
    entry = build(setup())[0]
    assert entry.approved_shares > 0 and entry.side == 'buy'
    assert entry.predicted_proba is None and entry.effective_probability is None
    assert entry.kelly_fraction is None and entry.score_source == 'oracle_amplitude_rank'
    assert entry.score_used == .9


@pytest.mark.parametrize('params', [dict(buying_power=0),dict(max_positions=1, positions=[
    {'symbol':'HELD','qty':10,'side':'long','avg_entry_price':100.,'current_price':100.}]),
    dict(max_positions=1, orders=[{'id':'pending','symbol':'PENDING','side':'buy','qty':1.,'type':'market','status':'open'}])])
def test_account_cash_positions_and_pending_orders_still_limit_entries(params):
    assert all(e.approved_shares == 0 for e in build(setup(**params)))


def test_same_symbol_pending_is_not_ordered_twice():
    b=setup(orders=[{'id':'pending','symbol':'NEW','side':'buy','qty':1.,'type':'market','status':'open'}])
    assert build(b) == []


@pytest.mark.parametrize('c', [candidate(side='short'),candidate(trade_date=DAY.replace(day=1)),
    candidate(lineage={}),candidate(p_side=float('nan'))])
def test_wrong_direction_date_semantics_or_score_fail_closed(c):
    with pytest.raises(ValueError): build(setup(),c)


def test_missing_prices_cannot_be_admitted():
    with pytest.raises(ValueError,match='non qualifié'): build(setup(), prices={})


def test_snapshot_and_regime_guards_remain_in_force():
    b=setup()
    b._operational_snapshot=None
    with pytest.raises(ValueError,match='snapshot'):build(b)
    b=setup()
    b._regime_snapshot=replace(b._regime_snapshot,allowed_long_entries=False)
    assert build(b)==[]


def test_real_factor_budget_can_still_refuse_an_entry():
    from risk_management.factor_model import FactorCovariance, FactorExposures
    b=setup(enable_factor_model=True,max_portfolio_beta=.001,beta_exposure_basis='account_equity')
    b._factor_covariance=FactorCovariance(np.eye(3),['market','size','momentum'],{'NEW':.05},DAY)
    b._factor_exposures={'NEW':FactorExposures('NEW',DAY,10.,10.,10.)}
    assert all(e.approved_shares==0 for e in build(b))


def test_correlation_filter_remains_active_for_amplitude_strategy():
    b=setup(correlation_min_overlap=2)
    second=candidate(symbol='OTHER',p_side=.8,side_rank=2)
    returns=pd.DataFrame({'NEW':[.01,-.01,.02],'OTHER':[.01,-.01,.02]},
                         index=pd.bdate_range(end=DAY,periods=3))
    result=build_entries(b,[candidate(),second],
        {s:PriceInfo(s,100.,2.,DAY,DAY,1000000.) for s in ['NEW','OTHER']},
        {'NEW':'Tech','OTHER':'Tech'},DAY,returns)
    assert len(result)==2
    assert sum(e.approved_shares>0 for e in result)==1
    assert any('corrélation' in e.decision_reason for e in result)


@pytest.mark.parametrize('policy',['oracle_pure_long','oracle_web_llm_directional'])
def test_covariance_is_retained_without_attaching_inapplicable_edge_optimizer(policy):
    b=setup()
    fc=SimpleNamespace(factor_cov=np.eye(3))
    b._factor_covariance=fc
    b._factor_exposures={'NEW':object()}
    _wire_covariance_to_optimizer(b,factor_cov_live=fc, operational_snapshot=b.operational_snapshot,
        directional_win_rates={},config=b._cfg,selection_policy=policy)
    assert b._portfolio_optimizer is None
    assert b._factor_covariance is fc and 'NEW' in b._factor_exposures


def test_directional_optimizer_still_requires_its_real_edges():
    b=setup()
    _wire_covariance_to_optimizer(b,factor_cov_live=SimpleNamespace(factor_cov=np.eye(3)),
        operational_snapshot=b.operational_snapshot,directional_win_rates={},config=b._cfg)
    assert b._portfolio_optimizer is not None
    with pytest.raises(ValueError,match='qualified directional edges'):build(b)
    with pytest.raises(ValueError,match='inconnue'):
        _wire_covariance_to_optimizer(b,factor_cov_live=None,operational_snapshot=None,
            directional_win_rates={},config=b._cfg,selection_policy='typo')
