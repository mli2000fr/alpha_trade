"""Dated provider-code changes: isolated files, no network or real SQL."""
import gzip
import json
from datetime import date

import pytest

from service.fr import eodhd_daily_15b as daily
from service.fr import publish_daily_bars_staging as publisher
from service.fr.collection_coverage_remediation import coverage


@pytest.fixture
def migration():
    return dict(old_symbol='PERR.PA', new_symbol='ALPER.PA', isin='FR0000061459',
        effective_from='2026-09-07', currency='EUR', new_mic='ALXP',
        evidence_url='https://live.euronext.com/fr/product/equities/FR0000061459-XPAR',
        provider_checked_at='2026-10-16T00:00:00+00:00')


def identities(tmp_path):
    path = tmp_path/'ids.jsonl.gz'
    with gzip.open(path, 'wt', encoding='utf-8') as stream:
        for symbol, isin in [('PERR.PA', 'FR0000061459'), ('LHYFE.PA', 'FR0014009YQ1')]:
            stream.write(json.dumps(dict(provider_symbol=symbol, isin=isin,
                identity_state='VERIFIED_RESEARCH', provider_status_current='active'))+'\n')
    return path


@pytest.mark.parametrize('start,end,expected', [
    ('2026-09-01', '2026-09-04', {'PERR.PA': ('2026-09-01', '2026-09-04')}),
    ('2026-09-07', '2026-09-11', {'ALPER.PA': ('2026-09-07', '2026-09-11')}),
    ('2026-09-04', '2026-09-08', {'PERR.PA': ('2026-09-04', '2026-09-06'),
                               'ALPER.PA': ('2026-09-07', '2026-09-08')}),
])
def test_temporal_split_never_relabels_old_prices(tmp_path, migration, start, end, expected):
    path=identities(tmp_path); original=path.read_bytes()
    windows=daily.symbol_windows(path, date.fromisoformat(start), date.fromisoformat(end), [migration])
    assert {s:tuple(map(str,w)) for s,w in windows.items() if s!='LHYFE.PA'}==expected
    assert windows['LHYFE.PA']==(date.fromisoformat(start),date.fromisoformat(end))
    assert path.read_bytes()==original


@pytest.mark.parametrize('overrides', [dict(isin='WRONG'),dict(new_symbol='80T.F'),
    dict(new_symbol='../ALPER.PA'),dict(new_symbol='LHYFE.PA'),dict(currency='USD'),
    dict(new_mic='XETR'),dict(provider_checked_at='2099-01-01T00:00:00+00:00'),
    dict(provider_checked_at='2026-10-16'),dict(evidence_url='')])
def test_unqualified_substitution_refused(tmp_path, migration, overrides):
    with pytest.raises(ValueError):
        daily.symbol_windows(identities(tmp_path),date(2026,10,9),date(2026,10,16),
                             [{**migration,**overrides}])


def test_duplicate_migration_refused(tmp_path,migration):
    with pytest.raises(ValueError):
        daily.symbol_windows(identities(tmp_path),date(2026,10,9),date(2026,10,16),[migration,migration])


def row(day):
    return dict(date=str(day),open=70,high=72,low=68,close=71,adjusted_close=71,volume=100)


def test_collector_archives_actual_codes_and_publisher_respects_dates(tmp_path,monkeypatch,migration):
    path=identities(tmp_path); root=tmp_path/'daily'
    monkeypatch.setenv('EODHD_API_TOKEN','test-secret')
    calls=[]
    def fetch(endpoint,token,params,**kw):
        calls.append((endpoint,params))
        if endpoint=='eod/LHYFE.PA': return []
        return [row('2026-09-04')] if endpoint=='eod/PERR.PA' else [row('2026-09-07'),row('2026-09-08')]
    monkeypatch.setattr(daily,'_fetch',fetch)
    result=dict(received_count=0,persisted_count=0,failed_count=0,warning_count=0)
    cfg=dict(lookback_days=7,request_interval_seconds=.1,provider_symbol_migrations=[migration])
    with pytest.raises(RuntimeError,match='1 titre'):
        daily.collect(cfg,result,root=root,identities=path,today=date(2026,9,8))
    params=dict(calls)
    assert params['eod/PERR.PA']['to']=='2026-09-06'
    assert params['eod/ALPER.PA']['from']=='2026-09-07'
    assert result['errors'][0]['symbol']=='LHYFE.PA'  # Never hidden to turn the run green.
    windows=daily.symbol_windows(path,date(2026,9,1),date(2026,9,8),[migration])
    payloads,errors,empty=publisher.prepare(root,list(windows),date(2026,9,1),date(2026,9,8),windows=windows)
    assert not errors
    assert {p['symbol'] for p in payloads}=={'PERR.PA','ALPER.PA'}
    for p in payloads:
        assert all(windows[p['symbol']][0]<=r['day']<=windows[p['symbol']][1] for r in p['rows'])
        assert json.loads((root/'raw'/f"{p['digest']}.json").read_text())['symbol']==p['symbol']
        assert p['request_key'].startswith(p['symbol']+':')
    # A repeated explicit resume skips only complete, hash-checked source windows.
    monkeypatch.setattr(daily,'_fetch',lambda *a,**k:pytest.fail('unexpected network'))
    res=dict(received_count=0,persisted_count=0,failed_count=0,warning_count=0)
    daily.collect(cfg,res,root=root,identities=path,today=date(2026,9,8),resume=True,
                  selected_symbols=['ALPER.PA'])
    assert res['failed_count']==0 and res['resumed_symbols']==1


