from modelFactory import cli

def test_cli_importable():
    assert hasattr(cli, "__doc__")

