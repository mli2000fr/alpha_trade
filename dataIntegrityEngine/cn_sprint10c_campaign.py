"""Exécuter/reprendre la campagne ranking CN Sprint 10-C."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from modelFactory.cn_global_ranking_aggregate import _find_run, aggregate
from modelFactory.cn_global_ranking_walk_forward import (
    DEFAULT_CONFIG,
    DEFAULT_OUTPUT,
    RankingProtocol,
    _sha,
    run,
)
from modelFactory.cn_oracle_walk_forward import AUDIT_PATH

LOGGER = logging.getLogger(__name__)


def campaign(*, config_path: Path = DEFAULT_CONFIG, output_root: Path = DEFAULT_OUTPUT,
             horizon: int | None = None, model: str | None = None) -> dict[str, object]:
    protocol = RankingProtocol.load(config_path)
    from modelFactory import cn_global_ranking_walk_forward as runner

    config_sha, code_sha, audit_sha = _sha(config_path), _sha(Path(runner.__file__)), _sha(AUDIT_PATH)
    horizons = [horizon] if horizon is not None else protocol.raw["horizons"]
    models = [model] if model is not None else protocol.raw["models"]
    if any(item not in protocol.raw["horizons"] for item in horizons):
        raise ValueError("Horizon CN hors protocole")
    if any(item not in protocol.raw["models"] for item in models):
        raise ValueError("Modèle CN hors protocole")
    completed = skipped = 0
    for current_horizon in horizons:
        for semester in protocol.raw["test_semesters"]:
            for current_model in models:
                existing = _find_run(output_root, horizon=current_horizon, semester=semester,
                                     model=current_model, config_sha=config_sha,
                                     code_sha=code_sha, audit_sha=audit_sha)
                if existing is not None:
                    skipped += 1
                    LOGGER.info("CN Ranking SKIP H%s %s %s: artefact vérifié", current_horizon,
                                semester, current_model)
                    continue
                LOGGER.info("CN Ranking START H%s %s %s", current_horizon, semester, current_model)
                report = run(horizon=current_horizon, semester=semester, model_name=current_model,
                             config_path=config_path, output_root=output_root)
                completed += 1
                LOGGER.info("CN Ranking DONE H%s %s %s uplift=%+.4f", current_horizon,
                            semester, current_model,
                            report["metrics"]["oracle_top20"]["tail_precision_uplift"])
    summary = aggregate(config_path=config_path, root=output_root)
    target = output_root / "sprint10c_global_ranking_summary.json"
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"completed": completed, "skipped_verified": skipped,
            "status": summary["status"], "missing": len(summary["missing"]),
            "summary": str(target)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--horizon", type=int)
    parser.add_argument("--model", choices=["lightgbm", "catboost"])
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    print(json.dumps(campaign(config_path=args.config, output_root=args.output_root,
                              horizon=args.horizon, model=args.model), ensure_ascii=False))


if __name__ == "__main__":
    main()
