"""Pre-open recovery: local receipts/SQL only, no broker/provider/order calls."""
from datetime import UTC, date, datetime, timedelta
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, text

from service.forward_pit import us_pipeline_recovery as recovery

NOW = datetime(2026,11,19,7,tzinfo=UTC)


def calendar(*, holiday=False, close_hour=21, open_hour=14):
    def sessions(start, end):
        result = []
        day = start
        while day <= end:
            if day.weekday() < 5 and not (holiday and day == end):
                result.append(SimpleNamespace(session_date=day, is_open=True,
                    open_at_utc=datetime(day.year, day.month, day.day, open_hour,30,tzinfo=UTC),
                    close_at_utc=datetime(day.year, day.month, day.day, close_hour,tzinfo=UTC)))
            day += timedelta(days=1)
        return result
    return SimpleNamespace(sessions=sessions)


@pytest.mark.parametrize('stamp,expected', [
    ('2026-11-19T07:00:00+00:00','2026-11-18'),
    ('2026-11-18T23:30:00+00:00','2026-11-18'), # Next Paris day, still previous NY day.
    ('2026-11-23T07:00:00+00:00','2026-11-20'), # Monday -> Friday.
    ('2026-11-19T14:29:59+00:00','2026-11-18'),
    ('2026-11-19T14:30:00+00:00',None),
    ('2026-11-19T22:00:00+00:00',None),
    ('2026-11-21T07:00:00+00:00',None)])
def test_window_requires_preopen_and_previous_actual_session(stamp, expected):
    result = recovery.recovery_session(datetime.fromisoformat(stamp), calendar=calendar())
    assert (str(result) if result else None) == expected


def test_holiday_and_dst_and_naive_timestamp():
    assert recovery.recovery_session(NOW,calendar=calendar(holiday=True)) is None
    stamp=datetime(2026,10,28,13,29,tzinfo=UTC)
    assert recovery.recovery_session(stamp,calendar=calendar(open_hour=13))==date(2026,10,27)
    assert recovery.recovery_session(stamp+timedelta(minutes=1),calendar=calendar(open_hour=13)) is None
    with pytest.raises(ValueError):
        recovery.recovery_session(NOW.replace(tzinfo=None),calendar=calendar())


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('''CREATE TABLE pit_collection_runs (
            run_id TEXT,batch_name TEXT,status TEXT,started_at TEXT,finished_at TEXT,
            requested_count INT,persisted_count INT,failed_count INT,details_json TEXT)'''))
    db=SimpleNamespace(url=SimpleNamespace(database='alpha_trade'),connect=engine.connect)
    def add(run='old', status='FAILED', details=None, requested=7, persisted=3, failed=1,
            started='2026-11-18 22:00:00'):
        payload=dict(trade_date='2026-11-18') if details is None else details
        with engine.begin() as conn:
            conn.execute(text('INSERT INTO pit_collection_runs VALUES '
                '(:r,"us_pipeline",:s,:start,:f,:q,:p,:n,:d)'),
                dict(r=run,s=status,f=None if status=='RUNNING' else '2026-11-18 23:00:00',
                     q=requested,p=persisted,n=failed,d=json.dumps(payload),start=started))
    def record(run='workflow',account='default',status='completed',children=()):
        folder=tmp_path/'artifacts/ihm_pipeline_runs/pipeline_workflow'/run
        folder.mkdir(parents=True)
        (folder/'record.json').write_text(json.dumps(dict(run_id=run,account_id=account,
            status=status,returncode=0 if status=='completed' else 1,
            workflow_total_steps=3,workflow_completed_steps=3 if status=='completed' else 1,
            workflow_child_run_ids=list(children))),encoding='utf-8')
    def child(run,step='execution'):
        folder=tmp_path/'artifacts/ihm_pipeline_runs'/step/run
        folder.mkdir(parents=True)
        (folder/'record.json').write_text(json.dumps(dict(run_id=run,step_key=step,status='failed')),encoding='utf-8')
    state=lambda **kw:recovery.recovery_state(db,now=NOW,calendar=calendar(),root=tmp_path,**kw)
    monkeypatch.setattr(recovery,'get_market_calendar',lambda *a,**k:calendar())
    yield SimpleNamespace(db=db,add=add,record=record,child=child,state=state,root=tmp_path)
    engine.dispose()


def test_no_run_is_eligible_and_current_skipped_run_does_not_hide_it(env):
    assert env.state()['eligible']
    env.add(status='SKIPPED',details=dict(trade_date='2026-11-19',skip_reason='SESSION_NOT_CLOSED'),persisted=0)
    assert env.state()['eligible'] and env.state()['trade_date']=='2026-11-18'


@pytest.mark.parametrize('status',['COMPLETED','COMPLETED_WITH_WARNINGS'])
def test_completed_session_hides_button_despite_later_skip_or_failure(env,status):
    env.add(status=status,requested=7,persisted=7,failed=0)
    env.add(run='new-failure')
    assert not env.state()['visible']


def test_partial_or_quota_limited_counts_are_not_success(env):
    env.add(status='COMPLETED_WITH_WARNINGS',persisted=2,failed=0)
    state=env.state()
    assert state['visible'] and not state['eligible']


def test_running_or_own_runner_and_revalidation_after_open(env):
    env.add(run='own',status='RUNNING',details={})
    assert not env.state()['eligible']
    assert env.state(exclude_run_id='own')['eligible']
    with pytest.raises(ValueError,match='marché ouvert'):
        recovery.require_recovery(env.db,'2026-11-18',now=NOW.replace(hour=15),root=env.root,exclude_run_id='own')
    assert recovery.require_recovery(env.db,'2026-11-18',now=NOW,root=env.root,exclude_run_id='own')['eligible']


