from ihm import app

def test_app_importable():
    assert hasattr(app, "__doc__")

