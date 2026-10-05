"""Positive temperature contract and legacy serving compatibility."""
import pickle

import numpy as np
import pytest
import torch

from modelFactory.calibration import TemperatureScaler, VectorScaler
from modelFactory.predictor import _load_optional_calibrator
from modelFactory.runtime_status import reset_runtime_status, snapshot_runtime_status


@pytest.mark.parametrize('kind',[TemperatureScaler,VectorScaler])
@pytest.mark.parametrize('temperature',[-1,0,float('nan'),float('inf'),float('-inf')])
def test_invalid_legacy_temperature_rejected(kind,temperature):
    with pytest.raises(ValueError,match='strictly positive'):
        kind.from_state_dict({'temperature':temperature,'fitted':True})


@pytest.mark.parametrize('kind',[TemperatureScaler,VectorScaler])
@pytest.mark.parametrize('temperature',[1e-9,.1,1,5,1e6])
def test_positive_legacy_state_roundtrip_exact_formula(kind,temperature):
    cal=kind.from_state_dict({'temperature':temperature,'fitted':True})
    logits=np.array([[0.,1.,2.],[2.,1.,0.]])
    expected=torch.softmax(torch.tensor(logits)/temperature,dim=1).numpy()
    np.testing.assert_allclose(cal.predict(logits),expected,atol=1e-12)
    assert cal.state_dict()['temperature']==temperature


@pytest.mark.parametrize('kind',[TemperatureScaler,VectorScaler])
def test_fit_positive_and_formula_identical_at_serving(kind):
    logits=np.array([[2.,0.,0.],[0.,2.,0.],[0.,0.,2.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
    labels=np.array([0,1,2,0,1,2])
    cal=kind(max_iter=20).fit(logits,labels)
    assert cal.fitted and np.isfinite(cal.temperature) and cal.temperature>0
    scaled=torch.tensor(logits)/cal.temperature
    if isinstance(cal,VectorScaler):
        scaled+=torch.tensor(cal.biases-cal.biases.mean())
    np.testing.assert_allclose(cal.predict(logits),torch.softmax(scaled,dim=1).numpy(),atol=1e-12)


@pytest.mark.parametrize('biases',[[0,float('nan'),0],[[0,0,0]],[0],[0,float('inf'),0]])
def test_invalid_vector_biases_rejected_on_load(biases):
    with pytest.raises(ValueError,match='biases'):
        VectorScaler.from_state_dict({'temperature':1,'biases':biases,'fitted':True})


def test_bias_dimension_mismatch_rejected_at_prediction():
    cal=VectorScaler(biases=np.zeros(2),fitted=True)
    with pytest.raises(ValueError,match='class count'):
        cal.predict(np.zeros((1,3)))


@pytest.mark.parametrize('kind',[TemperatureScaler,VectorScaler])
def test_mutated_invalid_state_rejected_at_runtime(kind):
    cal=kind(fitted=True)
    cal.temperature=-1
    with pytest.raises(ValueError,match='strictly positive'):
        cal.predict(np.zeros((1,3)))


@pytest.mark.parametrize('kind',[TemperatureScaler,VectorScaler])
def test_nonfinite_fit_inputs_rejected_without_fitted_state(kind):
    cal=kind()
    with pytest.raises(ValueError,match='finite'):
        cal.fit(np.array([[0,1,2],[float('nan'),0,1]]),np.array([0,1]))
    assert not cal.fitted


def test_invalid_calibrator_load_uses_existing_logged_fallback(tmp_path,caplog):
    reset_runtime_status()
    path=tmp_path/'calibrator.pkl'
    path.write_bytes(pickle.dumps({'method':'vector','temperature':-1,'biases':[0,0,0],'fitted':True}))
    result=_load_optional_calibrator(path,symbol='PENN',selected_model='catboost')
    assert result is None
    assert snapshot_runtime_status()['prediction_calibration_fallback_count']==1
    assert 'calibrator_fallback' in caplog.text
