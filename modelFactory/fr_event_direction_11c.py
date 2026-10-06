"""Run the frozen exploratory FR event-source ablation."""
import argparse
from pathlib import Path

from service.fr.event_direction_11c import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=Path("config/research_fr/event_direction_11c_v1.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.profile, args.output)
    print(report["strict_pit_verdict"], flush=True)


if __name__ == "__main__":
    main()
