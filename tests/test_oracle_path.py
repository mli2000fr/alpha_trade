from dataclasses import replace
from datetime import date
import json

import numpy as np
import pandas as pd
import pytest

from modelFactory.config import BaselineConfig, DataConfig, TrainingConfig, WalkForwardConfig
from modelFactory.oracle_path import TARGET, SCORE
from modelFactory.oracle_path.labels import classify, symbol_paths
from modelFactory.oracle_path import train as trainer


def bars(symbol="S00", n=90):
    return pd.DataFrame({"symbol": symbol, "date": pd.bdate_range("2020-01-02", periods=n),
        "open": 100., "close": 100., "adj_close": 100., "high": 101., "low": 99.,
        "volume": 1000, "is_filled": 0, "data_source": "EODHD",
        "data_adjustment": "SPLIT_DIVIDEND", "instrument_id": 1})


def paths(frame, end=None):
    return symbol_paths(frame, pd.DatetimeIndex(frame.date), start=frame.date.min(),
                        end=end or frame.date.max(), registry={})


def config(tmp_path, **overrides):
    result = TrainingConfig(data=DataConfig(oracle_path_model_only=True,
        training_start_date=date(2020, 1, 2), training_end_date=date(2020, 12, 31),
        feature_set="expert"), walk_forward=WalkForwardConfig(enabled=True,
        min_train_size=60, val_size=30, test_size=25, step_size=25, max_splits=2),
        baseline=BaselineConfig(n_estimators=10, lgbm_min_child_samples=2,
                                lgbm_early_stopping_rounds=2), artifacts_dir=tmp_path, max_workers=1)
    return replace(result, **overrides)


def test_path_target_not_terminal_and_not_absolute_dollars():
    frame = bars()
    frame.loc[9, ["open", "high", "low", "close", "adj_close"]] = [130, 132, 129, 130, 130]
    frame.loc[20, ["open", "high", "low", "close", "adj_close"]] = [75, 76, 74, 75, 75]
    frame.loc[21, "high"] = 900  # beyond the future window, must not affect J
    result, _ = paths(frame)
    row = result.iloc[0]
    assert row.path_qualified
    assert row.path_amplitude == pytest.approx(.32)
    assert row.terminal_return == pytest.approx(-.25)
    assert row.oracle_exit_date == frame.date.iloc[20]
    assert row.oracle_available_date == frame.date.iloc[21]


def test_negative_excursion_can_dominate_and_symmetric_tie_is_valid_amplitude():
    frame = bars()
    frame.loc[4, "high"] = 125
    frame.loc[12, "low"] = 70
    result, _ = paths(frame)
    assert result.path_amplitude.iloc[0] == pytest.approx(.30)
    frame.loc[12, "low"] = 75
    result, _ = paths(frame)
    assert result.path_qualified.iloc[0]
    assert result.path_amplitude.iloc[0] == pytest.approx(.25)


def test_split_is_adjusted_consistently():
    frame = bars()
    frame.loc[10:, ["open", "high", "low", "close"]] /= 2
    result, _ = paths(frame)
    assert result.path_qualified.iloc[0]
    assert result.path_amplitude.iloc[0] == pytest.approx(.01)


@pytest.mark.parametrize("column,value", [("volume", 0), ("is_filled", 1), ("high", np.nan),
    ("high", 90), ("data_source", "UNKNOWN"), ("data_source", "ALPACA"),
    ("data_adjustment", "RAW"), ("instrument_id", 2)])
def test_future_bad_path_does_not_remove_membership_at_j(column, value):
    frame = bars()
    frame.loc[10, column] = value
    result, membership = paths(frame)
    assert not result.path_qualified.iloc[0]
    assert result.path_amplitude.isna().iloc[0]
    assert frame.date.iloc[0] in set(membership.date)


def test_missing_session_not_forward_filled_and_j_plus_21_maturity():
    frame = bars()
    sessions = pd.DatetimeIndex(frame.date)
    result, _ = symbol_paths(frame.drop(index=8), sessions, start=sessions[0], end=sessions[-1], registry={})
    assert not result.path_qualified.iloc[0]
    result, _ = paths(frame, end=frame.date.iloc[20])
    assert result.path_quality_reason.iloc[0] == "IMMATURE_WINDOW"


def test_known_identity_break_invalidates_path():
    from modelFactory.oracle.security_continuity import SecurityDiscontinuity
    frame = bars()
    event = SecurityDiscontinuity("S00", frame.date.iloc[9], frame.date.iloc[10], "fixture")
    result, _ = symbol_paths(frame, pd.DatetimeIndex(frame.date), start=frame.date.min(),
                            end=frame.date.max(), registry={"S00": (event,)})
    assert result.path_quality_reason.iloc[0] == "KNOWN_IDENTITY_BREAK"


