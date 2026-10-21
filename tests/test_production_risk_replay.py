from dataclasses import replace
import pandas as pd
import pytest

from backtesting.production_risk_replay import GUARD_FIELDS,ProductionRiskController,force_close_selection
from backtesting.risk_overlay import DrawdownCircuitBreaker
from risk_management.config import RiskConfig
from scripts.research import us_intraday_protection_grid_risk as runner


def fields(**overrides):
    cfg=replace(RiskConfig(),policy='b4',max_portfolio_drawdown_pct=.2,max_daily_loss_pct=.03,
        degraded_entry_allocation_pct=.06,regime_ramp_up_enabled=True,rolling_peak_window_days=252,
        regime_ramp_up_max_pct=.25,**overrides)
    return {f:getattr(cfg,f) for f in GUARD_FIELDS}


def calendar():
    return pd.DataFrame([dict(date=pd.Timestamp(d),market_open=pd.Timestamp(d+' 14:30Z'),
        market_close=pd.Timestamp(d+' 14:45Z')) for d in ['2025-01-02','2025-01-03','2025-01-06']])


def test_production_dd_trip_and_floor():
    r=ProductionRiskController(fields())
    e=r.evaluate(pd.Timestamp('2025-01-02'),3100.,'SLIDE')
    assert e['just_tripped'] and e['allocation_scale']==.1
    assert e['active'] is False  # actual B4 production semantics, not hard halt


def test_production_daily_loss_under_b4_is_not_hard_halt():
    r=ProductionRiskController(fields())
    e=r.evaluate(pd.Timestamp('2025-01-02'),3800.,'BULL')
    assert e['daily_loss_status'] and not e['just_tripped']
    assert not e['active'] and e['allocation_scale']==1.


def test_once_per_session_not_once_per_bar():
    r=ProductionRiskController(fields())
    d=pd.Timestamp('2025-01-02');r.evaluate(d,3100.,'BULL')
    with pytest.raises(ValueError):r.evaluate(d,3000.,'BULL')
    with pytest.raises(ValueError):r.evaluate(d+pd.Timedelta(days=1),3000.,'BULL')
    r.finish(d,3000.)
    assert r.breaker._episode.favorable_streak==1


def test_hwm_daily_window_and_zero_intraday_status_appends():
    f=fields();f['rolling_peak_window_days']=2
    r=ProductionRiskController(f)
    d=pd.Timestamp('2025-01-02')
    r.evaluate(d,4000.,'BULL');r.finish(d,3900.)
    r.evaluate(d+pd.Timedelta(days=1),3900.,'BULL');r.finish(d+pd.Timedelta(days=1),3850.)
    e=r.evaluate(d+pd.Timedelta(days=2),3800.,'BULL')
    assert e['reference_peak']==3900.
    before=list(r.closes)
    for i in range(20):r.breaker.status()
    assert list(r.closes)==before


def test_b4_daily_component_matches_existing_backtest_machine():
    f=fields();f['rolling_peak_window_days']=0
    r=ProductionRiskController(f)
    b=DrawdownCircuitBreaker(enabled=True,policy='b4',max_dd_pct=.2,rolling_peak_window_days=0,
        degraded_entry_allocation_pct=.06,regime_ramp_up_enabled=True,regime_ramp_up_max_pct=.25)
    peak=4000.
    for i,(eq,reg) in enumerate([(4000,'BULL'),(3100,'SLIDE'),(3150,'REBOUND'),(3200,'REBOUND'),
        (3300,'BULL'),(3500,'BULL'),(3000,'BULL'),(3500,'BULL'),(3900,'BULL'),(4100,'BULL')]):
        d=pd.Timestamp('2025-01-02')+pd.Timedelta(days=i);peak=max(peak,eq)
        b._regime_today=reg;b.update(eq,peak);trip=b.just_tripped();b.update_regime_streak('normal',eq)
        e=r.evaluate(d,eq,reg)
        assert e['just_tripped']==trip and e['allocation_scale']==pytest.approx(b.allocation_scale('normal'))
        r.finish(d,eq)


