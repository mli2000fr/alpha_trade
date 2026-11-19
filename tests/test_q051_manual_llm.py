"""Explicit manual LLM veto: preserves the B selection/risk/exit contract."""
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from service.q051_paper import llm_filter as veto
from service.llm_directional.config import FilterConfig
from ihm.components import pipeline_batch_defaults as ui
from ihm.services import batch_management
from ihm.services.pipeline_runner import build_pipeline_command, path_directional_options
from service.forward_pit import us_pipeline


@pytest.fixture
def manual_view(monkeypatch):
    monkeypatch.setattr(us_pipeline,'require_paper_account',lambda *a:None)
    monkeypatch.setattr('common.q051_paper.require_paper',lambda *a:None)
    monkeypatch.setattr(us_pipeline,'additional_paper_accounts',lambda *a:('test1','test2'))
    return ui.load_defaults(now=datetime(2026,11,19,22,tzinfo=UTC))


def test_explicit_override_reaches_all_stages_without_changing_scheduled_defaults(manual_view):
    view=manual_view;policy=us_pipeline.load_pipeline_policy()
    ordinary=us_pipeline.fresh_pipeline_options(dict(view.spec.raw_config),policy,date(2026,11,19),view.steps)
    manual=us_pipeline.fresh_pipeline_options(dict(view.spec.raw_config,_manual_q051_llm_filter=True),policy,date(2026,11,19),view.steps)
    assert not ordinary.llm_filter_enabled and manual.llm_filter_enabled
    assert manual.q051_paper_enabled and not manual.llm_specific_protections
    assert manual.q051_profile_id==ordinary.q051_profile_id
    assert manual.ml_live_predict_batch_id==ordinary.ml_live_predict_batch_id
    assert path_directional_options(manual) is manual
    for stage in ['ml_predict','risk_management','execution']:
        command=build_pipeline_command(stage,manual)
        assert ('--llm-filter' in command)==(stage=='ml_predict')
        assert command[3]=='service.q051_paper.pipeline'
        assert command[command.index('--run-id')+1]==manual.q051_run_id


def test_launcher_flag_is_manual_scoped_not_a_yaml_change(manual_view,monkeypatch):
    seen={}
    monkeypatch.setattr(batch_management,'start_managed_run',lambda **kwargs:seen.update(kwargs))
    ui.launch(manual_view,db_config={'name':'alpha_trade'},llm_filter_enabled=True)
    assert seen['command']==batch_management.build_run_command(manual_view.spec)+['-Q051LlmFilter']
    assert '-Q051LlmFilter' not in batch_management.build_run_command(manual_view.spec)
    with pytest.raises(ValueError,match='reprise'):
        ui.launch(manual_view,db_config=None,llm_filter_enabled=True,recovery_date='2026-11-18')
    with pytest.raises(ValueError,match='us_pipeline'):
        batch_management.build_run_command(replace(manual_view.spec,name='other'),q051_llm_filter=True)


def test_runner_flag_reaches_handler_only_for_explicit_us_manual_run(monkeypatch):
    from service.forward_pit import batch
    config={'us_pipeline':dict(enabled=True,market_code='US_EQ')}
    seen=[]
    monkeypatch.setattr(batch,'load_batch_config',lambda *a:config)
    monkeypatch.setattr(batch,'get_sqlalchemy_engine',lambda:SimpleNamespace(url=SimpleNamespace(database='alpha_trade')))
    monkeypatch.setitem(batch.HANDLERS,'us_pipeline',lambda engine,cfg,*a:seen.append(cfg) or batch.Outcome())
    batch.execute('us_pipeline',dry_run=True,us_pipeline_llm_filter=True)
    assert seen[0]['_manual_q051_llm_filter'] is True
    assert '_manual_q051_llm_filter' not in config['us_pipeline']
    seen.clear();batch.execute('us_pipeline',dry_run=True)
    assert '_manual_q051_llm_filter' not in seen[0]
    with pytest.raises(ValueError,match='nouveau lancement'):
        batch.execute('us_pipeline',dry_run=True,us_pipeline_llm_filter=True,us_pipeline_recovery_date='2026-11-18')


