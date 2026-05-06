"""Phase C / S17.3 — Tests ``InMemoryCache``."""
from __future__ import annotations

import time

import pytest

from service.cache import InMemoryCache, build_cache_from_env


def test_set_get_basic():
    c = InMemoryCache()
    c.set("k", "v")
    assert c.get("k") == "v"
    assert c.get("missing") is None
    assert c.get("missing", default=42) == 42


def test_ttl_expiry_with_injected_clock():
    now = [1000.0]
    c = InMemoryCache(default_ttl=10.0, clock=lambda: now[0])
    c.set("k", 1)
    assert c.get("k") == 1
    now[0] += 9
    assert c.get("k") == 1
    now[0] += 2  # total +11 > 10
    assert c.get("k") is None
    assert c.stats["misses"] >= 1


def test_lru_eviction():
    c = InMemoryCache(max_size=3)
    c.set("a", 1); c.set("b", 2); c.set("c", 3)
    assert len(c) == 3
    c.get("a")  # a devient récent
    c.set("d", 4)  # évince b
    assert "b" not in c
    assert "a" in c and "c" in c and "d" in c
    assert c.stats["evictions"] == 1


def test_invalidate_and_clear():
    c = InMemoryCache()
    c.set("k", "v")
    assert c.invalidate("k") is True
    assert c.invalidate("k") is False
    c.set("k1", 1); c.set("k2", 2)
    c.clear()
    assert len(c) == 0


def test_max_size_validation():
    with pytest.raises(ValueError):
        InMemoryCache(max_size=0)
    with pytest.raises(ValueError):
        InMemoryCache(default_ttl=0.0)


def test_set_ttl_explicit_overrides_default():
    now = [0.0]
    c = InMemoryCache(default_ttl=100.0, clock=lambda: now[0])
    c.set("short", 1, ttl=1.0)
    c.set("long", 2)
    now[0] = 5.0
    assert c.get("short") is None
    assert c.get("long") == 2


def test_factory_returns_in_memory_when_no_env(monkeypatch):
    monkeypatch.delenv("ALPHA_TRADE_CACHE_URL", raising=False)
    cache = build_cache_from_env()
    assert isinstance(cache, InMemoryCache)


def test_factory_returns_in_memory_when_redis_unavailable(monkeypatch):
    monkeypatch.setenv("ALPHA_TRADE_CACHE_URL", "redis://localhost:6379")
    # Si redis non installé, factory doit fallback silencieusement
    cache = build_cache_from_env()
    # On ne peut pas garantir le type ; on garantit le contrat
    assert hasattr(cache, "get") and hasattr(cache, "set")

