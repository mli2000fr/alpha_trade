from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from functools import lru_cache

import pandas as pd
import pytest

from scripts.research import us_winner_monthly_cycle15_20261025 as experiment
from tests.test_winner_global_liquidation import data_with_global_drawdown, evaluation, MarkBook
from backtesting.simulator import BacktestEngine


def cycle_config(cfg):
    return replace(cfg,
        risk_config=replace(cfg.risk_config,max_portfolio_drawdown_pct=.15,
            force_close_on_breaker=True,force_close_pct=1.,rolling_peak_window_days=0),
        exec_config=replace(cfg.exec_config,force_close_on_breaker=True,force_close_pct=1.),
        winner_hard_drawdown_pct=None,winner_global_drawdown_halt=False,
        winner_cycle_drawdown_pct=.15,winner_drawdown_cooldown_months=3)


def controller():
    cfg,_,_ = data_with_global_drawdown()
    cfg = cycle_config(cfg)
    return experiment.CycleOnlyLiquidation(cfg,cfg.risk_config,cfg.exec_config)


def test_configuration_changes_only_declared_drawdown_policy(monkeypatch):
    cfg,_,_ = data_with_global_drawdown()
    monkeypatch.setattr(experiment,'BASE_CONFIGURATION',lambda *_:cfg)
    actual = experiment.configuration({},date(2020,1,1))
    assert asdict(actual) == asdict(cycle_config(cfg))
    assert actual.winner_hard_drawdown_pct is None
    assert actual.exec_config.winner_pyramiding == cfg.exec_config.winner_pyramiding
    assert actual.initial_equity == cfg.initial_equity


@pytest.mark.parametrize('field,value',[
    ('winner_hard_drawdown_pct',.25),('winner_cycle_drawdown_pct',.20),
    ('winner_drawdown_cooldown_months',0),('winner_global_drawdown_halt',True),
])
def test_adapter_rejects_wrong_risk_contract(field,value):
    cfg,_,_ = data_with_global_drawdown()
    cfg = replace(cycle_config(cfg),**{field:value})
    with pytest.raises(ValueError,match='Explicit cycle15'):
        experiment.CycleOnlyLiquidation(cfg,cfg.risk_config,cfg.exec_config)


def test_native_old_episode_cannot_trigger_premature_partial_liquidation():
    control = controller(); book = MarkBook()
    control.observe(datetime(2026,10,19,14,tzinfo=timezone.utc),3500.,book,evaluation(True,5000.))
    assert control.pending is None and not control.blocks_entries
    control.observe(datetime(2026,10,19,14,5,tzinfo=timezone.utc),3390.,book,evaluation(False,5000.))
    assert control.pending['reason'] == 'CYCLE_DRAWDOWN'
    assert control.pending['symbols'] == ['AAA','BBB','CCC']
    assert control.pending['force_close_pct'] == 1. and not control.halted


def test_repeated_resets_do_not_recapitalize_or_restore_a_hidden_global_cap():
    control = controller(); book = MarkBook(); book.marks = {}
    store = SimpleNamespace(rows=lambda:[])
    stamp = pd.Timestamp('2027-01-31T15:00Z')
    for index,equity in enumerate([3390.,2800.,2300.]):
        book.equity = lambda value=equity:value
        control.observe(stamp.to_pydatetime(),equity,book,evaluation(False,4000.))
        assert control.blocks_entries and not control.halted
        control.execute(stamp.to_pydatetime(),store,None,book,None)
        due = control.paused_until
        assert not control.resume(due-timedelta(seconds=1),book)
        assert control.resume(due,book)
        assert control.cycle_peak == equity and control.peak == 4000.
        assert control.resumes[-1]['equity'] == equity
        assert not control.halted and not control.blocks_entries
        stamp = pd.Timestamp(due)+pd.Timedelta(days=1)
    assert len(control.events) == len(control.resumes) == 3
    assert control.min_drawdown < -.40
    assert control.summary()['hard_threshold_pct'] is None
    assert control.summary()['reset_deposits'] == 0
    assert control.summary()['rearm'] == 'CYCLE_CALENDAR_COOLDOWN_NO_GLOBAL_HARD_CAP'


def test_pause_clips_month_end_and_prevents_duplicate_triggers():
    control = controller(); book = MarkBook(); book.marks = {}; book.equity = lambda:3390.
    stamp = datetime(2027,1,31,15,tzinfo=timezone.utc)
    control.observe(stamp,3390.,book,evaluation())
    control.observe(stamp+timedelta(minutes=5),3300.,book,evaluation(True))
    assert control.counter == 1
    control.execute(stamp+timedelta(minutes=5),SimpleNamespace(rows=lambda:[]),None,book,None)
    assert control.paused_until == pd.Timestamp('2027-04-30T00:00-04:00')
    control.observe(stamp+timedelta(days=1),3390.,book,evaluation(True))
    assert control.counter == 1 and control.blocks_entries


