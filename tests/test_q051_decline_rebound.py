import numpy as np
import pandas as pd
import pytest

from scripts.research.us_q051_decline_rebound_20261126 import pattern_features,screen,configuration


def prices(last=(86.,87.),bottom=85.):
    return pd.DataFrame({'A':[*np.linspace(100.,bottom,21),*last]},index=pd.bdate_range('2025-01-01',periods=23))


def test_prior_decline_and_two_daily_rises_are_distinct_from_drop_alone():
    two=pattern_features(prices())
    assert two['decline_qualified'].A.iloc[-1]
    assert two['rise_j_minus_1'].A.iloc[-1] and two['rise_j'].A.iloc[-1]
    one=pattern_features(prices(last=(84.,85.)))
    assert one['decline_qualified'].A.iloc[-1]
    assert not one['rise_j_minus_1'].A.iloc[-1] and one['rise_j'].A.iloc[-1]
    falling=pattern_features(prices(last=(84.,83.)))
    assert falling['decline_qualified'].A.iloc[-1] and not falling['rise_j'].A.iloc[-1]


def test_exact_ten_percent_threshold_inclusive_and_small_decline_rejected():
    assert pattern_features(prices(last=(91.,92.),bottom=90.))['decline_qualified'].A.iloc[-1]
    assert not pattern_features(prices(last=(92.,93.),bottom=91.))['decline_qualified'].A.iloc[-1]


def test_unknown_or_nonpositive_history_never_forward_filled():
    for value in (np.nan,0.,-1.):
        c=prices();c.iloc[10,0]=value
        f=pattern_features(c)
        assert not f['history_qualified'].A.iloc[-1] and not f['decline_qualified'].A.iloc[-1]
    assert not pattern_features(prices().iloc[:22])['history_qualified'].A.iloc[-1]


def test_future_changes_cannot_change_an_existing_signal():
    close=prices()
    a=pattern_features(close)
    extended=pd.concat([close,pd.DataFrame({'A':[1.,100000.]},index=pd.bdate_range(close.index[-1]+pd.Timedelta(days=1),periods=2))])
    b=pattern_features(extended)
    for name in a:
        pd.testing.assert_frame_equal(a[name],b[name].iloc[:len(close)])


def test_filter_keeps_original_order_and_does_not_refill():
    close=prices();close['B']=np.linspace(100.,130.,len(close))
    signals=pd.DataFrame(dict(trade_date=[close.index[-1]]*2,symbol=['B','A'],rank=[1,2],long_probability=[.9,.8]))
    a=screen(signals,close)
    assert a.loc[a.REBOUND_2,'symbol'].tolist()==['A']
    assert a.loc[a.REBOUND_2,'rank'].tolist()==[2]
    assert a.REFERENCE.all()


def test_price_level_rescaling_does_not_change_filter():
    a=pattern_features(prices());b=pattern_features(prices()*5)
    for name in ('history_qualified','rise_j','rise_j_minus_1','decline_qualified'):
        pd.testing.assert_frame_equal(a[name],b[name])


def test_duplicate_dates_rejected():
    c=prices();c.index=[*c.index[:-1],c.index[-2]]
    with pytest.raises(ValueError,match='dupliqués'):pattern_features(c)


def test_archived_configuration_remains_identical_for_simulation():
    cfg=configuration()
    assert cfg.initial_equity==4000 and cfg.risk_config.max_gross_exposure==1
    assert not cfg.winner_drawdown_controller_enabled and cfg.winner_daily_entry_enabled
    assert cfg.exec_config.winner_pyramiding.stop_loss_pct==.05
    assert cfg.exec_config.winner_pyramiding.horizon_sessions==10
