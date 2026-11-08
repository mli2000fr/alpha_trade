"""Read-only diagnostic fixtures; no real database, training or broker calls."""
from contextlib import contextmanager
from hashlib import sha256
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from ihm.services import oracle_path_diagnostics as diag


@pytest.fixture
def artifacts(tmp_path):
    root=tmp_path/'batch'/'oracle_path';root.mkdir(parents=True)
    protocol=dict(mode=diag.MODE,batch_id='batch',target=diag.TARGET,horizon=20,serving_ready=True,
        universe=['A','B'],generator_options={})
    protocol['fingerprint']=sha256(json.dumps(protocol,sort_keys=True,default=str).encode()).hexdigest()
    (root/'protocol.json').write_text(json.dumps(protocol))
    (root/'feature_profile.json').write_text(json.dumps(dict(mode=diag.MODE,target=diag.TARGET,
        serving_ready=True,feature_columns=['feature'],generator_options={})))
    summaries=[]
    for start,available in [('2023-12-01','2023-11-30'),('2024-07-01','2024-06-28')]:
        folder=root/'folds'/start;folder.mkdir(parents=True)
        (folder/'path_model.txt').write_text('fixture weights, never executed')
        pd.DataFrame({'date':pd.to_datetime([start]*2),'symbol':['A','B'],
            diag.TARGET:[1.,0.],'proba_path_extreme':[.8,.2],'path_amplitude':[.3,.1]}).to_parquet(folder/'oof.parquet')
        metrics=dict(fold_start=start,train_available_max='2023-06-01',val_start='2023-06-02',
            val_available_max=available,test_start=start,test_end=start,rows=2,dates=1,auc=.75,
            precision_at_10pct=.5,precision_at_20pct=.5,mean_path_amplitude_top10_pct=30.)
        summaries.append(metrics)
        (folder/'done.json').write_text(json.dumps(dict(metrics=metrics,files={name:sha256((folder/name).read_bytes()).hexdigest()
            for name in ('path_model.txt','oof.parquet')})))
    report=dict(status='completed',batch_id='batch',mode=diag.MODE,serving_ready=True,n_folds=2,n_features=1,
        folds=summaries,overall=dict(rows=4,dates=2,auc=.75,precision_at_20pct=.5,
            precision_top_10_titles=.8,mean_path_amplitude_top_10_titles_pct=30.,dates_top_10_titles=2))
    (root/'report.json').write_text(json.dumps(report))
    return tmp_path,root


@pytest.mark.parametrize('metadata',[
    {'cli_options':{'oracle_path_model_only':True}},
    json.dumps({'cli_options':{'oracle_path_model_only':True}}),
    {'training_config':{'data':{'oracle_path_model_only':True}}},
    {'mode':'oracle_path_h20'},
])
def test_recognition_uses_new_contract_not_legacy_enable_flag(tmp_path,metadata):
    assert diag.is_path_model('batch',metadata,tmp_path)


def test_artifact_recognition_and_bad_or_legacy_metadata(artifacts):
    parent,_=artifacts
    assert diag.is_path_model('batch',None,parent)
    assert diag.metadata_dict({'test':True})=={'test':True}
    assert diag.metadata_dict('invalid')=={}
    assert not diag.is_path_model('missing',{'cli_options':{'enable_oracle_model':True}},parent)
    assert not diag.is_path_model('../batch',{},parent)


def test_real_fold_oof_periods_and_counts_are_read_separately(artifacts):
    parent,_=artifacts;view=diag.load_path_artifacts('batch',parent)
    assert view['ready'] and not view['errors']
    assert view['oof_coverage']==dict(min_date=pd.Timestamp('2023-12-01'),max_date=pd.Timestamp('2024-07-01'),
        nb_dates=2,nb_symbols=2,n_rows=4)
    sql=dict(coverage=dict(min_date='2025-01-02',max_date='2025-02-03',nb_dates=20,nb_symbols=2,n_rows=40))
    rows=diag.period_rows(view,sql)
    assert len(rows)==2 and rows[0]['Période']=='2025-01-02 → 2025-02-03'
    assert rows[1]['Période']=='2023-12-01 → 2024-07-01'
    assert '—' not in rows[0]['Période']


