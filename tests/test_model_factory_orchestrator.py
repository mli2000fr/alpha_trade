import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from modelFactory import orchestrator
from modelFactory.config import ChampionSelectionConfig, DataConfig, ModelConfig, TrainingConfig
from modelFactory.features import build_feature_contract


def test_orchestrator_importable():
    assert hasattr(orchestrator, "__doc__")


def test_run_training_batch_loads_tradable_universe_symbols(monkeypatch, tmp_path) -> None:
    cfg = TrainingConfig(
        data=DataConfig(),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )

    monkeypatch.setattr(
        orchestrator,
        "load_tradable_universe_for_period",
        lambda engine, start_date, end_date: ["AAPL", "MSFT"],
    )
    monkeypatch.setattr(
        orchestrator,
        "_train_worker",
        lambda symbol, cfg, **kwargs: orchestrator.TrainResult(symbol, f"run-{symbol}", "completed"),
    )

    results = orchestrator.run_training_batch(
        cfg,
        engine=object(),
        symbols=None,
        universe_date=date(2026, 4, 17),
    )

    assert [result.symbol for result in results] == ["AAPL", "MSFT"]


def test_run_training_batch_passes_shared_batch_id_to_workers(monkeypatch, tmp_path) -> None:
    cfg = TrainingConfig(
        data=DataConfig(),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )
    batch_ids: list[str] = []
    artifact_dirs: list[tuple[object, object, object, object, object]] = []

    def fake_train_worker(symbol, cfg, **kwargs):
        batch_ids.append(kwargs["batch_id"])
        artifact_dirs.append(
            (
                cfg.artifacts_dir,
                cfg.benchmark_artifacts_dir,
                cfg.global_benchmark_artifacts_dir,
                cfg.catboost_artifacts_dir,
                cfg.batch_id,
            )
        )
        return orchestrator.TrainResult(symbol, f"run-{symbol}", "completed")

    monkeypatch.setattr(orchestrator, "_train_worker", fake_train_worker)

    results = orchestrator.run_training_batch(
        cfg,
        engine=object(),
        symbols=["AAPL", "MSFT"],
        batch_id="campaign-20260715",
    )

    assert [result.symbol for result in results] == ["AAPL", "MSFT"]
    assert len(set(batch_ids)) == 1
    assert batch_ids == ["campaign-20260715", "campaign-20260715"]
    expected_artifact_dirs = (
        tmp_path / "campaign-20260715",
        Path("artifacts/benchmarks") / "campaign-20260715",
        Path("artifacts/global_benchmark") / "campaign-20260715",
        Path("catboost_info") / "campaign-20260715",
        "campaign-20260715",
    )
    assert artifact_dirs == [expected_artifact_dirs, expected_artifact_dirs]


def test_run_training_batch_requires_pit_date_without_explicit_symbols(tmp_path) -> None:
    cfg = TrainingConfig(
        data=DataConfig(),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )

    import pytest

    with pytest.raises(ValueError, match="training_start_date et training_end_date ou universe_date"):
        orchestrator.run_training_batch(cfg, engine=object(), symbols=None)


