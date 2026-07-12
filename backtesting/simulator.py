"""
backtesting/simulator.py
=========================
Moteur de backtest principal utilisant vectorbt.
Rejoue la stratégie Alpha Trade (entrées par conviction, sorties bracket TP/TS)
sur l'historique OHLCV.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd

from backtesting.trading_constraints import TradingConstraintConfig, resolve_commission_preset
from backtesting.microstructure import (
    MicrostructureConfig,
    compute_adv_usd,
    compute_execution_price,
    resolve_intrabar_exit,
    should_skip_entry_for_gap,
    should_split_order,
)
from backtesting.risk_overlay import RiskOverlayConfig, compute_portfolio_vol_scaler
from common.quantity_utils import QUANTITY_EPSILON, normalize_share_quantity
from common.trading_costs import TradingCostModel, DEFAULT_COST_MODEL
from core.direction import (
    compute_gross_notional,
    compute_pullback_limit_price,
    compute_realized_pnl,
    compute_return_pct,
    compute_take_profit_price,
    compute_trailing_stop_price,
    is_short_side,
)
from execution_engine.config import ExecutionConfig
from risk_management.config import RiskConfig
from risk_management.concentration import (
    BreakoutConfirmationTracker,
    ConsecutiveLossTracker,
    SymbolTradeTracker,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration unifiée du backtest."""
    start_date: date
    end_date: date
    initial_equity: float = 100_000.0
    risk_config: RiskConfig | None = None
    exec_config: ExecutionConfig | None = None

    # Paramètres bracket (défauts = production)
    profit_taker_pct: float = 0.08
    trailing_stop_pct: float = 0.05
    use_live_protection_logic: bool = True
    time_stop_enabled: bool = True
    time_stop_max_business_days: int = 15
    time_stop_min_tp_progress_ratio: float = 0.5
    time_stop_near_zero_return_pct: float = 0.005
    max_positions: int = 20

    # Frais de transaction (Phase 6.1.b)
    # ``fees_pct`` reste le scalaire effectif appliqué par l'engine
    # (= commission + slippage / 10_000).
    fees_pct: float = 0.001  # 10 bps
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    # P3 — commission tiered (TieredCommissionConfig) : remplace le commission_bps
    # plat quand activé. Le fees_pct est alors recalculé = slippage_bps/10000 + tiered.
    use_tiered_commission: bool = False
    # ── Sprint 3 / Point 12 : modèle de coûts canonique ──────────────
    # Quand ``trading_cost_model`` est fourni, ses valeurs (spread, commission,
    # slippage, borrow_fee_annual) sont utilisées pour le calcul des coûts
    # d'entrée/sortie et le borrow fee des shorts. Sinon, les champs legacy
    # ci-dessus sont utilisés (rétrocompatibilité).
    # Le labeler (``TripleBarrierConfig``) partage le même modèle → parité
    # label/simulateur garantie.
    trading_cost_model: TradingCostModel | None = None
    # ── Parité label/simulateur ──────────────────────────────────────
    # Si True, utilise DEFAULT_COST_MODEL (spread=5bps, comm=1bps,
    # slippage=2bps, borrow=0.3%/an, round-trip=16bps) au lieu des
    # champs legacy. Active automatiquement la déduction du borrow fee
    # pour les shorts.
    use_canonical_costs: bool = False
    trading_constraints: TradingConstraintConfig = field(default_factory=TradingConstraintConfig)
    execution_timing: str = "next_open"
    execution_replay_mode: str = "off"
    protection_replay_mode: str = "off"
    watcher_replay_mode: str = "off"
    exit_lifecycle_replay_mode: str = "off"
    # Phase B (refactor) — micro-structure (slippage volume-aware,
    # initial stop, gap filter, intrabar priority).
    microstructure: MicrostructureConfig = field(default_factory=MicrostructureConfig)
    # Phase C (refactor) — surcouches risk (sizing, regime, sectoral, DD breaker).
    risk_overlay: RiskOverlayConfig = field(default_factory=RiskOverlayConfig)
    # Phase C.3 / D.1 — benchmark (utilisé par le filtre régime + métriques).
    benchmark_close: pd.Series | None = None
    seed: int | None = None

    # ── P1 — Trailing stop adaptatif basé sur l'ATR ──
    # Si > 0, remplace le trailing_stop_pct fixe par un stop dynamique :
    #   trailing_distance = atr_trailing_stop_multiplier * ATR_20
    # 0.0 = désactivé (utilise trailing_stop_pct fixe).
    # Pour les microcaps (vol daily 3-8%), une valeur de 1.5–2.5 est recommandée.
    atr_trailing_stop_multiplier: float = 0.0

    # Concentration / diversification (Priorité 4)
    # Assoupli pour le walk-forward sur petits univers (< 50 candidats/jour)
    # afin d'éviter l'étouffement par concentration.
    concentration_max_trades_per_symbol: int = 10
    concentration_window_calendar_days: int = 90
    concentration_max_consecutive_losses: int = 5
    concentration_blacklist_duration_days: int = 30

    # Anti-faux-départs (Quick Win 1)
    min_breakout_days: int = 1

    # Quick Win 2+3 — score minimum + pullback entry
    min_score_threshold: float = 0.7
    entry_limit_offset_pct: float = 0.01  # 1% sous le prix signal

    def __post_init__(self) -> None:
        if self.risk_config:
            self.max_positions = self.risk_config.max_positions
        if self.exec_config:
            self.profit_taker_pct = self.exec_config.profit_taker_pct
            self.trailing_stop_pct = self.exec_config.trailing_stop_pct
            self.time_stop_enabled = self.exec_config.time_stop.enabled
            self.time_stop_max_business_days = self.exec_config.time_stop.max_business_days
            self.time_stop_min_tp_progress_ratio = self.exec_config.time_stop.min_tp_progress_ratio
            self.time_stop_near_zero_return_pct = self.exec_config.time_stop.near_zero_return_pct
        if self.time_stop_max_business_days < 1:
            raise ValueError("time_stop_max_business_days doit être >= 1.")
        if not (0.0 <= self.time_stop_min_tp_progress_ratio <= 1.0):
            raise ValueError("time_stop_min_tp_progress_ratio doit être dans [0, 1].")
        if not (0.0 <= self.time_stop_near_zero_return_pct < 1.0):
            raise ValueError("time_stop_near_zero_return_pct doit être dans [0, 1[.")
        normalized_replay_mode = str(self.execution_replay_mode or "off").strip().lower()
        if normalized_replay_mode not in {"off", "execution_replay"}:
            raise ValueError(
                "execution_replay_mode doit être 'off' ou 'execution_replay'."
            )
        self.execution_replay_mode = normalized_replay_mode
        normalized_protection_mode = str(self.protection_replay_mode or "off").strip().lower()
        if normalized_protection_mode not in {"off", "protection_replay"}:
            raise ValueError(
                "protection_replay_mode doit être 'off' ou 'protection_replay'."
            )
        self.protection_replay_mode = normalized_protection_mode
        normalized_watcher_mode = str(self.watcher_replay_mode or "off").strip().lower()
        if normalized_watcher_mode not in {"off", "watcher_replay"}:
            raise ValueError(
                "watcher_replay_mode doit être 'off' ou 'watcher_replay'."
            )
        self.watcher_replay_mode = normalized_watcher_mode
        normalized_exit_lifecycle_mode = str(self.exit_lifecycle_replay_mode or "off").strip().lower()
        if normalized_exit_lifecycle_mode not in {"off", "exit_lifecycle_replay"}:
            raise ValueError(
                "exit_lifecycle_replay_mode doit être 'off' ou 'exit_lifecycle_replay'."
            )
        self.exit_lifecycle_replay_mode = normalized_exit_lifecycle_mode


@dataclass(slots=True)
class BacktestDiagnostics:
    """Compteurs métier utiles quand des contraintes de compte sont actives."""

    blocked_same_day_exits: int = 0
    blocked_cash_entries: int = 0
    executed_day_trades: int = 0
    # Phase B (refactor) — diagnostics micro-structure.
    blocked_entry_gap: int = 0
    initial_stop_exits: int = 0
    take_profit_exits: int = 0
    trailing_stop_exits: int = 0
    time_stop_exits: int = 0
    # Phase C (refactor) — diagnostics risk overlay.
    blocked_by_regime: int = 0
    blocked_by_sectoral_cap: int = 0
    blocked_by_gross_exposure: int = 0
    blocked_by_drawdown_breaker: int = 0
    # Priorité 4 — concentration / diversification
    blocked_by_concentration: int = 0
    blocked_by_blacklist: int = 0
    # Quick Win 1 — anti-faux-départs
    blocked_by_breakout: int = 0
    protection_replay_activations: int = 0
    watcher_replay_transitions: int = 0
    exit_lifecycle_replayed: int = 0
    # Sprint 5 — force-close par side
    force_close_exits_long: int = 0
    force_close_exits_short: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "blocked_same_day_exits": self.blocked_same_day_exits,
            "blocked_cash_entries": self.blocked_cash_entries,
            "executed_day_trades": self.executed_day_trades,
            "blocked_entry_gap": self.blocked_entry_gap,
            "initial_stop_exits": self.initial_stop_exits,
            "take_profit_exits": self.take_profit_exits,
            "trailing_stop_exits": self.trailing_stop_exits,
            "time_stop_exits": self.time_stop_exits,
            "blocked_by_regime": self.blocked_by_regime,
            "blocked_by_sectoral_cap": self.blocked_by_sectoral_cap,
            "blocked_by_gross_exposure": self.blocked_by_gross_exposure,
            "blocked_by_drawdown_breaker": self.blocked_by_drawdown_breaker,
            "blocked_by_concentration": self.blocked_by_concentration,
            "blocked_by_blacklist": self.blocked_by_blacklist,
            "blocked_by_breakout": self.blocked_by_breakout,
            "protection_replay_activations": self.protection_replay_activations,
            "watcher_replay_transitions": self.watcher_replay_transitions,
            "exit_lifecycle_replayed": self.exit_lifecycle_replayed,
            # Sprint 5 — force-close par side
            "force_close_exits_long": self.force_close_exits_long,
            "force_close_exits_short": self.force_close_exits_short,
        }


@dataclass(slots=True)
class _OpenPosition:
    symbol: str
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    entry_idx: int
    entry_price: float
    quantity: float
    peak_high: float
    trough_low: float  # Sprint 2 — trailing short
    entry_cost: float
    side: str = "buy"  # Sprint 2 — direction
    # Phase B.2 — stop-loss initial dur (None = désactivé).
    initial_stop_price: float | None = None
    risk_per_share: float | None = None
    replay_take_profit_price: float | None = None
    replay_initial_stop_price: float | None = None
    replay_trailing_stop_pct: float | None = None
    replay_trailing_activation_price: float | None = None
    replay_trailing_activation_mode: str | None = None
    replay_trailing_active: bool = False
    watcher_transition_state: str | None = None
    watcher_trigger_date: pd.Timestamp | None = None
    watcher_transition_effective_date: pd.Timestamp | None = None
    explicit_exit_date: pd.Timestamp | None = None
    explicit_exit_price: float | None = None
    explicit_exit_reason: str | None = None
    explicit_exit_intent_role: str | None = None
    explicit_oco_sibling_canceled: bool = False
    # Phase D.2 — secteur pour attribution sectorielle.
    sector: str | None = None
    signal_context: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class _RunState:
    """Phase E.3 (refactor) — état mutable centralisé du run.

    Concentre l'ensemble des compteurs/cash/positions précédemment éparpillés
    dans des variables locales de ``_run_with_constraints``. Permet aux
    sous-méthodes (``_apply_settlements``, ``_open_position``, ``_close_position``)
    d'opérer par mutation explicite sans return tuple verbeux.
    """

    settled_cash: float
    unsettled_cash: float = 0.0
    peak_equity: float = 0.0
    settlements_by_day: dict[int, float] = field(default_factory=lambda: defaultdict(float))
    positions: dict[str, _OpenPosition] = field(default_factory=dict)
    closed_trades: list[dict[str, object]] = field(default_factory=list)
    trade_events: list[dict[str, object]] = field(default_factory=list)
    equity_points: list[float] = field(default_factory=list)
    breaker_points: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _DailyLeverageState:
    feature_enabled: bool
    active: bool
    effective_leverage: float
    configured_max: float
    reason: str | None = None


