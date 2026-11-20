"""An explicit human choice may waive evidence only; original archives stay intact."""
import json
from types import SimpleNamespace

import pytest

from service.q051_paper import pipeline as p,human_selection as h
from tests.test_q051_human_selection import proposal


@pytest.fixture
def partial(proposal):
    folder,report,frame=proposal
    frame.loc[frame.symbol.eq('C'),['llm_probability_up_without_stop','llm_evidence_quality','llm_blockers']]=[
        .7,'PARTIAL','insufficient_fresh_sources, evidence_partial']
    frame.to_parquet(folder/'selection.parquet',index=False)
    report['selection_sha256']=p.digest(folder/'selection.parquet')
    (folder/'selection.json').write_text(json.dumps(report),encoding='utf-8')
    (folder/'seal.json').write_text(json.dumps(dict(report_sha256=p.digest(folder/'selection.json'))))
    return folder,report,frame


def test_new_policy_allows_explicit_partial_choice_with_auditable_frozen_waiver(partial,monkeypatch):
    folder,report,frame=partial
    with pytest.raises(ValueError):h.validate_choice(None,report['run_id'],['C'])
    monkeypatch.setattr(h,'selection_policy',lambda:dict(require_qualified_evidence=False))
    old_report=p.digest(folder/'selection.json');old_frame=p.digest(folder/'selection.parquet')
    approval=h.approve(None,report['run_id'],['C'])
    assert approval['schema_version']==2 and approval['selection_policy']==dict(require_qualified_evidence=False)
    assert approval['evidence_overrides']==[dict(symbol='C',evidence_quality='PARTIAL',blockers='insufficient_fresh_sources, evidence_partial')]
    updated,effective=h.effective(folder,report,frame)
    assert updated['selected']==['C'] and effective.loc[effective.selected,'symbol'].tolist()==['C']
    assert updated['llm_filter']['evidence_overrides']==approval['evidence_overrides']
    assert p.digest(folder/'selection.json')==old_report and p.digest(folder/'selection.parquet')==old_frame
    # Later config changes cannot silently alter a previously frozen approval.
    monkeypatch.setattr(h,'selection_policy',lambda:dict(require_qualified_evidence=True))
    assert h.read(folder,report,frame)==approval
    assert not (folder/'accounts').exists()


@pytest.mark.parametrize('blocker',['identity_not_confirmed','probability_undeterminable','long_not_allowed','future_unknown_check'])
def test_only_evidence_blockers_can_be_waived(partial,blocker):
    _,_,frame=partial
    frame.loc[frame.symbol.eq('C'),'llm_blockers']='evidence_partial, '+blocker
    assert 'C' not in h.selectable_symbols(frame,dict(require_qualified_evidence=False))


@pytest.mark.parametrize('probability',[None,float('nan'),True,-.1,1.1])
def test_waiver_does_not_authorize_an_absent_or_invalid_estimate(partial,probability):
    _,_,frame=partial
    frame['llm_probability_up_without_stop']=frame.llm_probability_up_without_stop.astype(object)
    frame.loc[frame.symbol.eq('C'),'llm_probability_up_without_stop']=probability
    assert 'C' not in h.selectable_symbols(frame,dict(require_qualified_evidence=False))


def test_legacy_approval_remains_strict_even_if_current_config_waives_evidence(partial,monkeypatch):
    folder,report,frame=partial
    value=h.approve(None,report['run_id'],['B'])
    value['schema_version']=1;value.pop('selection_policy');value.pop('evidence_overrides')
    h.approval_path(folder).write_text(json.dumps(value))
    monkeypatch.setattr(h,'selection_policy',lambda:dict(require_qualified_evidence=False))
    assert h.read(folder,report,frame)['selected_symbols']==['B']
    value['selected_symbols']=['C'];h.approval_path(folder).write_text(json.dumps(value))
    with pytest.raises(ValueError,match='incompatible'):h.read(folder,report,frame)


def test_policy_requires_a_boolean_and_defaults_to_strict(monkeypatch):
    monkeypatch.setattr('common.config_loader.load_config',lambda:{'us_pipeline':{}})
    assert h.selection_policy()==dict(require_qualified_evidence=True)
    monkeypatch.setattr('common.config_loader.load_config',lambda:{'us_pipeline':{'gpt_require_qualified_evidence_for_manual_selection':False}})
    assert h.selection_policy()==dict(require_qualified_evidence=False)
    monkeypatch.setattr('common.config_loader.load_config',lambda:{'us_pipeline':{'gpt_require_qualified_evidence_for_manual_selection':'false'}})
    with pytest.raises(ValueError,match='booléen'):h.selection_policy()


def test_ui_can_validate_partial_choice_and_clears_obsolete_strict_error(partial,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ihm.components import probability_selection as ui,prediction_review_table as table
    folder,report,frame=partial
    monkeypatch.setattr(ui,'_test_proposal',partial,raising=False)
    monkeypatch.setattr(table,'_table_component',lambda **kw:SimpleNamespace(selected_symbols=['C']))
    monkeypatch.setattr('ihm.services.db.get_engine',lambda:None)
    app=AppTest.from_string('''
from ihm.components.probability_selection import render,_test_proposal
render(*_test_proposal)
''').run(timeout=30)
    next(b for b in app.button if b.label=='Valider la sélection').click().run(timeout=30)
    assert app.error and not h.approval_path(folder).exists()
    monkeypatch.setattr(h,'selection_policy',lambda:dict(require_qualified_evidence=False))
    app.run(timeout=30)
    assert not app.exception and not app.error
    assert any('Qualification des preuves facultative' in i.value for i in app.info)
    next(b for b in app.button if b.label=='Valider la sélection').click().run(timeout=30)
    assert not app.exception and h.read(folder,report,frame)['selected_symbols']==['C']
