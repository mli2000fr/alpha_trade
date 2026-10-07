"""Échantillon fixé avant comparaison, contrôle Euronext/EODHD sans écriture DB."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import random
import shutil
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib import parse, request

from service.fr.eodhd_backfill import _atomic_json
from service.fr.euronext_delisted_reference import (
    BASE_URL,
    archive_path,
    decrypt_ajax,
    parse_page_settings,
    read_eodhd,
)
from service.fr.yahoo_price_reference_pilot import verified_tls_context

FIELDS = ("open", "high", "low", "close")
ROOT = Path("artifacts/fr/eodhd/backfill_2016")


def parse_reference(html: str) -> dict:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#AwlHistoricalPriceTable")
    if table is None:
        raise ValueError("Table Euronext absente")
    headers = [c.get_text(" ", strip=True).lower() for c in table.select("thead th")]
    required = {"date", "open", "high", "low", "close", "number of shares"}
    if not required.issubset(headers) or len(headers) != len(set(headers)):
        raise ValueError(f"En-têtes ambigus/incomplets : {headers}")
    result = {}
    for row in table.select("tbody tr"):
        cells = [c.get_text(" ", strip=True) for c in row.select("td")]
        if len(cells) != len(headers):
            raise ValueError("Nombre de cellules Euronext inattendu")
        values = dict(zip(headers, cells, strict=True))
        day = datetime.strptime(values["date"], "%d/%m/%Y").date().isoformat()
        if day in result:
            raise ValueError("Date Euronext dupliquée")
        prices = {field: None if values[field] in ("", "-") else float(values[field].replace(",", ""))
                  for field in FIELDS}
        shares = values["number of shares"].replace(",", "").replace(" ", "").replace("\u00a0", "")
        prices["volume"] = None if shares in ("", "-") else int(shares)
        result[day] = prices
    return result


def choose_sample() -> list[dict]:
    with gzip.open("artifacts/fr/sprint6c_reference/identities.jsonl.gz", "rt", encoding="utf-8") as f:
        identities = list(map(json.loads, f))
    active = sorted((r for r in identities if r["provider_status_current"] == "active"),
                    key=lambda r: r["provider_symbol"])
    chosen = random.Random(20261003).sample(active, 40)
    candidates = json.loads(Path("artifacts/fr/euronext_delisted_reference/report.json").read_text(encoding="utf-8"))
    delisted = random.Random(20261004).sample(sorted(candidates["results"], key=lambda r: r["symbol"]), 10)
    return ([{"symbol": r["provider_symbol"], "isin": r["isin"], "status": "active", "mics": r["mics"]}
             for r in chosen] +
            [{"symbol": r["symbol"], "isin": r["isin"], "status": "delisted",
              "mics": [r["instrument"]["mic"]]} for r in delisted])


def compare_rows(reference: dict, provider: dict) -> tuple[dict, list[dict]]:
    """Denominators explicit: only finite strictly positive paired OHLC count."""
    common = sorted(reference.keys() & provider.keys())
    counts = Counter()
    differences = []
    by_year = {}
    for day in common:
        r, p = reference[day], provider[day]
        missing = [field for field in FIELDS if any(
            v is None or not math.isfinite(float(v)) or float(v) <= 0
            for v in (r.get(field), p.get(field)))]
        counts["overlap_rows"] += 1
        counts["unpaired_price_rows"] += bool(missing)
        if missing:
            differences.append({"date": day, "kind": "MISSING_OR_INVALID_PRICE", "fields": missing})
            continue
        year = by_year.setdefault(day[:4], Counter())
        counts["paired_price_rows"] += 1
        year["paired_price_rows"] += 1
        exact = True
        within_10bps = True
        for field in FIELDS:
            delta = abs(float(r[field])-float(p[field]))
            bps = delta / abs(float(r[field])) * 10000
            counts[f"{field}_compared"] += 1
            counts[f"{field}_match_0001eur"] += delta <= .0001
            counts[f"{field}_match_10bps"] += bps <= 10
            exact &= delta <= .0001
            within_10bps &= bps <= 10
            if delta > .0001:
                differences.append({"date": day, "kind": "PRICE", "field": field,
                                    "euronext": r[field], "eodhd": p[field], "absolute_difference": delta,
                                    "relative_bps": bps})
        for key, value in (("ohlc_match_0001eur", exact), ("ohlc_match_10bps", within_10bps)):
            counts[key] += value
            year[key] += value
        if r.get("volume") is not None and p.get("volume") is not None:
            counts["volume_compared"] += 1
            counts["volume_exact"] += r["volume"] == p["volume"]
            if r["volume"] != p["volume"]:
                differences.append({"date": day, "kind": "VOLUME", "euronext": r["volume"],
                                    "eodhd": p["volume"]})
    counts["reference_only_dates"] = len(reference.keys()-provider.keys())
    counts["eodhd_only_dates_in_reference_span"] = sum(
        min(reference) <= d <= max(reference) for d in provider.keys()-reference.keys()) if reference else 0
    return {"counts": dict(counts), "by_year": {k: dict(v) for k, v in by_year.items()},
            "first_overlap": common[0] if common else None, "last_overlap": common[-1] if common else None}, differences


def fetch(url: str, context, data: dict | None = None) -> bytes:
    req = request.Request(url, data=parse.urlencode(data).encode() if data else None,
                          headers={"User-Agent": "alpha-trade-fr-research-audit/1.0",
                                   "X-Requested-With": "XMLHttpRequest"})
    with request.urlopen(req, context=context, timeout=60) as response:
        return response.read()


def collect_one(candidate: dict, output: Path, context, *,
                start_requested: str = "2024-10-03", end_requested: str = "2026-10-02") -> dict:
    symbol, isin = candidate["symbol"], candidate["isin"]
    instrument = None
    errors = []
    for mic in candidate["mics"]:
        url = f"{BASE_URL}/en/product/equities/{isin}-{mic}"
        try:
            page = fetch(url, context)
            instrument = parse_page_settings(page.decode("utf-8"), isin)
            if instrument["mic"] != mic:
                raise ValueError("MIC inattendu")
            (output / f"{symbol}.page.html").write_bytes(page)
            break
        except Exception as exc:
            errors.append(f"{mic}: {type(exc).__name__}: {exc}")
    if instrument is None:
        raise ValueError("; ".join(errors))
    start = max(start_requested, instrument.get("date_restriction") or start_requested)
    if start > end_requested:
        raise ValueError("Fenêtre demandée hors historique public disponible")
    raw = fetch(f"{BASE_URL}/en/ajax/getHistoricalPricePopup/{instrument['product_data']}", context,
                {"adjusted": "Y", "startdate": start, "enddate": end_requested, "nbSession": "800"})
    (output / f"{symbol}.encrypted.json").write_bytes(raw)
    html = decrypt_ajax(json.loads(raw), instrument["key"])
    (output / f"{symbol}.history.html").write_text(html, encoding="utf-8")
    reference = parse_reference(html)
    if not reference:
        raise ValueError("Historique public vide")
    if any(d < start or d > end_requested for d in reference):
        raise ValueError("Réponse hors fenêtre demandée")
    path = archive_path(ROOT, symbol)
    provider = read_eodhd(path)
    metrics, differences = compare_rows(reference, provider)
    (output / f"{symbol}.differences.json").write_text(json.dumps(differences, indent=2), encoding="utf-8")
    return {**candidate, "collection_status": "COMPLETED", "instrument": instrument,
            "start": start, "reference_rows": len(reference), "euronext_adjusted_parameter": "Y",
            "euronext_raw_sha256": hashlib.sha256(raw).hexdigest(),
            "eodhd_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **metrics}


def run(output: Path, sleep: float) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    sample = choose_sample()
    (output / "sample.json").write_text(json.dumps(sample, indent=2), encoding="utf-8")
    context = verified_tls_context()
    results = []
    for candidate in sample:
        try:
            result = collect_one(candidate, output, context)
        except Exception as exc:
            result = {**candidate, "collection_status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}
        results.append(result)
        (output / "progress.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"{len(results)}/{len(sample)} {candidate['symbol']} {result['collection_status']}", flush=True)
        time.sleep(sleep)
    total = Counter()
    groups = {}
    by_year = {}
    for result in results:
        if result["collection_status"] != "COMPLETED":
            continue
        total.update(result["counts"])
        groups.setdefault(result["status"], Counter()).update(result["counts"])
        for year, counts in result["by_year"].items():
            by_year.setdefault(year, Counter()).update(counts)
    report = {"generated_at": datetime.now(UTC).isoformat(), "requested": len(sample),
              "completed": sum(r["collection_status"] == "COMPLETED" for r in results),
              "tls_verified": True, "canonical_writes": False,
              "counts": dict(total), "by_group": {k: dict(v) for k, v in groups.items()},
              "by_year": {k: dict(v) for k, v in by_year.items()}, "results": results,
              "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "limitations": ["Recent public window only; not a random sample of all French equities",
                              "Euronext adjusted=Y; price convention compatibility not proven for each corporate action",
                              "Disagreement is not automatically an EODHD error; volumes diagnostic only",
                              "2026 included only for data quality, not for model selection"]}
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("requested", "completed", "counts")}), flush=True)
    return report


def recompute(output: Path, name: str = "header_checked") -> dict:
    """Relecture hors réseau : ne modifie ni les payloads ni les rapports initiaux."""
    original = json.loads((output / "report.json").read_text(encoding="utf-8"))
    if Path(name).name != name or name in ("", ".", ".."):
        raise ValueError("Nom de sous-répertoire invalide")
    destination = output / name
    destination.mkdir(exist_ok=False)
    totals = Counter()
    groups, years, results = {}, {}, []
    for old in original["results"]:
        if old["collection_status"] != "COMPLETED":
            results.append(old)
            continue
        symbol = old["symbol"]
        reference = parse_reference((output / f"{symbol}.history.html").read_text(encoding="utf-8"))
        provider = read_eodhd(archive_path(ROOT, symbol))
        metrics, differences = compare_rows(reference, provider)
        result = {**old, **metrics}
        results.append(result)
        totals.update(metrics["counts"])
        groups.setdefault(result["status"], Counter()).update(metrics["counts"])
        for year, counts in metrics["by_year"].items():
            years.setdefault(year, Counter()).update(counts)
        (destination / f"{symbol}.differences.json").write_text(json.dumps(differences, indent=2), encoding="utf-8")
    report = {**original, "counts": dict(totals), "by_group": {k: dict(v) for k, v in groups.items()},
              "by_year": {k: dict(v) for k, v in years.items()}, "results": results,
              "header_checked": True, "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (destination / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("requested", "completed", "counts")}))
    return report


def resume_failed(previous: Path, output: Path, sleep: float, attempts: int = 2) -> dict:
    """Fixed sample, preserved evidence, bounded retries; no canonical writes."""
    if attempts < 1 or attempts > 3 or sleep < 0:
        raise ValueError("Tentatives 1..3 et délai non négatif requis")
    sample_path, report_path = previous / "sample.json", previous / "report.json"
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    original = json.loads(report_path.read_text(encoding="utf-8"))
    old = {r["symbol"]: r for r in original["results"]}
    if len(old) != len(sample) or len({r["symbol"] for r in sample}) != len(sample):
        raise ValueError("Échantillon ou bilan incomplet/dupliqué")
    for row in sample:
        if row["symbol"] not in old or any(old[row["symbol"]][k] != row[k] for k in ("isin", "status", "mics")):
            raise ValueError("Identité de l'échantillon modifiée")
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(sample_path, output / "sample.json")
    provenance = {"previous": str(previous), "sample_sha256": hashlib.sha256(sample_path.read_bytes()).hexdigest(),
                  "previous_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                  "attempts_per_failed_symbol": attempts, "sample_redrawn": False}
    _atomic_json(output / "resume_protocol.json", provenance)
    results = []
    context = None
    for candidate in sample:
        symbol = candidate["symbol"]
        old_row = old[symbol]
        if old_row["collection_status"] == "COMPLETED":
            provider_path = archive_path(ROOT, symbol)
            if hashlib.sha256(provider_path.read_bytes()).hexdigest() != old_row["eodhd_sha256"]:
                raise ValueError(f"Archive EODHD modifiée : {symbol}")
            raw = previous / f"{symbol}.encrypted.json"
            if hashlib.sha256(raw.read_bytes()).hexdigest() != old_row["euronext_raw_sha256"]:
                raise ValueError(f"Archive Euronext modifiée : {symbol}")
            # Re-decode the original response, not a potentially edited HTML cache.
            html = decrypt_ajax(json.loads(raw.read_bytes()), old_row["instrument"]["key"])
            metrics, differences = compare_rows(parse_reference(html), read_eodhd(provider_path))
            for suffix in ("page.html", "encrypted.json"):
                source = previous / f"{symbol}.{suffix}"
                if source.exists():
                    shutil.copy2(source, output / f"{symbol}.{suffix}")
            (output / f"{symbol}.history.html").write_text(html, encoding="utf-8")
            _atomic_json(output / f"{symbol}.differences.json", differences)
            result = {**old_row, **metrics, "reused_previous_success": True,
                      "previous_page_archive_present": (previous / f"{symbol}.page.html").exists()}
        else:
            context = context or verified_tls_context()
            failures = []
            result = None
            for attempt in range(1, attempts + 1):
                _atomic_json(output / "state.json", {"status": "RUNNING", "requested": len(sample),
                             "processed": len(results), "current_symbol": symbol, "attempt": attempt,
                             "updated_at": datetime.now(UTC).isoformat()})
                try:
                    result = {**collect_one(candidate, output, context), "attempts_used": attempt,
                              "previous_error": old_row.get("error"), "retry_errors": failures}
                    break
                except Exception as exc:
                    failures.append(f"{type(exc).__name__}: {exc}")
                    if attempt < attempts:
                        time.sleep(max(sleep, 3))
            if result is None:
                result = {**candidate, "collection_status": "FAILED", "error": failures[-1],
                          "retry_errors": failures, "previous_error": old_row.get("error"), "attempts_used": attempts}
            time.sleep(sleep)
        results.append(result)
        _atomic_json(output / "progress.json", results)
        print(f"{len(results)}/{len(sample)} {symbol} {result['collection_status']}", flush=True)
    totals, groups, years = Counter(), {}, {}
    for row in results:
        if row["collection_status"] != "COMPLETED":
            continue
        totals.update(row["counts"])
        groups.setdefault(row["status"], Counter()).update(row["counts"])
        for year, counts in row["by_year"].items():
            years.setdefault(year, Counter()).update(counts)
    report = {**original, "generated_at": datetime.now(UTC).isoformat(), "results": results, "requested": len(sample),
              "completed": sum(r["collection_status"] == "COMPLETED" for r in results),
              "counts": dict(totals), "by_group": {k: dict(v) for k, v in groups.items()},
              "by_year": {k: dict(v) for k, v in years.items()}, "resume": provenance,
              "header_checked": True, "canonical_writes": False,
              "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    report["failed"] = len(results) - report["completed"]
    report["status"] = "COMPLETE_SAMPLE_AUDIT" if not report["failed"] else "PARTIAL_COLLECTION_FAILURES"
    _atomic_json(output / "report.json", report)
    _atomic_json(output / "state.json", {"status": report["status"], "processed": len(results),
                 "requested": len(sample), "completed": report["completed"], "failed": report["failed"]})
    print(json.dumps({k: report[k] for k in ("status", "requested", "completed", "failed")}), flush=True)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--sleep", type=float, default=1.)
    p.add_argument("--resume-from", type=Path, help="Reprendre les échecs du même échantillon dans un nouveau dossier")
    p.add_argument("--retry-attempts", type=int, default=2)
    p.add_argument("--recompute", action="store_true")
    p.add_argument("--recompute-name", default="header_checked")
    p.add_argument("--wait-for-report", action="store_true",
                   help="Attendre au plus une heure la fin de collecte avant relecture hors réseau")
    a = p.parse_args()
    if a.resume_from:
        if a.recompute or a.wait_for_report:
            p.error("--resume-from est incompatible avec --recompute/--wait-for-report")
        resume_failed(a.resume_from, a.output, a.sleep, a.retry_attempts)
        raise SystemExit(0)
    if a.wait_for_report:
        if not a.recompute:
            p.error("--wait-for-report nécessite --recompute")
        deadline = time.monotonic() + 3600
        while not (a.output / "report.json").exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("Rapport de collecte absent après une heure")
            time.sleep(5)
    recompute(a.output, a.recompute_name) if a.recompute else run(a.output, a.sleep)
