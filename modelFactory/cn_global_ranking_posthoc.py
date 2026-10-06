"""Diagnostic exploratoire, NON pré-enregistré, du momentum inversé CN."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from modelFactory.cn_global_ranking_aggregate import _find_run
from modelFactory.cn_global_ranking_walk_forward import (
    DEFAULT_CONFIG,
    DEFAULT_OUTPUT,
    RankingProtocol,
    _sha,
    ranking_metrics,
)
from modelFactory.cn_oracle_walk_forward import AUDIT_PATH


def diagnose(*, config_path: Path = DEFAULT_CONFIG, root: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    protocol = RankingProtocol.load(config_path)
    from modelFactory import cn_global_ranking_walk_forward as runner

    config_sha, code_sha, audit_sha = _sha(config_path), _sha(Path(runner.__file__)), _sha(AUDIT_PATH)
    results = {}
    for horizon in protocol.raw["horizons"]:
        frames = []
        for semester in protocol.raw["test_semesters"]:
            item = _find_run(root, horizon=horizon, semester=semester, model="lightgbm",
                             config_sha=config_sha, code_sha=code_sha, audit_sha=audit_sha)
            if item is None:
                raise RuntimeError(f"OOS H{horizon}/{semester} manquant")
            path, _ = item
            frames.append(pd.read_parquet(path))
        frame = pd.concat(frames, ignore_index=True)
        frame["reversal_score"] = -frame["baseline_score"]
        paired = frame.loc[frame["target_quality_valid"] & frame["baseline_score"].notna()]
        oracle = paired.loc[paired["oracle_top20"]]
        pct = float(protocol.raw["evaluation"]["conditional_tail_pct"])
        results[str(horizon)] = {
            "model": ranking_metrics(oracle, score="rank_score", tail_pct=pct),
            "momentum": ranking_metrics(oracle, score="baseline_score", tail_pct=pct),
            "reversal_posthoc": ranking_metrics(oracle, score="reversal_score", tail_pct=pct),
        }
    return {
        "status": "POST_HOC_DIAGNOSTIC_NOT_A_GATE", "market_code": "CN_A",
        "reason": "Le momentum fixé avant campagne a un IC négatif ; inversion exploratoire après lecture OOS.",
        "serving_enabled": False, "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = diagnose(config_path=args.config, root=args.output_root)
    path = args.output_root / "posthoc_reversed_momentum_diagnostic.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
