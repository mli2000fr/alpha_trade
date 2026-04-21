"""Configurations métier des contraintes de compte appliquées au backtesting."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SmallAccountMode = Literal["standard", "pdt", "swing", "cash"]


@dataclass(frozen=True, slots=True)
class TradingConstraintConfig:
    """Contraintes de compte applicables pendant un backtest.

    Modes supportés
    ----------------
    - ``standard`` : comportement historique, sans contrainte additionnelle.
    - ``pdt`` : limite les day trades à 3 sur 5 séances si l'equity est < 25k.
    - ``swing`` : interdit toute sortie le jour même de l'entrée.
    - ``cash`` : pas de règle PDT, mais seules les liquidités settled sont réutilisables.
    """

    mode: SmallAccountMode = "standard"
    pdt_equity_threshold: float = 25_000.0
    max_day_trades: int = 3
    rolling_window_days: int = 5
    cash_settlement_days: int = 1

    @property
    def enabled(self) -> bool:
        return self.mode != "standard"

    @property
    def restrict_same_day_exit(self) -> bool:
        return self.mode == "swing"

    @property
    def use_settled_cash_only(self) -> bool:
        return self.mode == "cash"

    def applies_pdt_limit(self, equity: float) -> bool:
        return self.mode == "pdt" and equity < self.pdt_equity_threshold

    def to_dict(self) -> dict[str, int | float | str | bool]:
        return {
            "mode": self.mode,
            "enabled": self.enabled,
            "pdt_equity_threshold": float(self.pdt_equity_threshold),
            "max_day_trades": int(self.max_day_trades),
            "rolling_window_days": int(self.rolling_window_days),
            "cash_settlement_days": int(self.cash_settlement_days),
            "restrict_same_day_exit": self.restrict_same_day_exit,
            "use_settled_cash_only": self.use_settled_cash_only,
        }

