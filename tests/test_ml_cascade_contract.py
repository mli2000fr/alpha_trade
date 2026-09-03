from __future__ import annotations

import json

from common.ml_cascade_contract import (
    infer_oracle_only_cascade_mode,
    load_serving_directional_bundle_manifest,
)


def _write_manifest(root, *, serving_ready: bool = True, paired_symbols: int = 2):
    batch = root / "batch-directional"
    batch.mkdir()
    (batch / "cascade_manifest.json").write_text(
        json.dumps({
            "batch_id": "batch-directional",
            "cascade_type": "oracle_extreme_plus_per_symbol_directional",
            "status": "completed",
            "serving_ready": serving_ready,
            "oracle": {"status": "completed"},
            "coverage": {"paired_symbols": paired_symbols},
        }),
        encoding="utf-8",
    )
    return batch


def test_serving_directional_manifest_is_authoritative(tmp_path):
    _write_manifest(tmp_path)

    manifest = load_serving_directional_bundle_manifest(tmp_path, "batch-directional")

    assert manifest is not None
    assert manifest["serving_ready"] is True


def test_infer_directional_mode_for_complete_bundle(tmp_path):
    _write_manifest(tmp_path)

    mode = infer_oracle_only_cascade_mode(
        tmp_path, "batch-directional", oracle_rows=100, global_rank_rows=0,
    )

    assert mode == "extreme_gate_directional"


def test_infer_legacy_mode_without_servable_bundle(tmp_path):
    _write_manifest(tmp_path, serving_ready=False)

    mode = infer_oracle_only_cascade_mode(
        tmp_path, "batch-directional", oracle_rows=100, global_rank_rows=0,
    )

    assert mode == "extreme_gate"


def test_no_auto_mode_when_global_ranks_exist(tmp_path):
    _write_manifest(tmp_path)

    mode = infer_oracle_only_cascade_mode(
        tmp_path, "batch-directional", oracle_rows=100, global_rank_rows=10,
    )

    assert mode is None
