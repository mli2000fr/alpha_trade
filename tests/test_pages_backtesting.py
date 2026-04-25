from ihm.pages import backtesting


def test_pages_backtesting_importable() -> None:
    assert hasattr(backtesting, "__doc__")


def test_parameter_reference_rows_include_screener_commands() -> None:
    diagnose_rows = backtesting._parameter_reference_rows("diagnose-screener")
    recommend_rows = backtesting._parameter_reference_rows("recommend-screener")

    assert any(row["Paramètre"] == "output_dir" for row in diagnose_rows)
    assert any(row["Paramètre"] == "max_scenarios" for row in diagnose_rows)
    assert any(row["Paramètre"] == "input_dir" for row in recommend_rows)
    assert any(row["Paramètre"] == "target_horizon" for row in recommend_rows)

