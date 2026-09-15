"""Forward PIT scheduled collectors configured exclusively by batch.yaml.

Every network payload is timestamped and hashed before normalization. Empty
provider responses are failures unless a handler explicitly allows them.
"""
from __future__ import annotations

import argparse
import csv
import html as html_lib
import hashlib
import io
import json
import logging
import os
import re
import ssl
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine

from common.config_loader import load_batch_config
from common.market_calendar import is_trading_day, nyse_session_dates
from database.connection import get_sqlalchemy_engine
from service.alpaca.clientAlpaca import fetch_alpaca_assets, get_alpaca_credentials
from service.forward_pit.options_delayed import (
    option_contract_adjustment_sync,
    options_delayed_bars_sync,
)

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
BQ_URL = "https://data.businessquant.com"
SEC_ARCHIVES = "https://www.sec.gov/Archives"
SEC_USER_AGENT_DEFAULT = ""
FAILED_RUNS_24H_SQL = """SELECT COUNT(*)
    FROM pit_collection_runs current_run
    JOIN (
        SELECT batch_name, MAX(started_at) AS started_at
        FROM pit_collection_runs
        WHERE batch_name <> 'pit_data_quality_daily'
        GROUP BY batch_name
    ) latest
      ON latest.batch_name=current_run.batch_name
     AND latest.started_at=current_run.started_at
    WHERE current_run.status='FAILED'
      AND current_run.started_at>=UTC_TIMESTAMP()-INTERVAL 24 HOUR"""

ALPACA_DATA_URL = "https://data.alpaca.markets"
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"

PENDING_BATCHES = {"auction_imbalance_sync", "securities_lending_sync", "official_options_nbbo_sync"}


@dataclass
class Outcome:
    requested: int = 0
    received: int = 0

    persisted: int = 0
    empty: int = 0
    failed: int = 0
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class BatchRunError(RuntimeError):
    """Échec bloquant conservant les compteurs déjà produits par le handler."""

    def __init__(self, message: str, outcome: Outcome):
        super().__init__(message)
        self.outcome = outcome


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _schema_hash(value: Any) -> str:
    if isinstance(value, dict):
        shape = {k: _schema_hash(v) for k, v in sorted(value.items())}
    elif isinstance(value, list):
        shape = [_schema_hash(value[0])] if value else []
    else:
        shape = type(value).__name__
    return _hash(shape)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _previous_weekdays(reference_date: date, lookback_days: int) -> list[date]:
    """Return past weekdays whose end-of-day file may already be published.

    The current New York date is deliberately excluded: EDGAR builds its daily
    indexes after the filing day.  Weekends are excluded because requesting a
    non-existent dated index can return 403 instead of 404 from sec.gov.
    """
    remaining = max(1, int(lookback_days))
    candidate = reference_date - timedelta(days=1)
    dates: list[date] = []
    while len(dates) < remaining:
        if candidate.weekday() < 5:
            dates.append(candidate)
        candidate -= timedelta(days=1)
    return dates


def _read_sec_response_limited(
    response: requests.Response,
    *,
    max_content_bytes: int,
    probe_bytes: int,
) -> tuple[str | None, str, int]:
    """Read a SEC response without ever retaining an oversized body in memory."""
    declared = int(response.headers.get("Content-Length") or 0)
    oversized = declared > max_content_bytes > 0
    content = bytearray()
    probe = bytearray()
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if len(probe) < probe_bytes:
            probe.extend(chunk[:max(0, probe_bytes - len(probe))])
        if not oversized:
            if len(content) + len(chunk) > max_content_bytes:
                oversized = True
                content.clear()
            else:
                content.extend(chunk)
        if oversized and len(probe) >= probe_bytes:
            break
    size = declared or total
    probe_text = bytes(probe).decode(response.encoding or "utf-8", errors="replace")
    if oversized:
        return None, probe_text, size
    body = bytes(content).decode(response.encoding or "utf-8", errors="replace")
    return body, body, size


def _sec_submission_header(
    submission_prefix: str, expected_form: str,
) -> tuple[datetime | None, str | None]:
    """Extract acceptance time and the primary document name from SEC SGML."""
    acceptance = None
    match = re.search(r"<ACCEPTANCE-DATETIME>\s*(\d{14})", submission_prefix, re.I)
    if match:
        acceptance = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
    expected = expected_form.strip().upper()
    candidates: list[tuple[str, str]] = []
    for document in re.finditer(
        r"<DOCUMENT>\s*(.*?)(?:<TEXT>|</DOCUMENT>|$)",
        submission_prefix,
        re.I | re.S,
    ):
        header = document.group(1)
        type_match = re.search(r"(?im)^<TYPE>\s*([^\r\n]+)", header)
        file_match = re.search(r"(?im)^<FILENAME>\s*([^\r\n]+)", header)
        if not file_match:
            continue
        name = file_match.group(1).strip().replace("\\", "/").rsplit("/", 1)[-1]
        if not name or not re.fullmatch(r"[A-Za-z0-9._-]+", name):
            continue
        candidates.append(((type_match.group(1).strip().upper() if type_match else ""), name))
    primary = next((name for doc_type, name in candidates if doc_type == expected), None)
    if primary is None and candidates:
        primary = candidates[0][1]
    return acceptance, primary


def _sec_filing_index_documents(index_html: str, base_url: str) -> list[dict[str, Any]]:
    """Parse SEC filing-detail rows into downloadable document descriptors."""
    documents: list[dict[str, Any]] = []
    for row_match in re.finditer(r"(?is)<tr[^>]*>(.*?)</tr>", index_html):
        row_html = row_match.group(1)
        cells = re.findall(r"(?is)<td[^>]*>(.*?)</td>", row_html)
        if len(cells) < 4:
            continue
        link_match = re.search(r"(?is)<a[^>]+href=[\"']([^\"']+)[\"']", cells[2])
        if not link_match:
            continue
        href = html_lib.unescape(link_match.group(1).strip())
        href_parts = urlsplit(href)
        if href_parts.path.rstrip('/') in ['/ix', '/ixviewer/doc/action']:
            href = parse_qs(href_parts.query).get('doc', [''])[0]
        resolved_url = urljoin(base_url.rstrip('/') + '/', href)
        resolved = urlsplit(resolved_url)
        if (not href or resolved.scheme != 'https' or resolved.hostname not in ['www.sec.gov', 'sec.gov']
                or resolved.username or resolved.password or resolved.port not in [None, 443]
                or not resolved.path.startswith('/Archives/edgar/data/')):
            continue
        filename = resolved.path.rsplit('/', 1)[-1]
        if not filename or not re.fullmatch(r"[A-Za-z0-9._-]+", filename):
            continue
        clean = lambda value: html_lib.unescape(re.sub(r"(?is)<[^>]+>", " ", value)).strip()
        sequence_text = clean(cells[0])
        size_text = clean(cells[4]) if len(cells) > 4 else ""
        documents.append({
            "sequence": int(sequence_text) if sequence_text.isdigit() else None,
            "description": re.sub(r"\s+", " ", clean(cells[1]))[:512] or None,
            "filename": filename,
            "document_type": re.sub(r"\s+", " ", clean(cells[3])).upper()[:32],
            "declared_size": int(size_text.replace(",", "")) if size_text.replace(",", "").isdigit() else None,
            "url": resolved_url,
        })
    return documents


def _read_response_bytes_limited(
    response: requests.Response, max_content_bytes: int,
) -> tuple[bytes | None, int]:
    """Read a binary attachment while enforcing a hard pre-insert bound."""
    declared = int(response.headers.get("Content-Length") or 0)
    if declared > max_content_bytes > 0:
        return None, declared
    content = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        if len(content) + len(chunk) > max_content_bytes:
            return None, len(content) + len(chunk)
        content.extend(chunk)
    return bytes(content), declared or len(content)


def _sec_exhibit_prefixes(value: Any) -> tuple[str, ...]:
    """Normalize configured SEC exhibit type prefixes."""
    raw_values = value if isinstance(value, (list, tuple, set)) else str(value or "EX-99").split(",")
    return tuple(item.strip().upper() for item in raw_values if str(item).strip()) or ("EX-99",)


def _selected_sec_exhibits(
    documents: list[dict[str, Any]], prefixes: tuple[str, ...], limit: int,
) -> list[dict[str, Any]]:
    """Keep configured exhibits, ordered as declared by the SEC filing index."""
    selected = [
        document for document in documents
        if any(str(document.get("document_type") or "").upper().startswith(prefix)
               for prefix in prefixes)
    ]
    selected.sort(key=lambda item: (
        item.get("sequence") is None,
        item.get("sequence") if item.get("sequence") is not None else 10**9,
        str(item.get("filename") or ""),
    ))
    return selected[:max(0, limit)]


def _sec_filing_index_url(submission_url: str, accession_number: str) -> str:
    """Build the SEC filing-detail page URL from a submission URL."""
    return submission_url.rsplit("/", 1)[0] + f"/{accession_number}-index.html"


def _download_sec_exhibits(
    engine: Engine,
    session: requests.Session,
    *,
    accession_number: str,
    submission_url: str,
    headers: dict[str, str],
    observed: datetime,
    run_id: str,
    prefixes: tuple[str, ...],
    max_exhibits: int,
    max_exhibit_bytes: int,
    max_requests_per_second: int,
) -> dict[str, Any]:
    """Discover and persist bounded exhibits as independent binary documents."""
    counters: dict[str, Any] = {
        "discovered": 0, "downloaded": 0, "persisted": 0,
        "skipped_existing": 0, "oversized": 0, "errors": [],
    }
    index_url = _sec_filing_index_url(submission_url, accession_number)
    response = session.get(index_url, headers=headers, timeout=60)
    if response.status_code == 404:
        response.close()
        index_url = index_url[:-1]  # .html -> .htm
        response = session.get(index_url, headers=headers, timeout=60)
    try:
        response.raise_for_status()
        base_url = index_url.rsplit("/", 1)[0]
        accession_directory = accession_number.replace('-', '')
        if not base_url.endswith('/' + accession_directory):
            base_url += '/' + accession_directory
        documents = _selected_sec_exhibits(
            _sec_filing_index_documents(response.text, base_url), prefixes, max_exhibits,
        )
    finally:
        response.close()
    time.sleep(1 / max(1, max_requests_per_second))
    counters["discovered"] = len(documents)

    for document in documents:
        with engine.connect() as conn:
            existing = conn.execute(text("""SELECT content_blob IS NOT NULL AS has_content
                FROM sec_filing_documents
                WHERE accession_number=:accession AND document_name=:name"""), {
                "accession": accession_number, "name": document["filename"],
            }).mappings().first()
        if existing and bool(existing["has_content"]):
            counters["skipped_existing"] += 1
            continue

        body: bytes | None = None
        actual_size = document.get("declared_size")
        mime_type = None
        error_message = None
        if actual_size and actual_size > max_exhibit_bytes:
            counters["oversized"] += 1
            error_message = f"taille déclarée {actual_size} > limite {max_exhibit_bytes}"
        else:
            attachment_response = None
            try:
                attachment_response = session.get(
                    document["url"], headers=headers, timeout=90, stream=True,
                )
                attachment_response.raise_for_status()
                mime_type = str(attachment_response.headers.get("Content-Type") or "").split(";", 1)[0] or None
                body, actual_size = _read_response_bytes_limited(
                    attachment_response, max_exhibit_bytes,
                )
                if body is None:
                    counters["oversized"] += 1
                    error_message = f"contenu > limite {max_exhibit_bytes}"
                else:
                    counters["downloaded"] += 1
            except Exception as exc:
                error_message = _safe_error_message(exc)
            finally:
                if attachment_response is not None:
                    attachment_response.close()

        if error_message:
            counters["errors"].append({
                "document": document["filename"], "error": error_message,
            })
        with engine.begin() as conn:
            result = conn.execute(text("""INSERT INTO sec_filing_documents
                (accession_number,document_sequence,document_type,document_name,description,
                 document_url,mime_type,content_bytes,content_sha256,content_blob,
                 observed_at,available_at,run_id)
                VALUES (:accession,:sequence,:document_type,:name,:description,:url,:mime_type,
                        :content_bytes,:content_sha256,:content_blob,:observed,:observed,:run)
                ON DUPLICATE KEY UPDATE
                  document_sequence=VALUES(document_sequence),document_type=VALUES(document_type),
                  description=VALUES(description),document_url=VALUES(document_url),
                  mime_type=COALESCE(VALUES(mime_type),mime_type),
                  content_bytes=COALESCE(VALUES(content_bytes),content_bytes),
                  content_sha256=COALESCE(VALUES(content_sha256),content_sha256),
                  content_blob=COALESCE(VALUES(content_blob),content_blob),
                  observed_at=VALUES(observed_at),available_at=VALUES(available_at),run_id=VALUES(run_id)"""), {
                "accession": accession_number, "sequence": document.get("sequence"),
                "document_type": document["document_type"], "name": document["filename"],
                "description": document.get("description"), "url": document["url"],
                "mime_type": mime_type, "content_bytes": actual_size,
                "content_sha256": hashlib.sha256(body).hexdigest() if body is not None else None,
                "content_blob": body, "observed": observed, "run": run_id,
            })
            counters["persisted"] += max(0, result.rowcount)
        time.sleep(1 / max(1, max_requests_per_second))
    return counters


