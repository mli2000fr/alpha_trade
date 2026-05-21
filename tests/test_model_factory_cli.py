from datetime import date

import pandas as pd

from modelFactory import cli

def test_cli_importable():
    assert hasattr(cli, "__doc__")


def test_cli_parser_accepts_threshold_optimization_options() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "train",
        "--optimize-target",
        "--candidate-up-thresholds", "0.01", "0.02",
        "--candidate-down-thresholds", "-0.01", "0.0",
        "--optimize-thresholds",
        "--candidate-decision-thresholds", "0.55", "0.65",
        "--min-action-rate", "0.05",
        "--max-action-rate", "0.25",
        "--min-precision-long", "0.6",
    ])

    assert opts.optimize_target is True
    assert opts.candidate_up_thresholds == [0.01, 0.02]
    assert opts.candidate_down_thresholds == [-0.01, 0.0]
    assert opts.optimize_thresholds is True
    assert opts.candidate_decision_thresholds == [0.55, 0.65]
    assert opts.min_action_rate == 0.05
    assert opts.max_action_rate == 0.25
    assert opts.min_precision_long == 0.6


def test_cli_parser_accepts_catboost_options() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "train",
        "--enable-catboost",
        "--catboost-depth", "8",
        "--catboost-iterations", "400",
        "--catboost-learning-rate", "0.05",
    ])

    assert opts.enable_catboost is True
    assert opts.catboost_depth == 8
    assert opts.catboost_iterations == 400
    assert opts.catboost_learning_rate == 0.05


def test_cli_parser_accepts_cross_sectional_options() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "train",
        "--enable-cross-sectional",
        "--cross-sectional-min-universe", "12",
    ])

    assert opts.enable_cross_sectional is True
    assert opts.cross_sectional_min_universe == 12


def test_cli_parser_accepts_selector_universe_filter_options() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "train",
        "--include-selector-context",
        "--selector-universe-signal-modes", "strict", "sector_neutralized",
        "--selector-universe-max-candidate-rank", "25",
        "--selector-universe-exclude-earnings-blackout",
    ])

    assert opts.include_selector_context is True
    assert opts.selector_universe_signal_modes == ["strict", "sector_neutralized"]
    assert opts.selector_universe_max_candidate_rank == 25
    assert opts.selector_universe_exclude_earnings_blackout is True


def test_cli_parser_accepts_global_model_options() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "train",
        "--enable-global-model",
        "--global-model-name", "lightgbm",
        "--global-artifact-symbol", "__GLOB__",
    ])

    assert opts.enable_global_model is True
    assert opts.global_model_name == "lightgbm"
    assert opts.global_artifact_symbol == "__GLOB__"


def test_cli_parser_accepts_champion_selection_options() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "train",
        "--select-champion",
        "--default-champion", "global_model",
        "--champion-selection-metric", "business_score",
    ])

    assert opts.select_champion is True
    assert opts.default_champion == "global_model"
    assert opts.champion_selection_metric == "business_score"


def test_cli_parser_accepts_symbol_source_option() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "train",
        "--symbol-source", "stock-bars-daily",
    ])

    assert opts.symbol_source == "stock-bars-daily"


def test_cli_parser_accepts_stock_scores_all_symbol_source_option() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "train",
        "--symbol-source", "stock-scores-all",
    ])

    assert opts.symbol_source == "stock-scores-all"


def test_cli_parser_accepts_debug_train_and_watchdog_options() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "train",
        "--debug-train",
        "--heartbeat-interval-seconds", "45",
        "--watchdog-timeout-seconds", "900",
    ])

    assert opts.debug_train is True
    assert opts.heartbeat_interval_seconds == 45
    assert opts.watchdog_timeout_seconds == 900


def test_cli_parser_accepts_training_start_date() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "train",
        "--training-start-date", "2019-07-01",
    ])

    assert opts.training_start_date == date(2019, 7, 1)


def test_cli_parser_accepts_training_end_date_for_historical_predict() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "predict",
        "--training-start-date", "2019-07-01",
        "--training-end-date", "2019-08-31",
    ])

    assert opts.training_start_date == date(2019, 7, 1)
    assert opts.training_end_date == date(2019, 8, 31)


def test_cli_main_predict_historical_loops_over_available_trading_dates(monkeypatch) -> None:
    import modelFactory.db_registry as db_registry
    import modelFactory.predictor as predictor

    prediction_calls: list[tuple[date | None, date | None]] = []
    inserted_batches: list[pd.DataFrame] = []
    emitted_summaries: list[dict[str, object]] = []

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "apply_reproducibility", lambda *args, **kwargs: {"seed": 42, "deterministic_applied": True, "deterministic_requested": True})
    monkeypatch.setattr(cli, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(cli, "load_available_trading_dates", lambda engine, symbols=None, start_date=None, end_date=None: [date(2022, 1, 3), date(2022, 1, 4)])
    monkeypatch.setattr(db_registry, "load_symbols_for_source", lambda engine, source: ["AAPL", "MSFT"])
    monkeypatch.setattr(db_registry, "filter_symbols_by_selector_context", lambda engine, symbols, **kwargs: (symbols, {"enabled": False, "applied": False}))
    monkeypatch.setattr(db_registry, "insert_predictions", lambda engine, preds: inserted_batches.append(preds.copy()) or len(preds))
    monkeypatch.setattr(
        predictor,
        "predict_batch",
        lambda symbols, artifacts_dir, engine, prediction_date=None, as_of_date=None, persist=False, accelerator="auto": prediction_calls.append((prediction_date, as_of_date)) or pd.DataFrame([
            {
                "symbol": symbols[0],
                "prediction_date": prediction_date,
                "predicted_proba": 0.7,
                "predicted_class": 1,
                "run_id": f"run-{prediction_date}",
            }
        ]),
    )
    monkeypatch.setattr(cli, "_emit_run_summary", lambda summary: emitted_summaries.append(summary))

    cli.main([
        "--mode", "predict",
        "--symbol-source", "candidates",
        "--training-start-date", "2022-01-01",
        "--training-end-date", "2022-01-04",
    ])

    assert prediction_calls == [
        (date(2022, 1, 3), date(2022, 1, 3)),
        (date(2022, 1, 4), date(2022, 1, 4)),
    ]
    assert len(inserted_batches) == 1
    inserted = inserted_batches[0]
    assert list(inserted["prediction_date"]) == [date(2022, 1, 3), date(2022, 1, 4)]
    assert emitted_summaries[-1]["historical_prediction_range_enabled"] is True
    assert emitted_summaries[-1]["training_end_date"] == "2022-01-04"


def test_cli_parser_accepts_seed_and_no_deterministic() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "train",
        "--seed", "123",
        "--no-deterministic",
    ])

    assert opts.seed == 123
    assert opts.deterministic is False