class _ReadableTradesAccessor:
    """Façade minimale proche de vectorbt.trades pour les runs contraints."""

    def __init__(self, closed_trades_df: pd.DataFrame) -> None:
        self._closed_trades_df = closed_trades_df

    @property
    def closed(self) -> _ReadableTradesAccessor:
        return self

    @property
    def records_readable(self) -> pd.DataFrame:
        if self._closed_trades_df.empty:
            return pd.DataFrame(
                columns=[
                    "Column", "Size", "Signal Timestamp", "Entry Timestamp", "Exit Timestamp",
                    "Avg Entry Price", "Avg Exit Price", "PnL", "Return [%]",
                    "Duration", "Exit Reason", "Day Trade",
                ]
            )
        return self._closed_trades_df.rename(
            columns={
                "symbol": "Column",
                "quantity": "Size",
                "signal_date": "Signal Timestamp",
                "entry_date": "Entry Timestamp",
                "exit_date": "Exit Timestamp",
                "entry_price": "Avg Entry Price",
                "exit_price": "Avg Exit Price",
                "pnl": "PnL",
                "return_pct": "Return [%]",
                "holding_days": "Duration",
                "exit_reason": "Exit Reason",
                "is_day_trade": "Day Trade",
            }
        )

    def count(self) -> int:
        return int(len(self._closed_trades_df))


@dataclass(slots=True)
class BacktestResult:
    """Résultat minimaliste de backtest compatible avec le reporting existant."""

    equity_curve: pd.Series
    closed_trades_df: pd.DataFrame
    trade_events_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    diagnostics: BacktestDiagnostics = field(default_factory=BacktestDiagnostics)
    drawdown_breaker_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    # P2 (2026-06-25) : snapshot des trackers pour persistence cross-run
    tracker_snapshot: dict[str, object] | None = None
    wrapper: SimpleNamespace = field(init=False)
    trades: _ReadableTradesAccessor = field(init=False)

    def __post_init__(self) -> None:
        self.wrapper = SimpleNamespace(index=self.equity_curve.index)
        self.trades = _ReadableTradesAccessor(self.closed_trades_df)

    def final_value(self) -> float:
        return float(self.equity_curve.iloc[-1]) if not self.equity_curve.empty else 0.0

    def value(self) -> pd.Series:
        return self.equity_curve


