import pandas as pd
import pytest

from scripts.research.us_options_winrate_audit_20261109 import trade_label,describe


def path():
    days=pd.bdate_range('2026-09-01',periods=4)
    f=pd.DataFrame(dict(open=[100.,102.,104.,106.],high=[103.,105.,107.,108.],low=[99.,101.,103.,105.],
        close=[102.,104.,106.,107.],is_filled=0,data_adjustment='split',instrument_id=1),index=days)
    return f,days


def test_no_tp_trailing_and_horizon_open_after_three_sessions():
    f,days=path();r=trade_label(f,days[:3],days[3])
    assert r['winning'] and r['exit_price']==106. and r['exit_reason']=='HORIZON_OPEN'
    assert r['net_return_pct']==pytest.approx(100*(106*(1-.0008)/(100*(1+.0008))-1))
    # Tomorrow's close is not the horizon opening exit.
    f.loc[days[3],'close']=105.5
    assert trade_label(f,days[:3],days[3])==r


@pytest.mark.parametrize('opening,low,fill,reason',[(102.,94.,95.,'STOP'),(90.,89.,90.,'STOP_GAP')])
def test_stop_and_gap_are_filled_adversely_and_cannot_be_saved_by_later_high(opening,low,fill,reason):
    f,days=path();f.loc[days[1],['open','low','high']]=[opening,low,200.]
    r=trade_label(f,days[:3],days[3])
    assert not r['winning'] and r['exit_price']==fill and r['exit_reason']==reason
    assert r['nostop_winning']


def test_missing_prices_are_not_filled_and_identity_change_is_rejected():
    f,days=path();f.loc[days[1],'close']=None
    assert trade_label(f,days[:3],days[3])['trade_status']=='INVALID_OR_MISSING_PRICE_IDENTITY'
    f,days=path();f.loc[days[2],'instrument_id']=2
    assert trade_label(f,days[:3],days[3])['trade_status']=='INVALID_OR_MISSING_PRICE_IDENTITY'


def test_flat_gross_trade_is_loser_after_fees():
    f,days=path();f.loc[days[3],['open','low']]=100.
    r=trade_label(f,days[:3],days[3]);assert not r['winning'] and r['net_return_pct']<0
