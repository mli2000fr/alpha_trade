from screener import __init__

def test_screener_init_importable():
    assert hasattr(__init__, "__doc__")

