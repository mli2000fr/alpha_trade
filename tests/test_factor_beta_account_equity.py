"""Budget measured against actual equity; unchanged factor/entry protections."""
from dataclasses import replace
from datetime import UTC, date, datetime
from types import SimpleNamespace

import numpy as np
import pytest

from risk_management.config import RiskConfig
from risk_management.factor_account import projected_factor_weights
from risk_management.factor_model import (FactorCovariance, portfolio_beta_exposure,
    check_factor_constraints_on_sized_weights)
from risk_management.models import FactorExposures
from risk_management.operational_data import BacktestOperationalDataAdapter


DAY=date(2026,10,27)


def exposure(beta=3.):
    return {'A':FactorExposures('A',DAY,beta,abs(beta),abs(beta))}


def covariance():
    return FactorCovariance(np.eye(3),['market','size','momentum'],{'A':.05},DAY)


def beta_rejections(weight, beta=3.):
    return check_factor_constraints_on_sized_weights({'A':weight},exposure(beta),covariance(),
        beta_exposure_basis='account_equity')


def test_small_entry_counts_cash_and_keeps_legacy_calculation_available():
    assert portfolio_beta_exposure({'A':100/4000},exposure(),basis='account_equity')==pytest.approx(.075)
    assert portfolio_beta_exposure({'A':100/4000},exposure(),basis='invested_capital')==pytest.approx(3.)
    assert not beta_rejections(.025)
    assert any('final_beta_exceeded' in reason for reason in beta_rejections(1.))


def test_leverage_increases_exposure_and_cannot_be_normalized_away():
    assert not beta_rejections(.4,2.)
    assert any('final_beta_exceeded' in reason for reason in beta_rejections(.8,2.))
    assert portfolio_beta_exposure({'A':2.},exposure(1.),basis='account_equity')==2.


def test_short_and_negative_beta_do_not_create_unqualified_netting_credit():
    exposures=exposure(3.)|{'B':FactorExposures('B',DAY,-3.,3.,3.)}
    assert portfolio_beta_exposure({'A':.25,'B':-.25},exposures,basis='account_equity')==1.5
    assert portfolio_beta_exposure({'A':-.5},exposure(),basis='account_equity')==1.5


@pytest.mark.parametrize('weights,exposures', [({'A':.1},{}),({'A':float('nan')},exposure()),
    ({'A':.1},exposure(float('nan')))])
def test_missing_or_nonfinite_data_never_qualify(weights,exposures):
    assert check_factor_constraints_on_sized_weights(weights,exposures,covariance(),
        beta_exposure_basis='account_equity')[0].startswith('factor_beta_inputs_unqualified')


def test_new_basis_does_not_relax_factor_concentration_or_diversification():
    exp={'A':FactorExposures('A',DAY,.1,10.,.01)}
    reasons=check_factor_constraints_on_sized_weights({'A':.001},exp,covariance(),
        beta_exposure_basis='account_equity')
    assert not any('final_beta_exceeded' in r for r in reasons)
    assert any('concentration' in r for r in reasons)
    assert any('diversification' in r for r in reasons)


def test_config_yaml_selects_equity_basis_and_legacy_snapshots_keep_old_default():
    cfg=RiskConfig.from_yaml_section({'beta_exposure_basis':'account_equity','max_portfolio_beta':1.2})
    assert cfg.beta_exposure_basis=='account_equity' and cfg.max_portfolio_beta==1.2
    assert RiskConfig.from_dict({}).beta_exposure_basis=='invested_capital'
    assert RiskConfig.from_dict(cfg.to_dict(exclude_defaults=False)).fingerprint==cfg.fingerprint
    with pytest.raises(ValueError,match='beta_exposure_basis'):
        replace(cfg,beta_exposure_basis='invalid')
    with pytest.raises(ValueError,match='max_portfolio_beta'):
        replace(cfg,max_portfolio_beta=float('nan'))


def snapshot(orders=(),positions=None):
    return BacktestOperationalDataAdapter.build(account_id='default',
        as_of=datetime(2026,10,28,12,tzinfo=UTC),
        account=dict(equity=4000.,cash=3000.,settled_cash=3000.,buying_power=3000.),
        positions=positions if positions is not None else [dict(symbol='A',side='long',qty='10',
            avg_entry_price='100',current_price='110')],orders=orders)


def entry(symbol='B',notional=100.):
    return SimpleNamespace(symbol=symbol,side='buy',decision='ACCEPTED',approved_shares=1.,target_notional=notional)


def test_account_projection_counts_holdings_remaining_pending_and_new_entries():
    snap=snapshot([dict(id='p',symbol='B',side='buy',type='limit',qty='5',filled_qty='2',limit_price='100')])
    weights=projected_factor_weights([entry()],4000.,snap)
    assert weights=={'A':1100/4000,'B':400/4000}
    assert snap.open_orders[0].limit_price==100.


def test_pending_protection_does_not_remove_held_market_exposure():
    snap=snapshot([dict(id='stop',symbol='A',side='sell',type='stop',qty='10',stop_price='90')])
    assert projected_factor_weights([],4000.,snap)=={'A':1100/4000}


def test_unpriced_pending_entry_or_wrong_equity_blocks_new_risk_targets():
    snap=snapshot([dict(id='p',symbol='B',side='buy',type='market',qty='5')])
    with pytest.raises(ValueError,match='Bounded pending'):
        projected_factor_weights([entry()],4000.,snap)
    with pytest.raises(ValueError,match='equity differs'):
        projected_factor_weights([entry()],8000.,snapshot())


def test_unfilled_opposite_entry_cannot_be_used_to_reduce_factor_risk():
    with pytest.raises(ValueError,match='side flip'):
        projected_factor_weights([],4000.,snapshot([
            dict(id='p',symbol='A',side='sell',type='limit',qty='11',limit_price='110')]))
