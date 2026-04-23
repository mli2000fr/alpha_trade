import json

from modelFactory import orchestrator
from modelFactory.config import ChampionSelectionConfig, DataConfig, ModelConfig, TrainingConfig


def test_orchestrator_importable():
    assert hasattr(orchestrator, "__doc__")


def test_train_worker_loads_universe_when_cross_sectional_enabled(monkeypatch) -> None:
    cfg = TrainingConfig(
        data=DataConfig(enable_cross_sectional_features=True, benchmark_symbol="SPY"),
        model=ModelConfig(max_epochs=1),
        accelerator="cpu",
    )
    captured: dict[str, object] = {}

    import database.connection as db_connection

    monkeypatch.setattr(db_connection, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(orchestrator, "load_symbol_bars", lambda engine, symbol: "bars")
    monkeypatch.setattr(orchestrator, "load_benchmark_bars", lambda engine, benchmark_symbol: "benchmark")
    monkeypatch.setattr(orchestrator, "load_symbol_sentiment", lambda engine, symbol: "sentiment")
    monkeypatch.setattr(orchestrator, "load_universe_bars", lambda engine, symbols: {"symbols": list(symbols)})

    def fake_train_symbol(symbol, bars, cfg, engine, sentiment_df=None, benchmark_df=None, universe_df=None):
        captured["symbol"] = symbol
        captured["universe_df"] = universe_df
        return orchestrator.TrainResult(symbol, "run-1", "completed")

    monkeypatch.setattr(orchestrator, "train_symbol", fake_train_symbol)

    result = orchestrator._train_worker("AAPL", cfg, universe_symbols=["AAPL", "MSFT"])

    assert result.status == "completed"
    assert captured["symbol"] == "AAPL"
    assert captured["universe_df"] == {"symbols": ["AAPL", "MSFT"]}


def test_run_training_batch_injects_global_model_into_symbol_artifacts(monkeypatch, tmp_path) -> None:
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

    def fake_train_worker(symbol, cfg):
        symbol_dir = tmp_path / symbol
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
        "artifact_paths": {"model_path": str(tmp_path / "__GLOBAL__" / "global_model.pkl"), "config_path": str(tmp_path / "__GLOBAL__" / "config.json"), "calibrator_path": None},
        "selection_score": 0.7,
        "by_symbol": {
            "AAPL": {"status": "completed", "model_name": "global_model", "selection_score": 0.7, "test": {"auc": 0.7}},
            "MSFT": {"status": "completed", "model_name": "global_model", "selection_score": 0.68, "test": {"auc": 0.68}},
        },
    })

    results = orchestrator.run_training_batch(cfg, engine=object(), symbols=["AAPL", "MSFT"])

    assert len(results) == 2
    with open(tmp_path / "AAPL" / "config.json", encoding="utf-8") as fh:
        config_data = json.load(fh)
    with open(tmp_path / "AAPL" / "metrics.json", encoding="utf-8") as fh:
        metrics = json.load(fh)
    assert config_data["artifact_routes"]["models"]["global_model"]["inference_backend"] == "global_tabular"
    assert metrics["challengers"]["global_model"]["model_name"] == "global_model"


def test_run_training_batch_can_auto_select_global_model(monkeypatch, tmp_path) -> None:
    cfg = TrainingConfig(
        data=DataConfig(),
        model=ModelConfig(max_epochs=1),
        global_model=TrainingConfig().global_model.__class__(enabled=True, model_name="lightgbm", artifact_symbol="__GLOBAL__"),
        champion_selection=ChampionSelectionConfig(enabled=True, allow_auto_selection=True, default_champion="lstm_attention"),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )

    def fake_train_worker(symbol, cfg):
        symbol_dir = tmp_path / symbol
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
        "artifact_paths": {"model_path": str(tmp_path / "__GLOBAL__" / "global_model.pkl"), "config_path": str(tmp_path / "__GLOBAL__" / "config.json"), "calibrator_path": None},
        "selection_score": 0.85,
        "by_symbol": {
            "AAPL": {"status": "completed", "model_name": "global_model", "selection_score": 0.85, "test": {"auc": 0.85}},
        },
    })

    orchestrator.run_training_batch(cfg, engine=object(), symbols=["AAPL"])

    with open(tmp_path / "AAPL" / "config.json", encoding="utf-8") as fh:
        config_data = json.load(fh)
    with open(tmp_path / "AAPL" / "metrics.json", encoding="utf-8") as fh:
        metrics = json.load(fh)

    assert config_data["architecture_selected"] == "global_model"
    assert config_data["artifact_routes"]["selected_model"] == "global_model"
    assert metrics["champion"]["model_name"] == "global_model"


