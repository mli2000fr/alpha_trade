"""Sprint S24.1 — Tolérances configurables pour le fuzzing différentiel.

Représente les seuils acceptables de divergence entre l'exécution
**replay backtest** et l'exécution **live simulée**. Chargeable depuis
``config.yaml`` (section ``fuzz_diff``) ou depuis un dict.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class FuzzTolerance:
    """Seuils numériques + booléens autorisés sur une divergence."""

    price_abs: float = 1e-4
    qty_abs: float = 1e-6
    pnl_abs_usd: float = 0.01
    pnl_rel_pct: float = 0.001  # 0.1 %
    status_strict: bool = True  # exige égalité stricte des statuts OCO
    audit_strict: bool = True   # exige égalité stricte des hash audit chain

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "FuzzTolerance":
        if not data:
            return cls()
        kwargs = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**kwargs)

    def accepts_price(self, live: float, replay: float) -> bool:
        return abs(float(live) - float(replay)) <= self.price_abs

    def accepts_qty(self, live: float, replay: float) -> bool:
        return abs(float(live) - float(replay)) <= self.qty_abs

    def accepts_pnl(self, live: float, replay: float) -> bool:
        delta = abs(float(live) - float(replay))
        if delta <= self.pnl_abs_usd:
            return True
        denom = max(abs(float(live)), abs(float(replay)), 1e-9)
        return (delta / denom) <= self.pnl_rel_pct