@pytest.mark.parametrize('corrupt',['weights','oof','report','causality'])
def test_invalid_artifacts_never_present_metrics_as_qualified(artifacts,corrupt):
    parent,root=artifacts
    if corrupt=='weights':(root/'folds/2023-12-01/path_model.txt').write_text('corrupt')
    elif corrupt=='oof':(root/'folds/2023-12-01/oof.parquet').write_bytes(b'corrupt')
    else:
        report=json.loads((root/'report.json').read_text())
        if corrupt=='report':report['overall']['rows']=5
        else:
            report['folds'][0]['val_available_max']='2023-12-01'
            done=json.loads((root/'folds/2023-12-01/done.json').read_text())
            done['metrics']=report['folds'][0]
            (root/'folds/2023-12-01/done.json').write_text(json.dumps(done))
        (root/'report.json').write_text(json.dumps(report))
    view=diag.load_path_artifacts('batch',parent)
    assert not view['ready'] and view['errors']


def test_in_progress_without_report_is_not_a_missing_legacy_model(artifacts):
    parent,root=artifacts;(root/'report.json').unlink()
    (root/'progress.json').write_text(json.dumps(dict(status='RUNNING',phase='training_fold',completed=1,total=2)))
    view=diag.load_path_artifacts('batch',parent)
    assert not view['ready'] and view['warnings'] and view['progress']['completed']==1


def test_signature_includes_oof_and_model_files(artifacts):
    parent,root=artifacts
    before=diag.artifact_signature('batch',parent)
    (root/'folds/2023-12-01/path_model.txt').write_text('changed')
    assert before!=diag.artifact_signature('batch',parent)


def test_terminal_oof_schema_cannot_replace_path_target(artifacts):
    parent,root=artifacts;folder=root/'folds/2023-12-01'
    pd.DataFrame({'date':pd.to_datetime(['2023-12-01']*2),'symbol':['A','B'],
        'oracle_extreme10':[1,0],'future_return':[.2,-.1]}).to_parquet(folder/'oof.parquet')
    done=json.loads((folder/'done.json').read_text())
    done['files']['oof.parquet']=sha256((folder/'oof.parquet').read_bytes()).hexdigest()
    (folder/'done.json').write_text(json.dumps(done))
    view=diag.load_path_artifacts('batch',parent)
    assert not view['ready'] and any('Schéma OOF' in message for message in view['errors'])


def test_top_ten_titles_not_ten_percent_and_amplitude_already_percent():
    rows=diag.top_k_rows({'overall':{'precision_top_10_titles':.8,'mean_path_amplitude_top_10_titles_pct':32.5}})
    assert rows[0]['Sélection']=='10 premiers titres'
    assert rows[0]['Précision véritable TOP20 %']==.8
    assert rows[0]['Amplitude maximale moyenne (%)']==32.5


def bundle_manifest(root):
    from modelFactory.oracle_path.directional import INPUTS
    records=[]
    for symbol,side in [('A','long'),('A','short'),('B','long')]:
        path=root/'directional'/symbol/f'{side}-2024.joblib'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b'hashed fixture; never deserialize')
        records.append(dict(symbol=symbol,side=side,year=2024,file=str(path.relative_to(root)),
            sha256=sha256(path.read_bytes()).hexdigest(),fit_start='2020-01-02',fit_end='2022-12-01',
            fit_available_max='2022-12-20',calibration_start='2023-01-03',calibration_end='2023-12-01',
            available='2023-12-20',fit_rows=800,calibration_rows=200))
    return dict(status='COMPLETED',features=INPUTS,models=records,
        skipped=[dict(symbol='B',side='short',year=2024,reason='INSUFFICIENT_HISTORY_OR_CLASSES')],
        contract=dict(enabled=True,oracle_top_n=20,selected_n=5,stop_loss_pct=.05,horizon_sessions=10,fee_per_leg=.0008),
        serving_side='long')


def test_directional_summary_counts_annual_models_and_separates_missing_titles(tmp_path):
    manifest=bundle_manifest(tmp_path)
    result=diag.directional_summary({'universe':['A','B']},manifest)
    assert result['models']==3 and result['long_models']==2 and result['short_models']==1
    assert result['coverage']==[{'Année d’utilisation':2024,'Titres de l’univers':2,
        'Titres avec LONG':2,'Titres avec SHORT':1,'Sans modèle LONG':0,'Sans modèle SHORT':1}]
    assert result['details'][0]['Fin calibration']=='2023-12-01'
    assert result['omissions'][0]['Symbole']=='B'
    assert 'insuffisants' in result['omissions'][0]['Motif']
    assert 'auc' not in result


