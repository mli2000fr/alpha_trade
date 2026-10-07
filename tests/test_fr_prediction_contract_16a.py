from copy import deepcopy

import pytest

from service.fr.prediction_contract_16a import prepare_manifest, preflight, scoped_path, ROOT


@pytest.fixture(scope="module")
def manifest():
    return prepare_manifest()


@pytest.fixture
def dataset(manifest):
    return {
        "schema_version": 1, "market_code": "FR_EQ", "features": manifest["features"],
        "feature_stage": "RAW_BEFORE_MODEL_TRANSFORMS",
        "decision_at": "2026-10-06T08:00:00+02:00", "expected_feature_session": "2026-10-05",
        "rows": [{
            "research_uid": item["research_uid"], "isin": item["isin"],
            "provider_symbol": item["provider_symbol"], "mic": item["mics"][0],
            "identity_qualified_at_session": True, "tradable_at_session": True,
            "feature_session": "2026-10-05", "available_at": "2026-10-05T23:00:00+02:00",
            "observed_at": "2026-10-05T22:00:00+02:00", "source": "eodhd",
            "source_payload_sha256": "a" * 64, "qualification": "QUALIFIED",
            "values": {feature: 0.01 for feature in manifest["features"]},
        } for item in manifest["universe"][:20]],
    }


def test_actual_manifest_is_draft(manifest):
    assert manifest["oracle_horizon"] == 5
    assert len(manifest["universe"]) == 330
    assert not manifest["serving_enabled"]
    assert manifest["candidate_champion"] == "trees"
    result = preflight(manifest, None)
    assert result["blocking_reasons"] == ["QUALIFIED_DAILY_DATASET_MISSING"]


def test_valid_envelope_never_authorizes_serving(manifest, dataset):
    result = preflight(manifest, dataset)
    assert result["technical_checks_passed"]
    assert result["accepted_rows"] == 20
    assert not result["serving_allowed"] and not result["orders_allowed"]


@pytest.mark.parametrize("key,value", [
    ("market_code", "US_EQ"), ("database", "alpha_trade_cn"),
    ("oracle_horizon", 20), ("serving_enabled", True),
    ("transforms", {}), ("calibration", "platt"),
])
def test_no_route_or_contract_fallback(manifest, dataset, key, value):
    changed = deepcopy(manifest)
    changed[key] = value
    result = preflight(changed, dataset)
    assert "MANIFEST_CONTRACT" in result["blocking_reasons"]
    assert "MANIFEST_LINEAGE_MISMATCH" in result["blocking_reasons"]


@pytest.mark.parametrize("key,value,reason", [
    ("available_at", "2026-10-06T09:00:00+02:00", "PIT_UNAVAILABLE_AT_DECISION"),
    ("observed_at", "2026-10-05T22:00:00", "PIT_TIMESTAMP_INVALID"),
    ("feature_session", "2026-10-02", "STALE_OR_WRONG_SESSION"),
    ("source", "yahoo", "SOURCE_LINEAGE_UNQUALIFIED"),
    ("isin", "INVALID", "IDENTITY_MISMATCH"),
    ("mic", "XNYS", "MIC_MISMATCH"),
    ("tradable_at_session", False, "DAILY_ELIGIBILITY_UNQUALIFIED"),
])
def test_row_rejections(manifest, dataset, key, value, reason):
    dataset["rows"][0][key] = value
    result = preflight(manifest, dataset)
    assert reason in result["rejected_rows"][0]["reasons"]
    assert not result["technical_checks_passed"]


def test_duplicate_and_invalid_features(manifest, dataset):
    dataset["rows"].append(deepcopy(dataset["rows"][0]))
    dataset["rows"][0]["values"]["atr20_pct"] = float("nan")
    result = preflight(manifest, dataset)
    reasons = {reason for row in result["rejected_rows"] for reason in row["reasons"]}
    assert {"DUPLICATE_IDENTITY", "INVALID_FEATURES"} <= reasons


def test_evidence_change_blocks(manifest):
    changed = deepcopy(manifest)
    changed["evidence"][0]["sha256"] = "0" * 64
    assert "EVIDENCE_HASH_MISMATCH" in preflight(changed, None)["blocking_reasons"]


def test_cross_market_path_rejected():
    with pytest.raises(ValueError):
        scoped_path("artifacts/models/us/model.joblib", ROOT)


def test_feature_stage_and_calendar(manifest, dataset):
    dataset["feature_stage"] = "LOG_TRANSFORMED"
    dataset["decision_at"] = "2026-10-06T08:00:00"
    result = preflight(manifest, dataset)
    assert {"DATASET_TRANSFORMS", "DECISION_CALENDAR_CONTRACT"} <= set(result["blocking_reasons"])
