"""Offline serving tests: real small Booster, zero broker / production SQL calls."""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle_path import MODE, TARGET
from modelFactory.oracle_path import predict as module
from modelFactory.oracle_path.train import digest


@pytest.fixture
def model(tmp_path):
    import lightgbm as lgb
    root = tmp_path/'batch'/'oracle_path'
    root.mkdir(parents=True)
    universe = [f'S{i:02}' for i in range(20)]
    protocol = dict(mode=MODE, batch_id='batch', target=TARGET, horizon=20, serving_ready=True,
        universe=universe, generator_options={'enable_cross_sectional_ranks': False})
    protocol['fingerprint'] = sha256(json.dumps(protocol, sort_keys=True, default=str).encode()).hexdigest()
    (root/'protocol.json').write_text(json.dumps(protocol))
    (root/'feature_profile.json').write_text(json.dumps(dict(mode=MODE, target=TARGET, serving_ready=True,
        feature_columns=['x'], generator_options=protocol['generator_options'])))
    (root/'report.json').write_text(json.dumps(dict(status='completed', mode=MODE,
        batch_id='batch', n_folds=2, serving_ready=True)))
    frame = pd.DataFrame({'x': np.arange(20, dtype=float)})
    booster = lgb.train(dict(objective='binary', verbosity=-1, num_threads=1, min_data_in_leaf=2),
        lgb.Dataset(frame, label=(frame.x > 9).astype(int)), num_boost_round=3)
    for start, available in [('2023-12-01', '2023-11-30'), ('2024-07-01', '2024-06-28')]:
        folder = root/'folds'/start
        folder.mkdir(parents=True)
        booster.save_model(str(folder/'path_model.txt'))
        done = dict(metrics=dict(fold_start=start, train_available_max='2023-06-01',
            val_available_max=available), files={'path_model.txt': digest(folder/'path_model.txt')})
        (folder/'done.json').write_text(json.dumps(done))
    return tmp_path, root, universe


def features(universe, start, end):
    return pd.DataFrame([dict(date=d, symbol=s, x=float(i))
        for d in pd.bdate_range(start, end) for i, s in enumerate(universe)])


def test_real_booster_inference_preserves_scope_causality_and_no_targets(model, monkeypatch):
    parent, root, universe = model
    calls, saved = [], []
    def build(engine, all_symbols, start, end, options):
        calls.append(all_symbols)
        return features(all_symbols, start, end)
    monkeypatch.setattr(module, 'build_inference_features', build)
    monkeypatch.setattr(module, 'write_path_predictions', lambda e, f, b: saved.append(f.copy()) or len(f))
    engine = SimpleNamespace(url=SimpleNamespace(database='alpha_trade'))
    result = module.predict_oracle_path_history(engine, 'batch', '2024-01-02', '2024-01-03',
        artifacts_dir=parent, symbols=universe[:2], persist_chunk_dates=1)
    frame = pd.concat(saved)
    assert result['n_rows'] == 4 and result['directional'] is False
    assert calls == [universe, universe]  # XS population not the selected two
    assert set(frame.symbol) == set(universe[:2])
    assert set(frame.fold_start) == {'2023-12-01'}
    assert frame.proba_extreme.between(0, 1).all()
    assert pd.to_datetime(frame.model_available_date).lt(frame.date).all()
    assert not {'future_return', TARGET, 'long_tp_before_sl', 'short_tp_before_sl'} & set(frame)


def test_no_future_first_fold_before_any_write(model, monkeypatch):
    parent, _, _ = model
    monkeypatch.setattr(module, 'write_path_predictions', lambda *a: pytest.fail('must not write'))
    monkeypatch.setattr(module, 'build_inference_features', lambda *a: pytest.fail('preflight first'))
    with pytest.raises(ValueError, match='Aucun fold causal'):
        module.predict_oracle_path_history(object(), 'batch', '2023-11-01', '2023-11-02', artifacts_dir=parent)


def test_equal_validation_date_and_latest_eligible_fold(model):
    parent, _, _ = model
    _, _, _, folds = module.load_contract(parent, 'batch')
    assert module.select_fold('2024-06-28', folds) == '2023-12-01'
    assert module.select_fold('2024-07-01', folds) == '2024-07-01'
    folds['2024-07-01']['metrics']['val_available_max'] = '2024-07-01'
    assert module.select_fold('2024-07-01', folds) == '2023-12-01'


