"""Forward PIT scheduled collectors configured exclusively by batch.yaml.

Every network payload is timestamped and hashed before normalization. Empty
provider responses are failures unless a handler explicitly allows them.
"""
from __future__ import annotations

import argparse
import csv
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

import requests
from requests.adapters import HTTPAdapter
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine

from common.config_loader import load_batch_config
from database.connection import get_sqlalchemy_engine
from service.alpaca.clientAlpaca import fetch_alpaca_assets, get_alpaca_credentials

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
BQ_URL = "https://data.businessquant.com"
SEC_ARCHIVES = "https://www.sec.gov/Archives"
SEC_USER_AGENT_DEFAULT = ""
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
    raise RuntimeError(f"Echec HTTP {url}: {last}")


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
            if response.status_code == 404:
                return None, 404
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(min(20, 2 ** attempt))
                continue
            response.raise_for_status()
            return response.text, response.status_code
        except requests.RequestException as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(f"Echec HTTP {url}: {last}")


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
    observed = _utcnow(); rows: list[dict[str, Any]] = []
    with requests.Session() as session, engine.begin() as conn:
        cik_symbols = {
            str(row.cik).zfill(10): row.symbol
            for row in conn.execute(text("""SELECT s.cik,s.symbol FROM security_master_snapshots s
                JOIN (SELECT cik,MAX(snapshot_date) d FROM security_master_snapshots WHERE cik IS NOT NULL GROUP BY cik) x
                ON x.cik=s.cik AND x.d=s.snapshot_date""")).fetchall()
        }
        headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        for offset in range(int(cfg.get("lookback_days", 3)) + 1):
            day = date.today() - timedelta(days=offset)
            quarter = (day.month - 1) // 3 + 1
            url = f"{SEC_ARCHIVES}/edgar/daily-index/{day.year}/QTR{quarter}/master.{day.strftime('%Y%m%d')}.idx"
            response = session.get(url, headers=headers, timeout=60)
            if response.status_code == 404: continue
            response.raise_for_status()
            if not dry:
                _raw(conn, run_id, "sec_edgar_incremental", "sec_edgar", "/daily-index/master.idx", day.isoformat(), {"text": response.text}, response.status_code, observed)
            body = response.text.split("--------------------------------------------------------------------------------", 1)[-1]
            for line in body.splitlines():
                parts = line.split("|")
                if len(parts) != 5: continue
                cik, company, form, filing_date, filename = parts
                if allowed and form.upper() not in allowed: continue
                accession = Path(filename).stem.replace("-", "")
                accession_fmt = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}" if len(accession) >= 18 else accession
                rows.append({"cik": cik.zfill(10), "company": company, "form": form, "filing_date": filing_date, "filename": filename, "accession": accession_fmt})
        outcome.requested = int(cfg.get("lookback_days", 3)) + 1; outcome.received = len(rows)
        for item in rows:
            exists = conn.execute(text("SELECT 1 FROM sec_filing_raw WHERE accession_number=:a"), {"a": item["accession"]}).first()
            if exists: continue
            content = None; filing_url = f"{SEC_ARCHIVES}/{item['filename']}"
            if cfg.get("download_primary_documents", True) and not dry:
                response = session.get(filing_url, headers=headers, timeout=90); response.raise_for_status(); content = response.text
                time.sleep(1 / max(1, int(cfg.get("max_requests_per_second", 8))))
            acceptance = None
            if content:
                match = re.search(r"<ACCEPTANCE-DATETIME>\s*(\d{14})", content, re.I)
                if match:
                    acceptance = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
            if not dry:
                result = conn.execute(text("""INSERT IGNORE INTO sec_filing_raw
                    (accession_number,cik,symbol,company_name,form_type,filing_date,acceptance_datetime,filing_url,content_sha256,content_text,observed_at,available_at,run_id,amendment)
                    VALUES (:accession,:cik,:symbol,:company,:form,:filing_date,:acceptance,:url,:hash,:content,:observed,:observed,:run,:amendment)"""), {**item, "symbol": cik_symbols.get(item["cik"]), "acceptance": acceptance, "url": filing_url, "hash": hashlib.sha256((content or "").encode(errors="ignore")).hexdigest() if content else None, "content": content, "observed": observed, "run": run_id, "amendment": item["form"].endswith("/A")})
                outcome.persisted += max(0, result.rowcount)
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
    outcome = Outcome(requested=lookback_days)
    files_found = 0
    with requests.Session() as session, engine.begin() as conn:
        for offset in range(lookback_days):
            trade_day = market_today - timedelta(days=offset)
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
    outcome.details.update({"files_found": files_found, "universe_symbols": len(symbols)})
    if files_found == 0:
        raise RuntimeError("Aucun fichier FINRA Consolidated NMS disponible sur la fenêtre")
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


