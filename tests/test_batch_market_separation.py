import pytest
from ihm.services import batch_management as manager
from tests.test_ihm_batches import _spec


def test_real_catalogues_are_disjoint_and_preserve_legacy_cn_location():
    us=manager.load_market_batch_specs('US_EQ')
    cn=manager.load_market_batch_specs('CN_A')
    fr=manager.load_market_batch_specs('FR_EQ')
    assert all(not s.name.startswith(('cn_','fr_')) for s in us)
    assert all(s.name.startswith('cn_') for s in cn)
    assert all(s.name.startswith('fr_') for s in fr)
    assert not ({s.name for s in us}&{s.name for s in cn})
    assert not ({s.name for s in cn}&{s.name for s in fr})
    assert any(s.name=='cn_oracle_prospective_daily' and s.catalog_path.endswith('batch.yaml') for s in cn)
    assert 'cn_master_calendar_sync' not in {s.name for s in cn}
    pending=next(s for s in cn if s.name=='cn_daily_market_data_sync')
    assert not pending.runnable
    assert pending.status=='DISABLED_DUPLICATE_D9'
    assert 'D9' in pending.execution_notice
    with pytest.raises(ValueError,match='CN'): manager.build_run_command(pending)


@pytest.mark.parametrize('market',['US_EQ','CN_A','FR_EQ'])
def test_same_ui_and_global_actions_only_selected_market(monkeypatch,market):
    from streamlit.testing.v1 import AppTest
    from ihm.pages import batches as page
    own={'US_EQ':'daily_bars_sync','CN_A':'cn_db_backup','FR_EQ':'fr_calendar_snapshot'}[market]
    spec=_spec(own)
    selected=[]
    monkeypatch.setattr(page,'load_market_batch_specs',lambda m: (selected.append(m), (spec,))[1])
    states=lambda: ({spec.task_name:dict(state='Ready',enabled=True)},None)
    states.clear=lambda:None
    monkeypatch.setattr(page,'_task_states',states)
    monkeypatch.setattr(page,'_latest_collection_runs',lambda: ({},None) if market=='US_EQ' else pytest.fail('US SQL from other market'))
    monkeypatch.setattr(page,'latest_cn_dragon_research_run',lambda s: None)
    from service.fr import operational_batch_15a
    monkeypatch.setattr(operational_batch_15a,'latest_run',lambda n:None)
    monkeypatch.setattr(page,'list_active_batch_runs',lambda: [dict(step_key='batch:foreign_market_job')])
    monkeypatch.setattr(page,'load_pipeline_history',lambda:[])
    monkeypatch.setattr(page,'read_batch_log_tail',lambda s:'')
    operations=[]
    monkeypatch.setattr(page,'install_all_batches',lambda specs,**kw: (operations.append(('install',[s.name for s in specs])),{})[1])
    monkeypatch.setattr(page,'uninstall_all_batches',lambda specs,**kw: (operations.append(('uninstall',[s.name for s in specs])),{})[1])
    def render(m):
        from ihm.pages.batches import render_market_batches
        render_market_batches(m)
    app=AppTest.from_function(render,args=(market,)).run(timeout=15)
    assert not app.exception
    assert {m.label for m in app.metric}=={'Configurés','Exécutables (catalogues)','Installés et exécutables','Installés mais dormants','En cours via l’IHM'}
    assert any(s.label=='Rechercher' for s in app.text_input)
    assert any(s.label=='Compte tâche' for s in app.selectbox)
    install=next(b for b in app.button if b.label=='♻️ Installer / réinstaller tous')
    install.click().run()
    assert operations==[('install',[own])]
    uninstall=next(b for b in app.button if b.label=='🗑️ Désinstaller tous les batchs')
    uninstall.click().run()
    assert operations[-1]==('uninstall',[own])


def test_selector_contains_three_markets_and_migrates_old_choice(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ihm.pages import batches as page
    monkeypatch.setattr(page,'render_market_batches',lambda m:page.st.caption(m))
    from ihm.services import fr_batch_view
    monkeypatch.setattr(fr_batch_view,'render_fr_batches',lambda:page.st.caption('FR_EQ'))
    def render():
        from ihm.pages.batches import render
        import streamlit as st
        if 'fr14_batch_market' not in st.session_state: st.session_state['fr14_batch_market']='US_CN'
        render()
    app=AppTest.from_function(render).run()
    assert not app.exception
    assert app.selectbox[0].options==['États-Unis (US)','Chine (CN)','France (FR)']
    assert app.selectbox[0].value=='US_EQ'
    app.selectbox[0].select('CN_A').run()
    assert any(c.value=='CN_A' for c in app.caption)
    app.selectbox[0].select('FR_EQ').run()
    assert any(c.value=='FR_EQ' for c in app.caption)
