"""Configuration immutable du module execution_engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Paramètres d'exécution — immutable après construction."""

    # --- Mode ---
    broker_mode: str = "paper"
    dry_run: bool = False
    account_id: str | None = None  # None = compte par défaut
    account_type: Literal["margin", "cash"] = "margin"
    pdt_rule: Literal["auto", "off"] = "auto"
    swing_only: bool = False
    pdt_equity_threshold: float = 25_000.0
    max_day_trades: int = 3
    cash_settlement_days: int = 1
    simulated_account_equity: float = 100_000.0
    simulated_margin_buying_power_multiplier: float = 2.0

    # --- Entry order ---
    entry_order_type: str = "market"
    limit_price_buffer_bps: int = 10

    # --- Bracket legs ---
    profit_taker_pct: float = 0.08
    trailing_stop_pct: float = 0.05
    trailing_stop_type: str = "percent"
    enable_dynamic_trailing_transition: bool = True
    trailing_activation_trigger: Literal["multiple_r", "profit_pct"] = "multiple_r"
    trailing_activation_r_multiple: float = 1.0
    trailing_activation_profit_pct: float = 0.03
    protection_transition_timeout_seconds: int = 0
    protection_transition_poll_interval_seconds: float = 2.0

    # --- Execution ---
    allow_fractional_shares: bool = False
    max_slippage_bps: int = 30
    max_order_retries: int = 3
    retry_base_delay_seconds: float = 1.0
    inter_order_delay_ms: int = 350
    poll_interval_seconds: float = 2.0
    fill_timeout_seconds: int = 120
    cancel_timeout_seconds: int = 30

    # --- Market hours ---
    market_clock_skew_seconds: int = 5
    allow_outside_rth: bool = False
    market_calendar_name: str = "NYSE"

    # --- Safety ---
    enable_kill_switch: bool = True
    max_consecutive_failures: int = 3
    execution_batch_size: int = 20

    # --- Reconciliation ---
    reconcile_after_submit: bool = True
    reconcile_tolerance_shares: int = 0
    auto_rebalance_on_reconcile: bool = False  # si True : soumet des ordres pour corriger les ecarts

    # --- TCA ---
    enable_tca: bool = True

    def __post_init__(self) -> None:
        if self.broker_mode not in ("paper", "live"):
            raise ValueError("broker_mode doit être 'paper' ou 'live'.")
        if self.account_type not in ("margin", "cash"):
            raise ValueError("account_type doit être 'margin' ou 'cash'.")
        if self.pdt_rule not in ("auto", "off"):
            raise ValueError("pdt_rule doit être 'auto' ou 'off'.")
        if self.entry_order_type not in ("market", "limit"):
            raise ValueError("entry_order_type doit être 'market' ou 'limit'.")
        if not (0 < self.profit_taker_pct < 1):
            raise ValueError("profit_taker_pct doit être dans ]0, 1[.")
        if not (0 < self.trailing_stop_pct < 1):
            raise ValueError("trailing_stop_pct doit être dans ]0, 1[.")
        if self.trailing_activation_trigger not in ("multiple_r", "profit_pct"):
            raise ValueError("trailing_activation_trigger doit être 'multiple_r' ou 'profit_pct'.")
        if self.trailing_activation_r_multiple <= 0:
            raise ValueError("trailing_activation_r_multiple doit être > 0.")
        if not (0 < self.trailing_activation_profit_pct < 1):
            raise ValueError("trailing_activation_profit_pct doit être dans ]0, 1[.")
        if not (0 <= self.max_slippage_bps <= 500):
            raise ValueError("max_slippage_bps doit être dans [0, 500].")
        if self.max_order_retries < 0:
            raise ValueError("max_order_retries doit être >= 0.")
        if self.retry_base_delay_seconds <= 0:
            raise ValueError("retry_base_delay_seconds doit être > 0.")
        if self.inter_order_delay_ms < 0:
            raise ValueError("inter_order_delay_ms doit être >= 0.")
        if self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds doit être > 0.")
        if self.fill_timeout_seconds <= 0:
            raise ValueError("fill_timeout_seconds doit être > 0.")
        if self.cancel_timeout_seconds <= 0:
            raise ValueError("cancel_timeout_seconds doit être > 0.")
        if self.protection_transition_timeout_seconds < 0:
            raise ValueError("protection_transition_timeout_seconds doit être >= 0.")
        if self.protection_transition_poll_interval_seconds <= 0:
            raise ValueError("protection_transition_poll_interval_seconds doit être > 0.")
        if self.execution_batch_size < 1:
            raise ValueError("execution_batch_size doit être >= 1.")
        if self.max_consecutive_failures < 1:
            raise ValueError("max_consecutive_failures doit être >= 1.")
        if self.pdt_equity_threshold <= 0:
            raise ValueError("pdt_equity_threshold doit être > 0.")
        if self.max_day_trades < 1:
            raise ValueError("max_day_trades doit être >= 1.")
        if self.cash_settlement_days < 1:
            raise ValueError("cash_settlement_days doit être >= 1.")
        if self.simulated_account_equity <= 0:
            raise ValueError("simulated_account_equity doit être > 0.")
        if self.simulated_margin_buying_power_multiplier < 1:
            raise ValueError("simulated_margin_buying_power_multiplier doit être >= 1.")

    @property
    def effective_pdt_rule(self) -> Literal["auto", "off"]:
        if self.account_type == "cash":
            return "off"
        return self.pdt_rule

    def applies_pdt_limit(self, equity: float) -> bool:
        return self.effective_pdt_rule == "auto" and equity < self.pdt_equity_threshold

    def is_paper(self) -> bool:
        return self.broker_mode == "paper"

    def is_live(self) -> bool:
        return self.broker_mode == "live"

