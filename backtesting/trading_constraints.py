"""Configurations métier des contraintes de compte appliquées au backtesting."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

AccountType = Literal["margin", "cash"]
PDTRule = Literal["auto", "off"]


@dataclass(frozen=True, slots=True)
class TradingConstraintConfig:
    """Contraintes de compte applicables pendant un backtest.

    Axes supportés
    --------------
    - ``account_type`` : ``margin`` ou ``cash``
    - ``pdt_rule`` : champ legacy accepté mais neutralisé (toujours ``off``)
    - ``swing_only`` : interdit les sorties le jour même quand activé

    """

    account_type: AccountType = "margin"
    pdt_rule: PDTRule = "off"
    swing_only: bool = False
    pdt_equity_threshold: float = 25_000.0
    max_day_trades: int = 3
    rolling_window_days: int = 5
    cash_settlement_days: int = 1

    def __post_init__(self) -> None:
        normalized_account_type = str(self.account_type).strip().lower()
        if normalized_account_type not in {"margin", "cash"}:
            raise ValueError("account_type doit être 'margin' ou 'cash'.")
        object.__setattr__(self, "account_type", cast(AccountType, normalized_account_type))
        # 2026-06 : les règles PDT sont décommissionnées. On conserve le champ
        # uniquement pour compatibilité ascendante des appels historiques.
        object.__setattr__(self, "pdt_rule", "off")

    @property
    def restrict_same_day_exit(self) -> bool:
        return self.swing_only

    @property
    def use_settled_cash_only(self) -> bool:
        return self.account_type == "cash"

    @property
    def effective_pdt_rule(self) -> PDTRule:
        return "off"

    def applies_pdt_limit(self, equity: float) -> bool:
        return False

    def requires_stateful_simulation(self, equity: float) -> bool:
        return self.restrict_same_day_exit or self.use_settled_cash_only


    def to_dict(self) -> dict[str, int | float | str | bool]:
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
    """Construit les contraintes backtest courantes sans logique PDT."""

    return TradingConstraintConfig(
        account_type=account_type,
        swing_only=bool(swing_only),
        cash_settlement_days=int(cash_settlement_days),
    )


