"""Phase F / S23.3 — Factory async engine (asyncpg / aiosqlite).

POC opt-in : activé uniquement si ``ALPHA_TRADE_ASYNC_DB=1``.
DSN par défaut lu depuis ``ALPHA_TRADE_ASYNC_DSN`` ; fallback aiosqlite
in-memory pour les tests.

Pas de dépendance dure : si ``sqlalchemy[asyncio]`` ou les drivers async
ne sont pas installés, les helpers retournent ``None`` et le code appelant
doit retomber sur la version sync.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)

ENV_TOGGLE = "ALPHA_TRADE_ASYNC_DB"
ENV_DSN = "ALPHA_TRADE_ASYNC_DSN"
DEFAULT_DSN = "sqlite+aiosqlite:///:memory:"


def is_async_enabled() -> bool:
    """Vrai ssi l'opérateur a explicitement activé le POC async."""
    return os.environ.get(ENV_TOGGLE, "").strip().lower() in {"1", "true", "yes", "on"}


def make_async_engine(dsn: Optional[str] = None) -> Any | None:
    """Construit un ``AsyncEngine`` SQLAlchemy ; retourne ``None`` si indisponible.

    Le caller est responsable de gérer le ``None`` (fallback sync).
    """
    if not is_async_enabled():
        return None
    try:
        from sqlalchemy.ext.asyncio import create_async_engine  # type: ignore
    except ImportError:
        LOGGER.warning(
            "ALPHA_TRADE_ASYNC_DB=1 mais sqlalchemy[asyncio] absent — "
            "fallback sync. Installer : pip install 'sqlalchemy[asyncio]' aiosqlite"
        )
        return None

    resolved_dsn = dsn or os.environ.get(ENV_DSN, DEFAULT_DSN)
    try:
        engine = create_async_engine(resolved_dsn, future=True, pool_pre_ping=True)
    except Exception as exc:  # ImportError driver, DSN invalide…
        LOGGER.warning("AsyncEngine non créé (%s) — fallback sync", exc)
        return None
    LOGGER.info("AsyncEngine créé : %s", resolved_dsn)
    return engine

