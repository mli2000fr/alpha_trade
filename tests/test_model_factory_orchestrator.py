import json
from datetime import date

from modelFactory import orchestrator
from modelFactory.config import ChampionSelectionConfig, DataConfig, ModelConfig, TrainingConfig
from modelFactory.features import build_feature_contract


def test_orchestrator_importable():
    assert hasattr(orchestrator, "__doc__")


def test_run_training_batch_loads_stock_bars_daily_symbols_when_requested(monkeypatch, tmp_path) -> None:
    cfg = TrainingConfig(
        data=DataConfig(),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )

    monkeypatch.setattr(orchestrator, "load_stock_bars_daily_symbols", lambda engine: ["AAPL", "MSFT"])
    monkeypatch.setattr(orchestrator, "load_candidate_symbols", lambda engine: [])
    monkeypatch.setattr(
        orchestrator,
        "_train_worker",
        lambda symbol, cfg: orchestrator.TrainResult(symbol, f"run-{symbol}", "completed"),
    )

    results = orchestrator.run_training_batch(cfg, engine=object(), symbols=None, symbol_source="stock-bars-daily")

    assert [result.symbol for result in results] == ["AAPL", "MSFT"]


def test_run_training_batch_applies_selector_universe_filter(monkeypatch, tmp_path) -> None:
    cfg = TrainingConfig(
        data=DataConfig(
            selector_universe_signal_modes=("strict",),
            selector_universe_max_candidate_rank=10,
            selector_universe_exclude_earnings_blackout=True,
        ),
        model=ModelConfig(max_epochs=1),
        artifacts_dir=tmp_path,
        max_workers=1,
        accelerator="cpu",
    )

    monkeypatch.setattr(orchestrator, "load_candidate_symbols", lambda engine: ["AAPL", "MSFT", "NVDA"])
    monkeypatch.setattr(
        orchestrator,
        "filter_symbols_by_selector_context",
        lambda engine, symbols, **kwargs: (["AAPL"], {"enabled": True, "applied": True, "input_symbol_count": 3, "output_symbol_count": 1, "reason": "selector_context_filtered"}),
    )
    monkeypatch.setattr(
        orchestrator,
        "_train_worker",
        lambda symbol, cfg: orchestrator.TrainResult(symbol, f"run-{symbol}", "completed"),
    )

    results = orchestrator.run_training_batch(cfg, engine=object(), symbols=None)

    assert [result.symbol for result in results] == ["AAPL"]


def test_train_worker_loads_universe_when_cross_sectional_enabled(monkeypatch) -> None:
    cfg = TrainingConfig(
        data=DataConfig(enable_cross_sectional_features=True, benchmark_symbol="SPY"),
        model=ModelConfig(max_epochs=1),
        accelerator="cpu",
    )
    captured: dict[str, object] = {}

    import database.connection as db_connection

    monkeypatch.setattr(db_connection, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(orchestrator, "load_symbol_latest_bar_date", lambda engine, symbol: date(2026, 4, 17))
    monkeypatch.setattr(orchestrator, "load_symbol_bars", lambda engine, symbol, end_date=None, start_date=None: {"symbol": symbol, "start_date": start_date, "end_date": end_date})
    monkeypatch.setattr(orchestrator, "load_benchmark_bars", lambda engine, benchmark_symbol, end_date=None, start_date=None: "benchmark")
    monkeypatch.setattr(orchestrator, "load_symbol_sentiment", lambda engine, symbol, end_date=None, start_date=None: "sentiment")
    monkeypatch.setattr(orchestrator, "load_universe_bars", lambda engine, symbols, end_date=None, start_date=None: {"symbols": list(symbols), "start_date": start_date, "end_date": end_date})

    def fake_train_symbol(symbol, bars, cfg, engine, sentiment_df=None, benchmark_df=None, universe_df=None, selector_df=None):
        captured["symbol"] = symbol
        captured["universe_df"] = universe_df
        return orchestrator.TrainResult(symbol, "run-1", "completed")

    monkeypatch.setattr(orchestrator, "train_symbol", fake_train_symbol)

    result = orchestrator._train_worker("AAPL", cfg, universe_symbols=["AAPL", "MSFT"])

    assert result.status == "completed"
    assert captured["symbol"] == "AAPL"
    assert captured["universe_df"]["symbols"] == ["AAPL", "MSFT"]
    assert captured["universe_df"]["end_date"] == date(2026, 4, 17)
    assert captured["universe_df"]["start_date"] == date(2020, 1, 1)


def test_train_worker_loads_selector_context_when_enabled(monkeypatch) -> None:
    cfg = TrainingConfig(
        data=DataConfig(include_selector_context_features=True),
        model=ModelConfig(max_epochs=1),
        accelerator="cpu",
    )
    captured: dict[str, object] = {}

    import database.connection as db_connection

    monkeypatch.setattr(db_connection, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(orchestrator, "load_symbol_latest_bar_date", lambda engine, symbol: date(2026, 4, 17))
    monkeypatch.setattr(orchestrator, "load_symbol_bars", lambda engine, symbol, end_date=None, start_date=None: {"symbol": symbol})
    monkeypatch.setattr(orchestrator, "load_symbol_selector_context", lambda engine, symbol, end_date=None, start_date=None: {"symbol": symbol, "end_date": end_date, "start_date": start_date})

    def fake_train_symbol(symbol, bars, cfg, engine, sentiment_df=None, benchmark_df=None, universe_df=None, selector_df=None):
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
    assert governance_call["selected_model"] == "global_model"
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

    assert config_data["artifact_routes"]["selected_model"] == "global_model"
    assert metrics["champion"]["model_name"] == "global_model"


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
        lambda engine, symbols: {"AAPL": date(2026, 4, 17), "MSFT": date(2026, 4, 17)},
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
        lambda engine, symbols: {"AAPL": date(2026, 4, 17)},
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
        lambda engine, symbols: {"AAPL": date(2026, 4, 17)},
    )

    kept = orchestrator._filter_symbols_by_mode(object(), ["AAPL"], mode="refresh-stale", cfg=cfg)

    assert kept == ["AAPL"]


