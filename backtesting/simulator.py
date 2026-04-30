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

from backtesting.trading_constraints import TradingConstraintConfig
from backtesting.microstructure import (
    MicrostructureConfig,
    SlippageConfig,
    compute_adv_usd,
    resolve_intrabar_exit,
    should_skip_entry_for_gap,
)
from backtesting.risk_overlay import RiskOverlayConfig
from risk_management.config import RiskConfig
from execution_engine.config import ExecutionConfig

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
    max_positions: int = 20

    # Frais de transaction (Phase 6.1.b)
    # ``fees_pct`` reste le scalaire effectif appliqué par l'engine
    # (= commission + slippage / 10_000).
    fees_pct: float = 0.001  # 10 bps
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    trading_constraints: TradingConstraintConfig = field(default_factory=TradingConstraintConfig)
    execution_timing: str = "next_open"
    # Phase B (refactor) — micro-structure (slippage volume-aware,
    # initial stop, gap filter, intrabar priority).
    microstructure: MicrostructureConfig = field(default_factory=MicrostructureConfig)
    # Phase C (refactor) — surcouches risk (sizing, regime, sectoral, DD breaker).
    risk_overlay: RiskOverlayConfig = field(default_factory=RiskOverlayConfig)
    # Phase C.3 / D.1 — benchmark (utilisé par le filtre régime + métriques).
    benchmark_close: pd.Series | None = None
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.risk_config:
            self.max_positions = self.risk_config.max_positions
        if self.exec_config:
            self.profit_taker_pct = self.exec_config.profit_taker_pct
            self.trailing_stop_pct = self.exec_config.trailing_stop_pct


@dataclass(slots=True)
class BacktestDiagnostics:
    """Compteurs métier utiles quand des contraintes de compte sont actives."""

    blocked_same_day_exits: int = 0
    blocked_pdt_day_trades: int = 0
    blocked_cash_entries: int = 0
    executed_day_trades: int = 0
    # Phase B (refactor) — diagnostics micro-structure.
    blocked_entry_gap: int = 0
    initial_stop_exits: int = 0
    take_profit_exits: int = 0
    trailing_stop_exits: int = 0
    # Phase C (refactor) — diagnostics risk overlay.
    blocked_by_regime: int = 0
    blocked_by_sectoral_cap: int = 0
    blocked_by_drawdown_breaker: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "blocked_same_day_exits": self.blocked_same_day_exits,
            "blocked_pdt_day_trades": self.blocked_pdt_day_trades,
            "blocked_cash_entries": self.blocked_cash_entries,
            "executed_day_trades": self.executed_day_trades,
            "blocked_entry_gap": self.blocked_entry_gap,
            "initial_stop_exits": self.initial_stop_exits,
            "take_profit_exits": self.take_profit_exits,
            "trailing_stop_exits": self.trailing_stop_exits,
            "blocked_by_regime": self.blocked_by_regime,
            "blocked_by_sectoral_cap": self.blocked_by_sectoral_cap,
            "blocked_by_drawdown_breaker": self.blocked_by_drawdown_breaker,
        }


