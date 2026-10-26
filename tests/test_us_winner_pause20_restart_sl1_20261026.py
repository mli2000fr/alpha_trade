from dataclasses import asdict,replace
from datetime import date,timedelta
from functools import lru_cache

import pandas as pd
import pytest

from scripts.research import us_winner_pause20_restart_sl1_20261026 as study


def profiles():
    return {**study.study.CATALOG,
        study.NORMAL:dict(name=study.NORMAL,stop_loss_pct=.05,take_profit_pct=None,trailing_stop_pct=None,horizon_sessions=20),
        study.DEFENSIVE:dict(name=study.DEFENSIVE,stop_loss_pct=.01,take_profit_pct=None,trailing_stop_pct=None,horizon_sessions=20)}


def test_twenty_active_sessions_include_resume_and_never_read_future_resumes():
    resume=pd.Timestamp('2024-11-01T13:30Z')
    sessions,normal=study.window_sessions(resume,study.grid.calendar())
    assert len(sessions)==20 and sessions[0].session_date==date(2024,11,1)
    rows=[dict(cycle=2,resumed_at=resume.isoformat())]
    assert study.phase_for_day(date(2024,10,31),rows,study.grid.calendar())==study.NORMAL
    assert study.phase_for_day(sessions[0].session_date,rows,study.grid.calendar())==study.DEFENSIVE
    assert study.phase_for_day(sessions[-1].session_date,rows,study.grid.calendar())==study.DEFENSIVE
    assert study.phase_for_day(normal.session_date,rows,study.grid.calendar())==study.NORMAL
    extra=rows+[dict(cycle=3,resumed_at='2025-01-02T14:30:00Z')]
    assert study.phase_for_day(date(2024,11,6),rows,study.grid.calendar())==study.phase_for_day(date(2024,11,6),extra,study.grid.calendar())


def test_second_resume_starts_a_fresh_twenty_session_window():
    rows=[dict(cycle=2,resumed_at='2024-01-02T14:30:00Z'),dict(cycle=3,resumed_at='2024-03-01T14:30:00Z')]
    assert study.phase_for_day(date(2024,2,29),rows,study.grid.calendar())==study.NORMAL
    assert study.phase_for_day(date(2024,3,1),rows,study.grid.calendar())==study.DEFENSIVE


@pytest.mark.parametrize('pending',[False,True])
def test_native_funded_sl1_never_widens_and_unfilled_plan_switches_to_sl5(monkeypatch,pending):
    from tests.test_us_winner_monthly_selector_20261024 import replay_fixture
    from backtesting.simulator import BacktestEngine
    cfg,args=replay_fixture(pending)
    monkeypatch.setattr(study.study,'CATALOG',profiles())
    resumes=[dict(cycle=2,resumed_at='2020-10-05T13:30:00Z')]
    selector=lambda day:study.phase_for_day(day,resumes,study.grid.calendar())
    assert selector(date(2020,10,30))==study.DEFENSIVE
    assert selector(date(2020,11,2))==study.NORMAL
    with study.study.capacity.corrected_runtime(),study.cycle.repair.campaign_adapter(cfg.exec_config,selector) as metadata:
        result=BacktestEngine(cfg).run(**args)
    funded=[m for m in metadata.values() if m.get('first_fill_at')]
    assert len(funded)==1
    assert funded[0]['policy']['stop_loss_pct']==(.05 if pending else .01)
    assert funded[0]['profile']==(study.NORMAL if pending else study.DEFENSIVE)
    if not pending:
        # Open100 onNov2 breaches the old1% stop100.98, NOT a widened5% stop96.9.
        trade=result.closed_trades_df.iloc[0]
        assert trade.exit_reason=='STOP_GAP' and trade.exit_price==100.
        assert pd.Timestamp(trade.exit_date).tz_convert('America/New_York').date()==date(2020,11,2)
    else:
        assert len({m['entry_expires_at'] for m in metadata.values()})==1