def test_train_worker_loads_universe_when_cross_sectional_enabled(monkeypatch) -> None:
    cfg = TrainingConfig(
        data=DataConfig(enable_cross_sectional_features=True, benchmark_symbol="SPY"),
        model=ModelConfig(max_epochs=1),
        accelerator="cpu",
    )
    captured: dict[str, object] = {}

    import database.connection as db_connection

    monkeypatch.setattr(db_connection, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(orchestrator, "load_symbol_latest_bar_date", lambda engine, symbol, end_date=None: date(2026, 4, 17))
    monkeypatch.setattr(orchestrator, "load_symbol_bars", lambda engine, symbol, end_date=None, start_date=None: {"symbol": symbol, "start_date": start_date, "end_date": end_date})
    monkeypatch.setattr(orchestrator, "load_benchmark_bars", lambda engine, benchmark_symbol, end_date=None, start_date=None: "benchmark")
    monkeypatch.setattr(orchestrator, "load_symbol_sentiment", lambda engine, symbol, end_date=None, start_date=None: "sentiment")
    def fake_train_symbol(
        symbol,
        bars,
        cfg,
        engine,
        sentiment_df=None,
        benchmark_df=None,
        universe_df=None,
        selector_df=None,
        cross_sectional_df=None,
        batch_id=None,
        **kwargs,
    ):
        captured["symbol"] = symbol
        captured["cross_sectional_df"] = cross_sectional_df
        return orchestrator.TrainResult(symbol, "run-1", "completed")

    monkeypatch.setattr(orchestrator, "train_symbol", fake_train_symbol)

    cross_sectional_cache = pd.DataFrame(
        {"symbol": ["AAPL"], "date": [pd.Timestamp("2026-04-17")], "ret_20_rank": [0.7]}
    )
    result = orchestrator._train_worker(
        "AAPL",
        cfg,
        universe_symbols=["AAPL", "MSFT"],
        cross_sectional_cache=cross_sectional_cache,
    )

    assert result.status == "completed"
    assert captured["symbol"] == "AAPL"
    assert captured["cross_sectional_df"].iloc[0]["ret_20_rank"] == 0.7


def test_train_worker_loads_selector_context_when_enabled(monkeypatch) -> None:
    cfg = TrainingConfig(
        data=DataConfig(include_screener_scores=True),
        model=ModelConfig(max_epochs=1),
        accelerator="cpu",
    )
    captured: dict[str, object] = {}

    import database.connection as db_connection

    monkeypatch.setattr(db_connection, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(orchestrator, "load_symbol_latest_bar_date", lambda engine, symbol, end_date=None: date(2026, 4, 17))
    monkeypatch.setattr(orchestrator, "load_symbol_bars", lambda engine, symbol, end_date=None, start_date=None: {"symbol": symbol})
    monkeypatch.setattr(orchestrator, "load_symbol_selector_context", lambda engine, symbol, end_date=None, start_date=None: {"symbol": symbol, "end_date": end_date, "start_date": start_date})

    def fake_train_symbol(
        symbol,
        bars,
        cfg,
        engine,
        sentiment_df=None,
        benchmark_df=None,
        universe_df=None,
        selector_df=None,
        cross_sectional_df=None,
        batch_id=None,
        **kwargs,
    ):
        captured["symbol"] = symbol
        captured["selector_df"] = selector_df
        return orchestrator.TrainResult(symbol, "run-1", "completed")

    monkeypatch.setattr(orchestrator, "train_symbol", fake_train_symbol)

    result = orchestrator._train_worker("AAPL", cfg)

    assert result.status == "completed"
    assert captured["symbol"] == "AAPL"
    assert captured["selector_df"]["symbol"] == "AAPL"
    assert captured["selector_df"]["end_date"] == date(2026, 4, 17)
    assert captured["selector_df"]["start_date"] == date(2020, 1, 1)


@pytest.mark.skip(reason="obsolete: global model training is no longer orchestrated by run_training_batch")
def test_run_training_batch_injects_global_model_into_symbol_artifacts(monkeypatch, tmp_path) -> None:
    batch_id = "campaign-global"
    cfg = TrainingConfig(
        data=DataConfig(),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
        accelerator="cpu",
    )
    cfg = TrainingConfig(
        data=cfg.data,
        model=cfg.model,
        calibration=cfg.calibration,
        walk_forward=cfg.walk_forward,
        baseline=cfg.baseline,
        global_model=cfg.global_model.__class__(enabled=True, model_name="lightgbm", artifact_symbol="__GLOBAL__"),
        target_optimization=cfg.target_optimization,
        threshold_optimization=cfg.threshold_optimization,
        artifacts_dir=cfg.artifacts_dir,
        max_workers=1,
        accelerator="cpu",
    )

    def fake_train_worker(symbol, cfg, **kwargs):
        symbol_dir = cfg.artifacts_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        with open(symbol_dir / "config.json", "w", encoding="utf-8") as fh:
            json.dump({
                "architecture_selected": "lstm_attention",
                "artifact_routes": {"selected_model": "lstm_attention", "models": {"lstm_attention": {}}},
            }, fh)
        with open(symbol_dir / "metrics.json", "w", encoding="utf-8") as fh:
            json.dump({
                "challengers": {
                    "lstm_attention": {"status": "completed", "model_name": "lstm_attention", "selection_score": 0.60, "test": {"auc": 0.60}},
                    "ranking": [{"rank": 1, "model_name": "lstm_attention", "selection_score": 0.60, "status": "selected_default_champion", "reason": None}],
                }
            }, fh)
        return orchestrator.TrainResult(symbol, f"run-{symbol}", "completed", metrics={})

    monkeypatch.setattr(orchestrator, "_train_worker", fake_train_worker)
    monkeypatch.setattr(orchestrator, "train_global_model", lambda symbols, cfg, artifacts_dir, engine: {
        "status": "completed",
        "artifact_symbol": "__GLOBAL__",
        "backend_model_name": "lightgbm",
        "artifact_paths": {"model_path": str(artifacts_dir / "__GLOBAL__" / "global_model.pkl"), "config_path": str(artifacts_dir / "__GLOBAL__" / "config.json"), "calibrator_path": None},
        "selection_score": 0.7,
        "by_symbol": {
            "AAPL": {"status": "completed", "model_name": "global_model", "selection_score": 0.7, "test": {"auc": 0.7}},
            "MSFT": {"status": "completed", "model_name": "global_model", "selection_score": 0.68, "test": {"auc": 0.68}},
        },
    })

    results = orchestrator.run_training_batch(cfg, engine=object(), symbols=["AAPL", "MSFT"], batch_id=batch_id)

    assert len(results) == 2
    with open(tmp_path / batch_id / "AAPL" / "config.json", encoding="utf-8") as fh:
        config_data = json.load(fh)
    with open(tmp_path / batch_id / "AAPL" / "metrics.json", encoding="utf-8") as fh:
        metrics = json.load(fh)
    assert config_data["artifact_routes"]["models"]["global_model"]["inference_backend"] == "global_tabular"
    assert metrics["challengers"]["global_model"]["model_name"] == "global_model"


@pytest.mark.skip(reason="obsolete: global model training is no longer orchestrated by run_training_batch")
def test_run_training_batch_can_auto_select_global_model(monkeypatch, tmp_path) -> None:
    batch_id = "campaign-auto-global"
    cfg = TrainingConfig(
        data=DataConfig(),
        model=ModelConfig(max_epochs=1),
        global_model=TrainingConfig().global_model.__class__(enabled=True, model_name="lightgbm", artifact_symbol="__GLOBAL__"),
        champion_selection=ChampionSelectionConfig(enabled=True, allow_auto_selection=True, default_champion="lstm_attention"),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )

    def fake_train_worker(symbol, cfg, **kwargs):
        symbol_dir = cfg.artifacts_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        with open(symbol_dir / "config.json", "w", encoding="utf-8") as fh:
            json.dump({
                "architecture_selected": "lstm_attention",
                "selection_mode": "auto_selected_champion",
                "champion_selection": {"enabled": True, "allow_auto_selection": True, "default_champion": "lstm_attention", "selection_metric": "selection_score"},
                "artifact_routes": {"selected_model": "lstm_attention", "models": {"lstm_attention": {"checkpoint_path": "x", "scaler_path": "y", "config_path": "z", "inference_backend": "lstm_attention"}}},
            }, fh)
        with open(symbol_dir / "metrics.json", "w", encoding="utf-8") as fh:
            json.dump({
                "challengers": {
                    "lstm_attention": {"status": "completed", "model_name": "lstm_attention", "selection_score": 0.60, "test": {"auc": 0.60}},
                    "ranking": [{"rank": 1, "model_name": "lstm_attention", "selection_score": 0.60, "status": "selected_auto_champion", "reason": None}],
                },
                "champion": {"model_name": "lstm_attention", "selection_mode": "auto_selected_champion", "selection_score": 0.60},
            }, fh)
        return orchestrator.TrainResult(symbol, f"run-{symbol}", "completed", metrics={})

    monkeypatch.setattr(orchestrator, "_train_worker", fake_train_worker)
    monkeypatch.setattr(orchestrator, "train_global_model", lambda symbols, cfg, artifacts_dir, engine: {
        "status": "completed",
        "artifact_symbol": "__GLOBAL__",
        "backend_model_name": "lightgbm",
        "artifact_paths": {"model_path": str(artifacts_dir / "__GLOBAL__" / "global_model.pkl"), "config_path": str(artifacts_dir / "__GLOBAL__" / "config.json"), "calibrator_path": None},
        "selection_score": 0.85,
        "by_symbol": {
            "AAPL": {"status": "completed", "model_name": "global_model", "selection_score": 0.85, "test": {"auc": 0.85}},
        },
    })

    orchestrator.run_training_batch(cfg, engine=object(), symbols=["AAPL"], batch_id=batch_id)

    with open(tmp_path / batch_id / "AAPL" / "config.json", encoding="utf-8") as fh:
        config_data = json.load(fh)
    with open(tmp_path / batch_id / "AAPL" / "metrics.json", encoding="utf-8") as fh:
        metrics = json.load(fh)

    assert config_data["architecture_selected"] == "global_model"
    assert config_data["artifact_routes"]["selected_model"] == "global_model"
    assert metrics["champion"]["model_name"] == "global_model"


def test_inject_global_model_persists_model_governance(monkeypatch, tmp_path) -> None:
    symbol_dir = tmp_path / "AAPL"
    symbol_dir.mkdir(parents=True, exist_ok=True)
    with open(symbol_dir / "config.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "run_id": "run-AAPL",
                "architecture_selected": "lstm_attention",
                "artifact_routes": {
                    "selected_model": "lstm_attention",
                    "models": {
                        "lstm_attention": {
                            "checkpoint_path": "best.ckpt",
                            "scaler_path": "scaler.pkl",
                            "config_path": str(symbol_dir / "config.json"),
                            "inference_backend": "lstm_attention",
                        }
                    },
                },
            },
            fh,
        )
    with open(symbol_dir / "metrics.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "challengers": {
                    "lstm_attention": {"status": "completed", "model_name": "lstm_attention", "selection_score": 0.60, "test": {"auc": 0.60}},
                    "ranking": [{"rank": 1, "model_name": "lstm_attention", "status": "selected_default_champion", "selection_score": 0.60}],
                },
                "champion": {"model_name": "lstm_attention", "selection_mode": "default_champion", "selection_score": 0.60},
            },
            fh,
        )

    governance_calls: list[dict[str, object]] = []
    monkeypatch.setattr(orchestrator, "replace_model_governance", lambda engine, **kwargs: governance_calls.append(kwargs) or 2)

    cfg = TrainingConfig(
        data=DataConfig(),
        model=ModelConfig(max_epochs=1),
        global_model=TrainingConfig().global_model.__class__(enabled=True, model_name="lightgbm", artifact_symbol="__GLOBAL__"),
        champion_selection=ChampionSelectionConfig(enabled=True, allow_auto_selection=True, default_champion="lstm_attention"),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )
    global_result = {
        "status": "completed",
        "artifact_symbol": "__GLOBAL__",
        "backend_model_name": "lightgbm",
        "artifact_paths": {
            "model_path": str(tmp_path / "__GLOBAL__" / "global_model.pkl"),
            "config_path": str(tmp_path / "__GLOBAL__" / "config.json"),
            "calibrator_path": None,
        },
        "selection_score": 0.85,
        "by_symbol": {
            "AAPL": {"status": "completed", "model_name": "global_model", "selection_score": 0.85, "test": {"auc": 0.85}},
        },
    }

    orchestrator._inject_global_model_into_symbol_artifacts("AAPL", cfg, global_result, engine=object())

    assert len(governance_calls) == 1
    governance_call = governance_calls[0]
    assert governance_call["run_id"] == "run-AAPL"
    assert governance_call["selected_model"] == "lstm_attention"
    assert any(row["model_name"] == "global_model" for row in governance_call["ranking"])


