import os
from functools import lru_cache

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_NAME = "alpha_trade"
DEFAULT_DB_USER_ENV = "LOGIN_DB"
DEFAULT_DB_PASSWORD_ENV = "PASSWORD_DB"


def _read_database_credentials(
    db_user_env: str = DEFAULT_DB_USER_ENV,
    db_password_env: str = DEFAULT_DB_PASSWORD_ENV,
) -> tuple[str, str]:
    db_user = os.getenv(db_user_env)
    db_password = os.getenv(db_password_env)
    if not db_user or not db_password:
        raise RuntimeError(f"{db_user_env} ou {db_password_env} non définis dans les variables d'environnement système.")
    return db_user, db_password


@lru_cache(maxsize=1)
def get_database_url(
    db_host: str = DEFAULT_DB_HOST,
    db_name: str = DEFAULT_DB_NAME,
    db_user_env: str = DEFAULT_DB_USER_ENV,
    db_password_env: str = DEFAULT_DB_PASSWORD_ENV,
) -> str:
    db_user, db_password = _read_database_credentials(db_user_env=db_user_env, db_password_env=db_password_env)
    return f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}?charset=utf8mb4"


@lru_cache(maxsize=1)
def get_sqlalchemy_engine(
    db_host: str = DEFAULT_DB_HOST,
    db_name: str = DEFAULT_DB_NAME,
    db_user_env: str = DEFAULT_DB_USER_ENV,
    db_password_env: str = DEFAULT_DB_PASSWORD_ENV,
) -> Engine:
    return create_engine(
        get_database_url(
            db_host=db_host,
            db_name=db_name,
            db_user_env=db_user_env,
            db_password_env=db_password_env,
        ),
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=get_sqlalchemy_engine())


def SessionLocal() -> Session:
    """Conserve l'API historique tout en retardant la connexion DB jusqu'au premier usage."""
    return get_session_factory()()


metadata = MetaData()
