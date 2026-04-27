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
    # (= commission + slippage / 10_000). ``commission_bps`` et
    # ``slippage_bps`` sont conservés pour la traçabilité et le run_summary.
    fees_pct: float = 0.001  # 10 bps
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    trading_constraints: TradingConstraintConfig = field(default_factory=TradingConstraintConfig)
    execution_timing: str = "next_open"

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

    def to_dict(self) -> dict[str, int]:
        return {
            "blocked_same_day_exits": self.blocked_same_day_exits,
            "blocked_pdt_day_trades": self.blocked_pdt_day_trades,
            "blocked_cash_entries": self.blocked_cash_entries,
            "executed_day_trades": self.executed_day_trades,
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
        open: pd.DataFrame,
        close: pd.DataFrame,
        high: pd.DataFrame,
        low: pd.DataFrame,
        signals_df: pd.DataFrame,
    ) -> BacktestResult:
        """Lance le backtest.

        Parameters
        ----------
        close : DataFrame pivoté (index=date, columns=symbols)
        high : idem
        low : idem
        signals_df : DataFrame issu de signal_replay.replay_signals()
            avec colonnes : trade_date, symbol, selected

        Returns
        -------
        BacktestResult
        """
        cfg = self.config
        constraints = cfg.trading_constraints

        # Aligner les symboles communs
        selected = signals_df[signals_df["selected"]].copy()
        symbols = sorted(set(selected["symbol"]) & set(close.columns))
        if not symbols:
            raise ValueError("Aucun symbole en commun entre signaux et OHLCV.")

        open = open[symbols].copy()
        close = close[symbols].copy()
        high = high[symbols].copy()
        low = low[symbols].copy()

        if cfg.execution_timing != "next_open":
            raise ValueError(f"Convention d'exécution non supportée: {cfg.execution_timing}")

        if constraints.requires_stateful_simulation(cfg.initial_equity):
            LOGGER.info("Backtest avec contraintes actives: %s", constraints.to_dict())
            return self._run_with_constraints(open=open, close=close, high=high, low=low, signals_df=selected)

        LOGGER.info(
            "Backtest standard (signal J, entrée J+1 open) : %d symboles, %d jours, TP=%.1f%%, TS=%.1f%%, equity=%.0f",
            len(symbols), len(close), cfg.profit_taker_pct * 100,
            cfg.trailing_stop_pct * 100, cfg.initial_equity,
        )

        return self._run_with_constraints(open=open, close=close, high=high, low=low, signals_df=selected)

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
        open: pd.DataFrame,
        close: pd.DataFrame,
        high: pd.DataFrame,
        low: pd.DataFrame,
        signals_df: pd.DataFrame,
    ) -> BacktestResult:
        cfg = self.config
        constraints = cfg.trading_constraints
        diagnostics = BacktestDiagnostics()

        trading_days = pd.DatetimeIndex(close.index)
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

        signals_by_day: dict[pd.Timestamp, pd.DataFrame] = {}
        if not scheduled_signals.empty:
            signals_by_day = {
                day: day_df.sort_values(["rank", "symbol"]).copy()
                for day, day_df in scheduled_signals.groupby("execution_date", sort=True)
            }

        settled_cash = float(cfg.initial_equity)
        unsettled_cash = 0.0
        settlements_by_day: dict[int, float] = defaultdict(float)
        positions: dict[str, _OpenPosition] = {}
        closed_trades: list[dict[str, object]] = []
        equity_points: list[float] = []
        day_trade_counts: dict[pd.Timestamp, int] = defaultdict(int)

        for day_idx in range(len(trading_days)):
            trade_day = pd.Timestamp(trading_days[day_idx])
            settlement_amount = settlements_by_day.pop(day_idx, 0.0)
            if settlement_amount:
                settled_cash += settlement_amount
                unsettled_cash = max(unsettled_cash - settlement_amount, 0.0)

            day_signals = signals_by_day.get(trade_day)
            candidate_rows: list[pd.Series] = []
            if day_signals is not None:
                available_slots = max(cfg.max_positions - len(positions), 0)
                if available_slots > 0:
                    candidate_rows = [
                        row
                        for _, row in day_signals.iterrows()
                        if str(row["symbol"]) not in positions and str(row["symbol"]) in close.columns
                    ][:available_slots]

            for candidate_pos, row in enumerate(candidate_rows):
                symbol = str(row["symbol"])
                entry_price = float(open.at[trade_day, symbol])
                if not np.isfinite(entry_price) or entry_price <= 0:
                    continue

                market_value = sum(
                    position.quantity * float(close.at[trade_day, position.symbol])
                    for position in positions.values()
                )
                total_equity = settled_cash + unsettled_cash + market_value
                remaining_candidates = max(len(candidate_rows) - candidate_pos, 1)
                per_position_cap = total_equity / max(cfg.max_positions, 1)
                candidate_budget = min(per_position_cap, settled_cash / remaining_candidates)
                quantity = int(candidate_budget // (entry_price * (1.0 + cfg.fees_pct)))

                if quantity <= 0:
                    if constraints.use_settled_cash_only:
                        diagnostics.blocked_cash_entries += 1
                    continue

                entry_cost = quantity * entry_price * (1.0 + cfg.fees_pct)
                if entry_cost > settled_cash:
                    if constraints.use_settled_cash_only:
                        diagnostics.blocked_cash_entries += 1
                    continue

                settled_cash -= entry_cost
                positions[symbol] = _OpenPosition(
                    symbol=symbol,
                    signal_date=pd.Timestamp(row["signal_date"]),
                    entry_date=trade_day,
                    entry_idx=day_idx,
                    entry_price=entry_price,
                    quantity=quantity,
                    peak_high=entry_price,
                    entry_cost=entry_cost,
                )

            symbols_to_close: list[str] = []
            for symbol, position in positions.items():
                day_high = float(high.at[trade_day, symbol])
                day_low = float(low.at[trade_day, symbol])

                if not np.isfinite(day_high) or not np.isfinite(day_low):
                    continue

                previous_peak_high = position.peak_high
                peak_high = max(previous_peak_high, day_high)
                take_profit_price = position.entry_price * (1.0 + cfg.profit_taker_pct)
                trailing_stop_price = previous_peak_high * (1.0 - cfg.trailing_stop_pct)
                is_same_day = trade_day.normalize() == position.entry_date.normalize()

                hit_take_profit = day_high >= take_profit_price
                hit_trailing_stop = day_low <= trailing_stop_price
                if not hit_take_profit and not hit_trailing_stop:
                    position.peak_high = peak_high
                    continue

                if is_same_day and constraints.restrict_same_day_exit:
                    diagnostics.blocked_same_day_exits += 1
                    position.peak_high = peak_high
                    continue

                if is_same_day and constraints.applies_pdt_limit(cfg.initial_equity):
                    window_start = max(0, day_idx - constraints.rolling_window_days + 1)
                    day_trades_in_window = sum(
                        day_trade_counts[pd.Timestamp(trading_days[idx])]
                        for idx in range(window_start, day_idx + 1)
                    )
                    if day_trades_in_window >= constraints.max_day_trades:
                        diagnostics.blocked_pdt_day_trades += 1
                        position.peak_high = peak_high
                        continue

                if hit_trailing_stop:
                    exit_price = trailing_stop_price
                    exit_reason = "trailing_stop"
                else:
                    exit_price = take_profit_price
                    exit_reason = "take_profit"

                proceeds = position.quantity * exit_price * (1.0 - cfg.fees_pct)
                pnl = proceeds - position.entry_cost
                holding_days = int((trade_day - position.entry_date).days)

                if constraints.use_settled_cash_only:
                    settlement_day_idx = day_idx + constraints.cash_settlement_days
                    unsettled_cash += proceeds
                    if settlement_day_idx < len(trading_days):
                        settlements_by_day[settlement_day_idx] += proceeds
                else:
                    settled_cash += proceeds

                is_day_trade = is_same_day
                if is_day_trade:
                    day_trade_counts[trade_day] += 1
                    diagnostics.executed_day_trades += 1

                closed_trades.append(
                    {
                        "symbol": symbol,
                        "signal_date": position.signal_date,
                        "quantity": position.quantity,
                        "entry_date": position.entry_date,
                        "exit_date": trade_day,
                        "entry_price": position.entry_price,
                        "exit_price": exit_price,
                        "entry_cost": position.entry_cost,
                        "proceeds": proceeds,
                        "pnl": pnl,
                        "return_pct": ((proceeds / position.entry_cost) - 1.0) * 100.0 if position.entry_cost else 0.0,
                        "holding_days": holding_days,
                        "exit_reason": exit_reason,
                        "is_day_trade": is_day_trade,
                    }
                )
                symbols_to_close.append(symbol)

            for symbol in symbols_to_close:
                positions.pop(symbol, None)

            market_value = sum(
                position.quantity * float(close.at[trade_day, position.symbol])
                for position in positions.values()
            )
            equity_points.append(settled_cash + unsettled_cash + market_value)

        equity_curve = pd.Series(equity_points, index=trading_days, name="portfolio_value", dtype=float)
        trades_df = pd.DataFrame(closed_trades)
        result = BacktestResult(equity_curve=equity_curve, closed_trades_df=trades_df, diagnostics=diagnostics)
        LOGGER.info(
            "Backtest contraint terminé — valeur finale : %.2f — diagnostics=%s",
            result.final_value(),
            diagnostics.to_dict(),
        )
        return result



