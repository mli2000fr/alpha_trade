"""Configurations métier des contraintes de compte appliquées au backtesting."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LegacySmallAccountMode = Literal["standard", "pdt", "swing", "cash"]
AccountType = Literal["margin", "cash"]
PDTRule = Literal["auto", "off"]


@dataclass(frozen=True, slots=True)
class TradingConstraintConfig:
    """Contraintes de compte applicables pendant un backtest.

    Axes supportés
    --------------
    - ``account_type`` : ``margin`` ou ``cash``
    - ``pdt_rule`` : ``auto`` ou ``off``
    - ``swing_only`` : interdit les sorties le jour même quand activé

    Compatibilité legacy
    --------------------
    Un pont `from_legacy_mode()` est conservé pour migrer l'ancien mode exclusif
    ``standard|pdt|swing|cash`` vers cette API plus expressive.
    """

    account_type: AccountType = "margin"
    pdt_rule: PDTRule = "auto"
    swing_only: bool = False
    pdt_equity_threshold: float = 25_000.0
    max_day_trades: int = 3
    rolling_window_days: int = 5
    cash_settlement_days: int = 1

    @property
    def restrict_same_day_exit(self) -> bool:
        return self.swing_only

    @property
    def use_settled_cash_only(self) -> bool:
        return self.account_type == "cash"

    @property
    def effective_pdt_rule(self) -> PDTRule:
        if self.account_type == "cash":
            return "off"
        return self.pdt_rule

    def applies_pdt_limit(self, equity: float) -> bool:
        return self.effective_pdt_rule == "auto" and equity < self.pdt_equity_threshold

    def requires_stateful_simulation(self, equity: float) -> bool:
        return self.restrict_same_day_exit or self.use_settled_cash_only or self.applies_pdt_limit(equity)

    @classmethod
    def from_legacy_mode(cls, mode: LegacySmallAccountMode) -> TradingConstraintConfig:
        mapping: dict[LegacySmallAccountMode, TradingConstraintConfig] = {
            "standard": cls(account_type="margin", pdt_rule="off", swing_only=False),
            "pdt": cls(account_type="margin", pdt_rule="auto", swing_only=False),
            "swing": cls(account_type="margin", pdt_rule="off", swing_only=True),
            "cash": cls(account_type="cash", pdt_rule="off", swing_only=False),
        }
        return mapping[mode]

    def to_dict(self) -> dict[str, int | float | str | bool]:
        return {
            "account_type": self.account_type,
            "pdt_rule": self.pdt_rule,
            "effective_pdt_rule": self.effective_pdt_rule,
            "swing_only": self.swing_only,
            "pdt_equity_threshold": float(self.pdt_equity_threshold),
            "max_day_trades": int(self.max_day_trades),
            "rolling_window_days": int(self.rolling_window_days),
            "cash_settlement_days": int(self.cash_settlement_days),
            "restrict_same_day_exit": self.restrict_same_day_exit,
            "use_settled_cash_only": self.use_settled_cash_only,
        }

