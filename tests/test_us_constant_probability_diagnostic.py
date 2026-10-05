import numpy as np
import torch
import pytest

from modelFactory.calibration import VectorScaler, probabilities_to_pseudo_logits
from modelFactory.predictor import _apply_optional_multiclass_calibration


def test_tabular_serving_uses_same_pseudo_logits_as_calibration():
    raw=np.array([[.05,.15,.8],[.7,.2,.1]])
    cal=VectorScaler(temperature=2,biases=np.array([.1,-.2,.1]),fitted=True)
    expected=cal.predict(probabilities_to_pseudo_logits(raw))
    actual,method=_apply_optional_multiclass_calibration(symbol='SYNTHETIC',selected_model='catboost',
        calibrator=cal,raw_probabilities=raw,calibrator_path=None)
    assert method=='vector'
    assert np.allclose(expected,actual)


def test_large_temperature_explains_flattening_without_constant_inputs():
    raw=np.array([[.05,.15,.8],[.7,.2,.1],[.2,.5,.3]])
    cal=VectorScaler(temperature=1e6,biases=np.log([.4,.268976,.331024]),fitted=True)
    calibrated=cal.predict(probabilities_to_pseudo_logits(raw))
    assert np.ptp(raw[:,2])>.5
    assert np.ptp(calibrated[:,2])<2e-6


def test_negative_temperature_state_rejected_after_fix():
    with pytest.raises(ValueError,match='strictly positive'):
        VectorScaler.from_state_dict(dict(temperature=-1,biases=[0,0,0],fitted=True))
