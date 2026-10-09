from datetime import datetime, UTC
import json
from types import SimpleNamespace

import numpy as np
import pytest

from service.fr import local_shadow_simulation as shadow


def population():
    return [{'research_uid':str(i),'isin':f'ISIN{i}','symbol':f'X{i}.PA',
        'resolved_mic':'XPAR','observed_provider_feature_inputs_usable':True,
        'orders_allowed':False,'shadow_eligible':False} for i in range(164)]


def test_top20_is_model_score_order_not_future_return():
    rows = population()
    scores = np.linspace(0,1,164)
    ranked = shadow.rank_scores(rows,scores,'2026-10-09')
    assert sum(r['selected_top20'] for r in ranked) == 33
    assert ranked[0]['research_uid'] == '163'
    assert ranked[0]['oracle_score_raw'] == 1
    assert not ranked[-1]['selected_top20']


def test_equal_score_ties_deterministic():
    rows = population()
    first = shadow.rank_scores(rows,[.5]*164,'2026-10-09')
    second = shadow.rank_scores(list(reversed(rows)),[.5]*164,'2026-10-09')
    assert [r['research_uid'] for r in first] == [r['research_uid'] for r in second]


@pytest.mark.parametrize('scores', [[.2],[np.nan,.5],[np.inf,.5],[-.1,.5],[1.01,.5]])
def test_invalid_scores_fail_closed(scores):
    with pytest.raises(ValueError,match='Invalid model scores'):
        shadow.rank_scores(population()[:2],scores,'2026-10-09')


def test_subset_exact_identity_and_nonserving_contract(tmp_path):
    rows = population()
    payload = {'market_code':'FR_EQ','serving_enabled':False,
               'historical_selection_allowed':False,'instruments':rows}
    manifest = {'universe':[{'research_uid':r['research_uid'],'isin':r['isin'],
                           'provider_symbol':r['symbol']} for r in rows]}
    path = tmp_path/'subset.json'
    path.write_text(json.dumps(payload))
    assert len(shadow.read_subset(path,manifest)[1]) == 164
    rows[0]['isin'] = 'WRONG'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='mismatch'):
        shadow.read_subset(path,manifest)


def test_duplicate_population_rejected(tmp_path):
    rows = population()
    rows[-1] = rows[0]
    path = tmp_path/'subset.json'
    path.write_text(json.dumps({'market_code':'FR_EQ','serving_enabled':False,
        'historical_selection_allowed':False,'instruments':rows}))
    with pytest.raises(ValueError,match='unique frozen'):
        shadow.read_subset(path,{'universe':[]})


def protocol_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow,'ROOT',tmp_path)
    source = tmp_path/'artifacts/fr/subset.json'
    source.parent.mkdir(parents=True)
    source.write_text('{}')
    bootstrap = tmp_path/'artifacts/fr/bootstrap'
    manifest = {'universe':[]}
    protocol = dict(schema_version=1,market_code='FR_EQ',purpose='LOCAL_UNQUALIFIED_SHADOW',
        universe_count=164,mic='XPAR',oracle_horizon=5,selection_fraction=.20,
        minimum_cross_section=20,seed=17,orders_allowed=False,sql_writes=False,
        serving_allowed=False,training_allowed=False,source_sha256=shadow.digest(source),
        model_manifest=manifest,bootstrap_dir='artifacts/fr/bootstrap',
        implementation_sha256=shadow.implementation_hashes(),
        frozen_at='2026-10-09T18:30:00+00:00',decision_date='2026-10-12')
    monkeypatch.setattr(shadow,'get_market_calendar',lambda *a,**k:SimpleNamespace(
        session=lambda day:SimpleNamespace(open_at_utc=datetime(2026,10,12,7,tzinfo=UTC))))
    return source,bootstrap,manifest,protocol


def test_protocol_frozen_before_decision_required(tmp_path,monkeypatch):
    source,bootstrap,manifest,p = protocol_fixture(tmp_path,monkeypatch)
    shadow.validate_protocol(p,manifest,source,bootstrap)
    p['frozen_at'] = '2026-10-12T07:00:00+00:00'
    with pytest.raises(ValueError,match='precede'):
        shadow.validate_protocol(p,manifest,source,bootstrap)


@pytest.mark.parametrize('key,value', [('orders_allowed',True),('sql_writes',True),
    ('serving_allowed',True),('training_allowed',True),('oracle_horizon',20),
    ('minimum_cross_section',3),('selection_fraction',.1)])
def test_protocol_mutation_cannot_release_or_tune(tmp_path,monkeypatch,key,value):
    source,bootstrap,manifest,p = protocol_fixture(tmp_path,monkeypatch)
    p[key] = value
    with pytest.raises(ValueError,match='modified or unsafe'):
        shadow.validate_protocol(p,manifest,source,bootstrap)


def test_frozen_source_and_model_cannot_change(tmp_path,monkeypatch):
    source,bootstrap,manifest,p = protocol_fixture(tmp_path,monkeypatch)
    source.write_text('{"changed":true}')
    with pytest.raises(ValueError,match='lineage changed'):
        shadow.validate_protocol(p,manifest,source,bootstrap)


def test_implementation_change_blocks_frozen_protocol(tmp_path,monkeypatch):
    source,bootstrap,manifest,p = protocol_fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(shadow,'implementation_hashes',lambda:{'changed':'abc'})
    with pytest.raises(ValueError,match='lineage changed'):
        shadow.validate_protocol(p,manifest,source,bootstrap)


def test_future_prospective_run_does_not_infer_or_write(tmp_path,monkeypatch):
    source,bootstrap,manifest,p = protocol_fixture(tmp_path,monkeypatch)
    proto = source.parent/'protocol.json'
    proto.write_text(json.dumps(p))
    monkeypatch.setattr(shadow,'prepare_manifest',lambda:manifest)
    monkeypatch.setattr(shadow,'read_subset',lambda *a:({'audit_at':p['frozen_at']},[]))
    monkeypatch.setattr(shadow,'observed_payloads',lambda *a:pytest.fail('archive read'))
    monkeypatch.setattr(shadow,'joblib',SimpleNamespace(load=lambda *a:pytest.fail('model load')))
    # Supply an explicit future opening independent of today's environment date.
    future = datetime(2099,1,1,7,tzinfo=UTC)
    monkeypatch.setattr(shadow,'get_market_calendar',lambda *a,**k:SimpleNamespace(
        session=lambda day:SimpleNamespace(open_at_utc=future)))
    output = tmp_path/'artifacts/fr/research/local_shadow_simulation/future'
    with pytest.raises(ValueError,match='not yet reached'):
        shadow.run(phase='prospective',output=output,subset=source,
            bootstrap=bootstrap,protocol_path=proto)
    assert not output.exists()
