import pytest
from scripts.research import fr_p0_p1_directional_audit_20261026 as s


def bar(day,o,h,l,c):return dict(date=day,open=o,high=h,low=l,close=c)


def test_stopped_long_cannot_recover_into_later_future_high():
    r=s.protected_excursion([bar('1',100,105,98,102),bar('2',99,104,89,90),bar('3',100,150,99,149)],'LONG')
    assert r['lower_pct']==pytest.approx(5) and r['upper_pct']==pytest.approx(5)
    assert r['stop_day']=='2' and not r['ambiguous']


def test_new_peak_and_stop_same_daily_bar_remain_bounds():
    r=s.protected_excursion([bar('1',100,125,89,100)],'LONG')
    assert r['lower_pct']==0 and r['upper_pct']==25 and r['ambiguous']


def test_gap_stop_precedes_any_rebound():
    r=s.protected_excursion([bar('1',100,108,95,105),bar('2',85,150,80,140)],'LONG')
    assert r['lower_pct']==pytest.approx(8) and r['upper_pct']==pytest.approx(8)
    assert r['stop_kind']=='GAP'


def test_short_excursion_uses_negative_price_move_as_positive_favorable_size():
    r=s.protected_excursion([bar('1',100,105,80,90),bar('2',111,130,70,100)],'SHORT')
    assert r['lower_pct']==pytest.approx(20) and r['stop_kind']=='GAP'


def test_short_exact_ten_percent_stop_is_not_lost_to_float_rounding():
    r=s.protected_excursion([bar('1',100,110,99,105),bar('2',105,109,50,90)],'SHORT')
    assert r['stop_day']=='1' and r['upper_pct']==pytest.approx(1)


def test_incomplete_horizon_is_not_silently_a_partial_target(monkeypatch):
    from datetime import date
    from types import SimpleNamespace
    import pandas as pd
    monkeypatch.setattr(s,'HORIZONS',(5,))
    days=[date(2026,10,d) for d in [6,7,8,9,12]]
    sessions=[SimpleNamespace(session_date=d,is_open=True,open_at_utc=pd.Timestamp(str(d)+'T07:00Z')) for d in days]
    frame=pd.DataFrame([dict(provider_symbol='A.PA',session_date=pd.Timestamp(d),
        available_at=pd.Timestamp('2026-10-13T20:00Z'),raw_payload_id=i,
        quality_code='VALID',open_price=100.,high_price=101.,low_price=99.,close_price=100.) for i,d in enumerate(days)])
    amf=[dict(available_at=pd.Timestamp('2026-10-05T20:00Z'),positions={'ID':{'holder':1.}})]
    labels,_=s.evaluate(frame,sessions,amf,{'A.PA':{'isin':'ID'}},{},date(2026,10,9))
    assert labels.status.eq('NOT_MATURE').all()


def test_bounded_direction_not_invented_and_first_peak_distinct():
    long=dict(lower_pct=5,upper_pct=25,peak_day='1',ambiguous=True)
    short=dict(lower_pct=20,upper_pct=20,peak_day='2',ambiguous=False)
    assert s.compare_paths(long,short)==('AMBIGUOUS_OR_TIE','INTRADAY_ORDER_UNKNOWN')
    long.update(lower_pct=25,ambiguous=False)
    assert s.compare_paths(long,short)==('LONG','LONG')


def row(holder,ratio,pub='2026-10-05',end=None):
    return dict(isin='ID',holder=holder,ratio_percent=ratio,publication_date=pub,
        position_date=pub,publication_end=end)


def test_below_threshold_absence_is_not_zero_and_future_publications_excluded():
    values,ambiguous=s.active_public_positions([row('a',.4),row('b',1.,pub='2026-10-07')],'2026-10-06',{'ID'})
    assert values=={} and ambiguous==0


def test_ambiguous_holder_not_arbitrarily_selected():
    values,ambiguous=s.active_public_positions([row('a',1.),row('a',2.)],'2026-10-06',{'ID'})
    assert values=={} and ambiguous==1


def test_expired_position_and_latest_same_holder():
    values,_=s.active_public_positions([row('a',1.,end='2026-10-06'),row('b',1.,pub='2026-10-04'),
        row('b',2.)],'2026-10-06',{'ID'})
    assert values=={'ID':{'b':2.}}
