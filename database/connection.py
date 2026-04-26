import os
from functools import lru_cache

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_NAME = "alpha_trade"
DEFAULT_DB_USER_ENV = "LOGIN_DB"
DEFAULT_DB_PASSWORD_ENV = "PASSWORD_DB"

# Phase 1 sécurité : placeholders évidents refusés (audit_global.md §1.5).
# Volontairement permissif sur "user" / "pass" pour ne pas casser les envs
# locaux historiques ; les vrais placeholders ("changeme", "your_password",
# "todo"…) restent bloqués.
_FORBIDDEN_PLAINTEXT = frozenset({
    "changeme", "change-me", "todo", "your_password", "your_user",
    "replaceme", "replace-me", "xxxxx", "xxx", "secret123",
})


def _read_database_credentials(
    db_user_env: str = DEFAULT_DB_USER_ENV,
    db_password_env: str = DEFAULT_DB_PASSWORD_ENV,
) -> tuple[str, str]:
    db_user = os.getenv(db_user_env)
    db_password = os.getenv(db_password_env)
    if not db_user or not db_password:
        raise RuntimeError(
            f"{db_user_env} ou {db_password_env} non définis dans les variables "
            "d'environnement système."
        )
    if db_user.strip().lower() in _FORBIDDEN_PLAINTEXT or db_password.strip().lower() in _FORBIDDEN_PLAINTEXT:
        raise RuntimeError(
            f"Valeurs sentinelles refusées pour {db_user_env}/{db_password_env} : "
            "remplace 'pass' / 'user' / 'changeme' par des credentials réels."
        )
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
        # Sizing explicite pour le modèle multi-process (ProcessPoolExecutor).
        # Chaque worker subprocess possède son propre engine via lru_cache isolé.
        # Budget max = pool_size + max_overflow = 5 connexions par worker.
        pool_size=2,
        max_overflow=3,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=get_sqlalchemy_engine())


def SessionLocal() -> Session:
    """Conserve l'API historique tout en retardant la connexion DB jusqu'au premier usage."""
    return get_session_factory()()


metadata = MetaData()
