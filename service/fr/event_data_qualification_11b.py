"""Research-only inventory of free FR event evidence. Never writes SQL."""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from bisect import bisect_left
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.request import urlopen
from zoneinfo import ZoneInfo

CATALOG = "https://www.data.gouv.fr/api/1/datasets/historique-des-positions-courtes-nettes-sur-actions-rendues-publiques-depuis-le-1er-novembre-2012/"
POSITION = "Date de debut position"
PUBLICATION = "Date de debut de publication position"
END = "Date de fin de publication position"
HOLDER = "Detenteur de la position courte nette"
ISIN = "code ISIN"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch(url: str) -> bytes:
    with urlopen(url, timeout=45) as response:
        raw = response.read(20_000_001)
    if len(raw) > 20_000_000:
        raise ValueError("Source exceeds 20 MB")
    return raw


def parse_positions(raw: bytes) -> tuple[list[dict], list[dict]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";")
    required = {POSITION, PUBLICATION, END, HOLDER, ISIN, "Ratio"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("Unexpected AMF schema")
    accepted, rejected = [], []
    for line, row in enumerate(reader, 2):
        try:
            position = date.fromisoformat(row[POSITION])
            publication = date.fromisoformat(row[PUBLICATION])
            end = date.fromisoformat(row[END]) if row[END] else None
            ratio = float(row["Ratio"].replace(",", "."))
            if not 0 <= ratio <= 100 or publication < position:
                raise ValueError("Invalid ratio or chronology")
            if end is not None and end < publication:
                raise ValueError("Publication end precedes start")
            if len(row[ISIN]) != 12 or not row[HOLDER].strip():
                raise ValueError("Missing identity")
            accepted.append({
                "isin": row[ISIN], "holder": row[HOLDER],
                "position_date": position.isoformat(),
                "publication_date": publication.isoformat(),
                "publication_end": end.isoformat() if end else None,
                "ratio_percent": ratio, "source_line": line,
                "state": "PUBLIC_THRESHOLD_CENSORED_NOT_TOTAL_SHORT_INTEREST",
                "availability_precision": "DATE_ONLY_NOT_INTRADAY_VERIFIED",
            })
        except (ValueError, TypeError) as exc:
            rejected.append({"source_line": line, "reason": str(exc), "raw": row})
    return accepted, rejected


def inventory(records: list[dict], isins: set[str]) -> dict:
    eligible = [r for r in records if "2018-01-01" <= r["publication_date"] <= "2025-12-31"]
    matched = [r for r in eligible if r["isin"] in isins]
    by_year = {}
    for year in range(2018, 2026):
        rows = [r for r in matched if r["publication_date"].startswith(str(year))]
        by_year[str(year)] = {"rows": len(rows), "isins": len({r["isin"] for r in rows})}
    keys: dict[tuple, set] = {}
    for row in matched:
        key = (row["isin"], row["holder"], row["publication_date"])
        keys.setdefault(key, set()).add((row["position_date"], row["ratio_percent"]))
    return {
        "historical_rows": len(eligible), "matched_rows": len(matched),
        "reference_isins": len(isins), "matched_isins": len({r["isin"] for r in matched}),
        "same_publication_day_ambiguous_groups": sum(len(v) > 1 for v in keys.values()),
        "by_year": by_year, "absence_state": "NOT_OBSERVED_NOT_ZERO",
        "verdict": "GO_SOURCE_QUALIFICATION_NOT_YET_DIRECTIONAL_TEST",
        "pit_limits": ["Current reconstructed export is not an archived historical vintage",
                       "Publication has day precision only; never use position date as availability",
                       "Below-threshold last disclosure is not a continuously observable position",
                       "Same-day multiple updates require a tie policy, not arbitrary row order"],
    }


def public_day(row: dict) -> str | None:
    """Latest explicit timezone-bearing transmission; never claim web availability."""
    values = []
    for key in ("uin_dat_amf", "uin_dat_mar", "informationdeposee_inf_dat_emt"):
        raw = row.get(key)
        if not raw:
            continue
        try:
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if stamp.tzinfo is not None:
            values.append(stamp)
    return max(values).astimezone(ZoneInfo("Europe/Paris")).date().isoformat() if values else None


def recent_count(days: list[str], decision: str, window: int = 7) -> int:
    """Calendar days [J-7,J); publication day is strictly excluded."""
    from datetime import timedelta
    lower = (date.fromisoformat(decision) - timedelta(days=window)).isoformat()
    return bisect_left(days, decision) - bisect_left(days, lower)


def pool_coverage(pool_path: Path, reference: list[dict], records: list[dict], metadata: list[dict], output: Path) -> dict:
    import pandas as pd

    pool = pd.read_parquet(pool_path)
    identity = {r["research_uid"]: r["isin"] for r in reference}
    amf, dila = {}, {}
    for row in records:
        if row["publication_date"] <= "2025-12-31":
            amf.setdefault(row["isin"], set()).add(row["publication_date"])
    # Count unique source IDs; French/English duplicates are not independent signals.
    seen = set()
    for row in metadata:
        day = public_day(row)
        key = (row.get("identificationsociete_iso_cd_isi"), row.get("uin_idt_uin"))
        if day and day <= "2025-12-31" and key[1] and key not in seen:
            seen.add(key)
            dila.setdefault(key[0], []).append(day)
    amf = {k: sorted(v) for k, v in amf.items()}
    dila = {k: sorted(v) for k, v in dila.items()}
    rows = []
    for item in pool.to_dict("records"):
        day = str(item["decision_session_date"])[:10]
        if day > "2025-12-31":
            raise ValueError("2026 is outside this research contract")
        isin = identity.get(item["research_uid"])
        if not isin:
            raise ValueError("OOF identity absent from reference")
        rows.append({"research_uid": item["research_uid"], "isin": isin,
                     "decision_session_date": day, "oracle_fold": item["oracle_fold"],
                     "oracle_phase": item["oracle_phase"],
                     "amf_publication_days_previous_7_calendar_days": recent_count(amf.get(isin, []), day),
                     "dila_documents_previous_7_calendar_days": recent_count(dila.get(isin, []), day),
                     "feature_status": "COVERAGE_ONLY_NOT_PIT_ADMITTED"})
    frame = pd.DataFrame(rows)
    frame.to_parquet(output / "oracle_event_coverage.parquet", index=False)
    groups = []
    for (fold, phase), group in frame.groupby(["oracle_fold", "oracle_phase"]):
        groups.append({"fold": int(fold), "phase": phase, "rows": len(group),
                       "amf_recent_rows": int((group.amf_publication_days_previous_7_calendar_days > 0).sum()),
                       "dila_recent_rows": int((group.dila_documents_previous_7_calendar_days > 0).sum())})
    return {"path": str(pool_path), "sha256": digest(pool_path.read_bytes()),
            "rows": len(frame), "groups": groups,
            "window": "Previous seven calendar days, decision day excluded",
            "verdict": "COVERAGE_ONLY_NO_TARGET_OR_PERFORMANCE_USED",
            "dila_scope": "Existing 120-issuer archive; missing issuer is uncollected, not no event"}


def run(output: Path, identities: Path, guidance: Path, pool_path: Path | None = None) -> dict:
    if output.exists():
        raise ValueError("Use a new output directory to preserve prior evidence")
    output.mkdir(parents=True)
    catalog_raw = fetch(CATALOG)
    (output / "catalog.json").write_bytes(catalog_raw)
    catalog = json.loads(catalog_raw)
    resources = [r for r in catalog["resources"] if r.get("format", "").lower() == "csv"]
    if len(resources) != 1:
        raise ValueError("AMF CSV resource ambiguous")
    url = resources[0]["url"]
    raw = fetch(url)
    (output / "amf_positions.csv").write_bytes(raw)
    records, rejected = parse_positions(raw)
    with gzip.open(identities, "rt", encoding="utf-8") as handle:
        reference = [json.loads(line) for line in handle if line.strip()]
    isins = {r["isin"] for r in reference}
    amf = inventory(records, isins)
    (output / "amf_normalized.json").write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    (output / "amf_rejected.json").write_text(json.dumps(rejected, ensure_ascii=False), encoding="utf-8")
    metadata = []
    source_hashes = {}
    for path in sorted((guidance / "metadata").glob("*.json")):
        data = path.read_bytes()
        source_hashes[str(path)] = digest(data)
        payload = json.loads(data)
        if not isinstance(payload, list):
            raise ValueError(f"Unexpected DILA export: {path}")
        metadata.extend(payload)
    matching = [r for r in metadata if r.get("identificationsociete_iso_cd_isi") in isins]
    report = {
        "schema_version": 1, "market_code": "FR_EQ",
        "observed_at": datetime.now(UTC).isoformat(),
        "status": "PARTIAL_SPRINT11_SOURCE_QUALIFICATION",
        "amf": {**amf, "all_rows": len(records), "rejected_rows": len(rejected),
                "url": url, "sha256": digest(raw), "catalog_sha256": digest(catalog_raw),
                "license": catalog.get("license")},
        "reference": {"path": str(identities), "sha256": digest(identities.read_bytes()),
                      "records": len(reference), "scope": "Reference identities, not daily tradability"},
        "dila": {"archive_files": len(source_hashes), "metadata_rows": len(metadata),
                 "matched_rows": len(matching),
                 "matched_isins": len({r["identificationsociete_iso_cd_isi"] for r in matching}),
                 "source_hashes": source_hashes,
                 "verdict": "GO_ARCHIVE_AUDIT_NOT_VERIFIED_PUBLICATION_TIME_OR_EVENT_DIRECTION"},
        "guidance": {"verdict": "SUPERVISED_PAIR_VALIDATION_REQUIRED",
                     "document": "doc/fr/poc_guidance_120_emetteurs.md",
                     "no_automatic_promotion": True},
        "training_run": False, "backtest_run": False, "canonical_writes": False,
        "remaining": ["Daily PIT join to qualified Oracle OOF",
                      "AMF vintage/correction and day-availability contract",
                      "DILA document availability and event validation",
                      "Independent validation of comparable guidance pairs",
                      "Incremental multi-fold predictive evaluation"],
    }
    report["amf"]["rejected_reasons"] = dict(Counter(r["reason"] for r in rejected))
    if pool_path:
        report["oracle_coverage"] = pool_coverage(pool_path, reference, records, metadata, output)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
