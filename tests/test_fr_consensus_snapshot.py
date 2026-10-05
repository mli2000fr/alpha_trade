import gzip
import json
from types import SimpleNamespace

import pytest

from service.fr.consensus_snapshot import collect, clean


def setup(tmp_path):
    identities = tmp_path/'identities.gz'
    with gzip.open(identities, 'wt', encoding='utf-8') as stream:
        stream.write(json.dumps(dict(provider_symbol='OR.PA', identity_state='VERIFIED_RESEARCH', provider_status_current='active', isin='FR0000120321'))+'\n')
    cfg = dict(pilot_symbols=['OR.PA'], max_symbols_per_run=3, request_interval_seconds=1)
    result = dict(requested_count=0, received_count=0, persisted_count=0, failed_count=0, warning_count=0)
    return identities, cfg, result


def ticker(currency='EUR', symbol='OR.PA'):
    return SimpleNamespace(get_info=lambda: dict(symbol=symbol, currency=currency, exchange='PAR', targetMeanPrice=400, numberOfAnalystOpinions=12),
                           get_earnings_estimate=lambda **kw: {'0y': {'avg': 12}},
                           get_revenue_estimate=lambda **kw: {},
                           get_eps_trend=lambda **kw: {'0y': {'current': 12, '7daysAgo': 11}})


def test_snapshot_and_replay_no_duplicate_object(tmp_path):
    identities, cfg, result = setup(tmp_path)
    for _ in range(2):
        collect(cfg, result, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: ticker(), sleep=lambda n: None)
    assert len(list((tmp_path/'out/objects').glob('*.json'))) == 1
    observations = list((tmp_path/'out/observations/OR.PA').glob('*.json'))
    assert len(observations) == 2
    row = json.loads(observations[0].read_text())
    assert row['available_at'] == row['observed_at']
    assert row['ml_eligible'] is row['historical_pit'] is row['identity_qualified'] is False
    assert row['coverage']['get_revenue_estimate'] is False
    assert result['warning_count'] == 2


def test_identity_failure_no_archive(tmp_path):
    identities, cfg, result = setup(tmp_path)
    with pytest.raises(RuntimeError):
        collect(cfg, result, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: ticker(currency='USD'), sleep=lambda n: None)
    assert result['failed_count'] == 1
    assert not (tmp_path/'out').exists()


def test_dry_run_no_network_no_write(tmp_path):
    identities, cfg, result = setup(tmp_path)
    collect(cfg, result, root=tmp_path/'out', identities=identities, dry_run=True, ticker_factory=lambda s: pytest.fail('network'))
    assert result['requested_count'] == 1
    assert not (tmp_path/'out').exists()


def test_outside_universe_rejected(tmp_path):
    identities, cfg, result = setup(tmp_path)
    cfg['pilot_symbols'] = ['AAPL.US']
    with pytest.raises(ValueError):
        collect(cfg, result, root=tmp_path/'out', identities=identities, dry_run=True)


def test_nonfinite_missing():
    assert clean({'avg': float('nan'), 'other': float('inf')}) == {'avg': None, 'other': None}


def test_reviewed_identity_contradiction_fails_closed(tmp_path):
    identities, cfg, result = setup(tmp_path)
    cfg['identity_checks'] = {'OR.PA': {'isin': 'FR0000120321', 'yahoo_long_name': "L'Oréal S.A.", 'reviewed_on': '2026-10-05'}}
    with pytest.raises(RuntimeError):
        collect(cfg, result, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: ticker(), sleep=lambda n: None)
    assert result['failed_count'] == 1
    assert not (tmp_path/'out').exists()


def test_complete_info_extra_tables_and_conservative_metadata(tmp_path):
    identities, cfg, result = setup(tmp_path)
    cfg['archive_extra_methods'] = ['get_eps_revisions', 'get_upgrades_downgrades']
    t = ticker()
    original = t.get_info()
    original.update(lastFiscalYearEnd=1735603200, financialCurrency='EUR', customProviderField=123)
    t.get_info = lambda: original
    t.get_eps_revisions = lambda **kw: {'upLast7days': {'0y': 4}}
    t.get_upgrades_downgrades = lambda **kw: {'Firm': {'2026-10-05': 'Analyst A'}}
    collect(cfg, result, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: t, sleep=lambda n: None)
    row = json.loads(next((tmp_path/'out/observations/OR.PA').glob('*.json')).read_text())
    raw = json.loads(__import__('pathlib').Path(row['object_path']).read_text())
    assert raw['raw_info'] == original
    assert raw['tables']['get_eps_revisions']['upLast7days']['0y'] == 4
    assert row['archive_version'] == 'fr-consensus-v2'
    assert row['fiscal_period_state'] == 'UNQUALIFIED_PROVIDER_LABELS'
    assert len(row['endpoint_observations']) == 6
    for endpoint in row['endpoint_observations'].values():
        assert endpoint['started_at'] <= endpoint['received_at'] <= row['available_at']
    assert row['ml_eligible'] is False


def test_optional_endpoint_error_is_explicit_not_invented(tmp_path):
    identities, cfg, result = setup(tmp_path)
    cfg['archive_extra_methods'] = ['get_eps_revisions']
    collect(cfg, result, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: ticker(), sleep=lambda n: None)
    row = json.loads(next((tmp_path/'out/observations/OR.PA').glob('*.json')).read_text())
    assert row['endpoint_observations']['get_eps_revisions']['status'] == 'ERROR'
    assert 'get_eps_revisions:AttributeError' in row['warnings']


def test_unknown_extra_endpoint_rejected_without_network(tmp_path):
    identities, cfg, result = setup(tmp_path)
    cfg['archive_extra_methods'] = ['get_secret']
    with pytest.raises(ValueError, match='non autorisés'):
        collect(cfg, result, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: pytest.fail('network'))
