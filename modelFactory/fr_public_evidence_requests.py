"""Collecte publique bornée et dossier précis de preuves FR manquantes."""
import argparse
import json
from pathlib import Path

from service.fr.public_evidence_requests import run
from service.fr.universe_contract_6a import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qualification", type=Path, default=ROOT / "artifacts/fr/research/economic_qualification_12a/qualification-20261004-v2")
    parser.add_argument("--evidence", type=Path, default=ROOT / "artifacts/fr/research/execution_evidence_12c/qualification-20261004-v4")
    args = parser.parse_args()
    result = run(args.output, args.qualification, args.evidence)
    print(json.dumps({k: v for k, v in result.items() if k not in ("sources", "input_hashes", "output_hashes")}))


if __name__ == "__main__":
    main()