def test_directional_files_and_manifest_invalidate_diagnostic_cache(artifacts):
    parent,root=artifacts
    manifest=bundle_manifest(root)
    (root/'directional/manifest.json').write_text(json.dumps(manifest))
    before=diag.artifact_signature('batch',parent)
    (root/manifest['models'][0]['file']).write_bytes(b'changed model fixture')
    assert before!=diag.artifact_signature('batch',parent)


def test_directional_section_displays_models_even_without_legacy_training_rows(tmp_path):
    from streamlit.testing.v1 import AppTest
    summary=diag.directional_summary({'universe':['A','B']},bundle_manifest(tmp_path))
    app=AppTest.from_string('''import streamlit as st
from ihm.components.oracle_path_diagnostics import render_directional
render_directional({'batch_id':'fixture','directional':st.session_state['summary']})
''')
    app.session_state['summary']=summary
    app.run(timeout=30)
    assert not app.exception
    assert {item.label:item.value for item in app.metric}=={
        'Modèles LONG entraînés':'2','Modèles SHORT entraînés':'1'}
    assert any('Sans modèle SHORT' in frame.value.columns for frame in app.dataframe)
    app.selectbox(key='diag_path_side_fixture').select('SHORT').run(timeout=30)
    assert not app.exception
    detail=next(frame.value for frame in app.dataframe if 'Fichier' in frame.value.columns)
    assert detail.Direction.tolist()==['SHORT']


def add_bundle_to_fixture(root):
    manifest=bundle_manifest(root)
    protocol=json.loads((root/'protocol.json').read_text())
    protocol.pop('fingerprint')
    protocol.update(mode='oracle_path_h10',target='oracle_path_extreme10',horizon=10,
        training_config={'oracle_path_directional_enabled':True},directional_contract=manifest['contract'])
    protocol['fingerprint']=sha256(json.dumps(protocol,sort_keys=True,default=str).encode()).hexdigest()
    (root/'protocol.json').write_text(json.dumps(protocol))
    profile=json.loads((root/'feature_profile.json').read_text())
    profile.update(mode=protocol['mode'],target=protocol['target'])
    (root/'feature_profile.json').write_text(json.dumps(profile))
    manifest['oracle_protocol_sha256']=sha256((root/'protocol.json').read_bytes()).hexdigest()
    (root/'directional/manifest.json').write_text(json.dumps(manifest))
    report=json.loads((root/'report.json').read_text())
    report.update(mode=protocol['mode'],horizon=10,directional_models=3,directional_skipped=1,
        directional_manifest_sha256=sha256((root/'directional/manifest.json').read_bytes()).hexdigest())
    (root/'report.json').write_text(json.dumps(report))
    for folder in (root/'folds').iterdir():
        frame=pd.read_parquet(folder/'oof.parquet').rename(columns={diag.TARGET:protocol['target']})
        frame.to_parquet(folder/'oof.parquet')
        done=json.loads((folder/'done.json').read_text())
        done['files']['oof.parquet']=sha256((folder/'oof.parquet').read_bytes()).hexdigest()
        (folder/'done.json').write_text(json.dumps(done))


def test_bundle_loader_exposes_verified_per_symbol_models_without_sql(artifacts):
    parent,root=artifacts
    add_bundle_to_fixture(root)
    view=diag.load_path_artifacts('batch',parent)
    assert view['ready'] and not view['errors']
    assert view['directional']['models']==3
    assert view['directional']['coverage'][0]['Sans modèle SHORT']==1


def test_bundle_periods_show_explicit_empty_per_symbol_rows(artifacts):
    parent,root=artifacts;add_bundle_to_fixture(root)
    view=diag.load_path_artifacts('batch',parent)
    result=diag.read_sql_periods(Engine(rows=0),'batch',view)
    assert not result['errors']
    rows=diag.period_rows(view,result)
    long=next(r for r in rows if r['Source']=='Per-symbol LONG — SQL')
    assert long['Période']=='—' and long['Lignes']==0
    assert 'aucune prédiction LONG' in long['Détail']
    assert any(r['Source']=='Per-symbol SHORT — SQL' for r in rows)


