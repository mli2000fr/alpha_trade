from datetime import date
import json

import pandas as pd
import pytest

from modelFactory import cli


def test_publish_tradable_universe_cli_accepts_a_complete_date_range(monkeypatch) -> None:
    from common import publish_tradable_universe

    published_dates: list[date] = []
    monkeypatch.setattr(publish_tradable_universe, "nyse_session_dates", lambda start, end: [start, end])
    monkeypatch.setattr(publish_tradable_universe, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(
        publish_tradable_universe,
        "publish_full_tradable_universe",
        lambda _engine, *, snapshot_date, capital_preset_key: published_dates.append(snapshot_date) or f"run-{snapshot_date}",
    )

    assert publish_tradable_universe.main(["--start-date", "2024-01-02", "--end-date", "2024-01-03"]) == 0
    assert published_dates == [date(2024, 1, 2), date(2024, 1, 3)]


def test_publish_tradable_universe_cli_reports_missing_screener_snapshots(monkeypatch, capsys) -> None:
    from common import publish_tradable_universe

    monkeypatch.setattr(publish_tradable_universe, "nyse_session_dates", lambda start, end: [start, end])
    monkeypatch.setattr(publish_tradable_universe, "get_sqlalchemy_engine", lambda: object())

    def _raise_for_first_day(_engine, *, snapshot_date, capital_preset_key):
        if snapshot_date == date(2024, 1, 2):
            raise RuntimeError("Aucun snapshot screener complet exact pour preset=small date=2024-01-02.")
        return "run-2024-01-03"

    monkeypatch.setattr(publish_tradable_universe, "publish_full_tradable_universe", _raise_for_first_day)

    assert publish_tradable_universe.main(["--start-date", "2024-01-02", "--end-date", "2024-01-03"]) == 2
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "incomplete_missing_screener_snapshots"
    assert output["missing_screener_snapshot_dates"] == ["2024-01-02"]

def test_cli_importable():
    assert hasattr(cli, "__doc__")


def test_cli_parser_accepts_stock_bars_daily_symbol_source() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args(["--mode", "train", "--symbol-source", "stock-bars-daily"])

    assert opts.symbol_source == "stock-bars-daily"


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


def test_cli_parser_rejects_selector_universe_filter_options() -> None:
    parser = cli.build_arg_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "train", "--selector-universe-signal-modes", "strict"])


def test_cli_parser_accepts_score_context_option_and_legacy_alias() -> None:
    parser = cli.build_arg_parser()

    assert parser.parse_args(["--mode", "train", "--include-screener-scores"]).include_screener_scores is True
    assert parser.parse_args(["--mode", "train", "--include-selector-context"]).include_screener_scores is True


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
    ])

    assert opts.select_champion is True
    assert opts.default_champion == "global_model"


