"""First-touch contract + isolated local training; no real DB/API/orders."""
from dataclasses import replace
from datetime import date
import json

import numpy as np
import pandas as pd
import pytest

from modelFactory.config import (BaselineConfig, DataConfig, TrainingConfig, WalkForwardConfig,
                                OracleBarrierConfig, load_oracle_barrier_config)
from modelFactory.oracle_barrier import TARGETS, SCORES, ANY_TARGET, ANY_SCORE
from modelFactory.oracle_barrier.labels import symbol_barriers
from modelFactory.oracle_barrier import train as trainer


def bars(symbol="S00", n=90):
    return pd.DataFrame({"symbol": symbol, "date": pd.bdate_range("2020-01-02", periods=n),
        "open": 100., "close": 100., "adj_close": 100., "high": 101., "low": 99.,
        "volume": 1000., "is_filled": 0, "data_source": "EODHD",
        "data_adjustment": "SPLIT_DIVIDEND", "instrument_id": 1})


def paths(frame, config=None, end=None):
    return symbol_barriers(frame, pd.DatetimeIndex(frame.date), start=frame.date.min(),
        end=end or frame.date.max(), registry={}, config=config or OracleBarrierConfig())


def training_config(tmp_path, **overrides):
    cfg = TrainingConfig(data=DataConfig(oracle_barrier_model_only=True, feature_set="expert",
        training_start_date=date(2020, 1, 2), training_end_date=date(2020, 12, 31)),
        walk_forward=WalkForwardConfig(enabled=True, min_train_size=60, val_size=30,
            test_size=25, step_size=25, max_splits=2),
        baseline=BaselineConfig(n_estimators=10, lgbm_min_child_samples=2, lgbm_early_stopping_rounds=2),
        artifacts_dir=tmp_path, max_workers=1)
    return replace(cfg, **overrides)


def test_rise_then_fall_is_long_success_not_terminal_short():
    frame = bars()
    frame.loc[9, "high"] = 122
    frame.loc[18, "low"] = 69
    frame.loc[20, ["open", "high", "low", "close", "adj_close"]] = [74, 75, 73, 74, 74]
    row = paths(frame)[0].iloc[0]
    assert row[TARGETS["long"]] == 1 and row[TARGETS["short"]] == 0
    assert row.long_outcome == "TP" and row.short_outcome == "SL"
    assert row.long_exit_date == frame.date.iloc[9]
    assert row.short_exit_date == frame.date.iloc[9]
    assert row.long_gross_return == pytest.approx(.20)
    assert row[ANY_TARGET] == 1


def test_fall_then_rise_is_short_success_and_no_resurrection():
    frame = bars()
    frame.loc[4, "low"] = 78
    frame.loc[10, "high"] = 140
    row = paths(frame)[0].iloc[0]
    assert row[TARGETS["short"]] == 1 and row[TARGETS["long"]] == 0
    assert row.long_exit_date == frame.date.iloc[4]
    assert row.short_gross_return == pytest.approx(.20)


def test_whipsaw_can_stop_both_sides_before_a_large_later_move():
    frame = bars()
    frame.loc[2, "high"] = 108  # SHORT stopped before any -20 %.
    frame.loc[4, "low"] = 92   # LONG stopped before any +20 %.
    frame.loc[9, ["high", "low"]] = [130, 70]
    row = paths(frame)[0].iloc[0]
    assert row.long_outcome == row.short_outcome == "SL"
    assert row[ANY_TARGET] == 0
    assert row.long_exit_date == frame.date.iloc[4]
    assert row.short_exit_date == frame.date.iloc[2]


def test_exact_barrier_touch_with_decimal_entry():
    frame = bars()
    frame[["open", "close", "adj_close"]] = 12.3
    frame["high"], frame["low"] = 12.4, 12.2
    frame.loc[2, "high"] = 14.76
    row = paths(frame)[0].iloc[0]
    assert row.long_outcome == "TP" and row[TARGETS["long"]] == 1


def test_entry_is_next_open_not_j_close_and_day_j_does_not_count():
    frame = bars()
    frame.loc[0, "high"] = 130
    frame.loc[1, ["open", "high", "low", "close", "adj_close"]] = [110, 121, 109, 110, 110]
    frame.loc[2:, ["open", "high", "low", "close", "adj_close"]] = [110, 121, 109, 110, 110]
    row = paths(frame)[0].iloc[0]
    assert row.entry_price == 110
    assert row[TARGETS["long"]] == 0 and row.long_outcome == "EXPIRED"


