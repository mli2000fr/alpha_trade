"""Frozen confirmation: causal dates, no replacement of missing outcomes, local-only."""
from hashlib import sha256
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.research import oracle_path_confirmation as module
from modelFactory.oracle_path import TARGET, MODE
from modelFactory.oracle_path.train import atomic_json, digest


def panel(day="2024-01-02"):
    symbols = [f"S{i:02d}" for i in range(60)]
    scores = pd.DataFrame(dict(date=pd.Timestamp(day), symbol=symbols,
        score_lightgbm=np.arange(60, dtype=float), score_catboost=np.arange(60, dtype=float),
        score_validation_champion=np.arange(60, dtype=float)))
    labels = pd.DataFrame(dict(date=pd.Timestamp(day), symbol=symbols,
        path_amplitude=np.arange(60)/100, **{TARGET: (np.arange(60)>=48).astype(float)}))
    return scores, labels


def test_missing_original_first_pick_not_replaced_by_next_symbol():
    scores, labels = panel()
    labels.loc[labels.symbol.eq("S59"), TARGET] = np.nan
    years, daily, strict, joined = module.evaluate(scores, labels,
        pd.bdate_range("2024-01-02", periods=60), pd.Timestamp("2024-03-15"))
    top = years["2024"]["strict_original_top"]["lightgbm"]["10"]
    assert top["common_complete_dates"] == 0 and top["precision"] is None
    assert top["missing_selected_outcomes"] == 1
    row = strict[(strict.backend=="lightgbm") & strict["count"].eq(10)].iloc[0]
    assert row.precision_lower_bound == .9 and row.precision_upper_bound == 1.
    # Conditional metric remains separate and would otherwise hide this missing pick.
    assert years["2024"]["conditional"]["lightgbm"]["precision_top_10_titles"] == 1.


def test_paired_days_same_for_both_candidates_and_no_future_label_at_early_peak():
    scores, labels = panel()
    scores["score_catboost"] = scores.score_lightgbm.iloc[::-1].to_numpy()
    scores["score_validation_champion"] = scores.score_catboost
    labels.loc[labels.symbol.eq("S00"), TARGET] = np.nan
    calendar = pd.bdate_range("2024-01-02", periods=60)
    years, daily, strict, _ = module.evaluate(scores, labels, calendar, calendar[20])
    assert daily.status.to_list() == ["IMMATURE"]  # J+21 required, even if path already touched peak.
    assert years["2024"]["evaluated_rows"] == 0
    assert years["2024"]["immature_dates"] == 1
    years, daily, strict, _ = module.evaluate(scores, labels, calendar, calendar[21])
    assert years["2024"]["strict_original_top"]["lightgbm"]["10"]["common_complete_dates"] == 0
    assert years["2024"]["strict_original_top"]["catboost"]["10"]["common_complete_dates"] == 0


def test_bad_keys_or_short_calendar_fail():
    scores, labels = panel()
    with pytest.raises(ValueError, match="Doublons"):
        module.evaluate(pd.concat([scores, scores]), labels, pd.bdate_range("2024-01-02", periods=60), "2024-03-15")
    with pytest.raises(ValueError, match="maturité"):
        module.evaluate(scores, labels, pd.bdate_range("2024-01-02", periods=10), "2024-03-15")


def test_completed_session_obeys_early_close_and_timezone(monkeypatch):
    schedule = pd.DataFrame(dict(market_close=pd.to_datetime(["2024-11-27T21:00Z", "2024-11-29T18:00Z"])),
        index=pd.to_datetime(["2024-11-27", "2024-11-29"]))
    monkeypatch.setattr(module, "_get_nyse_calendar", lambda: SimpleNamespace(schedule=lambda **k: schedule))
    assert module.completed_session(pd.Timestamp("2024-11-29T17:59Z")) == pd.Timestamp("2024-11-27")
    assert module.completed_session(pd.Timestamp("2024-11-29T19:01+01:00")) == pd.Timestamp("2024-11-29")
    with pytest.raises(ValueError, match="Timezone"):
        module.completed_session(pd.Timestamp("2024-11-29"))


def test_exclusive_run_blocks_duplicate_process_and_unlocks(tmp_path):
    with module.exclusive_run(tmp_path):
        with pytest.raises(RuntimeError, match="déjà"):
            with module.exclusive_run(tmp_path):
                pytest.fail("concurrent run")
    with module.exclusive_run(tmp_path):
        pass


