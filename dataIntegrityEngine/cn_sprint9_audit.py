"""Auditer les huit artefacts annuels de features CN du Sprint 9."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from modelFactory.cn_feature_panel import ROOT


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(root: Path, *, start_year: int = 2018, end_year: int = 2025) -> dict[str, Any]:
    profiles = root / "cn_price_v1"
    current_implementation = _sha256(ROOT / "modelFactory" / "cn_feature_panel.py")
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    schema_hashes: set[str] = set()
    for year in range(start_year, end_year + 1):
        matches: list[tuple[Path, dict[str, Any]]] = []
        for path in profiles.glob(f"cn-feature-{year}0101-{year}1231-*/report.json"):
            report = json.loads(path.read_text(encoding="utf-8"))
            if report.get("implementation_sha256") == current_implementation:
                matches.append((path, report))
        if len(matches) != 1:
            errors.append(f"{year}: {len(matches)} artefact(s) de l'implémentation courante")
            continue
        report_path, report = matches[0]
        panel_path = report_path.parent / "panel.parquet"
        if not panel_path.exists() or _sha256(panel_path) != report.get("panel_sha256"):
            errors.append(f"{year}: Parquet absent ou SHA différent")
        quality = report.get("quality") or {}
        if quality.get("duplicate_keys") or quality.get("late_source_rows"):
            errors.append(f"{year}: doublon ou information tardive")
        if not quality.get("research_ready_price_only"):
            errors.append(f"{year}: couverture prix/benchmark insuffisante")
        schema_hashes.add(str(report.get("feature_schema_fingerprint")))
        entries.append({
            "year": year, "rows": report.get("rows"), "sessions": report.get("sessions"),
            "instruments": report.get("instruments"),
            "price20_coverage": quality.get("price20_coverage"),
            "benchmark_coverage": quality.get("benchmark_coverage"),
            "position_52w_coverage": round(1 - report["missing_fraction"]["position_52w"], 6),
            "sector_coverage": report.get("sector_membership_coverage"),
            "boards": report.get("board_counts"), "panel_sha256": report.get("panel_sha256"),
            "report": str(report_path),
        })
    if len(schema_hashes) > 1:
        errors.append("Empreintes de schéma divergentes entre années")
    return {
        "status": "PASS_PRICE_ONLY" if not errors else "INCOMPLETE_OR_FAILED",
        "implementation_sha256": current_implementation,
        "years_expected": end_year - start_year + 1, "years_found": len(entries),
        "total_rows": sum(int(item["rows"] or 0) for item in entries),
        "yearly": entries, "errors": errors,
        "sector_pit_ready": False, "turnover_rate_ready": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts" / "cn" / "features")
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--report-path", type=Path)
    args = parser.parse_args()
    result = audit(args.output_root, start_year=args.start_year, end_year=args.end_year)
    report_path = args.report_path or args.output_root / f"sprint9_audit_{args.start_year}_{args.end_year}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS_PRICE_ONLY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
