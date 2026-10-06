"""Bounded last-known FR reference at decision time, diagnostic only."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path

import yaml

from common.market_calendar import get_market_calendar
from service.fr.daily_feature_adapter_16b import master_at, identity_resolution
from service.fr.prediction_contract_16a import ROOT, aware, prepare_manifest

POLICY = ROOT / "config/research_fr/observed_reference_16d.yaml"


def load_policy(path: Path = POLICY) -> dict:
    policy = yaml.safe_load(path.read_text(encoding="utf-8"))
    return validate_policy(policy)


def validate_policy(policy: dict) -> dict:
    fixed = {"schema_version": 1, "policy": "fr_last_known_reference_diagnostic_v1",
             "market_code": "FR_EQ", "calendar": "XPAR", "database_alias": "fr_primary",
             "historical_continuity_required_for_release": True,
             "serving_enabled": False, "orders_allowed": False, "canonical_writes_enabled": False}
    if any(policy.get(key) != value for key, value in fixed.items()):
        raise ValueError("Reference policy cannot enable serving or cross markets")
    if type(policy.get("max_coverage_lag_sessions")) is not int or not 0 <= policy["max_coverage_lag_sessions"] <= 1:
        raise ValueError("Diagnostic reference lag limited to 0..1 XPAR sessions")
    if type(policy.get("max_observation_age_hours")) is not int or not 1 <= policy["max_observation_age_hours"] <= 96:
        raise ValueError("Observation freshness limited to 96 hours")
    return policy


def select_reference(decision_at: str, feature_day: date, *, root: Path = ROOT,
                     policy: dict | None = None, calendar=None, manifest=None) -> dict:
    cutoff = aware(decision_at)
    policy = validate_policy(policy) if policy is not None else load_policy()
    calendar = calendar or get_market_calendar("FR_EQ", allow_us_weekday_fallback=False)
    if calendar.session(feature_day).close_at_utc > cutoff:
        raise ValueError("Feature session unfinished at decision")
    proofs = {}
    state, reasons, errors = master_at(root / "artifacts/fr/operations/fr_security_master_sync",
                                       cutoff, feature_day, root, proofs)
    diagnostic_blocks = list(errors)
    lag_days = []
    age = None
    identities = []
    if state is not None:
        covered = date.fromisoformat(state["end"])
        if covered > feature_day:
            diagnostic_blocks.append("REFERENCE_COVERS_FUTURE_SESSION")
        else:
            lag_days = calendar.session_dates(covered + timedelta(days=1), feature_day)
        age = (cutoff - aware(state["last_observed_at"])).total_seconds() / 3600
        if age < 0 or age > policy["max_observation_age_hours"]:
            diagnostic_blocks.append("REFERENCE_OBSERVATION_TOO_OLD")
        if len(lag_days) > policy["max_coverage_lag_sessions"]:
            diagnostic_blocks.append("REFERENCE_COVERAGE_LAG_TOO_LARGE")
        diagnostic_blocks.extend(reason for reason in reasons
                                 if reason not in {"MASTER_STALE_OR_WRONG_SESSION", "MASTER_CONTINUITY_UNQUALIFIED"})
        manifest = manifest or prepare_manifest(root=root)
        for identity in manifest["universe"]:
            resolved = identity_resolution(state, identity, covered)
            identities.append({"research_uid": identity["research_uid"], "symbol": identity["provider_symbol"],
                               "isin": identity["isin"], "known_state_asof": str(covered),
                               "mic": resolved["mic"], "nominal_currency": resolved["nominal_currency"],
                               "source_file": resolved.get("source_file"), "reasons": resolved["reasons"],
                               "tradability_at_decision_verified": False})
    else:
        diagnostic_blocks.extend(reasons)
    return {"schema_version": 1, "market_code": "FR_EQ", "policy": policy,
            "status": "KNOWN_REFERENCE_DIAGNOSTIC_ONLY" if not diagnostic_blocks else "BLOCKED_REFERENCE",
            "decision_at": cutoff.isoformat(), "feature_session": str(feature_day),
            "selected_coverage_end": state.get("end") if state else None,
            "selected_observed_at": state.get("last_observed_at") if state else None,
            "coverage_lag_sessions": len(lag_days), "unobserved_sessions": [str(day) for day in lag_days],
            "observation_age_hours": age, "diagnostic_blocks": sorted(set(diagnostic_blocks)),
            "release_reserves": sorted(set(reasons + ["INDEPENDENT_REFERENCE_QUALIFICATION",
                                                       "UNOBSERVED_SESSION_NOT_PROVEN_UNCHANGED"] if lag_days
                                             else reasons + ["INDEPENDENT_REFERENCE_QUALIFICATION"])),
            "identities": identities, "proofs_sha256": proofs,
            "serving_allowed": False, "orders_allowed": False, "sql_writes": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision-at", required=True)
    parser.add_argument("--feature-session", type=date.fromisoformat, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed = (ROOT / "artifacts/fr/research/observed_reference_16d").resolve()
    if not output.is_relative_to(allowed) or output == allowed or output.exists():
        parser.error("New FR 16-D output directory required")
    report = select_reference(args.decision_at, args.feature_session)
    output.mkdir(parents=True, exist_ok=False)
    with (output / "report.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({key: value for key, value in report.items()
                      if key not in {"identities", "proofs_sha256", "policy"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
