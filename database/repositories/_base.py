"""Base class commune aux repositories ``database/repositories``.

Phase 2.2 du refactor (`prompt/refactor/plan.md`).
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.engine import Connection, Engine

from database.connection import get_sqlalchemy_engine


class Repository:
    """Base class fournissant un engine SQLAlchemy paresseux + helper de transaction.

    Les sous-classes peuvent :
    - injecter un engine custom au constructeur (utile pour les tests
      avec `testcontainers[mysql]` ou un engine SQLite en mémoire) ;
    - utiliser :meth:`transaction` pour ouvrir un bloc atomique.
    """

    def __init__(self, *, engine: Engine | None = None) -> None:
        self._engine: Engine | None = engine

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = get_sqlalchemy_engine()
        return self._engine

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """Ouvre une transaction (commit auto à la sortie, rollback sur exception)."""
        with self.engine.begin() as conn:
            yield conn

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        """Ouvre une connexion en lecture (sans transaction explicite)."""
        with self.engine.connect() as conn:
            yield conn

