from modelFactory import __main__

def test_main_importable():
    assert hasattr(__main__, "__doc__")

