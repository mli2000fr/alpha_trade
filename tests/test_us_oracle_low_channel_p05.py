import pandas as pd
import pytest

from risk_management.models import PriceInfo
from scripts.research import us_oracle_low_channel_p05 as study
from scripts.research import us_oracle_low_channel_p05_audit as review


def fixture_history(lows=None):
    days=pd.bdate_range('2026-04-06',periods=12)
    schedule=pd.DataFrame(dict(date=days,market_open=days.tz_localize('UTC')+pd.Timedelta(hours=13,minutes=30),
        market_close=days.tz_localize('UTC')+pd.Timedelta(hours=20)))
    values=lows if lows is not None else [90+i for i in range(12)]
    groups={('A',d):pd.DataFrame(dict(low=[v,v+1])) for d,v in zip(days,values)}
    return groups,schedule


def make_path(rows):
    return pd.DataFrame([dict(symbol='A',bar_timestamp=pd.Timestamp(t),
        bar_end_timestamp=pd.Timestamp(t)+pd.Timedelta(minutes=5),open=o,high=h,low=l,close=c)
        for t,o,h,l,c in rows])


def unit(monkeypatch,rows,channels,expiry=None):
    monkeypatch.setattr(study,'CHANNELS',channels)
    monkeypatch.setattr(review,'AUDIT_CHANNELS',channels.copy())
    path=make_path(rows);due=expiry or path.bar_timestamp.iloc[-1]
    result=study.unit_outcome(path,dict(price=path.open.iloc[0]),due,.0008)
    k,px,phase=review.scalar_exit(path,0,due,{})
    assert px==result['price']
    assert result['time']==(path.bar_timestamp.iloc[k] if phase=='OPEN' else path.bar_end_timestamp.iloc[k])
    return result


def test_ten_sessions_not_calendar_days():
    groups,schedule=fixture_history()
    channels=study.build_channels(groups,schedule)
    assert ('A',schedule.date.iloc[8]) not in channels
    assert channels['A',schedule.date.iloc[9]]==90
    assert channels['A',schedule.date.iloc[10]]==91


def test_missing_session_not_replaced_by_older_session():
    groups,schedule=fixture_history();del groups['A',schedule.date.iloc[2]]
    channels=study.build_channels(groups,schedule)
    assert ('A',schedule.date.iloc[10]) not in channels
    assert ('A',schedule.date.iloc[11]) not in channels


def test_future_lows_cannot_change_prior_channel():
    groups,schedule=fixture_history();before=study.build_channels(groups,schedule)
    groups['A',schedule.date.iloc[11]]=pd.DataFrame(dict(low=[1.]))
    after=study.build_channels(groups,schedule)
    assert before['A',schedule.date.iloc[9]]==after['A',schedule.date.iloc[9]]
    assert after['A',schedule.date.iloc[11]]==1


def test_other_symbol_not_mixed_into_channel():
    groups,schedule=fixture_history()
    groups.update({('B',d):pd.DataFrame(dict(low=[1.])) for d in schedule.date})
    channels=study.build_channels(groups,schedule)
    assert channels['A',schedule.date.iloc[9]]==90
    assert channels['B',schedule.date.iloc[9]]==1


def test_scalar_channel_builder_independent(monkeypatch):
    groups,schedule=fixture_history();expected=study.build_channels(groups,schedule)
    monkeypatch.setattr(study,'build_channels',lambda *a:(_ for _ in ()).throw(RuntimeError('forbidden')))
    review.configure_history(groups,schedule)
    assert review.AUDIT_CHANNELS==expected


def test_channel_half_cent_contract_uses_scalar_python_round():
    groups,schedule=fixture_history([6.675]+[7.]*11)
    expected=study.build_channels(groups,schedule)
    review.configure_history(groups,schedule)
    assert expected['A',schedule.date.iloc[9]]==6.67
    assert review.AUDIT_CHANNELS==expected


