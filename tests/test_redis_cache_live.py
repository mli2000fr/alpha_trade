"""Sprint S21.6 — Test live Redis (testcontainers).

Skipped silencieusement si Docker / testcontainers / redis indisponibles.
"""
from __future__ import annotations

import time

import pytest

testcontainers = pytest.importorskip("testcontainers")
redis_pkg = pytest.importorskip("redis")

try:
    from testcontainers.redis import RedisContainer  # type: ignore
except Exception:  # noqa: BLE001
    pytest.skip("testcontainers[redis] non installé.", allow_module_level=True)

# Vérifie que Docker répond (sinon skip propre)
try:
    import docker  # type: ignore

    docker.from_env().ping()
except Exception:  # noqa: BLE001
    pytest.skip("Docker indisponible localement.", allow_module_level=True)

from service.cache.factory import build_cache_from_env  # noqa: E402
from service.cache.redis_cache import RedisCache  # noqa: E402

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def redis_url():
    with RedisContainer("redis:7-alpine") as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


def test_set_get_roundtrip(redis_url):
    cache = RedisCache(redis_url, namespace="alpha_trade_test")
    cache.set("foo", {"bar": 42})
    assert cache.get("foo") == {"bar": 42}
    cache.invalidate("foo")
    assert cache.get("foo") is None


def test_ttl_expiry(redis_url):
    cache = RedisCache(redis_url, namespace="alpha_trade_ttl", default_ttl=1)
    cache.set("k", "v")
    assert cache.get("k") == "v"
    time.sleep(1.5)
    assert cache.get("k") is None


def test_namespace_isolation(redis_url):
    a = RedisCache(redis_url, namespace="ns_a")
    b = RedisCache(redis_url, namespace="ns_b")
    a.set("shared", 1)
    b.set("shared", 2)
    assert a.get("shared") == 1
    assert b.get("shared") == 2
    a.clear()
    assert a.get("shared") is None
    assert b.get("shared") == 2
    b.clear()


def test_factory_builds_redis_when_url_set(redis_url, monkeypatch):
    monkeypatch.setenv("ALPHA_TRADE_CACHE_URL", redis_url)
    cache = build_cache_from_env(namespace="ns_factory")
    assert isinstance(cache, RedisCache)
    cache.set("x", 1)
    assert cache.get("x") == 1
    cache.clear()


def test_factory_falls_back_inmemory_when_no_url(monkeypatch):
    monkeypatch.delenv("ALPHA_TRADE_CACHE_URL", raising=False)
    cache = build_cache_from_env()
    assert not isinstance(cache, RedisCache)

