"""Audit ciblé des fichiers ESMA FIRDS FULINS_E ; aucune promotion canonique.

Les fichiers full sont des snapshots à leur date de publication. Une présence
ISIN/XPAR ne prouve pas l'absence d'interruption entre deux snapshots ; la
reconstruction as-of complète exige FULINS initial et DLTINS successifs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from service.fr.eodhd_backfill import _atomic_json


def _value(parent: ET.Element | None, path: str) -> str | None:
    item = parent.find(path) if parent is not None else None
    return item.text.strip() if item is not None and item.text else None


def extract_reference_files(archives: list[Path], target_isins: set[str],
                            expected_md5: dict[str, str]) -> tuple[list[dict], list[dict]]:
    matches = []
    files = []
    for archive in archives:
        expected = expected_md5.get(archive.name)
        if not expected:
            raise ValueError(f"checksum ESMA manquant : {archive.name}")
        actual = hashlib.md5(archive.read_bytes()).hexdigest()  # noqa: S324 - empreinte publiée ESMA
        if actual.lower() != expected.lower():
            raise ValueError(f"checksum ESMA incorrect : {archive.name}")
        file_count = 0
        with zipfile.ZipFile(archive) as compressed:
            members = compressed.namelist()
            if len(members) != 1 or not members[0].endswith(".xml"):
                raise ValueError(f"archive ESMA inattendue : {archive.name}")
            with compressed.open(members[0]) as stream:
                context = ET.iterparse(stream, events=("start", "end"))
                _, root = next(context)
                for event, element in context:
                    if event != "end" or element.tag.rsplit("}", 1)[-1] != "RefData":
                        continue
                    file_count += 1
                    attributes = element.find("{*}FinInstrmGnlAttrbts")
                    isin = _value(attributes, "{*}Id")
                    if isin in target_isins:
                        venue = element.find("{*}TradgVnRltdAttrbts")
                        matches.append({
                            "isin": isin,
                            "mic": _value(venue, "{*}Id"),
                            "currency": _value(attributes, "{*}NtnlCcy"),
                            "cfi": _value(attributes, "{*}ClssfctnTp"),
                            "name": _value(attributes, "{*}FullNm"),
                            "first_trade_reported": _value(venue, "{*}FrstTradDt"),
                            "termination_reported": _value(venue, "{*}TermntnDt"),
                            "source_file": archive.name,
                            "source_md5": actual,
                        })
                    root.clear()
        files.append({"file": archive.name, "md5": actual, "records_scanned": file_count})
    return matches, files


def summarize(subset: dict, matches: list[dict], files: list[dict]) -> dict:
    by_isin = defaultdict(list)
    for row in matches:
        by_isin[row["isin"]].append(row)
    results = []
    for item in subset["symbols"]:
        if item["status"] != "CANDIDATE_REQUIRES_EXTERNAL_PROOFS":
            continue
        evidence = by_isin[item["isin_reported"]]
        xpar = [row for row in evidence if row["mic"] == "XPAR"]
        other_mics = sorted({row["mic"] for row in evidence if row["mic"] != "XPAR" and row["mic"]})
        results.append({"symbol": item["symbol"], "isin": item["isin_reported"],
                        "provider_status_current": item["provider_status_current"],
                        "snapshot_xpar": bool(xpar), "other_mics": other_mics,
                        "reference_records": evidence,
                        "canonical_go": False})
    counts = Counter(("xpar" if row["snapshot_xpar"] else
                      "other_mic" if row["other_mics"] else "not_found") for row in results)
    by_snapshot = {}
    dates = sorted({row["file"].split("_")[2] for row in files})
    for day in dates:
        dated = defaultdict(set)
        for row in matches:
            if row["source_file"].split("_")[2] == day:
                dated[row["isin"]].add(row["mic"])
        by_snapshot[day] = {
            "xpar": sum("XPAR" in dated[row["isin"]] for row in results),
            "other_mic_only": sum(bool(dated[row["isin"]]) and
                                  "XPAR" not in dated[row["isin"]] for row in results),
            "not_found": sum(not dated[row["isin"]] for row in results),
        }
    return {"generated_at": datetime.now(UTC).isoformat(),
            "scope": "ESMA FIRDS FULINS_E snapshots only, not full historical delta reconstruction",
            "files": files, "counts": dict(counts), "by_snapshot": by_snapshot,
            "candidates_checked": len(results), "canonical_go": 0,
            "warning": "Un snapshot confirme seulement la présence ISIN/MIC à sa publication ; prix et dates PIT restent à contrôler.",
            "symbols": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", type=Path,
                        default=Path("artifacts/fr/eodhd/backfill_2016/sprint5_subset_audit.json"))
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--md5", action="append", required=True,
                        help="NomFichier.zip=empreinte_md5 publiée par ESMA")
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/fr/esma_firds/sprint5_reference_pilot.json"))
    args = parser.parse_args()
    checksums = dict(item.split("=", 1) for item in args.md5)
    subset = json.loads(args.subset.read_text(encoding="utf-8"))
    if subset.get("rule_version") != "fr_s5_subset_v1":
        raise ValueError("version du pool Sprint 5 inattendue")
    target_isins = {row["isin_reported"] for row in subset["symbols"]
                    if row["status"] == "CANDIDATE_REQUIRES_EXTERNAL_PROOFS"}
    archives = sorted(args.archives.rglob("FULINS_E_*.zip"))
    if not archives:
        raise ValueError("aucune archive ESMA FULINS_E")
    matches, files = extract_reference_files(archives, target_isins, checksums)
    report = summarize(subset, matches, files)
    _atomic_json(args.output, report)
    print(json.dumps({"files": files, "counts": report["counts"],
                      "by_snapshot": report["by_snapshot"],
                      "candidates_checked": report["candidates_checked"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
