"""Configurations métier des contraintes de compte appliquées au backtesting."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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


def build_current_trading_constraints(
    *,
    account_type: AccountType,
    swing_only: bool = False,
    cash_settlement_days: int = 1,
) -> TradingConstraintConfig:
    """Construit les contraintes backtest en vigueur après retrait du PDT.

    Le support bas niveau du PDT reste présent pour compatibilité historique,
    mais le flux CLI courant ne doit plus le réactiver.
    """

    return TradingConstraintConfig(
        account_type=account_type,
        pdt_rule="off",
        swing_only=bool(swing_only),
        cash_settlement_days=int(cash_settlement_days),
    )


