"""Phase F / S23.3 — Tests POC async DB (parité sync ↔ async).

Skipif ``aiosqlite`` ou ``sqlalchemy[asyncio]`` absents.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager

import pytest

aiosqlite = pytest.importorskip("aiosqlite")
sqlalchemy_asyncio = pytest.importorskip("sqlalchemy.ext.asyncio")

from database import async_engine, async_loaders  # noqa: E402


@contextmanager
def _async_enabled():
    prev_toggle = os.environ.get(async_engine.ENV_TOGGLE)
    prev_dsn = os.environ.get(async_engine.ENV_DSN)
    os.environ[async_engine.ENV_TOGGLE] = "1"
    os.environ[async_engine.ENV_DSN] = "sqlite+aiosqlite:///:memory:"
    try:
        yield
    finally:
        if prev_toggle is None:
            os.environ.pop(async_engine.ENV_TOGGLE, None)
        else:
            os.environ[async_engine.ENV_TOGGLE] = prev_toggle
        if prev_dsn is None:
            os.environ.pop(async_engine.ENV_DSN, None)
        else:
            os.environ[async_engine.ENV_DSN] = prev_dsn


def test_async_disabled_by_default() -> None:
    os.environ.pop(async_engine.ENV_TOGGLE, None)
    assert async_engine.is_async_enabled() is False
    assert async_engine.make_async_engine() is None


def test_async_engine_built_when_enabled() -> None:
    with _async_enabled():
        engine = async_engine.make_async_engine()
        assert engine is not None
        # Cleanup
        asyncio.get_event_loop().run_until_complete(engine.dispose())


def test_fetch_market_data_async_empty_returns_empty_list() -> None:
    with _async_enabled():
        result = asyncio.get_event_loop().run_until_complete(
            async_loaders.fetch_market_data_async(symbols=[])
        )
        assert result == []


def test_loaders_return_none_when_async_disabled() -> None:
    os.environ.pop(async_engine.ENV_TOGGLE, None)
    assert asyncio.get_event_loop().run_until_complete(
        async_loaders.fetch_scores_async("run-1")
    ) is None