def _download_sec_document(
    session: requests.Session,
    submission_url: str,
    form_type: str,
    headers: dict[str, str],
    *,
    max_submission_bytes: int,
    max_primary_document_bytes: int,
    probe_bytes: int,
) -> dict[str, Any]:
    """Download a bounded SEC submission, falling back to its primary document."""
    response = session.get(submission_url, headers=headers, timeout=90, stream=True)
    try:
        response.raise_for_status()
        content, prefix, submission_size = _read_sec_response_limited(
            response,
            max_content_bytes=max_submission_bytes,
            probe_bytes=probe_bytes,
        )
    finally:
        response.close()
    acceptance, primary_document = _sec_submission_header(prefix, form_type)
    if content is not None:
        return {
            "content": content,
            "acceptance": acceptance,
            "primary_document": primary_document,
            "content_url": submission_url,
            "submission_size": submission_size,
            "used_primary_fallback": False,
            "oversized_primary": False,
        }
    if not primary_document:
        return {
            "content": None,
            "acceptance": acceptance,
            "primary_document": None,
            "content_url": submission_url,
            "submission_size": submission_size,
            "used_primary_fallback": False,
            "oversized_primary": True,
        }
    primary_url = submission_url.rsplit("/", 1)[0] + "/" + primary_document
    primary_response = session.get(primary_url, headers=headers, timeout=90, stream=True)
    try:
        primary_response.raise_for_status()
        primary_content, _, primary_size = _read_sec_response_limited(
            primary_response,
            max_content_bytes=max_primary_document_bytes,
            probe_bytes=min(probe_bytes, max_primary_document_bytes),
        )
    finally:
        primary_response.close()
    return {
        "content": primary_content,
        "acceptance": acceptance,
        "primary_document": primary_document,
        "content_url": primary_url,
        "submission_size": submission_size,
        "primary_size": primary_size,
        "used_primary_fallback": True,
        "oversized_primary": primary_content is None,
    }


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _market_dt(value: Any, timezone_name: str = "America/New_York") -> tuple[datetime, datetime]:
    """Retourne (heure locale naïve, heure UTC naïve) pour un timestamp de marché."""
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    market_tz = ZoneInfo(timezone_name)
    localized = parsed.replace(tzinfo=market_tz) if parsed.tzinfo is None else parsed.astimezone(market_tz)
    return localized.replace(tzinfo=None), localized.astimezone(UTC).replace(tzinfo=None)


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _symbols(cfg: dict[str, Any]) -> list[str]:
    raw_path = str(cfg.get("symbols_file") or "").strip()
    if not raw_path:
        return []
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT / path
    content = path.read_text(encoding="utf-8-sig")
    return sorted({x.strip().upper() for x in re.split(r"[,\s;]+", content) if x.strip()})


def _collection_symbols(cfg: dict[str, Any]) -> list[str]:
    """Charge l'univers stable complet, sauf limite de smoke explicitement fournie."""
    symbols = _symbols(cfg)
    raw_limit = cfg.get("max_symbols")
    if raw_limit in (None, "", "all", "ALL"):
        return symbols
    limit = int(raw_limit)
    if limit <= 0:
        raise ValueError("max_symbols doit être strictement positif ou absent pour l'univers complet")
    return symbols[:limit]


def _assets_in_universe(
    assets: Iterable[dict[str, Any]], symbols: Iterable[str]
) -> list[dict[str, Any]]:
    allowed = {str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}
    return [
        item for item in assets
        if str(item.get("class")) == "us_equity"
        and str(item.get("symbol") or "").strip().upper() in allowed
    ]


def _secret(cfg: dict[str, Any], default_env: str) -> str:
    name = str(cfg.get("api_key_env") or default_env)
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Variable d'environnement {name} absente")
    return value


def _safe_error_message(error: Exception) -> str:
    """Redact credentials carried in request URLs before logging/persisting."""
    return re.sub(
        r"(?i)(api[_-]?key|access[_-]?token|token|secret|password)=([^&\s]+)",
        r"\1=***",
        str(error),
    )


def _request_json(session: requests.Session, url: str, *, params: dict[str, Any], headers: dict[str, str] | None = None, timeout: float = 45, attempts: int = 4) -> tuple[Any, int]:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            response = session.get(url, params=params, headers=headers, timeout=timeout)
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(min(20, 2 ** attempt)); continue
            response.raise_for_status()
            return response.json(), response.status_code
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(f"Echec HTTP {url}: {_safe_error_message(last or RuntimeError('erreur inconnue'))}")


def _paginated_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any],
    headers: dict[str, str],
    page_key: str,
    max_pages: int,
    pause_seconds: float = 0.0,
) -> list[tuple[dict[str, Any], int]]:
    """Charge toutes les pages Alpaca sans accepter une troncature silencieuse."""
    pages: list[tuple[dict[str, Any], int]] = []
    next_token: str | None = None
    for _page_number in range(1, max_pages + 1):
        page_params = dict(params)
        if next_token:
            page_params["page_token"] = next_token
        if pause_seconds > 0:
            time.sleep(pause_seconds)
        payload, status = _request_json(
            session, url, params=page_params, headers=headers,
        )
        if not isinstance(payload, dict):
            raise RuntimeError(f"Réponse Alpaca non objet pour {url}")
        pages.append((payload, status))
        next_token = str(payload.get(page_key) or "").strip() or None
        if not next_token:
            return pages
    raise RuntimeError(
        f"Pagination Alpaca tronquée après {max_pages} pages pour {url}"
    )


def _option_contract_parts(contract_symbol: str) -> tuple[date | None, float | None, str | None]:
    match = re.match(r"^(.+?)(\d{6})([CP])(\d{8})$", str(contract_symbol).upper())
    if not match:
        return None, None, None
    try:
        expiry = datetime.strptime(match.group(2), "%y%m%d").date()
        strike = int(match.group(4)) / 1000
    except ValueError:
        return None, None, None
    return expiry, strike, {"C": "CALL", "P": "PUT"}.get(match.group(3))


def _nearest_option_expirations(
    contracts: Iterable[str], target_dtes: Iterable[int], as_of: date,
) -> set[date]:
    expirations = sorted({
        expiry for contract in contracts
        for expiry, _, _ in [_option_contract_parts(contract)]
        if expiry is not None and expiry >= as_of
    })
    return {
        min(expirations, key=lambda expiry: (abs((expiry - as_of).days - target), expiry))
        for target in target_dtes if expirations
    }


def _select_option_surface_contracts(
    snapshots: dict[str, dict[str, Any]],
    *,
    expirations: set[date],
    spot: float,
    moneyness_targets: Iterable[float],
) -> set[str]:
    """Échantillonne une surface comparable : un strike par cible/type/échéance."""
    groups: dict[tuple[date, str], list[tuple[str, float]]] = {}
    for contract in snapshots:
        expiry, strike, option_type = _option_contract_parts(contract)
        if expiry not in expirations or strike is None or option_type is None:
            continue
        groups.setdefault((expiry, option_type), []).append((contract, strike))
    selected: set[str] = set()
    for contracts in groups.values():
        for target in moneyness_targets:
            selected.add(min(
                contracts,
                key=lambda pair: (abs(pair[1] / spot - target), pair[1], pair[0]),
            )[0])
    return selected


def _underlying_price(snapshot: dict[str, Any]) -> float | None:
    candidates = (
        (snapshot.get("latestTrade") or {}).get("p"),
        (snapshot.get("minuteBar") or {}).get("c"),
        (snapshot.get("dailyBar") or {}).get("c"),
        (snapshot.get("prevDailyBar") or {}).get("c"),
    )
    for value in candidates:
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            return price
    return None


def _option_is_liquid(
    item: dict[str, Any], *, min_bid: float, max_relative_spread: float,
    require_two_sided_quote: bool,
) -> bool:
    quote = item.get("latestQuote") or {}
    try:
        bid = float(quote.get("bp") or 0)
        ask = float(quote.get("ap") or 0)
    except (TypeError, ValueError):
        return False
    if require_two_sided_quote and (bid <= 0 or ask <= 0):
        return False
    if bid < min_bid or ask < bid:
        return False
    midpoint = (bid + ask) / 2
    return midpoint > 0 and (ask - bid) / midpoint <= max_relative_spread


class _SystemTrustAdapter(HTTPAdapter):
    """Requests adapter utilisant le magasin CA natif sans désactiver TLS."""

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        kwargs["ssl_context"] = ssl.create_default_context()
        super().init_poolmanager(*args, **kwargs)


def _configure_alpaca_session(
    session: requests.Session, *, use_system_trust_store: bool,
) -> None:
    if use_system_trust_store and sys.platform == "win32":
        session.mount("https://", _SystemTrustAdapter())


def _request_text_optional(
    session: requests.Session, url: str, *, timeout: float = 45, attempts: int = 4
) -> tuple[str | None, int]:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code in {403, 404}:
                return None, response.status_code
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(min(20, 2 ** attempt))
                continue
            response.raise_for_status()
            return response.text, response.status_code
        except requests.RequestException as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(f"Echec HTTP {url}: {_safe_error_message(last or RuntimeError('erreur inconnue'))}")


