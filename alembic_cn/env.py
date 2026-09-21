from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool, text

from alembic import context

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.router import build_database_url  # noqa: E402

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", build_database_url("cn_primary", "CN_A"))
target_metadata = None


def _assert_cn_database(connection) -> None:
    actual = str(connection.execute(text("SELECT DATABASE()" )).scalar() or "")
    if actual != "alpha_trade_cn":
        raise RuntimeError(f"Migration CN refusée sur le schéma {actual!r}")


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    # MySQL commite implicitement le DDL mais pas nécessairement l'INSERT dans
    # alembic_version. Un bloc Engine.begin() garantit le commit de la version
    # après une migration non transactionnelle.
    with connectable.begin() as connection:
        _assert_cn_database(connection)
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
