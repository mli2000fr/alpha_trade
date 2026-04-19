from execution_engine import config

def test_config_importable():
    assert hasattr(config, "__doc__")

