"""Configuration centralisée du module de gestion de risque."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RiskConfig:
    """Paramètres de risque — immutable après construction."""

    account_equity: float = 100_000.0
    risk_per_trade_pct: float = 0.01
    atr_window: int = 20
    atr_stop_multiple: float = 2.0

    max_positions: int = 20
    max_position_weight: float = 0.10
    max_sector_weight: float = 0.30
    max_gross_exposure: float = 1.0
    min_position_notional: float = 500.0

    max_portfolio_drawdown_pct: float = 0.15
    max_daily_loss_pct: float = 0.05

    dry_run: bool = False

    def __post_init__(self) -> None:
        if self.account_equity <= 0:
            raise ValueError("account_equity doit être > 0.")
        if not 0 < self.risk_per_trade_pct < 1:
            raise ValueError("risk_per_trade_pct doit être dans ]0, 1[.")
        if self.atr_window < 1:
            raise ValueError("atr_window doit être >= 1.")
        if self.atr_stop_multiple <= 0:
            raise ValueError("atr_stop_multiple doit être > 0.")
        if self.max_positions < 1:
            raise ValueError("max_positions doit être >= 1.")