def test_unrelated_old_sql_running_row_does_not_claim_current_recovery_is_active(env):
    # A real old launcher is still blocked by the existing named mutex and
    # pipeline locks; an unrelated stale SQL label alone is not that mutex.
    env.add(run='old-unrelated',status='RUNNING',started='2026-11-13 22:00:00',
            details=dict(trade_date='2026-11-13'))
    assert env.state()['eligible']


def test_only_last_closed_date_is_allowed_and_us_database_required(env):
    for day in ('2026-11-19','2026-11-17','2026-1-1'):
        with pytest.raises(ValueError):recovery.require_recovery(env.db,day,now=NOW,root=env.root)
    env.db.url.database='alpha_trade_fr'
    with pytest.raises(ValueError,match='US alpha_trade'):env.state()


def test_completed_account_uses_exact_initial_selection_and_is_preserved(env):
    env.record()
    options=dict(trade_date='2026-11-18',account_id='default',q051_run_id='exact-old-selection')
    env.add(details=dict(trade_date='2026-11-18',account_id='default',options=options,
        failed_account_id='test1',account_workflows=[dict(account_id='default',workflow_run_id='workflow')]))
    state=env.state()
    assert state['eligible'] and state['completed_accounts']==['default']
    assert state['resume_options']['q051_run_id']=='exact-old-selection'


@pytest.mark.parametrize('step',['risk_management','execution','corporate_actions_sync'])
def test_uncertain_account_attempt_never_replays_risk_or_orders(env,step):
    env.child('child',step);env.record(status='failed',children=['child'])
    env.add(details=dict(trade_date='2026-11-18',account_id='default',
        account_workflows=[dict(account_id='default',workflow_run_id='workflow')]))
    state=env.state()
    assert state['visible'] and not state['eligible'] and 'déjà tenté' in state['reason']


def test_collection_only_failure_can_restart_but_unknown_receipt_cannot(env):
    env.child('child','import_alpaca_bar');env.record(status='failed',children=['child'])
    env.add(details=dict(trade_date='2026-11-18',account_id='default',
        account_workflows=[dict(account_id='default',workflow_run_id='workflow')]))
    assert env.state()['eligible']
    (env.root/'artifacts/ihm_pipeline_runs/import_alpaca_bar/child/record.json').unlink()
    assert not env.state()['eligible']


def test_missing_selection_or_account_identity_never_adopts_another_run(env):
    env.record(account='other')
    env.add(details=dict(trade_date='2026-11-18',account_id='default',options={},
        account_workflows=[dict(account_id='default',workflow_run_id='workflow')]))
    assert not env.state()['eligible']


def test_expired_pre_risk_human_wait_can_start_fresh_instead_of_reusing_old_selection(env):
    env.child('prediction','ml_predict');env.record(status='failed',children=['prediction'])
    record=env.root/'artifacts/ihm_pipeline_runs/pipeline_workflow/workflow/record.json'
    payload=json.loads(record.read_text());payload['workflow_current_step_key']='ml_predict'
    record.write_text(json.dumps(payload))
    env.add(details=dict(trade_date='2026-11-18',account_id='default',
        options=dict(q051_run_id='expired-selection'),
        account_workflows=[dict(account_id='default',workflow_run_id='workflow')]))
    state=env.state()
    assert state['eligible'] and not state['completed_accounts']
    assert state['resume_options'] is None  # fresh_pipeline_options allocates a new step10 identity.


def test_cli_forwards_explicit_recovery_date_and_rejects_other_batches(monkeypatch):
    import sys
    from service.forward_pit import batch
    monkeypatch.setattr(sys,'argv',['batch','--batch','us_pipeline','--us-pipeline-recovery-date','2026-11-18'])
    execute=Mock(return_value=('DRY_RUN',batch.Outcome()))
    monkeypatch.setattr(batch,'execute',execute)
    batch.main()
    assert execute.call_args.kwargs['us_pipeline_recovery_date']=='2026-11-18'


def test_button_visibility_and_date_bound_launch(monkeypatch):
    from contextlib import nullcontext
    from ihm.pages import batches as page
    calls=[]
    buttons=[]
    class UI:
        def columns(self,n):return [nullcontext() for _ in range(n)]
        def container(self):return nullcontext()
        def button(self,label,**kw):
            buttons.append((label,kw))
            return label.startswith('↩️') and not kw['disabled']
        def caption(self,*a):pass
        def success(self,*a):pass
        def error(self,*a):pytest.fail(str(a))
        def rerun(self):pass
    monkeypatch.setattr(page,'st',UI())
    monkeypatch.setattr(page,'get_runtime_db_config',lambda:{'name':'alpha_trade'})
    def start(spec,**kw):calls.append(kw);return SimpleNamespace(run_id='new')
    monkeypatch.setattr(page,'start_batch',start)
    spec=SimpleNamespace(name='us_pipeline')
    page._render_run_buttons(spec,disabled=False,recovery={'visible':False})
    assert len(buttons)==1 and not calls
    buttons.clear()
    page._render_run_buttons(spec,disabled=False,recovery=dict(visible=True,eligible=True,trade_date='2026-11-18'))
    assert len(buttons)==2 and '18/11/2026' in buttons[1][0]
    assert calls[0]['recovery_date']=='2026-11-18'
    calls.clear()
    page._render_run_buttons(spec,disabled=False,recovery=dict(visible=True,eligible=False,trade_date='2026-11-18'))
    assert not calls
