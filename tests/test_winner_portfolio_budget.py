from dataclasses import replace
import numpy as np
import pandas as pd
import pytest

from backtesting.winner_portfolio_budget import portfolio_limit,replay_protections


def test_reusable_budget_matches_the_original_frozen_experiment():
    from tests.test_q051_portfolio_risk_policy import inputs
    from scripts.research.us_q051_portfolio_risk_policy_20261109 import portfolio_limit as original
    for target in [.1,.2,.8]:
        kw=inputs();kw['target']=target
        assert portfolio_limit(**kw)==original(**kw)


@pytest.mark.usefixtures('isolated_winner_config')
def test_native_engine_dispatch_uses_budget_and_keeps_inactive_results_identical():
    from tests.test_winner_daily_entry import daily_fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,_=daily_fixture(confirmation_bars=0)
    baseline=BacktestEngine(cfg).run(**args)
    inactive=BacktestEngine(cfg).run(**args,winner_entry_risk_policy=None)
    pd.testing.assert_frame_equal(baseline.trade_events_df,inactive.trade_events_df)
    pd.testing.assert_series_equal(baseline.equity_curve,inactive.equity_curve)
    dates=pd.bdate_range('2026-01-01','2026-10-16')
    close=pd.DataFrame({'AAA':100.*np.cumprod(np.resize([1.25,.8],len(dates)))},index=dates)
    policy,_=replay_protections(close,daily_entry=True,target=.01)
    result=BacktestEngine(cfg).run(**args,winner_entry_risk_policy=policy)
    assert policy.receipts and policy.receipts[0]['status']=='QUALIFIED'
    assert policy.receipts[0]['final_quantity']<policy.receipts[0]['native_quantity']
    assert len(result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')])==0
    cfg.winner_daily_entry_enabled=False
    with pytest.raises(ValueError,match='daily entry'):
        BacktestEngine(cfg).run(**args,winner_entry_risk_policy=policy)


def test_regime_uses_only_previous_close_and_composes_with_options_filter():
    dates=pd.bdate_range('2025-01-01',periods=260)
    frame=pd.DataFrame({'SPY':100.},index=dates)
    rows=pd.DataFrame({'symbol':['A','B']})
    calls=[]
    def upstream(day,rows,cutoff):
        calls.append(day);return dict(selected=['B'],incomplete=False)
    _,gate=replay_protections(frame,daily_entry=True,regime=True,upstream=upstream)
    cutoff=dates[250].tz_localize('UTC')+pd.Timedelta(days=1,hours=13)
    assert gate(dates[250],rows,cutoff)['selected']==['B']
    frame.loc[dates[251]:,'SPY']=1e9
    assert gate(dates[250],rows,cutoff)['selected']==['B']
    gate.close.loc[dates[250]]=50.
    assert gate(dates[250],rows,cutoff)['selected']==[]
    assert len(calls)==2


@pytest.mark.parametrize('kwargs',[dict(target=float('nan')),dict(target=0),dict(lookback=1),
    dict(regime=True,sma_window=0),dict(regime=True,bear_threshold=-1)])
def test_invalid_settings_fail_closed(kwargs):
    with pytest.raises(ValueError):replay_protections(pd.DataFrame(),daily_entry=True,**kwargs)


def test_archived_popup_reports_comparable_daily_drawdowns():
    from ihm.components.winner_profile_comparison import reference_comparison
    table,models=reference_comparison()
    assert len(table)==9 and len(models)==6
    assert table.iloc[1]['Rendement (%)']==125.98
    assert table.iloc[2]['Rendement (%)']==150.90
    assert table.iloc[3]['Rendement (%)']==280.94
    assert table.iloc[4]['Rendement (%)']==129.06
    assert table.iloc[5]['Rendement (%)']==297.35
    assert table.iloc[6]['Rendement (%)']==303.52
    assert table.iloc[6]['DD intraday (%)']==-34.98
    assert table.iloc[6]['Trades gagnants (%)']==38.13
    assert table.iloc[6]['Trades clôturés']==1356
    assert table.iloc[7]['Rendement (%)']==364.84
    assert table.iloc[7]['DD intraday (%)']==-46.26
    assert table.iloc[7]['Capital final ($)']==18593.49
    assert table.iloc[8]['DD sur clôtures (%)']==-25.36
    assert pd.isna(table.iloc[8]['DD intraday (%)'])
    from ihm.components.winner_profile_comparison import comparison_data,comparison_figure,CURVE_LABELS
    _,curves,_=comparison_data()
    assert list(curves)==list(CURVE_LABELS) and not curves.isna().any().any()
    assert curves.iloc[-1,2]==pytest.approx(10035.917949897084)
    assert curves.iloc[-1,3]==pytest.approx(15237.79291190506)
    assert curves.iloc[-1,6]==pytest.approx(16140.820229817295)
    assert curves.iloc[-1,7]==pytest.approx(18593.485021063672)
    figure=comparison_figure(curves)
    assert [line.name for line in figure.data]==list(CURVE_LABELS)
