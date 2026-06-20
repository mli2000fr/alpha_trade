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


# ── Sprint S11 : modèle de frais de transaction tiered ──


@dataclass(frozen=True, slots=True)
class TieredCommissionConfig:
    """Modèle de commission dégressif par palier de volume.

    Pour les petits ordres, une commission fixe par trade + un taux en bps
    reflète mieux la réalité qu'un taux fixe uniforme.

    - ``fixed_per_trade_usd`` : commission fixe par aller-retour (ex: 0.50 USD)
    - ``bps_rate`` : taux additionnel en bps sur le notionnel
    - ``min_ticket_usd`` : ticket minimum en USD pour que les frais ne dépassent
      pas un seuil de rentabilité (ex: 0.25% du notionnel)
    """

    fixed_per_trade_usd: float = 0.0
    bps_rate: float = 0.0
    min_ticket_usd: float = 100.0

    def compute_commission_usd(self, notional_usd: float) -> float:
        """Retourne la commission en USD pour un trade de notionnel donné."""
        if notional_usd <= 0:
            return 0.0
        return self.fixed_per_trade_usd + (notional_usd * self.bps_rate / 10_000.0)

    def effective_bps(self, notional_usd: float) -> float:
        """Retourne le taux effectif en bps pour un notionnel donné."""
        if notional_usd <= 0:
            return float("inf")
        commission = self.compute_commission_usd(notional_usd)
        return (commission / notional_usd) * 10_000.0

    def is_viable(self, notional_usd: float, max_bps: float = 25.0) -> bool:
        """Vérifie que le ticket est assez grand pour que les frais restent sous max_bps."""
        return notional_usd >= self.min_ticket_usd and self.effective_bps(notional_usd) <= max_bps


# Presets de commission par tranche de capital (Sprint S11)
COMMISSION_PRESETS: dict[str, TieredCommissionConfig] = {
    "micro": TieredCommissionConfig(fixed_per_trade_usd=0.50, bps_rate=15.0, min_ticket_usd=100.0),
    "small": TieredCommissionConfig(fixed_per_trade_usd=0.35, bps_rate=10.0, min_ticket_usd=150.0),
    "standard": TieredCommissionConfig(fixed_per_trade_usd=0.00, bps_rate=6.0, min_ticket_usd=300.0),
    "large": TieredCommissionConfig(fixed_per_trade_usd=0.00, bps_rate=4.0, min_ticket_usd=500.0),
}


def resolve_commission_preset(equity: float) -> TieredCommissionConfig:
    """Sélectionne le preset de commission adapté au capital."""
    if equity <= 2_000:
        return COMMISSION_PRESETS["micro"]
    if equity <= 10_000:
        return COMMISSION_PRESETS["small"]
    if equity <= 50_000:
        return COMMISSION_PRESETS["standard"]
    return COMMISSION_PRESETS["large"]


