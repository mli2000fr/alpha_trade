from ihm.pages import __init__

def test_pages_init_importable():
    assert hasattr(__init__, "__doc__")

