import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from ihm.services import pipeline_unlock as recovery
from service.options_directional.accounts import BINDING_PROTOCOL
from service.options_directional.store import digest


@pytest.fixture
def context(tmp_path,monkeypatch):
    monkeypatch.setattr(recovery,'require_paper_account',lambda account:account)
    monkeypatch.setattr(recovery.psutil,'process_iter',lambda attrs:[])
    report=dict(run_id='opt-'+'a'*32,trade_date='2026-10-30')
    folder=tmp_path/'consumer'
    folder.mkdir()
    monkeypatch.setattr(recovery,'consumer_directory',lambda *a:folder)
    monkeypatch.setattr(recovery,'sealed_report',lambda *a:report)
    summary=dict(run_id='risk-1',account_id='test1',options_filter_run_id=report['run_id'],run_mode='paper',dry_run=False)
    binding=dict(account_id='test1',binding_protocol=BINDING_PROTOCOL,risk_run_id='risk-1',
                 report_sha256=digest(report),summary_sha256=digest(summary))
    for name,value in [('risk.claim.json',dict(attempt_id='b'*32,run_id=report['run_id'],account_id='test1',report_sha256=digest(report),started_at='2026-11-01T14:00:00+00:00')),
                       ('risk_summary.json',summary),('risk_binding.json',binding),
                       ('execution.claim.json',dict(attempt_id='c'*32,started_at='2026-11-01T14:01:00+00:00',
                           account_id='test1',run_id=report['run_id'],risk_run_id='risk-1',
                           binding_sha256=digest(binding),report_sha256=digest(report)))]:
        (folder/name).write_text(json.dumps(value),encoding='utf-8')
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        for sql in [
            'CREATE TABLE execution_locks (account_id TEXT PRIMARY KEY,locked_by_run_id TEXT,acquired_at DATETIME,expires_at DATETIME)',
            'CREATE TABLE execution_order_requests (account_id TEXT,risk_run_id TEXT)',
            'CREATE TABLE execution_runs (account_id TEXT,risk_run_id TEXT,status TEXT)',
            'CREATE TABLE execution_winner_campaigns (account_id TEXT,risk_run_id TEXT,campaign_id TEXT,symbol TEXT,active_key TEXT,state_json TEXT)',
            'CREATE TABLE portfolio_targets (account_id TEXT,run_id TEXT,symbol TEXT)',
            "INSERT INTO portfolio_targets VALUES ('test1','risk-1','TARGET')"]:
            conn.exec_driver_sql(sql)
    broker=SimpleNamespace(get_positions=lambda:[],list_orders=lambda **kw:[])
    candidate=dict(kind='execute',account_id='test1',run_id=report['run_id'],label='test')
    return engine,folder,candidate,lambda account:broker


def test_no_locks_means_no_unlock_candidates(context):
    engine,folder,_,_=context
    assert recovery.list_locked_scopes(engine,['test1'])==[]
    candidates=recovery.list_locked_scopes(engine,['test1'],'opt-'+'a'*32)
    assert {c['kind'] for c in candidates}=={'risk','execute'}
    for path in folder.iterdir():
        path.unlink()
    assert recovery.list_locked_scopes(engine,['test1'],'opt-'+'a'*32)==[]


@pytest.mark.parametrize('phase',['risk','execute'])
def test_preview_is_readonly_and_confirmation_archives_exact_scope(context,phase):
    engine,folder,candidate,broker=context
    candidate['kind']=phase
    original={p.name:p.read_bytes() for p in folder.iterdir()}
    preview=recovery.inspect_unlock(engine,candidate,broker_factory=broker)
    assert {p.name:p.read_bytes() for p in folder.iterdir()}==original
    recovery.confirm_unlock(engine,preview,broker_factory=broker)
    archive=next((folder/'manual_rearms').iterdir())
    assert (archive/'authorization.json').is_file()
    assert (archive/'execution.claim.json').read_bytes()==original['execution.claim.json']
    if phase=='execute':
        assert (folder/'risk_binding.json').read_bytes()==original['risk_binding.json']
    else:
        assert not (folder/'risk_binding.json').exists()
    with engine.connect() as conn:
        assert conn.execute(text('SELECT COUNT(*) FROM execution_locks')).scalar_one()==0
        assert conn.execute(text('SELECT COUNT(*) FROM portfolio_targets')).scalar_one()==1


@pytest.mark.parametrize('sql,reason',[
    ("INSERT INTO execution_order_requests VALUES ('test1','risk-1')",'Ordres déjà'),
    ("INSERT INTO execution_runs VALUES ('test1','risk-1','RUNNING')",'Ordres déjà'),
])
def test_published_orders_or_running_execution_cannot_be_unlocked(context,sql,reason):
    engine,folder,candidate,broker=context
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)
    with pytest.raises(ValueError,match=reason):
        recovery.inspect_unlock(engine,candidate,broker_factory=broker)
    assert (folder/'execution.claim.json').exists()


