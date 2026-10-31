"""Scheduled 11/12 fan-out: no model, broker, watcher or SQL side effects."""
from dataclasses import replace
from datetime import date
import threading
from types import SimpleNamespace

import pytest

from ihm.services import process_registry
from service.forward_pit import us_pipeline,watcher_startup
from service.forward_pit.batch import BatchRunError
from service.options_directional.config import OptionsFilterConfig
from service.llm_directional.config import FilterConfig


@pytest.fixture
def env(monkeypatch,tmp_path):
    policy=dict(steps=[10,11,12],execution_mode='paper',account_id='default')
    state=SimpleNamespace(policy=policy,starts=[],polls=[],watchers=[],listed=0,
        fail_account=None,lost_account=None,start_failure=None,partial=False)
    accounts=[SimpleNamespace(account_id=a,mode=m) for a,m in
        [('default','paper'),('test1','paper'),('live-account','live'),('test2','paper'),('test1','paper')]]
    class Registry:
        def resolve(self,account):
            return next(a for a in accounts if a.account_id==account)
        def list_accounts(self):
            state.listed+=1
            return accounts
    monkeypatch.setattr('service.alpaca.accounts.AccountRegistry',Registry)
    monkeypatch.setattr(us_pipeline,'ROOT',tmp_path)
    monkeypatch.setattr(us_pipeline,'load_pipeline_policy',lambda:policy)
    monkeypatch.setattr(us_pipeline,'session_plan',lambda now:(date(2026,10,28),None))
    monkeypatch.setattr('common.us_signal_date.resolve_us_signal_date',lambda *a:date(2026,10,28))
    monkeypatch.setattr(us_pipeline,'load_filter_config',lambda:FilterConfig(enabled=False))
    monkeypatch.setattr('service.options_directional.config.load_options_filter_config',
        lambda:OptionsFilterConfig(enabled=True,default_oracle_batch_id='model-test'))
    def watcher(engine,options,**kw):
        state.watchers.append(options.account_id)
        return dict(account_id=options.account_id,status='REUSED_HEALTHY')
    monkeypatch.setattr(watcher_startup,'ensure_watcher',watcher)
    def start(options,**kw):
        if options.account_id==state.start_failure:
            raise RuntimeError('busy')
        assert len(state.polls)>=len(state.starts)  # No concurrent account workflow.
        record=dict(options=options,kwargs=kw)
        state.starts.append(record)
        for step in us_pipeline.selected_steps([11,12]):
            kw['before_step'](step,options,threading.Event())
        return SimpleNamespace(run_id='workflow-'+options.account_id)
    def poll(run):
        state.polls.append(run)
        account=run.removeprefix('workflow-')
        if account==state.lost_account:
            return None
        count=len(state.starts[-1]['kwargs']['selected_step_keys'])
        failed=account==state.fail_account
        return dict(status='failed' if failed and not state.partial else 'completed',
            workflow_completed_steps=1 if failed else count,run_summary={'account':account})
    monkeypatch.setattr(process_registry,'start_pipeline_workflow',start)
    monkeypatch.setattr(process_registry,'poll_pipeline_run',poll)
    state.run=lambda dry=False:us_pipeline.execute_pipeline(
        SimpleNamespace(url=SimpleNamespace(database='alpha_trade')),dict(market_code='US_EQ'),
        'test-run',dry)
    return state


def test_default_true_reuses_selection_after_primary_and_counts_every_account(env):
    result=env.run()
    assert [r['options'].account_id for r in env.starts]==['default','test1','test2']
    assert [r['kwargs']['selected_step_keys'] for r in env.starts]==[
        ('ml_predict','risk_management','execution'),('risk_management','execution'),('risk_management','execution')]
    assert len({r['options'].options_filter_run_id for r in env.starts})==1
    assert all(r['options'].ml_predict_batch_id=='model-test' and r['options'].trade_date=='2026-10-28'
        and r['options'].execution_mode=='paper' for r in env.starts)
    assert result.requested==result.persisted==result.received==7
    assert result.details['other_paper_accounts']==['test1','test2']
    assert env.watchers==['default','test1','test2'] and env.listed==1
    assert len(result.details['watcher_before_execution_results'])==3
    assert [r['account_id'] for r in result.details['account_workflows']]==['default','test1','test2']


