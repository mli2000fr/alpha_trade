"""Read-only, reproducible plan for the four CN research catalog sections."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from service.market.cn_catalog_preflight_17d import RESEARCH_BATCHES, ROOT, inspect


def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return data


def prepare(*, us_batch_path: Path, cn_batch_path: Path, quality_root: Path) -> dict:
    """Validate the proposed move in memory; never edit catalogs or Windows tasks."""
    preflight = inspect(us_batch_path=us_batch_path, cn_batch_path=cn_batch_path,
                        quality_root=quality_root)
    us, cn = _load(us_batch_path), _load(cn_batch_path)
    blockers = list(preflight["blockers"])
    parity = {}
    for name in RESEARCH_BATCHES:
        source = us.get(name)
        if not isinstance(source, dict) or name in cn:
            blockers.append(f"cannot_prepare_unique_move:{name}")
            continue
        proposed = dict(source)
        proposed["market_code"] = "CN_A"
        proposed["database_alias"] = "cn_primary"
        business_fields = {key: value for key, value in proposed.items()
                           if key not in {"market_code", "database_alias"}}
        parity[name] = {
            "business_fields_unchanged": business_fields == source,
            "added_identity": {"market_code": proposed["market_code"],
                               "database_alias": proposed["database_alias"]},
            "field_count": len(source),
        }
        if not parity[name]["business_fields_unchanged"]:
            blockers.append(f"business_field_drift:{name}")

    return {
        "status": "HOLD" if blockers else "PREPARED_MANUAL_SCHEDULER_CHECK_REQUIRED",
        "blockers": sorted(set(blockers)),
        "preflight_status": preflight["status"],
        "source_catalog_sha256": hashlib.sha256(us_batch_path.read_bytes()).hexdigest(),
        "destination_catalog_sha256": hashlib.sha256(cn_batch_path.read_bytes()).hexdigest(),
        "sections": parity,
        "task_names_unchanged": True,
        "scheduler_actions_verified": False,
        "catalogs_modified": False,
        "scheduler_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--us-batches", type=Path, default=ROOT / "batch.yaml")
    parser.add_argument("--cn-batches", type=Path, default=ROOT / "batch_cn.yaml")
    parser.add_argument("--quality-root", type=Path,
                        default=ROOT / "artifacts/research/cn_daily_quality_17c")
    parser.add_argument("--output", type=Path, help="Optional new JSON report; never overwrite")
    args = parser.parse_args()
    report = prepare(us_batch_path=args.us_batches, cn_batch_path=args.cn_batches,
                     quality_root=args.quality_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
