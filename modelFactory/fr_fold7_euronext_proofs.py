"""Collecte ciblée des preuves de prix fold7, sans admission ou fit automatique."""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from modelFactory.fr_eodhd_euronext_sample_audit import collect_one
from service.fr.yahoo_price_reference_pilot import verified_tls_context


def run(requests_path: Path, output: Path) -> None:
    ledger = json.loads(requests_path.read_text(encoding="utf-8"))
    grouped = {}
    for row in ledger["requests"]:
        grouped.setdefault(row["symbol"], []).append(row)
    output.mkdir(parents=True, exist_ok=False)
    context = verified_tls_context()
    results = []
    for symbol, rows in sorted(grouped.items()):
        request_row = rows[0]
        candidate = {"symbol": symbol, "isin": request_row["isin"],
                     "mics": request_row["mics"], "status": "FOLD7_PRICE_PROOF_REQUEST"}
        try:
            result = collect_one(candidate, output, context,
                                 start_requested=min(r["date"] for r in rows),
                                 end_requested=max(r["date"] for r in rows))
        except Exception as exc:
            result = {**candidate, "collection_status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}
        result["requested_dates"] = [r["date"] for r in rows]
        results.append(result)
        (output / "progress.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"{len(results)}/{len(grouped)} {symbol} {result['collection_status']}", flush=True)
        time.sleep(1)
    report = {"generated_at": datetime.now(UTC).isoformat(), "tls_verified": True,
              "requested_symbols": len(grouped), "requested_pairs": ledger["requested_pairs"],
              "completed": sum(r["collection_status"] == "COMPLETED" for r in results),
              "canonical_writes": False, "repaired_rows": 0, "models_trained": 0,
              "status": "COLLECTION_FINISHED_REQUIRES_EVIDENCE_REVIEW", "results": results}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--requests", type=Path, default=Path("artifacts/fr/research/fold7_repair/price_evidence_requests.json"))
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.requests, a.output)
