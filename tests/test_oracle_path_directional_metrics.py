import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle_path.directional import INPUTS,split
from modelFactory.oracle_path.directional_metrics import classification_metrics,model_metrics


def test_known_auc_accuracy_and_brier():
    metrics=classification_metrics([0,1,0,1],[.1,.9,.2,.8])
    assert metrics['auc']==metrics['accuracy']==metrics['balanced_accuracy']==1
    assert metrics['brier']==pytest.approx(.025)
    assert metrics['selected_at_05']==2 and metrics['precision_at_05']==1


def test_one_class_and_no_data_never_invent_auc():
    assert classification_metrics([1,1],[.6,.7])['auc'] is None
    assert classification_metrics([],[])['accuracy'] is None
    assert classification_metrics([0,1],[.1,.2])['precision_at_05'] is None


@pytest.mark.parametrize('p',[[0,2],[0,np.nan],[-.1,.5]])
def test_invalid_probabilities_are_rejected(p):
    with pytest.raises(ValueError):classification_metrics([0,1],p)


class Model:
    def predict_proba(self,x):
        p=x.iloc[:,0].to_numpy();return np.c_[1-p,p]


class Calibrator:
    def predict_proba(self,x):
        p=1/(1+np.exp(-x[:,0]));return np.c_[1-p,p]


def fixture():
    calendar=pd.bdate_range('2020-01-02','2024-12-31')
    a=pd.DataFrame(dict(date=calendar,available=calendar+pd.offsets.BDay(11)))
    a['long']=np.arange(len(a))%2
    for name in INPUTS:a[name]=np.where(a.long.eq(1),.8,.2)
    fit,cal=split(a,2024,'long')
    r=dict(symbol='A',year=2024,side='long',sha256='hash',fit_rows=len(fit),calibration_rows=len(cal),
        fit_start=str(fit.date.min().date()),fit_end=str(fit.date.max().date()),
        fit_available_max=str(fit.available.max().date()),calibration_start=str(cal.date.min().date()),
        calibration_end=str(cal.date.max().date()),available=str(cal.available.max().date()))
    w=dict(model=Model(),calibrator=Calibrator(),lo=pd.Series(0,index=INPUTS),hi=pd.Series(1,index=INPUTS))
    return a,r,w,calendar


def test_calibration_is_separate_and_test_is_mature_and_nonoverlap():
    a,r,w,calendar=fixture()
    result,pred=model_metrics(a,w,r,calendar,pd.Timestamp('2024-12-31'))
    assert not result['calibration']['independent_test'] and result['oos']['independent_test']
    assert pred.date.dt.year.eq(2024).all() and pred.available.le('2024-12-31').all()
    assert result['oos_nonoverlap']['n']==int(pred.nonoverlap.sum())<result['oos']['n']
    b=a.copy();b.loc[b.date.dt.year.eq(2024),'long']=1-b.loc[b.date.dt.year.eq(2024),'long']
    changed,_=model_metrics(b,w,r,calendar,pd.Timestamp('2024-12-31'))
    assert changed['train']==result['train'] and changed['calibration']==result['calibration']
    assert changed['oos']['auc']==0 and result['oos']['auc']==1


def test_frozen_training_membership_and_causality_are_checked():
    a,r,w,calendar=fixture()
    with pytest.raises(ValueError,match='membership'):
        model_metrics(a.iloc[1:],w,r,calendar,pd.Timestamp('2024-12-31'))
    with pytest.raises(ValueError,match='Noncausal'):
        model_metrics(a,w,{**r,'available':'2024-03-01'},calendar,pd.Timestamp('2024-12-31'))
