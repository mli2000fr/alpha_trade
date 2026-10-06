import json
from pathlib import Path

import pytest

from modelFactory import cn_margin_features_15b5 as builder
from modelFactory.cn_margin_features_audit_15b5 import run
from modelFactory.cn_oracle_walk_forward import _sha


def report():
    return {"status": "PASS_FEATURE_JOIN_PROXY_ONLY_PROTOCOL_HISTORY_BLOCKED",
            "implementation_sha256": _sha(Path(builder.__file__)), "training_ready": False,
            "strict_ml_allowed": False, "training_executed": False,
            "label_metadata_never_inputs": ["future_return"],
            "model_feature_columns": {"BASE": ["return_20"]},
            "features": {"years": {}}, "folds": {}}


@pytest.mark.parametrize("corruption", ["training", "label", "incomplete"])
def test_audit_rejects_unsafe_or_incomplete_reports(tmp_path, corruption):
    item = report()
    if corruption == "training":
        item["training_executed"] = True
    if corruption == "label":
        item["model_feature_columns"]["BASE"].append("future_return")
    (tmp_path / "report.json").write_text(json.dumps(item), encoding="utf-8")
    with pytest.raises(ValueError):
        run(tmp_path)