def opening_window_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    symbols = _collection_symbols(cfg); key = _secret(cfg, "BUSINESS_QUANT_API_KEY"); today = date.today(); observed = _utcnow(); outcome = Outcome(requested=len(symbols))
    with requests.Session() as session, engine.begin() as conn:
        for chunk in _chunks(symbols, 20):
            payload, status = _request_json(session, f"{BQ_URL}/quotes", params={"ticker": ",".join(chunk), "mode": "minute-bars", "from_date": today.isoformat(), "till_date": today.isoformat(), "limit": 1000, "api_key": key})
            if not dry:
                _raw(conn, run_id, "oracle_opening_window_sync", "business_quant", "/quotes:minute-bars", ",".join(chunk), payload, status, observed)
            for symbol, data, meta in _data_blocks(payload):
                resolved = str(symbol or meta.get("ticker") or "").upper(); ascending = sorted(data, key=lambda x: str(x.get("date")))
                previous = 0
                for item in ascending:
                    local_ts, utc_ts = _market_dt(item.get("date")); cumulative = int(item.get("volume") or 0); minute = max(0, cumulative - previous); previous = cumulative
                    if not (str(cfg.get("window_start", "04:00")) <= local_ts.strftime("%H:%M") <= str(cfg.get("window_end", "10:30"))): continue
                    outcome.received += 1
                    if dry: continue
                    result = conn.execute(text("""INSERT INTO stock_opening_window_bars
                        (provider,symbol,bar_timestamp,observed_at,available_at,open,high,low,close,cumulative_volume,minute_volume,session_name,payload_hash,run_id)
                        VALUES ('business_quant',:symbol,:ts,:observed,:observed,:open,:high,:low,:close,:cum,:minute,:session,:hash,:run)
                        ON DUPLICATE KEY UPDATE observed_at=VALUES(observed_at),available_at=VALUES(available_at),open=VALUES(open),high=VALUES(high),low=VALUES(low),close=VALUES(close),cumulative_volume=VALUES(cumulative_volume),minute_volume=VALUES(minute_volume),payload_hash=VALUES(payload_hash),run_id=VALUES(run_id)"""), {"symbol": resolved, "ts": utc_ts, "observed": observed, "open": item.get("open"), "high": item.get("high"), "low": item.get("low"), "close": item.get("close"), "cum": cumulative, "minute": minute, "session": "PRE" if local_ts.strftime("%H:%M") < "09:30" else "OPEN", "hash": _hash(item), "run": run_id})
                    outcome.persisted += max(0, result.rowcount)
    if not outcome.received: raise RuntimeError("Opening window vide")
    return outcome


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
    with requests.Session() as session, engine.begin() as conn:
        for series_id in series:
            payload, status = _request_json(session, "https://api.stlouisfed.org/fred/series/observations", params={"series_id": series_id, "api_key": key, "file_type": "json", "observation_start": start.isoformat(), "observation_end": today.isoformat(), "realtime_start": today.isoformat(), "realtime_end": today.isoformat(), "output_type": 1})
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
    if outcome.received == 0:
        raise RuntimeError("FRED/ALFRED vide pour toutes les séries demandées")
    return outcome


