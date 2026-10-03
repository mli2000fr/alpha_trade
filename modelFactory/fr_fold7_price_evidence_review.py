"""Rapproche les preuves demandées : ne promeut pas de barre ni de modèle."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from modelFactory.fr_eodhd_euronext_sample_audit import FIELDS, parse_reference


def comparison(reference: dict | None, provider: dict | None) -> str:
    if not reference or not provider:
        return "MISSING_PRICE_EVIDENCE"
    for field in FIELDS:
        if any(v is None or not math.isfinite(float(v)) or float(v) <= 0
               for v in (reference.get(field), provider.get(field))):
            return "MISSING_PRICE_EVIDENCE"
    return "CORROBORATED_OHLC" if all(abs(reference[f]-provider[f]) <= .0001 for f in FIELDS) else "DIFFERENT_UNRESOLVED"


def run(ledger_path: Path, collection: Path) -> dict:
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    collection_report = json.loads((collection / "report.json").read_text(encoding="utf-8"))
    collected = {r["symbol"]: r for r in collection_report["results"]}
    reference = {}
    hashes = {}
    results = []
    for row in ledger["requests"]:
        symbol, day = row["symbol"], row["date"]
        successful = collected[symbol]["collection_status"] == "COMPLETED"
        if successful and symbol not in reference:
            path = collection / f"{symbol}.history.html"
            reference[symbol] = parse_reference(path.read_text(encoding="utf-8"))
            hashes[symbol] = hashlib.sha256(path.read_bytes()).hexdigest()
        official = reference.get(symbol, {}).get(day)
        results.append({"symbol": symbol, "date": day, "isin": row["isin"],
                        "euronext": official, "eodhd": row["eodhd"], "yahoo": row["yahoo"],
                        "eodhd_state": comparison(official, row["eodhd"]),
                        "yahoo_state": comparison(official, row["yahoo"]),
                        "source_html_sha256": hashes.get(symbol),
                        "warning": "Adjusted=Y comparison, not automatic PIT tradability or canonical admission"})
    report = {"requested_pairs": len(results), "eodhd_counts": dict(Counter(r["eodhd_state"] for r in results)),
              "yahoo_counts": dict(Counter(r["yahoo_state"] for r in results)), "results": results,
              "ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
              "collection_report_sha256": hashlib.sha256((collection / "report.json").read_bytes()).hexdigest(),
              "canonical_writes": False, "repaired_rows": 0, "models_trained": 0}
    with (collection / "evidence_review.json").open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "results"}))
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--requests", type=Path, default=Path("artifacts/fr/research/fold7_repair/price_evidence_requests.json"))
    p.add_argument("--collection", type=Path, required=True)
    a = p.parse_args()
    run(a.requests, a.collection)
