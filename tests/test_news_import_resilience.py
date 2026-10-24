"""No real database, provider, FinBERT or broker in these regression tests."""
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
import logging
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import requests

from event_sentiment import importe_news as cli
from event_sentiment.config import EventSentimentConfig
from event_sentiment.ingestion import NewsIngestionService
from event_sentiment.import_runtime import ImportRuntime
from event_sentiment.models import NormalizedNewsArticle
from service.eodhd import news_client
from service._http_retry import CircuitOpenError

START=datetime(2026,10,10,tzinfo=timezone.utc)
END=datetime(2026,10,17,tzinfo=timezone.utc)


def bare():
    service=NewsIngestionService.__new__(NewsIngestionService)
    service.config=EventSentimentConfig()
    return service


def test_isolate_one_provider_error_keep_others_and_partial_counters():
    service=bare(); calls=[]
    def one(**kwargs):
        calls.append(kwargs['symbol'])
        if kwargs['symbol']=='AA':
            error=news_client.EodhdNewsFetchError('timeout https://example.com/news?api_token=hidden&s=AA.US')
            error.partial_summary={'fetched':4,'landed':2,'ticker_maps':2}
            raise error
        return {'fetched':3,'landed':3,'ticker_maps':3}
    service._run_symbol=one
    result=service.run(START,END,['A','AA','B'],continue_on_symbol_error=True)
    assert calls==['A','AA','B']
    assert result['status']=='INCOMPLETE' and result['failed_count']==1
    assert result['landed']==8 and result['fetched']==10
    assert result['succeeded_symbols']==2 and result['unattempted_symbols']==0
    assert 'hidden' not in result['failed_symbols'][0]['error']


@pytest.mark.parametrize('error', [news_client.EodhdNewsFetchError('403',status_code=403,terminal=True),
    news_client.EodhdNewsFetchError('429',status_code=429,terminal=True),CircuitOpenError('open')])
def test_global_errors_stop_without_marking_remaining_symbols_success(error):
    service=bare(); calls=[]
    def one(**kw):
        calls.append(kw['symbol']); raise error
    service._run_symbol=one
    result=service.run(START,END,['A','B','C'],continue_on_symbol_error=True)
    assert calls==['A'] and result['aborted']
    assert result['unattempted_symbols']==2 and result['succeeded_symbols']==0


def test_consecutive_failure_limit_and_legacy_fail_fast():
    service=bare()
    def fail(**kw): raise news_client.EodhdNewsFetchError('timeout')
    service._run_symbol=fail
    result=service.run(START,END,['A','B','C','D'],continue_on_symbol_error=True,max_consecutive_failures=3)
    assert result['attempted_symbols']==3 and result['unattempted_symbols']==1
    assert result['aborted'] and result['status']=='INCOMPLETE'
    with pytest.raises(news_client.EodhdNewsFetchError): service.run(START,END,['A','B'])


def test_database_or_programming_error_is_never_isolated():
    service=bare()
    def fail(**kw): raise RuntimeError('SQL failure')
    service._run_symbol=fail
    with pytest.raises(RuntimeError,match='SQL failure'):
        service.run(START,END,['A','B'],continue_on_symbol_error=True)


def test_failure_limit_carries_across_symbol_batches():
    service=bare()
    def fail(**kw): raise news_client.EodhdNewsFetchError('timeout')
    service._run_symbol=fail
    first=service.run(START,END,['A','B'],continue_on_symbol_error=True)
    assert not first['aborted'] and first['consecutive_failures']==2
    second=service.run(START,END,['C','D'],continue_on_symbol_error=True,
                       initial_consecutive_failures=first['consecutive_failures'])
    assert second['aborted'] and second['attempted_symbols']==1 and second['unattempted_symbols']==1


def test_failed_or_running_checkpoint_never_skipped_from_updated_time():
    repo=SimpleNamespace(get_checkpoints=lambda *a:{
        'A':dict(status='failed',updated_at=END+timedelta(days=1),watermark_published_at_utc=END),
        'B':dict(status='running',updated_at=END,watermark_published_at_utc=None),
        'C':dict(status='success',updated_at=END,watermark_published_at_utc=END)})
    symbols,starts,resume,skipped=cli._resolve_checkpoint_aware_import_scope(symbols=['A','B','C'],
        start_utc=START,end_utc=END,repository=repo,config=EventSentimentConfig(),logger=logging.getLogger('test'))
    assert symbols==['A','B'] and skipped==1
    assert starts=={'A':START,'B':START} and resume=={'A':False,'B':False}