@pytest.mark.parametrize("side,open_price,high,low,expected", [
    ("long", 85, 125, 80, -.15), ("short", 115, 120, 75, -.15),
    ("long", 125, 130, 90, .25), ("short", 75, 110, 70, .25)])
def test_gap_open_resolves_before_ambiguous_daily_extremes(side, open_price, high, low, expected):
    frame = bars()
    frame.loc[2, ["open", "high", "low", "close", "adj_close"]] = [open_price, high, low, open_price, open_price]
    row = paths(frame)[0].iloc[0]
    assert row[f"{side}_outcome"] == ("SL" if expected < 0 else "TP")
    assert row[f"{side}_exit_at_open"]
    assert row[f"{side}_exit_price"] == open_price
    assert row[f"{side}_gross_return"] == pytest.approx(expected)


def test_unknown_intrabar_order_is_not_fabricated():
    frame = bars()
    frame.loc[2, ["high", "low"]] = [125, 90]
    row = paths(frame)[0].iloc[0]
    assert row.path_qualified
    assert row.long_outcome == "AMBIGUOUS" and np.isnan(row[TARGETS["long"]])
    assert pd.isna(row.long_exit_date) and pd.isna(row.long_exit_at_open)
    assert row.short_outcome == "SL" and row[TARGETS["short"]] == 0
    assert np.isnan(row[ANY_TARGET])


def test_expiry_after_twenty_sessions_not_twenty_civil_days():
    frame = bars()
    frame.loc[21, ["open", "high", "low", "close", "adj_close"]] = [103, 150, 50, 100, 100]
    row = paths(frame)[0].iloc[0]
    assert row.long_outcome == "EXPIRED" and row.short_outcome == "EXPIRED"
    assert row.long_exit_date == frame.date.iloc[21]
    assert row.long_gross_return == pytest.approx(.03)
    assert row.oracle_available_date == frame.date.iloc[22]
    assert row[TARGETS["long"]] == 0 and row[TARGETS["short"]] == 0


def test_last_holding_session_counts_and_horizon_is_configurable():
    frame = bars()
    frame.loc[3, "high"] = 115
    row = paths(frame, OracleBarrierConfig(take_profit_pct=.10, max_sessions=3))[0].iloc[0]
    assert row.long_outcome == "TP"
    assert row.long_exit_date == frame.date.iloc[3]
    assert row.oracle_available_date == frame.date.iloc[5]


def test_split_adjustment_does_not_create_false_short():
    frame = bars()
    frame.loc[10:, ["open", "high", "low", "close"]] /= 2
    row = paths(frame)[0].iloc[0]
    assert row.path_qualified and row.short_outcome == "EXPIRED"
    assert row.entry_price == 100


@pytest.mark.parametrize("column,value", [("volume", 0), ("volume", np.inf), ("is_filled", 1),
    ("high", np.nan), ("high", 90), ("data_source", "UNKNOWN"), ("data_source", "ALPACA"),
    ("data_adjustment", "RAW"), ("instrument_id", 2), ("instrument_id", 0)])
def test_bad_future_preserves_membership_at_j_but_excludes_targets(column, value):
    frame = bars()
    frame.loc[10, column] = value
    result, membership = paths(frame)
    assert not result.path_qualified.iloc[0]
    assert result[list(TARGETS.values())].iloc[0].isna().all()
    assert frame.date.iloc[0] in set(membership.date)


def test_missing_session_and_conservative_maturity_even_early_tp():
    frame = bars()
    frame.loc[1, "high"] = 130
    sessions = pd.DatetimeIndex(frame.date)
    row = symbol_barriers(frame.drop(index=8), sessions, start=sessions[0], end=sessions[-1],
        registry={}, config=OracleBarrierConfig())[0].iloc[0]
    assert not row.path_qualified
    row = paths(frame, end=frame.date.iloc[21])[0].iloc[0]
    assert row.path_quality_reason == "IMMATURE_WINDOW" and np.isnan(row[TARGETS["long"]])


