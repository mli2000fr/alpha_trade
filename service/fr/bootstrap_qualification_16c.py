"""Audit completed FR warmup as observed now; NOT an opening decision replay."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from common.market_calendar import get_market_calendar
from modelFactory.fr_feature_panel import compute_symbol_features
from service.fr.daily_feature_adapter_16b import (
    action_checks, identity_reasons, master_at, observed_payloads, read_json, select_bars,
)
from service.fr.prediction_contract_16a import ROOT, FEATURES, aware, prepare_manifest, scoped_path


def qualify(bootstrap: Path, *, root: Path = ROOT, audit_at: datetime | None = None,
            calendar=None, manifest=None) -> dict:
    root = root.resolve()
    bootstrap = scoped_path(str(bootstrap), root)
    audit_at = audit_at or datetime.now(UTC)
    if audit_at.tzinfo is None:
        raise ValueError("Explicit audit timezone required")
    proofs = {}
    collection = read_json(bootstrap / "report.json", root, proofs)
    if collection.get("market_code") != "FR_EQ" or collection.get("status") not in (
        "COLLECTED_PENDING_QUALIFICATION", "PARTIAL_COLLECTION"
    ):
        raise ValueError("Completed FR collection required")
    if aware(collection["finished_at"]) > audit_at:
        raise ValueError("Collection unavailable at audit cutoff")
    feature_day = date.fromisoformat(collection["end_date"])
    calendar = calendar or get_market_calendar("FR_EQ", allow_us_weekday_fallback=False)
    if calendar.session(feature_day).close_at_utc > audit_at:
        raise ValueError("Feature session not closed at audit time")
    sessions = calendar.session_dates(calendar.previous_session(feature_day, 20), feature_day)
    if len(sessions) != 21:
        raise ValueError("21 sessions required")
    manifest = manifest or prepare_manifest(root=root)
    bars, bar_errors = observed_payloads(bootstrap / "eodhd_daily", audit_at, root, proofs)
    actions, action_errors = observed_payloads(bootstrap / "corporate_actions", audit_at, root, proofs)
    master, master_reasons, master_errors = master_at(
        root / "artifacts/fr/operations/fr_security_master_sync", audit_at, feature_day, root, proofs)
    diagnostics, features = [], []
    counts = Counter()
    for identity in manifest["universe"]:
        symbol = identity["provider_symbol"]
        reasons = []
        values = None
        missing = []
        inputs = []
        try:
            rows, missing = select_bars(bars, symbol, sessions, calendar, audit_at)
            if missing:
                reasons.append("INCOMPLETE_21_SESSION_WARMUP")
            else:
                frame = compute_symbol_features(pd.DataFrame(rows), sessions)
                values = {name: float(frame.iloc[-1][name]) for name in FEATURES}
                if not np.isfinite(list(values.values())).all():
                    values = None
                    reasons.append("FEATURES_NON_FINITE")
                else:
                    inputs = sorted({row["raw_sha256"] for row in rows})
        except (KeyError, ValueError, TypeError) as exc:
            reasons.append("BARS_INVALID: " + str(exc)[:180])
        try:
            reasons.extend(action_checks(actions, symbol, sessions))
        except (KeyError, ValueError, TypeError) as exc:
            reasons.append("ACTIONS_INVALID: " + str(exc)[:180])
        identity_errors = identity_reasons(master, identity, feature_day)
        reasons.extend(identity_errors)
        reasons = sorted(set(reasons))
        counts.update(reasons)
        if values is not None:
            features.append({"research_uid": identity["research_uid"], "symbol": symbol,
                             "values": values, "input_payload_sha256s": inputs})
        diagnostics.append({"research_uid": identity["research_uid"], "symbol": symbol,
                            "numeric_features_ready": values is not None,
                            "local_checks_without_global_reserves_passed": values is not None and not reasons,
                            "missing_sessions": missing, "reasons": reasons})
    global_reasons = list(master_reasons) + ["INDEPENDENT_MASTER_AND_ACTIONS_QUALIFICATION",
                                           "MODEL_RELEASE_REVIEW", "SPRINT15_OPERATIONAL_RESERVES"]
    errors = {"bars": bar_errors, "actions": action_errors, "master": master_errors}
    if any(errors.values()):
        global_reasons.append("ARCHIVE_INTEGRITY_ERRORS")
    if collection["status"] == "PARTIAL_COLLECTION":
        global_reasons.append("PARTIAL_COLLECTION")
    if (any(stage.get("failed_count", 0) for stage in collection["stages"].values())
            or set(collection["stages"]) != {"bars", "actions"}):
        global_reasons.append("COLLECTION_STAGE_FAILURE_OR_MISSING")
    # Pure feature values for investigation; not a dataset with qualification=true.
    feature_content = json.dumps(features, sort_keys=True, allow_nan=False).encode()
    return {"schema_version": 1, "market_code": "FR_EQ",
            "status": "WARMUP_AUDITED_SHADOW_BLOCKED",
            "audit_role": "BOOTSTRAP_WINDOW_AUDIT_NOT_DECISION_REPLAY",
            "audit_at": audit_at.isoformat(), "feature_session": str(feature_day),
            "required_sessions": [str(day) for day in sessions],
            "universe_count": len(diagnostics), "collection_symbol_count": collection["stages"]["bars"]["requested_count"],
            "numeric_features_ready_count": len(features),
            "local_checks_without_global_reserves_passed_count": sum(
                row["local_checks_without_global_reserves_passed"] for row in diagnostics),
            "servable_count": 0, "global_reserves": sorted(set(global_reasons)),
            "reason_counts": dict(sorted(counts.items())), "archive_errors": errors,
            "diagnostics": diagnostics, "numeric_features": features,
            "numeric_features_sha256": hashlib.sha256(feature_content).hexdigest(),
            "proofs_sha256": dict(sorted(proofs.items())),
            "serving_enabled": False, "orders_allowed": False, "sql_writes": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed = (ROOT / "artifacts/fr/research/data_readiness_16c").resolve()
    if not output.is_relative_to(allowed) or output == allowed or output.exists():
        parser.error("New FR 16-C output directory required")
    report = qualify(args.bootstrap_dir)
    output.mkdir(parents=True, exist_ok=False)
    with (output / "report.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({key: value for key, value in report.items()
                      if key not in {"diagnostics", "numeric_features", "proofs_sha256"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
