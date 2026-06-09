"""Helpers transverses pour normaliser et formatter les quantités d'actions."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN

QUANTITY_DECIMALS = 9
QUANTITY_EPSILON = 10 ** (-QUANTITY_DECIMALS)
_QUANTITY_QUANTIZER = Decimal("1." + ("0" * QUANTITY_DECIMALS))


def normalize_share_quantity(value: float | int | str | Decimal | None, *, decimals: int = QUANTITY_DECIMALS) -> float:
    """Normalise une quantité de shares en bornant la précision et en supprimant le bruit flottant.

    - ``None`` devient ``0.0``.
    - les valeurs négatives proches de zéro sont clampées à ``0.0``.
    - la précision est tronquée à ``decimals`` décimales pour rester compatible broker.
    """
    if value is None:
        return 0.0
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return 0.0

    quantizer = Decimal("1." + ("0" * max(int(decimals), 0)))
    normalized = decimal_value.quantize(quantizer, rounding=ROUND_DOWN)
    if abs(normalized) < Decimal("1e-{}".format(max(int(decimals), 0) or 1)):
        return 0.0
    return float(normalized)


def is_effectively_integer_quantity(value: float | int | str | Decimal | None, *, decimals: int = QUANTITY_DECIMALS) -> bool:
    """Retourne True si la quantité normalisée est un entier exact."""
    normalized = normalize_share_quantity(value, decimals=decimals)
    return float(normalized).is_integer()


def format_share_quantity(value: float | int | str | Decimal | None, *, decimals: int = QUANTITY_DECIMALS) -> str:
    """Formate une quantité pour les payloads broker et les logs applicatifs."""
    normalized = normalize_share_quantity(value, decimals=decimals)
    if float(normalized).is_integer():
        return str(int(normalized))
    text = f"{normalized:.{max(int(decimals), 0)}f}".rstrip("0").rstrip(".")
    return text or "0"


__all__ = [
    "QUANTITY_DECIMALS",
    "QUANTITY_EPSILON",
    "format_share_quantity",
    "is_effectively_integer_quantity",
    "normalize_share_quantity",
]

