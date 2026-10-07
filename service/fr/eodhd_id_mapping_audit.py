"""Snapshot et audit du mapping ISIN EODHD Paris, sans réécrire l'historique.

La réponse est une photographie actuelle : elle ne date ni IPO ni radiation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from service.fr.eodhd_backfill import _atomic_json
from service.fr.http import verified_system_session


def run(archive_root: Path, output_root: Path) -> dict:
    token = os.environ.get("EODHD_API_TOKEN")
    if not token:
        raise RuntimeError("EODHD_API_TOKEN absent")
    output_root.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_root / "id_mapping_snapshot.json"
    if snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    else:
        session = verified_system_session()
        pages = []
        offset = 0
        total = None
        try:
            while total is None or offset < total:
                response = session.get("https://eodhd.com/api/id-mapping",
                                       params={"filter[ex]": "PA", "page[limit]": 1000,
                                               "page[offset]": offset, "api_token": token,
                                               "fmt": "json"}, timeout=30)
                if not response.ok:
                    raise RuntimeError(f"ID mapping EODHD HTTP {response.status_code}")
                page = response.json()
                if not isinstance(page, dict) or not isinstance(page.get("data"), list):
                    raise RuntimeError("ID mapping EODHD invalide")
                total = int(page["meta"]["total"])
                if not page["data"]:
                    raise RuntimeError("page ID mapping vide avant total")
                pages.append(page["data"])
                offset += len(page["data"])
        finally:
            session.close()
        snapshot = {"observed_at": datetime.now(UTC).isoformat(),
                    "provider": "EODHD", "exchange_code": "PA",
                    "reported_total": total, "rows": [row for page in pages for row in page]}
        _atomic_json(snapshot_path, snapshot)
    manifest = json.loads((archive_root / "universe.json").read_text(encoding="utf-8"))
    records = [{**row, "provider_status": status} for status in ("active", "delisted")
               for row in manifest[status] if row.get("Type") == "Common Stock"
               and row.get("Currency") == "EUR" and row.get("Code")]
    mappings = defaultdict(set)
    for row in snapshot["rows"]:
        symbol = str(row.get("symbol") or "").upper()
        isin = str(row.get("isin") or "").upper()
        if symbol.endswith(".PA") and len(isin) == 12:
            mappings[symbol].add(isin)
    counts = Counter()
    resolved = []
    conflicts = []
    for record in records:
        symbol = f"{record['Code']}.PA".upper()
        original = str(record.get("Isin") or "").upper()
        candidates = sorted(mappings[symbol])
        if not original:
            counts["missing_original"] += 1
            if len(candidates) == 1:
                counts["resolved_current_mapping"] += 1
                resolved.append({"symbol": symbol, "isin": candidates[0]})
            elif not candidates:
                counts["unresolved"] += 1
            else:
                counts["ambiguous_mapping"] += 1
                conflicts.append({"symbol": symbol, "original": None, "mappings": candidates})
        elif candidates and original not in candidates:
            counts["conflicting_isin"] += 1
            conflicts.append({"symbol": symbol, "original": original, "mappings": candidates})
        elif original:
            counts["known_original"] += 1
    report = {"observed_at": snapshot["observed_at"],
              "snapshot_sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
              "provider_total": snapshot["reported_total"], "records": len(records),
              "counts": dict(counts), "resolved_current_only": resolved,
              "conflicts": conflicts,
              "warning": "Mapping actuel non PIT : aucune date de cotation/radiation/MIC n'est prouvée"}
    _atomic_json(output_root / "id_mapping_audit.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path,
                        default=Path("artifacts/fr/eodhd/backfill_2016"))
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/fr/eodhd/id_mapping_2026-10-02"))
    args = parser.parse_args()
    report = run(args.archive_root, args.output_root)
    print(json.dumps({"records": report["records"], "counts": report["counts"],
                      "report": str(args.output_root / 'id_mapping_audit.json')},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
