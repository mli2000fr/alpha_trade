"""FR prediction preparation only: immutable evidence and fail-closed preflight.

No SQL, joblib deserialization, model fitting, prediction or broker calls.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
from datetime import datetime, timezone, date
from pathlib import Path

from modelFactory.fr_feature_profile_freeze import FEATURES
from service.fr.research_catalog_14a import CATALOG

ROOT = Path(__file__).resolve().parents[2]
IDENTITIES = "artifacts/fr/sprint6c_reference/identities.jsonl.gz"
TRANSFORMS = {"traded_value_mean20_eur": "log1p"}


def scoped_path(relative: str, root: Path) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to((root / "artifacts/fr").resolve()):
        raise ValueError("Evidence outside artifacts/fr")
    return path


def evidence(relative: str, root: Path) -> dict:
    raw = scoped_path(relative, root).read_bytes()
    return {"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}


def prepare_manifest(*, root: Path = ROOT) -> dict:
    relative = "artifacts/fr/research/" + CATALOG["oracle_h5_repaired"][1]
    report = json.loads(scoped_path(relative, root).read_text(encoding="utf-8"))
    cfg = report["config"]
    if (cfg.get("market_code"), cfg.get("horizon"), cfg.get("calibration"),
            report.get("serving_enabled"), report.get("canonical_writes")) != (
                "FR_EQ", 5, "none", False, False):
        raise ValueError("Unexpected research model contract")
    parent = str(Path(relative).parent).replace("\\", "/")
    protocol = json.loads(scoped_path(parent + "/protocol.json", root).read_text(encoding="utf-8"))
    if protocol["features"] != list(FEATURES) or protocol["cfg"] != cfg:
        raise ValueError("Feature/protocol mismatch")
    fold = next(item for item in report["folds"] if item["fold"] == 7)
    if fold["champion"] not in {"trees", "logistic"}:
        raise ValueError("Unknown champion")
    with gzip.open(scoped_path(IDENTITIES, root), "rt", encoding="utf-8") as stream:
        identities = [json.loads(line) for line in stream if line.strip()]
    universe = [{"research_uid": item["research_uid"], "isin": item["isin"],
                 "provider_symbol": item["provider_symbol"], "mics": item["mics"]}
                for item in identities if item["identity_state"] == "VERIFIED_RESEARCH"]
    if len({item["research_uid"] for item in universe}) != len(universe):
        raise ValueError("Duplicate identities")
    return {
        "schema_version": 1, "contract": "fr_prediction_preparation_16a_v1",
        "market_code": "FR_EQ", "database_alias": "fr_primary",
        "database": "alpha_trade_fr", "currency": "EUR", "calendar": "XPAR",
        "status": "DRAFT_RESEARCH_NOT_RELEASED", "serving_enabled": False,
        "live_enabled": False, "canonical_writes_enabled": False,
        "model_role": "ORACLE_AMPLITUDE_ONLY", "oracle_horizon": 5,
        "calibration": "none", "score_semantics": "raw_binary_score_not_direction",
        "selection_fraction": 0.20, "min_cross_section": 20,
        "features": list(FEATURES), "transforms": TRANSFORMS,
        "candidate_fold": 7, "candidate_champion": fold["champion"],
        "candidate_dates": fold["dates"],
        "universe_role": "RESEARCH_IDENTITIES_NOT_DAILY_TRADABLE",
        "universe": universe,
        "evidence": [evidence(path, root) for path in (
            relative, parent + "/protocol.json",
            parent + f"/fold7_{fold['champion']}.joblib", IDENTITIES)],
    }


def aware(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timezone required")
    return result.astimezone(timezone.utc)


def preflight(manifest: dict, dataset: dict | None, *, root: Path = ROOT) -> dict:
    """Validate a proposed daily feature envelope; never authorizes serving in 16-A.

    expected_feature_session must come from an independently qualified XPAR
    calendar in the future 16-B adapter, not a calendar-day subtraction.
    """
    issues = []
    rejected = []
    def require(condition: bool, reason: str) -> None:
        if not condition:
            issues.append(reason)
    require(manifest.get("schema_version") == 1 and manifest.get("contract") ==
            "fr_prediction_preparation_16a_v1", "MANIFEST_SCHEMA")
    require(all(manifest.get(key) == value for key, value in {
        "market_code": "FR_EQ", "database_alias": "fr_primary", "database": "alpha_trade_fr",
        "calendar": "XPAR", "currency": "EUR", "oracle_horizon": 5,
        "model_role": "ORACLE_AMPLITUDE_ONLY", "calibration": "none",
        "features": list(FEATURES), "transforms": TRANSFORMS,
        "min_cross_section": 20, "selection_fraction": 0.20,
        "status": "DRAFT_RESEARCH_NOT_RELEASED", "serving_enabled": False,
        "live_enabled": False, "canonical_writes_enabled": False,
    }.items()), "MANIFEST_CONTRACT")
    require(len(manifest.get("evidence", [])) == 4, "MISSING_EVIDENCE")
    for item in manifest.get("evidence", []):
        try:
            require(evidence(item["path"], root) == item, "EVIDENCE_HASH_MISMATCH")
        except (OSError, ValueError, KeyError):
            issues.append("EVIDENCE_UNAVAILABLE")
    # Rebuild from evidence: editing a JSON flag or universe cannot release a model.
    try:
        require(manifest == prepare_manifest(root=root), "MANIFEST_LINEAGE_MISMATCH")
    except (OSError, ValueError, KeyError, StopIteration):
        issues.append("MANIFEST_LINEAGE_UNAVAILABLE")
    accepted = 0
    if dataset is None:
        issues.append("QUALIFIED_DAILY_DATASET_MISSING")
    else:
        require(dataset.get("market_code") == "FR_EQ" and dataset.get("schema_version") == 1,
                "DATASET_SCHEMA_MARKET")
        require(dataset.get("features") == list(FEATURES), "DATASET_FEATURE_ORDER")
        require(dataset.get("feature_stage") == "RAW_BEFORE_MODEL_TRANSFORMS", "DATASET_TRANSFORMS")
        try:
            cutoff = aware(dataset["decision_at"])
            expected = date.fromisoformat(dataset["expected_feature_session"])
            require(expected <= cutoff.date(), "FEATURE_SESSION_IN_FUTURE")
        except (KeyError, ValueError, TypeError):
            cutoff = None
            expected = None
            issues.append("DECISION_CALENDAR_CONTRACT")
        universe = {item["research_uid"]: item for item in manifest.get("universe", [])}
        seen = set()
        for index, row in enumerate(dataset.get("rows", [])):
            reasons = []
            uid = row.get("research_uid")
            identity = universe.get(uid)
            if uid in seen:
                reasons.append("DUPLICATE_IDENTITY")
            seen.add(uid)
            if not identity or any(row.get(k) != identity[k] for k in ("isin", "provider_symbol")):
                reasons.append("IDENTITY_MISMATCH")
            if not identity or row.get("mic") not in identity["mics"]:
                reasons.append("MIC_MISMATCH")
            if row.get("identity_qualified_at_session") is not True or row.get("tradable_at_session") is not True:
                reasons.append("DAILY_ELIGIBILITY_UNQUALIFIED")
            if row.get("feature_session") != (expected.isoformat() if expected else None):
                reasons.append("STALE_OR_WRONG_SESSION")
            try:
                available, observed = aware(row["available_at"]), aware(row["observed_at"])
                if cutoff is None or available > cutoff or observed > cutoff or available < observed:
                    reasons.append("PIT_UNAVAILABLE_AT_DECISION")
            except (KeyError, TypeError, ValueError):
                reasons.append("PIT_TIMESTAMP_INVALID")
            if (row.get("source") != "eodhd" or
                    not re.fullmatch(r"[0-9a-f]{64}", str(row.get("source_payload_sha256", ""))) or
                    row.get("qualification") != "QUALIFIED"):
                reasons.append("SOURCE_LINEAGE_UNQUALIFIED")
            values = row.get("values", {})
            if set(values) != set(FEATURES) or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in values.values()
            ) or values.get("traded_value_mean20_eur", -1) < 0:
                reasons.append("INVALID_FEATURES")
            if reasons:
                rejected.append({"row": index, "research_uid": uid, "reasons": reasons})
            else:
                accepted += 1
        require(not rejected, "ROWS_REJECTED")
        require(accepted >= manifest.get("min_cross_section", 20), "INSUFFICIENT_CROSS_SECTION")
    return {"status": "PREPARED_NOT_AUTHORIZED" if not issues else "BLOCKED",
            "market_code": "FR_EQ", "technical_checks_passed": not issues,
            "blocking_reasons": sorted(set(issues)), "accepted_rows": accepted,
            "rejected_rows": rejected, "serving_allowed": False, "orders_allowed": False,
            "remaining_release_gates": ["MODEL_RELEASE_REVIEW", "QUALIFIED_DAILY_ADAPTER_16B",
                                        "PROSPECTIVE_PROTOCOL_AND_SPRINT15_RESERVES"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset", type=Path)
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if not destination.is_relative_to((ROOT / "artifacts/fr/research/prediction_preparation_16a").resolve()):
        parser.error("Output must remain in artifacts/fr/research/prediction_preparation_16a")
    destination.mkdir(parents=True, exist_ok=False)
    manifest = prepare_manifest()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8")) if args.dataset else None
    report = preflight(manifest, dataset)
    for name, payload in (("manifest.json", manifest), ("preflight.json", report)):
        with (destination / name).open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"output": str(destination), **report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
