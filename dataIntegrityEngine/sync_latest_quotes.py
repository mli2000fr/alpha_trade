from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

import requests

from common.utils import configure_root_logging
from database.cleaning_audits import record_quotes_audit_run
from database.selector_reference import list_symbols_for_source, normalize_symbol_source, upsert_quote_snapshots
from service.alpaca.clientAlpaca import fetch_historical_quotes, fetch_latest_quotes

LOGGER = logging.getLogger(__name__)
DEFAULT_BATCH_SIZE = 200
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
MARKET_TZ = ZoneInfo("America/New_York")

# Format Alpaca latest quote : RFC 3339 / ISO 8601 avec suffixe `Z` (UTC) et
# fraction de seconde jusqu'à 9 chiffres (nanosecondes). MySQL DATETIME(6) ne
# supporte que 6 chiffres et n'accepte ni le `T` ni le `Z` en chaîne brute,
# d'où l'erreur 1292 si on passe la string sans la convertir.
_FRACTION_RE = re.compile(r"\.(\d+)")


def _parse_alpaca_timestamp(value: object) -> datetime | None:
    """Convertit un timestamp Alpaca (string RFC 3339, datetime, None) en
    ``datetime`` Python timezone-naïf en UTC, compatible MySQL ``DATETIME(6)``.

    - ``None`` → ``None`` (le ON DUPLICATE KEY UPDATE laissera l'ancienne
      valeur si la colonne est nullable, ce qui est le cas ici).
    - ``datetime`` aware → converti en UTC puis dépouillé de tzinfo.
    - ``datetime`` naïf → renvoyé tel quel (supposé déjà UTC).
    - ``str`` ISO 8601 (ex ``2026-04-29T19:59:49.779850529Z``) → parsé en
      tronquant la fraction à 6 chiffres (microsecondes) avant
      ``datetime.fromisoformat``.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if not isinstance(value, str):
        # Type inattendu : on tente une conversion générique avant d'abandonner.
        value = str(value)

    cleaned = value.strip()
    # Normalise le suffixe de timezone : `Z` → `+00:00` (compris par fromisoformat).
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"

    # Tronque la fraction de seconde à 6 chiffres (microsecondes), MySQL ne
    # supporte pas plus, et `fromisoformat` < 3.13 plafonne aussi à 6.
    def _truncate_fraction(match: re.Match[str]) -> str:
        digits = match.group(1)[:6]
        return f".{digits}"

    cleaned = _FRACTION_RE.sub(_truncate_fraction, cleaned, count=1)

    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        LOGGER.warning("quote_timestamp invalide ignoré : %r", value)
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _market_date_from_timestamp(
    quote_timestamp: datetime | None,
    *,
    fallback_utc_now: datetime | None = None,
) -> date:
    """Retourne la date de marché NY associée à une quote Alpaca.

    ``quote_timestamp`` est stocké en UTC naïf pour compatibilité MySQL. On le
    ré-interprète donc comme UTC puis on le convertit en ``America/New_York``
    avant d'en extraire la date de session. Si le timestamp est absent, on
    replie sur ``fallback_utc_now`` (ou maintenant UTC) afin d'éviter un
    ``quote_date`` dépendant du fuseau local de la machine.
    """
    effective_utc = quote_timestamp or fallback_utc_now or _utc_now_naive()
    if effective_utc.tzinfo is None:
        effective_utc = effective_utc.replace(tzinfo=timezone.utc)
    else:
        effective_utc = effective_utc.astimezone(timezone.utc)
    return effective_utc.astimezone(MARKET_TZ).date()



def _build_run_id(prefix: str) -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _emit_run_summary(summary: dict[str, object]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def _compute_spread_bps(bid_price: float | None, ask_price: float | None) -> float | None:
    if bid_price is None or ask_price is None:
        return None
    if bid_price <= 0 or ask_price <= 0:
        return None
    mid = (bid_price + ask_price) / 2.0
    if mid <= 0:
        return None
    return ((ask_price - bid_price) / mid) * 10_000.0


def _to_optional_float(value: object) -> float | None:
    return float(cast(Any, value)) if value is not None else None


def _normalize_quote_window(
    from_date: date | None,
    to_date: date | None,
) -> tuple[date | None, date | None]:
    if from_date is None and to_date is None:
        return None, None
    resolved_end = to_date or from_date or _market_date_from_timestamp(None)
    resolved_start = from_date or resolved_end
    if resolved_start > resolved_end:
        raise ValueError("from_date doit être antérieure ou égale à to_date.")
    return resolved_start, resolved_end


def _build_quote_snapshot_row(
    symbol: str,
    quote: dict[str, object],
    *,
    fallback_utc_now: datetime,
) -> dict[str, object]:
    bid_price = _to_optional_float(quote.get("bp"))
    ask_price = _to_optional_float(quote.get("ap"))
    quote_timestamp = _parse_alpaca_timestamp(quote.get("t"))
    return {
        "symbol": symbol,
        "quote_date": _market_date_from_timestamp(quote_timestamp, fallback_utc_now=fallback_utc_now),
        "quote_timestamp": quote_timestamp,
        "bid_price": bid_price,
        "ask_price": ask_price,
        "bid_size": _to_optional_float(quote.get("bs")),
        "ask_size": _to_optional_float(quote.get("as")),
        "spread_bps": _compute_spread_bps(bid_price, ask_price),
    }


def _select_latest_quotes_by_day(
    symbol: str,
    quotes: list[dict[str, object]],
    *,
    from_date: date,
    to_date: date,
    fallback_utc_now: datetime,
) -> list[dict[str, object]]:
    selected_by_day: dict[date, tuple[datetime, dict[str, object]]] = {}
    for quote in quotes:
        row = _build_quote_snapshot_row(symbol, quote, fallback_utc_now=fallback_utc_now)
        quote_date = row["quote_date"]
        if not isinstance(quote_date, date) or quote_date < from_date or quote_date > to_date:
            continue
        quote_timestamp = row.get("quote_timestamp")
        sort_key: datetime = quote_timestamp if isinstance(quote_timestamp, datetime) else fallback_utc_now
        existing = selected_by_day.get(quote_date)
        if existing is None or sort_key >= existing[0]:
            selected_by_day[quote_date] = (sort_key, row)
    return [selected_by_day[day][1] for day in sorted(selected_by_day)]


def sync_latest_quotes(
    limit: int | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    symbol_source: str | None = None,
) -> dict[str, int]:
    if batch_size < 1:
        raise ValueError("batch_size doit être supérieur ou égal à 1.")

    resolved_from_date, resolved_to_date = _normalize_quote_window(from_date, to_date)

    resolved_symbol_source = normalize_symbol_source(symbol_source)
    symbols = list_symbols_for_source(resolved_symbol_source, limit=limit)
    summary = {"symbols": len(symbols), "rows_upserted": 0}
    if not symbols:
        return summary

    session = requests.Session()
    try:
        run_utc_now = _utc_now_naive()
        if resolved_from_date is None or resolved_to_date is None:
            for start in range(0, len(symbols), batch_size):
                batch = symbols[start:start + batch_size]
                payload = fetch_latest_quotes(batch, session=session)
                rows: list[dict[str, object]] = []
                for symbol in batch:
                    quote = payload.get(symbol)
                    if not quote:
                        continue
                    rows.append(_build_quote_snapshot_row(symbol, quote, fallback_utc_now=run_utc_now))
                summary["rows_upserted"] += upsert_quote_snapshots(rows)
                LOGGER.info(
                    "Sync latest quotes | mode=latest symbol_source=%s batch=%s-%s symbols=%s rows_upserted=%s",
                    resolved_symbol_source,
                    start + 1,
                    start + len(batch),
                    len(batch),
                    summary["rows_upserted"],
                )
        else:
            for index, symbol in enumerate(symbols, start=1):
                historical_quotes = fetch_historical_quotes(
                    symbol,
                    start=resolved_from_date.isoformat(),
                    end=resolved_to_date.isoformat(),
                    session=session,
                )
                rows = _select_latest_quotes_by_day(
                    symbol,
                    historical_quotes,
                    from_date=resolved_from_date,
                    to_date=resolved_to_date,
                    fallback_utc_now=run_utc_now,
                )
                summary["rows_upserted"] += upsert_quote_snapshots(rows)
                LOGGER.info(
                    "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s symbol=%s days_upserted=%s rows_upserted=%s from=%s to=%s",
                    resolved_symbol_source,
                    index,
                    len(symbols),
                    symbol,
                    len(rows),
                    summary["rows_upserted"],
                    resolved_from_date,
                    resolved_to_date,
                )
    finally:
        session.close()

    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronise les latest quotes Alpaca dans stock_quote_snapshots")
    parser.add_argument("--from-date", type=str, default=None, help="Date de début ISO (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, default=None, help="Date de fin ISO (YYYY-MM-DD)")
    parser.add_argument("--symbol-source", type=str, default=None, help="Univers de symboles (`active-tradable`, `stock-scores`, `stock-scores-history`, `stock-scores-all`, `candidates`, `stock-bars-daily`)")
    parser.add_argument("--limit", type=int, default=None, help="Nombre maximum de symboles")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Taille de batch pour l'appel latest quotes")
    return parser


def main() -> None:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/sync_latest_quotes.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    args = _build_arg_parser().parse_args()
    started_at = _utc_now_naive()
    run_id = _build_run_id("sync-latest-quotes")
    status: str = "success"
    error_message: str | None = None
    summary: dict[str, int]
    try:
        summary = sync_latest_quotes(
            limit=args.limit,
            batch_size=args.batch_size,
            from_date=date.fromisoformat(args.from_date) if args.from_date else None,
            to_date=date.fromisoformat(args.to_date) if args.to_date else None,
            symbol_source=args.symbol_source,
        )
    except Exception as exc:  # noqa: BLE001 — audit + propagation contrôlée.
        status = "failed"
        error_message = repr(exc)
        summary = {"symbols": 0, "rows_upserted": 0}
        finished_at = _utc_now_naive()
        # Phase 3.1.c — audit dédié quotes.
        record_quotes_audit_run(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            symbols_requested=int(summary.get("symbols", 0)),
            rows_upserted=int(summary.get("rows_upserted", 0)),
            status="failed",
            error_message=error_message,
        )
        raise
    finished_at = _utc_now_naive()
    # Phase 3.1.c — audit dédié quotes (best-effort).
    record_quotes_audit_run(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        symbols_requested=int(summary.get("symbols", 0)),
        rows_upserted=int(summary.get("rows_upserted", 0)),
        status="success",
        error_message=None,
    )
    _emit_run_summary(
        {
            "run_id": run_id,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
            "from_date": args.from_date,
            "to_date": args.to_date,
            "symbol_source": normalize_symbol_source(args.symbol_source),
            "requested_limit": args.limit,
            "batch_size": args.batch_size,
            "audit_status": status,
            **summary,
        }
    )


if __name__ == "__main__":
    main()

