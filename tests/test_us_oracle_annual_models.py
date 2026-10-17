from copy import deepcopy

import pytest

from scripts.research.us_oracle_annual_models import causal_fold, validate_contract


def fold(start, available):
    head = dict(status='TRAINED', train_available_max='2023-06-01', val_available_max=available)
    return dict(metrics=dict(fold_start=start, test_end='2024-06-01', heads=dict(long=head, short=deepcopy(head))))


def test_both_fit_and_validation_must_predate_decision():
    folds = {'old': fold('2023-07-01', '2023-06-30'), 'new': fold('2024-01-08', '2024-01-05')}
    assert causal_fold('2024-01-02', folds) == 'old'
    assert causal_fold('2024-01-08', folds) == 'new'
    folds['new']['metrics']['heads']['short']['train_available_max'] = '2024-01-08'
    assert causal_fold('2024-01-08', folds) == 'old'


def test_equal_availability_and_missing_heads_rejected():
    folds = {'new': fold('2024-01-02', '2024-01-02')}
    with pytest.raises(ValueError, match='No causal'):
        causal_fold('2024-01-02', folds)
    del folds['new']['metrics']['heads']['short']
    with pytest.raises(ValueError, match='No causal'):
        causal_fold('2024-01-03', folds)


def test_oof_end_is_not_a_training_availability_date():
    assert causal_fold('2025-01-01', {'old': fold('2023-12-05', '2023-12-04')}) == 'old'


def test_nan_or_untrained_availability_rejected():
    f = fold('2023-12-05', None)
    with pytest.raises(ValueError):
        causal_fold('2024-01-02', {'bad': f})
    f = fold('2023-12-05', '2023-12-04')
    f['metrics']['heads']['short']['status'] = 'FAILED'
    with pytest.raises(ValueError):
        causal_fold('2024-01-02', {'bad': f})


def test_contract_barriers_and_matrix_are_frozen():
    reference = dict(universe=['A'], columns=['f'], options={'x': 1})
    profile = dict(feature_columns=['f'], generator_options={'x': 1})
    protocol = dict(mode='oracle_tp_before_sl', universe=['A'],
        barriers=dict(take_profit_pct=.2, stop_loss_pct=.1, max_sessions=20))
    validate_contract(protocol, profile, dict(status='completed'), reference)
    protocol['barriers']['stop_loss_pct'] = .07
    with pytest.raises(ValueError, match='TP20/SL10'):
        validate_contract(protocol, profile, dict(status='completed'), reference)
    protocol['barriers']['stop_loss_pct'] = .1
    profile['feature_columns'] = ['g']
    with pytest.raises(ValueError, match='feature contract'):
        validate_contract(protocol, profile, dict(status='completed'), reference)


def test_audit_rejects_partial_campaign(tmp_path):
    from scripts.research.us_concentrated_historical_tapes import atomic_json
    from scripts.research.us_oracle_annual_result_audit import audit
    atomic_json(tmp_path/'report.json', dict(status='PARTIAL_FAILED', completed=8, failed=1))
    atomic_json(tmp_path/'manifest.json', {})
    with pytest.raises(ValueError, match='Nine completed'):
        audit(tmp_path)
