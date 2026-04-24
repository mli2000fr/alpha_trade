from __future__ import annotations

import argparse
import logging
import os
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterator, Optional, Sequence, cast

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from common.utils import configure_root_logging
from database.connection import get_sqlalchemy_engine
from database.assets import (
    HISTORY_STATUS_EXCLUDED_BY_POLICY,
    HISTORY_STATUS_NO_HISTORY,
    HISTORY_STATUS_PENDING,
    HISTORY_STATUS_PROVIDER_ERROR,
    HISTORY_STATUS_READY,
    HISTORY_STATUS_SUSPENDED_OR_STALE,
)
from selector.strict_filter_profiles import STRICT_SWING_CASH_FILTERS, StrictFilterProfile

LOGGER = logging.getLogger(__name__)

PRICE_COLUMNS = ["symbol", "date", "close", "volume", "high", "low"]
METADATA_COLUMNS = [
    "symbol",
    "company_name",
    "asset_class",
    "status",
    "tradable",
    "bars_available",
    "history_status",
    "sector",
    "market_cap",
]
ELIGIBLE_HISTORY_STATUSES = {HISTORY_STATUS_PENDING, HISTORY_STATUS_READY}
ETF_NAME_PATTERNS = (
    "etf",
    "etn",
    "fund",
    "index fund",
    "ishares",
    "spdr",
    "vanguard",
    "invesco",
    "proshares",
    "direxion",
    "wisdomtree",
    "global x",
    "first trust",
    "xtrackers",
    "schwab",
    "bond",
    "treasury",
)
FACTOR_COLUMNS = [
    "symbol",
    "date",
    "latest_close",
    "avg_dollar_volume_20d",
    "history_days",
    "atr_20",
    "atr_pct_20",
    "beta_126",
    "ma50",
    "ma150",
    "ma200",
    "high_52w",
    "low_52w",
    "high_52w_proximity",
    "weekly_close",
    "weekly_ma10",
    "weekly_ma30",
    "weekly_trend_score",
    "volatility_ratio",
    "trend_score",
    "vcp_score",
]
SCORE_COLUMNS = [
    "symbol",
    "liquidity_val",
    "relative_strength_index",
    "total_score",
    "sector",
    "market_cap",
    "beta_126",
    "spread_bps",
    "earnings_date",
    "days_to_earnings",
    "earnings_blackout",
    "sanitizer_status",
    "anomaly_count",
    "missing_days_count",
]
PERSISTED_SELECTOR_SCORE_COLUMNS = [
    "symbol",
    "trend_score",
    "vcp_score",
    "final_score",
    "market_cap",
    "beta_126",
    "spread_bps",
    "earnings_date",
    "days_to_earnings",
    "earnings_blackout",
]
OUTPUT_COLUMNS = [
    "rank",
    "symbol",
    "sector",
    "latest_close",
    "avg_dollar_volume_20d",
    "liquidity_val",
    "relative_strength_index",
    "total_score",
    "trend_score",
    "vcp_score",
    "raw_final_score",
    "final_score",
    "volatility_ratio",
    "atr_20",
    "atr_pct_20",
    "market_cap",
    "beta_126",
    "spread_bps",
    "earnings_date",
    "days_to_earnings",
    "earnings_blackout",
    "ma50",
    "ma150",
    "ma200",
    "high_52w",
    "low_52w",
    "high_52w_proximity",
    "weekly_close",
    "weekly_ma10",
    "weekly_ma30",
    "weekly_trend_score",
    "history_days",
    "anomaly_count",
    "missing_days_count",
]


@dataclass(frozen=True, slots=True)
class AlphaScannerConfig:
    price_table: str = "stock_bars_daily"
    score_table: str = "stock_scores"
    chunk_size: int = 500
    selection_size: int = 100
    min_history_days: int = 252
    liquidity_threshold: float = 20_000_000.0
    min_close: float = 5.0
    max_volatility_ratio: float | None = None
    min_relative_strength_index: float | None = None
    min_high_52w_proximity: float | None = None
    min_weekly_trend_score: float | None = None
    min_atr_pct_20: float | None = None
    max_atr_pct_20: float | None = None
    min_market_cap: float | None = None
    min_beta_126: float | None = None
    max_spread_bps: float | None = None
    earnings_blackout_days: int | None = None
    require_above_ma200: bool = False
    max_anomaly_count: int = 20
    max_missing_days_count: int = 10
    sector_cap_ratio: float = 0.30
    volatility_short_window: int = 10
    volatility_long_window: int = 60
    vcp_ratio_threshold: float = 0.60
    ma_short_window: int = 50
    ma_mid_window: int = 150
    ma_long_window: int = 200
    trailing_range_window: int = 252
    liquidity_lookback_days: int = 20
    update_batch_size: int = 500
    max_workers: int | None = None

    # --- Composition des facteurs (P1 — poids configurables) -----------------
    # Remplace les constantes hardcodées 0.5 / 0.3 / 0.2 dans merge_scores().
    # Pour passer à un schéma IC-weighted, ajustez ces valeurs après avoir calculé
    # l'Information Coefficient (corrélation rang-facteur → rendement futur 5/10/20j)
    # via un backtest (ex. vectorbt / zipline).
    weight_trend_vcp: float = 0.50    # 50 % : moyenne (trend_score + vcp_score)
    weight_total_score: float = 0.30  # 30 % : score screener (RSI relatif, range historique)
    weight_rsi: float = 0.20          # 20 % : RSI relatif vs SPY normalisé

    # --- Winsorisation (P1 — protection contre les outliers) -----------------
    # Percentiles utilisés pour borner les séries avant normalisation min-max.
    # Valeurs standard : [1 %, 99 %]. Réduire à [2 %, 98 %] si outliers fréquents.
    winsor_lower_pct: float = 0.01
    winsor_upper_pct: float = 0.99

    # --- Neutralisation sectorielle (P0) -------------------------------------
    # Si True, RSI et total_score sont transformés en z-scores intra-secteur
    # avant la composition du final_score, ce qui élimine le biais de secteur
    # (ex. titres Energy surreprésentés en bull sectoriel).
    neutralize_by_sector: bool = True

    @classmethod
    def from_filter_profile(
        cls,
        profile: StrictFilterProfile,
        **overrides: object,
    ) -> "AlphaScannerConfig":
        merged_kwargs: dict[str, object] = dict(profile.to_scanner_config_kwargs())
        for key, value in overrides.items():
            merged_kwargs[key] = value
        return cls(**merged_kwargs)

    @classmethod
    def strict_swing_cash(cls, **overrides: object) -> "AlphaScannerConfig":
        return cls.from_filter_profile(STRICT_SWING_CASH_FILTERS, **overrides)

    def __post_init__(self) -> None:
        if self.chunk_size < 1:
            raise ValueError("chunk_size doit être supérieur ou égal à 1.")
        if self.selection_size < 1:
            raise ValueError("selection_size doit être supérieur ou égal à 1.")
        if self.min_history_days < self.trailing_range_window:
            raise ValueError("min_history_days doit être supérieur ou égal à trailing_range_window.")
        if self.liquidity_threshold <= 0:
            raise ValueError("liquidity_threshold doit être strictement positif.")
        if self.min_close <= 0:
            raise ValueError("min_close doit être strictement positif.")
        if self.max_volatility_ratio is not None and self.max_volatility_ratio <= 0:
            raise ValueError("max_volatility_ratio doit être strictement positif lorsqu'il est renseigné.")
        if self.min_relative_strength_index is not None and self.min_relative_strength_index <= 0:
            raise ValueError("min_relative_strength_index doit être strictement positif lorsqu'il est renseigné.")
        if self.min_high_52w_proximity is not None and not 0 < self.min_high_52w_proximity <= 1:
            raise ValueError("min_high_52w_proximity doit être compris dans ]0, 1] lorsqu'il est renseigné.")
        if self.min_weekly_trend_score is not None and not 0 <= self.min_weekly_trend_score <= 1:
            raise ValueError("min_weekly_trend_score doit être compris dans [0, 1] lorsqu'il est renseigné.")
        if self.min_atr_pct_20 is not None and self.min_atr_pct_20 <= 0:
            raise ValueError("min_atr_pct_20 doit être strictement positif lorsqu'il est renseigné.")
        if self.max_atr_pct_20 is not None and self.max_atr_pct_20 <= 0:
            raise ValueError("max_atr_pct_20 doit être strictement positif lorsqu'il est renseigné.")
        if self.min_market_cap is not None and self.min_market_cap <= 0:
            raise ValueError("min_market_cap doit être strictement positif lorsqu'il est renseigné.")
        if self.min_beta_126 is not None and self.min_beta_126 <= 0:
            raise ValueError("min_beta_126 doit être strictement positif lorsqu'il est renseigné.")
        if self.max_spread_bps is not None and self.max_spread_bps <= 0:
            raise ValueError("max_spread_bps doit être strictement positif lorsqu'il est renseigné.")
        if self.earnings_blackout_days is not None and self.earnings_blackout_days < 0:
            raise ValueError("earnings_blackout_days doit être positif ou nul lorsqu'il est renseigné.")
        if (
            self.min_atr_pct_20 is not None
            and self.max_atr_pct_20 is not None
            and self.min_atr_pct_20 > self.max_atr_pct_20
        ):
            raise ValueError("min_atr_pct_20 ne peut pas être supérieur à max_atr_pct_20.")
        if not 0 < self.sector_cap_ratio <= 1:
            raise ValueError("sector_cap_ratio doit être compris entre 0 exclus et 1 inclus.")
        if self.volatility_short_window < 2 or self.volatility_long_window <= self.volatility_short_window:
            raise ValueError("Les fenêtres de volatilité sont invalides.")
        if self.vcp_ratio_threshold <= 0:
            raise ValueError("vcp_ratio_threshold doit être strictement positif.")
        if self.update_batch_size < 1:
            raise ValueError("update_batch_size doit être supérieur ou égal à 1.")
        if self.max_workers is not None and self.max_workers < 1:
            raise ValueError("max_workers doit être supérieur ou égal à 1.")
        total_weight = self.weight_trend_vcp + self.weight_total_score + self.weight_rsi
        if not np.isclose(total_weight, 1.0, atol=1e-6):
            raise ValueError(
                f"La somme des poids facteurs doit être égale à 1.0 "
                f"(weight_trend_vcp + weight_total_score + weight_rsi = {total_weight:.6f})."
            )
        if not 0.0 <= self.winsor_lower_pct < self.winsor_upper_pct <= 1.0:
            raise ValueError("winsor_lower_pct et winsor_upper_pct doivent respecter 0 ≤ lower < upper ≤ 1.")


