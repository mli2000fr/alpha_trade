from datetime import datetime,timezone
import pytest

from service.options_directional import store
from ihm.services.options_prediction_review import load_options_prediction_review
from test_options_directional_filter import report,RUN,DAY,NOW


def setup(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(store,'validate_window',lambda *a:None)
    a=tmp_path/'config/univers/test.txt';b=tmp_path/'config/univers_batch/test.txt'
    a.parent.mkdir(parents=True);b.parent.mkdir(parents=True)
    a.write_text('A,B',encoding='utf-8');b.write_text('A,B',encoding='utf-8')
    root=tmp_path/'evidence'
    data={**report(),'symbol_source':'universe-file:config/univers_batch/test.txt'}
    store.seal(RUN,data,{'universe':['A','B']},root=root)
    return root,a,b


def test_display_alias_is_allowed_but_execution_stays_exact(tmp_path,monkeypatch):
    root,a,b=setup(tmp_path,monkeypatch)
    review=load_options_prediction_review(RUN,symbol_source='universe-file:test.txt',
        project_root=tmp_path,root=root,trade_date=DAY,now=NOW,batch_id='model-test')
    assert review['symbol_source']=='universe-file:config/univers_batch/test.txt'
    assert review['selected']==['A']
    with pytest.raises(ValueError,match='symbol_source'):
        store.qualified(RUN,symbol_source='universe-file:test.txt',root=root,trade_date=DAY,now=NOW)


@pytest.mark.parametrize('changed',['display','saved','both'])
def test_different_contents_are_never_an_alias(tmp_path,monkeypatch,changed):
    root,a,b=setup(tmp_path,monkeypatch)
    for path in ([a,b] if changed=='both' else [a] if changed=='display' else [b]):
        path.write_text('A,C',encoding='utf-8')
    with pytest.raises(ValueError,match='univers'):
        load_options_prediction_review(RUN,symbol_source='universe-file:test.txt',
            project_root=tmp_path,root=root,trade_date=DAY,now=NOW)


@pytest.mark.parametrize('changes',[{'batch_id':'other'},{'account_id':'other'},
    {'capital_preset_key':'other'},{'trade_date':'2026-10-15'},
    {'now':datetime(2026,10,22,tzinfo=timezone.utc)}])
def test_display_preserves_other_qualification_guards(tmp_path,monkeypatch,changes):
    root,_,_=setup(tmp_path,monkeypatch)
    kwargs=dict(root=root,trade_date=DAY,now=NOW)
    with pytest.raises(ValueError):
        load_options_prediction_review(RUN,symbol_source='universe-file:test.txt',
            project_root=tmp_path,**{**kwargs,**changes})


def test_tampered_archive_is_blocked(tmp_path,monkeypatch):
    root,_,_=setup(tmp_path,monkeypatch)
    (store.directory(RUN,root)/'inputs.json').write_text('{"universe":["A","B"]}',encoding='utf-8')
    # Change the sealed body rather than only its whitespace.
    (store.directory(RUN,root)/'report.json').write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError):
        load_options_prediction_review(RUN,symbol_source='universe-file:test.txt',
            project_root=tmp_path,root=root,trade_date=DAY,now=NOW)


def test_other_account_can_display_shared_selection_with_identical_alias(tmp_path,monkeypatch):
    root,_,_=setup(tmp_path,monkeypatch)
    review=load_options_prediction_review(RUN,symbol_source='universe-file:test.txt',
        project_root=tmp_path,root=root,trade_date=DAY,now=NOW,
        account_id='test1',capital_preset_key='capital_0_2000',shared_selection=True)
    assert review['selected']==['A'] and review['account_id']=='default'
