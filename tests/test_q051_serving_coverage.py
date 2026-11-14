"""Serving eligibility changes coverage only; ranking/inference remain full-model."""
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
import json

import numpy as np
import pandas as pd
import pytest

from service.q051_paper import coverage as c

NOW = datetime(2026, 11, 14, 10, tzinfo=UTC)
DAY = date(2026, 11, 13)


@pytest.fixture
def sample(monkeypatch):
    def paper(account, mode='paper'):
        if not account or mode != 'paper':
            raise ValueError('PAPER requis')
    monkeypatch.setattr(c, 'require_paper', paper)
    names = [f'S{i:04}' for i in range(1790)]
    raw = [dict(symbol=name, id=name, status='active', tradable=True, **{'class':'us_equity'})
           for name in names[:1734]]
    return names, raw, c.receipt(raw, names, account='default', day=DAY, observed_at=NOW)


def test_93_percent_uses_only_tradable_numerator_and_preserves_default(sample):
    from modelFactory.oracle_path.predict import validate_prediction_coverage
    names, _, scope = sample
    # One additional nontradable row must not inflate 1643 / 1734.
    frame = pd.DataFrame(dict(date=pd.Timestamp(DAY), symbol=names[:1643]+[names[-1]]))
    proto = dict(min_daily_universe=20, directional_contract=dict(oracle_top_n=20))
    eligible = c.validate(scope, names, [DAY], now=NOW)
    validate_prediction_coverage(frame, eligible, [DAY], proto, .93)
    assert len(eligible) == 1734 and len(scope['excluded']) == 56
    with pytest.raises(ValueError, match='1644/1790, minimum 1665'):
        validate_prediction_coverage(frame, names, [DAY], proto, .93)
    # Below the SAME 93% threshold, extra excluded scores cannot rescue coverage.
    low = pd.DataFrame(dict(date=pd.Timestamp(DAY), symbol=names[:1612]+names[1734:]))
    with pytest.raises(ValueError, match='1612/1734, minimum 1613'):
        validate_prediction_coverage(low, eligible, [DAY], proto, .93)


@pytest.mark.parametrize('mutation', ['live','future','stale','history','subset','eligible','source','multiday','empty'])
def test_scope_cannot_be_reused_for_live_history_or_changed_population(sample, mutation):
    names, _, original = sample
    scope = deepcopy(original)
    days = [DAY]
    if mutation == 'live': scope['broker_mode'] = 'live'
    if mutation == 'future': scope['observed_at'] = (NOW+timedelta(seconds=1)).isoformat()
    if mutation == 'stale': scope['observed_at'] = (NOW-timedelta(minutes=11)).isoformat()
    if mutation == 'history': scope['signal_day'] = '2026-11-12'; days = [date(2026,11,12)]
    if mutation == 'subset': names = names[:-1]
    if mutation == 'eligible': scope['eligible'].append(names[-1])
    if mutation == 'source': scope['source']['endpoint'] = 'https://api.alpaca.markets/v2/assets'
    if mutation == 'multiday': days.append(DAY)
    if mutation == 'empty': scope['eligible'] = []
    with pytest.raises(ValueError):
        c.validate(scope, names, days, now=NOW)


def test_receipt_requires_complete_typed_unique_response(sample):
    names, raw, _ = sample
    for payload in [[], raw+[raw[0]], [dict(raw[0],tradable='true')], [dict(raw[0],status='inactive')]]:
        with pytest.raises(ValueError):
            c.receipt(payload, names, account='default', day=DAY, observed_at=NOW)
    raw[0]['tradable'] = False
    out = c.receipt(raw, names, account='default', day=DAY, observed_at=NOW)
    assert names[0] not in out['eligible'] and names[0] in out['excluded']


