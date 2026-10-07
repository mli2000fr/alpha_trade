"""Read-only readiness check before moving the four CN research batch sections."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_BATCHES = (
    "cn_dragon_tiger_before_open",
    "cn_dragon_tiger_daily_match",
    "cn_dragon_tiger_after_close",
    "cn_oracle_prospective_daily",
)
FIRST_ELIGIBLE_SESSION = date(2026, 10, 8)
REQUIRED_QUALITY_CHECKS = {
    "manifest_nonempty", "chunks_complete", "d9_owner_completed",
    "open_session_canonical", "equity_bar_coverage", "required_indices",
    "unique_bars", "invalid_ohlc", "suspended_with_volume",
    "missing_lineage", "future_lineage", "preclose_lineage",
    "daily_staging_to_canonical", "index_staging_complete",
    "factors_promoted", "limit_coverage", "unknown_limit_policies",
    "oracle_next_decision", "d6_before_open_snapshot",
    "d6_after_close_snapshot", "d10_outcome_blind_match",
}


def _load(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return value


def _latest_quality_report(root: Path) -> dict | None:
    folder = root / "runs"
    for path in sorted(folder.glob("run-*.json"), reverse=True):
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError(f"Expected JSON object: {path}")
        try:
            session = date.fromisoformat(str(report.get("session")))
        except ValueError:
            continue
        if session >= FIRST_ELIGIBLE_SESSION:
            return {"path": str(path.resolve()), "report": report}
    return None


def _complete_real_cycle(report: dict) -> bool:
    evidence = report.get("evidence") or {}
    checks = report.get("checks") or []
    return bool(
        report.get("status") == "COMPLETED"
        and report.get("failed_count") == 0
        and report.get("warning_count") == 0
        and report.get("finished_at_utc")
        and report.get("database_modified") is False
        and isinstance(checks, list) and checks
        and all(isinstance(item, dict) and item.get("status") == "PASS" for item in checks)
        and {item["name"] for item in checks} >= REQUIRED_QUALITY_CHECKS
        and (evidence.get("d9_run") or {}).get("status") == "COMPLETED_RESEARCH_ONLY"
        and (evidence.get("d10_run") or {}).get("status") == "COMPLETED_RESEARCH_ONLY"
        and evidence.get("d6_before") is not None
        and evidence.get("d6_after") is not None
    )


def inspect(*, us_batch_path: Path, cn_batch_path: Path, quality_root: Path) -> dict:
    """Inspect configuration and first real quality evidence; never mutate tasks or DB."""
    us, cn = _load(us_batch_path), _load(cn_batch_path)
    sections = {}
    blockers = []
    for name in RESEARCH_BATCHES:
        in_us, in_cn = isinstance(us.get(name), dict), isinstance(cn.get(name), dict)
        sections[name] = "DUPLICATE" if in_us and in_cn else (
            "batch.yaml" if in_us else "batch_cn.yaml" if in_cn else "MISSING"
        )
        if in_us and in_cn:
            blockers.append(f"duplicate_section:{name}")
        elif not in_us and not in_cn:
            blockers.append(f"missing_section:{name}")
        else:
            cfg = (us if in_us else cn)[name]
            if not cfg.get("enabled") or cfg.get("status") != "RESEARCH_ONLY":
                blockers.append(f"inactive_research_batch:{name}")
            if in_cn and (cfg.get("market_code") != "CN_A"
                          or cfg.get("database_alias") != "cn_primary"):
                blockers.append(f"unsafe_cn_route:{name}")

    if (cn.get("defaults") or {}).get("database_alias") != "cn_primary":
        blockers.append("unsafe_cn_default_database")
    if cn.get("cn_daily_market_data_sync", {}).get("enabled"):
        blockers.append("duplicate_canonical_collector")
    quality_cfg = cn.get("cn_daily_quality_17c") or {}
    if not quality_cfg.get("enabled") or quality_cfg.get("status") != "ACTIVE":
        blockers.append("daily_quality_inactive")

    latest = _latest_quality_report(quality_root)
    quality = None
    if latest:
        report = latest["report"]
        quality = {
            "session": report.get("session"),
            "status": report.get("status"),
            "failed_count": report.get("failed_count"),
            "warning_count": report.get("warning_count"),
            "path": latest["path"],
        }
    if not latest or not _complete_real_cycle(latest["report"]):
        blockers.append("first_real_d6_d9_d10_quality_cycle_missing")

    catalog_blockers = [item for item in blockers if item != "first_real_d6_d9_d10_quality_cycle_missing"]
    return {
        "status": "BLOCKED" if blockers else "CONFIG_AND_FIRST_CYCLE_READY_MANUAL_TASK_CHECK_REQUIRED",
        "sections": sections,
        "quality_cycle": quality,
        "blockers": blockers,
        "catalog_safe": not catalog_blockers,
        "scheduler_actions_verified": False,
        "database_modified": False,
        "scheduler_changed": False,
        "serving_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--us-batches", type=Path, default=ROOT / "batch.yaml")
    parser.add_argument("--cn-batches", type=Path, default=ROOT / "batch_cn.yaml")
    parser.add_argument("--quality-root", type=Path,
                        default=ROOT / "artifacts/research/cn_daily_quality_17c")
    parser.add_argument("--output", type=Path, help="Optional new JSON report; never overwrite")
    args = parser.parse_args()
    report = inspect(us_batch_path=args.us_batches, cn_batch_path=args.cn_batches,
                     quality_root=args.quality_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