class BacktestEngine:
    """Exécute le backtest à partir des signaux reconstruits."""

    _SIGNAL_CONTEXT_FIELDS: tuple[tuple[str, str], ...] = (
        ("signal_date", "signal_date"),
        ("execution_date", "execution_date"),
        ("score", "score"),
        ("score_source", "score_source"),
        ("predicted_proba", "predicted_proba"),
        ("conviction", "conviction"),
        ("rank", "rank"),
        ("selection_rank", "selection_rank"),
        ("sector", "signal_sector"),
        ("selector_signal_mode", "selector_signal_mode"),
        ("selection_explanation", "selection_explanation"),
        ("selector_earnings_blackout", "selector_earnings_blackout"),
        ("decision", "entry_decision"),
        ("decision_reason", "entry_reason"),
        ("target_weight", "signal_target_weight"),
        ("target_notional", "signal_target_notional"),
        ("approved_shares", "signal_approved_shares"),
        ("filled_qty", "signal_filled_qty"),
        ("fill_price", "signal_fill_price"),
        ("watcher_transition_state", "watcher_transition_state"),
        ("watcher_trigger_date", "watcher_trigger_date"),
        ("watcher_transition_effective_date", "watcher_transition_effective_date"),
        ("replay_take_profit_price", "replay_take_profit_price"),
        ("replay_initial_stop_price", "replay_initial_stop_price"),
        ("replay_trailing_stop_pct", "replay_trailing_stop_pct"),
        ("replay_trailing_activation_price", "replay_trailing_activation_price"),
        ("replay_trailing_activation_mode", "replay_trailing_activation_mode"),
        ("replay_exit_date", "replay_exit_date"),
        ("replay_exit_price", "replay_exit_price"),
        ("replay_exit_reason", "replay_exit_reason"),
        ("replay_exit_intent_role", "replay_exit_intent_role"),
        ("replay_oco_sibling_canceled", "replay_oco_sibling_canceled"),
    )

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config
        # ── Sprint 3 / Point 12 : modèle de coûts canonique ──────────
        self._cost_model = self._resolve_cost_model(config)
        # Concentration filters (Priorité 4)
        self._concentration_trade_tracker = SymbolTradeTracker(
            max_trades=config.concentration_max_trades_per_symbol,
            window_days=config.concentration_window_calendar_days,
        )
        self._concentration_loss_tracker = ConsecutiveLossTracker(
            max_consecutive_losses=config.concentration_max_consecutive_losses,
            blacklist_duration_days=config.concentration_blacklist_duration_days,
        )
        # Anti-faux-départs (Quick Win 1)
        self._breakout_tracker = BreakoutConfirmationTracker(
            min_breakout_days=config.min_breakout_days,
        )

    @staticmethod
    def _resolve_cost_model(config: BacktestConfig) -> TradingCostModel:
        """Résout le modèle de coûts effectif pour le simulateur.

        Priorité :
        1. ``trading_cost_model`` explicitement fourni
        2. ``use_canonical_costs=True`` → ``DEFAULT_COST_MODEL``
        3. Champs legacy (``commission_bps``, ``slippage_bps``, ``fees_pct``)
        """
        if config.trading_cost_model is not None:
            return config.trading_cost_model
        if config.use_canonical_costs:
            return DEFAULT_COST_MODEL
        # Rétrocompatibilité : construire depuis les champs legacy
        return TradingCostModel(
            spread_bps=0.0,  # le spread réel est géré séparément via _get_spread_bps
            commission_bps=float(config.commission_bps),
            slippage_bps=float(config.slippage_bps),
            borrow_fee_annual=0.003,  # défaut standard
        )

    # ------------------------------------------------------------------
    # P2 (2026-06-25) : persistence cross-run des trackers
    # ------------------------------------------------------------------
    @property
    def tracker_snapshot(self) -> dict[str, object]:
        """Snapshot sérialisable des 3 trackers pour persistence cross-run."""
        return {
            "symbol_trade_tracker": self._concentration_trade_tracker.to_dict(),
            "consecutive_loss_tracker": self._concentration_loss_tracker.to_dict(),
            "breakout_tracker": self._breakout_tracker.to_dict(),
        }

    def load_tracker_state(self, snapshot: dict[str, object]) -> None:
        """Restaure l'état des trackers depuis un snapshot (P2 2026-06-25)."""
        from risk_management.concentration import (
            SymbolTradeTracker,
            ConsecutiveLossTracker,
            BreakoutConfirmationTracker,
        )
        trade_data = snapshot.get("symbol_trade_tracker")
        if isinstance(trade_data, dict):
            self._concentration_trade_tracker = SymbolTradeTracker.from_dict(trade_data)
        loss_data = snapshot.get("consecutive_loss_tracker")
        if isinstance(loss_data, dict):
            self._concentration_loss_tracker = ConsecutiveLossTracker.from_dict(loss_data)
        breakout_data = snapshot.get("breakout_tracker")
        if isinstance(breakout_data, dict):
            self._breakout_tracker = BreakoutConfirmationTracker.from_dict(breakout_data)
        LOGGER.info(
            "Tracker state loaded: trade=%s loss=%s breakout=%s",
            self._concentration_trade_tracker.to_summary(),
            self._concentration_loss_tracker.to_summary(),
            self._breakout_tracker.to_summary(),
        )

    @staticmethod
    def _to_scalar(value) -> float:
        """Convertit une sortie vectorbt/pandas scalaire ou Series en float."""
        if hasattr(value, "iloc"):
            return float(value.iloc[0])
        return float(value)

    @staticmethod
    def _empty_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
        """Préserve l'index du marché tout en retirant toutes les colonnes symboles."""
        return frame.iloc[:, 0:0].copy()

    def _allow_fractional_shares(self) -> bool:
        return bool(self.config.risk_config is not None and self.config.risk_config.allow_fractional_shares)

    def _normalize_trade_quantity(self, value: float | int | None) -> float:
        normalized = max(normalize_share_quantity(value), 0.0)
        if self._allow_fractional_shares():
            return normalized
        return float(int(normalized))

    def _resolve_daily_leverage_state(self, current_equity: float, *, drawdown_scale: float = 1.0) -> _DailyLeverageState:
        exec_cfg = self.config.exec_config
        if exec_cfg is None:
            return _DailyLeverageState(
                feature_enabled=False,
                active=False,
                effective_leverage=1.0,
                configured_max=1.0,
                reason="missing_exec_config",
            )

        leverage_cfg = exec_cfg.leverage
        feature_enabled = bool(leverage_cfg.enabled and leverage_cfg.mode != "disabled")
        configured_max = float(leverage_cfg.capped_live_max_leverage)
        if str(exec_cfg.account_type).strip().lower() != "margin":
            return _DailyLeverageState(
                feature_enabled=feature_enabled,
                active=False,
                effective_leverage=1.0,
                configured_max=configured_max,
                reason="cash_account",
            )
        if not feature_enabled or leverage_cfg.max_leverage <= 1.0:
            return _DailyLeverageState(
                feature_enabled=feature_enabled,
                active=False,
                effective_leverage=1.0,
                configured_max=configured_max,
                reason="feature_disabled",
            )
        if current_equity < float(leverage_cfg.min_equity_usd):
            return _DailyLeverageState(
                feature_enabled=feature_enabled,
                active=False,
                effective_leverage=1.0,
                configured_max=configured_max,
                reason="equity_below_minimum",
            )
        if leverage_cfg.only_in_entry_mode == "normal" and exec_cfg.entry_mode != "normal":
            return _DailyLeverageState(
                feature_enabled=feature_enabled,
                active=False,
                effective_leverage=1.0,
                configured_max=configured_max,
                reason="entry_mode_not_normal",
            )
        if leverage_cfg.disable_in_capital_preservation and exec_cfg.entry_mode == "capital_preservation":
            return _DailyLeverageState(
                feature_enabled=feature_enabled,
                active=False,
                effective_leverage=1.0,
                configured_max=configured_max,
                reason="capital_preservation",
            )

        # ── Levier dynamique : réduit progressivement en période de drawdown ──
        # drawdown_scale = 1.0 → levier max normal
        # drawdown_scale = 0.0 → levier = 1.0x (pas d'emprunt)
        base_leverage = min(
            max(float(exec_cfg.simulated_margin_buying_power_multiplier), 1.0),
            float(leverage_cfg.dry_run_simulated_leverage),
            configured_max,
        )
        dd_scale = max(0.0, min(1.0, float(drawdown_scale)))
        dynamic_leverage = 1.0 + (base_leverage - 1.0) * dd_scale
        return _DailyLeverageState(
            feature_enabled=feature_enabled,
            active=True,
            effective_leverage=float(dynamic_leverage),
            configured_max=configured_max,
            reason=f"drawdown_scale={dd_scale:.2f}" if dd_scale < 0.99 else None,
        )

    def _resolve_margin_buying_power_multiplier(self, current_equity: float, *, drawdown_scale: float = 1.0) -> float:
        """Résout le multiplicateur de buying power/gross exposure en backtest.

        En backtest, le simple fait d'être sur un compte ``margin`` ne suffit pas
        à autoriser une exposition > 100 % : il faut que la politique explicite
        ``leverage`` soit active et passe ses garde-fous runtime. Sinon on reste
        volontairement à 1.0x.

        Le paramètre ``drawdown_scale`` (0.0–1.0) réduit dynamiquement le levier
        en période de drawdown : 1.0 = levier max, 0.0 = pas de levier.
        """
        return float(self._resolve_daily_leverage_state(current_equity, drawdown_scale=drawdown_scale).effective_leverage)

    def _resolve_available_entry_budget(
        self,
        *,
        constraints: TradingConstraintConfig,
        settled_cash: float,
        current_equity: float,
        current_gross_notional: float,
    ) -> float:
        if constraints.use_settled_cash_only:
            return max(float(settled_cash), 0.0)
        if str(constraints.account_type).strip().lower() != "margin":
            return max(float(settled_cash), 0.0)
        effective_multiplier = self._resolve_margin_buying_power_multiplier(float(current_equity))
        total_buying_power = max(float(current_equity) * effective_multiplier, 0.0)
        return max(total_buying_power - max(float(current_gross_notional), 0.0), 0.0)

    def run(
        self,
        open_df: pd.DataFrame | None = None,
        close: pd.DataFrame | None = None,
        high: pd.DataFrame | None = None,
        low: pd.DataFrame | None = None,
        signals_df: pd.DataFrame | None = None,
        volume: pd.DataFrame | None = None,
        sector_map: dict[str, str] | None = None,
        # Phase A.1 (refactor) — alias de rétro-compatibilité.
        # L'ancien paramètre s'appelait ``open`` et ombrait la builtin Python.
        # P1 — spread réel par ticker (stock_quote_snapshots).
        spread_df: pd.DataFrame | None = None,
        **legacy_kwargs,
    ) -> BacktestResult:
        """Lance le backtest.

        Parameters
        ----------
        open_df, close, high, low : DataFrame pivoté (index=date, columns=symbols)
        signals_df : DataFrame issu de signal_replay.replay_signals().
        volume : Phase B.1 — volume journalier optionnel pour ADV slippage.
        sector_map : Phase C.4 — mapping symbol → secteur pour cap sectoriel.
        """
        # Compat A.1 : accepter encore ``open=`` comme kwarg.
        if open_df is None and "open" in legacy_kwargs:
            open_df = legacy_kwargs.pop("open")
        if legacy_kwargs:
            raise TypeError(
                f"BacktestEngine.run a reçu des arguments inattendus : {list(legacy_kwargs)}"
            )
        if open_df is None or close is None or high is None or low is None or signals_df is None:
            raise TypeError(
                "BacktestEngine.run requiert open_df, close, high, low et signals_df."
            )
        cfg = self.config
        constraints = cfg.trading_constraints

        signals = signals_df.copy()
        if signals.empty:
            for column_name, dtype in {
                "trade_date": "datetime64[ns]",
                "symbol": "object",
                "selected": "bool",
                "rank": "float64",
            }.items():
                if column_name not in signals.columns:
                    signals[column_name] = pd.Series(dtype=dtype)

        missing_columns = [
            column_name for column_name in ("trade_date", "symbol", "selected") if column_name not in signals.columns
        ]
        if missing_columns:
            raise ValueError(
                f"BacktestEngine.run requiert les colonnes de signaux suivantes : {missing_columns}"
            )

        # Aligner les symboles communs
        selected = signals.loc[signals["selected"].fillna(False).astype(bool)].copy()
        if selected.empty:
            LOGGER.info("Aucun signal sélectionné — backtest plat sans trade.")
            return self._run_with_constraints(
                open_df=self._empty_market_frame(open_df),
                close=self._empty_market_frame(close),
                high=self._empty_market_frame(high),
                low=self._empty_market_frame(low),
                signals_df=selected,
                volume=self._empty_market_frame(volume) if volume is not None else None,
                sector_map=sector_map,
                spread_df=spread_df,
            )

        symbols = sorted(set(selected["symbol"]) & set(close.columns))
        if not symbols:
            LOGGER.warning("Aucun symbole exécutable en commun entre signaux sélectionnés et OHLCV — backtest plat.")
            return self._run_with_constraints(
                open_df=self._empty_market_frame(open_df),
                close=self._empty_market_frame(close),
                high=self._empty_market_frame(high),
                low=self._empty_market_frame(low),
                signals_df=selected,
                volume=self._empty_market_frame(volume) if volume is not None else None,
                sector_map=sector_map,
                spread_df=spread_df,
            )

        open_df = open_df[symbols].copy()
        close = close[symbols].copy()
        high = high[symbols].copy()
        low = low[symbols].copy()
        if volume is not None:
            volume = volume[[s for s in symbols if s in volume.columns]].copy()

        if cfg.execution_timing != "next_open":
            raise ValueError(f"Convention d'exécution non supportée: {cfg.execution_timing}")

        if constraints.requires_stateful_simulation(cfg.initial_equity):
            LOGGER.info("Backtest avec contraintes actives: %s", constraints.to_dict())
            return self._run_with_constraints(
                open_df=open_df, close=close, high=high, low=low,
                signals_df=selected, volume=volume, sector_map=sector_map,
                spread_df=spread_df,
            )

        LOGGER.info(
            "Backtest standard (signal J, entrée J+1 open) : %d symboles, %d jours, TP=%.1f%%, TS=%.1f%%, equity=%.0f",
            len(symbols), len(close), cfg.profit_taker_pct * 100,
            cfg.trailing_stop_pct * 100, cfg.initial_equity,
        )

        return self._run_with_constraints(
            open_df=open_df, close=close, high=high, low=low,
            signals_df=selected, volume=volume, sector_map=sector_map,
            spread_df=spread_df,
        )

    @staticmethod
    def _schedule_signals_for_execution(
        signals_df: pd.DataFrame,
        trading_days: pd.DatetimeIndex,
    ) -> pd.DataFrame:
        """Décale chaque signal sur la prochaine séance disponible (J+1 open)."""
        if signals_df.empty:
            return signals_df.copy()

        scheduled = signals_df.copy()
        scheduled["trade_date"] = pd.to_datetime(scheduled["trade_date"])
        execution_indices = trading_days.searchsorted(
            scheduled["trade_date"].to_numpy(dtype="datetime64[ns]"),
            side="right",
        )
        valid_mask = execution_indices < len(trading_days)
        scheduled = scheduled.loc[valid_mask].copy()
        if scheduled.empty:
            return scheduled

        scheduled["signal_date"] = scheduled["trade_date"]
        scheduled["execution_date"] = trading_days.take(execution_indices[valid_mask]).values
        return scheduled

    @staticmethod
    def _normalize_event_value(value: object) -> object | None:
        if value is None:
            return None
        if isinstance(value, (pd.Timestamp, np.datetime64)):
            timestamp = pd.Timestamp(value)
            return None if pd.isna(timestamp) else timestamp
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float):
            return value if np.isfinite(value) else None
        if isinstance(value, (int, bool, str)):
            return value
        try:
            if pd.isna(value):
                return None
        except TypeError:
            return value
        return value

    def _build_signal_context(self, row: pd.Series) -> dict[str, object]:
        context: dict[str, object] = {}
        for source_name, target_name in self._SIGNAL_CONTEXT_FIELDS:
            if source_name not in row.index:
                continue
            normalized_value = self._normalize_event_value(row.get(source_name))
            if normalized_value is None:
                continue
            context[target_name] = normalized_value
        context.setdefault("entry_reason", self._derive_entry_reason(row))
        return context

    def _derive_entry_reason(self, row: pd.Series) -> str:
        explicit_reason = self._resolve_signal_text(row, "decision_reason")
        if explicit_reason:
            return explicit_reason
        score_source = self._resolve_signal_text(row, "score_source")
        if score_source:
            return f"selected_from_{score_source}"
        return "selected_signal"

    @staticmethod
    def _format_event_payload(payload: dict[str, object]) -> str:
        return ", ".join(f"{key}={value}" for key, value in payload.items())

    def _record_trade_event(
        self,
        state: _RunState,
        event_type: str,
        **payload: object,
    ) -> None:
        event_payload: dict[str, object] = {"event_type": event_type}
        for key, raw_value in payload.items():
            normalized_value = self._normalize_event_value(raw_value)
            if normalized_value is None:
                continue
            event_payload[key] = normalized_value
        state.trade_events.append(event_payload)
        LOGGER.info("BT_EVENT %s", self._format_event_payload(event_payload))

    def _run_with_constraints(
        self,
        *,
        open_df: pd.DataFrame,
        close: pd.DataFrame,
        high: pd.DataFrame,
        low: pd.DataFrame,
        signals_df: pd.DataFrame,
        volume: pd.DataFrame | None = None,
        sector_map: dict[str, str] | None = None,
        spread_df: pd.DataFrame | None = None,
    ) -> BacktestResult:
        cfg = self.config
        constraints = cfg.trading_constraints
        diagnostics = BacktestDiagnostics()
        rng = np.random.default_rng(cfg.seed) if cfg.seed is not None else None
        sector_map = sector_map or {}

        trading_days = pd.DatetimeIndex(close.index)
        signals_by_day = self._prepare_signals_by_day(signals_df, trading_days)

        # Phase B.1 — ADV pré-calculé pour le slippage volume-aware.
        adv_usd_df = compute_adv_usd(close, volume, window=20) if volume is not None else None
        # ── P1 — ATR pré-calculé pour le trailing stop adaptatif ──
        atr_df: pd.DataFrame | None = None
        if cfg.atr_trailing_stop_multiplier > 0:
            atr_df = self._compute_atr(high, low, close, window=20)
        mtm_close = close.ffill()

        state = _RunState(
            settled_cash=float(cfg.initial_equity),
            peak_equity=float(cfg.initial_equity),
        )

        for day_idx in range(len(trading_days)):
            trade_day = pd.Timestamp(trading_days[day_idx])
            self._apply_settlements(state, day_idx)

            # Phase E.4 — single mark-to-market précoce pour Phase C.5.
            current_market_value = self._mark_to_market(state.positions, mtm_close, trade_day)
            current_equity = state.settled_cash + state.unsettled_cash + current_market_value
            state.peak_equity = max(state.peak_equity, current_equity)
            entries_allowed_by_breaker = cfg.risk_overlay.drawdown_breaker.update(
                current_equity, state.peak_equity
            )

            # Quick Win — force-close partiel si le breaker trippe (direction-aware)
            if (
                cfg.risk_overlay.drawdown_breaker.force_close_on_breaker
                and cfg.risk_overlay.drawdown_breaker.just_tripped()
                and state.positions
            ):
                force_pct = float(cfg.risk_overlay.drawdown_breaker.force_close_pct)
                # Trier par PnL (on liquide les plus gros perdants d'abord)
                position_pnls = []
                for symbol, position in state.positions.items():
                    close_price = float(close.at[trade_day, symbol]) if symbol in close.columns else position.entry_price
                    pos_side = getattr(position, "side", "buy") or "buy"
                    abs_qty = abs(position.quantity)
                    pnl = compute_realized_pnl(pos_side, abs_qty, position.entry_price, close_price)
                    position_pnls.append((symbol, pnl, close_price, pos_side))
                position_pnls.sort(key=lambda x: x[1])  # pire PnL d'abord
                
                n_close = max(1, int(len(position_pnls) * force_pct + 0.5))
                to_close = position_pnls[:n_close]
                
                LOGGER.warning(
                    "Force-close partiel (%.0f%%): liquidation de %d/%d positions (equity=%.2f)",
                    force_pct * 100, n_close, len(state.positions), current_equity,
                )
                diagnostics.blocked_by_drawdown_breaker += n_close
                # Sprint 5 — compter force-close par side
                for symbol, pnl, close_price, pos_side in to_close:
                    if is_short_side(pos_side):
                        diagnostics.force_close_exits_short += 1
                    else:
                        diagnostics.force_close_exits_long += 1
                
                for symbol, pnl, close_price, pos_side in to_close:
                    position = state.positions[symbol]
                    abs_qty = abs(position.quantity)
                    return_pct = compute_return_pct(pos_side, position.entry_price, close_price)
                    if is_short_side(pos_side):
                        # Short close: buy back, debit cash
                        state.settled_cash -= abs_qty * close_price
                    else:
                        # Long close: sell, credit cash
                        state.settled_cash += abs_qty * close_price
                    state.closed_trades.append({
                        "symbol": symbol,
                        "side": pos_side,
                        "quantity": position.quantity,
                        "entry_date": position.entry_date,
                        "entry_price": position.entry_price,
                        "exit_date": trade_day,
                        "exit_price": close_price,
                        "pnl": pnl,
                        "return_pct": return_pct,
                        "holding_days": (trade_day - position.entry_date).days,
                        "exit_reason": "force_close_breaker",
                        "sector": position.sector,
                    })
                    del state.positions[symbol]
                
                current_market_value = self._mark_to_market(state.positions, mtm_close, trade_day)
                current_equity = state.settled_cash + state.unsettled_cash + current_market_value
                state.peak_equity = max(state.peak_equity, current_equity)

            _entry_mode = cfg.exec_config.entry_mode if cfg.exec_config is not None else None
            cfg.risk_overlay.drawdown_breaker.update_regime_streak(_entry_mode, float(current_equity))
            drawdown_allocation_scale = cfg.risk_overlay.drawdown_breaker.allocation_scale(
                entry_mode=_entry_mode
            )

            # Diagnostic quotidien breaker (C.5)
            if cfg.risk_overlay.drawdown_breaker.enabled:
                _ref_peak = cfg.risk_overlay.drawdown_breaker._reference_peak(state.peak_equity)
                state.breaker_points.append({
                    "trade_date": trade_day,
                    "equity": current_equity,
                    "reference_peak": _ref_peak,
                    "dd_pct": round(((current_equity / _ref_peak) - 1.0) * 100.0, 4) if _ref_peak > 0 else None,
                    "tripped": not entries_allowed_by_breaker,
                    "allocation_scale": drawdown_allocation_scale,
                    "normal_streak": cfg.risk_overlay.drawdown_breaker._normal_streak,
                    "entry_mode": _entry_mode,
                })

            # Phase C.3 — filtre régime (benchmark).
            entries_allowed_by_regime = cfg.risk_overlay.regime_filter.is_entry_allowed(
                cfg.benchmark_close, trade_day,
            )
            current_gross_notional = self._compute_gross_notional(state.positions, mtm_close, trade_day)
            leverage_state = self._resolve_daily_leverage_state(float(current_equity), drawdown_scale=drawdown_allocation_scale)
            self._record_trade_event(
                state,
                "daily_leverage_snapshot",
                event_date=trade_day,
                account_type=str(constraints.account_type),
                entry_mode=(cfg.exec_config.entry_mode if cfg.exec_config is not None else None),
                leverage_feature_enabled=leverage_state.feature_enabled,
                leverage_active=leverage_state.active,
                leverage_configured_max=leverage_state.configured_max,
                effective_leverage=leverage_state.effective_leverage,
                leverage_reason=leverage_state.reason,
                current_equity=current_equity,
                settled_cash=state.settled_cash,
                unsettled_cash=state.unsettled_cash,
                current_gross_notional=current_gross_notional,
                gross_exposure_before_pct=(current_gross_notional / current_equity) if current_equity > 0 else 0.0,
                available_entry_budget=self._resolve_available_entry_budget(
                    constraints=constraints,
                    settled_cash=state.settled_cash,
                    current_equity=current_equity,
                    current_gross_notional=current_gross_notional,
                ),
            )

            day_signals = signals_by_day.get(trade_day)
            candidate_rows = self._select_candidate_rows(
                state=state,
                trade_day=trade_day,
                day_signals=day_signals,
                close_columns=close.columns,
                entries_allowed_by_breaker=entries_allowed_by_breaker,
                drawdown_allocation_scale=drawdown_allocation_scale,
                entries_allowed_by_regime=entries_allowed_by_regime,
                diagnostics=diagnostics,
            )

            # Quick Win 1 — anti-faux-départs : enregistrer les candidats
            # et filtrer ceux dont le breakout n'est pas confirmé.
            # P1 (2026-06-25) : les shorts ne sont plus exemptés.
            if candidate_rows and self._breakout_tracker is not None:
                trade_day_date = trade_day.date()
                all_symbols = [str(row["symbol"]) for row in candidate_rows]
                self._breakout_tracker.record_selections(all_symbols, trade_day_date)
                before = len(candidate_rows)
                candidate_rows = [
                    row for row in candidate_rows
                    if self._breakout_tracker.allow_entry(str(row["symbol"]))
                ]
                diagnostics.blocked_by_breakout += before - len(candidate_rows)

            # ── Force-close longs en régime défensif ──
            # Quand le régime passe en capital_preservation, les nouveaux longs
            # sont bloqués et des shorts sont ouverts. Les longs existants
            # doivent être liquidés pour éviter de porter les deux directions.
            if (
                getattr(cfg, "risk_config", None) is not None
                and getattr(cfg.risk_config, "close_longs_on_defensive_regime", False)
                and day_signals is not None
                and "side" in day_signals.columns
            ):
                n_sells = int((day_signals["side"] == "sell").sum())
                n_buys = int((day_signals["side"] == "buy").sum())
                # Régime défensif : shorts présents, pas de nouveaux longs
                if n_sells > 0 and n_buys == 0 and state.positions:
                    to_close = [
                        (sym, pos) for sym, pos in state.positions.items()
                        if getattr(pos, "side", "buy") == "buy"
                    ]
                    for symbol, position in to_close:
                        close_price = float(close.at[trade_day, symbol]) if symbol in close.columns else position.entry_price
                        if not (np.isfinite(close_price) and close_price > 0):
                            continue
                        abs_qty = abs(position.quantity)
                        pnl = compute_realized_pnl("buy", abs_qty, position.entry_price, close_price)
                        return_pct = compute_return_pct("buy", position.entry_price, close_price)
                        state.settled_cash += abs_qty * close_price
                        state.closed_trades.append({
                            "symbol": symbol,
                            "side": "buy",
                            "quantity": position.quantity,
                            "entry_date": position.entry_date,
                            "entry_price": position.entry_price,
                            "exit_date": trade_day,
                            "exit_price": close_price,
                            "pnl": pnl,
                            "return_pct": return_pct,
                            "holding_days": (trade_day - position.entry_date).days,
                            "exit_reason": "force_close_defensive_regime",
                            "sector": getattr(position, "sector", "Unknown"),
                        })
                        del state.positions[symbol]
                        LOGGER.info(
                            "BT force-close long (defensive regime): date=%s symbol=%s exit_price=%.2f pnl=%.2f",
                            trade_day.date(), symbol, close_price, pnl,
                        )
                    if to_close:
                        current_market_value = self._mark_to_market(state.positions, mtm_close, trade_day)
                        current_equity = state.settled_cash + state.unsettled_cash + current_market_value

            self._try_open_entries(
                state=state,
                candidate_rows=candidate_rows,
                open_df=open_df,
                high_df=high,
                low_df=low,
                close=close,
                trade_day=trade_day,
                day_idx=day_idx,
                trading_days=trading_days,
                adv_usd_df=adv_usd_df,
                sector_map=sector_map,
                current_equity=current_equity,
                drawdown_allocation_scale=drawdown_allocation_scale,
                diagnostics=diagnostics,
                spread_df=spread_df,
            )

            self._try_close_positions(
                state=state,
                close=close,
                high=high,
                low=low,
                trade_day=trade_day,
                day_idx=day_idx,
                trading_days=trading_days,
                adv_usd_df=adv_usd_df,
                rng=rng,
                diagnostics=diagnostics,
                spread_df=spread_df,
                current_equity=current_equity,
            )

            # Phase E.4 — single mark-to-market final pour equity du jour.
            market_value = self._mark_to_market(state.positions, mtm_close, trade_day)
            state.equity_points.append(state.settled_cash + state.unsettled_cash + market_value)

        equity_curve = pd.Series(
            state.equity_points, index=trading_days, name="portfolio_value", dtype=float
        )
        trades_df = pd.DataFrame(state.closed_trades)
        trade_events_df = pd.DataFrame(state.trade_events)
        breaker_df = pd.DataFrame(state.breaker_points) if state.breaker_points else pd.DataFrame()
        result = BacktestResult(
            equity_curve=equity_curve,
            closed_trades_df=trades_df,
            trade_events_df=trade_events_df,
            diagnostics=diagnostics,
            drawdown_breaker_df=breaker_df,
            tracker_snapshot=self.tracker_snapshot,
        )
        LOGGER.info(
            "Backtest contraint terminé — valeur finale : %.2f — diagnostics=%s — événements=%d",
            result.final_value(),
            diagnostics.to_dict(),
            len(trade_events_df),
        )
        return result

    # ------------------------------------------------------------------
    # Phase E.3 (refactor) — sous-méthodes du run constraint.
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_atr(
        high: pd.DataFrame,
        low: pd.DataFrame,
        close: pd.DataFrame,
        window: int = 20,
    ) -> pd.DataFrame:
        """Calcule l'ATR (Average True Range) sur ``window`` jours.

        Retourne un DataFrame de même shape que ``close``, avec l'ATR
        en dollars (pas en pourcentage). Utilisé par le trailing stop
        adaptatif (P1).
        """
        prev_close = close.shift(1).fillna(close)  # fallback: utilise close au lieu de NaN
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        # Combiner les trois true ranges en prenant le max par élément
        tr_combined = pd.DataFrame(
            np.maximum(np.maximum(tr1.values, tr2.values), tr3.values),
            index=close.index,
            columns=close.columns,
        )
        atr = tr_combined.rolling(window=window, min_periods=1).mean()
        return pd.DataFrame(atr, index=close.index, columns=close.columns)

    def _prepare_signals_by_day(
        self,
        signals_df: pd.DataFrame,
        trading_days: pd.DatetimeIndex,
    ) -> dict[pd.Timestamp, pd.DataFrame]:
        """Programme les signaux sur la séance d'exécution suivante (J+1 open)."""
        signals = signals_df.copy()
        signals["trade_date"] = pd.to_datetime(signals["trade_date"])
        if "rank" not in signals.columns:
            signals["rank"] = 1.0

        scheduled_signals = self._schedule_signals_for_execution(signals, trading_days)
        skipped_signals = len(signals) - len(scheduled_signals)
        if skipped_signals > 0:
            LOGGER.info(
                "Signaux ignorés faute de séance d'exécution suivante (J+1 open) : %d",
                skipped_signals,
            )
        if scheduled_signals.empty:
            return {}
        return {
            day: day_df.sort_values(["rank", "symbol"]).copy()
            for day, day_df in scheduled_signals.groupby("execution_date", sort=True)
        }

    def _apply_settlements(self, state: _RunState, day_idx: int) -> None:
        """Phase E.3 — règle T+N pour comptes cash : libère le cash settled."""
        settlement_amount = state.settlements_by_day.pop(day_idx, 0.0)
        if settlement_amount:
            state.settled_cash += settlement_amount
            state.unsettled_cash = max(state.unsettled_cash - settlement_amount, 0.0)

    def _select_candidate_rows(
        self,
        *,
        state: _RunState,
        trade_day: pd.Timestamp,
        day_signals: pd.DataFrame | None,
        close_columns: pd.Index,
        entries_allowed_by_breaker: bool,
        drawdown_allocation_scale: float,
        entries_allowed_by_regime: bool,
        diagnostics: BacktestDiagnostics,
    ) -> list[pd.Series]:
        """Phase E.3 — filtre les signaux du jour selon les overlays risk."""
        cfg = self.config
        if day_signals is None:
            return []
        # Sprint 2 — log les signaux shorts entrants
        n_sells_day = int((day_signals["side"] == "sell").sum()) if "side" in day_signals.columns else 0
        if n_sells_day > 0:
            LOGGER.info(
                "BT short signals received: date=%s total_signals=%d sells=%d available_slots=%d positions=%d",
                trade_day.date(), len(day_signals), n_sells_day,
                max(cfg.max_positions - len(state.positions), 0), len(state.positions),
            )
        available_slots = max(cfg.max_positions - len(state.positions), 0)
        filtered_rows = [
            row
            for _, row in day_signals.iterrows()
            if str(row["symbol"]) not in state.positions and str(row["symbol"]) in close_columns
        ]
        breaker_hard_blocked = (not entries_allowed_by_breaker) and drawdown_allocation_scale <= 0.0
        if breaker_hard_blocked or not entries_allowed_by_regime:
            blocked_count = int(max(cfg.max_positions - len(state.positions), 0))
            if breaker_hard_blocked:
                diagnostics.blocked_by_drawdown_breaker += blocked_count
            if not entries_allowed_by_regime:
                diagnostics.blocked_by_regime += blocked_count
            for row in filtered_rows[:available_slots]:
                self._record_trade_event(
                    state,
                    "entry_blocked_overlay",
                    event_date=trade_day,
                    symbol=str(row["symbol"]),
                    rejection_reason=(
                        "drawdown_breaker_and_regime_filter"
                        if (breaker_hard_blocked and not entries_allowed_by_regime)
                        else "drawdown_breaker"
                        if breaker_hard_blocked
                        else "regime_filter"
                    ),
                    **self._build_signal_context(row),
                )
            return []

        if available_slots <= 0:
            return []
        return filtered_rows[:available_slots]

    def _try_open_entries(
        self,
        *,
        state: _RunState,
        candidate_rows: list[pd.Series],
        open_df: pd.DataFrame,
        high_df: pd.DataFrame | None = None,
        low_df: pd.DataFrame,
        close: pd.DataFrame,
        trade_day: pd.Timestamp,
        day_idx: int,
        trading_days: pd.DatetimeIndex,
        adv_usd_df: pd.DataFrame | None,
        sector_map: dict[str, str],
        current_equity: float,
        drawdown_allocation_scale: float,
        diagnostics: BacktestDiagnostics,
        spread_df: pd.DataFrame | None = None,
    ) -> None:
        """Phase E.3 — ouvre les nouvelles positions (gap, sectoral, sizing, slippage)."""
        cfg = self.config
        constraints = cfg.trading_constraints
        micro = cfg.microstructure
        risk = cfg.risk_overlay

        if not candidate_rows:
            return

        cand_df = pd.DataFrame(candidate_rows)
        sizing_weights = risk.sizing.compute_weights(cand_df, cfg.max_positions)
        vol_target_scaler = 1.0
        if risk.target_annual_vol is not None and float(risk.target_annual_vol) > 0.0:
            equity_history = pd.Series(state.equity_points, dtype=float)
            vol_target_scaler = compute_portfolio_vol_scaler(
                equity_history.pct_change().dropna(),
                target_annual_vol=float(risk.target_annual_vol),
            )

        # Phase E.3.b — snapshot des expositions sectorielles courantes via
        # la primitive testable `snapshot_sector_exposure` (Phase C.4).
        sector_exposure_pct: dict[str, float] = defaultdict(float)
        if risk.sectoral_cap.enabled and current_equity > 0:
            from backtesting.risk_overlay import snapshot_sector_exposure
            sector_exposure_pct.update(
                snapshot_sector_exposure(
                    state.positions, close, trade_day, sector_map, current_equity
                )
            )
        gross_exposure_limit = self._resolve_max_gross_exposure_limit(float(current_equity))
        current_gross_notional = self._compute_gross_notional(state.positions, close, trade_day)

        for candidate_pos, row in enumerate(candidate_rows):
            symbol = str(row["symbol"])
            signal_context = self._build_signal_context(row)

            # Sprint 2 — direction
            side = str(row.get("side", "buy") or "buy").strip().lower()
            if side not in ("buy", "sell"):
                side = "buy"
            short = is_short_side(side)
            if short:
                LOGGER.info(
                    "BT short candidate: date=%s symbol=%s side=%s score=%.4f available_slots=%d",
                    trade_day.date(), symbol, side,
                    float(row.get("score", row.get("score_used", 0.0) or 0.0)),
                    len(candidate_rows) - candidate_pos,
                )

            # Quick Win 2 — score threshold (Sprint 2: skip pour shorts)
            if cfg.min_score_threshold > 0 and not short:
                score_val = float(row.get("score", row.get("score_used", 0.0) or 0.0))
                if score_val < cfg.min_score_threshold:
                    continue  # silently skip low-score candidates

            signal_price = float(open_df.at[trade_day, symbol])
            if not np.isfinite(signal_price) or signal_price <= 0:
                self._record_trade_event(
                    state,
                    "entry_rejected",
                    event_date=trade_day,
                    symbol=symbol,
                    rejection_reason="missing_entry_price",
                    attempted_entry_price=signal_price,
                    **signal_context,
                )
                continue

            # P4 — modèle d'exécution intraday : calcul du prix d'exécution estimé
            day_high_for_exec = float(high_df.at[trade_day, symbol]) if high_df is not None and symbol in high_df.columns else None
            day_low_for_exec = float(low_df.at[trade_day, symbol]) if symbol in low_df.columns else None
            day_close_for_exec = float(close.at[trade_day, symbol]) if symbol in close.columns else None
            exec_entry_price = compute_execution_price(
                model=micro.execution_model,
                side=side,
                open_price=signal_price,
                high_price=day_high_for_exec,
                low_price=day_low_for_exec,
                close_price=day_close_for_exec,
            )

            # Quick Win 3 — pullback entry (direction-aware)
            # Le pullback utilise le signal_price (open) comme référence, pas le prix d'exécution
            entry_price = exec_entry_price

            # ── P1 (2026-06-25) : slippage model pour backtest réaliste ──
            trade_spread_bps = self._get_spread_bps(
                spread_df, trade_day, symbol, fallback_bps=float(cfg.slippage_bps)
            )
            slippage_bps = 5.0 + trade_spread_bps / 2.0
            if is_short_side(side):
                entry_price = entry_price * (1.0 - slippage_bps / 10_000.0)
            else:
                entry_price = entry_price * (1.0 + slippage_bps / 10_000.0)

            if cfg.entry_limit_offset_pct > 0:
                limit_price = compute_pullback_limit_price(side, signal_price, float(cfg.entry_limit_offset_pct))
                if is_short_side(side):
                    # TODO(Sprint 3) : pour le short, vérifier day_high >= limit_price (nécessite high_df)
                    # Pour l'instant, short_selling_enabled=false donc ce chemin n'est pas emprunté.
                    entry_price = limit_price
                else:
                    day_low = float(low_df.at[trade_day, symbol]) if symbol in low_df.columns else None
                    if day_low is not None and np.isfinite(day_low) and day_low <= limit_price:
                        entry_price = limit_price
                    else:
                        self._record_trade_event(
                            state, "entry_rejected",
                            event_date=trade_day, symbol=symbol,
                            rejection_reason="pullback_limit_not_reached",
                            attempted_entry_price=signal_price,
                            limit_price=limit_price, side=side,
                            **signal_context,
                        )
                        continue

            quantity_override = (
                self._resolve_signal_quantity_override(row)
                if cfg.execution_replay_mode == "execution_replay"
                else None
            )

            # Phase B.3 — gap d'ouverture excessif.
            previous_close: float | None = None
            if day_idx > 0 and symbol in close.columns:
                prev_day = close.index[day_idx - 1]
                try:
                    previous_close = float(close.at[prev_day, symbol])
                except (KeyError, ValueError):
                    previous_close = None
            entry_gap_pct = (
                ((entry_price / previous_close) - 1.0)
                if previous_close is not None and previous_close > 0
                else None
            )
            if should_skip_entry_for_gap(
                previous_close, entry_price, max_gap_pct=micro.max_entry_gap_pct
            ):
                diagnostics.blocked_entry_gap += 1
                self._record_trade_event(
                    state,
                    "entry_rejected",
                    event_date=trade_day,
                    symbol=symbol,
                    rejection_reason="entry_gap_filter",
                    attempted_entry_price=entry_price,
                    previous_close=previous_close,
                    entry_gap_pct=entry_gap_pct,
                    max_entry_gap_pct=micro.max_entry_gap_pct,
                    **signal_context,
                )
                continue

            # Priorité 4 — concentration / anti-répétition
            trade_day_date = trade_day.date()
            if not self._concentration_trade_tracker.allow_entry(symbol, trade_day_date, side=side):
                diagnostics.blocked_by_concentration += 1
                self._record_trade_event(
                    state,
                    "entry_rejected",
                    event_date=trade_day,
                    symbol=symbol,
                    rejection_reason="concentration_max_trades_per_symbol",
                    max_trades=self._concentration_trade_tracker.max_trades,
                    window_days=self._concentration_trade_tracker.window_days,
                    **signal_context,
                )
                continue
            if self._concentration_loss_tracker.is_blacklisted(symbol, trade_day_date, side=side):
                diagnostics.blocked_by_blacklist += 1
                self._record_trade_event(
                    state,
                    "entry_rejected",
                    event_date=trade_day,
                    symbol=symbol,
                    rejection_reason="consecutive_loss_blacklist",
                    max_consecutive_losses=self._concentration_loss_tracker.max_consecutive_losses,
                    **signal_context,
                )
                continue

            signal_target_weight = self._resolve_signal_target_weight(row)
            if quantity_override is not None and signal_target_weight is not None:
                target_weight_pct = signal_target_weight
            else:
                target_weight_pct = (
                    float(sizing_weights.iloc[candidate_pos])
                    if not sizing_weights.empty and candidate_pos < len(sizing_weights)
                    else 1.0 / max(cfg.max_positions, 1)
                )
            if quantity_override is None and vol_target_scaler != 1.0:
                target_weight_pct = float(np.clip(target_weight_pct * vol_target_scaler, 0.0, 1.0))
            if drawdown_allocation_scale < 1.0:
                target_weight_pct = float(np.clip(target_weight_pct * drawdown_allocation_scale, 0.0, 1.0))
            if quantity_override is None:
                target_weight_pct *= self._resolve_margin_buying_power_multiplier(float(current_equity), drawdown_scale=drawdown_allocation_scale)

            sector = (
                str(row["sector"])
                if "sector" in row and pd.notna(row.get("sector"))
                else sector_map.get(symbol, "Unknown")
            )
            if not risk.sectoral_cap.is_entry_allowed(
                sector, sector_exposure_pct.get(sector, 0.0), target_weight_pct
            ):
                diagnostics.blocked_by_sectoral_cap += 1
                self._record_trade_event(
                    state,
                    "entry_rejected",
                    event_date=trade_day,
                    symbol=symbol,
                    rejection_reason="sectoral_cap",
                    sector=sector,
                    sector_exposure_pct=sector_exposure_pct.get(sector, 0.0),
                    target_weight_pct=target_weight_pct,
                    vol_target_scaler=vol_target_scaler,
                    max_sector_exposure_pct=risk.sectoral_cap.max_sector_exposure_pct,
                    **signal_context,
                )
                continue

            remaining_candidates = max(len(candidate_rows) - candidate_pos, 1)
            per_position_cap = current_equity * target_weight_pct
            available_entry_budget = self._resolve_available_entry_budget(
                constraints=constraints,
                settled_cash=state.settled_cash,
                current_equity=current_equity,
                current_gross_notional=current_gross_notional,
            )
            candidate_budget = min(per_position_cap, available_entry_budget / remaining_candidates)
            settled_cash_before_entry = state.settled_cash
            gross_exposure_before_pct = (
                (current_gross_notional / current_equity)
                if current_equity > 0
                else 0.0
            )

            preliminary_size_usd = max(
                float(quantity_override) * entry_price if quantity_override is not None else candidate_budget,
                0.0,
            )
            adv_usd = self._get_adv_usd(adv_usd_df, trade_day, symbol)
            extra_slippage_pct = micro.slippage.compute_bps(preliminary_size_usd, adv_usd) / 10_000.0
            # P1 — spread réel par ticker comme coût de transaction
            spread_cost_pct = self._get_spread_bps(
                spread_df, trade_day, symbol, fallback_bps=float(cfg.slippage_bps)
            ) / 10_000.0
            # P3 — commission tiered ou plate
            if cfg.use_tiered_commission:
                commission_config = resolve_commission_preset(float(current_equity))
                # Pour le calcul préliminaire, on utilise le taux seul (le fixe sera ajouté après)
                commission_rate_pct = commission_config.bps_rate / 10_000.0
                base_cost_pct = commission_rate_pct + (cfg.slippage_bps / 10_000.0) + extra_slippage_pct + spread_cost_pct
            else:
                base_cost_pct = cfg.fees_pct + extra_slippage_pct + spread_cost_pct
            effective_unit_cost = entry_price * (1.0 + base_cost_pct)
            if quantity_override is not None:
                affordable_quantity = (
                    self._normalize_trade_quantity(available_entry_budget / effective_unit_cost)
                    if effective_unit_cost > 0
                    else 0.0
                )
                quantity = min(self._normalize_trade_quantity(quantity_override), affordable_quantity)
                if drawdown_allocation_scale < 1.0 and effective_unit_cost > 0:
                    degraded_budget_quantity = self._normalize_trade_quantity(candidate_budget / effective_unit_cost)
                    quantity = min(quantity, degraded_budget_quantity)
            else:
                quantity = self._normalize_trade_quantity(candidate_budget / effective_unit_cost)
            quantity = self._normalize_trade_quantity(quantity)
            quantity_before_gross_exposure_cap = quantity
            gross_exposure_cap_binds = False

            if gross_exposure_limit is not None and current_equity > 0 and entry_price > 0:
                remaining_gross_notional = max(
                    (gross_exposure_limit * current_equity) - current_gross_notional,
                    0.0,
                )
                max_quantity_for_gross_exposure = self._normalize_trade_quantity(remaining_gross_notional / entry_price)
                quantity = min(quantity, max_quantity_for_gross_exposure)
                quantity = self._normalize_trade_quantity(quantity)
                gross_exposure_cap_binds = quantity < quantity_before_gross_exposure_cap

            if quantity <= QUANTITY_EPSILON:
                if gross_exposure_cap_binds:
                    diagnostics.blocked_by_gross_exposure += 1
                    self._record_trade_event(
                        state,
                        "entry_rejected",
                        event_date=trade_day,
                        symbol=symbol,
                        rejection_reason="gross_exposure_cap",
                        settled_cash_before=settled_cash_before_entry,
                        candidate_budget=candidate_budget,
                        target_weight_pct=target_weight_pct,
                        vol_target_scaler=vol_target_scaler,
                        quantity_override=quantity_override,
                        effective_unit_cost=effective_unit_cost,
                        gross_exposure_limit_pct=gross_exposure_limit,
                        gross_exposure_before_pct=gross_exposure_before_pct,
                        gross_exposure_remaining_notional=max(
                            (gross_exposure_limit * current_equity) - current_gross_notional,
                            0.0,
                        ),
                        **signal_context,
                    )
                    continue
                if constraints.use_settled_cash_only:
                    diagnostics.blocked_cash_entries += 1
                self._record_trade_event(
                    state,
                    "entry_rejected",
                    event_date=trade_day,
                    symbol=symbol,
                    rejection_reason="insufficient_cash_for_quantity",
                    settled_cash_before=settled_cash_before_entry,
                    candidate_budget=candidate_budget,
                    target_weight_pct=target_weight_pct,
                    vol_target_scaler=vol_target_scaler,
                    quantity_override=quantity_override,
                    effective_unit_cost=effective_unit_cost,
                    **signal_context,
                )
                continue

            entry_cost = quantity * effective_unit_cost
            if entry_cost > available_entry_budget:
                if constraints.use_settled_cash_only:
                    diagnostics.blocked_cash_entries += 1
                self._record_trade_event(
                    state,
                    "entry_rejected",
                    event_date=trade_day,
                    symbol=symbol,
                    rejection_reason="entry_cost_exceeds_cash",
                    settled_cash_before=settled_cash_before_entry,
                    candidate_budget=candidate_budget,
                    quantity=quantity,
                    entry_cost=entry_cost,
                    available_entry_budget=available_entry_budget,
                    effective_unit_cost=effective_unit_cost,
                    **signal_context,
                )
                continue

            # Sprint 2 — direction-aware cash and position creation
            quantity_abs = abs(quantity)
            # P3 — ajout de la commission fixe tiered après détermination de la quantité
            entry_notional = quantity_abs * entry_price
            if cfg.use_tiered_commission:
                tiered_fixed = commission_config.fixed_per_trade_usd
                effective_cost_pct = base_cost_pct
            else:
                tiered_fixed = 0.0
                effective_cost_pct = base_cost_pct

            if is_short_side(side):
                # Short sale: credit cash (proceeds from short selling)
                # P1+P3 — cost inclut commission tiered + slippage volume + spread réel
                short_credit = quantity_abs * entry_price * (1.0 - effective_cost_pct) - tiered_fixed
                state.settled_cash += short_credit
            else:
                state.settled_cash -= entry_cost + tiered_fixed

            initial_stop_price, risk_per_share = self._resolve_initial_protection_state(
                row=row,
                entry_price=entry_price,
                fallback_initial_stop_pct=micro.initial_stop_pct,
                side=side,
            )
            state.positions[symbol] = _OpenPosition(
                symbol=symbol,
                side=side,
                signal_date=pd.Timestamp(row["signal_date"]),
                entry_date=trade_day,
                entry_idx=day_idx,
                entry_price=entry_price,
                quantity=quantity,
                peak_high=entry_price,
                trough_low=entry_price,
                entry_cost=entry_cost,
                initial_stop_price=initial_stop_price,
                risk_per_share=risk_per_share,
                replay_take_profit_price=(
                    self._resolve_signal_float(row, "replay_take_profit_price")
                    if cfg.protection_replay_mode == "protection_replay"
                    else None
                ),
                replay_initial_stop_price=(
                    self._resolve_signal_float(row, "replay_initial_stop_price")
                    if cfg.protection_replay_mode == "protection_replay"
                    else None
                ),
                replay_trailing_stop_pct=(
                    self._resolve_signal_float(row, "replay_trailing_stop_pct")
                    if cfg.protection_replay_mode == "protection_replay"
                    else None
                ),
                replay_trailing_activation_price=(
                    self._resolve_signal_float(row, "replay_trailing_activation_price")
                    if cfg.protection_replay_mode == "protection_replay"
                    else None
                ),
                replay_trailing_activation_mode=(
                    self._resolve_signal_text(row, "replay_trailing_activation_mode")
                    if cfg.protection_replay_mode == "protection_replay"
                    else None
                ),
                watcher_transition_state=(
                    self._resolve_signal_text(row, "watcher_transition_state")
                    if cfg.watcher_replay_mode == "watcher_replay"
                    else None
                ),
                watcher_trigger_date=(
                    self._resolve_signal_timestamp(row, "watcher_trigger_date")
                    if cfg.watcher_replay_mode == "watcher_replay"
                    else None
                ),
                watcher_transition_effective_date=(
                    self._resolve_signal_timestamp(row, "watcher_transition_effective_date")
                    if cfg.watcher_replay_mode == "watcher_replay"
                    else None
                ),
                explicit_exit_date=(
                    self._resolve_signal_timestamp(row, "replay_exit_date")
                    if cfg.exit_lifecycle_replay_mode == "exit_lifecycle_replay"
                    else None
                ),
                explicit_exit_price=(
                    self._resolve_signal_float(row, "replay_exit_price")
                    if cfg.exit_lifecycle_replay_mode == "exit_lifecycle_replay"
                    else None
                ),
                explicit_exit_reason=(
                    self._resolve_signal_text(row, "replay_exit_reason")
                    if cfg.exit_lifecycle_replay_mode == "exit_lifecycle_replay"
                    else None
                ),
                explicit_exit_intent_role=(
                    self._resolve_signal_text(row, "replay_exit_intent_role")
                    if cfg.exit_lifecycle_replay_mode == "exit_lifecycle_replay"
                    else None
                ),
                explicit_oco_sibling_canceled=(
                    self._resolve_signal_bool(row, "replay_oco_sibling_canceled")
                    if cfg.exit_lifecycle_replay_mode == "exit_lifecycle_replay"
                    else False
                ),
                sector=sector,
                signal_context=signal_context,
            )
            if risk.sectoral_cap.enabled:
                sector_exposure_pct[sector] += target_weight_pct
            current_gross_notional += quantity * entry_price
            self._record_trade_event(
                state,
                "entry_opened",
                event_date=trade_day,
                symbol=symbol,
                side=side,
                sector=sector,
                quantity=quantity,
                entry_price=entry_price,
                entry_cost=entry_cost,
                effective_unit_cost=effective_unit_cost,
                target_weight_pct=target_weight_pct,
                vol_target_scaler=vol_target_scaler,
                candidate_budget=candidate_budget,
                available_entry_budget=available_entry_budget,
                settled_cash_before=settled_cash_before_entry,
                settled_cash_after=state.settled_cash,
                quantity_override=quantity_override,
                gross_exposure_limit_pct=gross_exposure_limit,
                gross_exposure_before_pct=gross_exposure_before_pct,
                gross_exposure_after_pct=(current_gross_notional / current_equity) if current_equity > 0 else 0.0,
                gross_exposure_capped=gross_exposure_cap_binds,
                previous_close=previous_close,
                entry_gap_pct=entry_gap_pct,
                **signal_context,
            )
            # Priorité 4 — enregistrer l'entrée dans le tracker de concentration
            self._concentration_trade_tracker.record(symbol, trade_day.date(), side=side)

    def _try_close_positions(
        self,
        *,
        state: _RunState,
        close: pd.DataFrame,
        high: pd.DataFrame,
        low: pd.DataFrame,
        trade_day: pd.Timestamp,
        day_idx: int,
        trading_days: pd.DatetimeIndex,
        adv_usd_df: pd.DataFrame | None,
        rng: np.random.Generator | None,
        diagnostics: BacktestDiagnostics,
        spread_df: pd.DataFrame | None = None,
        current_equity: float = 0.0,
        atr_df: pd.DataFrame | None = None,
    ) -> None:
        """Phase E.3 — résout les sorties (TP/TS/initial stop) et applique le settlement."""
        cfg = self.config
        constraints = cfg.trading_constraints
        micro = cfg.microstructure

        symbols_to_close: list[str] = []
        for symbol, position in state.positions.items():
            day_high = float(high.at[trade_day, symbol])
            day_low = float(low.at[trade_day, symbol])
            if not np.isfinite(day_high) or not np.isfinite(day_low):
                continue

            # Sprint 2 — direction-aware state
            side = getattr(position, "side", "buy") or "buy"
            short = is_short_side(side)

            previous_peak_high = position.peak_high
            peak_high = max(previous_peak_high or 0.0, day_high)
            previous_trough_low = getattr(position, "trough_low", position.entry_price) or position.entry_price
            trough_low = min(previous_trough_low or float("inf"), day_low)
            explicit_resolution = None
            if (
                cfg.exit_lifecycle_replay_mode == "exit_lifecycle_replay"
                and position.explicit_exit_date is not None
                and position.explicit_exit_price is not None
                and position.explicit_exit_reason is not None
            ):
                if trade_day.normalize() == position.explicit_exit_date.normalize():
                    explicit_resolution = {
                        "exit_price": float(position.explicit_exit_price),
                        "exit_reason": str(position.explicit_exit_reason),
                    }
                else:
                    position.peak_high = peak_high
                    position.trough_low = trough_low
                    continue
            if cfg.protection_replay_mode == "protection_replay" and self._position_uses_replayed_protection(position):
                take_profit_price = (
                    position.replay_take_profit_price
                    if position.replay_take_profit_price is not None
                    else position.entry_price * (1.0 + cfg.profit_taker_pct)
                )
                if cfg.watcher_replay_mode == "watcher_replay":
                    if (
                        not position.replay_trailing_active
                        and position.watcher_transition_effective_date is not None
                        and trade_day.normalize() >= position.watcher_transition_effective_date.normalize()
                    ):
                        position.replay_trailing_active = True
                        diagnostics.watcher_replay_transitions += 1
                        diagnostics.protection_replay_activations += 1
                        self._record_trade_event(
                            state,
                            "watcher_transition",
                            event_date=trade_day,
                            symbol=symbol,
                            trigger_date=position.watcher_trigger_date,
                            effective_date=position.watcher_transition_effective_date,
                            transition_state=position.watcher_transition_state or "transitioned",
                            trailing_stop_pct=position.replay_trailing_stop_pct,
                            **position.signal_context,
                        )
                else:
                    if (
                        not position.replay_trailing_active
                        and position.replay_trailing_activation_price is not None
                        and day_high >= position.replay_trailing_activation_price
                    ):
                        position.replay_trailing_active = True
                        diagnostics.protection_replay_activations += 1
                        self._record_trade_event(
                            state,
                            "protection_activated",
                            event_date=trade_day,
                            symbol=symbol,
                            activation_reason="trailing_activation_price",
                            trigger_price=position.replay_trailing_activation_price,
                            trailing_stop_pct=position.replay_trailing_stop_pct,
                            **position.signal_context,
                        )
                trailing_stop_pct = (
                    position.replay_trailing_stop_pct
                    if position.replay_trailing_active and position.replay_trailing_stop_pct is not None
                    else None
                )
                trailing_stop_price = (
                    previous_peak_high * (1.0 - trailing_stop_pct)
                    if trailing_stop_pct is not None
                    else float("-inf")
                )
                active_initial_stop = (
                    None
                    if position.replay_trailing_active
                    else (position.replay_initial_stop_price or position.initial_stop_price)
                )
            else:
                # Sprint 2 — direction-aware protection prices
                if cfg.use_live_protection_logic:
                    percent_target = compute_take_profit_price(side, position.entry_price, float(cfg.profit_taker_pct))
                    risk_based_target = None
                    if position.risk_per_share is not None and position.risk_per_share > 0 and position.entry_price > 0:
                        sign = -1 if short else 1
                        risk_based_target = position.entry_price + sign * (2.0 * position.risk_per_share)
                    if risk_based_target is not None:
                        take_profit_price = max(percent_target, risk_based_target) if not short else min(percent_target, risk_based_target)
                    else:
                        take_profit_price = percent_target
                    if (
                        position.initial_stop_price is not None
                        and position.entry_price > 0
                    ):
                        trailing_stop_pct = (
                            abs(position.entry_price - position.initial_stop_price) / position.entry_price
                        )
                    elif position.risk_per_share is not None and position.risk_per_share > 0 and position.entry_price > 0:
                        trailing_stop_pct = position.risk_per_share / position.entry_price
                    else:
                        trailing_stop_pct = float(cfg.trailing_stop_pct)
                    trailing_ref = (previous_trough_low if short else previous_peak_high)
                    trailing_stop_price = compute_trailing_stop_price(side, trailing_ref, trailing_stop_pct)
                else:
                    take_profit_price = compute_take_profit_price(side, position.entry_price, float(cfg.profit_taker_pct))
                    trailing_ref = (previous_trough_low if short else previous_peak_high)
                    trailing_stop_price = compute_trailing_stop_price(side, trailing_ref, float(cfg.trailing_stop_pct))
                # ── P1 — ATR-based trailing stop override ──
                if cfg.atr_trailing_stop_multiplier > 0 and atr_df is not None and symbol in atr_df.columns:
                    atr_value = float(atr_df.at[trade_day, symbol])
                    if np.isfinite(atr_value) and atr_value > 0:
                        sign = -1 if short else 1
                        atr_distance = float(cfg.atr_trailing_stop_multiplier) * atr_value
                        atr_stop_price = round(trailing_ref - sign * atr_distance, 4)
                        # Prendre le stop le plus large des deux (fixe vs ATR)
                        if not short:
                            trailing_stop_price = min(trailing_stop_price, atr_stop_price)
                        else:
                            trailing_stop_price = max(trailing_stop_price, atr_stop_price)
                active_initial_stop = position.initial_stop_price
            is_same_day = trade_day.normalize() == position.entry_date.normalize()

            if explicit_resolution is None:
                resolution = resolve_intrabar_exit(
                    day_high=day_high,
                    day_low=day_low,
                    take_profit_price=take_profit_price,
                    trailing_stop_price=trailing_stop_price,
                    initial_stop_price=active_initial_stop,
                    priority=micro.intrabar_priority,
                    side=side,
                    rng=rng,
                )
                if not resolution.triggered:
                    if self.config.time_stop_enabled:
                        close_price = float(close.at[trade_day, symbol])
                        if np.isfinite(close_price) and close_price > 0:
                            holding_business_days = int(day_idx - position.entry_idx)
                            if holding_business_days >= int(self.config.time_stop_max_business_days):
                                # Sprint 2 — direction-aware time stop
                                if short:
                                    objective_move = max(position.entry_price - take_profit_price, 0.0)
                                    current_move = max(position.entry_price - close_price, 0.0)
                                else:
                                    objective_move = max(take_profit_price - position.entry_price, 0.0)
                                    current_move = max(close_price - position.entry_price, 0.0)
                                tp_progress = (
                                    (current_move / objective_move)
                                    if objective_move > 0
                                    else 0.0
                                )
                                close_return_pct = compute_return_pct(side, position.entry_price, close_price)
                                if (
                                    tp_progress < float(self.config.time_stop_min_tp_progress_ratio)
                                    or abs(close_return_pct) <= float(self.config.time_stop_near_zero_return_pct)
                                ):
                                    exit_price = close_price
                                    exit_reason = "time_stop"
                                else:
                                    position.peak_high = peak_high
                                    position.trough_low = trough_low
                                    continue
                            else:
                                position.peak_high = peak_high
                                position.trough_low = trough_low
                                continue
                        else:
                            position.peak_high = peak_high
                            position.trough_low = trough_low
                            continue
                    else:
                        position.peak_high = peak_high
                        position.trough_low = trough_low
                        continue
                else:
                    exit_price = resolution.exit_price
                    exit_reason = resolution.exit_reason
            else:
                exit_price = float(explicit_resolution["exit_price"])
                exit_reason = str(explicit_resolution["exit_reason"])

            if is_same_day and constraints.restrict_same_day_exit:
                diagnostics.blocked_same_day_exits += 1
                position.peak_high = peak_high
                position.trough_low = trough_low
                continue

            if exit_reason == "take_profit":
                diagnostics.take_profit_exits += 1
            elif exit_reason == "trailing_stop":
                diagnostics.trailing_stop_exits += 1
            elif exit_reason == "initial_stop":
                diagnostics.initial_stop_exits += 1
            elif exit_reason == "time_stop":
                diagnostics.time_stop_exits += 1
            if explicit_resolution is not None:
                diagnostics.exit_lifecycle_replayed += 1

            # Sprint 2 — direction-aware PnL and settlement
            abs_qty = abs(position.quantity)
            exit_notional = abs_qty * exit_price
            adv_usd = self._get_adv_usd(adv_usd_df, trade_day, symbol)
            extra_slippage_pct = micro.slippage.compute_bps(exit_notional, adv_usd) / 10_000.0
            # P1 — spread réel par ticker comme coût de sortie
            spread_cost_pct = self._get_spread_bps(
                spread_df, trade_day, symbol, fallback_bps=float(cfg.slippage_bps)
            ) / 10_000.0
            # P3 — commission tiered ou plate en sortie
            if cfg.use_tiered_commission:
                exit_commission_config = resolve_commission_preset(float(current_equity))
                exit_commission_rate_pct = exit_commission_config.bps_rate / 10_000.0
                fees_rate = exit_commission_rate_pct + (cfg.slippage_bps / 10_000.0) + extra_slippage_pct + spread_cost_pct
                exit_fixed_commission = exit_commission_config.fixed_per_trade_usd
            else:
                fees_rate = float(cfg.fees_pct) + extra_slippage_pct + spread_cost_pct
                exit_fixed_commission = 0.0

            if short:
                # Short exit = buy back → cost = qty * exit_price * (1 + fees) + fixed
                exit_cost = abs_qty * exit_price * (1.0 + fees_rate) + exit_fixed_commission
                proceeds = -exit_cost  # negative cash flow (buy to cover)
                if constraints.use_settled_cash_only:
                    settlement_day_idx = day_idx + constraints.cash_settlement_days
                    state.unsettled_cash -= exit_cost
                    if settlement_day_idx < len(trading_days):
                        state.settlements_by_day[settlement_day_idx] -= exit_cost
                else:
                    state.settled_cash -= exit_cost
            else:
                # Long exit = sell → proceeds = qty * exit_price * (1 - fees) - fixed
                proceeds = abs_qty * exit_price * (1.0 - fees_rate) - exit_fixed_commission
                if constraints.use_settled_cash_only:
                    settlement_day_idx = day_idx + constraints.cash_settlement_days
                    state.unsettled_cash += proceeds
                    if settlement_day_idx < len(trading_days):
                        state.settlements_by_day[settlement_day_idx] += proceeds
                else:
                    state.settled_cash += proceeds

            pnl = compute_realized_pnl(side, abs_qty, position.entry_price, exit_price, fees=0.0)
            return_pct = compute_return_pct(side, position.entry_price, exit_price)
            holding_days = int((trade_day - position.entry_date).days)

            # ── Sprint 3 / Point 12 : borrow fee pour shorts ──────────
            borrow_cost = 0.0
            if short and self._cost_model.borrow_fee_annual > 0 and holding_days > 0:
                holding_sessions = max(1, holding_days)  # ~1 session par jour calendaire
                borrow_cost_pct = self._cost_model.borrow_cost_for_holding(
                    holding_sessions, sessions_per_year=252,
                )
                # Coût du borrow sur le notional de la position
                entry_notional = abs_qty * position.entry_price
                borrow_cost = entry_notional * borrow_cost_pct
                pnl -= borrow_cost
                # Déduire aussi du cash settled
                if constraints.use_settled_cash_only:
                    state.unsettled_cash -= borrow_cost
                else:
                    state.settled_cash -= borrow_cost

            is_day_trade = is_same_day
            if is_day_trade:
                diagnostics.executed_day_trades += 1

            state.closed_trades.append(
                {
                    "symbol": symbol,
                    "side": side,
                    "sector": position.sector,
                    "signal_date": position.signal_date,
                    "quantity": position.quantity,
                    "entry_date": position.entry_date,
                    "exit_date": trade_day,
                    "entry_price": position.entry_price,
                    "exit_price": exit_price,
                    "entry_cost": position.entry_cost,
                    "proceeds": proceeds,
                    "pnl": pnl,
                    "return_pct": return_pct,
                    "holding_days": holding_days,
                    "borrow_cost": borrow_cost,  # Sprint 3 / Point 12
                    "exit_reason": exit_reason,
                    "exit_source": "explicit_replay" if explicit_resolution is not None else "intrabar_resolution",
                    "exit_intent_role": position.explicit_exit_intent_role,
                    "oco_sibling_canceled": (
                        position.explicit_oco_sibling_canceled if explicit_resolution is not None else False
                    ),
                    "is_day_trade": is_day_trade,
                    **position.signal_context,
                }
            )
            self._record_trade_event(
                state,
                "exit_closed",
                event_date=trade_day,
                symbol=symbol,
                side=side,
                sector=position.sector,
                entry_date=position.entry_date,
                entry_price=position.entry_price,
                quantity=position.quantity,
                exit_price=exit_price,
                exit_reason=exit_reason,
                exit_source="explicit_replay" if explicit_resolution is not None else "intrabar_resolution",
                proceeds=proceeds,
                pnl=pnl,
                return_pct=return_pct,
                holding_days=holding_days,
                is_day_trade=is_day_trade,
                settled_cash_after=state.settled_cash,
                unsettled_cash_after=state.unsettled_cash,
                **position.signal_context,
            )
            # Priorité 4 — enregistrer le PnL dans le tracker de pertes consécutives
            self._concentration_loss_tracker.record(symbol, pnl, trade_day.date(), side=side)
            symbols_to_close.append(symbol)

        for symbol in symbols_to_close:
            state.positions.pop(symbol, None)

    @staticmethod
    def _get_spread_bps(
        spread_df: pd.DataFrame | None,
        trade_day: pd.Timestamp,
        symbol: str,
        *,
        fallback_bps: float = 1.0,  # Alpaca : spread réel ~1-2 bps pour actions liquides
    ) -> float:
        """Lookup du spread bid-ask réel en bps pour un ticker/jour donné.

        Priorité :
        1. Donnée réelle depuis ``stock_quote_snapshots`` (spread_df pivoté).
        2. Fallback à ``fallback_bps`` si la donnée est absente.

        La valeur retournée est toujours >= 0.
        """
        if spread_df is None or spread_df.empty:
            return max(float(fallback_bps), 0.0)
        if symbol not in spread_df.columns or trade_day not in spread_df.index:
            return max(float(fallback_bps), 0.0)
        try:
            value = float(spread_df.at[trade_day, symbol])
            if np.isfinite(value) and value >= 0:
                return value
            return max(float(fallback_bps), 0.0)
        except (KeyError, ValueError):
            return max(float(fallback_bps), 0.0)

    @staticmethod
    def _get_adv_usd(
        adv_usd_df: pd.DataFrame | None,
        trade_day: pd.Timestamp,
        symbol: str,
    ) -> float | None:
        """Lookup ADV en USD pour la journée donnée (None si indisponible)."""
        if adv_usd_df is None or symbol not in adv_usd_df.columns or trade_day not in adv_usd_df.index:
            return None
        try:
            return float(adv_usd_df.at[trade_day, symbol])
        except (KeyError, ValueError):
            return None

    def _resolve_signal_quantity_override(self, row: pd.Series) -> float | None:
        """Retourne une quantité explicite issue du signal, si disponible."""
        for column_name in ("filled_qty", "approved_shares", "target_shares"):
            if column_name not in row.index:
                continue
            value = row.get(column_name)
            if value is None or pd.isna(value):
                continue
            try:
                quantity = self._normalize_trade_quantity(float(value))
            except (TypeError, ValueError):
                continue
            if quantity > QUANTITY_EPSILON:
                return quantity
        return None

    @staticmethod
    def _resolve_signal_target_weight(row: pd.Series) -> float | None:
        """Retourne un target_weight explicite issu du signal, si disponible."""
        if "target_weight" not in row.index:
            return None
        value = row.get("target_weight")
        if value is None or pd.isna(value):
            return None
        try:
            target_weight = float(value)
        except (TypeError, ValueError):
            return None
        return target_weight if target_weight > 0 else None

    @staticmethod
    def _resolve_signal_float(row: pd.Series, column_name: str) -> float | None:
        if column_name not in row.index:
            return None
        value = row.get(column_name)
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _resolve_initial_protection_state(
        self,
        *,
        row: pd.Series,
        entry_price: float,
        fallback_initial_stop_pct: float,
        side: str = "buy",
    ) -> tuple[float | None, float | None]:
        """Résout le stop initial/risk_per_share selon le mode live-like ou fixe.

        Sprint 2 — direction-aware : pour un short, le stop est au-dessus du prix.
        """
        risk_per_share = self._resolve_signal_float(row, "risk_per_share")
        stop_price_initial = self._resolve_signal_float(row, "stop_price_initial")
        short = is_short_side(side)

        if self.config.use_live_protection_logic and entry_price > 0:
            if (
                stop_price_initial is not None
                and stop_price_initial > 0
            ):
                # Direction-aware: for long stop < entry, for short stop > entry
                if not short and stop_price_initial < entry_price:
                    return stop_price_initial, risk_per_share
                if short and stop_price_initial > entry_price:
                    return stop_price_initial, risk_per_share
            if risk_per_share is not None and risk_per_share > 0:
                sign = -1 if short else 1
                derived_stop = entry_price - sign * risk_per_share
                if (not short and 0 < derived_stop < entry_price) or (short and derived_stop > entry_price):
                    return derived_stop, risk_per_share
            return None, risk_per_share

        if fallback_initial_stop_pct > 0 and entry_price > 0:
            sign = -1 if short else 1
            return entry_price * (1.0 - sign * fallback_initial_stop_pct), risk_per_share
        return None, risk_per_share

    @staticmethod
    def _resolve_signal_text(row: pd.Series, column_name: str) -> str | None:
        if column_name not in row.index:
            return None
        value = row.get(column_name)
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _resolve_signal_timestamp(row: pd.Series, column_name: str) -> pd.Timestamp | None:
        if column_name not in row.index:
            return None
        value = row.get(column_name)
        if value is None or pd.isna(value):
            return None
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError):
            return None
        return None if pd.isna(timestamp) else timestamp

    @staticmethod
    def _resolve_signal_bool(row: pd.Series, column_name: str) -> bool:
        if column_name not in row.index:
            return False
        value = row.get(column_name)
        if value is None or pd.isna(value):
            return False
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        return text in {"1", "true", "yes", "oui"}

    @staticmethod
    def _position_uses_replayed_protection(position: _OpenPosition) -> bool:
        return any(
            value is not None
            for value in (
                position.replay_take_profit_price,
                position.replay_initial_stop_price,
                position.replay_trailing_stop_pct,
                position.replay_trailing_activation_price,
            )
        )

    def _resolve_max_gross_exposure_limit(self, current_equity: float) -> float | None:
        leverage_limit = self._resolve_margin_buying_power_multiplier(float(current_equity))
        limit: float | None = leverage_limit if leverage_limit > 1.0 else None
        if self.config.risk_config is not None:
            risk_limit = float(self.config.risk_config.max_gross_exposure)
            if 0 < risk_limit < 1.0:
                limit = risk_limit
            elif leverage_limit > 1.0 and risk_limit > 1.0:
                limit = min(limit, risk_limit) if limit is not None else risk_limit
        if self.config.exec_config is not None:
            exec_limit = getattr(self.config.exec_config, "regime_max_gross_exposure", None)
            if exec_limit is not None:
                exec_limit = float(exec_limit)
                if exec_limit > 0:
                    limit = min(limit, exec_limit) if limit is not None else exec_limit
        return limit

    @staticmethod
    def _mark_to_market(
        positions: dict[str, _OpenPosition],
        close: pd.DataFrame,
        trade_day: pd.Timestamp,
    ) -> float:
        """Phase E.4 — calcule la valeur de marché nette des positions ouvertes.

        Longs : +qty * px (positive)
        Shorts : -qty * px (négative, car due au broker)
        """
        if not positions:
            return 0.0
        total = 0.0
        for position in positions.values():
            try:
                px = float(close.at[trade_day, position.symbol])
                if np.isfinite(px):
                    sign = -1 if is_short_side(getattr(position, "side", "buy") or "buy") else 1
                    total += sign * abs(position.quantity) * px
            except (KeyError, ValueError):
                continue
        return total

    @staticmethod
    def _compute_gross_notional(
        positions: dict[str, _OpenPosition],
        close: pd.DataFrame,
        trade_day: pd.Timestamp,
    ) -> float:
        """Phase E.4 — exposition brute = somme des |qty| * px, toujours positive."""
        if not positions:
            return 0.0
        total = 0.0
        for position in positions.values():
            try:
                px = float(close.at[trade_day, position.symbol])
                if np.isfinite(px):
                    total += abs(position.quantity) * px
            except (KeyError, ValueError):
                continue
        return total



