"""Persistence and point-in-time resolution of the tradable universe."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable, Literal
from uuid import uuid4

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from common.capital_presets import DEFAULT_CAPITAL_PRESET_KEY

UniverseRunStatus = Literal["running", "completed", "failed"]


class UniverseSnapshotNotFoundError(RuntimeError):
    """Raised when no complete canonical snapshot exists as-of a date."""


@dataclass(frozen=True, slots=True)
class UniverseMember:
    symbol: str
    is_tradable: bool
    tradability_reason_code: str
    tradability_reasons: tuple[str, ...] = ()
    history_days: int | None = None
    bars_available: bool | None = None
    data_source: str | None = None
    close_price: float | None = None
    adv_usd: float | None = None
    spread_bps: float | None = None
    market_cap: float | None = None
    atr_pct_20: float | None = None
    earnings_blackout: bool | None = None
    data_quality_grade: str = "unknown"

    def __post_init__(self) -> None:
        normalized_symbol = str(self.symbol or "").strip().upper()
        normalized_reason = str(self.tradability_reason_code or "").strip()
        if not normalized_symbol:
            raise ValueError("UniverseMember.symbol est obligatoire.")
        if not normalized_reason:
            raise ValueError("UniverseMember.tradability_reason_code est obligatoire.")
        object.__setattr__(self, "symbol", normalized_symbol)
        object.__setattr__(self, "tradability_reason_code", normalized_reason)


@dataclass(frozen=True, slots=True)
class UniverseResolution:
    frame: pd.DataFrame
    universe_run_id: str
    snapshot_date: date
    capital_preset_key: str
    config_fingerprint: str
    data_quality_grade: str
    rows_expected: int
    rows_written: int

    @property
    def symbols(self) -> list[str]:
        if self.frame.empty:
            return []
        return self.frame["symbol"].astype(str).tolist()


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def universe_schema_available(engine: Engine) -> bool:
    """Return whether both PIT universe tables are installed."""
    try:
        inspector = inspect(engine)
        return inspector.has_table("tradable_universe_runs") and inspector.has_table(
            "tradable_universe_history"
        )
    except Exception:
        return False


def begin_universe_run(
    engine: Engine,
    *,
    snapshot_date: date,
    capital_preset_key: str,
    config_fingerprint: str,
    rows_expected: int,
    universe_run_id: str | None = None,
    data_quality_grade: str = "unknown",
) -> str:
    if rows_expected < 0:
        raise ValueError("rows_expected doit être >= 0.")
    run_id = str(universe_run_id or f"universe-{uuid4().hex}").strip()
    if not run_id:
        raise ValueError("universe_run_id est obligatoire.")
    preset_key = str(capital_preset_key or "").strip()
    fingerprint = str(config_fingerprint or "").strip()
    if not preset_key or not fingerprint:
        raise ValueError("capital_preset_key et config_fingerprint sont obligatoires.")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO tradable_universe_runs (
                    universe_run_id, snapshot_date, capital_preset_key,
                    config_fingerprint, status, is_canonical,
                    rows_expected, rows_written, tradable_rows,
                    data_quality_grade, started_at
                ) VALUES (
                    :run_id, :snapshot_date, :preset_key,
                    :fingerprint, 'running', 0,
                    :rows_expected, 0, 0,
                    :data_quality_grade, :started_at
                )
                """
            ),
            {
                "run_id": run_id,
                "snapshot_date": snapshot_date,
                "preset_key": preset_key,
                "fingerprint": fingerprint,
                "rows_expected": rows_expected,
                "data_quality_grade": data_quality_grade,
                "started_at": _utc_now_naive(),
            },
        )
    return run_id


