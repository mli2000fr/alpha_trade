"""Prepare or confirm one locked FR opening, without waiting or trading."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path

from common.market_calendar import get_market_calendar
from service.fr.daily_feature_adapter_16b import master_at, observed_payloads, select_bars
from service.fr.decision_qualification_16e import audit
from service.fr.prediction_contract_16a import ROOT, prepare_manifest

PROTOCOL = ROOT / "config/research_fr/opening_confirmation_16f.json"


def validate(protocol):
    fixed = {"schema_version": 1, "market_code": "FR_EQ", "calendar": "XPAR",
             "serving_allowed": False, "orders_allowed": False, "sql_writes": False}
    if any(protocol.get(k) != v for k, v in fixed.items()):
        raise ValueError("FR diagnostic-only protocol required")
    date.fromisoformat(protocol["decision_date"])
    return protocol


def execute(protocol, phase, *, now=None, root=ROOT, calendar=None):
    validate(protocol)
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("Aware audit time required")
    calendar = calendar or get_market_calendar("FR_EQ", allow_us_weekday_fallback=False)
    day = date.fromisoformat(protocol["decision_date"])
    cutoff = calendar.session(day).open_at_utc
    feature_day = calendar.previous_session(day)
    digest = hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest()
    if phase == "confirm":
        if now < cutoff:
            raise ValueError("Wait for actual XPAR opening; confirmation is not yet possible")
        result = audit(day, Path(protocol["bootstrap_dir"]), Path(protocol["evidence_dir"]),
                       now=now, root=root, calendar=calendar)
        return {"phase": "confirm", "protocol_sha256": digest, "protocol": protocol, **result}
    if phase != "prepare":
        raise ValueError("Unknown phase")
    proofs = {}
    operations = root / "artifacts/fr/operations"
    bars, bar_errors = observed_payloads(operations / "eodhd_daily", now, root, proofs)
    actions, action_errors = observed_payloads(operations / "fr_corporate_actions_sync", now, root, proofs)
    master, reasons, master_errors = master_at(operations / "fr_security_master_sync", now,
                                               feature_day, root, proofs)
    manifest = prepare_manifest(root=root)
    rows = []
    for identity in manifest["universe"]:
        symbol = identity["provider_symbol"]
        try:
            values, missing = select_bars(bars, symbol, [feature_day], calendar, now)
            bar = bool(values) and not missing
            error = None
        except (ValueError, KeyError, TypeError) as exc:
            bar = False
            error = str(exc)[:180]
        coverage = {}
        for kind in ("div", "splits"):
            coverage[kind] = any(p["raw"]["symbol"] == symbol and p["raw"]["kind"] == kind
                and p["raw"]["window"][0] <= str(feature_day) <= p["raw"]["window"][1] for p in actions)
        rows.append({"symbol": symbol, "last_session_bar_observed_now": bar,
                     "bar_reserve": error, "action_response_coverage_observed_now": coverage})
    return {"schema_version": 1, "market_code": "FR_EQ", "phase": "prepare",
            "status": "WAIT_ACTUAL_OPENING" if now < cutoff else "PREPARED_CONFIRMATION_NOT_EXECUTED",
            "prepared_at": now.isoformat(), "planned_decision_at": cutoff.isoformat(),
            "expected_feature_session": str(feature_day), "protocol": protocol, "protocol_sha256": digest,
            "inventory_role": "AS_KNOWN_NOW_NOT_OPENING_QUALIFICATION",
            "universe_count": len(rows), "last_session_bars_observed_now": sum(r["last_session_bar_observed_now"] for r in rows),
            "div_response_coverage_observed_now": sum(r["action_response_coverage_observed_now"]["div"] for r in rows),
            "split_response_coverage_observed_now": sum(r["action_response_coverage_observed_now"]["splits"] for r in rows),
            "master_coverage_now": master.get("end") if master else None,
            "master_observed_now": master.get("last_observed_at") if master else None,
            "master_reserves_now": reasons, "inventory": rows,
            "archive_errors": {"bars": bar_errors, "actions": action_errors, "master": master_errors},
            "proofs_sha256": proofs, "serving_allowed": False, "orders_allowed": False, "sql_writes": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepare", "confirm"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed = (ROOT / "artifacts/fr/research/opening_confirmation_16f").resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        parser.error("New FR 16-F output directory required")
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    result = execute(protocol, args.phase)
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    keys = ("status", "phase", "planned_decision_at", "decision_at", "last_session_bars_observed_now",
            "div_response_coverage_observed_now", "split_response_coverage_observed_now", "master_coverage_now", "serving_allowed")
    print(json.dumps({k: result[k] for k in keys if k in result}))


if __name__ == "__main__":
    main()
