from __future__ import annotations

import argparse
import itertools
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import bindparam, text

from common.market_calendar import get_nyse_session_bounds, nyse_session_dates
from common.utils import configure_root_logging
from database.cleaning_audits import record_quotes_audit_run
from database.connection import get_sqlalchemy_engine
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
)
from service.yahoo.clientYahooFinance import (
    fetch_latest_quotes_yahoo,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_BATCH_SIZE = 200
DEFAULT_QUOTES_PROVIDER_LIVE = "yahoo"
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
MARKET_TZ = ZoneInfo("America/New_York")
QUOTE_IEX_BIAS_PROXY_NAME = "same_session_mid_vs_stock_bars_daily_close"
HISTORICAL_CLOSE_PROGRESS_LOG_EVERY_DAYS = 10
HISTORICAL_UPSERT_BATCH_ROWS = 50

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


def _iter_year_blocks(start: date, end: date) -> list[tuple[date, date]]:
    """Découpe ``[start, end]`` en blocs annuels (ex: 2020-06 → 2020-12, 2021, 2022, 2023-01→2023-04)."""
    if end < start:
        return []
    blocks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        year_end = min(date(cursor.year, 12, 31), end)
        blocks.append((cursor, year_end))
        cursor = year_end + timedelta(days=1)
    return blocks


def _session_window(session_date: date) -> list[tuple[datetime, datetime]]:
    """Retourne une unique fenêtre couvrant la session NYSE entière.
    Avec ``limit=1&sort=desc`` côté Alpaca, cela donne la quote la plus
    tardive de la journée — exactement ce dont on a besoin."""
    market_open_utc, market_close_utc = get_nyse_session_bounds(session_date)
    return [(market_open_utc, market_close_utc)]


def _resolve_account_cycler() -> itertools.cycle[str] | None:
    """Retourne un itérateur cyclique sur les ``account_id`` Alpaca configurés,
    ou ``None`` si un seul compte (ou aucun) est disponible."""
    try:
        from service.alpaca.accounts import AccountRegistry

        account_ids = AccountRegistry.get().list_account_ids()
    except Exception:
        account_ids = []
    if len(account_ids) <= 1:
        return None
    LOGGER.info("Rotation multi-comptes Alpaca activee | comptes=%s", account_ids)
    return itertools.cycle(account_ids)


def _bump_account(account_cycler: itertools.cycle[str] | None) -> str | None:
    """Retourne le prochain ``account_id`` ou ``None`` si pas de rotation."""
    if account_cycler is None:
        return None
    return next(account_cycler)


def _resolve_latest_quotes_fetcher() -> tuple[
    object,  # primary fetcher callable
    str,     # primary provider name
    object | None,  # secondary fetcher callable (or None)
]:
    """Résout le(s) provider(s) de quotes live depuis ``config.yaml``.

    - ``market_data.quotes_provider_live`` (défaut ``"yahoo"``)
    - ``market_data.quotes_provider_live_second`` (optionnel)

    Returns ``(primary_fn, primary_name, secondary_fn)``.
    """
    try:
        from common.config_loader import load_config

        cfg = load_config() or {}
    except Exception:
        cfg = {}
    market_cfg = cfg.get("market_data") or {}
    if not isinstance(market_cfg, dict):
        market_cfg = {}

    provider_map: dict[str, object] = {
        "alpaca": fetch_latest_quotes,
        "yahoo": fetch_latest_quotes_yahoo,
    }

    primary_name = str(
        market_cfg.get("quotes_provider_live") or DEFAULT_QUOTES_PROVIDER_LIVE
    ).strip().lower()
    primary_fn = provider_map.get(primary_name)
    if primary_fn is None:
        LOGGER.warning(
            "quotes_provider_live='%s' inconnu — fallback sur '%s'.",
            primary_name,
            DEFAULT_QUOTES_PROVIDER_LIVE,
        )
        primary_name = DEFAULT_QUOTES_PROVIDER_LIVE
        primary_fn = provider_map[primary_name]

    secondary_raw = market_cfg.get("quotes_provider_live_second")
    secondary_name = str(secondary_raw or "").strip().lower()
    secondary_fn = provider_map.get(secondary_name) if secondary_name else None

    if secondary_fn is not None:
        LOGGER.info(
            "Quotes provider live | primary=%s secondary=%s",
            primary_name,
            secondary_name,
        )
    else:
        LOGGER.info("Quotes provider live | primary=%s", primary_name)

    return primary_fn, primary_name, secondary_fn


def _symbol_has_any_quotes_in_window(
    symbol: str,
    from_date: date,
    to_date: date,
    *,
    session: requests.Session,
    account_id: str | None = None,
) -> bool:
    """Vérifie en 1 seul appel API si le symbole a au moins une quote
    dans la fenêtre [from_date, to_date]. Évite le traitement jour par jour
    coûteux pour les symboles sans couverture IEX."""
    range_open_utc, _ = get_nyse_session_bounds(from_date)
    _, range_close_utc = get_nyse_session_bounds(to_date)
    quote = fetch_latest_historical_quote_in_window(
        symbol,
        start=_to_iso_zulu(range_open_utc),
        end=_to_iso_zulu(range_close_utc),
        session=session,
        account_id=account_id,
    )
    return isinstance(quote, dict)


def _fetch_near_close_quote_for_session(
    symbol: str,
    session_date: date,
    *,
    session: requests.Session,
    account_id: str | None = None,
) -> tuple[dict[str, object] | None, int | None, tuple[datetime, datetime] | None]:
    for window_index, (window_start, window_end) in enumerate(_session_window(session_date), start=1):
        quote = fetch_latest_historical_quote_in_window(
            symbol,
            start=_to_iso_zulu(window_start),
            end=_to_iso_zulu(window_end),
            session=session,
            account_id=account_id,
        )
        if isinstance(quote, dict):
            return cast(dict[str, object], quote), window_index, (window_start, window_end)
    return None, None, None


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


def _coerce_sql_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


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


def _iter_symbol_batches(symbols: list[str], *, batch_size: int = 500) -> list[list[str]]:
    if batch_size < 1:
        raise ValueError("batch_size doit être supérieur ou égal à 1.")
    return [symbols[index:index + batch_size] for index in range(0, len(symbols), batch_size)]


def _resolve_quote_bias_window(
    from_date: date | None,
    to_date: date | None,
) -> tuple[date, date, str]:
    resolved_from_date, resolved_to_date = _normalize_quote_window(from_date, to_date)
    if resolved_from_date is None or resolved_to_date is None:
        market_date = _market_date_from_timestamp(None)
        return market_date, market_date, "latest"
    return resolved_from_date, resolved_to_date, "historical"


def _load_quote_rows_for_bias(
    *,
    symbols: list[str],
    from_date: date,
    to_date: date,
) -> list[dict[str, object]]:
    if not symbols:
        return []
    stmt = text(
        """
        SELECT symbol, quote_date, bid_price, ask_price
        FROM stock_quote_snapshots
        WHERE symbol IN :symbols
          AND quote_date BETWEEN :from_date AND :to_date
        """
    ).bindparams(bindparam("symbols", expanding=True))
    try:
        with get_sqlalchemy_engine().connect() as conn:
            rows = conn.execute(
                stmt,
                {"symbols": symbols, "from_date": from_date, "to_date": to_date},
            ).mappings().all()
    except Exception:
        LOGGER.debug("Proxy quote bias IEX : lecture stock_quote_snapshots indisponible.", exc_info=True)
        return []
    return [{str(key): value for key, value in row.items()} for row in rows]


def _load_consolidated_close_map(
    *,
    symbols: list[str],
    from_date: date,
    to_date: date,
) -> dict[tuple[str, date], float]:
    if not symbols:
        return {}
    stmt = text(
        """
        SELECT symbol, date, close
        FROM stock_bars_daily
        WHERE symbol IN :symbols
          AND date BETWEEN :from_date AND :to_date
        """
    ).bindparams(bindparam("symbols", expanding=True))
    try:
        with get_sqlalchemy_engine().connect() as conn:
            rows = conn.execute(
                stmt,
                {"symbols": symbols, "from_date": from_date, "to_date": to_date},
            ).mappings().all()
    except Exception:
        LOGGER.debug("Proxy quote bias IEX : lecture stock_bars_daily indisponible.", exc_info=True)
        return {}
    close_map: dict[tuple[str, date], float] = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        close_date = _coerce_sql_date(row.get("date"))
        close_value = _to_optional_float(row.get("close"))
        if not symbol or close_date is None or close_value is None or close_value <= 0:
            continue
        close_map[(symbol, close_date)] = close_value
    return close_map


def _build_quote_bias_summary_from_rows(
    quote_rows: list[dict[str, object]],
    consolidated_close_map: dict[tuple[str, date], float],
) -> dict[str, object]:
    proxy_name = QUOTE_IEX_BIAS_PROXY_NAME
    two_sided_quotes = 0
    matched = 0
    missing_close = 0
    sum_abs_bps = 0.0
    sum_signed_bps = 0.0
    max_abs_bps = 0.0
    max_abs_symbol = ""
    max_abs_date: date | None = None

    for row in quote_rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        quote_date = _coerce_sql_date(row.get("quote_date"))
        bid_price = _to_optional_float(row.get("bid_price"))
        ask_price = _to_optional_float(row.get("ask_price"))
        if not symbol or quote_date is None:
            continue
        mid_price = None
        if bid_price is not None and ask_price is not None and bid_price > 0 and ask_price > 0:
            mid_price = (bid_price + ask_price) / 2.0
        if mid_price is None or mid_price <= 0:
            continue
        two_sided_quotes += 1
        consolidated_close = consolidated_close_map.get((symbol, quote_date))
        if consolidated_close is None or consolidated_close <= 0:
            missing_close += 1
            continue
        signed_bps = ((mid_price - consolidated_close) / consolidated_close) * 10_000.0
        abs_bps = abs(signed_bps)
        matched += 1
        sum_abs_bps += abs_bps
        sum_signed_bps += signed_bps
        if abs_bps >= max_abs_bps:
            max_abs_bps = abs_bps
            max_abs_symbol = symbol
            max_abs_date = quote_date

    if matched <= 0:
        return {
            "quote_iex_vs_consolidated_status": "unavailable",
            "quote_iex_vs_consolidated_proxy": proxy_name,
            "quote_iex_vs_consolidated_observations": 0,
            "quote_iex_vs_consolidated_candidates": int(two_sided_quotes),
            "quote_iex_vs_consolidated_missing_closes": int(missing_close),
        }

    return {
        "quote_iex_vs_consolidated_status": "ok",
        "quote_iex_vs_consolidated_proxy": proxy_name,
        "quote_iex_vs_consolidated_observations": int(matched),
        "quote_iex_vs_consolidated_candidates": int(two_sided_quotes),
        "quote_iex_vs_consolidated_missing_closes": int(missing_close),
        "quote_iex_vs_consolidated_bps": round(sum_abs_bps / matched, 2),
        "quote_iex_vs_consolidated_signed_bps": round(sum_signed_bps / matched, 2),
        "max_quote_iex_vs_consolidated_bps": round(max_abs_bps, 2),
        "max_quote_iex_vs_consolidated_symbol": max_abs_symbol,
        "max_quote_iex_vs_consolidated_date": max_abs_date.isoformat() if max_abs_date is not None else None,
    }


def build_quote_iex_vs_consolidated_bias_summary(
    *,
    from_date: date | None,
    to_date: date | None,
    symbol_source: str | None,
    limit: int | None,
    start_symbol: str | None,
) -> dict[str, object]:
    normalized_source = normalize_symbol_source(symbol_source)
    normalized_start_symbol = normalize_start_symbol(start_symbol)
    window_start, window_end, mode = _resolve_quote_bias_window(from_date, to_date)
    try:
        symbols = list_symbols_for_source(
            normalized_source,
            limit=limit,
            start_symbol=normalized_start_symbol,
        )
    except Exception:
        LOGGER.debug("Proxy quote bias IEX : impossible de résoudre l'univers symbole.", exc_info=True)
        return {
            "quote_iex_vs_consolidated_status": "unavailable",
            "quote_iex_vs_consolidated_proxy": "same_session_mid_vs_stock_bars_daily_close",
            "quote_iex_vs_consolidated_observations": 0,
            "quote_iex_vs_consolidated_window_mode": mode,
            "quote_iex_vs_consolidated_window_start": window_start.isoformat(),
            "quote_iex_vs_consolidated_window_end": window_end.isoformat(),
        }
    aggregated_quote_rows: list[dict[str, object]] = []
    consolidated_close_map: dict[tuple[str, date], float] = {}
    for batch in _iter_symbol_batches(symbols):
        aggregated_quote_rows.extend(
            _load_quote_rows_for_bias(symbols=batch, from_date=window_start, to_date=window_end)
        )
        consolidated_close_map.update(
            _load_consolidated_close_map(symbols=batch, from_date=window_start, to_date=window_end)
        )
    payload = _build_quote_bias_summary_from_rows(aggregated_quote_rows, consolidated_close_map)
    payload["quote_iex_vs_consolidated_window_mode"] = mode
    payload["quote_iex_vs_consolidated_window_start"] = window_start.isoformat()
    payload["quote_iex_vs_consolidated_window_end"] = window_end.isoformat()
    payload["quote_iex_vs_consolidated_symbol_scope"] = normalized_source
    payload["quote_iex_vs_consolidated_symbols_requested"] = int(len(symbols))
    return payload


def safe_build_quote_iex_vs_consolidated_bias_summary(
    *,
    from_date: date | None,
    to_date: date | None,
    symbol_source: str | None,
    limit: int | None,
    start_symbol: str | None,
) -> dict[str, object]:
    normalized_source = normalize_symbol_source(symbol_source)
    window_start, window_end, mode = _resolve_quote_bias_window(from_date, to_date)
    try:
        return build_quote_iex_vs_consolidated_bias_summary(
            from_date=from_date,
            to_date=to_date,
            symbol_source=symbol_source,
            limit=limit,
            start_symbol=start_symbol,
        )
    except Exception:
        LOGGER.warning(
            "Proxy quote bias IEX indisponible pendant l'émission du run summary.",
            exc_info=True,
        )
        return {
            "quote_iex_vs_consolidated_status": "unavailable",
            "quote_iex_vs_consolidated_proxy": QUOTE_IEX_BIAS_PROXY_NAME,
            "quote_iex_vs_consolidated_observations": 0,
            "quote_iex_vs_consolidated_window_mode": mode,
            "quote_iex_vs_consolidated_window_start": window_start.isoformat(),
            "quote_iex_vs_consolidated_window_end": window_end.isoformat(),
            "quote_iex_vs_consolidated_symbol_scope": normalized_source,
            "quote_iex_vs_consolidated_symbols_requested": 0,
        }


def estimate_sync_latest_quotes_cost(
    *,
    symbol_count: int,
    batch_size: int = DEFAULT_BATCH_SIZE,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict[str, object]:
    """Estime grossièrement la charge d'un run quotes pour l'IHM opérateur.

    L'objectif n'est pas d'être exact à la requête près, mais de donner un
    ordre de grandeur fiable pour distinguer un petit run latest d'un rattrapage
    historique potentiellement coûteux.
    """
    if symbol_count < 0:
        raise ValueError("symbol_count doit être >= 0.")
    if batch_size < 1:
        raise ValueError("batch_size doit être >= 1.")

    resolved_from_date, resolved_to_date = _normalize_quote_window(from_date, to_date)
    latest_mode = resolved_from_date is None or resolved_to_date is None
    if latest_mode:
        batch_count = (symbol_count + batch_size - 1) // batch_size if symbol_count > 0 else 0
        estimated_api_calls = batch_count
        estimated_duration_seconds = round(batch_count * 0.35, 2)
        severity = "low" if batch_count <= 5 else "medium" if batch_count <= 20 else "high"
        return {
            "mode": "latest",
            "symbol_count": int(symbol_count),
            "batch_size": int(batch_size),
            "estimated_batch_count": int(batch_count),
            "estimated_api_calls": int(estimated_api_calls),
            "estimated_duration_seconds": float(estimated_duration_seconds),
            "estimated_duration_minutes": round(estimated_duration_seconds / 60.0, 2),
            "trading_days": 0,
            "monthly_blocks": 0,
            "symbol_days": 0,
            "warning_required": severity == "high",
            "severity": severity,
        }

    if resolved_from_date is None or resolved_to_date is None:
        raise RuntimeError("Fenêtre quotes historique non résolue.")

    trading_days = len(nyse_session_dates(resolved_from_date, resolved_to_date))
    symbol_days = int(symbol_count * trading_days)
    # 1 appel API par jour manquant + 1 quick-check par plage (estimé ~1 plage/symbole)
    estimated_api_calls = int(symbol_days + symbol_count)
    estimated_duration_seconds = round(estimated_api_calls * 0.40, 2)
    severity = "low"
    if symbol_days >= 15_000 or estimated_api_calls >= 800:
        severity = "high"
    elif symbol_days >= 4_000 or estimated_api_calls >= 250:
        severity = "medium"
    return {
        "mode": "historical",
        "symbol_count": int(symbol_count),
        "batch_size": int(batch_size),
        "from_date": resolved_from_date.isoformat(),
        "to_date": resolved_to_date.isoformat(),
        "trading_days": int(trading_days),
        "symbol_days": int(symbol_days),
        "estimated_api_calls": int(estimated_api_calls),
        "estimated_duration_seconds": float(estimated_duration_seconds),
        "estimated_duration_minutes": round(estimated_duration_seconds / 60.0, 2),
        "warning_required": severity == "high",
        "severity": severity,
    }


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
    account_cycler = _resolve_account_cycler()
    # Résolution du/des provider(s) live (mode latest uniquement)
    primary_fn, primary_name, secondary_fn = _resolve_latest_quotes_fetcher()
    try:
        run_utc_now = _utc_now_naive()
        if resolved_from_date is None or resolved_to_date is None:
            total_batches = (len(symbols) + batch_size - 1) // batch_size
            for start in range(0, len(symbols), batch_size):
                batch = symbols[start:start + batch_size]

                # ── Provider principal ──
                used_provider = primary_name
                try:
                    payload = primary_fn(batch, session=session, account_id=_bump_account(account_cycler))
                except Exception:
                    LOGGER.warning(
                        "Quotes provider primary='%s' a echoue — tentative fallback",
                        primary_name,
                        exc_info=True,
                    )
                    payload = {}

                # ── Fallback secondaire si aucune donnée ──
                if not payload and secondary_fn is not None:
                    try:
                        payload = secondary_fn(batch, session=session, account_id=_bump_account(account_cycler))
                        used_provider = f"{primary_name}→fallback"
                    except Exception:
                        LOGGER.warning(
                            "Quotes provider secondary a egalement echoue",
                            exc_info=True,
                        )
                        payload = {}

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
                    "Sync latest quotes | mode=latest symbol_source=%s batch=%s/%s range=%s-%s symbols=%s rows_in_batch=%s rows_upserted=%s provider=%s",
                    resolved_symbol_source,
                    batch_index,
                    total_batches,
                    start + 1,
                    start + len(batch),
                    len(batch),
                    len(rows),
                    summary["rows_upserted"],
                    used_provider,
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

                # ── Pre-check annuel : 1 appel API par année avec jours manquants ──
                all_years = list(range(resolved_from_date.year, resolved_to_date.year + 1))
                years_with_quotes: set[int] = set()
                years_checked = 0
                for check_year in all_years:
                    year_start = date(check_year, 1, 1)
                    year_end = date(check_year, 12, 31)
                    year_missing_days = sum(
                        len(nyse_session_dates(max(r_start, year_start), min(r_end, year_end)))
                        for r_start, r_end in missing_ranges
                        if max(r_start, year_start) <= min(r_end, year_end)
                    )
                    if year_missing_days == 0:
                        LOGGER.info(
                            "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=skip_year_already_stored year=%s total_rows_upserted=%s",
                            resolved_symbol_source,
                            index,
                            len(symbols),
                            (index / len(symbols)) * 100.0,
                            symbol,
                            check_year,
                            summary["rows_upserted"],
                        )
                        continue

                    years_checked += 1
                    if _symbol_has_any_quotes_in_window(
                        symbol,
                        year_start,
                        year_end,
                        session=session,
                        account_id=_bump_account(account_cycler),
                    ):
                        years_with_quotes.add(check_year)
                    else:
                        year_open_utc, _ = get_nyse_session_bounds(year_start)
                        _, year_close_utc = get_nyse_session_bounds(year_end)
                        LOGGER.info(
                            "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=skip_year_no_quotes_iex year=%s window_utc=%s..%s missing_days=%s total_rows_upserted=%s",
                            resolved_symbol_source,
                            index,
                            len(symbols),
                            (index / len(symbols)) * 100.0,
                            symbol,
                            check_year,
                            _to_iso_zulu(year_open_utc),
                            _to_iso_zulu(year_close_utc),
                            year_missing_days,
                            summary["rows_upserted"],
                        )

                if not years_with_quotes:
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
                        skipped_existing=False,
                    )
                    LOGGER.info(
                        "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s api_calls=%s days_fetched=0 ranges_fetched=0 rows_upserted=%s from=%s to=%s",
                        resolved_symbol_source,
                        index,
                        len(symbols),
                        (index / len(symbols)) * 100.0,
                        symbol,
                        years_checked,
                        summary["rows_upserted"],
                        resolved_from_date,
                        resolved_to_date,
                    )
                    continue

                # ── Traitement des plages uniquement dans les années avec quotes ──
                symbol_api_calls = years_checked
                symbol_fetched_days = 0
                symbol_rows: list[dict[str, object]] = []
                symbol_fetched_ranges = 0

                for range_index, (range_start, range_end) in enumerate(missing_ranges, start=1):
                    # ── Découpe les plages multi-années en blocs annuels ──
                    for block_start, block_end in _iter_year_blocks(range_start, range_end):
                        if block_start.year not in years_with_quotes:
                            continue

                        block_session_dates = nyse_session_dates(block_start, block_end)
                        if not block_session_dates:
                            continue

                        symbol_fetched_ranges += 1
                        last_progress_log = 0
                        LOGGER.info(
                            "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=fetch_range range=%s/%s block=%s-%s sessions=%s",
                            resolved_symbol_source,
                            index,
                            len(symbols),
                            (index / len(symbols)) * 100.0,
                            symbol,
                            range_index,
                            len(missing_ranges),
                            block_start,
                            block_end,
                            len(block_session_dates),
                        )

                        for day_index, session_date in enumerate(block_session_dates, start=1):
                            quote, window_index, window_used = _fetch_near_close_quote_for_session(
                                symbol,
                                session_date,
                                session=session,
                                account_id=_bump_account(account_cycler),
                            )
                            symbol_api_calls += 1
                            if quote is not None:
                                row = _build_quote_snapshot_row(symbol, quote, fallback_utc_now=run_utc_now)
                                row["quote_date"] = session_date
                                symbol_rows.append(row)
                                symbol_fetched_days += 1

                            # ── UPSERT incremental tous les N rows ──
                            if len(symbol_rows) >= HISTORICAL_UPSERT_BATCH_ROWS:
                                batch_upserted = upsert_quote_snapshots(symbol_rows)
                                summary["rows_upserted"] += batch_upserted
                                symbol_rows.clear()

                            if (
                                day_index == 1
                                or day_index == len(block_session_dates)
                                or day_index - last_progress_log >= HISTORICAL_CLOSE_PROGRESS_LOG_EVERY_DAYS
                            ):
                                last_progress_log = day_index
                                LOGGER.info(
                                    "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s stage=day_progress range=%s/%s day=%s/%s session=%s fetched=%s api_calls=%s total_rows_upserted=%s",
                                    resolved_symbol_source,
                                    index,
                                    len(symbols),
                                    (index / len(symbols)) * 100.0,
                                    symbol,
                                    range_index,
                                    len(missing_ranges),
                                    day_index,
                                    len(block_session_dates),
                                    session_date,
                                    symbol_fetched_days,
                                    symbol_api_calls,
                                    summary["rows_upserted"],
                                )

                # ── Flush des rows restantes (< HISTORICAL_UPSERT_BATCH_ROWS) ──
                if symbol_rows:
                    batch_upserted = upsert_quote_snapshots(symbol_rows)
                    summary["rows_upserted"] += batch_upserted
                    symbol_rows.clear()

                _log_historical_symbol_summary(
                    symbol_source=resolved_symbol_source,
                    index=index,
                    total_symbols=len(symbols),
                    symbol=symbol,
                    from_date=resolved_from_date,
                    to_date=resolved_to_date,
                    missing_ranges=len(missing_ranges),
                    missing_days=missing_days,
                    fetched_ranges=symbol_fetched_ranges,
                    skipped_existing=False,
                )
                LOGGER.info(
                    "Sync latest quotes | mode=historical symbol_source=%s progress=%s/%s pct=%.2f symbol=%s api_calls=%s days_fetched=%s ranges_fetched=%s rows_upserted=%s from=%s to=%s",
                    resolved_symbol_source,
                    index,
                    len(symbols),
                    (index / len(symbols)) * 100.0,
                    symbol,
                    symbol_api_calls,
                    symbol_fetched_days,
                    symbol_fetched_ranges,
                    symbol_fetched_days,
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
    parser.add_argument("--symbol-source", type=str, default=None, help="Univers de symboles (`active-tradable`, `stock-scores`, `stock-scores-history`, `stock-scores-all`, `stock-bars-daily`)")
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
    resolved_start_symbol = normalize_start_symbol(getattr(args, "start_symbol", None))
    started_at = _utc_now_naive()
    run_id = _build_run_id("sync-latest-quotes")
    status: str = "success"
    error_message: str | None = None
    summary: dict[str, int]
    resolved_from_date = date.fromisoformat(args.from_date) if args.from_date else None
    resolved_to_date = date.fromisoformat(args.to_date) if args.to_date else None
    try:
        sync_kwargs: dict[str, object] = {
            "limit": args.limit,
            "batch_size": args.batch_size,
            "from_date": resolved_from_date,
            "to_date": resolved_to_date,
            "symbol_source": args.symbol_source,
        }
        if resolved_start_symbol:
            sync_kwargs["start_symbol"] = resolved_start_symbol
        summary = sync_latest_quotes(
            **sync_kwargs,
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
                "start_symbol": resolved_start_symbol,
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
        # Alerte système : sync latest quotes en échec (API down probable)
        try:
            from service.alerting import send_system_alert
            send_system_alert(
                event="SYNC_QUOTES_FAILED",
                payload={
                    "run_id": run_id,
                    "error": error_message,
                    "symbol_source": normalize_symbol_source(args.symbol_source),
                    "mode": "historical" if resolved_from_date else "latest",
                },
                severity="critical",
            )
        except Exception:
            LOGGER.debug("Alerte sync_quotes indisponible.", exc_info=True)
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
        _emit_run_summary(
            {
                "run_id": run_id,
                "started_at": started_at.isoformat(timespec="seconds"),
                "finished_at": finished_at.isoformat(timespec="seconds"),
                "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
                "from_date": args.from_date,
                "to_date": args.to_date,
                "symbol_source": normalize_symbol_source(args.symbol_source),
                "start_symbol": resolved_start_symbol,
                "requested_limit": args.limit,
                "batch_size": args.batch_size,
                "audit_status": status,
                "error_message": error_message,
                **summary,
            }
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
            "start_symbol": resolved_start_symbol,
            "requested_limit": args.limit,
            "batch_size": args.batch_size,
            "audit_status": status,
            **safe_build_quote_iex_vs_consolidated_bias_summary(
                from_date=resolved_from_date,
                to_date=resolved_to_date,
                symbol_source=args.symbol_source,
                limit=args.limit,
                start_symbol=resolved_start_symbol,
            ),
            **summary,
        }
    )


if __name__ == "__main__":
    main()

