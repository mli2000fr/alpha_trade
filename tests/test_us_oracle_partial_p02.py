from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from risk_management.models import PriceInfo
from scripts.research import us_oracle_partial_p02 as study
from scripts.research.us_oracle_partial_p02_audit import expected_exits


def frame(rows):
    times=pd.date_range('2026-01-05 14:30Z',periods=len(rows),freq='5min')
    return pd.DataFrame([dict(bar_timestamp=t,bar_end_timestamp=t+pd.Timedelta(minutes=5),
        open=o,high=h,low=l,close=c) for t,(o,h,l,c) in zip(times,rows)])


@pytest.mark.parametrize('qty,partial',[(1,0),(2,1),(3,1),(5,2),(10,5)])
def test_whole_share_half_keeps_positive_remainder(qty,partial):
    assert study.partial_quantity(qty)==partial
    assert qty-partial>=1


def test_stop_collision_before_partial_on_all_shares():
    f=frame([(100,112,90,103)])
    events,left=study.scalar_legs(f,0,pd.Timestamp('2026-02-03 14:30Z'),10,True)
    assert left==0 and len(events)==1
    assert events[0]==dict(index=0,quantity=10,price=93.,phase='INTRABAR',role='FINAL')


def test_partial_once_preserves_horizon_and_not_break_even():
    f=frame([(100,112,99,110),(110,115,100,111),(92,94,90,92)])
    events,left=study.scalar_legs(f,0,pd.Timestamp('2026-02-03 14:30Z'),5,True)
    assert left==0 and [e['quantity'] for e in events]==[2,3]
    assert events[0]['price']==110 and events[1]['price']==92
    assert events[1]['index']==2  # low100 on bar1 does not trigger an invented BE stop


def test_gap_partial_receives_limit_not_windfall():
    f=frame([(100,101,99,100),(125,127,120,126)])
    events,left=study.scalar_legs(f,0,f.bar_timestamp.iloc[1],10,True)
    assert [(e['quantity'],e['price'],e['role']) for e in events]==[(5,110.,'PARTIAL'),(5,125.,'FINAL')]
    assert left==0


def test_trailing_uses_prior_completed_high_after_partial():
    f=frame([(100,120,99,115),(110,112,100,105)])
    events,left=study.scalar_legs(f,0,pd.Timestamp('2026-02-03 14:30Z'),10,True)
    assert len(events)==2 and events[0]['price']==110 and events[1]['price']==102
    assert events[1]['index']==1


def test_one_share_never_sold_as_full_tp_by_partial_rule():
    f=frame([(100,120,99,115)])
    events,left=study.scalar_legs(f,0,pd.Timestamp('2026-02-03 14:30Z'),1,True)
    assert events==[] and left==1


def test_half_cent_stop_follows_shared_contract():
    f=frame([(151.5,152,140,145)])
    events,left=study.scalar_legs(f,0,pd.Timestamp('2026-02-03 14:30Z'),2,True)
    assert events[0]['price']==140.89


def test_independent_scalar_agrees_in_collision_gap_and_fraction_cases():
    for rows in [[(100,112,90,103)],[(100,120,99,115),(110,112,100,105)],
                 [(100,101,99,100),(125,127,120,126)]]:
        f=frame(rows);due=pd.Timestamp('2026-02-03 14:30Z')
        for qty in [1,3,10]:
            a,left=study.scalar_legs(f,0,due,qty,True)
            b,rest=expected_exits(f,0,due,qty,True)
            assert left==rest
            assert [(e['index'],e['quantity'],e['price'],e['phase']) for e in a]==b


@pytest.fixture
def opened(tmp_path,monkeypatch):
    risk=study.parent.risk
    profile=study.READ(study.parent.REFERENCE/'production-risk.json')
    monkeypatch.setattr(risk,'PROFILE',profile)
    day=pd.Timestamp('2026-01-05')
    monkeypatch.setattr(risk,'REGIMES',{day:dict(source_date=pd.Timestamp('2026-01-02'),regime='BULL')})
    monkeypatch.setattr(risk,'ACTIVE_OUTPUT',tmp_path)
    calendar=pd.DataFrame([dict(date=day,market_open=pd.Timestamp('2026-01-05 14:30Z'),market_close=pd.Timestamp('2026-01-05 14:50Z'))])
    ledger=study.PartialLedger(calendar,sl=.07,trailing=.15,tp=None,partial_enabled=True)
    ledger.bar_number=0;ledger.begin_bar(pd.Timestamp('2026-01-05 14:30Z'),{'A':100.})
    ledger.entry_context=dict(pair_id=1,oracle_date=pd.Timestamp('2026-01-02'),rank=1,expiry=pd.Timestamp('2026-02-03 14:30Z'))
    info=PriceInfo('A',100.,2.,price_asof_date=day.date(),atr_asof_date=pd.Timestamp('2026-01-02').date(),adv_usd=100_000_000.)
    assert ledger.enter('A','buy',info,sector='RESEARCH_NO_SECTOR_CAP',signal_time=ledger.now,quantity_fraction=.5,selection_rank=1)
    assert ledger.state.positions['A'].quantity==10
    return ledger


