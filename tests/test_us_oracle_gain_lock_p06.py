from types import SimpleNamespace

import pandas as pd
import pytest

from risk_management.models import PriceInfo
from scripts.research import us_oracle_gain_lock_p06 as study
from scripts.research.us_oracle_gain_lock_p06_audit import scalar_exit


def path(rows):
    times=pd.date_range('2026-01-05 14:30Z',periods=len(rows),freq='5min')
    return pd.DataFrame([dict(bar_timestamp=t,bar_end_timestamp=t+pd.Timedelta(minutes=5),
        open=o,high=h,low=l,close=c) for t,(o,h,l,c) in zip(times,rows)])


def outcome(rows,due=None):
    frame=path(rows)
    expiry=due or frame.bar_timestamp.iloc[-1]
    return study.unit_outcome(frame,dict(price=frame.open.iloc[0]),expiry,.0008)


def test_protects_gain_not_percent_of_peak():
    assert study.gain_stop(100.,120.)==(110.,True)
    assert max(round(100*(1-.07),2),round(120*(1-.15),2))==102.


def test_no_old_trailing_before_activation():
    assert study.gain_stop(100.,109.9)==(93.,False)
    assert study.gain_stop(100.,110.)==(105.,True)


def test_activation_tick_rounding_avoids_float_110_boundary():
    assert 100*(1+.10)>110.
    assert study.gain_stop(100.,110.)[1] is True


def test_half_cent_initial_stop_matches_existing_winner():
    assert study.gain_stop(151.5,151.5)==(140.89,False)


def test_stop_ratchets_with_observed_maximum_only():
    peak=100.;stops=[]
    for high in [105,110,120,115,130,118]:
        peak=max(peak,high);stops.append(study.gain_stop(100.,peak)[0])
    assert stops==[93.,105.,110.,110.,115.,115.]


def test_same_bar_high_cannot_raise_own_stop():
    r=outcome([(100,120,94,115),(115,116,114,115)])
    assert r['price']==115 and r['reason']=='HORIZON_OPEN' and r['activated']


def test_stop_collision_precedes_activation_from_unknown_high_order():
    r=outcome([(100,120,90,115),(115,116,114,115)])
    assert r['price']==93 and r['activated'] is False


def test_next_bar_uses_new_gain_stop_on_whole_position():
    r=outcome([(100,120,99,115),(115,116,105,110),(110,111,109,110)])
    assert r['price']==110 and r['reason']=='STOP' and r['time']==pd.Timestamp('2026-01-05 14:40Z')


def test_gap_can_erase_the_protected_gain():
    r=outcome([(100,120,99,115),(90,92,88,90)])
    assert r['price']==90 and r['reason']=='STOP_GAP' and r['net_pct']< -10


def test_horizon_does_not_reset_on_activation():
    r=outcome([(100,110,99,109),(111,112,110,111)])
    assert r['price']==111 and r['time']==pd.Timestamp('2026-01-05 14:35Z')


def test_no_partial_fill_at_activation_threshold():
    r=outcome([(100,120,99,115),(140,142,139,140)])
    assert r['price']==140 and r['reason']=='HORIZON_OPEN'
    assert r['net_pct']==pytest.approx(40-.0008*240)


def test_future_prices_after_stop_do_not_change_result():
    a=outcome([(100,120,90,100),(100,101,99,100)])
    b=outcome([(100,120,90,100),(500,600,400,500)])
    assert a==b


def test_separate_scalar_agrees_without_calling_primary_stop(monkeypatch):
    f=path([(100,120,99,115),(115,116,105,110),(110,111,109,110)])
    due=f.bar_timestamp.iloc[2]
    result=study.unit_outcome(f,dict(price=100.),due,.0008)
    monkeypatch.setattr(study,'gain_stop',lambda *a:(_ for _ in ()).throw(RuntimeError('primary not allowed')))
    k,px,phase=scalar_exit(f,0,due,{})
    assert k==1 and px==result['price'] and phase=='INTRABAR'


