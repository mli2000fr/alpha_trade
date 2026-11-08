from datetime import date
import pytest

from scripts.research.us_winner_continuous_annual_models_20261108 import selection_size,annual_signal_days,same_settings


def test_pool_keeps_source_or_uniform_percent_explicitly():
    assert selection_size('recorded',1790,20)==20
    assert selection_size('uniform20pct',1790,20)==358
    assert selection_size('uniform20pct',32,20)==7
    with pytest.raises(ValueError):selection_size('unknown',1790,20)


def test_model_mapping_uses_next_entry_year_at_year_boundary():
    from common.market_calendar import get_market_calendar
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    actual21,signals21=annual_signal_days(cal,2021)
    actual22,signals22=annual_signal_days(cal,2022)
    assert signals22[0]==date(2021,12,31) and actual22[0]==date(2022,1,3)
    assert signals21[-1]==date(2021,12,30)
    assert not set(signals21)&set(signals22)
    assert cal.next_session(signals22[0])==actual22[0]


def test_portfolio_settings_differences_are_not_silently_merged():
    keys=['account_type','max_leverage','margin_interest_annual','cost_per_leg_bps','max_positions',
        'daily_entry','drawdown_controller','factor_model','ignore_missing_intraday','options_filter']
    p={k:{} for k in ('winner_policy','risk','leverage','drawdown_controller','initial_entry')}
    p['arguments']=dict.fromkeys(keys,1)
    assert same_settings({2021:p,2022:p}) is p
    altered={**p,'risk':{'risk_per_trade_pct':.03}}
    with pytest.raises(ValueError,match='risk'):same_settings({2021:p,2022:altered})
