import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle import dataset
from scripts.research.us_oracle_numeric_external import (
    compare_external_features, legacy_compute, paired_builders,
)


def test_private_legacy_imports_do_not_patch_production(monkeypatch):
    from modelFactory import factor_features
    original = factor_features.compute_factor_features
    sources = {
        'features': b'from modelFactory.factor_features import compute_factor_features\n'
                    b'def compute_features(x):\n return compute_factor_features(x)\n',
        'factor_features': b'def compute_factor_features(x):\n return x + 123\n',
    }
    monkeypatch.setattr('subprocess.check_output',
        lambda argv: sources['factor_features' if 'factor_features.py' in argv[-1] else 'features'])
    private, hashes = legacy_compute('immutable-commit')
    assert private(1) == 124
    assert set(hashes) == {'features', 'factor_features'}
    assert factor_features.compute_factor_features is original


def test_builders_share_raw_inputs_without_mutating_production(monkeypatch):
    from modelFactory import data_loader
    original_compute = dataset.compute_features
    original_loader = dataset.load_universe_bars
    calls = []
    def empty(*args, **kwargs):
        calls.append(1)
        return pd.DataFrame()
    monkeypatch.setattr(data_loader, 'load_universe_bars', empty)
    builders, cache = paired_builders(lambda x: x)
    for builder in builders.values():
        assert builder(None, ['A'], start_date='2025-01-01', end_date='2025-01-02').empty
    assert len(calls) == 1
    assert cache
    assert dataset.compute_features is original_compute
    assert dataset.load_universe_bars is original_loader


def test_only_treatment_columns_can_change():
    old = pd.DataFrame(dict(date=pd.to_datetime(['2025-01-02']), symbol=['A'],
                            momentum_20=[.1], beta_252=[1.]))
    new = old.copy()
    new['beta_252'] = 2.
    compare_external_features(old, new)
    new['momentum_20'] = .2
    with pytest.raises(ValueError, match='untreated'):
        compare_external_features(old, new)


def test_changed_dates_or_column_contract_rejected():
    old = pd.DataFrame(dict(date=pd.to_datetime(['2025-01-02']), symbol=['A'], beta_252=[1.]))
    new = old.copy()
    new['date'] += pd.Timedelta(days=1)
    with pytest.raises(ValueError, match='keys'):
        compare_external_features(old, new)