def test_cohort_requires_history_even_for_later_potential_holding_days(monkeypatch):
    days=pd.bdate_range('2026-04-06',periods=21)
    signals=pd.DataFrame([dict(pair_id=1,symbol='A',date=days[0],oracle_date=days[0])])
    channels={('A',d):98. for d in days[:20]}
    del channels['A',days[18]]
    monkeypatch.setattr(study,'CHANNELS',channels)
    common,reserves=study.common_cohort(signals,pd.DataFrame(dict(date=days)))
    assert common.empty and reserves[0]['pair_id']==1
    assert reserves[0]['missing_channel_dates']==[days[18]]


def test_no_channel_on_entry_session(monkeypatch):
    result=unit(monkeypatch,[('2026-04-20 13:30Z',100,130,94,120),
        ('2026-04-20 13:35Z',120,121,96,100)],{('A',pd.Timestamp('2026-04-20')):110.})
    assert result['price']==120 and not result['tightened']


def test_no_intraday_trailing_from_same_session_high(monkeypatch):
    result=unit(monkeypatch,[('2026-04-20 13:30Z',100,150,94,140),
        ('2026-04-20 13:35Z',140,141,94,100),('2026-04-20 13:40Z',100,101,99,100)],{})
    assert result['price']==100


def test_initial_hard_stop_immediate(monkeypatch):
    result=unit(monkeypatch,[('2026-04-20 13:30Z',100,130,90,120),
        ('2026-04-20 13:35Z',120,121,110,120)],{})
    assert result['price']==93 and not result['tightened']


def test_half_cent_same_initial_expression(monkeypatch):
    result=unit(monkeypatch,[('2026-04-20 13:30Z',151.5,160,130,150),
        ('2026-04-20 13:35Z',150,151,140,150)],{})
    assert result['price']==140.89


def test_channel_effective_next_session_not_next_bar(monkeypatch):
    result=unit(monkeypatch,[('2026-04-20 19:50Z',100,120,94,115),
        ('2026-04-20 19:55Z',115,116,95,105),('2026-04-21 13:30Z',105,106,97,100),
        ('2026-04-21 13:35Z',100,101,99,100)],{('A',pd.Timestamp('2026-04-20')):98.})
    assert result['price']==98 and result['time']==pd.Timestamp('2026-04-21 13:35Z')


def test_gap_fills_below_new_channel(monkeypatch):
    result=unit(monkeypatch,[('2026-04-20 19:55Z',100,120,94,115),
        ('2026-04-21 13:30Z',90,92,89,91)],{('A',pd.Timestamp('2026-04-20')):98.})
    assert result['price']==90 and result['net_pct'] < -10


def test_lower_channel_never_loosens_previous_stop(monkeypatch):
    result=unit(monkeypatch,[('2026-04-20 19:55Z',100,120,94,115),
        ('2026-04-21 19:55Z',110,111,99,100),('2026-04-22 13:30Z',100,101,95,99),
        ('2026-04-22 13:35Z',99,100,98,99)],{('A',pd.Timestamp('2026-04-20')):98.,
        ('A',pd.Timestamp('2026-04-21')):95.})
    assert result['price']==98


def test_below_hard_stop_channel_does_not_loosen(monkeypatch):
    result=unit(monkeypatch,[('2026-04-20 19:55Z',100,101,94,100),
        ('2026-04-21 13:30Z',100,101,92,99),('2026-04-21 13:35Z',99,100,98,99)],
        {('A',pd.Timestamp('2026-04-20')):80.})
    assert result['price']==93 and not result['tightened']


def test_expiry_open_does_not_wait_for_channel_break(monkeypatch):
    result=unit(monkeypatch,[('2026-04-20 19:55Z',100,101,99,100),
        ('2026-04-21 13:30Z',120,121,119,120)],{('A',pd.Timestamp('2026-04-20')):99.})
    assert result['price']==120
    assert result['net_pct']==pytest.approx(20-.0008*220)


def test_missing_channel_raises_no_silent_fallback(monkeypatch):
    with pytest.raises(KeyError):
        unit(monkeypatch,[('2026-04-20 19:55Z',100,101,99,100),
            ('2026-04-21 13:30Z',120,121,119,120)],{})


