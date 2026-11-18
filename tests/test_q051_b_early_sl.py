import numpy as np
import pandas as pd
import pytest
from scripts.research import us_q051_b_early_sl_20261116 as e


def bars():
    dates=pd.bdate_range('2023-01-02',periods=20)
    return pd.DataFrame(dict(date=dates,symbol='A',open=100.,high=101.,low=99.,close=100.,volume=1000.,
        is_filled=0,instrument_id=1,data_source='alpaca_sip',data_adjustment='raw')),dates


def test_first_session_target_availability_and_future_independence():
    b,c=bars();b.loc[1,'low']=94.
    y=e.early_labels(b,c)
    assert y.iloc[0].first_session_sl==1 and y.iloc[0].event_available==c[2]
    assert y.iloc[1].first_session_sl==0
    b.loc[2:,'low']=1.
    pd.testing.assert_series_equal(y.iloc[0],e.early_labels(b,c).iloc[0])


def test_missing_or_changed_identity_is_unknown_not_non_stop():
    b,c=bars();b.loc[1,'open']=np.nan
    assert pd.isna(e.early_labels(b,c).iloc[0].first_session_sl)
    b,c=bars();b.loc[1,'instrument_id']=2
    assert pd.isna(e.early_labels(b,c).iloc[0].first_session_sl)
    b,c=bars();b.loc[1,'data_source']='eodhd_eod'
    assert pd.isna(e.early_labels(b,c).iloc[0].first_session_sl)


def test_path10_uses_consecutive_exchange_sessions_and_no_future():
    days=pd.bdate_range('2023-01-02',periods=20)
    f=pd.DataFrame(dict(date=days,symbol='A',**{c:np.arange(20,dtype=float) for c in e.PATH_SOURCES}))
    out=e.path_panel(f,days)
    assert out.iloc[9][e.PATH_COLUMNS[0]]==9 and out.iloc[9][e.PATH_COLUMNS[1]]==1
    changed=f.copy();changed.loc[10:,e.PATH_SOURCES]=1e6
    pd.testing.assert_frame_equal(out.iloc[:10],e.path_panel(changed,days).iloc[:10])
    hole=f.drop(index=3)
    assert pd.isna(e.path_panel(hole,days).iloc[8][e.PATH_COLUMNS[0]])


def test_temporal_split_purges_unavailable_labels():
    f=pd.DataFrame(dict(date=pd.to_datetime(['2022-12-20','2022-12-30','2023-01-03','2023-12-29','2024-01-02']),
        available=pd.to_datetime(['2022-12-22','2023-01-03','2023-01-05','2024-01-02','2024-01-04']),target=1.))
    fit,cal=e.temporal_split(f,2024,'target','available')
    assert fit.date.tolist()==[pd.Timestamp('2022-12-20')]
    assert cal.date.tolist()==[pd.Timestamp('2023-01-03')]


def test_meta_gate_is_after_selection_no_refill_and_keeps_unknown():
    day=pd.Timestamp('2024-01-02')
    selected=pd.DataFrame(dict(date=day,symbol=['A','B'],rank=[1,2],selected=True))
    risks=pd.DataFrame(dict(date=day,symbol=['A','B','C'],SLJ_risk=[.8,np.nan,.1],
        SLJ_threshold=[.7,np.nan,.7],SLJ_available=['2023-12-20',None,'2023-12-20']))
    result=e.meta_filter(selected,risks,'SLJ')
    assert result[result.selected].symbol.tolist()==['B']
    risks.loc[0,'SLJ_available']='2024-01-02'
    with pytest.raises(ValueError,match='Future'):e.meta_filter(selected,risks,'SLJ')


def test_fixed_feature_dimensions_and_no_outcome_columns():
    assert len(e.columns())==29 and len(e.columns(True))==44
    assert not set(e.columns(True))&{'first_session_sl','long','event_available','entry_open','entry_low'}


def test_real_meta_model_serialization_keeps_feature_order(tmp_path):
    import joblib
    from modelFactory.oracle_path.directional_metrics import predict
    rng=np.random.default_rng(72)
    f=pd.DataFrame(dict(x=rng.normal(size=1500),z=rng.normal(size=1500)))
    f['target']=(f.x+.3*f.z>1).astype(float)
    fit,cal=f.iloc[:1100],f.iloc[1100:]
    weights,metrics=e.fit_model(fit,cal,['x','z'],'target')
    assert weights is not None and metrics['n']==400
    path=tmp_path/'model.joblib';joblib.dump(weights,path)
    p=predict(weights,cal);again=predict(joblib.load(path),cal)
    np.testing.assert_allclose(p,again,atol=0,rtol=0)
    assert list(weights['model'][-1].feature_names_in_)==['x','z']
    threshold=float(np.quantile(p,.9))
    assert np.mean(p>threshold)<=.1
