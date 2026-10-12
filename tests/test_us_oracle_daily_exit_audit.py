import numpy as np
import pytest
from scripts.research.us_oracle_daily_exit_audit import simulate,opportunity


def prices():
    return np.full((20,4),100.)


def test_time_exit_next_open_not_observed_close():
    p=prices()
    p[2]=[100,115,100,110]
    p[3]=[105,105,100,100]
    r=simulate(p,'EXIT_AFTER3')
    assert r['exit_session']==4 and r['decision_session']==3
    assert np.isclose(r['gross_return'],.05)


def test_intraday_stop_before_first_observation_unavoidable():
    p=prices()
    p[0,2]=90
    baseline=simulate(p,'HOLD20_SL7')
    assert baseline['exit_session']==1
    assert not opportunity(p,baseline)['daily_exit_feasible_before_stop']
    assert opportunity(p,baseline)['ideal_delta']==0


def test_open_gap_priority_over_scheduled_exit():
    p=prices()
    p[3]=[85,100,85,100]
    r=simulate(p,'EXIT_AFTER3')
    assert r['exit_reason']=='STOP_GAP'
    assert np.isclose(r['gross_return'],-.15)


def test_ideal_bound_can_exit_before_next_intraday_stop():
    p=prices()
    p[1]=[102,102,90,100]
    baseline=simulate(p,'HOLD20_SL7')
    bound=opportunity(p,baseline)
    assert bound['daily_exit_feasible_before_stop']
    assert np.isclose(bound['ideal_daily_open_return'],.02)
    assert np.isclose(bound['ideal_delta'],.09)


def test_loss_rule_waits_for_close3_and_still_keeps_stop():
    p=prices()
    p[2]=[100,100,96,98]
    p[3]=[99,100,97,99]
    assert simulate(p,'LOSS_AFTER3')['exit_session']==4
    p[2,2]=90
    assert simulate(p,'LOSS_AFTER3')['exit_reason']=='STOP_INTRADAY'


def test_trailing_can_not_loosen_initial_stop():
    p=prices()
    p[0,1]=140
    p[1]=[130,130,125,125]
    r=simulate(p,'TRAILING_CLOSE20')
    assert r['exit_session']==2
    assert np.isclose(r['gross_return'],.3)


def test_invalid_shapes_rejected():
    with pytest.raises(ValueError): simulate(prices()[:19],'HOLD20_SL7')
    with pytest.raises(ValueError): simulate(prices(),'UNKNOWN')
