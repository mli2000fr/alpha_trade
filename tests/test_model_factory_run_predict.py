from modelFactory import run_predict

def test_run_predict_importable():
    assert hasattr(run_predict, "__doc__")

