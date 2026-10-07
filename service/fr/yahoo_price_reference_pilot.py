"""Contre-vérification historique Yahoo des archives EODHD France.

Ce module est un outil de recherche : il ne modifie aucune table canonique et
ne transforme jamais une concordance Yahoo/EODHD en preuve PIT. Sous Windows,
le contexte TLS combine ``certifi`` et le magasin de certificats du système ;
la vérification TLS n'est jamais désactivée.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import ssl
import time
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib import parse, request

from service.fr.eodhd_backfill import _atomic_json

FIELDS = ("open", "high", "low", "close")
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def verified_tls_context() -> ssl.SSLContext:
    """Construit un contexte TLS vérifié utilisable derrière le proxy Windows."""
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:  # pragma: no cover - certifi est une dépendance du projet
        context = ssl.create_default_context()
    enum = getattr(ssl, "enum_certificates", None)
    if enum is None:
        return context
    for certificate, encoding, _trust in enum("ROOT"):
        if encoding != "x509_asn":
            continue
        try:
            context.load_verify_locations(
                cadata=ssl.DER_cert_to_PEM_cert(certificate))
        except ssl.SSLError:
            continue
    return context


def _epoch(day: date) -> int:
    return int(datetime.combine(day, dt_time.min, tzinfo=timezone.utc).timestamp())


def chart_url(symbol: str, start: date, end: date) -> str:
    if end < start:
        raise ValueError("end antérieur à start")
    params = {
        "period1": _epoch(start),
        "period2": _epoch(end + timedelta(days=1)),
        "interval": "1d",
        "events": "div,splits",
    }
    return f"{YAHOO_CHART_URL.format(symbol=parse.quote(symbol))}?{parse.urlencode(params)}"


def fetch_chart(symbol: str, start: date, end: date, *, timeout: float = 30,
                urlopen: Callable = request.urlopen) -> dict:
    req = request.Request(chart_url(symbol, start, end), headers={
        "User-Agent": "alpha-trade-fr-price-audit/0.1",
        "Accept": "application/json",
    })
    with urlopen(req, context=verified_tls_context(), timeout=timeout) as response:
        payload = json.load(response)
    error = payload.get("chart", {}).get("error")
    if error:
        raise ValueError(f"Yahoo chart error {symbol}: {error}")
    return payload


def normalize_chart(payload: dict) -> tuple[dict[str, dict], dict]:
    results = payload.get("chart", {}).get("result") or []
    if len(results) != 1:
        raise ValueError("réponse Yahoo sans résultat unique")
    result = results[0]
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    quotes = indicators.get("quote") or []
    if len(quotes) != 1:
        raise ValueError("bloc quote Yahoo absent ou ambigu")
    quote = quotes[0]
    lengths = [len(quote.get(field) or []) for field in (*FIELDS, "volume")]
    if any(length != len(timestamps) for length in lengths):
        raise ValueError("tableaux Yahoo de longueurs incohérentes")
    adjusted_blocks = indicators.get("adjclose") or []
    adjusted = adjusted_blocks[0].get("adjclose", []) if adjusted_blocks else []
    if adjusted and len(adjusted) != len(timestamps):
        raise ValueError("tableau Yahoo adjclose de longueur incohérente")
    rows: dict[str, dict] = {}
    for index, stamp in enumerate(timestamps):
        values = {field: quote[field][index] for field in FIELDS}
        if any(value is None for value in values.values()):
            continue
        day = datetime.fromtimestamp(int(stamp), tz=timezone.utc).date().isoformat()
        if day in rows:
            raise ValueError(f"date Yahoo dupliquée : {day}")
        rows[day] = {
            **{field: float(value) for field, value in values.items()},
            "volume": (None if quote["volume"][index] is None
                       else int(quote["volume"][index])),
            "adjusted_close": (float(adjusted[index]) if adjusted
                               and adjusted[index] is not None else None),
        }
    metadata = result.get("meta") or {}
    return rows, {
        "currency": metadata.get("currency"),
        "exchange_name": metadata.get("exchangeName"),
        "instrument_type": metadata.get("instrumentType"),
        "timezone": metadata.get("exchangeTimezoneName"),
    }


def compare(reference: dict[str, dict], provider_rows: list[dict], *,
            start: str, end: str, tolerance: float = 0.0001) -> dict:
    provider: dict[str, dict] = {}
    for row in provider_rows:
        day = row.get("date")
        if not isinstance(day, str) or not start <= day <= end:
            continue
        if day in provider:
            raise ValueError(f"date EODHD dupliquée : {day}")
        provider[day] = row
    common = sorted(reference.keys() & provider.keys())
    price_differences = []
    volume_differences = []
    for day in common:
        yahoo, eodhd = reference[day], provider[day]
        for field in FIELDS:
            delta = abs(yahoo[field] - float(eodhd[field]))
            if delta > tolerance:
                price_differences.append({
                    "date": day, "field": field, "yahoo": yahoo[field],
                    "eodhd": float(eodhd[field]),
                    "abs_difference": round(delta, 8),
                })
        yahoo_volume = yahoo.get("volume")
        if yahoo_volume is not None and yahoo_volume != int(eodhd.get("volume") or 0):
            volume_differences.append({
                "date": day, "yahoo": yahoo_volume,
                "eodhd": int(eodhd.get("volume") or 0),
            })
    return {
        "reference_rows": len(reference), "provider_rows": len(provider),
        "overlap_rows": len(common),
        "first_overlap": common[0] if common else None,
        "last_overlap": common[-1] if common else None,
        "yahoo_only_dates": len(reference.keys() - provider.keys()),
        "eodhd_only_dates": len(provider.keys() - reference.keys()),
        "price_difference_count": len(price_differences),
        "price_difference_examples": price_differences[:50],
        "volume_difference_count": len(volume_differences),
        "volume_difference_examples": volume_differences[:30],
        "tolerance_eur": tolerance,
    }


def audit_symbol(root: Path, cache_dir: Path, symbol: str, *, start: date,
                 end: date, timeout: float = 30, force: bool = False) -> dict:
    key = hashlib.sha256(symbol.encode("utf-8")).hexdigest()[:16]
    metadata_path = root / "symbols" / f"{key}.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"métadonnées EODHD absentes : {symbol}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("symbol") != symbol or metadata.get("status") != "COMPLETED":
        raise ValueError(f"archive EODHD incomplète : {symbol}")
    cache_path = cache_dir / f"{key}_{start.isoformat()}_{end.isoformat()}.json"
    if cache_path.is_file() and not force:
        envelope = json.loads(cache_path.read_text(encoding="utf-8"))
        payload = envelope["payload"]
        cache_status = "HIT"
    else:
        payload = fetch_chart(symbol, start, end, timeout=timeout)
        envelope = {
            "symbol": symbol, "start": start.isoformat(), "end": end.isoformat(),
            "fetched_at": datetime.now(timezone.utc).isoformat(), "payload": payload,
        }
        _atomic_json(cache_path, envelope)
        cache_status = "MISS"
    reference, yahoo_meta = normalize_chart(payload)
    bars_path = root / metadata["payloads"]["eod"]["file"]
    with gzip.open(bars_path, "rt", encoding="utf-8") as stream:
        provider_rows = json.load(stream)
    result = compare(reference, provider_rows, start=start.isoformat(),
                     end=end.isoformat())
    result.update({
        "symbol": symbol, "isin": metadata["record"].get("Isin"),
        "provider_status": metadata["record"].get("provider_status"),
        "yahoo_metadata": yahoo_meta, "cache": cache_status,
        "cache_sha256": hashlib.sha256(cache_path.read_bytes()).hexdigest(),
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path("artifacts/fr/eodhd/backfill_2016"))
    parser.add_argument("--symbols", required=True,
                        help="Codes Yahoo/EODHD séparés par une virgule")
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--cache-dir", type=Path,
                        default=Path("artifacts/fr/yahoo_daily_reference/cache"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sleep-seconds", type=float, default=1.1)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("liste de symboles vide ou dupliquée")
    reports = []
    failures = []
    for index, symbol in enumerate(symbols):
        try:
            reports.append(audit_symbol(
                args.root, args.cache_dir, symbol, start=args.start_date,
                end=args.end_date, timeout=args.timeout, force=args.force))
        except Exception as exc:  # les échecs restent visibles dans le rapport
            failures.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})
        if index + 1 < len(symbols) and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)
    output = {
        "source": "Yahoo Finance public chart endpoint",
        "start": args.start_date.isoformat(), "end": args.end_date.isoformat(),
        "requested": len(symbols), "completed": len(reports),
        "failed": len(failures), "results": reports, "failures": failures,
        "canonical_go": False,
        "limitations": [
            "Yahoo est une seconde source fournisseur, pas une preuve officielle ni PIT",
            "la concordance ne prouve pas la négociabilité pendant une suspension",
            "les prix bruts sont comparés ; adjusted_close reste diagnostique",
            "les volumes peuvent différer selon la consolidation et les corrections",
        ],
    }
    _atomic_json(args.output, output)
    print(json.dumps({key: output[key] for key in
                      ("start", "end", "requested", "completed", "failed")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
