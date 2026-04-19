from execution_engine import db_io

def test_db_io_importable():
    assert hasattr(db_io, "__doc__")

