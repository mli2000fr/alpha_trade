import run_execution


def test_run_execution_importable():
    assert hasattr(run_execution, "__doc__")


def test_build_parser_defaults_to_overnight_cash_swing_inputs() -> None:
    parser = run_execution.build_parser()

    args = parser.parse_args(["paper"])

    assert args.account_type == "cash"
    assert args.pdt_rule == "off"
    assert args.swing_only is True
    assert args.submission_window is None


