import numpy as np
import pandas as pd

from scripts.research.us_oracle_path_excursions import evaluate_symbol,summarize


def fixture():
    sessions=pd.bdate_range('2025-01-02',periods=24)
    selected=pd.DataFrame([dict(date=sessions[0],symbol='TEST',future_return=0.,
        target_quality_valid=1,oracle_available_date=sessions[21])])
    bars=pd.DataFrame(dict(date=sessions,symbol='TEST',open=100.,high=100.,low=100.,
        close=100.,adj_close=100.,volume=1000,is_filled=0,instrument_id=1,
        data_source='fixture',data_adjustment='split'))
    return sessions,selected,bars


def test_intraday_hidden_peak_and_no_close_hidden():
    sessions,selected,bars=fixture()
    bars.loc[5,'high']=130.
    result=evaluate_symbol(selected,bars,sessions,{}) .iloc[0]
    assert result.path_qualified
    assert result.hidden_ge20
    assert not result.close_hidden_ge20
    assert np.isclose(result.path_amplitude,.3)
    assert result.first_touch_20_session==5


def test_close_roundtrip_identified():
    sessions,selected,bars=fixture()
    bars.loc[5,['open','high','low','close','adj_close']]=130.
    result=evaluate_symbol(selected,bars,sessions,{}).iloc[0]
    assert result.close_hidden_ge20
    assert result.large_close_jump_review==False


def test_split_factor_does_not_create_false_excursion():
    sessions,selected,bars=fixture()
    bars.loc[5:,['open','high','low','close']]=50.
    result=evaluate_symbol(selected,bars,sessions,{}).iloc[0]
    assert result.path_qualified
    assert result.path_amplitude==0.


def test_missing_session_not_skipped_or_forward_filled():
    sessions,selected,bars=fixture()
    result=evaluate_symbol(selected,bars.drop(index=5),sessions,{}).iloc[0]
    assert not result.path_qualified
    assert result.exit_date==sessions[20]
    assert 'MISSING' in result.path_flags


def test_labels_and_source_changes_reserved():
    sessions,selected,bars=fixture()
    bars.loc[5,'data_source']='other'
    selected['future_return']=.2
    result=evaluate_symbol(selected,bars,sessions,{}).iloc[0]
    assert not result.path_qualified
    assert 'SOURCE_CHANGE' in result.path_flags
    assert 'ARCHIVED_RETURN' in result.path_flags


def test_both_directions_same_day_ambiguous():
    sessions,selected,bars=fixture()
    bars.loc[5,'high'],bars.loc[5,'low']=130.,70.
    result=evaluate_symbol(selected,bars,sessions,{}).iloc[0]
    assert result.both_sides_ge20
    assert result.first_touch_20_ambiguous


def test_day_zero_and_after_horizon_excluded():
    sessions,selected,bars=fixture()
    bars.loc[0,'high'],bars.loc[21,'high']=180.,180.
    result=evaluate_symbol(selected,bars,sessions,{}).iloc[0]
    assert result.path_amplitude==0.


def test_exact_twenty_percent_touch_inclusive():
    sessions,selected,bars=fixture()
    bars.loc[5,'high']=120.
    result=evaluate_symbol(selected,bars,sessions,{}).iloc[0]
    assert result.hidden_ge20
    assert result.first_touch_20_session==5


def test_known_identity_break_reserved_even_if_prices_continuous():
    from modelFactory.oracle.security_continuity import SecurityDiscontinuity
    sessions,selected,bars=fixture()
    registry={'TEST':(SecurityDiscontinuity('TEST',sessions[5],sessions[6],'fixture'),)}
    result=evaluate_symbol(selected,bars,sessions,registry).iloc[0]
    assert not result.path_qualified
    assert 'KNOWN_IDENTITY_BREAK' in result.path_flags


def test_object_boolean_summary_uses_arithmetic_not_logical_reduction():
    sessions,selected,bars=fixture()
    selected['source']='fixture'
    selected['oracle_pool_rank'],selected['atr_pool_rank']=1,1
    bars.loc[5,'high']=130.
    row=evaluate_symbol(selected,bars,sessions,{}).iloc[0].to_dict()
    rows=pd.DataFrame([row,row,row])
    rows['terminal_ge20']=pd.Series([np.bool_(True),True,False],dtype=object)
    rows['hidden_ge20']=pd.Series([False,np.bool_(True),False],dtype=object)
    result=summarize(rows)[0]
    assert np.isclose(result['terminal_ge20'],2/3)
    assert np.isclose(result['hidden_ge20'],1/3)
    assert np.isclose(result['hidden_share_of_reached_20'],1/3)
