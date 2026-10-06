"""Research-only exchange Dragon/Tiger observation ledger; no serving or DB writes.

An observed timestamp is evidence of *this* retrieval, never a reconstructed
historical publication timestamp. Historical-date calls remain retrospective.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from service.market.cn_dragon_tiger_pilot_15d2 import official_sse, official_szse

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _fingerprint(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def sanitize_official(sse: list[dict], szse: list[dict]) -> list[dict]:
    """Persist identifiers/reasons/hashes, not seat names or monetary fields."""
    output = []
    for source, rows in (("SSE", sse), ("SZSE", szse)):
        for row in rows:
            if row.get("exchange") != source:
                raise ValueError("Exchange mismatch")
            day = str(row.get("date") or "")
            code = str(row.get("code") or "")
            if not re.fullmatch(r"20\d\d-\d\d-\d\d", day) or not re.fullmatch(r"\d{6}", code):
                raise ValueError("Invalid event identity")
            reason = str(row.get("reason_code") if source == "SSE" else row.get("detail_reason_code") or row.get("reason") or "")
            identity = {"date": day, "exchange": source, "code": code, "reason": reason}
            output.append({**identity, "payload_sha256": _fingerprint(row)})
    output.sort(key=lambda item: (item["date"], item["exchange"], item["code"], item["reason"]))
    if len({(r["date"], r["exchange"], r["code"], r["reason"]) for r in output}) != len(output):
        raise RuntimeError("Duplicate exchange event identity")
    return output


def prior_observations(folder: Path) -> list[dict]:
    result = []
    if folder.exists():
        for path in sorted(folder.glob("snapshot-*.json")):
            item = json.loads(path.read_text(encoding="utf-8"))
            if item.get("schema") != "cn_dragon_tiger_observation_v1":
                raise RuntimeError(f"Unexpected snapshot schema: {path}")
            if int((item.get("counts") or {}).get("events", -1)) != len(item.get("events") or []):
                raise RuntimeError(f"Snapshot event count mismatch: {path}")
            result.append(item)
    return result


def build_snapshot(day: date, sse: list[dict], szse: list[dict],
                   prior: list[dict], observed_at: datetime,
                   provenance: dict, collection_context: dict | None = None) -> dict:
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")
    stamp = observed_at.astimezone(timezone.utc).isoformat()
    rows = sanitize_official(sse, szse)
    if any(row["date"] != day.isoformat() for row in rows):
        raise ValueError("Event date mismatch")
    today_shanghai = observed_at.astimezone(SHANGHAI).date()
    if day > today_shanghai:
        raise ValueError("Future exchange session cannot be observed")
    retrospective = day < today_shanghai
    first_seen = {}
    previous_rows = {}
    for snapshot in prior:
        if snapshot.get("trade_date") != day.isoformat():
            raise RuntimeError("Prior snapshot belongs to another session")
        for old in snapshot.get("events", []):
            key = (old["date"], old["exchange"], old["code"], old["reason"])
            first_seen[key] = min(first_seen.get(key, old["first_seen_at_utc"]),
                                  old["first_seen_at_utc"])
    if prior:
        previous_rows = {
            (old["date"], old["exchange"], old["code"], old["reason"]): old
            for old in prior[-1].get("events", [])
        }
    new_keys = set()
    changed = 0
    for row in rows:
        key = (row["date"], row["exchange"], row["code"], row["reason"])
        new_keys.add(key)
        old = previous_rows.get(key)
        row["first_seen_at_utc"] = first_seen.get(key, stamp)
        if old is not None and old["payload_sha256"] != row["payload_sha256"]:
            changed += 1
    snapshot = {
        "schema": "cn_dragon_tiger_observation_v1",
        "trade_date": day.isoformat(), "observed_at_utc": stamp,
        "retrospective": retrospective,
        "pit_usable": False,
        "pit_note": "Observation timestamp is not exchange publication time; live use requires separate decision-time checks and rights clearance.",
        "source": "SSE_SSE_STAR_SZSE_OFFICIAL",
        "provenance": provenance,
        "counts": {"events": len(rows), "first_seen": len(new_keys - set(first_seen)),
                   "removed_since_last": len(set(previous_rows) - new_keys),
                   "changed_payload_since_last": changed},
        "events": rows,
    }
    if collection_context is not None:
        snapshot["collection_context"] = collection_context
    return snapshot


def run(day: date, root: Path, *, collection_context: dict | None = None) -> Path:
    folder = root / day.isoformat()
    prior = prior_observations(folder)
    sse, sse_meta = official_sse(day.isoformat())
    szse, szse_meta = official_szse(day.isoformat())
    observed_at = datetime.now(timezone.utc)
    snapshot = build_snapshot(day, sse, szse, prior, observed_at,
                              {"sse": sse_meta, "szse": szse_meta},
                              collection_context=collection_context)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"snapshot-{observed_at.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(snapshot, stream, ensure_ascii=False, indent=2)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/research/cn_dragon_tiger_15d5/observations"))
    args = parser.parse_args()
    path = run(args.date, args.output_root)
    print(path)


if __name__ == "__main__":
    main()
