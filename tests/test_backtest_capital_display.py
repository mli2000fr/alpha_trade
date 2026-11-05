"""Observed gross capital, including cash periods and changing account equity."""
import pandas as pd
import pytest

from ihm.pages.backtesting import _average_committed_capital


def test_existing_winner_root_values_take_precedence_over_old_zero_summary():
    report=dict(average_gross_capital=778.7599588169072,average_gross_equity_ratio=.2020730699358629,
        summary=dict(initial_equity=4000.,gross_exposure_avg_pct=0.),
        run_metadata=dict(engine='winner_campaign_replay'))
    amount,pct,basis=_average_committed_capital(report)
    assert amount==pytest.approx(778.76,abs=.005) and pct==pytest.approx(20.20730699358629)
    assert basis=='REGULAR_5M_MARKS'


def test_daily_fallback_basis_is_never_relabelled_as_observed_intraday():
    report=dict(average_gross_capital=1000.,average_gross_equity_ratio=.25,
        summary=dict(capital_observation_basis='MIXED_5M_AND_DAILY_KNOWN_MARKS'),
        run_metadata=dict(engine='winner_campaign_replay'))
    assert _average_committed_capital(report)==(1000.,25.,'MIXED_5M_AND_DAILY_KNOWN_MARKS')


def test_summary_values_and_cash_only_are_displayable_without_reconstruction():
    assert _average_committed_capital(dict(summary=dict(average_gross_capital=2000.,
        gross_exposure_avg_pct=30.,capital_observation_basis='DAILY_BEFORE_ENTRIES')))==(2000.,30.,'DAILY_BEFORE_ENTRIES')
    assert _average_committed_capital(dict(average_gross_capital=0.,average_gross_equity_ratio=0.))[:2]==(0.,0.)
    assert _average_committed_capital(dict(summary=dict(gross_exposure_avg_pct=0.)))==(None,None,None)
    assert _average_committed_capital(dict(summary=dict(initial_equity=4000.,gross_exposure_avg_pct=25.)))[:2]==(None,25.)
    assert _average_committed_capital(dict(average_gross_capital=1000.,summary=dict(gross_exposure_avg_pct=0.)))[:2]==(1000.,None)
    assert _average_committed_capital(dict(average_gross_capital=6000.,average_gross_equity_ratio=1.5))[:2]==(6000.,150.)


@pytest.mark.parametrize('value',[None,'bad',float('nan'),float('inf'),-1.,True])
def test_invalid_amount_is_missing_not_falsely_zero(value):
    assert _average_committed_capital(dict(average_gross_capital=value))[0] is None


def test_daily_report_averages_observed_notionals_including_zero_and_not_initial_equity():
    from backtesting.report import generate_report
    from backtesting.simulator import BacktestResult
    dates=pd.date_range('2025-01-02',periods=3)
    snapshots=pd.DataFrame(dict(event_type=['daily_leverage_snapshot']*3,
        current_gross_notional=[0.,2000.,4000.],gross_exposure_before_pct=[0.,.4,.5],
        net_exposure_before_pct=[0.,.4,-.5]))
    snapshots=pd.concat([snapshots,pd.DataFrame([dict(event_type='other',current_gross_notional=1e9)])],ignore_index=True)
    result=BacktestResult(equity_curve=pd.Series([4000.,5000.,8000.],index=dates),
        closed_trades_df=pd.DataFrame(),trade_events_df=snapshots)
    summary=generate_report(result,4000.).to_serializable_dict()
    assert summary['average_gross_capital']==2000.
    assert summary['gross_exposure_avg_pct']==pytest.approx(30.)
    assert summary['capital_observation_basis']=='DAILY_BEFORE_ENTRIES'
    assert summary['gross_exposure_avg_pct']!=100*summary['average_gross_capital']/4000.
    result.trade_events_df=pd.DataFrame()
    assert generate_report(result,4000.).to_serializable_dict()['average_gross_capital'] is None


def test_capital_metrics_are_visible_in_details_for_existing_winner_report():
    from streamlit.testing.v1 import AppTest
    def app():
        from ihm.pages.backtesting import _render_average_committed_capital
        _render_average_committed_capital(dict(average_gross_capital=778.7599588169072,
            average_gross_equity_ratio=.2020730699358629,run_metadata=dict(engine='winner_campaign_replay')))
    at=AppTest.from_function(app).run(timeout=30)
    assert not at.exception
    metrics={m.label:m.value for m in at.metric}
    assert metrics['Capital engagé moyen']=='$778.76'
    assert metrics['Engagement moyen / capital du compte']=='20.21 %'
    assert any('sans position' in c.value for c in at.caption)
