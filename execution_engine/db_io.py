"""Accès base de données pour le module execution_engine."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from database.connection import get_sqlalchemy_engine
from execution_engine.models import BrokerOrder, ExecutionTarget

LOGGER = logging.getLogger(__name__)


class ExecutionRepository:
    """Lecture/écriture SQL pour le module execution_engine."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or get_sqlalchemy_engine()

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def load_portfolio_targets(
        self,
        risk_run_id: str | None = None,
        trade_date: date | None = None,
    ) -> list[ExecutionTarget]:
        """Charge les cibles depuis portfolio_targets."""
        if risk_run_id:
            query = text("""
                SELECT run_id, trade_date, symbol, decision_rank, side, shares, entry_price,
                       atr_20, price_asof_date, atr_asof_date, stop_price_initial,
                       risk_per_share, risk_budget_dollars, initial_risk_dollars,
                       target_notional, target_weight, sector, conviction_score,
                       sizing_method, kelly_fraction
                FROM portfolio_targets
                WHERE run_id = :run_id
                ORDER BY COALESCE(decision_rank, 999999), target_weight DESC, symbol ASC
            """)
            params: dict[str, Any] = {"run_id": risk_run_id}
        else:
            # Dernier run_id par MAX(created_at)
            if trade_date:
                query = text("""
                    SELECT run_id, trade_date, symbol, decision_rank, side, shares, entry_price,
                           atr_20, price_asof_date, atr_asof_date, stop_price_initial,
                           risk_per_share, risk_budget_dollars, initial_risk_dollars,
                           target_notional, target_weight, sector, conviction_score,
                           sizing_method, kelly_fraction
                    FROM portfolio_targets
                    WHERE run_id = (
                        SELECT run_id FROM portfolio_targets
                        WHERE trade_date = :trade_date
                        ORDER BY created_at DESC LIMIT 1
                    )
                    ORDER BY COALESCE(decision_rank, 999999), target_weight DESC, symbol ASC
                """)
                params = {"trade_date": trade_date}
            else:
                query = text("""
                    SELECT run_id, trade_date, symbol, decision_rank, side, shares, entry_price,
                           atr_20, price_asof_date, atr_asof_date, stop_price_initial,
                           risk_per_share, risk_budget_dollars, initial_risk_dollars,
                           target_notional, target_weight, sector, conviction_score,
                           sizing_method, kelly_fraction
                    FROM portfolio_targets
                    WHERE run_id = (
                        SELECT run_id FROM portfolio_targets
                        ORDER BY created_at DESC LIMIT 1
                    )
                    ORDER BY COALESCE(decision_rank, 999999), target_weight DESC, symbol ASC
                """)
                params = {}

        with self.engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()

        return [
            ExecutionTarget(
                risk_run_id=str(r["run_id"]),
                trade_date=r["trade_date"] if isinstance(r["trade_date"], date) else date.fromisoformat(str(r["trade_date"])),
                symbol=str(r["symbol"]).strip().upper(),
                target_shares=int(r["shares"]),
                entry_price=float(r["entry_price"]),
                target_weight=float(r["target_weight"]),
                sector=str(r["sector"]) if r["sector"] else None,
                conviction_score=float(r["conviction_score"]) if r.get("conviction_score") is not None else None,
                sizing_method=str(r["sizing_method"]) if r.get("sizing_method") else None,
                kelly_fraction=float(r["kelly_fraction"]) if r.get("kelly_fraction") is not None else None,
                decision_rank=int(r["decision_rank"]) if r.get("decision_rank") is not None else None,
                side=str(r["side"]) if r.get("side") else None,
                atr_20=float(r["atr_20"]) if r.get("atr_20") is not None else None,
                price_asof_date=r["price_asof_date"] if isinstance(r.get("price_asof_date"), date) else (date.fromisoformat(str(r["price_asof_date"])) if r.get("price_asof_date") else None),
                atr_asof_date=r["atr_asof_date"] if isinstance(r.get("atr_asof_date"), date) else (date.fromisoformat(str(r["atr_asof_date"])) if r.get("atr_asof_date") else None),
                stop_price_initial=float(r["stop_price_initial"]) if r.get("stop_price_initial") is not None else None,
                risk_per_share=float(r["risk_per_share"]) if r.get("risk_per_share") is not None else None,
                risk_budget_dollars=float(r["risk_budget_dollars"]) if r.get("risk_budget_dollars") is not None else None,
                initial_risk_dollars=float(r["initial_risk_dollars"]) if r.get("initial_risk_dollars") is not None else None,
                target_notional=float(r["target_notional"]) if r.get("target_notional") is not None else None,
            )
            for r in rows
        ]

    def load_submitted_idempotency_keys(self, exec_run_id: str) -> set[str]:
        query = text("""
            SELECT idempotency_key FROM execution_orders
            WHERE exec_run_id = :exec_run_id
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, {"exec_run_id": exec_run_id}).mappings().all()
        return {str(r["idempotency_key"]) for r in rows}

    def load_execution_orders(self, exec_run_id: str) -> list[BrokerOrder]:
        query = text("""
            SELECT broker_order_id, client_order_id, intent_id, symbol, side,
                   qty, filled_qty, avg_fill_price, status, order_type,
                   limit_price, stop_price, trail_percent, created_at, updated_at
            FROM execution_orders
            WHERE exec_run_id = :exec_run_id
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, {"exec_run_id": exec_run_id}).mappings().all()
        return [self._row_to_broker_order(r) for r in rows]

    def load_open_child_orders(self, parent_intent_id: str) -> list[BrokerOrder]:
        query = text("""
            SELECT broker_order_id, client_order_id, intent_id, symbol, side,
                   qty, filled_qty, avg_fill_price, status, order_type,
                   limit_price, stop_price, trail_percent, created_at, updated_at
            FROM execution_orders
            WHERE parent_intent_id = :parent_intent_id
              AND status NOT IN ('FILLED', 'CANCELED', 'REJECTED', 'FAILED', 'EXPIRED')
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, {"parent_intent_id": parent_intent_id}).mappings().all()
        return [self._row_to_broker_order(r) for r in rows]

    @staticmethod
    def _row_to_broker_order(r: Any) -> BrokerOrder:
        return BrokerOrder(
            broker_order_id=str(r["broker_order_id"] or ""),
            client_order_id=str(r["client_order_id"] or ""),
            intent_id=str(r["intent_id"] or ""),
            symbol=str(r["symbol"]),
            side=str(r["side"]),
            qty=float(r["qty"]),
            filled_qty=float(r["filled_qty"] or 0),
            avg_fill_price=float(r["avg_fill_price"]) if r["avg_fill_price"] is not None else None,
            status=str(r["status"]),
            order_type=str(r["order_type"]),
            limit_price=float(r["limit_price"]) if r["limit_price"] is not None else None,
            stop_price=float(r["stop_price"]) if r["stop_price"] is not None else None,
            trail_percent=float(r["trail_percent"]) if r["trail_percent"] is not None else None,
            created_at=r["created_at"] if isinstance(r.get("created_at"), datetime) else None,
            updated_at=r["updated_at"] if isinstance(r.get("updated_at"), datetime) else None,
        )

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------

    def insert_execution_run(
        self,
        exec_run_id: str,
        risk_run_id: str,
        trade_date: date,
        broker_mode: str,
        dry_run: bool,
        total_targets: int,
        account_id: str | None = None,
    ) -> None:
        stmt = text("""
            INSERT INTO execution_runs
                (exec_run_id, risk_run_id, trade_date, broker_mode, dry_run,
                 status, started_at, total_targets, total_submitted, total_filled, account_id)
            VALUES
                (:exec_run_id, :risk_run_id, :trade_date, :broker_mode, :dry_run,
                 'RUNNING', :started_at, :total_targets, 0, 0, :account_id)
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, {
                "exec_run_id": exec_run_id,
                "risk_run_id": risk_run_id,
                "trade_date": trade_date,
                "broker_mode": broker_mode,
                "dry_run": dry_run,
                "started_at": datetime.now(timezone.utc),
                "total_targets": total_targets,
                "account_id": account_id,
            })

    def update_execution_run_status(
        self,
        exec_run_id: str,
        status: str,
        total_submitted: int = 0,
        total_filled: int = 0,
        error_message: str | None = None,
    ) -> None:
        stmt = text("""
            UPDATE execution_runs
            SET status = :status,
                completed_at = :completed_at,
                total_submitted = :total_submitted,
                total_filled = :total_filled,
                error_message = :error_message
            WHERE exec_run_id = :exec_run_id
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, {
                "exec_run_id": exec_run_id,
                "status": status,
                "completed_at": datetime.now(timezone.utc),
                "total_submitted": total_submitted,
                "total_filled": total_filled,
                "error_message": error_message,
            })

    def upsert_execution_order(self, order_dict: dict[str, Any]) -> None:
        stmt = text("""
            INSERT INTO execution_orders
                (exec_run_id, risk_run_id, symbol, intent_id, parent_intent_id,
                 intent_role, idempotency_key, broker_mode, broker_order_id,
                 client_order_id, side, qty, filled_qty, avg_fill_price,
                 order_type, limit_price, stop_price, trail_percent,
                 decision_price, status, created_at, updated_at)
            VALUES
                (:exec_run_id, :risk_run_id, :symbol, :intent_id, :parent_intent_id,
                 :intent_role, :idempotency_key, :broker_mode, :broker_order_id,
                 :client_order_id, :side, :qty, :filled_qty, :avg_fill_price,
                 :order_type, :limit_price, :stop_price, :trail_percent,
                 :decision_price, :status, :created_at, :updated_at)
            ON DUPLICATE KEY UPDATE
                broker_order_id = VALUES(broker_order_id),
                filled_qty = VALUES(filled_qty),
                avg_fill_price = VALUES(avg_fill_price),
                status = VALUES(status),
                updated_at = VALUES(updated_at)
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, order_dict)

    def insert_execution_fill(self, fill_dict: dict[str, Any]) -> None:
        stmt = text("""
            INSERT INTO execution_fills
                (exec_run_id, fill_id, broker_order_id, intent_id, symbol,
                 filled_qty, avg_fill_price, fill_timestamp,
                 decision_price, slippage_bps, implementation_shortfall)
            VALUES
                (:exec_run_id, :fill_id, :broker_order_id, :intent_id, :symbol,
                 :filled_qty, :avg_fill_price, :fill_timestamp,
                 :decision_price, :slippage_bps, :implementation_shortfall)
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, fill_dict)

    def insert_execution_event(self, event_dict: dict[str, Any]) -> None:
        stmt = text("""
            INSERT INTO execution_events
                (event_id, exec_run_id, symbol, event_type, message,
                 broker_order_id, intent_id, payload_json, created_at)
            VALUES
                (:event_id, :exec_run_id, :symbol, :event_type, :message,
                 :broker_order_id, :intent_id, :payload_json, :created_at)
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, event_dict)

    def snapshot_broker_positions(
        self,
        exec_run_id: str,
        broker_mode: str,
        positions: list[dict[str, Any]],
        account_id: str | None = None,
    ) -> None:
        if not positions:
            return
        stmt = text("""
            INSERT INTO broker_positions_snapshots
                (exec_run_id, broker_mode, symbol, qty, avg_entry_price,
                 market_value, unrealized_pnl, created_at, account_id)
            VALUES
                (:exec_run_id, :broker_mode, :symbol, :qty, :avg_entry_price,
                 :market_value, :unrealized_pnl, :created_at, :account_id)
        """)
        now = datetime.now(timezone.utc)
        records = [
            {
                "exec_run_id": exec_run_id,
                "broker_mode": broker_mode,
                "symbol": p.get("symbol", ""),
                "qty": float(p.get("qty", 0)),
                "avg_entry_price": float(p.get("avg_entry_price", 0)),
                "market_value": float(p.get("market_value", 0)),
                "unrealized_pnl": float(p.get("unrealized_pl", 0)),
                "created_at": now,
                "account_id": account_id,
            }
            for p in positions
        ]
        with self.engine.begin() as conn:
            conn.execute(stmt, records)

