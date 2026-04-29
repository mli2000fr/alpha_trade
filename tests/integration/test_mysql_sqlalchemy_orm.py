import pytest
from testcontainers.mysql import MySqlContainer
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, Session


def _docker_available() -> bool:
    try:
        import docker
        client = docker.from_env()
        client.ping()
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(not _docker_available(), reason="Docker indisponible sur cette machine")

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)

@pytest.fixture(scope="session")
def mysql_url():
    with MySqlContainer("mysql:8.0") as mysql:
        engine = create_engine(mysql.get_connection_url())
        Base.metadata.create_all(engine)
        yield mysql.get_connection_url()


def test_orm_insert_and_query(mysql_url):
    engine = create_engine(mysql_url)
    with Session(engine) as session:
        user = User(id=1, name="Alice")
        session.add(user)
        session.commit()

        result = session.query(User).filter_by(name="Alice").first()
        assert result is not None
        assert result.id == 1
        assert result.name == "Alice"


def test_orm_update(mysql_url):
    engine = create_engine(mysql_url)
    with Session(engine) as session:
        user = session.query(User).filter_by(id=1).first()
        user.name = "Bob"
        session.commit()

        result = session.query(User).filter_by(id=1).first()
        assert result.name == "Bob"