def test_native_partial_preserves_cash_basis_peak_horizon_trackers(opened):
    l=opened;orig=deepcopy(l.state.positions['A']);meta=deepcopy(l.live_meta['A'])
    losses=l.engine._concentration_loss_tracker.to_dict();entries=l.engine._concentration_trade_tracker.to_dict()
    l.observe_bar({'A':(100.,112.,99.,110.)})
    p=l.state.positions['A'];leg=l.state.closed_trades[0]
    assert p.quantity==5 and p.entry_price==100 and l.live_meta['A']==meta
    assert p.entry_cash_flow==pytest.approx(orig.entry_cash_flow/2)
    assert p.entry_cost==pytest.approx(orig.entry_cost/2)
    assert p.peak_high==112 and l.known_stop('A')==95.2  # NOT moved to100
    assert leg['quantity']==5 and leg['exit_price']==110 and leg['leg_role']=='PARTIAL'
    assert l.engine._concentration_loss_tracker.to_dict()==losses
    assert l.engine._concentration_trade_tracker.to_dict()==entries
    fee=l.engine._cost_model.per_leg_cost_pct
    assert leg['pnl']==pytest.approx(5*(110-100)-5*(110+100)*fee)
    assert l.equity()==pytest.approx(4000-10*100*(1+fee)+5*110*(1-fee)+5*110)


def test_intrabar_partial_cash_not_available_at_preceding_open(opened):
    l=opened;before=l.state.settled_cash
    assert len(l.state.closed_trades)==0
    l.observe_bar({'A':(100.,112.,99.,110.)})
    assert l.phase=='INTRABAR' and l.state.settled_cash>before
    with pytest.raises(ValueError,match='phase'):
        l.enter('B','buy',PriceInfo('B',100.,2.),sector='RESEARCH_NO_SECTOR_CAP',signal_time=l.now)


def test_native_stop_beats_partial_collision(opened):
    l=opened;l.observe_bar({'A':(100.,112.,90.,105.)})
    assert not l.state.positions and len(l.state.closed_trades)==1
    assert l.state.closed_trades[0]['quantity']==10 and l.state.closed_trades[0]['exit_price']==93
    assert l.state.closed_trades[0]['leg_role']=='FINAL'


def test_no_second_partial_after_repeated_target_touches(opened):
    l=opened;l.observe_bar({'A':(100.,112.,99.,110.)})
    l.bar_number=1;l.begin_bar(pd.Timestamp('2026-01-05 14:35Z'),{'A':111.})
    l.observe_bar({'A':(111.,115.,105.,112.)})
    assert l.state.positions['A'].quantity==5 and len(l.state.closed_trades)==1


def test_campaign_profit_not_classified_as_loss_of_remaining_fragment(opened):
    l=opened;l.observe_bar({'A':(100.,110.,99.,110.)})
    l.bar_number=1;l.begin_bar(pd.Timestamp('2026-01-05 14:35Z'),{'A':93.})
    l.resolve_open()
    assert not l.state.positions
    assert l.state.closed_trades[-1]['pnl']<0
    assert sum(r['pnl'] for r in l.state.closed_trades)>0
    assert l.engine._concentration_loss_tracker.to_dict()['streak']['long:A']==0
    f=pd.DataFrame(l.state.closed_trades)
    summary=study.campaigns_from_legs(f,[])
    assert len(summary)==1 and summary.pnl.iloc[0]>0 and summary.quantity.iloc[0]==10


def test_open_partial_campaign_not_counted_as_closed_trade(opened):
    l=opened;l.observe_bar({'A':(100.,112.,99.,110.)})
    assert study.campaigns_from_legs(pd.DataFrame(l.state.closed_trades),[dict(pair_id=1)]).empty


def test_partial_profit_cannot_reset_prior_loss_streak_before_final_exit(opened):
    l=opened;tracker=l.engine._concentration_loss_tracker
    tracker.record('A',-10.,l.day.date(),side='buy')
    tracker.record('A',-10.,l.day.date(),side='buy')
    l.observe_bar({'A':(100.,112.,99.,110.)})
    assert l.engine._concentration_loss_tracker.to_dict()['streak']['long:A']==2


def test_config_confirmation_is_two_above_prior_high_not_two_rising_closes():
    raw=dict(enabled=False,initial_position_fraction=.5,reinforcement_enabled=False,confirmation_bars=2,
        stop_loss_pct=.07,take_profit_pct=None,trailing_stop_pct=.15,horizon_sessions=20,entry_valid_sessions=20)
    assert study.validate_config(raw).confirmation_bars==2
    with pytest.raises(ValueError,match='differs'):
        study.validate_config(dict(raw,confirmation_bars=1))


def test_same_native_entry_fee_is_not_double_counted_in_partial_legs():
    f=frame([(100.,110.,99.,110.),(93.,94.,92.,93.)])
    events,_=study.scalar_legs(f,0,pd.Timestamp('2026-02-03 14:30Z'),10,True)
    assert sum(e['quantity'] for e in events)==10
    fee=.0008;net=sum(e['quantity']*((e['price']-100)-fee*(e['price']+100)) for e in events)
    assert net==pytest.approx(15.-fee*(1000+550+465))
