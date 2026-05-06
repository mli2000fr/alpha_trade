"""Helpers purs (transforms) pour l'ingestion EODHD.

Aucune dépendance DB / HTTP / I/O — fonctions pures sans état, déplaçables
sans risque (non patchées par la suite de tests).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Iterable, Optional


_PREFERRED_SERIES_SYMBOL_RE = re.compile(r"^[A-Z]+\.PR[A-Z0-9]+$")


def normalize_date(value: date | str | datetime | None) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def index_bulk_by_project_symbol(
    bulk: Iterable[dict], universe: set[str]
) -> dict[str, dict]:
    """Indexe le payload bulk par symbole projet (filtré sur l'univers).

    Le bulk EODHD renvoie ``code`` (ticker sans suffixe) + ``exchange_short_name``.
    On reconstruit le symbole projet en inversant la convention class-share
    (``BRK-B`` -> ``BRK.B``).
    """
    indexed: dict[str, dict] = {}
    universe_upper = {s.strip().upper() for s in universe}
    for entry in bulk or []:
        raw_code = str(entry.get("code") or "").strip().upper()
        if not raw_code:
            continue
        project_symbol = raw_code.replace("-", ".") if "-" in raw_code else raw_code
        if universe_upper and project_symbol not in universe_upper:
            continue
        indexed[project_symbol] = entry
    return indexed


def bulk_entry_to_raw_bar(entry: dict, target_date: str) -> dict:
    """Convertit une entrée bulk EODHD en barre OHLCV brute pour l'adapter."""
    return {
        "date": str(entry.get("date") or target_date),
        "open": float(entry["open"]),
        "high": float(entry["high"]),
        "low": float(entry["low"]),
        "close": float(entry["close"]),
        "adjusted_close": float(entry.get("adjusted_close", entry["close"])),
        "volume": int(entry.get("volume") or 0),
    }


def rows_to_raw_bars(rows: Iterable[dict]) -> list[dict]:
    raw_bars: list[dict] = []
    for raw in rows or []:
        try:
            raw_bars.append(
                {
                    "date": str(raw.get("date") or ""),
                    "open": float(raw["open"]),
                    "high": float(raw["high"]),
                    "low": float(raw["low"]),
                    "close": float(raw["close"]),
                    "adjusted_close": float(raw.get("adjusted_close", raw["close"])),
                    "volume": int(raw.get("volume") or 0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return raw_bars


def dedupe_raw_bars_by_date(raw_bars: Iterable[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for raw_bar in raw_bars or []:
        raw_date = str(raw_bar.get("date") or "").strip()
        if not raw_date:
            continue
        deduped[raw_date] = raw_bar
    return [deduped[key] for key in sorted(deduped)]


def resolve_missing_fetch_window(
    last_known_date: Optional[date],
    target_date_value: date,
    *,
    target_date_covered_by_bulk: bool,
) -> tuple[Optional[str], Optional[str]]:
    if last_known_date is None or last_known_date >= target_date_value:
        return None, None
    start = last_known_date + timedelta(days=1)
    end = target_date_value - timedelta(days=1) if target_date_covered_by_bulk else target_date_value
    if start > end:
        return None, None
    return start.isoformat(), end.isoformat()


def is_known_unsupported_fallback_symbol(symbol: str) -> bool:
    normalized = str(symbol or "").strip().upper()
    return bool(_PREFERRED_SERIES_SYMBOL_RE.match(normalized))


__all__ = [
    "_PREFERRED_SERIES_SYMBOL_RE",
    "normalize_date",
    "index_bulk_by_project_symbol",
    "bulk_entry_to_raw_bar",
    "rows_to_raw_bars",
    "dedupe_raw_bars_by_date",
    "resolve_missing_fetch_window",
    "is_known_unsupported_fallback_symbol",
]

