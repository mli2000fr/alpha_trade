from modelFactory import run_train

def test_run_train_importable():
    assert hasattr(run_train, "__doc__")

