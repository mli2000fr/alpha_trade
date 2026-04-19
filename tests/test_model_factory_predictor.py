from modelFactory import predictor

def test_predictor_importable():
    assert hasattr(predictor, "__doc__")

