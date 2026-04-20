"""
backtesting/simulator.py
=========================
Moteur de backtest principal utilisant vectorbt.
Rejoue la stratégie Alpha Trade (entrées par conviction, sorties bracket TP/TS)
sur l'historique OHLCV.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
import vectorbt as vbt

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

    # Frais de transaction (slippage simulé)
    fees_pct: float = 0.001  # 10 bps

    def __post_init__(self) -> None:
        if self.risk_config:
            self.max_positions = self.risk_config.max_positions
        if self.exec_config:
            self.profit_taker_pct = self.exec_config.profit_taker_pct
            self.trailing_stop_pct = self.exec_config.trailing_stop_pct


class BacktestEngine:
    """Exécute le backtest vectorbt à partir des signaux reconstruits."""

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
        close: pd.DataFrame,
        high: pd.DataFrame,
        low: pd.DataFrame,
        signals_df: pd.DataFrame,
    ) -> vbt.Portfolio:
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
        vbt.Portfolio
        """
        cfg = self.config

        # Aligner les symboles communs
        selected = signals_df[signals_df["selected"]].copy()
        symbols = sorted(set(selected["symbol"]) & set(close.columns))
        if not symbols:
            raise ValueError("Aucun symbole en commun entre signaux et OHLCV.")

        close = close[symbols].copy()
        high = high[symbols].copy()
        low = low[symbols].copy()

        # Construire la matrice d'entrées (entries) : True quand le symbole est sélectionné ce jour
        entries = pd.DataFrame(False, index=close.index, columns=close.columns)
        for _, row in selected.iterrows():
            td = row["trade_date"]
            sym = row["symbol"]
            if td in entries.index and sym in entries.columns:
                entries.loc[td, sym] = True

        # Sizing : répartition equal-weight parmi les positions sélectionnées par jour
        # vectorbt gère le sizing via size + size_type
        n_selected_per_day = entries.sum(axis=1).replace(0, np.nan)
        size_pct = entries.div(n_selected_per_day, axis=0).fillna(0.0)
        # Limiter au max_positions
        size_pct = size_pct.clip(upper=1.0 / max(cfg.max_positions, 1))

        LOGGER.info(
            "Backtest : %d symboles, %d jours, TP=%.1f%%, TS=%.1f%%, equity=%.0f",
            len(symbols), len(close), cfg.profit_taker_pct * 100,
            cfg.trailing_stop_pct * 100, cfg.initial_equity,
        )

        # Exécuter via vectorbt from_signals avec TP et trailing SL
        pf = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=pd.DataFrame(False, index=close.index, columns=close.columns),
            open=high,  # conservatif : entrée au high
            high=high,
            low=low,
            # Bracket : take-profit et trailing stop
            tp_stop=cfg.profit_taker_pct,
            sl_stop=cfg.trailing_stop_pct,
            sl_trail=True,  # trailing stop loss
            # Sizing
            size=size_pct,
            size_type="percent",
            # Config
            init_cash=cfg.initial_equity,
            fees=cfg.fees_pct,
            freq="1D",
            cash_sharing=True,
            group_by=True,
            accumulate=False,  # pas d'accumulation sur même symbole
            upon_opposite_entry="close",  # fermer avant de ré-entrer
        )

        LOGGER.info("Backtest terminé — valeur finale : %.2f", self._to_scalar(pf.final_value()))
        return pf



