from copy import deepcopy
import numpy as np
import pandas as pd
import pytest

from scripts.research.us_q051_portfolio_risk_policy_20261109 import portfolio_limit,PortfolioRiskPolicy


def history():
    dates=pd.bdate_range('2026-01-01',periods=80)
    return pd.DataFrame({'A':np.tile([.03,-.03],40),'B':np.tile([.03,-.03],40)},index=dates)


def inputs():
    r=history()
    return dict(returns=r,prior_day=r.index[65],positions=[],pending=[],symbol='A',price=100.,
        equity=4000.,proposed=40,target=.20)


def test_budget_limits_quantity_and_ignores_all_future_returns():
    kwargs=inputs();first=portfolio_limit(**kwargs)
    assert 0<first['quantity']<40
    assert first['approved_vol']<=.20
    kwargs['returns'].loc[kwargs['returns'].index>kwargs['prior_day']]=10000.
    assert portfolio_limit(**kwargs)==first
    assert first['history_end']==str(kwargs['prior_day'].date())


def test_covariance_and_pending_notional_count_and_existing_risk_blocks_only_entry():
    kwargs=inputs();kwargs['proposed']=20
    kwargs['positions']=[dict(symbol='B',quantity=10.,mark=100.,side='long')]
    positive=portfolio_limit(**kwargs)
    kwargs['returns']['B']=-kwargs['returns']['A']
    diversified=portfolio_limit(**kwargs)
    assert positive['quantity']<diversified['quantity']
    kwargs=inputs();kwargs['pending']=[dict(symbol='B',notional=3000.,side='buy')]
    pending=deepcopy(kwargs['pending'])
    assert portfolio_limit(**kwargs)['quantity']==0
    assert kwargs['pending']==pending


def test_incomplete_prior_history_is_rejected_instead_of_filled():
    kwargs=inputs();kwargs['returns'].loc[kwargs['prior_day'],'A']=np.nan
    with pytest.raises(ValueError,match='complete prior'):
        portfolio_limit(**kwargs)


@pytest.mark.usefixtures('isolated_winner_config')
def test_inactive_hook_preserves_native_fills_and_active_hook_reapproves_lower_quantity(monkeypatch):
    from tests import test_winner_daily_entry as native_test
    original=native_test.approve_daily_open
    baseline=native_test.port()
    dates=pd.bdate_range('2026-01-01','2026-10-16')
    series=100.*pd.Series(np.resize([1.25,.8],len(dates)),index=dates).cumprod()
    close=pd.DataFrame({'AAA':series})
    inactive=PortfolioRiskPolicy(close,target=None)
    monkeypatch.setattr(native_test,'approve_daily_open',inactive.wrap(original))
    control=native_test.port()
    assert baseline[0].cash==control[0].cash
    assert baseline[0].gross()==control[0].gross()
    assert not inactive.receipts
    active=PortfolioRiskPolicy(close,target=.2)
    monkeypatch.setattr(native_test,'approve_daily_open',active.wrap(original))
    reduced=native_test.port()
    assert active.receipts and active.receipts[0]['final_quantity']<active.receipts[0]['native_quantity']
    assert reduced[0].gross()<baseline[0].gross()
    assert all(r['producer']=='native_daily_open_replay_risk' for r in reduced[2])


def test_variants_keep_selection_and_exit_policy_unchanged():
    from dataclasses import asdict
    import json
    from tests.test_winner_continuous_q051_q088 import reference
    from scripts.research.us_winner_q051_risk_budget_20261109 import matched_configuration,shared,ALL_VARIANTS
    ref=reference();ref['risk']['policy']='b4'
    plan={'reference':ref,'cases':{'Q051_050':shared.CASES['Q051_050']}}
    baseline=shared.configuration(ref,shared.CASES['Q051_050'])
    saved={'portfolio':json.loads(json.dumps(asdict(baseline),default=str))}
    for v in ALL_VARIANTS:
        case,cfg=matched_configuration(plan,saved,v)
        assert case['pool']==.1 and case['long_top_n']==5 and case['score']==case['auc']==.5
        assert not cfg.winner_drawdown_controller_enabled and not cfg.risk_config.force_close_on_breaker
        assert asdict(cfg.exec_config.winner_pyramiding)==asdict(baseline.exec_config.winner_pyramiding)
        assert cfg.winner_daily_entry_enabled and cfg.exec_config.leverage.max_leverage==2.
        assert cfg.risk_config.max_gross_exposure==(.75 if v=='STATIC75' else 1.)
