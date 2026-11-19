"""A terminal snapshot must not become a phantom active run at account handoff."""
import threading
from types import SimpleNamespace
import pytest
from ihm.services import process_registry as registry


@pytest.fixture
def isolated(monkeypatch):
    monkeypatch.setattr(registry,'_ACTIVE_RUNS',{})
    monkeypatch.setattr(registry,'_ACTIVE_WORKFLOWS',{})


@pytest.mark.usefixtures('isolated')
@pytest.mark.parametrize('kind',['step','workflow'])
def test_completed_snapshot_removed_during_poll_is_not_reported_active(monkeypatch,kind):
    target=registry._ACTIVE_RUNS if kind=='step' else registry._ACTIVE_WORKFLOWS
    target['old']=object()
    def poll(run):
        target.pop(run)
        return dict(run_id=run,status='completed',is_active=False)
    monkeypatch.setattr(registry,'poll_pipeline_run',poll)
    assert registry.list_active_pipeline_runs()==[]


@pytest.mark.usefixtures('isolated')
@pytest.mark.parametrize('alive',[False,True])
def test_terminal_workflow_exposes_actual_cleanup_barrier(alive):
    record=registry.PipelineRunRecord(run_id='old',step_key='pipeline_workflow',step_label='test',
        command=[],command_display='',account_id='default',status='completed',executed_at='2026-11-19T00:00:00')
    managed=registry._ManagedWorkflow(record=record,thread=SimpleNamespace(is_alive=lambda:alive),
        started_perf=None,stop_event=threading.Event())
    registry._ACTIVE_WORKFLOWS['old']=managed
    snapshot=registry._poll_workflow_run('old',managed)
    assert snapshot['workflow_finalizing'] is alive
    assert bool(registry.list_active_pipeline_runs()) is alive


@pytest.mark.usefixtures('isolated')
@pytest.mark.parametrize('status',['scheduled','starting','running'])
def test_real_active_run_still_blocks(monkeypatch,status):
    registry._ACTIVE_RUNS['active']=object()
    monkeypatch.setattr(registry,'poll_pipeline_run',lambda run:dict(status=status,is_active=True))
    assert len(registry.list_active_pipeline_runs())==1
