import pandas as pd
import pytest

from scripts.research.us_oracle_barrier_trailing_audit import audit_trailing_paths


def fixture():
    days=pd.bdate_range('2026-01-02',periods=3)
    prices=pd.DataFrame(dict(date=days,symbol=['A']*3,open=[100,110,110],
                            high=[115,125,115],low=[99,100,105]))
    trade=pd.DataFrame([dict(symbol='A',entry_date=days[0],exit_date=days[1],entry_price=100,
        replay_initial_stop_price=90,replay_trailing_stop_pct=.10,
        replay_trailing_activation_price=100,exit_price=103.5,exit_reason='trailing_stop')])
    return trade,prices


def test_prior_peak_not_current_high():
    trades,prices=fixture()
    result=audit_trailing_paths(trades,prices)[0]
    assert result['working_stop']==pytest.approx(103.5)
    assert result['prior_peak']==115
    trades.loc[0,'exit_price']=112.5
    with pytest.raises(ValueError,match='Wrong intraday'):
        audit_trailing_paths(trades,prices)


def test_no_same_day_activation():
    trades,prices=fixture()
    trades.loc[0,'replay_trailing_activation_price']=120
    with pytest.raises(ValueError,match='before qualified activation'):
        audit_trailing_paths(trades,prices)


def test_gap_uses_actual_open_even_below_initial_sl():
    trades,prices=fixture()
    prices.loc[1,'open']=80
    trades.loc[0,['exit_reason','exit_price']]=['trailing_stop_gap_open',80]
    assert audit_trailing_paths(trades,prices)[0]['exit_price']==80
    trades.loc[0,'exit_price']=90
    with pytest.raises(ValueError,match='Wrong gap'):
        audit_trailing_paths(trades,prices)


def test_unqualified_path_rejected():
    trades,prices=fixture()
    with pytest.raises(ValueError,match='Missing'):
        audit_trailing_paths(trades,prices.iloc[1:])


def test_corporate_action_rebases_own_lot_not_unrelated_target_history():
    trades,prices=fixture()
    trades.loc[0,'symbol']='B'
    prices.loc[1:,'symbol']='B'
    prices.loc[0,['open','high','low']]=[200,230,198]
    action=dict(status='CONVERTED',source='A',target='B',day=str(prices.date.iloc[1].date()),
                ratio='2',preserved_entry_date=str(prices.date.iloc[0].date()))
    assert audit_trailing_paths(trades,prices,[action])[0]['prior_peak']==115


def test_indexed_price_groups_preserve_exact_audit_results():
    trades,prices=fixture()
    groups={s:g for s,g in prices.groupby('symbol',sort=False)}
    assert audit_trailing_paths(trades,groups)==audit_trailing_paths(trades,prices)