def test_coverage_counts_each_instrument_session_once():
    days=[date(2026,9,4),date(2026,9,7)]
    expected={'PERR.PA':days[:1],'ALPER.PA':days[1:]}
    report=coverage(list(expected),days,{'PERR.PA':['2026-09-04'], 'ALPER.PA':['2026-09-07']},
                    symbol_sessions=expected)
    assert report['expected_symbol_sessions']==report['present_symbol_sessions']==2
    assert report['coverage_pct']==100


def test_exclusion_applies_after_migration_without_rewriting_reference(tmp_path,migration):
    path=identities(tmp_path); original=path.read_bytes()
    windows=daily.symbol_windows(path,date(2026,10,9),date(2026,10,16),[migration],
                                 excluded_symbols=['LHYFE.PA'])
    assert list(windows)==['ALPER.PA']
    assert path.read_bytes()==original
    assert 'LHYFE.PA' in daily.symbols_from_identities(path)


@pytest.mark.parametrize('exclusions', ['LHYFE.PA', ['LHYFE.PA','LHYFE.PA'],
                                      ['ALHYF.PA'], [None], ['PERR.PA','LHYFE.PA']])
def test_invalid_or_empty_exclusion_refused(tmp_path,exclusions):
    with pytest.raises(ValueError,match='exclu|excluded'):
        daily.symbol_windows(identities(tmp_path),date(2026,10,9),date(2026,10,16),
                             excluded_symbols=exclusions)


def test_excluded_symbol_never_requested_and_cannot_be_reselected(tmp_path,monkeypatch,migration):
    path=identities(tmp_path); root=tmp_path/'daily'
    monkeypatch.setenv('EODHD_API_TOKEN','test-secret')
    calls=[]
    def fetch(endpoint,token,params,**kw):
        calls.append(endpoint)
        assert endpoint=='eod/ALPER.PA'
        return [row(d) for d in ['2026-10-09','2026-10-12','2026-10-13','2026-10-14','2026-10-15','2026-10-16']]
    monkeypatch.setattr(daily,'_fetch',fetch)
    cfg=dict(lookback_days=7,request_interval_seconds=.1,provider_symbol_migrations=[migration],
             excluded_symbols=['LHYFE.PA'])
    result=dict(received_count=0,persisted_count=0,failed_count=0,warning_count=0)
    daily.collect(cfg,result,root=root,identities=path,today=date(2026,10,16))
    assert calls==['eod/ALPER.PA']
    assert result['requested_count']==1 and result['failed_count']==0
    assert result['excluded_symbols']==['LHYFE.PA']
    with pytest.raises(ValueError,match='hors univers'):
        daily.collect(cfg,{},root=root,identities=path,today=date(2026,10,16),
                      selected_symbols=['LHYFE.PA'],dry_run=True)


def test_publisher_excludes_from_coverage_before_sql(tmp_path,monkeypatch,migration):
    monkeypatch.setattr(publisher,'ROOT',tmp_path)
    folder=tmp_path/'artifacts/fr'; folder.mkdir(parents=True)
    path=identities(folder)
    monkeypatch.setattr(publisher,'get_market_engine',lambda *a,**k:pytest.fail('preview SQL'))
    report=publisher.run(start=date(2026,10,9),end=date(2026,10,16),identities=path,
        root=folder/'daily',symbol_migrations=[migration],excluded_symbols=['LHYFE.PA'])
    assert report['status']=='PREVIEW'
    assert report['selected_symbol_count']==1
    assert report['excluded_symbols']==['LHYFE.PA']
    assert report['source_file_coverage']['expected_symbol_sessions']==6
    assert report['source_file_coverage']['missing'][0]['symbol']=='ALPER.PA'
