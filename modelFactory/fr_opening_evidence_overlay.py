"""Build research-only opening rejection evidence, not an economic backtest."""
import argparse
import json
from pathlib import Path

from service.fr.opening_evidence_overlay import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output)))
