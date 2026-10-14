"""Real small CPU challengers; isolated files, no production SQL/API/account."""
from dataclasses import replace
from datetime import date
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from modelFactory.config import BaselineConfig, DataConfig, TrainingConfig, WalkForwardConfig
from modelFactory.oracle_path import TARGET, SCORE, MODE
from modelFactory.oracle_path import train as trainer, predict as serving


def fixture_data():
    dates = pd.bdate_range("2020-01-02", periods=200)
    data = pd.DataFrame([(day, f"S{i:02d}", float(i), int(i >= 16))
                         for day in dates for i in range(20)], columns=["date", "symbol", "x", TARGET])
    data["path_amplitude"] = data.x / 100
    data["terminal_return"] = 0.
    data["up_excursion"] = data.path_amplitude
    data["down_excursion"] = 0.
    data["oracle_available_date"] = data.date + pd.Timedelta(days=30)
    return data


def comparison_config(root):
    return TrainingConfig(data=DataConfig(oracle_path_model_only=True, feature_set="expert",
        training_start_date=date(2020, 1, 2), training_end_date=date(2020, 12, 31)),
        walk_forward=WalkForwardConfig(enabled=True, min_train_size=60, val_size=30,
            test_size=25, step_size=25, max_splits=2),
        baseline=BaselineConfig(enable_catboost=True, n_estimators=10, lgbm_min_child_samples=2,
            catboost_iterations=10, catboost_depth=2, catboost_border_count=32),
        artifacts_dir=root, max_workers=1)


def test_selection_validation_only_and_fixed_tie():
    assert trainer.select_champion({"catboost": {"auc": .7}, "lightgbm": {"auc": .7}}) == "lightgbm"
    assert trainer.select_champion({"lightgbm": {"auc": .7}, "catboost": {"auc": .71}}) == "catboost"
    with pytest.raises(ValueError, match="validation"):
        trainer.select_champion({"lightgbm": {"auc": None}})


def test_real_comparison_resume_and_test_labels_do_not_choose_champion(tmp_path, monkeypatch):
    data = fixture_data()
    root = tmp_path/"comparison"
    root.mkdir()
    cfg = comparison_config(root)
    events = []
    result = trainer.fit_folds(data, ["x"], cfg, root, lambda *a: events.append(a))
    assert result["n_folds"] == 2
    assert set(result["comparison_oof"]) == {"lightgbm", "catboost"}
    assert any(e[0] == "training_catboost_fold" for e in events)
    assert result["overall"]["dates_top_50_titles"] == 0  # never pretend 20 titles = TOP50
    for fold in result["folds"]:
        folder = root/"folds"/fold["fold_start"]
        done = json.loads((folder/"done.json").read_text())
        assert set(done["validation_candidates"]) == {"lightgbm", "catboost"}
        assert done["champion"]["backend"] == trainer.select_champion(done["validation_candidates"])
        assert set(done["files"]) == {"path_model.txt", "catboost_model.cbm", "oof.parquet"}
    oof = pd.read_parquet(root/"oof_predictions.parquet")
    assert {SCORE, "score_lightgbm", "score_catboost", "selected_backend"}.issubset(oof)
    # Hold training/validation and their fits fixed; reverse only test outcomes.
    fold = trainer.build_folds_adaptive(data, min_train_dates=60, val_dates=30,
        test_dates=25, step_dates=25, max_splits=1, forecast_horizon=20, materialize=False)[0]
    changed = data.copy()
    mask = changed.date.isin(fold["test_dates"])
    changed.loc[mask, TARGET] = 1-changed.loc[mask, TARGET]
    other = tmp_path/"changed"
    other.mkdir()
    one = replace(cfg, walk_forward=replace(cfg.walk_forward, max_splits=1))
    repeated = trainer.fit_folds(changed, ["x"], one, other, lambda *a: None)
    assert repeated["folds"][0]["selected_backend"] == result["folds"][0]["selected_backend"]
    assert repeated["folds"][0]["validation_candidates"] == result["folds"][0]["validation_candidates"]
    monkeypatch.setattr(trainer, "train_model", lambda *a: pytest.fail("resume must not train"))
    monkeypatch.setattr(trainer, "train_catboost", lambda *a: pytest.fail("resume must not train"))
    resumed = trainer.fit_folds(data, ["x"], cfg, root, lambda *a: None)
    assert resumed["comparison_oof"] == result["comparison_oof"]
    (root/"folds"/result["folds"][0]["fold_start"]/"catboost_model.cbm").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="Corrupt"):
        trainer.fit_folds(data, ["x"], cfg, root, lambda *a: None)


