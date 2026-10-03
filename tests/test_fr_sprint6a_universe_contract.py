from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from service.fr.universe_contract_6a import (
    FRUniversePolicy,
    audit_contract,
    classify_manifest_row,
)

ROOT = Path(__file__).resolve().parents[1]


def _policy() -> FRUniversePolicy:
    return FRUniversePolicy.from_yaml(ROOT / "config" / "universe_fr.yaml")


def test_fr_migration_0006_is_isolated_and_chained() -> None:
    path = ROOT / "alembic_fr" / "versions" / "0006_fr_universe_contract.py"
    spec = importlib.util.spec_from_file_location("fr_migration_0006", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "0005_fr_staging_quality_version"
    sql = (
        ROOT / "database" / "sql" / "fr" / "migration_fr_0006_universe_contract.sql"
    ).read_text(encoding="utf-8")
    assert "fr_universe_runs" in sql
    assert "fr_universe_decisions" in sql
    assert "alpha_trade." not in sql
    assert "publication_tier='RESEARCH_J1'" in sql


def test_fr_policy_keeps_live_tradable_and_serving_disabled(tmp_path: Path) -> None:
    policy = _policy()
    assert policy.market_code == "FR_EQ"
    assert not policy.tradable_enabled
    assert not policy.servable_enabled
    assert {"no_live", "no_paper", "no_serving", "no_canonical_write"} <= set(
        policy.prohibitions
    )
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(
        (ROOT / "config" / "universe_fr.yaml")
        .read_text(encoding="utf-8")
        .replace("enabled: false", "enabled: true", 1),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="interdit"):
        FRUniversePolicy.from_yaml(invalid)


def test_research_row_is_observable_but_not_yet_trainable_or_tradable() -> None:
    result = classify_manifest_row(
        {
            "symbol": "AIR.PA",
            "session_date": "2024-06-03",
            "mic": "XPAR",
            "research_j1_eligible": True,
        },
        _policy(),
    )
    assert result.observable_state == "ELIGIBLE"
    assert result.training_state == "UNKNOWN"
    assert result.tradable_state == "PROHIBITED"
    assert result.servable_state == "PROHIBITED"


def test_rejected_source_row_cannot_enter_downstream_scopes() -> None:
    result = classify_manifest_row(
        {
            "symbol": "BAD.PA",
            "session_date": "2024-06-03",
            "mic": "XPAR",
            "research_j1_eligible": False,
            "research_rejection_reasons": ["INVALID_OR_ZERO_VOLUME_BAR"],
        },
        _policy(),
    )
    assert result.observable_state == "INELIGIBLE"
    assert result.observable_reason == "INVALID_OR_ZERO_VOLUME_BAR"
    assert result.training_state == "INELIGIBLE"
    assert result.tradable_state == "PROHIBITED"


def test_contract_audit_verifies_hash_and_never_publishes(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl.gz"
    rows = [
        {
            "symbol": "AIR.PA",
            "session_date": "2024-06-03",
            "mic": "XPAR",
            "research_j1_eligible": True,
        },
        {
            "symbol": "BAD.PA",
            "session_date": "2024-06-03",
            "mic": "XPAR",
            "research_j1_eligible": False,
            "research_rejection_reasons": ["NO_OBSERVED_ACTIVE_TARGET_MIC"],
        },
    ]
    with gzip.open(manifest, "wt", encoding="utf-8") as sink:
        for row in rows:
            sink.write(json.dumps(row) + "\n")
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    source_report = tmp_path / "report.json"
    source_report.write_text(
        json.dumps({
            "verdict": "GO_RESEARCH_J1",
            "policy_version": "fr_s5_limited_v1",
            "canonical_writes_performed": False,
            "manifest": {"sha256": digest},
        }),
        encoding="utf-8",
    )
    report = audit_contract(
        _policy(), source_report_path=source_report, source_manifest_path=manifest
    )
    assert report["verdict"] == "GO_6A_CONTRACT_ONLY"
    assert report["rows"] == 2
    assert report["stage_counts"]["observable"] == {
        "ELIGIBLE": 1,
        "INELIGIBLE": 1,
    }
    assert report["stage_counts"]["tradable"] == {"PROHIBITED": 2}
    assert report["stage_counts"]["servable"] == {"PROHIBITED": 2}
    assert report["database_writes_performed"] is False


def test_contract_audit_rejects_manifest_hash_mismatch(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl.gz"
    with gzip.open(manifest, "wt", encoding="utf-8") as sink:
        sink.write("{}\n")
    source_report = tmp_path / "report.json"
    source_report.write_text(json.dumps({
        "verdict": "GO_RESEARCH_J1",
        "policy_version": "fr_s5_limited_v1",
        "canonical_writes_performed": False,
        "manifest": {"sha256": "0" * 64},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Hash"):
        audit_contract(
            _policy(), source_report_path=source_report, source_manifest_path=manifest
        )
