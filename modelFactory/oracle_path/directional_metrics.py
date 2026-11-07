"""Classification diagnostics; calibration is never called an independent test."""
import numpy as np
import pandas as pd

from .directional import INPUTS, split
from .named_prediction import predict_proba as named_predict_proba


def classification_metrics(labels, probabilities):
    from sklearn.metrics import roc_auc_score, balanced_accuracy_score
    y=np.asarray(labels,dtype=float);p=np.asarray(probabilities,dtype=float)
    if (y.shape!=p.shape or y.ndim!=1 or not np.isfinite(y).all() or not np.isfinite(p).all()
            or not np.isin(y,[0,1]).all() or not ((p>=0)&(p<=1)).all()):
        raise ValueError('Invalid directional diagnostic labels/probabilities')
    n=len(y)
    if not n:
        return dict(n=0,positives=0,auc=None,accuracy=None,balanced_accuracy=None,brier=None,
            positive_rate=None,selected_at_05=0,precision_at_05=None)
    selected=p>=.5;two=len(np.unique(y))==2
    return dict(n=n,positives=int(y.sum()),auc=float(roc_auc_score(y,p)) if two else None,
        accuracy=float(np.mean(selected==y)),balanced_accuracy=float(balanced_accuracy_score(y,selected)) if two else None,
        brier=float(np.mean((p-y)**2)),positive_rate=float(y.mean()),
        selected_at_05=int(selected.sum()),precision_at_05=float(y[selected].mean()) if selected.any() else None)


def predict(weights,frame):
    x=frame[INPUTS].replace([np.inf,-np.inf],np.nan).clip(weights['lo'],weights['hi'],axis=1)
    raw=np.clip(named_predict_proba(weights['model'],x,INPUTS)[:,1],1e-6,1-1e-6)
    return weights['calibrator'].predict_proba(np.log(raw/(1-raw)).reshape(-1,1))[:,1]


def model_metrics(panel,weights,record,calendar,end):
    """Evaluate only this model's held-out calendar year with mature outcomes.

    Train and calibration rows are separately marked non-independent. The fixed
    global phase modulo H+1 reports a second, non-overlapping OOS diagnostic.
    """
    side=record['side'];year=int(record['year'])
    fit,cal=split(panel,year,side)
    if (len(fit)!=record['fit_rows'] or len(cal)!=record['calibration_rows']
            or str(fit.date.min().date())!=record['fit_start'] or str(fit.date.max().date())!=record['fit_end']
            or str(cal.date.min().date())!=record['calibration_start'] or str(cal.date.max().date())!=record['calibration_end']):
        raise ValueError('Reconstructed panel differs from frozen training/calibration membership')
    cutoff=pd.Timestamp(end)
    test=panel[panel.date.dt.year.eq(year)&panel[side].notna()&panel.available.le(cutoff)].copy()
    if not test.empty and (test.date.le(pd.Timestamp(record['available'])).any()
            or test.date.le(pd.Timestamp(record['fit_available_max'])).any()):
        raise ValueError('Noncausal held-out directional evaluation')
    metrics={};test_predictions=None
    for name,frame in [('train',fit),('calibration',cal),('oos',test)]:
        p=predict(weights,frame) if len(frame) else np.array([])
        metrics[name]=dict(**classification_metrics(frame[side].to_numpy(),p),
            first_date=str(frame.date.min().date()) if len(frame) else None,
            last_date=str(frame.date.max().date()) if len(frame) else None,
            independent_test=name=='oos')
        if name=='oos':
            test_predictions=frame[['date','available']].copy()
            test_predictions['label']=frame[side].to_numpy();test_predictions['probability']=p
            test_predictions['symbol']=record['symbol'];test_predictions['side']=side
            test_predictions['model_year']=year;test_predictions['model_sha256']=record['sha256']
            # The label observes the path to open11; fixed phase avoids overlapping paths.
            positions=pd.DatetimeIndex(calendar).get_indexer(frame.date)
            if (positions<0).any():raise ValueError('Test dates outside frozen calendar')
            independent=positions%11==0
            metrics['oos_nonoverlap']=classification_metrics(frame[side].to_numpy()[independent],p[independent])
            test_predictions['nonoverlap']=independent
    return metrics,test_predictions