@pytest.mark.parametrize('change', ['weights', 'profile', 'unfinished', 'not_ready', 'fingerprint'])
def test_invalid_artifacts_are_never_served(model, change):
    parent, root, _ = model
    if change == 'weights':
        (root/'folds/2023-12-01/path_model.txt').write_text('corrupt')
    else:
        name = 'feature_profile.json' if change == 'profile' else ('protocol.json' if change == 'fingerprint' else 'report.json')
        p = root/name
        data = json.loads(p.read_text())
        if change == 'profile': data['generator_options'] = {}
        if change == 'unfinished': data['status'] = 'running'
        if change == 'not_ready': data['serving_ready'] = False
        if change == 'fingerprint': data['universe'] = ['OTHER']
        p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        module.load_contract(parent, 'batch')


def test_unknown_symbols_or_other_market_fail_before_write(model, monkeypatch):
    parent, _, _ = model
    monkeypatch.setattr(module, 'write_path_predictions', lambda *a: pytest.fail('write'))
    with pytest.raises(ValueError, match='hors contrat'):
        module.predict_oracle_path_history(object(), 'batch', '2024-01-02', '2024-01-03',
            artifacts_dir=parent, symbols=['UNKNOWN'])
    with pytest.raises(ValueError, match='alpha_trade'):
        module.predict_oracle_path_history(SimpleNamespace(url=SimpleNamespace(database='alpha_trade_fr')),
            'batch', '2024-01-02', '2024-01-03', artifacts_dir=parent)


class Engine:
    def __init__(self): self.calls = []
    @contextmanager
    def begin(self): yield self
    connect = begin
    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        return SimpleNamespace(scalar=lambda: 'US_EQ')


def test_score_and_lineage_in_same_transaction_terminal_labels_null():
    engine = Engine()
    frame = pd.DataFrame([dict(date='2024-01-02', symbol='A', proba_extreme=.8, fold_start='2023-12-01',
        model_available_date='2023-11-30', model_sha256='a'*64, feature_profile_sha256='b'*64)])
    assert module.write_path_predictions(engine, frame, 'batch') == 1
    inserts = [(s, p) for s, p in engine.calls if 'INSERT' in s]
    assert len(inserts) == 2
    rows = inserts[0][1]
    assert rows[0]['future_return'] is None and rows[0]['oracle_extreme10'] is None
    assert inserts[1][1][0]['target_name'] == TARGET
    assert inserts[1][1][0]['target_horizon'] == 20


@pytest.mark.parametrize('bad', ['missing', 'future', 'model_hash', 'profile_hash', 'terminal_label'])
def test_path_loader_requires_qualified_lineage(model, monkeypatch, bad):
    from modelFactory.oracle import predictions_store
    parent, root, _ = model
    main = pd.DataFrame([dict(date='2024-01-02', symbol='S00', proba_extreme=.8,
        future_return=None, oracle_extreme10=None, fold_start='2023-12-01')])
    evidence = pd.DataFrame([dict(date='2024-01-02', symbol='S00', fold_start='2023-12-01',
        model_available_date='2023-11-30', target_name=TARGET, target_horizon=20,
        model_sha256=digest(root/'folds/2023-12-01/path_model.txt'),
        feature_profile_sha256=digest(root/'feature_profile.json'))])
    if bad == 'missing': evidence = evidence.iloc[:0]
    if bad == 'future': evidence['model_available_date'] = '2024-01-02'
    if bad == 'model_hash': evidence['model_sha256'] = 'c'*64
    if bad == 'profile_hash': evidence['feature_profile_sha256'] = 'c'*64
    if bad == 'terminal_label': main['oracle_extreme10'] = 1
    def read_sql(query, engine, params):
        assert params['batch_id'] == 'batch'
        return evidence.copy() if 'oracle_path_prediction_lineage' in str(query) else main.copy()
    monkeypatch.setattr(predictions_store.pd, 'read_sql', read_sql)
    with pytest.raises(ValueError, match='Lineage'):
        predictions_store.load_oracle_predictions(object(), batch_id='batch', artifacts_dir=parent)


@pytest.mark.parametrize('policy', ['long_only', 'abstain'])
def test_path_policy_not_a_directional_model_probability(model, monkeypatch, policy):
    from modelFactory import synthesize_oracle_predictions as synth
    from modelFactory.oracle import predictions_store
    parent, _, universe = model
    engine = Engine()
    monkeypatch.setattr(synth, 'get_sqlalchemy_engine', lambda: engine)
    monkeypatch.setattr(synth, 'ensure_synthetic_run', lambda *a, **kw: None)
    raw = pd.DataFrame([dict(date='2024-01-02', symbol=s, proba_extreme=(i+1)/100)
        for i, s in enumerate(universe)])
    monkeypatch.setattr(synth.pd, 'read_sql', lambda *a, **kw: raw.rename(columns={'date':'prediction_date'}))
    monkeypatch.setattr(predictions_store, 'load_oracle_predictions', lambda *a, **kw: raw.copy())
    monkeypatch.setattr('common.config_loader.load_config', lambda: {'oracle_path': {'direction_policy': policy}})
    result = synth.synthesize('batch', artifacts_dir=parent)
    rows = next(p for s, p in engine.calls if 'INSERT INTO alpha_trade.model_predictions' in s)
    assert all(r['source'] == 'oracle_path_policy' and r['calibration_method'] == 'rank_policy' for r in rows)
    assert not any(r['predicted_side'] == 'short' for r in rows)
    assert (result['long_count'] > 0) == (policy == 'long_only')
    if policy == 'long_only':
        assert result['long_count'] == len(universe)  # exact TOP filtering is owned by the Oracle/tradable gate
    if policy == 'long_only':
        best = next(r for r in rows if r['symbol'] == 'S19')
        assert best['proba_long'] == 1 and best['proba_long'] != .2  # rank, not amplitude probability