def test_inject_global_model_tolerates_governance_write_failure(monkeypatch, tmp_path) -> None:
    symbol_dir = tmp_path / "AAPL"
    symbol_dir.mkdir(parents=True, exist_ok=True)
    with open(symbol_dir / "config.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "run_id": "run-AAPL",
                "architecture_selected": "lstm_attention",
                "artifact_routes": {
                    "selected_model": "lstm_attention",
                    "models": {
                        "lstm_attention": {
                            "checkpoint_path": "best.ckpt",
                            "scaler_path": "scaler.pkl",
                            "config_path": str(symbol_dir / "config.json"),
                            "inference_backend": "lstm_attention",
                        }
                    },
                },
            },
            fh,
        )
    with open(symbol_dir / "metrics.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "challengers": {
                    "lstm_attention": {"status": "completed", "model_name": "lstm_attention", "selection_score": 0.60, "test": {"auc": 0.60}},
                    "ranking": [{"rank": 1, "model_name": "lstm_attention", "status": "selected_default_champion", "selection_score": 0.60}],
                },
                "champion": {"model_name": "lstm_attention", "selection_mode": "default_champion", "selection_score": 0.60},
            },
            fh,
        )

    monkeypatch.setattr(orchestrator, "replace_model_governance", lambda engine, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")))

    cfg = TrainingConfig(
        data=DataConfig(),
        model=ModelConfig(max_epochs=1),
        global_model=TrainingConfig().global_model.__class__(enabled=True, model_name="lightgbm", artifact_symbol="__GLOBAL__"),
        champion_selection=ChampionSelectionConfig(enabled=True, allow_auto_selection=True, default_champion="lstm_attention"),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )
    global_result = {
        "status": "completed",
        "artifact_symbol": "__GLOBAL__",
        "backend_model_name": "lightgbm",
        "artifact_paths": {
            "model_path": str(tmp_path / "__GLOBAL__" / "global_model.pkl"),
            "config_path": str(tmp_path / "__GLOBAL__" / "config.json"),
            "calibrator_path": None,
        },
        "selection_score": 0.85,
        "by_symbol": {
            "AAPL": {"status": "completed", "model_name": "global_model", "selection_score": 0.85, "test": {"auc": 0.85}},
        },
    }

    orchestrator._inject_global_model_into_symbol_artifacts("AAPL", cfg, global_result, engine=object())

    with open(symbol_dir / "config.json", encoding="utf-8") as fh:
        config_data = json.load(fh)
    with open(symbol_dir / "metrics.json", encoding="utf-8") as fh:
        metrics = json.load(fh)

    assert config_data["artifact_routes"]["selected_model"] == "lstm_attention"
    assert metrics["champion"]["model_name"] == "lstm_attention"


def test_filter_symbols_by_mode_rebuild_missing_keeps_only_absent_artifacts(monkeypatch, tmp_path) -> None:
    cfg = TrainingConfig(
        data=DataConfig(),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )
    (tmp_path / "AAPL").mkdir(parents=True, exist_ok=True)
    with open(tmp_path / "AAPL" / "config.json", "w", encoding="utf-8") as fh:
        json.dump({"feature_fingerprint": "anything"}, fh)

    kept = orchestrator._filter_symbols_by_mode(object(), ["AAPL", "MSFT"], mode="rebuild-missing", cfg=cfg)

    assert kept == ["MSFT"]


def test_filter_symbols_by_mode_refresh_stale_keeps_only_outdated_models(monkeypatch, tmp_path) -> None:
    cfg = TrainingConfig(
        data=DataConfig(training_start_date=date(2020, 1, 1)),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )
    current_fp = orchestrator.compute_feature_fingerprint(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
    )
    current_contract = build_feature_contract(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
    )
    for symbol, trained_through in (("AAPL", "2026-04-16"), ("MSFT", "2026-04-17")):
        symbol_dir = tmp_path / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        with open(symbol_dir / "config.json", "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "feature_fingerprint": current_fp,
                    "feature_columns": current_contract["feature_columns"],
                    "feature_contract": current_contract,
                    "trained_through_date": trained_through,
                    "data": {"training_start_date": "2020-01-01"},
                },
                fh,
            )

    monkeypatch.setattr(
        orchestrator,
        "load_symbol_latest_bar_dates",
        lambda engine, symbols, end_date=None: {"AAPL": date(2026, 4, 17), "MSFT": date(2026, 4, 17)},
    )

    kept = orchestrator._filter_symbols_by_mode(object(), ["AAPL", "MSFT"], mode="refresh-stale", cfg=cfg)

    assert kept == ["AAPL"]


