"""Contract tests for standalone tabular baseline artifacts."""

from __future__ import annotations

import json

import pytest

from modelFactory.tabular_baseline import save_baseline_artifact


def test_save_baseline_artifact_persists_real_run_fingerprints_and_side_metrics(tmp_path):
	result = {
		"model_name": "logistic",
		"inference_backend": "logistic_tabular",
		"seed": 42,
		"feature_fingerprint": "features-123",
		"val": {"f1_short": 0.4, "f1_flat": 0.5, "f1_long": 0.6},
		"test": {"f1_short": 0.7, "f1_flat": 0.8, "f1_long": 0.9},
	}

	path = save_baseline_artifact(
		result,
		artifact_dir=tmp_path,
		period_start="2025-01-01",
		period_end="2025-01-31",
		universe_run_id="universe-run-1",
		code_version="abc123",
		data_fingerprint="data-456",
		config_fingerprint="config-789",
	)

	payload = json.loads(path.read_text(encoding="utf-8"))
	assert payload["period"] == {"start": "2025-01-01", "end": "2025-01-31"}
	assert payload["universe"]["run_id"] == "universe-run-1"
	assert payload["model"]["seed"] == 42
	assert payload["code"]["version"] == "abc123"
	assert payload["fingerprints"] == {
		"features": "features-123",
		"data": "data-456",
		"configuration": "config-789",
	}
	assert payload["metrics"]["val"] == {
		"n_observations": None,
		"accuracy": None,
		"f1_macro": None,
		"f1_weighted": None,
		"f1_long": 0.6,
		"f1_short": 0.4,
		"f1_flat": 0.5,
		"balanced_accuracy": None,
		"action_rate": None,
		"pred_fraction_long": None,
		"pred_fraction_short": None,
		"pred_fraction_flat": None,
		"brier_multiclass": None,
		"log_loss": None,
		"selection_score": None,
	}
	assert {key: payload["metrics"]["test"][key] for key in ("f1_short", "f1_flat", "f1_long")} == {
		"f1_short": 0.7,
		"f1_flat": 0.8,
		"f1_long": 0.9,
	}


@pytest.mark.parametrize("keyword", ["data_fingerprint", "config_fingerprint"])
def test_save_baseline_artifact_rejects_missing_required_fingerprint(tmp_path, keyword):
	kwargs = {
		"data_fingerprint": "data-456",
		"config_fingerprint": "config-789",
	}
	kwargs[keyword] = ""

	with pytest.raises(ValueError, match=keyword):
		save_baseline_artifact(
			{},
			artifact_dir=tmp_path,
			period_start="2025-01-01",
			period_end="2025-01-31",
			**kwargs,
		)