"""Accès base de données pour le module execution_engine."""
from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from database.connection import get_sqlalchemy_engine
from database.run_business_summaries import parse_summary_json
from execution_engine.models import (
    BrokerOrder,
    ExecutionFill,
    ExecutionOrderRequest,
    ExecutionPosition,
    ExecutionPositionLot,
    ExecutionReconciliationResult,
    ExecutionTarget,
    OrderIntent,
    ProtectionWatchItem,
)

LOGGER = logging.getLogger(__name__)


class ExecutionRepository:
    """Lecture/écriture SQL pour le module execution_engine."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or get_sqlalchemy_engine()

    # ------------------------------------------------------------------
    # Phase 5.2.c — Kill switch runs
    # ------------------------------------------------------------------
    def persist_kill_switch_run(
        self,
        *,
        run_id: str,
        account_id: str,
        broker_mode: str,
        reason: str,
        results: list[dict[str, Any]],
        dry_run: bool,
        started_at: datetime,
        finished_at: datetime,
    ) -> None:
        """Phase 5.2.c — Persiste une exécution de la commande ``cancel-all``.

        ``results`` est une liste de dicts ``{broker_order_id, symbol, canceled, error}``.
        Best-effort : log un warning si la table est absente (pas de migration appliquée).
        """
        total_open = len(results)
        canceled = sum(1 for r in results if r.get("canceled"))
        failed = total_open - canceled
        try:
            stmt = text(
                """
                INSERT INTO execution_kill_switch_runs
                    (run_id, account_id, broker_mode, reason, total_open,
                     canceled, failed, dry_run, started_at, finished_at, results_json)
                VALUES
                    (:run_id, :account_id, :broker_mode, :reason, :total_open,
                     :canceled, :failed, :dry_run, :started_at, :finished_at, :results_json)
                """
            )
            with self.engine.begin() as conn:
                conn.execute(
                    stmt,
                    {
                        "run_id": run_id,
                        "account_id": account_id,
                        "broker_mode": broker_mode,
                        "reason": reason[:255],
                        "total_open": total_open,
                        "canceled": canceled,
                        "failed": failed,
                        "dry_run": 1 if dry_run else 0,
                        "started_at": started_at,
                        "finished_at": finished_at,
                        "results_json": json.dumps(results, default=str),
                    },
                )
        except Exception:
            LOGGER.warning(
                "persist_kill_switch_run failed (table missing?) run_id=%s account=%s",
                run_id, account_id, exc_info=True,
            )

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def _has_table(self, table_name: str) -> bool:
        try:
            return bool(inspect(self.engine).has_table(table_name))
        except Exception:
            return False

    def _get_table_columns(self, table_name: str) -> set[str]:
        try:
            return {
                str(column.get("name", "")).strip()
                for column in inspect(self.engine).get_columns(table_name)
                if str(column.get("name", "")).strip()
            }
        except Exception:
            return set()

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text_value = str(value).strip()
        return text_value or None

    def _portfolio_targets_select_clause(self) -> str:
        available_columns = self._get_table_columns("portfolio_targets")
        required_columns = [
            "run_id", "trade_date", "symbol", "decision_rank", "side", "shares", "entry_price",
            "atr_20", "price_asof_date", "atr_asof_date", "stop_price_initial",
            "risk_per_share", "risk_budget_dollars", "initial_risk_dollars",
            "target_notional", "target_weight", "sector", "conviction_score",
            "sizing_method", "kelly_fraction",
        ]
        optional_columns = [
            "candidate_rank",
            "selector_signal_mode",
            "selection_explanation",
            "selector_earnings_blackout",
            "previous_close",
        ]
        select_parts = [*required_columns]
        select_parts.extend(
            column if column in available_columns else f"NULL AS {column}"
            for column in optional_columns
        )
        return ",\n                       ".join(select_parts)

    def _execution_targets_snapshot_select_clause(self) -> str:
        available_columns = self._get_table_columns("execution_targets_snapshot")
        required_columns = [
            "risk_run_id", "trade_date", "symbol", "decision_rank", "side", "target_shares",
            "entry_price", "target_weight", "sector", "conviction_score", "sizing_method",
            "kelly_fraction", "atr_20", "price_asof_date", "atr_asof_date",
            "stop_price_initial", "risk_per_share", "risk_budget_dollars",
            "initial_risk_dollars", "target_notional",
        ]
        optional_columns = [
            "candidate_rank",
            "selector_signal_mode",
            "selection_explanation",
            "selector_earnings_blackout",
        ]
        select_parts = [*required_columns]
        select_parts.extend(
            column if column in available_columns else f"NULL AS {column}"
            for column in optional_columns
        )
        return ",\n                   ".join(select_parts)

    def _resolve_latest_risk_run_from_summary(
        self,
        *,
        account_id: str,
        trade_date: date | None,
    ) -> tuple[str | None, bool]:
        """Retourne (risk_run_id, latest_run_has_zero_targets).

        Quand l'étape 11 la plus récente du compte/date a produit 0 cible, on ne
        doit surtout pas retomber sur un ancien `portfolio_targets` encore présent
        en base. Dans ce cas on renvoie `(None, True)` pour forcer un résultat vide.
        """
        if not self._has_table("run_business_summaries"):
            return None, False

        where_trade_date = "AND trade_date = :trade_date" if trade_date is not None else ""
        # Compatibilité historique : les anciens résumés risk du compte implicite
        # ont parfois été persistés avec ``account_id IS NULL`` alors que les
        # cibles ``portfolio_targets`` sont stockées sous ``default``.
        # On considère donc ``NULL`` comme synonyme de ``default`` pour éviter
        # les faux fallback vers d'anciens targets et pour préserver le garde-fou
        # « dernier run = 0 cible ».
        account_scope_clause = "AND account_id = :account_id"
        if account_id == "default":
            account_scope_clause = "AND (account_id = :account_id OR account_id IS NULL)"
        stmt = text(
            f"""
            SELECT summary_run_id, entity_run_id, summary_json
            FROM run_business_summaries
            WHERE step_key = 'risk_management'
              AND run_kind = 'step'
              {account_scope_clause}
              {where_trade_date}
            ORDER BY COALESCE(finished_at, started_at, created_at) DESC, summary_run_id DESC
            LIMIT 1
            """
        )
        params: dict[str, Any] = {"account_id": account_id}
        if trade_date is not None:
            params["trade_date"] = trade_date

        with self.engine.connect() as conn:
            row = conn.execute(stmt, params).mappings().first()
        if row is None:
            return None, False

        summary = parse_summary_json(row.get("summary_json"))
        raw_target_positions = summary.get("target_positions")
        try:
            target_positions = int(str(raw_target_positions)) if raw_target_positions is not None else None
        except (TypeError, ValueError):
            target_positions = None

        resolved_run_id = str(
            summary.get("run_id")
            or row.get("entity_run_id")
            or row.get("summary_run_id")
            or ""
        ).strip() or None
        if target_positions is not None and target_positions <= 0:
            return None, True
        return resolved_run_id, False

    def load_portfolio_targets(
        self,
        risk_run_id: str | None = None,
        trade_date: date | None = None,
        account_id: str | None = None,
    ) -> list[ExecutionTarget]:
        """Charge les cibles depuis portfolio_targets."""
        resolved_account_id = account_id or "default"
        select_clause = self._portfolio_targets_select_clause()
        if risk_run_id:
            query = text(f"""
                SELECT {select_clause}
                FROM portfolio_targets
                WHERE run_id = :run_id
                  AND account_id = :account_id
                ORDER BY COALESCE(decision_rank, 999999), target_weight DESC, symbol ASC
            """)
            params: dict[str, Any] = {"run_id": risk_run_id, "account_id": resolved_account_id}
        else:
            latest_risk_run_id, latest_risk_has_zero_targets = self._resolve_latest_risk_run_from_summary(
                account_id=resolved_account_id,
                trade_date=trade_date,
            )
            if latest_risk_has_zero_targets:
                LOGGER.info(
                    "load_portfolio_targets | dernier risk run pour account=%s trade_date=%s a 0 cible retenue ; aucun fallback vers un ancien portfolio_targets.",
                    resolved_account_id,
                    trade_date,
                )
                return []
            if latest_risk_run_id:
                query = text(f"""
                    SELECT {select_clause}
                    FROM portfolio_targets
                    WHERE run_id = :run_id
                      AND account_id = :account_id
                    ORDER BY COALESCE(decision_rank, 999999), target_weight DESC, symbol ASC
                """)
                params = {"run_id": latest_risk_run_id, "account_id": resolved_account_id}
            else:
            # Dernier run_id par MAX(created_at)
                if trade_date:
                    query = text(f"""
                        SELECT {select_clause}
                        FROM portfolio_targets
                        WHERE run_id = (
                            SELECT run_id FROM portfolio_targets
                            WHERE trade_date = :trade_date
                              AND account_id = :account_id
                            ORDER BY created_at DESC LIMIT 1
                        )
                          AND account_id = :account_id
                        ORDER BY COALESCE(decision_rank, 999999), target_weight DESC, symbol ASC
                    """)
                    params = {"trade_date": trade_date, "account_id": resolved_account_id}
                else:
                    query = text(f"""
                        SELECT {select_clause}
                        FROM portfolio_targets
                        WHERE run_id = (
                            SELECT run_id FROM portfolio_targets
                            WHERE account_id = :account_id
                            ORDER BY created_at DESC LIMIT 1
                        )
                          AND account_id = :account_id
                        ORDER BY COALESCE(decision_rank, 999999), target_weight DESC, symbol ASC
                    """)
                    params = {"account_id": resolved_account_id}

        with self.engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()

        return [
            ExecutionTarget(
                risk_run_id=str(r["run_id"]),
                trade_date=r["trade_date"] if isinstance(r["trade_date"], date) else date.fromisoformat(str(r["trade_date"])),
                symbol=str(r["symbol"]).strip().upper(),
                target_shares=float(r["shares"]),
                entry_price=float(r["entry_price"]),
                target_weight=float(r["target_weight"]),
                sector=str(r["sector"]) if r["sector"] else None,
                conviction_score=float(r["conviction_score"]) if r.get("conviction_score") is not None else None,
                sizing_method=str(r["sizing_method"]) if r.get("sizing_method") else None,
                kelly_fraction=float(r["kelly_fraction"]) if r.get("kelly_fraction") is not None else None,
                candidate_rank=self._optional_int(r.get("candidate_rank")),
                decision_rank=int(r["decision_rank"]) if r.get("decision_rank") is not None else None,
                selector_signal_mode=self._optional_text(r.get("selector_signal_mode")),
                selection_explanation=self._optional_text(r.get("selection_explanation")),
                selector_earnings_blackout=self._optional_int(r.get("selector_earnings_blackout")),
                side=str(r["side"]) if r.get("side") else None,
                atr_20=float(r["atr_20"]) if r.get("atr_20") is not None else None,
                price_asof_date=r["price_asof_date"] if isinstance(r.get("price_asof_date"), date) else (date.fromisoformat(str(r["price_asof_date"])) if r.get("price_asof_date") else None),
                atr_asof_date=r["atr_asof_date"] if isinstance(r.get("atr_asof_date"), date) else (date.fromisoformat(str(r["atr_asof_date"])) if r.get("atr_asof_date") else None),
                stop_price_initial=float(r["stop_price_initial"]) if r.get("stop_price_initial") is not None else None,
                risk_per_share=float(r["risk_per_share"]) if r.get("risk_per_share") is not None else None,
                risk_budget_dollars=float(r["risk_budget_dollars"]) if r.get("risk_budget_dollars") is not None else None,
                initial_risk_dollars=float(r["initial_risk_dollars"]) if r.get("initial_risk_dollars") is not None else None,
                target_notional=float(r["target_notional"]) if r.get("target_notional") is not None else None,
                previous_close=float(r["previous_close"]) if r.get("previous_close") is not None else None,
            )
            for r in rows
        ]

    def load_previous_closes_asof(
        self,
        *,
        symbols: list[str],
        trade_date: date,
    ) -> dict[str, float]:
        """Charge le close J-1 (ou dernière clôture disponible avant `trade_date`)."""
        if not symbols:
            return {}

        placeholders = ", ".join(f":s{i}" for i in range(len(symbols)))
        params: dict[str, Any] = {f"s{i}": s for i, s in enumerate(symbols)}
        params["trade_date"] = trade_date
        query = text(f"""
            WITH ranked AS (
                SELECT
                    symbol,
                    `date` AS trade_day,
                    `close` AS close_price,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY `date` DESC) AS rn
                FROM stock_bars_daily
                WHERE symbol IN ({placeholders})
                  AND `date` < :trade_date
            )
            SELECT symbol, trade_day, close_price
            FROM ranked
            WHERE rn = 1
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()
        return {
            str(row["symbol"]).strip().upper(): float(row["close_price"])
            for row in rows
            if row.get("symbol") is not None and row.get("close_price") is not None
        }

    def load_submitted_idempotency_keys(self, exec_run_id: str) -> set[str]:
        query = text("""
            SELECT business_key FROM execution_order_requests
            WHERE exec_run_id = :exec_run_id
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, {"exec_run_id": exec_run_id}).mappings().all()
        return {str(r["business_key"]) for r in rows}

    def find_order_request_by_submission_key(
        self,
        *,
        account_id: str,
        submission_key: str,
    ) -> ExecutionOrderRequest | None:
        stmt = text("""
            SELECT request_id, exec_run_id, account_id, risk_run_id, symbol, side,
                   target_qty, order_type, business_key, submission_key, attempt_no,
                   parent_request_id, intent_role, decision_price, limit_price,
                   stop_price, trail_percent, status, failure_reason
            FROM execution_order_requests
            WHERE account_id = :account_id
              AND submission_key = :submission_key
            LIMIT 1
        """)
        with self.engine.connect() as conn:
            row = conn.execute(stmt, {"account_id": account_id, "submission_key": submission_key}).mappings().first()
        return self._row_to_execution_order_request(row) if row is not None else None

    def find_order_request_by_broker_order_id(
        self,
        *,
        account_id: str,
        broker_order_id: str,
    ) -> ExecutionOrderRequest | None:
        stmt = text("""
            SELECT req.request_id, req.exec_run_id, req.account_id, req.risk_run_id, req.symbol, req.side,
                   req.target_qty, req.order_type, req.business_key, req.submission_key, req.attempt_no,
                   req.parent_request_id, req.intent_role, req.decision_price, req.limit_price,
                   req.stop_price, req.trail_percent, req.status, req.failure_reason
            FROM execution_order_requests req
            INNER JOIN execution_broker_orders bo
                    ON bo.request_id = req.request_id
            WHERE req.account_id = :account_id
              AND bo.broker_order_id = :broker_order_id
            LIMIT 1
        """)
        with self.engine.connect() as conn:
            row = conn.execute(stmt, {"account_id": account_id, "broker_order_id": broker_order_id}).mappings().first()
        return self._row_to_execution_order_request(row) if row is not None else None

    def load_cumulative_filled_qty(self, *, request_id: str) -> float:
        stmt = text("""
            SELECT COALESCE(SUM(filled_qty), 0)
            FROM execution_broker_fills
            WHERE request_id = :request_id
        """)
        with self.engine.connect() as conn:
            value = conn.execute(stmt, {"request_id": request_id}).scalar()
        return float(value or 0.0)

    def load_execution_position_lot_inputs(self, *, account_id: str) -> list[dict[str, Any]]:
        stmt = text("""
            SELECT fill.fill_id, fill.exec_run_id, fill.request_id, fill.symbol,
                   req.side, fill.filled_qty, fill.avg_fill_price, fill.fill_timestamp, fill.created_at
            FROM execution_broker_fills fill
            INNER JOIN execution_order_requests req
                    ON req.request_id = fill.request_id
            WHERE fill.account_id = :account_id
            ORDER BY fill.fill_timestamp ASC, fill.created_at ASC, fill.fill_id ASC
        """)
        with self.engine.connect() as conn:
            return list(conn.execute(stmt, {"account_id": account_id}).mappings().all())

    def load_execution_targets_snapshot(self, *, exec_run_id: str) -> list[ExecutionTarget]:
        select_clause = self._execution_targets_snapshot_select_clause()
        stmt = text(f"""
            SELECT {select_clause}
            FROM execution_targets_snapshot
            WHERE exec_run_id = :exec_run_id
            ORDER BY COALESCE(decision_rank, 999999), symbol ASC
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(stmt, {"exec_run_id": exec_run_id}).mappings().all()
        return [
            ExecutionTarget(
                risk_run_id=str(r["risk_run_id"]),
                trade_date=r["trade_date"] if isinstance(r["trade_date"], date) else date.fromisoformat(str(r["trade_date"])),
                symbol=str(r["symbol"]).strip().upper(),
                target_shares=float(r["target_shares"]),
                entry_price=float(r["entry_price"]),
                target_weight=float(r["target_weight"]),
                sector=str(r["sector"]) if r.get("sector") else None,
                conviction_score=float(r["conviction_score"]) if r.get("conviction_score") is not None else None,
                sizing_method=str(r["sizing_method"]) if r.get("sizing_method") is not None else None,
                kelly_fraction=float(r["kelly_fraction"]) if r.get("kelly_fraction") is not None else None,
                candidate_rank=self._optional_int(r.get("candidate_rank")),
                decision_rank=int(r["decision_rank"]) if r.get("decision_rank") is not None else None,
                selector_signal_mode=self._optional_text(r.get("selector_signal_mode")),
                selection_explanation=self._optional_text(r.get("selection_explanation")),
                selector_earnings_blackout=self._optional_int(r.get("selector_earnings_blackout")),
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

    def load_open_reconciliation_order_state(self, *, account_id: str) -> list[dict[str, Any]]:
        stmt = text("""
            SELECT req.symbol AS symbol,
                   SUM(CASE WHEN req.side = 'buy' THEN req.target_qty ELSE 0 END) AS open_request_buy_qty,
                   SUM(CASE WHEN req.side = 'sell' THEN req.target_qty ELSE 0 END) AS open_request_sell_qty,
                   SUM(CASE WHEN COALESCE(bo.side, req.side) = 'buy' THEN COALESCE(bo.qty, req.target_qty, 0) ELSE 0 END) AS open_broker_buy_qty,
                   SUM(CASE WHEN COALESCE(bo.side, req.side) = 'sell' THEN COALESCE(bo.qty, req.target_qty, 0) ELSE 0 END) AS open_broker_sell_qty
            FROM execution_order_requests req
            LEFT JOIN execution_broker_orders bo
                   ON bo.request_id = req.request_id
            WHERE req.account_id = :account_id
              AND COALESCE(bo.normalized_status, req.status) IN ('NEW', 'PARTIALLY_FILLED', 'SIMULATED', 'SUBMITTED')
            GROUP BY req.symbol
            ORDER BY req.symbol ASC
        """)
        with self.engine.connect() as conn:
            return list(conn.execute(stmt, {"account_id": account_id}).mappings().all())

    def load_reconciliation_protection_state(self, *, account_id: str) -> list[dict[str, Any]]:
        stmt = text("""
            SELECT parent_req.symbol AS symbol,
                   SUM(COALESCE(parent_fill.total_filled_qty, parent_obs.filled_qty, parent_req.target_qty, 0)) AS protection_qty
            FROM execution_order_requests child_req
            INNER JOIN execution_order_requests parent_req
                    ON parent_req.request_id = child_req.parent_request_id
            LEFT JOIN execution_broker_orders child_obs
                   ON child_obs.request_id = child_req.request_id
            LEFT JOIN execution_broker_orders parent_obs
                   ON parent_obs.request_id = parent_req.request_id
            LEFT JOIN (
                SELECT request_id,
                       SUM(filled_qty) AS total_filled_qty
                FROM execution_broker_fills
                GROUP BY request_id
            ) parent_fill
                   ON parent_fill.request_id = parent_req.request_id
            WHERE parent_req.account_id = :account_id
              AND child_req.intent_role IN ('initial_stop', 'trailing_stop')
              AND COALESCE(child_obs.normalized_status, child_req.status) IN ('NEW', 'PARTIALLY_FILLED', 'SIMULATED', 'SUBMITTED')
            GROUP BY parent_req.symbol
            ORDER BY parent_req.symbol ASC
        """)
        with self.engine.connect() as conn:
            return list(conn.execute(stmt, {"account_id": account_id}).mappings().all())

    def load_latest_broker_account_snapshot(
        self,
        *,
        account_id: str,
        snapshot_kind: str = "preflight",
    ) -> dict[str, Any] | None:
        stmt = text("""
            SELECT snapshot_kind, equity, cash, settled_cash, buying_power,
                   daytrade_count, raw_payload_json, created_at
            FROM broker_account_snapshots
            WHERE account_id = :account_id
              AND snapshot_kind = :snapshot_kind
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        """)
        with self.engine.connect() as conn:
            row = conn.execute(stmt, {"account_id": account_id, "snapshot_kind": snapshot_kind}).mappings().first()
        return dict(row) if row is not None else None

    def load_execution_run_context(self, *, exec_run_id: str) -> dict[str, Any] | None:
        stmt = text("""
            SELECT exec_run_id, risk_run_id, trade_date, broker_mode, status, account_id,
                   execution_profile, submission_window, started_at, completed_at
            FROM execution_runs
            WHERE exec_run_id = :exec_run_id
            LIMIT 1
        """)
        with self.engine.connect() as conn:
            row = conn.execute(stmt, {"exec_run_id": exec_run_id}).mappings().first()
        return dict(row) if row is not None else None

    def load_execution_run_context_for_risk_run_id(
        self,
        *,
        risk_run_id: str,
        account_id: str | None = None,
        trade_date: date | None = None,
    ) -> dict[str, Any] | None:
        if not self._has_table("execution_runs"):
            return None
        normalized_risk_run_id = str(risk_run_id or "").strip()
        if not normalized_risk_run_id:
            return None
        resolved_account_id = account_id or "default"
        account_scope_clause = "AND account_id = :account_id"
        if resolved_account_id == "default":
            account_scope_clause = "AND (account_id = :account_id OR account_id IS NULL)"
        trade_date_clause = "AND trade_date = :trade_date" if trade_date is not None else ""
        stmt = text(
            f"""
            SELECT exec_run_id, risk_run_id, trade_date, broker_mode, status, account_id,
                   execution_profile, submission_window, started_at, completed_at
            FROM execution_runs
            WHERE risk_run_id = :risk_run_id
              {account_scope_clause}
              {trade_date_clause}
            ORDER BY COALESCE(completed_at, started_at) DESC, exec_run_id DESC
            LIMIT 1
            """
        )
        params: dict[str, Any] = {
            "risk_run_id": normalized_risk_run_id,
            "account_id": resolved_account_id,
        }
        if trade_date is not None:
            params["trade_date"] = trade_date
        with self.engine.connect() as conn:
            row = conn.execute(stmt, params).mappings().first()
        return dict(row) if row is not None else None

    def load_latest_execution_run_id_for_date(
        self,
        *,
        trade_date: date,
        account_id: str | None = None,
    ) -> str | None:
        if not self._has_table("execution_runs"):
            return None
        resolved_account_id = account_id or "default"
        account_scope_clause = "AND account_id = :account_id"
        if resolved_account_id == "default":
            account_scope_clause = "AND (account_id = :account_id OR account_id IS NULL)"
        stmt = text(
            f"""
            SELECT exec_run_id
            FROM execution_runs
            WHERE trade_date = :trade_date
              {account_scope_clause}
            ORDER BY COALESCE(completed_at, started_at) DESC, exec_run_id DESC
            LIMIT 1
            """
        )
        with self.engine.connect() as conn:
            value = conn.execute(
                stmt,
                {"trade_date": trade_date, "account_id": resolved_account_id},
            ).scalar()
        text_value = str(value or "").strip()
        return text_value or None

    def load_latest_execution_targets_snapshot_for_date(
        self,
        *,
        trade_date: date,
        account_id: str | None = None,
    ) -> list[ExecutionTarget]:
        exec_run_id = self.load_latest_execution_run_id_for_date(
            trade_date=trade_date,
            account_id=account_id,
        )
        if exec_run_id is None:
            return []
        return self.load_execution_targets_snapshot(exec_run_id=exec_run_id)

    def load_execution_fills_for_run(
        self,
        *,
        exec_run_id: str,
        account_id: str | None = None,
    ) -> pd.DataFrame:
        columns = [
            "run_id",
            "exec_run_id",
            "risk_run_id",
            "account_id",
            "request_id",
            "parent_request_id",
            "intent_role",
            "symbol",
            "side",
            "filled_qty",
            "avg_fill_price",
            "fill_timestamp",
            "decision_price",
            "slippage_bps",
            "implementation_shortfall",
        ]
        if not self._has_table("execution_broker_fills") or not self._has_table("execution_order_requests"):
            return pd.DataFrame(columns=columns)
        params: dict[str, Any] = {"exec_run_id": exec_run_id}
        account_clause = ""
        if account_id is not None:
            account_clause = " AND fill.account_id = :account_id"
            params["account_id"] = account_id
        stmt = text(
            f"""
            SELECT fill.exec_run_id AS run_id,
                   fill.exec_run_id,
                   req.risk_run_id,
                   fill.account_id,
                   fill.request_id,
                   req.parent_request_id,
                   req.intent_role,
                   fill.symbol,
                   req.side,
                   fill.filled_qty,
                   fill.avg_fill_price,
                   fill.fill_timestamp,
                   fill.decision_price,
                   fill.slippage_bps,
                   fill.implementation_shortfall
            FROM execution_broker_fills fill
            INNER JOIN execution_order_requests req
                    ON req.request_id = fill.request_id
            WHERE fill.exec_run_id = :exec_run_id{account_clause}
            ORDER BY fill.fill_timestamp ASC, fill.fill_id ASC
            """
        )
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(stmt, params).mappings().all()
        except Exception:
            LOGGER.warning("load_execution_fills_for_run failed exec_run_id=%s", exec_run_id, exc_info=True)
            return pd.DataFrame(columns=columns)
        return pd.DataFrame([dict(row) for row in rows], columns=columns)

    def load_execution_position_lots_for_open_run(
        self,
        *,
        open_exec_run_id: str,
        account_id: str | None = None,
    ) -> pd.DataFrame:
        columns = [
            "lot_id",
            "account_id",
            "symbol",
            "opened_qty",
            "remaining_qty",
            "entry_price",
            "opened_at",
            "open_exec_run_id",
            "open_request_id",
            "open_fill_id",
            "lot_status",
            "close_exec_run_id",
            "close_request_id",
            "close_fill_id",
            "closed_at",
            "exit_price",
            "close_intent_role",
            "close_side",
            "closed_qty",
            "realized_pnl",
            "run_id",
        ]
        if not self._has_table("execution_position_lots"):
            return pd.DataFrame(columns=columns)
        params: dict[str, Any] = {"open_exec_run_id": open_exec_run_id}
        account_clause = ""
        if account_id is not None:
            account_clause = " AND lot.account_id = :account_id"
            params["account_id"] = account_id
        close_join = ""
        close_select = "NULL AS close_intent_role, NULL AS close_side"
        if self._has_table("execution_order_requests"):
            close_join = "LEFT JOIN execution_order_requests close_req ON close_req.request_id = lot.close_request_id"
            close_select = "close_req.intent_role AS close_intent_role, close_req.side AS close_side"
        stmt = text(
            f"""
            SELECT lot.lot_id,
                   lot.account_id,
                   lot.symbol,
                   lot.opened_qty,
                   lot.remaining_qty,
                   lot.entry_price,
                   lot.opened_at,
                   lot.open_exec_run_id,
                   lot.open_request_id,
                   lot.open_fill_id,
                   lot.lot_status,
                   lot.close_exec_run_id,
                   lot.close_request_id,
                   lot.close_fill_id,
                   lot.closed_at,
                   lot.exit_price,
                   {close_select},
                   CASE
                       WHEN lot.opened_qty IS NOT NULL AND lot.remaining_qty IS NOT NULL AND (lot.opened_qty - lot.remaining_qty) > 0
                           THEN (lot.opened_qty - lot.remaining_qty)
                       WHEN lot.opened_qty IS NOT NULL AND lot.remaining_qty IS NOT NULL
                           THEN 0
                       ELSE NULL
                   END AS closed_qty,
                   CASE
                       WHEN lot.exit_price IS NOT NULL AND lot.entry_price IS NOT NULL AND lot.opened_qty IS NOT NULL AND lot.remaining_qty IS NOT NULL AND (lot.opened_qty - lot.remaining_qty) > 0
                           THEN (lot.opened_qty - lot.remaining_qty) * (lot.exit_price - lot.entry_price)
                       WHEN lot.exit_price IS NOT NULL AND lot.entry_price IS NOT NULL AND lot.opened_qty IS NOT NULL AND lot.remaining_qty IS NOT NULL
                           THEN 0
                       ELSE NULL
                   END AS realized_pnl,
                   COALESCE(lot.close_exec_run_id, lot.open_exec_run_id) AS run_id
            FROM execution_position_lots lot
            {close_join}
            WHERE lot.open_exec_run_id = :open_exec_run_id{account_clause}
            ORDER BY lot.opened_at ASC, lot.lot_id ASC
            """
        )
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(stmt, params).mappings().all()
        except Exception:
            LOGGER.warning("load_execution_position_lots_for_open_run failed open_exec_run_id=%s", open_exec_run_id, exc_info=True)
            return pd.DataFrame(columns=columns)
        return pd.DataFrame([dict(row) for row in rows], columns=columns)

    def load_open_child_orders(self, parent_intent_id: str) -> list[BrokerOrder]:
        v2_query = text("""
            SELECT COALESCE(bo.broker_order_id, '') AS broker_order_id,
                   COALESCE(bo.client_order_id, req.submission_key, '') AS client_order_id,
                   req.request_id AS intent_id,
                   req.symbol AS symbol,
                   req.side AS side,
                   req.target_qty AS qty,
                   COALESCE(bo.filled_qty, 0) AS filled_qty,
                   bo.avg_fill_price AS avg_fill_price,
                   COALESCE(bo.normalized_status, req.status) AS status,
                   req.order_type AS order_type,
                   req.limit_price AS limit_price,
                   req.stop_price AS stop_price,
                   req.trail_percent AS trail_percent,
                   bo.submitted_at AS created_at,
                   bo.last_seen_at AS updated_at
            FROM execution_order_requests req
            LEFT JOIN execution_broker_orders bo
                   ON bo.request_id = req.request_id
            WHERE req.parent_request_id = :parent_intent_id
              AND COALESCE(bo.normalized_status, req.status) IN ('NEW', 'PARTIALLY_FILLED', 'SIMULATED', 'SUBMITTED')
        """)
        with self.engine.connect() as conn:
            v2_rows = conn.execute(v2_query, {"parent_intent_id": parent_intent_id}).mappings().all()
        return [self._row_to_broker_order(row) for row in v2_rows]

    # ------------------------------------------------------------------
    # Sprint S26 (gap P3) — Filets de sécurité TP/SL
    # ------------------------------------------------------------------
    # Cas observé : en profil overnight (`overnight_cash_swing`), Execution
    # soumet l'ordre d'entrée puis saute la phase de polling/`_submit_children`
    # car le marché est fermé. À l'ouverture, l'entrée est remplie chez le
    # broker mais aucun TP / STOP n'a jamais été soumis.
    # Cette méthode retourne tous les ordres d'entrée FILLED (ou
    # PARTIALLY_FILLED) qui n'ont AUCUN take-profit ni AUCUN stop encore
    # ouvert chez le broker. L'executor + le watcher consomment cette liste
    # pour armer les enfants manquants ("synthetic bracket post-fill").
    # Inclut aussi les ``adopted_entry`` issus d'achats manuels adoptés : si
    # le premier armement TP/SL échoue, le watcher doit pouvoir réessayer au
    # tick suivant / au run suivant.
    def load_unprotected_filled_parents(
        self,
        *,
        exec_run_id: str | None = None,
        account_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        query = text(f"""
            SELECT
                parent_req.request_id          AS parent_intent_id,
                parent_req.exec_run_id         AS exec_run_id,
                parent_req.risk_run_id         AS risk_run_id,
                parent_req.account_id          AS account_id,
                COALESCE(er.broker_mode, 'paper') AS broker_mode,
                er.trade_date                  AS trade_date,
                parent_req.created_at          AS parent_created_at,
                parent_req.symbol              AS symbol,
                parent_req.side                AS side,
                parent_req.intent_role         AS parent_intent_role,
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM execution_order_requests c
                        LEFT JOIN execution_broker_orders co
                               ON co.request_id = c.request_id
                        WHERE c.parent_request_id = parent_req.request_id
                          AND c.intent_role = 'take_profit'
                          AND COALESCE(co.normalized_status, c.status)
                              NOT IN ('CANCELED', 'REJECTED', 'FAILED', 'EXPIRED')
                    ) THEN 1 ELSE 0
                END AS has_open_take_profit,
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM execution_order_requests c
                        LEFT JOIN execution_broker_orders co
                               ON co.request_id = c.request_id
                        WHERE c.parent_request_id = parent_req.request_id
                          AND c.intent_role IN ('initial_stop', 'trailing_stop')
                          AND COALESCE(co.normalized_status, c.status)
                              NOT IN ('CANCELED', 'REJECTED', 'FAILED', 'EXPIRED')
                    ) THEN 1 ELSE 0
                END AS has_open_protection,
                parent_req.target_qty          AS target_qty,
                parent_req.order_type          AS order_type,
                parent_req.limit_price         AS limit_price,
                parent_req.decision_price      AS decision_price,
                parent_req.business_key        AS business_key,
                parent_req.submission_key      AS submission_key,
                parent_obs.broker_order_id     AS parent_broker_order_id,
                COALESCE(
                    current_pos.qty,
                    parent_open_lots.open_remaining_qty,
                    parent_fill.total_filled_qty,
                    parent_obs.filled_qty,
                    0
                ) AS fill_qty,
                COALESCE(
                    current_pos.avg_entry_price,
                    parent_open_lots.open_avg_entry_price,
                    parent_fill.weighted_avg_fill_price,
                    parent_obs.avg_fill_price,
                    parent_req.decision_price
                ) AS fill_price
            FROM execution_order_requests parent_req
            LEFT JOIN execution_runs er
                   ON er.exec_run_id = parent_req.exec_run_id
            LEFT JOIN execution_broker_orders parent_obs
                   ON parent_obs.request_id = parent_req.request_id
            LEFT JOIN (
                SELECT request_id,
                       SUM(filled_qty) AS total_filled_qty,
                       CASE
                           WHEN SUM(filled_qty) > 0
                               THEN SUM(filled_qty * avg_fill_price) / SUM(filled_qty)
                           ELSE AVG(avg_fill_price)
                       END AS weighted_avg_fill_price
                FROM execution_broker_fills
                GROUP BY request_id
            ) parent_fill
                   ON parent_fill.request_id = parent_req.request_id
            LEFT JOIN (
                SELECT
                    account_id,
                    open_request_id AS request_id,
                    SUM(CASE WHEN lot_status = 'OPEN' THEN remaining_qty ELSE 0 END) AS open_remaining_qty,
                    CASE
                        WHEN SUM(CASE WHEN lot_status = 'OPEN' THEN remaining_qty ELSE 0 END) > 0
                            THEN SUM(CASE WHEN lot_status = 'OPEN' THEN remaining_qty * entry_price ELSE 0 END)
                                 / SUM(CASE WHEN lot_status = 'OPEN' THEN remaining_qty ELSE 0 END)
                        ELSE NULL
                    END AS open_avg_entry_price,
                    COUNT(*) AS total_lot_count
                FROM execution_position_lots
                GROUP BY account_id, open_request_id
            ) parent_open_lots
                   ON parent_open_lots.account_id = parent_req.account_id
                  AND parent_open_lots.request_id = parent_req.request_id
            LEFT JOIN (
                SELECT account_id, MAX(created_at) AS latest_at
                FROM broker_positions_snapshots
                GROUP BY account_id
            ) latest_account_snapshot
                   ON latest_account_snapshot.account_id = parent_req.account_id
            LEFT JOIN broker_positions_snapshots current_pos
                   ON current_pos.account_id = parent_req.account_id
                  AND current_pos.symbol = parent_req.symbol
                  AND current_pos.created_at = latest_account_snapshot.latest_at
            WHERE parent_req.intent_role IN ('entry', 'adopted_entry')
              AND parent_req.side = 'buy'
              AND COALESCE(parent_obs.normalized_status, parent_req.status)
                  IN ('FILLED', 'PARTIALLY_FILLED')
              AND COALESCE(
                    current_pos.qty,
                    parent_open_lots.open_remaining_qty,
                    parent_fill.total_filled_qty,
                    parent_obs.filled_qty,
                    0
                  ) > 0
              AND (
                    latest_account_snapshot.latest_at IS NULL
                 OR COALESCE(current_pos.qty, 0) > 0
              )
              AND (
                    COALESCE(parent_open_lots.total_lot_count, 0) = 0
                 OR COALESCE(parent_open_lots.open_remaining_qty, 0) > 0
              )
              AND (
                    NOT EXISTS (
                        SELECT 1
                        FROM execution_order_requests c
                        LEFT JOIN execution_broker_orders co
                               ON co.request_id = c.request_id
                        WHERE c.parent_request_id = parent_req.request_id
                          AND c.intent_role = 'take_profit'
                          AND COALESCE(co.normalized_status, c.status)
                              NOT IN ('CANCELED', 'REJECTED', 'FAILED', 'EXPIRED')
                    )
                 OR NOT EXISTS (
                        SELECT 1
                        FROM execution_order_requests c
                        LEFT JOIN execution_broker_orders co
                               ON co.request_id = c.request_id
                        WHERE c.parent_request_id = parent_req.request_id
                          AND c.intent_role IN ('initial_stop', 'trailing_stop')
                          AND COALESCE(co.normalized_status, c.status)
                              NOT IN ('CANCELED', 'REJECTED', 'FAILED', 'EXPIRED')
                    )
              )
              AND (:exec_run_id IS NULL OR parent_req.exec_run_id = :exec_run_id)
              AND (:account_id IS NULL OR parent_req.account_id = :account_id)
            ORDER BY parent_req.created_at ASC
            LIMIT {int(limit)}
        """)
        params = {"exec_run_id": exec_run_id, "account_id": account_id}
        with self.engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Sprint 2026-05 — Adoption d'orphelin (Q8 du FAQ opérateur).
    # ------------------------------------------------------------------
    # Retourne les positions broker (snapshot le plus récent) **sans aucun
    # OrderIntent ``entry`` / ``adopted_entry``** rattaché côté DB. Ces lignes
    # sont des achats manuels passés directement chez le broker (site Alpaca,
    # app mobile) que le watcher doit adopter puis protéger via TP + SL
    # (cf. ``execution_engine.protection_watcher``).
    def load_orphan_filled_buy_positions(
        self,
        *,
        account_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        query = text(f"""
            SELECT
                snap.account_id      AS account_id,
                snap.broker_mode     AS broker_mode,
                snap.symbol          AS symbol,
                snap.qty             AS qty,
                snap.avg_entry_price AS avg_entry_price,
                snap.market_value    AS market_value,
                snap.created_at      AS snapshot_at
            FROM broker_positions_snapshots snap
            INNER JOIN (
                SELECT account_id, symbol, MAX(created_at) AS last_at
                FROM broker_positions_snapshots
                GROUP BY account_id, symbol
            ) latest
                    ON latest.account_id = snap.account_id
                   AND latest.symbol     = snap.symbol
                   AND latest.last_at    = snap.created_at
            WHERE snap.qty > 0
              AND snap.symbol IS NOT NULL
              AND snap.symbol <> ''
              AND snap.symbol <> '__FLAT__'
              AND (:account_id IS NULL OR snap.account_id = :account_id)
              AND NOT EXISTS (
                    SELECT 1
                    FROM execution_order_requests req
                    WHERE req.account_id = snap.account_id
                      AND req.symbol     = snap.symbol
                      AND req.side       = 'buy'
                      AND req.intent_role IN ('entry', 'adopted_entry', 'rebalance_buy')
              )
            ORDER BY snap.created_at DESC
            LIMIT {int(limit)}
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, {"account_id": account_id}).mappings().all()
        return [dict(r) for r in rows]

    def load_latest_broker_order_status(
        self,
        *,
        account_id: str,
        broker_order_id: str,
    ) -> dict[str, Any] | None:
        stmt = text("""
            SELECT bo.broker_order_id, bo.client_order_id, req.request_id,
                   req.exec_run_id, req.account_id, req.risk_run_id, req.symbol, req.side,
                   req.target_qty, req.order_type, req.business_key, req.submission_key, req.attempt_no,
                   req.parent_request_id, req.intent_role, req.decision_price, req.limit_price,
                   req.stop_price, req.trail_percent, req.status, req.failure_reason,
                   bo.filled_qty, bo.avg_fill_price, bo.raw_status, bo.normalized_status,
                   bo.submitted_at, bo.last_seen_at
            FROM execution_broker_orders bo
            INNER JOIN execution_order_requests req
                    ON req.request_id = bo.request_id
            WHERE req.account_id = :account_id
              AND bo.broker_order_id = :broker_order_id
            ORDER BY bo.last_seen_at DESC
            LIMIT 1
        """)
        with self.engine.connect() as conn:
            row = conn.execute(stmt, {"account_id": account_id, "broker_order_id": broker_order_id}).mappings().first()
        return dict(row) if row is not None else None

    def load_pending_protection_watch_items(
        self,
        *,
        exec_run_id: str | None = None,
        account_id: str | None = None,
        limit: int = 100,
    ) -> list[ProtectionWatchItem]:
        query = text(f"""
            SELECT
                stop_req.exec_run_id AS source_exec_run_id,
                stop_req.risk_run_id AS risk_run_id,
                er.trade_date AS trade_date,
                er.account_id AS account_id,
                er.broker_mode AS broker_mode,
                stop_req.symbol AS symbol,
                stop_req.parent_request_id AS parent_intent_id,
                stop_req.request_id AS initial_stop_intent_id,
                COALESCE(stop_obs.broker_order_id, '') AS initial_stop_broker_order_id,
                COALESCE(parent_fill.total_filled_qty, stop_obs.filled_qty, stop_req.target_qty, 0) AS fill_qty,
                COALESCE(parent_fill.weighted_avg_fill_price, parent_obs.avg_fill_price, parent_req.decision_price, ets.entry_price, stop_req.decision_price, 0) AS fill_price,
                ets.stop_price_initial AS stop_price_initial,
                ets.risk_per_share AS risk_per_share,
                ets.initial_risk_dollars AS initial_risk_dollars,
                ets.target_notional AS target_notional
            FROM execution_order_requests stop_req
            INNER JOIN execution_runs er
                    ON er.exec_run_id = stop_req.exec_run_id
            INNER JOIN execution_order_requests parent_req
                    ON parent_req.exec_run_id = stop_req.exec_run_id
                   AND parent_req.request_id = stop_req.parent_request_id
            LEFT JOIN execution_broker_orders stop_obs
                   ON stop_obs.request_id = stop_req.request_id
            LEFT JOIN execution_broker_orders parent_obs
                   ON parent_obs.request_id = parent_req.request_id
            LEFT JOIN (
                SELECT request_id,
                       SUM(filled_qty) AS total_filled_qty,
                       CASE
                           WHEN SUM(filled_qty) > 0 THEN SUM(filled_qty * avg_fill_price) / SUM(filled_qty)
                           ELSE AVG(avg_fill_price)
                       END AS weighted_avg_fill_price
                FROM execution_broker_fills
                GROUP BY request_id
            ) parent_fill
                   ON parent_fill.request_id = parent_req.request_id
            LEFT JOIN execution_targets_snapshot ets
                   ON ets.exec_run_id = stop_req.exec_run_id
                  AND ets.symbol = stop_req.symbol
            LEFT JOIN execution_order_requests trailing_req
                   ON trailing_req.exec_run_id = stop_req.exec_run_id
                  AND trailing_req.parent_request_id = stop_req.parent_request_id
                  AND trailing_req.intent_role = 'trailing_stop'
            LEFT JOIN execution_broker_orders trailing_obs
                   ON trailing_obs.request_id = trailing_req.request_id
            WHERE stop_req.intent_role = 'initial_stop'
              AND COALESCE(stop_obs.normalized_status, stop_req.status) IN ('NEW', 'PARTIALLY_FILLED', 'SIMULATED', 'SUBMITTED')
              AND (
                    trailing_req.request_id IS NULL
                 OR COALESCE(trailing_obs.normalized_status, trailing_req.status) NOT IN ('NEW', 'PARTIALLY_FILLED', 'SIMULATED', 'SUBMITTED')
              )
              AND (:exec_run_id IS NULL OR stop_req.exec_run_id = :exec_run_id)
              AND (:account_id IS NULL OR er.account_id = :account_id)
            ORDER BY COALESCE(stop_obs.submitted_at, stop_req.created_at) ASC
            LIMIT {int(limit)}
        """)
        params = {"exec_run_id": exec_run_id, "account_id": account_id}
        with self.engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()
        return self._rows_to_protection_watch_items(rows)

    @staticmethod
    def _rows_to_protection_watch_items(rows: list[Any]) -> list[ProtectionWatchItem]:
        return [
            ProtectionWatchItem(
                source_exec_run_id=str(r["source_exec_run_id"]),
                risk_run_id=str(r["risk_run_id"]),
                trade_date=r["trade_date"] if isinstance(r["trade_date"], date) else date.fromisoformat(str(r["trade_date"])),
                account_id=str(r["account_id"]) if r.get("account_id") not in (None, "") else None,
                broker_mode=str(r.get("broker_mode") or "paper"),
                symbol=str(r["symbol"]).strip().upper(),
                parent_intent_id=str(r["parent_intent_id"]),
                initial_stop_intent_id=str(r["initial_stop_intent_id"]),
                initial_stop_broker_order_id=str(r.get("initial_stop_broker_order_id") or ""),
                fill_qty=float(r.get("fill_qty") or 0.0),
                fill_price=float(r.get("fill_price") or 0.0),
                stop_price_initial=float(r["stop_price_initial"]) if r.get("stop_price_initial") is not None else None,
                risk_per_share=float(r["risk_per_share"]) if r.get("risk_per_share") is not None else None,
                initial_risk_dollars=float(r["initial_risk_dollars"]) if r.get("initial_risk_dollars") is not None else None,
                target_notional=float(r["target_notional"]) if r.get("target_notional") is not None else None,
            )
            for r in rows
        ]

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

    @staticmethod
    def _row_to_execution_order_request(r: Any) -> ExecutionOrderRequest:
        return ExecutionOrderRequest(
            request_id=str(r["request_id"]),
            exec_run_id=str(r["exec_run_id"]),
            account_id=str(r["account_id"]),
            risk_run_id=str(r["risk_run_id"]),
            symbol=str(r["symbol"]),
            side=str(r["side"]),
            target_qty=float(r["target_qty"]),
            order_type=str(r["order_type"]),
            business_key=str(r["business_key"]),
            submission_key=str(r["submission_key"]) if r.get("submission_key") not in (None, "") else None,
            attempt_no=int(r["attempt_no"]),
            parent_request_id=str(r["parent_request_id"]) if r.get("parent_request_id") not in (None, "") else None,
            intent_role=str(r["intent_role"]),
            decision_price=float(r["decision_price"]),
            limit_price=float(r["limit_price"]) if r.get("limit_price") is not None else None,
            stop_price=float(r["stop_price"]) if r.get("stop_price") is not None else None,
            trail_percent=float(r["trail_percent"]) if r.get("trail_percent") is not None else None,
            status=str(r.get("status") or "NEW"),
            failure_reason=str(r["failure_reason"]) if r.get("failure_reason") not in (None, "") else None,
        )

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------

    def acquire_execution_lock(
        self,
        *,
        account_id: str | None,
        exec_run_id: str,
        ttl_seconds: int = 3600,
    ) -> bool:
        resolved_account_id = account_id or "default"
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=max(ttl_seconds, 1))
        purge_stmt = text("""
            DELETE FROM execution_locks
            WHERE account_id = :account_id
              AND expires_at < :now
        """)
        insert_stmt = text("""
            INSERT INTO execution_locks (account_id, locked_by_run_id, acquired_at, expires_at)
            VALUES (:account_id, :locked_by_run_id, :acquired_at, :expires_at)
        """)
        try:
            with self.engine.begin() as conn:
                conn.execute(purge_stmt, {"account_id": resolved_account_id, "now": now})
                conn.execute(insert_stmt, {
                    "account_id": resolved_account_id,
                    "locked_by_run_id": exec_run_id,
                    "acquired_at": now,
                    "expires_at": expires_at,
                })
            return True
        except IntegrityError:
            LOGGER.info("Execution lock already held for account_id=%s", resolved_account_id)
            return False

    def release_execution_lock(self, *, account_id: str | None, exec_run_id: str) -> None:
        resolved_account_id = account_id or "default"
        stmt = text("""
            DELETE FROM execution_locks
            WHERE account_id = :account_id
              AND locked_by_run_id = :locked_by_run_id
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, {"account_id": resolved_account_id, "locked_by_run_id": exec_run_id})

    def refresh_execution_lock(
        self,
        *,
        account_id: str | None,
        exec_run_id: str,
        ttl_seconds: int = 3600,
    ) -> bool:
        """Prolonge le TTL d'un verrou encore détenu par ``exec_run_id``."""
        resolved_account_id = account_id or "default"
        expires_at = datetime.now(UTC) + timedelta(seconds=max(ttl_seconds, 1))
        stmt = text("""
            UPDATE execution_locks
            SET expires_at = :expires_at
            WHERE account_id = :account_id
              AND locked_by_run_id = :locked_by_run_id
        """)
        with self.engine.begin() as conn:
            result = conn.execute(stmt, {
                "account_id": resolved_account_id,
                "locked_by_run_id": exec_run_id,
                "expires_at": expires_at,
            })
        return bool(result.rowcount)

    def force_release_execution_lock(self, *, account_id: str | None) -> int:
        """Supprime un verrou par scope, utilisé seulement pour nettoyer un service local IHM tué."""
        resolved_account_id = account_id or "default"
        stmt = text("""
            DELETE FROM execution_locks
            WHERE account_id = :account_id
        """)
        with self.engine.begin() as conn:
            result = conn.execute(stmt, {"account_id": resolved_account_id})
        return int(result.rowcount or 0)

    # ------------------------------------------------------------------
    # Watcher heartbeat (Phase 1 refactor — audit_watcher.md, audit_global.md §6.8)
    # ------------------------------------------------------------------

    def upsert_watcher_heartbeat(
        self,
        *,
        watcher_name: str,
        account_id: str | None = None,
        hostname: str | None = None,
        pid: int | None = None,
        status: str = "RUNNING",
        last_error: str | None = None,
    ) -> None:
        """UPSERT du heartbeat persistant d'un watcher.

        - Idempotent : ré-écrit ``last_heartbeat_at`` à chaque appel.
        - Tolérant si la table n'existe pas encore (log debug, pas d'erreur).
        """
        resolved_account_id = account_id or "default"
        params = {
            "watcher_name": watcher_name,
            "account_id": resolved_account_id,
            "hostname": hostname,
            "pid": pid,
            "status": status,
            "last_error": (last_error or None),
            "now": datetime.now(UTC),
        }
        # MySQL : INSERT ... ON DUPLICATE KEY UPDATE
        stmt = text("""
            INSERT INTO watcher_heartbeats
                (watcher_name, account_id, hostname, pid, status,
                 last_heartbeat_at, started_at, last_error)
            VALUES
                (:watcher_name, :account_id, :hostname, :pid, :status,
                 :now, :now, :last_error)
            ON DUPLICATE KEY UPDATE
                hostname = VALUES(hostname),
                pid = VALUES(pid),
                status = VALUES(status),
                last_heartbeat_at = VALUES(last_heartbeat_at),
                last_error = VALUES(last_error)
        """)
        try:
            with self.engine.begin() as conn:
                conn.execute(stmt, params)
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("watcher_heartbeats upsert ignored (table absente ?): %s", exc)

    def snapshot_execution_targets(
        self,
        *,
        exec_run_id: str,
        account_id: str | None,
        targets: list[ExecutionTarget],
    ) -> int:
        if not targets:
            return 0
        resolved_account_id = account_id or "default"
        available_columns = self._get_table_columns("execution_targets_snapshot")
        canonical_columns = [
            "exec_run_id", "account_id", "risk_run_id", "trade_date", "symbol", "candidate_rank", "decision_rank",
            "selector_signal_mode", "selection_explanation", "selector_earnings_blackout", "side",
            "target_shares", "entry_price", "target_weight", "sector", "conviction_score",
            "sizing_method", "kelly_fraction", "atr_20", "price_asof_date", "atr_asof_date",
            "stop_price_initial", "risk_per_share", "risk_budget_dollars", "initial_risk_dollars",
            "target_notional", "created_at",
        ]
        insert_columns = [column for column in canonical_columns if not available_columns or column in available_columns]
        stmt = text(
            "INSERT INTO execution_targets_snapshot ("
            + ", ".join(insert_columns)
            + ") VALUES ("
            + ", ".join(f":{column}" for column in insert_columns)
            + ")"
        )
        now = datetime.now(UTC)
        records = [
            {
                "exec_run_id": exec_run_id,
                "account_id": resolved_account_id,
                "risk_run_id": target.risk_run_id,
                "trade_date": target.trade_date,
                "symbol": target.symbol,
                "candidate_rank": target.candidate_rank,
                "decision_rank": target.decision_rank,
                "selector_signal_mode": target.selector_signal_mode,
                "selection_explanation": target.selection_explanation,
                "selector_earnings_blackout": target.selector_earnings_blackout,
                "side": target.side,
                "target_shares": target.target_shares,
                "entry_price": target.entry_price,
                "target_weight": target.target_weight,
                "sector": target.sector,
                "conviction_score": target.conviction_score,
                "sizing_method": target.sizing_method,
                "kelly_fraction": target.kelly_fraction,
                "atr_20": target.atr_20,
                "price_asof_date": target.price_asof_date,
                "atr_asof_date": target.atr_asof_date,
                "stop_price_initial": target.stop_price_initial,
                "risk_per_share": target.risk_per_share,
                "risk_budget_dollars": target.risk_budget_dollars,
                "initial_risk_dollars": target.initial_risk_dollars,
                "target_notional": target.target_notional,
                "created_at": now,
            }
            for target in targets
        ]
        records = [{column: record.get(column) for column in insert_columns} for record in records]
        with self.engine.begin() as conn:
            conn.execute(stmt, records)
        return len(records)

    def insert_execution_run(
        self,
        exec_run_id: str,
        risk_run_id: str,
        trade_date: date,
        broker_mode: str,
        dry_run: bool,
        total_targets: int,
        account_id: str | None = None,
        execution_profile: str | None = None,
        submission_window: str | None = None,
    ) -> None:
        stmt = text("""
            INSERT INTO execution_runs
                (exec_run_id, risk_run_id, trade_date, broker_mode, dry_run,
                 status, started_at, total_targets, total_submitted, total_filled, account_id,
                 execution_profile, submission_window)
            VALUES
                (:exec_run_id, :risk_run_id, :trade_date, :broker_mode, :dry_run,
                 'RUNNING', :started_at, :total_targets, 0, 0, :account_id,
                 :execution_profile, :submission_window)
        """)
        resolved_account_id = account_id or "default"
        with self.engine.begin() as conn:
            conn.execute(stmt, {
                "exec_run_id": exec_run_id,
                "risk_run_id": risk_run_id,
                "trade_date": trade_date,
                "broker_mode": broker_mode,
                "dry_run": dry_run,
                "started_at": datetime.now(UTC),
                "total_targets": total_targets,
                "account_id": resolved_account_id,
                "execution_profile": execution_profile,
                "submission_window": submission_window,
            })
        # Sprint S12.2 — chaîne d'audit HMAC SOX-like (best-effort).
        try:
            from database.audit_chain import AuditChainRepository

            AuditChainRepository(self.engine).append(
                "execution_runs",
                exec_run_id,
                {
                    "exec_run_id": exec_run_id,
                    "risk_run_id": risk_run_id,
                    "trade_date": str(trade_date),
                    "broker_mode": broker_mode,
                    "dry_run": bool(dry_run),
                    "total_targets": int(total_targets),
                    "account_id": resolved_account_id,
                    "execution_profile": execution_profile,
                    "submission_window": submission_window,
                    "event": "insert",
                },
            )
        except Exception:  # noqa: BLE001
            pass

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
                "completed_at": datetime.now(UTC),
                "total_submitted": total_submitted,
                "total_filled": total_filled,
                "error_message": error_message,
            })

    def _next_request_attempt_no(self, account_id: str, business_key: str) -> int:
        stmt = text("""
            SELECT COALESCE(MAX(attempt_no), 0)
            FROM execution_order_requests
            WHERE account_id = :account_id
              AND business_key = :business_key
        """)
        with self.engine.connect() as conn:
            value = conn.execute(stmt, {"account_id": account_id, "business_key": business_key}).scalar()
        return int(value or 0) + 1

    def _load_request_attempt_no(self, request_id: str) -> int | None:
        stmt = text("SELECT attempt_no FROM execution_order_requests WHERE request_id = :request_id")
        with self.engine.connect() as conn:
            value = conn.execute(stmt, {"request_id": request_id}).scalar()
        return int(value) if value is not None else None

    def upsert_execution_order_request_from_intent(
        self,
        intent: OrderIntent,
        *,
        account_id: str,
        status: str,
        failure_reason: str | None = None,
    ) -> int:
        attempt_no = self._load_request_attempt_no(intent.intent_id)
        if attempt_no is None:
            attempt_no = self._next_request_attempt_no(account_id, intent.idempotency_key)
        row = {
            "request_id": intent.intent_id,
            "exec_run_id": intent.exec_run_id,
            "account_id": account_id,
            "risk_run_id": intent.risk_run_id,
            "symbol": intent.symbol,
            "side": intent.side,
            "target_qty": intent.qty,
            "order_type": intent.order_type,
            "business_key": intent.idempotency_key,
            "submission_key": intent.submission_key,
            "attempt_no": attempt_no,
            "parent_request_id": intent.parent_intent_id,
            "intent_role": intent.intent_role,
            "decision_price": intent.decision_price,
            "limit_price": intent.limit_price,
            "stop_price": intent.stop_price,
            "trail_percent": intent.trail_percent,
            "status": status,
            "failure_reason": failure_reason,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        if self.engine.dialect.name == "sqlite":
            stmt = text("""
                INSERT INTO execution_order_requests (
                    request_id, exec_run_id, account_id, risk_run_id, symbol, side,
                    target_qty, order_type, business_key, submission_key, attempt_no,
                    parent_request_id, intent_role, decision_price, limit_price,
                    stop_price, trail_percent, status, failure_reason, created_at, updated_at
                ) VALUES (
                    :request_id, :exec_run_id, :account_id, :risk_run_id, :symbol, :side,
                    :target_qty, :order_type, :business_key, :submission_key, :attempt_no,
                    :parent_request_id, :intent_role, :decision_price, :limit_price,
                    :stop_price, :trail_percent, :status, :failure_reason, :created_at, :updated_at
                )
                ON CONFLICT(request_id) DO UPDATE SET
                    submission_key = excluded.submission_key,
                    limit_price = excluded.limit_price,
                    stop_price = excluded.stop_price,
                    trail_percent = excluded.trail_percent,
                    status = excluded.status,
                    failure_reason = excluded.failure_reason,
                    updated_at = excluded.updated_at
            """)
        else:
            stmt = text("""
                INSERT INTO execution_order_requests (
                    request_id, exec_run_id, account_id, risk_run_id, symbol, side,
                    target_qty, order_type, business_key, submission_key, attempt_no,
                    parent_request_id, intent_role, decision_price, limit_price,
                    stop_price, trail_percent, status, failure_reason, created_at, updated_at
                ) VALUES (
                    :request_id, :exec_run_id, :account_id, :risk_run_id, :symbol, :side,
                    :target_qty, :order_type, :business_key, :submission_key, :attempt_no,
                    :parent_request_id, :intent_role, :decision_price, :limit_price,
                    :stop_price, :trail_percent, :status, :failure_reason, :created_at, :updated_at
                )
                ON DUPLICATE KEY UPDATE
                    submission_key = VALUES(submission_key),
                    limit_price = VALUES(limit_price),
                    stop_price = VALUES(stop_price),
                    trail_percent = VALUES(trail_percent),
                    status = VALUES(status),
                    failure_reason = VALUES(failure_reason),
                    updated_at = VALUES(updated_at)
            """)
        with self.engine.begin() as conn:
            conn.execute(stmt, row)
        return attempt_no

    def upsert_execution_broker_order(
        self,
        intent: OrderIntent,
        order: BrokerOrder,
        *,
        account_id: str,
        raw_payload: dict[str, Any] | None = None,
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        row = {
            "request_id": intent.intent_id,
            "exec_run_id": intent.exec_run_id,
            "account_id": account_id,
            "broker_order_id": order.broker_order_id,
            "client_order_id": order.client_order_id,
            "symbol": order.symbol,
            "side": order.side,
            "qty": order.qty,
            "filled_qty": order.filled_qty,
            "avg_fill_price": order.avg_fill_price,
            "raw_status": order.status,
            "normalized_status": order.status,
            "order_type": order.order_type,
            "limit_price": order.limit_price,
            "stop_price": order.stop_price,
            "trail_percent": order.trail_percent,
            "raw_payload_json": json.dumps(raw_payload) if raw_payload is not None else None,
            "raw_response_json": json.dumps(raw_response) if raw_response is not None else None,
            "submitted_at": order.created_at or datetime.now(UTC),
            "last_seen_at": order.updated_at or datetime.now(UTC),
        }
        if self.engine.dialect.name == "sqlite":
            stmt = text("""
                INSERT INTO execution_broker_orders (
                    request_id, exec_run_id, account_id, broker_order_id, client_order_id,
                    symbol, side, qty, filled_qty, avg_fill_price, raw_status,
                    normalized_status, order_type, limit_price, stop_price, trail_percent,
                    raw_payload_json, raw_response_json, submitted_at, last_seen_at
                ) VALUES (
                    :request_id, :exec_run_id, :account_id, :broker_order_id, :client_order_id,
                    :symbol, :side, :qty, :filled_qty, :avg_fill_price, :raw_status,
                    :normalized_status, :order_type, :limit_price, :stop_price, :trail_percent,
                    :raw_payload_json, :raw_response_json, :submitted_at, :last_seen_at
                )
                ON CONFLICT(broker_order_id) DO UPDATE SET
                    client_order_id = excluded.client_order_id,
                    filled_qty = excluded.filled_qty,
                    avg_fill_price = excluded.avg_fill_price,
                    raw_status = excluded.raw_status,
                    normalized_status = excluded.normalized_status,
                    raw_response_json = excluded.raw_response_json,
                    last_seen_at = excluded.last_seen_at
            """)
        else:
            stmt = text("""
                INSERT INTO execution_broker_orders (
                    request_id, exec_run_id, account_id, broker_order_id, client_order_id,
                    symbol, side, qty, filled_qty, avg_fill_price, raw_status,
                    normalized_status, order_type, limit_price, stop_price, trail_percent,
                    raw_payload_json, raw_response_json, submitted_at, last_seen_at
                ) VALUES (
                    :request_id, :exec_run_id, :account_id, :broker_order_id, :client_order_id,
                    :symbol, :side, :qty, :filled_qty, :avg_fill_price, :raw_status,
                    :normalized_status, :order_type, :limit_price, :stop_price, :trail_percent,
                    :raw_payload_json, :raw_response_json, :submitted_at, :last_seen_at
                )
                ON DUPLICATE KEY UPDATE
                    client_order_id = VALUES(client_order_id),
                    filled_qty = VALUES(filled_qty),
                    avg_fill_price = VALUES(avg_fill_price),
                    raw_status = VALUES(raw_status),
                    normalized_status = VALUES(normalized_status),
                    raw_response_json = VALUES(raw_response_json),
                    last_seen_at = VALUES(last_seen_at)
            """)
        with self.engine.begin() as conn:
            conn.execute(stmt, row)

    def insert_execution_broker_fill(
        self,
        fill: ExecutionFill,
        *,
        account_id: str,
        raw_fill: dict[str, Any] | None = None,
    ) -> None:
        lookup_stmt = text("SELECT exec_run_id FROM execution_order_requests WHERE request_id = :request_id")
        sqlite_insert_stmt = text("""
            INSERT OR IGNORE INTO execution_broker_fills (
                fill_id, exec_run_id, account_id, broker_order_id, request_id,
                symbol, filled_qty, avg_fill_price, fill_timestamp, decision_price,
                slippage_bps, implementation_shortfall, raw_fill_json, created_at
            ) VALUES (
                :fill_id, :exec_run_id, :account_id, :broker_order_id, :request_id,
                :symbol, :filled_qty, :avg_fill_price, :fill_timestamp, :decision_price,
                :slippage_bps, :implementation_shortfall, :raw_fill_json, :created_at
            )
        """)
        ignore_duplicate_stmt = text("""
            INSERT INTO execution_broker_fills (
                fill_id, exec_run_id, account_id, broker_order_id, request_id,
                symbol, filled_qty, avg_fill_price, fill_timestamp, decision_price,
                slippage_bps, implementation_shortfall, raw_fill_json, created_at
            ) VALUES (
                :fill_id, :exec_run_id, :account_id, :broker_order_id, :request_id,
                :symbol, :filled_qty, :avg_fill_price, :fill_timestamp, :decision_price,
                :slippage_bps, :implementation_shortfall, :raw_fill_json, :created_at
            )
            ON DUPLICATE KEY UPDATE fill_id = fill_id
        """)
        row = {
            "fill_id": fill.fill_id,
            "exec_run_id": None,
            "account_id": account_id,
            "broker_order_id": fill.broker_order_id,
            "request_id": fill.intent_id,
            "symbol": fill.symbol,
            "filled_qty": fill.filled_qty,
            "avg_fill_price": fill.avg_fill_price,
            "fill_timestamp": fill.fill_timestamp,
            "decision_price": fill.decision_price,
            "slippage_bps": fill.slippage_bps,
            "implementation_shortfall": fill.implementation_shortfall,
            "raw_fill_json": json.dumps(raw_fill) if raw_fill is not None else None,
            "created_at": datetime.now(UTC),
        }
        with self.engine.begin() as conn:
            row["exec_run_id"] = conn.execute(lookup_stmt, {"request_id": fill.intent_id}).scalar()
            if self.engine.dialect.name == "sqlite":
                conn.execute(sqlite_insert_stmt, row)
            else:
                conn.execute(ignore_duplicate_stmt, row)

    def snapshot_broker_account(
        self,
        exec_run_id: str,
        *,
        account_id: str,
        broker_mode: str,
        snapshot: dict[str, Any],
        snapshot_kind: str = "preflight",
        allow_zero_equity: bool = False,
    ) -> None:
        equity_value = float(snapshot.get("equity", 0.0) or 0.0)
        if equity_value <= 0.0 and not allow_zero_equity:
            # Hardening live : un snapshot avec equity ≤ 0 corrompt les analyses risque
            # (high_watermark, fallback PnLSnapshot, etc.). On refuse l'insert et on trace.
            LOGGER.warning(
                "snapshot_broker_account refusé — equity invalide=%.4f | exec_run_id=%s "
                "account=%s broker_mode=%s snapshot_kind=%s raw_keys=%s",
                equity_value,
                exec_run_id,
                account_id,
                broker_mode,
                snapshot_kind,
                sorted(snapshot.keys()) if isinstance(snapshot, dict) else type(snapshot).__name__,
            )
            return
        stmt = text("""
            INSERT INTO broker_account_snapshots (
                exec_run_id, account_id, broker_mode, snapshot_kind,
                equity, cash, settled_cash, buying_power, daytrade_count,
                raw_payload_json, created_at
            ) VALUES (
                :exec_run_id, :account_id, :broker_mode, :snapshot_kind,
                :equity, :cash, :settled_cash, :buying_power, :daytrade_count,
                :raw_payload_json, :created_at
            )
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, {
                "exec_run_id": exec_run_id,
                "account_id": account_id,
                "broker_mode": broker_mode,
                "snapshot_kind": snapshot_kind,
                "equity": float(snapshot.get("equity", 0.0) or 0.0),
                "cash": float(snapshot.get("cash", 0.0) or 0.0),
                "settled_cash": float(snapshot.get("settled_cash", snapshot.get("cash", 0.0)) or 0.0),
                "buying_power": float(snapshot.get("buying_power", 0.0) or 0.0),
                "daytrade_count": int(snapshot.get("daytrade_count", 0) or 0),
                "raw_payload_json": json.dumps(snapshot),
                "created_at": datetime.now(UTC),
            })


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
        now = datetime.now(UTC)
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

    def replace_execution_positions(
        self,
        *,
        exec_run_id: str,
        account_id: str,
        broker_mode: str,
        positions: list[dict[str, Any]],
    ) -> int:
        delete_stmt = text("DELETE FROM execution_positions WHERE account_id = :account_id")
        insert_stmt = text("""
            INSERT INTO execution_positions (
                account_id, symbol, net_qty, avg_entry_price, market_price,
                market_value, unrealized_pnl, broker_mode, source_exec_run_id,
                position_status, last_broker_snapshot_at, updated_at
            ) VALUES (
                :account_id, :symbol, :net_qty, :avg_entry_price, :market_price,
                :market_value, :unrealized_pnl, :broker_mode, :source_exec_run_id,
                :position_status, :last_broker_snapshot_at, :updated_at
            )
        """)
        now = datetime.now(UTC)
        records: list[dict[str, Any]] = []
        for position in positions:
            symbol = str(position.get("symbol", "") or "").strip().upper()
            if not symbol:
                continue
            qty = float(position.get("qty", 0) or 0)
            current_price = position.get("current_price")
            if current_price in (None, ""):
                market_value = position.get("market_value")
                if market_value not in (None, "") and qty not in (0, 0.0):
                    current_price = float(market_value) / qty
            records.append({
                "account_id": account_id,
                "symbol": symbol,
                "net_qty": qty,
                "avg_entry_price": float(position.get("avg_entry_price")) if position.get("avg_entry_price") not in (None, "") else None,
                "market_price": float(current_price) if current_price not in (None, "") else None,
                "market_value": float(position.get("market_value")) if position.get("market_value") not in (None, "") else None,
                "unrealized_pnl": float(position.get("unrealized_pl")) if position.get("unrealized_pl") not in (None, "") else None,
                "broker_mode": broker_mode,
                "source_exec_run_id": exec_run_id,
                "position_status": "OPEN",
                "last_broker_snapshot_at": now,
                "updated_at": now,
            })
        if not records:
            records = [{
                "account_id": account_id,
                "symbol": "__FLAT__",
                "net_qty": 0.0,
                "avg_entry_price": None,
                "market_price": None,
                "market_value": None,
                "unrealized_pnl": None,
                "broker_mode": broker_mode,
                "source_exec_run_id": exec_run_id,
                "position_status": "FLAT",
                "last_broker_snapshot_at": now,
                "updated_at": now,
            }]
        with self.engine.begin() as conn:
            conn.execute(delete_stmt, {"account_id": account_id})
            conn.execute(insert_stmt, records)
        return len(records)

    def rebuild_execution_position_lots(
        self,
        *,
        account_id: str,
    ) -> int:
        inputs = self.load_execution_position_lot_inputs(account_id=account_id)
        delete_stmt = text("DELETE FROM execution_position_lots WHERE account_id = :account_id")
        insert_stmt = text("""
            INSERT INTO execution_position_lots (
                lot_id, account_id, symbol, opened_qty, remaining_qty, entry_price,
                opened_at, open_exec_run_id, open_request_id, open_fill_id, lot_status,
                close_exec_run_id, close_request_id, close_fill_id, closed_at, exit_price,
                source_kind, updated_at
            ) VALUES (
                :lot_id, :account_id, :symbol, :opened_qty, :remaining_qty, :entry_price,
                :opened_at, :open_exec_run_id, :open_request_id, :open_fill_id, :lot_status,
                :close_exec_run_id, :close_request_id, :close_fill_id, :closed_at, :exit_price,
                :source_kind, :updated_at
            )
        """)
        open_lots_by_symbol: dict[str, list[dict[str, Any]]] = {}
        records: list[dict[str, Any]] = []
        for row in inputs:
            symbol = str(row["symbol"]).strip().upper()
            side = str(row["side"]).strip().lower()
            fill_qty = float(row.get("filled_qty") or 0.0)
            fill_price = float(row.get("avg_fill_price") or 0.0)
            fill_timestamp = row.get("fill_timestamp") if isinstance(row.get("fill_timestamp"), datetime) else datetime.now(UTC)
            if fill_qty <= 0:
                continue
            if side == "buy":
                lot = {
                    "lot_id": f"lot-{row['fill_id']}",
                    "account_id": account_id,
                    "symbol": symbol,
                    "opened_qty": fill_qty,
                    "remaining_qty": fill_qty,
                    "entry_price": fill_price,
                    "opened_at": fill_timestamp,
                    "open_exec_run_id": row.get("exec_run_id"),
                    "open_request_id": row.get("request_id"),
                    "open_fill_id": row.get("fill_id"),
                    "lot_status": "OPEN",
                    "close_exec_run_id": None,
                    "close_request_id": None,
                    "close_fill_id": None,
                    "closed_at": None,
                    "exit_price": None,
                    "source_kind": "execution_broker_fill",
                    "updated_at": datetime.now(UTC),
                }
                records.append(lot)
                open_lots_by_symbol.setdefault(symbol, []).append(lot)
                continue

            remaining_to_close = fill_qty
            candidate_lots = open_lots_by_symbol.get(symbol, [])
            while remaining_to_close > 1e-9 and candidate_lots:
                lot = candidate_lots[0]
                consume_qty = min(float(lot["remaining_qty"]), remaining_to_close)
                lot["remaining_qty"] = max(float(lot["remaining_qty"]) - consume_qty, 0.0)
                lot["updated_at"] = datetime.now(UTC)
                remaining_to_close -= consume_qty
                if lot["remaining_qty"] <= 1e-9:
                    lot["remaining_qty"] = 0.0
                    lot["lot_status"] = "CLOSED"
                    lot["close_exec_run_id"] = row.get("exec_run_id")
                    lot["close_request_id"] = row.get("request_id")
                    lot["close_fill_id"] = row.get("fill_id")
                    lot["closed_at"] = fill_timestamp
                    lot["exit_price"] = fill_price
                    candidate_lots.pop(0)

        with self.engine.begin() as conn:
            conn.execute(delete_stmt, {"account_id": account_id})
            if records:
                conn.execute(insert_stmt, records)
        return len(records)

    def replace_execution_reconciliation_results(
        self,
        *,
        exec_run_id: str,
        account_id: str,
        results: list[ExecutionReconciliationResult],
    ) -> int:
        delete_stmt = text("""
            DELETE FROM execution_reconciliation_results
            WHERE exec_run_id = :exec_run_id
              AND account_id = :account_id
        """)
        insert_stmt = text("""
            INSERT INTO execution_reconciliation_results (
                exec_run_id, account_id, symbol, target_qty, internal_position_qty,
                broker_position_qty, position_delta, open_request_buy_qty,
                open_request_sell_qty, open_broker_buy_qty, open_broker_sell_qty,
                has_open_protection, protection_qty, action,
                reconciliation_status, reason_code, created_at
            ) VALUES (
                :exec_run_id, :account_id, :symbol, :target_qty, :internal_position_qty,
                :broker_position_qty, :position_delta, :open_request_buy_qty,
                :open_request_sell_qty, :open_broker_buy_qty, :open_broker_sell_qty,
                :has_open_protection, :protection_qty, :action,
                :reconciliation_status, :reason_code, :created_at
            )
        """)
        records = [
            {
                "exec_run_id": result.exec_run_id,
                "account_id": result.account_id,
                "symbol": result.symbol,
                "target_qty": result.target_qty,
                "internal_position_qty": result.internal_position_qty,
                "broker_position_qty": result.broker_position_qty,
                "position_delta": result.position_delta,
                "open_request_buy_qty": result.open_request_buy_qty,
                "open_request_sell_qty": result.open_request_sell_qty,
                "open_broker_buy_qty": result.open_broker_buy_qty,
                "open_broker_sell_qty": result.open_broker_sell_qty,
                "has_open_protection": int(bool(result.has_open_protection)),
                "protection_qty": result.protection_qty,
                "action": result.action,
                "reconciliation_status": result.reconciliation_status,
                "reason_code": result.reason_code,
                "created_at": result.created_at or datetime.now(UTC),
            }
            for result in results
        ]
        with self.engine.begin() as conn:
            conn.execute(delete_stmt, {"exec_run_id": exec_run_id, "account_id": account_id})
            if records:
                conn.execute(insert_stmt, records)
        return len(records)

    def load_execution_positions(self, *, account_id: str | None = None) -> list[ExecutionPosition]:
        stmt = text("""
            SELECT account_id, symbol, net_qty, avg_entry_price, market_price,
                   market_value, unrealized_pnl, broker_mode, source_exec_run_id,
                   position_status, last_broker_snapshot_at, updated_at
            FROM execution_positions
            WHERE (:account_id IS NULL OR account_id = :account_id)
            ORDER BY CASE WHEN position_status = 'FLAT' THEN 1 ELSE 0 END, ABS(net_qty) DESC, symbol ASC
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(stmt, {"account_id": account_id}).mappings().all()
        return [
            ExecutionPosition(
                account_id=str(r["account_id"]),
                symbol=str(r["symbol"]),
                net_qty=float(r["net_qty"]),
                avg_entry_price=float(r["avg_entry_price"]) if r.get("avg_entry_price") is not None else None,
                market_price=float(r["market_price"]) if r.get("market_price") is not None else None,
                market_value=float(r["market_value"]) if r.get("market_value") is not None else None,
                unrealized_pnl=float(r["unrealized_pnl"]) if r.get("unrealized_pnl") is not None else None,
                broker_mode=str(r["broker_mode"]) if r.get("broker_mode") not in (None, "") else None,
                source_exec_run_id=str(r["source_exec_run_id"]) if r.get("source_exec_run_id") not in (None, "") else None,
                position_status=str(r.get("position_status") or "OPEN"),
                last_broker_snapshot_at=r.get("last_broker_snapshot_at") if isinstance(r.get("last_broker_snapshot_at"), datetime) else None,
                updated_at=r.get("updated_at") if isinstance(r.get("updated_at"), datetime) else None,
            )
            for r in rows
        ]

    def load_execution_position_lots(self, *, account_id: str | None = None) -> list[ExecutionPositionLot]:
        stmt = text("""
            SELECT lot_id, account_id, symbol, opened_qty, remaining_qty, entry_price,
                   opened_at, open_exec_run_id, open_request_id, open_fill_id, lot_status,
                   close_exec_run_id, close_request_id, close_fill_id, closed_at, exit_price,
                   source_kind, updated_at
            FROM execution_position_lots
            WHERE (:account_id IS NULL OR account_id = :account_id)
            ORDER BY opened_at DESC, lot_id DESC
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(stmt, {"account_id": account_id}).mappings().all()
        return [
            ExecutionPositionLot(
                lot_id=str(r["lot_id"]),
                account_id=str(r["account_id"]),
                symbol=str(r["symbol"]),
                opened_qty=float(r["opened_qty"]),
                remaining_qty=float(r["remaining_qty"]),
                entry_price=float(r["entry_price"]),
                opened_at=r["opened_at"] if isinstance(r.get("opened_at"), datetime) else datetime.now(UTC),
                open_exec_run_id=str(r["open_exec_run_id"]) if r.get("open_exec_run_id") not in (None, "") else None,
                open_request_id=str(r["open_request_id"]) if r.get("open_request_id") not in (None, "") else None,
                open_fill_id=str(r["open_fill_id"]) if r.get("open_fill_id") not in (None, "") else None,
                lot_status=str(r.get("lot_status") or "OPEN"),
                close_exec_run_id=str(r["close_exec_run_id"]) if r.get("close_exec_run_id") not in (None, "") else None,
                close_request_id=str(r["close_request_id"]) if r.get("close_request_id") not in (None, "") else None,
                close_fill_id=str(r["close_fill_id"]) if r.get("close_fill_id") not in (None, "") else None,
                closed_at=r.get("closed_at") if isinstance(r.get("closed_at"), datetime) else None,
                exit_price=float(r["exit_price"]) if r.get("exit_price") is not None else None,
                source_kind=str(r.get("source_kind") or "execution_broker_fill"),
            )
            for r in rows
        ]

    def load_execution_reconciliation_results(
        self,
        *,
        exec_run_id: str | None = None,
        account_id: str | None = None,
    ) -> list[ExecutionReconciliationResult]:
        stmt = text("""
            SELECT exec_run_id, account_id, symbol, target_qty, internal_position_qty,
                   broker_position_qty, position_delta, open_request_buy_qty,
                   open_request_sell_qty, open_broker_buy_qty, open_broker_sell_qty,
                   has_open_protection, protection_qty, action,
                   reconciliation_status, reason_code, created_at
            FROM execution_reconciliation_results
            WHERE (:exec_run_id IS NULL OR exec_run_id = :exec_run_id)
              AND (:account_id IS NULL OR account_id = :account_id)
            ORDER BY created_at DESC, symbol ASC
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(stmt, {"exec_run_id": exec_run_id, "account_id": account_id}).mappings().all()
        return [
            ExecutionReconciliationResult(
                exec_run_id=str(r["exec_run_id"]),
                account_id=str(r["account_id"]),
                symbol=str(r["symbol"]),
                target_qty=float(r.get("target_qty") or 0.0),
                internal_position_qty=float(r.get("internal_position_qty") or 0.0),
                broker_position_qty=float(r.get("broker_position_qty") or 0.0),
                position_delta=float(r.get("position_delta") or 0.0),
                open_request_buy_qty=float(r.get("open_request_buy_qty") or 0.0),
                open_request_sell_qty=float(r.get("open_request_sell_qty") or 0.0),
                open_broker_buy_qty=float(r.get("open_broker_buy_qty") or 0.0),
                open_broker_sell_qty=float(r.get("open_broker_sell_qty") or 0.0),
                has_open_protection=bool(r.get("has_open_protection")),
                protection_qty=float(r.get("protection_qty") or 0.0),
                action=str(r.get("action") or "none"),
                reconciliation_status=str(r.get("reconciliation_status") or "MANUAL_REVIEW"),
                reason_code=str(r["reason_code"]) if r.get("reason_code") not in (None, "") else None,
                created_at=r.get("created_at") if isinstance(r.get("created_at"), datetime) else None,
            )
            for r in rows
        ]

