from datetime import date

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


