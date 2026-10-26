"""Offline policy amendment and scalar qualification of global portfolio sales."""
from dataclasses import asdict
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.research import us_winner_monthly_drawdown_20261024 as experiment
from tests.test_winner_global_liquidation import data_with_global_drawdown
from backtesting.simulator import BacktestEngine


def test_configuration_only_overrides_declared_global_risk(monkeypatch):
    cfg,_,_=data_with_global_drawdown()
    monkeypatch.setattr(experiment,'BASE_CONFIGURATION',lambda *_:cfg)
    got=experiment.configuration({},date(2020,1,1))
    assert got.winner_hard_drawdown_pct==.25 and not got.winner_global_drawdown_halt
    assert got.risk_config.max_portfolio_drawdown_pct==.15
    assert got.risk_config.rolling_peak_window_days==0
    assert got.exec_config.force_close_on_breaker and got.exec_config.force_close_pct==.5
    assert got.risk_config.force_close_on_breaker and got.risk_config.force_close_pct==.5
    assert got.exec_config.winner_pyramiding==cfg.exec_config.winner_pyramiding
    assert got.cost_round_trip_bps==cfg.cost_round_trip_bps


def test_cooldown_variant_preserves_global25_but_resets_local_cycle(monkeypatch):
    cfg,_,_=data_with_global_drawdown()
    monkeypatch.setattr(experiment,'BASE_CONFIGURATION',lambda *_:cfg)
    monkeypatch.setattr(experiment,'VARIANT','cooldown20')
    got=experiment.configuration({},date(2020,1,1))
    assert got.winner_hard_drawdown_pct==.25
    assert got.winner_cycle_drawdown_pct==.20
    assert got.winner_drawdown_cooldown_months==3
    assert got.risk_config.max_portfolio_drawdown_pct==.15


def test_installation_restores_patches_and_never_uses_old_input_preparer():
    study=experiment.study
    before=(study.ROOT,study.inputs.prepare,study.configuration,study.run_case)
    with experiment.installed():
        assert study.ROOT==experiment.ROOT
        assert study.inputs.prepare is experiment.archived_inputs
        assert study.configuration is experiment.configuration
    assert (study.ROOT,study.inputs.prepare,study.configuration,study.run_case)==before


def audited_fixture():
    cfg,args,raw=data_with_global_drawdown(last=date(2026,10,19))
    result=BacktestEngine(cfg).run(**args)
    summary=experiment.study.capacity.grid.metrics(result,4000.)
    class Tape:
        schedule={s.session_date:s for s in experiment.study.inputs.sessions(start=date(2026,10,1),end=cfg.end_date)}
        def day(self,symbol,day):
            f=raw[day,symbol].rename(columns={'timestamp':'bar_timestamp'}).copy()
            f['bar_end_timestamp']=f.bar_timestamp+pd.Timedelta(minutes=5)
            f['trade_date']=pd.Timestamp(day)
            f['session_close']=pd.Timestamp(self.schedule[day].close_at_utc)
            return f
        def path(self,symbol,start,end):
            parts=[self.day(symbol,d) for d,s in raw if s==symbol and start.date()<=d<=end.date()]
            f=pd.concat(parts,ignore_index=True)
            return f[f.bar_timestamp.between(start,end)].sort_values('bar_timestamp')
    metadata={t.campaign_id:dict(policy=asdict(cfg.exec_config.winner_pyramiding),
        symbol=t.symbol,first_fill_at=t.entry_date) for t in result.closed_trades_df.itertuples()}
    return result,summary,metadata,Tape()


def test_actual_global_sales_pass_independent_scalar_cash_price_fees_audit(monkeypatch):
    result,summary,metadata,tape=audited_fixture()
    monkeypatch.setattr(experiment.study.inputs,'END',date(2026,10,19))
    checks=experiment.audit(result,summary,metadata,tape)
    assert checks['global_exit_checks']==3 and checks['hard_halted']
    assert checks['normal_exit_checks']==0 and checks['buys']==3


@pytest.mark.parametrize('fault',['price','fee','quantity','pending','reentry','threshold'])
def test_independent_audit_rejects_bad_global_result(monkeypatch,fault):
    result,summary,metadata,tape=audited_fixture()
    monkeypatch.setattr(experiment.study.inputs,'END',date(2026,10,19))
    if fault=='price':result.closed_trades_df.loc[0,'exit_price']+=1
    elif fault=='fee':result.closed_trades_df.loc[0,'exit_fees']+=1
    elif fault=='quantity':summary['global_liquidation']['events'][0]['quantities']['AAA']+=1
    elif fault=='pending':summary['global_liquidation']['pending']={'event_id':100}
    elif fault=='threshold':summary['global_liquidation']['hard_threshold_pct']=.20
    elif fault=='reentry':
        event=summary['global_liquidation']['events'][0]
        idx=result.trade_events_df.index[result.trade_events_df.event.eq('BUY_FILL')][0]
        result.trade_events_df.loc[idx,'time']=pd.Timestamp(event['executed_at'])
    with pytest.raises((ValueError,AssertionError)):
        experiment.audit(result,summary,metadata,tape)