def test_bundle_periods_read_actual_directional_scores_and_manifest(artifacts):
    parent,root=artifacts;add_bundle_to_fixture(root)
    view=diag.load_path_artifacts('batch',parent)
    class BundleEngine(Engine):
        def execute(self,statement,params):
            sql=str(statement)
            if 'oracle_path_directional_predictions' in sql:
                assert params['manifest']==view['directional']['manifest_sha256']
                assert '_probability IS NOT NULL' in sql
                return SimpleNamespace(mappings=lambda:SimpleNamespace(one=lambda:dict(
                    min_date='2024-01-02',max_date='2024-02-01',nb_dates=20,nb_symbols=2,
                    n_rows=40,matching_manifest_rows=40)))
            if 'oracle_path_prediction_lineage l' in sql:return SimpleNamespace(scalar_one=lambda:4)
            return super().execute(statement,params)
    result=diag.read_sql_periods(BundleEngine(),'batch',view)
    assert not result['errors']
    rows=diag.period_rows(view,result)
    long=next(r for r in rows if r['Source']=='Per-symbol LONG — SQL')
    assert long['Période']=='2024-01-02 → 2024-02-01' and long['Lignes']==40


def test_metric_rows_and_streamlit_keep_calibration_distinct_from_test(tmp_path):
    from streamlit.testing.v1 import AppTest
    from modelFactory.oracle_path.directional_metrics import classification_metrics
    record=dict(symbol='A',year=2024,side='long',metrics={
        'calibration':classification_metrics([0,1],[.1,.9]),
        'oos':classification_metrics([0,1],[.8,.2]),
        'oos_nonoverlap':classification_metrics([1],[.2]),
        'train':classification_metrics([0,1],[.1,.9])})
    rows=diag.directional_metric_rows([record])
    assert next(r for r in rows if r['Échantillon']=='oos')['AUC']==0
    app=AppTest.from_string('''import streamlit as st
from ihm.components.oracle_path_diagnostics import render_directional_metrics
render_directional_metrics({'batch_id':'fixture'},{'metrics_rows':st.session_state['rows']})
''')
    app.session_state['rows']=rows;app.run(timeout=30)
    assert not app.exception
    assert any(m.label=='AUC médiane par titre' and m.value=='0.000' for m in app.metric)
    assert not app.warning
    app.selectbox(key='diag_path_metric_stage_fixture').select('calibration').run(timeout=30)
    assert not app.exception and any('pas un test indépendant' in w.value for w in app.warning)


def test_per_symbol_oos_file_periods_are_distinct_from_oracle_and_sql(tmp_path):
    file=tmp_path/'oos.parquet'
    pd.DataFrame(dict(date=pd.to_datetime(['2024-01-02','2024-01-03']),
        symbol=['A','A'],side=['long','short'])).to_parquet(file)
    info=[dict(path=file.name,rows=2,sha256=sha256(file.read_bytes()).hexdigest())]
    coverage=diag.directional_oos_coverage(tmp_path,info)
    assert coverage['long']['n_rows']==1 and coverage['short']['n_rows']==1
    rows=diag.period_rows({'directional':{'oos_coverage':coverage}},
        {'directional':{'long':{'n_rows':0},'short':{'n_rows':0}}})
    test=next(r for r in rows if r['Source']=='Tests OOS per-symbol LONG')
    assert test['Période']=='2024-01-02 → 2024-01-02' and test['Séances']==1
    file.write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='corrompues'):diag.directional_oos_coverage(tmp_path,info)


@pytest.mark.parametrize('corrupt',['count','weights'])
def test_invalid_directional_artifacts_never_show_qualified_metrics(artifacts,corrupt):
    parent,root=artifacts
    add_bundle_to_fixture(root)
    if corrupt=='count':
        report=json.loads((root/'report.json').read_text());report['directional_models']=999
        (root/'report.json').write_text(json.dumps(report))
    else:(root/'directional/A/long-2024.joblib').write_bytes(b'corrupt')
    view=diag.load_path_artifacts('batch',parent)
    assert not view['ready'] and view['errors']


def test_empty_sql_aggregate_does_not_create_nat_period(artifacts):
    parent,_=artifacts;view=diag.load_path_artifacts('batch',parent)
    rows=diag.period_rows(view,{'coverage':dict(n_rows=0,min_date=None,max_date=None,nb_dates=0)})
    assert len(rows)==1 and rows[0]['Source']=='Tests OOF du training'


