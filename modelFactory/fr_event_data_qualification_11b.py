"""CLI for research-only FR event-source qualification."""
import argparse
import json
from pathlib import Path

from service.fr.event_data_qualification_11b import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--identities", type=Path, default=Path("artifacts/fr/sprint6c_reference/identities.jsonl.gz"))
    parser.add_argument("--guidance", type=Path, default=Path("artifacts/research/fr_guidance_feasibility/pilot-20260917-124430"))
    parser.add_argument("--oracle-pool", type=Path)
    args = parser.parse_args()
    report = run(args.output, args.identities, args.guidance, args.oracle_pool)
    print(json.dumps({"status": report["status"], "amf": report["amf"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