def test_filter_symbols_by_mode_refresh_stale_accepts_legacy_history_window_artifacts(monkeypatch, tmp_path) -> None:
    cfg = TrainingConfig(
        data=DataConfig(training_start_date=date(2016, 4, 17)),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )
    current_fp = orchestrator.compute_feature_fingerprint(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
    )
    current_contract = build_feature_contract(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
    )
    symbol_dir = tmp_path / "AAPL"
    symbol_dir.mkdir(parents=True, exist_ok=True)
    with open(symbol_dir / "config.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "feature_fingerprint": current_fp,
                "feature_columns": current_contract["feature_columns"],
                "feature_contract": current_contract,
                "trained_through_date": "2026-04-17",
                "data": {"history_window_years": 10},
            },
            fh,
        )

    monkeypatch.setattr(
        orchestrator,
        "load_symbol_latest_bar_dates",
        lambda engine, symbols, end_date=None: {"AAPL": date(2026, 4, 17)},
    )

    kept = orchestrator._filter_symbols_by_mode(object(), ["AAPL"], mode="refresh-stale", cfg=cfg)

    assert kept == []


def test_filter_symbols_by_mode_refresh_stale_rebuilds_when_feature_contract_missing(monkeypatch, tmp_path) -> None:
    cfg = TrainingConfig(
        data=DataConfig(training_start_date=date(2020, 1, 1)),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )
    current_fp = orchestrator.compute_feature_fingerprint(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
    )
    symbol_dir = tmp_path / "AAPL"
    symbol_dir.mkdir(parents=True, exist_ok=True)
    with open(symbol_dir / "config.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "feature_fingerprint": current_fp,
                "trained_through_date": "2026-04-17",
                "data": {"training_start_date": "2020-01-01"},
            },
            fh,
        )

    monkeypatch.setattr(
        orchestrator,
        "load_symbol_latest_bar_dates",
        lambda engine, symbols, end_date=None: {"AAPL": date(2026, 4, 17)},
    )

    kept = orchestrator._filter_symbols_by_mode(object(), ["AAPL"], mode="refresh-stale", cfg=cfg)

    assert kept == ["AAPL"]