@dataclass(slots=True)
class _OpenPosition:
    symbol: str
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    entry_idx: int
    entry_price: float
    quantity: int
    peak_high: float
    entry_cost: float
    # Phase B.2 — stop-loss initial dur (None = désactivé).
    initial_stop_price: float | None = None
    # Phase D.2 — secteur pour attribution sectorielle.
    sector: str | None = None


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
    equity_points: list[float] = field(default_factory=list)
    day_trade_counts: dict[pd.Timestamp, int] = field(default_factory=lambda: defaultdict(int))


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
    diagnostics: BacktestDiagnostics = field(default_factory=BacktestDiagnostics)
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

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    @staticmethod
    def _to_scalar(value) -> float:
        """Convertit une sortie vectorbt/pandas scalaire ou Series en float."""
        if hasattr(value, "iloc"):
            return float(value.iloc[0])
        return float(value)

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

        # Aligner les symboles communs
        selected = signals_df[signals_df["selected"]].copy()
        symbols = sorted(set(selected["symbol"]) & set(close.columns))
        if not symbols:
            raise ValueError("Aucun symbole en commun entre signaux et OHLCV.")

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
            )

        LOGGER.info(
            "Backtest standard (signal J, entrée J+1 open) : %d symboles, %d jours, TP=%.1f%%, TS=%.1f%%, equity=%.0f",
            len(symbols), len(close), cfg.profit_taker_pct * 100,
            cfg.trailing_stop_pct * 100, cfg.initial_equity,
        )

        return self._run_with_constraints(
            open_df=open_df, close=close, high=high, low=low,
            signals_df=selected, volume=volume, sector_map=sector_map,
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

        state = _RunState(
            settled_cash=float(cfg.initial_equity),
            peak_equity=float(cfg.initial_equity),
        )

        for day_idx in range(len(trading_days)):
            trade_day = pd.Timestamp(trading_days[day_idx])
            self._apply_settlements(state, day_idx)

            # Phase E.4 — single mark-to-market précoce pour Phase C.5.
            current_market_value = self._mark_to_market(state.positions, close, trade_day)
            current_equity = state.settled_cash + state.unsettled_cash + current_market_value
            state.peak_equity = max(state.peak_equity, current_equity)
            entries_allowed_by_breaker = cfg.risk_overlay.drawdown_breaker.update(
                current_equity, state.peak_equity
            )

            # Phase C.3 — filtre régime (benchmark).
            entries_allowed_by_regime = cfg.risk_overlay.regime_filter.is_entry_allowed(
                cfg.benchmark_close, trade_day,
            )

            day_signals = signals_by_day.get(trade_day)
            candidate_rows = self._select_candidate_rows(
                state=state,
                day_signals=day_signals,
                close_columns=close.columns,
                entries_allowed_by_breaker=entries_allowed_by_breaker,
                entries_allowed_by_regime=entries_allowed_by_regime,
                diagnostics=diagnostics,
            )

            self._try_open_entries(
                state=state,
                candidate_rows=candidate_rows,
                open_df=open_df,
                close=close,
                trade_day=trade_day,
                day_idx=day_idx,
                trading_days=trading_days,
                adv_usd_df=adv_usd_df,
                sector_map=sector_map,
                current_equity=current_equity,
                diagnostics=diagnostics,
            )

            self._try_close_positions(
                state=state,
                high=high,
                low=low,
                trade_day=trade_day,
                day_idx=day_idx,
                trading_days=trading_days,
                adv_usd_df=adv_usd_df,
                rng=rng,
                diagnostics=diagnostics,
            )

            # Phase E.4 — single mark-to-market final pour equity du jour.
            market_value = self._mark_to_market(state.positions, close, trade_day)
            state.equity_points.append(state.settled_cash + state.unsettled_cash + market_value)

        equity_curve = pd.Series(
            state.equity_points, index=trading_days, name="portfolio_value", dtype=float
        )
        trades_df = pd.DataFrame(state.closed_trades)
        result = BacktestResult(equity_curve=equity_curve, closed_trades_df=trades_df, diagnostics=diagnostics)
        LOGGER.info(
            "Backtest contraint terminé — valeur finale : %.2f — diagnostics=%s",
            result.final_value(),
            diagnostics.to_dict(),
        )
        return result

    # ------------------------------------------------------------------
    # Phase E.3 (refactor) — sous-méthodes du run constraint.
    # ------------------------------------------------------------------

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
        day_signals: pd.DataFrame | None,
        close_columns: pd.Index,
        entries_allowed_by_breaker: bool,
        entries_allowed_by_regime: bool,
        diagnostics: BacktestDiagnostics,
    ) -> list[pd.Series]:
        """Phase E.3 — filtre les signaux du jour selon les overlays risk."""
        cfg = self.config
        if day_signals is None:
            return []
        if not entries_allowed_by_breaker or not entries_allowed_by_regime:
            blocked_count = int(max(cfg.max_positions - len(state.positions), 0))
            if not entries_allowed_by_breaker:
                diagnostics.blocked_by_drawdown_breaker += blocked_count
            if not entries_allowed_by_regime:
                diagnostics.blocked_by_regime += blocked_count
            return []

        available_slots = max(cfg.max_positions - len(state.positions), 0)
        if available_slots <= 0:
            return []
        return [
            row
            for _, row in day_signals.iterrows()
            if str(row["symbol"]) not in state.positions and str(row["symbol"]) in close_columns
        ][:available_slots]

    def _try_open_entries(
        self,
        *,
        state: _RunState,
        candidate_rows: list[pd.Series],
        open_df: pd.DataFrame,
        close: pd.DataFrame,
        trade_day: pd.Timestamp,
        day_idx: int,
        trading_days: pd.DatetimeIndex,
        adv_usd_df: pd.DataFrame | None,
        sector_map: dict[str, str],
        current_equity: float,
        diagnostics: BacktestDiagnostics,
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

        # Snapshot des expositions sectorielles courantes (Phase C.4).
        sector_exposure_pct: dict[str, float] = defaultdict(float)
        if risk.sectoral_cap.enabled and current_equity > 0:
            for pos in state.positions.values():
                px = (
                    float(close.at[trade_day, pos.symbol])
                    if pos.symbol in close.columns
                    else pos.entry_price
                )
                sec = pos.sector or sector_map.get(pos.symbol, "Unknown")
                sector_exposure_pct[sec] += (pos.quantity * px) / current_equity

        for candidate_pos, row in enumerate(candidate_rows):
            symbol = str(row["symbol"])
            entry_price = float(open_df.at[trade_day, symbol])
            if not np.isfinite(entry_price) or entry_price <= 0:
                continue

            # Phase B.3 — gap d'ouverture excessif.
            previous_close: float | None = None
            if day_idx > 0 and symbol in close.columns:
                prev_day = trading_days[day_idx - 1]
                try:
                    previous_close = float(close.at[prev_day, symbol])
                except (KeyError, ValueError):
                    previous_close = None
            if should_skip_entry_for_gap(
                previous_close, entry_price, max_gap_pct=micro.max_entry_gap_pct
            ):
                diagnostics.blocked_entry_gap += 1
                continue

            target_weight_pct = (
                float(sizing_weights.iloc[candidate_pos])
                if not sizing_weights.empty and candidate_pos < len(sizing_weights)
                else 1.0 / max(cfg.max_positions, 1)
            )

            sector = (
                str(row["sector"])
                if "sector" in row and pd.notna(row.get("sector"))
                else sector_map.get(symbol, "Unknown")
            )
            if not risk.sectoral_cap.is_entry_allowed(
                sector, sector_exposure_pct.get(sector, 0.0), target_weight_pct
            ):
                diagnostics.blocked_by_sectoral_cap += 1
                continue

            remaining_candidates = max(len(candidate_rows) - candidate_pos, 1)
            per_position_cap = current_equity * target_weight_pct
            candidate_budget = min(per_position_cap, state.settled_cash / remaining_candidates)

            preliminary_size_usd = max(candidate_budget, 0.0)
            adv_usd = self._get_adv_usd(adv_usd_df, trade_day, symbol)
            extra_slippage_pct = micro.slippage.compute_bps(preliminary_size_usd, adv_usd) / 10_000.0
            effective_unit_cost = entry_price * (1.0 + cfg.fees_pct + extra_slippage_pct)
            quantity = int(candidate_budget // effective_unit_cost)

            if quantity <= 0:
                if constraints.use_settled_cash_only:
                    diagnostics.blocked_cash_entries += 1
                continue

            entry_cost = quantity * effective_unit_cost
            if entry_cost > state.settled_cash:
                if constraints.use_settled_cash_only:
                    diagnostics.blocked_cash_entries += 1
                continue

            state.settled_cash -= entry_cost
            initial_stop_price = (
                entry_price * (1.0 - micro.initial_stop_pct)
                if micro.initial_stop_pct > 0
                else None
            )
            state.positions[symbol] = _OpenPosition(
                symbol=symbol,
                signal_date=pd.Timestamp(row["signal_date"]),
                entry_date=trade_day,
                entry_idx=day_idx,
                entry_price=entry_price,
                quantity=quantity,
                peak_high=entry_price,
                entry_cost=entry_cost,
                initial_stop_price=initial_stop_price,
                sector=sector,
            )
            if risk.sectoral_cap.enabled:
                sector_exposure_pct[sector] += target_weight_pct

    def _try_close_positions(
        self,
        *,
        state: _RunState,
        high: pd.DataFrame,
        low: pd.DataFrame,
        trade_day: pd.Timestamp,
        day_idx: int,
        trading_days: pd.DatetimeIndex,
        adv_usd_df: pd.DataFrame | None,
        rng: np.random.Generator | None,
        diagnostics: BacktestDiagnostics,
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

            previous_peak_high = position.peak_high
            peak_high = max(previous_peak_high, day_high)
            take_profit_price = position.entry_price * (1.0 + cfg.profit_taker_pct)
            trailing_stop_price = previous_peak_high * (1.0 - cfg.trailing_stop_pct)
            is_same_day = trade_day.normalize() == position.entry_date.normalize()

            resolution = resolve_intrabar_exit(
                day_high=day_high,
                day_low=day_low,
                take_profit_price=take_profit_price,
                trailing_stop_price=trailing_stop_price,
                initial_stop_price=position.initial_stop_price,
                priority=micro.intrabar_priority,
                rng=rng,
            )
            if not resolution.triggered:
                position.peak_high = peak_high
                continue

            if is_same_day and constraints.restrict_same_day_exit:
                diagnostics.blocked_same_day_exits += 1
                position.peak_high = peak_high
                continue

            if is_same_day and constraints.applies_pdt_limit(cfg.initial_equity):
                window_start = max(0, day_idx - constraints.rolling_window_days + 1)
                day_trades_in_window = sum(
                    state.day_trade_counts[pd.Timestamp(trading_days[idx])]
                    for idx in range(window_start, day_idx + 1)
                )
                if day_trades_in_window >= constraints.max_day_trades:
                    diagnostics.blocked_pdt_day_trades += 1
                    position.peak_high = peak_high
                    continue

            exit_price = resolution.exit_price
            exit_reason = resolution.exit_reason
            if exit_reason == "take_profit":
                diagnostics.take_profit_exits += 1
            elif exit_reason == "trailing_stop":
                diagnostics.trailing_stop_exits += 1
            elif exit_reason == "initial_stop":
                diagnostics.initial_stop_exits += 1

            size_usd = position.quantity * exit_price
            adv_usd = self._get_adv_usd(adv_usd_df, trade_day, symbol)
            extra_slippage_pct = micro.slippage.compute_bps(size_usd, adv_usd) / 10_000.0
            proceeds = position.quantity * exit_price * (1.0 - cfg.fees_pct - extra_slippage_pct)
            pnl = proceeds - position.entry_cost
            holding_days = int((trade_day - position.entry_date).days)

            if constraints.use_settled_cash_only:
                settlement_day_idx = day_idx + constraints.cash_settlement_days
                state.unsettled_cash += proceeds
                if settlement_day_idx < len(trading_days):
                    state.settlements_by_day[settlement_day_idx] += proceeds
            else:
                state.settled_cash += proceeds

            is_day_trade = is_same_day
            if is_day_trade:
                state.day_trade_counts[trade_day] += 1
                diagnostics.executed_day_trades += 1

            state.closed_trades.append(
                {
                    "symbol": symbol,
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
                    "return_pct": ((proceeds / position.entry_cost) - 1.0) * 100.0
                    if position.entry_cost
                    else 0.0,
                    "holding_days": holding_days,
                    "exit_reason": exit_reason,
                    "is_day_trade": is_day_trade,
                }
            )
            symbols_to_close.append(symbol)

        for symbol in symbols_to_close:
            state.positions.pop(symbol, None)

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

    @staticmethod
    def _mark_to_market(
        positions: dict[str, _OpenPosition],
        close: pd.DataFrame,
        trade_day: pd.Timestamp,
    ) -> float:
        """Phase E.4 — calcule la valeur de marché courante des positions ouvertes."""
        if not positions:
            return 0.0
        total = 0.0
        for position in positions.values():
            try:
                px = float(close.at[trade_day, position.symbol])
                if np.isfinite(px):
                    total += position.quantity * px
            except (KeyError, ValueError):
                continue
        return total



