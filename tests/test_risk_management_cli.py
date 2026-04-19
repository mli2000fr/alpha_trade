from risk_management import cli

def test_cli_importable():
    assert hasattr(cli, "__doc__")

