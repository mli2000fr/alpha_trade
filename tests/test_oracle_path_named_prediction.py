"""Preserve numeric predictions and validate schema for both artifact vintages."""
import warnings

import numpy as np
import pandas as pd
import pytest
from lightgbm import LGBMClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

from modelFactory.oracle_path.named_prediction import predict_proba


def fixture(*, named=False, empty_feature=False):
    rng = np.random.default_rng(42)
    frame = pd.DataFrame(rng.normal(size=(200, 3)), columns=['momentum', 'volatility', 'sentiment'])
    labels = (frame.momentum + .4 * frame.volatility > 0).astype(int)
    if empty_feature:
        frame['sentiment'] = np.nan
    frame.loc[::9, 'volatility'] = np.nan
    imputer = SimpleImputer(strategy='median')
    if named:
        imputer.set_output(transform='pandas')
    model = make_pipeline(imputer, LGBMClassifier(n_estimators=8, max_depth=3,
        min_child_samples=5, n_jobs=1, verbosity=-1, random_state=42))
    model.fit(frame, labels)
    return model, frame


@pytest.mark.parametrize('named', [False, True])
def test_legacy_and_named_pipelines_keep_exact_probabilities_without_warning(named):
    model, frame = fixture(named=named)
    with warnings.catch_warnings(record=True) as original_warnings:
        warnings.simplefilter('always')
        baseline = model.predict_proba(frame)
    if not named:
        assert any('does not have valid feature names' in str(w.message) for w in original_warnings)
    with warnings.catch_warnings():
        warnings.filterwarnings('error', message='.*does not have valid feature names.*')
        actual = predict_proba(model, frame, list(frame.columns))
    np.testing.assert_array_equal(actual, baseline)


def test_imputer_dropped_empty_column_keeps_the_original_mapping():
    model, frame = fixture(empty_feature=True)
    with warnings.catch_warnings(record=True):
        baseline = model.predict_proba(frame)
    with warnings.catch_warnings(record=True) as found:
        actual = predict_proba(model, frame, list(frame.columns))
    assert not any('does not have valid feature names' in str(w.message) for w in found)
    np.testing.assert_array_equal(actual, baseline)


@pytest.mark.parametrize('kind', ['reversed', 'missing', 'extra', 'duplicate', 'array'])
def test_invalid_input_contract_fails_before_prediction(kind):
    model, frame = fixture()
    names = list(frame.columns)
    altered = {'reversed': frame[names[::-1]], 'missing': frame.drop(columns=names[0]),
               'extra': frame.assign(unknown=0), 'duplicate': frame.set_axis(['momentum']*3, axis=1),
               'array': frame.to_numpy()}[kind]
    with pytest.raises(ValueError, match='noms ou ordre'):
        predict_proba(model, altered, names)


def test_fitted_input_order_must_match_contract():
    model, frame = fixture()
    reversed_frame = frame.iloc[:, ::-1]
    with pytest.raises(ValueError, match='variables du modèle'):
        predict_proba(model, reversed_frame, list(reversed_frame.columns))


def test_estimator_schema_cannot_be_arbitrarily_renamed(monkeypatch):
    model, frame = fixture()
    monkeypatch.setattr(LGBMClassifier, 'feature_name_', property(lambda self: ['wrong0', 'wrong1', 'wrong2']))
    with pytest.raises(ValueError, match='colonnes LightGBM'):
        predict_proba(model, frame, list(frame.columns))
