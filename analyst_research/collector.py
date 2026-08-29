"""Collecteur Yahoo analyst — snapshots PIT append-only dans MySQL (RESEARCH ONLY).

Flux : Yahoo (yfinance) → validation/normalisation (parsers) → MySQL
(``AnalystSnapshotRepository``). Aucun stockage fichier.

Garanties :
- ``observed_at`` = moment réel de l'observation ; ``available_at`` =
  prochaine clôture de séance après observation (voir ``available_at.py``).
- Idempotence : une même (provider, symbol, snapshot_date, …) ne crée jamais de
  doublon (insertion "si absente" dans le repository).
- Classification par symbole : OK / EMPTY / RATE_LIMIT / TEMPORARY_ERROR /
  INVALID_SYMBOL / PROVIDER_SCHEMA_CHANGED / PARSE_ERROR.
- Timeout watchdog par symbole (ThreadPoolExecutor) + retry avec backoff/jitter.
- Une panne Yahoo ne touche jamais aux données historiques déjà stockées.
"""
from __future__ import annotations

import logging
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


def _utcnow() -> datetime:
    """UTC NAIVE (stockage MySQL DATETIME), sans dépréciation utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

import yfinance as yf

from analyst_research.available_at import resolve_available_at, snapshot_date_of, to_utc_naive
from analyst_research.parsers import (
    PROVIDER,
    SCHEMA_VERSION,
    STATUS_EMPTY,
    STATUS_INVALID_SYMBOL,
    STATUS_OK,
    STATUS_PARSE_ERROR,
    STATUS_PROVIDER_SCHEMA_CHANGED,
    STATUS_RATE_LIMIT,
    STATUS_TEMPORARY_ERROR,
    ParseError,
    ProviderSchemaChangedError,
    parse_estimate,
    parse_recommendations,
    parse_targets,
)
from database.repositories.analyst_snapshots import AnalystSnapshotRepository

LOGGER = logging.getLogger(__name__)


@dataclass
class SymbolCollection:
    symbol: str
    status: str = STATUS_OK
    error: str | None = None
    families: dict[str, str] = field(default_factory=dict)
    estimates_rows: list[dict] = field(default_factory=list)
    targets_rows: list[dict] = field(default_factory=list)
    recommendations_rows: list[dict] = field(default_factory=list)


def _classify_exception(e: BaseException) -> str:
    s = f"{type(e).__name__}: {e}".lower()
    if "ratelimit" in type(e).__name__.lower() or "429" in s or "too many requests" in s:
        return STATUS_RATE_LIMIT
    if "no data" in s or "symbol may be delisted" in s or "invalid" in s or "tznone" in s:
        return STATUS_INVALID_SYMBOL
    if "timeout" in s or "connection" in s or "network" in s or "http" in s or "broken" in s:
        return STATUS_TEMPORARY_ERROR
    return STATUS_TEMPORARY_ERROR


def _collect_family(
    ticker: Any,
    attr: str,
    parser: Callable[..., list[dict]],
    ctx: dict[str, Any],
) -> tuple[str, list[dict]]:
    try:
        raw = getattr(ticker, attr)
    except Exception as e:  # noqa: BLE001 - classification explicite
        return _classify_exception(e), []
    try:
        rows = parser(raw, **ctx)
    except ProviderSchemaChangedError:
        return STATUS_PROVIDER_SCHEMA_CHANGED, []
    except ParseError:
        return STATUS_PARSE_ERROR, []
    except Exception as e:  # noqa: BLE001
        LOGGER.debug("%s parse error: %s", attr, e)
        return STATUS_PARSE_ERROR, []
    return (STATUS_OK if rows else STATUS_EMPTY), rows


def collect_symbol(symbol: str, *, observed_at: datetime, timeout_seconds: float) -> SymbolCollection:
    """Collecte les 4 familles Yahoo pour un symbole (avec watchdog timeout)."""
    snapshot_date = snapshot_date_of(observed_at)
    available_at = to_utc_naive(resolve_available_at(observed_at))
    ctx = {
        "symbol": symbol,
        "provider": PROVIDER,
        "snapshot_date": snapshot_date,
        "observed_at": to_utc_naive(observed_at),
        "available_at": available_at,
        "schema_version": SCHEMA_VERSION,
    }
    result = SymbolCollection(symbol=symbol)
    ticker = yf.Ticker(symbol)

    # EPS / REVENUE estimates
    for attr, etype, parser in (
        ("earnings_estimate", "EPS", parse_estimate),
        ("revenue_estimate", "REVENUE", parse_estimate),
    ):
        st, rows = _collect_family(ticker, attr, parser, {**ctx, "estimate_type": etype})
        result.families[f"{attr}"] = st
        result.estimates_rows.extend(rows)

    # Price targets
    st, rows = _collect_family(ticker, "analyst_price_targets", parse_targets, ctx)
    result.families["analyst_price_targets"] = st
    result.targets_rows.extend(rows)

    # Recommendations
    st, rows = _collect_family(ticker, "recommendations", parse_recommendations, ctx)
    result.families["recommendations"] = st
    result.recommendations_rows.extend(rows)

    # Statut global du symbole
    statuses = set(result.families.values())
    if STATUS_RATE_LIMIT in statuses:
        result.status = STATUS_RATE_LIMIT
    elif STATUS_PROVIDER_SCHEMA_CHANGED in statuses:
        result.status = STATUS_PROVIDER_SCHEMA_CHANGED
    elif STATUS_PARSE_ERROR in statuses:
        result.status = STATUS_PARSE_ERROR
    elif STATUS_INVALID_SYMBOL in statuses:
        result.status = STATUS_INVALID_SYMBOL
    elif STATUS_TEMPORARY_ERROR in statuses:
        result.status = STATUS_TEMPORARY_ERROR
    elif any(result.estimates_rows) or any(result.targets_rows) or any(result.recommendations_rows):
        result.status = STATUS_OK
    else:
        result.status = STATUS_EMPTY
    return result


def _collect_with_timeout(symbol: str, *, observed_at: datetime, timeout_seconds: float) -> SymbolCollection:
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(collect_symbol, symbol, observed_at=observed_at, timeout_seconds=timeout_seconds)
        try:
            return fut.result(timeout=timeout_seconds)
        except _FutTimeout:
            return SymbolCollection(symbol=symbol, status=STATUS_TEMPORARY_ERROR,
                                    error="timeout watchdog")


def _collect_with_retries(
    symbol: str,
    *,
    observed_at: datetime,
    timeout_seconds: float,
    max_retries: int,
    base_backoff: float = 1.0,
) -> SymbolCollection:
    for attempt in range(max_retries + 1):
        res = _collect_with_timeout(symbol, observed_at=observed_at, timeout_seconds=timeout_seconds)
        if res.status not in (STATUS_TEMPORARY_ERROR, STATUS_RATE_LIMIT) or attempt == max_retries:
            return res
        backoff = base_backoff * (2 ** attempt) + random.uniform(0, 0.5)
        LOGGER.warning("%s: %s → retry %d/%d (backoff %.1fs)",
                       symbol, res.status, attempt + 1, max_retries, backoff)
        time.sleep(backoff)
    return res  # pragma: no cover - unreachable


def run_collection(
    universe: list[str],
    *,
    write_db: bool = False,
    dry_run: bool = False,
    sleep_seconds: float = 0.25,
    timeout_seconds: float = 20.0,
    max_retries: int = 2,
    run_id: str | None = None,
    log_every: int = 25,
) -> dict[str, Any]:
    """Collecte l'univers et (si ``write_db``) persiste dans MySQL.

    ``dry_run`` : aucune écriture DB, aucun run tracé (POC/validation).
    Retourne un résumé (counts, coverage, runtime).
    """
    if write_db and dry_run:
        raise ValueError("write_db et dry_run sont mutuellement exclusifs")
    repo = AnalystSnapshotRepository()
    started = _utcnow()
    _mono_start = time.monotonic()
    run_id = run_id or f"yahoo_{started.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    if write_db:
        repo.start_collection_run(run_id, PROVIDER, len(universe))

    counts = {
        "estimates": 0, "targets": 0, "recommendations": 0,
        "symbols_ok": 0, "symbols_empty": 0, "symbols_failed": 0,
        "rate_limit": 0, "temporary_error": 0, "schema_error": 0, "parse_error": 0,
        "eps_symbols": 0, "revenue_symbols": 0, "target_symbols": 0, "reco_symbols": 0,
    }
    status_by_symbol: dict[str, str] = {}
    family_counter: dict[str, dict[str, int]] = {}

    for i, symbol in enumerate(universe, start=1):
        observed_at = _utcnow()
        res = _collect_with_retries(
            symbol, observed_at=observed_at,
            timeout_seconds=timeout_seconds, max_retries=max_retries,
        )
        status_by_symbol[symbol] = res.status
        for fam, st in res.families.items():
            family_counter.setdefault(fam, {})[st] = family_counter.setdefault(fam, {}).get(st, 0) + 1

        if write_db:
            counts["estimates"] += repo.insert_estimate_snapshots(res.estimates_rows)
            counts["targets"] += repo.insert_target_snapshots(res.targets_rows)
            counts["recommendations"] += repo.insert_recommendation_snapshots(res.recommendations_rows)
        else:
            counts["estimates"] += len(res.estimates_rows)
            counts["targets"] += len(res.targets_rows)
            counts["recommendations"] += len(res.recommendations_rows)

        if res.estimates_rows:
            counts["eps_symbols"] += 1
            if any(r["estimate_type"] == "REVENUE" for r in res.estimates_rows):
                counts["revenue_symbols"] += 1
        if res.targets_rows:
            counts["target_symbols"] += 1
        if res.recommendations_rows:
            counts["reco_symbols"] += 1

        if res.status == STATUS_OK:
            counts["symbols_ok"] += 1
        elif res.status == STATUS_EMPTY:
            counts["symbols_empty"] += 1
        else:
            counts["symbols_failed"] += 1
        counts["rate_limit"] += int(res.status == STATUS_RATE_LIMIT)
        counts["temporary_error"] += int(res.status == STATUS_TEMPORARY_ERROR)
        counts["schema_error"] += int(res.status == STATUS_PROVIDER_SCHEMA_CHANGED)
        counts["parse_error"] += int(res.status == STATUS_PARSE_ERROR)

        if i % log_every == 0 or i == len(universe):
            LOGGER.info("[%d/%d] ok=%d empty=%d failed=%d | est=%d tgt=%d rec=%d",
                        i, len(universe), counts["symbols_ok"], counts["symbols_empty"],
                        counts["symbols_failed"], counts["estimates"], counts["targets"],
                        counts["recommendations"])
        time.sleep(sleep_seconds)

    requested = len(universe)
    summary = {
        "run_id": run_id,
        "requested_symbols": requested,
        "successful_symbols": counts["symbols_ok"],
        "empty_symbols": counts["symbols_empty"],
        "failed_symbols": counts["symbols_failed"],
        "estimates_rows_inserted": counts["estimates"],
        "targets_rows_inserted": counts["targets"],
        "recommendations_rows_inserted": counts["recommendations"],
        "rate_limit_count": counts["rate_limit"],
        "temporary_error_count": counts["temporary_error"],
        "schema_error_count": counts["schema_error"],
        "parse_error_count": counts["parse_error"],
        "eps_coverage": round(counts["eps_symbols"] / requested, 4) if requested else 0.0,
        "revenue_coverage": round(counts["revenue_symbols"] / requested, 4) if requested else 0.0,
        "target_coverage": round(counts["target_symbols"] / requested, 4) if requested else 0.0,
        "recommendation_coverage": round(counts["reco_symbols"] / requested, 4) if requested else 0.0,
        "elapsed_seconds": round(time.monotonic() - _mono_start, 1),
        "status": "COMPLETED",
    }
    if write_db:
        repo.finish_collection_run(run_id, stats=summary, status="COMPLETED")
    LOGGER.info("run %s terminé en %.1fs : est=%d tgt=%d rec=%d | coverage eps=%.1f%% rev=%.1f%% tgt=%.1f%% rec=%.1f%%",
                run_id, summary["elapsed_seconds"], counts["estimates"], counts["targets"],
                counts["recommendations"], 100 * summary["eps_coverage"],
                100 * summary["revenue_coverage"], 100 * summary["target_coverage"],
                100 * summary["recommendation_coverage"])
    return summary
