import pytest
from database import connection

class _FakeEngine:
    def __init__(self):
        self.connected = False
    def connect(self):
        self.connected = True
        return self
    def dispose(self):
        self.connected = False

def test_get_sqlalchemy_engine_returns_engine(monkeypatch):
    monkeypatch.setattr(connection, "create_engine", lambda url, **kwargs: _FakeEngine())
    engine = connection.get_sqlalchemy_engine()
    assert isinstance(engine, _FakeEngine)
    assert not engine.connected

def test_get_sqlalchemy_engine_with_url(monkeypatch):
    monkeypatch.setattr(connection, "create_engine", lambda url, **kwargs: _FakeEngine())
    engine = connection.get_sqlalchemy_engine(url="sqlite:///:memory:")
    assert isinstance(engine, _FakeEngine)

def test_get_sqlalchemy_engine_handles_error(monkeypatch):
    monkeypatch.setattr(connection, "create_engine", lambda url, **kwargs: (_ for _ in ()).throw(RuntimeError("fail")))
    with pytest.raises(RuntimeError):
        connection.get_sqlalchemy_engine()

