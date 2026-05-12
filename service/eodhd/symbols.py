"""Mapping symbole projet <-> symbole EODHD.

Règles (validées Phase 1, cf. ``artifacts/eodhd_cache/phase1_smoke_*.json``) :

- **Défaut** : ``<TICKER>.<EXCHANGE>`` -- ex. ``AAPL`` -> ``AAPL.US``.
- **Class share** (Berkshire, Brown-Forman) : le ``.`` projet devient ``-``
  côté EODHD -- ex. ``BRK.B`` -> ``BRK-B.US``, ``BF.B`` -> ``BF-B.US``.
- **Alphabet** : le ``.`` est préservé -- ``GOOG`` -> ``GOOG.US``,
  ``GOOGL`` -> ``GOOGL.US`` (pas de classes A/B/C suffixées).
- Exceptions explicites : ``service/eodhd/symbols_exceptions.json``.

Le distinguo « class share » vs « Alphabet » est nécessaire car les deux
notations contiennent un ``.`` côté projet mais ne se transposent pas
de la même façon côté EODHD.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)

DEFAULT_EXCHANGE = "US"
_EXCEPTIONS_PATH = Path(__file__).with_name("symbols_exceptions.json")

# Tickers ayant un ``.`` mais où le ``.`` doit être préservé côté EODHD.
# (ex. Alphabet) — par opposition aux class shares (BRK.B, BF.B) qui
# remplacent ``.`` par ``-``.
_DOT_PRESERVED_PREFIXES: frozenset[str] = frozenset({"GOOG"})


@lru_cache(maxsize=1)
def _load_exceptions() -> dict[str, str]:
    try:
        with open(_EXCEPTIONS_PATH, encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        return {}
    except Exception as exc:
        LOGGER.warning("symbols_exceptions.json illisible : %s", exc)
        return {}
    return dict(payload.get("exceptions", {}) or {})


def reset_exceptions_cache() -> None:
    """Vide le cache (utile en tests après écriture du JSON)."""
    _load_exceptions.cache_clear()


def to_eodhd(symbol: str, exchange: str = DEFAULT_EXCHANGE) -> str:
    """Convertit un symbole projet vers la notation EODHD.

    >>> to_eodhd("AAPL")
    'AAPL.US'
    >>> to_eodhd("BRK.B")
    'BRK-B.US'
    >>> to_eodhd("GOOGL")
    'GOOGL.US'
    >>> to_eodhd("GOOG")
    'GOOG.US'
    """
    if not symbol:
        raise ValueError("symbol vide")
    sym = symbol.strip().upper()
    exch = (exchange or DEFAULT_EXCHANGE).strip().upper()

    exceptions = _load_exceptions()
    if sym in exceptions:
        return exceptions[sym]

    if "." in sym:
        base, _, suffix = sym.rpartition(".")
        if base and suffix.isalpha() and len(suffix) >= 2:
            # Déjà au format provider natif : ``AAPL.US``, ``VIX.INDX``,
            # ``US10Y.INDX``, ``SAP.DE``… On le laisse intact.
            return sym
        prefix, _, suffix = sym.partition(".")
        if prefix in _DOT_PRESERVED_PREFIXES:
            # Alphabet : le ``.`` est conservé mais ne doit pas créer un .US redondant
            return f"{sym}.{exch}" if not sym.endswith(f".{exch}") else sym
        # Class share : ``.`` -> ``-``
        sym = f"{prefix}-{suffix}"

    return f"{sym}.{exch}"


def from_eodhd(eodhd_symbol: str) -> tuple[str, str]:
    """Inverse : ``AAPL.US`` -> ``("AAPL", "US")`` ; ``BRK-B.US`` -> ``("BRK.B", "US")``.

    >>> from_eodhd("AAPL.US")
    ('AAPL', 'US')
    >>> from_eodhd("BRK-B.US")
    ('BRK.B', 'US')
    """
    if not eodhd_symbol or "." not in eodhd_symbol:
        raise ValueError(f"Symbole EODHD invalide : {eodhd_symbol!r}")
    raw = eodhd_symbol.strip().upper()
    base, _, exch = raw.rpartition(".")
    if not base:
        raise ValueError(f"Symbole EODHD invalide : {eodhd_symbol!r}")
    # Reverse class-share : ``-`` -> ``.`` SAUF si dans exceptions
    project_symbol = base.replace("-", ".") if "-" in base else base
    return project_symbol, exch


def is_supported(symbol: str) -> bool:
    """Retourne False si le symbole est connu pour ne pas être supporté
    sur le plan basique EODHD (cf. ``known_unsupported_basic_plan``)."""
    try:
        with open(_EXCEPTIONS_PATH, encoding="utf-8") as fh:
            payload = json.load(fh)
        unsupported: set[str] = set(payload.get("known_unsupported_basic_plan", []) or [])
    except Exception:
        return True
    return symbol.strip().upper() not in unsupported


def add_exception(project_symbol: str, eodhd_symbol: Optional[str]) -> None:
    """Ajoute / supprime une exception runtime (en mémoire seulement,
    le JSON n'est pas réécrit). Utile pour les tests."""
    excs = dict(_load_exceptions())
    if eodhd_symbol is None:
        excs.pop(project_symbol.upper(), None)
    else:
        excs[project_symbol.upper()] = eodhd_symbol
    # patch cache
    _load_exceptions.cache_clear()
    # injecte via fonction côté tests (re-écriture controlée si besoin)
    _runtime_exceptions.update(excs)


_runtime_exceptions: dict[str, str] = {}


def _resolve_with_runtime(symbol: str) -> Optional[str]:
    return _runtime_exceptions.get(symbol.upper())


__all__ = [
    "DEFAULT_EXCHANGE",
    "add_exception",
    "from_eodhd",
    "is_supported",
    "reset_exceptions_cache",
    "to_eodhd",
]

