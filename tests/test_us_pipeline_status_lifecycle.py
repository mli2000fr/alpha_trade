"""Database-width and finalization regressions; SQLite only, no workflow/orders."""
import json

import pytest
from sqlalchemy import create_engine, text

from service.forward_pit import batch


@pytest.fixture
def env(monkeypatch):
    engine=create_engine('sqlite://')
    # Match the real VARCHAR(24) bound, which SQLite would not enforce alone.
    with engine.begin() as conn:
        conn.execute(text('''CREATE TABLE pit_collection_runs (
            run_id TEXT PRIMARY KEY,batch_name TEXT,provider TEXT,
            status TEXT NOT NULL CHECK(length(status)<=24),started_at DATETIME,
            finished_at DATETIME,error_message TEXT,requested_count INTEGER,
            received_count INTEGER,persisted_count INTEGER,empty_count INTEGER,
            failed_count INTEGER,warning_count INTEGER,details_json TEXT)'''))
    # Runtime DB guard without changing the SQLite engine's actual URL.
    class Engine:
        from types import SimpleNamespace
        url=SimpleNamespace(database='alpha_trade')
        def begin(self):return engine.begin()
    monkeypatch.setattr(batch,'load_batch_config',lambda *a:{'us_pipeline':{'enabled':True,'provider':'local'}})
    monkeypatch.setattr(batch,'get_sqlalchemy_engine',lambda:Engine())
    yield engine
    engine.dispose()


@pytest.mark.parametrize('reason',['SESSION_NOT_CLOSED','NON_TRADING_DAY'])
def test_skip_is_short_terminal_status_with_exact_reason(env,monkeypatch,reason):
    monkeypatch.setitem(batch.HANDLERS,'us_pipeline',lambda *a:batch.Outcome(details={'skip_reason':reason}))
    status,outcome=batch.execute('us_pipeline')
    assert status=='SKIPPED'
    with env.connect() as conn:
        row=conn.execute(text('SELECT * FROM pit_collection_runs')).mappings().one()
    assert row['status']=='SKIPPED' and row['finished_at'] is not None
    assert json.loads(row['details_json'])['skip_reason']==reason
    assert row['failed_count']==row['requested_count']==0


def test_finalization_error_seals_failed_and_preserves_outcome(env,monkeypatch):
    # Reject normal finalization, while allowing the FAILED repair transaction.
    with env.begin() as conn:
        conn.execute(text('''CREATE TRIGGER reject_complete BEFORE UPDATE ON pit_collection_runs
            WHEN NEW.status='COMPLETED' BEGIN SELECT RAISE(ABORT,'test finalization failure'); END'''))
    monkeypatch.setitem(batch.HANDLERS,'us_pipeline',lambda *a:batch.Outcome(requested=5,persisted=3,details={'proof':'retained'}))
    with pytest.raises(Exception,match='test finalization failure'):
        batch.execute('us_pipeline')
    with env.connect() as conn:
        row=conn.execute(text('SELECT * FROM pit_collection_runs')).mappings().one()
    assert row['status']=='FAILED' and row['finished_at'] is not None
    assert row['requested_count']==5 and row['persisted_count']==3
    assert json.loads(row['details_json'])['proof']=='retained'


def test_skipped_run_not_eligible_for_successful_recovery_gate(env,monkeypatch):
    monkeypatch.setitem(batch.HANDLERS,'us_pipeline',lambda *a:batch.Outcome(details={'skip_reason':'SESSION_NOT_CLOSED'}))
    batch.execute('us_pipeline')
    with env.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM pit_collection_runs WHERE status IN ('COMPLETED','COMPLETED_WITH_WARNINGS')")).scalar()==0


def test_precise_orphan_repair_refuses_other_rows_or_missing_terminal_evidence():
    from scripts.research.us_pipeline_skip_reconcile import RUN_ID,START,validate
    row=dict(run_id=RUN_ID,batch_name='us_pipeline',started_at=START,status='RUNNING',finished_at=None)
    log=RUN_ID+" 'status': 'SKIPPED_SESSION_NOT_CLOSED' [2026-10-21 09:29:17] FIN us_pipeline status=ERROR exit=1"
    validate(row,log)
    for change in ({'run_id':'different'},{'status':'COMPLETED'},{'finished_at':START},{'started_at':None}):
        with pytest.raises(ValueError):validate({**row,**change},log)
    with pytest.raises(ValueError):validate(row,'only a START log')
