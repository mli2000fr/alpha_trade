"""Human subset publication, exact binding, expiry and pause/resume; no broker."""
from datetime import UTC,datetime,timedelta
import json
from types import SimpleNamespace
import threading

import pandas as pd
import pytest

from service.q051_paper import pipeline as p,human_selection as human
from service.llm_directional.prompts import PROBABILITY_VERSION
from common.q051_paper import reference


@pytest.fixture
def proposal(tmp_path,monkeypatch):
    monkeypatch.setattr(human,'selection_policy',lambda:dict(require_qualified_evidence=True))
    monkeypatch.setattr(p,'ARTIFACTS',tmp_path)
    run='q051-'+'a'*32;folder=tmp_path/run;folder.mkdir()
    frame=pd.DataFrame(dict(symbol=['A','B','C'],rank=[1,2,3],oracle_rank=[1,2,3],
        selected_before_llm=[True,True,True],selected=[True,True,False],
        llm_probability_up_without_stop=[.6,.9,None],llm_evidence_quality=['SUFFICIENT','SUFFICIENT','INSUFFICIENT'],
        llm_explanation=['a','b','unknown'],llm_blockers=['','','no evidence']))
    frame.to_parquet(folder/'selection.parquet')
    profile=reference('q051_b_witness_v1')
    receipt=dict(protocol=PROBABILITY_VERSION,approval_required=True,run_id='llm-example',input_sha256='input',
        requested=3,selected=['A','B'],horizon=10,contract={'horizon_sessions':10,'stop_loss_pct':.05,'exit_session':11},
        approval_expires_at=(datetime.now(UTC)+timedelta(hours=1)).isoformat())
    report=dict(status='COMPLETED',run_id=run,trade_date='2026-11-19',batch_id='oracle-test',cutoff='2026-11-19T22:00:00+00:00',
        strategy_profile=profile['profile_id'],profile=profile,llm_filter=receipt,selected=['A','B'],
        selection_sha256=p.digest(folder/'selection.parquet'))
    (folder/'selection.json').write_text(json.dumps(report),encoding='utf-8')
    (folder/'seal.json').write_text(json.dumps({'report_sha256':p.digest(folder/'selection.json')}))
    monkeypatch.setattr(p,'qualified',lambda *a,**k:(folder,report))
    return folder,report,frame


def test_risk_cannot_start_before_explicit_human_choice(proposal):
    folder,report,frame=proposal
    with pytest.raises(ValueError,match='Validation manuelle'):
        human.effective(folder,report,frame)
    with pytest.raises(ValueError,match='Validation manuelle'):
        p.risk(None,folder,report,'default',__import__('datetime').date(2026,11,19))
    assert not (folder/'accounts').exists()


def test_human_selection_is_atomic_idempotent_and_sorted_by_probability(proposal):
    folder,report,frame=proposal
    value=human.approve(None,report['run_id'],['A','B'])
    assert value['selected_symbols']==['B','A']
    assert human.approve(None,report['run_id'],['B','A'])==value
    updated,effective=human.effective(folder,report,frame)
    assert updated['selected']==['B','A']
    assert effective[effective.selected].sort_values('rank').symbol.tolist()==['B','A']
    assert report['selected']==['A','B'] and p.digest(folder/'selection.parquet')==report['selection_sha256']
    with pytest.raises(ValueError,match='déjà'):
        human.approve(None,report['run_id'],['A'])


@pytest.mark.parametrize('symbols',[['C'],['OTHER'],['A','A']])
def test_unqualified_unknown_and_duplicate_symbols_are_rejected(proposal,symbols):
    _,report,_=proposal
    with pytest.raises(ValueError):human.approve(None,report['run_id'],symbols)


def test_empty_human_selection_explicitly_cancels_all_entries(proposal):
    folder,report,frame=proposal
    human.approve(None,report['run_id'],[])
    updated,effective=human.effective(folder,report,frame)
    assert updated['selected']==[] and not effective.selected.any()


def test_read_only_choice_validation_does_not_publish_or_resume(proposal):
    folder,report,frame=proposal
    _,_,_,ordered=human.validate_choice(None,report['run_id'],['A','B'])
    assert ordered==['B','A']
    assert human.validate_choice(None,report['run_id'],[])[-1]==[]
    with pytest.raises(ValueError,match='qualifiés'):
        human.validate_choice(None,report['run_id'],['C'])
    assert not human.approval_path(folder).exists() and not (folder/'accounts').exists()


