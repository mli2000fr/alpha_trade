from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from backtesting.data_loader import get_required_bars_source_filter, load_ohlcv, pivot_ohlcv
from backtesting.report import (
    BacktestReport,
    extract_diagnostics,
    generate_report,
    save_equity_curve,
    save_equity_curve_csv,
    save_report_json,
    save_trades_csv,
)
from backtesting.simulator import BacktestConfig, BacktestEngine
from common.utils import configure_root_logging
from database.connection import get_sqlalchemy_engine
from database.run_business_summaries import persist_run_business_summary
from event_sentiment.signal_aggregator import SentimentSignalAggregator

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
STEP_KEY = "backtesting_sentiment_calibration"


def _normalize_preset_keys(
    keys: str | list[str] | None,
) -> list[str] | None:
    """Normalise les clés de preset capital en liste ou None (tous)."""
    if keys is None:
        return None
    if isinstance(keys, str):
        keys = [k.strip() for k in keys.split(",") if k.strip()]
        return keys if keys else None
    if isinstance(keys, list):
        cleaned = [str(k).strip() for k in keys if str(k).strip()]
        return cleaned if cleaned else None
    return None


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


@dataclass(frozen=True, slots=True)
class SentimentCalibrationScenario:
    sentiment_weight: float
    macro_weight: float
    quant_weight: float

    @property
    def scenario_name(self) -> str:
        return f"sent_{self.sentiment_weight:.2f}_macro_{self.macro_weight:.2f}_quant_{self.quant_weight:.2f}"


@dataclass(frozen=True, slots=True)
class SentimentCalibrationResult:
    start_date: date
    end_date: date
    scenarios_evaluated: int
    rows_evaluated: int
    best_scenario_name: str
    best_overall_score: float
    artifact_dir: str | None = None


@dataclass(frozen=True, slots=True)
class WalkForwardFoldResult:
    fold_index: int
    train_start_date: date
    train_end_date: date
    test_start_date: date
    test_end_date: date
    best_scenario_name: str
    best_train_overall_score: float
    out_of_sample_overall_score: float
    rows_tested: int
    trading_days_tested: int


@dataclass(frozen=True, slots=True)
class WalkForwardCalibrationResult:
    start_date: date
    end_date: date
    folds_evaluated: int
    scenarios_evaluated: int
    out_of_sample_rows: int
    out_of_sample_days: int
    latest_best_scenario_name: str
    final_value: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    artifact_dir: str | None = None


