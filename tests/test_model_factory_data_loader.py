from modelFactory import data_loader

def test_data_loader_importable():
    assert hasattr(data_loader, "__doc__")

