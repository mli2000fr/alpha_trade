"""Offline FR decision audit with issuer evidence; never authorizes shadow."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path

from common.market_calendar import get_market_calendar
from service.fr.daily_feature_adapter_16b import assemble
from service.fr.evidence_archive_16e import available, verify_record
from service.fr.observed_reference_16d import select_reference
from service.fr.prediction_contract_16a import ROOT, aware, scoped_path

REVIEW = ROOT / "config/research_fr/evidence_review_16e.json"


def evidence_at(archive: Path, review: dict, cutoff: datetime) -> dict:
    if review.get("market_code") != "FR_EQ" or review.get("serving_enabled") is not False:
        raise ValueError("FR non-serving review required")
    report_path = archive / "report.json"
    raw = report_path.read_bytes()
    report = json.loads(raw)
    if report.get("market_code") != "FR_EQ" or report.get("serving_enabled") is not False:
        raise ValueError("FR non-serving archive required")
    indexed = {row["id"]: row for row in review["records"]}
    if len(indexed) != len(review["records"]):
        raise ValueError("Duplicate evidence review ID")
    rows = []
    for source in report["records"]:
        valid = verify_record(source, archive)
        known = valid and available(source, cutoff.isoformat())
        checked = indexed.get(source["id"])
        matched = bool(valid and checked and checked["sha256"] == source["sha256"])
        # Review also has its own availability; it is not retrospectively known.
        review_known = matched and aware(review["reviewed_at"]) <= cutoff
        rows.append({"id": source["id"], "symbol": source["symbol"], "archive_valid": valid,
                     "source_known_at_decision": known, "content_review_matches": matched,
                     "review_known_at_decision": review_known,
                     "reviewed_terms_known_at_decision": bool(known and review_known),
                     "action_adjustment_qualified": False, "historical_currency_interval_qualified": False,
                     "remaining_reserves": ["NO_AUTOMATIC_ACTION_OR_CURRENCY_PROMOTION"]})
    return {"records": rows, "report_sha256": hashlib.sha256(raw).hexdigest(),
            "review_sha256": hashlib.sha256(json.dumps(review, sort_keys=True).encode()).hexdigest(),
            "archived_count": sum(row["archive_valid"] for row in rows),
            "content_reviewed_count": sum(row["content_review_matches"] for row in rows),
            "reviewed_terms_known_count": sum(row["reviewed_terms_known_at_decision"] for row in rows)}


def audit(decision_day: date, bootstrap: Path, archive: Path, *, now=None, root=ROOT, calendar=None):
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("Aware audit time required")
    calendar = calendar or get_market_calendar("FR_EQ", allow_us_weekday_fallback=False)
    cutoff = calendar.session(decision_day).open_at_utc
    if cutoff > now:
        raise ValueError("Decision has not occurred: rerun after the actual XPAR opening")
    bootstrap = scoped_path(str(bootstrap), root)
    archive = scoped_path(str(archive), root)
    assembled = assemble(decision_day, root=root, calendar=calendar, bootstrap_dir=bootstrap)
    review = json.loads((root / "config/research_fr/evidence_review_16e.json").read_text(encoding="utf-8"))
    evidence = evidence_at(archive, review, cutoff)
    reference = select_reference(cutoff.isoformat(), calendar.previous_session(decision_day),
                                 root=root, calendar=calendar, manifest=assembled["manifest"])
    return {"schema_version": 1, "market_code": "FR_EQ", "status": "DECISION_AUDITED_SHADOW_BLOCKED",
            "audit_at": now.isoformat(), "decision_at": cutoff.isoformat(),
            "daily_assembly": assembled["report"], "reference": reference, "evidence": evidence,
            "serving_allowed": False, "orders_allowed": False, "sql_writes": False,
            "next_gates": ["CURRENT_SESSION_REFERENCE_AND_DATA", "ESMA_CONTINUITY",
                           "ACTION_FEATURE_TREATMENT", "CURRENCY_EFFECTIVE_INTERVALS",
                           "INDEPENDENT_QUALIFICATION", "MODEL_RELEASE_REVIEW", "SPRINT15_RESERVES"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision-date", type=date.fromisoformat, required=True)
    parser.add_argument("--bootstrap-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed = (ROOT / "artifacts/fr/research/decision_qualification_16e").resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        parser.error("New FR decision_qualification_16e output folder required")
    report = audit(args.decision_date, args.bootstrap_dir, args.evidence_dir)
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "decision_at": report["decision_at"],
        "features_computed": report["daily_assembly"]["features_computed_count"],
        "evidence_archived": report["evidence"]["archived_count"],
        "reviewed_terms_known": report["evidence"]["reviewed_terms_known_count"], "serving_allowed": False}))


if __name__ == "__main__":
    main()