def test_train_worker_uses_training_end_date_as_history_cutoff(monkeypatch) -> None:
    cfg = TrainingConfig(
        data=DataConfig(training_start_date=date(2020, 1, 1), training_end_date=date(2024, 12, 31)),
        model=ModelConfig(max_epochs=1),
        accelerator="cpu",
    )
    captured: dict[str, object] = {}

    import database.connection as db_connection

    monkeypatch.setattr(db_connection, "get_sqlalchemy_engine", lambda: object())

    def _fake_latest_bar_date(engine, symbol, end_date=None):
        captured["requested_end_date"] = end_date
        return date(2024, 12, 31)

    monkeypatch.setattr(orchestrator, "load_symbol_latest_bar_date", _fake_latest_bar_date)
    monkeypatch.setattr(orchestrator, "load_symbol_bars", lambda engine, symbol, end_date=None, start_date=None: {"symbol": symbol, "end_date": end_date, "start_date": start_date})
    monkeypatch.setattr(orchestrator, "train_symbol", lambda symbol, bars, cfg, engine, **kwargs: orchestrator.TrainResult(symbol, "run-1", "completed"))

    result = orchestrator._train_worker("AAPL", cfg)

    assert result.status == "completed"
    assert captured["requested_end_date"] == date(2024, 12, 31)


