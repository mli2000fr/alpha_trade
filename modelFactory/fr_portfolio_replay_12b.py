"""CLI du rejeu FR ; audit par défaut, tape qualifiée explicite pour les fills."""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

import pandas as pd

from modelFactory.fr_fold7_rebuild import sha
from service.fr.execution_costs import load_cost_profile
from service.fr.portfolio_replay_12b import ReplayBlocked, replay
from service.fr.universe_contract_6a import ROOT


def write(path, payload):
    def encode(value):
        if isinstance(value, Decimal):
            return str(value)
        raise TypeError(type(value).__name__)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=encode), encoding="utf-8")


def audit(preflight: Path, qualification: Path, output: Path) -> dict:
    """Read-only evidence gate; never filters the pool by future path goodness."""
    report_path = preflight / "report.json"
    prior = json.loads(report_path.read_text(encoding="utf-8"))
    scored = preflight / "decision_candidates_scored.parquet"
    if sha(scored) != prior["causal_research_rescoring"]["scores_sha256"]:
        raise ValueError("Scores du préflight modifiés")
    qualified = json.loads((qualification / "report.json").read_text(encoding="utf-8"))
    if qualified["preflight_report_sha256"] != sha(report_path):
        raise ValueError("Qualification non reliée au préflight")
    paths = pd.read_parquet(qualification / "holding_path_qualification.parquet")
    if len(paths) != qualified["candidate_paths"] or paths.duplicated(["fold", "research_uid", "entry_session"]).any():
        raise ValueError("Chemins incomplets/dupliqués")
    candidates = pd.read_parquet(scored, columns=["fold", "research_uid", "decision_session_date"])
    keys = candidates.rename(columns={"decision_session_date": "entry_session"})
    joined = keys.merge(paths[["fold", "research_uid", "entry_session"]],
                        on=["fold", "research_uid", "entry_session"], how="outer", indicator=True, validate="one_to_one")
    if not joined["_merge"].eq("both").all() or keys.entry_session.gt("2025-12-31").any():
        raise ValueError("Chemins et population causale divergents")
    # These are repair requests, NOT candidate removals in a portfolio replay.
    paths.to_parquet(output / "execution_evidence_requests.parquet", index=False)
    ready = bool(len(paths)) and bool(paths.economic_return_ready.all())
    result = {"status": "BLOCKED_EXECUTION_EVIDENCE", "candidate_paths": len(paths),
              "qualified_paths": int(paths.economic_return_ready.sum()),
              "all_paths_ready": ready, "net_pnl": None, "executed_orders": 0,
              "blockers": ["ISIN_DATE_TTF_MAPPING", "OFFICIAL_CORPORATE_ACTION_COVERAGE",
                           "VERIFIED_PRICE_AND_EXECUTION_STATUS", "EXPLICIT_SETTLEMENT_CALENDAR"],
              "path_states": paths.provider_state.value_counts().to_dict(),
              "preflight_report_sha256": sha(report_path), "scores_sha256": sha(scored),
              "qualification_report_sha256": sha(qualification / "report.json"),
              "requests_sha256": sha(output / "execution_evidence_requests.parquet"),
              "implementation_sha256": sha(ROOT / "service/fr/portfolio_replay_12b.py"),
              "future_path_filtering": False, "canonical_writes": False,
              "serving_enabled": False, "models_refit": 0, "confirmation_2026_evaluated": False}
    write(output / "report.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--input", type=Path, help="Tape JSON normalisée/qualifiée ; sinon audit sans fills")
    parser.add_argument("--preflight", type=Path, default=ROOT / "artifacts/fr/research/economic_references_11a/preflight-20261004-v2")
    parser.add_argument("--qualification", type=Path, default=ROOT / "artifacts/fr/research/economic_qualification_12a/qualification-20261004-v2")
    parser.add_argument("--cost-profile", type=Path, default=ROOT / "config/markets/fr_execution_research_v1.yaml")
    parser.add_argument("--eligibility", type=Path, default=ROOT / "config/taxes/fr_ttf_eligibility.yaml")
    parser.add_argument("--stress-multiplier", type=Decimal, default=Decimal(1))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.input:
        cfg = load_cost_profile(args.cost_profile)
        tape = json.loads(args.input.read_text(encoding="utf-8"))
        try:
            report = replay(tape, cfg, args.eligibility, stress_multiplier=args.stress_multiplier)
            ledger = report.pop("ledger")
        except ReplayBlocked as exc:
            ledger = exc.ledger
            report = {"status": "BLOCKED_EXECUTION_EVIDENCE", "reason": str(exc), "net_pnl": None,
                      "partial_ledger_not_performance": True, "economic_go_allowed": False,
                      "canonical_writes": False, "serving_enabled": False}
        write(args.output / "ledger.json", ledger)
        report.update(input_sha256=sha(args.input), cost_profile_sha256=sha(args.cost_profile),
                      eligibility_sha256=sha(args.eligibility), stress_multiplier=str(args.stress_multiplier),
                      implementation_sha256=sha(ROOT / "service/fr/portfolio_replay_12b.py"))
        write(args.output / "report.json", report)
    else:
        report = audit(args.preflight, args.qualification, args.output)
    print(json.dumps({"status": report["status"], "output": str(args.output), "net_pnl": report["net_pnl"]}, default=str))
    if report["status"].startswith("BLOCKED"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
