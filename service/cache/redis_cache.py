"""Phase C / S17.3 — Adaptateur Redis opt-in pour le cache.

Sélectionné uniquement si la dépendance ``redis`` est installée et
si une URL est fournie. En CI sans Redis, on retombe sur
``InMemoryCache`` via :func:`service.cache.factory.build_cache_from_env`.
"""
from __future__ import annotations

import json
from typing import Any


class RedisCache:
    """Wrapper minimal autour d'un ``redis.Redis`` pour le contrat cache.

    Sérialisation JSON par défaut (suffisant pour quotes/fundamentals).
    Pour d'autres types, fournir ``serialize/deserialize`` à
    l'instanciation.
    """

    def __init__(
        self,
        url: str,
        *,
        namespace: str = "alpha_trade",
        default_ttl: float | None = None,
        serialize=json.dumps,
        deserialize=json.loads,
    ) -> None:
        try:
            import redis  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - import opt
            raise RuntimeError(
                "Le paquet 'redis' n'est pas installé. "
                "Installez-le via 'pip install redis>=5'."
            ) from exc
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._ns = namespace
        self._default_ttl = default_ttl
        self._serialize = serialize
        self._deserialize = deserialize

    def _k(self, key: str) -> str:
        return f"{self._ns}:{key}"

    def get(self, key: str, default: Any = None) -> Any:
        raw = self._client.get(self._k(key))
        if raw is None:
            return default
        try:
            return self._deserialize(raw)
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: Any, ttl: float | None = ...) -> None:  # type: ignore[assignment]
        if ttl is ...:
            ttl = self._default_ttl
        payload = self._serialize(value)
        if ttl is None:
            self._client.set(self._k(key), payload)
        else:
            self._client.setex(self._k(key), int(ttl), payload)

    def invalidate(self, key: str) -> bool:
        return bool(self._client.delete(self._k(key)))

    def clear(self) -> None:
        # supprime uniquement les clés du namespace
        for k in self._client.scan_iter(match=f"{self._ns}:*"):
            self._client.delete(k)

