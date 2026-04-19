from modelFactory import model

def test_model_importable():
    assert hasattr(model, "__doc__")

