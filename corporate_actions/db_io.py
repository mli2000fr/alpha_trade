"""Accès base de données pour le module corporate_actions."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from corporate_actions.models import (
    CaStatus,
    CashLedgerEntry,
    CorporateActionApplication,
    CorporateActionEvent,
)
from database.connection import get_sqlalchemy_engine

LOGGER = logging.getLogger(__name__)


class CorporateActionRepository:
    """Lecture / écriture SQL pour le module corporate_actions."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or get_sqlalchemy_engine()

    @property
    def _is_sqlite(self) -> bool:
        return self.engine.dialect.name == "sqlite"

    # ------------------------------------------------------------------
    # Insertion événements
    # ------------------------------------------------------------------

    def insert_event(self, event: CorporateActionEvent) -> int:
        """
        Insère un événement dans corporate_actions_events.

        Retourne l'id de la ligne insérée, ou -1 si doublon (idempotency_key).
        """
        if self._is_sqlite:
            return self.insert_event_sqlite(event)
        stmt = text("""
            INSERT INTO corporate_actions_events
                (idempotency_key, provider, provider_event_id, symbol, ca_type,
                 amount_per_share, split_from, split_to, currency,
                 announcement_date, ex_date, record_date, payable_date,
                 raw_payload, status, ingested_at)
            VALUES
                (:idempotency_key, :provider, :provider_event_id, :symbol, :ca_type,
                 :amount_per_share, :split_from, :split_to, :currency,
                 :announcement_date, :ex_date, :record_date, :payable_date,
                 :raw_payload, :status, :ingested_at)
            ON DUPLICATE KEY UPDATE id = id
        """)
        now = datetime.now(timezone.utc)
        params: dict[str, Any] = {
            "idempotency_key": event.idempotency_key,
            "provider": event.provider,
            "provider_event_id": event.provider_event_id,
            "symbol": event.symbol,
            "ca_type": event.ca_type,
            "amount_per_share": event.amount_per_share,
            "split_from": event.split_from,
            "split_to": event.split_to,
            "currency": event.currency,
            "announcement_date": event.announcement_date,
            "ex_date": event.ex_date,
            "record_date": event.record_date,
            "payable_date": event.payable_date,
            "raw_payload": json.dumps(event.raw_payload) if event.raw_payload else None,
            "status": CaStatus.PENDING,
            "ingested_at": now,
        }
        with self.engine.begin() as conn:
            result = conn.execute(stmt, params)
            row_id = result.lastrowid
            if result.rowcount == 0:
                LOGGER.debug("Événement corporate action doublon ignoré | key=%s", event.idempotency_key)
                return -1
            LOGGER.info(
                "Événement corporate action ingéré | id=%s symbol=%s type=%s ex_date=%s",
                row_id, event.symbol, event.ca_type, event.ex_date,
            )
            return row_id or -1

    def insert_event_sqlite(self, event: CorporateActionEvent) -> int:
        """Insert compatible SQLite (tests). Utilise INSERT OR IGNORE."""
        stmt = text("""
            INSERT OR IGNORE INTO corporate_actions_events
                (idempotency_key, provider, provider_event_id, symbol, ca_type,
                 amount_per_share, split_from, split_to, currency,
                 announcement_date, ex_date, record_date, payable_date,
                 raw_payload, status, ingested_at)
            VALUES
                (:idempotency_key, :provider, :provider_event_id, :symbol, :ca_type,
                 :amount_per_share, :split_from, :split_to, :currency,
                 :announcement_date, :ex_date, :record_date, :payable_date,
                 :raw_payload, :status, :ingested_at)
        """)
        now = datetime.now(timezone.utc)
        params: dict[str, Any] = {
            "idempotency_key": event.idempotency_key,
            "provider": event.provider,
            "provider_event_id": event.provider_event_id,
            "symbol": event.symbol,
            "ca_type": event.ca_type,
            "amount_per_share": event.amount_per_share,
            "split_from": event.split_from,
            "split_to": event.split_to,
            "currency": event.currency,
            "announcement_date": event.announcement_date,
            "ex_date": event.ex_date,
            "record_date": event.record_date,
            "payable_date": event.payable_date,
            "raw_payload": json.dumps(event.raw_payload) if event.raw_payload else None,
            "status": CaStatus.PENDING,
            "ingested_at": now,
        }
        with self.engine.begin() as conn:
            result = conn.execute(stmt, params)
            if result.rowcount == 0:
                return -1
            return result.lastrowid or -1

    # ------------------------------------------------------------------
    # Lecture événements pending
    # ------------------------------------------------------------------

    def load_pending_events(self, as_of: Any = None) -> list[CorporateActionEvent]:
        """Charge les événements pending dont l'ex_date <= as_of (ou tous si None)."""
        if as_of:
            stmt = text("""
                SELECT id, idempotency_key, provider, provider_event_id, symbol, ca_type,
                       amount_per_share, split_from, split_to, currency,
                       announcement_date, ex_date, record_date, payable_date,
                       raw_payload, status, ingested_at
                FROM corporate_actions_events
                WHERE status = 'pending' AND ex_date <= :as_of
                ORDER BY ex_date ASC, id ASC
            """)
            params = {"as_of": as_of}
        else:
            stmt = text("""
                SELECT id, idempotency_key, provider, provider_event_id, symbol, ca_type,
                       amount_per_share, split_from, split_to, currency,
                       announcement_date, ex_date, record_date, payable_date,
                       raw_payload, status, ingested_at
                FROM corporate_actions_events
                WHERE status = 'pending'
                ORDER BY ex_date ASC, id ASC
            """)
            params = {}
        with self.engine.connect() as conn:
            rows = conn.execute(stmt, params).mappings().all()
        return [self._row_to_event(r) for r in rows]

    def is_event_applied(self, idempotency_key: str) -> bool:
        """Vérifie si un événement a déjà été appliqué."""
        stmt = text("""
            SELECT status FROM corporate_actions_events
            WHERE idempotency_key = :key
        """)
        with self.engine.connect() as conn:
            status = conn.execute(stmt, {"key": idempotency_key}).scalar_one_or_none()
        return status == CaStatus.APPLIED

    # ------------------------------------------------------------------
    # Mise à jour statut
    # ------------------------------------------------------------------

    def mark_applied(self, event_id: int) -> None:
        stmt = text("""
            UPDATE corporate_actions_events
            SET status = 'applied', applied_at = :now
            WHERE id = :id
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, {"id": event_id, "now": datetime.now(timezone.utc)})

    def mark_failed(self, event_id: int, error_message: str) -> None:
        stmt = text("""
            UPDATE corporate_actions_events
            SET status = 'failed', error_message = :err, applied_at = :now
            WHERE id = :id
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, {"id": event_id, "err": error_message[:500], "now": datetime.now(timezone.utc)})

    def mark_skipped(self, event_id: int, reason: str) -> None:
        stmt = text("""
            UPDATE corporate_actions_events
            SET status = 'skipped', error_message = :reason
            WHERE id = :id
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, {"id": event_id, "reason": reason[:500]})

    # ------------------------------------------------------------------
    # Applications & ledger
    # ------------------------------------------------------------------

    def insert_application(self, app: CorporateActionApplication, account_id: str | None = None) -> None:
        stmt = text("""
            INSERT INTO corporate_actions_applications
                (event_id, symbol, ca_type,
                 position_qty_before, position_qty_after,
                 cost_basis_before, cost_basis_after,
                 cash_impact, fractional_shares, account_id, applied_at)
            VALUES
                (:event_id, :symbol, :ca_type,
                 :qty_before, :qty_after,
                 :cb_before, :cb_after,
                 :cash_impact, :fractional, :account_id, :now)
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, {
                "event_id": app.event_id,
                "symbol": app.symbol,
                "ca_type": app.ca_type,
                "qty_before": app.position_qty_before,
                "qty_after": app.position_qty_after,
                "cb_before": app.cost_basis_before,
                "cb_after": app.cost_basis_after,
                "cash_impact": app.cash_impact,
                "fractional": app.fractional_shares,
                "account_id": account_id or "default",
                "now": datetime.now(timezone.utc),
            })

    def insert_cash_ledger(self, entry: CashLedgerEntry, account_id: str | None = None) -> None:
        stmt = text("""
            INSERT INTO portfolio_cash_ledger
                (event_id, symbol, entry_type, amount, currency, description, account_id, created_at)
            VALUES
                (:event_id, :symbol, :entry_type, :amount, :currency, :description, :account_id, :now)
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, {
                "event_id": entry.event_id,
                "symbol": entry.symbol,
                "entry_type": entry.entry_type,
                "amount": entry.amount,
                "currency": entry.currency,
                "description": entry.description,
                "account_id": account_id or "default",
                "now": datetime.now(timezone.utc),
            })

    def get_total_dividends(self, symbol: str | None = None) -> float:
        """Retourne le total des dividendes crédités."""
        if symbol:
            stmt = text("SELECT COALESCE(SUM(amount), 0) FROM portfolio_cash_ledger WHERE entry_type = 'dividend_credit' AND symbol = :sym")
            params: dict[str, Any] = {"sym": symbol}
        else:
            stmt = text("SELECT COALESCE(SUM(amount), 0) FROM portfolio_cash_ledger WHERE entry_type = 'dividend_credit'")
            params = {}
        with self.engine.connect() as conn:
            return float(conn.execute(stmt, params).scalar_one())

    # ------------------------------------------------------------------
    # Positions broker (lecture du dernier snapshot)
    # ------------------------------------------------------------------

    def load_latest_positions(self, account_id: str | None = None) -> list[dict[str, Any]]:
        """Charge le dernier snapshot des positions broker, filtré par account_id si fourni."""
        if account_id:
            stmt = text("""
                SELECT symbol, qty, avg_entry_price, market_value, unrealized_pnl
                FROM broker_positions_snapshots
                WHERE account_id = :account_id
                  AND exec_run_id = (
                    SELECT exec_run_id FROM broker_positions_snapshots
                    WHERE account_id = :account_id
                    ORDER BY created_at DESC LIMIT 1
                )
            """)
            params: dict[str, Any] = {"account_id": account_id}
        else:
            stmt = text("""
                SELECT symbol, qty, avg_entry_price, market_value, unrealized_pnl
                FROM broker_positions_snapshots
                WHERE exec_run_id = (
                    SELECT exec_run_id FROM broker_positions_snapshots
                    ORDER BY created_at DESC LIMIT 1
                )
            """)
            params = {}
        with self.engine.connect() as conn:
            rows = conn.execute(stmt, params).mappings().all()
        return [dict(r) for r in rows]

    def load_latest_position_symbols(self) -> list[str]:
        """Retourne les symboles distincts du dernier snapshot broker avec qty non nulle."""
        rows = self.load_latest_positions()
        symbols = {
            str(r.get("symbol", "")).strip().upper()
            for r in rows
            if str(r.get("symbol", "")).strip() and float(r.get("qty", 0) or 0) != 0.0
        }
        return sorted(symbols)

    def load_bars_available_symbols(self) -> list[str]:
        """Retourne les symboles actifs/tradables avec bars disponibles depuis stock_metadata."""
        stmt = text("""
            SELECT symbol
            FROM stock_metadata
            WHERE status = 'active'
              AND tradable = 1
              AND bars_available = 1
            ORDER BY symbol ASC
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).scalars().all()
        return [str(symbol).strip().upper() for symbol in rows if str(symbol).strip()]

    def load_existing_event_symbols(self, symbols: list[str] | None = None) -> list[str]:
        """Retourne les symboles déjà présents dans corporate_actions_events."""
        if symbols == []:
            return []

        if symbols is None:
            stmt = text("""
                SELECT DISTINCT symbol
                FROM corporate_actions_events
                WHERE symbol IS NOT NULL
                  AND TRIM(symbol) <> ''
                ORDER BY symbol ASC
            """)
            params: dict[str, Any] = {}
        else:
            normalized_symbols = sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})
            if not normalized_symbols:
                return []

            placeholders = ", ".join(f":symbol_{idx}" for idx in range(len(normalized_symbols)))
            stmt = text(f"""
                SELECT DISTINCT symbol
                FROM corporate_actions_events
                WHERE UPPER(symbol) IN ({placeholders})
                ORDER BY symbol ASC
            """)
            params = {f"symbol_{idx}": symbol for idx, symbol in enumerate(normalized_symbols)}

        with self.engine.connect() as conn:
            rows = conn.execute(stmt, params).scalars().all()
        return sorted({str(symbol).strip().upper() for symbol in rows if str(symbol).strip()})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_event(r: Any) -> CorporateActionEvent:
        raw = r.get("raw_payload") or r.get("raw_payload")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                raw = None
        return CorporateActionEvent(
            id=int(r["id"]),
            provider=str(r["provider"]),
            provider_event_id=str(r["provider_event_id"]) if r.get("provider_event_id") else None,
            symbol=str(r["symbol"]),
            ca_type=str(r["ca_type"]),
            amount_per_share=float(r["amount_per_share"]) if r.get("amount_per_share") is not None else None,
            split_from=int(r["split_from"]) if r.get("split_from") is not None else None,
            split_to=int(r["split_to"]) if r.get("split_to") is not None else None,
            currency=str(r.get("currency", "USD")),
            announcement_date=r.get("announcement_date"),
            ex_date=r["ex_date"],
            record_date=r.get("record_date"),
            payable_date=r.get("payable_date"),
            raw_payload=raw,
            status=str(r["status"]),
            ingested_at=r.get("ingested_at"),
        )



