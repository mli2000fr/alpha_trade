"""Phase C / S17.3 — Couche cache pluggable.

Interface ``QuoteCache`` / ``FundamentalsCache`` partagée. Implémentation
``InMemoryCache`` LRU+TTL utilisée par défaut (testable, pas d'infra) et
adaptateur ``RedisCache`` opt-in si ``redis`` installé et
``ALPHA_TRADE_CACHE_URL`` défini.

Voir ``service.cache.factory.build_cache_from_env``.
"""
from service.cache.in_memory import InMemoryCache  # noqa: F401
from service.cache.factory import build_cache_from_env  # noqa: F401

__all__ = ["InMemoryCache", "build_cache_from_env"]

