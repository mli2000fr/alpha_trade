"""Repository ``analyst_snapshot_collection`` — collecte prospective Yahoo (RESEARCH ONLY).

Implémente le contrat PIT du chantier (todo3.txt) :
- Append-only strict : chaque nouvelle observation crée une nouvelle ligne ;
  jamais d'UPDATE d'une valeur ancienne.
- Idempotence : insertion "si absente" (vérification de la clé UNIQUE logique
  avant INSERT) ⇒ relancer un run ne crée jamais de doublon.
- Requêtes PIT : ``available_at <= :decision_cutoff`` (un snapshot observé après
  la clôture d'une séance n'est visible qu'à la séance suivante).

Tables (schéma ``alpha_trade``, créées par la migration 0068) :
- ``stock_analyst_estimate_history``
- ``stock_analyst_target_history``
- ``stock_analyst_recommendation_history``
- ``analyst_snapshot_collection_run``

SQL portable MySQL/SQLite (SQLAlchemy Core ``text()``) — les tests passent sur
SQLite en mémoire avec le même schéma logique.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping

from sqlalchemy import text


def _utcnow() -> datetime:
    """UTC NAIVE (MySQL DATETIME), sans dépréciation utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from database.repositories._base import Repository

LOGGER = logging.getLogger(__name__)

SCHEMA = "alpha_trade"

# Clés UNIQUE logiques (miroir des contraintes de la migration 0068).
_ESTIMATE_UNIQUE = ["provider", "symbol", "snapshot_date", "estimate_type", "horizon_normalized"]
_TARGET_UNIQUE = ["provider", "symbol", "snapshot_date"]
_RECOMMENDATION_UNIQUE = ["provider", "symbol", "snapshot_date", "period_raw"]

_ESTIMATE_COLS = [
    "provider", "symbol", "snapshot_date", "observed_at", "available_at",
    "estimate_type", "horizon_raw", "horizon_normalized",
    "fiscal_period_end", "fiscal_year", "fiscal_quarter", "relative_horizon_only",
    "avg_value", "low_value", "high_value", "analyst_count", "growth_value",
    "raw_payload_json", "raw_hash", "provider_schema_version",
]
_TARGET_COLS = [
    "provider", "symbol", "snapshot_date", "observed_at", "available_at",
    "current_price", "target_low", "target_mean", "target_median", "target_high",
    "analyst_count", "raw_payload_json", "raw_hash", "provider_schema_version",
]
_RECOMMENDATION_COLS = [
    "provider", "symbol", "snapshot_date", "observed_at", "available_at",
    "period_raw", "strong_buy", "buy", "hold", "sell", "strong_sell",
    "raw_payload_json", "raw_hash", "provider_schema_version",
]
_RUN_COLS = [
    "run_id", "provider", "started_at", "finished_at", "requested_symbols",
    "successful_symbols", "empty_symbols", "failed_symbols",
    "estimates_rows_inserted", "targets_rows_inserted", "recommendations_rows_inserted",
    "rate_limit_count", "temporary_error_count", "schema_error_count", "parse_error_count",
    "eps_coverage", "revenue_coverage", "target_coverage", "recommendation_coverage",
    "status",
]

_SCHEMA_PREFIX = "alpha_trade."


def _q(table: str) -> str:
    """Nom qualifié de table (compatible MySQL ; ignoré par SQLite en tests)."""
    return f"{_SCHEMA_PREFIX}{table}"


