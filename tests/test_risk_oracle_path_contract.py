"""Signed Oracle contract replaces, not bypasses, per-symbol registry checks."""
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from modelFactory.oracle_path.predict import load_contract
from modelFactory.oracle_path.train import digest
from risk_management.models import PredictionInfo
from risk_management.oracle_path_contract import check_compatibility
from tests.test_oracle_path_serving import model

DAY = date(2024,1,2)
NOW = datetime(2024,1,3,8,tzinfo=timezone.utc)


@pytest.fixture
def serving(model):
    parent, root, universe = model
    engine = create_engine('sqlite://')
    _, _, _, folds = load_contract(parent, 'batch')
    with engine.begin() as conn:
        conn.execute(text('''CREATE TABLE oracle_extreme_predictions (symbol TEXT,prediction_date DATE,
            batch_id TEXT,proba_extreme REAL,fold_start DATE,created_at TIMESTAMP)'''))
        conn.execute(text('''CREATE TABLE oracle_path_prediction_lineage (symbol TEXT,prediction_date DATE,
            batch_id TEXT,fold_start DATE,model_available_date DATE,target_name TEXT,target_horizon INTEGER,
            model_sha256 TEXT,feature_profile_sha256 TEXT,created_at TIMESTAMP)'''))
        conn.execute(text('''CREATE TABLE model_predictions (symbol TEXT,prediction_date DATE,run_id TEXT,
            source TEXT,predicted_side TEXT,created_at TIMESTAMP)'''))
        conn.execute(text("INSERT INTO oracle_extreme_predictions VALUES ('S00','2024-01-02','batch',.8,'2023-12-01','2024-01-02 22:00:00')"))
        conn.execute(text("""INSERT INTO oracle_path_prediction_lineage VALUES ('S00','2024-01-02','batch',
            '2023-12-01','2023-11-30','oracle_path_extreme20',20,:model,:profile,'2024-01-02 22:00:00')"""),
            dict(model=folds['2023-12-01']['model_sha256'], profile=digest(root/'feature_profile.json')))
        conn.execute(text("INSERT INTO model_predictions VALUES ('S00','2024-01-02','batch_oracle_synth','oracle_path_policy','long','2024-01-02 22:01:00')"))
    proxy = SimpleNamespace(url=SimpleNamespace(database='alpha_trade'), dialect=engine.dialect, connect=engine.connect)
    pred = PredictionInfo('S00', .8, 1, 'batch_oracle_synth', DAY, predicted_side='long')
    return engine, proxy, parent, root, pred


def check(serving, **kwargs):
    _, engine, parent, _, pred = serving
    return check_compatibility(engine, {'S00':pred}, batch_id='batch', trade_date=DAY,
                               artifacts_dir=parent, now=NOW, **kwargs)


def test_valid_contract_passes_without_legacy_registry(serving):
    result = check(serving)
    assert result['compatible'] and result['issues'] == []
    assert result['source'] == 'oracle_path_signed_contract'
    assert result['fold_start'] == '2023-12-01'
    assert result['session_freshness']['signal_date'] == '2024-01-02'


@pytest.mark.parametrize('horizon',[10,15])
def test_shorter_path_contract_preserves_all_risk_checks(serving,horizon):
    import json
    from hashlib import sha256
    from modelFactory.oracle_path import target_name,mode_name
    engine,_,_,root,_=serving
    protocol_path=root/'protocol.json'
    protocol=json.loads(protocol_path.read_text())
    protocol.update(horizon=horizon,target=target_name(horizon),mode=mode_name(horizon))
    frozen={k:v for k,v in protocol.items() if k!='fingerprint'}
    protocol['fingerprint']=sha256(json.dumps(frozen,sort_keys=True,default=str).encode()).hexdigest()
    protocol_path.write_text(json.dumps(protocol))
    for name in ['feature_profile.json','report.json']:
        path=root/name;data=json.loads(path.read_text());data['mode']=mode_name(horizon)
        if name=='feature_profile.json':data['target']=target_name(horizon)
        path.write_text(json.dumps(data))
    with engine.begin() as conn:
        conn.execute(text('UPDATE oracle_path_prediction_lineage SET target_horizon=:h,target_name=:target,'
            'feature_profile_sha256=:profile'),dict(h=horizon,target=target_name(horizon),profile=digest(root/'feature_profile.json')))
    result=check(serving)
    assert result['compatible'] and result['horizon']==horizon
    with engine.begin() as conn:
        conn.execute(text('UPDATE oracle_path_prediction_lineage SET target_horizon=20'))
    assert not check(serving)['compatible']


@pytest.mark.parametrize('sql', [
    'DELETE FROM oracle_path_prediction_lineage',
    "UPDATE oracle_path_prediction_lineage SET model_sha256='wrong'",
    "UPDATE oracle_path_prediction_lineage SET target_horizon=10",
    "UPDATE oracle_path_prediction_lineage SET feature_profile_sha256='wrong'",
    "UPDATE oracle_path_prediction_lineage SET model_available_date='2024-01-02'",
    "UPDATE oracle_path_prediction_lineage SET fold_start='2024-07-01'",
    "UPDATE oracle_extreme_predictions SET created_at='2024-01-04 00:00:00'",
    "UPDATE oracle_path_prediction_lineage SET created_at='2024-01-04 00:00:00'",
    "UPDATE model_predictions SET created_at='2024-01-04 00:00:00'",
    "UPDATE model_predictions SET source='per_symbol'",
    "UPDATE model_predictions SET predicted_side='short'",
    "UPDATE oracle_extreme_predictions SET proba_extreme=1.5",
])
def test_bad_or_future_lineage_and_policy_remain_blocked(serving, sql):
    with serving[0].begin() as conn:
        conn.execute(text(sql))
    result = check(serving)
    assert not result['compatible'] and result['issues']


@pytest.mark.parametrize('change', ['weights','missing_contract','wrong_batch','wrong_day','research_only'])
def test_artifacts_or_prediction_identity_fail_closed(serving, change):
    from dataclasses import replace
    engine, proxy, parent, root, pred = serving
    if change == 'weights':
        (root/'folds/2023-12-01/path_model.txt').write_text('corrupt')
    if change == 'missing_contract':
        (root/'protocol.json').unlink()
    if change == 'wrong_batch': pred = replace(pred, run_id='other_oracle_synth')
    if change == 'wrong_day': pred = replace(pred, prediction_date=date(2024,1,1))
    if change == 'research_only': pred = replace(pred, research_only=True)
    result = check((engine,proxy,parent,root,pred))
    assert not result['compatible'] and result['issues']


@pytest.mark.parametrize('now', [datetime(2024,1,2,20,tzinfo=timezone.utc),
    datetime(2024,1,3,15,tzinfo=timezone.utc), datetime(2024,1,4,8,tzinfo=timezone.utc)])
def test_preclose_postopen_or_stale_signal_stays_blocked(serving, now):
    _, engine, parent, _, pred = serving
    result = check_compatibility(engine, {'S00':pred}, batch_id='batch', trade_date=DAY,
                                 artifacts_dir=parent, now=now)
    assert not result['compatible'] and result['issues']