def test_filter_symbols_by_mode_refresh_stale_rebuilds_when_training_end_date_changes(monkeypatch, tmp_path) -> None:
    cfg = TrainingConfig(
        data=DataConfig(training_start_date=date(2020, 1, 1), training_end_date=date(2026, 4, 17)),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )
    current_fp = orchestrator.compute_feature_fingerprint(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
    )
    current_contract = build_feature_contract(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
    )
    symbol_dir = tmp_path / "AAPL"
    symbol_dir.mkdir(parents=True, exist_ok=True)
    with open(symbol_dir / "config.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "feature_fingerprint": current_fp,
                "feature_columns": current_contract["feature_columns"],
                "feature_contract": current_contract,
                "trained_through_date": "2026-04-17",
                "data": {"training_start_date": "2020-01-01", "training_end_date": "2026-04-16"},
            },
            fh,
        )

    monkeypatch.setattr(
        orchestrator,
        "load_symbol_latest_bar_dates",
        lambda engine, symbols, end_date=None: {"AAPL": date(2026, 4, 17)},
    )

    kept = orchestrator._filter_symbols_by_mode(object(), ["AAPL"], mode="refresh-stale", cfg=cfg)

    assert kept == ["AAPL"]


# ─────────────────────────────────────────────────────────────────────────────
# POINT 1 (2026-08-29) : remplir global_rank_history AVANT la jointure Oracle
# pendant l'entraînement (mode combiné). Sans ce pré-remplissage, build_dataset
# (merge INNER sur global_rank_history) produit un dataset vide → Oracle skipped.
# ─────────────────────────────────────────────────────────────────────────────


