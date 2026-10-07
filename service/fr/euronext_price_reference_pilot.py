"""Compare un export CSV individuel Euronext à une archive EODHD, sans import DB.

L'export public Euronext couvre une fenêtre récente et ne valide pas les barres
historiques antérieures. Les colonnes comparées sont des prix OHLC bruts ; le
volume n'est comparé que si l'appelant atteste l'absence de split dans la fenêtre.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path

from service.fr.eodhd_backfill import _atomic_json

FIELDS = ("open", "high", "low", "close")


def read_euronext(path: Path) -> dict[str, dict]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if len(lines) < 5 or lines[0] != '"Historical Data"':
        raise ValueError("export historique Euronext inattendu")
    records: dict[str, dict] = {}
    for row in csv.DictReader(lines[3:], delimiter=";"):
        day = datetime.strptime(row["Date"], "%d/%m/%Y").date().isoformat()
        if day in records:
            raise ValueError(f"date Euronext dupliquée : {day}")
        records[day] = {
            "open": float(row["Open"]), "high": float(row["High"]),
            "low": float(row["Low"]), "close": float(row["Close"]),
            "shares": int(row["Number of Shares"]),
        }
    return records


def audit(euronext_path: Path, eodhd_path: Path, *, isin: str,
          tolerance: float = 0.0001, compare_volume: bool = False) -> dict:
    reference = read_euronext(euronext_path)
    with gzip.open(eodhd_path, "rt", encoding="utf-8") as stream:
        rows = json.load(stream)
    provider = {}
    for row in rows:
        day = row["date"]
        if day in provider:
            raise ValueError(f"date EODHD dupliquée : {day}")
        provider[day] = row
    common = sorted(reference.keys() & provider.keys())
    differences = []
    for day in common:
        ref, got = reference[day], provider[day]
        for field in FIELDS:
            delta = abs(ref[field] - float(got[field]))
            if delta > tolerance:
                differences.append({"date": day, "field": field,
                                    "euronext": ref[field], "eodhd": got[field],
                                    "abs_difference": round(delta, 8)})
        if compare_volume and ref["shares"] != int(got["volume"]):
            differences.append({"date": day, "field": "volume",
                                "euronext": ref["shares"],
                                "eodhd": int(got["volume"])})
    return {
        "isin": isin,
        "euronext_sha256": hashlib.sha256(euronext_path.read_bytes()).hexdigest(),
        "eodhd_sha256": hashlib.sha256(eodhd_path.read_bytes()).hexdigest(),
        "reference_rows": len(reference), "provider_rows": len(provider),
        "overlap_rows": len(common), "first_overlap": common[0] if common else None,
        "last_overlap": common[-1] if common else None,
        "euronext_only_dates": len(reference.keys() - provider.keys()),
        "eodhd_only_dates": len(provider.keys() - reference.keys()),
        "tolerance_eur": tolerance, "volume_compared": compare_volume,
        "difference_count": len(differences), "difference_examples": differences[:30],
        "scope_warning": "Vérification de cet ISIN et de la fenêtre CSV uniquement, pas de validation PIT ni des autres titres.",
        "canonical_go": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--euronext-csv", type=Path, required=True)
    parser.add_argument("--eodhd-gzip", type=Path, required=True)
    parser.add_argument("--isin", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare-volume", action="store_true")
    args = parser.parse_args()
    report = audit(args.euronext_csv, args.eodhd_gzip, isin=args.isin,
                   compare_volume=args.compare_volume)
    _atomic_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
