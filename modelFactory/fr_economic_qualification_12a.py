"""Audit ciblé coûts/taxes et opérations sur titres des candidats FR 11-A."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from service.fr.economic_qualification_12a import run
from service.fr.universe_contract_6a import ROOT

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", type=Path, default=ROOT / "artifacts/fr/research/economic_references_11a/preflight-20261004-v2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.preflight, args.output)
    print(json.dumps({k: result[k] for k in ("verdict", "symbols", "candidate_paths", "path_states", "tax_matching_states")}, ensure_ascii=False))
