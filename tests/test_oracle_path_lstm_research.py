"""Small real neural fits and strict causal sequence contracts, no SQL/accounts."""
from dataclasses import replace
from types import SimpleNamespace
import json

import numpy as np
import pandas as pd
import pytest
import torch

from modelFactory.oracle_path import TARGET
from modelFactory.oracle_path import lstm_research as neural
from scripts.research import oracle_path_lstm_comparison as runner


def metadata(n=12):
    dates = pd.bdate_range("2020-01-02", periods=n)
    return pd.DataFrame([dict(date=d, symbol=s, instrument_id=i+1, data_source="EODHD",
        data_adjustment="SPLIT_DIVIDEND", feature_present=True) for i,s in enumerate(("A","B")) for d in dates]), dates


def test_sequence_boundaries_missing_session_and_identity():
    meta, days = metadata()
    good, reason = neural.sequence_eligibility(meta, days, 3, {})
    assert not good[:2].any() and not good[12:14].any()
    assert good.sum() == 20
    broken = meta.drop(index=5).reset_index(drop=True)
    good, reason = neural.sequence_eligibility(broken, days, 3, {})
    assert reason[5] == "MISSING_SESSION_IN_SEQUENCE"
    meta.loc[4, "instrument_id"] = 999
    good, reason = neural.sequence_eligibility(meta, days, 3, {})
    assert not good[4:7].any()
    assert reason[6] == "UNKNOWN_OR_CHANGED_INSTRUMENT_ID"


def test_known_break_and_empty_feature_row_excluded():
    meta, days = metadata()
    event = SimpleNamespace(last_predecessor_date=days[4], first_successor_date=days[5])
    good, reason = neural.sequence_eligibility(meta, days, 3, {"A":(event,)})
    assert reason[5] == reason[6] == "KNOWN_IDENTITY_BREAK_IN_SEQUENCE"
    meta.loc[3,"feature_present"] = False
    good, reason = neural.sequence_eligibility(meta, days, 3, {})
    assert not good[3:6].any()
    with pytest.raises(ValueError, match="trier"):
        neural.sequence_eligibility(meta.iloc[::-1], days, 3, {})


def test_scaler_train_only_missing_mask_and_no_future_read():
    x = np.array([[1, np.nan], [2,np.nan], [3,np.nan], [1000,1000]], dtype=np.float32)
    scaler = neural.fit_scaler(x, np.arange(3))
    assert scaler["mean"] == [2.,0.]
    assert scaler["finite_train_counts"] == [3,0]
    spec = neural.SequenceSpec(length=3)
    batch = neural.sequence_batch(x, np.array([2]), scaler, spec)
    assert batch.shape == (1,3,4)
    assert (batch[0,:,1]==0).all() and (batch[0,:,3]==1).all()
    x[3] = [-9999,9999]
    assert np.array_equal(batch, neural.sequence_batch(x, np.array([2]), scaler, spec))
    assert neural.fit_scaler(x, np.arange(3)) == scaler


def test_real_fit_resume_and_scaler_corruption(tmp_path):
    torch.set_num_threads(1)
    spec = neural.SequenceSpec(length=3, hidden_size=4, batch_size=16, max_epochs=2,
        patience=2, threads=1, dropout=0., seed=7)
    x = np.random.default_rng(7).normal(size=(160,2)).astype(np.float32)
    y = (x[:,0]>0).astype(np.float32)
    train, val = np.arange(3,90), np.arange(100,130)
    events = []
    model, scaler, report = neural.fit(x,y,train,val,spec,tmp_path,"cpu",lambda *a:events.append(a))
    scores = neural.predict(model,x,val,scaler,spec,"cpu")
    assert np.isfinite(scores).all() and ((scores>=0)&(scores<=1)).all()
    assert report["epochs_completed"] == 2
    assert (tmp_path/"epoch_state_1.pt").is_file() and (tmp_path/"epoch_state_2.pt").is_file()
    assert report["best_epoch"] in (1,2) and any(e[0]=="epoch_completed" for e in events)
    again, scaling, repeated = neural.fit(x,y,train,val,spec,tmp_path,"cpu",lambda *a:pytest.fail("finished fit resumed"))
    assert scaling == scaler
    assert np.allclose(neural.predict(again,x,val,scaling,spec,"cpu"), scores)
    # Altering ONLY unseen test inputs does not affect the training normalization.
    changed = x.copy()
    changed[140:] = 10000
    assert neural.fit_scaler(changed,train) == scaler
    (tmp_path/"scaler.json").write_text("{}")
    with pytest.raises(ValueError, match="Scaler"):
        neural.fit(x,y,train,val,spec,tmp_path,"cpu",lambda *a:None)


def test_invalid_specs_and_targets(tmp_path):
    with pytest.raises(ValueError):
        neural.SequenceSpec(max_epochs=0)
    x=np.ones((30,1),dtype=np.float32)
    with pytest.raises(ValueError, match="binaires"):
        neural.fit(x,np.zeros(30),np.arange(3,10),np.arange(15,25),neural.SequenceSpec(length=3),tmp_path,"cpu",lambda *a:None)