def test_broker_open_buy_is_not_treated_as_an_unused_attempt(context):
    engine,folder,candidate,_=context
    broker=SimpleNamespace(get_positions=lambda:[],list_orders=lambda **kw:[dict(symbol='TARGET',side='buy')])
    with pytest.raises(ValueError,match='achat déjà ouvert'):
        recovery.inspect_unlock(engine,candidate,broker_factory=lambda account:broker)
    assert (folder/'execution.claim.json').exists()


def test_unsubmitted_pending_plan_survives_recovery(context):
    engine,folder,candidate,broker=context
    with engine.begin() as conn:
        conn.execute(text('INSERT INTO execution_winner_campaigns VALUES (\'test1\',\'risk-1\',\'wp-1\',\'TARGET\',\'test1|paper|TARGET\',:state)'),
                     dict(state=json.dumps(dict(status='PENDING',operations=[],lots=[]))))
    preview=recovery.inspect_unlock(engine,candidate,broker_factory=broker)
    assert preview['pending_campaigns_preserved']==1
    recovery.confirm_unlock(engine,preview,broker_factory=broker)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT COUNT(*) FROM execution_winner_campaigns')).scalar_one()==1


def test_changed_receipt_requires_new_confirmation(context):
    engine,folder,candidate,broker=context
    preview=recovery.inspect_unlock(engine,candidate,broker_factory=broker)
    claim=json.loads((folder/'execution.claim.json').read_text(encoding='utf-8'))
    claim['attempt_id']='d'*32
    (folder/'execution.claim.json').write_text(json.dumps(claim),encoding='utf-8')
    with pytest.raises(ValueError,match='État modifié'):
        recovery.confirm_unlock(engine,preview,broker_factory=broker)
    assert not (folder/'manual_rearms').exists()


def test_filled_then_closed_broker_buy_cannot_be_mistaken_for_no_effects(context):
    engine,folder,candidate,_=context
    def orders(**kw):
        return [] if kw['status']=='open' else [dict(symbol='TARGET',side='buy',filled_qty='1',filled_at='2026-11-01T14:02:00Z')]
    broker=SimpleNamespace(get_positions=lambda:[],list_orders=orders)
    with pytest.raises(ValueError,match='Achat déjà exécuté'):
        recovery.inspect_unlock(engine,candidate,broker_factory=lambda account:broker)
    assert (folder/'execution.claim.json').exists()


@pytest.mark.parametrize('field,value',[('risk_run_id','another-risk'),('account_id','default')])
def test_claim_cannot_be_unlocked_using_another_risk_or_account(context,field,value):
    engine,folder,candidate,broker=context
    claim=json.loads((folder/'execution.claim.json').read_text(encoding='utf-8'))
    claim[field]=value
    (folder/'execution.claim.json').write_text(json.dumps(claim),encoding='utf-8')
    with pytest.raises(ValueError,match='Verrou d’exécution incompatible'):
        recovery.inspect_unlock(engine,candidate,broker_factory=broker)
    assert (folder/'execution.claim.json').exists()


def test_button_hidden_without_lock_then_requires_explicit_confirmation(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ihm.components import pipeline_unlock as ui
    from ihm.services import watcher_runtime
    candidate=dict(kind='watcher',account_id='test1',run_id=None,label='test1 — Watcher')
    candidates=[]
    calls=[]
    monkeypatch.setattr(watcher_runtime,'list_alpaca_account_ids',lambda:['test1'])
    monkeypatch.setattr(ui,'list_locked_scopes',lambda *a:list(candidates))
    monkeypatch.setattr(ui,'inspect_unlock',lambda *a:dict(candidate=candidate,fingerprint='fingerprint',message='Ancien watcher arrêté.'))
    def apply(*args):
        calls.append(args)
        candidates.clear()
        return 'Verrou libéré'
    monkeypatch.setattr(ui,'confirm_unlock',apply)
    app=AppTest.from_string('''
from types import SimpleNamespace
from ihm.components.pipeline_unlock import render_pipeline_unlock
render_pipeline_unlock(None,SimpleNamespace(options_filter_run_id=None),[])
''').run()
    assert not app.exception and len(app.button)==0
    candidates.append(candidate)
    app.run()
    assert len(app.button)==1
    app.button(key='pipeline_unlock_verify').click().run()
    assert not app.exception
    assert app.button(key='pipeline_unlock_apply').disabled
    app.checkbox(key='pipeline_unlock_confirm_fingerprint').check().run()
    app.button(key='pipeline_unlock_apply').click().run()
    assert not app.exception and len(calls)==1
    assert len(app.button)==0
