"""Collecteur de recherche Eroya pour l'étude directionnelle post-Oracle.

Il ne modifie aucune table. La clé vient uniquement de EROYA_API_KEY et n'est
jamais écrite dans les logs ou les artefacts.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import gzip
import json
import logging
import os
from pathlib import Path
import re
import ssl
import sys
import time
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter

from screener.db_io import load_symbols_from_file

LOGGER = logging.getLogger(__name__)
API_BASE = "https://api.eroya.co/v1/"
DEFAULT_OUTPUT_ROOT = Path("artifacts/research/eroya_directional")


def _normalize_api_url(url_or_path: str) -> str:
    """Normalise les liens de pagination des fournisseurs derrière Eroya.

    Certains endpoints renvoient un ``next_url`` Massive/Polygon. Ce lien doit
    repasser par le proxy Eroya ; le suivre directement produit un HTTP 401 et
    transmettrait inutilement le bearer Eroya à un autre domaine. Les éventuels
    paramètres de clé présents dans un lien fournisseur sont également retirés.
    """
    raw_url = (url_or_path if url_or_path.startswith("https://")
               else urljoin(API_BASE, url_or_path))
    parts = urlsplit(raw_url)
    query = urlencode(
        [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
         if key.lower() not in {"apikey", "api_key"}],
        doseq=True,
    )
    if (parts.hostname or "").lower() in {"api.massive.com", "api.polygon.io"}:
        provider_path = re.sub(r"^/v\d+/", "/", parts.path, count=1)
        # Certaines routes SEC expérimentales exposent leur version au milieu
        # du chemin fournisseur (``/stocks/filings/vX/form-4``), tandis que le
        # proxy Eroya public utilise ``/stocks/filings/form-4``.
        provider_path = re.sub(r"/vX/", "/", provider_path, flags=re.IGNORECASE)
        proxied = urlsplit(urljoin(API_BASE, provider_path.lstrip("/")))
        return urlunsplit((proxied.scheme, proxied.netloc, proxied.path, query, ""))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _windows_trust_context() -> ssl.SSLContext:
    """Construit un contexte TLS validé avec les autorités racines Windows."""
    context = ssl.create_default_context()
    if sys.platform == "win32" and hasattr(ssl, "enum_certificates"):
        for store in ("ROOT", "CA"):
            for certificate, encoding, _trust in ssl.enum_certificates(store):
                if encoding == "x509_asn":
                    context.load_verify_locations(
                        cadata=ssl.DER_cert_to_PEM_cert(certificate))
    return context


class _SystemTrustAdapter(HTTPAdapter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._ssl_context = _windows_trust_context()
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        kwargs["ssl_context"] = self._ssl_context
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any):
        proxy_kwargs["ssl_context"] = self._ssl_context
        return super().proxy_manager_for(proxy, **proxy_kwargs)


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    name: str
    path: str
    ticker_parameter: str | None
    ticker_suffix: str = ""
    limit: int | None = None
    historical: bool = False
    pit_status: str = "unverified"
    priority: int = 3


DATASETS: dict[str, DatasetSpec] = {
    "short_interest": DatasetSpec("short_interest", "stocks/short-interest", "ticker", limit=50_000, historical=True, pit_status="publication_lag_required", priority=2),
    "short_volume": DatasetSpec("short_volume", "stocks/short-volume", "ticker", limit=50_000, historical=True, pit_status="trade_date", priority=3),
    "upgrades_downgrades": DatasetSpec("upgrades_downgrades", "fundamentals/us-upgrades-downgrades", "ticker", ".US", 100, True, "event_timestamp_to_verify", 1),
    "analyst_insights": DatasetSpec("analyst_insights", "benzinga/analyst-insights", "ticker", limit=50_000, historical=True, pit_status="last_updated_timestamp", priority=1),
    "news_recent": DatasetSpec("news_recent", "reference/news", "ticker", ".US", limit=100, historical=False, pit_status="publishedAt_current_snapshot", priority=2),
    "form4_raw": DatasetSpec("form4_raw", "stocks/filings/form-4", "tickers", limit=50_000, historical=True, pit_status="filing_date", priority=2),
    "form8k_disclosures": DatasetSpec("form8k_disclosures", "stocks/filings/8-K/disclosures", "tickers", limit=50_000, historical=True, pit_status="filing_date_plus_one_business_day", priority=1),
    "13f_raw": DatasetSpec("13f_raw", "stocks/filings/13-F", None, historical=True, pit_status="filing_timestamp_expected", priority=4),
    "options_contracts": DatasetSpec("options_contracts", "reference/options/contracts", "underlying_ticker", limit=50_000, historical=True, pit_status="as_of_contract_reference", priority=2),
    "flatfile_catalog": DatasetSpec("flatfile_catalog", "flatfiles/datasets", None, historical=False, pit_status="catalog_only", priority=3),
    "eps_trend": DatasetSpec("eps_trend", "fundamentals/us-eps-trend", "ticker", ".US", historical=False, pit_status="current_snapshot_only_until_verified", priority=1),
    "eps_revisions": DatasetSpec("eps_revisions", "fundamentals/us-eps-revisions", "ticker", ".US", historical=False, pit_status="current_snapshot_only_until_verified", priority=1),
    "recommendations": DatasetSpec("recommendations", "fundamentals/us-recommendations", "ticker", ".US", historical=False, pit_status="period_snapshot_to_verify", priority=1),
    "analyst_price_targets": DatasetSpec("analyst_price_targets", "fundamentals/us-analyst-price-targets", "ticker", ".US", historical=False, pit_status="current_snapshot_only", priority=2),
    "earnings_estimate": DatasetSpec("earnings_estimate", "fundamentals/us-earnings-estimate", "ticker", ".US", historical=True, pit_status="forecast_validity_intervals_to_verify", priority=1),
    "earnings_dates": DatasetSpec("earnings_dates", "fundamentals/us-earnings-dates", "ticker", ".US", limit=200, historical=True, pit_status="earnings_timestamp", priority=1),
    "revenue_estimate": DatasetSpec("revenue_estimate", "fundamentals/us-revenue-estimate", "ticker", ".US", historical=False, pit_status="current_snapshot_only_until_verified", priority=1),
    "growth_estimates": DatasetSpec("growth_estimates", "fundamentals/us-growth-estimates", "ticker", ".US", historical=False, pit_status="current_snapshot_only", priority=2),
    "earnings_history": DatasetSpec("earnings_history", "fundamentals/us-earnings-history", "ticker", ".US", historical=True, pit_status="event_and_publication_timestamp_to_verify", priority=2),
    "insider_transactions": DatasetSpec("insider_transactions", "fundamentals/us-insider-transactions", "ticker", ".US", 100, True, "filing_timestamp_to_verify", 1),
    "insider_purchases": DatasetSpec("insider_purchases", "fundamentals/us-insider-purchases", "ticker", ".US", historical=False, pit_status="current_trailing_snapshot", priority=2),
    "institutional_holders": DatasetSpec("institutional_holders", "fundamentals/us-institutional-holders", "ticker", ".US", 100, False, "filing_lag_and_period_to_verify", 3),
    "options_chain": DatasetSpec("options_chain", "snapshot/options/{ticker}", None, limit=2, historical=False, pit_status="current_snapshot_only", priority=3),
    "trades": DatasetSpec("trades", "trades/{ticker}", None, limit=2, historical=True, pit_status="nanosecond_timestamp", priority=4),
    "quotes": DatasetSpec("quotes", "quotes/{ticker}", None, limit=2, historical=True, pit_status="nanosecond_timestamp", priority=4),
}
DEFAULT_PROBE_DATASETS = tuple(DATASETS)
DEFAULT_COLLECTION_DATASETS = ("upgrades_downgrades", "insider_transactions", "short_interest", "short_volume", "eps_trend", "eps_revisions")


class EroyaClient:
    def __init__(self, api_key: str, *, timeout_seconds: float = 30.0,
                 max_retries: int = 3, session: requests.Session | None = None) -> None:
        if not api_key.strip():
            raise ValueError("Clé Eroya vide.")
        self._session = session or requests.Session()
        if session is None and sys.platform == "win32":
            self._session.mount("https://", _SystemTrustAdapter())
        self._session.headers.update({"Authorization": f"Bearer {api_key.strip()}", "User-Agent": "alpha-trade-eroya-directional-poc/0.1"})
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = int(max_retries)

    def get(self, url_or_path: str, *, params: dict[str, Any] | None = None) -> requests.Response:
        url = _normalize_api_url(url_or_path)
        for attempt in range(self.max_retries + 1):
            response = self._session.get(url, params=params, timeout=self.timeout_seconds)
            if response.status_code != 429 and response.status_code < 500:
                return response
            if attempt >= self.max_retries:
                return response
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 ** attempt
            time.sleep(min(delay, 30.0))
        raise AssertionError("Boucle de retry Eroya incohérente.")


def _request_for(spec: DatasetSpec, symbol: str, *, start_date: str | None,
                 end_date: str | None, probe: bool) -> tuple[str, dict[str, Any]]:
    path = spec.path.format(ticker=symbol.upper())
    params: dict[str, Any] = {}
    if spec.ticker_parameter:
        params[spec.ticker_parameter] = symbol.upper() + spec.ticker_suffix
    if spec.limit is not None:
        params["limit"] = min(spec.limit, 2) if probe else spec.limit
    if not probe and spec.name == "short_interest":
        if start_date:
            params["settlement_date.gte"] = start_date
        if end_date:
            params["settlement_date.lte"] = end_date
    if not probe and spec.name == "short_volume":
        if start_date:
            params["date.gte"] = start_date
        if end_date:
            params["date.lte"] = end_date
    if not probe and spec.name == "analyst_insights":
        if start_date:
            params["date.gte"] = start_date
        if end_date:
            params["date.lte"] = end_date
    if not probe and spec.name in {"form4_raw", "form8k_disclosures"}:
        if start_date:
            params["filing_date.gte"] = start_date
        if end_date:
            params["filing_date.lte"] = end_date
    return path, params


def _safe_error(response: requests.Response) -> str | None:
    if response.ok:
        return None
    try:
        payload = response.json()
        if isinstance(payload, dict):
            value = payload.get("error") or payload.get("message") or payload.get("detail")
            return str(value)[:500] if value is not None else f"HTTP {response.status_code}"
    except ValueError:
        pass
    return f"HTTP {response.status_code}"


def _result_count(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    results = payload.get("results")
    if isinstance(results, (list, dict)):
        return len(results)
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return len(data["items"])
    return None


def probe_entitlements(client: EroyaClient, datasets: Iterable[str], *, symbol: str = "AAPL") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in datasets:
        spec = DATASETS[name]
        path, params = _request_for(spec, symbol, start_date=None, end_date=None, probe=True)
        response = client.get(path, params=params)
        payload: Any = None
        if response.ok:
            try:
                payload = response.json()
            except ValueError:
                pass
        rows.append({"dataset": name, "priority": spec.priority, "http_status": int(response.status_code), "accessible": bool(response.ok), "result_count_sample": _result_count(payload), "has_next_page": bool(isinstance(payload, dict) and payload.get("next_url")), "historical_claimed": spec.historical, "pit_status": spec.pit_status, "error": _safe_error(response)})
    return rows


def collect_dataset(client: EroyaClient, spec: DatasetSpec, symbols: list[str],
                    destination: Path, *, start_date: str | None,
                    end_date: str | None, max_pages: int) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    requests_count = pages = successes = failures = records = 0
    statuses: dict[str, int] = {}
    request_symbols = symbols
    if spec.ticker_parameter is None and "{ticker}" not in spec.path:
        # Endpoints globaux (Form 4, 13F, catalogues) ne doivent être appelés
        # qu'une fois, indépendamment de la taille de l'univers local.
        request_symbols = ["__GLOBAL__"]
    with gzip.open(destination, "wt", encoding="utf-8") as stream:
        for symbol in request_symbols:
            path, params = _request_for(spec, symbol, start_date=start_date, end_date=end_date, probe=False)
            next_url: str | None = path
            page = 0
            while next_url and page < int(max_pages):
                response = client.get(next_url, params=params if page == 0 else None)
                requests_count += 1
                statuses[str(response.status_code)] = statuses.get(str(response.status_code), 0) + 1
                if not response.ok:
                    failures += 1
                    stream.write(json.dumps({"dataset": spec.name, "symbol_requested": symbol, "http_status": response.status_code, "error": _safe_error(response)}, ensure_ascii=False) + "\n")
                    break
                successes += 1
                payload = response.json()
                records += int(_result_count(payload) or 0)
                stream.write(json.dumps({"dataset": spec.name, "symbol_requested": symbol, "page": page + 1, "collected_at": datetime.now(timezone.utc).isoformat(), "payload": payload}, ensure_ascii=False, default=str) + "\n")
                page += 1
                pages += 1
                next_url = payload.get("next_url") if isinstance(payload, dict) else None
                params = None
    return {"dataset": spec.name, "symbols_requested": len(request_symbols), "universe_symbols": len(symbols), "requests": requests_count, "pages": pages, "successes": successes, "failures": failures, "records_reported": records, "http_status_counts": statuses, "pit_status": spec.pit_status, "artifact": str(destination.resolve())}


def _api_key() -> str:
    key = os.getenv("EROYA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("EROYA_API_KEY n'est pas visible par ce processus. Redémarrer le terminal/IHM après création de la variable, puis relancer.")
    return key


def _dataset_names(raw: str, defaults: tuple[str, ...]) -> list[str]:
    values = [value.strip() for value in raw.split(",") if value.strip()] if raw else list(defaults)
    unknown = sorted(set(values).difference(DATASETS))
    if unknown:
        raise ValueError(f"Datasets Eroya inconnus: {unknown}")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("probe", "collect"), default="probe")
    parser.add_argument("--datasets", default="")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--symbol-file", default="config/univers/ticket_mid_cap_400.txt")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--symbols-limit", type=int, default=None)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    defaults = DEFAULT_PROBE_DATASETS if args.mode == "probe" else DEFAULT_COLLECTION_DATASETS
    selected = _dataset_names(args.datasets, defaults)
    client = EroyaClient(_api_key())
    # La précision à la microseconde permet plusieurs collectes parallèles sans
    # collision de répertoire (cas normal du POC multi-datasets).
    run_id = f"eroya-{args.mode}-{datetime.now(timezone.utc):%Y%m%d%H%M%S%f}"
    output = args.output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    if args.mode == "probe":
        result: Any = probe_entitlements(client, selected, symbol=args.symbol)
        (output / "entitlement_probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        symbols = load_symbols_from_file(args.symbol_file)
        if args.symbols_limit is not None:
            if args.symbols_limit < 1:
                raise ValueError("--symbols-limit doit être positif.")
            symbols = symbols[:args.symbols_limit]
        reports = [collect_dataset(client, DATASETS[name], symbols, output / f"{name}.jsonl.gz", start_date=args.start_date, end_date=args.end_date, max_pages=args.max_pages) for name in selected]
        result = {"symbols": len(symbols), "datasets": reports}
        (output / "collection_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "contract.json").write_text(json.dumps({"run_id": run_id, "mode": args.mode, "datasets": selected, "created_at": datetime.now(timezone.utc).isoformat(), "api_key_persisted": False, "specifications": [asdict(DATASETS[name]) for name in selected]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Artefacts Eroya POC: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
