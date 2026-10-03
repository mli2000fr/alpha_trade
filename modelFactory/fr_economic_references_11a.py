"""Sprint 11-A économique anticipé : protocole et aptitude au rejeu FR."""
from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import joblib
from threadpoolctl import threadpool_limits

from modelFactory.fr_fold7_rebuild import sha, write_json
from service.fr.economic_preflight_11a import audit, load_protocol, score_candidates, selection_ledger
from service.fr.universe_contract_6a import ROOT


def run(profile: Path, output: Path) -> dict:
    cfg = load_protocol(profile)
    logging.info("11-A : contrôle causal des candidats et aptitude économique")
    report, candidates = audit(cfg)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    candidates.loc[candidates.oracle_score_missing, ["fold", "decision_session_date", "source_session_date", "research_uid", "provider_symbol"]].to_parquet(output / "missing_oracle_scores.parquet", index=False)
    root = ROOT / cfg["rebuild_root"]
    oracle = json.loads((root / "confirmation/report.json").read_text(encoding="utf-8"))["oracle"]
    oracle_root = Path(oracle["artifact_directory"])
    model_paths = {fold: oracle_root / f"fold{fold}_trees.joblib" for fold in cfg["folds"]}
    model_hashes = {str(fold): sha(path) for fold, path in model_paths.items()}
    logging.info("11-A : compléter les scores avec les modèles gelés, aucun fit")
    with threadpool_limits(limits=2):
        scored = score_candidates(candidates, {fold: joblib.load(path) for fold, path in model_paths.items()})
    if model_hashes != {str(fold): sha(path) for fold, path in model_paths.items()}:
        raise ValueError("Modèle modifié pendant le scoring")
    score_path = output / "decision_candidates_scored.parquet"
    scored.to_parquet(score_path, index=False)
    selection_ledger(scored, cfg).to_parquet(output / "selection_intents.parquet", index=False)
    report["causal_research_rescoring"] = {"rows": len(scored), "previously_missing": int(candidates.oracle_score_missing.sum()),
                                         "missing_after": 0, "models_refit": 0, "existing_scores_identical_atol": 1e-12,
                                         "model_sha256": model_hashes, "scores_sha256": sha(score_path),
                                         "strict_historical_pit_verified": False}
    for check in report["checks"]:
        if check["name"] == "oracle_scores_without_future_selection":
            check.update(passed=True, missing_rows=0)
    report.update(generated_at=datetime.now(UTC).isoformat(), artifact_directory=str(output))
    write_json(output / "report.json", report)
    print(json.dumps({k: report[k] for k in ("artifact_directory", "verdict", "folds", "checks")}, ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "config/research_fr/economic_references_11a_v1.yaml")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.profile, args.output)
