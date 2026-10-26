from copy import deepcopy
from dataclasses import asdict,replace
from datetime import date,timedelta
from functools import lru_cache
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.research import us_winner_cycle15_pause20_min70_20261026 as study
from tests.test_winner_global_liquidation import data_with_global_drawdown,MarkBook,evaluation


@pytest.mark.parametrize('day,expected',[
    ('2024-05-24T15:00Z','2024-06-26T13:30Z'),
    ('2024-11-27T15:00Z','2024-12-30T14:30Z'),
    ('2024-11-01T15:00Z','2024-12-03T14:30Z'),
])
def test_twenty_real_sessions_holidays_half_days_dst(day,expected):
    paused,resume=study.pause_schedule(pd.Timestamp(day),study.grid.calendar())
    assert len(paused)==20 and len({s.session_date for s in paused})==20
    assert pd.Timestamp(resume.open_at_utc)==pd.Timestamp(expected)
    assert all(s.session_date>pd.Timestamp(day).date() for s in paused)
    if day.startswith('2024-11-27'):assert paused[0].session_date==date(2024,11,29)


def test_configuration_only_changes_pause_unit_from_three_months():
    parent=study.base.read(study.runner.CONTROL/'protocol.json')
    cfg=study.runner.base_configuration(parent)
    before=study.ORIGINAL_WITH_CYCLE(cfg);after=study.with_sessions(cfg)
    a,b=study.runner.normalized(before),study.runner.normalized(after)
    b['winner_drawdown_cooldown_months']=3
    assert a==b and after.risk_config.effective_min_notional==70.
    assert after.initial_equity==4000. and after.winner_hard_drawdown_pct is None
    controller=study.SessionCycle(after,after.risk_config,after.exec_config)
    assert controller.summary()['cooldown_sessions']==20
    assert controller.summary()['cooldown_months']==0
    with pytest.raises(ValueError):study.SessionCycle(before,before.risk_config,before.exec_config)


def test_resume_cannot_start_on_twentieth_session_or_recapitalize():
    cfg,_,_=data_with_global_drawdown()
    cfg=replace(cfg,risk_config=replace(cfg.risk_config,min_position_notional=70.))
    cfg=study.with_sessions(cfg)
    control=study.SessionCycle(cfg,cfg.risk_config,cfg.exec_config)
    book=MarkBook();book.marks={};book.equity=lambda:3390.
    store=SimpleNamespace(rows=lambda:[])
    stamp=pd.Timestamp('2024-11-27T15:00Z').to_pydatetime()
    control.observe(stamp,3390.,book,evaluation());control.execute(stamp,store,None,book,None)
    due=control.paused_until
    assert pd.Timestamp(due)==pd.Timestamp('2024-12-30T14:30Z')
    assert not control.resume(pd.Timestamp('2024-12-27T20:00Z').to_pydatetime(),book)
    assert not control.resume(due-timedelta(seconds=1),book)
    assert control.resume(due,book)
    assert control.cycle_peak==3390. and control.peak==4000.
    assert control.summary()['reset_deposits']==0 and control.resumes[0]['equity']==3390.


@lru_cache(maxsize=1)
def replay_fixture():
    cfg,args,raw=data_with_global_drawdown(last=date(2026,11,20))
    cfg=replace(cfg,risk_config=replace(cfg.risk_config,min_position_notional=70.))
    cfg=study.with_sessions(cfg)
    cfg=replace(cfg,risk_config=replace(cfg.risk_config,policy='b4',min_position_notional=70.))
    args['close']['SPY']=100.+pd.Series(range(len(args['close'])),index=args['close'].index)*.01
    for symbol in ('AAA','BBB','CCC'):
        raw[cfg.start_date,symbol].loc[10:,['open','close','high','low']]=[100.,100.,100.1,99.9]
        raw[date(2026,11,17),symbol].loc[1:,['open','close','high','low']]=[106.,106.,106.1,105.9]
    fresh=pd.DataFrame([dict(trade_date=date(2026,11,16),symbol=s,rank=i+1,selected=True)
        for i,s in enumerate(('AAA','BBB','CCC'))])
    args['signals_df']=pd.concat([args['signals_df'],fresh],ignore_index=True)
    with study.installed(),study.session_scope(None):result=study.base.BacktestEngine(cfg).run(**args)
    metadata={t.campaign_id:dict(policy=asdict(cfg.exec_config.winner_pyramiding),symbol=t.symbol,first_fill_at=t.entry_date)
        for t in result.closed_trades_df.itertuples()}
    for row in result.trade_events_df[result.trade_events_df.event.eq('BUY_FILL')].itertuples():
        if (row.symbol,pd.Timestamp(row.time)) not in {(m['symbol'],pd.Timestamp(m['first_fill_at'])) for m in metadata.values()}:
            metadata['open-'+row.symbol]=dict(policy=asdict(cfg.exec_config.winner_pyramiding),symbol=row.symbol,first_fill_at=row.time)
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


def test_actual_replay_waits_twenty_sessions_and_restarts_with_fresh_signal(monkeypatch):
    cfg,result,metadata,tape=replay_fixture()
    info=result.tracker_snapshot['winner_replay']['global_liquidation']
    assert len(info['events'])==len(info['resumes'])==1
    assert pd.Timestamp(info['resumes'][0]['resumed_at'])==pd.Timestamp('2026-11-17T14:30Z')
    buys=result.trade_events_df[result.trade_events_df.event.eq('BUY_FILL')]
    times=pd.to_datetime(buys.time,utc=True);resume=pd.Timestamp(info['resumes'][0]['resumed_at'])
    assert not (times.ge(pd.Timestamp(info['events'][0]['detected_at']))&times.lt(resume)).any()
    assert times.ge(resume).any()
    monkeypatch.setattr(study.study.inputs,'END',cfg.end_date)
    summary=study.grid.metrics(result,4000.)
    assert study.session_audit(result,summary,metadata,tape)['resumes']==1


@pytest.mark.parametrize('fault',['pause','deposit','quantity','risk_reset','hidden_months'])
def test_audit_rejects_bad_dates_cash_quantities_and_risk(monkeypatch,fault):
    cfg,original,metadata,tape=replay_fixture();result=deepcopy(original)
    info=result.tracker_snapshot['winner_replay']['global_liquidation']
    if fault=='pause':info['events'][0]['paused_until']='2026-11-16T14:30:00+00:00'
    elif fault=='deposit':info['resumes'][0]['equity']+=1000.
    elif fault=='quantity':info['events'][0]['quantities']['AAA']+=1
    elif fault=='hidden_months':info['cooldown_months']=3
    else:
        rows=pd.to_datetime(result.drawdown_breaker_df.timestamp,utc=True).eq(pd.Timestamp(info['resumes'][0]['resumed_at']))
        result.drawdown_breaker_df.loc[rows,'peak']=99999.
    monkeypatch.setattr(study.study.inputs,'END',cfg.end_date)
    summary=study.grid.metrics(result,4000.)
    with pytest.raises((ValueError,AssertionError)):study.session_audit(result,summary,metadata,tape)


def test_installation_restores_all_original_functions():
    old=(study.runner.ROOT,study.runner.ARM,study.runner.prepare,study.runner.with_cycle,
        study.runner.bridge,study.runner.shared.scope,study.cycle.audit)
    with study.installed():assert study.cycle.audit is study.session_audit
    assert old==(study.runner.ROOT,study.runner.ARM,study.runner.prepare,study.runner.with_cycle,
        study.runner.bridge,study.runner.shared.scope,study.cycle.audit)
