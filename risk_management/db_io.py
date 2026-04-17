"""Accès base de données pour le module risk_management."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from risk_management.config import RiskConfig
from risk_management.models import CandidateScore, PriceInfo

LOGGER = logging.getLogger(__name__)


class RiskRepository:
    """Lecture/écriture SQL pour le module risk_management."""

    def __init__(self) -> None:
        self.engine = get_sqlalchemy_engine()

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

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------
    def write_risk_decisions(self, records: list[dict[str, Any]]) -> int:
        """Insère dans risk_decisions."""
        if not records:
            return 0
        stmt = text("""
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
            conn.execute(stmt, records)
        return len(records)

    def write_portfolio_targets(self, records: list[dict[str, Any]]) -> int:
        """Insère dans portfolio_targets."""
        if not records:
            return 0
        stmt = text("""
            INSERT INTO portfolio_targets
                (run_id, trade_date, symbol, shares, entry_price, target_weight,
                 sector, score_used, score_source)
            VALUES
                (:run_id, :trade_date, :symbol, :shares, :entry_price, :target_weight,
                 :sector, :score_used, :score_source)
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, records)
        return len(records)
