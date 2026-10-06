"""Assemble observed FR daily archives at an XPAR opening, files only.

Latest files are deliberately not used: they can contain corrections received
after the decision. Reuses the training feature formulas without model fitting.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from common.market_calendar import get_market_calendar
from modelFactory.fr_feature_panel import compute_symbol_features
from service.fr.load_eodhd_staging import classify_bar
from service.fr.prediction_contract_16a import ROOT, FEATURES, aware, prepare_manifest, preflight, scoped_path


def read_json(path: Path, root: Path, proofs: dict) -> dict:
    path = scoped_path(str(path), root)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    proofs[str(path.relative_to(root.resolve())).replace("\\", "/")] = digest
    return json.loads(raw)


def observed_payloads(folder: Path, cutoff, root: Path, proofs: dict) -> tuple[list, list]:
    """Return every version actually observed by the cutoff; validate raw links."""
    selected, errors = [], []
    for path in sorted((folder / "observations").rglob("*.json")):
        try:
            observation = json.loads(scoped_path(str(path), root).read_bytes())
            observed = aware(observation["observed_at"])
            available = aware(observation["available_at"])
            if observed > cutoff or available > cutoff:
                continue
            read_json(path, root, proofs)
            if available < observed:
                raise ValueError("availability precedes observation")
            digest = observation["raw_sha256"]
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("invalid payload hash")
            raw_path = folder / "raw" / (digest + ".json")
            raw = read_json(raw_path, root, proofs)
            if proofs[str(raw_path.resolve().relative_to(root.resolve())).replace("\\", "/")] != digest:
                raise ValueError("payload hash mismatch")
            if raw["symbol"] != observation["symbol"] or raw["window"] != observation["window"]:
                raise ValueError("observation/payload mismatch")
            if raw.get("kind") != observation.get("kind"):
                raise ValueError("action type mismatch")
            selected.append({"observation": observation, "raw": raw, "time": available,
                             "observed": observed, "path": str(path)})
        except (OSError, KeyError, ValueError, TypeError) as exc:
            errors.append({"path": str(path), "reason": type(exc).__name__ + ": " + str(exc)[:160]})
    return selected, errors


def select_bars(payloads: list, symbol: str, sessions: list[date], calendar, cutoff) -> tuple[list, list]:
    versions = {}
    for payload in payloads:
        if payload["raw"]["symbol"] != symbol:
            continue
        if payload["time"] > cutoff or payload["observed"] > cutoff:
            continue
        window = [date.fromisoformat(day) for day in payload["raw"]["window"]]
        seen = set()
        for row in payload["raw"]["rows"]:
            day = date.fromisoformat(row["date"])
            if day in seen or not window[0] <= day <= window[1]:
                raise ValueError("duplicate/out-of-window provider bar")
            seen.add(day)
            if day not in sessions:
                continue
            if payload["observed"] < calendar.session(day).close_at_utc:
                raise ValueError("bar observed before session close")
            previous = versions.get(day)
            if previous and previous["time"] == payload["time"] and previous["row"] != row:
                raise ValueError("ambiguous correction at identical availability")
            if previous is None or payload["time"] > previous["time"]:
                versions[day] = {**payload, "row": row}
    missing = [str(day) for day in sessions if day not in versions]
    rows = []
    for day in sessions:
        if day not in versions:
            continue
        version = versions[day]
        _, quality, _ = classify_bar(version["row"], set(sessions))
        if quality != "VALID":
            raise ValueError("bar unsuitable for frozen features: " + quality)
        rows.append({**version["row"], "source_session_date": day,
                     "available_at": version["time"], "observed_at": version["observed"],
                     "raw_sha256": version["observation"]["raw_sha256"]})
    return rows, missing


def action_checks(payloads: list, symbol: str, sessions: list[date]) -> list[str]:
    """Require observed coverage, not an empty 'latest' file taken as no event."""
    reasons = []
    for kind in ("div", "splits"):
        coverage = set()
        events = {}
        same_time = {}
        for payload in sorted(payloads, key=lambda item: (item["time"], item["path"])):
            raw = payload["raw"]
            if raw["symbol"] != symbol or raw["kind"] != kind:
                continue
            key = (payload["time"], tuple(raw["window"]))
            if key in same_time and same_time[key] != raw["rows"]:
                raise ValueError("ambiguous action correction at identical availability")
            same_time[key] = raw["rows"]
            start, end = map(date.fromisoformat, raw["window"])
            # A fresh response replaces earlier events in its covered window.
            events = {day: rows for day, rows in events.items() if not start <= day <= end}
            coverage.update(day for day in sessions if start <= day <= end)
            for event in raw["rows"]:
                day = date.fromisoformat(event["date"])
                if not start <= day <= end:
                    raise ValueError("action outside provider window")
                events.setdefault(day, []).append(event)
        if set(sessions) - coverage:
            reasons.append("INCOMPLETE_" + kind.upper() + "_OBSERVED_COVERAGE")
        if any(day in sessions for day in events):
            # No automatic adjustment: the training profile excludes split histories.
            reasons.append("UNQUALIFIED_" + kind.upper() + "_IN_FEATURE_WINDOW")
    return reasons


def master_at(folder: Path, cutoff, feature_day: date, root: Path, proofs: dict):
    candidates, errors = [], []
    for path in sorted((folder / "versions").glob("*.json")):
        try:
            state = json.loads(scoped_path(str(path), root).read_bytes())
            stamp = aware(state["last_observed_at"])
            if stamp <= cutoff:
                read_json(path, root, proofs)
                if proofs[str(path.relative_to(root.resolve())).replace("\\", "/")] != path.stem:
                    raise ValueError("master version hash mismatch")
                candidates.append((stamp, str(path), state))
        except (OSError, KeyError, ValueError, TypeError) as exc:
            errors.append(str(exc)[:180])
    if not candidates:
        return None, ["MASTER_NOT_OBSERVED_AT_DECISION"], errors
    state = max(candidates, key=lambda item: (item[0], item[1]))[2]
    reasons = []
    if state.get("market_code") != "FR_EQ":
        reasons.append("MASTER_WRONG_MARKET")
    if state.get("end") != str(feature_day):
        reasons.append("MASTER_STALE_OR_WRONG_SESSION")
    if not state.get("historical_continuity_confirmed") or not state.get("delta_publication_continuity_confirmed"):
        reasons.append("MASTER_CONTINUITY_UNQUALIFIED")
    if state.get("anomalies"):
        reasons.append("MASTER_HAS_ANOMALIES")
    # Archive/base independent qualification remains a release gate even when
    # the supplied master assertions pass. Never calls this a production universe.
    return state, reasons, errors


def identity_resolution(state: dict | None, identity: dict, day: date) -> dict:
    """Resolve active venue only; a terminal record on another MIC is not active."""
    def reject(reason):
        return {"reasons": [reason], "mic": None, "nominal_currency": None}
    if state is None:
        return reject("DAILY_IDENTITY_UNAVAILABLE")
    entries = [item for item in state["symbols"] if item["isin"] == identity["isin"]]
    if len(entries) != 1:
        return reject("DAILY_IDENTITY_ABSENT_OR_AMBIGUOUS")
    versions = []
    for reference in entries[0]["market_reference"]:
        if reference["mic"] not in identity["mics"]:
            continue
        applicable = [v for v in reference["versions"]
                      if v.get("asof_from", "9999") <= str(day)
                      and (not v.get("asof_to") or str(day) <= v["asof_to"])]
        if len(applicable) > 1:
            return reject("DAILY_IDENTITY_VERSION_AMBIGUOUS")
        for version in applicable:
            terminal = version.get("event") in ("TermntdRcrd", "CancRcrd")
            termination = version.get("termination_reported")
            if terminal or (termination and str(termination)[:10] <= str(day)):
                continue
            first_trade = version.get("first_trade_reported")
            if first_trade and str(first_trade)[:10] > str(day):
                continue
            versions.append((reference["mic"], version))
    if not versions:
        return reject("DAILY_IDENTITY_TERMINATED_OR_RESERVED")
    if len(versions) != 1:
        return reject("DAILY_IDENTITY_VERSION_AMBIGUOUS")
    mic, version = versions[0]
    if version.get("isin") != identity["isin"]:
        return reject("DAILY_IDENTITY_ISIN_MISMATCH")
    if not str(version.get("cfi", "")).startswith("E"):
        return reject("DAILY_IDENTITY_EQUITY_CLASS_UNVERIFIED")
    reasons = []
    # Parser maps NtnlCcy, not verified trading currency. Preserve a reserve;
    # do not silently convert GBP/USD/ZMW observations into EUR quote evidence.
    if version.get("currency") != "EUR":
        reasons.append("NON_EUR_NOMINAL_REQUIRES_TRADING_CURRENCY_PROOF")
    return {"reasons": reasons, "mic": mic, "nominal_currency": version.get("currency"),
            "trading_currency_independently_verified": False,
            "source_file": version.get("source_file"), "version": version}


def identity_reasons(state: dict | None, identity: dict, day: date) -> list[str]:
    return identity_resolution(state, identity, day)["reasons"]


def assemble(decision_day: date, *, root: Path = ROOT, calendar=None, manifest=None,
             bootstrap_dir: Path | None = None) -> dict:
    root = root.resolve()
    manifest = manifest or prepare_manifest(root=root)
    calendar = calendar or get_market_calendar("FR_EQ", allow_us_weekday_fallback=False)
    cutoff = calendar.session(decision_day).open_at_utc
    feature_day = calendar.previous_session(decision_day)
    sessions = calendar.session_dates(calendar.previous_session(feature_day, 20), feature_day)
    if len(sessions) != 21:
        raise ValueError("Frozen short profile requires exactly 21 XPAR sessions")
    proofs = {}
    operations = root / "artifacts/fr/operations"
    bars, bar_errors = observed_payloads(operations / "eodhd_daily", cutoff, root, proofs)
    actions, action_errors = observed_payloads(operations / "fr_corporate_actions_sync", cutoff, root, proofs)
    if bootstrap_dir is not None:
        bootstrap_dir = scoped_path(str(bootstrap_dir), root)
        extra_bars, extra_errors = observed_payloads(bootstrap_dir / "eodhd_daily", cutoff, root, proofs)
        bars.extend(extra_bars)
        bar_errors.extend(extra_errors)
        extra_actions, extra_errors = observed_payloads(bootstrap_dir / "corporate_actions", cutoff, root, proofs)
        actions.extend(extra_actions)
        action_errors.extend(extra_errors)
    master, master_reasons, master_errors = master_at(
        operations / "fr_security_master_sync", cutoff, feature_day, root, proofs)
    dataset = {"schema_version": 1, "market_code": "FR_EQ", "features": list(FEATURES),
               "feature_stage": "RAW_BEFORE_MODEL_TRANSFORMS", "decision_at": cutoff.isoformat(),
               "expected_feature_session": str(feature_day), "rows": []}
    diagnostics = []
    counts = Counter()
    computed_count = 0
    for identity in manifest["universe"]:
        symbol = identity["provider_symbol"]
        reasons = list(master_reasons) + identity_reasons(master, identity, feature_day)
        missing = []
        values = None
        try:
            rows, missing = select_bars(bars, symbol, sessions, calendar, cutoff)
            if missing:
                reasons.append("INCOMPLETE_21_SESSION_WARMUP")
            else:
                frame = compute_symbol_features(pd.DataFrame(rows), sessions)
                values = {name: float(frame.iloc[-1][name]) for name in FEATURES}
                if not np.isfinite(list(values.values())).all():
                    values = None
                    reasons.append("FEATURES_NON_FINITE")
                else:
                    computed_count += 1
            reasons.extend(action_checks(actions, symbol, sessions))
            if not reasons and values is not None:
                # Provisional: archive integrity is not independent data qualification.
                dataset["rows"].append({**{k: identity[k] for k in ("research_uid", "isin", "provider_symbol")},
                    "mic": identity_resolution(master, identity, feature_day)["mic"], "identity_qualified_at_session": False,
                    "tradable_at_session": False, "feature_session": str(feature_day),
                    "available_at": max(row["available_at"] for row in rows).isoformat(),
                    "observed_at": max(row["observed_at"] for row in rows).isoformat(),
                    "source": "eodhd", "source_payload_sha256": rows[-1]["raw_sha256"],
                    "input_payload_sha256s": sorted({row["raw_sha256"] for row in rows}),
                    "qualification": "OBSERVED_RESEARCH_NOT_INDEPENDENTLY_QUALIFIED", "values": values})
        except (ValueError, KeyError, TypeError) as exc:
            reasons.append("INPUT_INVALID: " + str(exc)[:180])
        reasons = sorted(set(reasons))
        counts.update(reasons)
        diagnostics.append({"research_uid": identity["research_uid"], "symbol": symbol,
                            "missing_sessions": missing, "reasons": reasons,
                            "features_computed": values is not None})
    errors = {"bars": bar_errors, "actions": action_errors, "master": master_errors}
    report = {"schema_version": 1, "market_code": "FR_EQ", "status": "BLOCKED_NOT_RELEASED",
              "decision_at": cutoff.isoformat(), "feature_session": str(feature_day),
              "required_sessions": [str(day) for day in sessions],
              "universe_count": len(manifest["universe"]), "features_computed_count": computed_count,
              "candidate_rows_count": len(dataset["rows"]), "reason_counts": dict(sorted(counts.items())),
              "archive_errors": errors, "diagnostics": diagnostics,
              "proofs_sha256": dict(sorted(proofs.items())), "preflight": preflight(manifest, dataset, root=root),
              "serving_enabled": False, "orders_allowed": False, "sql_writes": False,
              "release_reserves": ["INDEPENDENT_MASTER_AND_ACTIONS_QUALIFICATION", "MODEL_RELEASE_REVIEW",
                                   "SPRINT15_OPERATIONAL_RESERVES"]}
    if any(errors.values()):
        dataset["rows"] = []
        report["candidate_rows_count"] = 0
        report["preflight"] = preflight(manifest, dataset, root=root)
    return {"manifest": manifest, "dataset": dataset, "report": report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision-date", type=date.fromisoformat, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-dir", type=Path)
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    base = (ROOT / "artifacts/fr/research/daily_feature_adapter_16b").resolve()
    if not destination.is_relative_to(base):
        parser.error("Output outside FR 16-B research scope")
    if destination.exists():
        parser.error("Output already exists; choose a new version")
    result = assemble(args.decision_date, bootstrap_dir=args.bootstrap_dir)
    destination.mkdir(parents=True, exist_ok=False)
    for name, payload in result.items():
        with (destination / (name + ".json")).open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({key: value for key, value in result["report"].items()
                      if key not in {"diagnostics", "proofs_sha256", "preflight"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
