from ihm.services import db

def test_services_db_importable():
    assert hasattr(db, "__doc__")