def test_target_daily_absolute_rank_coverage_and_constant_ties():
    labels = pd.DataFrame({"date": pd.Timestamp("2020-01-02"),
        "symbol": [f"S{i}" for i in range(20)], "path_amplitude": np.arange(20) / 100.,
        "path_qualified": True})
    result = classify(labels)
    assert result[TARGET].sum() == 4
    assert result.loc[result[TARGET].eq(1), "path_amplitude"].min() == .16
    labels.loc[0, ["path_amplitude", "path_qualified"]] = [np.nan, False]
    assert classify(labels)[TARGET].notna().sum() == 19
    labels.loc[1, ["path_amplitude", "path_qualified"]] = [np.nan, False]
    assert classify(labels)[TARGET].isna().all()
    labels["path_amplitude"] = .1
    labels["path_qualified"] = True
    assert classify(labels)[TARGET].isna().all()


def test_restored_cross_sectional_ranks_include_future_bad_symbols():
    features = pd.DataFrame({"date": pd.Timestamp("2020-01-02"), "symbol": ["A", "B", "C"],
                             "momentum_20": [1, 2, 3]})
    ranked = trainer.restore_ranks(features, {})
    assert ranked.momentum_20_xs_rank.to_list() == pytest.approx([1/3, 2/3, 1])


@pytest.mark.parametrize("changes", [dict(oracle_horizon=5), dict(oracle_universe_mode="pit_dynamic_bars"),
    dict(data=DataConfig(oracle_path_model_only=True, enable_oracle_model=True)),
    dict(directional_profiles_enabled=True), dict(walk_forward=WalkForwardConfig(enabled=False)),
    dict(walk_forward=WalkForwardConfig(enabled=True, step_size=1, test_size=2))])
def test_path_contract_rejects_conflicting_modes(tmp_path, changes):
    with pytest.raises(ValueError, match="Oracle parcours|modes séparés"):
        config(tmp_path, **changes)


def test_cli_ihm_path_mode_separate_from_default_and_terminal():
    from modelFactory.cli import build_arg_parser
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    assert build_arg_parser().parse_args(["--mode", "train"]).oracle_path_model_only is False
    opts = PipelineLaunchOptions(ml_oracle_path_model_only=True, ml_oracle_model_only=True,
                                ml_enable_oracle_model=True, ml_walkforward=True,
                                ml_training_end_date="2024-12-31")
    command = build_pipeline_command("ml_train", opts)
    assert "--oracle-path-model-only" in command
    assert "--enable-oracle-model" not in command
    assert "--oracle-model-only" not in command
    assert "--global-model-only" not in command
    assert build_arg_parser().parse_args(command[4:]).oracle_path_model_only
    terminal = build_pipeline_command("ml_train", PipelineLaunchOptions(ml_oracle_model_only=True))
    assert "--oracle-model-only" in terminal
    assert "--oracle-path-model-only" not in terminal


def test_isolation_fit_resume_and_real_lightgbm(tmp_path, monkeypatch):
    """Full local fixture training; no external DB, old champions or label writes."""
    symbols = [f"S{i:02d}" for i in range(20)]
    frames = []
    for i, symbol in enumerate(symbols):
        frame = bars(symbol, n=200)
        frame["high"] = 101 + i
        frame["instrument_id"] = i + 1
        frames.append(frame)
    panel = pd.concat(frames, ignore_index=True)
    cfg = config(tmp_path / "campaign")
    calendar = pd.DatetimeIndex(frames[0].date)
    monkeypatch.setattr(trainer, "nyse_sessions", lambda *a: calendar)
    monkeypatch.setattr(trainer, "load_security_discontinuities", lambda: {})
    monkeypatch.setattr(trainer, "load_bars", lambda *a: panel.copy())
    def features(*args, **kwargs):
        assert kwargs["generator_options"]["enable_cross_sectional_ranks"] is False
        result = panel[["date", "symbol"]].copy()
        result["momentum_20"] = result.symbol.str[1:].astype(float)
        return result
    monkeypatch.setattr(trainer, "build_feature_matrix", features)
    result = trainer.train_oracle_path(cfg, object(), "fixture-path", symbols)
    assert result["status"] == "completed"
    assert result["n_folds"] == 2
    assert result["serving_ready"] is True
    root = cfg.artifacts_dir / "oracle_path"
    assert (root / "folds" / result["folds"][0]["fold_start"] / "path_model.txt").is_file()
    assert not (cfg.artifacts_dir / "oracle").exists()
    oof = pd.read_parquet(root / "oof_predictions.parquet")
    assert TARGET in oof and SCORE in oof
    assert "oracle_extreme10" not in oof
    assert not oof.duplicated(["date", "symbol"]).any()
    for fold in result["folds"]:
        assert pd.Timestamp(fold["train_available_max"]) < pd.Timestamp(fold["val_start"])
        assert pd.Timestamp(fold["val_available_max"]) < pd.Timestamp(fold["test_start"])
    from modelFactory.oracle.dataset import TARGET_COL
    assert TARGET_COL == "oracle_extreme10"
    monkeypatch.setattr(trainer, "load_bars", lambda *a: pytest.fail("cache must be reused"))
    monkeypatch.setattr(trainer, "train_model", lambda *a: pytest.fail("saved fold must be reused"))
    again = trainer.train_oracle_path(cfg, object(), "fixture-path", symbols)
    assert again["overall"] == result["overall"]
    assert trainer.is_path_batch(cfg.artifacts_dir, "fixture-path")
    with pytest.raises(ValueError, match="protocole différent"):
        trainer.train_oracle_path(replace(cfg, max_workers=2), object(), "fixture-path", symbols)


