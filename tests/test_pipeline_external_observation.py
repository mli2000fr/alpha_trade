"""Cross-process display: no SQL, broker, process mutation or network calls."""
import json
from types import SimpleNamespace
import pytest
from ihm.services import process_registry as registry, pipeline_lock


@pytest.fixture
def external(tmp_path,monkeypatch):
    root=tmp_path/'runs'
    parent_id='20261127_230504_516dac04'
    child_id='20261127_232849_7feb9a57'
    parent=dict(run_id=parent_id,run_kind='workflow',step_key='pipeline_workflow',status='running',
        finished_at=None,executed_at='2026-11-27T23:05:04',workflow_completed_steps=1,
        workflow_total_steps=11,workflow_current_step_key='data_sanitizer_daily',
        workflow_current_child_run_id=child_id,workflow_child_run_ids=[child_id])
    child=dict(run_id=child_id,run_kind='step',step_key='data_sanitizer_daily',status='running',
        finished_at=None,parent_run_id=parent_id,executed_at='2026-11-27T23:28:49')
    def write(row):
        folder=root/row['step_key']/row['run_id'];folder.mkdir(parents=True,exist_ok=True)
        (folder/'record.json').write_text(json.dumps(row),encoding='utf-8')
    write(parent);write(child)
    index=root/'history_index.json'
    index.write_text(json.dumps({row['run_id']:dict(row,status='stopped',stop_requested=True)
                               for row in (parent,child)}),encoding='utf-8')
    monkeypatch.setattr(registry,'RUNS_DIR',root)
    monkeypatch.setattr(registry,'HISTORY_INDEX_PATH',index)
    monkeypatch.setattr(registry,'_ACTIVE_RUNS',{})
    monkeypatch.setattr(registry,'_ACTIVE_WORKFLOWS',{})
    monkeypatch.setattr(registry,'_RECOVERY_DONE',True)
    alive=[True]
    holder=dict(scope='pipeline',owner='pipeline_workflow',run_id=parent_id,pid=999999)
    monkeypatch.setattr(pipeline_lock,'_read_lock',lambda path:holder)
    monkeypatch.setattr(pipeline_lock,'_is_lock_active',lambda row:alive[0])
    return SimpleNamespace(root=root,parent=parent,child=child,index=index,write=write,alive=alive,holder=holder)


def test_external_parent_and_child_are_live_despite_stale_stopped_index(external):
    original=external.index.read_bytes()
    history={r['run_id']:r for r in registry.load_pipeline_history()}
    for row in (external.parent,external.child):
        current=history[row['run_id']]
        assert current['status']=='running' and current['external_process']
        assert registry.get_pipeline_run_record(row['run_id'])['status']=='running'
    active=registry.list_active_pipeline_runs()
    assert {r['run_id'] for r in active}=={external.parent['run_id'],external.child['run_id']}
    assert external.index.read_bytes()==original
    assert not registry._ACTIVE_RUNS and not registry._ACTIVE_WORKFLOWS


def test_progress_read_through_is_fresh_and_terminal_child_is_not_listed_active(external):
    external.parent['workflow_completed_steps']=2
    external.write(external.parent)
    external.child['status']='completed';external.child['finished_at']='2026-11-27T23:35:00'
    external.write(external.child)
    assert registry.get_pipeline_run_record(external.parent['run_id'])['workflow_completed_steps']==2
    assert registry.get_pipeline_run_record(external.child['run_id'])['status']=='completed'
    assert len(registry.list_active_pipeline_runs())==1


@pytest.mark.parametrize('invalid',['dead_or_reused_pid','wrong_owner','wrong_run','terminal_parent','missing_receipt'])
def test_unproved_external_run_is_never_declared_active(external,invalid):
    if invalid=='dead_or_reused_pid':external.alive[0]=False
    elif invalid=='wrong_owner':external.holder['owner']='another-owner'
    elif invalid=='wrong_run':external.holder['run_id']='20261127_235959_deadbeef'
    elif invalid=='terminal_parent':
        external.parent['status']='completed';external.parent['finished_at']='2026-11-27T23:35:00'
        external.write(external.parent)
    else:(external.root/'pipeline_workflow'/external.parent['run_id']/'record.json').unlink()
    assert registry._external_pipeline_records()=={}
    assert not registry.list_active_pipeline_runs()


def test_unrelated_child_is_not_adopted_and_external_stop_is_not_claimed(external):
    external.child['parent_run_id']='another-workflow';external.write(external.child)
    assert set(registry._external_pipeline_records())=={external.parent['run_id']}
    assert registry.stop_pipeline_run(external.parent['run_id']) is False
    assert json.loads((external.root/'pipeline_workflow'/external.parent['run_id']/'record.json').read_text())['status']=='running'
