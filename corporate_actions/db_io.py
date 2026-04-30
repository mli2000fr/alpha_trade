"""Accès base de données pour le module corporate_actions."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import MetaData, Table, and_, select, text
from sqlalchemy.engine import Engine

from corporate_actions.models import (
    CaStatus,
    CashLedgerEntry,
    CorporateActionApplication,
    CorporateActionEvent,
)
from database.assets import build_eligible_stock_metadata_filters
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

    def insert_event(self, event: CorporateActionEvent, account_id: str | None = None) -> int:
        """
        Insère un événement dans corporate_actions_events.

        Phase 5.3.a — la clé scopée ``account_idempotency_key`` est calculée à
        partir de ``account_id`` (``None`` → clé legacy = ``GLOBAL`` implicite).

        Retourne l'id de la ligne insérée, ou -1 si doublon (idempotency_key).
        """
        if self._is_sqlite:
            return self.insert_event_sqlite(event, account_id=account_id)
        stmt = text("""
            INSERT INTO corporate_actions_events
                (idempotency_key, account_idempotency_key, provider, provider_event_id, symbol, ca_type,
                 amount_per_share, split_from, split_to, currency,
                 announcement_date, ex_date, record_date, payable_date,
                 raw_payload, status, ingested_at)
            VALUES
                (:idempotency_key, :account_idempotency_key, :provider, :provider_event_id, :symbol, :ca_type,
                 :amount_per_share, :split_from, :split_to, :currency,
                 :announcement_date, :ex_date, :record_date, :payable_date,
                 :raw_payload, :status, :ingested_at)
            ON DUPLICATE KEY UPDATE id = id
        """)
        now = datetime.now(timezone.utc)
        params: dict[str, Any] = {
            "idempotency_key": event.idempotency_key,
            "account_idempotency_key": event.compute_idempotency_key(account_id),
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
                LOGGER.debug("Evenement corporate action doublon ignore | key=%s", event.idempotency_key)
                return -1
            LOGGER.info(
                "Evenement corporate action ingere | id=%s symbol=%s type=%s ex_date=%s",
                row_id, event.symbol, event.ca_type, event.ex_date,
            )
            return row_id or -1

    def insert_event_sqlite(self, event: CorporateActionEvent, account_id: str | None = None) -> int:
        """Insert compatible SQLite (tests). Utilise INSERT OR IGNORE."""
        # Phase 5.3.a — colonne ``account_idempotency_key`` optionnelle : on
        # vérifie sa présence dans le schéma SQLite pour rester compatible avec
        # les fixtures de test legacy qui ne la déclarent pas encore.
        has_account_col = self._sqlite_has_column(
            "corporate_actions_events", "account_idempotency_key"
        )
        if has_account_col:
            stmt = text("""
                INSERT OR IGNORE INTO corporate_actions_events
                    (idempotency_key, account_idempotency_key, provider, provider_event_id, symbol, ca_type,
                     amount_per_share, split_from, split_to, currency,
                     announcement_date, ex_date, record_date, payable_date,
                     raw_payload, status, ingested_at)
                VALUES
                    (:idempotency_key, :account_idempotency_key, :provider, :provider_event_id, :symbol, :ca_type,
                     :amount_per_share, :split_from, :split_to, :currency,
                     :announcement_date, :ex_date, :record_date, :payable_date,
                     :raw_payload, :status, :ingested_at)
            """)
        else:
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
        if has_account_col:
            params["account_idempotency_key"] = event.compute_idempotency_key(account_id)
        with self.engine.begin() as conn:
            result = conn.execute(stmt, params)
            if result.rowcount == 0:
                return -1
            return result.lastrowid or -1

    def _sqlite_has_column(self, table: str, column: str) -> bool:
        """Phase 5.3.a — utilitaire pour rester compatible avec les fixtures
        SQLite des tests qui n'ont pas encore appliqué la migration 0019."""
        if not self._is_sqlite:
            return True
        with self.engine.connect() as conn:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).mappings().all()
        return any(str(r.get("name", "")).lower() == column.lower() for r in rows)

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

    def is_event_applied(self, idempotency_key: str, legacy_key: str | None = None) -> bool:
        """Vérifie si un événement a déjà été appliqué.

        Phase 5.3.a — la clé est désormais scopée par ``account_id`` via
        :meth:`CorporateActionEvent.compute_idempotency_key`. Pour les events
        ingérés avant la migration ``0019``, la colonne
        ``account_idempotency_key`` est NULL et la clé scopée n'est pas
        retrouvée : on retombe alors sur ``legacy_key`` (sans scope) pour
        éviter de rejouer un dividende déjà appliqué.
        """
        # 1. Recherche par clé scopée (post-migration 0019).
        has_account_col = self._sqlite_has_column(
            "corporate_actions_events", "account_idempotency_key"
        )
        if has_account_col:
            stmt = text(
                "SELECT status FROM corporate_actions_events "
                "WHERE account_idempotency_key = :key"
            )
            with self.engine.connect() as conn:
                status = conn.execute(stmt, {"key": idempotency_key}).scalar_one_or_none()
            if status == CaStatus.APPLIED:
                return True
        # 2. Fallback legacy (events historiques OU clé scopée fournie =
        #    legacy_key parce que account_id était None).
        legacy = legacy_key or idempotency_key
        stmt = text(
            "SELECT status FROM corporate_actions_events "
            "WHERE idempotency_key = :key"
        )
        with self.engine.connect() as conn:
            status = conn.execute(stmt, {"key": legacy}).scalar_one_or_none()
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

    def load_broker_live_position_symbols(self, account_id: str | None = None) -> list[str]:
        """Interroge l'API Alpaca Trading pour récupérer les symboles en position *réelle*."""
        try:
            from service.alpaca.trading_client import AlpacaTradingClient
            client = AlpacaTradingClient(broker_mode="paper", account_id=account_id)
            positions = client.get_positions()
            symbols = {
                str(p.get("symbol", "")).strip().upper()
                for p in positions
                if str(p.get("symbol", "")).strip() and float(p.get("qty", 0) or 0) != 0.0
            }
            LOGGER.info("Broker live positions | count=%d symbols=%s", len(symbols), sorted(symbols))
            return sorted(symbols)
        except Exception:
            LOGGER.warning("Impossible de recuperer les positions live Alpaca, fallback sur snapshot DB.", exc_info=True)
            return []

    def load_pending_buy_order_symbols(self, account_id: str | None = None) -> list[str]:
        """Interroge l'API Alpaca Trading pour récupérer les symboles des ordres BUY ouverts (accepted/new/pending_new)."""
        try:
            from service.alpaca.trading_client import AlpacaTradingClient
            client = AlpacaTradingClient(broker_mode="paper", account_id=account_id)
            orders = client.list_orders(status="open")
            symbols = {
                str(o.get("symbol", "")).strip().upper()
                for o in orders
                if str(o.get("side", "")).lower() == "buy"
                and str(o.get("status", "")).lower() in ("new", "accepted", "pending_new", "held")
                and str(o.get("symbol", "")).strip()
            }
            LOGGER.info("Pending BUY orders | count=%d symbols=%s", len(symbols), sorted(symbols))
            return sorted(symbols)
        except Exception:
            LOGGER.warning("Impossible de recuperer les ordres BUY pending Alpaca.", exc_info=True)
            return []

    def load_bars_available_symbols(self) -> list[str]:
        """Retourne les symboles actifs/tradables avec bars disponibles depuis stock_metadata."""
        stock_metadata = Table("stock_metadata", MetaData(), autoload_with=self.engine)
        stmt = (
            select(stock_metadata.c.symbol)
            .where(and_(*build_eligible_stock_metadata_filters(stock_metadata)))
            .order_by(stock_metadata.c.symbol.asc())
        )
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

    # ------------------------------------------------------------------
    # Phase 5.3.b — Audit run trail (corporate_actions_audit_runs)
    # ------------------------------------------------------------------

    def persist_audit_run(
        self,
        *,
        run_id: str,
        run_kind: str,
        account_id: str | None,
        started_at: datetime,
        finished_at: datetime,
        stats: dict[str, Any] | None = None,
        anomalies: list[dict[str, Any]] | None = None,
        status: str = "completed",
        summary: dict[str, Any] | None = None,
    ) -> None:
        """Persiste une ligne dans ``corporate_actions_audit_runs``.

        Best-effort : si la table n'existe pas (fixtures SQLite legacy), on log
        en debug et on retourne sans lever — l'audit ne doit jamais bloquer le
        run métier.
        """
        stats = stats or {}
        duration = max(0.0, (finished_at - started_at).total_seconds())
        params = {
            "run_id": run_id,
            "run_kind": run_kind,
            "account_id": account_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": round(duration, 3),
            "fetched": int(stats.get("fetched", 0)),
            "inserted": int(stats.get("inserted", 0)),
            "duplicates": int(stats.get("duplicates", 0)),
            "invalid": int(stats.get("invalid", 0)),
            "applied": int(stats.get("applied", 0)),
            "skipped": int(stats.get("skipped", 0)),
            "failed": int(stats.get("failed", 0)),
            "reconcile_diffs": int(stats.get("reconcile_diffs", 0)),
            "anomalies_json": json.dumps(anomalies) if anomalies else None,
            "status": status,
            "summary_json": (
                json.dumps(summary, default=str).encode("utf-8") if summary else None
            ),
        }
        stmt = text(
            "INSERT INTO corporate_actions_audit_runs ("
            "run_id, run_kind, account_id, started_at, finished_at, duration_seconds, "
            "fetched, inserted, duplicates, invalid, applied, skipped, failed, "
            "reconcile_diffs, anomalies_json, status, summary_json"
            ") VALUES ("
            ":run_id, :run_kind, :account_id, :started_at, :finished_at, :duration_seconds, "
            ":fetched, :inserted, :duplicates, :invalid, :applied, :skipped, :failed, "
            ":reconcile_diffs, :anomalies_json, :status, :summary_json"
            ")"
        )
        try:
            with self.engine.begin() as conn:
                conn.execute(stmt, params)
        except Exception:
            LOGGER.debug(
                "Persistance corporate_actions_audit_runs indisponible (run_id=%s).",
                run_id,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Phase 5.3.c — Cross-check Yahoo : chargement events dividendes
    # ------------------------------------------------------------------

    def load_dividend_events_in_range(
        self,
        *,
        start_date: Any,
        end_date: Any,
        symbols: list[str] | None = None,
    ) -> list[CorporateActionEvent]:
        """Charge les events ``cash_dividend`` / ``special_dividend`` ingérés
        dont ``ex_date`` ∈ [start_date, end_date], pour cross-check provider
        externe (Phase 5.3.c)."""
        base_sql = (
            "SELECT id, idempotency_key, provider, provider_event_id, symbol, ca_type, "
            "amount_per_share, split_from, split_to, currency, "
            "announcement_date, ex_date, record_date, payable_date, "
            "raw_payload, status, ingested_at "
            "FROM corporate_actions_events "
            "WHERE ca_type IN ('cash_dividend', 'special_dividend') "
            "AND ex_date BETWEEN :start_date AND :end_date "
        )
        params: dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        if symbols:
            normalized = sorted({s.strip().upper() for s in symbols if s and s.strip()})
            if normalized:
                placeholders = ", ".join(f":sym_{i}" for i in range(len(normalized)))
                base_sql += f"AND UPPER(symbol) IN ({placeholders}) "
                for i, sym in enumerate(normalized):
                    params[f"sym_{i}"] = sym
        base_sql += "ORDER BY ex_date ASC, symbol ASC, id ASC"
        with self.engine.connect() as conn:
            rows = conn.execute(text(base_sql), params).mappings().all()
        return [self._row_to_event(r) for r in rows]
