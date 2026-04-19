from execution_engine import models

def test_models_importable():
    assert hasattr(models, "__doc__")