def test_known_identity_break_and_duplicate_dates_fail_closed():
    from modelFactory.oracle.security_continuity import SecurityDiscontinuity
    frame = bars()
    event = SecurityDiscontinuity("S00", frame.date.iloc[9], frame.date.iloc[10], "fixture")
    row = symbol_barriers(frame, pd.DatetimeIndex(frame.date), start=frame.date.min(), end=frame.date.max(),
        registry={"S00": (event,)}, config=OracleBarrierConfig())[0].iloc[0]
    assert row.path_quality_reason == "KNOWN_IDENTITY_BREAK"
    with pytest.raises(ValueError, match="Duplicate"):
        paths(pd.concat([frame, frame.iloc[[0]]], ignore_index=True))


@pytest.mark.parametrize("values", [{"take_profit_pct": 20}, {"stop_loss_pct": 0},
    {"take_profit_pct": float("nan")}, {"stop_loss_pct": True}, {"max_sessions": 0},
    {"max_sessions": 2.5}, {"max_sessions": True}, {"max_sessions": 61}])
def test_bad_parameters_rejected(values):
    with pytest.raises(ValueError):
        OracleBarrierConfig(**values)


def test_yaml_defaults_and_override(monkeypatch):
    import common.config_loader as loader
    monkeypatch.setattr(loader, "load_config", lambda path: {"oracle_barrier": {"take_profit_pct": .15}})
    assert load_oracle_barrier_config().take_profit_pct == .15
    assert load_oracle_barrier_config().stop_loss_pct == .07
    monkeypatch.setattr(loader, "load_config", lambda path: {"oracle_barrier": {"typo": 5}})
    with pytest.raises(ValueError, match="inconnues"):
        load_oracle_barrier_config()
    monkeypatch.setattr(loader, "load_config", lambda path: {"oracle_barrier": False})
    with pytest.raises(ValueError, match="objet YAML"):
        load_oracle_barrier_config()


@pytest.mark.parametrize("changes", [dict(data=DataConfig(oracle_barrier_model_only=True, enable_oracle_model=True)),
    dict(data=DataConfig(oracle_barrier_model_only=True, oracle_path_model_only=True)),
    dict(data=DataConfig(oracle_barrier_model_only=True, global_model_only=True)),
    dict(data=DataConfig(oracle_barrier_model_only=True, benchmark_symbol="QQQ")),
    dict(directional_profiles_enabled=True), dict(oracle_universe_mode="pit_dynamic_bars"),
    dict(walk_forward=WalkForwardConfig(enabled=False)),
    dict(walk_forward=WalkForwardConfig(enabled=True, step_size=1, test_size=2))])
def test_modes_stay_separate(tmp_path, changes):
    with pytest.raises(ValueError):
        training_config(tmp_path, **changes)


def test_cli_and_pipeline_command_default_and_custom_barriers():
    from modelFactory.cli import build_arg_parser
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    parser = build_arg_parser()
    assert not parser.parse_args(["--mode", "train"]).oracle_barrier_model_only
    opts = PipelineLaunchOptions(ml_oracle_barrier_model_only=True, ml_oracle_model_only=True,
        ml_enable_oracle_model=True, ml_walkforward=True, ml_training_end_date="2024-12-31")
    command = build_pipeline_command("ml_train", opts)
    assert "--oracle-barrier-model-only" in command
    assert "--oracle-model-only" not in command and "--enable-oracle-model" not in command
    assert "--oracle-path-model-only" not in command and "--global-model-only" not in command
    assert "--enable-global-model" not in command and "--enable-global-stacking" not in command
    parsed = parser.parse_args(command[4:])
    assert parsed.oracle_barrier_tp_pct == .20 and parsed.oracle_barrier_sl_pct == .07
    assert parsed.oracle_barrier_max_sessions == 20
    custom = parser.parse_args(build_pipeline_command("ml_train", replace(opts,
        ml_oracle_barrier_tp_pct=.15, ml_oracle_barrier_sl_pct=.05, ml_oracle_barrier_max_sessions=10))[4:])
    assert (custom.oracle_barrier_tp_pct, custom.oracle_barrier_sl_pct, custom.oracle_barrier_max_sessions) == (.15, .05, 10)
    with pytest.raises(ValueError, match="Choisir"):
        build_pipeline_command("ml_train", replace(opts, ml_oracle_path_model_only=True))