class SentimentWeightCalibrator:
    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or get_sqlalchemy_engine()

    @staticmethod
    def default_scenarios() -> list[SentimentCalibrationScenario]:
        """Grille de scénarios pour la calibration walk-forward.

        Diagnostic empirique (capital_2001_5000, 2024-2025) :
        - macro_weight : IC ≈ 0, t-stat ≈ 0 → fixé à 0.0 (désactivé)
        - sentiment_weight : IC ≈ 0.01, t-stat ≈ 1.1 → plage réduite [0.00, 0.10]
        - quant_weight : IC ≈ 0.03, t-stat ≈ 2.5 → seul signal significatif

        La grille explore 11 scénarios : sentiment ∈ {0.00, 0.02, 0.05, 0.08, 0.10}
        avec quant = 1.0 - sentiment, macro = 0.0. On ajoute aussi des variantes
        avec un peu de macro pour validation croisée (macro=0.02).
        """
        scenarios: list[SentimentCalibrationScenario] = []
        # Scénarios principaux : macro = 0.0, sentiment variable
        for sentiment_weight in (0.00, 0.02, 0.05, 0.08, 0.10):
            quant_weight = round(1.0 - sentiment_weight, 6)
            scenarios.append(
                SentimentCalibrationScenario(
                    sentiment_weight=round(sentiment_weight, 4),
                    macro_weight=0.0,
                    quant_weight=quant_weight,
                )
            )
        # Scénarios de validation croisée : macro = 0.02, sentiment variable
        for sentiment_weight in (0.00, 0.02, 0.05, 0.08):
            quant_weight = round(1.0 - sentiment_weight - 0.02, 6)
            if quant_weight < 0.80:
                continue
            scenarios.append(
                SentimentCalibrationScenario(
                    sentiment_weight=round(sentiment_weight, 4),
                    macro_weight=0.02,
                    quant_weight=quant_weight,
                )
            )
        return scenarios

    def load_dataset(
        self,
        start_date: date,
        end_date: date,
        horizons: tuple[int, ...] = (5, 10, 20),
        candidates_only: bool = True,
        capital_preset_keys: str | list[str] | None = None,
    ) -> pd.DataFrame:
        """Charge le dataset scores + forward returns.

        Traitement symbole par symbole : chaque batch SQL (300 symboles) est
        découpé en traitements unitaires. ``build_forward_return_frame`` ne
        voit qu'un seul symbole à la fois → pic RAM minimal (~60K lignes).
        """
        buffer_days = max(horizons) * 3
        end_date_plus_buffer = end_date + pd.Timedelta(days=buffer_days)

        symbols = self._list_symbols(
            start_date=start_date,
            end_date=end_date,
            candidates_only=candidates_only,
            capital_preset_keys=capital_preset_keys,
        )
        if not symbols:
            return pd.DataFrame()

        final_frames: list[pd.DataFrame] = []
        batch_size = 300
        total_symbols = len(symbols)
        processed = 0
        LOGGER.info("Chargement dataset | symboles=%d batches=%d batch_size=%d",
                     total_symbols, (total_symbols + batch_size - 1) // batch_size, batch_size)
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_symbols + batch_size - 1) // batch_size
            LOGGER.info("Batch %d/%d | %d symboles | chargement SQL...",
                         batch_num, total_batches, len(batch))
            # 1. Charger le raw pour tout le batch (un seul SQL)
            batch_raw = self._load_dataset_batch_sql(
                batch_symbols=batch,
                start_date=start_date,
                end_date=end_date,
                end_date_plus_buffer=end_date_plus_buffer,
                candidates_only=candidates_only,
                capital_preset_keys=capital_preset_keys,
            )
            if batch_raw.empty:
                LOGGER.info("Batch %d/%d | aucun résultat, skip.", batch_num, total_batches)
                continue

            raw_rows = len(batch_raw)
            LOGGER.info("Batch %d/%d | %d lignes raw chargées | traitement symbole par symbole...",
                         batch_num, total_batches, raw_rows)
            # 2. Traiter symbole par symbole (évite les copies massives)
            batch_processed = 0
            for sym in batch:
                sym_raw = batch_raw[batch_raw["symbol"] == sym]
                if sym_raw.empty:
                    continue
                sym_final = self.build_forward_return_frame(sym_raw, horizons=horizons)
                if not sym_final.empty:
                    final_frames.append(sym_final)
                    batch_processed += 1
                processed += 1
                if processed % 500 == 0:
                    LOGGER.info("Progression | %d/%d symboles traités (%d lignes finales accumulées)",
                                 processed, total_symbols, sum(len(f) for f in final_frames))

            # 3. Libérer le raw du batch avant de passer au suivant
            del batch_raw
            LOGGER.info("Batch %d/%d terminé | %d symboles produisant des données | %d/%d symboles totaux",
                         batch_num, total_batches, batch_processed, processed, total_symbols)

        total_rows = sum(len(f) for f in final_frames)
        LOGGER.info("Chargement dataset terminé | %d symboles → %d lignes finales",
                     processed, total_rows)

        if not final_frames:
            return pd.DataFrame()
        return pd.concat(final_frames, ignore_index=True)

    def _list_symbols(
        self,
        start_date: date,
        end_date: date,
        candidates_only: bool = True,
        capital_preset_keys: str | list[str] | None = None,
    ) -> list[str]:
        """Retourne la liste des symboles distincts sur la période."""
        preset_clause = ""
        params: dict[str, object] = {
            "start_date": start_date,
            "end_date": end_date,
            "candidates_only": 1 if candidates_only else 0,
        }
        keys = _normalize_preset_keys(capital_preset_keys)
        if keys is not None:
            preset_clause = "AND h.capital_preset_key IN :capital_preset_keys"
            params["capital_preset_keys"] = tuple(keys)
        query = text(
            f"""
            SELECT DISTINCT h.symbol
            FROM stock_scores_history h
            WHERE h.snapshot_date BETWEEN :start_date AND :end_date
              AND (:candidates_only = 0 OR h.is_candidate = 1)
              {preset_clause}
            ORDER BY h.symbol
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query, params).scalars().all()
        return [str(r) for r in rows]

    def _load_dataset_batch_sql(
        self,
        batch_symbols: list[str],
        start_date: date,
        end_date: date,
        end_date_plus_buffer: date,
        candidates_only: bool = True,
        capital_preset_keys: str | list[str] | None = None,
    ) -> pd.DataFrame:
        """Range-JOIN SQL pour un batch de symboles.

        Le JOIN ``b.date >= h.snapshot_date AND b.date <= buffer`` est exécuté
        côté MySQL avec les index, produisant uniquement les lignes nécessaires
        (pas de cartésien pandas).
        """
        source_filter_sql, source_filter_params = get_required_bars_source_filter(
            self.engine,
            table_name="stock_bars_daily",
            table_alias="b",
        )
        escaped = ", ".join([f"'{sym.replace(chr(39), '')}'" for sym in batch_symbols])
        preset_clause = ""
        params: dict[str, object] = {
            "start_date": start_date,
            "end_date": end_date,
            "end_date_plus_buffer": end_date_plus_buffer,
            "candidates_only": 1 if candidates_only else 0,
            **source_filter_params,
        }
        keys = _normalize_preset_keys(capital_preset_keys)
        if keys is not None:
            preset_clause = "AND h.capital_preset_key IN :capital_preset_keys"
            params["capital_preset_keys"] = tuple(keys)

        query = text(
            f"""
            SELECT
                h.snapshot_date,
                h.symbol,
                h.sector,
                h.final_score,
                h.sentiment_net_agg,
                h.sector_impact_agg,
                h.final_score_sentiment,
                h.short_score,
                h.is_candidate,
                b.date AS bar_date,
                COALESCE(b.adj_close, b.close) AS close_price
            FROM stock_scores_history h
            JOIN stock_bars_daily b
              ON b.symbol = h.symbol
             AND b.date >= h.snapshot_date
             AND b.date <= :end_date_plus_buffer
             {source_filter_sql}
            WHERE h.symbol IN ({escaped})
              AND h.snapshot_date BETWEEN :start_date AND :end_date
              AND (:candidates_only = 0 OR h.is_candidate = 1)
              {preset_clause}
            ORDER BY h.snapshot_date, h.symbol, b.date
            """
        )
        with self.engine.connect() as conn:
            raw = pd.read_sql_query(query, conn, params=params)
        return raw

    @staticmethod
    def build_forward_return_frame(raw: pd.DataFrame, horizons: tuple[int, ...] = (5, 10, 20)) -> pd.DataFrame:
        if raw.empty:
            return pd.DataFrame()

        base_columns = [
            "snapshot_date",
            "symbol",
            "sector",
            "final_score",
            "sentiment_net_agg",
            "sector_impact_agg",
            "final_score_sentiment",
            "short_score",
            "is_candidate",
        ]
        snapshot_df = raw[base_columns].drop_duplicates(subset=["snapshot_date", "symbol"], keep="first").copy()
        price_df = raw[["snapshot_date", "symbol", "bar_date", "close_price"]].copy()
        price_df = price_df.sort_values(["snapshot_date", "symbol", "bar_date"]).reset_index(drop=True)

        forward_map: dict[tuple[pd.Timestamp, str], dict[str, float]] = {}
        for (snapshot_date, symbol), group in price_df.groupby(["snapshot_date", "symbol"], sort=False):
            ordered = group.sort_values("bar_date").reset_index(drop=True)
            if ordered.empty:
                continue
            entry_price = float(ordered.loc[0, "close_price"])
            row_metrics: dict[str, float] = {}
            for horizon in horizons:
                if len(ordered) <= horizon:
                    row_metrics[f"forward_return_{horizon}d"] = float("nan")
                    continue
                exit_price = float(ordered.loc[horizon, "close_price"])
                row_metrics[f"forward_return_{horizon}d"] = (exit_price / entry_price) - 1.0 if entry_price else float("nan")
            forward_map[(pd.Timestamp(snapshot_date), str(symbol))] = row_metrics

        for horizon in horizons:
            snapshot_df[f"forward_return_{horizon}d"] = [
                forward_map.get((pd.Timestamp(row["snapshot_date"]), str(row["symbol"])), {}).get(f"forward_return_{horizon}d")
                for row in snapshot_df.to_dict(orient="records")
            ]
        return snapshot_df

    @staticmethod
    def _normalize_signal(series: pd.Series) -> pd.Series:
        """Normalise un signal signé [-1, 1] vers [0, 1] par ranking cross-sectional.

        Contrairement à ``_normalize_signed_signal`` (linéaire ``(x+1)/2``) qui
        écrase la dispersion quand les valeurs sont concentrées autour de 0,
        cette méthode applique un **ranking percentile par jour** sur les valeurs
        non-NaN, garantissant une distribution uniforme dans [0, 1] et donc un
        pouvoir discriminant maximal.

        Les NaN restent NaN (pas de ``fillna(0)`` qui créerait un faux signal
        neutre à 0.5). L'appelant décide du traitement (exclusion ou imputation).
        """
        numeric = pd.to_numeric(series, errors="coerce").astype(float)
        numeric = numeric.where(np.isfinite(numeric), np.nan)
        numeric = numeric.clip(-1.0, 1.0)
        return numeric.rank(pct=True, na_option="keep")

    @staticmethod
    def build_walk_forward_windows(
        snapshot_dates: Iterable[pd.Timestamp | str | datetime | date],
        *,
        min_train_days: int = 252,
        test_days: int = 63,
        step_days: int | None = None,
    ) -> list[dict[str, Any]]:
        """Construit des fenêtres walk-forward avec sémantique calendaire.

        ``min_train_days``, ``test_days`` et ``step_days`` sont désormais
        interprétés en **jours calendaires** (et non en nombre de snapshots).
        Cela garantit que des historiques PIT à fréquence irrégulière
        (ex. hebdomadaire) produisent des folds même quand le nombre de
        snapshots uniques est inférieur à ``min_train_days``.
        """
        if min_train_days <= 0:
            raise ValueError("min_train_days doit être strictement positif.")
        if test_days <= 0:
            raise ValueError("test_days doit être strictement positif.")
        if step_days is not None and step_days <= 0:
            raise ValueError("step_days doit être strictement positif s'il est fourni.")

        unique_dates = sorted(pd.to_datetime(pd.Index(list(snapshot_dates)).dropna().unique()).tolist())
        if len(unique_dates) < 2:
            LOGGER.info(
                "build_walk_forward_windows: %d snapshot(s) unique(s) → pas assez pour construire des folds.",
                len(unique_dates),
            )
            return []

        total_span_days = (unique_dates[-1] - unique_dates[0]).days
        if total_span_days < min_train_days:
            LOGGER.info(
                "build_walk_forward_windows: %d snapshots uniques couvrent %d jours calendaires, "
                "min_train_days=%d → aucune fenêtre possible.",
                len(unique_dates),
                total_span_days,
                min_train_days,
            )
            return []

        step = step_days or test_days
        windows: list[dict[str, Any]] = []

        # Trouver l'index du premier snapshot dont la date est >= first_date + min_train_days
        first_date = unique_dates[0]
        min_split_date = first_date + pd.Timedelta(days=min_train_days)
        cursor_idx: int | None = None
        for i, d in enumerate(unique_dates):
            if d >= min_split_date:
                cursor_idx = i
                break
        if cursor_idx is None or cursor_idx == 0:
            LOGGER.info(
                "build_walk_forward_windows: aucun snapshot au-delà de %s + %d jours → pas de fold.",
                first_date.date().isoformat(),
                min_train_days,
            )
            return []

        cursor_date = unique_dates[cursor_idx]
        while cursor_idx < len(unique_dates):
            train_dates_list = unique_dates[:cursor_idx]
            cursor_date = unique_dates[cursor_idx]
            test_end_date = cursor_date + pd.Timedelta(days=test_days)
            test_dates_list = [d for d in unique_dates[cursor_idx:] if d <= test_end_date]
            if not test_dates_list:
                break
            windows.append(
                {
                    "fold_index": len(windows) + 1,
                    "train_dates": train_dates_list,
                    "test_dates": test_dates_list,
                    "train_start_date": pd.Timestamp(train_dates_list[0]),
                    "train_end_date": pd.Timestamp(train_dates_list[-1]),
                    "test_start_date": pd.Timestamp(test_dates_list[0]),
                    "test_end_date": pd.Timestamp(test_dates_list[-1]),
                }
            )
            # Avancer le curseur de ``step`` jours calendaires
            next_cursor_date = cursor_date + pd.Timedelta(days=step)
            new_cursor_idx: int | None = None
            for i in range(cursor_idx + 1, len(unique_dates)):
                if unique_dates[i] >= next_cursor_date:
                    new_cursor_idx = i
                    break
            if new_cursor_idx is None:
                break
            cursor_idx = new_cursor_idx

        LOGGER.info(
            "build_walk_forward_windows: %d snapshots uniques, span=%d jours calendaires, "
            "min_train=%d test=%d step=%d → %d fold(s).",
            len(unique_dates),
            total_span_days,
            min_train_days,
            test_days,
            step,
            len(windows),
        )
        return windows

    def score_dataset_for_scenario(
        self,
        dataset: pd.DataFrame,
        scenario: SentimentCalibrationScenario,
        *,
        score_column: str = "composite_score",
    ) -> pd.DataFrame:
        if dataset.empty:
            return dataset.copy()

        scored = dataset.copy()
        scored["quant_score"] = pd.Series(
            pd.to_numeric(scored["final_score"], errors="coerce"),
            index=scored.index,
            dtype=float,
        ).fillna(0.0).clip(0.0, 1.0)
        # P2 — ranking cross-sectional : les NaN restent NaN, on les fill à 0.0
        # pour le calcul du composite (pas de contribution si pas de signal).
        scored["company_idio_signal_norm"] = self._normalize_signal(scored["sentiment_net_agg"]).fillna(0.0)
        scored["macro_regime_signal_norm"] = self._normalize_signal(scored["sector_impact_agg"]).fillna(0.0)
        scored["quant_component"] = scenario.quant_weight * scored["quant_score"]
        scored["company_idio_component"] = scenario.sentiment_weight * scored["company_idio_signal_norm"]
        scored["macro_regime_component"] = scenario.macro_weight * scored["macro_regime_signal_norm"]
        scored[score_column] = (
            scored["quant_component"]
            + scored["company_idio_component"]
            + scored["macro_regime_component"]
        ).clip(0.0, 1.0)
        scored["scenario_name"] = scenario.scenario_name
        scored["scenario_sentiment_weight"] = scenario.sentiment_weight
        scored["scenario_macro_weight"] = scenario.macro_weight
        scored["scenario_quant_weight"] = scenario.quant_weight
        return scored

    @staticmethod
    def build_portfolio_signals(
        scored_df: pd.DataFrame,
        *,
        score_column: str,
        max_positions: int,
    ) -> pd.DataFrame:
        if scored_df.empty:
            return pd.DataFrame(columns=["trade_date", "symbol", "sector", "score", "rank", "selected"])

        signals = scored_df.copy()
        signals["trade_date"] = pd.to_datetime(signals["snapshot_date"])
        signals["score"] = pd.Series(pd.to_numeric(signals[score_column], errors="coerce"), index=signals.index).fillna(0.0)
        signals["rank"] = signals.groupby("trade_date")["score"].rank(ascending=False, method="first")
        signals["selected"] = signals["rank"] <= max_positions
        keep_columns = [
            column
            for column in [
                "trade_date",
                "symbol",
                "sector",
                "score",
                "rank",
                "selected",
                "scenario_name",
                "company_idio_component",
                "macro_regime_component",
                "quant_component",
                score_column,
            ]
            if column in signals.columns
        ]
        return signals.loc[:, keep_columns].sort_values(["trade_date", "rank", "symbol"]).reset_index(drop=True)

    @staticmethod
    def build_portfolio_signals_long_short(
        scored_df: pd.DataFrame,
        *,
        score_column: str = "final_score_walk_forward",
        max_positions_long: int = 4,
        max_positions_short: int = 4,
    ) -> pd.DataFrame:
        """Construit les signaux long + short pour le walk-forward.

        Longs  : top-N par ``score_column`` décroissant, side="buy"
        Shorts : top-N par ``short_score`` décroissant, side="sell"
                 (exclut les symboles déjà sélectionnés en long)

        Retourne un DataFrame compatible avec ``BacktestEngine.run()``
        (colonnes trade_date, symbol, score, rank, selected, side).
        """
        if scored_df.empty:
            return pd.DataFrame(columns=["trade_date", "symbol", "sector", "score", "rank", "selected", "side"])

        long_frames: list[pd.DataFrame] = []
        short_frames: list[pd.DataFrame] = []

        for trade_date, daily in scored_df.groupby("snapshot_date"):
            day_df = daily.copy()
            trade_date_ts = pd.Timestamp(trade_date)

            # ── Longs ──
            long_candidates = day_df.copy()
            long_candidates["score"] = pd.to_numeric(long_candidates[score_column], errors="coerce").fillna(0.0)
            long_candidates = long_candidates.sort_values("score", ascending=False)
            n_long = min(max_positions_long, len(long_candidates))
            long_selected = long_candidates.head(n_long).copy()
            long_selected["trade_date"] = trade_date_ts
            long_selected["rank"] = range(1, n_long + 1)
            long_selected["selected"] = True
            long_selected["side"] = "buy"
            long_frames.append(long_selected)

            # ── Shorts ──
            long_symbols = set(long_selected["symbol"].tolist()) if n_long > 0 else set()
            short_candidates = day_df[~day_df["symbol"].isin(long_symbols)].copy()

            if "short_score" in short_candidates.columns:
                short_candidates["score"] = pd.to_numeric(short_candidates["short_score"], errors="coerce").fillna(0.0)
                # Exclure les short_score nuls (pas de signal baissier)
                short_candidates = short_candidates[short_candidates["score"] > 0.0]
                short_candidates = short_candidates.sort_values("score", ascending=False)
                n_short = min(max_positions_short, len(short_candidates))
                short_selected = short_candidates.head(n_short).copy()
                short_selected["trade_date"] = trade_date_ts
                short_selected["rank"] = range(1, n_short + 1)
                short_selected["selected"] = True
                short_selected["side"] = "sell"
                short_frames.append(short_selected)

        all_signals = pd.concat(long_frames + short_frames, ignore_index=True) if (long_frames or short_frames) else pd.DataFrame(
            columns=["trade_date", "symbol", "sector", "score", "rank", "selected", "side"]
        )

        if all_signals.empty:
            return all_signals

        keep_columns = [
            column
            for column in [
                "trade_date", "symbol", "sector", "score", "rank", "selected", "side",
                "scenario_name", score_column, "short_score",
            ]
            if column in all_signals.columns
        ]
        return all_signals.loc[:, keep_columns].sort_values(["trade_date", "rank", "symbol"]).reset_index(drop=True)

    @staticmethod
    def _scenario_from_row(row: dict[str, Any]) -> SentimentCalibrationScenario:
        return SentimentCalibrationScenario(
            sentiment_weight=float(row.get("sentiment_weight") or 0.0),
            macro_weight=float(row.get("macro_weight") or 0.0),
            quant_weight=float(row.get("quant_weight") or 0.0),
        )

    def evaluate_scenarios(
        self,
        dataset: pd.DataFrame,
        scenarios: Iterable[SentimentCalibrationScenario],
        horizons: tuple[int, ...] = (5, 10, 20),
        top_n: int = 20,
    ) -> pd.DataFrame:
        if dataset.empty:
            return pd.DataFrame()

        results: list[dict[str, object]] = []
        for scenario in scenarios:
            working = self.score_dataset_for_scenario(dataset, scenario, score_column="composite_score")

            metrics: dict[str, object] = {
                "scenario_name": scenario.scenario_name,
                "sentiment_weight": scenario.sentiment_weight,
                "macro_weight": scenario.macro_weight,
                "quant_weight": scenario.quant_weight,
                "rows_evaluated": int(len(working)),
                "days_evaluated": int(working["snapshot_date"].nunique()),
            }
            per_horizon_scores: list[float] = []
            for horizon in horizons:
                return_col = f"forward_return_{horizon}d"
                ic_values: list[float] = []
                top_bucket_returns: list[float] = []
                universe_returns: list[float] = []
                for _, daily in working.groupby("snapshot_date"):
                    valid = daily[["composite_score", return_col]].dropna().copy()
                    if len(valid) < 3:
                        continue
                    # P2 — cap top_n à max(5, len(valid)//3) pour garantir que
                    # le bucket « top » est un vrai sous-ensemble de l'univers.
                    # Évite le cas où top_n >= len(valid) → spread = 0 systématique.
                    effective_top_n = max(5, min(top_n, len(valid) // 3))
                    score_rank = valid["composite_score"].rank(method="average")
                    return_rank = valid[return_col].rank(method="average")
                    if score_rank.nunique() > 1 and return_rank.nunique() > 1:
                        rank_ic = score_rank.corr(return_rank)
                        if pd.notna(rank_ic):
                            ic_values.append(float(rank_ic))
                    top_slice = valid.nlargest(effective_top_n, "composite_score")
                    if not top_slice.empty:
                        top_bucket_returns.append(float(top_slice[return_col].mean()))
                    universe_returns.append(float(valid[return_col].mean()))

                mean_ic = sum(ic_values) / len(ic_values) if ic_values else 0.0
                top_mean = sum(top_bucket_returns) / len(top_bucket_returns) if top_bucket_returns else 0.0
                universe_mean = sum(universe_returns) / len(universe_returns) if universe_returns else 0.0
                spread = top_mean - universe_mean
                horizon_score = (0.65 * mean_ic) + (0.35 * spread)
                metrics[f"ic_{horizon}d"] = mean_ic
                metrics[f"top_return_{horizon}d"] = top_mean
                metrics[f"universe_return_{horizon}d"] = universe_mean
                metrics[f"spread_{horizon}d"] = spread
                metrics[f"score_{horizon}d"] = horizon_score
                per_horizon_scores.append(horizon_score)

            metrics["overall_score"] = sum(per_horizon_scores) / len(per_horizon_scores) if per_horizon_scores else 0.0
            results.append(metrics)

        return pd.DataFrame(results).sort_values("overall_score", ascending=False).reset_index(drop=True)

    @staticmethod
    def export_results(result_df: pd.DataFrame, output_dir: Path) -> dict[str, str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "sentiment_weight_calibration.csv"
        json_path = output_dir / "sentiment_weight_calibration_best.json"
        result_df.to_csv(csv_path, index=False)
        best_payload = result_df.iloc[0].to_dict() if not result_df.empty else {}
        json_path.write_text(json.dumps(best_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return {"calibration_csv": str(csv_path), "best_json": str(json_path)}

    @staticmethod
    def export_walk_forward_results(
        *,
        fold_df: pd.DataFrame,
        scored_oos_df: pd.DataFrame,
        signals_df: pd.DataFrame,
        report: BacktestReport,
        pf: Any,
        output_dir: Path,
        params: dict[str, object],
    ) -> dict[str, str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts: dict[str, str] = {}

        fold_csv = output_dir / "walk_forward_folds.csv"
        fold_metrics_csv = output_dir / "fold_metrics.csv"
        oos_csv = output_dir / "walk_forward_out_of_sample_scores.csv"
        signals_csv = output_dir / "walk_forward_selected_signals.csv"
        latest_json = output_dir / "walk_forward_best_weights_latest.json"
        latest_best_json = output_dir / "latest_best_weights.json"
        champion_json = output_dir / "champion_weights.json"
        selected_weights_csv = output_dir / "selected_weights.csv"

        fold_df.to_csv(fold_csv, index=False)
        fold_df.to_csv(fold_metrics_csv, index=False)
        scored_oos_df.to_csv(oos_csv, index=False)
        signals_df.to_csv(signals_csv, index=False)
        selected_weights_df = fold_df[[
            column for column in [
                "fold_index", "train_start_date", "train_end_date", "test_start_date", "test_end_date",
                "best_scenario_name", "sentiment_weight", "macro_weight", "quant_weight",
                "best_train_overall_score", "out_of_sample_overall_score",
            ] if column in fold_df.columns
        ]].copy() if not fold_df.empty else pd.DataFrame()
        selected_weights_df.to_csv(selected_weights_csv, index=False)
        artifacts["walk_forward_folds_csv"] = str(fold_csv)
        artifacts["fold_metrics_csv"] = str(fold_metrics_csv)
        artifacts["walk_forward_out_of_sample_scores_csv"] = str(oos_csv)
        artifacts["walk_forward_selected_signals_csv"] = str(signals_csv)
        artifacts["selected_weights_csv"] = str(selected_weights_csv)

        latest_payload = fold_df.iloc[-1].to_dict() if not fold_df.empty else {}
        latest_json.write_text(json.dumps(latest_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        latest_best_json.write_text(json.dumps(latest_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        if not fold_df.empty and "out_of_sample_overall_score" in fold_df.columns:
            champion_payload = fold_df.sort_values("out_of_sample_overall_score", ascending=False).iloc[0].to_dict()
        else:
            champion_payload = latest_payload
        champion_json.write_text(json.dumps(champion_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        artifacts["walk_forward_best_weights_latest_json"] = str(latest_json)
        artifacts["latest_best_weights_json"] = str(latest_best_json)
        artifacts["champion_weights_json"] = str(champion_json)

        equity_curve_csv = save_equity_curve_csv(pf, output_dir=output_dir)
        trades_csv = save_trades_csv(pf, output_dir=output_dir)
        equity_curve_png = save_equity_curve(pf, output_dir=output_dir)
        artifacts["equity_curve_csv"] = str(equity_curve_csv)
        artifacts["trades_csv"] = str(trades_csv)
        artifacts["equity_curve_png"] = str(equity_curve_png)

        report_json = save_report_json(
            report,
            output_dir=output_dir,
            artifacts=artifacts,
            params=params,
            diagnostics=extract_diagnostics(pf),
        )
        artifacts["report_json"] = str(report_json)
        return artifacts

    def calibrate(
        self,
        start_date: date,
        end_date: date,
        scenarios: Iterable[SentimentCalibrationScenario] | None = None,
        horizons: tuple[int, ...] = (5, 10, 20),
        top_n: int = 20,
        candidates_only: bool = True,
        output_dir: Path | None = None,
        capital_preset_keys: str | list[str] | None = None,
    ) -> tuple[SentimentCalibrationResult, pd.DataFrame, dict[str, str]]:
        scenario_list = list(scenarios or self.default_scenarios())
        dataset = self.load_dataset(start_date, end_date, horizons=horizons, candidates_only=candidates_only, capital_preset_keys=capital_preset_keys)
        result_df = self.evaluate_scenarios(dataset, scenario_list, horizons=horizons, top_n=top_n)
        artifacts: dict[str, str] = {}
        if output_dir is not None:
            artifacts = self.export_results(result_df, output_dir)
        if not result_df.empty:
            best_row = result_df.iloc[0].to_dict()
            best_scenario_name = str(best_row.get("scenario_name") or "none")
            best_overall_score = float(best_row.get("overall_score") or 0.0)
        else:
            best_scenario_name = "none"
            best_overall_score = 0.0
        return (
            SentimentCalibrationResult(
                start_date=start_date,
                end_date=end_date,
                scenarios_evaluated=len(scenario_list),
                rows_evaluated=int(len(dataset)),
                best_scenario_name=best_scenario_name,
                best_overall_score=best_overall_score,
                artifact_dir=str(output_dir) if output_dir is not None else None,
            ),
            result_df,
            artifacts,
        )

    def walk_forward_backtest(
        self,
        *,
        start_date: date,
        end_date: date,
        scenarios: Iterable[SentimentCalibrationScenario] | None = None,
        horizons: tuple[int, ...] = (5, 10, 20),
        top_n: int = 20,
        candidates_only: bool = True,
        min_train_days: int = 252,
        test_days: int = 63,
        step_days: int | None = None,
        max_positions: int = 20,
        initial_equity: float = 100_000.0,
        profit_taker_pct: float = 0.08,
        trailing_stop_pct: float = 0.05,
        fees_pct: float = 0.001,
        output_dir: Path | None = None,
        capital_preset_keys: str | list[str] | None = None,
        atr_trailing_stop_multiplier: float = 0.0,
    ) -> tuple[WalkForwardCalibrationResult, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]:
        scenario_list = list(scenarios or self.default_scenarios())
        dataset = self.load_dataset(start_date, end_date, horizons=horizons, candidates_only=candidates_only, capital_preset_keys=capital_preset_keys)
        windows = self.build_walk_forward_windows(
            dataset.get("snapshot_date", pd.Series(dtype="datetime64[ns]")),
            min_train_days=min_train_days,
            test_days=test_days,
            step_days=step_days,
        )
        if dataset.empty or not windows:
            LOGGER.warning(
                "walk_forward_backtest: dataset.empty=%s | windows=%d | "
                "snapshots_uniques=%d | min_train_days=%d | test_days=%d | capital_preset_keys=%s → early exit (0 folds).",
                dataset.empty,
                len(windows),
                int(dataset["snapshot_date"].nunique()) if not dataset.empty else 0,
                min_train_days,
                test_days,
                capital_preset_keys,
            )
            empty_result = WalkForwardCalibrationResult(
                start_date=start_date,
                end_date=end_date,
                folds_evaluated=0,
                scenarios_evaluated=len(scenario_list),
                out_of_sample_rows=0,
                out_of_sample_days=0,
                latest_best_scenario_name="none",
                final_value=initial_equity,
                total_return_pct=0.0,
                sharpe_ratio=0.0,
                max_drawdown_pct=0.0,
                artifact_dir=str(output_dir) if output_dir is not None else None,
            )
            return empty_result, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}

        # Normaliser snapshot_date en datetime64[ns] pour garantir la compatibilité
        # avec les pd.Timestamp produits par build_walk_forward_windows.
        dataset["snapshot_date"] = pd.to_datetime(dataset["snapshot_date"])

        fold_rows: list[dict[str, Any]] = []
        out_of_sample_frames: list[pd.DataFrame] = []
        skipped_empty_train = 0
        skipped_empty_test = 0
        skipped_empty_ranking = 0
        for window in windows:
            train_df = dataset[dataset["snapshot_date"].isin(window["train_dates"])].copy()
            test_df = dataset[dataset["snapshot_date"].isin(window["test_dates"])].copy()
            if train_df.empty:
                skipped_empty_train += 1
                continue
            if test_df.empty:
                skipped_empty_test += 1
                continue

            train_ranking = self.evaluate_scenarios(train_df, scenario_list, horizons=horizons, top_n=top_n)
            if train_ranking.empty:
                skipped_empty_ranking += 1
                continue

            best_train_row = train_ranking.iloc[0].to_dict()
            best_scenario = self._scenario_from_row(best_train_row)
            scored_test = self.score_dataset_for_scenario(test_df, best_scenario, score_column="final_score_walk_forward")
            scored_test["fold_index"] = int(window["fold_index"])
            scored_test["train_start_date"] = pd.Timestamp(window["train_start_date"])
            scored_test["train_end_date"] = pd.Timestamp(window["train_end_date"])
            scored_test["test_start_date"] = pd.Timestamp(window["test_start_date"])
            scored_test["test_end_date"] = pd.Timestamp(window["test_end_date"])
            out_of_sample_frames.append(scored_test)

            oos_eval_df = self.evaluate_scenarios(test_df, [best_scenario], horizons=horizons, top_n=top_n)
            oos_eval = oos_eval_df.iloc[0].to_dict() if not oos_eval_df.empty else {}
            fold_rows.append(
                {
                    "fold_index": int(window["fold_index"]),
                    "train_start_date": pd.Timestamp(window["train_start_date"]).date(),
                    "train_end_date": pd.Timestamp(window["train_end_date"]).date(),
                    "test_start_date": pd.Timestamp(window["test_start_date"]).date(),
                    "test_end_date": pd.Timestamp(window["test_end_date"]).date(),
                    "training_days": int(len(window["train_dates"])),
                    "test_days": int(len(window["test_dates"])),
                    "best_scenario_name": str(best_train_row.get("scenario_name") or "none"),
                    "sentiment_weight": float(best_train_row.get("sentiment_weight") or 0.0),
                    "macro_weight": float(best_train_row.get("macro_weight") or 0.0),
                    "quant_weight": float(best_train_row.get("quant_weight") or 0.0),
                    "best_train_overall_score": float(best_train_row.get("overall_score") or 0.0),
                    "out_of_sample_overall_score": float(oos_eval.get("overall_score") or 0.0),
                    "rows_tested": int(len(test_df)),
                    "trading_days_tested": int(test_df["snapshot_date"].nunique()),
                }
            )

        fold_df = pd.DataFrame(fold_rows)
        scored_oos_df = pd.concat(out_of_sample_frames, ignore_index=True) if out_of_sample_frames else pd.DataFrame()

        if skipped_empty_train or skipped_empty_test or skipped_empty_ranking:
            LOGGER.warning(
                "walk_forward_backtest: %d window(s) au total, "
                "train_df vide=%d, test_df vide=%d, train_ranking vide=%d, folds réussis=%d.",
                len(windows),
                skipped_empty_train,
                skipped_empty_test,
                skipped_empty_ranking,
                len(fold_df),
            )

        # ── P3 — signaux long + short (chaque côté = max_positions) ──
        signals_df = self.build_portfolio_signals_long_short(
            scored_oos_df,
            score_column="final_score_walk_forward",
            max_positions_long=max_positions,
            max_positions_short=max_positions,
        )
        LOGGER.info(
            "Signaux long+short construits | total=%d longs=%d shorts=%d",
            len(signals_df),
            int((signals_df["side"] == "buy").sum()) if not signals_df.empty and "side" in signals_df.columns else 0,
            int((signals_df["side"] == "sell").sum()) if not signals_df.empty and "side" in signals_df.columns else 0,
        )
        if signals_df.empty:
            empty_result = WalkForwardCalibrationResult(
                start_date=start_date,
                end_date=end_date,
                folds_evaluated=int(len(fold_df)),
                scenarios_evaluated=len(scenario_list),
                out_of_sample_rows=int(len(scored_oos_df)),
                out_of_sample_days=int(scored_oos_df["snapshot_date"].nunique()) if not scored_oos_df.empty else 0,
                latest_best_scenario_name=str(fold_df.iloc[-1]["best_scenario_name"]) if not fold_df.empty else "none",
                final_value=initial_equity,
                total_return_pct=0.0,
                sharpe_ratio=0.0,
                max_drawdown_pct=0.0,
                artifact_dir=str(output_dir) if output_dir is not None else None,
            )
            return empty_result, fold_df, scored_oos_df, signals_df, {}

        ohlcv_df = load_ohlcv(self.engine, start_date, end_date)
        if ohlcv_df.empty:
            raise RuntimeError("Aucune donnée OHLCV disponible pour exécuter le backtest walk-forward.")
        pivoted = pivot_ohlcv(ohlcv_df)
        pf = BacktestEngine(
            BacktestConfig(
                start_date=start_date,
                end_date=end_date,
                initial_equity=initial_equity,
                profit_taker_pct=profit_taker_pct,
                trailing_stop_pct=trailing_stop_pct,
                max_positions=max_positions,
                fees_pct=fees_pct,
                atr_trailing_stop_multiplier=atr_trailing_stop_multiplier,
            )
        ).run(
            open=pivoted["open"],
            close=pivoted["close"],
            high=pivoted["high"],
            low=pivoted["low"],
            signals_df=signals_df,
        )
        report = generate_report(pf, initial_equity)

        artifacts: dict[str, str] = {}
        if output_dir is not None:
            artifacts = self.export_walk_forward_results(
                fold_df=fold_df,
                scored_oos_df=scored_oos_df,
                signals_df=signals_df,
                report=report,
                pf=pf,
                output_dir=output_dir,
                params={
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "horizons": list(horizons),
                    "top_n": top_n,
                    "candidates_only": candidates_only,
                    "min_train_days": min_train_days,
                    "test_days": test_days,
                    "step_days": step_days,
                    "max_positions": max_positions,
                    "initial_equity": initial_equity,
                    "profit_taker_pct": profit_taker_pct,
                    "trailing_stop_pct": trailing_stop_pct,
                    "fees_pct": fees_pct,
                },
            )

        latest_best_name = str(fold_df.iloc[-1]["best_scenario_name"]) if not fold_df.empty else "none"
        result = WalkForwardCalibrationResult(
            start_date=start_date,
            end_date=end_date,
            folds_evaluated=int(len(fold_df)),
            scenarios_evaluated=len(scenario_list),
            out_of_sample_rows=int(len(scored_oos_df)),
            out_of_sample_days=int(scored_oos_df["snapshot_date"].nunique()) if not scored_oos_df.empty else 0,
            latest_best_scenario_name=latest_best_name,
            final_value=float(report.final_value),
            total_return_pct=float(report.total_return_pct),
            sharpe_ratio=float(report.sharpe_ratio),
            max_drawdown_pct=float(report.max_drawdown_pct),
            artifact_dir=str(output_dir) if output_dir is not None else None,
        )
        return result, fold_df, scored_oos_df, signals_df, artifacts


def _emit_run_summary(summary: dict[str, object]) -> None:
    if not bool(summary.get("progress_live")):
        try:
            persist_run_business_summary(
                summary=summary,
                step_key=STEP_KEY,
                run_kind="step",
                status=str(summary.get("status", "") or "") or None,
                summary_run_id=str(summary.get("run_id", "") or "") or None,
                entity_run_id=str(summary.get("run_id", "") or "") or None,
                trade_date=summary.get("trade_date"),
                started_at=summary.get("started_at"),
                finished_at=summary.get("finished_at"),
            )
        except Exception:
            LOGGER.debug("Persistance run_summaries indisponible pour backtesting sentiment.", exc_info=True)
    print(f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}", flush=True)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibre les poids sentiment/macro via backtest forward returns.")
    parser.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    parser.add_argument("--top-n", type=int, default=20, help="Nombre de symboles retenus par jour pour mesurer le spread.")
    parser.add_argument("--horizons", type=str, default="5,10,20", help="Horizons forward CSV en jours.")
    parser.add_argument("--output-dir", default="artifacts/sentiment_calibration", help="Répertoire de sortie des artefacts.")
    parser.add_argument("--all-symbols", action="store_true", help="Utilise tout l'univers historisé, pas seulement les candidats.")
    parser.add_argument("--walk-forward", action="store_true", help="Exécute une calibration walk-forward stricte avec backtest portefeuille hors échantillon.")
    parser.add_argument("--min-train-days", type=int, default=252, help="Nombre minimal de séances d'entraînement par fold walk-forward.")
    parser.add_argument("--test-days", type=int, default=63, help="Nombre de séances hors échantillon par fold walk-forward.")
    parser.add_argument("--step-days", type=int, default=None, help="Décalage entre folds walk-forward (défaut = test-days).")
    parser.add_argument("--max-positions", type=int, default=20, help="Nombre maximal de positions du portefeuille walk-forward.")
    parser.add_argument("--equity", type=float, default=100_000.0, help="Capital initial du portefeuille walk-forward.")
    parser.add_argument("--tp", type=float, default=0.08, help="Take profit du portefeuille walk-forward.")
    parser.add_argument("--ts", type=float, default=0.05, help="Trailing stop du portefeuille walk-forward.")
    parser.add_argument("--fees", type=float, default=0.001, help="Frais simulés du portefeuille walk-forward.")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    configure_root_logging(
        level=getattr(logging, args.log_level),
        log_path="./log/sentiment_weight_calibration.log",
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)
    horizons = tuple(int(token.strip()) for token in args.horizons.split(",") if token.strip())
    calibrator = SentimentWeightCalibrator(engine=get_sqlalchemy_engine())
    started_at = _utc_now_naive()
    if args.walk_forward:
        result, fold_df, _, _, artifacts = calibrator.walk_forward_backtest(
            start_date=start_date,
            end_date=end_date,
            horizons=horizons,
            top_n=args.top_n,
            candidates_only=not args.all_symbols,
            min_train_days=args.min_train_days,
            test_days=args.test_days,
            step_days=args.step_days,
            max_positions=args.max_positions,
            initial_equity=args.equity,
            profit_taker_pct=args.tp,
            trailing_stop_pct=args.ts,
            fees_pct=args.fees,
            output_dir=Path(args.output_dir),
        )
        extra_summary = {"folds_evaluated": len(fold_df)}
    else:
        result, _, artifacts = calibrator.calibrate(
            start_date=start_date,
            end_date=end_date,
            horizons=horizons,
            top_n=args.top_n,
            candidates_only=not args.all_symbols,
            output_dir=Path(args.output_dir),
        )
        extra_summary = {}
    finished_at = _utc_now_naive()
    _emit_run_summary(
        {
            "run_id": _build_run_id("sentiment-walk-forward" if args.walk_forward else "sentiment-calibration"),
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
            **asdict(result),
            **extra_summary,
            **artifacts,
        }
    )
    LOGGER.info("Calibration des poids sentiment terminée | walk_forward=%s result=%s", args.walk_forward, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




