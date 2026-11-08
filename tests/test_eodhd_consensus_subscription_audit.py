import pandas as pd
import pytest

from scripts.research.us_eodhd_consensus_subscription_audit_20261108 import outcome,measure,calendar


def test_peak_long_is_separate_from_losing_close_and_barrier_result():
    path=pd.DataFrame(dict(open=[100.,120.],high=[125.,122.],low=[99.,98.],close=[120.,99.]))
    result=outcome(path)
    assert result['max_abs_long']
    assert result['close_return']==pytest.approx(-.01)
    assert result['barrier_status']=='TP'
    assert result['barrier_net_return']==pytest.approx(.0984)


def test_both_barriers_daily_candle_is_adverse_first_and_gap_kept():
    from decimal import Decimal
    decimal_path=pd.DataFrame(dict(open=[Decimal('100')],high=[Decimal('115')],low=[Decimal('99')],close=[Decimal('110')]))
    assert outcome(decimal_path)['barrier_status']=='TP'
    path=pd.DataFrame(dict(open=[100.],high=[115.],low=[85.],close=[110.]))
    assert outcome(path)['barrier_status']=='SL'
    path=pd.DataFrame(dict(open=[100.,85.],high=[101.,90.],low=[99.,80.],close=[100.,88.]))
    assert outcome(path)['barrier_return']==pytest.approx(-.15)


def test_horizons_use_official_sessions_and_never_treat_missing_prices_as_losers():
    sched=calendar()
    idx=sched.index[sched.day.eq(pd.Timestamp('2026-10-12'))][0]
    features=pd.DataFrame([dict(symbol='A',entry_idx=idx,entry_day=sched.iloc[idx].day)])
    prices=pd.DataFrame(dict(symbol=['A']*5,date=sched.day.iloc[idx:idx+5].tolist(),
        open=[100.]*5,high=[101.]*5,low=[99.]*5,close=[100.]*5,is_filled=[0]*5,
        data_adjustment=['split']*5,instrument_id=[1]*5))
    result=measure(features,prices,sched,pd.Timestamp('2026-11-07',tz='UTC')).set_index('horizon')
    assert result.loc[5,'status']=='MATURE'
    assert result.loc[10,'status']=='MISSING_OR_UNQUALIFIED_PATH'
    assert result.loc[20,'status']=='MISSING_OR_UNQUALIFIED_PATH'
    assert pd.isna(result.loc[20,'barrier_return'])
    prices.loc[0,'high']=None
    invalid=measure(features,prices,sched,pd.Timestamp('2026-11-07',tz='UTC')).set_index('horizon')
    assert invalid.loc[5,'status']=='MISSING_OR_UNQUALIFIED_PATH'
