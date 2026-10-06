"""Read-only Sprint 17-A audit of CN batch isolation and operations readiness."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_RESEARCH = {
    "cn_dragon_tiger_after_close", "cn_dragon_tiger_before_open",
    "cn_oracle_prospective_daily", "cn_dragon_tiger_daily_match",
}


def inspect(*, us_batch_path: Path, cn_batch_path: Path) -> dict:
    us = yaml.safe_load(us_batch_path.read_text(encoding="utf-8")) or {}
    cn = yaml.safe_load(cn_batch_path.read_text(encoding="utf-8")) or {}
    if not isinstance(us, dict) or not isinstance(cn, dict):
        raise ValueError("Batch configuration must be a YAML mapping")
    research = {name: cfg for name, cfg in us.items()
                if name.startswith("cn_") and isinstance(cfg, dict)}
    operational = {name: cfg for name, cfg in cn.items()
                   if name.startswith("cn_") and isinstance(cfg, dict)}
    findings: list[dict] = []

    def finding(code: str, severity: str, detail: str) -> None:
        findings.append({"code": code, "severity": severity, "detail": detail})

    all_cn_names = set(research) | set(operational)
    if not all_cn_names >= REQUIRED_RESEARCH:
        finding("CN_RESEARCH_BATCH_MISSING", "CRITICAL",
                f"Missing: {sorted(REQUIRED_RESEARCH - all_cn_names)}")
    if research:
        finding("CN_RESEARCH_IN_LEGACY_BATCH_CATALOG", "WARNING",
                "Active CN research tasks remain in batch.yaml; migrate only after a verified cutover, not before the October decision.")
    if set(research) & set(operational):
        finding("DUPLICATE_CN_BATCH_NAME", "CRITICAL",
                f"Names in both catalogs: {sorted(set(research) & set(operational))}")
    if str((cn.get("defaults") or {}).get("database_alias")) != "cn_primary":
        finding("CN_DATABASE_ROUTE_UNSAFE", "CRITICAL", "batch_cn.yaml does not pin cn_primary")
    if str((cn.get("defaults") or {}).get("timezone")) != "Asia/Shanghai":
        finding("CN_TIMEZONE_UNSAFE", "CRITICAL", "batch_cn.yaml does not pin Asia/Shanghai")
    d9_active = bool((research.get("cn_oracle_prospective_daily")
                      or operational.get("cn_oracle_prospective_daily") or {}).get("enabled"))
    generic_active = bool(operational.get("cn_daily_market_data_sync", {}).get("enabled"))
    if d9_active and generic_active:
        finding("CN_DUPLICATE_CANONICAL_DAILY_OWNER", "CRITICAL",
                "D9 and the generic CN daily collector are both enabled; only D9 may own prospective canonical writes.")
    elif not d9_active and not generic_active:
        finding("CN_CANONICAL_DAILY_SYNC_DISABLED", "WARNING",
                "Neither D9 nor the generic CN daily collector is enabled.")
    if not (operational.get("cn_staging_quality_daily", {}).get("enabled")
            or operational.get("cn_daily_quality_17c", {}).get("enabled")):
        finding("CN_STAGING_QUALITY_DISABLED", "WARNING",
                "No recurring CN quality-control batch is enabled in batch_cn.yaml.")
    cn_backups = {name: cfg for name, cfg in {**operational, **research}.items()
                  if "backup" in name and cfg.get("enabled")}
    if not cn_backups:
        finding("CN_BACKUP_NOT_SCHEDULED", "CRITICAL",
                "No active CN database/artifact backup is declared in either batch catalog.")
    for name, cfg in research.items():
        if cfg.get("enabled") and cfg.get("status") == "RESEARCH_ONLY" and not cfg.get("timezone"):
            finding("CN_RESEARCH_TIMEZONE_MISSING", "CRITICAL", f"{name} has no explicit timezone")
    for name in REQUIRED_RESEARCH & set(operational):
        cfg = operational[name]
        if cfg.get("market_code") != "CN_A" or cfg.get("database_alias") != "cn_primary":
            finding("CN_RESEARCH_ROUTE_UNSAFE", "CRITICAL", f"{name} must route to CN_A/cn_primary")
        if cfg.get("enabled") and cfg.get("status") == "RESEARCH_ONLY" and not cfg.get("timezone"):
            finding("CN_RESEARCH_TIMEZONE_MISSING", "CRITICAL", f"{name} has no explicit timezone")
    return {
        "status": "OPERATIONAL_GAPS_PRESENT" if findings else "CONFIGURATION_GATES_PRESENT",
        "audited_at_utc": datetime.now(UTC).isoformat(),
        "us_batch_config": str(us_batch_path.resolve()),
        "cn_batch_config": str(cn_batch_path.resolve()),
        "cn_research_batches_in_batch_yaml": sorted(research),
        "cn_operational_batches_in_batch_cn_yaml": sorted(operational),
        "enabled_cn_research": sorted(name for name, cfg in research.items() if cfg.get("enabled")),
        "enabled_cn_operational": sorted(name for name, cfg in operational.items() if cfg.get("enabled")),
        "findings": findings,
        "database_modified": False, "training_performed": False,
        "serving_changed": False, "scheduler_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--us-batches", type=Path, default=ROOT / "batch.yaml")
    parser.add_argument("--cn-batches", type=Path, default=ROOT / "batch_cn.yaml")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite CN operations audit: {args.output}")
    report = inspect(us_batch_path=args.us_batches, cn_batch_path=args.cn_batches)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"status": report["status"], "findings": len(report["findings"]),
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