def test_train_oracle_extreme_prefills_global_rank_history_before_dataset(monkeypatch, tmp_path) -> None:
    """POINT 1 : en mode combiné (require_global_rank=True), predict_global_rank_history
    est appelé AVANT build_dataset pour remplir global_rank_history (sinon dataset vide)."""
    import modelFactory.oracle.dataset as oracle_dataset_mod
    import modelFactory.oracle.build_labels as oracle_build_labels_mod
    import modelFactory.predictor as predictor_mod

    call_order: list[str] = []
    pgrh_kwargs: dict = {}

    def _fake_pgrh(start, end, batch_id, *, artifacts_dir=None, engine=None, symbols=None):
        call_order.append("predict_global_rank_history")
        pgrh_kwargs.update(start=start, end=end, batch_id=batch_id, artifacts_dir=artifacts_dir, symbols=symbols)
        return {"2022-01-03": 2}

    def _fake_build_dataset(*a, **k):
        call_order.append("build_dataset")
        return pd.DataFrame(), []  # dataset vide → skipped proprement

    monkeypatch.setattr(oracle_build_labels_mod, "build_labels", lambda *a, **k: {"status": "ok"})
    monkeypatch.setattr(predictor_mod, "predict_global_rank_history", _fake_pgrh)
    monkeypatch.setattr(oracle_dataset_mod, "build_dataset", _fake_build_dataset)

    cfg = TrainingConfig(
        data=DataConfig(
            training_start_date=date(2022, 1, 1),
            training_end_date=date(2022, 1, 31),
            oracle_model_only=False,
        ),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
    )
    result = orchestrator.train_oracle_extreme(
        cfg, engine=object(), batch_id="batch-1", symbols=["AAPL", "MSFT"],
    )

    assert result["status"] == "skipped"  # dataset vide → skipped proprement
    assert call_order == ["predict_global_rank_history", "build_dataset"]
    assert pgrh_kwargs["start"] == "2022-01-01"
    assert pgrh_kwargs["end"] == "2022-01-31"
    assert pgrh_kwargs["batch_id"] == "batch-1"
    assert pgrh_kwargs["artifacts_dir"] == tmp_path
    assert pgrh_kwargs["symbols"] == ["AAPL", "MSFT"]


def test_train_oracle_extreme_skips_global_rank_prefill_when_oracle_only(monkeypatch, tmp_path) -> None:
    """POINT 1 : en mode oracle_model_only (require_global_rank=False), le pré-remplissage
    de global_rank_history est SKIPPÉ (pas de jointure global_rank attendue)."""
    import modelFactory.oracle.dataset as oracle_dataset_mod
    import modelFactory.oracle.build_labels as oracle_build_labels_mod
    import modelFactory.predictor as predictor_mod

    call_order: list[str] = []
    monkeypatch.setattr(oracle_build_labels_mod, "build_labels", lambda *a, **k: {"status": "ok"})
    monkeypatch.setattr(
        predictor_mod, "predict_global_rank_history",
        lambda *a, **k: call_order.append("predict_global_rank_history") or {},
    )
    monkeypatch.setattr(
        oracle_dataset_mod, "build_dataset",
        lambda *a, **k: call_order.append("build_dataset") or (pd.DataFrame(), []),
    )

    cfg = TrainingConfig(
        data=DataConfig(
            training_start_date=date(2022, 1, 1),
            training_end_date=date(2022, 1, 31),
            oracle_model_only=True,
        ),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
    )
    result = orchestrator.train_oracle_extreme(
        cfg, engine=object(), batch_id="batch-1", symbols=["AAPL"],
    )

    assert result["status"] == "skipped"
    assert call_order == ["build_dataset"]  # pas de prefill