def test_actual_prediction_keeps_full_feature_population_and_all_observed_rows(sample, monkeypatch, tmp_path):
    from modelFactory.oracle_path import predict as p, directional as d
    names, _, scope = sample
    root = tmp_path
    (root/'feature_profile.json').write_text('{}')
    protocol = dict(horizon=10, universe=names, target='path', min_daily_universe=20,
                    directional_contract=dict(oracle_top_n=20))
    fold = dict(backend='lightgbm', model_file='dummy', model_sha256='sha',
                metrics=dict(fold_start='2026-01-02', train_available_max='2025-01-01', val_available_max='2025-12-31'))
    monkeypatch.setattr(p,'load_contract',lambda *a:(root,protocol,dict(feature_columns=['x'],generator_options={}),{'2026-01-02':fold}))
    monkeypatch.setattr(d,'enabled',lambda _:True)
    monkeypatch.setattr(p,'prediction_coverage_ratio',lambda:.93)
    original_validate = c.validate
    monkeypatch.setattr(c,'validate',lambda value, universe, days:original_validate(value,universe,days,now=NOW))
    built, saved = [], []
    def features(engine, universe, *args):
        built.append(universe)
        return pd.DataFrame(dict(date=pd.Timestamp(DAY),symbol=names[:1643]+[names[-1]],x=1.))
    monkeypatch.setattr(p,'build_inference_features',features)
    monkeypatch.setattr('lightgbm.Booster',lambda **kw:SimpleNamespace(feature_name=lambda:['x']))
    monkeypatch.setattr(p,'model_probabilities',lambda *args:np.full(len(args[-1]),.7))
    monkeypatch.setattr(d,'infer',lambda e,r,s:s)
    monkeypatch.setattr(d,'write_predictions',lambda *a:None)
    monkeypatch.setattr(p,'write_path_predictions',lambda e,s,*a,**k:saved.append(s.copy()) or len(s))
    result=p.predict_oracle_path_history(SimpleNamespace(url=SimpleNamespace(database='alpha_trade')),
        'batch',DAY,DAY,paper_serving_coverage=scope)
    assert built == [names] and len(saved[0]) == 1644
    assert names[-1] in set(saved[0].symbol)  # denominator eligibility is not a ranking filter
    assert result['model_universe_count']==1790 and result['coverage_universe_count']==1734
    assert result['min_prediction_coverage_ratio']==.93
    with pytest.raises(ValueError,match='minimum 1665'):
        p.predict_oracle_path_history(object(),'batch',DAY,DAY)


def test_q051_archives_scope_and_ranks_top179_then_seals(sample, monkeypatch, tmp_path):
    from service.q051_paper import pipeline as p
    names, raw, scope = sample
    root = tmp_path/'model'; (root/'directional').mkdir(parents=True)
    for name in ['protocol.json','directional/manifest.json']: (root/name).write_text('{}')
    monkeypatch.setattr(p,'ARTIFACTS',tmp_path/'runs')
    monkeypatch.setattr(p,'contract',lambda *a:(root,dict(universe=names)))
    monkeypatch.setattr(p,'make_broker',lambda *a:(None,MagicMock(),None))
    monkeypatch.setattr(c,'capture',lambda *a,**k:(scope,raw))
    calls=[]
    monkeypatch.setattr('modelFactory.oracle_path.predict.predict_oracle_path_history',lambda *a,**k:calls.append(k))
    monkeypatch.setattr('modelFactory.oracle_path.predict.prediction_coverage_ratio',lambda:.93)
    frame = pd.DataFrame(dict(date=pd.Timestamp(DAY),symbol=names[:1643],
        proba_extreme=np.linspace(.99,.01,1643),long_probability=.7,short_probability=.3,long_auc=.7,
        long_auc_available_date=pd.Timestamp('2025-12-31'),long_auc_source='calibration',
        long_auc_model_sha256='sha',long_model_sha256='sha'))
    monkeypatch.setattr('modelFactory.oracle.predictions_store.load_oracle_predictions',lambda *a,**k:frame)
    monkeypatch.setattr('modelFactory.oracle_path.directional.read_predictions',lambda *a,**k:frame)
    monkeypatch.setattr('backtesting.per_symbol_selection.attach_calibration_auc',lambda f,r:f)
    report = p.predict(None,run_id='q051-'+'a'*32,batch='batch',day=DAY,artifacts_dir=root)
    assert report['universe_count']==1790 and report['policy']['oracle_top_n']==179
    assert report['coverage']['observed']==1643 and report['coverage']['denominator']==1734
    assert len(report['selected'])==5 and calls[0]['symbols']==names
    assert calls[0]['paper_serving_coverage']==scope
    folder, _ = p.qualified(report['run_id'],batch='batch',day=DAY,artifacts_dir=root)
    (folder/'coverage.json').write_text(json.dumps(dict(scope,eligible=[])))
    with pytest.raises(ValueError,match='preuve de couverture modifiée'):
        p.qualified(report['run_id'],batch='batch',day=DAY,artifacts_dir=root)
