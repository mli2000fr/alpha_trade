from datetime import UTC,date,datetime

import numpy as np
import pandas as pd
import pytest

from risk_management.config import RiskConfig
from risk_management.models import FactorExposures
from risk_management.factor_model import FactorCovariance
from risk_management.live_factor_context import observed_factor_returns, factor_violations, qualify_factor_context

DAY=date(2026,10,27)
NOW=datetime(2026,10,28,10,tzinfo=UTC)


def evidence():
    ix=pd.bdate_range(end=str(DAY),periods=272);k=np.arange(272)
    prices=pd.DataFrame(dict(SPY=100*np.exp(.0002*k+.01*np.sin(k/6)),
        IWM=100*np.exp(.0001*k+.02*np.sin(k/9)),MTUM=100*np.exp(.0003*k+.015*np.cos(k/7))),index=ix)
    frame=pd.DataFrame([dict(symbol=f'S{i}',quality='QUALIFIED',asof_date=DAY,observed_at=NOW,
        run_id='test',beta_126=.5+i/30,market_cap=1e9*(i+1),trend_score=i/24) for i in range(25)])
    returns=pd.DataFrame({'S0':prices.SPY.pct_change(fill_method=None)+.001*np.sin(k)},index=ix)
    return frame,prices,returns


def test_proxy_factors_are_observed_returns_not_returns_of_returns_or_zeros():
    _,prices,_=evidence()
    factors=observed_factor_returns(prices)
    expected=prices.pct_change(fill_method=None).iloc[1:]
    np.testing.assert_allclose(factors.market,expected.SPY)
    np.testing.assert_allclose(factors['size'],expected.IWM-expected.SPY)
    assert factors.var().gt(0).all()


def test_qualification_requires_actual_inputs_and_residuals():
    frame,prices,returns=evidence()
    context=qualify_factor_context(frame,prices,returns,['S0'],DAY,NOW,RiskConfig())
    assert context['qualified'] and context['universe_count']==25
    assert context['covariance'].specific_variances['S0']>=0
    assert context['factor_names']==['market','size','momentum']
    assert context['value_factor'].startswith('NOT_MODELED')


@pytest.mark.parametrize('kind', ['future','missing_beta','missing_symbol','stale_proxy','no_proxy','short_universe'])
def test_no_imputation_or_qualification_with_missing_future_or_stale_evidence(kind):
    frame,prices,returns=evidence()
    if kind=='future':frame['observed_at']=NOW+pd.Timedelta(seconds=1)
    elif kind=='missing_beta':frame.loc[0,'beta_126']=np.nan
    elif kind=='missing_symbol':frame=frame.iloc[1:]
    elif kind=='stale_proxy':prices=prices.iloc[:-1]
    elif kind=='no_proxy':prices=prices.drop(columns='IWM')
    else:frame=frame.iloc[:10]
    with pytest.raises(ValueError):qualify_factor_context(frame,prices,returns,['S0'],DAY,NOW,RiskConfig())


def context(beta=.4):
    return dict(qualified=True,exposures={'A':FactorExposures('A',DAY,beta,1.,1.)},
        covariance=FactorCovariance(np.eye(3),['market','size','momentum'],{'A':.05},DAY))


def test_existing_beta_concentration_and_diversification_limits_are_enforced():
    cfg=RiskConfig(enable_factor_model=True)
    assert factor_violations(context(),{'A':.1},cfg,candidate='A')==[]
    high_beta=factor_violations(context(2.),{'A':.1},cfg,candidate='A')
    assert any('beta' in reason for reason in high_beta)
    concentrated=context();concentrated['exposures']['A']=FactorExposures('A',DAY,.1,10.,.1)
    reasons=factor_violations(concentrated,{'A':.1},cfg,candidate='A')
    assert any('concentration' in reason for reason in reasons)
    assert any('diversification' in reason for reason in reasons)


def test_missing_held_exposure_and_factor_correlation_are_not_skipped():
    ctx=context();cfg=RiskConfig(enable_factor_model=True,use_factor_correlation_filter=True)
    with pytest.raises(ValueError):factor_violations(ctx,{'A':.1,'B':.1},cfg,candidate='A')
    ctx['exposures']['B']=FactorExposures('B',DAY,.4,1.,1.)
    ctx['covariance'].specific_variances['B']=.05
    assert any('factor_correlation' in r for r in factor_violations(ctx,{'A':.1,'B':.1},cfg,candidate='A',other_sides={'B':'long'}))