def _parse_finra_short_volume(content: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in csv.DictReader(io.StringIO(content.lstrip("\ufeff")), delimiter="|"):
        raw_date = str(item.get("Date") or "").strip()
        symbol = str(item.get("Symbol") or "").strip().upper()
        if len(raw_date) != 8 or not raw_date.isdigit() or not symbol:
            continue
        try:
            rows.append({
                "trade_date": datetime.strptime(raw_date, "%Y%m%d").date(),
                "symbol": symbol,
                "short_volume": int(item.get("ShortVolume") or 0),
                "short_exempt_volume": int(item.get("ShortExemptVolume") or 0),
                "total_volume": int(item.get("TotalVolume") or 0),
                "market": str(item.get("Market") or "").strip().upper() or "CNMS",
            })
        except (TypeError, ValueError):
            continue
    return rows


def _raw(conn: Connection, run_id: str, batch: str, provider: str, endpoint: str, entity: str, payload: Any, status: int = 200, observed: datetime | None = None) -> None:
    observed = observed or _utcnow()
    conn.execute(text("""
        INSERT IGNORE INTO pit_raw_payloads
        (run_id,batch_name,provider,endpoint,entity_key,observed_at,available_at,http_status,payload_hash,schema_hash,payload_json)
        VALUES (:run,:batch,:provider,:endpoint,:entity,:observed,:available,:status,:hash,:schema,:payload)
    """), {"run": run_id, "batch": batch, "provider": provider, "endpoint": endpoint, "entity": entity[:128], "observed": observed, "available": observed, "status": status, "hash": _hash(payload), "schema": _schema_hash(payload), "payload": _json(payload)})


def _data_blocks(payload: Any) -> Iterable[tuple[str, list[dict[str, Any]], dict[str, Any]]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        meta = payload.get("metadata") or {}
        yield str(meta.get("ticker") or ""), payload["data"], meta
    elif isinstance(payload, dict):
        for symbol, block in payload.items():
            if isinstance(block, dict) and isinstance(block.get("data"), list):
                yield str(symbol), block["data"], block.get("metadata") or {}


_SECURITY_FIELDS = (
    "cik", "cusip", "company_name", "exchange", "security_type", "asset_class",
    "etf_flag", "test_issue", "listing_status", "sector", "industry",
)


def _security_changes(
    previous: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Compare deux snapshots d'un même fournisseur sans conclure trop vite à un delisting."""
    if not previous:
        return []
    changes: list[dict[str, Any]] = []
    for symbol in sorted(current.keys() - previous.keys()):
        changes.append({"symbol": symbol, "type": "NEW_SYMBOL", "previous": None,
                        "current": _json(current[symbol]), "confirmed": False})
    for symbol in sorted(previous.keys() - current.keys()):
        changes.append({"symbol": symbol, "type": "MISSING_FROM_DIRECTORY",
                        "previous": _json(previous[symbol]), "current": None, "confirmed": False})
    for symbol in sorted(previous.keys() & current.keys()):
        for field_name in _SECURITY_FIELDS:
            old, new = previous[symbol].get(field_name), current[symbol].get(field_name)
            if old != new:
                changes.append({"symbol": symbol, "type": f"FIELD_{field_name.upper()}",
                                "previous": _json(old), "current": _json(new), "confirmed": False})
    return changes


def market_cap_sync(
    engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool
) -> Outcome:
    """Rafraîchit la capitalisation avec SEC primaire et fallbacks ciblés.

    La SEC fournit le nombre d'actions PIT, que le publieur d'univers multiplie
    par le cours de la date demandée. Yahoo puis Finnhub ne sont interrogés que
    pour les symboles sans ``shares_outstanding`` SEC frais.
    """
    symbols = _symbols(cfg)
    primary = str(cfg.get("primary_provider") or "sec").strip().lower()
    fallbacks = [
        item.strip().lower()
        for item in str(cfg.get("fallback_providers") or "yahoo_finance,finnhub").split(",")
        if item.strip()
    ]
    if primary != "sec":
        raise ValueError("market_cap_sync.primary_provider doit être 'sec'")
    if fallbacks != ["yahoo_finance", "finnhub"]:
        raise ValueError(
            "market_cap_sync.fallback_providers doit respecter l'ordre "
            "'yahoo_finance,finnhub'"
        )
    if not symbols:
        raise ValueError("market_cap_sync: univers vide")

    sec_lookback_days = max(1, int(cfg.get("sec_lookback_days", 30)))
    max_age_days = max(0, int(cfg.get("max_age_days", 365)))
    min_coverage_ratio = float(cfg.get("min_coverage_ratio", 0.95))
    if not 0.0 <= min_coverage_ratio <= 1.0:
        raise ValueError("market_cap_sync.min_coverage_ratio doit être compris entre 0 et 1")

    # Les compteurs globaux portent sur l'univers, pas sur la somme des appels
    # aux trois fournisseurs. Le détail des tentatives reste par provider.
    outcome = Outcome(requested=len(symbols))
    if dry:
        outcome.details.update({
            "strategy": "sec_edgar_then_yahoo_then_finnhub",
            "symbols": len(symbols),
            "sec_lookback_days": sec_lookback_days,
            "max_age_days": max_age_days,
        })
        return outcome

    from modelFactory.fundamental_features import fetch_and_store_fundamentals

    today = date.today()
    target_date = today + timedelta(days=1)
    sec_start = today - timedelta(days=sec_lookback_days)
    provider_details: dict[str, dict[str, Any]] = {}

    def _run_provider(provider: str, candidates: list[str], **kwargs: Any) -> None:
        if not candidates:
            result: dict[str, Any] = {"stored": 0, "failed": 0, "errors": []}
        else:
            result = fetch_and_store_fundamentals(
                candidates, engine=engine, provider=provider, **kwargs
            )
        stored = max(0, int(result.get("stored") or 0))
        failed = max(0, int(result.get("failed") or 0))
        outcome.persisted += stored
        provider_details[provider] = {
            "requested_symbols": len(candidates),
            "stored": stored,
            "failed": failed,
            "error_samples": [str(error) for error in (result.get("errors") or [])][:20],
        }

    _run_provider(
        "sec", symbols,
        start_date=sec_start.isoformat(), end_date=today.isoformat(),
    )
    sec_covered = _market_cap_covered_symbols(
        engine, symbols, target_date, max_age_days, ("SEC_EDGAR",)
    )

    yahoo_candidates = sorted(set(symbols) - sec_covered)
    _run_provider("yahoo_finance", yahoo_candidates)
    yahoo_covered = _market_cap_covered_symbols(
        engine, yahoo_candidates, target_date, max_age_days, ("YAHOO FINANCE",)
    )

    finnhub_candidates = sorted(set(yahoo_candidates) - yahoo_covered)
    _run_provider("finnhub", finnhub_candidates)
    finnhub_covered = _market_cap_covered_symbols(
        engine, finnhub_candidates, target_date, max_age_days, ("FINNHUB",)
    )

    covered = sec_covered | yahoo_covered | finnhub_covered
    uncovered = sorted(set(symbols) - covered)
    outcome.received = len(covered)
    outcome.empty = len(uncovered)
    coverage_ratio = len(covered) / len(symbols)
    provider_details["sec"]["eligible_symbols"] = len(sec_covered)
    provider_details["yahoo_finance"]["eligible_symbols"] = len(yahoo_covered)
    provider_details["finnhub"]["eligible_symbols"] = len(finnhub_covered)

    outcome.details.update({
        "strategy": "sec_edgar_then_yahoo_then_finnhub",
        "providers": provider_details,
        "symbols": len(symbols),
        "covered_symbols": len(covered),
        "coverage_ratio": coverage_ratio,
        "coverage_threshold": min_coverage_ratio,
        "coverage_accepted": coverage_ratio >= min_coverage_ratio,
        "uncovered_count": len(uncovered),
        "uncovered_symbols": uncovered[:100],
        "target_available_date": target_date.isoformat(),
        "sec_lookback_days": sec_lookback_days,
        "max_age_days": max_age_days,
    })
    _apply_market_cap_coverage_policy(
        outcome, uncovered, coverage_ratio, min_coverage_ratio,
    )
    return outcome


def _apply_market_cap_coverage_policy(
    outcome: Outcome,
    uncovered: list[str],
    coverage_ratio: float,
    min_coverage_ratio: float,
) -> None:
    """Keep missing-symbol diagnostics without failing an accepted run."""
    if coverage_ratio >= min_coverage_ratio:
        outcome.failed = 0
        return
    outcome.failed = len(uncovered) or 1
    raise BatchRunError(
        "market_cap_sync: couverture composite insuffisante "
        f"({coverage_ratio:.2%} < {min_coverage_ratio:.2%})",
        outcome,
    )


def _market_cap_covered_symbols(
    engine: Engine,
    symbols: Iterable[str],
    as_of: date,
    max_age_days: int,
    sources: tuple[str, ...],
) -> set[str]:
    """Retourne les symboles disposant d'une observation PIT fraîche et valide."""
    normalized_symbols = sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})
    normalized_sources = tuple(str(source).strip().upper() for source in sources if str(source).strip())
    if not normalized_symbols or not normalized_sources:
        return set()
    statement = text("""
        SELECT DISTINCT symbol
        FROM stock_fundamentals_daily
        WHERE symbol IN :symbols
          AND UPPER(source) IN :sources
          AND trade_date BETWEEN :min_date AND :as_of
          AND COALESCE(available_date, DATE_ADD(trade_date, INTERVAL 1 DAY)) <= :as_of
          AND (
              (UPPER(source) = 'SEC_EDGAR' AND shares_outstanding > 0)
              OR
              (UPPER(source) <> 'SEC_EDGAR' AND market_cap > 0)
          )
    """).bindparams(bindparam("symbols", expanding=True), bindparam("sources", expanding=True))
    with engine.connect() as connection:
        rows = connection.execute(statement, {
            "symbols": normalized_symbols,
            "sources": normalized_sources,
            "min_date": as_of - timedelta(days=max_age_days),
            "as_of": as_of,
        }).scalars().all()
    return {str(symbol).strip().upper() for symbol in rows if str(symbol).strip()}


def daily_bars_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    if cfg.get("canonical_upsert", False):
        raise RuntimeError(
            "canonical_upsert interdit: les OHLCV Business Quant sont RAW; "
            "un ajustement splits validé est requis avant stock_bars_daily"
        )
    symbols, key = _symbols(cfg), _secret(cfg, "BUSINESS_QUANT_API_KEY")
    outcome = Outcome(requested=len(symbols)); today = date.today(); start = today - timedelta(days=int(cfg.get("lookback_days", 10)))
    with requests.Session() as session, engine.begin() as conn:
        for chunk in _chunks(symbols, int(cfg.get("batch_size", 100))):
            payload, status = _request_json(session, f"{BQ_URL}/quotes", params={"ticker": ",".join(chunk), "mode": "eod", "from_date": start.isoformat(), "till_date": today.isoformat(), "limit": 10000, "api_key": key})
            if not dry:
                _raw(conn, run_id, "daily_bars_sync", "business_quant", "/quotes", ",".join(chunk), payload, status)
            rows = []
            for symbol, data, meta in _data_blocks(payload):
                resolved = str(symbol or meta.get("ticker") or "").upper()
                for item in data:
                    try:
                        local_ts, utc_ts = _market_dt(item.get("date"))
                        row = {"provider": "business_quant", "symbol": resolved, "trade_date": local_ts.date(), "observed": _utcnow(), "available": _utcnow(), "open": float(item["open"]), "high": float(item["high"]), "low": float(item["low"]), "close": float(item["close"]), "volume": int(item.get("volume") or 0), "provider_ts": utc_ts, "hash": _hash(item), "run": run_id}
                        rows.append(row)
                    except (KeyError, TypeError, ValueError, AssertionError):
                        outcome.failed += 1
            outcome.received += len(rows)
            if not rows:
                raise RuntimeError(f"Business Quant EOD vide pour lot de {len(chunk)} symboles")
            if dry:
                continue
            for row in rows:
                result = conn.execute(text("""INSERT IGNORE INTO stock_bars_daily_versions
                    (provider,symbol,trade_date,observed_at,available_at,open,high,low,close,volume,provider_timestamp,payload_hash,adjustment_mode,run_id)
                    VALUES (:provider,:symbol,:trade_date,:observed,:available,:open,:high,:low,:close,:volume,:provider_ts,:hash,'raw',:run)"""), row)
                outcome.persisted += max(0, result.rowcount)
        if not dry:
            # Une seconde valeur différente pour la même séance est une correction.
            # Les versions sont conservées sans toucher à la table canonique ajustée.
            conn.execute(text("""UPDATE stock_bars_daily_versions v
                JOIN (SELECT provider,symbol,trade_date FROM stock_bars_daily_versions
                      WHERE run_id=:run GROUP BY provider,symbol,trade_date) touched
                  ON touched.provider=v.provider AND touched.symbol=v.symbol AND touched.trade_date=v.trade_date
                JOIN (SELECT provider,symbol,trade_date FROM
                        (SELECT provider,symbol,trade_date,payload_hash FROM stock_bars_daily_versions) version_snapshot
                      GROUP BY provider,symbol,trade_date HAVING COUNT(DISTINCT payload_hash)>1) corrected
                  ON corrected.provider=v.provider AND corrected.symbol=v.symbol AND corrected.trade_date=v.trade_date
                SET v.is_correction=1"""), {"run": run_id})
    return outcome


def _nasdaq_rows(session: requests.Session) -> list[dict[str, Any]]:
    import csv, io
    rows: list[dict[str, Any]] = []
    sources = (("nasdaqlisted", "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"), ("otherlisted", "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"))
    for source, url in sources:
        response = session.get(url, timeout=45); response.raise_for_status()
        for row in csv.DictReader(io.StringIO(response.text), delimiter="|"):
            symbol = row.get("Symbol") or row.get("ACT Symbol")
            if symbol and not symbol.startswith("File Creation Time"):
                rows.append({"symbol": symbol, "company_name": row.get("Security Name"), "exchange": row.get("Exchange") or "NASDAQ", "security_type": source, "etf_flag": str(row.get("ETF", "N")).upper() == "Y", "test_issue": str(row.get("Test Issue", "N")).upper() == "Y", "listing_status": "active", "raw": row})
    return rows


def security_master_snapshot(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    outcome = Outcome(); observed = _utcnow(); snapshot = date.today(); providers = [x.strip() for x in str(cfg.get("providers", "nasdaq_symbol_directory,business_quant")).split(",")]
    with requests.Session() as session, engine.begin() as conn:
        for provider in providers:
            if provider == "nasdaq_symbol_directory":
                rows = _nasdaq_rows(session); payload = {"rows": rows}
                if not dry:
                    _raw(conn, run_id, "security_master_snapshot", provider,
                         "/dynamic/SymDir", "ALL", payload, observed=observed)
            elif provider == "business_quant":
                allowed_days = {int(x) for x in str(cfg.get("business_quant_weekdays", "")).split(",") if x.strip()}
                # Python weekday: Monday=0; batch.yaml run_days: Sunday=0.
                current_batch_day = (date.today().weekday() + 1) % 7
                if allowed_days and current_batch_day not in allowed_days:
                    outcome.warnings.append("business_quant universe ignoré hors jour hebdomadaire")
                    continue
                key = _secret(cfg, "BUSINESS_QUANT_API_KEY")
                payload, status = _request_json(session, f"{BQ_URL}/universe", params={"api_key": key})
                if not dry:
                    _raw(conn, run_id, "security_master_snapshot", provider, "/universe", "ALL", payload, status, observed)
                data = payload.get("data", payload) if isinstance(payload, dict) else payload
                rows = []
                for item in data if isinstance(data, list) else []:
                    security_type = str(item.get("security_type") or "")
                    rows.append({"symbol": item.get("ticker") or item.get("symbol"), "cik": item.get("cik"), "cusip": item.get("cusip"), "company_name": item.get("name") or item.get("companyname"), "exchange": item.get("exchange"), "security_type": security_type, "asset_class": item.get("asset_class") or security_type, "etf_flag": security_type.upper() == "ETF", "listing_status": item.get("status") or "active", "sector": item.get("sector"), "industry": item.get("industry"), "raw": item})
            else:
                outcome.warnings.append(f"provider inconnu: {provider}"); continue
            outcome.requested += 1; outcome.received += len(rows)
            if not rows:
                raise RuntimeError(f"security master vide provider={provider}")
            current_map = {
                str(item.get("symbol") or "").strip().upper(): {
                    field_name: item.get(field_name) for field_name in _SECURITY_FIELDS
                }
                for item in rows if str(item.get("symbol") or "").strip()
            }
            previous_rows = conn.execute(text("""SELECT symbol,cik,cusip,company_name,exchange,
                    security_type,asset_class,etf_flag,test_issue,listing_status,sector,industry
                FROM security_master_snapshots
                WHERE provider=:provider AND snapshot_date=(
                    SELECT MAX(snapshot_date) FROM security_master_snapshots
                    WHERE provider=:provider AND snapshot_date<:snapshot)"""),
                {"provider": provider, "snapshot": snapshot}).mappings().all()
            previous_map = {str(row["symbol"]): dict(row) for row in previous_rows}
            if dry:
                outcome.details[f"{provider}_changes"] = len(_security_changes(previous_map, current_map))
                continue
            for item in rows:
                symbol = str(item.get("symbol") or "").strip().upper()
                if not symbol: continue
                params = {"provider": provider, "snapshot": snapshot, "observed": observed, "available": observed, "symbol": symbol, "cik": str(item.get("cik") or "").zfill(10) if item.get("cik") else None, "cusip": item.get("cusip"), "name": item.get("company_name"), "exchange": item.get("exchange"), "stype": item.get("security_type"), "aclass": item.get("asset_class"), "etf": item.get("etf_flag"), "test": item.get("test_issue"), "status": item.get("listing_status"), "sector": item.get("sector"), "industry": item.get("industry"), "hash": _hash(item.get("raw", item)), "run": run_id}
                result = conn.execute(text("""INSERT INTO security_master_snapshots
                    (provider,snapshot_date,observed_at,available_at,symbol,cik,cusip,company_name,exchange,security_type,asset_class,etf_flag,test_issue,listing_status,sector,industry,raw_hash,run_id)
                    VALUES (:provider,:snapshot,:observed,:available,:symbol,:cik,:cusip,:name,:exchange,:stype,:aclass,:etf,:test,:status,:sector,:industry,:hash,:run)
                    ON DUPLICATE KEY UPDATE observed_at=VALUES(observed_at),available_at=VALUES(available_at),cik=VALUES(cik),cusip=VALUES(cusip),company_name=VALUES(company_name),exchange=VALUES(exchange),security_type=VALUES(security_type),asset_class=VALUES(asset_class),etf_flag=VALUES(etf_flag),test_issue=VALUES(test_issue),listing_status=VALUES(listing_status),sector=VALUES(sector),industry=VALUES(industry),raw_hash=VALUES(raw_hash),run_id=VALUES(run_id)"""), params)
                outcome.persisted += max(0, result.rowcount)
            changes = _security_changes(previous_map, current_map)
            for change in changes:
                result = conn.execute(text("""INSERT INTO security_master_changes
                    (provider,detected_date,symbol,change_type,previous_value,current_value,confirmed,run_id)
                    VALUES (:provider,:snapshot,:symbol,:type,:previous,:current,:confirmed,:run)
                    ON DUPLICATE KEY UPDATE previous_value=VALUES(previous_value),current_value=VALUES(current_value),
                    confirmed=VALUES(confirmed),run_id=VALUES(run_id)"""),
                    {"provider": provider, "snapshot": snapshot, "run": run_id, **change})
                outcome.persisted += max(0, result.rowcount)
            outcome.details[f"{provider}_changes"] = len(changes)
    return outcome


def corporate_actions_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    outcome = Outcome(); today = date.today(); start = today - timedelta(days=int(cfg.get("lookback_days", 7))); end = today + timedelta(days=int(cfg.get("forward_days", 30)))
    providers = [x.strip() for x in str(cfg.get("providers", "business_quant,alpaca")).split(",")]
    normalized: list[dict[str, Any]] = []
    with requests.Session() as session, engine.begin() as conn:
        if "business_quant" in providers:
            key = _secret(cfg, "BUSINESS_QUANT_API_KEY"); page = 1
            while True:
                payload, status = _request_json(session, f"{BQ_URL}/corporate_actions", params={"action": "all", "from_date": start.isoformat(), "till_date": end.isoformat(), "limit": 10000, "page": page, "api_key": key})
                if not dry:
                    _raw(conn, run_id, "corporate_actions_sync", "business_quant", "/corporate_actions", f"{start}:{end}:p{page}", payload, status)
                data = payload.get("data", []) if isinstance(payload, dict) else []
                for item in data:
                    normalized.append({"provider": "business_quant", "event_id": item.get("id"), "symbol": str(item.get("ticker") or "").upper(), "type": str(item.get("action") or "unknown").lower(), "date": item.get("date"), "value": item.get("value"), "related": item.get("related_ticker"), "related_name": item.get("related_name"), "notes": item.get("notes"), "raw": item})
                pages = ((payload.get("metadata") or {}).get("pagination") or {}).get("total_pages", 1)
                if page >= int(pages or 1): break
                page += 1
        if "alpaca" in providers:
            from corporate_actions.provider import AlpacaCorporateActionProvider
            for event in AlpacaCorporateActionProvider().fetch_events(None, start, end):
                raw = event.raw_payload or {}
                value = event.amount_per_share if event.amount_per_share is not None else ((event.split_to / event.split_from) if event.split_from and event.split_to else None)
                normalized.append({"provider": "alpaca", "event_id": event.provider_event_id, "symbol": event.symbol, "type": str(event.ca_type), "date": event.ex_date, "value": value, "related": None, "related_name": None, "notes": None, "raw": raw})
        outcome.requested = len(providers); outcome.received = len(normalized)
        if not normalized: raise RuntimeError("Aucune corporate action reçue: une réponse vide n'est pas un succès")
        if not dry:
            for item in normalized:
                conflict = _hash([item["symbol"], item["type"], str(item["date"])])
                result = conn.execute(text("""INSERT IGNORE INTO corporate_action_source_events
                    (provider,provider_event_id,symbol,action_type,effective_date,value_num,related_symbol,related_name,notes,observed_at,available_at,payload_hash,run_id,conflict_group_key)
                    VALUES (:provider,:event_id,:symbol,:type,:date,:value,:related,:related_name,:notes,:observed,:observed,:hash,:run,:conflict)"""), {**item, "observed": _utcnow(), "hash": _hash(item["raw"]), "run": run_id, "conflict": conflict})
                outcome.persisted += max(0, result.rowcount)
    return outcome


def sec_edgar_incremental(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    user_agent = (os.getenv(str(cfg.get("user_agent_env", "SEC_EDGAR_USER_AGENT"))) or SEC_USER_AGENT_DEFAULT).strip()
    if not user_agent:
        raise RuntimeError("SEC_EDGAR_USER_AGENT absent (format attendu: application contact@email)")
    allowed = {x.strip().upper() for x in str(cfg.get("forms", "")).split(",") if x.strip()}
    observed = _utcnow(); rows: list[dict[str, Any]] = []; outcome = Outcome()
    sec_today = datetime.now(ZoneInfo("America/New_York")).date()
    index_dates = _previous_weekdays(sec_today, int(cfg.get("lookback_days", 3)))
    unavailable_indexes: list[dict[str, Any]] = []
    accessible_indexes = 0
    max_submission_bytes = max(1024, int(cfg.get("max_submission_bytes", 16 * 1024 * 1024)))
    max_primary_bytes = max(1024, int(cfg.get("max_primary_document_bytes", 16 * 1024 * 1024)))
    probe_bytes = max(1024, int(cfg.get("submission_probe_bytes", 2 * 1024 * 1024)))
    download_exhibits = bool(cfg.get("download_exhibits", False))
    exhibit_prefixes = _sec_exhibit_prefixes(cfg.get("exhibit_type_prefixes", "EX-99"))
    max_exhibits = max(1, int(cfg.get("max_exhibits_per_filing", 10)))
    max_exhibit_bytes = max(1024, int(cfg.get("max_exhibit_bytes", 8 * 1024 * 1024)))
    max_requests_per_second = max(1, int(cfg.get("max_requests_per_second", 8)))
    document_errors: list[dict[str, str]] = []
    primary_fallbacks = 0
    oversized_primary_documents = 0
    exhibit_totals: dict[str, Any] = {
        "discovered": 0, "downloaded": 0, "persisted": 0,
        "skipped_existing": 0, "oversized": 0, "errors": [],
    }
    with engine.connect() as conn:
        cik_symbols = {
            str(row.cik).zfill(10): row.symbol
            for row in conn.execute(text("""SELECT s.cik,s.symbol FROM security_master_snapshots s
                JOIN (SELECT cik,MAX(snapshot_date) d FROM security_master_snapshots WHERE cik IS NOT NULL GROUP BY cik) x
                ON x.cik=s.cik AND x.d=s.snapshot_date""")).fetchall()
        }
    with requests.Session() as session:
        headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        indexed_rows: dict[str, dict[str, Any]] = {}
        for day in index_dates:
            quarter = (day.month - 1) // 3 + 1
            url = f"{SEC_ARCHIVES}/edgar/daily-index/{day.year}/QTR{quarter}/master.{day.strftime('%Y%m%d')}.idx"
            outcome.requested += 1
            response = session.get(url, headers=headers, timeout=60)
            if response.status_code in {403, 404}:
                unavailable_indexes.append({"date": day.isoformat(), "status": response.status_code})
                continue
            response.raise_for_status()
            accessible_indexes += 1
            if not dry:
                with engine.begin() as conn:
                    _raw(conn, run_id, "sec_edgar_incremental", "sec_edgar", "/daily-index/master.idx", day.isoformat(), {"text": response.text}, response.status_code, observed)
            body = response.text.split("--------------------------------------------------------------------------------", 1)[-1]
            for line in body.splitlines():
                parts = line.split("|")
                if len(parts) != 5: continue
                cik, company, form, filing_date, filename = parts
                if allowed and form.upper() not in allowed: continue
                accession = Path(filename).stem.replace("-", "")
                accession_fmt = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}" if len(accession) >= 18 else accession
                indexed_rows[accession_fmt] = {"cik": cik.zfill(10), "company": company, "form": form, "filing_date": filing_date, "filename": filename, "accession": accession_fmt}
        rows = list(indexed_rows.values())
        outcome.received = len(rows)
        outcome.details["index_dates"] = [day.isoformat() for day in index_dates]
        outcome.details["accessible_indexes"] = accessible_indexes
        outcome.details["unavailable_indexes"] = unavailable_indexes
        if accessible_indexes == 0:
            outcome.failed = len(unavailable_indexes) or 1
            raise BatchRunError(
                "Aucun index quotidien SEC accessible; vérifier SEC_EDGAR_USER_AGENT, "
                "la disponibilité des index et une éventuelle limitation SEC",
                outcome,
            )
        if unavailable_indexes:
            unavailable = ", ".join(
                f"{item['date']} (HTTP {item['status']})" for item in unavailable_indexes
            )
            outcome.warnings.append(f"Index SEC non encore disponible: {unavailable}")
        for item in rows:
            with engine.connect() as conn:
                existing = conn.execute(text("""SELECT id,content_text IS NOT NULL AS has_content
                    FROM sec_filing_raw WHERE accession_number=:a"""), {"a": item["accession"]}).mappings().first()
            needs_primary = not existing or (
                cfg.get("download_primary_documents", True) and not bool(existing["has_content"])
            )
            if not needs_primary and not download_exhibits:
                continue
            content = None
            primary_document = None
            submission_url = f"{SEC_ARCHIVES}/{item['filename']}"
            content_url = submission_url
            acceptance = None
            if needs_primary and cfg.get("download_primary_documents", True) and not dry:
                try:
                    downloaded = _download_sec_document(
                        session, submission_url, item["form"], headers,
                        max_submission_bytes=max_submission_bytes,
                        max_primary_document_bytes=max_primary_bytes,
                        probe_bytes=probe_bytes,
                    )
                    content = downloaded["content"]
                    acceptance = downloaded["acceptance"]
                    primary_document = downloaded["primary_document"]
                    content_url = downloaded["content_url"]
                    if downloaded["used_primary_fallback"]:
                        primary_fallbacks += 1
                    if downloaded["oversized_primary"]:
                        oversized_primary_documents += 1
                        outcome.failed += 1
                        document_errors.append({
                            "accession": item["accession"],
                            "error": "document principal absent ou supérieur à la limite",
                        })
                except Exception as exc:
                    outcome.failed += 1
                    document_errors.append({
                        "accession": item["accession"],
                        "error": _safe_error_message(exc),
                    })
                time.sleep(1 / max_requests_per_second)
            if not dry and needs_primary:
                with engine.begin() as conn:
                    result = conn.execute(text("""INSERT INTO sec_filing_raw
                        (accession_number,cik,symbol,company_name,form_type,filing_date,acceptance_datetime,primary_document,filing_url,content_sha256,content_text,observed_at,available_at,run_id,amendment)
                        VALUES (:accession,:cik,:symbol,:company,:form,:filing_date,:acceptance,:primary_document,:url,:hash,:content,:observed,:observed,:run,:amendment)
                        ON DUPLICATE KEY UPDATE
                          symbol=COALESCE(VALUES(symbol),symbol),
                          acceptance_datetime=COALESCE(VALUES(acceptance_datetime),acceptance_datetime),
                          primary_document=COALESCE(VALUES(primary_document),primary_document),
                          filing_url=COALESCE(VALUES(filing_url),filing_url),
                          content_sha256=COALESCE(VALUES(content_sha256),content_sha256),
                          content_text=COALESCE(VALUES(content_text),content_text),
                          observed_at=VALUES(observed_at),available_at=VALUES(available_at),run_id=VALUES(run_id)"""), {**item, "symbol": cik_symbols.get(item["cik"]), "acceptance": acceptance, "primary_document": primary_document, "url": content_url, "hash": hashlib.sha256((content or "").encode(errors="ignore")).hexdigest() if content else None, "content": content, "observed": observed, "run": run_id, "amendment": item["form"].endswith("/A")})
                    outcome.persisted += max(0, result.rowcount)
            if download_exhibits and not dry:
                try:
                    exhibit_result = _download_sec_exhibits(
                        engine, session,
                        accession_number=item["accession"],
                        submission_url=submission_url,
                        headers=headers,
                        observed=observed,
                        run_id=run_id,
                        prefixes=exhibit_prefixes,
                        max_exhibits=max_exhibits,
                        max_exhibit_bytes=max_exhibit_bytes,
                        max_requests_per_second=max_requests_per_second,
                    )
                    for key in ("discovered", "downloaded", "persisted", "skipped_existing", "oversized"):
                        exhibit_totals[key] += exhibit_result[key]
                    exhibit_totals["errors"].extend(exhibit_result["errors"])
                    outcome.persisted += exhibit_result["persisted"]
                except Exception as exc:
                    exhibit_totals["errors"].append({
                        "accession": item["accession"], "error": _safe_error_message(exc),
                    })
    outcome.details.update({
        "max_submission_bytes": max_submission_bytes,
        "max_primary_document_bytes": max_primary_bytes,
        "primary_document_fallbacks": primary_fallbacks,
        "oversized_primary_documents": oversized_primary_documents,
        "document_errors": document_errors[:50],
        "download_exhibits": download_exhibits,
        "exhibit_type_prefixes": list(exhibit_prefixes),
        "max_exhibits_per_filing": max_exhibits,
        "max_exhibit_bytes": max_exhibit_bytes,
        "exhibits": {**exhibit_totals, "errors": exhibit_totals["errors"][:50]},
    })
    if document_errors:
        outcome.warnings.append(
            f"Contenu indisponible pour {len(document_errors)} dépôt(s) SEC; métadonnées conservées"
        )
    if exhibit_totals["errors"]:
        outcome.failed += len(exhibit_totals["errors"])
        outcome.warnings.append(
            f"{len(exhibit_totals['errors'])} annexe(s) SEC indisponible(s) ou trop volumineuse(s); métadonnées conservées"
        )
    if not rows: outcome.warnings.append("Aucun filing correspondant dans les daily indexes disponibles")
    return outcome


def borrow_status_snapshot(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    requested_symbols = set(_collection_symbols(cfg))
    assets = fetch_alpaca_assets()
    observed = _utcnow()
    if not assets: raise RuntimeError("Alpaca assets vide")
    selected_assets = _assets_in_universe(assets, requested_symbols)
    outcome = Outcome(requested=len(requested_symbols), received=len(selected_assets))
    outcome.details["provider_assets_received"] = len(assets)
    outcome.details["universe_symbols"] = len(requested_symbols)
    with engine.begin() as conn:
        if not dry:
            _raw(conn, run_id, "borrow_status_snapshot", "alpaca", "/v2/assets", "ALL", assets, observed=observed)
        if not dry:
            for item in selected_assets:
                shortable, etb = item.get("shortable"), item.get("easy_to_borrow")
                status = "EASY" if shortable and etb else ("LOCATE_REQUIRED" if shortable else "NOT_SHORTABLE")
                result = conn.execute(text("""INSERT IGNORE INTO stock_borrow_status_snapshots
                    (provider,symbol,observed_at,available_at,shortable,easy_to_borrow,marginable,tradable,status,borrow_status,payload_hash,run_id)
                    VALUES ('alpaca',:symbol,:observed,:observed,:shortable,:etb,:marginable,:tradable,:status,:borrow,:hash,:run)"""), {"symbol": item.get("symbol"), "observed": observed, "shortable": shortable, "etb": etb, "marginable": item.get("marginable"), "tradable": item.get("tradable"), "status": item.get("status"), "borrow": status, "hash": _hash(item), "run": run_id})
                outcome.persisted += max(0, result.rowcount)
    return outcome


def finra_short_volume_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    symbols = set(_collection_symbols(cfg))
    observed = _utcnow()
    lookback_days = max(1, int(cfg.get("lookback_days", 7)))
    template = str(cfg.get("source_url_template") or
                   "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date}.txt")
    market_today = datetime.now(ZoneInfo("America/New_York")).date()
    trade_days = _previous_weekdays(market_today, lookback_days)
    outcome = Outcome(requested=len(trade_days))
    files_found = 0
    with requests.Session() as session, engine.begin() as conn:
        for trade_day in trade_days:
            url = template.format(date=trade_day.strftime("%Y%m%d"))
            content, status = _request_text_optional(session, url)
            if content is None:
                outcome.empty += 1
                continue
            files_found += 1
            if not dry:
                _raw(conn, run_id, "finra_short_volume_sync", "finra",
                     "/equity/regsho/daily/CNMS", trade_day.isoformat(),
                     content, status, observed)
            rows = [row for row in _parse_finra_short_volume(content)
                    if row["symbol"] in symbols]
            outcome.received += len(rows)
            if dry:
                continue
            existing = conn.execute(text("""SELECT symbol,market,payload_hash
                FROM stock_short_volume_daily
                WHERE provider='finra_cnms' AND trade_date=:trade_date"""),
                {"trade_date": trade_day}).mappings().all()
            known_hashes: dict[tuple[str, str], set[str]] = {}
            for item in existing:
                known_hashes.setdefault(
                    (str(item["symbol"]), str(item["market"])), set()
                ).add(str(item["payload_hash"]))
            for row in rows:
                row_hash = _hash(row)
                previous_hashes = known_hashes.get((row["symbol"], row["market"]), set())
                correction = bool(previous_hashes and row_hash not in previous_hashes)
                result = conn.execute(text("""INSERT IGNORE INTO stock_short_volume_daily
                    (provider,trade_date,symbol,market,short_volume,short_exempt_volume,
                     total_volume,observed_at,available_at,payload_hash,run_id,is_correction)
                    VALUES ('finra_cnms',:trade_date,:symbol,:market,:short_volume,
                            :short_exempt_volume,:total_volume,:observed,:observed,:hash,:run,
                            :correction)"""),
                    {**row, "observed": observed, "hash": row_hash, "run": run_id,
                     "correction": correction})
                outcome.persisted += max(0, result.rowcount)
    outcome.details.update({
        "candidate_dates": [day.isoformat() for day in trade_days],
        "files_found": files_found,
        "universe_symbols": len(symbols),
    })
    if files_found == 0:
        outcome.failed = len(trade_days)
        raise BatchRunError(
            "Aucun fichier FINRA Consolidated NMS disponible sur les jours ouvrés précédents",
            outcome,
        )
    if outcome.received == 0:
        raise RuntimeError("Fichiers FINRA trouvés mais aucun symbole de l'univers n'est couvert")
    return outcome


def business_quant_analyst_snapshot(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    symbols = _collection_symbols(cfg); metrics = [x.strip() for x in str(cfg.get("metrics", "eps")).split(",")]; key = _secret(cfg, "BUSINESS_QUANT_API_KEY"); observed = _utcnow(); outcome = Outcome(requested=len(symbols) * len(metrics))
    with requests.Session() as session, engine.begin() as conn:
        for symbol in symbols:
            for metric in metrics:
                payload, status = _request_json(session, f"{BQ_URL}/estimates", params={"ticker": symbol, "mode": metric, "api_key": key})
                if not dry:
                    _raw(conn, run_id, "business_quant_analyst_snapshot", "business_quant", "/estimates", f"{symbol}:{metric}", payload, status, observed)
                inserted = 0
                for block in payload.get("data", []) if isinstance(payload, dict) else []:
                    dimension = block.get("dimension")
                    for item in block.get("estimates", []):
                        outcome.received += 1
                        if dry: continue
                        result = conn.execute(text("""INSERT IGNORE INTO stock_analyst_consensus_snapshots
                            (provider,symbol,metric,dimension_name,fiscal_period,data_type,consensus_value,high_value,low_value,actual_value,observed_at,available_at,payload_hash,run_id)
                            VALUES ('business_quant',:symbol,:metric,:dimension,:period,:dtype,:consensus,:high,:low,:actual,:observed,:observed,:hash,:run)"""), {"symbol": symbol, "metric": metric.upper(), "dimension": dimension, "period": item.get("period"), "dtype": item.get("data_type"), "consensus": item.get("value_estimate"), "high": item.get("high_estimate"), "low": item.get("low_estimate"), "actual": item.get("value_reported"), "observed": observed, "hash": _hash(item), "run": run_id})
                        inserted += max(0, result.rowcount)
                outcome.persisted += inserted
                if not payload.get("data"): outcome.empty += 1
    if outcome.received == 0:
        raise RuntimeError("Business Quant estimates vide pour tout l'univers demandé")
    return outcome


def options_snapshot(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    symbols = _collection_symbols(cfg)
    feed = str(cfg.get("feed", "indicative")).strip().lower()
    if feed != "indicative":
        raise ValueError("Le batch gratuit impose feed=indicative; OPRA exige un abonnement")
    target_dtes = tuple(sorted({
        int(value) for value in str(cfg.get("target_dtes", "5,10,20")).split(",")
        if str(value).strip()
    }))
    if not target_dtes or min(target_dtes) <= 0:
        raise ValueError("target_dtes doit contenir des horizons strictement positifs")
    moneyness_targets = tuple(sorted({
        float(value) for value in str(
            cfg.get("moneyness_targets", "0.85,0.90,0.95,1.00,1.05,1.10,1.15")
        ).split(",") if str(value).strip()
    }))
    if not moneyness_targets:
        raise ValueError("moneyness_targets ne peut pas être vide")
    tolerance = int(cfg.get("dte_tolerance_days", 4))
    moneyness_min = float(cfg.get("moneyness_min", 0.80))
    moneyness_max = float(cfg.get("moneyness_max", 1.20))
    if not 0 < moneyness_min < 1 < moneyness_max:
        raise ValueError("La fenêtre de moneyness doit encadrer 1.0")
    min_bid = float(cfg.get("min_bid", 0.01))
    max_relative_spread = float(cfg.get("max_relative_spread", 1.0))
    require_two_sided = bool(cfg.get("require_two_sided_quote", True))
    include_contract_metadata = bool(cfg.get("include_contract_metadata", True))
    min_open_interest = int(cfg.get("min_open_interest", 10))
    allow_missing_oi = bool(cfg.get("allow_missing_open_interest", True))
    max_pages = int(cfg.get("max_pages_per_symbol", 10))
    request_pause = float(cfg.get("request_interval_seconds", 0.35))
    stock_chunk_size = int(cfg.get("stock_snapshot_batch_size", 100))
    max_consecutive_failures = int(cfg.get("max_consecutive_failures", 5))
    max_failure_ratio = float(cfg.get("max_failure_ratio", 0.05))
    as_of = datetime.now(ZoneInfo("America/New_York")).date()
    min_expiry = as_of + timedelta(days=max(1, min(target_dtes) - tolerance))
    max_expiry = as_of + timedelta(days=max(target_dtes) + tolerance)
    observed = _utcnow()
    key, secret = get_alpaca_credentials()
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    outcome = Outcome(requested=len(symbols))
    details: dict[str, int] = {
        "universe_symbols": len(symbols), "symbols_with_spot": 0,
        "symbols_with_options": 0, "symbols_without_options": 0,
        "symbols_without_spot": 0, "snapshot_pages": 0,
        "contract_pages": 0, "contracts_before_filters": 0,
        "contracts_after_filters": 0, "contract_metadata_failures": 0,
    }
    with requests.Session() as session, engine.begin() as conn:
        _configure_alpaca_session(
            session,
            use_system_trust_store=bool(cfg.get("use_system_trust_store", True)),
        )
        prices: dict[str, float] = {}
        for chunk in _chunks(symbols, stock_chunk_size):
            if request_pause > 0:
                time.sleep(request_pause)
            payload, status = _request_json(
                session, f"{ALPACA_DATA_URL}/v2/stocks/snapshots",
                params={"symbols": ",".join(chunk), "feed": "iex"},
                headers=headers,
            )
            if not dry:
                _raw(
                    conn, run_id, "oracle_options_indicative_snapshot", "alpaca",
                    "/v2/stocks/snapshots", "UNDERLYING:" + ",".join(chunk),
                    payload, status, observed,
                )
            if isinstance(payload, dict):
                for symbol, item in payload.items():
                    if isinstance(item, dict):
                        price = _underlying_price(item)
                        if price is not None:
                            prices[str(symbol).upper()] = price
        details["symbols_with_spot"] = len(prices)
        details["symbols_without_spot"] = len(symbols) - len(prices)

        consecutive_failures = 0
        for symbol_index, symbol in enumerate(symbols, start=1):
            spot = prices.get(symbol)
            if spot is None:
                outcome.empty += 1
                continue
            if symbol_index == 1 or symbol_index % 50 == 0:
                LOGGER.info(
                    "alpaca_options progress=%s/%s received=%s failed=%s empty=%s",
                    symbol_index, len(symbols), outcome.received,
                    outcome.failed, outcome.empty,
                )
            common_params = {
                "limit": 1000,
                "expiration_date_gte": min_expiry.isoformat(),
                "expiration_date_lte": max_expiry.isoformat(),
                "strike_price_gte": round(spot * moneyness_min, 4),
                "strike_price_lte": round(spot * moneyness_max, 4),
            }
            try:
                pages = _paginated_json(
                    session,
                    f"{ALPACA_DATA_URL}/v1beta1/options/snapshots/{symbol}",
                    params={**common_params, "feed": feed},
                    headers=headers, page_key="next_page_token",
                    max_pages=max_pages, pause_seconds=request_pause,
                )
                consecutive_failures = 0
            except Exception as exc:
                error_text = str(exc)
                if "401 Client Error" in error_text or "403 Client Error" in error_text:
                    raise RuntimeError(
                        "Accès Alpaca Options refusé; vérifier les clés et les droits du feed indicative"
                    ) from exc
                if "404 Client Error" in error_text:
                    consecutive_failures = 0
                    details["symbols_without_options"] += 1
                    outcome.empty += 1
                    continue
                outcome.failed += 1
                consecutive_failures += 1
                outcome.warnings.append(f"{symbol}: snapshots indisponibles ({exc})")
                if consecutive_failures >= max_consecutive_failures:
                    raise RuntimeError(
                        f"Alpaca options interrompu après {consecutive_failures} "
                        f"échecs consécutifs; dernier symbole={symbol}"
                    ) from exc
                continue
            details["snapshot_pages"] += len(pages)
            snapshots: dict[str, dict[str, Any]] = {}
            for page_number, (payload, status) in enumerate(pages, start=1):
                if not dry:
                    _raw(
                        conn, run_id, "oracle_options_indicative_snapshot", "alpaca",
                        "/v1beta1/options/snapshots", f"{symbol}:page:{page_number}",
                        payload, status, observed,
                    )
                block = payload.get("snapshots") or {}
                if isinstance(block, dict):
                    snapshots.update({
                        str(contract): item for contract, item in block.items()
                        if isinstance(item, dict)
                    })
            details["contracts_before_filters"] += len(snapshots)
            if not snapshots:
                details["symbols_without_options"] += 1
                outcome.empty += 1
                continue

            selected_expiries = _nearest_option_expirations(
                snapshots.keys(), target_dtes, as_of,
            )
            selected_contracts = _select_option_surface_contracts(
                snapshots, expirations=selected_expiries, spot=spot,
                moneyness_targets=moneyness_targets,
            )
            metadata: dict[str, dict[str, Any]] = {}
            if include_contract_metadata:
                try:
                    contract_pages = _paginated_json(
                        session, f"{ALPACA_PAPER_URL}/v2/options/contracts",
                        params={**common_params, "underlying_symbols": symbol},
                        headers=headers, page_key="next_page_token",
                        max_pages=max_pages, pause_seconds=request_pause,
                    )
                    details["contract_pages"] += len(contract_pages)
                    for page_number, (payload, status) in enumerate(contract_pages, start=1):
                        if not dry:
                            _raw(
                                conn, run_id, "oracle_options_indicative_snapshot", "alpaca",
                                "/v2/options/contracts", f"{symbol}:contracts:page:{page_number}",
                                payload, status, observed,
                            )
                        for item in payload.get("option_contracts") or []:
                            if isinstance(item, dict) and item.get("symbol"):
                                metadata[str(item["symbol"])] = item
                except Exception as exc:
                    error_text = str(exc)
                    if "401 Client Error" in error_text or "403 Client Error" in error_text:
                        raise RuntimeError(
                            "Accès Alpaca Options Contracts refusé; open interest non accessible"
                        ) from exc
                    details["contract_metadata_failures"] += 1
                    outcome.warnings.append(
                        f"{symbol}: open interest indisponible ({exc})"
                    )

            kept_for_symbol = 0
            for contract, item in snapshots.items():
                if contract not in selected_contracts:
                    continue
                expiry, strike, option_type = _option_contract_parts(contract)
                if expiry not in selected_expiries or strike is None or option_type is None:
                    continue
                if not _option_is_liquid(
                    item, min_bid=min_bid, max_relative_spread=max_relative_spread,
                    require_two_sided_quote=require_two_sided,
                ):
                    continue
                contract_meta = metadata.get(contract) or {}
                raw_oi = contract_meta.get("open_interest")
                try:
                    open_interest = int(raw_oi) if raw_oi is not None else None
                except (TypeError, ValueError):
                    open_interest = None
                if open_interest is None and not allow_missing_oi:
                    continue
                if open_interest is not None and open_interest < min_open_interest:
                    continue
                kept_for_symbol += 1
                outcome.received += 1
                if dry:
                    continue
                quote = item.get("latestQuote") or {}
                trade = item.get("latestTrade") or {}
                greeks = item.get("greeks") or {}
                params = {
                    "provider": "alpaca", "feed": feed, "underlying": symbol,
                    "contract": contract, "expiry": expiry, "strike": strike,
                    "otype": option_type, "observed": observed,
                    "provider_ts": _dt(quote.get("t") or trade.get("t")),
                    "bid": quote.get("bp"), "ask": quote.get("ap"),
                    "bid_size": quote.get("bs"), "ask_size": quote.get("as"),
                    "trade_price": trade.get("p"), "trade_size": trade.get("s"),
                    "iv": item.get("impliedVolatility"),
                    "delta": greeks.get("delta"), "gamma": greeks.get("gamma"),
                    "theta": greeks.get("theta"), "vega": greeks.get("vega"),
                    "open_interest": open_interest, "volume": None,
                    "hash": _hash({"snapshot": item, "contract": contract_meta}),
                    "run": run_id,
                }
                result = conn.execute(text("""INSERT IGNORE INTO stock_option_snapshots
                    (provider,feed,underlying_symbol,contract_symbol,expiration_date,strike,option_type,observed_at,available_at,provider_timestamp,bid,ask,bid_size,ask_size,trade_price,trade_size,implied_volatility,delta,gamma,theta,vega,open_interest,volume,payload_hash,run_id)
                    VALUES (:provider,:feed,:underlying,:contract,:expiry,:strike,:otype,:observed,:observed,:provider_ts,:bid,:ask,:bid_size,:ask_size,:trade_price,:trade_size,:iv,:delta,:gamma,:theta,:vega,:open_interest,:volume,:hash,:run)"""), params)
                outcome.persisted += max(0, result.rowcount)
            details["contracts_after_filters"] += kept_for_symbol
            if kept_for_symbol:
                details["symbols_with_options"] += 1
            else:
                details["symbols_without_options"] += 1
                outcome.empty += 1

    outcome.details.update(details)
    outcome.details.update({
        "feed": feed, "target_dtes": list(target_dtes),
        "moneyness_targets": list(moneyness_targets),
        "expiration_window": [min_expiry.isoformat(), max_expiry.isoformat()],
        "moneyness": [moneyness_min, moneyness_max],
        "volume_status": "not_available_in_alpaca_chain_snapshot",
    })
    if outcome.received == 0:
        raise RuntimeError("Snapshots options Alpaca vides après filtres pour tout l'univers")
    if symbols and outcome.failed / len(symbols) > max_failure_ratio:
        raise RuntimeError(
            f"Taux d'échec Alpaca options excessif: {outcome.failed}/{len(symbols)}"
        )
    return outcome


def _alpaca_opening_row(
    symbol: str,
    item: dict[str, Any],
    *,
    observed: datetime,
    cumulative_volume: int,
    run_id: str,
    feed: str,
    adjustment: str,
) -> dict[str, Any]:
    """Normalise une barre Alpaca sans confondre volume minute et cumul."""
    local_ts, utc_ts = _market_dt(item.get("t"))
    minute_volume = max(0, int(item.get("v") or 0))
    return {
        "provider": "alpaca", "feed": feed, "adjustment": adjustment,
        "symbol": symbol, "ts": utc_ts, "observed": observed,
        # Contrat PIT conservateur : disponible lorsque notre collecte l'a reçue.
        "available": observed,
        "open": item.get("o"), "high": item.get("h"),
        "low": item.get("l"), "close": item.get("c"),
        "minute": minute_volume, "cum": cumulative_volume,
        "trade_count": item.get("n"), "vwap": item.get("vw"),
        "session": "PRE" if local_ts.strftime("%H:%M") < "09:30" else "OPEN",
        "hash": _hash({"bar": item, "cumulative_volume": cumulative_volume}),
        "run": run_id,
    }


def _opening_window_single_session(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    """Collecte les barres Alpaca SIP 1 minute de 04:00 à 10:30 ET."""
    provider = str(cfg.get("provider", "alpaca")).strip().lower()
    feed = str(cfg.get("feed", "sip")).strip().lower()
    adjustment = str(cfg.get("adjustment", "raw")).strip().lower()
    if provider != "alpaca":
        raise ValueError("oracle_opening_window_sync impose provider=alpaca")
    if feed != "sip":
        raise ValueError("oracle_opening_window_sync impose feed=sip")
    if adjustment not in {"raw", "split", "dividend", "spin-off", "all"}:
        raise ValueError(f"adjustment Alpaca invalide: {adjustment}")

    symbols = _collection_symbols(cfg)
    market_tz = ZoneInfo(str(cfg.get("timezone", "America/New_York")))
    raw_session_date = cfg.get("_session_date")
    session_date = (
        date.fromisoformat(str(raw_session_date))
        if raw_session_date else datetime.now(market_tz).date()
    )
    outcome = Outcome(requested=len(symbols))
    if not is_trading_day(session_date):
        outcome.warnings.append(f"Marché NYSE fermé le {session_date}; collecte ignorée")
        outcome.details.update({"session_date": session_date.isoformat(), "market_closed": True})
        return outcome

    window_start = str(cfg.get("window_start", "04:00"))
    window_end = str(cfg.get("window_end", "10:30"))
    start_local = datetime.fromisoformat(
        f"{session_date.isoformat()}T{window_start}:00"
    ).replace(tzinfo=market_tz)
    end_local = datetime.fromisoformat(
        f"{session_date.isoformat()}T{window_end}:00"
    ).replace(tzinfo=market_tz)
    minimum_delay = int(cfg.get("minimum_sip_delay_minutes", 16))
    if datetime.now(UTC) < end_local.astimezone(UTC) + timedelta(minutes=minimum_delay):
        raise RuntimeError(
            f"SIP gratuit encore récent : attendre {minimum_delay} minutes après "
            f"{window_end} America/New_York"
        )

    chunk_size = int(cfg.get("symbol_batch_size", 100))
    max_pages = int(cfg.get("max_pages_per_batch", 20))
    if chunk_size <= 0 or max_pages <= 0:
        raise ValueError("symbol_batch_size et max_pages_per_batch doivent être positifs")
    key, secret = get_alpaca_credentials()
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    covered: set[str] = set()
    covered_open: set[str] = set()
    covered_pre: set[str] = set()
    cumulative_by_symbol: dict[str, int] = {}
    pages_count = 0
    invalid_rows = 0

    canonical_sql = text("""INSERT INTO stock_opening_window_bars
        (provider,feed,adjustment_mode,symbol,bar_timestamp,observed_at,available_at,
         open,high,low,close,cumulative_volume,minute_volume,trade_count,vwap,
         session_name,payload_hash,run_id)
        VALUES (:provider,:feed,:adjustment,:symbol,:ts,:observed,:available,
         :open,:high,:low,:close,:cum,:minute,:trade_count,:vwap,:session,:hash,:run)
        ON DUPLICATE KEY UPDATE
         open=VALUES(open),high=VALUES(high),low=VALUES(low),close=VALUES(close),
         cumulative_volume=VALUES(cumulative_volume),minute_volume=VALUES(minute_volume),
         trade_count=VALUES(trade_count),vwap=VALUES(vwap),payload_hash=VALUES(payload_hash),
         run_id=VALUES(run_id),observed_at=LEAST(observed_at,VALUES(observed_at)),
         available_at=LEAST(available_at,VALUES(available_at))""")
    version_sql = text("""INSERT IGNORE INTO stock_opening_window_bar_versions
        (provider,feed,adjustment_mode,symbol,bar_timestamp,observed_at,available_at,
         open,high,low,close,cumulative_volume,minute_volume,trade_count,vwap,
         session_name,payload_hash,run_id)
        VALUES (:provider,:feed,:adjustment,:symbol,:ts,:observed,:available,
         :open,:high,:low,:close,:cum,:minute,:trade_count,:vwap,:session,:hash,:run)""")

    with requests.Session() as session, engine.begin() as conn:
        _configure_alpaca_session(
            session,
            use_system_trust_store=bool(cfg.get("use_system_trust_store", True)),
        )
        for chunk_number, chunk in enumerate(_chunks(symbols, chunk_size), start=1):
            pages = _paginated_json(
                session, f"{ALPACA_DATA_URL}/v2/stocks/bars",
                params={
                    "symbols": ",".join(chunk), "timeframe": "1Min",
                    "start": start_local.astimezone(UTC).isoformat(),
                    "end": end_local.astimezone(UTC).isoformat(),
                    "feed": feed, "adjustment": adjustment,
                    "limit": 10000, "sort": "asc",
                }, headers=headers, page_key="next_page_token", max_pages=max_pages,
                pause_seconds=float(cfg.get("request_interval_seconds", 0.0)),
            )
            pages_count += len(pages)
            for page_number, (payload, status) in enumerate(pages, start=1):
                observed = _utcnow()
                if not dry:
                    _raw(
                        conn, run_id, "oracle_opening_window_sync", "alpaca",
                        "/v2/stocks/bars", f"{session_date}:chunk:{chunk_number}:page:{page_number}",
                        payload, status, observed,
                    )
                normalized: list[dict[str, Any]] = []
                bars = payload.get("bars") or {}
                if not isinstance(bars, dict):
                    raise RuntimeError("Réponse Alpaca sans objet bars")
                for raw_symbol, items in bars.items():
                    symbol = str(raw_symbol or "").strip().upper()
                    for item in items if isinstance(items, list) else []:
                        if not isinstance(item, dict):
                            invalid_rows += 1
                            continue
                        local_ts, _ = _market_dt(item.get("t"))
                        if not window_start <= local_ts.strftime("%H:%M") <= window_end:
                            invalid_rows += 1
                            continue
                        try:
                            opn, high, low, close = (
                                float(item[name]) for name in ("o", "h", "l", "c")
                            )
                        except (KeyError, TypeError, ValueError):
                            invalid_rows += 1
                            continue
                        if min(opn, high, low, close) <= 0 or high < max(opn, low, close) or low > min(opn, high, close):
                            invalid_rows += 1
                            continue
                        cumulative_by_symbol[symbol] = cumulative_by_symbol.get(symbol, 0) + max(0, int(item.get("v") or 0))
                        row = _alpaca_opening_row(
                            symbol, item, observed=observed,
                            cumulative_volume=cumulative_by_symbol[symbol], run_id=run_id,
                            feed=feed, adjustment=adjustment,
                        )
                        normalized.append(row)
                        covered.add(symbol)
                        (covered_pre if row["session"] == "PRE" else covered_open).add(symbol)
                outcome.received += len(normalized)
                if normalized and not dry:
                    conn.execute(version_sql, normalized)
                    conn.execute(canonical_sql, normalized)
                    outcome.persisted += len(normalized)
            LOGGER.info(
                "alpaca_opening chunks=%s covered=%s bars=%s pages=%s",
                chunk_number, len(covered), outcome.received, pages_count,
            )

    coverage = len(covered) / len(symbols) if symbols else 0.0
    open_coverage = len(covered_open) / len(symbols) if symbols else 0.0
    pre_coverage = len(covered_pre) / len(symbols) if symbols else 0.0
    outcome.empty = max(0, len(symbols) - len(covered))
    outcome.details.update({
        "session_date": session_date.isoformat(), "provider": provider, "feed": feed,
        "adjustment": adjustment, "universe_symbols": len(symbols),
        "covered_symbols": len(covered), "covered_pre_symbols": len(covered_pre),
        "covered_open_symbols": len(covered_open), "symbol_coverage": coverage,
        "premarket_symbol_coverage": pre_coverage, "open_symbol_coverage": open_coverage,
        "pages": pages_count, "invalid_rows": invalid_rows,
        "missing_symbols": sorted(set(symbols) - covered),
        "window": [window_start, window_end],
        "availability_contract": "local_collection_time_conservative",
    })
    failures: list[str] = []
    min_coverage = float(cfg.get("min_symbol_coverage", 0.75))
    min_open_coverage = float(cfg.get("min_open_symbol_coverage", 0.70))
    if coverage < min_coverage:
        failures.append(f"couverture globale {coverage:.1%} < {min_coverage:.1%}")
    if open_coverage < min_open_coverage:
        failures.append(f"couverture OPEN {open_coverage:.1%} < {min_open_coverage:.1%}")
    if invalid_rows:
        outcome.warnings.append(f"{invalid_rows} barre(s) invalides ou hors fenêtre ignorées")
    if failures:
        outcome.details["quality_gate_failures"] = failures
        if bool(cfg.get("fail_on_quality_gate", True)):
            outcome.failed = len(failures)
            if not dry:
                # ``execute`` marquera ensuite le run FAILED. On conserve ici
                # le diagnostic détaillé, que son gestionnaire d'exception ne
                # doit pas faire disparaître.
                with engine.begin() as conn:
                    conn.execute(text("""UPDATE pit_collection_runs
                        SET received_count=:received,persisted_count=:persisted,
                            empty_count=:empty,failed_count=:failed,
                            warning_count=:warnings,details_json=:details
                        WHERE run_id=:run"""), {
                        "received": outcome.received,
                        "persisted": outcome.persisted,
                        "empty": outcome.empty,
                        "failed": outcome.failed,
                        "warnings": len(outcome.warnings),
                        "details": _json(outcome.details | {"warnings": outcome.warnings}),
                        "run": run_id,
                    })
            raise RuntimeError("Qualité opening window insuffisante: " + "; ".join(failures))
        outcome.warnings.extend(failures)
    if not outcome.received:
        raise RuntimeError("Opening window Alpaca vide")
    return outcome


def _opening_window_session_complete(
    engine: Engine, cfg: dict[str, Any], session_date: date, symbol_count: int,
) -> bool:
    if symbol_count <= 0:
        return True
    market_tz = ZoneInfo(str(cfg.get("timezone", "America/New_York")))
    window_start = str(cfg.get("window_start", "04:00"))
    window_end = str(cfg.get("window_end", "10:30"))
    start_utc = datetime.fromisoformat(
        f"{session_date.isoformat()}T{window_start}:00"
    ).replace(tzinfo=market_tz).astimezone(UTC).replace(tzinfo=None)
    end_utc = datetime.fromisoformat(
        f"{session_date.isoformat()}T{window_end}:00"
    ).replace(tzinfo=market_tz).astimezone(UTC).replace(tzinfo=None)
    with engine.connect() as conn:
        covered = int(conn.execute(text("""SELECT COUNT(DISTINCT symbol)
            FROM stock_opening_window_bars
            WHERE provider=:provider AND feed=:feed AND session_name='OPEN'
              AND bar_timestamp BETWEEN :start AND :end"""), {
                "provider": str(cfg.get("provider", "alpaca")).lower(),
                "feed": str(cfg.get("feed", "sip")).lower(),
                "start": start_utc, "end": end_utc,
            }).scalar() or 0)
    return covered / symbol_count >= float(cfg.get("min_open_symbol_coverage", 0.70))


def opening_window_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    """Rattrape les séances NYSE J-N/J absentes puis agrège leurs compteurs."""
    symbols = _collection_symbols(cfg)
    market_tz = ZoneInfo(str(cfg.get("timezone", "America/New_York")))
    today = datetime.now(market_tz).date()
    lookback_days = max(0, int(cfg.get("lookback_days", 7)))
    sessions = nyse_session_dates(today - timedelta(days=lookback_days), today)
    total = Outcome(details={
        "from_date": (today - timedelta(days=lookback_days)).isoformat(),
        "to_date": today.isoformat(), "lookback_days": lookback_days,
        "sessions_considered": [item.isoformat() for item in sessions],
        "sessions_fetched": [], "sessions_skipped_existing": [],
    })
    for session_date in sessions:
        if not dry and _opening_window_session_complete(engine, cfg, session_date, len(symbols)):
            total.details["sessions_skipped_existing"].append(session_date.isoformat())
            continue
        session_cfg = dict(cfg)
        session_cfg["_session_date"] = session_date.isoformat()
        result = _opening_window_single_session(engine, session_cfg, run_id, dry)
        total.requested += result.requested
        total.received += result.received
        total.persisted += result.persisted
        total.empty += result.empty
        total.failed += result.failed
        total.warnings.extend(result.warnings)
        total.details["sessions_fetched"].append(session_date.isoformat())
        total.details.setdefault("session_details", {})[session_date.isoformat()] = result.details
    total.details["session_count"] = len(sessions)
    return total


def normalize_sec_events(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    forms = [x.strip() for x in str(cfg.get("forms", "8-K,8-K/A,6-K,6-K/A")).split(",")]
    outcome = Outcome()
    with engine.begin() as conn:
        query = text("SELECT accession_number,cik,symbol,form_type,filing_date,acceptance_datetime,available_at,content_sha256,content_text FROM sec_filing_raw WHERE form_type IN :forms AND content_text IS NOT NULL AND accession_number NOT IN (SELECT accession_number FROM sec_corporate_events)").bindparams(bindparam("forms", expanding=True))
        rows = conn.execute(query, {"forms": forms}).mappings().all()
        outcome.requested = len(rows)
        for row in rows:
            items = list(re.finditer(r"(?im)^\s*ITEM\s+(\d+\.\d+)\s*[:.\-]?\s*(.*)$", row["content_text"]))
            for index, match in enumerate(items):
                start, end = match.start(), items[index + 1].start() if index + 1 < len(items) else min(len(row["content_text"]), match.start() + 20000)
                event_text = row["content_text"][start:end]
                outcome.received += 1
                if dry: continue
                result = conn.execute(text("""INSERT IGNORE INTO sec_corporate_events
                    (accession_number,cik,symbol,form_type,item_code,event_type,event_text,filing_date,acceptance_datetime,available_at,amendment,content_sha256,run_id)
                    VALUES (:accession_number,:cik,:symbol,:form_type,:item,:etype,:event_text,:filing_date,:acceptance_datetime,:available_at,:amendment,:content_sha256,:run)"""), {**dict(row), "item": match.group(1), "etype": match.group(2)[:64], "event_text": event_text, "amendment": str(row["form_type"]).endswith("/A"), "run": run_id})
                outcome.persisted += max(0, result.rowcount)
    return outcome


def normalize_sec_ownership(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    forms = [x.strip() for x in str(cfg.get("forms", "")).split(",")]; outcome = Outcome()
    with engine.begin() as conn:
        query = text("SELECT accession_number,cik,symbol,form_type,filing_date,acceptance_datetime,available_at,content_sha256,content_text FROM sec_filing_raw WHERE form_type IN :forms AND content_text IS NOT NULL AND accession_number NOT IN (SELECT DISTINCT accession_number FROM sec_ownership_snapshots)").bindparams(bindparam("forms", expanding=True))
        rows = conn.execute(query, {"forms": forms}).mappings().all()
        outcome.requested = len(rows)
        for row in rows:
            content = row["content_text"]
            # Conservative filing-level normalization; holdings remain NULL when
            # the submission does not embed a parseable information table.
            issuers = re.findall(r"(?is)<nameofissuer>(.*?)</nameofissuer>.*?<cusip>(.*?)</cusip>.*?<value>(.*?)</value>.*?<sshprnamt>(.*?)</sshprnamt>", content)
            records = issuers or [(None, None, None, None)]
            for issuer, cusip, value, shares in records:
                outcome.received += 1
                if dry: continue
                params = {**dict(row), "issuer": re.sub(r"<[^>]+>", "", issuer or "")[:255] or None, "cusip": (cusip or "")[:16] or None, "value": float(value) * 1000 if value and str(value).strip().replace(".", "", 1).isdigit() else None, "shares": float(shares) if shares and str(shares).strip().replace(".", "", 1).isdigit() else None, "hash": _hash([issuer, cusip, value, shares]), "amendment": str(row["form_type"]).endswith("/A"), "run": run_id}
                result = conn.execute(text("""INSERT IGNORE INTO sec_ownership_snapshots
                    (accession_number,form_type,filer_cik,issuer_symbol,issuer_name,cusip,acceptance_datetime,available_at,shares,value_usd,amendment,payload_hash,run_id)
                    VALUES (:accession_number,:form_type,:cik,:symbol,:issuer,:cusip,:acceptance_datetime,:available_at,:shares,:value,:amendment,:hash,:run)"""), params)
                outcome.persisted += max(0, result.rowcount)
    return outcome


def fred_alfred_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    key = _secret(cfg, "KEY_FRED"); series = [x.strip().upper() for x in str(cfg.get("series", "")).split(",") if x.strip()]; today = date.today(); start = today - timedelta(days=int(cfg.get("observation_lookback_days", 730))); observed = _utcnow(); outcome = Outcome(requested=len(series))
    series_errors: list[dict[str, str]] = []
    with requests.Session() as session, engine.begin() as conn:
        for series_id in series:
            try:
                payload, status = _request_json(session, "https://api.stlouisfed.org/fred/series/observations", params={"series_id": series_id, "api_key": key, "file_type": "json", "observation_start": start.isoformat(), "observation_end": today.isoformat(), "realtime_start": today.isoformat(), "realtime_end": today.isoformat(), "output_type": 1})
            except Exception as exc:
                outcome.failed += 1
                series_errors.append({"series_id": series_id, "error": _safe_error_message(exc)})
                continue
            if not dry:
                _raw(conn, run_id, "fred_alfred_vintage_sync", "fred_alfred", "/fred/series/observations", series_id, payload, status, observed)
            rows = payload.get("observations", []); outcome.received += len(rows)
            if not rows: outcome.empty += 1; continue
            if dry: continue
            for item in rows:
                raw_value = item.get("value"); numeric = None if raw_value in (None, ".") else float(raw_value)
                result = conn.execute(text("""INSERT INTO macro_vintage_observations
                    (provider,series_id,observation_date,value_num,value_raw,realtime_start,realtime_end,vintage_date,observed_at,available_at,run_id)
                    VALUES ('fred_alfred',:series,:obs_date,:value,:raw,:rt_start,:rt_end,:vintage,:observed,:observed,:run)
                    ON DUPLICATE KEY UPDATE value_num=VALUES(value_num),value_raw=VALUES(value_raw),realtime_start=VALUES(realtime_start),realtime_end=VALUES(realtime_end),observed_at=VALUES(observed_at),available_at=VALUES(available_at),run_id=VALUES(run_id)"""), {"series": series_id, "obs_date": item.get("date"), "value": numeric, "raw": raw_value, "rt_start": item.get("realtime_start") or today, "rt_end": item.get("realtime_end") or today, "vintage": today, "observed": observed, "run": run_id})
                outcome.persisted += max(0, result.rowcount)
    outcome.details["series_requested"] = len(series)
    outcome.details["series_failed"] = series_errors
    if series_errors:
        outcome.warnings.append(
            f"FRED/ALFRED partiel: {len(series_errors)}/{len(series)} série(s) en échec"
        )
    if outcome.received == 0:
        raise BatchRunError("FRED/ALFRED vide pour toutes les séries demandées", outcome)
    return outcome


def latest_quotes_sync_batch(
    engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool,
) -> Outcome:
    """Rattrape les snapshots quotes manquants sur une courte fenêtre mobile.

    Le collecteur historique existant est réutilisé afin de conserver son
    contrat d'idempotence ``(symbol, quote_date)`` et sa logique de reprise par
    journées manquantes. Le batch commun apporte en plus la supervision dans
    ``pit_collection_runs`` et les notifications d'exploitation.
    """
    del engine  # La persistance canonique est gérée par sync_latest_quotes.
    from dataIntegrityEngine.sync_latest_quotes import sync_latest_quotes
    from database.cleaning_audits import record_quotes_audit_run

    symbols = _collection_symbols(cfg)
    lookback_days = max(0, int(cfg.get("lookback_days", 5)))
    batch_size = max(1, int(cfg.get("batch_size", 200)))
    timezone_name = str(cfg.get("timezone") or "America/New_York")
    to_date = datetime.now(ZoneInfo(timezone_name)).date()
    from_date = to_date - timedelta(days=lookback_days)
    source_path = str(cfg.get("symbols_file") or "").strip()
    symbol_source = f"universe-file:{source_path}"
    started_at = _utcnow()
    outcome = Outcome(
        requested=len(symbols),
        details={
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "lookback_days": lookback_days,
            "batch_size": batch_size,
            "symbol_source": symbol_source,
            "feed": "iex",
            "expected_sessions": len(nyse_session_dates(from_date, to_date)),
        },
    )
    if dry:
        return outcome

    try:
        summary = sync_latest_quotes(
            batch_size=batch_size,
            from_date=from_date,
            to_date=to_date,
            symbol_source=symbol_source,
        )
    except Exception as exc:
        outcome.failed = 1
        record_quotes_audit_run(
            run_id=run_id,
            started_at=started_at,
            finished_at=_utcnow(),
            symbols_requested=len(symbols),
            rows_upserted=0,
            status="failed",
            error_message=_safe_error_message(exc),
        )
        raise BatchRunError(
            f"Collecte latest quotes en échec: {_safe_error_message(exc)}", outcome,
        ) from exc

    outcome.requested = int(summary.get("symbols", len(symbols)))
    outcome.received = int(summary.get("rows_upserted", 0))
    outcome.persisted = outcome.received
    outcome.details["rows_upserted"] = outcome.persisted
    outcome.details["idempotent_no_new_rows"] = outcome.persisted == 0
    record_quotes_audit_run(
        run_id=run_id,
        started_at=started_at,
        finished_at=_utcnow(),
        symbols_requested=outcome.requested,
        rows_upserted=outcome.persisted,
        status="success",
        error_message=None,
    )
    return outcome


def quality_daily(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    checks = [
        ("daily_bars_sync", "business_quant", "bars_age_days", "SELECT DATEDIFF(CURRENT_DATE,MAX(trade_date)) FROM stock_bars_daily_versions WHERE provider='business_quant'", float(cfg.get("bars_max_age_days", 4)), "MAX"),
        ("security_master_snapshot", None, "security_master_age_days", "SELECT DATEDIFF(CURRENT_DATE,MAX(snapshot_date)) FROM security_master_snapshots", float(cfg.get("security_master_max_age_days", 8)), "MAX"),
        ("borrow_status_snapshot", "alpaca", "borrow_age_hours", "SELECT TIMESTAMPDIFF(HOUR,MAX(observed_at),UTC_TIMESTAMP()) FROM stock_borrow_status_snapshots", float(cfg.get("borrow_max_age_hours", 30)), "MAX"),
        ("fred_alfred_vintage_sync", "fred_alfred", "macro_age_days", "SELECT DATEDIFF(CURRENT_DATE,MAX(vintage_date)) FROM macro_vintage_observations", float(cfg.get("macro_max_age_days", 10)), "MAX"),
        ("all", None, "failed_runs_24h", FAILED_RUNS_24H_SQL, 0.0, "MAX"),
    ]
    expected_symbols = _symbols(cfg)
    outcome = Outcome(requested=len(checks) + int(bool(expected_symbols))); critical = 0
    critical_checks: list[dict[str, Any]] = []
    with engine.begin() as conn:
        for batch, provider, name, sql, threshold, direction in checks:
            value = conn.execute(text(sql)).scalar(); value_num = float(value) if value is not None else None
            ok = value_num is not None and value_num <= threshold; status = "OK" if ok else "CRITICAL"; critical += int(not ok)
            if not ok:
                critical_checks.append({"name": name, "value": value_num, "threshold": threshold})
            if not dry:
                conn.execute(text("""INSERT INTO pit_data_quality_metrics
                    (metric_date,batch_name,provider,metric_name,metric_value,threshold_value,status,details_json,run_id)
                    VALUES (CURRENT_DATE,:batch,:provider,:name,:value,:threshold,:status,:details,:run)
                    ON DUPLICATE KEY UPDATE metric_value=VALUES(metric_value),threshold_value=VALUES(threshold_value),status=VALUES(status),details_json=VALUES(details_json),run_id=VALUES(run_id)"""), {"batch": batch, "provider": provider, "name": name, "value": value_num, "threshold": threshold, "status": status, "details": _json({"direction": direction}), "run": run_id})
                if not ok:
                    conn.execute(text("""INSERT INTO pit_data_quality_issues
                        (detected_at,severity,batch_name,provider,issue_type,message,details_json,run_id)
                        VALUES (UTC_TIMESTAMP(6),'CRITICAL',:batch,:provider,:name,:message,:details,:run)"""), {"batch": batch, "provider": provider, "name": name, "message": f"{name}={value_num} seuil={threshold}", "details": _json({"value": value_num, "threshold": threshold}), "run": run_id})
            outcome.received += 1; outcome.persisted += int(not dry)
        if expected_symbols:
            query = text("""SELECT COUNT(DISTINCT symbol) FROM stock_bars_daily_versions
                WHERE provider='business_quant' AND trade_date>=CURRENT_DATE-INTERVAL 7 DAY
                AND symbol IN :symbols""").bindparams(
                    bindparam("symbols", expanding=True))
            covered = int(conn.execute(query, {"symbols": expected_symbols}).scalar() or 0)
            ratio = covered / len(expected_symbols)
            threshold = float(cfg.get("min_universe_coverage", 0.90))
            ok = ratio >= threshold; critical += int(not ok)
            if not ok:
                critical_checks.append({"name": "universe_coverage_7d", "value": ratio, "threshold": threshold})
            if not dry:
                conn.execute(text("""INSERT INTO pit_data_quality_metrics
                    (metric_date,batch_name,provider,metric_name,metric_value,threshold_value,status,details_json,run_id)
                    VALUES (CURRENT_DATE,'daily_bars_sync','business_quant','universe_coverage_7d',:value,:threshold,:status,:details,:run)
                    ON DUPLICATE KEY UPDATE metric_value=VALUES(metric_value),threshold_value=VALUES(threshold_value),
                    status=VALUES(status),details_json=VALUES(details_json),run_id=VALUES(run_id)"""),
                    {"value": ratio, "threshold": threshold, "status": "OK" if ok else "CRITICAL",
                     "details": _json({"covered": covered, "expected": len(expected_symbols)}), "run": run_id})
            outcome.received += 1; outcome.persisted += int(not dry)
    outcome.failed = critical
    outcome.details.update({"critical": critical, "critical_checks": critical_checks})
    if critical and cfg.get("fail_on_critical", True):
        raise BatchRunError(f"{critical} contrôles PIT critiques en échec", outcome)
    return outcome


def ml_artifacts_backup(
    engine: Engine,
    cfg: dict[str, Any],
    run_id: str,
    dry: bool,
) -> Outcome:
    """Archive les seuls artefacts indispensables au serving ML."""
    del engine, run_id
    from scripts.backup_ml_artifacts import backup

    source = Path(str(cfg.get("artifacts_dir") or "artifacts/models"))
    destination = Path(str(cfg.get("dest_dir") or "backups/ml"))
    if not source.is_absolute():
        source = ROOT / source
    if not destination.is_absolute():
        destination = ROOT / destination
    keep = int(cfg.get("keep", 3))
    report = backup(
        artifacts_dir=source,
        dest_dir=destination,
        keep=keep,
        dry_run=dry,
    )
    outcome = Outcome(
        requested=1,
        received=0 if report.errors else 1,
        persisted=0 if dry or report.errors else 1,
        failed=1 if report.errors else 0,
        details={
            "artifacts_dir": report.artifacts_dir,
            "dest_dir": report.dest_dir,
            "archive_path": report.archive_path,
            "archive_size_bytes": report.archive_size_bytes,
            "rotated_files": report.rotated_files,
            "kept_files": report.kept_files,
            "keep": keep,
            "excluded_non_runtime_paths": ["catboost_info"],
        },
    )
    if report.errors:
        raise BatchRunError("; ".join(report.errors), outcome)
    return outcome


def database_backup(
    engine: Engine,
    cfg: dict[str, Any],
    run_id: str,
    dry: bool,
) -> Outcome:
    """Crée un dump MySQL complet ou limité aux tables déclarées."""
    del engine, run_id
    from scripts.backup_db import backup_db

    def table_list(name: str) -> list[str]:
        value = cfg.get(name)
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    destination = Path(str(cfg.get("dest_dir") or "backups/db"))
    if not destination.is_absolute():
        destination = ROOT / destination
    keep = int(cfg.get("keep", 5))
    report = backup_db(
        host=str(cfg.get("host") or "localhost"),
        db=str(cfg.get("db") or "alpha_trade"),
        dest_dir=destination,
        keep=keep,
        archive_prefix=str(cfg.get("archive_prefix") or cfg.get("db") or "alpha_trade"),
        include_tables=table_list("include_tables"),
        exclude_tables=table_list("exclude_tables"),
        include_routines=bool(cfg.get("include_routines", True)),
        include_triggers=bool(cfg.get("include_triggers", True)),
        mysqldump_path=str(cfg.get("mysqldump_path") or "") or None,
        dry_run=dry,
    )
    outcome = Outcome(
        requested=1,
        received=0 if report.errors else 1,
        persisted=0 if dry or report.errors else 1,
        failed=1 if report.errors else 0,
        details={
            "host": report.host,
            "db": report.db,
            "dest_dir": report.dest_dir,
            "dump_path": report.dump_path,
            "dump_size_bytes": report.dump_size_bytes,
            "archive_prefix": report.archive_prefix,
            "mysqldump_path": str(cfg.get("mysqldump_path") or "PATH"),
            "include_tables": report.include_tables,
            "exclude_tables": report.exclude_tables,
            "rotated_files": report.rotated_files,
            "kept_files": report.kept_files,
            "keep": keep,
        },
    )
    if report.errors:
        raise BatchRunError("; ".join(report.errors), outcome)
    return outcome


HANDLERS: dict[str, Callable[[Engine, dict[str, Any], str, bool], Outcome]] = {
    "ml_artifacts_backup": ml_artifacts_backup,
    "db_core_backup": database_backup,
    "db_news_raw_backup": database_backup,
    "market_cap_sync": market_cap_sync,
    "latest_quotes_sync": latest_quotes_sync_batch,
    "daily_bars_sync": daily_bars_sync,
    "security_master_snapshot": security_master_snapshot,
    "corporate_actions_sync": corporate_actions_sync,
    "sec_edgar_incremental": sec_edgar_incremental,
    "pit_data_quality_daily": quality_daily,
    "borrow_status_snapshot": borrow_status_snapshot,
    "finra_short_volume_sync": finra_short_volume_sync,
    "business_quant_analyst_snapshot": business_quant_analyst_snapshot,
    "oracle_options_indicative_snapshot": options_snapshot,
    "options_delayed_bars_sync": options_delayed_bars_sync,
    "option_contract_adjustment_sync": option_contract_adjustment_sync,
    "oracle_opening_window_sync": opening_window_sync,
    "sec_corporate_events_normalize": normalize_sec_events,
    "sec_institutional_ownership_normalize": normalize_sec_ownership,
    "fred_alfred_vintage_sync": fred_alfred_sync,
}


def execute(batch_name: str, *, dry_run: bool = False, config_path: str | None = None) -> tuple[str, Outcome]:
    config = load_batch_config(config_path); cfg = config.get(batch_name)
    if not isinstance(cfg, dict): raise KeyError(f"Section {batch_name} absente de batch.yaml")
    if not cfg.get("enabled", False):
        status = str(cfg.get("status") or "DISABLED")
        return f"SKIPPED_{status}", Outcome(details={"reason": status})
    handler = HANDLERS.get(batch_name)
    if handler is None:
        if batch_name in PENDING_BATCHES: return "SKIPPED_PENDING_PROVIDER", Outcome(details={"reason": cfg.get("status")})
        raise KeyError(f"Aucun handler pour {batch_name}")
    run_id = f"{batch_name}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    engine = get_sqlalchemy_engine(); started = _utcnow()
    if not dry_run:
        with engine.begin() as conn:
            conn.execute(text("""INSERT INTO pit_collection_runs(run_id,batch_name,provider,status,started_at)
                VALUES (:run,:batch,:provider,'RUNNING',:started)"""), {"run": run_id, "batch": batch_name, "provider": str(cfg.get("provider") or cfg.get("providers") or ""), "started": started})
    try:
        outcome = handler(engine, cfg, run_id, dry_run)
        status = "DRY_RUN" if dry_run else ("COMPLETED_WITH_WARNINGS" if outcome.warnings or outcome.failed else "COMPLETED")
    except Exception as exc:
        failure_outcome = exc.outcome if isinstance(exc, BatchRunError) else Outcome(failed=1)
        if not dry_run:
            with engine.begin() as conn:
                conn.execute(text("""UPDATE pit_collection_runs
                    SET status='FAILED',finished_at=:finished,error_message=:error,
                        requested_count=:requested,received_count=:received,
                        persisted_count=:persisted,empty_count=:empty,
                        failed_count=:failed,warning_count=:warnings,
                        details_json=:details
                    WHERE run_id=:run"""), {
                    "finished": _utcnow(),
                    "error": str(exc)[:65535],
                    "requested": failure_outcome.requested,
                    "received": failure_outcome.received,
                    "persisted": failure_outcome.persisted,
                    "empty": failure_outcome.empty,
                    "failed": max(1, failure_outcome.failed),
                    "warnings": len(failure_outcome.warnings),
                    "details": _json(
                        failure_outcome.details | {"warnings": failure_outcome.warnings}
                    ),
                    "run": run_id,
                })
        raise
    if not dry_run:
        with engine.begin() as conn:
            conn.execute(text("""UPDATE pit_collection_runs SET status=:status,finished_at=:finished,requested_count=:requested,
                received_count=:received,persisted_count=:persisted,empty_count=:empty,failed_count=:failed,
                warning_count=:warnings,details_json=:details WHERE run_id=:run"""), {"status": status, "finished": _utcnow(), "requested": outcome.requested, "received": outcome.received, "persisted": outcome.persisted, "empty": outcome.empty, "failed": outcome.failed, "warnings": len(outcome.warnings), "details": _json(outcome.details | {"warnings": outcome.warnings}), "run": run_id})
    return status, outcome


def main() -> None:
    parser = argparse.ArgumentParser(description="Forward PIT batch runner")
    parser.add_argument("--batch", required=True)
    parser.add_argument("--batch-config")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(); logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        status, outcome = execute(
            args.batch, dry_run=args.dry_run, config_path=args.batch_config,
        )
    except Exception as exc:
        failure_outcome = exc.outcome if isinstance(exc, BatchRunError) else Outcome(failed=1)
        summary = {
            "batch": args.batch,
            "status": "FAILED",
            **failure_outcome.__dict__,
            "failed": max(1, failure_outcome.failed),
            "warning_count": len(failure_outcome.warnings),
            "error_message": str(exc),
        }
        print("::alpha_trade_run_summary::" + _json(summary), flush=True)
        raise
    summary = {"batch": args.batch, "status": status, **outcome.__dict__}
    print("::alpha_trade_run_summary::" + _json(summary), flush=True)


if __name__ == "__main__":
    main()