def publish_universe_run(
    engine: Engine,
    universe_run_id: str,
    members: Iterable[UniverseMember],
) -> None:
    normalized_members = list(members)
    symbols = [member.symbol for member in normalized_members]
    if len(symbols) != len(set(symbols)):
        raise ValueError("Un snapshot d'univers ne peut pas contenir deux fois le même symbole.")

    with engine.begin() as connection:
        run = connection.execute(
            text(
                """
                SELECT snapshot_date, capital_preset_key, status, rows_expected
                FROM tradable_universe_runs
                WHERE universe_run_id = :run_id
                """
            ),
            {"run_id": universe_run_id},
        ).mappings().first()
        if run is None:
            raise ValueError(f"Run univers introuvable: {universe_run_id}")
        if str(run["status"]) != "running":
            raise ValueError(f"Le run univers {universe_run_id} n'est pas en statut running.")
        rows_expected = int(run["rows_expected"])
        if len(normalized_members) != rows_expected:
            raise ValueError(
                f"Snapshot incomplet: rows_written={len(normalized_members)} rows_expected={rows_expected}."
            )

        created_at = _utc_now_naive()
        if normalized_members:
            connection.execute(
                text(
                    """
                    INSERT INTO tradable_universe_history (
                        universe_run_id, symbol, is_tradable,
                        tradability_reason_code, tradability_reasons_json,
                        history_days, bars_available, data_source, close_price,
                        adv_usd, spread_bps, market_cap, atr_pct_20,
                        earnings_blackout, data_quality_grade, created_at
                    ) VALUES (
                        :run_id, :symbol, :is_tradable,
                        :reason_code, :reasons_json,
                        :history_days, :bars_available, :data_source, :close_price,
                        :adv_usd, :spread_bps, :market_cap, :atr_pct_20,
                        :earnings_blackout, :data_quality_grade, :created_at
                    )
                    """
                ),
                [
                    {
                        "run_id": universe_run_id,
                        "symbol": member.symbol,
                        "is_tradable": bool(member.is_tradable),
                        "reason_code": member.tradability_reason_code,
                        "reasons_json": json.dumps(list(member.tradability_reasons)),
                        "history_days": member.history_days,
                        "bars_available": member.bars_available,
                        "data_source": member.data_source,
                        "close_price": member.close_price,
                        "adv_usd": member.adv_usd,
                        "spread_bps": member.spread_bps,
                        "market_cap": member.market_cap,
                        "atr_pct_20": member.atr_pct_20,
                        "earnings_blackout": member.earnings_blackout,
                        "data_quality_grade": member.data_quality_grade,
                        "created_at": created_at,
                    }
                    for member in normalized_members
                ],
            )

        connection.execute(
            text(
                """
                UPDATE tradable_universe_runs
                SET is_canonical = 0
                WHERE snapshot_date = :snapshot_date
                  AND capital_preset_key = :preset_key
                  AND is_canonical = 1
                """
            ),
            {
                "snapshot_date": run["snapshot_date"],
                "preset_key": run["capital_preset_key"],
            },
        )
        connection.execute(
            text(
                """
                UPDATE tradable_universe_runs
                SET status = 'completed',
                    is_canonical = 1,
                    rows_written = :rows_written,
                    tradable_rows = :tradable_rows,
                    finished_at = :finished_at
                WHERE universe_run_id = :run_id
                  AND status = 'running'
                """
            ),
            {
                "run_id": universe_run_id,
                "rows_written": len(normalized_members),
                "tradable_rows": sum(member.is_tradable for member in normalized_members),
                "finished_at": created_at,
            },
        )