def test_force_close_half_positions_not_half_capital_and_side_correct():
    held=[dict(symbol='L',side='buy',quantity=10,entry_price=100,mark=90),
        dict(symbol='S',side='sell',quantity=10,entry_price=100,mark=115),
        dict(symbol='G',side='buy',quantity=100,entry_price=100,mark=110)]
    assert force_close_selection(held,.5)==['S','L']
    assert force_close_selection([],.5)==[]


def setup_ledger(monkeypatch,force=True):
    monkeypatch.setattr(runner,'PROFILE',dict(guard_fields=fields(),force_close_enabled=force,force_close_fraction=.5))
    monkeypatch.setattr(runner,'REGIMES',{d:dict(source_date=d-pd.Timedelta(days=1),regime='SLIDE') for d in calendar().date})
    monkeypatch.setattr(runner,'ACTIVE_OUTPUT',__import__('pathlib').Path('unused-test-output'))
    return runner.ProductionRiskGridLedger(calendar(),sl=.07,trailing=None)


def entry(l,s):
    from risk_management.models import PriceInfo
    l.entry_context=dict(pair_id=1,oracle_date=l.day,rank=1,expiry=pd.Timestamp('2025-01-06 14:40Z'))
    return l.enter(s,'buy',PriceInfo(s,100.,2.,price_asof_date=l.day.date(),
        atr_asof_date=pd.Timestamp('2025-01-01').date(),adv_usd=1e8),
        sector='RESEARCH_NO_SECTOR_CAP',signal_time=l.now,quantity_fraction=.5)


def test_scale_changes_booked_quantity_not_only_log(monkeypatch):
    l=setup_ledger(monkeypatch)
    l.state.settled_cash=3100.
    l.begin_bar(pd.Timestamp('2025-01-02 14:30Z'),{'ABC':100.})
    assert l.allocation==.1
    assert entry(l,'ABC') is False  # full15 shares =>half7=>degraded0, no upward rounding
    assert not l.state.positions


def test_scale_is_applied_once_with_whole_shares(monkeypatch):
    l=setup_ledger(monkeypatch)
    # Artificial prior peak, no future bar data: current4000, loss25% from peak.
    l.guard.closes.clear();l.guard.closes.append(5500.)
    l.begin_bar(pd.Timestamp('2025-01-02 14:30Z'),{'ABC':100.})
    assert entry(l,'ABC')
    assert l.state.positions['ABC'].quantity==1  # full20*.5*.1
    assert l.audit[-1]['production_approved']==1


def test_force_exit_uses_observed_next_open_and_native_costs(monkeypatch):
    l=setup_ledger(monkeypatch)
    l.begin_bar(pd.Timestamp('2025-01-02 14:30Z'),{'A':100.,'B':100.})
    entry(l,'A');entry(l,'B')
    for i in range(3):
        if i:l.begin_bar(pd.Timestamp('2025-01-02 14:30Z')+pd.Timedelta(minutes=5*i),{'A':100.,'B':100.})
        l.observe_bar({'A':[100.,100.,100.,100.],'B':[100.,100.,100.,100.]})
    l.finish_day()
    # Equity loss external to these marks, synthetic trigger for lifecycle test.
    l.state.settled_cash-=1000.
    l.begin_bar(pd.Timestamp('2025-01-03 14:30Z'),{'A':100.,'B':100.})
    assert len(l.state.positions)==1
    t=l.state.closed_trades[-1]
    assert t['exit_reason']=='PRODUCTION_BREAKER_FORCE' and t['exit_price']==100.
    assert t['pnl']<0 and t['exit_phase']=='OPEN'


def test_no_alert_or_broker_side_effects(monkeypatch):
    import risk_management.circuit_breaker as cb
    monkeypatch.setattr(cb,'_try_send_alert',lambda *a,**k:pytest.fail('No research alerts'))
    r=ProductionRiskController(fields());r.evaluate(pd.Timestamp('2025-01-02'),3000.,None)