class AlphaScanner:
    """Scanner multi-facteurs basé sur prix journaliers + table auxiliaire de scores."""

    def __init__(
        self,
        engine: Engine | None = None,
        config: AlphaScannerConfig | None = None,
    ) -> None:
        self.engine = engine or get_sqlalchemy_engine()
        self.config = config or AlphaScannerConfig.strict_swing_cash()
        self._stock_metadata_columns_cache: set[str] | None = None

    def _get_stock_metadata_columns(self) -> set[str]:
        if self._stock_metadata_columns_cache is not None:
            return self._stock_metadata_columns_cache
        try:
            self._stock_metadata_columns_cache = {
                str(column.get("name"))
                for column in inspect(self.engine).get_columns("stock_metadata")
            }
        except Exception:
            LOGGER.warning("Inspection stock_metadata indisponible; fallback sans history_status explicite.")
            self._stock_metadata_columns_cache = set()
        return self._stock_metadata_columns_cache

    def fetch_market_data(self, symbols: Sequence[str]) -> pd.DataFrame:
        """Charge un chunk d'historique marché depuis la table daily."""
        if not symbols:
            return pd.DataFrame(columns=PRICE_COLUMNS)

        LOGGER.debug("Chargement market data | symboles=%s", len(symbols))

        stmt = text(
            f"""
            SELECT symbol, date, close, volume, high, low
            FROM {self.config.price_table}
            WHERE symbol IN :symbols
            ORDER BY symbol, date
            """
        ).bindparams(bindparam("symbols", expanding=True))

        try:
            market_data = pd.read_sql_query(
                stmt,
                self.engine,
                params=cast(dict[str, Any], {"symbols": list(symbols)}),
            )
        except SQLAlchemyError as exc:
            LOGGER.exception("Echec lecture %s pour %s symboles.", self.config.price_table, len(symbols))
            raise RuntimeError("Impossible de charger les données marché.") from exc

        if market_data.empty:
            return pd.DataFrame(columns=PRICE_COLUMNS)

        market_data["date"] = pd.to_datetime(market_data["date"], utc=False)
        return market_data

    def fetch_scores(self, symbols: Sequence[str]) -> pd.DataFrame:
        """Charge les scores auxiliaires; absence de table/ligne tolérée."""
        if not symbols:
            return pd.DataFrame(columns=SCORE_COLUMNS)

        LOGGER.debug("Chargement scores auxiliaires | symboles=%s", len(symbols))

        stmt = text(
            f"""
            SELECT symbol,
                   liquidity_val,
                   relative_strength_index,
                   total_score,
                   sector,
                   market_cap,
                   beta_126,
                   spread_bps,
                   earnings_date,
                   days_to_earnings,
                   earnings_blackout,
                   sanitizer_status,
                   anomaly_count,
                   missing_days_count
            FROM {self.config.score_table}
            WHERE symbol IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))

        try:
            scores = pd.read_sql_query(
                stmt,
                self.engine,
                params=cast(dict[str, Any], {"symbols": list(symbols)}),
            )
        except SQLAlchemyError:
            LOGGER.warning(
                "Lecture auxiliaire %s indisponible; poursuite avec facteurs recalcules seulement.",
                self.config.score_table,
            )
            return pd.DataFrame(columns=SCORE_COLUMNS)

        return scores if not scores.empty else pd.DataFrame(columns=SCORE_COLUMNS)

    def fetch_instrument_metadata(self, symbols: Sequence[str]) -> pd.DataFrame:
        """Charge les métadonnées instrument pour enrichir les secteurs et exclure les ETFs/fonds."""
        if not symbols:
            return pd.DataFrame(columns=METADATA_COLUMNS)

        available_columns = self._get_stock_metadata_columns()
        select_columns = [
            "symbol",
            "company_name",
            "asset_class",
            "status",
            "tradable",
            "bars_available",
        ]
        if "history_status" in available_columns:
            select_columns.append("history_status")
        if "sector" in available_columns:
            select_columns.append("sector")
        if "market_cap" in available_columns:
            select_columns.append("market_cap")

        stmt = text(
            f"""
            SELECT {', '.join(select_columns)}
            FROM stock_metadata
            WHERE symbol IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))

        try:
            metadata_df = pd.read_sql_query(
                stmt,
                self.engine,
                params=cast(dict[str, Any], {"symbols": list(symbols)}),
            )
        except SQLAlchemyError:
            LOGGER.warning("Lecture stock_metadata indisponible; impossibilite de filtrer explicitement les ETFs.")
            return pd.DataFrame(columns=METADATA_COLUMNS)

        if metadata_df.empty:
            return pd.DataFrame(columns=METADATA_COLUMNS)

        for column in METADATA_COLUMNS:
            if column not in metadata_df.columns:
                metadata_df[column] = pd.NA
        return metadata_df.loc[:, METADATA_COLUMNS]

    def _load_benchmark_returns(self, start_date: date, end_date: date) -> pd.DataFrame:
        stmt = text(
            f"""
            SELECT date, close
            FROM {self.config.price_table}
            WHERE symbol = 'SPY'
              AND date BETWEEN :start_date AND :end_date
            ORDER BY date
            """
        )
        try:
            benchmark_df = pd.read_sql_query(
                stmt,
                self.engine,
                params={"start_date": start_date, "end_date": end_date},
            )
        except SQLAlchemyError:
            LOGGER.warning("Lecture benchmark SPY indisponible pour le calcul du beta.")
            return pd.DataFrame(columns=["date", "spy_return"])

        if benchmark_df.empty:
            return pd.DataFrame(columns=["date", "spy_return"])

        benchmark_df["date"] = pd.to_datetime(benchmark_df["date"], utc=False)
        benchmark_df["close"] = pd.to_numeric(benchmark_df["close"], errors="coerce")
        benchmark_df["spy_return"] = benchmark_df["close"].pct_change()
        return benchmark_df[["date", "spy_return"]].dropna().reset_index(drop=True)

    def fetch_quote_snapshots(self, symbols: Sequence[str], *, reference_date: date | None = None) -> pd.DataFrame:
        if not symbols:
            return pd.DataFrame(columns=["symbol", "quote_date", "spread_bps"])

        effective_reference_date = reference_date or date.today()

        stmt = text(
            """
            SELECT q.symbol, q.quote_date, q.spread_bps
            FROM stock_quote_snapshots q
            INNER JOIN (
                SELECT symbol, MAX(quote_date) AS max_quote_date
                FROM stock_quote_snapshots
                WHERE symbol IN :symbols
                  AND quote_date <= :reference_date
                GROUP BY symbol
            ) latest ON latest.symbol = q.symbol AND latest.max_quote_date = q.quote_date
            WHERE q.symbol IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))

        try:
            quotes_df = pd.read_sql_query(
                stmt,
                self.engine,
                params={"symbols": list(symbols), "reference_date": effective_reference_date},
            )
        except SQLAlchemyError:
            LOGGER.warning("Lecture stock_quote_snapshots indisponible; filtre de spread desactive.")
            return pd.DataFrame(columns=["symbol", "quote_date", "spread_bps"])
        return quotes_df if not quotes_df.empty else pd.DataFrame(columns=["symbol", "quote_date", "spread_bps"])

    def fetch_next_earnings(self, symbols: Sequence[str], *, reference_date: date | None = None) -> pd.DataFrame:
        if not symbols:
            return pd.DataFrame(columns=["symbol", "earnings_date", "days_to_earnings", "earnings_blackout"])

        effective_reference_date = reference_date or date.today()

        stmt = text(
            """
            SELECT e.symbol,
                   e.earnings_date
            FROM stock_earnings_calendar e
            INNER JOIN (
                SELECT symbol, MIN(earnings_date) AS next_earnings_date
                FROM stock_earnings_calendar
                WHERE symbol IN :symbols
                  AND earnings_date >= :reference_date
                GROUP BY symbol
            ) next_e ON next_e.symbol = e.symbol AND next_e.next_earnings_date = e.earnings_date
            WHERE e.symbol IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))

        try:
            earnings_df = pd.read_sql_query(
                stmt,
                self.engine,
                params={"symbols": list(symbols), "reference_date": effective_reference_date},
            )
        except SQLAlchemyError:
            LOGGER.warning("Lecture stock_earnings_calendar indisponible; filtre earnings blackout desactive.")
            return pd.DataFrame(columns=["symbol", "earnings_date", "days_to_earnings", "earnings_blackout"])

        if earnings_df.empty:
            return pd.DataFrame(columns=["symbol", "earnings_date", "days_to_earnings", "earnings_blackout"])

        earnings_timestamps = pd.to_datetime(earnings_df["earnings_date"], utc=False)
        earnings_df["earnings_date"] = earnings_timestamps.dt.date
        days_to_earnings = (earnings_timestamps - pd.Timestamp(effective_reference_date)).dt.days
        earnings_df["days_to_earnings"] = pd.Series(days_to_earnings, index=earnings_df.index)
        blackout_days = self.config.earnings_blackout_days if self.config.earnings_blackout_days is not None else 0
        earnings_df["earnings_blackout"] = (
            pd.Series(pd.to_numeric(earnings_df["days_to_earnings"], errors="coerce"), index=earnings_df.index)
            .fillna(9999)
            .astype(int)
            <= blackout_days
        ).astype(int)
        return earnings_df

    def compute_factors(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """Calcule MA, range 52 semaines, trend_score Minervini et VCP score."""
        if market_data.empty:
            return pd.DataFrame(columns=FACTOR_COLUMNS)

        LOGGER.debug("Calcul facteurs | lignes_marche=%s symboles=%s", len(market_data), market_data["symbol"].nunique())

        required = {"symbol", "date", "close", "volume"}
        missing = required.difference(market_data.columns)
        if missing:
            raise ValueError(f"Colonnes marché manquantes: {sorted(missing)}")

        prices = market_data.copy()
        prices["date"] = pd.to_datetime(prices["date"], utc=False)
        prices = prices.sort_values(["symbol", "date"]).reset_index(drop=True)
        prices["close"] = prices["close"].astype(float)
        prices["volume"] = prices["volume"].astype(float)
        prices["high"] = prices["high"].astype(float) if "high" in prices.columns else prices["close"]
        prices["low"] = prices["low"].astype(float) if "low" in prices.columns else prices["close"]
        prices["dollar_volume"] = prices["close"] * prices["volume"]
        grouped = prices.groupby("symbol", group_keys=False)
        prices["prev_close"] = grouped["close"].shift(1)
        prices["true_range"] = np.maximum.reduce(
            [
                (prices["high"] - prices["low"]).to_numpy(dtype=float),
                (prices["high"] - prices["prev_close"]).abs().fillna(0.0).to_numpy(dtype=float),
                (prices["low"] - prices["prev_close"]).abs().fillna(0.0).to_numpy(dtype=float),
            ]
        )
        prices["daily_return"] = (
            prices.groupby("symbol")["close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        )
        benchmark_returns = self._load_benchmark_returns(
            start_date=prices["date"].min().date(),
            end_date=prices["date"].max().date(),
        )
        beta_rows: list[dict[str, float | str]] = []
        for symbol, symbol_prices in prices.groupby("symbol", sort=False):
            if benchmark_returns.empty:
                beta_rows.append({"symbol": str(symbol), "beta_126": np.nan})
                continue
            merged_returns = symbol_prices[["date", "daily_return"]].merge(benchmark_returns, on="date", how="inner")
            merged_returns = merged_returns.dropna(subset=["daily_return", "spy_return"])
            if len(merged_returns) < 30:
                beta_rows.append({"symbol": str(symbol), "beta_126": np.nan})
                continue
            tail = merged_returns.tail(126)
            variance = float(tail["spy_return"].var(ddof=0))
            if variance <= 1e-12:
                beta_rows.append({"symbol": str(symbol), "beta_126": np.nan})
                continue
            covariance = float(np.cov(tail["daily_return"], tail["spy_return"], ddof=0)[0, 1])
            beta_rows.append({"symbol": str(symbol), "beta_126": covariance / variance})

        prices["ma50"] = grouped["close"].rolling(self.config.ma_short_window, min_periods=self.config.ma_short_window).mean().reset_index(level=0, drop=True)
        prices["ma150"] = grouped["close"].rolling(self.config.ma_mid_window, min_periods=self.config.ma_mid_window).mean().reset_index(level=0, drop=True)
        prices["ma200"] = grouped["close"].rolling(self.config.ma_long_window, min_periods=self.config.ma_long_window).mean().reset_index(level=0, drop=True)
        prices["ma200_lag_20"] = prices.groupby("symbol")["ma200"].shift(20)
        prices["high_52w"] = grouped["high"].rolling(self.config.trailing_range_window, min_periods=self.config.trailing_range_window).max().reset_index(level=0, drop=True)
        prices["low_52w"] = grouped["low"].rolling(self.config.trailing_range_window, min_periods=self.config.trailing_range_window).min().reset_index(level=0, drop=True)
        prices["avg_dollar_volume_20d"] = grouped["dollar_volume"].rolling(self.config.liquidity_lookback_days, min_periods=self.config.liquidity_lookback_days).mean().reset_index(level=0, drop=True)
        prices["atr_20"] = grouped["true_range"].rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
        prices["atr_pct_20"] = np.where(prices["close"] > 0, prices["atr_20"] / prices["close"], np.nan)
        prices["vol_10"] = grouped["daily_return"].rolling(self.config.volatility_short_window, min_periods=self.config.volatility_short_window).std(ddof=0).reset_index(level=0, drop=True)
        prices["vol_60"] = grouped["daily_return"].rolling(self.config.volatility_long_window, min_periods=self.config.volatility_long_window).std(ddof=0).reset_index(level=0, drop=True)
        prices["volatility_ratio"] = np.where(prices["vol_60"] > 0, prices["vol_10"] / prices["vol_60"], np.nan)

        latest = grouped.tail(1).copy()
        history_days = prices.groupby("symbol")["date"].size().reset_index(name="history_days")
        latest = latest.merge(history_days, on="symbol", how="left")
        latest = latest.merge(pd.DataFrame(beta_rows), on="symbol", how="left")
        latest["high_52w_proximity"] = np.where(
            latest["high_52w"] > 0,
            latest["close"] / latest["high_52w"],
            np.nan,
        )

        weekly_feature_rows: list[dict[str, float | str]] = []
        for symbol, symbol_prices in prices.groupby("symbol", sort=False):
            weekly_close = (
                symbol_prices.set_index("date")["close"]
                .resample("W-FRI")
                .last()
                .dropna()
            )
            if weekly_close.empty:
                weekly_feature_rows.append(
                    {
                        "symbol": str(symbol),
                        "weekly_close": np.nan,
                        "weekly_ma10": np.nan,
                        "weekly_ma30": np.nan,
                    }
                )
                continue

            weekly_df = weekly_close.to_frame(name="weekly_close")
            weekly_df["weekly_ma10"] = weekly_df["weekly_close"].rolling(10, min_periods=10).mean()
            weekly_df["weekly_ma30"] = weekly_df["weekly_close"].rolling(30, min_periods=30).mean()
            latest_week = weekly_df.iloc[-1]
            weekly_feature_rows.append(
                {
                    "symbol": str(symbol),
                    "weekly_close": float(latest_week["weekly_close"]),
                    "weekly_ma10": float(latest_week["weekly_ma10"]) if pd.notna(latest_week["weekly_ma10"]) else np.nan,
                    "weekly_ma30": float(latest_week["weekly_ma30"]) if pd.notna(latest_week["weekly_ma30"]) else np.nan,
                }
            )

        latest = latest.merge(pd.DataFrame(weekly_feature_rows), on="symbol", how="left")

        criteria = pd.DataFrame(
            {
                "close_gt_ma150": latest["close"] > latest["ma150"],
                "close_gt_ma200": latest["close"] > latest["ma200"],
                "ma150_gt_ma200": latest["ma150"] > latest["ma200"],
                "ma200_uptrend": latest["ma200"] > latest["ma200_lag_20"],
                "close_gt_ma50": latest["close"] > latest["ma50"],
                "close_25pct_above_low52": latest["close"] >= (1.25 * latest["low_52w"]),
                "close_within_25pct_high52": latest["close"] >= (0.75 * latest["high_52w"]),
            }
        )
        latest["trend_score"] = criteria.fillna(False).astype(float).mean(axis=1)
        weekly_criteria = pd.DataFrame(
            {
                "weekly_close_gt_ma10": latest["weekly_close"] > latest["weekly_ma10"],
                "weekly_ma10_gt_ma30": latest["weekly_ma10"] > latest["weekly_ma30"],
            }
        )
        latest["weekly_trend_score"] = weekly_criteria.fillna(False).astype(float).mean(axis=1)
        latest["vcp_score"] = (
            (self.config.vcp_ratio_threshold - latest["volatility_ratio"]) / self.config.vcp_ratio_threshold
        ).clip(lower=0.0, upper=1.0)
        latest["vcp_score"] = latest["vcp_score"].fillna(0.0)

        factor_frame = latest[
            [
                "symbol",
                "date",
                "close",
                "avg_dollar_volume_20d",
                "history_days",
                "atr_20",
                "atr_pct_20",
                "beta_126",
                "ma50",
                "ma150",
                "ma200",
                "high_52w",
                "low_52w",
                "high_52w_proximity",
                "weekly_close",
                "weekly_ma10",
                "weekly_ma30",
                "weekly_trend_score",
                "volatility_ratio",
                "trend_score",
                "vcp_score",
            ]
        ].rename(columns={"close": "latest_close"})

        factor_frame["volatility_ratio"] = factor_frame["volatility_ratio"].replace([np.inf, -np.inf], np.nan)
        factor_frame["atr_pct_20"] = factor_frame["atr_pct_20"].replace([np.inf, -np.inf], np.nan)
        factor_frame["beta_126"] = factor_frame["beta_126"].replace([np.inf, -np.inf], np.nan)
        factor_frame["high_52w_proximity"] = factor_frame["high_52w_proximity"].clip(lower=0.0)
        factor_frame["trend_score"] = factor_frame["trend_score"].clip(0.0, 1.0)
        factor_frame["weekly_trend_score"] = factor_frame["weekly_trend_score"].clip(0.0, 1.0)
        factor_frame["vcp_score"] = factor_frame["vcp_score"].clip(0.0, 1.0)
        return factor_frame.reset_index(drop=True)

    def merge_scores(self, computed_df: pd.DataFrame, scores_df: pd.DataFrame) -> pd.DataFrame:
        """
        Fusionne facteurs recalculés et scores auxiliaires.

        Normalisation : winsorisation [winsor_lower_pct, winsor_upper_pct] + min-max → [0, 1].
        Composition   : poids configurables via AlphaScannerConfig (weight_trend_vcp /
                        weight_total_score / weight_rsi).

        NOTE : La neutralisation sectorielle (cross-sectional z-score) est appliquée
        APRÈS cet appel, dans _apply_factor_neutralization(), une fois le secteur connu
        pour l'ensemble de l'univers (après _enrich_and_filter_equities + concat des chunks).
        """
        if computed_df.empty:
            return pd.DataFrame(columns=FACTOR_COLUMNS + SCORE_COLUMNS + ["normalized_total_score", "normalized_rsi", "raw_final_score", "final_score"])

        scores = scores_df.copy() if not scores_df.empty else pd.DataFrame(columns=SCORE_COLUMNS)
        merged = computed_df.merge(scores, on="symbol", how="left", suffixes=("", "_aux"))

        # Winsorisation + normalisation (remplace le min-max pur sensible aux outliers)
        merged["normalized_total_score"] = self._winsorize_and_normalize(
            merged.get("total_score"),
            lower_pct=self.config.winsor_lower_pct,
            upper_pct=self.config.winsor_upper_pct,
        )
        merged["normalized_rsi"] = self._winsorize_and_normalize(
            merged.get("relative_strength_index"),
            lower_pct=self.config.winsor_lower_pct,
            upper_pct=self.config.winsor_upper_pct,
        )
        merged["sector"] = merged.get("sector").where(merged.get("sector").notna(), "Unknown") if "sector" in merged.columns else "Unknown"

        # Composition multi-facteurs avec poids configurables
        # vcp_score : (threshold - vol_ratio) / threshold, clipé [0,1].
        # Un score proche de 1 = contraction de volatilité forte (signal VCP idéal).
        # Un score proche de 0 = volatilité récente élevée (pas de setup VCP).
        factor_component = 0.5 * (
            merged["trend_score"].fillna(0.0) + merged["vcp_score"].fillna(0.0)
        )
        aux_mask = merged[["total_score", "relative_strength_index"]].notna().any(axis=1)
        merged["raw_final_score"] = factor_component
        merged.loc[aux_mask, "raw_final_score"] = (
            self.config.weight_trend_vcp * factor_component[aux_mask]
            + self.config.weight_total_score * merged.loc[aux_mask, "normalized_total_score"].fillna(0.0)
            + self.config.weight_rsi * merged.loc[aux_mask, "normalized_rsi"].fillna(0.0)
        )
        merged["final_score"] = merged["raw_final_score"]
        return merged

    def _apply_factor_neutralization(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Neutralisation cross-sectorielle (P0) — appliquée sur l'univers COMPLET
        après concaténation de tous les chunks, une fois le secteur connu.

        Pour chaque facteur (relative_strength_index, total_score) :
          1. Calcule le z-score intra-secteur (mean=0, std=1 par secteur)
          2. Winsorise + normalise en [0, 1]
          3. Remplace la composante correspondante dans final_score

        Cela élimine le biais sectoriel : un titre Energy surreprésenté en bull
        sectoriel ne peut plus dominer un titre Tech simplement grâce à son secteur.

        Si neutralize_by_sector=False ou si la colonne sector est absente, retourne df inchangé.
        """
        if not self.config.neutralize_by_sector or df.empty:
            return df

        if "sector" not in df.columns or df["sector"].isna().all():
            LOGGER.warning(
                "Neutralisation sectorielle desactivee : colonne sector absente ou entierement nulle."
            )
            return df

        result = df.copy()
        result["sector"] = result["sector"].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")

        def _intra_sector_zscore(series: pd.Series) -> pd.Series:
            """Z-score robuste par secteur (ddof=0, fallback 0.0 si std≈0)."""
            mu = series.mean()
            sigma = series.std(ddof=0)
            if sigma < 1e-9:
                return pd.Series(0.0, index=series.index)
            return (series - mu) / sigma

        factors_to_neutralize = [
            col for col in ["relative_strength_index", "total_score"]
            if col in result.columns and result[col].notna().any()
        ]

        for col in factors_to_neutralize:
            z_col = f"{col}_sector_z"
            result[z_col] = result.groupby("sector")[col].transform(_intra_sector_zscore)
            result[f"{col}_neutralized"] = self._winsorize_and_normalize(
                result[z_col],
                lower_pct=self.config.winsor_lower_pct,
                upper_pct=self.config.winsor_upper_pct,
            )

        LOGGER.info(
            "Neutralisation sectorielle appliquee | univers=%s secteurs=%s facteurs=%s",
            len(result),
            result["sector"].nunique(),
            factors_to_neutralize,
        )

        # Recomposer final_score avec les composantes neutralisées
        factor_component = 0.5 * (
            result["trend_score"].fillna(0.0) + result["vcp_score"].fillna(0.0)
        )

        rsi_neutralized = result.get("relative_strength_index_neutralized")
        total_neutralized = result.get("total_score_neutralized")

        aux_mask = pd.Series(False, index=result.index)
        if rsi_neutralized is not None:
            aux_mask |= rsi_neutralized.notna()
        if total_neutralized is not None:
            aux_mask |= total_neutralized.notna()

        result["raw_final_score"] = factor_component
        if aux_mask.any():
            result.loc[aux_mask, "raw_final_score"] = (
                self.config.weight_trend_vcp * factor_component[aux_mask]
                + self.config.weight_total_score * (total_neutralized[aux_mask].fillna(0.0) if total_neutralized is not None else 0.0)
                + self.config.weight_rsi * (rsi_neutralized[aux_mask].fillna(0.0) if rsi_neutralized is not None else 0.0)
            )
        result["final_score"] = result["raw_final_score"]
        return result

    def _apply_filters_with_stats(self, merged_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
        if merged_df.empty:
            empty_stats = {
                "input": 0,
                "output": 0,
                "rejected_etf": 0,
                "rejected_history": 0,
                "rejected_price": 0,
                "rejected_market_liquidity": 0,
                "rejected_volatility": 0,
                "rejected_atr": 0,
                "rejected_relative_strength": 0,
                "rejected_ma200": 0,
                "rejected_high_52w": 0,
                "rejected_weekly": 0,
                "rejected_market_cap": 0,
                "rejected_beta": 0,
                "rejected_spread": 0,
                "rejected_earnings_blackout": 0,
                "rejected_score_liquidity": 0,
                "rejected_anomalies": 0,
                "rejected_missing_days": 0,
            }
            return merged_df.copy(), empty_stats

        filtered = merged_df.copy()
        before_count = len(filtered)

        # Exclusion ETF / crypto : seules les actions us_equity actives et tradables sont retenues.
        # (Le JOIN stock_metadata dans _iter_eligible_symbol_chunks filtre déjà en amont ;
        #  ce filtre pandas est un filet de sécurité au cas où metadata_df serait partielle.)
        if "asset_class" in filtered.columns:
            before_etf = len(filtered)
            filtered = filtered[filtered["asset_class"].isna() | (filtered["asset_class"] == "us_equity")]
            after_etf = len(filtered)
            if before_etf - after_etf:
                LOGGER.info("Filtre ETF/crypto | rejetes=%s", before_etf - after_etf)
        if "tradable" in filtered.columns:
            filtered = filtered[filtered["tradable"].isna() | (filtered["tradable"] == True)]  # noqa: E712

        after_etf_filter = len(filtered)
        filtered = filtered[filtered["history_days"] >= self.config.min_history_days]
        after_history = len(filtered)
        filtered = filtered[filtered["latest_close"] > self.config.min_close]
        after_close = len(filtered)
        filtered = filtered[filtered["avg_dollar_volume_20d"] > self.config.liquidity_threshold]
        after_market_liquidity = len(filtered)

        # Le filtre de volatilité relative dépend de facteurs calculés en pandas
        # (vol_10 / vol_60). Il est donc appliqué ici, après compute_factors(),
        # et non dans la présélection SQL brute.
        if self.config.max_volatility_ratio is not None:
            if "volatility_ratio" not in filtered.columns:
                LOGGER.warning(
                    "Filtre volatilite relative active mais colonne volatility_ratio absente; aucun titre retenu."
                )
                filtered = filtered.iloc[0:0].copy()
            else:
                filtered = filtered[
                    filtered["volatility_ratio"].notna()
                    & (filtered["volatility_ratio"] <= self.config.max_volatility_ratio)
                ]
        after_volatility = len(filtered)

        if self.config.min_atr_pct_20 is not None or self.config.max_atr_pct_20 is not None:
            if "atr_pct_20" not in filtered.columns:
                LOGGER.warning(
                    "Filtre ATR %% active mais colonne atr_pct_20 absente; aucun titre retenu."
                )
                filtered = filtered.iloc[0:0].copy()
            else:
                atr_mask = filtered["atr_pct_20"].notna()
                if self.config.min_atr_pct_20 is not None:
                    atr_mask &= filtered["atr_pct_20"] >= self.config.min_atr_pct_20
                if self.config.max_atr_pct_20 is not None:
                    atr_mask &= filtered["atr_pct_20"] <= self.config.max_atr_pct_20
                filtered = filtered[atr_mask]
        after_atr = len(filtered)

        if self.config.min_relative_strength_index is not None:
            if "relative_strength_index" not in filtered.columns:
                LOGGER.warning(
                    "Filtre force relative active mais colonne relative_strength_index absente; aucun titre retenu."
                )
                filtered = filtered.iloc[0:0].copy()
            else:
                filtered = filtered[
                    filtered["relative_strength_index"].notna()
                    & (filtered["relative_strength_index"] >= self.config.min_relative_strength_index)
                ]
        after_relative_strength = len(filtered)

        if self.config.require_above_ma200:
            required_ma200_cols = {"ma200", "latest_close"}
            if not required_ma200_cols.issubset(filtered.columns):
                LOGGER.warning(
                    "Filtre close>MA200 active mais colonnes requises absentes; aucun titre retenu."
                )
                filtered = filtered.iloc[0:0].copy()
            else:
                filtered = filtered[filtered["ma200"].notna() & (filtered["latest_close"] > filtered["ma200"])]
        after_ma200 = len(filtered)

        if self.config.min_high_52w_proximity is not None:
            if "high_52w_proximity" not in filtered.columns:
                LOGGER.warning(
                    "Filtre proximité high 52w active mais colonne high_52w_proximity absente; aucun titre retenu."
                )
                filtered = filtered.iloc[0:0].copy()
            else:
                filtered = filtered[
                    filtered["high_52w_proximity"].notna()
                    & (filtered["high_52w_proximity"] >= self.config.min_high_52w_proximity)
                ]
        after_high_52w = len(filtered)

        if self.config.min_weekly_trend_score is not None:
            if "weekly_trend_score" not in filtered.columns:
                LOGGER.warning(
                    "Filtre weekly trend active mais colonne weekly_trend_score absente; aucun titre retenu."
                )
                filtered = filtered.iloc[0:0].copy()
            else:
                filtered = filtered[
                    filtered["weekly_trend_score"].notna()
                    & (filtered["weekly_trend_score"] >= self.config.min_weekly_trend_score)
                ]
        after_weekly = len(filtered)

        if self.config.min_market_cap is not None:
            if "market_cap" not in filtered.columns:
                LOGGER.warning(
                    "Filtre market cap active mais colonne market_cap absente; aucun titre retenu."
                )
                filtered = filtered.iloc[0:0].copy()
            else:
                filtered = filtered[
                    filtered["market_cap"].notna()
                    & (pd.to_numeric(filtered["market_cap"], errors="coerce") >= self.config.min_market_cap)
                ]
        after_market_cap = len(filtered)

        if self.config.min_beta_126 is not None:
            if "beta_126" not in filtered.columns:
                LOGGER.warning(
                    "Filtre beta 126 active mais colonne beta_126 absente; aucun titre retenu."
                )
                filtered = filtered.iloc[0:0].copy()
            else:
                filtered = filtered[
                    filtered["beta_126"].notna()
                    & (pd.to_numeric(filtered["beta_126"], errors="coerce") >= self.config.min_beta_126)
                ]
        after_beta = len(filtered)

        if self.config.max_spread_bps is not None:
            if "spread_bps" not in filtered.columns:
                LOGGER.warning(
                    "Filtre spread active mais colonne spread_bps absente; aucun titre retenu."
                )
                filtered = filtered.iloc[0:0].copy()
            else:
                filtered = filtered[
                    filtered["spread_bps"].notna()
                    & (pd.to_numeric(filtered["spread_bps"], errors="coerce") <= self.config.max_spread_bps)
                ]
        after_spread = len(filtered)

        if self.config.earnings_blackout_days is not None:
            if "earnings_blackout" not in filtered.columns:
                LOGGER.warning(
                    "Filtre earnings blackout active mais colonne earnings_blackout absente; aucun titre retenu."
                )
                filtered = filtered.iloc[0:0].copy()
            else:
                filtered = filtered[
                    pd.to_numeric(filtered["earnings_blackout"], errors="coerce").fillna(0).astype(int) == 0
                ]
        after_earnings_blackout = len(filtered)

        if "liquidity_val" in filtered.columns:
            filtered = filtered[(filtered["liquidity_val"].isna()) | (filtered["liquidity_val"] > self.config.liquidity_threshold)]
        after_score_liquidity = len(filtered)
        if "sanitizer_status" in filtered.columns:
            filtered = filtered[
                filtered["sanitizer_status"].isna()
                | (filtered["sanitizer_status"].astype(str).str.lower() == "success")
            ]
        after_sanitizer = len(filtered)
        if "anomaly_count" in filtered.columns:
            filtered = filtered[(filtered["anomaly_count"].isna()) | (filtered["anomaly_count"] <= self.config.max_anomaly_count)]
        after_anomaly = len(filtered)
        if "missing_days_count" in filtered.columns:
            filtered = filtered[(filtered["missing_days_count"].isna()) | (filtered["missing_days_count"] < self.config.max_missing_days_count)]

        stats = {
            "input": before_count,
            "output": len(filtered),
            "rejected_etf": before_count - after_etf_filter,
            "rejected_history": after_etf_filter - after_history,
            "rejected_price": after_history - after_close,
            "rejected_market_liquidity": after_close - after_market_liquidity,
            "rejected_volatility": after_market_liquidity - after_volatility,
            "rejected_atr": after_volatility - after_atr,
            "rejected_relative_strength": after_atr - after_relative_strength,
            "rejected_ma200": after_relative_strength - after_ma200,
            "rejected_high_52w": after_ma200 - after_high_52w,
            "rejected_weekly": after_high_52w - after_weekly,
            "rejected_market_cap": after_weekly - after_market_cap,
            "rejected_beta": after_market_cap - after_beta,
            "rejected_spread": after_beta - after_spread,
            "rejected_earnings_blackout": after_spread - after_earnings_blackout,
            "rejected_score_liquidity": after_earnings_blackout - after_score_liquidity,
            "rejected_sanitizer": after_score_liquidity - after_sanitizer,
            "rejected_anomalies": after_sanitizer - after_anomaly,
            "rejected_missing_days": after_anomaly - len(filtered),
        }
        return filtered.reset_index(drop=True), stats

    def apply_filters(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        filtered, stats = self._apply_filters_with_stats(merged_df)

        LOGGER.info(
            "Filtres appliques | entree=%s sortie=%s rejet_etf=%s rejet_historique=%s rejet_prix=%s rejet_liquidite_marche=%s rejet_volatilite_relative=%s rejet_atr_pct=%s rejet_force_relative=%s rejet_ma200=%s rejet_high_52w=%s rejet_weekly=%s rejet_market_cap=%s rejet_beta=%s rejet_spread=%s rejet_earnings_blackout=%s rejet_liquidite_scores=%s rejet_anomalies=%s rejet_missing_days=%s",
            stats["input"],
            stats["output"],
            stats["rejected_etf"],
            stats["rejected_history"],
            stats["rejected_price"],
            stats["rejected_market_liquidity"],
            stats["rejected_volatility"],
            stats["rejected_atr"],
            stats["rejected_relative_strength"],
            stats["rejected_ma200"],
            stats["rejected_high_52w"],
            stats["rejected_weekly"],
            stats["rejected_market_cap"],
            stats["rejected_beta"],
            stats["rejected_spread"],
            stats["rejected_earnings_blackout"],
            stats["rejected_score_liquidity"],
            stats["rejected_anomalies"],
            stats["rejected_missing_days"],
        )

        return filtered

    def apply_sector_neutrality(self, ranked_df: pd.DataFrame) -> pd.DataFrame:
        """Sélection round-robin avec plafond sectoriel."""
        if ranked_df.empty:
            return ranked_df.copy()

        target_size = min(self.config.selection_size, len(ranked_df))
        sector_cap = max(1, int(np.floor(self.config.selection_size * self.config.sector_cap_ratio)))
        LOGGER.info(
            "Neutralisation sectorielle | candidats=%s cible=%s plafond_par_secteur=%s",
            len(ranked_df),
            target_size,
            sector_cap,
        )
        prepared = ranked_df.copy()
        prepared["sector"] = prepared["sector"].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
        prepared = prepared.sort_values(
            ["final_score", "trend_score", "vcp_score", "avg_dollar_volume_20d"],
            ascending=False,
        ).reset_index(drop=True)

        groups = {
            sector: group.reset_index(drop=True)
            for sector, group in prepared.groupby("sector", sort=False)
        }
        pointers = {sector: 0 for sector in groups}
        counts: Counter[str] = Counter()
        selected_rows: list[pd.Series] = []

        while len(selected_rows) < target_size:
            available: list[tuple[float, str]] = []
            for sector, group in groups.items():
                sector_name = str(sector)
                pointer = pointers[sector]
                if (sector_name != "Unknown" and counts[sector_name] >= sector_cap) or pointer >= len(group):
                    continue
                available.append((float(group.iloc[pointer]["final_score"]), sector_name))

            if not available:
                break

            for _, sector in sorted(available, key=lambda item: item[0], reverse=True):
                if len(selected_rows) >= target_size:
                    break
                pointer = pointers[sector]
                group = groups[sector]
                if (sector != "Unknown" and counts[sector] >= sector_cap) or pointer >= len(group):
                    continue
                selected_rows.append(group.iloc[pointer])
                pointers[sector] += 1
                counts[sector] += 1

        if not selected_rows:
            return prepared.iloc[0:0].copy()

        selected = pd.DataFrame(selected_rows).reset_index(drop=True)
        LOGGER.info(
            "Neutralisation terminee | retenus=%s secteurs=%s repartition=%s",
            len(selected),
            selected["sector"].nunique(),
            selected["sector"].value_counts().to_dict(),
        )
        return selected

    def rank_and_select(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """Trie, neutralise par secteur et retourne le top final."""
        if merged_df.empty:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        LOGGER.info("Classement final | candidats_eligibles=%s", len(merged_df))

        ranked = merged_df.sort_values(
            ["final_score", "trend_score", "vcp_score", "avg_dollar_volume_20d"],
            ascending=False,
        ).reset_index(drop=True)
        selected = self.apply_sector_neutrality(ranked)
        if selected.empty:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        selected = selected.sort_values(
            ["final_score", "trend_score", "vcp_score", "avg_dollar_volume_20d"],
            ascending=False,
        ).reset_index(drop=True)
        selected.insert(0, "rank", np.arange(1, len(selected) + 1))
        LOGGER.info("Classement termine | selection_finale=%s top3=%s", len(selected), selected["symbol"].head(3).tolist())
        for column in OUTPUT_COLUMNS:
            if column not in selected.columns:
                selected[column] = np.nan
        return selected.loc[:, OUTPUT_COLUMNS].copy()

    def update_database(self, selected_df: pd.DataFrame, scored_df: Optional[pd.DataFrame] = None) -> int:
        """Met à jour stock_scores avec les scores selector et les candidats retenus."""
        selected_symbols = selected_df["symbol"].astype(str).dropna().tolist() if not selected_df.empty else []
        scores_snapshot = self._prepare_scores_snapshot(scored_df)
        reset_stmt = text(f"UPDATE {self.config.score_table} SET is_candidate = 0")
        score_stmt = text(
            f"""
            UPDATE {self.config.score_table}
            SET trend_score = :trend_score,
                vcp_score = :vcp_score,
                final_score = :final_score,
                market_cap = :market_cap,
                beta_126 = :beta_126,
                spread_bps = :spread_bps,
                earnings_date = :earnings_date,
                days_to_earnings = :days_to_earnings,
                earnings_blackout = :earnings_blackout,
                last_updated_scan = :updated_at
            WHERE symbol = :symbol
            """
        )
        mark_stmt = text(
            f"""
            UPDATE {self.config.score_table}
            SET is_candidate = 1
            WHERE symbol IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))
        updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        LOGGER.info(
            "Mise a jour DB | table=%s snapshot_scores=%s candidats=%s batch_size=%s",
            self.config.score_table,
            len(scores_snapshot),
            len(selected_symbols),
            self.config.update_batch_size,
        )

        try:
            with self.engine.begin() as conn:
                for start in range(0, len(scores_snapshot), self.config.update_batch_size):
                    score_batch = [
                        {**row, "updated_at": updated_at}
                        for row in scores_snapshot[start:start + self.config.update_batch_size]
                    ]
                    if not score_batch:
                        continue
                    conn.execute(score_stmt, score_batch)
                    LOGGER.info(
                        "Mise a jour DB | scores selector batch=%s-%s taille=%s",
                        start + 1,
                        start + len(score_batch),
                        len(score_batch),
                    )
                conn.execute(reset_stmt)
                LOGGER.info("Mise a jour DB | reset is_candidate=0 effectue")
                for start in range(0, len(selected_symbols), self.config.update_batch_size):
                    batch = selected_symbols[start:start + self.config.update_batch_size]
                    if not batch:
                        continue
                    conn.execute(mark_stmt, {"updated_at": updated_at, "symbols": batch})
                    LOGGER.info(
                        "Mise a jour DB | batch=%s-%s taille=%s",
                        start + 1,
                        start + len(batch),
                        len(batch),
                    )
        except SQLAlchemyError as exc:
            LOGGER.exception("Echec de mise a jour transactionnelle de %s.", self.config.score_table)
            raise RuntimeError("Impossible de mettre à jour les candidats en base.") from exc

        LOGGER.info("Mise a jour DB terminee | candidats_mis_a_jour=%s", len(selected_symbols))
        return len(selected_symbols)

    def run(self) -> pd.DataFrame:
        """Exécute le scan complet et retourne le Top N final."""
        started_at = datetime.now(timezone.utc)
        LOGGER.info(
            "Demarrage AlphaScanner | table_prix=%s table_scores=%s chunk_size=%s selection=%s workers=%s",
            self.config.price_table,
            self.config.score_table,
            self.config.chunk_size,
            self.config.selection_size,
            self._resolve_worker_count(),
        )

        self._reset_selector_outputs()

        all_frames: list[pd.DataFrame] = []
        workers = self._resolve_worker_count()
        max_in_flight = max(2, workers * 2)
        pending: set[Future[pd.DataFrame]] = set()
        submitted_chunks = 0
        completed_chunks = 0

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for symbols in self._iter_eligible_symbol_chunks():
                while len(pending) >= max_in_flight:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    completed_chunks += self._collect_completed(done, all_frames)
                    LOGGER.info(
                        "Progression scan | chunks_termines=%s chunks_soumis=%s en_vol=%s candidats_cumules=%s",
                        completed_chunks,
                        submitted_chunks,
                        len(pending),
                        sum(len(frame) for frame in all_frames),
                    )
                pending.add(executor.submit(self._process_chunk, symbols))
                submitted_chunks += 1
                LOGGER.info(
                    "Chunk soumis | index=%s taille=%s en_vol=%s",
                    submitted_chunks,
                    len(symbols),
                    len(pending),
                )

            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                completed_chunks += self._collect_completed(done, all_frames)
                LOGGER.info(
                    "Progression scan | chunks_termines=%s chunks_soumis=%s en_vol=%s candidats_cumules=%s",
                    completed_chunks,
                    submitted_chunks,
                    len(pending),
                    sum(len(frame) for frame in all_frames),
                )

        merged_candidates = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
        LOGGER.info("Agregation terminee | lignes_candidates=%s", len(merged_candidates))

        # Neutralisation cross-sectorielle sur l'univers COMPLET (après concat de tous les chunks).
        # Cette étape doit impérativement se faire ici et non dans _process_chunk,
        # car le z-score intra-secteur n'est significatif que sur l'univers entier.
        merged_candidates = self._apply_factor_neutralization(merged_candidates)

        selected = self.rank_and_select(merged_candidates)


        self.update_database(selected, merged_candidates)

        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()

        # --- Monitoring : alerte si le pipeline produit 0 candidats (P1) ---
        # Causes possibles : seuil de liquidité trop élevé, table stock_bars_daily vide,
        # critères Minervini trop stricts en marché baissier.
        # LOGGER.critical() est visible dans les outils de monitoring (Datadog, CloudWatch…).
        if selected.empty:
            LOGGER.critical(
                "AlphaScanner a produit 0 candidats | duree=%.2fs | "
                "Verifier : stock_bars_daily peuplee ? liquidity_threshold trop eleve ? "
                "Marche en tendance baissiere (trend_score=0 pour tous) ?",
                elapsed,
            )
        else:
            LOGGER.info("AlphaScanner termine en %.2fs | candidats=%s", elapsed, len(selected))

        return selected

    def _process_chunk(self, symbols: Sequence[str], as_of_date: date | None = None) -> pd.DataFrame:
        try:
            LOGGER.debug("Debut chunk | symboles=%s", len(symbols))
            market_data = self.fetch_market_data(symbols)
            computed = self.compute_factors(market_data)
            scores = self.fetch_scores(symbols)
            metadata_df = self.fetch_instrument_metadata(symbols)
            quotes_df = self.fetch_quote_snapshots(symbols, reference_date=as_of_date)
            earnings_df = self.fetch_next_earnings(symbols, reference_date=as_of_date)
            merged = self.merge_scores(computed, scores)
            merged = self._enrich_and_filter_equities(merged, metadata_df)
            merged = self._merge_optional_symbol_overlays(merged, quotes_df, earnings_df)
            filtered = self.apply_filters(merged)
            LOGGER.debug(
                "Fin chunk | symboles=%s lignes_market=%s facteurs=%s scores=%s metadata=%s quotes=%s earnings=%s fusion=%s filtre=%s",
                len(symbols),
                len(market_data),
                len(computed),
                len(scores),
                len(metadata_df),
                len(quotes_df),
                len(earnings_df),
                len(merged),
                len(filtered),
            )
            return filtered
        except Exception:
            LOGGER.exception("Chunk en echec | symboles=%s", len(symbols))
            return pd.DataFrame()

    def _collect_completed(self, done: set[Future[pd.DataFrame]], all_frames: list[pd.DataFrame]) -> int:
        completed = 0
        for future in done:
            frame = future.result()
            completed += 1
            if not frame.empty:
                all_frames.append(frame)
        return completed

    def _resolve_worker_count(self) -> int:
        if self.config.max_workers is not None:
            return self.config.max_workers
        return min(8, os.cpu_count() or 1)

    def _reset_selector_outputs(self) -> None:
        reset_stmt = text(
            f"""
            UPDATE {self.config.score_table}
            SET trend_score = NULL,
                vcp_score = NULL,
                final_score = NULL,
                market_cap = NULL,
                beta_126 = NULL,
                spread_bps = NULL,
                earnings_date = NULL,
                days_to_earnings = NULL,
                earnings_blackout = 0,
                is_candidate = 0
            """
        )

        LOGGER.info(
            "Reset selector avant run | table=%s colonnes=[trend_score, vcp_score, final_score, market_cap, beta_126, spread_bps, earnings_date, days_to_earnings, earnings_blackout, is_candidate]",
            self.config.score_table,
        )
        try:
            with self.engine.begin() as conn:
                conn.execute(reset_stmt)
        except SQLAlchemyError as exc:
            LOGGER.exception("Echec du reset selector sur %s.", self.config.score_table)
            raise RuntimeError("Impossible de réinitialiser les colonnes selector avant exécution.") from exc

    def _prepare_scores_snapshot(self, scored_df: Optional[pd.DataFrame]) -> list[dict[str, object]]:
        if scored_df is None or scored_df.empty:
            return []

        available_columns = [column for column in PERSISTED_SELECTOR_SCORE_COLUMNS if column in scored_df.columns]
        if available_columns != PERSISTED_SELECTOR_SCORE_COLUMNS:
            missing = [column for column in PERSISTED_SELECTOR_SCORE_COLUMNS if column not in available_columns]
            raise ValueError(f"Colonnes selector manquantes pour persistance: {missing}")

        snapshot = scored_df.loc[:, PERSISTED_SELECTOR_SCORE_COLUMNS].copy()
        snapshot = snapshot.dropna(subset=["symbol"]).drop_duplicates(subset=["symbol"], keep="last")
        for column in ["trend_score", "vcp_score", "final_score"]:
            snapshot[column] = pd.to_numeric(snapshot[column], errors="coerce")
        for column in ["market_cap", "beta_126", "spread_bps"]:
            snapshot[column] = pd.to_numeric(snapshot[column], errors="coerce")
        snapshot["days_to_earnings"] = pd.to_numeric(snapshot["days_to_earnings"], errors="coerce")
        snapshot["earnings_blackout"] = (
            pd.to_numeric(snapshot["earnings_blackout"], errors="coerce")
            .fillna(0)
            .astype(int)
        )
        snapshot["earnings_date"] = pd.to_datetime(snapshot["earnings_date"], errors="coerce", utc=False).dt.date

        snapshot = snapshot.astype(object)
        snapshot = snapshot.where(pd.notna(snapshot), None)
        return snapshot.to_dict(orient="records")

    def _enrich_and_filter_equities(self, merged_df: pd.DataFrame, metadata_df: pd.DataFrame) -> pd.DataFrame:
        if merged_df.empty:
            return merged_df.copy()
        if metadata_df.empty:
            LOGGER.info(
                "Filtre instruments | entree=%s sortie_actions=%s exclus_total=%s detail=%s",
                len(merged_df),
                len(merged_df),
                0,
                {"metadata_unavailable": 0},
            )
            return merged_df.copy()

        metadata = metadata_df.copy()
        metadata = metadata.drop_duplicates(subset=["symbol"], keep="last")
        for column in METADATA_COLUMNS:
            if column not in metadata.columns:
                metadata[column] = pd.NA
        metadata["company_name"] = metadata["company_name"].fillna("").astype(str)
        metadata["asset_class"] = metadata["asset_class"].fillna("").astype(str).str.lower()
        metadata["status"] = metadata["status"].fillna("").astype(str).str.lower()
        metadata["tradable"] = metadata["tradable"].fillna(False).astype(bool)
        metadata["bars_available"] = metadata["bars_available"].fillna(False).astype(bool)
        metadata["history_status"] = metadata["history_status"].fillna("").astype(str).str.lower().str.strip()

        requested_symbols = merged_df["symbol"].astype(str)
        requested_symbol_set = set(requested_symbols)
        metadata = metadata[metadata["symbol"].astype(str).isin(requested_symbol_set)].copy()

        company_name_normalized = metadata["company_name"].str.lower()
        etf_mask = company_name_normalized.apply(
            lambda value: any(pattern in value for pattern in ETF_NAME_PATTERNS)
        )
        reason_masks = {
            "metadata_missing": pd.Index(sorted(requested_symbol_set.difference(set(metadata["symbol"].astype(str))))),
            "non_us_equity": metadata.loc[metadata["asset_class"] != "us_equity", "symbol"],
            "inactive": metadata.loc[metadata["status"] != "active", "symbol"],
            "non_tradable": metadata.loc[~metadata["tradable"], "symbol"],
            "bars_unavailable": metadata.loc[~metadata["bars_available"], "symbol"],
            "history_no_history": metadata.loc[metadata["history_status"] == HISTORY_STATUS_NO_HISTORY, "symbol"],
            "history_provider_error": metadata.loc[metadata["history_status"] == HISTORY_STATUS_PROVIDER_ERROR, "symbol"],
            "history_suspended_or_stale": metadata.loc[metadata["history_status"] == HISTORY_STATUS_SUSPENDED_OR_STALE, "symbol"],
            "history_excluded_by_policy": metadata.loc[metadata["history_status"] == HISTORY_STATUS_EXCLUDED_BY_POLICY, "symbol"],
            "etf_name": metadata.loc[etf_mask, "symbol"],
        }
        exclusion_details = {
            reason: sorted({str(symbol) for symbol in symbols if str(symbol) in requested_symbol_set})
            for reason, symbols in reason_masks.items()
        }
        exclusion_counts = {
            reason: len(symbols)
            for reason, symbols in exclusion_details.items()
            if len(symbols) > 0
        }

        disqualified_symbols = {
            symbol
            for symbols in exclusion_details.values()
            for symbol in symbols
        }
        eligible_symbols = sorted(requested_symbol_set.difference(disqualified_symbols))

        eligible_metadata_columns = ["symbol", "sector", "history_status"]
        if "market_cap" in metadata.columns:
            eligible_metadata_columns.append("market_cap")
        eligible_metadata = metadata.loc[
            metadata["symbol"].astype(str).isin(eligible_symbols),
            eligible_metadata_columns,
        ].copy()
        enriched = merged_df.merge(eligible_metadata, on="symbol", how="inner", suffixes=("", "_meta"))
        if "sector_meta" in enriched.columns:
            enriched["sector"] = enriched["sector_meta"].where(
                enriched["sector_meta"].notna() & (enriched["sector_meta"].astype(str).str.strip() != ""),
                enriched.get("sector"),
            )
            enriched = enriched.drop(columns=["sector_meta"])
        if "market_cap_meta" in enriched.columns:
            enriched["market_cap"] = pd.to_numeric(enriched["market_cap_meta"], errors="coerce").combine_first(
                pd.to_numeric(enriched.get("market_cap"), errors="coerce")
            )
            enriched = enriched.drop(columns=["market_cap_meta"])

        LOGGER.info(
            "Filtre instruments | entree=%s sortie_actions=%s exclus_total=%s detail=%s",
            len(merged_df),
            len(enriched),
            len(merged_df) - len(enriched),
            exclusion_counts,
        )
        if exclusion_counts:
            LOGGER.debug(
                "Filtre instruments details symboles | %s",
                {reason: symbols[:5] for reason, symbols in exclusion_details.items() if symbols},
            )
        return enriched.reset_index(drop=True)

    def _merge_optional_symbol_overlays(
        self,
        merged_df: pd.DataFrame,
        quotes_df: pd.DataFrame,
        earnings_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if merged_df.empty:
            return merged_df.copy()

        enriched = merged_df.copy()

        if not quotes_df.empty:
            latest_quotes = quotes_df[["symbol", "spread_bps"]].drop_duplicates(subset=["symbol"], keep="last")
            enriched = enriched.merge(latest_quotes, on="symbol", how="left", suffixes=("", "_quote"))
            if "spread_bps_quote" in enriched.columns:
                enriched["spread_bps"] = pd.to_numeric(enriched["spread_bps_quote"], errors="coerce").combine_first(
                    pd.to_numeric(enriched.get("spread_bps"), errors="coerce")
                )
                enriched = enriched.drop(columns=["spread_bps_quote"])

        if not earnings_df.empty:
            latest_earnings = earnings_df[
                ["symbol", "earnings_date", "days_to_earnings", "earnings_blackout"]
            ].drop_duplicates(subset=["symbol"], keep="last")
            enriched = enriched.merge(latest_earnings, on="symbol", how="left", suffixes=("", "_earnings"))
            if "earnings_date_earnings" in enriched.columns:
                enriched["earnings_date"] = enriched["earnings_date_earnings"].combine_first(enriched.get("earnings_date"))
                enriched = enriched.drop(columns=["earnings_date_earnings"])
            if "days_to_earnings_earnings" in enriched.columns:
                existing_days_to_earnings = (
                    pd.to_numeric(enriched["days_to_earnings"], errors="coerce")
                    if "days_to_earnings" in enriched.columns
                    else pd.Series(index=enriched.index, dtype=float)
                )
                overlay_days_to_earnings = pd.to_numeric(
                    enriched["days_to_earnings_earnings"], errors="coerce"
                )
                enriched["days_to_earnings"] = overlay_days_to_earnings.where(
                    overlay_days_to_earnings.notna(),
                    existing_days_to_earnings,
                )
                enriched = enriched.drop(columns=["days_to_earnings_earnings"])
            if "earnings_blackout_earnings" in enriched.columns:
                existing_earnings_blackout = (
                    pd.to_numeric(enriched["earnings_blackout"], errors="coerce")
                    if "earnings_blackout" in enriched.columns
                    else pd.Series(index=enriched.index, dtype=float)
                )
                overlay_earnings_blackout = pd.to_numeric(
                    enriched["earnings_blackout_earnings"], errors="coerce"
                )
                enriched["earnings_blackout"] = overlay_earnings_blackout.where(
                    overlay_earnings_blackout.notna(),
                    existing_earnings_blackout,
                )
                enriched = enriched.drop(columns=["earnings_blackout_earnings"])

        return enriched

    def _iter_eligible_symbol_chunks(self) -> Iterator[list[str]]:
        """Filtre SQL brut: liquidité 20j, close > 5, historique >= 252 jours,
        actions US uniquement (asset_class='us_equity', tradable=1, exclut ETF/crypto)."""
        offset = 0
        history_status_filter = ""
        if "history_status" in self._get_stock_metadata_columns():
            eligible_statuses = ", ".join(f"'{status}'" for status in sorted(ELIGIBLE_HISTORY_STATUSES))
            history_status_filter = f"""
                  AND (
                        sm.history_status IS NULL
                     OR TRIM(sm.history_status) = ''
                     OR LOWER(TRIM(sm.history_status)) IN ({eligible_statuses})
                  )
            """
        stmt = text(
            f"""
            WITH ranked AS (
                SELECT symbol,
                       date,
                       close,
                       volume,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                FROM {self.config.price_table}
            ), eligible AS (
                SELECT r.symbol
                FROM ranked r
                INNER JOIN stock_metadata sm ON sm.symbol = r.symbol
                WHERE sm.asset_class = 'us_equity'
                  AND sm.tradable    = 1
                  AND sm.status      = 'active'
                  AND sm.bars_available = 1
                  {history_status_filter}
                GROUP BY r.symbol
                HAVING COUNT(*) >= :min_history_days
                   AND MAX(CASE WHEN rn = 1 THEN close END) > :min_close
                   AND AVG(CASE WHEN rn <= :liquidity_lookback_days THEN close * volume END) > :liquidity_threshold
            )
            SELECT symbol
            FROM eligible
            ORDER BY symbol
            LIMIT :limit OFFSET :offset
            """
        )

        while True:
            try:
                with self.engine.connect() as conn:
                    rows = conn.execute(
                        stmt,
                        {
                            "min_history_days": self.config.min_history_days,
                            "min_close": self.config.min_close,
                            "liquidity_lookback_days": self.config.liquidity_lookback_days,
                            "liquidity_threshold": self.config.liquidity_threshold,
                            "limit": self.config.chunk_size,
                            "offset": offset,
                        },
                    ).fetchall()
            except SQLAlchemyError as exc:
                LOGGER.exception("Echec de la preselection SQL sur %s.", self.config.price_table)
                raise RuntimeError("Impossible de présélectionner les symboles.") from exc

            symbols = [str(row[0]) for row in rows]
            if not symbols:
                break

            LOGGER.info(
                "Preselection SQL | offset=%s chunk_size=%s retournes=%s",
                offset,
                self.config.chunk_size,
                len(symbols),
            )
            yield symbols
            offset += self.config.chunk_size

    @staticmethod
    def _winsorize_and_normalize(
        series: Optional[pd.Series],
        lower_pct: float = 0.01,
        upper_pct: float = 0.99,
    ) -> pd.Series:
        """
        Winsorise [lower_pct, upper_pct] puis normalise en [0, 1] (min-max).

        Remplace le min-max pur (_normalize_zero_one) qui était sensible aux outliers :
        1 seule valeur extrême compressait tous les autres scores vers 0 ou 1.

        :param lower_pct: Percentile inférieur de winsorisation (défaut 1 %).
        :param upper_pct: Percentile supérieur de winsorisation (défaut 99 %).
        """
        if series is None:
            return pd.Series(dtype=float)

        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.empty:
            return pd.Series(dtype=float)

        non_null = numeric.dropna()
        if non_null.empty:
            return pd.Series(np.nan, index=numeric.index, dtype=float)

        lo = float(non_null.quantile(lower_pct))
        hi = float(non_null.quantile(upper_pct))
        winsorized = numeric.clip(lo, hi)

        if np.isclose(hi, lo):
            result = pd.Series(np.nan, index=numeric.index, dtype=float)
            result.loc[non_null.index] = 0.5
            return result

        return ((winsorized - lo) / (hi - lo)).clip(0.0, 1.0)

    # Alias de compatibilité conservé pour les appelants externes éventuels.
    @staticmethod
    def _normalize_zero_one(series: Optional[pd.Series]) -> pd.Series:
        """Déprécié — utiliser _winsorize_and_normalize à la place."""
        return AlphaScanner._winsorize_and_normalize(series)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AlphaScanner multi-facteurs")
    parser.add_argument("--preset", choices=["strict"], default="strict", help=argparse.SUPPRESS)
    parser.add_argument("--chunk-size", type=int, default=500, help="Taille des chunks de symboles")
    parser.add_argument("--selection-size", type=int, default=50, help="Nombre final de titres à retenir")
    parser.add_argument("--max-workers", type=int, default=None, help="Nombre maximum de threads")
    parser.add_argument("--liquidity-threshold", type=float, default=None, help="Seuil minimal de liquidité en dollar volume moyen 20j")
    parser.add_argument("--min-close", type=float, default=None, help="Prix minimal de clôture")
    parser.add_argument("--max-volatility-ratio", type=float, default=None, help="Seuil maximal optionnel du ratio de volatilité récente vol10/vol60")
    parser.add_argument("--min-relative-strength-index", type=float, default=None, help="Force relative minimale vs SPY (100 = performance égale au benchmark)")
    parser.add_argument("--min-high-52w-proximity", type=float, default=None, help="Proximité minimale du high 52 semaines en ratio close/high_52w")
    parser.add_argument("--min-weekly-trend-score", type=float, default=None, help="Score trend weekly minimal sur [0,1]")
    parser.add_argument("--min-atr-pct-20", type=float, default=None, help="ATR20 minimale en pourcentage du prix, ex. 0.02 = 2%%")
    parser.add_argument("--max-atr-pct-20", type=float, default=None, help="ATR20 maximale en pourcentage du prix, ex. 0.05 = 5%%")
    parser.add_argument("--min-market-cap", type=float, default=None, help="Capitalisation minimale, ex. 2000000000 = 2 Md$")
    parser.add_argument("--min-beta-126", type=float, default=None, help="Beta minimale calculée sur 126 séances vs SPY")
    parser.add_argument("--max-spread-bps", type=float, default=None, help="Spread bid/ask maximal en basis points")
    parser.add_argument("--earnings-blackout-days", type=int, default=None, help="Exclut les titres dont les résultats tombent dans les N prochains jours")
    parser.add_argument("--require-above-ma200", action="store_true", default=False, help="Exige latest_close > MA200")
    parser.add_argument("--max-anomaly-count", type=int, default=20, help="Nombre maximum d'anomalies accepté par titre")
    parser.add_argument("--sector-cap-ratio", type=float, default=0.30, help="Plafond par secteur, ex. 0.30 = 30%")
    parser.add_argument("--log-level", type=str, default="INFO", help="Niveau de log (DEBUG, INFO, WARNING, ERROR)")
    return parser


def _build_config_from_args(args: argparse.Namespace) -> AlphaScannerConfig:
    threshold_overrides: dict[str, object] = {}
    if args.liquidity_threshold is not None:
        threshold_overrides["liquidity_threshold"] = args.liquidity_threshold
    if args.min_close is not None:
        threshold_overrides["min_close"] = args.min_close
    if args.max_volatility_ratio is not None:
        threshold_overrides["max_volatility_ratio"] = args.max_volatility_ratio
    if args.min_relative_strength_index is not None:
        threshold_overrides["min_relative_strength_index"] = args.min_relative_strength_index
    if args.min_high_52w_proximity is not None:
        threshold_overrides["min_high_52w_proximity"] = args.min_high_52w_proximity
    if args.min_weekly_trend_score is not None:
        threshold_overrides["min_weekly_trend_score"] = args.min_weekly_trend_score
    if args.min_atr_pct_20 is not None:
        threshold_overrides["min_atr_pct_20"] = args.min_atr_pct_20
    if args.max_atr_pct_20 is not None:
        threshold_overrides["max_atr_pct_20"] = args.max_atr_pct_20
    if args.min_market_cap is not None:
        threshold_overrides["min_market_cap"] = args.min_market_cap
    if args.min_beta_126 is not None:
        threshold_overrides["min_beta_126"] = args.min_beta_126
    if args.max_spread_bps is not None:
        threshold_overrides["max_spread_bps"] = args.max_spread_bps
    if args.earnings_blackout_days is not None:
        threshold_overrides["earnings_blackout_days"] = args.earnings_blackout_days
    if args.require_above_ma200:
        threshold_overrides["require_above_ma200"] = True

    common_kwargs = {
        "chunk_size": args.chunk_size,
        "selection_size": args.selection_size,
        "max_workers": args.max_workers,
        "max_anomaly_count": args.max_anomaly_count,
        "sector_cap_ratio": args.sector_cap_ratio,
        **threshold_overrides,
    }

    if args.preset == "strict":
        return AlphaScannerConfig.strict_swing_cash(**common_kwargs)
    return AlphaScannerConfig.strict_swing_cash(**common_kwargs)


def main() -> None:
    args = _build_arg_parser().parse_args()
    configure_root_logging(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        log_path="./log/alpha_scanner.log",
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    config = _build_config_from_args(args)

    result = AlphaScanner(config=config).run()

    if result.empty:
        print("Aucun candidat retenu.")
        return

    display_columns = [
        column
        for column in ["rank", "symbol", "sector", "final_score", "trend_score", "vcp_score"]
        if column in result.columns
    ]
    print(result.loc[:, display_columns].to_string(index=False))


if __name__ == "__main__":
    main()



