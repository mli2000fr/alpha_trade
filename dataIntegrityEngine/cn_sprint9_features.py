"""Construire le panel de features CN_A du Sprint 9, sans entraîner de modèle."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from modelFactory.cn_feature_panel import build_panel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--universe-policy", type=Path)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    options = {"start": args.start_date, "end": args.end_date}
    if args.profile is not None:
        options["profile_path"] = args.profile
    if args.universe_policy is not None:
        options["universe_policy_path"] = args.universe_policy
    if args.output_root is not None:
        options["output_root"] = args.output_root
    print(json.dumps(build_panel(**options), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