def test_cli_parser_defaults_to_tradable_universe_and_rejects_legacy_source() -> None:
    parser = cli.build_arg_parser()

    assert parser.parse_args(["--mode", "train"]).symbol_source == "tradable-universe"
    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "train", "--symbol-source", "candidates"])


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
    monkeypatch.setattr(
        db_registry,
        "load_symbols_for_source",
        lambda engine, source, *, trade_date: ["AAPL", "MSFT"],
    )
    monkeypatch.setattr(db_registry, "insert_predictions", lambda engine, preds: inserted_batches.append(preds.copy()) or len(preds))
    monkeypatch.setattr(
        predictor,
        "predict_batch",
        lambda symbols, artifacts_dir, engine, prediction_date=None, as_of_date=None, persist=False, accelerator="auto", max_workers=1: prediction_calls.append((prediction_date, as_of_date)) or pd.DataFrame([
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
        "--training-start-date", "2022-01-01",
        "--training-end-date", "2022-01-04",
    ])

    assert prediction_calls == [
        (date(2022, 1, 3), date(2022, 1, 3)),
        (date(2022, 1, 4), date(2022, 1, 4)),
    ]
    assert len(inserted_batches) == 2
    assert list(inserted_batches[0]["prediction_date"]) == [date(2022, 1, 3)]
    assert list(inserted_batches[1]["prediction_date"]) == [date(2022, 1, 4)]
    assert emitted_summaries[-1]["historical_prediction_range_enabled"] is True
    assert emitted_summaries[-1]["training_end_date"] == "2022-01-04"


def test_cli_main_predict_historical_resolves_pit_universe_per_date(monkeypatch) -> None:
    import modelFactory.db_registry as db_registry
    import modelFactory.predictor as predictor

    prediction_calls: list[tuple[tuple[str, ...], date | None, date | None]] = []
    inserted_batches: list[pd.DataFrame] = []

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "apply_reproducibility", lambda *args, **kwargs: {"seed": 42, "deterministic_applied": True, "deterministic_requested": True})
    monkeypatch.setattr(cli, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(
        cli,
        "load_available_trading_dates",
        lambda engine, **kwargs: [date(2022, 1, 3), date(2022, 1, 4)],
    )
    symbols_by_date = {
        date(2022, 1, 3): ["AAPL", "MSFT"],
        date(2022, 1, 4): ["MSFT"],
    }
    monkeypatch.setattr(
        db_registry,
        "load_symbols_for_source",
        lambda engine, source, *, trade_date: symbols_by_date[trade_date],
    )
    monkeypatch.setattr(db_registry, "insert_predictions", lambda engine, preds: inserted_batches.append(preds.copy()) or len(preds))
    monkeypatch.setattr(
        predictor,
        "predict_batch",
        lambda symbols, artifacts_dir, engine, prediction_date=None, as_of_date=None, persist=False, accelerator="auto", max_workers=1: prediction_calls.append((tuple(symbols), prediction_date, as_of_date)) or pd.DataFrame([
            {
                "symbol": symbol,
                "prediction_date": prediction_date,
                "predicted_proba": 0.7,
                "predicted_class": 1,
                "run_id": f"run-{prediction_date}",
            }
            for symbol in symbols
        ]),
    )
    monkeypatch.setattr(cli, "_emit_run_summary", lambda summary: None)

    cli.main([
        "--mode", "predict",
        "--training-start-date", "2022-01-01",
        "--training-end-date", "2022-01-04",
    ])

    assert prediction_calls == [
        (("AAPL", "MSFT"), date(2022, 1, 3), date(2022, 1, 3)),
        (("MSFT",), date(2022, 1, 4), date(2022, 1, 4)),
    ]
    assert len(inserted_batches) == 2
    assert list(inserted_batches[0]["symbol"]) == ["AAPL", "MSFT"]
    assert list(inserted_batches[1]["symbol"]) == ["MSFT"]


def test_load_historical_prediction_scopes_from_scores_history_groups_symbols_by_snapshot_date(monkeypatch) -> None:
    from modelFactory import data_loader

    captured: dict[str, object] = {}

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            captured["sql"] = str(query)
            captured["params"] = dict(params)

            class _Result:
                def mappings(self_inner):
                    class _Mappings:
                        def all(self_mappings):
                            return [
                                {"snapshot_date": date(2022, 1, 3), "symbol": "AAPL"},
                                {"snapshot_date": date(2022, 1, 3), "symbol": "MSFT"},
                                {"snapshot_date": date(2022, 1, 4), "symbol": "MSFT"},
                            ]

                    return _Mappings()

            return _Result()

    class FakeEngine:
        def connect(self):
            return FakeConn()

    monkeypatch.setattr(
        data_loader,
        "_get_table_columns",
        lambda engine, table_name: {"snapshot_date", "symbol", "selector_signal_mode", "selection_rank", "earnings_blackout"},
    )

    scopes = data_loader.load_historical_prediction_scopes_from_scores_history(
        FakeEngine(),  # type: ignore[arg-type]
        start_date=date(2022, 1, 1),
        end_date=date(2022, 1, 4),
        signal_modes=("strict",),
        max_selection_rank=20,
        exclude_earnings_blackout=True,
    )

    assert scopes == {
        date(2022, 1, 3): ["AAPL", "MSFT"],
        date(2022, 1, 4): ["MSFT"],
    }
    assert "FROM stock_scores_history" in captured["sql"]
    assert "snapshot_date BETWEEN :start_date AND :end_date" in captured["sql"]
    assert "selection_rank <= :max_selection_rank" in captured["sql"]
    assert "COALESCE(earnings_blackout, 0) = 0" in captured["sql"]
    assert captured["params"]["max_selection_rank"] == 20
    assert captured["params"]["signal_mode_0"] == "strict"


def test_cli_parser_accepts_seed_and_no_deterministic() -> None:
    parser = cli.build_arg_parser()

    opts = parser.parse_args([
        "--mode", "train",
        "--seed", "123",
        "--no-deterministic",
    ])

    assert opts.seed == 123
    assert opts.deterministic is False


def test_cli_train_persists_one_batch_record_with_command_and_final_counts(monkeypatch, tmp_path) -> None:
    from modelFactory import db_registry, orchestrator

    inserted_batches: list[dict[str, object]] = []
    updated_batches: list[dict[str, object]] = []
    emitted_summaries: list[dict[str, object]] = []

    monkeypatch.setattr(cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "apply_reproducibility", lambda *args, **kwargs: {"seed": 42, "deterministic_applied": True, "deterministic_requested": True})
    monkeypatch.setattr(cli, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(cli, "_emit_run_summary", lambda summary: emitted_summaries.append(summary))
    monkeypatch.setattr(
        db_registry,
        "insert_training_batch",
        lambda engine, **kwargs: inserted_batches.append(kwargs),
    )
    monkeypatch.setattr(
        db_registry,
        "update_training_batch",
        lambda engine, batch_id, **kwargs: updated_batches.append({"batch_id": batch_id, **kwargs}),
    )
    monkeypatch.setattr(
        orchestrator,
        "run_training_batch",
        lambda *args, **kwargs: [
            orchestrator.TrainResult("AAPL", "run-aapl", "completed"),
            orchestrator.TrainResult("MSFT", "run-msft", "skipped"),
        ],
    )

    cli.main([
        "--mode", "train",
        "--symbols", "AAPL", "MSFT",
        "--artifacts-dir", str(tmp_path),
        "--feature-set", "expert",
    ])

    assert len(inserted_batches) == 1
    batch = inserted_batches[0]
    assert batch["command_line"].endswith("--feature-set expert")
    assert json.loads(str(batch["command_argv_json"])) == [
        "--mode", "train", "--symbols", "AAPL", "MSFT", "--artifacts-dir", str(tmp_path), "--feature-set", "expert",
    ]
    metadata = json.loads(str(batch["metadata_json"]))
    assert "regime_bull_market" in metadata["feature_columns"]
    assert len(updated_batches) == 1
    assert updated_batches[0]["batch_id"] == batch["batch_id"]
    assert updated_batches[0]["status"] == "completed"
    assert updated_batches[0]["symbols_completed"] == 1
    assert updated_batches[0]["symbols_skipped"] == 1
    assert emitted_summaries[-1]["symbols_completed"] == 1


