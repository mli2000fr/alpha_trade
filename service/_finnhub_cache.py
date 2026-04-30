"""Cache disque TTL pour les profils Finnhub.

Phase 2.3 du refactor (`prompt/refactor/plan.md`, audit_service §3 cache).

Le profil société Finnhub (secteur, market cap, exchange...) change
rarement : un cache de 7 jours réduit drastiquement les appels API et
contourne le rate-limit free tier (60 req/min).

Stockage simple : un fichier JSON par symbole sous
``artifacts/finnhub_cache/<SYMBOL>.json`` avec un timestamp UTC.

Cette implémentation est volontairement minimaliste (pas de
``diskcache`` ni de SQLite) pour rester sans dépendance et facile à
auditer (un humain peut ouvrir/supprimer un fichier à la main).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

LOGGER = logging.getLogger(__name__)

DEFAULT_CACHE_TTL_DAYS: int = 7
_DEFAULT_CACHE_ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "finnhub_cache"


def _cache_root() -> Path:
    """Racine du cache, surchargeable via ``FINNHUB_CACHE_DIR``."""
    override = os.getenv("FINNHUB_CACHE_DIR")
    root = Path(override) if override else _DEFAULT_CACHE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def _cache_path(symbol: str) -> Path:
    safe = "".join(ch for ch in symbol.strip().upper() if ch.isalnum() or ch in "._-")
    if not safe:
        raise ValueError("symbol invalide pour cache Finnhub.")
    return _cache_root() / f"{safe}.json"


def get_cached_profile(
    symbol: str, *, ttl_days: int = DEFAULT_CACHE_TTL_DAYS
) -> dict[str, Any] | None:
    """Retourne le profil en cache si frais (< ``ttl_days``), sinon ``None``."""
    path = _cache_path(symbol)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        LOGGER.debug("Cache Finnhub corrompu pour %s, ignoré.", symbol)
        return None
    cached_at_raw = payload.get("_cached_at")
    if not isinstance(cached_at_raw, str):
        return None
    try:
        cached_at = datetime.fromisoformat(cached_at_raw)
    except ValueError:
        return None
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - cached_at > timedelta(days=ttl_days):
        return None
    profile = payload.get("profile")
    return profile if isinstance(profile, dict) else None


def store_profile(symbol: str, profile: Mapping[str, Any]) -> None:
    """Persiste le profil pour ``symbol`` (timestamp UTC inclus)."""
    path = _cache_path(symbol)
    payload = {
        "_cached_at": datetime.now(timezone.utc).isoformat(),
        "profile": dict(profile),
    }
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
    except OSError as exc:
        LOGGER.warning("Impossible d'écrire le cache Finnhub pour %s : %s", symbol, exc)


def invalidate(symbol: str) -> None:
    """Supprime l'entrée cache pour un symbole (no-op si absent)."""
    try:
        _cache_path(symbol).unlink(missing_ok=True)
    except OSError:  # pragma: no cover
        pass


__all__ = [
    "DEFAULT_CACHE_TTL_DAYS",
    "get_cached_profile",
    "invalidate",
    "store_profile",
]