def test_variant_factory_restored_on_failure():
    original=(study.parent.CentLedger,study.parent.scalar_exit_cents)
    with pytest.raises(RuntimeError,match='test failure'):
        with study.replay_variant('P06'):
            assert study.parent.CentLedger is study.GainLockLedger
            raise RuntimeError('test failure')
    assert (study.parent.CentLedger,study.parent.scalar_exit_cents)==original


@pytest.fixture
def opened(tmp_path,monkeypatch):
    risk=study.parent.risk;day=pd.Timestamp('2026-01-05')
    monkeypatch.setattr(risk,'PROFILE',study.READ(study.parent.REFERENCE/'production-risk.json'))
    monkeypatch.setattr(risk,'REGIMES',{day:dict(source_date=pd.Timestamp('2026-01-02'),regime='BULL')})
    monkeypatch.setattr(risk,'ACTIVE_OUTPUT',tmp_path)
    calendar=pd.DataFrame([dict(date=day,market_open=pd.Timestamp('2026-01-05 14:30Z'),market_close=pd.Timestamp('2026-01-05 14:50Z'))])
    ledger=study.GainLockLedger(calendar,sl=.07,trailing=.15,tp=None)
    ledger.bar_number=0;ledger.begin_bar(pd.Timestamp('2026-01-05 14:30Z'),{'A':100.})
    ledger.entry_context=dict(pair_id=1,oracle_date=pd.Timestamp('2026-01-02'),rank=1,expiry=pd.Timestamp('2026-02-03 14:30Z'))
    info=PriceInfo('A',100.,2.,price_asof_date=day.date(),atr_asof_date=pd.Timestamp('2026-01-02').date(),adv_usd=100_000_000.)
    assert ledger.enter('A','buy',info,sector='RESEARCH_NO_SECTOR_CAP',signal_time=ledger.now,quantity_fraction=.5,selection_rank=1)
    return ledger


def test_native_activation_preserves_all_shares_and_expiry(opened):
    l=opened;q=l.state.positions['A'].quantity;expiry=l.live_meta['A']['expiry']
    l.observe_bar({'A':(100.,120.,99.,115.)})
    assert not l.state.closed_trades and l.state.positions['A'].quantity==q
    assert l.live_meta['A']['expiry']==expiry and l.known_stop('A')==110
    assert len(l.activations)==1 and l.activations[0]['observed_at']==pd.Timestamp('2026-01-05 14:35Z')


def test_native_prior_stop_before_new_same_bar_high(opened):
    l=opened;l.observe_bar({'A':(100.,120.,90.,115.)})
    assert not l.state.positions and l.state.closed_trades[0]['exit_price']==93
    assert l.activations==[]


def test_native_next_bar_gain_stop_not_tp_or_reduction(opened):
    l=opened;q=l.state.positions['A'].quantity;l.observe_bar({'A':(100.,120.,99.,115.)})
    l.bar_number=1;l.begin_bar(pd.Timestamp('2026-01-05 14:35Z'),{'A':115.})
    l.observe_bar({'A':(115.,116.,105.,110.)})
    assert len(l.state.closed_trades)==1
    assert l.state.closed_trades[0]['quantity']==q and l.state.closed_trades[0]['exit_price']==110


def test_native_logs_activation_once_per_campaign(opened):
    l=opened;l.observe_bar({'A':(100.,110.,99.,109.)})
    l.bar_number=1;l.begin_bar(pd.Timestamp('2026-01-05 14:35Z'),{'A':111.})
    l.observe_bar({'A':(111.,120.,110.,115.)})
    assert len(l.activations)==1 and l.known_stop('A')==110


def test_native_does_not_tighten_to_old_tr15_before_gainlock(opened):
    l=opened;l.observe_bar({'A':(100.,109.9,99.,109.)})
    assert not l.activations and l.known_stop('A')==93
