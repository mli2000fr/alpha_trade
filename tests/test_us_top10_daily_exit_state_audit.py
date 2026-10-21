from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from scripts.research import us_top10_daily_exit_state_audit as s
from tests.test_us_top10_three_session_confirmation import fixture


def case(f=None):
    f=fixture() if f is None else f
    result=s.parent.trades_for(f,[20],'LONG')
    row=SimpleNamespace(date=f.index[20],symbol='A',year=2024,entry_date=f.index[23],last_path_date=f.index[32],
        **{k:v[0] for k,v in result.items()})
    row.net_outcome=s.net_return(row.exit_price,row.entry_price)
    features=s.price_features(f,pd.Series(100.,index=f.index))
    return row,f,features


def test_native_exit_session_has_no_state_and_no_forced_expiry_decision():
    row,f,features=case(); states=s.trade_states(row,f,features,f.index)
    assert len(states)==9 and max(x['holding_age'] for x in states)==9
    assert all(x['state_date']<x['execution_date']<=x['last_path_date']<x['label_available_date'] for x in states)
    f=fixture(); f.loc[f.index[23],'high']=111
    row,f,features=case(f); assert row.exit_session==1
    assert s.trade_states(row,f,features,f.index)==[]


def test_stop_already_hit_on_day_cannot_be_overruled_at_close():
    f=fixture(); f.loc[f.index[25],'low']=94
    row,f,features=case(f); states=s.trade_states(row,f,features,f.index)
    assert row.exit_session==3 and len(states)==2
    assert all(x['state_date']<f.index[25] for x in states)


@pytest.mark.parametrize('op,high,low,expected_priority,exit_price',[
    (80,81,79,'SL_GAP',80),(120,121,119,'TP_AT_OPEN',110)])
def test_next_open_protection_priority_retained_as_zero_value(op,high,low,expected_priority,exit_price):
    f=fixture(); f.iloc[24,f.columns.get_indexer(['open','high','low','close'])]=[op,high,low,op]
    row,f,features=case(f); states=s.trade_states(row,f,features,f.index)
    assert len(states)==1 and states[0]['next_open_priority']==expected_priority
    assert states[0]['immediate_exit_net']==pytest.approx(s.net_return(exit_price,100))
    assert states[0]['exit_advantage_remaining']==pytest.approx(0.,abs=1e-12)
    assert states[0]['exit_advantage_next3']==pytest.approx(0.,abs=1e-12)


def test_future_peak_not_a_feature_at_entry_close():
    f=fixture(); f.loc[f.index[27],'high']=109
    row,f,features=case(f); state=s.trade_states(row,f,features,f.index)[0]
    assert state['mfe_so_far']==pytest.approx(.01)
    assert state['giveback_atr']==pytest.approx(.5)


def test_short_target_respects_next_three_sessions_not_final_close():
    f=fixture(); f.loc[f.index[26],['high','close']]=[103,102]
    row,f,features=case(f); state=s.trade_states(row,f,features,f.index)[0]
    assert state['exit_advantage_remaining']==pytest.approx(0.,abs=1e-12)
    assert state['exit_advantage_next3']<0


def test_price_features_prefix_causal_including_spy_and_volume():
    f=fixture(); spy=pd.Series(np.linspace(99,102,len(f)),index=f.index)
    prefix=s.price_features(f.iloc[:25],spy.iloc[:25]); full=s.price_features(f,spy)
    pd.testing.assert_frame_equal(prefix,full.iloc[:25])
    changed=f.copy(); changed.loc[changed.index[25]:,['open','high','low','close','volume']]*=3
    changed_spy=spy.copy(); changed_spy.iloc[25:]*=5
    altered=s.price_features(changed,changed_spy)
    pd.testing.assert_frame_equal(full.iloc[:25],altered.iloc[:25])


def test_current_return_relative_not_unadjusted_or_future_spy():
    f=fixture(); f.loc[f.index[23],['high','close']]=[103,102]
    spy=pd.Series(100.,index=f.index); spy.iloc[23]=101
    features=s.price_features(f,spy)
    assert features.relative_spy_1d.iloc[23]==pytest.approx(.01)


def test_feature_history_not_truncated_to_position_entry_and_missing_not_filled():
    row,f,features=case(); assert np.isfinite(features.return_5d.iloc[23])
    f.loc[f.index[20],'is_filled']=1
    features=s.price_features(f,pd.Series(100.,index=f.index))
    assert np.isnan(features.atr.iloc[23]) and np.isnan(features.return_1d.iloc[23])


def test_all_states_of_unmatured_2024_trade_excluded_from_discovery():
    f=pd.DataFrame(dict(signal_year=[2024,2024,2025],state_date=pd.to_datetime(['2024-12-20','2024-12-20','2025-01-03']),
        label_available_date=pd.to_datetime(['2024-12-31','2025-01-02','2025-01-20'])))
    assert s.discovery_states(f).index.tolist()==[0]


def test_targets_not_in_feature_contract():
    assert set(s.FEATURES).isdisjoint(s.LABELS+['baseline_stopped','baseline_winner','next_open_priority','label_available_date'])


def test_weighted_quantiles_do_not_count_many_states_as_many_trades():
    values=np.array([0.]+[100.]*100); weights=np.array([1.]+[.01]*100)
    a=s.weighted_quantiles(values,weights)
    assert a[0]<50 and a[1]>50