@lru_cache(maxsize=1)
def replay():
    from tests.test_winner_global_liquidation import data_with_global_drawdown
    cfg,args,raw=data_with_global_drawdown(last=date(2026,11,20))
    cfg=replace(cfg,risk_config=replace(cfg.risk_config,min_position_notional=70.,policy='b4'))
    cfg=study.pause.with_sessions(cfg)
    args['close']['SPY']=100.+pd.Series(range(len(args['close'])),index=args['close'].index)*.01
    for symbol in ('AAA','BBB','CCC'):
        raw[cfg.start_date,symbol].loc[10:,['open','close','high','low']]=[100.,100.,100.1,99.9]
        raw[date(2026,11,17),symbol].loc[1:,['open','close','high','low']]=[106.,106.,106.1,105.9]
    fresh=pd.DataFrame([dict(trade_date=date(2026,11,16),symbol=s,rank=i+1,selected=True)
        for i,s in enumerate(('AAA','BBB','CCC'))])
    args['signals_df']=pd.concat([args['signals_df'],fresh],ignore_index=True)
    with study.hybrid_scope(None),study.study.capacity.corrected_runtime(),study.cycle.repair.campaign_adapter(
            cfg.exec_config,study.select_phase) as metadata:
        result=study.base.BacktestEngine(cfg).run(**args)
    class Tape:
        schedule={s.session_date:s for s in study.study.inputs.sessions(start=date(2026,10,1),end=cfg.end_date)}
        def day(self,symbol,day):
            f=raw[day,symbol].rename(columns={'timestamp':'bar_timestamp'}).copy()
            f['bar_end_timestamp']=f.bar_timestamp+pd.Timedelta(minutes=5)
            f['trade_date']=pd.Timestamp(day);f['session_close']=pd.Timestamp(self.schedule[day].close_at_utc)
            return f
        def path(self,symbol,start,end):
            f=pd.concat([self.day(s,d) for d,s in raw if s==symbol and start.date()<=d<=end.date()],ignore_index=True)
            return f[f.bar_timestamp.between(start,end)].sort_values('bar_timestamp')
    return cfg,result,metadata,Tape()


def test_actual_pause_and_restart_protections_pass_audit(monkeypatch):
    cfg,result,metadata,tape=replay()
    monkeypatch.setattr(study.study.inputs,'END',cfg.end_date)
    original_sessions=study.study.inputs.sessions
    monkeypatch.setattr(study.study.inputs,'sessions',lambda start,**kw:original_sessions(start=start,end=cfg.end_date))
    summary=study.grid.metrics(result,4000.)
    checked=study.audit(result,summary,metadata,tape)
    assert checked['phase_counts'][study.NORMAL]==3
    assert checked['phase_counts'][study.DEFENSIVE]==3
    assert checked['resumes']==1
    assert summary['restart_windows'][0]['sl_during_restart']==.01


def test_phase_audit_rejects_wrong_actual_entry_stop(monkeypatch):
    from copy import deepcopy
    cfg,result,original,tape=replay()
    metadata=deepcopy(original)
    item=next(m for m in metadata.values() if m.get('first_fill_at') and m['profile']==study.DEFENSIVE)
    item['policy']['stop_loss_pct']=.05
    monkeypatch.setattr(study.study.inputs,'END',cfg.end_date)
    original_sessions=study.study.inputs.sessions
    monkeypatch.setattr(study.study.inputs,'sessions',lambda start,**kw:original_sessions(start=start,end=cfg.end_date))
    with pytest.raises((ValueError,AssertionError)):
        study.audit(result,study.grid.metrics(result,4000.),metadata,tape)


def test_scope_restores_controller_catalog_and_active_state():
    import backtesting.winner_global_liquidation as module
    old=(module.GlobalLiquidation,study.study.CATALOG,study.ACTIVE)
    with study.hybrid_scope(None):assert module.GlobalLiquidation is study.RestartController
    assert old==(module.GlobalLiquidation,study.study.CATALOG,study.ACTIVE)