def test_ui_explains_rejected_symbols_and_keeps_error_after_automatic_refresh(proposal,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ihm.components import probability_selection as ui,prediction_review_table as table
    folder,report,frame=proposal
    monkeypatch.setattr(ui,'_test_proposal',proposal,raising=False)
    monkeypatch.setattr(table,'_table_component',lambda **kw:SimpleNamespace(selected_symbols=['C']))
    monkeypatch.setattr('ihm.services.db.get_engine',lambda:pytest.fail('No SQL qualification for an already unqualified checkbox'))
    app=AppTest.from_string('''
from ihm.components.probability_selection import render,_test_proposal
render(*_test_proposal)
''').run(timeout=30)
    next(b for b in app.button if b.label=='Valider la sélection').click().run(timeout=30)
    assert not app.exception and any('preuves non qualifiées pour C' in e.value for e in app.error)
    app.run(timeout=30)
    assert not app.exception and any('étapes 11/12 restent en attente' in e.value for e in app.error)
    assert not human.approval_path(folder).exists() and not (folder/'accounts').exists()


def test_expired_or_tampered_approval_is_not_reused(proposal):
    folder,report,frame=proposal
    human.approve(None,report['run_id'],['A'])
    with pytest.raises(ValueError,match='expirée'):
        human.read(folder,report,frame,now=datetime.now(UTC)+timedelta(days=1))
    value=json.loads(human.approval_path(folder).read_text());value['run_id']='q051-other'
    human.approval_path(folder).write_text(json.dumps(value))
    with pytest.raises(ValueError,match='incompatible'):human.read(folder,report,frame)


def test_workflow_gate_waits_then_resumes_and_is_cancelable(proposal):
    folder,report,frame=proposal
    options=SimpleNamespace(q051_run_id=report['run_id'],ml_predict_batch_id=report['batch_id'],trade_date=report['trade_date'])
    class Event:
        def is_set(self):return False
        def wait(self,seconds):human.approve(None,report['run_id'],['B'])
    result=human.wait_for_selection(options,Event())
    assert result['status']=='HUMAN_SELECTION_VALIDATED' and result['count']==1
    stopped=threading.Event();stopped.set()
    assert human.wait_for_selection(options,stopped)['status']=='STOPPED_WAITING_HUMAN_SELECTION'


def test_expiration_while_waiting_requires_new_analysis_and_never_approves(proposal,monkeypatch):
    folder,report,_=proposal
    options=SimpleNamespace(q051_run_id=report['run_id'],ml_predict_batch_id=report['batch_id'],trade_date=report['trade_date'])
    original=human.check_expiry
    waited=[]
    class Event:
        def is_set(self):return False
        def wait(self,seconds):waited.append(seconds)
    def advancing_expiry(value):
        original(value,now=datetime.now(UTC)+timedelta(days=1) if waited else None)
    monkeypatch.setattr(human,'check_expiry',advancing_expiry)
    with pytest.raises(ValueError,match='nouveau batch ou pipeline'):
        human.wait_for_selection(options,Event())
    assert waited==[1.] and not human.approval_path(folder).exists()
    assert not (folder/'accounts').exists()


def test_ui_displays_probability_sorted_checkboxes_without_automatic_choice(proposal,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ihm.components import probability_selection as ui
    folder,report,frame=proposal
    monkeypatch.setattr(ui,'_test_proposal',proposal,raising=False)
    app=AppTest.from_string('''
from ihm.components.probability_selection import render,_test_proposal
from ihm.components.prediction_review_table import _registered_table_component
_registered_table_component.clear()
render(*_test_proposal)
''').run(timeout=30)
    assert not app.exception
    data=json.loads(app.get('bidi_component')[0].proto.json)
    assert [r['symbol'] for r in data['rows']]==['B','A','C']
    assert data['selected_symbols']==[]
    assert any(button.label=='Valider la sélection' for button in app.button)
    assert not human.approval_path(folder).exists()
    monkeypatch.setattr('ihm.services.db.get_engine',lambda:None)
    next(b for b in app.button if b.label=='Valider la sélection').click().run(timeout=30)
    assert not app.exception
    assert human.read(folder,report,frame)['selected_symbols']==[]


def test_pending_proposal_stays_visible_after_calendar_rollover(proposal,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ihm.components import pipeline_batch_defaults as ui
    from ihm.services.pipeline_runner import PipelineLaunchOptions
    folder,report,_=proposal
    options=PipelineLaunchOptions(q051_paper_enabled=True,q051_profile_id=report['strategy_profile'],
        ml_predict_batch_id=report['batch_id'],trade_date='2026-11-20',account_id='default')
    view=SimpleNamespace(options=options,other_accounts=())
    monkeypatch.setattr(ui,'load_defaults',lambda:view)
    app=AppTest.from_string('''
from ihm.components.pipeline_batch_defaults import render_selection,load_defaults
from ihm.components.prediction_review_table import _registered_table_component
_registered_table_component.clear()
render_selection(load_defaults())
''').run(timeout=30)
    assert not app.exception
    data=json.loads(app.get('bidi_component')[0].proto.json)
    assert [r['symbol'] for r in data['rows']]==['B','A','C']
    assert any('TOP Oracle — avis GPT / DeepSeek' in m.value for m in app.markdown)
    assert any('Validation possible jusqu’au' in c.value for c in app.caption)
    assert not human.approval_path(folder).exists()


@pytest.mark.parametrize('waive_evidence',[False,True])
def test_human_subset_is_bound_into_real_risk_and_execution(tmp_path,monkeypatch,waive_evidence):
    from tests.test_q051_paper_profile import risk_fixture
    from datetime import date
    module,engine,repo,broker,folder,_=risk_fixture(tmp_path,monkeypatch)
    run='q051-'+'b'*32
    frame=pd.read_parquet(folder/'selection.parquet').assign(oracle_rank=1,selected_before_llm=True,
        llm_probability_up_without_stop=.7)
    if waive_evidence:
        frame=frame.assign(selected=False,llm_evidence_quality='PARTIAL',llm_blockers='evidence_partial')
    monkeypatch.setattr(human,'selection_policy',lambda:dict(require_qualified_evidence=not waive_evidence))
    frame.to_parquet(folder/'selection.parquet')
    report=dict(run_id=run,strategy_profile=reference()['profile_id'],batch_id='batch',trade_date='2026-10-16',
        selected=[] if waive_evidence else ['TEST'],selection_sha256=p.digest(folder/'selection.parquet'),
        llm_filter=dict(approval_required=True,input_sha256='input',selected=[] if waive_evidence else ['TEST'],
                       approval_expires_at=(datetime.now(UTC)+timedelta(hours=1)).isoformat()))
    (folder/'selection.json').write_text(json.dumps(report))
    monkeypatch.setattr(p,'directory',lambda run_id:folder)
    monkeypatch.setattr(p,'qualified',lambda *a,**kw:(folder,report))
    human.approve(None,run,['TEST'])
    risk=module.risk(engine,folder,report,'default',date(2026,10,16))
    assert risk['targets']==1 and risk['decisions'][0]['shares']==8
    assert risk['human_selection_sha256']==p.digest(human.approval_path(folder))
    # A changed approval cannot reuse risk calculated for a different subset.
    altered=json.loads(human.approval_path(folder).read_text());altered['selected_symbols']=[]
    human.approval_path(folder).write_text(json.dumps(altered))
    with pytest.raises(ValueError,match='validation humaine'):
        module.execute(engine,folder,report,'default',date(2026,10,16))
    broker.submit_intent.assert_not_called()


def test_probability_adapter_proposes_all_qualified_candidates_for_review(monkeypatch):
    from service.q051_paper import probability_filter as module
    from service.llm_directional.config import FilterConfig
    monkeypatch.setattr(module,'config',lambda h,n:FilterConfig(enabled=True,analysis_mode='web_search',
        scoring_mode='long_without_stop_probability',horizon=h,min_confidence=0.))
    calls=[]
    monkeypatch.setattr(module,'contexts',lambda engine,candidates,**kw:[dict(symbol=s) for s in candidates.symbol])
    monkeypatch.setattr(module,'analyze',lambda **kwargs:calls.append(kwargs))
    monkeypatch.setattr('service.pipeline_telegram.notify_llm',lambda *a,**kw:None)
    raw=dict(completed_at=datetime.now(UTC),input_sha256='hash')
    items=[dict(symbol=s,assessment_json=json.dumps(dict(probability_up_without_stop=p,
        probability_stop_touch=.1,probability_positive_exit=.9,
        stop_touch_explanation='Risque de stop.',positive_exit_explanation='Hausse finale.',
        probability_explanation='Joint event',evidence_quality='SUFFICIENT',selection_blockers=[])))
        for s,p in [('A',.6),('B',.8)]]
    monkeypatch.setattr(module,'qualified_selection',lambda *a,**k:(raw,[dict(symbol='A'),dict(symbol='B')]))
    monkeypatch.setattr(module,'Repository',lambda engine:SimpleNamespace(get=lambda run_id:(raw,items)))
    ranked=pd.DataFrame(dict(symbol=['A','B'],selected=True,rank=[1,2],oracle_rank=[1,2]))
    frame,receipt=module.apply(None,ranked,run_id='q051-parent',batch='batch',day=__import__('datetime').date(2026,11,19),horizon=10)
    assert receipt['approval_required'] and frame.selected.all()
    assert receipt['contract']['stop_loss_pct']==.05 and receipt['contract']['exit_session']==11
    from service.llm_directional.prompts import PROBABILITY_BREAKDOWN_VERSION
    assert all(c['analysis_protocol']==PROBABILITY_BREAKDOWN_VERSION and c['analysis_language']=='fr' for c in calls[0]['inputs'])
    assert frame.llm_probability_up_without_stop.tolist()==[.6,.8]
    assert frame.llm_probability_stop_touch.tolist()==[.1,.1]
    assert frame.llm_probability_positive_exit.tolist()==[.9,.9]
