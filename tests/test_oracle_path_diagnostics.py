"""Read-only diagnostic fixtures; no real database, training or broker calls."""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
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


def test_top_ten_titles_not_ten_percent_and_amplitude_already_percent():
    rows=diag.top_k_rows({'overall':{'precision_top_10_titles':.8,'mean_path_amplitude_top_10_titles_pct':32.5}})
    assert rows[0]['Sélection']=='10 premiers titres'
    assert rows[0]['Précision véritable TOP20 %']==.8
    assert rows[0]['Amplitude maximale moyenne (%)']==32.5


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
    assert 'p.future_return IS NULL' in engine.calls[1][0]


def test_missing_lineage_keeps_sql_dates_but_reports_unqualified(artifacts):
    parent,_=artifacts;view=diag.load_path_artifacts('batch',parent)
    result=diag.read_sql_periods(Engine(fail_lineage=True),'batch',view)
    assert result['coverage']['n_rows']==4 and result['errors'] and result['matching_lineage_rows'] is None


def test_unavailable_or_wrong_database_never_invents_empty_success():
    assert diag.read_sql_periods(None,'batch',{})['errors']
    engine=Engine();engine.url=SimpleNamespace(database='alpha_trade_cn')
    assert diag.read_sql_periods(engine,'batch',{})['errors'] and not engine.calls


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