def fail_universe_run(engine: Engine, universe_run_id: str, reason: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE tradable_universe_runs
                SET status = 'failed', is_canonical = 0,
                    failure_reason = :reason, finished_at = :finished_at
                WHERE universe_run_id = :run_id AND status = 'running'
                """
            ),
            {
                "run_id": universe_run_id,
                "reason": str(reason or "unknown_failure"),
                "finished_at": _utc_now_naive(),
            },
        )


def resolve_universe_asof(
    engine: Engine,
    trade_date: date,
    capital_preset_key: str,
    *,
    tradable_only: bool = True,
) -> UniverseResolution:
    with engine.connect() as connection:
        run = connection.execute(
            text(
                """
                SELECT universe_run_id, snapshot_date, capital_preset_key,
                       config_fingerprint, data_quality_grade,
                       rows_expected, rows_written
                FROM tradable_universe_runs
                WHERE capital_preset_key = :preset_key
                  AND snapshot_date <= :trade_date
                  AND status = 'completed'
                  AND is_canonical = 1
                  AND rows_written = rows_expected
                ORDER BY snapshot_date DESC, finished_at DESC
                LIMIT 1
                """
            ),
            {"preset_key": capital_preset_key, "trade_date": trade_date},
        ).mappings().first()
        if run is None:
            raise UniverseSnapshotNotFoundError(
                f"Aucun univers complet publié pour preset={capital_preset_key} asof={trade_date}."
            )

        tradable_clause = "AND is_tradable = 1" if tradable_only else ""
        frame = pd.read_sql(
            text(
                f"""
                SELECT symbol, is_tradable, tradability_reason_code,
                       tradability_reasons_json, history_days, bars_available,
                       data_source, close_price, adv_usd, spread_bps,
                       market_cap, atr_pct_20, earnings_blackout,
                       data_quality_grade, created_at
                FROM tradable_universe_history
                WHERE universe_run_id = :run_id
                  {tradable_clause}
                ORDER BY symbol
                """
            ),
            connection,
            params={"run_id": run["universe_run_id"]},
        )

    snapshot_date = run["snapshot_date"]
    if isinstance(snapshot_date, str):
        snapshot_date = date.fromisoformat(snapshot_date)
    return UniverseResolution(
        frame=frame,
        universe_run_id=str(run["universe_run_id"]),
        snapshot_date=snapshot_date,
        capital_preset_key=str(run["capital_preset_key"]),
        config_fingerprint=str(run["config_fingerprint"]),
        data_quality_grade=str(run["data_quality_grade"]),
        rows_expected=int(run["rows_expected"]),
        rows_written=int(run["rows_written"]),
    )


def load_tradable_universe_for_period(
    engine: Engine,
    start_date: date,
    end_date: date,
    capital_preset_key: str = DEFAULT_CAPITAL_PRESET_KEY,
    *,
    tradable_only: bool = True,
) -> list[str]:
    """Retourne l'union des symboles tradables sur une période.

    Interroge tous les snapshots canoniques complétés entre *start_date* et
    *end_date* (inclus) et retourne la liste triée et dédupliquée des symboles
    qui étaient tradables à au moins une date de la période.

    Args:
        engine: Connexion SQLAlchemy.
        start_date: Début de la période (inclus).
        end_date: Fin de la période (inclus).
        capital_preset_key: Preset capital utilisé pour filtrer les runs.
        tradable_only: Si True (défaut), ne retourne que les symboles
            ``is_tradable = 1``. Si False, tous les symboles des snapshots.

    Returns:
        Liste triée de symboles uniques.
    """
    if end_date < start_date:
        return []

    tradable_clause = "AND h.is_tradable = 1" if tradable_only else ""
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                f"""
                SELECT DISTINCT UPPER(TRIM(h.symbol)) AS symbol
                FROM tradable_universe_history h
                JOIN tradable_universe_runs r ON r.universe_run_id = h.universe_run_id
                WHERE r.capital_preset_key = :preset_key
                  AND r.snapshot_date BETWEEN :start_date AND :end_date
                  AND r.status = 'completed'
                  AND r.is_canonical = 1
                  AND r.rows_written = r.rows_expected
                  {tradable_clause}
                ORDER BY symbol
                """
            ),
            {
                "preset_key": capital_preset_key,
                "start_date": start_date,
                "end_date": end_date,
            },
        ).scalars().all()

    symbols = [str(symbol) for symbol in rows if symbol]
    return symbols


# ── Universe fingerprint helper (Section 17 Point 2.2) ──────────────────────

def compute_universe_fingerprint(
    universe_run_id: str,
    symbols: list[str],
    snapshot_date: str | date | None = None,
    capital_preset_key: str | None = None,
) -> str:
    """Produit un fingerprint déterministe d'un snapshot d'univers.

    Le fingerprint est un hash SHA256/16 combinant le ``universe_run_id``,
    la liste triée des symboles, et optionnellement la date de snapshot
    et le preset capital. Deux snapshots identiques produisent le même
    fingerprint, garantissant la reproductibilité cross-sectionnelle.

    Parameters
    ----------
    universe_run_id : str
        Identifiant canonique du run d'univers.
    symbols : list[str]
        Liste des symboles tradables (sera triée).
    snapshot_date : str | date | None
        Date du snapshot (optionnelle, renforce la spécificité).
    capital_preset_key : str | None
        Preset capital (optionnel).

    Returns
    -------
    str
        Hash hexadécimal de 16 caractères.
    """
    import hashlib

    normalized_symbols = sorted({s.strip().upper() for s in symbols if s and s.strip()})
    payload = f"{universe_run_id}|{','.join(normalized_symbols)}"
    if snapshot_date is not None:
        payload += f"|{snapshot_date}"
    if capital_preset_key is not None:
        payload += f"|{capital_preset_key}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]