def test_three_candidate_evaluation_preserves_missing_original_selection():
    dates = pd.bdate_range("2024-01-02",periods=60)
    symbols=[f"S{i:02}" for i in range(60)]
    scores=pd.DataFrame(dict(date=dates[0],symbol=symbols,score_lightgbm=np.arange(60),
        score_catboost=np.arange(60),score_lstm=np.arange(60)))
    labels=pd.DataFrame(dict(date=dates[0],symbol=symbols,path_amplitude=np.arange(60)/100,
        **{TARGET:(np.arange(60)>=48).astype(float)}))
    labels.loc[59,TARGET]=np.nan
    years,daily,strict,frame=runner.evaluate_three(scores,labels,dates,dates[-1])
    assert set(years["2024"]["strict_original_top"]) == {"lightgbm","catboost","lstm"}
    assert set(strict.backend) == {"lightgbm","catboost","lstm"}
    assert years["2024"]["strict_original_top"]["lstm"]["10"]["precision"] is None
    assert "score_lstm" in frame and "score_validation_champion" not in frame


def test_fold_purge_and_common_rows_are_exact():
    meta=pd.DataFrame(dict(date=pd.to_datetime(["2020-01-02","2020-01-03","2020-02-03","2020-02-04","2020-03-03"]),
        period="history",oracle_available_date=pd.to_datetime(["2020-01-31","2020-02-04","2020-02-28","2020-03-04","2020-04-02"]),
        sequence_eligible=[True,True,True,True,True], **{TARGET:[0.,1.,0.,1.,0.]}))
    fold=dict(train_dates=pd.to_datetime(["2020-01-02","2020-01-03"]),val_dates=pd.to_datetime(["2020-02-03","2020-02-04"]),
        test_dates=pd.to_datetime(["2020-03-03"]),val_start="2020-02-03",t_start="2020-03-03")
    (train,val,test),counts=runner.fold_indices(meta,fold,dict(n_train=1,n_val=1))
    assert train.tolist()==[0] and val.tolist()==[2] and test.tolist()==[4]
    with pytest.raises(ValueError,match="différents"):
        runner.fold_indices(meta,fold,dict(n_train=2,n_val=2))


def test_epoch_progress_handles_detail_epoch_without_duplicate_keyword():
    payload=runner.epoch_payload("2023-01-05",9,10,neural.SequenceSpec(),1,100,100,
        dict(epoch=1,validation_auc=.7,train_loss=.4,seconds=12.))
    assert payload["epoch"]==1 and payload["validation_auc"]==.7 and payload["completed"]==100


def test_cache_uses_previous_year_for_january_sequence(tmp_path, monkeypatch):
    root,confirmation,out=tmp_path/"history",tmp_path/"confirm",tmp_path/"output"
    for base in (root,confirmation):
        (base/"chunks"/"0000").mkdir(parents=True)
    dates=pd.bdate_range("2023-12-27",periods=6)
    for base,scope in ((root,dates[:3]),(confirmation,dates[3:])):
        f=pd.DataFrame(dict(date=scope,symbol="A",x=np.arange(len(scope),dtype=np.float32)))
        f.to_parquet(base/"chunks"/"0000"/"features.parquet",index=False)
        f.assign(instrument_id=1,data_source="EODHD",data_adjustment="SPLIT_DIVIDEND")[
            ["date","symbol","instrument_id","data_source","data_adjustment"]].to_parquet(base/"chunks"/"0000"/"bars.parquet",index=False)
        f.assign(**{TARGET:0.},path_amplitude=.1,oracle_available_date=scope+pd.Timedelta(days=30))[
            ["date","symbol",TARGET,"path_amplitude","oracle_available_date"]].to_parquet(base/"labels.parquet",index=False)
    profile=dict(feature_columns=["x"],generator_options={"enable_cross_sectional_ranks":False})
    meta,matrix=runner.build_cache(root,confirmation,profile,{},dates,neural.SequenceSpec(length=3),out,lambda *a:None)
    assert meta.sequence_eligible.tolist()==[False,False,True,True,True,True]
    assert meta.loc[3,"period"]=="confirmation" and matrix.shape==(6,1)
    again,cached=runner.build_cache(root,confirmation,profile,{},dates,neural.SequenceSpec(length=3),out,lambda *a:None)
    assert np.array_equal(matrix,cached) and again.equals(meta)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA absent")
def test_real_gpu_fit_with_full_feature_width(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    x=np.random.default_rng(42).normal(size=(560,173)).astype(np.float32)
    y=(x[:,0]>0).astype(np.float32)
    spec=neural.SequenceSpec(max_epochs=1)
    model,scaler,report=neural.fit(x,y,np.arange(40,440),np.arange(450,540),spec,tmp_path,"cuda",lambda *a:None)
    assert report["epochs_completed"]==1
    values=neural.predict(model,x,np.arange(450,540),scaler,spec,"cuda")
    assert np.isfinite(values).all() and next(model.parameters()).is_cuda
