from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

import requests

from common.market_calendar import get_nyse_session_bounds, nyse_session_dates
from common.utils import configure_root_logging
from database.cleaning_audits import record_quotes_audit_run
from database.selector_reference import (
    get_quote_snapshot_resume_state,
    list_symbols_for_source,
    normalize_symbol_source,
    normalize_start_symbol,
    upsert_quote_snapshots,
)
from service.alpaca.clientAlpaca import (
    fetch_latest_historical_quote_in_window,
    fetch_latest_quotes,
    iter_historical_quotes_pages,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_BATCH_SIZE = 200
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
MARKET_TZ = ZoneInfo("America/New_York")
HISTORICAL_CLOSE_PRIMARY_LOOKBACK_MINUTES = 10
HISTORICAL_CLOSE_FALLBACK_LOOKBACK_MINUTES = 45
HISTORICAL_CLOSE_PROGRESS_LOG_EVERY_DAYS = 10
HISTORICAL_BLOCK_PROGRESS_LOG_EVERY_PAGES = 10

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


def _to_iso_zulu(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _month_end(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1) - timedelta(days=1)
    return date(value.year, value.month + 1, 1) - timedelta(days=1)


def _iter_monthly_blocks(start: date, end: date) -> list[tuple[date, date]]:
    if end < start:
        return []
    blocks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        block_end = min(_month_end(cursor), end)
        blocks.append((cursor, block_end))
        cursor = block_end + timedelta(days=1)
    return blocks


def _iter_historical_close_windows(session_date: date) -> list[tuple[datetime, datetime]]:
    market_open_utc, market_close_utc = get_nyse_session_bounds(session_date)
    windows = [
        (
            max(market_open_utc, market_close_utc - timedelta(minutes=HISTORICAL_CLOSE_PRIMARY_LOOKBACK_MINUTES)),
            market_close_utc,
        ),
        (
            max(market_open_utc, market_close_utc - timedelta(minutes=HISTORICAL_CLOSE_FALLBACK_LOOKBACK_MINUTES)),
            market_close_utc,
        ),
        (market_open_utc, market_close_utc),
    ]
    deduped_windows: list[tuple[datetime, datetime]] = []
    seen: set[tuple[str, str]] = set()
    for window_start, window_end in windows:
        key = (_to_iso_zulu(window_start), _to_iso_zulu(window_end))
        if key in seen:
            continue
        seen.add(key)
        deduped_windows.append((window_start, window_end))
    return deduped_windows


def _fetch_near_close_quote_for_session(
    symbol: str,
    session_date: date,
    *,
    session: requests.Session,
) -> tuple[dict[str, object] | None, int | None, tuple[datetime, datetime] | None]:
    for window_index, (window_start, window_end) in enumerate(_iter_historical_close_windows(session_date), start=1):
        quote = fetch_latest_historical_quote_in_window(
            symbol,
            start=_to_iso_zulu(window_start),
            end=_to_iso_zulu(window_end),
            session=session,
        )
        if isinstance(quote, dict):
            return cast(dict[str, object], quote), window_index, (window_start, window_end)
    return None, None, None


def _range_has_any_quotes(
    symbol: str,
    session_dates: list[date],
    *,
    session: requests.Session,
) -> bool:
    if not session_dates:
        return False
    range_open_utc, _ = get_nyse_session_bounds(session_dates[0])
    _, range_close_utc = get_nyse_session_bounds(session_dates[-1])
    quote = fetch_latest_historical_quote_in_window(
        symbol,
        start=_to_iso_zulu(range_open_utc),
        end=_to_iso_zulu(range_close_utc),
        session=session,
    )
    return isinstance(quote, dict)


def _log_historical_symbol_summary(
    *,
    symbol_source: str,
    index: int,
    total_symbols: int,
    symbol: str,
    from_date: date,
    to_date: date,
    missing_ranges: int,
    missing_days: int,
    fetched_ranges: int,
    skipped_existing: bool,
) -> None:
    LOGGER.info(
        "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=symbol_summary missing_ranges=%s missing_days=%s fetched_ranges=%s skipped_existing=%s from=%s to=%s",
        symbol_source,
        index,
        total_symbols,
        (index / total_symbols) * 100.0,
        symbol,
        missing_ranges,
        missing_days,
        fetched_ranges,
        skipped_existing,
        from_date,
        to_date,
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


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(cast(Any, value))
    except (TypeError, ValueError):
        return default


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
    _merge_quotes_into_daily_selection(
        selected_by_day,
        symbol=symbol,
        quotes=quotes,
        from_date=from_date,
        to_date=to_date,
        fallback_utc_now=fallback_utc_now,
    )
    return [selected_by_day[day][1] for day in sorted(selected_by_day)]


def _merge_quotes_into_daily_selection(
    selected_by_day: dict[date, tuple[datetime, dict[str, object]]],
    *,
    symbol: str,
    quotes: list[dict[str, object]],
    from_date: date,
    to_date: date,
    fallback_utc_now: datetime,
    allowed_dates: set[date] | None = None,
) -> None:
    for quote in quotes:
        row = _build_quote_snapshot_row(symbol, quote, fallback_utc_now=fallback_utc_now)
        quote_date = row["quote_date"]
        if not isinstance(quote_date, date) or quote_date < from_date or quote_date > to_date:
            continue
        if allowed_dates is not None and quote_date not in allowed_dates:
            continue
        quote_timestamp = row.get("quote_timestamp")
        sort_key: datetime = quote_timestamp if isinstance(quote_timestamp, datetime) else fallback_utc_now
        existing = selected_by_day.get(quote_date)
        if existing is None or sort_key >= existing[0]:
            selected_by_day[quote_date] = (sort_key, row)


def sync_latest_quotes(
    limit: int | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    symbol_source: str | None = None,
    start_symbol: str | None = None,
) -> dict[str, int]:
    if batch_size < 1:
        raise ValueError("batch_size doit être supérieur ou égal à 1.")

    resolved_from_date, resolved_to_date = _normalize_quote_window(from_date, to_date)
    mode = "historical" if resolved_from_date is not None and resolved_to_date is not None else "latest"

    resolved_symbol_source = normalize_symbol_source(symbol_source)
    resolved_start_symbol = normalize_start_symbol(start_symbol)
    if resolved_start_symbol is not None:
        symbols = list_symbols_for_source(resolved_symbol_source, limit=limit, start_symbol=resolved_start_symbol)
    else:
        symbols = list_symbols_for_source(resolved_symbol_source, limit=limit)
    summary = {"symbols": len(symbols), "rows_upserted": 0}
    LOGGER.info(
        "Sync latest quotes start | mode=%s symbol_source=%s symbols=%s from=%s to=%s limit=%s batch_size=%s start_symbol=%s",
        mode,
        resolved_symbol_source,
        len(symbols),
        resolved_from_date,
        resolved_to_date,
        limit,
        batch_size,
        resolved_start_symbol,
    )
    if not symbols:
        LOGGER.warning(
            "Sync latest quotes skipped | aucun symbole résolu pour symbol_source=%s mode=%s start_symbol=%s.",
            resolved_symbol_source,
            mode,
            resolved_start_symbol,
        )
        return summary

    session = requests.Session()
    try:
        run_utc_now = _utc_now_naive()
        if resolved_from_date is None or resolved_to_date is None:
            total_batches = (len(symbols) + batch_size - 1) // batch_size
            for start in range(0, len(symbols), batch_size):
                batch = symbols[start:start + batch_size]
                payload = fetch_latest_quotes(batch, session=session)
                rows: list[dict[str, object]] = []
                for symbol in batch:
                    quote = payload.get(symbol)
                    if not quote:
                        continue
                    rows.append(_build_quote_snapshot_row(symbol, quote, fallback_utc_now=run_utc_now))
                batch_upserted = upsert_quote_snapshots(rows)
                summary["rows_upserted"] += batch_upserted
                batch_index = (start // batch_size) + 1
                LOGGER.info(
                    "Sync latest quotes | mode=latest symbol_source=%s batch=%s/%s range=%s-%s symbols=%s rows_in_batch=%s rows_upserted=%s",
                    resolved_symbol_source,
                    batch_index,
                    total_batches,
                    start + 1,
                    start + len(batch),
                    len(batch),
                    len(rows),
                    summary["rows_upserted"],
                )
        else:
            expected_quote_dates = tuple(nyse_session_dates(resolved_from_date, resolved_to_date))
            for index, symbol in enumerate(symbols, start=1):
                resume_state = get_quote_snapshot_resume_state(
                    symbol,
                    from_date=resolved_from_date,
                    to_date=resolved_to_date,
                    expected_dates=expected_quote_dates,
                )
                expected_days = _to_int(resume_state.get("expected_days", 0))
                stored_days = _to_int(resume_state.get("stored_days", 0))
                missing_days = _to_int(resume_state.get("missing_days", 0))
                first_missing_date = resume_state.get("first_missing_date")
                missing_ranges_raw = resume_state.get("missing_ranges", [])
                missing_ranges: list[tuple[date, date]] = []
                if isinstance(missing_ranges_raw, list):
                    for raw_range in missing_ranges_raw:
                        if not isinstance(raw_range, (list, tuple)) or len(raw_range) != 2:
                            continue
                        range_start, range_end = raw_range
                        if isinstance(range_start, date) and isinstance(range_end, date):
                            missing_ranges.append((range_start, range_end))
                if not bool(resume_state.get("has_expected_days", False)):
                    _log_historical_symbol_summary(
                        symbol_source=resolved_symbol_source,
                        index=index,
                        total_symbols=len(symbols),
                        symbol=symbol,
                        from_date=resolved_from_date,
                        to_date=resolved_to_date,
                        missing_ranges=0,
                        missing_days=0,
                        fetched_ranges=0,
                        skipped_existing=False,
                    )
                    LOGGER.info(
                        "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=skip_no_bars from=%s to=%s",
                        resolved_symbol_source,
                        index,
                        len(symbols),
                        (index / len(symbols)) * 100.0,
                        symbol,
                        resolved_from_date,
                        resolved_to_date,
                    )
                    continue
                if bool(resume_state.get("is_complete", False)):
                    _log_historical_symbol_summary(
                        symbol_source=resolved_symbol_source,
                        index=index,
                        total_symbols=len(symbols),
                        symbol=symbol,
                        from_date=resolved_from_date,
                        to_date=resolved_to_date,
                        missing_ranges=len(missing_ranges),
                        missing_days=missing_days,
                        fetched_ranges=0,
                        skipped_existing=True,
                    )
                    LOGGER.info(
                        "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=skip_existing expected_days=%s stored_days=%s from=%s to=%s",
                        resolved_symbol_source,
                        index,
                        len(symbols),
                        (index / len(symbols)) * 100.0,
                        symbol,
                        expected_days,
                        stored_days,
                        resolved_from_date,
                        resolved_to_date,
                    )
                    continue
                fetch_start_date = first_missing_date if isinstance(first_missing_date, date) else resolved_from_date
                LOGGER.info(
                    "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s symbol=%s stage=fetch_start from=%s to=%s fetch_from=%s expected_days=%s stored_days=%s missing_days=%s missing_ranges=%s",
                    resolved_symbol_source,
                    index,
                    len(symbols),
                    symbol,
                    resolved_from_date,
                    resolved_to_date,
                    fetch_start_date,
                    expected_days,
                    stored_days,
                    missing_days,
                    len(missing_ranges),
                )
                effective_missing_ranges: list[tuple[date, date]] = missing_ranges or [(fetch_start_date, resolved_to_date)]
                symbol_raw_quotes_scanned = 0
                symbol_rows_upserted = 0
                symbol_fetched_ranges = 0
                for range_index, (range_start, range_end) in enumerate(effective_missing_ranges, start=1):
                    LOGGER.info(
                        "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=fetch_range range=%s/%s range_start=%s range_end=%s",
                        resolved_symbol_source,
                        index,
                        len(symbols),
                        (index / len(symbols)) * 100.0,
                        symbol,
                        range_index,
                        len(effective_missing_ranges),
                        range_start,
                        range_end,
                    )
                    session_dates = nyse_session_dates(range_start, range_end)
                    if not session_dates:
                        LOGGER.info(
                            "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=skip_range_empty_calendar range=%s/%s range_start=%s range_end=%s",
                            resolved_symbol_source,
                            index,
                            len(symbols),
                            (index / len(symbols)) * 100.0,
                            symbol,
                            range_index,
                            len(effective_missing_ranges),
                            range_start,
                            range_end,
                        )
                        continue
                    if not _range_has_any_quotes(symbol, session_dates, session=session):
                        LOGGER.info(
                            "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=skip_range_no_quotes range=%s/%s range_start=%s range_end=%s sessions=%s total_rows_upserted=%s",
                            resolved_symbol_source,
                            index,
                            len(symbols),
                            (index / len(symbols)) * 100.0,
                            symbol,
                            range_index,
                            len(effective_missing_ranges),
                            range_start,
                            range_end,
                            len(session_dates),
                            summary["rows_upserted"],
                        )
                        continue
                    symbol_fetched_ranges += 1
                    monthly_blocks = _iter_monthly_blocks(range_start, range_end)
                    for block_index, (block_start, block_end) in enumerate(monthly_blocks, start=1):
                        block_session_dates = nyse_session_dates(block_start, block_end)
                        if not block_session_dates:
                            LOGGER.info(
                                "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=skip_block_empty_calendar range=%s/%s block=%s/%s block_start=%s block_end=%s",
                                resolved_symbol_source,
                                index,
                                len(symbols),
                                (index / len(symbols)) * 100.0,
                                symbol,
                                range_index,
                                len(effective_missing_ranges),
                                block_index,
                                len(monthly_blocks),
                                block_start,
                                block_end,
                            )
                            continue
                        block_open_utc, _ = get_nyse_session_bounds(block_session_dates[0])
                        _, block_close_utc = get_nyse_session_bounds(block_session_dates[-1])
                        LOGGER.info(
                            "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=fetch_block range=%s/%s block=%s/%s block_start=%s block_end=%s sessions=%s",
                            resolved_symbol_source,
                            index,
                            len(symbols),
                            (index / len(symbols)) * 100.0,
                            symbol,
                            range_index,
                            len(effective_missing_ranges),
                            block_index,
                            len(monthly_blocks),
                            block_start,
                            block_end,
                            len(block_session_dates),
                        )
                        selected_by_day: dict[date, tuple[datetime, dict[str, object]]] = {}
                        block_pages = 0
                        block_raw_quotes_scanned = 0
                        allowed_dates = set(block_session_dates)
                        for page in iter_historical_quotes_pages(
                            symbol,
                            start=_to_iso_zulu(block_open_utc),
                            end=_to_iso_zulu(block_close_utc),
                            session=session,
                        ):
                            page_quotes = [
                                quote for quote in cast(list[object], page.get("quotes") or []) if isinstance(quote, dict)
                            ]
                            block_pages += 1
                            block_raw_quotes_scanned += len(page_quotes)
                            _merge_quotes_into_daily_selection(
                                selected_by_day,
                                symbol=symbol,
                                quotes=cast(list[dict[str, object]], page_quotes),
                                from_date=block_start,
                                to_date=block_end,
                                fallback_utc_now=run_utc_now,
                                allowed_dates=allowed_dates,
                            )
                            has_next = bool(page.get("has_next", False))
                            if (
                                block_pages == 1
                                or not has_next
                                or block_pages % HISTORICAL_BLOCK_PROGRESS_LOG_EVERY_PAGES == 0
                            ):
                                covered_to = max(selected_by_day) if selected_by_day else None
                                LOGGER.info(
                                    "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=block_progress range=%s/%s block=%s/%s page=%s selected_days=%s covered_to=%s raw_quotes_scanned=%s total_rows_upserted=%s",
                                    resolved_symbol_source,
                                    index,
                                    len(symbols),
                                    (index / len(symbols)) * 100.0,
                                    symbol,
                                    range_index,
                                    len(effective_missing_ranges),
                                    block_index,
                                    len(monthly_blocks),
                                    block_pages,
                                    len(selected_by_day),
                                    covered_to,
                                    block_raw_quotes_scanned,
                                    summary["rows_upserted"],
                                )

                        rows = [selected_by_day[day][1] for day in sorted(selected_by_day)]
                        symbol_raw_quotes_scanned += block_raw_quotes_scanned
                        if not rows:
                            LOGGER.info(
                                "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=block_empty_result range=%s/%s block=%s/%s block_start=%s block_end=%s raw_quotes_scanned=%s total_rows_upserted=%s",
                                resolved_symbol_source,
                                index,
                                len(symbols),
                                (index / len(symbols)) * 100.0,
                                symbol,
                                range_index,
                                len(effective_missing_ranges),
                                block_index,
                                len(monthly_blocks),
                                block_start,
                                block_end,
                                block_raw_quotes_scanned,
                                summary["rows_upserted"],
                            )
                            continue

                        batch_upserted = upsert_quote_snapshots(rows)
                        symbol_rows_upserted += batch_upserted
                        summary["rows_upserted"] += batch_upserted
                        covered_to = rows[-1].get("quote_date") if isinstance(rows[-1].get("quote_date"), date) else block_end
                        LOGGER.info(
                            "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=block_persist range=%s/%s block=%s/%s block_start=%s block_end=%s selected_days=%s covered_to=%s block_rows_upserted=%s symbol_rows_upserted=%s total_rows_upserted=%s raw_quotes_scanned=%s",
                            resolved_symbol_source,
                            index,
                            len(symbols),
                            (index / len(symbols)) * 100.0,
                            symbol,
                            range_index,
                            len(effective_missing_ranges),
                            block_index,
                            len(monthly_blocks),
                            block_start,
                            block_end,
                            len(rows),
                            covered_to,
                            batch_upserted,
                            symbol_rows_upserted,
                            summary["rows_upserted"],
                            block_raw_quotes_scanned,
                        )
                _log_historical_symbol_summary(
                    symbol_source=resolved_symbol_source,
                    index=index,
                    total_symbols=len(symbols),
                    symbol=symbol,
                    from_date=resolved_from_date,
                    to_date=resolved_to_date,
                    missing_ranges=len(effective_missing_ranges),
                    missing_days=missing_days,
                    fetched_ranges=symbol_fetched_ranges,
                    skipped_existing=False,
                )
                LOGGER.info(
                    "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s raw_quotes_scanned=%s days_selected=%s rows_upserted=%s from=%s to=%s",
                    resolved_symbol_source,
                    index,
                    len(symbols),
                    (index / len(symbols)) * 100.0,
                    symbol,
                    symbol_raw_quotes_scanned,
                    symbol_rows_upserted,
                    summary["rows_upserted"],
                    resolved_from_date,
                    resolved_to_date,
                )
    finally:
        session.close()

    LOGGER.info(
        "Sync latest quotes completed | mode=%s symbol_source=%s symbols=%s rows_upserted=%s from=%s to=%s start_symbol=%s",
        mode,
        resolved_symbol_source,
        len(symbols),
        summary["rows_upserted"],
        resolved_from_date,
        resolved_to_date,
        resolved_start_symbol,
    )
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronise les latest quotes Alpaca dans stock_quote_snapshots")
    parser.add_argument("--from-date", type=str, default=None, help="Date de début ISO (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, default=None, help="Date de fin ISO (YYYY-MM-DD)")
    parser.add_argument("--symbol-source", type=str, default=None, help="Univers de symboles (`active-tradable`, `stock-scores`, `stock-scores-history`, `stock-scores-all`, `candidates`, `stock-bars-daily`)")
    parser.add_argument("--start-symbol", type=str, default=None, help="Symbole optionnel à partir duquel commencer (les symboles alphabétiquement avant sont sautés)")
    parser.add_argument("--limit", type=int, default=None, help="Nombre maximum de symboles")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Taille de batch pour l'appel latest quotes")
    return parser


def main() -> None:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/sync_latest_quotes.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
        use_timed_rotation=True,
        timed_rotation_backup_count=14,
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
            start_symbol=args.start_symbol,
        )
    except KeyboardInterrupt as exc:
        status = "failed"
        error_message = "KeyboardInterrupt()"
        summary = {"symbols": 0, "rows_upserted": 0}
        finished_at = _utc_now_naive()
        LOGGER.warning("Sync latest quotes interrompu par l'utilisateur | run_id=%s", run_id)
        record_quotes_audit_run(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            symbols_requested=int(summary.get("symbols", 0)),
            rows_upserted=int(summary.get("rows_upserted", 0)),
            status="failed",
            error_message=error_message,
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
                "start_symbol": normalize_start_symbol(args.start_symbol),
                "requested_limit": args.limit,
                "batch_size": args.batch_size,
                "audit_status": status,
                "error_message": error_message,
                **summary,
            }
        )
        raise exc
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
            "start_symbol": normalize_start_symbol(args.start_symbol),
            "requested_limit": args.limit,
            "batch_size": args.batch_size,
            "audit_status": status,
            **summary,
        }
    )


if __name__ == "__main__":
    main()

