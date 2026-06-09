"""Configurations métier des contraintes de compte appliquées au backtesting."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

AccountType = Literal["margin", "cash"]


@dataclass(frozen=True, slots=True)
class TradingConstraintConfig:
    """Contraintes de compte applicables pendant un backtest.

    Axes supportés
    --------------
    - ``account_type`` : ``margin`` ou ``cash``
    - ``swing_only`` : interdit les sorties le jour même quand activé
    - ``cash_settlement_days`` : délai de règlement-livraison simulé pour les comptes cash

    """

    account_type: AccountType = "margin"
    swing_only: bool = False
    cash_settlement_days: int = 1

    def __post_init__(self) -> None:
        normalized_account_type = str(self.account_type).strip().lower()
        if normalized_account_type not in {"margin", "cash"}:
            raise ValueError("account_type doit être 'margin' ou 'cash'.")
        object.__setattr__(self, "account_type", cast(AccountType, normalized_account_type))
        normalized_cash_settlement_days = int(self.cash_settlement_days)
        if normalized_cash_settlement_days < 0:
            raise ValueError("cash_settlement_days doit être >= 0.")
        object.__setattr__(self, "cash_settlement_days", normalized_cash_settlement_days)

    @property
    def restrict_same_day_exit(self) -> bool:
        return self.swing_only

    @property
    def use_settled_cash_only(self) -> bool:
        return self.account_type == "cash"

    def requires_stateful_simulation(self, equity: float) -> bool:
        del equity
        return self.restrict_same_day_exit or self.use_settled_cash_only

    def to_dict(self) -> dict[str, int | str | bool]:
        return {
            "account_type": self.account_type,
            "swing_only": self.swing_only,
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

    return TradingConstraintConfig(
        account_type=account_type,
        swing_only=bool(swing_only),
        cash_settlement_days=int(cash_settlement_days),
    )


