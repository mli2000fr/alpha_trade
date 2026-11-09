import json
from datetime import datetime,timezone

import pandas as pd
import pytest

from ihm.services import backtesting_registry as registry
from ihm.services.backtesting_import import import_continuous_winner,digest


def write(path,payload):path.write_text(json.dumps(payload,default=str),encoding='utf-8')


@pytest.fixture
def archive(tmp_path,monkeypatch,isolated_winner_config):
    from tests.test_winner_daily_protection import setup
    from backtesting.simulator import BacktestEngine
    from backtesting.winner_campaign_replay import metrics
    cfg,args,_=setup(horizon_sessions=1)
    result=BacktestEngine(cfg).run(**args)
    source=tmp_path/'research';source.mkdir();out=source/'continuous-uniform20pct';out.mkdir()
    report=metrics(result,4000.)
    report.update(status='INCOMPLETE_COVERAGE',finished_at_utc=datetime.now(timezone.utc).isoformat())
    write(out/'report.json',report);write(out/'configuration.json',{})
    write(source/'protocol.json',dict(start=str(cfg.start_date),end=str(cfg.end_date),reference={},annual_models={'2026':{'batch_id':'test'}}))
    write(source/'progress.json',{'status':'COMPLETED_EXPLORATORY'})
    write(source/'isolation.json',{'status':'COMPLETED','violations':[]})
    result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
    result.closed_trades_df.to_csv(out/'trades.csv',index=False)
    result.trade_events_df.to_csv(out/'events.csv',index=False)
    result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
    result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
    pd.DataFrame([{**report,'year':2026,'model':'test'}]).drop(columns=['coverage_gaps'],errors='ignore').to_csv(out/'annual-summary.csv',index=False)
    runs=tmp_path/'ihm';runs.mkdir()
    monkeypatch.setattr(registry,'RUNS_DIR',runs);monkeypatch.setattr(registry,'HISTORY_INDEX_PATH',runs/'history_index.json')
    registry._write_history_index({'keep':dict(run_id='keep',status='completed',run_kind='run')})
    return source,out,report


@pytest.mark.parametrize('result_subdir',['continuous-uniform20pct','result'])
def test_import_is_visible_idempotent_and_deletion_keeps_original_archive(archive,result_subdir):
    from ihm.pages import backtesting as page
    source,out,original=archive
    if result_subdir!=out.name:
        destination=source/result_subdir;out.rename(destination);out=destination
    checksum=digest(out/'report.json')
    record=import_continuous_winner(source,run_id='import-test',label='Continu — modèles annuels',result_subdir=result_subdir)
    assert {r['run_id'] for r in registry.load_backtesting_history()}=={'keep','import-test'}
    assert page._extract_run_dates(record)==('2026-10-19','2026-10-20')
    label=page._format_run_inspect_label(record,{})
    assert 'Continu — modèles annuels' in label and 'couverture incomplète' in label
    report=page._load_run_report(record)
    assert report['summary']['final_value']==pytest.approx(original['final_equity'])
    assert report['summary']['total_trades']==original['closed_lot_trades']
    assert report['run_metadata']['annual_models']=={'2026':{'batch_id':'test'}}
    assert len(page._load_equity_curve_df(record))==2
    assert import_continuous_winner(source,run_id='import-test',result_subdir=result_subdir)==record
    assert registry.delete_backtesting_runs(['import-test'],stop_active=False)['deleted']==['import-test']
    assert digest(out/'report.json')==checksum
    assert {r['run_id'] for r in registry.load_backtesting_history()}=={'keep'}


def test_unfinished_or_changed_sources_are_not_registered(archive):
    source,out,_=archive
    write(source/'progress.json',{'status':'RUNNING'})
    with pytest.raises(ValueError,match='terminé'):import_continuous_winner(source,run_id='bad')
    assert len(registry.load_backtesting_history())==1
    write(source/'progress.json',{'status':'COMPLETED_EXPLORATORY'})
    import_continuous_winner(source,run_id='good')
    report=json.loads((out/'report.json').read_text());report['final_equity']=1.
    write(out/'report.json',report)
    with pytest.raises(ValueError,match='autre archive'):import_continuous_winner(source,run_id='good')
