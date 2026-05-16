"""Configuration immutable du module execution_engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, slots=True)
class TrailingStopConfig:
    """Configuration trailing stop ATR (Axe F du plan ``prompt/parttern/plan.md``).

    Le bloc YAML correspondant est ``risk_management.trailing_stop`` (cf.
    ``service.market.config.TrailingStopYAMLConfig``). On le remonte ici car
    le watcher / order_intents en sont les vrais consommateurs.
    """

    enabled: bool = False
    mode: Literal["fixed", "dynamic_atr"] = "fixed"
    atr_period: int = 14
    atr_multiplier: float = 2.5
    fallback_fixed_pct: float = 5.0
    break_even_after_atr_multiple: float = 2.0
    eod_check_time_est: str = "15:50"
    apply_to_manual_orphan_buys: bool = True

    def __post_init__(self) -> None:
        if self.mode not in ("fixed", "dynamic_atr"):
            raise ValueError("trailing_stop.mode doit être 'fixed' ou 'dynamic_atr'.")
        if self.atr_period < 1:
            raise ValueError("trailing_stop.atr_period doit être >= 1.")
        if self.atr_multiplier <= 0:
            raise ValueError("trailing_stop.atr_multiplier doit être > 0.")
        if not (0 < self.fallback_fixed_pct < 100):
            raise ValueError("trailing_stop.fallback_fixed_pct doit être dans ]0, 100[.")
        if self.break_even_after_atr_multiple <= 0:
            raise ValueError("trailing_stop.break_even_after_atr_multiple doit être > 0.")


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Paramètres d'exécution — immutable après construction."""

    # --- Mode ---
    broker_mode: str = "paper"
    dry_run: bool = False
    account_id: str | None = None  # None = compte par défaut
    execution_profile: Literal["overnight_cash_swing", "custom", "legacy_intraday"] = "overnight_cash_swing"
    submission_window: Literal["post_close", "pre_open", "both"] = "both"
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
    # Stop-loss appliqué EXCLUSIVEMENT aux achats manuels orphelins adoptés par
    # le watcher (positions ouvertes hors Alpha Trade — site / app Alpaca).
    # Pour les achats normaux, le stop initial reste calculé à partir de
    # l'ATR / risk_per_share du selector.
    manual_buy_stop_loss_pct: float = 0.05
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
    fill_timeout_seconds: int = 180  # A-017 fix : 180s paper (was 120s) — réduit les ordres orphelins lors de gaps d'ouverture volatils ; live recommandé 300s (configurable via preset)
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

    # --- Market-aware regime (Axe C du plan ``prompt/parttern/plan.md``) ---
    # Mode d'entrée global pour le cycle (ajusté par le snapshot régime).
    entry_mode: Literal["normal", "close_only", "cash_only", "capital_preservation"] = "normal"

    # --- Trailing stop ATR dynamique (Axe F) ---
    trailing_stop: TrailingStopConfig = field(default_factory=TrailingStopConfig)

    def __post_init__(self) -> None:
        if self.broker_mode not in ("paper", "live"):
            raise ValueError("broker_mode doit être 'paper' ou 'live'.")
        if self.execution_profile not in ("overnight_cash_swing", "custom", "legacy_intraday"):
            raise ValueError("execution_profile doit être 'overnight_cash_swing', 'custom' ou 'legacy_intraday'.")
        if self.submission_window not in ("post_close", "pre_open", "both"):
            raise ValueError("submission_window doit être 'post_close', 'pre_open' ou 'both'.")
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
        if not (0 < self.manual_buy_stop_loss_pct < 1):
            raise ValueError("manual_buy_stop_loss_pct doit être dans ]0, 1[.")
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
        if self.entry_mode not in ("normal", "close_only", "cash_only", "capital_preservation"):
            raise ValueError("entry_mode invalide.")

    @property
    def effective_pdt_rule(self) -> Literal["auto", "off"]:
        if self.account_type == "cash":
            return "off"
        return self.pdt_rule

    @property
    def resolved_account_id(self) -> str:
        return self.account_id or "default"

    @property
    def is_overnight_profile(self) -> bool:
        return self.execution_profile == "overnight_cash_swing"

    def applies_pdt_limit(self, equity: float) -> bool:
        return self.effective_pdt_rule == "auto" and equity < self.pdt_equity_threshold

    def is_paper(self) -> bool:
        return self.broker_mode == "paper"

    def is_live(self) -> bool:
        return self.broker_mode == "live"

    @property
    def blocks_new_entries(self) -> bool:
        """True si le mode courant interdit l'ouverture de nouvelles positions."""
        return self.entry_mode in ("close_only", "cash_only")


@dataclass(frozen=True, slots=True)
class ProtectionWatcherServiceConfig:
    """Paramètres du scheduler/service persistant du watcher de protection."""

    interval_seconds: float = 30.0
    idle_interval_seconds: float = 120.0
    heartbeat_interval_seconds: float = 300.0
    max_iterations: int | None = None
    stop_when_idle: bool = False
    max_consecutive_failures: int = 3

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds doit être > 0.")
        if self.idle_interval_seconds <= 0:
            raise ValueError("idle_interval_seconds doit être > 0.")
        if self.heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds doit être > 0.")
        if self.max_iterations is not None and self.max_iterations < 1:
            raise ValueError("max_iterations doit être >= 1 quand renseigné.")
        if self.max_consecutive_failures < 1:
            raise ValueError("max_consecutive_failures doit être >= 1.")