def test_real_catboost_serving_champion_no_silent_fallback(tmp_path, monkeypatch):
    from hashlib import sha256
    import lightgbm as lgb
    root = tmp_path/"batch"/"oracle_path"
    root.mkdir(parents=True)
    cfg = comparison_config(root)
    # Deliberately non-informative LGBM to exercise CatBoost's serving route.
    def constant_lgb(train, val, columns, config):
        return lgb.train(dict(objective="binary", verbosity=-1, num_threads=1, min_data_in_leaf=100000),
            lgb.Dataset(train[columns], label=train[TARGET]), num_boost_round=1)
    monkeypatch.setattr(trainer, "train_model", constant_lgb)
    result = trainer.fit_folds(fixture_data(), ["x"], cfg, root, lambda *a: None)
    assert all(f["selected_backend"] == "catboost" for f in result["folds"])
    universe = [f"S{i:02d}" for i in range(20)]
    protocol = dict(mode=MODE, batch_id="batch", target=TARGET, horizon=20, serving_ready=True,
        universe=universe, generator_options={}, backend="lightgbm_catboost_cpu")
    protocol["fingerprint"] = sha256(json.dumps(protocol, sort_keys=True, default=str).encode()).hexdigest()
    trainer.atomic_json(root/"protocol.json", protocol)
    trainer.atomic_json(root/"feature_profile.json", dict(mode=MODE, target=TARGET, serving_ready=True,
        feature_columns=["x"], generator_options={}))
    trainer.atomic_json(root/"report.json", dict(result, status="completed", batch_id="batch", mode=MODE, serving_ready=True))
    day = result["folds"][0]["fold_start"]
    monkeypatch.setattr("modelFactory.oracle.build_labels.nyse_sessions", lambda *a: pd.DatetimeIndex([day]))
    monkeypatch.setattr(serving, "build_inference_features", lambda *a: pd.DataFrame(
        dict(date=pd.Timestamp(day), symbol=universe, x=np.arange(20, dtype=float))))
    saved = []
    monkeypatch.setattr(serving, "write_path_predictions", lambda e, f, b: saved.append(f.copy()) or len(f))
    report = serving.predict_oracle_path_history(SimpleNamespace(url=SimpleNamespace(database="alpha_trade")),
        "batch", day, day, artifacts_dir=tmp_path)
    assert report["n_rows"] == 20 and report["directional"] is False
    assert saved[0].proba_extreme.between(0, 1).all()
    folder = root/"folds"/day
    done = json.loads((folder/"done.json").read_text())
    assert saved[0].model_sha256.iloc[0] == done["files"]["catboost_model.cbm"]
    done["champion"]["model_file"] = "../other.cbm"
    trainer.atomic_json(folder/"done.json", done)
    with pytest.raises(ValueError, match="Backend"):
        serving.load_contract(tmp_path, "batch")


def test_catboost_fit_failure_is_not_swallowed(tmp_path, monkeypatch):
    root = tmp_path/"fail"
    root.mkdir()
    def failure(*a):
        raise RuntimeError("CatBoost failed")
    monkeypatch.setattr(trainer, "train_catboost", failure)
    with pytest.raises(RuntimeError, match="CatBoost failed"):
        trainer.fit_folds(fixture_data(), ["x"], comparison_config(root), root, lambda *a: None)
    assert not list(root.glob("folds/*/done.json"))


def test_research_defaults_and_ihm_command_agree(tmp_path):
    from scripts.research.oracle_path_comparison import comparison_config as research_config
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    options = PipelineLaunchOptions(ml_oracle_path_model_only=True, ml_walkforward=True, ml_enable_catboost=True)
    cfg = research_config(tmp_path, options.ml_training_start_date, options.ml_training_end_date)
    assert cfg.data.oracle_path_model_only and cfg.baseline.enable_catboost
    assert cfg.baseline.n_estimators == options.ml_lgbm_n_estimators
    assert cfg.baseline.catboost_iterations == options.ml_catboost_iterations
    assert cfg.data.include_sentiment_features == options.ml_include_sentiment
    assert cfg.walk_forward.max_splits == options.ml_wf_max_splits
    assert cfg.max_workers == options.ml_max_workers
    command = build_pipeline_command("ml_train", options)
    assert "--enable-catboost" in command and "--oracle-path-model-only" in command
    assert command[command.index("--default-champion")+1] == "lightgbm"  # no pretend LSTM