def test_orchestrator_dispatch_skips_all_legacy_training(tmp_path, monkeypatch):
    from modelFactory import orchestrator
    cfg = config(tmp_path)
    seen = []
    def path(config, engine, batch_id, symbols):
        seen.append(config.artifacts_dir)
        return {"status": "completed", "mode": "oracle_path_h20"}
    monkeypatch.setattr(trainer, "train_oracle_path", path)
    monkeypatch.setattr(orchestrator, "update_training_batch", lambda *a, **kw: None)
    monkeypatch.setattr(orchestrator, "train_oracle_extreme", lambda *a, **kw: pytest.fail("legacy Oracle called"))
    monkeypatch.setattr(orchestrator, "_train_worker", lambda *a, **kw: pytest.fail("per symbol called"))
    results = orchestrator.run_training_batch(cfg, object(), symbols=[f"S{i}" for i in range(20)], batch_id="new-path")
    assert len(results) == 1 and results[0].symbol == "__ORACLE_PATH__"
    assert results[0].status == "completed"
    assert seen == [tmp_path / "new-path"]


def test_atomic_progress_retries_windows_file_lock(tmp_path, monkeypatch):
    original = trainer.os.replace
    calls = []
    def replace_file(src, dst):
        calls.append(src)
        if len(calls) < 3:
            raise PermissionError("reader holds file")
        return original(src, dst)
    monkeypatch.setattr(trainer.os, "replace", replace_file)
    monkeypatch.setattr(trainer.time, "sleep", lambda _: None)
    trainer.atomic_json(tmp_path / "progress.json", {"status": "COMPLETED"})
    assert json.loads((tmp_path / "progress.json").read_text())["status"] == "COMPLETED"
    assert not list(tmp_path.glob("*.tmp"))


def test_existing_terminal_artifacts_cannot_be_overwritten(tmp_path):
    destination = tmp_path / "old-terminal"
    destination.mkdir()
    (destination / "oracle").mkdir()
    (destination / "oracle" / "champion.txt").write_text("original")
    with pytest.raises(ValueError, match="aucun artefact existant"):
        trainer.train_oracle_path(config(destination), object(), "old-terminal", [f"S{i}" for i in range(20)])
    assert (destination / "oracle" / "champion.txt").read_text() == "original"
    assert not (destination / "oracle_path").exists()


def test_feature_warmup_reserved_before_future_label_ranking():
    labels = pd.DataFrame({"date": pd.Timestamp("2020-01-02"),
        "symbol": [f"S{i}" for i in range(21)], "path_amplitude": np.arange(21) / 100.,
        "path_qualified": True})
    features = labels.loc[labels.symbol.ne("S20"), ["date", "symbol"]]
    result = trainer.qualify_feature_membership(labels, features)
    assert result[TARGET].sum() == 4
    assert result.loc[result.symbol.eq("S20"), TARGET].isna().all()
    assert not result.loc[result.symbol.eq("S20"), "feature_eligible"].iloc[0]


def test_full_training_widget_path_mode_and_command():
    from streamlit.testing.v1 import AppTest
    def app():
        import streamlit as st
        from ihm.pages._execution_center import _build_launch_options
        from ihm.services.pipeline_runner import build_pipeline_command
        options, _ = _build_launch_options()
        st.session_state["test_path_command"] = build_pipeline_command("ml_train", options)
        st.session_state["test_path_enabled"] = options.ml_oracle_path_model_only
    at = AppTest.from_function(app)
    at.session_state["pipeline_ml_oracle_barrier_model_only"] = False
    at.session_state["pipeline_ml_oracle_path_model_only"] = True
    at.session_state["pipeline_ml_directional_profiles_enabled"] = True
    at.session_state["pipeline_ml_enable_oracle_model"] = True
    at.run(timeout=30)
    assert not at.exception
    assert "--oracle-path-model-only" in at.session_state["test_path_command"]
    assert "--enable-oracle-model" not in at.session_state["test_path_command"]
    assert "--directional-feature-profiles" not in at.session_state["test_path_command"]
    assert at.checkbox(key="pipeline_ml_walkforward").disabled
    at.checkbox(key="pipeline_ml_oracle_path_model_only").uncheck().run(timeout=30)
    assert not at.exception
    assert not at.session_state["test_path_enabled"]
    assert "--oracle-path-model-only" not in at.session_state["test_path_command"]
