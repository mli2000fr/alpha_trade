"""Qualifie les preuves accessibles avant le rejeu économique FR."""
import argparse
import json
from pathlib import Path

from service.fr.execution_evidence_12c import run
from service.fr.universe_contract_6a import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qualification", type=Path, default=ROOT / "artifacts/fr/research/economic_qualification_12a/qualification-20261004-v2")
    args = parser.parse_args()
    report = run(args.output, args.qualification)
    print(json.dumps({k: report[k] for k in ("status", "positive_tax_issuer_years", "unknown_tax_issuer_years", "paths_promoted_to_ready", "net_pnl")}))


if __name__ == "__main__":
    main()