class Engine:
    url=SimpleNamespace(database='alpha_trade')
    def __init__(self,*,rows=4,lineage=4,fail_lineage=False):
        self.rows,self.lineage,self.fail_lineage=rows,lineage,fail_lineage;self.calls=[]
    @contextmanager
    def connect(self):yield self
    def execution_options(self,**options):self.isolation=options['isolation_level'];return self
    def execute(self,statement,params):
        sql=str(statement);self.calls.append((sql,params))
        assert sql.lstrip().upper().startswith('SELECT') and params['batch_id']=='batch'
        if 'MIN(prediction_date)' in sql:
            row=dict(min_date='2025-01-02' if self.rows else None,max_date='2025-01-03' if self.rows else None,
                nb_dates=2 if self.rows else 0,nb_symbols=2 if self.rows else 0,n_rows=self.rows)
            return SimpleNamespace(mappings=lambda:SimpleNamespace(one=lambda:row))
        if self.fail_lineage:raise RuntimeError('Missing lineage table')
        assert params['target']==diag.TARGET and params['fold0']=='2023-12-01'
        assert params['available0']=='2023-11-30'
        return SimpleNamespace(scalar_one=lambda:self.lineage)


def test_sql_filter_and_causal_lineage_are_batch_scoped(artifacts):
    parent,_=artifacts;view=diag.load_path_artifacts('batch',parent);engine=Engine()
    result=diag.read_sql_periods(engine,'batch',view)
    assert result['coverage']['n_rows']==4 and result['matching_lineage_rows']==4 and not result['errors']
    assert len(engine.calls)==2
    assert engine.isolation=='REPEATABLE READ'
    assert 'p.future_return IS NULL' in engine.calls[1][0]


def test_missing_lineage_keeps_sql_dates_but_reports_unqualified(artifacts):
    parent,_=artifacts;view=diag.load_path_artifacts('batch',parent)
    result=diag.read_sql_periods(Engine(fail_lineage=True),'batch',view)
    assert result['coverage']['n_rows']==4 and result['errors'] and result['matching_lineage_rows'] is None


def test_unavailable_or_wrong_database_never_invents_empty_success():
    assert diag.read_sql_periods(None,'batch',{})['errors']
    engine=Engine();engine.url=SimpleNamespace(database='alpha_trade_cn')
    assert diag.read_sql_periods(engine,'batch',{})['errors'] and not engine.calls


def test_connection_error_is_displayable_not_a_page_crash():
    engine=Engine()
    def fail():raise RuntimeError('offline')
    engine.connect=fail
    assert diag.read_sql_periods(engine,'batch',{})['errors']


def test_legacy_oracle_empty_aggregate_has_no_nat_period(monkeypatch):
    from ihm.pages import ml_diagnostics as page
    monkeypatch.setattr(page,'safe_query',lambda *args:pd.DataFrame([
        dict(min_date=None,max_date=None,nb_dates=0,nb_symbols=0)]))
    assert page._oracle_periods('batch')==[]
    assert page._batch_trains_oracle(pd.Series({'metadata_json':{'cli_options':{'oracle_path_model_only':True}}}))


def test_page_path_branch_never_reads_terminal_labels_or_legacy_metrics(artifacts,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ihm.pages import ml_diagnostics as page
    parent,_=artifacts;view=diag.load_path_artifacts('batch',parent)
    sql=diag.read_sql_periods(Engine(),'batch',view)
    row=pd.Series(dict(batch_id='batch',status='completed',symbol_source='stock-bars',
        metadata_json=json.dumps({'cli_options':{'oracle_path_model_only':True,'artifacts_dir':str(parent)}})))
    monkeypatch.setattr(page,'_cached_query',lambda query,params:pd.DataFrame([row]))
    monkeypatch.setattr(page,'_path_view',lambda *args:view)
    monkeypatch.setattr(page,'_path_sql_periods',lambda *args:sql)
    monkeypatch.setattr(page,'get_engine',lambda:Engine())
    monkeypatch.setattr(page,'_get_batch_training_logs',lambda *args:'fixture')
    monkeypatch.setattr(page,'safe_query',lambda *args,**kwargs:pytest.fail('No legacy SQL for path model'))
    app=AppTest.from_string('''import pandas as pd
import streamlit as st
from ihm.pages.ml_diagnostics import _render_batch_detail
_render_batch_detail(pd.Series(st.session_state['batch']))
''')
    app.session_state['batch']=row.to_dict();app.run(timeout=45)
    assert not app.exception
    labels={item.label for item in app.metric}
    assert 'AUC amplitude — OOF' in labels and 'Précision 10 premiers titres' in labels
    assert not any('F1' in label or 'IC Rank Global' in label for label in labels)
    assert any('Rapport Oracle parcours' in item.label for item in app.get('download_button'))
    app.button(key='ml_diag_pred_periods_batch').click().run(timeout=45)
    assert not app.exception
    assert any('2025-01-02 → 2025-01-03' in frame.value.to_string() for frame in app.dataframe)
