"""Recoupe l'état FIRDS rejoué avec un Full ultérieur officiel, sans promotion."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from service.fr.eodhd_backfill import _atomic_json
from service.fr.esma_firds_history import DEFAULT_MICS, archive_records


FIELDS = ("currency", "cfi", "first_trade_reported", "termination_reported")
TIMESTAMP_FIELDS = {"first_trade_reported", "termination_reported"}


def _comparable_value(field: str, value):
    """Normalise les dates FIRDS sans confondre instant et représentation.

    Les anciens fichiers omettent parfois le suffixe UTC tandis que les Full
    plus récents ajoutent ``Z`` au même instant. Dans ce flux officiel, une
    date sans fuseau est interprétée en UTC uniquement pour la comparaison.
    """
    if field not in TIMESTAMP_FIELDS or not isinstance(value, str):
        return value
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00"
                                        if value.endswith("Z") else value)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _asof_state(history: dict, asof: date) -> tuple[dict[tuple[str, str], dict], list[dict]]:
    current = {}
    overlaps = []
    day = asof.isoformat()
    for symbol in history["symbols"]:
        for market in symbol["market_reference"]:
            applicable = [row for row in market["versions"]
                          if row["asof_from"] <= day and (row["asof_to"] is None or day <= row["asof_to"])]
            if len(applicable) > 1:
                overlaps.append({"isin": symbol["isin"], "mic": market["mic"], "date": day,
                                 "source_files": [row["source_file"] for row in applicable]})
                continue
            if applicable and applicable[0]["event"] not in {"TermntdRcrd", "CancRcrd"}:
                current[(symbol["isin"], market["mic"])] = applicable[0]
    return current, overlaps


def reconcile(history: dict, archives: list[Path], asof: date) -> dict:
    target_isins = {row["isin"] for row in history["symbols"]}
    observed = {}
    duplicates = []
    for archive in archives:
        for record in archive_records(archive, target_isins, DEFAULT_MICS):
            key = record["isin"], record["mic"]
            if key in observed:
                duplicates.append({"isin": key[0], "mic": key[1], "file": archive.name})
            else:
                observed[key] = record
    replayed, overlaps = _asof_state(history, asof)
    excluded = {(row["isin"], row["mic"]) for row in overlaps}
    keys = sorted((set(replayed) | set(observed)) - excluded)
    mismatches = []
    for key in keys:
        left = replayed.get(key)
        right = observed.get(key)
        if left is None or right is None:
            mismatches.append({"isin": key[0], "mic": key[1], "type": "missing_in_replay" if left is None else "missing_in_full"})
            continue
        differences = {
            field: {"replay": left.get(field), "full": right.get(field)}
            for field in FIELDS
            if _comparable_value(field, left.get(field))
            != _comparable_value(field, right.get(field))
        }
        if differences:
            mismatches.append({"isin": key[0], "mic": key[1], "type": "field_difference", "fields": differences})
    return {"asof": asof.isoformat(), "full_files": [path.name for path in archives],
            "full_records": len(observed), "replayed_active_records": len(replayed),
            "overlapping_replay_versions": overlaps,
            "duplicate_full_keys": duplicates, "mismatches": mismatches,
            "mismatch_types": dict(Counter(row["type"] for row in mismatches)),
            "candidate_pairs_reconciled": not (overlaps or duplicates or mismatches),
            "canonical_go": False,
            "limitations": ["Un Full recoupé ne date pas précisément un changement sur une journée sans Delta.",
                            "La concordance ISIN/MIC ne valide ni les prix ni les actions sur titres."]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--full-root", type=Path, default=Path("artifacts/fr/esma_firds/full_reconciliation_2018/2018"))
    parser.add_argument("--full-date", type=date.fromisoformat, default=date(2018, 12, 29))
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/fr/esma_firds/replay_2018/full_reconciliation_2018.json"))
    args = parser.parse_args()
    archives = sorted(args.full_root.glob(f"FULINS_E_{args.full_date:%Y%m%d}_*.zip"))
    if not archives:
        parser.error("aucun Full officiel à la date demandée")
    history = json.loads(args.history.read_text(encoding="utf-8"))
    if history["end"] < args.full_date.isoformat():
        parser.error("rejeu arrêté avant la date du Full")
    report = reconcile(history, archives, args.full_date)
    _atomic_json(args.output, report)
    print(json.dumps({key: report[key] for key in ("full_records", "replayed_active_records",
                       "mismatch_types", "candidate_pairs_reconciled")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
