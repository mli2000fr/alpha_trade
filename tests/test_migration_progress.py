"""Progress telemetry, limits and readable UI; no real databases/providers."""
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from service.migration.tracking import Progress,CountingWriter,emit
from ihm.services import migration_runner


def test_progress_throttles_ticks_but_keeps_phase_boundaries(tmp_path):
    now=[0.]
    progress=Progress(tmp_path,'export',clock=lambda:now[0])
    progress.update('DATABASE_EXPORT',database='alpha_trade',completed=0,total=3)
    for count in range(200):progress.update(processed_bytes=count)
    lines=(tmp_path/'events.jsonl').read_text().splitlines()
    assert len(lines)==2
    now[0]=2.;progress.update(processed_bytes=1234)
    state=json.loads((tmp_path/'tracking.json').read_text())
    assert state['processed_bytes']==1234 and state['percent']<100
    progress.update('DATABASE_EXPORT',database='alpha_trade_fr',completed=1,total=3)
    progress.update('FAILED')
    state=json.loads((tmp_path/'tracking.json').read_text())
    assert state['status']=='FAILED' and state['percent']<100
    assert len((tmp_path/'events.jsonl').read_text().splitlines())==4


def test_progress_ignores_sensitive_fields_and_completes_only_at_end(tmp_path):
    progress=Progress(tmp_path,'restore')
    secret='fictional-only-token-S586'
    progress.update('DATABASE_REPLACEMENT',database='alpha_trade',password=secret,sql=secret,request={'key':secret})
    progress.update('ROLLBACK')
    progress.update('FAILED_ROLLED_BACK')
    assert progress.state['percent']<100
    for file in tmp_path.iterdir():
        if file.is_file():assert secret not in file.read_text(encoding='utf-8')
    progress.update('FINISHED')
    assert json.loads((tmp_path/'tracking.json').read_text())['percent']==100


def test_file_volume_and_parts_make_progress_visible(tmp_path):
    now=[0.];progress=Progress(tmp_path,'export',clock=lambda:now[0])
    progress.update('FILES_EXPORT',package='modeles',part_index=2,parts_total=4,total_bytes=1000,processed_bytes=0)
    before=progress.state['percent']
    now[0]=2;progress.update(processed_bytes=500)
    assert before<progress.state['percent']<100
    assert progress.state['total_bytes']==1000
    progress.update('DATABASE_RECHECK',database='alpha_trade')
    assert 'total_bytes' not in progress.state


def test_emit_does_not_prevent_rollback_if_log_disk_fails():
    def unavailable(*args,**kwargs):raise OSError('test disk full')
    emit(unavailable,'ROLLBACK')


def test_same_failure_is_not_logged_twice_and_lock_error_has_detail(tmp_path):
    progress=Progress(tmp_path,'export')
    progress.update('FAILED',error_code='MIGRATION_BUSY',owner_pid=123)
    progress.update('FAILED',error_code='MIGRATION_BUSY',owner_pid=123)
    events=[json.loads(line) for line in (tmp_path/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len([e for e in events if e['phase']=='FAILED'])==1
    assert 'Une autre sauvegarde' in events[-1]['message'] and '123' in events[-1]['message']


def test_counting_stream_never_records_contents(tmp_path):
    import io
    clear=io.BytesIO();progress=Progress(tmp_path,'export')
    progress.update('DATABASE_EXPORT',database='alpha_trade')
    stream=CountingWriter(clear,progress.update);stream.write(b'fictional-sensitive-data');stream.flush()
    progress.update(checkpoint=True)
    assert progress.state['processed_bytes']==len(b'fictional-sensitive-data')
    assert 'fictional-sensitive-data' not in (tmp_path/'events.jsonl').read_text()


def test_log_reader_is_bounded_and_ignores_partial_record(tmp_path):
    path=tmp_path/'events.jsonl'
    with path.open('w',encoding='utf-8') as out:
        out.write('bad partial record\n')
        for i in range(400):out.write(json.dumps({'message':str(i)})+'\n')
    events=migration_runner.read_events(path,limit=10)
    assert len(events)==10 and events[-1]['message']=='399'


def test_progress_fragment_shows_metrics_scrollable_logs_and_warning(tmp_path,monkeypatch):
    state=dict(progress={'status':'FINISHED'},tracking={
        'label':'Opération terminée','percent':100,'elapsed_seconds':62,'warning':True,
        'database':'alpha_trade','processed_bytes':1024,'total_bytes':2048},
        events=[dict(updated_at='2026-10-31T12:00:00+00:00',message='Sauvegarde de la base — alpha_trade')],
        result={})
    monkeypatch.setattr(migration_runner,'job_state',lambda path:state)
    app=AppTest.from_string("from ihm.components.migration_progress import render_migration_progress\nrender_migration_progress(['synthetic-job'])").run()
    assert not app.exception
    assert len(app.get('progress'))==2
    assert any(metric.value=='00:01:02' for metric in app.metric)
    assert app.warning and 'Python' in app.warning[0].value
    assert '31/10 13:00:00' in app.code[0].value
    assert 'alpha_trade' in app.code[0].value
    assert app.get('download_button')
