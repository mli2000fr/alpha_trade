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
    connection.get_database_url.cache_clear()
    connection.get_sqlalchemy_engine.cache_clear()
    monkeypatch.setattr(connection, "create_engine", lambda url, **kwargs: _FakeEngine())
    engine = connection.get_sqlalchemy_engine()
    assert isinstance(engine, _FakeEngine)
    assert not engine.connected

def test_get_sqlalchemy_engine_with_url(monkeypatch):
    connection.get_database_url.cache_clear()
    connection.get_sqlalchemy_engine.cache_clear()
    monkeypatch.setattr(connection, "create_engine", lambda url, **kwargs: _FakeEngine())
    engine = connection.get_sqlalchemy_engine(url="sqlite:///:memory:")
    assert isinstance(engine, _FakeEngine)

def test_get_sqlalchemy_engine_handles_error(monkeypatch):
    connection.get_database_url.cache_clear()
    connection.get_sqlalchemy_engine.cache_clear()
    monkeypatch.setattr(connection, "create_engine", lambda url, **kwargs: (_ for _ in ()).throw(RuntimeError("fail")))
    with pytest.raises(RuntimeError):
        connection.get_sqlalchemy_engine()


def test_get_database_url_honors_db_host_and_name_env(monkeypatch):
    connection.get_database_url.cache_clear()
    connection.get_sqlalchemy_engine.cache_clear()
    monkeypatch.setenv("DB_HOST", "mysql.internal")
    monkeypatch.setenv("DB_NAME", "alpha_trade_shadow")
    monkeypatch.setenv(connection.DEFAULT_DB_USER_ENV, "user")
    monkeypatch.setenv(connection.DEFAULT_DB_PASSWORD_ENV, "secret")

    url = connection.get_database_url()

    assert "@mysql.internal/alpha_trade_shadow?" in url


