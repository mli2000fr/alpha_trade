"""Dedicated FR research command; output confined to IHM-owned FR runs."""
from pathlib import Path
import sys

from service.fr.research_replay_14b import FRResearchReplayOptions, OUTPUT_PARENT, preflight, validate_options


def build_fr_replay_command(options: FRResearchReplayOptions) -> list[str]:
    validate_options(options, require_output=True)
    return [sys.executable, "-u", "-m", "service.fr.research_replay_14b",
            "--market-code", options.market_code, "--database-alias", options.database_alias,
            "--fold", str(options.fold), "--policy", options.policy, "--variant", options.variant,
            "--tax-scenario", options.tax_scenario, "--cost-scenario", options.cost_scenario,
            "--output-root", str(Path(options.output_root).resolve())]
