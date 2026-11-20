"""Stages remain visible while waiting; only exact account archives are shown."""
import json
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from ihm.components import pipeline_batch_results as results,pipeline_batch_defaults as defaults
from ihm.services.pipeline_runner import PipelineLaunchOptions
from service.q051_paper import pipeline


@pytest.fixture
def archive(tmp_path,monkeypatch):
    path=tmp_path/'selection.json'
    record=dict(run_id='q051-example',trade_date='2026-11-19')
    path.write_text(json.dumps(record))
    def add(account='default',qty=4):
        folder=tmp_path/'accounts'/account;folder.mkdir(parents=True,exist_ok=True)
        risk=dict(status='COMPLETED',risk_run_id='risk-'+account,q051_run_id=record['run_id'],
            account_id=account,trade_date=record['trade_date'],selection_sha256=pipeline.digest(path),
            profile_sha256='profile',equity=4000.,targets=1,approved_count=1,rejected_count=0,
            decisions=[dict(symbol='EXAMPLE',decision='APPROVED',reason='PASS',approved_shares=qty,
                entry_price=100.,target_notional=qty*100.)])
        rp=folder/'risk.json';rp.write_text(json.dumps(risk))
        (folder/'risk.seal.json').write_text(json.dumps(dict(risk_sha256=pipeline.digest(rp))))
        execution=dict(exec_run_id='exec-'+account,risk_run_id=risk['risk_run_id'],account_id=account,
            trade_date=record['trade_date'],profile_sha256='profile',targets=1,status='COMPLETED',submitted=1,
            winner_standard_entry=dict(standard_orders=[dict(symbol='EXAMPLE',status='SUBMITTED',
                requested_quantity=qty,filled_quantity=0,broker_order_id='broker-'+account)]))
        (folder/'execution.json').write_text(json.dumps(execution))
        return risk,execution
    view=SimpleNamespace(options=PipelineLaunchOptions(llm_filter_enabled=True,account_id='default'),other_accounts=('test1',))
    monkeypatch.setattr(results,'_test_context',(view,path,record),raising=False)
    return SimpleNamespace(path=path,record=record,add=add,view=view)


def app():
    return AppTest.from_string('''
from ihm.components.pipeline_batch_results import render_account_stages,_test_context
render_account_stages(*_test_context)
''').run(timeout=30)


def test_same_account_risk_and_execution_and_submitted_is_not_filled(archive):
    archive.add();archive.add('test1',qty=2)
    page=app()
    assert not page.exception
    assert page.dataframe[0].value.iloc[0]['Quantité']==4
    order=page.dataframe[1].value.iloc[0]
    assert order['Quantité demandée']==4 and order['Quantité exécutée']==0
    assert order['Prix de référence']==100. and order['Montant cible']==400.
    assert all(e.proto.expanded for e in page.expander)
    page.selectbox(key='pipeline_us_defaults_review_account').select('test1').run(timeout=30)
    assert not page.exception
    assert page.dataframe[0].value.iloc[0]['Quantité']==2
    assert page.dataframe[1].value.iloc[0]['Ordre broker']=='broker-test1'


def test_three_stages_visible_before_step10_exists(tmp_path,monkeypatch):
    monkeypatch.setattr(pipeline,'ARTIFACTS',tmp_path)
    view=SimpleNamespace(options=PipelineLaunchOptions(q051_paper_enabled=True,llm_filter_enabled=True,
        ml_predict_batch_id='model',trade_date='2026-11-20'),other_accounts=())
    monkeypatch.setattr(defaults,'_test_view',view,raising=False)
    page=AppTest.from_string('''
from ihm.components.pipeline_batch_defaults import render_selection,_test_view
from ihm.components.prediction_review_table import _registered_table_component
_registered_table_component.clear()
render_selection(_test_view)
''').run(timeout=30)
    assert not page.exception
    labels=[e.label for e in page.expander]
    assert any(s.startswith('10.') for s in labels)
    assert any(s.startswith('11.') for s in labels)
    assert any(s.startswith('12.') for s in labels)
    assert any('En attente' in i.value for i in page.info)


def test_missing_risk_keeps_step12_visible_without_stale_execution(archive):
    archive.add()
    (archive.path.parent/'accounts/default/risk.json').unlink()
    page=app()
    assert not page.exception and not page.dataframe
    assert any(e.label.startswith('12.') for e in page.expander)
    assert any('En attente du bilan de risque exact' in i.value for i in page.info)


@pytest.mark.parametrize('field,value',[('account_id','test1'),('risk_run_id','another-risk'),('trade_date','2026-11-18')])
def test_other_execution_scope_never_displayed(archive,field,value):
    archive.add()
    path=archive.path.parent/'accounts/default/execution.json'
    data=json.loads(path.read_text());data[field]=value;path.write_text(json.dumps(data))
    page=app()
    assert not page.exception and len(page.dataframe)==1
    assert any('Exécution incompatible' in w.value for w in page.warning)