def test_eodhd_page_failure_preserves_success_boundary_and_restart_zero():
    service=bare(); checkpoints=[]; commits=[]; seen=[]
    service.repository=SimpleNamespace(
        get_checkpoint=lambda *a:dict(next_page_token='500',watermark_published_at_utc=START.replace(tzinfo=None)),
        upsert_checkpoint=lambda *a,**k:checkpoints.append((a,k)),get_existing_article_ids=lambda ids:[],
        persist_news_page=lambda raw,tickers,**kw:commits.append(raw) or {'landed':len(raw),'ticker_maps':len(tickers)})
    service.mapper=SimpleNamespace(resolve=lambda *a,**k:{})
    service._max_tickers_per_article=25
    service._session_factory=lambda:nullcontext(object())
    from event_sentiment.relevance import DEFAULT_WEIGHTS
    service._ticker_relevance_mode='provider_default'; service._relevance_weights=DEFAULT_WEIGHTS
    service._min_relevance_score=0.
    article=NormalizedNewsArticle(article_id='eodhd:1',headline='Title',summary=None,content='text',
        source='source',author=None,url='https://example.com/1',published_at_utc=START+timedelta(days=1),
        event_timestamp_utc=START,event_timestamp_ny=START,effective_trade_date=START.date(),market_session_tag='regular')
    service._normalize_article=lambda payload:article
    def pages(**kw):
        seen.append(kw)
        yield [{}],'500'
        raise news_client.EodhdNewsFetchError('page2 timeout')
    service._iter_news_pages=pages
    with pytest.raises(news_client.EodhdNewsFetchError) as error:
        service._run_symbol('A',START,END,True)
    assert seen[0]['page_token'] is None
    assert seen[0]['retry_policy'].timeout_seconds==45 and seen[0]['retry_policy'].max_attempts==3
    assert len(commits)==1 and error.value.partial_summary['landed']==1
    assert checkpoints[-1][0][4]=='failed'
    assert checkpoints[-1][0][2]==START.replace(tzinfo=None)
    assert all(args[2]!=END.replace(tzinfo=None) for args,_ in checkpoints)


def setup_cli(monkeypatch,tmp_path,summary):
    monkeypatch.setattr(cli,'__file__',str(tmp_path/'project/event_sentiment/importe_news.py'))
    monkeypatch.setattr(cli,'configure_root_logging',lambda **kw:None)
    monkeypatch.setattr(cli,'load_import_runtime',lambda:ImportRuntime())
    monkeypatch.setattr(cli,'get_all_symbols_from_tradable_universe',lambda:['A','B','C'])
    monkeypatch.setattr(cli,'EventSentimentRepository',lambda:SimpleNamespace(get_checkpoints=lambda *a:{}))
    calls=[]
    class Service:
        def __init__(self,**kw): pass
        def run(self,**kw): calls.append(kw); return summary
    monkeypatch.setattr(cli,'NewsIngestionService',Service)
    return calls


def test_cli_incomplete_nonzero_report_and_explicit_range_preserved(monkeypatch,tmp_path,capsys):
    calls=setup_cli(monkeypatch,tmp_path,dict(status='INCOMPLETE',attempted_symbols=2,
        succeeded_symbols=1,failed_symbols=[dict(symbol='B',error='timeout')],aborted=True,landed=7))
    monkeypatch.setattr(sys,'argv',['importe_news','--start-date','2025-01-01','--end-date','2025-03-31',
        '--continue-on-symbol-error','--resume-checkpoints'])
    with pytest.raises(SystemExit) as err: cli.main()
    assert err.value.code==1 and calls[0]['start_utc'].year==2025
    report=next((tmp_path/'project/artifacts/news_import_runs').glob('*/report.json'))
    value=json.loads(report.read_text(encoding='utf-8'))
    assert value['status']=='INCOMPLETE' and value['unattempted_symbols']==1
    assert value['metrics']['landed']==7
    assert '::alpha_trade_run_summary::' in capsys.readouterr().out


def test_cli_explicit_recent_window(monkeypatch,tmp_path):
    calls=setup_cli(monkeypatch,tmp_path,dict(fetched=0,landed=0))
    monkeypatch.setattr(sys,'argv',['importe_news','--end-date','2026-10-17','--lookback-days','7'])
    cli.main()
    assert calls[0]['start_utc']==START and calls[0]['end_utc']==END


