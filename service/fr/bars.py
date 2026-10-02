"""Validation pure des barres EOD françaises avant toute persistance.

Le prix ajusté fournisseur n'est jamais interprété implicitement comme un
ajustement de split ou un indice total-return. Ces deux séries exigent une
reconstruction séparée à partir d'actions sur titres vérifiées.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from common.market_calendar import dataset_cutoff, get_market_calendar


class FRBarError(ValueError):
    """Barre ou provenance incompatible avec le contrat FR."""


def _price(value: Any, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise FRBarError(f"{name} non numérique") from exc
    if not result.is_finite() or result <= 0:
        raise FRBarError(f"{name} doit être fini et positif")
    return result


@dataclass(frozen=True, slots=True)
class FRProviderBar:
    session_date: date
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    provider_volume_split_adjusted: int | None
    provider_adjusted_close: Decimal | None
    available_at: datetime
    observed_at: datetime


def normalize_eod_bar(
    payload: Mapping[str, Any], *, observed_at: datetime,
    published_at: datetime | None = None,
) -> FRProviderBar:
    """Prépare une barre vérifiée ; n'infère jamais la publication historique.

    Sans ``published_at`` prouvé, la première disponibilité enregistrable est
    l'observation effective. Cela interdit de transformer un backfill actuel
    en fausse donnée historiquement accessible.
    """
    if observed_at.tzinfo is None or (published_at is not None and published_at.tzinfo is None):
        raise FRBarError("horodatages timezone-aware requis")
    try:
        day = date.fromisoformat(str(payload["date"]))
    except (KeyError, ValueError) as exc:
        raise FRBarError("date ISO de séance manquante ou invalide") from exc
    calendar = get_market_calendar("FR_EQ")
    try:
        calendar.session(day)
    except Exception as exc:
        raise FRBarError(f"{day} n'est pas une séance XPAR vérifiée") from exc
    opened = _price(payload.get("open"), "open")
    high = _price(payload.get("high"), "high")
    low = _price(payload.get("low"), "low")
    closed = _price(payload.get("close"), "close")
    if low > min(opened, closed) or high < max(opened, closed) or high < low:
        raise FRBarError("OHLC incohérent")
    raw_volume = payload.get("volume")
    if raw_volume is None:
        volume = None
    else:
        try:
            volume = int(raw_volume)
        except (TypeError, ValueError) as exc:
            raise FRBarError("volume invalide") from exc
        if volume < 0 or str(raw_volume).strip() != str(volume):
            raise FRBarError("volume doit être un entier non négatif")
    if (opened == high == low == closed == Decimal("999999.9999")
            and volume == 0):
        raise FRBarError("barre placeholder EODHD 999999.9999")
    adjusted = payload.get("adjusted_close")
    if adjusted is None:
        adjusted = payload.get("adjusted_close_provider")
    provider_adjusted_close = None if adjusted is None else _price(adjusted, "adjusted_close")
    lower_bound = dataset_cutoff("FR_EQ", "daily_bars", day)
    available_at = max(lower_bound, observed_at.astimezone(UTC),
                       published_at.astimezone(UTC) if published_at else observed_at.astimezone(UTC))
    return FRProviderBar(day, opened, high, low, closed, volume,
                         provider_adjusted_close, available_at, observed_at.astimezone(UTC))