def test_metrics_do_not_replace_highest_score_unknown_outcomes():
    frame = pd.DataFrame({"date": pd.Timestamp("2020-01-02"), "symbol": [f"S{i:02d}" for i in range(20)],
        TARGETS["long"]: [np.nan] + [1.] * 19, SCORES["long"]: np.arange(20, 0, -1) / 20})
    result = trainer.metrics(frame, TARGETS["long"], SCORES["long"])
    assert result["selected_at_10pct"] == 2 and result["evaluated_at_10pct"] == 1
    assert result["excluded_labels"] == 1


def test_direction_rule_ties_abstentions_and_baselines():
    frame = pd.DataFrame({SCORES["long"]: [.8, .3, .4, .8, np.nan],
        SCORES["short"]: [.3, .8, .3, .8, .8], TARGETS["long"]: [1., 0., 0., 1., 0.],
        TARGETS["short"]: [0., 1., 0., 0., 1.], "long_gross_return": [.2, -.07, .03, .2, -.07],
        "short_gross_return": [-.07, .2, -.03, -.07, .2]})
    annotated = trainer.annotate_direction(frame, .5)
    assert annotated.research_direction.tolist() == ["LONG", "SHORT", "ABSTAIN", "ABSTAIN", "ABSTAIN"]
    assert np.isnan(annotated[ANY_SCORE].iloc[-1])
    result = trainer.direction_metrics(annotated)
    assert result["chosen_tp_rate"] == 1
    assert result["paired_always_long_tp_rate"] == .5 == result["paired_always_short_tp_rate"]


def fixture_panel():
    frames = []
    for i in range(20):
        frame = bars(f"S{i:02d}", n=200)
        frame["instrument_id"] = i + 1
        if i < 5:
            frame["high"] = 125.
        elif i < 10:
            frame["low"] = 75.
        frames.append(frame)
    return pd.concat(frames, ignore_index=True), pd.DatetimeIndex(frames[0].date)


def test_real_lightgbm_two_heads_resume_causality_and_namespace(tmp_path, monkeypatch):
    panel, calendar = fixture_panel()
    cfg = training_config(tmp_path / "campaign")
    monkeypatch.setattr(trainer, "nyse_sessions", lambda *a: calendar)
    monkeypatch.setattr(trainer, "load_security_discontinuities", lambda: {})
    monkeypatch.setattr(trainer, "load_bars", lambda *a: panel.copy())
    def features(*args, **kwargs):
        assert kwargs["generator_options"]["enable_cross_sectional_ranks"] is False
        result = panel[["date", "symbol"]].copy()
        result["momentum_20"] = result.symbol.str[1:].astype(float)
        return result
    monkeypatch.setattr(trainer, "build_feature_matrix", features)
    report = trainer.train_oracle_barrier(cfg, object(), "fixture-barrier", sorted(panel.symbol.unique()))
    assert report["status"] == "completed" and report["n_folds"] == 2
    assert report["serving_ready"] is False
    root = cfg.artifacts_dir / "oracle_barrier"
    oof = pd.read_parquet(root / "oof_predictions.parquet")
    assert set(TARGETS.values()) | set(SCORES.values()) <= set(oof)
    assert "oracle_extreme10" not in oof and "oracle_path_extreme20" not in oof
    assert not oof.duplicated(["date", "symbol"]).any()
    for fold in report["folds"]:
        folder = root / "folds" / fold["fold_start"]
        for side in TARGETS:
            assert (folder / f"{side}_model.txt").is_file()
            assert pd.Timestamp(fold["heads"][side]["train_available_max"]) < pd.Timestamp(fold["val_start"])
            assert pd.Timestamp(fold["heads"][side]["val_available_max"]) < pd.Timestamp(fold["fold_start"])
    assert not (cfg.artifacts_dir / "oracle").exists() and not (cfg.artifacts_dir / "oracle_path").exists()
    monkeypatch.setattr(trainer, "load_bars", lambda *a: pytest.fail("reuse dataset"))
    monkeypatch.setattr(trainer, "train_model", lambda *a: pytest.fail("reuse models"))
    again = trainer.train_oracle_barrier(cfg, object(), "fixture-barrier", sorted(panel.symbol.unique()))
    assert again["overall"] == report["overall"]
    assert trainer.is_barrier_batch(cfg.artifacts_dir, "fixture-barrier")
    with pytest.raises(ValueError, match="protocole différent"):
        trainer.train_oracle_barrier(replace(cfg, oracle_barrier=OracleBarrierConfig(take_profit_pct=.15)),
            object(), "fixture-barrier", sorted(panel.symbol.unique()))
    marker = root / "chunks" / "0000" / "done.json"
    assert json.loads(marker.read_text())["files"]
    (marker.parent / "features.parquet").write_bytes(b"corrupt fixture")
    with pytest.raises(ValueError, match="Corrupt"):
        trainer.train_oracle_barrier(cfg, object(), "fixture-barrier", sorted(panel.symbol.unique()))


