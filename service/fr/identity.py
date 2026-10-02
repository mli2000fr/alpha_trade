"""Validation PIT des mappings de cotation et de ticker FR avant persistance.

La contrainte UNIQUE SQL contrôle la duplication exacte. Les recouvrements
de périodes exigent ce contrôle applicatif, avant tout upsert.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable


class FrIdentityConflict(ValueError):
    """Deux identités prétendent au même symbole/ISIN à la même date."""


@dataclass(frozen=True)
class Validity:
    instrument_uid: str
    namespace: str
    value: str
    valid_from: date
    valid_to: date | None = None

    def __post_init__(self) -> None:
        if not self.instrument_uid or not self.namespace or not self.value:
            raise FrIdentityConflict("Identité et namespace obligatoires")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise FrIdentityConflict("Période inversée")


def assert_no_overlap(rows: Iterable[Validity]) -> None:
    """Refuse tout recouvrement dans un même namespace/valeur.

    Pour les symboles fournisseur : namespace='eodhd:PA', value='AIR.PA'.
    Pour une cotation : namespace='listing:XPAR', value=ISIN. Les bornes
    valid_to sont inclusives : le successeur commence au plus tôt J+1.
    """
    grouped: dict[tuple[str, str], list[Validity]] = {}
    for row in rows:
        key = row.namespace.strip().upper(), row.value.strip().upper()
        grouped.setdefault(key, []).append(row)
    for key, values in grouped.items():
        previous: Validity | None = None
        for current in sorted(values, key=lambda item: (item.valid_from, item.instrument_uid)):
            if previous is not None and (previous.valid_to is None or current.valid_from <= previous.valid_to):
                raise FrIdentityConflict(
                    f"Périodes chevauchantes pour {key[0]}/{key[1]}: "
                    f"{previous.instrument_uid} et {current.instrument_uid}"
                )
            previous = current
