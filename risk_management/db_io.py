"""Accès base de données pour le module risk_management."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from database.connection import get_sqlalchemy_engine
from risk_management.config import RiskConfig
from risk_management.models import CandidateScore, PredictionInfo, PriceInfo, WinRateInfo

LOGGER = logging.getLogger(__name__)


class RiskRepository:
    """Lecture/écriture SQL pour le module risk_management."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or get_sqlalchemy_engine()

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    def load_candidates(self, config: RiskConfig) -> list[CandidateScore]:
        """Charge les candidats depuis stock_scores.

        Le score utilisé est ``final_score_sentiment`` qui intègre déjà
        ``final_score`` (fusion quant + sentiment par signal_aggregator).
        Les filtres qualité (anomaly_count, missing_days_count) sont déjà
        appliqués en amont lors du calcul de ``is_candidate``.
        """
        query = text("""
            SELECT
                s.symbol,
                COALESCE(s.sector, 'UNKNOWN') AS sector,
                s.final_score_sentiment       AS score_used
            FROM stock_scores s
            WHERE s.is_candidate = 1
              AND s.final_score_sentiment IS NOT NULL
            ORDER BY score_used DESC
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [
            CandidateScore(
                symbol=str(r["symbol"]).strip().upper(),
                sector=str(r["sector"]),
                score_used=float(r["score_used"]),
            )
            for r in rows
        ]

    def load_prices(self, symbols: list[str], atr_window: int = 20) -> dict[str, PriceInfo]:
        """Charge le dernier close et l'ATR depuis stock_bars_daily."""
        if not symbols:
            return {}
        placeholders = ", ".join(f":s{i}" for i in range(len(symbols)))
        params: dict[str, Any] = {f"s{i}": s for i, s in enumerate(symbols)}
        params["n"] = atr_window

        query = text(f"""
            WITH ranked AS (
                SELECT
                    symbol,
                    `close`   AS close_price,
                    `high`    AS h,
                    `low`     AS l,
                    LAG(`close`) OVER (PARTITION BY symbol ORDER BY `date`) AS prev_close,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY `date` DESC) AS rn
                FROM stock_bars_daily
                WHERE symbol IN ({placeholders})
            ),
            tr AS (
                SELECT symbol, rn, close_price,
                       GREATEST(h - l, ABS(h - prev_close), ABS(l - prev_close)) AS true_range
                FROM ranked
                WHERE prev_close IS NOT NULL
            )
            SELECT
                a.symbol,
                a.close_price AS last_close,
                b.atr_20
            FROM (SELECT symbol, close_price FROM ranked WHERE rn = 1) a
            LEFT JOIN (
                SELECT symbol, AVG(true_range) AS atr_20
                FROM tr
                WHERE rn <= :n + 1
                GROUP BY symbol
            ) b ON a.symbol = b.symbol
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()
        result: dict[str, PriceInfo] = {}
        for r in rows:
            sym = str(r["symbol"]).strip().upper()
            atr_val = float(r["atr_20"]) if r["atr_20"] is not None else None
            result[sym] = PriceInfo(symbol=sym, last_close=float(r["last_close"]), atr_20=atr_val)
        return result

    def load_predictions(
        self, symbols: list[str], trade_date: date,
    ) -> dict[str, PredictionInfo]:
        """Charge la dernière prédiction ML par symbole."""
        if not symbols:
            return {}
        placeholders = ", ".join(f":s{i}" for i in range(len(symbols)))
        params: dict[str, Any] = {f"s{i}": s for i, s in enumerate(symbols)}
        params["trade_date"] = trade_date
        query = text(f"""
            SELECT symbol, predicted_proba, predicted_class, run_id
            FROM model_predictions
            WHERE symbol IN ({placeholders})
              AND prediction_date <= :trade_date
            ORDER BY prediction_date DESC, created_at DESC
        """)
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, params).mappings().all()
        except Exception:
            LOGGER.warning("Impossible de charger model_predictions — table absente ?")
            return {}
        result: dict[str, PredictionInfo] = {}
        for r in rows:
            sym = str(r["symbol"]).strip().upper()
            if sym not in result:
                result[sym] = PredictionInfo(
                    symbol=sym,
                    predicted_proba=float(r["predicted_proba"]),
                    predicted_class=int(r["predicted_class"]),
                    run_id=str(r["run_id"]),
                )
        return result

    def load_win_rates(self, symbols: list[str]) -> dict[str, WinRateInfo]:
        """Charge le win rate historique par symbole via model_metrics + model_training_run."""
        if not symbols:
            return {}
        placeholders = ", ".join(f":s{i}" for i in range(len(symbols)))
        params: dict[str, Any] = {f"s{i}": s for i, s in enumerate(symbols)}
        query = text(f"""
            SELECT m.symbol, m.directional_accuracy, m.split_name, m.run_id
            FROM model_metrics m
            JOIN model_training_run t ON m.run_id = t.run_id
            WHERE t.status = 'completed'
              AND m.symbol IN ({placeholders})
              AND m.directional_accuracy IS NOT NULL
            ORDER BY m.symbol,
                     CASE m.split_name WHEN 'test' THEN 0 WHEN 'val' THEN 1 ELSE 2 END,
                     t.finished_at DESC
        """)
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, params).mappings().all()
        except Exception:
            LOGGER.warning("Impossible de charger model_metrics — table absente ?")
            return {}
        result: dict[str, WinRateInfo] = {}
        for r in rows:
            sym = str(r["symbol"]).strip().upper()
            if sym not in result:
                result[sym] = WinRateInfo(
                    symbol=sym,
                    directional_accuracy=float(r["directional_accuracy"]),
                    split_name=str(r["split_name"]),
                    run_id=str(r["run_id"]),
                )
        return result

    def load_return_matrix(
        self, symbols: list[str], lookback_days: int,
    ) -> pd.DataFrame:
        """Charge les rendements close-to-close récents en matrice pivotée."""
        if not symbols:
            return pd.DataFrame()
        placeholders = ", ".join(f":s{i}" for i in range(len(symbols)))
        params: dict[str, Any] = {f"s{i}": s for i, s in enumerate(symbols)}
        row_limit = lookback_days * len(symbols)
        params["row_limit"] = row_limit
        query = text(f"""
            SELECT symbol, `date`, `close` AS close_price
            FROM stock_bars_daily
            WHERE symbol IN ({placeholders})
            ORDER BY `date` DESC
            LIMIT :row_limit
        """)
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, params).mappings().all()
        except Exception:
            LOGGER.warning("Impossible de charger stock_bars_daily pour la matrice de corrélation.", exc_info=True)
            return pd.DataFrame()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        pivot = df.pivot_table(index="date", columns="symbol", values="close_price")
        returns = pivot.sort_index().pct_change(fill_method=None).iloc[1:]
        return returns

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------
    def write_risk_decisions(self, records: list[dict[str, Any]], account_id: str | None = None) -> int:
        """Insère dans risk_decisions. Tente V3 (account_id) puis V2 puis fallback V1."""
        if not records:
            return 0
        # Injecter account_id dans chaque record
        for r in records:
            r.setdefault("account_id", account_id or "default")
        stmt_v3 = text("""
            INSERT INTO risk_decisions
                (run_id, trade_date, symbol, decision, reason, score_used,
                 score_source, entry_price, proposed_shares, approved_shares,
                 target_weight, sector, conviction_score, predicted_proba,
                 historical_win_rate, effective_probability, kelly_fraction,
                 sizing_method, correlation_blocker, correlation_value, account_id)
            VALUES
                (:run_id, :trade_date, :symbol, :decision, :reason, :score_used,
                 :score_source, :entry_price, :proposed_shares, :approved_shares,
                 :target_weight, :sector, :conviction_score, :predicted_proba,
                 :historical_win_rate, :effective_probability, :kelly_fraction,
                 :sizing_method, :correlation_blocker, :correlation_value, :account_id)
        """)
        stmt_v2 = text("""
            INSERT INTO risk_decisions
                (run_id, trade_date, symbol, decision, reason, score_used,
                 score_source, entry_price, proposed_shares, approved_shares,
                 target_weight, sector, conviction_score, predicted_proba,
                 historical_win_rate, effective_probability, kelly_fraction,
                 sizing_method, correlation_blocker, correlation_value)
            VALUES
                (:run_id, :trade_date, :symbol, :decision, :reason, :score_used,
                 :score_source, :entry_price, :proposed_shares, :approved_shares,
                 :target_weight, :sector, :conviction_score, :predicted_proba,
                 :historical_win_rate, :effective_probability, :kelly_fraction,
                 :sizing_method, :correlation_blocker, :correlation_value)
        """)
        stmt_v1 = text("""
            INSERT INTO risk_decisions
                (run_id, trade_date, symbol, decision, reason, score_used,
                 score_source, entry_price, proposed_shares, approved_shares,
                 target_weight, sector)
            VALUES
                (:run_id, :trade_date, :symbol, :decision, :reason, :score_used,
                 :score_source, :entry_price, :proposed_shares, :approved_shares,
                 :target_weight, :sector)
        """)
        with self.engine.begin() as conn:
            try:
                conn.execute(stmt_v3, records)
            except Exception:
                try:
                    conn.execute(stmt_v2, records)
                except Exception:
                    LOGGER.info("Colonnes V2 absentes dans risk_decisions — fallback V1.")
                    conn.execute(stmt_v1, records)
        return len(records)

    def write_portfolio_targets(self, records: list[dict[str, Any]], account_id: str | None = None) -> int:
        """Insère dans portfolio_targets. Tente V3 (account_id) puis V2 puis fallback V1."""
        if not records:
            return 0
        for r in records:
            r.setdefault("account_id", account_id or "default")
        stmt_v3 = text("""
            INSERT INTO portfolio_targets
                (run_id, trade_date, symbol, shares, entry_price, target_weight,
                 sector, score_used, score_source, conviction_score, sizing_method,
                 kelly_fraction, account_id)
            VALUES
                (:run_id, :trade_date, :symbol, :shares, :entry_price, :target_weight,
                 :sector, :score_used, :score_source, :conviction_score, :sizing_method,
                 :kelly_fraction, :account_id)
        """)
        stmt_v2 = text("""
            INSERT INTO portfolio_targets
                (run_id, trade_date, symbol, shares, entry_price, target_weight,
                 sector, score_used, score_source, conviction_score, sizing_method,
                 kelly_fraction)
            VALUES
                (:run_id, :trade_date, :symbol, :shares, :entry_price, :target_weight,
                 :sector, :score_used, :score_source, :conviction_score, :sizing_method,
                 :kelly_fraction)
        """)
        stmt_v1 = text("""
            INSERT INTO portfolio_targets
                (run_id, trade_date, symbol, shares, entry_price, target_weight,
                 sector, score_used, score_source)
            VALUES
                (:run_id, :trade_date, :symbol, :shares, :entry_price, :target_weight,
                 :sector, :score_used, :score_source)
        """)
        with self.engine.begin() as conn:
            try:
                conn.execute(stmt_v3, records)
            except Exception:
                try:
                    conn.execute(stmt_v2, records)
                except Exception:
                    LOGGER.info("Colonnes V2 absentes dans portfolio_targets — fallback V1.")
                    conn.execute(stmt_v1, records)
        return len(records)
