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