def quality_daily(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome:
    checks = [
        ("daily_bars_sync", "business_quant", "bars_age_days", "SELECT DATEDIFF(CURRENT_DATE,MAX(trade_date)) FROM stock_bars_daily_versions WHERE provider='business_quant'", float(cfg.get("bars_max_age_days", 4)), "MAX"),
        ("security_master_snapshot", None, "security_master_age_days", "SELECT DATEDIFF(CURRENT_DATE,MAX(snapshot_date)) FROM security_master_snapshots", float(cfg.get("security_master_max_age_days", 8)), "MAX"),
        ("borrow_status_snapshot", "alpaca", "borrow_age_hours", "SELECT TIMESTAMPDIFF(HOUR,MAX(observed_at),UTC_TIMESTAMP()) FROM stock_borrow_status_snapshots", float(cfg.get("borrow_max_age_hours", 30)), "MAX"),
        ("fred_alfred_vintage_sync", "fred_alfred", "macro_age_days", "SELECT DATEDIFF(CURRENT_DATE,MAX(vintage_date)) FROM macro_vintage_observations", float(cfg.get("macro_max_age_days", 10)), "MAX"),
        ("all", None, "failed_runs_24h", "SELECT COUNT(*) FROM pit_collection_runs WHERE status='FAILED' AND started_at>=UTC_TIMESTAMP()-INTERVAL 24 HOUR", 0.0, "MAX"),
    ]
    expected_symbols = _symbols(cfg)
    outcome = Outcome(requested=len(checks) + int(bool(expected_symbols))); critical = 0
    with engine.begin() as conn:
        for batch, provider, name, sql, threshold, direction in checks:
            value = conn.execute(text(sql)).scalar(); value_num = float(value) if value is not None else None
            ok = value_num is not None and value_num <= threshold; status = "OK" if ok else "CRITICAL"; critical += int(not ok)
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
            if not dry:
                conn.execute(text("""INSERT INTO pit_data_quality_metrics
                    (metric_date,batch_name,provider,metric_name,metric_value,threshold_value,status,details_json,run_id)
                    VALUES (CURRENT_DATE,'daily_bars_sync','business_quant','universe_coverage_7d',:value,:threshold,:status,:details,:run)
                    ON DUPLICATE KEY UPDATE metric_value=VALUES(metric_value),threshold_value=VALUES(threshold_value),
                    status=VALUES(status),details_json=VALUES(details_json),run_id=VALUES(run_id)"""),
                    {"value": ratio, "threshold": threshold, "status": "OK" if ok else "CRITICAL",
                     "details": _json({"covered": covered, "expected": len(expected_symbols)}), "run": run_id})
            outcome.received += 1; outcome.persisted += int(not dry)
    outcome.failed = critical; outcome.details["critical"] = critical
    if critical and cfg.get("fail_on_critical", True): raise RuntimeError(f"{critical} contrôles PIT critiques en échec")
    return outcome


HANDLERS: dict[str, Callable[[Engine, dict[str, Any], str, bool], Outcome]] = {
    "daily_bars_sync": daily_bars_sync,
    "security_master_snapshot": security_master_snapshot,
    "corporate_actions_sync": corporate_actions_sync,
    "sec_edgar_incremental": sec_edgar_incremental,
    "pit_data_quality_daily": quality_daily,
    "borrow_status_snapshot": borrow_status_snapshot,
    "finra_short_volume_sync": finra_short_volume_sync,
    "business_quant_analyst_snapshot": business_quant_analyst_snapshot,
    "oracle_options_indicative_snapshot": options_snapshot,
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
        if not dry_run:
            with engine.begin() as conn:
                conn.execute(text("UPDATE pit_collection_runs SET status='FAILED',finished_at=:finished,error_message=:error WHERE run_id=:run"), {"finished": _utcnow(), "error": str(exc)[:65535], "run": run_id})
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
    status, outcome = execute(args.batch, dry_run=args.dry_run, config_path=args.batch_config)
    summary = {"batch": args.batch, "status": status, **outcome.__dict__}
    print("::alpha_trade_run_summary::" + _json(summary))


if __name__ == "__main__":
    main()