def test_scalar_maintenance_open_priority(monkeypatch):
    path=make_path([('2026-04-20 19:55Z',100,101,99,100),('2026-04-21 13:30Z',120,121,119,120)])
    monkeypatch.setattr(review,'AUDIT_CHANNELS',{('A',pd.Timestamp('2026-04-20')):99.})
    assert review.scalar_exit(path,0,pd.Timestamp('2026-05-20 13:30Z'),{},path.bar_timestamp.iloc[1])==(1,120.,'OPEN')


def test_variant_factory_restored_on_error():
    previous=study.parent.CentLedger,study.parent.scalar_exit_cents
    with pytest.raises(RuntimeError):
        with study.replay_variant('P05'):
            assert study.parent.CentLedger is study.LowChannelLedger
            raise RuntimeError('test')
    assert (study.parent.CentLedger,study.parent.scalar_exit_cents)==previous


def test_common_control_uses_original_factory():
    with study.replay_variant('COMMON_WINNER'):
        assert study.parent.CentLedger is study.ORIGINAL_LEDGER


@pytest.fixture
def opened(tmp_path,monkeypatch):
    risk=study.parent.risk;day=pd.Timestamp('2026-01-05')
    monkeypatch.setattr(risk,'PROFILE',study.READ(study.parent.REFERENCE/'production-risk.json'))
    monkeypatch.setattr(risk,'REGIMES',{day:dict(source_date=pd.Timestamp('2026-01-02'),regime='BULL')})
    monkeypatch.setattr(risk,'ACTIVE_OUTPUT',tmp_path)
    monkeypatch.setattr(study,'CHANNELS',{('A',day):98.})
    monkeypatch.setattr(study,'CLOSES',{day:pd.Timestamp('2026-01-05 14:50Z')})
    monkeypatch.setattr(study,'NEXT_OPENS',{day:pd.Timestamp('2026-01-06 14:30Z')})
    calendar=pd.DataFrame([dict(date=day,market_open=pd.Timestamp('2026-01-05 14:30Z'),market_close=pd.Timestamp('2026-01-05 14:50Z'))])
    ledger=study.LowChannelLedger(calendar,sl=.07,trailing=.15,tp=None)
    ledger.bar_number=0;ledger.begin_bar(pd.Timestamp('2026-01-05 14:30Z'),{'A':100.})
    ledger.entry_context=dict(pair_id=1,oracle_date=pd.Timestamp('2026-01-02'),rank=1,expiry=pd.Timestamp('2026-02-03 14:30Z'))
    info=PriceInfo('A',100.,2.,price_asof_date=day.date(),atr_asof_date=pd.Timestamp('2026-01-02').date(),adv_usd=100_000_000.)
    assert ledger.enter('A','buy',info,sector='RESEARCH_NO_SECTOR_CAP',signal_time=ledger.now,quantity_fraction=.5,selection_rank=1)
    return ledger


def finish_fixture_day(ledger):
    ledger.observe_bar({'A':(100.,120.,94.,115.)})
    for i in (1,2,3):
        ledger.bar_number=i;ledger.begin_bar(pd.Timestamp('2026-01-05 14:30Z')+pd.Timedelta(minutes=5*i),{'A':115.})
        ledger.observe_bar({'A':(115.,116.,99.,110.)})
    ledger.finish_day()


def test_native_does_not_trail_from_intraday_high(opened):
    opened.observe_bar({'A':(100.,140.,94.,120.)})
    assert opened.known_stop('A')==93 and opened.channel_events==[]


def test_native_channel_only_after_day_complete_preserves_shares_expiry(opened):
    quantity=opened.state.positions['A'].quantity;expiry=opened.live_meta['A']['expiry']
    finish_fixture_day(opened)
    assert opened.known_stop('A')==98 and len(opened.channel_events)==1
    assert opened.state.positions['A'].quantity==quantity and opened.live_meta['A']['expiry']==expiry
    assert opened.channel_events[0]['effective_at']==pd.Timestamp('2026-01-06 14:30Z')


def test_native_stop_before_daily_update(opened):
    opened.observe_bar({'A':(100.,120.,90.,115.)})
    assert opened.state.closed_trades[0]['exit_price']==93
    assert not opened.state.positions and not opened.channel_events


def test_native_channel_never_partial_exit(opened):
    finish_fixture_day(opened)
    assert not opened.state.closed_trades
    assert len(opened.state.positions)==1
