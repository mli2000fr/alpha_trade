import ast
from datetime import date
import inspect
from pathlib import Path

import pytest

from common.market_cap import load_market_cap_config
from corporate_actions import cli
from dataIntegrityEngine import update_sector
from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command, pipeline_page_default_options
from modelFactory import fundamental_features
from scripts.audit_market_cap_coverage import summarize
from service._http_retry import CircuitOpenError
from service.forward_pit import batch


def test_shared_page_scheduler_defaults_have_no_yahoo():
    for options in [PipelineLaunchOptions(),pipeline_page_default_options(trade_date='2026-10-16')]:
        cmd=build_pipeline_command('update_sector',options)
        assert cmd[cmd.index('--provider')+1]=='finnhub'
        cmd=build_pipeline_command('corporate_actions_sync',options)
        assert cmd[cmd.index('--cross-check')+1]=='none'
        assert 'yahoo' not in ' '.join(cmd).lower()


@pytest.mark.parametrize('name',['yahoo','yahoo_finance','yfinance'])
def test_step2_rejects_yahoo_before_any_collection(name):
    with pytest.raises(ValueError,match='Yahoo retiré'):
        update_sector._normalize_provider(name)


@pytest.mark.parametrize('command',['sync','run'])
def test_corporate_actions_cli_cannot_enable_yahoo(command):
    assert cli._build_parser().parse_args([command]).cross_check=='none'
    with pytest.raises(SystemExit):
        cli._build_parser().parse_args([command,'--cross-check','yahoo'])


def test_market_cap_fallback_skips_fresh_finnhub_and_measures_scopes(monkeypatch):
    from service.forward_pit import market_cap_calculations as calc
    monkeypatch.setattr(calc,'require_schema',lambda e:None)
    monkeypatch.setattr(calc,'reference_session',lambda *a,**k:date(2026,10,16))
    monkeypatch.setattr(calc,'calculate_sec',lambda *a,**k:dict(symbols={'A'},persisted=1,details={}))
    monkeypatch.setattr(calc,'calculate_finnhub',lambda *a,**k:dict(symbols={'B','C'},persisted=2,details={}))
    monkeypatch.setattr(batch,'_symbols',lambda cfg:['A','B','C'] if cfg.get('symbols_file')!='core' else ['A','C','OUT'])
    calls=[]
    def fetch(symbols,**kwargs):
        calls.append((kwargs['provider'],symbols,kwargs))
        return {'stored':len(symbols),'failed':0,'errors':[]}
    def covered(engine,symbols,as_of,age,sources):
        if sources==('SEC_EDGAR',):return {'A'}
        assert sources==('FINNHUB',)
        return {'B','C'} if calls[-1][0]=='finnhub' else {'B'}
    monkeypatch.setattr(fundamental_features,'fetch_and_store_fundamentals',fetch)
    monkeypatch.setattr(batch,'_market_cap_covered_symbols',covered)
    outcome=batch.market_cap_sync(object(),{'coverage_reference_symbols_file':'core'},'test',False)
    assert [(p,s) for p,s,k in calls]==[('sec',['A','B','C']),('finnhub',['C'])]
    assert calls[1][2]['sleep_seconds']==1.1 and calls[1][2]['stop_on_circuit_open']
    assert outcome.received==3
    assert outcome.details['providers']['finnhub']['fresh_before_run']==1
    assert outcome.details['providers']['finnhub']['newly_covered']==1
    ref=outcome.details['coverage_scopes']['tradable_reference']
    assert ref['covered_symbols']==2 and ref['outside_collection_count']==1


def test_old_batch_configuration_cannot_silently_call_yahoo(monkeypatch):
    monkeypatch.setattr(batch,'_symbols',lambda cfg:['A'])
    with pytest.raises(ValueError,match='Yahoo retiré'):
        batch.market_cap_sync(object(),{'fallback_providers':'yahoo_finance,finnhub'},'test',False)


def test_finnhub_circuit_open_defers_remainder_without_retry_storm(monkeypatch):
    calls=[]
    def fetch(symbol,**kwargs):
        calls.append(symbol)
        if symbol=='B':raise CircuitOpenError('test')
        return {'sector':'Technology','market_cap':100,'source':'Finnhub'}
    monkeypatch.setattr(fundamental_features,'_fetch_fundamentals_record',fetch)
    monkeypatch.setattr(fundamental_features,'_upsert_fundamentals_row',lambda *a,**kw:None)
    monkeypatch.setattr('time.sleep',lambda s:None)
    result=fundamental_features.fetch_and_store_fundamentals(['A','B','C'],engine=object(),provider='finnhub',stop_on_circuit_open=True)
    assert calls==['A','B'] and result['stored']==1 and result['deferred']==2
    assert result['failed']==0  # Not attempted; the handler still fails missing coverage.


def test_finnhub_interval_checked_before_network():
    with pytest.raises(ValueError,match='Intervalle'):
        fundamental_features.fetch_and_store_fundamentals(['A'],engine=object(),provider='finnhub',sleep_seconds=.25)


def test_measured_observations_are_not_automatically_computable_cap():
    row=summarize({'A','B','C','D'},{'A','B'},{'B','C'},{'A'})
    assert row['covered_observations']==3 and row['sec_with_reference_close']==1
    assert row['finnhub_incremental_over_sec']==1 and row['potentially_computable_market_cap']==3
    row=summarize({'A','B','C','D'},{'A','B'},{'C'},{'A'})
    assert row['covered_observations']==3 and row['potentially_computable_market_cap']==2
    assert row['missing_computable']==['B','D']


def test_no_yahoo_download_import_in_changed_entry_paths():
    for file in ['corporate_actions/cli.py','dataIntegrityEngine/update_sector.py']:
        tree=ast.parse(Path(file).read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                assert 'yahoo' not in (node.module or '').lower()


def test_b2_is_auxiliary_not_daily_step_two():
    from ihm.services.pipeline_runner import get_pipeline_steps
    assert next(s for s in get_pipeline_steps() if s.num=='2').key=='data_sanitizer_daily'
    assert 'update_sector' not in {s.key for s in get_pipeline_steps()}


def test_yahoo_only_rows_never_become_composite_fallback():
    import pandas as pd
    from common.publish_tradable_universe import _select_market_cap_rows
    rows=pd.DataFrame([dict(symbol='A',market_value=100,market_cap_source='YAHOO FINANCE',market_cap_reference_date='2026-10-16')])
    assert _select_market_cap_rows(rows,snapshot_date=date(2026,10,18),max_age_days=365,provider='sec_edgar_then_finnhub').empty
