"""Sprint 14-C: fail-closed launcher contract for a CN_A research replay.

The frozen Sprint 13-B replay is deliberately not a production backtest. The
operator can select one pre-registered semester and one protocol cell only.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from database.router import get_market_engine, resolve_database_route
from ihm.services.pipeline_runner import PROJECT_ROOT

PROTOCOL_PATH = PROJECT_ROOT / "config/research_cn/sprint13a_economic_preflight.yaml"
EVIDENCE_PATH = PROJECT_ROOT / "artifacts/cn/corporate_actions/sprint13a2/evidence.json"
DECISION_PATH = PROJECT_ROOT / "artifacts/cn/economic/sprint13c/decision/decision-d1745c4c96351267/report.json"
OUTPUT_PARENT = PROJECT_ROOT / "artifacts/ihm_backtesting_runs/cn-research-replay"


@dataclass(frozen=True, slots=True)
class CNResearchReplayOptions:
    market_code: str = "CN_A"
    database_alias: str = "cn_primary"
    semester: str = "2024H1"
    policy: str = "oracle_all"
    seed: int = 0
    scenario: str = "base"
    cost_profile: str = "cn_a_research"
    output_root: str | None = None


def replay_choices() -> dict[str, tuple]:
    """Read the frozen protocol; never populate choices from US batches."""
    from modelFactory.cn_economic_preflight import load_protocol
    from modelFactory.cn_economic_replay_13b import POLICY_NAMES

    protocol = load_protocol(PROTOCOL_PATH)
    if protocol.get("market_code") != "CN_A" or protocol.get("database_alias") != "cn_primary":
        raise ValueError("Protocole économique CN incompatible")
    return {
        "semesters": tuple(protocol["test_semesters"]),
        "policies": tuple(POLICY_NAMES),
        "seeds": tuple(protocol["portfolio"]["tie_break_seeds"]),
        "scenarios": tuple(protocol["fill_scenarios"]),
        "cost_profiles": tuple(protocol["cost_profiles"]),
    }


def validate_replay_options(options: CNResearchReplayOptions, *, require_output: bool = False) -> None:
    """Reject cross-market settings and all values outside the frozen protocol."""
    if options.market_code != "CN_A" or options.database_alias != "cn_primary":
        raise ValueError("Replay CN incompatible avec le marché ou la base demandée")
    route = resolve_database_route(options.database_alias, options.market_code)
    if route.database != "alpha_trade_cn":
        raise ValueError("La route CN doit viser exactement alpha_trade_cn")
    choices = replay_choices()
    for key, value in (
        ("semesters", options.semester),
        ("policies", options.policy),
        ("seeds", options.seed),
        ("scenarios", options.scenario),
        ("cost_profiles", options.cost_profile),
    ):
        if value not in choices[key]:
            raise ValueError(f"Paramètre {key} hors protocole CN : {value}")
    if require_output:
        if not options.output_root:
            raise ValueError("Répertoire de sortie CN absent")
        target = Path(options.output_root).resolve()
        if OUTPUT_PARENT.resolve() not in target.parents:
            raise ValueError("La sortie du replay CN doit rester dans les runs IHM CN")


def preflight_cn_replay(options: CNResearchReplayOptions) -> None:
    """Check OOS lineage, evidence and real schema before any subprocess starts."""
    from modelFactory.cn_economic_replay_13b import _source
    from modelFactory.cn_portfolio_replay import load_verified_action_evidence

    validate_replay_options(options)
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    if (
        decision.get("decision") != "NO_PRODUCTION_GO_INSPECTED_OOS"
        or decision.get("serving_enabled") is not False
        or decision.get("live_enabled") is not False
        or decision.get("economic_go_allowed") is not False
    ):
        raise ValueError("Décision économique CN absente ou incompatible avec la recherche")
    source_path, source = _source(options.semester)
    if not source_path.is_file() or not source.get("predictions_sha256"):
        raise ValueError("Prédictions Ranking OOS CN absentes ou non vérifiées")
    load_verified_action_evidence(EVIDENCE_PATH)
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT DATABASE()")).scalar_one() != "alpha_trade_cn":
                raise ValueError("Connexion réelle hors alpha_trade_cn")
    finally:
        engine.dispose()


def build_cn_replay_command(options: CNResearchReplayOptions) -> list[str]:
    """Only the dedicated CN module, with an IHM-owned output directory."""
    validate_replay_options(options, require_output=True)
    return [
        sys.executable,
        "-u",
        "-m",
        "ihm.services.cn_replay_worker",
        "--market-code",
        "CN_A",
        "--database-alias",
        "cn_primary",
        "--semesters",
        options.semester,
        "--policies",
        options.policy,
        "--seeds",
        str(options.seed),
        "--scenarios",
        options.scenario,
        "--cost-profiles",
        options.cost_profile,
        "--evidence",
        str(EVIDENCE_PATH),
        "--output-root",
        str(Path(options.output_root).resolve()),
    ]
