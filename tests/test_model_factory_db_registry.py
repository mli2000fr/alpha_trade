from modelFactory import db_registry

def test_db_registry_importable():
    assert hasattr(db_registry, "__doc__")

