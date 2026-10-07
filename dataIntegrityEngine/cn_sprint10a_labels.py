"""Construire les labels Oracle CN_A H5/H10/H15/H20, sans entraînement."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from modelFactory.cn_oracle_labels import build_year


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    kwargs = {"year": args.year, "start_date": args.start_date, "end_date": args.end_date}
    if args.config:
        kwargs["config_path"] = args.config
    if args.output_root:
        kwargs["output_root"] = args.output_root
    report = build_year(**kwargs)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
