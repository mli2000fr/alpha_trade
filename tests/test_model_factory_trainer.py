from modelFactory import trainer

def test_trainer_importable():
    assert hasattr(trainer, "__doc__")

