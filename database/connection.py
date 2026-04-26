import os
from functools import lru_cache

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_NAME = "alpha_trade"
DEFAULT_DB_USER_ENV = "LOGIN_DB"
DEFAULT_DB_PASSWORD_ENV = "PASSWORD_DB"

# Phase 2.2 — pool / TLS configurables via env (audit_database §1.4 / §3).
DB_POOL_SIZE_ENV = "DB_POOL_SIZE"
DB_MAX_OVERFLOW_ENV = "DB_MAX_OVERFLOW"
DB_POOL_RECYCLE_ENV = "DB_POOL_RECYCLE_SECONDS"
DB_SSL_CA_PATH_ENV = "DB_SSL_CA_PATH"

DEFAULT_POOL_SIZE = 2
DEFAULT_MAX_OVERFLOW = 3
DEFAULT_POOL_RECYCLE = 3600

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


def _read_int_env(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Variable d'environnement {name}='{raw}' invalide : entier attendu."
        ) from exc
    if value < minimum:
        raise RuntimeError(
            f"Variable d'environnement {name}={value} doit être ≥ {minimum}."
        )
    return value


def _read_ssl_connect_args() -> dict[str, dict[str, str]]:
    """Si ``DB_SSL_CA_PATH`` est défini, retourne ``{"ssl": {"ca": <path>}}``.

    Conformité audit_database §3 (TLS optionnel). PyMySQL accepte
    ``connect_args={"ssl": {"ca": "..."}}`` pour activer TLS sans casser
    les configurations locales (LAN dev) qui n'ont pas de CA.
    """
    ca_path = os.getenv(DB_SSL_CA_PATH_ENV)
    if not ca_path:
        return {}
    if not os.path.isfile(ca_path):
        raise RuntimeError(
            f"{DB_SSL_CA_PATH_ENV}='{ca_path}' : fichier introuvable."
        )
    return {"ssl": {"ca": ca_path}}


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
    *,
    url: str | None = None,
) -> Engine:
    pool_size = _read_int_env(DB_POOL_SIZE_ENV, DEFAULT_POOL_SIZE, minimum=1)
    max_overflow = _read_int_env(DB_MAX_OVERFLOW_ENV, DEFAULT_MAX_OVERFLOW, minimum=0)
    pool_recycle = _read_int_env(DB_POOL_RECYCLE_ENV, DEFAULT_POOL_RECYCLE, minimum=60)
    connect_args = _read_ssl_connect_args()
    # Phase 2.2 : ``url`` permet d'injecter un DSN custom (tests, SQLite en
    # mémoire, override d'environnement ponctuel) sans toucher aux variables
    # d'environnement de credentials.
    resolved_url = url or get_database_url(
        db_host=db_host,
        db_name=db_name,
        db_user_env=db_user_env,
        db_password_env=db_password_env,
    )
    return create_engine(
        resolved_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=pool_recycle,
        # Phase 2.2 : sizing configurable via env (DB_POOL_SIZE / DB_MAX_OVERFLOW)
        # Défauts conservateurs adaptés au modèle multi-process (ProcessPoolExecutor) :
        # chaque worker possède son propre engine via lru_cache isolé.
        # Budget max par worker = pool_size + max_overflow.
        pool_size=pool_size,
        max_overflow=max_overflow,
        connect_args=connect_args,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=get_sqlalchemy_engine())


def SessionLocal() -> Session:
    """Conserve l'API historique tout en retardant la connexion DB jusqu'au premier usage."""
    return get_session_factory()()


metadata = MetaData()
