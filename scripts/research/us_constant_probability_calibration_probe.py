"""Synthetic calibration checks, no real-model training or database access."""
import json
from pathlib import Path

import numpy as np
import torch
from modelFactory.calibration import VectorScaler, probabilities_to_pseudo_logits
from modelFactory.predictor import _apply_optional_multiclass_calibration

ROOT=Path('artifacts/research/us_common_degradation/constant-probability-20261005-v1')


def run():
    torch.set_num_threads(1)
    raw=np.array([[.05,.15,.8],[.7,.2,.1],[.2,.5,.3]])
    logits=probabilities_to_pseudo_logits(raw)
    ordinary=VectorScaler(temperature=2,biases=np.array([.1,-.2,.1]),fitted=True)
    expected=ordinary.predict(logits)
    served,method=_apply_optional_multiclass_calibration(symbol='SYNTHETIC',selected_model='catboost',
        calibrator=ordinary,raw_probabilities=raw,calibrator_path=None)
    flattened=VectorScaler(temperature=1e6,biases=np.log([.4,.268976,.331024]),fitted=True).predict(logits)
    invalid_rejected=False
    try:
        invalid=VectorScaler.from_state_dict(dict(temperature=-1,biases=[0,0,0],fitted=True))
    except ValueError:
        invalid_rejected=True
        invalid=None
    x=np.array([[0.,0.,2.]])
    fit_formula=torch.softmax(torch.tensor(x,dtype=torch.float32)/-1,dim=1).numpy()
    prediction=None if invalid is None else invalid.predict(x)
    random=np.random.default_rng(317)
    trials=[]
    for seed in range(3):
        x=random.normal(size=(96,3)); y=random.integers(0,3,96)
        cal=VectorScaler(max_iter=100).fit(x,y)
        trials.append(dict(trial=seed,temperature=cal.temperature,
            long_range=float(np.ptp(cal.predict(x)[:,2]))))
    report=dict(ordinary_train_serve_max_difference=float(np.max(abs(expected-served))),method=method,
        synthetic_raw_long_range=float(np.ptp(raw[:,2])),synthetic_flattened_long_range=float(np.ptp(flattened[:,2])),
        flattened_probabilities=flattened.tolist(),
        invalid_negative_temperature_accepted=not invalid_rejected,
        invalid_fit_formula=fit_formula.tolist(),invalid_predict_formula=None if prediction is None else prediction.tolist(),
        synthetic_random_signal_calibration=trials,
        notes=['Synthetic examples not parameters recovered from PENN/ROKU/GH',
            'Large temperature can legitimately discard non-predictive model variation',
            'Negative-temperature train/serve mismatch is a separate implementation defect, not proven cause of old scores'])
    # Preserve the pre-fix diagnostic evidence.
    (ROOT/'calibration_probe_after_fix.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    run()
