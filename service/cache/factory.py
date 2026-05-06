"""Phase C / S17.3 — Factory cache (env-based)."""
from __future__ import annotations

import os

from service.cache.in_memory import InMemoryCache


def build_cache_from_env(
    *,
    env_var: str = "ALPHA_TRADE_CACHE_URL",
    namespace: str = "alpha_trade",
    max_size: int = 4096,
    default_ttl: float | None = 300.0,
):
    """Retourne un cache compatible avec le contrat ``get/set/invalidate``.

    - Si ``ALPHA_TRADE_CACHE_URL`` commence par ``redis://`` ou
      ``rediss://`` **et** que ``redis`` est importable, retourne
      ``RedisCache``.
    - Sinon, retourne ``InMemoryCache`` (défaut sans infra).
    """
    url = os.getenv(env_var, "").strip()
    if url.startswith(("redis://", "rediss://")):
        try:
            from service.cache.redis_cache import RedisCache
            return RedisCache(url, namespace=namespace, default_ttl=default_ttl)
        except RuntimeError:
            # redis non installé → fallback silencieux
            pass
    return InMemoryCache(max_size=max_size, default_ttl=default_ttl)