def test_pipeline_threads_path_batch_from_predict_to_risk(model):
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    from modelFactory.oracle.artifact_contract import resolve_oracle_artifact_horizon
    from common.ml_cascade_contract import infer_oracle_only_cascade_mode
    parent, _, _ = model
    opts = PipelineLaunchOptions(ml_live_predict_batch_id='batch', ml_artifacts_dir=str(parent))
    command = build_pipeline_command('ml_predict', opts)
    assert command[command.index('--batch-id')+1] == 'batch'
    risk = build_pipeline_command('risk_management', opts)
    assert risk[risk.index('--oracle-batch-id')+1] == 'batch'
    assert risk[risk.index('--oracle-tradable-policy')+1] == 'filter_then_top20'
    assert resolve_oracle_artifact_horizon('batch', parent) == 20
    assert infer_oracle_only_cascade_mode(parent, 'batch', oracle_rows=20, global_rank_rows=0) == 'extreme_gate'


def test_valid_score_loader_and_tradable_subset_risk_use_same_scores(model, monkeypatch):
    from modelFactory.oracle import predictions_store
    from risk_management.db_io import RiskRepository
    parent, root, _ = model
    main = pd.DataFrame([dict(date='2024-01-02', symbol='S00', proba_extreme=.8,
        future_return=None, oracle_extreme10=None, fold_start='2023-12-01')])
    evidence = pd.DataFrame([dict(date='2024-01-02', symbol='S00', fold_start='2023-12-01',
        model_available_date='2023-11-30', target_name=TARGET, target_horizon=20,
        model_sha256=digest(root/'folds/2023-12-01/path_model.txt'),
        feature_profile_sha256=digest(root/'feature_profile.json'))])
    monkeypatch.setattr(predictions_store.pd, 'read_sql', lambda q, *a, **kw:
        evidence.copy() if 'oracle_path_prediction_lineage' in str(q) else main.copy())
    frame = predictions_store.load_oracle_predictions(object(), batch_id='batch', artifacts_dir=parent)
    assert frame.proba_extreme.tolist() == [.8]
    repo = RiskRepository.__new__(RiskRepository)
    repo.engine = object()
    day = pd.Timestamp('2024-01-02').date()
    assert repo.load_oracle_scores_asof(day, batch_id='batch', symbols=['S00'], artifacts_dir=parent) == {'S00': .8}
    assert repo.load_oracle_scores_asof(day, batch_id='batch', symbols=['S99'], artifacts_dir=parent) == {}


def test_backtest_policy_preserves_oracle_order_without_directional_confirmation(monkeypatch):
    from modelFactory.predictor import apply_cascade_to_predictions
    monkeypatch.setattr('modelFactory.predictor.load_cascade_config', lambda: dict(
        top_pct=.2, min_prob_classification=.55, min_prob_regression=.1))
    symbols = [f'S{i:02}' for i in range(20)]
    scores = {s: (i+1)/100 for i, s in enumerate(symbols)}
    frame = pd.DataFrame([dict(trade_date=pd.Timestamp('2024-01-02'), symbol=s,
        predicted_proba=(i+1)/20, predicted_side='long', proba_long=(i+1)/20,
        proba_flat=0., proba_short=0., source='oracle_path_policy', run_id='path-policy')
        for i, s in enumerate(symbols)])
    result = apply_cascade_to_predictions(frame, 'batch', rank_mode='extreme_gate',
        oracle_rank_map={'2024-01-02': scores}, extreme_gate_pct=.2,
        extreme_gate_per_symbol='bypass', oracle_atr_enabled=False)
    longs = result.loc[result.predicted_side.eq('long')].sort_values('cascade_score', ascending=False)
    assert longs.symbol.tolist() == ['S19', 'S18', 'S17', 'S16', 'S15']
    assert longs.proba_long.tolist() == pytest.approx([1., .95, .9, .85, .8])
    assert not result.predicted_side.eq('short').any()