def test_full_local_confirmation_and_resume_no_training_or_writes(tmp_path, monkeypatch):
    import lightgbm as lgb
    from catboost import CatBoostClassifier
    source = tmp_path/"source"
    root = source/"models"/"oracle-path-comparison"/"oracle_path"
    folder = root/"folds"/"2023-01-05"
    folder.mkdir(parents=True)
    universe = [f"S{i:02d}" for i in range(20)]
    x = pd.DataFrame(dict(x=np.arange(20, dtype=float)))
    target = (x.x>=16).astype(int)
    lgbm = lgb.train(dict(objective="binary", num_threads=1, min_data_in_leaf=1000, verbosity=-1),
        lgb.Dataset(x, label=target), num_boost_round=1)
    cb = CatBoostClassifier(iterations=5, depth=2, allow_writing_files=False, verbose=False, thread_count=1)
    cb.fit(x, target)
    lgbm.save_model(str(folder/"path_model.txt"))
    cb.save_model(str(folder/"catboost_model.cbm"))
    done = dict(metrics=dict(fold_start="2023-01-05", train_available_max="2022-07-06", val_available_max="2023-01-04"),
        files={n:digest(folder/n) for n in ("path_model.txt", "catboost_model.cbm")},
        champion=dict(backend="catboost", model_file="catboost_model.cbm", selection="validation_auc; exact_tie_lightgbm"),
        validation_candidates={"lightgbm":{"auc":.5},"catboost":{"auc":.9}})
    atomic_json(folder/"done.json", done)
    protocol = dict(batch_id="oracle-path-comparison", mode=MODE, target=TARGET, horizon=20,
        serving_ready=True, universe=universe, generator_options={"enable_cross_sectional_ranks":False},
        backend="lightgbm_catboost_cpu", security_discontinuities={},
        training_config={"data":{"training_end_date":"2023-12-31"}})
    protocol["fingerprint"] = sha256(json.dumps(protocol, sort_keys=True, default=str).encode()).hexdigest()
    atomic_json(root/"protocol.json", protocol)
    atomic_json(root/"feature_profile.json", dict(mode=MODE, target=TARGET, serving_ready=True,
        feature_columns=["x"], generator_options=protocol["generator_options"]))
    atomic_json(root/"report.json", dict(mode=MODE, batch_id="oracle-path-comparison", serving_ready=True, status="completed", n_folds=1))
    atomic_json(source/"plan.json", dict(source_hashes={}))
    dates = pd.bdate_range("2024-01-02", periods=100)
    as_of = pd.Timestamp("2024-03-15")
    start, end = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-03")
    monkeypatch.setattr(module, "nyse_sessions", lambda *a: dates)
    monkeypatch.setattr(module, "resolve_window", lambda *a, **k: (start,end,as_of))
    monkeypatch.setattr(module, "load_security_discontinuities", lambda: {})
    def load(*a):
        return pd.DataFrame([dict(date=d, symbol=s, open=100., high=101.+i, low=99., close=100., adj_close=100.,
            volume=1000, is_filled=0, instrument_id=i+1, data_source="EODHD", data_adjustment="SPLIT_DIVIDEND")
            for i,s in enumerate(universe) for d in dates if d<=as_of])
    monkeypatch.setattr(module, "load_bars", load)
    def features(*a, **kw):
        assert kw["membership"].date.max() <= as_of
        assert kw["end_date"] == "2024-01-03"
        return pd.DataFrame([dict(date=d,symbol=s,x=float(i)) for d in dates[:2] for i,s in enumerate(universe)])
    monkeypatch.setattr(module, "build_feature_matrix", features)
    monkeypatch.setattr("modelFactory.oracle_path.train.train_model", lambda *a: pytest.fail("must not retrain"))
    monkeypatch.setattr("modelFactory.oracle_path.predict.write_path_predictions", lambda *a: pytest.fail("must not write SQL"))
    engine = SimpleNamespace(url=SimpleNamespace(database="alpha_trade"))
    out = tmp_path/"out"
    report = module.run(engine, source, out, end="2024-01-03", as_of="2024-03-15")
    assert report["status"] == "completed" and report["scored_rows"] == 40
    assert report["years"]["2024"]["strict_original_top"]["catboost"]["10"]["common_complete_dates"] == 2
    assert report["validation_champion"] == "catboost"
    assert (out/"scores.parquet").is_file()
    assert json.loads((out/"run.json").read_text())["status"] == "COMPLETED"
    monkeypatch.setattr(module, "load_bars", lambda *a: pytest.fail("reuse archived inputs"))
    monkeypatch.setattr(module, "build_feature_matrix", lambda *a, **k: pytest.fail("reuse archived features"))
    again = module.run(engine, source, out, end="2024-01-03", as_of="2024-03-15")
    assert again["years"] == report["years"]
    (out/"chunks"/"0000"/"features.parquet").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="Checkpoint corrompu"):
        module.run(engine, source, out, end="2024-01-03", as_of="2024-03-15")