def test_existing_terminal_campaign_cannot_be_replaced(tmp_path):
    root = tmp_path / "old-terminal"
    (root / "oracle").mkdir(parents=True)
    with pytest.raises(ValueError, match="occupée"):
        trainer.train_oracle_barrier(training_config(root), object(), "old", [f"S{i}" for i in range(20)])
    assert not (root / "oracle_barrier").exists()


def test_orchestrator_dispatch_isolated(tmp_path, monkeypatch):
    from modelFactory import orchestrator
    monkeypatch.setattr(trainer, "train_oracle_barrier", lambda cfg, *a: {
        "status": "completed", "root": str(cfg.artifacts_dir), "serving_ready": False})
    monkeypatch.setattr(orchestrator, "train_oracle_extreme", lambda *a, **kw: pytest.fail("terminal trainer"))
    monkeypatch.setattr(orchestrator, "_train_worker", lambda *a, **kw: pytest.fail("per-symbol trainer"))
    result = orchestrator.run_training_batch(training_config(tmp_path), object(),
        symbols=[f"S{i}" for i in range(20)], batch_id="new-barrier")
    assert len(result) == 1 and result[0].symbol == "__ORACLE_BARRIER__"
    assert result[0].metrics["root"] == str(tmp_path / "new-barrier")


def test_orchestrator_rejects_rebuild_missing_before_touching_db(tmp_path):
    from modelFactory import orchestrator
    with pytest.raises(ValueError, match="rebuild-all"):
        orchestrator.run_training_batch(training_config(tmp_path), object(), symbols=[f"S{i}" for i in range(20)],
            mode="rebuild-missing", batch_id="barrier")


def test_cli_rejects_barrier_overrides_without_mode_before_db(monkeypatch):
    import sys
    from modelFactory import cli
    monkeypatch.setattr(cli, "get_sqlalchemy_engine", lambda: pytest.fail("DB must not be reached"))
    monkeypatch.setattr(sys, "argv", ["modelFactory", "--mode", "train", "--market-code", "US_EQ",
                                    "--oracle-barrier-tp-pct", "0.2"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2


def test_pipeline_complete_widget_and_mutually_exclusive_modes():
    from streamlit.testing.v1 import AppTest
    def app():
        import streamlit as st
        from ihm.pages._execution_center import _build_launch_options
        from ihm.services.pipeline_runner import build_pipeline_command
        options, _ = _build_launch_options()
        st.session_state["barrier_command"] = build_pipeline_command("ml_train", options)
    at = AppTest.from_function(app)
    at.session_state["pipeline_ml_oracle_barrier_model_only"] = True
    at.session_state["pipeline_ml_oracle_path_model_only"] = True
    at.session_state["pipeline_ml_directional_profiles_enabled"] = True
    at.run(timeout=30)
    assert not at.exception
    command = at.session_state["barrier_command"]
    assert "--oracle-barrier-model-only" in command
    assert "--oracle-path-model-only" not in command and "--oracle-model-only" not in command
    assert "--directional-feature-profiles" not in command
    assert at.checkbox(key="pipeline_ml_walkforward").disabled
    assert at.checkbox(key="pipeline_ml_oracle_path_model_only").disabled
    at.checkbox(key="pipeline_ml_oracle_barrier_model_only").uncheck().run(timeout=30)
    assert not at.exception and "--oracle-barrier-model-only" not in at.session_state["barrier_command"]
