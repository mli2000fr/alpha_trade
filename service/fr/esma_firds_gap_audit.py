"""Audit hors ligne de l'index FIRDS téléchargé (preuves, pas promotion)."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from common.market_calendar import get_market_calendar
from service.fr.eodhd_backfill import _atomic_json

PART = re.compile(r"^(?:FULINS_E|DLTINS)_\d{8}_(\d+)of(\d+)\.zip$")


def audit(root: Path, *, end: date) -> dict:
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    state = json.loads((root / "download_state.json").read_text(encoding="utf-8"))
    records = [row for row in index["files"] if date.fromisoformat(row["date"]) <= end]
    state_by_name = {row["file"]: row for row in state["files"]}
    missing_files = []
    missing_evidence = []
    groups = defaultdict(list)
    for row in records:
        groups[(row["date"], row["type"])].append(row)
        if not (root / row["date"][:4] / row["file"]).is_file():
            missing_files.append(row["file"])
        if row["file"] not in state_by_name or not state_by_name[row["file"]].get("sha256"):
            missing_evidence.append(row["file"])
    incomplete_parts = []
    for (day, kind), parts in groups.items():
        numbers = set()
        totals = set()
        for part in parts:
            match = PART.fullmatch(part["file"])
            if match is None:
                incomplete_parts.append({"date": day, "type": kind, "reason": "invalid_name"})
                continue
            numbers.add(int(match[1]))
            totals.add(int(match[2]))
        if len(totals) != 1 or numbers != set(range(1, next(iter(totals)) + 1)):
            incomplete_parts.append({"date": day, "type": kind,
                                     "observed_parts": sorted(numbers), "declared_totals": sorted(totals)})

    initial = date.fromisoformat(index["full_date"])
    published_delta_days = {row["date"] for row in records if row["type"] == "DLTINS"}
    expected_sessions = set(map(str, get_market_calendar("FR_EQ").session_dates(
        (initial + timedelta(days=1)).isoformat(), end.isoformat())))
    without_delta = []
    current = initial + timedelta(days=1)
    while current <= end:
        if current.isoformat() not in published_delta_days:
            without_delta.append(current.isoformat())
        current += timedelta(days=1)
    gap_sessions = sorted(set(without_delta) & expected_sessions)
    return {
        "start": initial.isoformat(), "end": end.isoformat(),
        "files_indexed": len(records), "files_missing_on_disk": missing_files,
        "files_without_download_evidence": missing_evidence,
        "incomplete_part_groups": incomplete_parts,
        "delta_publication_gaps": without_delta,
        "delta_gaps_on_xpar_sessions": gap_sessions,
        "delta_gaps_outside_xpar_sessions": sorted(set(without_delta) - expected_sessions),
        "gaps_by_year": dict(sorted(Counter(day[:4] for day in gap_sessions).items())),
        "download_verified_as_indexed": not (missing_files or missing_evidence or state["failed"]),
        "part_groups_consistent": not incomplete_parts,
        "publication_continuity_verified": not without_delta,
        "canonical_go": False,
        "limitations": ["Un jour sans Delta indexé n'est pas un jour prouvé sans changement.",
                        "L'absence de Delta sur une séance XPAR exige un autre contrôle, notamment Full ultérieur.",
                        "La présence d'un fichier et de son SHA-256 ne valide pas les prix ni les actions sur titres."],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/fr/esma_firds/replay_2018"))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 10, 1))
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/fr/esma_firds/replay_2018/gap_audit.json"))
    args = parser.parse_args()
    report = audit(args.root, end=args.end_date)
    _atomic_json(args.output, report)
    print(json.dumps({key: report[key] for key in
                      ("files_indexed", "gaps_by_year", "download_verified_as_indexed",
                       "publication_continuity_verified")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