def test_all_success_checkpoints_produce_complete_report_without_fetch(monkeypatch,tmp_path):
    calls=setup_cli(monkeypatch,tmp_path,{})
    monkeypatch.setattr(cli,'EventSentimentRepository',lambda:SimpleNamespace(get_checkpoints=lambda *a:{
        s:dict(status='success',watermark_published_at_utc=END) for s in ['A','B','C']}))
    monkeypatch.setattr(sys,'argv',['importe_news','--end-date','2026-10-17','--lookback-days','7',
                                  '--resume-checkpoints','--continue-on-symbol-error'])
    cli.main()
    assert calls==[]
    report=next((tmp_path/'project/artifacts/news_import_runs').glob('*/report.json'))
    value=json.loads(report.read_text(encoding='utf-8'))
    assert value['status']=='COMPLETED' and value['skipped_symbols']==3
    assert value['attempted_symbols']==0 and value['metrics']['landed']==0


def test_unexpected_cli_error_leaves_terminal_report_not_running(monkeypatch,tmp_path):
    setup_cli(monkeypatch,tmp_path,{})
    class Broken:
        def __init__(self,**kw): pass
        def run(self,**kw): raise RuntimeError('SQL unavailable')
    monkeypatch.setattr(cli,'NewsIngestionService',Broken)
    monkeypatch.setattr(sys,'argv',['importe_news','--continue-on-symbol-error','--lookback-days','7'])
    with pytest.raises(RuntimeError,match='SQL unavailable'): cli.main()
    report=next((tmp_path/'project/artifacts/news_import_runs').glob('*/report.json'))
    assert json.loads(report.read_text(encoding='utf-8'))['status']=='FAILED'


@pytest.mark.parametrize('covered,total,skipped,accepted',[(95,100,0,True),(94,100,0,False),
    (19,20,0,True),(18,20,0,False),(94,100,1,True),(100,100,0,True)])
def test_coverage_threshold_inclusive_on_whole_universe(covered,total,skipped,accepted):
    from event_sentiment.import_runtime import coverage_decision
    decision=coverage_decision(total,covered,skipped,.95)
    assert decision['coverage_accepted']==accepted
    assert decision['success_ratio']==(covered+skipped)/total


def test_global_failure_blocks_even_above_threshold():
    from event_sentiment.import_runtime import coverage_decision
    assert not coverage_decision(100,99,0,.95,blocking_error=True)['coverage_accepted']


@pytest.mark.parametrize('succeeded,blocking,exit_code',[(19,False,0),(18,False,1),(19,True,1)])
def test_cli_threshold_and_end_report(monkeypatch,tmp_path,capsys,succeeded,blocking,exit_code):
    setup_cli(monkeypatch,tmp_path,dict(attempted_symbols=20,succeeded_symbols=succeeded,
        failed_symbols=[dict(symbol=f'KO{i}',error='timeout',blocking_error=blocking) for i in range(20-succeeded)],
        blocking_error=blocking,landed=11))
    monkeypatch.setattr(cli,'get_all_symbols_from_tradable_universe',lambda:[f'S{i}' for i in range(20)])
    summary_path=tmp_path/'summary.json'
    monkeypatch.setattr(sys,'argv',['importe_news','--continue-on-symbol-error','--lookback-days','7',
                                   '--summary-path',str(summary_path)])
    if exit_code:
        with pytest.raises(SystemExit) as error: cli.main()
        assert error.value.code==exit_code
    else:
        cli.main()
    value=json.loads(summary_path.read_text(encoding='utf-8'))
    assert value['coverage_accepted']==(exit_code==0)
    assert value['collection_complete'] is False
    assert value['metrics']['landed']==11
    from event_sentiment.import_runtime import print_stage_report
    print_stage_report(summary_path)
    output=capsys.readouterr().out
    assert f'{20-succeeded} symbole(s) KO / 20' in output and 'KO' in output


def test_stage8_has_final_ko_log_and_preserves_failure_code():
    from ihm.services.pipeline_runner import PipelineLaunchOptions,build_pipeline_command
    script=build_pipeline_command('sentiment_pipeline',PipelineLaunchOptions())[-1]
    assert '--summary-path $newsImportSummary' in script
    assert '[guid]::NewGuid()' in script
    assert "'stage8-'" in script
    final=script.index('-m event_sentiment.import_runtime')
    assert final > script.index('[5/5]')
    assert 'if ($ec -eq 0 -and $LASTEXITCODE -ne 0)' in script[final:]
    assert script.endswith('exit $ec')


@pytest.mark.parametrize('value',[0,True,float('nan'),1.1])
def test_invalid_coverage_threshold(value):
    with pytest.raises(ValueError): ImportRuntime(min_success_ratio=value)


