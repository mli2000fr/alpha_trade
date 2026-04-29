"""Cache disque pour les payloads EODHD à TTL.

Plan §5.4 : ``cached_fetch_splits`` avec TTL **7 jours**.

Stockage simple JSON sous ``artifacts/eodhd_cache/<namespace>/<key>.json``.
Le namespace permet de cloisonner ``splits/``, ``dividends/``, ``eod/`` etc.
Aucune dépendance externe — utilise stdlib uniquement.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

LOGGER = logging.getLogger(__name__)

DEFAULT_CACHE_ROOT = Path("artifacts") / "eodhd_cache"
DEFAULT_TTL_SPLITS_SECONDS = 7 * 24 * 3600
DEFAULT_TTL_DIVIDENDS_SECONDS = 7 * 24 * 3600
DEFAULT_TTL_EOD_SECONDS = 24 * 3600


@dataclass(frozen=True, slots=True)
class CacheEntry:
    payload: Any
    saved_at_epoch: float

    @property
    def age_seconds(self) -> float:
        return max(0.0, time.time() - self.saved_at_epoch)

    def is_fresh(self, ttl_seconds: float) -> bool:
        return self.age_seconds <= ttl_seconds


class EodhdDiskCache:
    """Cache disque minimaliste, thread-safe niveau filesystem."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root is not None else DEFAULT_CACHE_ROOT

    # ------------------------------------------------------------------
    @staticmethod
    def _safe_key(key: str) -> str:
        # Sanitize : on ne fait pas confiance au caller (peut contenir / : etc.)
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        slug = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in key)
        return f"{slug[:48]}_{digest}.json"

    def _path(self, namespace: str, key: str) -> Path:
        return self.root / namespace / self._safe_key(key)

    # ------------------------------------------------------------------
    def get(self, namespace: str, key: str, *, ttl_seconds: float) -> Optional[Any]:
        path = self._path(namespace, key)
        if not path.exists():
            return None
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            LOGGER.warning("[eodhd-cache] read error %s: %s", path, exc)
            return None
        entry = CacheEntry(payload=blob.get("payload"), saved_at_epoch=float(blob.get("saved_at_epoch", 0.0)))
        if not entry.is_fresh(ttl_seconds):
            return None
        return entry.payload

    def set(self, namespace: str, key: str, payload: Any) -> None:
        path = self._path(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(
                json.dumps({"saved_at_epoch": time.time(), "payload": payload}, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            LOGGER.warning("[eodhd-cache] write error %s: %s", path, exc)

    def get_or_fetch(
        self,
        namespace: str,
        key: str,
        loader: Callable[[], Any],
        *,
        ttl_seconds: float,
    ) -> Any:
        cached = self.get(namespace, key, ttl_seconds=ttl_seconds)
        if cached is not None:
            return cached
        payload = loader()
        if payload is not None:
            self.set(namespace, key, payload)
        return payload

    def invalidate(self, namespace: Optional[str] = None) -> int:
        """Supprime un namespace entier ou tout le cache. Retourne le nb supprimé."""
        target = self.root / namespace if namespace else self.root
        if not target.exists():
            return 0
        count = 0
        for path in target.rglob("*.json"):
            try:
                path.unlink()
                count += 1
            except OSError:
                pass
        return count


__all__ = [
    "DEFAULT_CACHE_ROOT",
    "DEFAULT_TTL_DIVIDENDS_SECONDS",
    "DEFAULT_TTL_EOD_SECONDS",
    "DEFAULT_TTL_SPLITS_SECONDS",
    "CacheEntry",
    "EodhdDiskCache",
]

