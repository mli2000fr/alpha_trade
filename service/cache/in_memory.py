"""Phase C / S17.3 — ``InMemoryCache`` LRU + TTL.

Implémentation pure Python, thread-safe (``threading.RLock``), sans
dépendance externe. Utilisée par défaut en CI et en dev. Le contrat
``get/set/invalidate/clear`` est partagé avec ``RedisCache``.

Politique d'éviction : LRU strict une fois ``max_size`` atteint.
TTL : par-clé, indépendant ; ``ttl=None`` = pas d'expiration.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _Entry:
    value: Any
    expires_at: float | None  # epoch seconds, None = jamais


class InMemoryCache:
    """Cache LRU + TTL thread-safe.

    Parameters
    ----------
    max_size: int
        nombre maximum d'entrées avant éviction LRU.
    default_ttl: float | None
        TTL par défaut (secondes). ``None`` = pas d'expiration.
    clock: callable, optionnel
        retourne le temps courant (epoch s). Injectable pour les tests
        déterministes.
    """

    def __init__(
        self,
        max_size: int = 1024,
        default_ttl: float | None = None,
        *,
        clock=time.time,
    ) -> None:
        if max_size < 1:
            raise ValueError("max_size doit être >= 1.")
        if default_ttl is not None and default_ttl <= 0:
            raise ValueError("default_ttl doit être > 0 ou None.")
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._clock = clock
        self._data: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    # -------- API publique --------
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return default
            if entry.expires_at is not None and self._clock() >= entry.expires_at:
                # expirée
                del self._data[key]
                self._misses += 1
                return default
            # LRU : réordonne en queue (= récemment utilisée)
            self._data.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: float | None = ...) -> None:  # type: ignore[assignment]
        if ttl is ...:  # sentinel pour distinguer "pas fourni" de "None explicite"
            ttl = self._default_ttl
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl doit être > 0 ou None.")
        expires_at = (self._clock() + ttl) if ttl is not None else None
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self._data[key] = _Entry(value=value, expires_at=expires_at)
                return
            self._data[key] = _Entry(value=value, expires_at=expires_at)
            while len(self._data) > self._max_size:
                self._data.popitem(last=False)
                self._evictions += 1

    def invalidate(self, key: str) -> bool:
        with self._lock:
            return self._data.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __contains__(self, key: str) -> bool:
        return self.get(key, default=_MISS) is not _MISS

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    # -------- observabilité --------
    @property
    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "size": len(self._data),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
            }


_MISS = object()

