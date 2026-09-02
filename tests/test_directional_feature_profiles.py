from __future__ import annotations

import json
from pathlib import Path

import pytest

from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
from modelFactory.config import DataConfig, TrainingConfig
from modelFactory.cli import build_arg_parser
from modelFactory.db_registry import insert_predictions
from modelFactory.feature_profiles import (
    apply_feature_profile,
    discover_feature_profiles,
    load_feature_profile,
    resolve_profile_path,
)
from modelFactory.predictor import (
    DirectionalBundleContractError,
    _LightGBMBoosterAdapter,
    _directional_bundle_root,
    predict_directional_symbol,
    validate_directional_bundle_for_prediction,
)
from modelFactory.orchestrator import _oracle_requires_global_rank
from modelFactory.oracle.dataset import expert_feature_columns
from modelFactory.global_ranking import _XS_RANK_SOURCE_FEATURES, _xs_rank_column_name


def test_bundled_profiles_are_discoverable_and_valid() -> None:
    assert "oracle.json" in discover_feature_profiles("oracle")
    assert "long.json" in discover_feature_profiles("long")
    assert "short.json" in discover_feature_profiles("short")
    long_profile = load_feature_profile("long", "long.json")
    short_profile = load_feature_profile("short", "short.json")
    oracle_profile = load_feature_profile("oracle", "oracle.json")
    expected_oracle = expert_feature_columns() + [
        _xs_rank_column_name(column) for column in _XS_RANK_SOURCE_FEATURES
    ]
    assert oracle_profile["feature_columns"] == expected_oracle
    assert len(oracle_profile["feature_columns"]) == 174
    assert len(long_profile["feature_columns"]) == 84
    assert len(short_profile["feature_columns"]) == 130
    assert short_profile["generator_options"]["include_macro_move"] is True
    assert len(long_profile["sha256"]) == 64


def test_profile_path_rejects_traversal() -> None:
    with pytest.raises(ValueError):
        resolve_profile_path("long", "../short/short.json")


def test_cli_accepts_directional_profile_contract() -> None:
    options = build_arg_parser().parse_args([
        "--mode", "train", "--directional-feature-profiles",
        "--oracle-feature-profile", "oracle.json", "--long-feature-profile", "long.json",
        "--short-feature-profile", "short.json",
    ])
    assert options.directional_feature_profiles is True
    assert options.oracle_feature_profile == "oracle.json"
    assert options.long_feature_profile == "long.json"
    assert options.short_feature_profile == "short.json"


def test_profile_application_isolates_direction_artifacts() -> None:
    cfg = TrainingConfig(directional_profiles_enabled=True)
    effective = apply_feature_profile(cfg, load_feature_profile("long", "long.json"), "long")
    assert effective.model_role == "direction_long"
    assert effective.data.feature_set == "expert"
    assert effective.data.feature_whitelist_enabled is True
    assert effective.data.include_score_components is False
    assert effective.global_model.stacking_enabled is False
    assert len(effective.data.feature_whitelist) == 84
    assert effective.artifacts_dir.as_posix().endswith("directions/long")
    assert effective.data.target_mode == "ternary"
    assert effective.model.num_classes == 3
    assert effective.data.target_up_threshold == pytest.approx(0.03)
    assert effective.data.target_down_threshold == pytest.approx(-0.03)


def test_ihm_command_emits_bundle_and_ignores_manual_feature_switches() -> None:
    options = PipelineLaunchOptions(
        ml_directional_profiles_enabled=True,
        ml_oracle_feature_profile="oracle.json",
        ml_long_feature_profile="long.json",
        ml_short_feature_profile="short.json",
        ml_include_sentiment=True,
        ml_include_macro_vix=True,
        ml_global_model_only=True,
        ml_exclude_per_symbol_per_sector=True,
        ml_target_mode="regression",
    )
    command = build_pipeline_command("ml_train", options)
    assert "--directional-feature-profiles" in command
    assert command[command.index("--oracle-feature-profile") + 1] == "oracle.json"
    assert command[command.index("--long-feature-profile") + 1] == "long.json"
    assert command[command.index("--short-feature-profile") + 1] == "short.json"
    assert "--enable-oracle-model" in command
    assert "--include-sentiment" not in command
    assert "--include-macro-vix" not in command
    assert "--no-include-score-components" not in command
    assert "--global-model-only" not in command
    assert "--exclude-per-symbol-per-sector" not in command
    assert command[command.index("--target-mode") + 1] == "ternary"
    assert command[command.index("--num-classes") + 1] == "3"


def test_oracle_o0_bundle_does_not_require_global_rank_history() -> None:
    assert _oracle_requires_global_rank(TrainingConfig(directional_profiles_enabled=True)) is False
    assert _oracle_requires_global_rank(TrainingConfig()) is True
    assert _oracle_requires_global_rank(
        TrainingConfig(data=DataConfig(oracle_model_only=True))
    ) is False


def test_lightgbm_adapter_supports_regression_predict() -> None:
    import numpy as np

    class Booster:
        def predict(self, X):
            return [0.1, -0.2]

    adapter = _LightGBMBoosterAdapter(Booster())
    assert np.asarray(adapter.predict([[1], [2]])).tolist() == pytest.approx([0.1, -0.2])