def _insert_if_absent(
    conn: Any,
    table: str,
    unique_cols: list[str],
    row: Mapping[str, Any],
) -> bool:
    """Insère ``row`` si aucune ligne existante ne porte la clé UNIQUE logique.

    Retourne True si une ligne a été insérée (append-only), False sinon
    (doublon détecté → idempotent, aucune écriture).
    """
    where = " AND ".join(f"{c} = :{c}" for c in unique_cols)
    exists = conn.execute(
        text(f"SELECT 1 FROM {_q(table)} WHERE {where} LIMIT 1"),
        {c: row[c] for c in unique_cols},
    ).first()
    if exists is not None:
        return False
    cols = list(row.keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    colnames = ", ".join(cols)
    conn.execute(
        text(f"INSERT INTO {_q(table)} ({colnames}) VALUES ({placeholders})"),
        dict(row),
    )
    return True


class AnalystSnapshotRepository(Repository):
    """Repository de la collecte prospective d'analyst data Yahoo."""

    # ── Inserts (append-only, idempotents) ────────────────────────────────

    def insert_estimate_snapshots(self, rows: Iterable[Mapping[str, Any]]) -> int:
        """Insère des snapshots d'estimates (EPS/REVENUE). Retourne le nb inséré."""
        n = 0
        with self.transaction() as conn:
            for row in rows:
                payload = {c: row.get(c) for c in _ESTIMATE_COLS}
                if _insert_if_absent(conn, "stock_analyst_estimate_history",
                                     _ESTIMATE_UNIQUE, payload):
                    n += 1
        return n

    def insert_target_snapshots(self, rows: Iterable[Mapping[str, Any]]) -> int:
        n = 0
        with self.transaction() as conn:
            for row in rows:
                payload = {c: row.get(c) for c in _TARGET_COLS}
                if _insert_if_absent(conn, "stock_analyst_target_history",
                                     _TARGET_UNIQUE, payload):
                    n += 1
        return n

    def insert_recommendation_snapshots(self, rows: Iterable[Mapping[str, Any]]) -> int:
        n = 0
        with self.transaction() as conn:
            for row in rows:
                payload = {c: row.get(c) for c in _RECOMMENDATION_COLS}
                if _insert_if_absent(conn, "stock_analyst_recommendation_history",
                                     _RECOMMENDATION_UNIQUE, payload):
                    n += 1
        return n

    # ── Runs de collecte ──────────────────────────────────────────────────

    def start_collection_run(self, run_id: str, provider: str, requested_symbols: int,
                             started_at: datetime | None = None) -> None:
        row = {
            "run_id": run_id, "provider": provider,
            "started_at": started_at or _utcnow(),
            "requested_symbols": requested_symbols, "status": "RUNNING",
        }
        with self.transaction() as conn:
            _insert_if_absent(conn, "analyst_snapshot_collection_run",
                              ["run_id"], {c: row[c] for c in _RUN_COLS if c in row})

    def finish_collection_run(self, run_id: str, *, stats: Mapping[str, Any],
                              status: str = "COMPLETED",
                              finished_at: datetime | None = None) -> None:
        allowed = {c: stats.get(c) for c in _RUN_COLS if c in stats}
        sets = ", ".join(f"{c} = :{c}" for c in allowed)
        params = dict(allowed)
        params["run_id"] = run_id
        params["finished_at"] = finished_at or _utcnow()
        params["status"] = status
        sql = (f"UPDATE {_q('analyst_snapshot_collection_run')} "
               f"SET finished_at = :finished_at, status = :status"
               + (f", {sets}" if sets else "") + " WHERE run_id = :run_id")
        with self.transaction() as conn:
            conn.execute(text(sql), params)

    # ── Requêtes PIT (available_at <= cutoff) ─────────────────────────────

    def get_latest_estimate_before(
        self,
        symbol: str,
        estimate_type: str,
        horizon_normalized: str,
        cutoff: datetime,
    ) -> dict[str, Any] | None:
        sql = (
            f"SELECT * FROM {_q('stock_analyst_estimate_history')} "
            "WHERE symbol = :symbol AND estimate_type = :et AND horizon_normalized = :hz "
            "AND available_at <= :cutoff ORDER BY available_at DESC, id DESC LIMIT 1"
        )
        with self.connect() as conn:
            row = conn.execute(text(sql), {
                "symbol": symbol, "et": estimate_type, "hz": horizon_normalized,
                "cutoff": cutoff,
            }).mappings().first()
        return dict(row) if row else None

    def get_latest_target_before(self, symbol: str, cutoff: datetime) -> dict[str, Any] | None:
        sql = (
            f"SELECT * FROM {_q('stock_analyst_target_history')} "
            "WHERE symbol = :symbol AND available_at <= :cutoff "
            "ORDER BY available_at DESC, id DESC LIMIT 1"
        )
        with self.connect() as conn:
            row = conn.execute(text(sql), {"symbol": symbol, "cutoff": cutoff}).mappings().first()
        return dict(row) if row else None

    def get_latest_recommendation_before(
        self, symbol: str, period_raw: str, cutoff: datetime
    ) -> dict[str, Any] | None:
        sql = (
            f"SELECT * FROM {_q('stock_analyst_recommendation_history')} "
            "WHERE symbol = :symbol AND period_raw = :pr AND available_at <= :cutoff "
            "ORDER BY available_at DESC, id DESC LIMIT 1"
        )
        with self.connect() as conn:
            row = conn.execute(text(sql), {
                "symbol": symbol, "pr": period_raw, "cutoff": cutoff,
            }).mappings().first()
        return dict(row) if row else None

    # ── Historiques ───────────────────────────────────────────────────────

    def get_estimate_history(
        self,
        symbol: str,
        estimate_type: str | None = None,
        horizon_normalized: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        sql = (
            f"SELECT * FROM {_q('stock_analyst_estimate_history')} "
            "WHERE symbol = :symbol"
        )
        params: dict[str, Any] = {"symbol": symbol}
        if estimate_type:
            sql += " AND estimate_type = :et"
            params["et"] = estimate_type
        if horizon_normalized:
            sql += " AND horizon_normalized = :hz"
            params["hz"] = horizon_normalized
        sql += " ORDER BY available_at ASC, id ASC"
        if limit:
            sql += " LIMIT :lim"
            params["lim"] = limit
        with self.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]

    def get_target_history(self, symbol: str, limit: int | None = None) -> list[dict[str, Any]]:
        sql = (
            f"SELECT * FROM {_q('stock_analyst_target_history')} "
            "WHERE symbol = :symbol ORDER BY available_at ASC, id ASC"
        )
        params: dict[str, Any] = {"symbol": symbol}
        if limit:
            sql += " LIMIT :lim"
            params["lim"] = limit
        with self.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]

    def get_recommendation_history(
        self, symbol: str, period_raw: str = "0m", limit: int | None = None
    ) -> list[dict[str, Any]]:
        sql = (
            f"SELECT * FROM {_q('stock_analyst_recommendation_history')} "
            "WHERE symbol = :symbol AND period_raw = :pr "
            "ORDER BY available_at ASC, id ASC"
        )
        params: dict[str, Any] = {"symbol": symbol, "pr": period_raw}
        if limit:
            sql += " LIMIT :lim"
            params["lim"] = limit
        with self.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]

    # ── Runs / monitoring ─────────────────────────────────────────────────

    def get_last_collection_run(self) -> dict[str, Any] | None:
        sql = (
            f"SELECT * FROM {_q('analyst_snapshot_collection_run')} "
            "ORDER BY started_at DESC, id DESC LIMIT 1"
        )
        with self.connect() as conn:
            row = conn.execute(text(sql)).mappings().first()
        return dict(row) if row else None

    def get_collection_run(self, run_id: str) -> dict[str, Any] | None:
        sql = f"SELECT * FROM {_q('analyst_snapshot_collection_run')} WHERE run_id = :run_id"
        with self.connect() as conn:
            row = conn.execute(text(sql), {"run_id": run_id}).mappings().first()
        return dict(row) if row else None

    def count_rows(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for name in ("stock_analyst_estimate_history", "stock_analyst_target_history",
                     "stock_analyst_recommendation_history"):
            with self.connect() as conn:
                out[name] = int(conn.execute(
                    text(f"SELECT COUNT(*) FROM {_q(name)}")
                ).scalar())
        return out

    def get_symbols_with_snapshot_on(self, snapshot_date: date) -> set[str]:
        """Symboles ayant déjà un snapshot à ``snapshot_date`` (pour ``--resume``)."""
        out: set[str] = set()
        tables = ("stock_analyst_estimate_history", "stock_analyst_target_history",
                  "stock_analyst_recommendation_history")
        with self.connect() as conn:
            for t in tables:
                rows = conn.execute(
                    text(f"SELECT DISTINCT symbol FROM {_q(t)} WHERE snapshot_date = :d"),
                    {"d": snapshot_date},
                ).all()
                out.update(r[0] for r in rows)
        return out