def test_shared_page_checkbox_is_available_but_does_not_call_until_launch(manual_view,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(ui,'load_defaults',lambda:manual_view)
    monkeypatch.setattr(ui,'us_pipeline_recovery_state',lambda spec:{'visible':False})
    monkeypatch.setattr(ui,'render_selection',lambda view:None)
    calls=[]
    monkeypatch.setattr(ui,'launch',lambda *a,**kw:calls.append(kw) or SimpleNamespace(run_id='fake'))
    app=AppTest.from_string('''
from ihm.components.pipeline_batch_defaults import render
render(db_config={'name':'alpha_trade'},active_runs=[])
''').run(timeout=30)
    assert not app.exception
    checkbox=app.checkbox(key='pipeline_q051_manual_llm_filter')
    assert not checkbox.disabled and not checkbox.value
    checkbox.check().run(timeout=30)
    assert not calls and not app.exception
    app.button(key='pipeline_launch_us_batch_defaults').click().run(timeout=30)
    assert calls==[dict(db_config={'name':'alpha_trade'},llm_filter_enabled=True)]


def test_manual_permission_false_blocks_shared_ui_option(manual_view,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(ui,'load_defaults',lambda:manual_view)
    monkeypatch.setattr(ui,'us_pipeline_recovery_state',lambda spec:{'visible':False})
    monkeypatch.setattr(ui,'render_selection',lambda view:None)
    monkeypatch.setattr('service.llm_directional.config.load_filter_config',lambda:FilterConfig(manual_opt_in_allowed=False))
    app=AppTest.from_string('''
from ihm.components.pipeline_batch_defaults import render
render(db_config={'name':'alpha_trade'},active_runs=[])
''').run(timeout=30)
    assert not app.exception
    assert app.checkbox(key='pipeline_q051_manual_llm_filter').disabled
    assert not app.checkbox(key='pipeline_q051_manual_llm_filter').value


@pytest.fixture
def fake_llm(monkeypatch):
    calls=[]
    monkeypatch.setattr(veto,'load_filter_config',lambda:FilterConfig(enabled=False,horizon=20))
    monkeypatch.setattr(veto,'contexts',lambda engine,candidates,**kw:[dict(symbol=s) for s in candidates.symbol])
    monkeypatch.setattr(veto,'analyze',lambda **kwargs:calls.append(kwargs))
    monkeypatch.setattr('service.pipeline_telegram.notify_llm',lambda *a,**k:None)
    run={'input_sha256':'input-hash'}
    items=[dict(symbol=s,assessment_json=json.dumps(dict(decision=decision,direction_score=score,
           evidence_quality='SUFFICIENT',selection_blockers=[]))) for s,decision,score in [('A','LONG',9),('B','SHORT',2)]]
    monkeypatch.setattr(veto,'qualified_selection',lambda *a,**k:(run,[dict(symbol='A')]))
    monkeypatch.setattr(veto,'Repository',lambda engine:SimpleNamespace(get=lambda run_id:(run,items)))
    return calls


def ranked():
    return pd.DataFrame(dict(symbol=['A','B','C'],proba_extreme=[.9,.8,.7],oracle_rank=[1,2,3],
                             rank=[1,2,3],selected=[True,True,False],reason=['RETAINED','RETAINED','BELOW_TOP']))


def test_gpt_only_removes_candidates_preserves_order_and_winner(fake_llm):
    before=ranked()
    result,receipt=veto.apply(None,before,run_id='q051-parent',batch='batch',day=date(2026,11,19),horizon=10)
    assert result.loc[result.selected,'symbol'].tolist()==['A']
    assert result.loc[result.selected_before_llm,'symbol'].tolist()==['A','B']
    assert result['rank'].tolist()==before['rank'].tolist()
    assert result.loc[result.symbol=='B','reason'].iloc[0]=='LLM_NOT_RETAINED'
    assert result.loc[result.symbol=='C','reason'].iloc[0]=='BELOW_TOP'
    assert receipt['requested']==2 and receipt['selected']==['A']
    assert len(fake_llm)==1
    cfg=fake_llm[0]['config']
    assert cfg.enabled and cfg.horizon==10 and not cfg.allow_short and cfg.protections is None
    assert [p['symbol'] for p in fake_llm[0]['inputs']]==['A','B']
    assert before.selected.tolist()==[True,True,False]  # No mutation of the parent ranking.


def test_no_candidate_means_no_cloud_call(fake_llm):
    frame=ranked();frame['selected']=False
    result,receipt=veto.apply(None,frame,run_id='q051-parent',batch='batch',day=date(2026,11,19),horizon=10)
    assert not fake_llm and receipt['run_id'] is None and receipt['selected']==[]
    assert not result.selected.any()


def test_failed_analysis_never_publishes_an_unfiltered_fallback(fake_llm,monkeypatch):
    def fail(**kwargs):raise RuntimeError('invalid cloud response')
    monkeypatch.setattr(veto,'analyze',fail)
    with pytest.raises(RuntimeError,match='invalid cloud'):
        veto.apply(None,ranked(),run_id='q051-parent',batch='batch',day=date(2026,11,19),horizon=10)


def test_explicit_manual_permission_can_disable_the_option(monkeypatch):
    monkeypatch.setattr(veto,'load_filter_config',lambda:FilterConfig(manual_opt_in_allowed=False))
    with pytest.raises(ValueError,match='interdite'):
        veto.manual_config(10,5)


def test_validate_rejects_changed_parent_or_new_candidates(monkeypatch):
    frame=ranked();frame['selected_before_llm']=frame.selected;frame['selected']=[True,False,False]
    parent='q051-parent';day=date(2026,11,19)
    run=dict(input_sha256='hash',batch_id='batch',input_json=json.dumps(dict(symbol_source='q051-selection:'+parent,
        candidates=[dict(symbol=s,parent_q051_run_id=parent) for s in ['A','B']])),
        config_json=json.dumps(dict(horizon=10,allow_short=False)))
    monkeypatch.setattr(veto,'qualified_selection',lambda *a,**k:(run,[dict(symbol='A')]))
    report=dict(run_id=parent,batch_id='batch',profile={'winner':{'horizon_sessions':10}},
        llm_filter=dict(enabled=True,run_id='llm-example',input_sha256='hash',horizon=10,selected=['A']))
    veto.validate(None,report,frame,day)
    for change in ['parent','horizon','selection']:
        altered=deepcopy(report)
        if change=='parent':altered['run_id']='another'
        if change=='horizon':altered['llm_filter']['horizon']=20
        if change=='selection':altered['llm_filter']['selected']=['A','C']
        with pytest.raises(ValueError,match='altérée'):veto.validate(None,altered,frame,day)


def test_input_packet_reads_only_j_and_earlier_not_future_labels(monkeypatch):
    from sqlalchemy import create_engine,text,event
    from service.llm_directional import fresh_evidence
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE stock_metadata(symbol TEXT,company_name TEXT,exchange TEXT)'))
        conn.execute(text('CREATE TABLE stock_bars_daily(symbol TEXT,date TEXT,close REAL,is_filled INTEGER)'))
        conn.execute(text("INSERT INTO stock_metadata VALUES('A','Example','NYSE')"))
        conn.execute(text("INSERT INTO stock_bars_daily VALUES('A','2026-11-19',100,0),('A','2026-11-20',200,0)"))
    queries=[]
    event.listen(engine,'before_cursor_execute',lambda conn,cursor,sql,*a:queries.append(sql))
    monkeypatch.setattr('common.daily_bar_sources.daily_source_filter',lambda:('',{}))
    monkeypatch.setattr(fresh_evidence,'enrich_contexts',lambda engine,contexts,*a:contexts)
    frame=ranked().iloc[:1].assign(future_return=1.0,oracle_extreme10=True)
    packets=veto.contexts(engine,frame,day=date(2026,11,19),horizon=10,config=FilterConfig(),parent_run_id='q051-parent')
    assert packets[0]['horizon_sessions']==10 and packets[0]['oracle_target']=='path_amplitude_J1_J10'
    assert packets[0]['prices_through_decision_date']==[dict(date='2026-11-19',close=100.)]
    assert 'future_return' not in packets[0] and 'oracle_extreme10' not in packets[0]
    assert queries and all(q.lstrip().upper().startswith('SELECT') for q in queries)
