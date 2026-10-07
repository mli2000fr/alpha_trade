import gzip
import json
from types import SimpleNamespace

import pytest

from service.fr.consensus_daily import collect_daily, normal_name, reference_scope
from service.fr.consensus_snapshot import CollectionPause


def setup(tmp_path, mic='XPAR'):
    identities = tmp_path/'identities.gz'
    row = dict(provider_symbol='OR.PA', identity_state='VERIFIED_RESEARCH', provider_status_current='active', isin='FR0000120321',
               market_reference=[dict(mic=mic, versions=[dict(name="L'OREAL", asof_to=None)])])
    with gzip.open(identities, 'wt', encoding='utf-8') as stream:
        stream.write(json.dumps(row)+'\n')
    cfg = dict(universe_mode='all_verified_active', max_symbols_per_run=400,
               max_endpoint_calls_per_day=20, max_attempts_per_symbol_per_day=2, request_interval_seconds=1)
    return identities, cfg


def result():
    return dict(requested_count=0, received_count=0, persisted_count=0, failed_count=0, warning_count=0)


def ticker(name="L'OREAL", empty=False):
    return SimpleNamespace(get_info=lambda: dict(symbol='OR.PA', shortName=name, quoteType='EQUITY', currency='EUR', exchange='PAR', targetMeanPrice=None if empty else 400, numberOfAnalystOpinions=None if empty else 12),
                           get_earnings_estimate=lambda **kw: {'avg': {'0y': None if empty else 12}, 'currency': {'0y': 'EUR'}},
                           get_revenue_estimate=lambda **kw: {},
                           get_eps_trend=lambda **kw: {})


def test_daily_idempotency_and_resume_no_network(tmp_path):
    identities, cfg = setup(tmp_path)
    a = result()
    collect_daily(cfg, a, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: ticker(), sleep=lambda n: None)
    b = result()
    collect_daily(cfg, b, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: pytest.fail('duplicate network'), sleep=lambda n: None)
    assert a['persisted_count'] == 1
    assert b['persisted_count'] == 0
    assert b['skipped_completed'] == 1
    assert b['endpoint_calls_today'] == 4
    assert b['coverage_ratio'] == 1
    assert len(list((tmp_path/'out/daily_observations').glob('*/observations/OR.PA/*.json'))) == 1


@pytest.mark.parametrize('mic', ['XPAR', 'ALXP', 'XMLI'])
def test_paris_segments_not_us_or_other_market(tmp_path, mic):
    identities, _ = setup(tmp_path, mic=mic)
    total, scope, excluded = reference_scope(identities)
    assert total == len(scope) == 1
    assert excluded == []


def test_identity_conflict_excluded_not_silently_archived(tmp_path):
    identities, cfg = setup(tmp_path)
    r = result()
    collect_daily(cfg, r, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: ticker(name='AUTRE SOCIETE'), sleep=lambda n: None)
    assert r['excluded_identity_count'] == 1
    assert r['persisted_count'] == 0
    assert r['coverage_complete'] is True
    assert r['coverage_ratio'] == 0


def test_currency_only_table_is_not_eps_coverage(tmp_path):
    identities, cfg = setup(tmp_path)
    r = result()
    collect_daily(cfg, r, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: ticker(empty=True), sleep=lambda n: None)
    assert r['empty_count'] == 1
    assert r['persisted_count'] == 0


def test_rate_limit_pause_keeps_partial_counters_and_checkpoint(tmp_path):
    identities, cfg = setup(tmp_path)
    class YFRateLimitError(Exception):
        pass
    t = ticker()
    t.get_earnings_estimate = lambda **kw: (_ for _ in ()).throw(YFRateLimitError())
    r = result()
    with pytest.raises(RuntimeError, match='YAHOO_RATE_LIMIT'):
        collect_daily(cfg, r, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: t, sleep=lambda n: None)
    assert r['pending_count'] == 1
    assert r['endpoint_calls_today'] == 2
    receipts=list((tmp_path/'out/daily_observations').glob('*/endpoints/observations/OR.PA/*.json'))
    assert len(receipts)==1
    assert json.loads(receipts[0].read_text())['endpoint']=='get_info'
    later = result()
    collect_daily(cfg, later, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: ticker(), sleep=lambda n: None)
    assert later['persisted_count'] == 1
    assert later['endpoint_calls_today'] == 6


def test_crash_after_archive_before_checkpoint_recovers(tmp_path):
    identities, cfg = setup(tmp_path)
    r = result()
    collect_daily(cfg, r, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: ticker(), sleep=lambda n: None)
    checkpoint = next((tmp_path/'out/days').glob('*.json'))
    state = json.loads(checkpoint.read_text())
    state['symbols']['OR.PA'] = {'status': 'RUNNING', 'attempts': 2}
    checkpoint.write_text(json.dumps(state))
    later = result()
    collect_daily(cfg, later, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: pytest.fail('network'), sleep=lambda n: None)
    assert later['archived_symbols_today'] == 1
    assert later['skipped_completed'] == 1


def test_normalized_name_not_fuzzy():
    assert normal_name('L&apos;ORÉAL') == normal_name("L'OREAL")
    assert normal_name('ABC') != normal_name('AB SCIENCE')


def test_extra_methods_use_daily_budget_and_are_archived(tmp_path):
    identities, cfg = setup(tmp_path)
    cfg['archive_extra_methods'] = ['get_eps_revisions', 'get_recommendations', 'get_upgrades_downgrades']
    t = ticker()
    for method in cfg['archive_extra_methods']:
        setattr(t, method, lambda **kw: {'value': {'0y': 1}})
    r = result()
    collect_daily(cfg, r, root=tmp_path/'out', identities=identities, ticker_factory=lambda s: t, sleep=lambda n: None)
    assert r['endpoint_calls_today'] == 7
    assert r['persisted_count'] == 1


def test_ihm_checkpoint_is_fr_scoped(tmp_path, monkeypatch):
    from ihm.services import batch_management
    monkeypatch.setattr(batch_management, 'PROJECT_ROOT', tmp_path)
    root = tmp_path/'artifacts/fr/operations/fr_consensus_snapshot/days'
    root.mkdir(parents=True)
    path = root/'2026-10-05.json'
    path.write_text(json.dumps({'market_code': 'FR_EQ', 'day': '2026-10-05', 'symbols': {}}))
    spec = SimpleNamespace(name='fr_consensus_snapshot')
    assert batch_management.read_fr_consensus_state(spec)['day'] == '2026-10-05'
    path.write_text(json.dumps({'market_code': 'US_EQ', 'day': '2026-10-05'}))
    with pytest.raises(ValueError):
        batch_management.read_fr_consensus_state(spec)
