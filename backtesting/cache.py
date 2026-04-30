"""
backtesting/cache.py
=====================
Phase E.1 — cache local Parquet pour OHLCV / scores / predictions.

Évite de re-télécharger depuis MySQL à chaque run.
Usage type :

    from backtesting.cache import ParquetCache

    cache = ParquetCache()
    df = cache.get_or_load("ohlcv_2020_2025_eodhd",
                           loader=lambda: load_ohlcv(engine, start, end))
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Callable

import pandas as pd

LOGGER = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("artifacts/backtesting_cache")


class ParquetCache:
    """Cache simple basé sur des fichiers Parquet."""

    def __init__(self, cache_dir: Path | str = DEFAULT_CACHE_DIR, enabled: bool = True) -> None:
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]

    def path_for(self, key: str) -> Path:
        return self.cache_dir / f"{self._hash_key(key)}_{_safe_filename(key)}.parquet"

    def get(self, key: str) -> pd.DataFrame | None:
        if not self.enabled:
            return None
        path = self.path_for(key)
        if not path.exists():
            return None
        try:
            df = pd.read_parquet(path)
            LOGGER.info("Cache HIT %s (%d lignes)", key, len(df))
            return df
        except Exception as exc:  # pragma: no cover - défensif
            LOGGER.warning("Cache illisible (%s) : %s — recompute.", path, exc)
            return None

    def put(self, key: str, df: pd.DataFrame) -> None:
        if not self.enabled or df is None or df.empty:
            return
        path = self.path_for(key)
        try:
            df.to_parquet(path, index=True)
            LOGGER.info("Cache PUT %s (%d lignes) → %s", key, len(df), path)
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("Cache write failed (%s) : %s", path, exc)

    def get_or_load(
        self,
        key: str,
        loader: Callable[[], pd.DataFrame],
    ) -> pd.DataFrame:
        cached = self.get(key)
        if cached is not None:
            return cached
        df = loader()
        self.put(key, df)
        return df

    def invalidate(self, key: str | None = None) -> int:
        """Supprime un cache ou tout le répertoire si key=None."""
        if not self.enabled:
            return 0
        removed = 0
        if key is None:
            for path in self.cache_dir.glob("*.parquet"):
                path.unlink(missing_ok=True)
                removed += 1
        else:
            path = self.path_for(key)
            if path.exists():
                path.unlink()
                removed = 1
        LOGGER.info("Cache invalidated : %d entrée(s)", removed)
        return removed


def _safe_filename(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in s)[:64]


__all__ = ["ParquetCache", "DEFAULT_CACHE_DIR"]

