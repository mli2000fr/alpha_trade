from modelFactory import dataset

def test_dataset_importable():
    assert hasattr(dataset, "__doc__")