@lru_cache(maxsize=1)
def cached_replay_fixture():
    cfg,args,raw = data_with_global_drawdown(last=date(2027,1,21))
    cfg = cycle_config(cfg)
    cfg.risk_config = replace(cfg.risk_config,policy='b4')
    args['close']['SPY'] = 100.+pd.Series(range(len(args['close'])),index=args['close'].index)*.01
    for symbol in ('AAA','BBB','CCC'):
        raw[cfg.start_date,symbol].loc[10:,['open','close','high','low']] = [100.,100.,100.1,99.9]
        raw[date(2027,1,19),symbol].loc[1:,['open','close','high','low']] = [106.,106.,106.1,105.9]
    fresh = pd.DataFrame([dict(trade_date=date(2027,1,15),symbol=s,rank=i+1,selected=True)
        for i,s in enumerate(('AAA','BBB','CCC'))])
    args['signals_df'] = pd.concat([args['signals_df'],fresh],ignore_index=True)
    with experiment.installed():
        result = BacktestEngine(cfg).run(**args)
    info = result.tracker_snapshot['winner_replay']['global_liquidation']
    class Tape:
        schedule = {s.session_date:s for s in experiment.study.inputs.sessions(start=date(2026,10,1),end=cfg.end_date)}
        def day(self,symbol,day):
            frame = raw[day,symbol].rename(columns={'timestamp':'bar_timestamp'}).copy()
            frame['bar_end_timestamp'] = frame.bar_timestamp+pd.Timedelta(minutes=5)
            frame['trade_date'] = pd.Timestamp(day)
            frame['session_close'] = pd.Timestamp(self.schedule[day].close_at_utc)
            return frame
        def path(self,symbol,start,end):
            frames = [self.day(symbol,d) for d,s in raw if s == symbol and start.date() <= d <= end.date()]
            f = pd.concat(frames,ignore_index=True)
            return f[f.bar_timestamp.between(start,end)].sort_values('bar_timestamp')
    metadata = {t.campaign_id:dict(policy=asdict(cfg.exec_config.winner_pyramiding),symbol=t.symbol,first_fill_at=t.entry_date)
        for t in result.closed_trades_df.itertuples()}
    buys = result.trade_events_df[result.trade_events_df.event.eq('BUY_FILL')]
    for buy in buys.itertuples():
        # Audit's entry identity can include positions still open at test end.
        if (buy.symbol,pd.Timestamp(buy.time)) not in {(m['symbol'],pd.Timestamp(m['first_fill_at'])) for m in metadata.values()}:
            metadata['open-'+buy.symbol] = dict(policy=asdict(cfg.exec_config.winner_pyramiding),symbol=buy.symbol,first_fill_at=buy.time)
    return cfg,result,info,metadata,Tape()


def replay_fixture():
    # One deterministic replay suffices; every corruption test gets a deep
    # independent result so neither mutations nor cached data can leak.
    cfg,result,info,metadata,tape = cached_replay_fixture()
    cloned = deepcopy(result)
    return cfg,cloned,cloned.tracker_snapshot['winner_replay']['global_liquidation'],deepcopy(metadata),tape


def test_real_replay_resumes_on_official_open_after_holiday_with_fresh_signal():
    cfg,result,info,_,_ = replay_fixture()
    assert info['hard_threshold_pct'] is None and not info['halted']
    assert len(info['events']) == len(info['resumes']) == 1
    assert all(e['reason'] == 'CYCLE_DRAWDOWN' for e in info['events'])
    resume = pd.Timestamp(info['resumes'][0]['resumed_at'])
    assert resume == pd.Timestamp('2027-01-19T14:30Z')
    buys = result.trade_events_df[result.trade_events_df.event.eq('BUY_FILL')]
    times = pd.to_datetime(buys.time,utc=True)
    assert not ((times >= pd.Timestamp(info['events'][0]['detected_at'])) & (times < resume)).any()
    assert (times >= resume).any()
    assert info['resumes'][0]['equity'] == pytest.approx(info['events'][0]['equity_after'])


def test_native_sales_and_resumption_pass_independent_audit(monkeypatch):
    cfg,result,info,metadata,tape = replay_fixture()
    monkeypatch.setattr(experiment.study.inputs,'END',cfg.end_date)
    summary = experiment.study.capacity.grid.metrics(result,4000.)
    checks = experiment.audit(result,summary,metadata,tape)
    assert checks['global_exit_checks'] == 3 and checks['resumes'] == 1
    assert checks['hard_cap_absent']
    assert summary['hard_drawdown_halted'] is False


@pytest.mark.parametrize('fault',['pause','deposit','hard_cap','quantity','new_buy_during_pause','risk_peak_not_reset'])
def test_audit_rejects_corrupted_pause_or_capital(monkeypatch,fault):
    cfg,result,info,metadata,tape = replay_fixture()
    monkeypatch.setattr(experiment.study.inputs,'END',cfg.end_date)
    summary = experiment.study.capacity.grid.metrics(result,4000.)
    if fault == 'pause':
        info['events'][0]['paused_until'] = '2027-01-17T00:00:00-05:00'
    elif fault == 'deposit':
        info['resumes'][0]['equity'] += 1000.
    elif fault == 'hard_cap':
        info['hard_threshold_pct'] = .25
    elif fault == 'quantity':
        info['events'][0]['quantities']['AAA'] += 1
    elif fault == 'risk_peak_not_reset':
        stamp = pd.Timestamp(info['resumes'][0]['resumed_at'])
        rows = pd.to_datetime(result.drawdown_breaker_df.timestamp,utc=True).eq(stamp)
        result.drawdown_breaker_df.loc[rows,'peak'] = 999999.
    else:
        row = result.trade_events_df.index[result.trade_events_df.event.eq('BUY_FILL')][-1]
        result.trade_events_df.loc[row,'time'] = pd.Timestamp('2026-11-02T14:45Z')
    with pytest.raises((ValueError,AssertionError)):
        experiment.audit(result,summary,metadata,tape)


def test_run_local_installation_restores_engine_and_input_preparer():
    import backtesting.winner_global_liquidation as engine
    original = engine.GlobalLiquidation
    before = experiment.study.inputs.prepare,experiment.study.configuration,experiment.study.ROOT
    with experiment.installed():
        assert engine.GlobalLiquidation is experiment.CycleOnlyLiquidation
        assert experiment.study.inputs.prepare is experiment.previous.archived_inputs
    assert engine.GlobalLiquidation is original
    assert before == (experiment.study.inputs.prepare,experiment.study.configuration,experiment.study.ROOT)