def test_false_runs_primary_only_and_does_not_enumerate_accounts(env):
    env.policy['run_other_paper_accounts']=False
    result=env.run()
    assert len(env.starts)==1 and env.listed==0
    assert result.requested==result.persisted==3


def test_dry_plan_lists_secondary_commands_without_starting_anything(env):
    result=env.run(True)
    assert result.requested==7 and result.persisted==0
    assert not env.starts and not env.watchers
    for entry in result.details['additional_account_workflows']:
        assert entry['selected_step_numbers']==[11,12]
        for step in entry['steps']:
            command=step['command']
            assert command[command.index('--account')+1]==entry['account_id']
            assert command[command.index('--run-id')+1]==result.details['options']['options_filter_run_id']


@pytest.mark.parametrize('bad',[None,0,1,'true','false',[]])
def test_invalid_boolean_rejected_before_workflow(env,bad):
    env.policy['run_other_paper_accounts']=bad
    with pytest.raises(ValueError,match='must be boolean'):env.run()
    assert not env.starts


@pytest.mark.parametrize('account,completed,starts',[('default',1,1),('test1',4,2)])
def test_account_failure_stops_chain_without_replaying_or_resetting_primary(env,account,completed,starts):
    env.fail_account=account
    with pytest.raises(BatchRunError,match='account='+account) as error:env.run()
    assert len(env.starts)==starts
    assert error.value.outcome.persisted==completed and error.value.outcome.requested==7
    assert error.value.outcome.details['failed_account_id']==account
    assert error.value.outcome.failed==1


def test_incomplete_primary_success_never_starts_other_accounts(env):
    env.fail_account='default';env.partial=True
    with pytest.raises(BatchRunError):env.run()
    assert len(env.starts)==1


def test_lost_secondary_monitoring_does_not_launch_next_account(env):
    env.lost_account='test1'
    with pytest.raises(BatchRunError,match='monitoring lost') as error:env.run()
    assert len(env.starts)==2 and error.value.outcome.persisted==3


def test_busy_secondary_keeps_primary_success_counters(env):
    env.start_failure='test1'
    with pytest.raises(BatchRunError,match='could not start account=test1') as error:env.run()
    assert len(env.starts)==1 and error.value.outcome.persisted==3
    assert error.value.outcome.details['account_workflows'][0]['status']=='completed'


def test_primary_can_be_another_account_and_is_never_duplicated(env):
    env.policy['account_id']='test1'
    result=env.run()
    assert [r['options'].account_id for r in env.starts]==['test1','default','test2']
    assert result.details['other_paper_accounts']==['default','test2']


@pytest.mark.parametrize('numbers',[[1,2],[10],[10,11],[12]])
def test_missing_11_or_12_never_adds_omitted_steps(env,numbers):
    options=us_pipeline.pipeline_page_default_options(trade_date='2026-10-28')
    assert not us_pipeline.additional_paper_accounts(replace(options,execution_mode='paper'),{},
        us_pipeline.selected_steps(numbers))
    assert env.listed==0


def test_simulation_does_not_activate_secondary_paper_execution(env):
    options=replace(us_pipeline.pipeline_page_default_options(trade_date='2026-10-28'),execution_mode='simulate')
    assert not us_pipeline.additional_paper_accounts(options,{},us_pipeline.selected_steps([11,12]))
    assert env.listed==0


def test_llm_never_silently_falls_back_to_unfiltered_secondary_execution(env):
    options=replace(us_pipeline.pipeline_page_default_options(trade_date='2026-10-28'),
        execution_mode='paper',llm_filter_enabled=True)
    with pytest.raises(ValueError,match='run_other_paper_accounts: false'):
        us_pipeline.additional_paper_accounts(options,{},us_pipeline.selected_steps([11,12]))
    assert not env.starts and env.listed==0
