"""Revue gratuite stricte des blocages fiscaux FR."""
import argparse
import json
from pathlib import Path

from service.fr.free_blocker_review import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({k: v for k, v in result.items() if k not in ("sources", "input_hashes")}))


if __name__ == "__main__":
    main()
