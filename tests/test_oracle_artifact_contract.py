from __future__ import annotations

import json

from modelFactory.oracle.artifact_contract import (
    oracle_horizon_badge,
    resolve_oracle_artifact_horizon,
)


def test_resolve_oracle_horizon_from_batch_profile(tmp_path) -> None:
    profile = tmp_path / "batch-h10" / "oracle" / "feature_profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(json.dumps({"oracle_horizon": 10}), encoding="utf-8")
    assert resolve_oracle_artifact_horizon("batch-h10", tmp_path) == 10
    assert oracle_horizon_badge("batch-h10", tmp_path) == "H10"


def test_resolve_oracle_horizon_from_champion_profile(tmp_path) -> None:
    profile = tmp_path / "oracle" / "champions" / "batch-h5" / "feature_profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(json.dumps({"oracle_horizon": 5}), encoding="utf-8")
    assert resolve_oracle_artifact_horizon("batch-h5", tmp_path) == 5


def test_resolve_oracle_horizon_returns_none_for_non_oracle_batch(tmp_path) -> None:
    assert resolve_oracle_artifact_horizon("ordinary-batch", tmp_path) is None
    assert oracle_horizon_badge("ordinary-batch", tmp_path) == ""


def test_legacy_oracle_champions_default_to_h20(tmp_path) -> None:
    champions = tmp_path / "oracle" / "champions" / "legacy" / "oracle_champions.json"
    champions.parent.mkdir(parents=True)
    champions.write_text("[]", encoding="utf-8")
    assert resolve_oracle_artifact_horizon("legacy", tmp_path) == 20