@pytest.mark.parametrize('code',[0,1])
def test_actual_local_ps_chain_logs_ko_and_only_continues_on_zero(tmp_path,code):
    """Only local print/exit child processes; no provider/SQL/ML execution."""
    import subprocess
    from ihm.services.pipeline_runner import _build_chained_ps_commands
    report=tmp_path/'summary.json'
    report.write_text(json.dumps(dict(status='COMPLETED' if code==0 else 'INCOMPLETE',
        requested=20,failed_symbols=[dict(symbol='KO')],unattempted_symbols=0,
        success_ratio=.95,coverage_status='PARTIAL_ACCEPTED' if code==0 else 'INCOMPLETE')),encoding='utf-8')
    quoted=str(report).replace("'","''")
    command=_build_chained_ps_commands([
        ('Fake import',[sys.executable,'-c',f'import sys; sys.exit({code})']),
        ('Next marker',[sys.executable,'-c',"print('NEXT_STEP_MARKER')"])],
        prelude=f"$newsImportSummary = '{quoted}'",
        final_log_command=[sys.executable,'-m','event_sentiment.import_runtime','--report','$newsImportSummary'])
    result=subprocess.run(command,capture_output=True,encoding='utf-8',errors='replace',timeout=30)
    assert result.returncode==code,(result.stdout,result.stderr)
    assert ('NEXT_STEP_MARKER' in result.stdout)==(code==0)
    assert '1 symbole(s) KO / 20' in result.stdout


def test_report_atomic_replacement_retries_windows_lock(monkeypatch,tmp_path):
    from event_sentiment import import_runtime
    destination=tmp_path/'report.json'; destination.write_text('{"old":true}')
    original=Path.replace; attempts=[]
    def replace_file(path,target):
        attempts.append(1)
        assert json.loads(destination.read_text())=={'old':True}
        if len(attempts)<3: raise PermissionError('temporary lock')
        return original(path,target)
    monkeypatch.setattr(Path,'replace',replace_file)
    monkeypatch.setattr(import_runtime.time,'sleep',lambda _:None)
    import_runtime.write_report(destination,dict(status='INCOMPLETE'))
    assert len(attempts)==3 and json.loads(destination.read_text())['status']=='INCOMPLETE'
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('recalc_days', [30, 52])
def test_pipeline_only_bounded_by_default_explicit_history_stays(monkeypatch, recalc_days):
    from ihm.services.pipeline_runner import PipelineLaunchOptions,build_pipeline_command
    monkeypatch.setattr('event_sentiment.import_runtime.load_import_runtime',lambda:ImportRuntime(
        pipeline_lookback_days=7, pipeline_feature_recalc_days=recalc_days))
    script=build_pipeline_command('sentiment_pipeline',PipelineLaunchOptions())[-1]
    assert '--lookback-days 7' in script and '--continue-on-symbol-error' in script
    assert f'--recent-days {recalc_days}' in script and '--resume-features' in script
    assert '--resume-checkpoints' in script and 'ETAPE 8' in script
    historical=build_pipeline_command('sentiment_pipeline',PipelineLaunchOptions(
        sentiment_start_utc='2025-01-01T00:00:00Z',sentiment_end_utc='2025-03-31T23:59:59Z'))[-1]
    assert '--start-date 2025-01-01' in historical and '--lookback-days' not in historical
    assert 'if ($ec -eq 0)' in historical  # No scoring after incomplete import.


@pytest.mark.parametrize('key,value',[('pipeline_lookback_days',0),
    ('pipeline_feature_recalc_days',0),('pipeline_feature_recalc_days',366),
    ('pipeline_feature_recalc_days',True),('pipeline_feature_recalc_days',1.5),
    ('request_timeout_seconds',True),
    ('max_attempts',0),('max_consecutive_symbol_failures',0)])
def test_invalid_runtime(key,value):
    with pytest.raises(ValueError): ImportRuntime(**{key:value})


@pytest.mark.parametrize('status',[401,403,429,404,500])
def test_eodhd_http_errors_classified_without_real_api(monkeypatch,status):
    monkeypatch.setattr(news_client,'_get_token',lambda:'secret')
    monkeypatch.setattr(news_client,'_get_base_url',lambda:'https://example.com/api')
    response=requests.Response(); response.status_code=status
    def request(*a,**kw): raise requests.HTTPError('HTTP error',response=response)
    monkeypatch.setattr(news_client,'request_with_retry',request)
    with pytest.raises(news_client.EodhdNewsFetchError) as error:
        news_client.fetch_news_page(START,END,['A'],session=object())
    assert error.value.status_code==status
    assert error.value.terminal==(status in (401,403,429))
