"""Preparation cannot sneak future labels into candidate ranking or fit dates."""
import json

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_path_profit_filter_protocol as study


def scores():
    return pd.DataFrame(dict(date=pd.Timestamp('2021-01-04'),
        symbol=[f'S{i:02}' for i in range(25)], score=np.linspace(.99, .1, 25),
        fold_start=pd.Timestamp('2020-07-07'), future_return=np.arange(25)*100.,
        future_path_quality=False, selected=False))


def test_rank_before_future_validity_and_no_replacement():
    result = study.freeze_top20(scores())
    assert len(result) == 20 and result.symbol.tolist() == [f'S{i:02}' for i in range(20)]
    assert set(result) == {*study.SAFE_SCORE_COLUMNS, 'oracle_rank'}
    assert result.oracle_rank.tolist() == list(range(1, 21))


def test_tie_order_is_symbol_not_future_profit():
    source = scores().assign(score=.8).iloc[::-1]
    assert study.freeze_top20(source).symbol.tolist() == [f'S{i:02}' for i in range(20)]


@pytest.mark.parametrize('fault', ['duplicate', 'nonfinite', 'small', 'missing'])
def test_invalid_score_population_fails(fault):
    data = scores()
    if fault == 'duplicate': data = pd.concat([data, data.iloc[:1]])
    if fault == 'nonfinite': data.loc[0, 'score'] = np.inf
    if fault == 'small': data = data.iloc[:19]
    if fault == 'missing': data.loc[0, 'symbol'] = None
    with pytest.raises(ValueError): study.freeze_top20(data)


def test_fold_causality_checks_validation_labels_not_just_train():
    metrics = dict(test_start='2022-01-03', test_end='2022-07-01',
        train_available_max='2021-06-01', val_available_max='2021-12-31')
    study.causal_fold(metrics)
    with pytest.raises(ValueError):
        study.causal_fold(dict(metrics, val_available_max='2022-01-03'))


@pytest.mark.parametrize('day,available,expected', [
    ('2021-11-01', '2021-12-01', 'FIT'),
    ('2021-12-30', '2022-02-01', 'PURGED_FIT'),
    ('2022-12-01', '2023-01-01', 'PURGED_VALIDATION'),
    ('2023-01-03', '2023-02-06', 'CONTROL'),
    ('2025-01-03', '2025-02-06', 'OUTSIDE_FIT_VALIDATION_CONTROL'),
    ('2026-09-30', None, 'UNKNOWN_LABEL')])
def test_split_uses_availability(day, available, expected):
    assert study.split_for_label(day, available, study.read(study.SPEC)) == expected


def test_protocol_no_training_and_not_a_new_direction_claim():
    spec = study.read(study.SPEC)
    assert spec['target']['take_profit_pct'] == spec['target']['stop_loss_pct'] == .1
    assert spec['target']['expiry_can_be_positive'] and spec['target']['monitor_entry_session']
    assert spec['target']['require_label_native_parity_before_fit']
    assert spec['learner']['threshold'] == .5 and len(spec['features']) == 24
    assert spec['safety']['new_GO_required_before_label_engine_and_training']
    assert not spec['splits']['external_is_virgin_holdout']
    assert study.duplicate_audit()['genuinely_new_signal_family'] is False
    assert json.dumps(spec, allow_nan=False)


def test_hash_verification_does_not_accept_content_or_line_ending_changes(tmp_path):
    path = tmp_path/'fixture.py'
    path.write_bytes(b'a = 1\n')
    expected = study.digest(path)
    path.write_bytes(b'a = 1\r\n')
    with pytest.raises(ValueError): study.require_hash(path, expected)