def test_bundle_preflight_keeps_only_complete_ternary_symbols(tmp_path: Path) -> None:
    bundle = tmp_path / "batch-1"
    bundle.mkdir()
    (bundle / "cascade_manifest.json").write_text(json.dumps({
        "batch_id": "batch-1",
        "cascade_type": "oracle_extreme_plus_per_symbol_directional",
        "status": "completed",
        "serving_ready": True,
        "oracle": {"status": "completed"},
    }), encoding="utf-8")

    for symbol in ("BOTH", "LONG_ONLY"):
        directions = ("long", "short") if symbol == "BOTH" else ("long",)
        for direction in directions:
            symbol_dir = bundle / "directions" / direction / symbol
            symbol_dir.mkdir(parents=True)
            model_path = symbol_dir / "lightgbm_model.txt"
            model_path.write_text("tree\nversion=v4\n", encoding="utf-8")
            (symbol_dir / "config.json").write_text(json.dumps({
                "model_role": f"direction_{direction}",
                "data": {"target_mode": "ternary"},
                "model": {"num_classes": 3},
                "feature_fingerprint": "fp-ok",
                "feature_contract": {"feature_fingerprint": "fp-ok"},
                "architecture_selected": "lightgbm",
                "artifact_routes": {
                    "selected_model": "lightgbm",
                    "models": {"lightgbm": {"model_path": str(model_path)}},
                },
            }), encoding="utf-8")

    valid, excluded = validate_directional_bundle_for_prediction(
        bundle, ["BOTH", "LONG_ONLY"], require_oracle=False,
    )
    assert valid == ["BOTH"]
    assert excluded == {"LONG_ONLY": ["short:config_missing"]}


def test_bundle_preflight_rejects_non_servable_manifest(tmp_path: Path) -> None:
    bundle = tmp_path / "batch-1"
    bundle.mkdir()
    (bundle / "cascade_manifest.json").write_text(json.dumps({
        "batch_id": "batch-1",
        "cascade_type": "oracle_extreme_plus_per_symbol_directional",
        "status": "failed",
        "serving_ready": False,
    }), encoding="utf-8")
    with pytest.raises(DirectionalBundleContractError, match="bundle_not_serving_ready"):
        validate_directional_bundle_for_prediction(bundle, ["AAPL"], require_oracle=False)


def test_directional_manifest_detection(tmp_path: Path) -> None:
    batch = tmp_path / "batch-1"
    batch.mkdir()
    (batch / "cascade_manifest.json").write_text(json.dumps({
        "cascade_type": "oracle_extreme_plus_per_symbol_directional"
    }), encoding="utf-8")
    assert _directional_bundle_root(tmp_path, "batch-1") == batch


def test_directional_prediction_merges_branch_probabilities(monkeypatch, tmp_path: Path) -> None:
    import pandas as pd

    for direction in ("long", "short"):
        symbol_dir = tmp_path / "directions" / direction / "AAPL"
        symbol_dir.mkdir(parents=True)
        (symbol_dir / "config.json").write_text(json.dumps({
            "run_id": f"run-{direction}", "model_role": f"direction_{direction}"
        }), encoding="utf-8")

    def fake_predict(symbol, artifacts_dir, engine, prediction_date, **kwargs):
        is_long = artifacts_dir.parts[-2:] == ("directions", "long")
        return pd.DataFrame([{
            "symbol": symbol,
            "prediction_date": "2026-09-02",
            "predicted_proba": 0.72 if is_long else 0.61,
            "predicted_class": 1 if is_long else -1,
            "predicted_side": "long" if is_long else "short",
            "proba_long": 0.72 if is_long else 0.10,
            "proba_short": 0.12 if is_long else 0.61,
            "proba_flat": 0.16 if is_long else 0.29,
            "run_id": "run-long" if is_long else "run-short",
            "decision_threshold": 0.55,
            "calibration_method": "platt",
            "selected_model": "lightgbm",
            "source": "per_symbol",
        }])

    monkeypatch.setattr("modelFactory.predictor.predict_symbol", fake_predict)
    merged = predict_directional_symbol("AAPL", tmp_path, object(), persist=False)
    assert merged is not None
    row = merged.iloc[0]
    assert row["proba_long"] == pytest.approx(0.72)
    assert row["proba_short"] == pytest.approx(0.61)
    assert row["predicted_side"] == "long"
    assert row["direction_short_run_id"] == "run-short"
    assert row["selected_model"] == "directional_bundle"
    assert row["direction_long_model"] == "lightgbm"
    assert row["direction_short_model"] == "lightgbm"


def test_directional_lineage_is_persisted() -> None:
    import pandas as pd

    captured = {}

    class Connection:
        def execute(self, statement, params):
            captured["sql"] = str(statement)
            captured["params"] = params
            return type("Result", (), {"rowcount": 1})()

    class Context:
        def __enter__(self):
            return Connection()

        def __exit__(self, *args):
            return False

    class Engine:
        def begin(self):
            return Context()

    frame = pd.DataFrame([{
        "symbol": "AAPL", "prediction_date": "2026-09-02",
        "predicted_proba": 0.72, "predicted_class": 1,
        "predicted_side": "long", "proba_long": 0.72,
        "proba_flat": 0.16, "proba_short": 0.61,
        "run_id": "run-long", "selected_model": "directional_bundle",
        "decision_threshold": 0.55, "signal_label": "LONG",
        "calibration_method": "long:platt|short:platt", "source": "per_symbol",
        "model_role": "directional_bundle",
        "direction_long_run_id": "run-long", "direction_short_run_id": "run-short",
        "direction_long_model": "lightgbm", "direction_short_model": "catboost",
    }])
    assert insert_predictions(Engine(), frame) == 1
    assert "direction_long_run_id" in captured["sql"]
    assert captured["params"]["long_run"] == "run-long"
    assert captured["params"]["short_run"] == "run-short"
    assert captured["params"]["long_model"] == "lightgbm"
    assert captured["params"]["short_model"] == "catboost"
