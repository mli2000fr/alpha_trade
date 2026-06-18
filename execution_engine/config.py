"""Configuration immutable du module execution_engine."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, cast

from common.quantity_utils import QUANTITY_EPSILON, is_effectively_integer_quantity
from common.config_loader import load_config
from service.market import parse_trailing_stop


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
class TimeStopConfig:
    """Configuration du mécanisme Time Stop live/backtest."""

    enabled: bool = False
    max_business_days: int = 20
    min_tp_progress_ratio: float = 0.5
    near_zero_return_pct: float = 0.005

    def __post_init__(self) -> None:
        if self.max_business_days < 1:
            raise ValueError("time_stop.max_business_days doit être >= 1.")
        if not (0.0 <= self.min_tp_progress_ratio <= 1.0):
            raise ValueError("time_stop.min_tp_progress_ratio doit être dans [0, 1].")
        if not (0.0 <= self.near_zero_return_pct < 1.0):
            raise ValueError("time_stop.near_zero_return_pct doit être dans [0, 1[.")


@dataclass(frozen=True, slots=True)
class LeverageConfig:
    """Configuration de levier long-only bornée pour le swing overnight."""

    enabled: bool = False
    mode: Literal["disabled", "regt_swing"] = "disabled"
    max_leverage: float = 1.0
    min_equity_usd: float = 2_000.0
    require_margin_account: bool = True
    only_in_entry_mode: Literal["normal", "any"] = "normal"
    disable_in_capital_preservation: bool = True
    disable_if_buying_power_field_missing: bool = False
    buying_power_field_priority: tuple[str, ...] = ("regt_buying_power", "buying_power")
    dry_run_simulated_leverage: float = 1.0
    audit_log: bool = True

    def __post_init__(self) -> None:
        if self.mode not in ("disabled", "regt_swing"):
            raise ValueError("leverage.mode doit être 'disabled' ou 'regt_swing'.")
        if not (1.0 <= self.max_leverage <= 2.0):
            raise ValueError("leverage.max_leverage doit être dans [1.0, 2.0].")
        if self.min_equity_usd < 0:
            raise ValueError("leverage.min_equity_usd doit être >= 0.")
        if self.only_in_entry_mode not in ("normal", "any"):
            raise ValueError("leverage.only_in_entry_mode doit être 'normal' ou 'any'.")
        if not (1.0 <= self.dry_run_simulated_leverage <= 2.0):
            raise ValueError("leverage.dry_run_simulated_leverage doit être dans [1.0, 2.0].")

        normalized_priority = tuple(
            str(field_name).strip()
            for field_name in self.buying_power_field_priority
            if str(field_name).strip()
        )
        if not normalized_priority:
            raise ValueError("leverage.buying_power_field_priority ne doit pas être vide.")
        object.__setattr__(self, "buying_power_field_priority", normalized_priority)
        if self.mode == "disabled":
            object.__setattr__(self, "enabled", False)

    @property
    def capped_live_max_leverage(self) -> float:
        """Borne défensive hard : swing overnight limité à 2x max."""
        return min(float(self.max_leverage), 2.0)


def load_trailing_stop_config_from_yaml(raw_config: Mapping[str, Any] | None = None) -> TrailingStopConfig:
    """Charge la config ``risk_management.trailing_stop`` depuis ``config.yaml``.

    Retourne toujours une instance valide de ``TrailingStopConfig`` ; en absence
    de section YAML, on retombe explicitement sur les valeurs par défaut.
    """
    yaml_cfg = raw_config if raw_config is not None else load_config()
    risk_management_cfg = yaml_cfg.get("risk_management", {}) if isinstance(yaml_cfg, Mapping) else {}
    trailing_stop_cfg = risk_management_cfg.get("trailing_stop") if isinstance(risk_management_cfg, Mapping) else None
    parsed = parse_trailing_stop(trailing_stop_cfg)
    return TrailingStopConfig(
        enabled=bool(parsed.enabled),
        mode=cast(Literal["fixed", "dynamic_atr"], str(parsed.mode)),
        atr_period=int(parsed.atr_period),
        atr_multiplier=float(parsed.atr_multiplier),
        fallback_fixed_pct=float(parsed.fallback_fixed_pct),
        break_even_after_atr_multiple=float(parsed.break_even_after_atr_multiple),
        eod_check_time_est=str(parsed.eod_check_time_est),
        apply_to_manual_orphan_buys=bool(parsed.apply_to_manual_orphan_buys),
    )


def load_time_stop_config_from_yaml(raw_config: Mapping[str, Any] | None = None) -> TimeStopConfig:
    """Charge la config ``risk_management.time_stop`` depuis ``config.yaml``."""
    yaml_cfg = raw_config if raw_config is not None else load_config()
    risk_management_cfg = yaml_cfg.get("risk_management", {}) if isinstance(yaml_cfg, Mapping) else {}
    time_stop_cfg = risk_management_cfg.get("time_stop", {}) if isinstance(risk_management_cfg, Mapping) else {}
    time_stop_map = time_stop_cfg if isinstance(time_stop_cfg, Mapping) else {}
    return TimeStopConfig(
        enabled=bool(time_stop_map.get("enabled", False)),
        max_business_days=int(time_stop_map.get("max_business_days", 20)),
        min_tp_progress_ratio=float(time_stop_map.get("min_tp_progress_ratio", 0.5)),
        near_zero_return_pct=float(time_stop_map.get("near_zero_return_pct", 0.005)),
    )


def load_leverage_config_from_yaml(raw_config: Mapping[str, Any] | None = None) -> LeverageConfig:
    """Charge la config ``leverage`` depuis ``config.yaml``."""
    yaml_cfg = raw_config if raw_config is not None else load_config()
    leverage_cfg = yaml_cfg.get("leverage", {}) if isinstance(yaml_cfg, Mapping) else {}
    leverage_map = leverage_cfg if isinstance(leverage_cfg, Mapping) else {}
    raw_priority = leverage_map.get("buying_power_field_priority", ("regt_buying_power", "buying_power"))
    if isinstance(raw_priority, (list, tuple)):
        priority = tuple(str(field_name) for field_name in raw_priority)
    else:
        priority = ("regt_buying_power", "buying_power")
    return LeverageConfig(
        enabled=bool(leverage_map.get("enabled", False)),
        mode=cast(Literal["disabled", "regt_swing"], str(leverage_map.get("mode", "disabled"))),
        max_leverage=float(leverage_map.get("max_leverage", 1.0)),
        min_equity_usd=float(leverage_map.get("min_equity_usd", 2_000.0)),
        require_margin_account=bool(leverage_map.get("require_margin_account", True)),
        only_in_entry_mode=cast(
            Literal["normal", "any"],
            str(leverage_map.get("only_in_entry_mode", "normal")),
        ),
        disable_in_capital_preservation=bool(leverage_map.get("disable_in_capital_preservation", True)),
        disable_if_buying_power_field_missing=bool(
            leverage_map.get("disable_if_buying_power_field_missing", False)
        ),
        buying_power_field_priority=priority,
        dry_run_simulated_leverage=float(leverage_map.get("dry_run_simulated_leverage", 1.0)),
        audit_log=bool(leverage_map.get("audit_log", True)),
    )


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Paramètres d'exécution — immutable après construction."""

    # --- Mode ---
    broker_mode: str = "paper"
    dry_run: bool = False
    account_id: str | None = None  # None = compte par défaut
    execution_profile: Literal["overnight_cash_swing", "custom", "legacy_intraday"] = "overnight_cash_swing"
    submission_window: Literal["post_close", "pre_open", "both"] = "both"
    account_type: Literal["margin", "cash"] = "cash"
    swing_only: bool = True
    cash_settlement_days: int = 1
    simulated_account_equity: float = 100_000.0
    simulated_margin_buying_power_multiplier: float = 2.0

    # --- Entry order ---
    entry_order_type: str = "market"
    limit_price_buffer_bps: int = 10
    max_entry_gap_pct: float = 0.0

    # --- Bracket legs ---
    profit_taker_pct: float = 0.12
    trailing_stop_pct: float = 0.10
    # Stop-loss appliqué EXCLUSIVEMENT aux achats manuels orphelins adoptés par
    # le watcher (positions ouvertes hors Alpha Trade — site / app Alpaca).
    # Pour les achats normaux, le stop initial reste calculé à partir de
    # l'ATR / risk_per_share du selector.
    manual_buy_stop_loss_pct: float = 0.05
    trailing_stop_type: str = "percent"
    enable_dynamic_trailing_transition: bool = True
    trailing_activation_trigger: Literal["multiple_r", "profit_pct"] = "multiple_r"
    trailing_activation_r_multiple: float = 2.0
    trailing_activation_profit_pct: float = 0.03
    protection_transition_timeout_seconds: int = 0
    protection_transition_poll_interval_seconds: float = 2.0

    # --- Execution ---
    allow_fractional_shares: bool = False
    allow_fractional_live_protections: bool = False
    fractional_live_mode: Literal["entry_only", "intraday_only", "full_if_supported"] = "entry_only"
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
    reconcile_tolerance_shares: float = 0.0
    reconcile_tolerance_epsilon: float = QUANTITY_EPSILON
    auto_rebalance_on_reconcile: bool = False  # si True : soumet des ordres pour corriger les ecarts

    # --- TCA ---
    enable_tca: bool = True

    # --- Market-aware regime (Axe C du plan ``prompt/parttern/plan.md``) ---
    # Mode d'entrée global pour le cycle (ajusté par le snapshot régime).
    entry_mode: Literal["normal", "close_only", "cash_only", "capital_preservation"] = "normal"
    regime_max_positions: int | None = None
    regime_max_position_weight: float | None = None
    regime_max_sector_weight: float | None = None
    regime_max_gross_exposure: float | None = None

    # --- Levier long-only borné (swing overnight) ---
    leverage: LeverageConfig = field(default_factory=LeverageConfig)

    # --- Trailing stop ATR dynamique (Axe F) ---
    trailing_stop: TrailingStopConfig = field(default_factory=TrailingStopConfig)

    # --- Time stop : coupe manuelle si stagnation prolongée ---
    time_stop: TimeStopConfig = field(default_factory=TimeStopConfig)

    def __post_init__(self) -> None:
        if self.broker_mode not in ("paper", "live"):
            raise ValueError("broker_mode doit être 'paper' ou 'live'.")
        if self.execution_profile not in ("overnight_cash_swing", "custom", "legacy_intraday"):
            raise ValueError("execution_profile doit être 'overnight_cash_swing', 'custom' ou 'legacy_intraday'.")
        if self.submission_window not in ("post_close", "pre_open", "both"):
            raise ValueError("submission_window doit être 'post_close', 'pre_open' ou 'both'.")
        if self.account_type not in ("margin", "cash"):
            raise ValueError("account_type doit être 'margin' ou 'cash'.")
        if self.entry_order_type not in ("market", "limit"):
            raise ValueError("entry_order_type doit être 'market' ou 'limit'.")
        if not (0 <= self.max_entry_gap_pct < 1):
            raise ValueError("max_entry_gap_pct doit être dans [0, 1[.")
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
        if self.cash_settlement_days < 1:
            raise ValueError("cash_settlement_days doit être >= 1.")
        if self.simulated_account_equity <= 0:
            raise ValueError("simulated_account_equity doit être > 0.")
        if self.simulated_margin_buying_power_multiplier < 1:
            raise ValueError("simulated_margin_buying_power_multiplier doit être >= 1.")
        if self.entry_mode not in ("normal", "close_only", "cash_only", "capital_preservation"):
            raise ValueError("entry_mode invalide.")
        if self.fractional_live_mode not in ("entry_only", "intraday_only", "full_if_supported"):
            raise ValueError("fractional_live_mode doit être 'entry_only', 'intraday_only' ou 'full_if_supported'.")
        if self.reconcile_tolerance_shares < 0:
            raise ValueError("reconcile_tolerance_shares doit être >= 0.")
        if self.reconcile_tolerance_epsilon <= 0:
            raise ValueError("reconcile_tolerance_epsilon doit être > 0.")
        if self.regime_max_positions is not None and self.regime_max_positions < 1:
            raise ValueError("regime_max_positions doit être >= 1 quand renseigné.")
        if self.regime_max_position_weight is not None and not (0 < self.regime_max_position_weight <= 1):
            raise ValueError("regime_max_position_weight doit être dans ]0, 1].")
        if self.regime_max_sector_weight is not None and not (0 < self.regime_max_sector_weight <= 1):
            raise ValueError("regime_max_sector_weight doit être dans ]0, 1].")
        if self.regime_max_gross_exposure is not None and not (0 < self.regime_max_gross_exposure <= 1):
            raise ValueError("regime_max_gross_exposure doit être dans ]0, 1].")

    @property
    def resolved_account_id(self) -> str:
        return self.account_id or "default"

    @property
    def is_overnight_profile(self) -> bool:
        return self.execution_profile == "overnight_cash_swing"


    def is_paper(self) -> bool:
        return self.broker_mode == "paper"

    def is_live(self) -> bool:
        return self.broker_mode == "live"

    @property
    def fractional_live_entries_enabled(self) -> bool:
        """Active les entrées fractionnaires live/paper du MVP Sprint 4."""
        return bool(self.allow_fractional_shares)

    @property
    def resolved_fractional_live_mode(self) -> Literal["entry_only", "intraday_only", "full_if_supported"]:
        """Résout le mode effectif en conservant la compatibilité du flag Sprint 4."""
        if self.fractional_live_mode != "entry_only":
            return self.fractional_live_mode
        if self.allow_fractional_live_protections:
            return "full_if_supported"
        return "entry_only"

    @property
    def fractional_live_protections_enabled(self) -> bool:
        """Les protections fractionnaires restent opt-in et hors MVP d'entrée."""
        return bool(self.allow_fractional_shares and self.resolved_fractional_live_mode != "entry_only")

    def can_submit_fractional_protection_orders(
        self,
        qty: float,
        *,
        trade_date: date | None = None,
        context: Literal["children", "watcher"] = "children",
    ) -> tuple[bool, str | None]:
        """Retourne si une protection server-side est autorisée pour une qty donnée."""
        if is_effectively_integer_quantity(qty):
            return True, None
        if not self.allow_fractional_shares:
            return False, "fractional_shares_disabled"

        mode = self.resolved_fractional_live_mode
        if mode == "entry_only":
            return False, "fractional_live_entry_only_mode"
        if mode == "intraday_only":
            if self.swing_only or self.is_overnight_profile:
                return False, "fractional_live_intraday_only_mode"
            if context == "watcher" and trade_date is not None and trade_date != date.today():
                return False, "fractional_live_intraday_only_mode"
        return True, None

    def resolve_fractional_protection_time_in_force(self, qty: float) -> str:
        """Retourne le TIF broker approprié pour une protection fractionnaire."""
        if is_effectively_integer_quantity(qty):
            return "gtc"

        mode = self.resolved_fractional_live_mode
        if mode == "intraday_only":
            return "day"
        if mode == "full_if_supported":
            return "gtc"
        raise ValueError(
            "Fractional protection payload requested while fractional_live_mode blocks server-side protections."
        )

    @property
    def effective_reconcile_tolerance_shares(self) -> float:
        """Tolérance effective appliquée à la réconciliation, bornée par un epsilon configurable."""
        return max(float(self.reconcile_tolerance_shares), float(self.reconcile_tolerance_epsilon))

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


