import pytest
from testcontainers.mysql import MySqlContainer
import sqlalchemy


def _docker_available() -> bool:
    try:
        import docker
        client = docker.from_env()
        client.ping()
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(not _docker_available(), reason="Docker indisponible sur cette machine")

@pytest.fixture(scope="session")
def mysql_url():
    with MySqlContainer("mysql:8.0") as mysql:
        engine = sqlalchemy.create_engine(mysql.get_connection_url())
        # Exemple : création d'une table de test
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("CREATE TABLE test_table (id INT PRIMARY KEY, val VARCHAR(50))"))
            conn.execute(sqlalchemy.text("INSERT INTO test_table (id, val) VALUES (1, 'foo'), (2, 'bar')"))
        yield mysql.get_connection_url()


def test_db_connection(mysql_url):
    engine = sqlalchemy.create_engine(mysql_url)
    with engine.connect() as conn:
        result = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM test_table"))
        count = result.scalar()
        assert count == 2


def test_insert_and_select(mysql_url):
    engine = sqlalchemy.create_engine(mysql_url)
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("INSERT INTO test_table (id, val) VALUES (3, 'baz')"))
        result = conn.execute(sqlalchemy.text("SELECT val FROM test_table WHERE id=3"))
        val = result.scalar()
        assert val == 'baz'

